from __future__ import annotations

import json

import pytest

from backend.app.domains.logistics.services.nl2sql.evaluation_log import (
    InMemoryLogisticsNl2SqlEvaluationLogSink,
    JsonlLogisticsNl2SqlEvaluationLogSink,
    LogisticsNl2SqlEvaluationLogRecord,
    redact_evaluation_text,
    summarize_evaluation_logs,
)


def test_evaluation_log_record_redacts_questions_errors_and_metadata_without_sql_payload() -> None:
    """评估日志只能保留脱敏摘要、SQL hash 与参数 key，不能持久化 SQL/密钥原文。"""

    password_key = "password"
    token_key = "token"
    bearer_value = "bearer-secret-value"
    api_value = "sk-unitsecret123"
    record = LogisticsNl2SqlEvaluationLogRecord.from_pipeline(
        trace_id="trace-001",
        request_id="req-001",
        question=f"2025年发运量 {password_key}=unit-password {token_key}=tok_unitsecret Bearer {bearer_value} {api_value}",
        rewritten_question=f"2025年发运量 {password_key}=unit-password",
        domain="logistics",
        source_system="middle_db",
        status="explain_failed",
        stage="explain",
        error_codes=["sql_execution_executor_failed::explain"],
        error_message=(
            "mysql://demo:pass123@127.0.0.1/db "
            f"{password_key}=unit-password {token_key}=tok_unitsecret Bearer {bearer_value} {api_value}"
        ),
        catalog_ids=["metric:shipment_mw", "table:dws_logistics_detail_union"],
        catalog_versions=["logistics_nl2sql_catalog.v1"],
        sql_hash="a" * 64,
        sql_param_keys=["p0", "p1"],
        validation_errors=[],
        safety_errors=[],
        explain_ok=False,
        trial_ok=False,
        row_count=0,
        sample_row_count=0,
        duration_ms=12,
        pipeline_version="logistics_nl2sql_shadow.v1",
    )

    payload = record.model_dump_json()

    assert "unit-password" not in payload
    assert "tok_unitsecret" not in payload
    assert bearer_value not in payload
    assert api_value not in payload
    assert "pass123" not in payload
    assert "[REDACTED]" in payload
    assert record.sql_hash == "a" * 64
    assert record.sql_param_keys == ["p0", "p1"]
    assert not hasattr(record, "sql")


def test_evaluation_log_redacts_list_metadata_and_sql_like_text() -> None:
    """catalog/error 元数据列表也必须脱敏，不能把候选输入中的密钥或 SQL 原文写入日志。"""

    password_key = "password"
    token_key = "token"
    bearer_value = "bearer-secret-value"
    record = LogisticsNl2SqlEvaluationLogRecord.from_pipeline(
        trace_id="trace-metadata",
        request_id=f"req {password_key}=unit-password",
        question="2025年发运量是多少",
        rewritten_question=None,
        domain=f"logistics {password_key}=unit-password",
        source_system=f"middle_db Bearer {bearer_value}",
        status="validation_failed",
        stage="validation",
        error_codes=[
            f"shadow_strategy_not_sql_direct::{token_key}=tok_unitsecret",
            "raw_sql::SELECT * FROM dws_logistics_detail_union WHERE id = 1",
        ],
        error_message=None,
        catalog_ids=[
            "metric:shipment_mw",
            f"table:{password_key}=unit-password",
            "raw::SELECT * FROM dws_logistics_detail_union",
        ],
        catalog_versions=["logistics_nl2sql_catalog.v1", f"Bearer {bearer_value}"],
        sql_hash="c" * 64,
        sql_param_keys=["p0", f"p1_{token_key}=tok_unitsecret"],
        validation_errors=[f"sqlplan_bad::{password_key}=unit-password"],
        safety_errors=["raw::SELECT * FROM dws_logistics_detail_union"],
        explain_ok=False,
        trial_ok=False,
        row_count=0,
        sample_row_count=0,
        duration_ms=1,
        pipeline_version="logistics_nl2sql_shadow.v1",
        warnings=[f"warn {token_key}=tok_unitsecret"],
    )

    payload = record.model_dump_json()

    assert "unit-password" not in payload
    assert "tok_unitsecret" not in payload
    assert bearer_value not in payload
    assert "SELECT * FROM" not in payload
    assert "[REDACTED]" in payload
    assert "[SQL_REDACTED]" in payload


def test_evaluation_log_rejects_non_hash_sql_hash_values() -> None:
    """sql_hash 字段只允许 64 位哈希，误传 SQL 或密钥文本时必须 fail-closed。"""

    record = LogisticsNl2SqlEvaluationLogRecord.from_pipeline(
        trace_id="trace-bad-hash",
        request_id=None,
        question="2025年发运量是多少",
        rewritten_question=None,
        domain="logistics",
        source_system="middle_db",
        status="success",
        stage="trial",
        error_codes=[],
        error_message=None,
        catalog_ids=[],
        catalog_versions=[],
        sql_hash="SELECT password=unit-password FROM dws_logistics_detail_union",
        sql_param_keys=[],
        validation_errors=[],
        safety_errors=[],
        explain_ok=True,
        trial_ok=True,
        row_count=1,
        sample_row_count=1,
        duration_ms=1,
        pipeline_version="logistics_nl2sql_shadow.v1",
    )

    payload = record.model_dump_json()

    assert record.sql_hash is None
    assert "SELECT" not in payload
    assert "unit-password" not in payload


def test_direct_log_record_construction_sanitizes_hash_sql_dsn_and_secret_text() -> None:
    """直接构造日志记录也必须执行同样的脱敏与 sql_hash 形态校验。"""

    record = LogisticsNl2SqlEvaluationLogRecord(
        pipeline_version="logistics_nl2sql_shadow.v1",
        trace_id="trace-direct",
        request_id="req password=unit-password",
        question="SELECT 1 password=unit-password mysql://demo:pass123@127.0.0.1/db",
        rewritten_question="WITH cte AS (SELECT 1) SELECT * FROM cte",
        domain="logistics",
        source_system="middle_db",
        status="success",
        stage="trial",
        error_codes=["raw::EXPLAIN SELECT 1", "token=tok_unitsecret"],
        error_message="mysql://demo:pass123@127.0.0.1/db Bearer bearer-secret-value",
        catalog_ids=["table:dws_logistics_detail_union"],
        catalog_versions=["logistics_nl2sql_catalog.v1"],
        sql_hash="SELECT password=unit-password FROM dws_logistics_detail_union",
        sql_param_keys=["p0", "token=tok_unitsecret"],
        validation_errors=["api_key=unit-secret"],
        safety_errors=["SELECT 1"],
        explain_ok=True,
        trial_ok=True,
        row_count=-1,
        sample_row_count=-2,
        duration_ms=-3,
        warnings=["sk-unitsecret123"],
    )

    payload = record.model_dump_json()

    assert record.sql_hash is None
    assert record.row_count == 0
    assert record.sample_row_count == 0
    assert record.duration_ms == 0
    assert "SELECT" not in payload
    assert "WITH" not in payload
    assert "mysql://" not in payload
    assert "127.0.0.1" not in payload
    assert "demo" not in payload
    assert "unit-password" not in payload
    assert "tok_unitsecret" not in payload
    assert "bearer-secret-value" not in payload
    assert "unit-secret" not in payload
    assert "sk-unitsecret123" not in payload
    assert "[SQL_REDACTED]" in payload
    assert "[DSN_REDACTED]" in payload


def test_jsonl_log_sink_revalidates_direct_records_before_persisting(tmp_path) -> None:
    """JSONL sink 写入前应二次校验，防止手工构造记录绕过 from_pipeline 安全入口。"""

    record = LogisticsNl2SqlEvaluationLogRecord(
        pipeline_version="logistics_nl2sql_shadow.v1",
        trace_id="trace-jsonl-direct",
        question="mysql://demo:pass123@db.local/prod password=unit-password",
        status="success",
        stage="trial",
        sql_hash="SELECT password=unit-password FROM dws_logistics_detail_union",
    )
    log_path = tmp_path / "shadow" / "eval.jsonl"
    sink = JsonlLogisticsNl2SqlEvaluationLogSink(log_path, root_dir=tmp_path)

    sink.write(record)

    payload = log_path.read_text(encoding="utf-8")
    decoded = json.loads(payload)
    assert decoded["sql_hash"] is None
    assert "SELECT" not in payload
    assert "mysql://" not in payload
    assert "db.local" not in payload
    assert "prod" not in payload
    assert "unit-password" not in payload
    assert "[DSN_REDACTED]" in payload


def test_in_memory_log_sink_collects_records_and_summarizes_status_families() -> None:
    """内存 sink 应支持单测读取与后续按状态汇总成功/失败/跳过数量。"""

    sink = InMemoryLogisticsNl2SqlEvaluationLogSink()
    records = [
        _record("success", "trial"),
        _record("validation_failed", "validation", error_codes=["sqlplan_tables_required"]),
        _record("safety_failed", "safety", error_codes=["sql_safety_select_star_forbidden"]),
        _record("skipped", "candidate", error_codes=["shadow_candidate_missing"]),
    ]

    for record in records:
        sink.write(record)

    summary = summarize_evaluation_logs(sink.records)

    assert [item.status for item in sink.records] == ["success", "validation_failed", "safety_failed", "skipped"]
    assert summary.total == 4
    assert summary.by_status == {"success": 1, "validation_failed": 1, "safety_failed": 1, "skipped": 1}
    assert summary.success_count == 1
    assert summary.failure_count == 2
    assert summary.skipped_count == 1


def test_jsonl_log_sink_writes_sanitized_json_lines_under_controlled_path(tmp_path) -> None:
    """JSONL sink 只写受控路径，并输出可逐行解析的脱敏评估日志。"""

    log_path = tmp_path / "shadow" / "eval.jsonl"
    sink = JsonlLogisticsNl2SqlEvaluationLogSink(log_path, root_dir=tmp_path)
    sink.write(_record("success", "trial", question="查发运量 password=unit-password"))
    sink.write(_record("skipped", "candidate"))

    lines = log_path.read_text(encoding="utf-8").splitlines()
    decoded = [json.loads(line) for line in lines]

    assert len(decoded) == 2
    assert decoded[0]["status"] == "success"
    assert "unit-password" not in lines[0]
    assert decoded[0]["sql_param_keys"] == ["p0"]
    assert "sql" not in decoded[0]


def test_jsonl_log_sink_rejects_paths_outside_controlled_root(tmp_path) -> None:
    """JSONL sink 路径必须被限制在显式 root_dir 下，避免评估日志写出工作区。"""

    outside_path = tmp_path.parent / "outside-eval.jsonl"

    with pytest.raises(ValueError, match="evaluation_log_path_outside_root"):
        JsonlLogisticsNl2SqlEvaluationLogSink(outside_path, root_dir=tmp_path)


def test_redact_evaluation_text_handles_dict_json_secret_shapes() -> None:
    """脱敏函数应覆盖 key=value、Bearer、sk-*、DSN 与 JSON/dict 风格 secret。"""

    password_key = "pass" + "word"
    key_name = "api" + "_key"
    dsn_pw = "pass" + "123"
    openai_like = "sk-" + "unitsecret123"
    text = (
        f"{password_key}=unit-password "
        "Bearer bearer-secret-value "
        f"{openai_like} mysql://demo:{dsn_pw}@127.0.0.1/db "
        f"{{\"{key_name}\":\"json-secret\"}} "
        f"'{key_name}': 'dict-secret'"
    )

    redacted = redact_evaluation_text(text)

    assert "unit-password" not in redacted
    assert "bearer-secret-value" not in redacted
    assert openai_like not in redacted
    assert dsn_pw not in redacted
    assert "json-secret" not in redacted
    assert "dict-secret" not in redacted
    assert "[REDACTED]" in redacted


def _record(
    status: str,
    stage: str,
    *,
    error_codes: list[str] | None = None,
    question: str = "2025年发运量是多少",
) -> LogisticsNl2SqlEvaluationLogRecord:
    """生成测试用评估日志记录。"""

    return LogisticsNl2SqlEvaluationLogRecord.from_pipeline(
        trace_id=f"trace-{status}",
        request_id=None,
        question=question,
        rewritten_question=None,
        domain="logistics",
        source_system="middle_db",
        status=status,
        stage=stage,
        error_codes=error_codes or [],
        error_message=None,
        catalog_ids=["metric:shipment_mw"],
        catalog_versions=["logistics_nl2sql_catalog.v1"],
        sql_hash="b" * 64 if status == "success" else None,
        sql_param_keys=["p0"] if status == "success" else [],
        validation_errors=error_codes or [],
        safety_errors=[],
        explain_ok=status == "success",
        trial_ok=status == "success",
        row_count=1 if status == "success" else 0,
        sample_row_count=1 if status == "success" else 0,
        duration_ms=3,
        pipeline_version="logistics_nl2sql_shadow.v1",
    )

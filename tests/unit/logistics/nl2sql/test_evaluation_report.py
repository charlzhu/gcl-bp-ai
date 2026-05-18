from __future__ import annotations

import json

from backend.app.domains.logistics.services.nl2sql.evaluation_log import LogisticsNl2SqlEvaluationLogRecord
from backend.app.domains.logistics.services.nl2sql.evaluation_report import (
    LogisticsNl2SqlEvaluationReport,
    LogisticsNl2SqlEvaluationReportSampleOutcome,
    LogisticsNl2SqlEvaluationReportTopError,
    build_logistics_nl2sql_evaluation_report,
    render_logistics_nl2sql_evaluation_report_markdown,
)


def test_evaluation_report_summarizes_status_stage_error_and_quality_metrics() -> None:
    """M6 评估报表应确定性汇总状态、阶段、错误码与关键质量指标。"""

    records = [
        _record("success", "trial", sql_hash="a" * 64, explain_ok=True, trial_ok=True),
        _record("skipped", "candidate", error_codes=["shadow_candidate_missing"]),
        _record("unsupported", "candidate", error_codes=["shadow_strategy_not_sql_direct::clarify"]),
        _record("validation_failed", "validation", error_codes=["sqlplan_unknown_metric::unknown_fee"]),
        _record("safety_failed", "safety", error_codes=["sql_safety_select_star_forbidden"], sql_hash="b" * 64),
        _record(
            "explain_failed",
            "explain",
            error_codes=["sql_execution_executor_failed::explain"],
            sql_hash="c" * 64,
        ),
        _record(
            "trial_failed",
            "trial",
            error_codes=["sql_execution_executor_failed::trial"],
            sql_hash="d" * 64,
            explain_ok=True,
        ),
    ]

    report = build_logistics_nl2sql_evaluation_report(records, sample_descriptions={"trace-success": "合法计划成功"})

    assert report.total == 7
    assert report.by_status == {
        "success": 1,
        "skipped": 1,
        "unsupported": 1,
        "validation_failed": 1,
        "safety_failed": 1,
        "explain_failed": 1,
        "trial_failed": 1,
    }
    assert report.by_stage == {"trial": 2, "candidate": 2, "validation": 1, "safety": 1, "explain": 1}
    assert report.by_error_code["sql_execution_executor_failed::trial"] == 1
    assert report.success_count == 1
    assert report.failure_count == 4
    assert report.skipped_count == 1
    assert report.unsupported_count == 1
    assert report.success_rate == 1 / 7
    assert report.fail_closed_count == 4
    assert report.safety_block_count == 1
    assert report.execution_failure_count == 2
    assert report.sql_hash_coverage == 1.0
    assert report.top_errors[0].error_code == "shadow_candidate_missing"
    assert report.sample_outcomes[0].sample_id == "trace-success"
    assert report.sample_outcomes[0].description == "合法计划成功"


def test_evaluation_report_json_and_markdown_do_not_leak_sql_params_or_secrets() -> None:
    """报表 JSON/Markdown 只输出脱敏后的聚合信息，不能泄露 SQL 原文、参数值或密钥。"""

    password_key = "pass" + "word"
    token_key = "tok" + "en"
    bearer_value = "bearer-secret-value"
    records = [
        _record(
            "explain_failed",
            "explain",
            question=f"查发运量 {password_key}=unit-password SELECT * FROM dws_logistics_detail_union",
            error_codes=[f"sql_execution_executor_failed::explain {token_key}=tok_unitsecret"],
            error_message=f"mysql://demo:pass123@db.local/prod Bearer {bearer_value}",
            sql_hash="e" * 64,
            sql_param_keys=["p0", "secret_param_value_should_not_show"],
            warnings=[
                f"warning {password_key}=unit-password",
                "raw sql SELECT * FROM dws_logistics_detail_union WHERE biz_year = 2025",
            ],
        )
    ]

    report = build_logistics_nl2sql_evaluation_report(
        records,
        sample_descriptions={"trace-explain_failed": "脱敏样例"},
        warnings=[f"outer {token_key}=tok_unitsecret"],
    )
    json_payload = json.dumps(report.model_dump(mode="json"), ensure_ascii=False)
    markdown = render_logistics_nl2sql_evaluation_report_markdown(report)
    payload = json_payload + markdown

    assert "SELECT" not in payload
    assert "dws_logistics_detail_union" not in payload
    assert "p0" not in payload
    assert "secret_param_value_should_not_show" not in payload
    assert "unit-password" not in payload
    assert "tok_unitsecret" not in payload
    assert "pass123" not in payload
    assert "db.local" not in payload
    assert bearer_value not in payload
    assert "[REDACTED]" in payload or "[SQL_REDACTED]" in payload or "[DSN_REDACTED]" in payload


def test_evaluation_report_handles_empty_records_as_json_safe_zero_report() -> None:
    """空样本报表应可 JSON 序列化并给出 0 覆盖率，便于离线验收脚本复用。"""

    report = build_logistics_nl2sql_evaluation_report([])

    assert report.total == 0
    assert report.success_rate == 0.0
    assert report.sql_hash_coverage == 0.0
    assert report.sample_outcomes == []
    assert json.loads(report.model_dump_json())["total"] == 0


def test_evaluation_report_direct_model_construction_sanitizes_nested_text_fields() -> None:
    """即使绕过 builder 直接构造报表模型，嵌套文本字段也必须脱敏。"""

    password_key = "pass" + "word"
    token_key = "tok" + "en"
    api_key_name = "api" + "_key"
    openai_like = "sk-" + "unitsecret123"
    report = LogisticsNl2SqlEvaluationReport(
        total=1,
        by_status={f"success {password_key}=unit-password": 1},
        by_stage={"trial SELECT * FROM dws_logistics_detail_union": 1},
        by_error_code={f"err {api_key_name}=unit-secret {openai_like}": 1},
        success_count=1,
        failure_count=0,
        skipped_count=0,
        unsupported_count=0,
        success_rate=1.0,
        fail_closed_count=0,
        safety_block_count=0,
        execution_failure_count=0,
        sql_hash_coverage=1.0,
        top_errors=[LogisticsNl2SqlEvaluationReportTopError(error_code=f"raw {token_key}=tok_unitsecret", count=1)],
        sample_outcomes=[
            LogisticsNl2SqlEvaluationReportSampleOutcome(
                sample_id="sample-1 SELECT * FROM dws_logistics_detail_union",
                description=f"desc {password_key}=unit-password",
                status="success",
                stage="trial",
                error_codes=[f"warning {api_key_name}=unit-secret {openai_like}"],
            )
        ],
        warnings=[f"outer {token_key}=tok_unitsecret {openai_like}"],
    )

    payload = report.model_dump_json()

    assert "SELECT" not in payload
    assert "dws_logistics_detail_union" not in payload
    assert "unit-password" not in payload
    assert "tok_unitsecret" not in payload
    assert "unit-secret" not in payload
    assert openai_like not in payload
    assert "[REDACTED]" in payload or "[SQL_REDACTED]" in payload



def _record(
    status: str,
    stage: str,
    *,
    error_codes: list[str] | None = None,
    error_message: str | None = None,
    question: str = "2025年发运量是多少",
    sql_hash: str | None = None,
    sql_param_keys: list[str] | None = None,
    explain_ok: bool = False,
    trial_ok: bool = False,
    warnings: list[str] | None = None,
) -> LogisticsNl2SqlEvaluationLogRecord:
    """生成 M6 报表测试用脱敏评估日志。"""

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
        error_message=error_message,
        catalog_ids=["metric:shipment_mw"],
        catalog_versions=["logistics_nl2sql_catalog.v1"],
        sql_hash=sql_hash,
        sql_param_keys=sql_param_keys or [],
        validation_errors=(error_codes or []) if status == "validation_failed" else [],
        safety_errors=(error_codes or []) if status == "safety_failed" else [],
        explain_ok=explain_ok,
        trial_ok=trial_ok,
        row_count=1 if status == "success" else 0,
        sample_row_count=1 if status == "success" else 0,
        duration_ms=3,
        pipeline_version="logistics_nl2sql_shadow.v1",
        warnings=warnings or [],
    )

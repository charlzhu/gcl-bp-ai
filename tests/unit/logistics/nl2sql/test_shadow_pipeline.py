from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.app.domains.logistics.services.nl2sql.evaluation_log import InMemoryLogisticsNl2SqlEvaluationLogSink
from backend.app.domains.logistics.services.nl2sql.shadow_pipeline import (
    LogisticsNl2SqlShadowPipeline,
    LogisticsNl2SqlShadowPipelineRequest,
)
from backend.app.domains.logistics.services.nl2sql.sql_execution import (
    FakeLogisticsSqlExecutor,
    LogisticsSqlExecutionService,
)
from backend.app.domains.logistics.services.nl2sql.sql_renderer import LogisticsRenderedSql


class _UnsafeRenderer:
    """测试用 renderer：故意返回 Safety 会拒绝的 SELECT *。"""

    def render(self, validation_result: Any) -> LogisticsRenderedSql:
        """返回不安全 SQL，用于验证 shadow pipeline 在 safety 阶段 fail-closed。"""

        return LogisticsRenderedSql(
            sql="SELECT * FROM dws_logistics_detail_union WHERE dws_logistics_detail_union.biz_year = :p0",
            params={"p0": 2025},
            referenced_tables=["dws_logistics_detail_union"],
            referenced_columns=[("dws_logistics_detail_union", "biz_year")],
        )


class _FailingRenderer:
    """测试用 renderer：模拟 renderer 边界异常。"""

    def render(self, validation_result: Any) -> LogisticsRenderedSql:
        """抛出带 SQL/密钥片段的异常，验证 render_failed 脱敏且不进入 executor。"""

        password_key = "password"
        raise RuntimeError(f"SELECT {password_key}=unit-password FROM dws_logistics_detail_union")


class _TrialFailingExecutor:
    """测试用 executor：EXPLAIN 成功但 trial 失败。"""

    def __init__(self) -> None:
        """初始化调用记录。"""

        self.calls: list[str] = []

    def explain(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """记录 EXPLAIN 并返回成功行。"""

        self.calls.append("explain")
        return [{"select_type": "SIMPLE"}]

    def trial(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """记录 trial 并抛出带敏感片段的错误。"""

        self.calls.append("trial")
        token_key = "token"
        raise RuntimeError(f"trial failed {token_key}=tok_unitsecret")


class _FailingLogSink:
    """测试用日志 sink：模拟日志落盘失败。"""

    def write(self, record: Any) -> None:
        """抛出带敏感片段的异常，验证主 shadow 结果不受影响且错误被脱敏。"""

        password_key = "password"
        raise RuntimeError(f"disk full {password_key}=unit-password")


def test_shadow_pipeline_success_runs_validation_render_safety_explain_trial_and_logs_hash_only() -> None:
    """合法 SQLPlan 应走完 M3/M4/explain/trial，并只在结果与日志中保留 SQL hash。"""

    executor = FakeLogisticsSqlExecutor(
        explain_rows=[{"select_type": "SIMPLE"}],
        trial_rows=[{"logistics_company_name": "承运商A", "shipment_mw": 12.3}],
    )
    sink = InMemoryLogisticsNl2SqlEvaluationLogSink()
    pipeline = LogisticsNl2SqlShadowPipeline(
        execution_service=LogisticsSqlExecutionService(executor=executor),
        log_sink=sink,
    )

    result = pipeline.run(
        LogisticsNl2SqlShadowPipelineRequest(
            question="2025年哪个物流承运商发运量最多",
            rewritten_question="2025年按承运商统计发运量并排序",
            request_id="req-success",
            candidate=_valid_candidate(),
        )
    )

    assert result.status == "success", result.error_codes
    assert result.stage == "trial"
    assert result.explain_ok is True
    assert result.trial_ok is True
    assert result.row_count == 1
    assert result.sample_row_count == 1
    assert result.sql_hash is not None and len(result.sql_hash) == 64
    assert result.sql_param_keys == ["p0", "p1", "p2", "p3", "p4"]
    assert [call.mode for call in executor.calls] == ["explain", "trial"]
    assert len(sink.records) == 1
    assert sink.records[0].status == "success"
    assert sink.records[0].sql_hash == result.sql_hash
    assert "SELECT " not in result.model_dump_json()
    assert "dws_logistics_detail_union.biz_year" not in sink.records[0].model_dump_json()


def test_shadow_pipeline_validation_failure_logs_and_skips_renderer_safety_executor() -> None:
    """M3 SQLPlan validation 失败时必须停止后续阶段，但仍写 evaluation log。"""

    executor = FakeLogisticsSqlExecutor()
    sink = InMemoryLogisticsNl2SqlEvaluationLogSink()
    pipeline = LogisticsNl2SqlShadowPipeline(
        execution_service=LogisticsSqlExecutionService(executor=executor),
        log_sink=sink,
    )

    result = pipeline.run(
        LogisticsNl2SqlShadowPipelineRequest(
            question="2025年运输吨位是多少",
            candidate=_valid_candidate(plan={"requested_unit": "吨"}),
        )
    )

    assert result.status == "validation_failed"
    assert result.stage == "validation"
    assert "sqlplan_unsupported_unit::吨" in result.error_codes
    assert executor.calls == []
    assert sink.records[0].status == "validation_failed"
    assert "sqlplan_unsupported_unit::吨" in sink.records[0].validation_errors


def test_shadow_pipeline_render_failure_logs_and_never_calls_safety_or_executor() -> None:
    """renderer 异常时必须停止在 render 阶段，并脱敏 SQL/密钥错误文本。"""

    executor = FakeLogisticsSqlExecutor()
    sink = InMemoryLogisticsNl2SqlEvaluationLogSink()
    pipeline = LogisticsNl2SqlShadowPipeline(
        renderer=_FailingRenderer(),
        execution_service=LogisticsSqlExecutionService(executor=executor),
        log_sink=sink,
    )

    result = pipeline.run(
        LogisticsNl2SqlShadowPipelineRequest(
            question="2025年发运量是多少",
            candidate=_valid_candidate(),
        )
    )
    payload = result.model_dump_json() + sink.records[0].model_dump_json()

    assert result.status == "render_failed"
    assert result.stage == "render"
    assert "shadow_render_failed" in result.error_codes
    assert executor.calls == []
    assert "SELECT" not in payload
    assert "unit-password" not in payload
    assert "[SQL_REDACTED]" in payload


def test_shadow_pipeline_safety_failure_logs_and_never_calls_executor() -> None:
    """M4 Safety 失败时不得进入 EXPLAIN/trial executor。"""

    executor = FakeLogisticsSqlExecutor()
    sink = InMemoryLogisticsNl2SqlEvaluationLogSink()
    pipeline = LogisticsNl2SqlShadowPipeline(
        renderer=_UnsafeRenderer(),
        execution_service=LogisticsSqlExecutionService(executor=executor),
        log_sink=sink,
    )

    result = pipeline.run(
        LogisticsNl2SqlShadowPipelineRequest(
            question="2025年发运量是多少",
            candidate=_valid_candidate(),
        )
    )

    assert result.status == "safety_failed"
    assert result.stage == "safety"
    assert "sql_safety_select_star_forbidden" in result.error_codes
    assert result.explain_ok is False
    assert result.trial_ok is False
    assert executor.calls == []
    assert sink.records[0].status == "safety_failed"
    assert "sql_safety_select_star_forbidden" in sink.records[0].safety_errors


def test_shadow_pipeline_explain_failure_is_redacted_and_trial_is_not_called() -> None:
    """EXPLAIN 异常要脱敏并阻断 trial，避免失败后继续执行 SQL。"""

    password_key = "password"
    token_key = "token"
    bearer_value = "bearer-secret-value"
    executor = FakeLogisticsSqlExecutor(
        raise_message=f"mysql://demo:pass123@127.0.0.1/db {password_key}=unit-password {token_key}=tok_unitsecret Bearer {bearer_value}"
    )
    sink = InMemoryLogisticsNl2SqlEvaluationLogSink()
    pipeline = LogisticsNl2SqlShadowPipeline(
        execution_service=LogisticsSqlExecutionService(executor=executor),
        log_sink=sink,
    )

    result = pipeline.run(
        LogisticsNl2SqlShadowPipelineRequest(
            question="2025年发运量是多少",
            candidate=_valid_candidate(plan={"query_type": "aggregate", "dimensions": [], "group_by": [], "order_by": [], "limit": None}),
        )
    )

    payload = result.model_dump_json() + sink.records[0].model_dump_json()

    assert result.status == "explain_failed"
    assert result.stage == "explain"
    assert "sql_execution_executor_failed::explain" in result.error_codes
    assert [call.mode for call in executor.calls] == ["explain"]
    assert "unit-password" not in payload
    assert "tok_unitsecret" not in payload
    assert "pass123" not in payload
    assert bearer_value not in payload
    assert "[REDACTED]" in payload


def test_shadow_pipeline_trial_failure_is_redacted_after_successful_explain() -> None:
    """EXPLAIN 成功但 trial 异常时，应返回 trial_failed 并写脱敏日志。"""

    executor = _TrialFailingExecutor()
    sink = InMemoryLogisticsNl2SqlEvaluationLogSink()
    pipeline = LogisticsNl2SqlShadowPipeline(
        execution_service=LogisticsSqlExecutionService(executor=executor),
        log_sink=sink,
    )

    result = pipeline.run(
        LogisticsNl2SqlShadowPipelineRequest(
            question="2025年发运量是多少",
            candidate=_valid_candidate(plan={"query_type": "aggregate", "dimensions": [], "group_by": [], "order_by": [], "limit": None}),
        )
    )
    payload = result.model_dump_json() + sink.records[0].model_dump_json()

    assert result.status == "trial_failed"
    assert result.stage == "trial"
    assert result.explain_ok is True
    assert result.trial_ok is False
    assert "sql_execution_executor_failed::trial" in result.error_codes
    assert executor.calls == ["explain", "trial"]
    assert "tok_unitsecret" not in payload
    assert "[REDACTED]" in payload


def test_shadow_pipeline_skips_unsupported_domain_or_source_without_sql_execution() -> None:
    """非 logistics/middle_db 的 shadow 请求只记录 skipped，不进入 SQL validator/renderer/executor。"""

    executor = FakeLogisticsSqlExecutor()
    sink = InMemoryLogisticsNl2SqlEvaluationLogSink()
    pipeline = LogisticsNl2SqlShadowPipeline(
        execution_service=LogisticsSqlExecutionService(executor=executor),
        log_sink=sink,
    )

    domain_result = pipeline.run(
        LogisticsNl2SqlShadowPipelineRequest(
            question="查计划 BOM",
            domain="plan_bom",
            candidate=_valid_candidate(),
        )
    )
    source_result = pipeline.run(
        LogisticsNl2SqlShadowPipelineRequest(
            question="查物流",
            source_system="sap_mid",
            candidate=_valid_candidate(),
        )
    )

    assert domain_result.status == "skipped"
    assert domain_result.stage == "domain"
    assert "shadow_domain_not_supported::plan_bom" in domain_result.error_codes
    assert source_result.status == "skipped"
    assert source_result.stage == "source_system"
    assert "shadow_source_system_not_supported::sap_mid" in source_result.error_codes
    assert executor.calls == []
    assert [record.status for record in sink.records] == ["skipped", "skipped"]


def test_shadow_pipeline_skips_missing_or_non_sql_direct_candidate_but_writes_log() -> None:
    """缺少 candidate 或非 sql_direct candidate 只记录 shadow 评估，不进入 SQL 阶段。"""

    executor = FakeLogisticsSqlExecutor()
    sink = InMemoryLogisticsNl2SqlEvaluationLogSink()
    pipeline = LogisticsNl2SqlShadowPipeline(
        execution_service=LogisticsSqlExecutionService(executor=executor),
        log_sink=sink,
    )

    missing = pipeline.run(LogisticsNl2SqlShadowPipelineRequest(question="发运量是多少"))
    unsupported = pipeline.run(
        LogisticsNl2SqlShadowPipelineRequest(
            question="请闲聊一下物流情况",
            candidate=_valid_candidate(strategy="chat_fallback"),
        )
    )

    assert missing.status == "skipped"
    assert missing.stage == "candidate"
    assert "shadow_candidate_missing" in missing.error_codes
    assert unsupported.status == "unsupported"
    assert unsupported.stage == "candidate"
    assert "shadow_strategy_not_sql_direct::chat_fallback" in unsupported.error_codes
    assert executor.calls == []
    assert [record.status for record in sink.records] == ["skipped", "unsupported"]


def test_shadow_pipeline_redacts_external_values_embedded_in_skip_error_codes_and_log() -> None:
    """strategy/domain/source 等外部输入进入错误码时也要脱敏，不能污染 shadow result/evaluation log。"""

    password_key = "password"
    token_key = "token"
    bearer_value = "bearer-secret-value"
    executor = FakeLogisticsSqlExecutor()
    sink = InMemoryLogisticsNl2SqlEvaluationLogSink()
    pipeline = LogisticsNl2SqlShadowPipeline(
        execution_service=LogisticsSqlExecutionService(executor=executor),
        log_sink=sink,
    )

    result = pipeline.run(
        LogisticsNl2SqlShadowPipelineRequest(
            question="发运量是多少",
            candidate=_valid_candidate(
                strategy=f"chat_fallback {password_key}=unit-password {token_key}=tok_unitsecret Bearer {bearer_value}",
                catalog_refs=[
                    {"catalog_id": f"metric:{password_key}=unit-password", "catalog_version": f"Bearer {bearer_value}"},
                    {"catalog_id": "raw::SELECT * FROM dws_logistics_detail_union", "catalog_version": "v1"},
                ],
            ),
        )
    )

    payload = result.model_dump_json() + sink.records[0].model_dump_json()

    assert result.status == "unsupported"
    assert executor.calls == []
    assert "unit-password" not in payload
    assert "tok_unitsecret" not in payload
    assert bearer_value not in payload
    assert "SELECT * FROM" not in payload
    assert "[REDACTED]" in payload
    assert "[SQL_REDACTED]" in payload


def test_shadow_pipeline_log_sink_failure_does_not_block_main_result_and_is_redacted() -> None:
    """evaluation log 写失败不能阻断 shadow 结果，但 log_error 必须脱敏。"""

    executor = FakeLogisticsSqlExecutor(explain_rows=[{"select_type": "SIMPLE"}], trial_rows=[])
    pipeline = LogisticsNl2SqlShadowPipeline(
        execution_service=LogisticsSqlExecutionService(executor=executor),
        log_sink=_FailingLogSink(),
    )

    result = pipeline.run(
        LogisticsNl2SqlShadowPipelineRequest(
            question="2025年发运量是多少",
            candidate=_valid_candidate(plan={"query_type": "aggregate", "dimensions": [], "group_by": [], "order_by": [], "limit": None}),
        )
    )

    assert result.status == "success"
    assert result.log_error is not None
    assert "unit-password" not in result.log_error
    assert "[REDACTED]" in result.log_error
    assert [call.mode for call in executor.calls] == ["explain", "trial"]


def _filter(dimension: str, operator: str, values: list) -> dict:
    """生成测试用过滤条件。"""

    return {"dimension": dimension, "operator": operator, "values": values}


def _valid_candidate(**overrides) -> dict:
    """生成一份 M3 可通过的 SQLPlan candidate，测试按需覆盖。"""

    candidate = {
        "schema_version": "logistics_sqlplan_candidate.v1",
        "domain": "logistics",
        "strategy": "sql_direct",
        "catalog_version": "logistics_nl2sql_catalog.v1",
        "catalog_refs": [
            {"catalog_id": "table:dws_logistics_detail_union", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "metric:shipment_mw", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "metric:row_count", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "dimension:biz_year", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "dimension:logistics_company_name", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "rule:default_time_range", "catalog_version": "logistics_nl2sql_catalog.v1"},
        ],
        "plan": {
            "query_type": "ranking",
            "tables": ["dws_logistics_detail_union"],
            "joins": [],
            "metrics": ["shipment_mw", "row_count"],
            "dimensions": ["logistics_company_name"],
            "filters": [_filter("biz_year", "in", [2023, 2024, 2025, 2026])],
            "group_by": ["logistics_company_name"],
            "order_by": [{"metric": "shipment_mw", "direction": "desc"}],
            "business_rules": ["default_time_range"],
            "explicit_year_buckets": [2023, 2024, 2025, 2026],
            "requested_unit": "MW",
            "limit": 20,
        },
        "clarification_questions": [],
        "unsupported_reason": None,
        "confidence": 0.91,
    }
    return _deep_merge(candidate, overrides)


def _deep_merge(base: dict, overrides: dict) -> dict:
    """递归合并测试覆盖字段，列表和值直接替换，额外 catalog_refs 追加。"""

    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        elif isinstance(value, list) and key == "catalog_refs":
            merged[key] = [*merged[key], *value]
        else:
            merged[key] = value
    return merged

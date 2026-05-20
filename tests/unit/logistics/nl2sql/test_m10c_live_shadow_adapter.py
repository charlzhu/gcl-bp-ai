from __future__ import annotations

import json
from typing import Any

from backend.app.domains.logistics.schemas.data_qa import (
    LogisticsDataQaPlan,
    LogisticsDataQaResult,
    LogisticsDataQaStatus,
    LogisticsDataQaTable,
)
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.domains.logistics.services.nl2sql.live_shadow_adapter import (
    LogisticsNl2SqlLiveShadowAdapter,
    LogisticsNl2SqlLiveShadowSummary,
)
from backend.app.domains.logistics.services.nl2sql.m9_sqlplan_generation import LogisticsSqlPlanGenerationResult
from backend.app.domains.logistics.services.nl2sql.shadow_pipeline import LogisticsNl2SqlShadowPipeline


class _ForbiddenFactory:
    """默认关闭测试用工厂：若被调用说明 shadow 旁路没有做到懒加载。"""

    def __call__(self) -> Any:
        """默认关闭时不允许构造任何外部依赖。"""

        raise AssertionError("默认关闭时不应构造 recall/generator/pipeline")


class _FakeRecallService:
    """测试用召回服务：返回最小 ok 结果。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def recall(self, **kwargs: Any) -> Any:
        """记录召回入参并返回有命中的对象，避免访问真实向量库。"""

        self.calls.append(dict(kwargs))
        return type("RecallResult", (), {"status": "ok", "hits": [object()], "error": None})()


class _FakeGenerator:
    """测试用 SQLPlan 生成器：返回候选，避免访问真实 LLM provider。"""

    def __init__(self, result: LogisticsSqlPlanGenerationResult | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.result = result or LogisticsSqlPlanGenerationResult(
            status="ok",
            candidate={"strategy": "sql_direct", "plan": {"metrics": ["shipment_mw"]}},
            validation_result=None,
            error_codes=[],
        )

    def generate(self, **kwargs: Any) -> LogisticsSqlPlanGenerationResult:
        """记录生成入参并返回测试指定结果。"""

        self.calls.append(dict(kwargs))
        return self.result


class _FakePipelineResult:
    """测试用 shadow pipeline 结果对象。"""

    status = "success"
    stage = "trial"
    error_codes: list[str] = []
    error_message = None
    sql_hash = "a" * 64
    row_count = 2
    candidate_sql_gate_allowed = True
    candidate_sql_gate_rejected = False
    candidate_sql_gate_reason_code = "allowed"
    duration_ms = 7


class _FakePipeline:
    """测试用 shadow pipeline：只记录请求，模拟 M10-B gate 已被调用后的安全摘要。"""

    def __init__(self) -> None:
        self.calls: list[Any] = []

    def run(self, request: Any) -> _FakePipelineResult:
        """记录 raw_candidate_sql 是否被传入 pipeline，并返回脱敏摘要。"""

        self.calls.append(request)
        return _FakePipelineResult()


class _FakeDb:
    """服务层测试用数据库替身，只提供事务方法。"""

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


class _FakeQueryLogRepository:
    """捕获 sys_query_log 写入 payload，避免真实落库。"""

    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        """保存历史写入内容并返回伪造日志 ID。"""

        self.payloads.append(dict(payload))
        return 123


class _NoopRepository:
    """服务构造用 repository 替身，本测试不执行真实查询。"""

    def list_historical_carrier_names(self) -> list[str]:
        return []


class _CaptureShadowAdapter:
    """服务层测试用 M10-C adapter，返回含敏感片段的摘要以验证最终防泄漏。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def run_shadow(self, **kwargs: Any) -> LogisticsNl2SqlLiveShadowSummary:
        """记录调用并返回安全字段；恶意错误码应在 summary 模型内脱敏。"""

        self.calls.append(dict(kwargs))
        return LogisticsNl2SqlLiveShadowSummary(
            enabled=True,
            status="success",
            stage="trial",
            error_codes=["ok", "SELECT password=unit-secret FROM dws_logistics_detail_union"],
            sql_hash="b" * 64,
            row_count=1,
            candidate_sql_gate_allowed=True,
            candidate_sql_gate_rejected=False,
            candidate_sql_gate_reason_code="allowed",
        )


class _ExplodingShadowAdapter:
    """模拟 adapter 意外异常，验证正式 QA 历史写入不会中断。"""

    def run_shadow(self, **kwargs: Any) -> LogisticsNl2SqlLiveShadowSummary:  # noqa: ARG002
        """抛出带敏感形态的异常，调用方必须脱敏收敛。"""

        raise RuntimeError("SELECT api_key=unit-secret FROM dws_logistics_detail_union")


def test_live_shadow_adapter_default_disabled_does_not_construct_external_dependencies() -> None:
    """M10-C 默认关闭时不得构造召回、LLM 或 pipeline 依赖，也不得影响正式 QA。"""

    adapter = LogisticsNl2SqlLiveShadowAdapter(
        enabled=False,
        recall_service_factory=_ForbiddenFactory(),
        generator_factory=_ForbiddenFactory(),
        pipeline_factory=_ForbiddenFactory(),
    )

    summary = adapter.run_shadow(question="哪个物流跑得最多？", trace_id="trace-disabled")

    assert summary.enabled is False
    assert summary.shadow_only is True
    assert summary.status == "disabled"
    assert summary.stage == "disabled"
    assert summary.error_codes == ["m10c_live_shadow_disabled"]


def test_live_shadow_adapter_enabled_reuses_candidate_sql_gate_before_pipeline_validation() -> None:
    """显式开启时 raw candidate SQL 必须先过 M10-B gate，拒绝后不能继续进入 renderer/executor。"""

    adapter = LogisticsNl2SqlLiveShadowAdapter(
        enabled=True,
        recall_service_factory=lambda: _FakeRecallService(),
        generator_factory=lambda: _FakeGenerator(),
        pipeline_factory=lambda: LogisticsNl2SqlShadowPipeline(),
    )
    raw_candidate_sql = "SELECT biz_year FROM dws_logistics_detail_union LIMIT 10; DROP TABLE sys_user"

    summary = adapter.run_shadow(
        question="哪个物流跑得最多？",
        trace_id="trace-gate",
        raw_candidate_sql=raw_candidate_sql,
    )
    payload = summary.model_dump_json()

    assert summary.status == "validation_failed"
    assert summary.stage == "candidate_sql_gate"
    assert summary.candidate_sql_gate_rejected is True
    assert summary.candidate_sql_gate_allowed is False
    assert summary.candidate_sql_gate_reason_code == "multi_statement"
    assert any("candidate_sql_gate_rejected::multi_statement" == code for code in summary.error_codes)
    assert raw_candidate_sql not in payload
    assert "DROP TABLE" not in payload
    assert "dws_logistics_detail_union" not in payload


def test_live_shadow_adapter_enabled_runs_shadow_pipeline_and_passes_raw_sql_to_gate_boundary() -> None:
    """显式开启时应进入 NL2SQL shadow pipeline，raw SQL 只传给 M10-B gate 边界而不出现在摘要中。"""

    recall_service = _FakeRecallService()
    generator = _FakeGenerator()
    pipeline = _FakePipeline()
    adapter = LogisticsNl2SqlLiveShadowAdapter(
        enabled=True,
        recall_service_factory=lambda: recall_service,
        generator_factory=lambda: generator,
        pipeline_factory=lambda: pipeline,
    )
    raw_candidate_sql = "SELECT password_token_dsn FROM dws_logistics_detail_union LIMIT 9999"

    summary = adapter.run_shadow(
        question="哪个物流跑得最多？",
        trace_id="trace-enabled",
        raw_candidate_sql=raw_candidate_sql,
    )
    payload = summary.model_dump_json()

    assert summary.status == "success"
    assert summary.stage == "trial"
    assert summary.sql_hash == "a" * 64
    assert summary.candidate_sql_gate_allowed is True
    assert pipeline.calls and pipeline.calls[0].raw_candidate_sql == raw_candidate_sql
    assert raw_candidate_sql not in payload
    assert "password_token_dsn" not in payload
    assert "dws_logistics_detail_union" not in payload


def test_live_shadow_adapter_fail_closed_generation_error_is_redacted() -> None:
    """provider/generator 失败只能返回脱敏 shadow 状态，不能抛出异常或泄漏 SQL/密钥。"""

    generator = _FakeGenerator(
        LogisticsSqlPlanGenerationResult(
            status="error",
            candidate=None,
            error_codes=[
                "sqlplan_table_not_allowed::dws_logistics_detail_union",
                "sql_safety_column_not_allowed::dws_logistics_detail_union.secret_column",
                "provider_debug::dashscope_internal_trace",
                "SELECT api_key=unit-secret FROM dws_logistics_detail_union",
            ],
            error_message="provider=dashscope table=dws_logistics_detail_union Bearer bearer-secret-value mysql://user:***@example/db",
        )
    )
    adapter = LogisticsNl2SqlLiveShadowAdapter(
        enabled=True,
        recall_service_factory=lambda: _FakeRecallService(),
        generator_factory=lambda: generator,
        pipeline_factory=_ForbiddenFactory(),
    )

    summary = adapter.run_shadow(question="哪个物流跑得最多？", trace_id="trace-error")
    payload = summary.model_dump_json()

    assert summary.status == "error"
    assert summary.stage == "generation"
    assert "m10c_generation_not_ok::error" in summary.error_codes
    assert "m10c_error_redacted" in summary.error_codes
    assert summary.error_message == "shadow error redacted"
    assert "sqlplan" not in payload
    assert "sql_safety" not in payload
    assert "provider" not in payload
    assert "dashscope" not in payload
    assert "unit-secret" not in payload
    assert "bearer-secret-value" not in payload
    assert "mysql://" not in payload
    assert "SELECT" not in payload
    assert "dws_logistics_detail_union" not in payload


def test_data_qa_history_records_m10c_shadow_summary_without_mutating_user_visible_result() -> None:
    """正式 QA 只把 M10-C 脱敏摘要写入历史快照，不改变返回给用户的结果对象。"""

    log_repository = _FakeQueryLogRepository()
    shadow_adapter = _CaptureShadowAdapter()
    service = LogisticsDataQaService(
        db=_FakeDb(),  # type: ignore[arg-type]
        repository=_NoopRepository(),  # type: ignore[arg-type]
        query_log_repository=log_repository,  # type: ignore[arg-type]
        nl2sql_live_shadow_adapter=shadow_adapter,
    )
    result = LogisticsDataQaResult(
        answer_summary="正式物流回答保持不变。",
        result_table=LogisticsDataQaTable(columns=["承运商", "发运量"], rows=[{"承运商": "A", "发运量": 1.0}]),
        calculation_logic=["正式链路确定性计算。"],
        data_scope={"scope": "业务中间库"},
        query_plan=LogisticsDataQaPlan(intent="ranking", query_key="formal_query_key"),
        status=LogisticsDataQaStatus(code="OK", message="正式物流回答保持不变。", success=True),
    )
    before = result.model_dump(mode="json")

    log_id = service._write_history_snapshot(question="哪个物流跑得最多？", trace_id="trace-history", result=result)
    request_payload = json.loads(log_repository.payloads[0]["request_payload"])
    shadow_summary = request_payload["response_meta"]["nl2sql_live_shadow"]
    shadow_payload = json.dumps(shadow_summary, ensure_ascii=False)

    assert log_id == 123
    assert shadow_adapter.calls and shadow_adapter.calls[0]["formal_result"] is result
    assert result.model_dump(mode="json") == before
    assert shadow_summary["shadow_only"] is True
    assert shadow_summary["status"] == "success"
    assert shadow_summary["sql_hash"] == "b" * 64
    assert "unit-secret" not in shadow_payload
    assert "SELECT" not in shadow_payload
    assert "dws_logistics_detail_union" not in shadow_payload


def test_data_qa_history_shadow_adapter_exception_falls_back_to_sanitized_audit() -> None:
    """adapter 异常时仍写入正式 QA 历史，并把异常摘要收敛为脱敏 fallback。"""

    log_repository = _FakeQueryLogRepository()
    service = LogisticsDataQaService(
        db=_FakeDb(),  # type: ignore[arg-type]
        repository=_NoopRepository(),  # type: ignore[arg-type]
        query_log_repository=log_repository,  # type: ignore[arg-type]
        nl2sql_live_shadow_adapter=_ExplodingShadowAdapter(),  # type: ignore[arg-type]
    )
    result = LogisticsDataQaResult(
        answer_summary="正式物流回答保持不变。",
        result_table=LogisticsDataQaTable(columns=["承运商", "发运量"], rows=[{"承运商": "A", "发运量": 1.0}]),
        calculation_logic=["正式链路确定性计算。"],
        data_scope={"scope": "业务中间库"},
        query_plan=LogisticsDataQaPlan(intent="ranking", query_key="formal_query_key"),
        status=LogisticsDataQaStatus(code="OK", message="正式物流回答保持不变。", success=True),
    )

    log_id = service._write_history_snapshot(question="哪个物流跑得最多？", trace_id="trace-explode", result=result)
    request_payload = json.loads(log_repository.payloads[0]["request_payload"])
    shadow_summary = request_payload["response_meta"]["nl2sql_live_shadow"]
    shadow_payload = json.dumps(shadow_summary, ensure_ascii=False)

    assert log_id == 123
    assert shadow_summary["shadow_only"] is True
    assert shadow_summary["status"] == "error"
    assert shadow_summary["stage"] == "adapter"
    assert shadow_summary["error_codes"] == ["m10c_live_shadow_audit_error"]
    assert shadow_summary["error_message"] == "shadow audit failed"
    assert shadow_summary["trace_id"] == "trace-explode"
    assert "unit-secret" not in shadow_payload
    assert "SELECT" not in shadow_payload
    assert "dws_logistics_detail_union" not in shadow_payload

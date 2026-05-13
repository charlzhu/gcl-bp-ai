from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from backend.app.domains.logistics.schemas.data_qa import (
    LogisticsDataQaPlan,
    LogisticsDataQaResult,
    LogisticsDataQaStatus,
    LogisticsDataQaTable,
)
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.domains.plan_bom.schemas.qa import PlanBomNluCandidate, PlanBomQaResponse, PlanBomQaStatus
from backend.app.domains.plan_bom.services.qa_service import PlanBomQaService
from backend.app.domains.query_planning.services.shadow_snapshot_builder import QueryPlanningV2ShadowSnapshotBuilder


class _FakeDb:
    """测试用 DB，会话只记录提交/回滚次数。"""

    def __init__(self) -> None:
        self.commit_count = 0
        self.rollback_count = 0

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1


class _CapturingQueryLogRepository:
    """捕获 sys_query_log 写入 payload。"""

    def __init__(self, log_id: int = 501) -> None:
        self.log_id = log_id
        self.payloads: list[dict] = []

    def write_query_log(self, db, payload: dict) -> int:  # noqa: ANN001
        self.payloads.append(payload)
        return self.log_id


class _BrokenShadowSnapshotBuilder:
    """模拟 shadow 构建失败，验证不阻断主问答链路。"""

    def build_logistics_snapshot(self, **_: Any) -> dict[str, Any]:
        raise RuntimeError("shadow compare failed")

    def build_plan_bom_snapshot(self, **_: Any) -> dict[str, Any]:
        raise RuntimeError("shadow compare failed")


def _logistics_success_result(query_key: str = "hist_mw_by_carrier") -> LogisticsDataQaResult:
    """构造物流 A 类成功结果。"""

    return LogisticsDataQaResult(
        answer_summary="已统计 2025 年各承运商发运量。",
        result_table=LogisticsDataQaTable(columns=["承运商", "发运量"], rows=[{"承运商": "A", "发运量": 1}]),
        query_plan=LogisticsDataQaPlan(
            intent="aggregate",
            query_key=query_key,
            metrics=["shipment_mw"],
            dimensions=["carrier"],
            filters={"year": 2025},
        ),
        status=LogisticsDataQaStatus(code="OK", message="查询成功", success=True),
    )


def test_logistics_shadow_snapshot_records_online_comparison_summary() -> None:
    """物流 shadow 快照应在线记录 formal/shadow 对比摘要，便于后续灰度报表直接读取。"""
    snapshot = QueryPlanningV2ShadowSnapshotBuilder().build_logistics_snapshot(
        question="2025年各承运商发运量是多少？",
        result=_logistics_success_result(),
        trace_id="trace-p55-logistics",
    )

    comparison = snapshot["comparison"]
    assert comparison["domain"] == "logistics"
    assert comparison["formal_status"] == "SUCCESS"
    assert comparison["formal_query_key"] == "hist_mw_by_carrier"
    assert comparison["shadow_strategy"] == "DIRECT_RETRIEVAL"
    assert comparison["shadow_query_key"] == "hist_mw_by_carrier"
    assert comparison["query_key_matched"] is True
    assert comparison["matched"] is True
    assert comparison["risk_tags"] == []
    assert comparison["shadow_only"] is True
    assert comparison["llm_can_execute"] is False
    assert comparison["sql_generation_allowed"] is False
    assert snapshot["risk_tags"] == []


def test_logistics_history_payload_exposes_shadow_comparison_without_changing_formal_result() -> None:
    """物流历史日志应只新增审计字段，正式 query_result 不被 shadow 对比覆盖。"""
    db = _FakeDb()
    query_log_repository = _CapturingQueryLogRepository(log_id=502)
    service = LogisticsDataQaService(
        db=db,
        repository=object(),
        query_log_repository=query_log_repository,
    )
    result = _logistics_success_result()

    log_id = service._write_history_snapshot(question="2025年各承运商发运量是多少？", trace_id="trace-p55", result=result)

    assert log_id == 502
    assert db.commit_count == 1
    payload = json.loads(query_log_repository.payloads[0]["request_payload"])
    comparison = payload["query_plan_v2_shadow"]["comparison"]
    assert comparison["matched"] is True
    assert payload["response_meta"]["query_plan_v2_compare_matched"] is True
    assert payload["response_meta"]["query_plan_v2_risk_tags"] == []
    assert payload["query_result"]["answer_summary"] == result.answer_summary
    assert payload["query_result"]["query_plan"]["query_key"] == "hist_mw_by_carrier"


def test_plan_bom_shadow_snapshot_records_clarify_boundary_comparison() -> None:
    """BOM B 类追问应记录 CLARIFY 边界一致的 comparison，不把 shadow 当成正式答案。"""
    response = PlanBomQaResponse(
        question="这个订单玻璃是什么？",
        classification="B",
        status=PlanBomQaStatus(code="CLARIFICATION_REQUIRED", message="请补充订单。", success=False, severity="warning"),
        nlu=PlanBomNluCandidate(
            question="这个订单玻璃是什么？",
            intent="single_order_material_specs",
            slots={"material_category": ["玻璃"]},
            missing_slots=["order_id"],
            confidence=0.6,
            provider_mode="rule",
        ),
        answer_summary="请补充订单号、BOM 文件名或客户实例。",
    )

    snapshot = QueryPlanningV2ShadowSnapshotBuilder().build_plan_bom_snapshot(
        question=response.question,
        response=response,
        trace_id="trace-p55-bom",
    )

    comparison = snapshot["comparison"]
    assert comparison["domain"] == "plan_bom"
    assert comparison["formal_status"] == "CLARIFICATION"
    assert comparison["formal_query_key"] == "single_order_material_specs"
    assert comparison["shadow_strategy"] == "CLARIFY"
    assert comparison["shadow_query_key"] is None
    assert comparison["query_key_matched"] is False
    assert comparison["matched"] is False
    assert comparison["risk_tags"] == ["query_key_mismatch"]
    assert "query_key_mismatch" in snapshot["risk_tags"]


def test_plan_bom_shadow_comparison_handles_c_no_answer_and_error_boundaries() -> None:
    """BOM C、空结果和异常边界应有明确 comparison，不能被误记为 guardrail 安全拦截。"""
    unsupported_response = PlanBomQaResponse(
        question="预测一下明年市场价格？",
        classification="C",
        status=PlanBomQaStatus(code="UNSUPPORTED_QUESTION", message="暂不支持。", success=False, severity="info"),
        nlu=PlanBomNluCandidate(
            question="预测一下明年市场价格？",
            intent="unsupported",
            slots={},
            confidence=0.5,
            provider_mode="rule",
        ),
        answer_summary="当前问题超出计划 BOM 结构化查询边界。",
    )
    unsupported_snapshot = QueryPlanningV2ShadowSnapshotBuilder().build_plan_bom_snapshot(
        question=unsupported_response.question,
        response=unsupported_response,
        trace_id="trace-p55-bom-c",
    )
    assert unsupported_snapshot["comparison"]["formal_status"] == "UNSUPPORTED"
    assert unsupported_snapshot["comparison"]["shadow_strategy"] == "UNSUPPORTED"
    assert unsupported_snapshot["comparison"]["guardrail_status"] == "rejected"
    assert "guardrail_blocked" not in unsupported_snapshot["risk_tags"]

    empty_response = PlanBomQaResponse(
        question="订单 X 的玻璃是什么？",
        classification="A",
        status=PlanBomQaStatus(code="EMPTY_RESULT", message="未查到结果。", success=True, severity="warning"),
        nlu=PlanBomNluCandidate(
            question="订单 X 的玻璃是什么？",
            intent="single_order_material_specs",
            slots={"order_id": "X", "material_category": ["玻璃"]},
            confidence=0.9,
            provider_mode="rule",
        ),
        answer_summary="未查到匹配 BOM。",
    )
    empty_snapshot = QueryPlanningV2ShadowSnapshotBuilder().build_plan_bom_snapshot(
        question=empty_response.question,
        response=empty_response,
        trace_id="trace-p55-bom-empty",
    )
    assert empty_snapshot["comparison"]["formal_status"] == "EMPTY_RESULT"
    assert empty_snapshot["comparison"]["shadow_strategy"] == "NO_ANSWER"
    assert empty_snapshot["comparison"]["guardrail_status"] == "rejected"
    assert "guardrail_blocked" not in empty_snapshot["risk_tags"]

    error_response = PlanBomQaResponse(
        question="订单 X 的玻璃是什么？",
        classification="D",
        status=PlanBomQaStatus(code="EXECUTION_ERROR", message="执行异常。", success=False, severity="error"),
        nlu=PlanBomNluCandidate(
            question="订单 X 的玻璃是什么？",
            intent="single_order_material_specs",
            slots={"order_id": "X", "material_category": ["玻璃"]},
            confidence=0.9,
            provider_mode="rule",
        ),
        answer_summary="查询执行失败。",
    )
    error_snapshot = QueryPlanningV2ShadowSnapshotBuilder().build_plan_bom_snapshot(
        question=error_response.question,
        response=error_response,
        trace_id="trace-p55-bom-error",
    )
    assert error_snapshot["comparison"]["formal_status"] == "ERROR"
    assert error_snapshot["comparison"]["shadow_strategy"] == "UNSUPPORTED"
    assert error_snapshot["comparison"]["matched"] is False
    assert error_snapshot["risk_tags"]


def test_plan_bom_history_payload_exposes_shadow_comparison_meta() -> None:
    """BOM 历史日志 response_meta 应携带 comparison 摘要，供运营看板轻量读取。"""
    db = _FakeDb()
    query_log_repository = _CapturingQueryLogRepository(log_id=503)
    service = PlanBomQaService(
        repository=SimpleNamespace(db=db),
        query_service=object(),
        nlu_service=object(),
        presentation_service=object(),
        power_config_resolver=object(),
        power_prediction_engine=object(),
        power_recommendation_service=object(),
        query_log_repository=query_log_repository,
    )
    response = PlanBomQaResponse(
        question="这个订单玻璃是什么？",
        classification="B",
        status=PlanBomQaStatus(code="CLARIFICATION_REQUIRED", message="请补充订单。", success=False, severity="warning"),
        nlu=PlanBomNluCandidate(
            question="这个订单玻璃是什么？",
            intent="single_order_material_specs",
            slots={"material_category": ["玻璃"]},
            missing_slots=["order_id"],
            confidence=0.6,
            provider_mode="rule",
        ),
        answer_summary="请补充订单号、BOM 文件名或客户实例。",
    )

    log_id = service._write_history_snapshot(question=response.question, trace_id="trace-bom", response=response)

    assert log_id == 503
    assert db.commit_count == 1
    payload = json.loads(query_log_repository.payloads[0]["request_payload"])
    comparison = payload["query_plan_v2_shadow"]["comparison"]
    assert comparison["formal_status"] == "CLARIFICATION"
    assert payload["response_meta"]["query_plan_v2_compare_matched"] is False
    assert payload["response_meta"]["query_plan_v2_formal_query_key"] == "single_order_material_specs"
    assert payload["response_meta"]["query_plan_v2_shadow_query_key"] is None
    assert payload["response_meta"]["query_plan_v2_risk_tags"] == ["query_key_mismatch"]


def test_history_snapshot_fail_soft_when_shadow_compare_builder_fails() -> None:
    """shadow comparison 构建失败时只影响历史日志，不向上抛出异常。"""
    logistics_db = _FakeDb()
    logistics_repository = _CapturingQueryLogRepository(log_id=504)
    logistics_service = LogisticsDataQaService(
        db=logistics_db,
        repository=object(),
        query_log_repository=logistics_repository,
    )
    logistics_service.query_plan_shadow_builder = _BrokenShadowSnapshotBuilder()

    logistics_log_id = logistics_service._write_history_snapshot(
        question="2025年各承运商发运量是多少？",
        trace_id="trace-fail-soft-logistics",
        result=_logistics_success_result(),
    )

    assert logistics_log_id == 0
    assert logistics_db.rollback_count == 1
    assert logistics_repository.payloads == []

    bom_db = _FakeDb()
    bom_repository = _CapturingQueryLogRepository(log_id=505)
    bom_service = PlanBomQaService(
        repository=SimpleNamespace(db=bom_db),
        query_service=object(),
        nlu_service=object(),
        presentation_service=object(),
        power_config_resolver=object(),
        power_prediction_engine=object(),
        power_recommendation_service=object(),
        query_log_repository=bom_repository,
    )
    bom_service.query_plan_shadow_builder = _BrokenShadowSnapshotBuilder()
    response = PlanBomQaResponse(
        question="这个订单玻璃是什么？",
        classification="B",
        status=PlanBomQaStatus(code="CLARIFICATION_REQUIRED", message="请补充订单。", success=False, severity="warning"),
        nlu=PlanBomNluCandidate(
            question="这个订单玻璃是什么？",
            intent="single_order_material_specs",
            slots={"material_category": ["玻璃"]},
            missing_slots=["order_id"],
            confidence=0.6,
            provider_mode="rule",
        ),
        answer_summary="请补充订单号、BOM 文件名或客户实例。",
    )

    bom_log_id = bom_service._write_history_snapshot(
        question=response.question,
        trace_id="trace-fail-soft-bom",
        response=response,
    )

    assert bom_log_id == 0
    assert bom_db.rollback_count == 1
    assert bom_repository.payloads == []

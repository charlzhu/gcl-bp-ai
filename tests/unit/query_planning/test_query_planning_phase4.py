from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.app.api.deps import require_query_planning_internal_access
from backend.app.core.config import Settings
from backend.app.domains.logistics.schemas.data_qa import (
    LogisticsDataQaPlan,
    LogisticsDataQaResult,
    LogisticsDataQaStatus,
    LogisticsDataQaTable,
)
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.domains.plan_bom.schemas.qa import PlanBomNluCandidate, PlanBomQaResponse, PlanBomQaStatus
from backend.app.domains.plan_bom.services.qa_service import PlanBomQaService
from backend.app.domains.query_planning.services.shadow_report_service import (
    DEFAULT_QUERY_PLANNING_V2_SHADOW_CASES,
    QueryPlanningV2ShadowReportService,
)
from backend.app.domains.query_planning.schemas.query_plan_v2 import QueryPlanningV2Plan


class _FakeDb:
    """测试用 DB 会话，只记录 commit / rollback，不连接真实数据库。"""

    def __init__(self) -> None:
        self.commit_count = 0
        self.rollback_count = 0

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1


class _CapturingQueryLogRepository:
    """测试用 sys_query_log 仓储，捕获待写入的 request_payload。"""

    def __init__(self, log_id: int = 88) -> None:
        self.log_id = log_id
        self.payloads: list[dict] = []

    def write_query_log(self, db, payload: dict) -> int:  # noqa: ANN001
        self.payloads.append(payload)
        return self.log_id


class _FakePlanningService:
    """测试用 Query Planning 服务，按问题返回预期策略，避免 shadow 报表测试依赖真实数据。"""

    def plan(
        self,
        *,
        question: str,
        domain: str | None = None,
        trace_id: str | None = None,
        write_audit: bool = False,
    ) -> QueryPlanningV2Plan:
        expected = next(case for case in DEFAULT_QUERY_PLANNING_V2_SHADOW_CASES if case.question == question)
        plan = QueryPlanningV2Plan(
            domain=domain or expected.domain,
            original_question=question,
            strategy=expected.expected_strategy,
            intent=expected.expected_intent,
            query_key=expected.expected_query_key,
        )
        plan.audit.trace_id = trace_id
        return plan


def test_query_planning_internal_access_allows_non_prod_and_blocks_prod() -> None:
    """Query Planning V2 诊断接口只能作为内部能力使用，生产环境需等正式权限模块接管。"""
    require_query_planning_internal_access(Settings(app_env="local"))
    require_query_planning_internal_access(Settings(app_env="test"))

    with pytest.raises(HTTPException) as exc_info:
        require_query_planning_internal_access(Settings(app_env="prod"))

    assert exc_info.value.status_code == 403
    assert "内部诊断" in str(exc_info.value.detail)
    assert "用户权限模块" in str(exc_info.value.detail)


def test_logistics_history_payload_embeds_query_plan_v2_shadow_snapshot() -> None:
    """物流 Data QA 写 sys_query_log 时，应在 request_payload 中写入 query_plan_v2 shadow 快照。"""
    db = _FakeDb()
    query_log_repository = _CapturingQueryLogRepository(log_id=101)
    service = LogisticsDataQaService(
        db=db,
        repository=object(),
        query_log_repository=query_log_repository,
    )
    result = LogisticsDataQaResult(
        answer_summary="已统计 2025 年各承运商发运量。",
        result_table=LogisticsDataQaTable(columns=["承运商", "发运量"], rows=[{"承运商": "A", "发运量": 1}]),
        query_plan=LogisticsDataQaPlan(
            intent="aggregate",
            query_key="hist_mw_by_carrier",
            metrics=["shipment_mw"],
            dimensions=["carrier"],
            filters={"year": 2025},
        ),
        status=LogisticsDataQaStatus(code="OK", message="查询成功", success=True),
    )

    log_id = service._write_history_snapshot(question="2025年各承运商发运量是多少？", trace_id="trace-log", result=result)

    assert log_id == 101
    assert db.commit_count == 1
    payload = json.loads(query_log_repository.payloads[0]["request_payload"])
    shadow = payload["query_plan_v2_shadow"]
    assert shadow["schema_version"] == "query_plan_v2.0"
    assert shadow["original_question"] == "2025年各承运商发运量是多少？"
    assert shadow["domain"] == "logistics"
    assert shadow["strategy"] == "DIRECT_RETRIEVAL"
    assert shadow["query_key"] == "hist_mw_by_carrier"
    assert shadow["slots"]["filters"] == {"year": 2025}
    assert shadow["guardrail_decision"]["policy_locked"] is True
    assert shadow["execution_policy"]["shadow_only"] is True
    assert shadow["execution_policy"]["llm_can_execute"] is False
    assert shadow["execution_policy"]["sql_generation_allowed"] is False
    assert payload["response_meta"]["query_plan_v2_strategy"] == "DIRECT_RETRIEVAL"


def test_plan_bom_history_payload_embeds_clarify_query_plan_v2_shadow_snapshot() -> None:
    """BOM QA B 类追问也要写入 query_plan_v2 shadow，便于统一审计 CLARIFY 策略。"""
    db = _FakeDb()
    query_log_repository = _CapturingQueryLogRepository(log_id=202)
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

    assert log_id == 202
    assert db.commit_count == 1
    payload = json.loads(query_log_repository.payloads[0]["request_payload"])
    shadow = payload["query_plan_v2_shadow"]
    assert shadow["domain"] == "plan_bom"
    assert shadow["strategy"] == "CLARIFY"
    assert shadow["intent"] == "single_order_material_specs"
    assert shadow["query_key"] is None
    assert shadow["slots"]["filters"]["material_category"] == ["玻璃"]
    assert shadow["clarification_questions"]
    assert shadow["execution_policy"]["executable"] is False
    assert payload["response_meta"]["query_plan_v2_strategy"] == "CLARIFY"


def test_shadow_report_contains_ten_logistics_and_bom_cases() -> None:
    """Phase 4 shadow 对比报表应内置 10 类物流/BOM 问题并输出策略匹配结果。"""
    service = QueryPlanningV2ShadowReportService(planning_service=_FakePlanningService())

    report = service.build_default_report(trace_id="trace-report", write_audit=False)

    assert report.total_cases == 10
    assert report.matched_cases == 10
    assert report.mismatched_cases == 0
    assert {case.domain for case in report.cases} == {"logistics", "plan_bom"}
    assert sum(1 for case in report.cases if case.domain == "logistics") == 5
    assert sum(1 for case in report.cases if case.domain == "plan_bom") == 5
    assert {case.expected_strategy for case in report.cases} >= {"DIRECT_RETRIEVAL", "CLARIFY", "UNSUPPORTED"}
    assert all(case.actual_strategy == case.expected_strategy for case in report.cases)

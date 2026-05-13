from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaPlan
from backend.app.domains.plan_bom.schemas.qa import PlanBomNluCandidate
from backend.app.domains.query_planning.schemas.query_plan_v2 import QueryPlanningV2Plan
from backend.app.domains.query_planning.services.logistics_adapter import LogisticsQueryPlanningAdapter
from backend.app.domains.query_planning.services.plan_bom_adapter import PlanBomQueryPlanningAdapter
from backend.app.domains.query_planning.services.query_plan_v2_audit_writer import QueryPlanV2AuditWriter
from backend.app.domains.query_planning.services.query_planning_v2_service import QueryPlanningV2Service


class _FakeLogisticsPlanner:
    """测试用物流 planner，只返回受控 plan，不执行查询。"""

    def __init__(self, plan: LogisticsDataQaPlan) -> None:
        self.plan = plan
        self.questions: list[str] = []

    def build_plan(self, question: str) -> LogisticsDataQaPlan:
        self.questions.append(question)
        return self.plan


class _FakePlanBomNluService:
    """测试用 BOM NLU，只返回候选理解，不查数。"""

    def __init__(self, candidate: PlanBomNluCandidate) -> None:
        self.candidate = candidate
        self.calls: list[dict[str, Any]] = []

    def understand(self, question: str, *, use_llm: bool = True) -> PlanBomNluCandidate:
        self.calls.append({"question": question, "use_llm": use_llm})
        return self.candidate


def test_logistics_adapter_outputs_direct_query_plan_without_executing_data_qa() -> None:
    """物流 adapter 应包装现有规则 plan，输出统一 query_plan_v2。"""
    rule_plan = LogisticsDataQaPlan(
        intent="aggregate",
        query_key="hist_mw_by_carrier",
        metrics=["shipment_mw"],
        dimensions=["carrier"],
        filters={"year": 2025},
    )
    planner = _FakeLogisticsPlanner(rule_plan)

    plan = LogisticsQueryPlanningAdapter(planner=planner).build_candidate("2025年各承运商发运量是多少？", trace_id="t-log")

    assert isinstance(plan, QueryPlanningV2Plan)
    assert planner.questions == ["2025年各承运商发运量是多少？"]
    assert plan.domain == "logistics"
    assert plan.original_question == "2025年各承运商发运量是多少？"
    assert plan.strategy == "DIRECT_RETRIEVAL"
    assert plan.query_key == "hist_mw_by_carrier"
    assert plan.slots.metrics == ["shipment_mw"]
    assert plan.slots.filters == {"year": 2025}
    assert plan.rule_plan["query_key"] == "hist_mw_by_carrier"
    assert plan.guardrail_decision.final_source == "rule"


def test_plan_bom_adapter_outputs_clarify_plan_and_does_not_enable_llm_by_default() -> None:
    """BOM adapter 仅调用 NLU Center 的受控理解，缺槽时输出 CLARIFY。"""
    candidate = PlanBomNluCandidate(
        question="这个订单玻璃是什么？",
        intent="single_order_material_specs",
        slots={"material_category": ["玻璃"]},
        missing_slots=["order_id"],
        confidence=0.58,
        provider_mode="rule",
        guardrail_notes=["规则层完成初始意图和槽位抽取。"],
    )
    nlu = _FakePlanBomNluService(candidate)

    plan = PlanBomQueryPlanningAdapter(nlu_service=nlu).build_candidate("这个订单玻璃是什么？", trace_id="t-bom")

    assert nlu.calls == [{"question": "这个订单玻璃是什么？", "use_llm": False}]
    assert plan.domain == "plan_bom"
    assert plan.strategy == "CLARIFY"
    assert plan.intent == "single_order_material_specs"
    assert plan.query_key is None
    assert plan.clarification_questions
    assert plan.slots.filters["material_category"] == ["玻璃"]
    assert plan.guardrail_decision.policy_locked is True
    assert plan.execution_policy.llm_can_execute is False


def test_query_planning_service_routes_and_writes_jsonl_audit(tmp_path: Path) -> None:
    """统一服务应路由领域 adapter，并把 shadow query_plan_v2 写入 JSONL 审计。"""
    audit_path = tmp_path / "query_planning_v2_audit.jsonl"
    logistics_adapter = LogisticsQueryPlanningAdapter(
        planner=_FakeLogisticsPlanner(
            LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_mw_by_carrier",
                metrics=["shipment_mw"],
                dimensions=["carrier"],
                filters={"year": 2025},
            )
        )
    )
    bom_adapter = PlanBomQueryPlanningAdapter(
        nlu_service=_FakePlanBomNluService(
            PlanBomNluCandidate(question="订单001玻璃", intent="single_order_material_specs", slots={"order_tail_no": ["001"]})
        )
    )
    service = QueryPlanningV2Service(
        logistics_adapter=logistics_adapter,
        plan_bom_adapter=bom_adapter,
        audit_writer=QueryPlanV2AuditWriter(path=audit_path),
    )

    plan = service.plan(question="2025年各承运商发运量是多少？", domain="logistics", trace_id="trace-001")

    assert plan.strategy == "DIRECT_RETRIEVAL"
    assert plan.audit.trace_id == "trace-001"
    assert audit_path.exists()
    text = audit_path.read_text(encoding="utf-8")
    assert "trace-001" in text
    assert "DIRECT_RETRIEVAL" in text
    audit_line = json.loads(text.strip().splitlines()[0])
    assert audit_line["query_plan"]["audit"]["audit_logged"] is True
    assert audit_line["query_plan"]["audit"]["audit_log_path"] == str(audit_path)

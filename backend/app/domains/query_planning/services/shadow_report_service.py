from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domains.query_planning.schemas.query_plan_v2 import QueryPlanningV2Plan
from backend.app.domains.query_planning.services.query_planning_v2_service import QueryPlanningV2Service

QueryPlanningV2ShadowDomain = Literal["logistics", "plan_bom"]


class QueryPlanningV2ShadowCase(BaseModel):
    """Query Planning V2 shadow 回归用例定义。

    参数：
        case_id: 稳定用例 ID。
        category: 验收分类，例如物流明确查询、BOM 缺槽澄清。
        domain: 业务域。
        question: 业务员问法。
        expected_strategy: 期望策略。
        expected_intent: 期望受控意图，可为空。
        expected_query_key: 期望 query_key，可为空。
    返回：
        shadow 报表服务用于回放的最小用例。
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str
    category: str
    domain: QueryPlanningV2ShadowDomain
    question: str
    expected_strategy: str
    expected_intent: str | None = None
    expected_query_key: str | None = None


class QueryPlanningV2ShadowCaseResult(BaseModel):
    """单条 shadow 用例对比结果。"""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    category: str
    domain: QueryPlanningV2ShadowDomain
    question: str
    expected_strategy: str
    actual_strategy: str
    expected_intent: str | None = None
    actual_intent: str | None = None
    expected_query_key: str | None = None
    actual_query_key: str | None = None
    matched: bool = False
    mismatch_reasons: list[str] = Field(default_factory=list)
    query_plan: QueryPlanningV2Plan


class QueryPlanningV2ShadowReport(BaseModel):
    """Query Planning V2 shadow 对比报表。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "query_planning_v2_shadow_report.1"
    total_cases: int = 0
    matched_cases: int = 0
    mismatched_cases: int = 0
    cases: list[QueryPlanningV2ShadowCaseResult] = Field(default_factory=list)


DEFAULT_QUERY_PLANNING_V2_SHADOW_CASES: tuple[QueryPlanningV2ShadowCase, ...] = (
    QueryPlanningV2ShadowCase(
        case_id="logistics_direct_clear",
        category="物流明确查询",
        domain="logistics",
        question="2025年各承运商发运量是多少？",
        expected_strategy="DIRECT_RETRIEVAL",
        expected_intent="aggregate",
        expected_query_key="hist_mw_by_carrier",
    ),
    QueryPlanningV2ShadowCase(
        case_id="logistics_rewrite_colloquial_shadow",
        category="物流口语化查询",
        domain="logistics",
        question="帮我统计一下25年每家物流公司的发运量和占比。",
        expected_strategy="DIRECT_RETRIEVAL",
        expected_intent="aggregate",
        expected_query_key="hist_mw_by_carrier",
    ),
    QueryPlanningV2ShadowCase(
        case_id="logistics_complex_composite",
        category="物流复杂复合查询",
        domain="logistics",
        question="统计24年高运费地址，并列出询比价和招标发运量。",
        expected_strategy="QUERY_DECOMPOSITION",
        expected_intent="composite",
        expected_query_key="composite_decomposed",
    ),
    QueryPlanningV2ShadowCase(
        case_id="logistics_clarify_missing_metric",
        category="物流缺槽澄清",
        domain="logistics",
        question="帮我看一下物流情况。",
        expected_strategy="CLARIFY",
        expected_intent="clarification",
        expected_query_key=None,
    ),
    QueryPlanningV2ShadowCase(
        case_id="logistics_unsupported_prediction",
        category="物流无答案拒答",
        domain="logistics",
        question="预测未来三个月各区域发运量。",
        expected_strategy="UNSUPPORTED",
        expected_intent="unsupported",
        expected_query_key=None,
    ),
    QueryPlanningV2ShadowCase(
        case_id="plan_bom_single_order",
        category="BOM 单订单查询",
        domain="plan_bom",
        question="订单001玻璃规格是什么？",
        expected_strategy="DIRECT_RETRIEVAL",
        expected_intent="single_order_material_specs",
        expected_query_key="single_order_material_specs",
    ),
    QueryPlanningV2ShadowCase(
        case_id="plan_bom_multi_order_table",
        category="BOM 多订单表格",
        domain="plan_bom",
        question="订单001和002的玻璃、焊带做成表格。",
        expected_strategy="DIRECT_RETRIEVAL",
        expected_intent="multi_order_material_table",
        expected_query_key="multi_order_material_table",
    ),
    QueryPlanningV2ShadowCase(
        case_id="plan_bom_order_compare",
        category="BOM 订单对比",
        domain="plan_bom",
        question="订单001和002的关键材料有什么差异？",
        expected_strategy="DIRECT_RETRIEVAL",
        expected_intent="cross_order_material_compare",
        expected_query_key="cross_order_material_compare",
    ),
    QueryPlanningV2ShadowCase(
        case_id="plan_bom_clarify_missing_order",
        category="BOM 缺槽澄清",
        domain="plan_bom",
        question="这个订单玻璃是什么？",
        expected_strategy="CLARIFY",
        expected_intent="single_order_material_specs",
        expected_query_key=None,
    ),
    QueryPlanningV2ShadowCase(
        case_id="plan_bom_variant_power_question",
        category="问法变体鲁棒性",
        domain="plan_bom",
        question="帮我看下这个BOM能不能做到620W占比60%。",
        expected_strategy="CLARIFY",
        expected_intent="plan_power_supplier_recommendation",
        expected_query_key=None,
    ),
)


class QueryPlanningV2ShadowReportService:
    """Query Planning V2 shadow 对比报表服务。

    说明：
        1. 内置 10 类物流 / BOM 验收问题，覆盖明确查询、口语化、复合、澄清和拒答；
        2. 只调用 QueryPlanningV2Service.plan 生成 shadow 计划，不执行正式查询；
        3. 输出期望策略与实际策略的结构化对比，便于灰度回放。
    """

    def __init__(self, *, planning_service: QueryPlanningV2Service) -> None:
        """初始化 shadow 报表服务。"""

        self.planning_service = planning_service

    def build_default_report(self, *, trace_id: str | None = None, write_audit: bool = False) -> QueryPlanningV2ShadowReport:
        """回放默认 10 类用例并生成对比报表。

        参数：
            trace_id: 当前请求追踪号。
            write_audit: 是否让底层 QueryPlanningV2Service 写 JSONL 审计。
        返回：
            Query Planning V2 shadow 对比报表。
        """

        results: list[QueryPlanningV2ShadowCaseResult] = []
        for case in DEFAULT_QUERY_PLANNING_V2_SHADOW_CASES:
            plan = self.planning_service.plan(
                question=case.question,
                domain=case.domain,
                trace_id=f"{trace_id}:{case.case_id}" if trace_id else case.case_id,
                write_audit=write_audit,
            )
            results.append(self._compare(case, plan))
        matched_cases = sum(1 for result in results if result.matched)
        return QueryPlanningV2ShadowReport(
            total_cases=len(results),
            matched_cases=matched_cases,
            mismatched_cases=len(results) - matched_cases,
            cases=results,
        )

    @staticmethod
    def _compare(case: QueryPlanningV2ShadowCase, plan: QueryPlanningV2Plan) -> QueryPlanningV2ShadowCaseResult:
        """对比单条用例期望与实际 query_plan。"""

        mismatch_reasons: list[str] = []
        if plan.strategy != case.expected_strategy:
            mismatch_reasons.append(f"strategy 期望 {case.expected_strategy}，实际 {plan.strategy}")
        if case.expected_intent is not None and plan.intent != case.expected_intent:
            mismatch_reasons.append(f"intent 期望 {case.expected_intent}，实际 {plan.intent}")
        if plan.query_key != case.expected_query_key:
            mismatch_reasons.append(f"query_key 期望 {case.expected_query_key}，实际 {plan.query_key}")
        return QueryPlanningV2ShadowCaseResult(
            case_id=case.case_id,
            category=case.category,
            domain=case.domain,
            question=case.question,
            expected_strategy=case.expected_strategy,
            actual_strategy=plan.strategy,
            expected_intent=case.expected_intent,
            actual_intent=plan.intent,
            expected_query_key=case.expected_query_key,
            actual_query_key=plan.query_key,
            matched=not mismatch_reasons,
            mismatch_reasons=mismatch_reasons,
            query_plan=plan,
        )


__all__ = [
    "DEFAULT_QUERY_PLANNING_V2_SHADOW_CASES",
    "QueryPlanningV2ShadowCase",
    "QueryPlanningV2ShadowCaseResult",
    "QueryPlanningV2ShadowReport",
    "QueryPlanningV2ShadowReportService",
]

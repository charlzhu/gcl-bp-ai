from __future__ import annotations

from backend.app.domains.business_analysis.services.inventory_sales_production.nl_query_planner import (
    InventorySalesProductionNlQueryPlanner,
    InventorySalesProductionPlanningError,
)
from backend.app.domains.query_planning.schemas.query_plan_v2 import (
    QueryPlanningV2GuardrailDecision,
    QueryPlanningV2Plan,
)

# M10：产销存经营分析领域 adapter，复用 M4 临时规划器输出 query_plan，
# 转换为 Query Planning V2 格式供统一入口使用，不执行正式查询。


class InventorySalesProductionQueryPlanningAdapter:
    """产销存 Query Planning V2 领域适配器。

    说明：
        1. 复用 M4 InventorySalesProductionNlQueryPlanner 生成受控 QueryPlan；
        2. 转换为统一 QueryPlanningV2Plan，不执行 SQL、不查数；
        3. 保持 M3/M4 QueryExecutor 不变。
    """

    def __init__(self, *, planner: InventorySalesProductionNlQueryPlanner | None = None) -> None:
        self.planner = planner or InventorySalesProductionNlQueryPlanner()

    def build_candidate(self, question: str, *, trace_id: str | None = None) -> QueryPlanningV2Plan:
        """生成产销存查询规划候选。

        参数：
            question: 用户自然语言问题。
            trace_id: 请求追踪号。
        返回：
            QueryPlanningV2Plan，策略由上游 strategy_router 最终裁决。
        """

        try:
            query_plan = self.planner.build_plan(question)
        except InventorySalesProductionPlanningError as exc:
            return QueryPlanningV2Plan(
                domain="business_analysis",
                sub_domain="inventory_sales_production",
                original_question=question,
                strategy="CLARIFY" if exc.status == "clarification" else "UNSUPPORTED",
                intent="clarification" if exc.status == "clarification" else "unsupported",
                query_key=query_plan.query_key if exc.status == "clarification" else None,  # type: ignore[union-attr]
                clarification_questions=[exc.message] if exc.status == "clarification" else [],
                unsupported_reason=exc.message if exc.status == "unsupported" else None,
                guardrail_decision=QueryPlanningV2GuardrailDecision(
                    guardrail_enabled=True,
                    guardrail_mode="fail_closed",
                    final_source="planner_rejected",
                    policy_locked=True,
                    accepted=False,
                    blocked_reason=exc.message,
                ),
            )

        return QueryPlanningV2Plan(
            domain="business_analysis",
            sub_domain="inventory_sales_production",
            original_question=question,
            strategy="DIRECT_RETRIEVAL",
            intent="query",
            query_key=query_plan.query_key,
            metrics=list(query_plan.metrics),
            dimensions=list(query_plan.dimensions),
            filters=query_plan.filters,
            period_type=query_plan.period.period_type,
            year=query_plan.period.year,
            month=query_plan.period.month,
            quarter=query_plan.period.quarter,
            guardrail_decision=QueryPlanningV2GuardrailDecision(
                guardrail_enabled=True,
                guardrail_mode="shadow",
                final_source="m4_planner",
                policy_locked=True,
                accepted=True,
            ),
        )


__all__ = ["InventorySalesProductionQueryPlanningAdapter"]

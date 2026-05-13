from __future__ import annotations

from typing import Any

from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaPlan
from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.query_planner_v2 import LogisticsQueryPlannerV2, LogisticsQueryPlannerV2Fallback
from backend.app.domains.query_planning.schemas.query_plan_v2 import (
    QueryPlanningV2GuardrailDecision,
    QueryPlanningV2Plan,
    QueryPlanningV2Slots,
    QueryPlanningV2SubQuery,
)


class LogisticsQueryPlanningAdapter:
    """物流 Query Planning V2 适配器。

    说明：
        1. 复用现有 LogisticsDataQaPlanner 产出的白名单 query_key；
        2. 不调用 LogisticsDataQaService.query，因此不会执行 SQL / 写正式查询历史 / 生成最终答案；
        3. 只把现有规则计划包装成统一 query_plan_v2，用于 Phase 3 shadow 诊断。
    """

    def __init__(
        self,
        planner: LogisticsDataQaPlanner | Any | None = None,
        planner_v2: LogisticsQueryPlannerV2 | Any | None = None,
    ) -> None:
        """初始化物流适配器。

        参数：
            planner: 可注入的物流规则 planner；测试场景可传 fake planner。
            planner_v2: 可注入的新物流 Query Planner V2；默认随配置 shadow 开关启用。
        返回：无返回值。
        """

        self.planner = planner or LogisticsDataQaPlanner()
        self.planner_v2 = planner_v2 or LogisticsQueryPlannerV2(
            fallback=LogisticsQueryPlannerV2Fallback(legacy_planner=self.planner)
        )

    def build_candidate(self, question: str, *, trace_id: str | None = None) -> QueryPlanningV2Plan:
        """构建物流领域 query_plan_v2 候选。

        参数：
            question: 用户原始问题。
            trace_id: 可选追踪号。
        返回：
            物流领域统一 query_plan_v2。
        业务逻辑：只复用 planner 的受控结果，不触发正式 Data QA 主链路执行。
        """

        if self._should_use_planner_v2():
            return self.planner_v2.build_shadow_plan(question, trace_id=trace_id)

        rule_plan: LogisticsDataQaPlan = self.planner.build_plan(question)
        strategy = self._strategy_from_rule_plan(rule_plan)
        sub_queries = self._sub_queries_from_rule_plan(rule_plan)
        clarification_questions = list(rule_plan.clarification_questions or [])
        if strategy == "CLARIFY" and not clarification_questions:
            clarification_questions = ["当前问题缺少可执行查询条件，请补充时间、指标、维度或业务对象后再查询。"]

        plan = QueryPlanningV2Plan(
            domain="logistics",
            original_question=question,
            strategy=strategy,
            intent=rule_plan.intent,
            query_key=rule_plan.query_key,
            slots=QueryPlanningV2Slots(
                metrics=list(rule_plan.metrics or []),
                dimensions=list(rule_plan.dimensions or []),
                filters=dict(rule_plan.filters or {}),
                group_by=list(rule_plan.group_by or []),
                sort=list(rule_plan.sort or []),
                limit=rule_plan.limit,
            ),
            sub_queries=sub_queries,
            clarification_questions=clarification_questions,
            unsupported_reason=rule_plan.unsupported_reason,
            guardrail_decision=QueryPlanningV2GuardrailDecision(
                guardrail_enabled=True,
                guardrail_mode="rule",
                final_source="rule",
                policy_locked=True,
                accepted=True,
                notes=["复用物流规则 planner 结果；Phase 3 不执行 Data QA 查询。"],
            ),
            rule_plan=rule_plan.model_dump(mode="json"),
        )
        plan.audit.trace_id = trace_id
        return plan

    def _should_use_planner_v2(self) -> bool:
        """判断是否启用新的物流 Query Planner V2 shadow 编排。

        参数：无。
        返回：
            True 表示调用 LLM QueryPlan candidate + Validator；False 表示沿用旧规则 planner 包装。
        业务逻辑：默认配置关闭，因此不会影响正式物流 QA 或既有诊断链路。
        """

        should_use = getattr(self.planner_v2, "should_use", None)
        return bool(callable(should_use) and should_use())

    @staticmethod
    def _strategy_from_rule_plan(rule_plan: LogisticsDataQaPlan) -> str:
        """根据物流规则计划推导初始策略。"""

        if rule_plan.intent == "unsupported" or rule_plan.unsupported_reason:
            return "UNSUPPORTED"
        if rule_plan.needs_clarification or rule_plan.intent == "clarification":
            return "CLARIFY"
        if rule_plan.query_key == "composite_decomposed":
            return "QUERY_DECOMPOSITION"
        if rule_plan.query_key:
            return "DIRECT_RETRIEVAL"
        return "CLARIFY"

    def _sub_queries_from_rule_plan(self, rule_plan: LogisticsDataQaPlan) -> list[QueryPlanningV2SubQuery]:
        """从 composite_decomposed 规则计划中提取受控子查询。"""

        if rule_plan.query_key != "composite_decomposed":
            return []
        raw_sub_plans = (rule_plan.filters or {}).get("sub_plans")
        if not isinstance(raw_sub_plans, list):
            return []
        sub_queries: list[QueryPlanningV2SubQuery] = []
        for index, item in enumerate(raw_sub_plans, start=1):
            if not isinstance(item, dict):
                continue
            filters = item.get("filters") if isinstance(item.get("filters"), dict) else {}
            sub_queries.append(
                QueryPlanningV2SubQuery(
                    sub_query_id=f"logistics_sub_{index}",
                    source_clause=str(item.get("source_clause") or item.get("section_label") or f"sub_{index}"),
                    domain="logistics",
                    intent=item.get("intent"),
                    query_key=item.get("query_key"),
                    slots=QueryPlanningV2Slots(
                        metrics=list(item.get("metrics") or []),
                        dimensions=list(item.get("dimensions") or []),
                        filters=dict(filters),
                        group_by=list(item.get("group_by") or []),
                        sort=list(item.get("sort") or []),
                        limit=item.get("limit"),
                    ),
                    executable=bool(item.get("query_key")),
                    merge_policy="按 section_label 分区展示并保持子查询独立结果。",
                    guardrail_notes=["子查询来自现有 composite_decomposed 受控计划。"],
                )
            )
        return sub_queries


__all__ = ["LogisticsQueryPlanningAdapter"]

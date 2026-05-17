from __future__ import annotations

from typing import Any

from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaPlan
from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.query_planning.schemas.query_plan_v2 import (
    QueryPlanningV2GuardrailDecision,
    QueryPlanningV2Plan,
    QueryPlanningV2Slots,
    QueryPlanningV2SubQuery,
)


class LogisticsQueryPlannerV2Fallback:
    """物流 Query Planner V2 的旧 planner fallback。

    业务逻辑：当 LLM 不可用、低置信或 Validator fail closed 时，保留旧规则 planner 的正式能力，
    并把失败原因写入 shadow 审计，不改变正式物流 QA 答案。
    """

    def __init__(self, legacy_planner: LogisticsDataQaPlanner | Any | None = None) -> None:
        """初始化 fallback。

        参数：
            legacy_planner: 旧 LogisticsDataQaPlanner 或测试 fake。
        返回：无。
        """

        self.legacy_planner = legacy_planner or LogisticsDataQaPlanner()

    def build_legacy_plan(self, question: str) -> LogisticsDataQaPlan:
        """调用旧规则 planner 生成受控 plan；不执行 Data QA 查询。"""

        return self.legacy_planner.build_plan(question)

    def to_query_plan(self, *, question: str, trace_id: str | None = None, reason: str) -> QueryPlanningV2Plan:
        """回退旧 planner 并包装成 QueryPlanningV2Plan。

        参数：
            question: 原始问题。
            trace_id: 请求追踪号。
            reason: 触发 fallback 的原因。
        返回：
            仅用于 shadow 诊断的 QueryPlanningV2Plan。
        """

        rule_plan = self.build_legacy_plan(question)
        strategy = self._strategy_from_rule_plan(rule_plan)
        plan = QueryPlanningV2Plan(
            domain="logistics",
            original_question=question,
            strategy=strategy,
            intent=rule_plan.intent,
            query_key=rule_plan.query_key if strategy in {"DIRECT_RETRIEVAL", "QUERY_DECOMPOSITION"} else None,
            slots=QueryPlanningV2Slots(
                metrics=list(rule_plan.metrics or []),
                dimensions=list(rule_plan.dimensions or []),
                filters=dict(rule_plan.filters or {}),
                group_by=list(rule_plan.group_by or []),
                sort=list(rule_plan.sort or []),
                limit=rule_plan.limit,
            ),
            sub_queries=self._sub_queries_from_rule_plan(rule_plan),
            clarification_questions=list(rule_plan.clarification_questions or []) if strategy == "CLARIFY" else [],
            unsupported_reason=rule_plan.unsupported_reason if strategy == "UNSUPPORTED" else None,
            guardrail_decision=QueryPlanningV2GuardrailDecision(
                guardrail_enabled=True,
                guardrail_mode="llm_query_planner_v2_fallback",
                final_source="legacy_rule_planner_fallback",
                policy_locked=True,
                accepted=False,
                blocked_reason=reason,
                notes=[
                    "物流 Query Planner V2 未放行，已回退旧规则 planner。",
                    "fallback 不执行 SQL，不替换正式 QA 主链路。",
                ],
            ),
            rule_plan=rule_plan.model_dump(mode="json"),
        )
        plan.audit.trace_id = trace_id
        return plan

    @staticmethod
    def _strategy_from_rule_plan(rule_plan: LogisticsDataQaPlan) -> str:
        """根据旧 plan 推导 Query Planning V2 策略。"""

        if rule_plan.intent == "unsupported" or rule_plan.unsupported_reason:
            return "UNSUPPORTED"
        if rule_plan.needs_clarification or rule_plan.intent == "clarification":
            return "CLARIFY"
        if rule_plan.query_key == "composite_decomposed":
            return "QUERY_DECOMPOSITION"
        if rule_plan.query_key:
            return "DIRECT_RETRIEVAL"
        return "CLARIFY"

    @staticmethod
    def _sub_queries_from_rule_plan(rule_plan: LogisticsDataQaPlan) -> list[QueryPlanningV2SubQuery]:
        """从旧 composite_decomposed plan 提取子查询快照。"""

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
                    merge_policy="旧规则 planner fallback 子查询，仅用于 shadow 对比。",
                    guardrail_notes=["子查询来自旧 composite_decomposed 受控计划。"],
                )
            )
        return sub_queries


__all__ = ["LogisticsQueryPlannerV2Fallback"]

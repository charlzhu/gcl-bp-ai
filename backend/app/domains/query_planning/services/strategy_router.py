from __future__ import annotations

from backend.app.domains.query_planning.schemas.query_plan_v2 import (
    QueryPlanningV2ExecutionPolicy,
    QueryPlanningV2Plan,
)


class QueryPlanningV2StrategyRouter:
    """Query Planning V2 策略路由器。

    说明：
        1. 只基于既有规则 plan / NLU 候选 / Guardrail 结果做安全归类；
        2. 不调用数据库、不执行查询、不生成 SQL；
        3. 采用 fail closed：无法确定时回到 CLARIFY。
    """

    def route(self, plan: QueryPlanningV2Plan) -> QueryPlanningV2Plan:
        """根据计划字段确定最终策略。

        参数：
            plan: adapter 产出的候选 query_plan。
        返回：
            已归一 strategy 和 execution_policy 的 query_plan。
        业务逻辑：拒答/澄清优先于可执行查询；复合拆分优先于普通 DIRECT。
        """

        routed = plan.model_copy(deep=True)
        strategy = self._decide_strategy(routed)
        routed.strategy = strategy
        if strategy == "CLARIFY" and not routed.clarification_questions:
            routed.clarification_questions = ["当前问题缺少可执行查询条件，请补充业务域、时间、指标、维度或实体信息。"]
        routed.execution_policy = self._policy_for(routed)
        # 重新触发 schema 层策略校验，确保 HYDE / 拒答等安全边界不会被调用方覆盖。
        return QueryPlanningV2Plan.model_validate(routed.model_dump(mode="json"))

    def _decide_strategy(self, plan: QueryPlanningV2Plan) -> str:
        """按安全优先级判断策略。"""

        if plan.unsupported_reason or plan.intent == "unsupported" or plan.strategy == "UNSUPPORTED":
            return "UNSUPPORTED"
        if plan.no_answer_reason or plan.strategy == "NO_ANSWER":
            return "NO_ANSWER"
        if plan.clarification_questions or plan.intent == "clarification":
            return "CLARIFY"
        if plan.query_key == "composite_decomposed" or plan.sub_queries:
            return "QUERY_DECOMPOSITION"
        if plan.query_key:
            return "DIRECT_RETRIEVAL"
        if plan.hyde_text:
            return "HYDE_RETRIEVAL"
        if plan.rewritten_question:
            return "QUERY_REWRITE_SIMPLIFY"
        return "CLARIFY"

    def _policy_for(self, plan: QueryPlanningV2Plan) -> QueryPlanningV2ExecutionPolicy:
        """为策略生成最小安全执行策略。"""

        allowed_query_keys = []
        if plan.query_key:
            allowed_query_keys.append(plan.query_key)
        for sub_query in plan.sub_queries:
            if sub_query.query_key and sub_query.query_key not in allowed_query_keys:
                allowed_query_keys.append(sub_query.query_key)
        policy = QueryPlanningV2ExecutionPolicy(allowed_query_keys=allowed_query_keys)
        if plan.strategy in {"DIRECT_RETRIEVAL", "QUERY_DECOMPOSITION"}:
            policy.executable = bool(plan.query_key)
        elif plan.strategy == "HYDE_RETRIEVAL":
            policy.retrieval_only = True
            policy.executable = False
        else:
            policy.executable = False
        return policy


__all__ = ["QueryPlanningV2StrategyRouter"]

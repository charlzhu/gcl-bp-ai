from __future__ import annotations

from typing import Any

from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaPlan, LogisticsDataQaResult
from backend.app.domains.logistics.schemas.llm_understanding import LogisticsLlmGuardrailDecision
from backend.app.domains.plan_bom.schemas.qa import PlanBomNluCandidate, PlanBomQaResponse
from backend.app.domains.query_planning.schemas.query_plan_v2 import (
    QueryPlanningV2GuardrailDecision,
    QueryPlanningV2Plan,
    QueryPlanningV2Slots,
    QueryPlanningV2SubQuery,
)
from backend.app.domains.query_planning.services.strategy_router import QueryPlanningV2StrategyRouter


class QueryPlanningV2ShadowSnapshotBuilder:
    """从正式问答结果构建 Query Planning V2 shadow 快照。

    说明：
        1. 只消费已经产生的规则 plan / NLU / Guardrail 决策，不重新查库、不重新规划；
        2. 生成的 query_plan_v2 仅写入 sys_query_log.request_payload 作为审计元数据；
        3. 不改变物流 Data QA 或 BOM QA 的正式执行结果。
    """

    def __init__(self, router: QueryPlanningV2StrategyRouter | None = None) -> None:
        """初始化 shadow 快照构建器。

        参数：
            router: Query Planning V2 策略路由器，测试可注入。
        返回：无返回值。
        """

        self.router = router or QueryPlanningV2StrategyRouter()

    def build_logistics_snapshot(
        self,
        *,
        question: str,
        result: LogisticsDataQaResult,
        trace_id: str | None = None,
        guardrail_decision: LogisticsLlmGuardrailDecision | None = None,
    ) -> dict[str, Any]:
        """构建物流问答 query_plan_v2 shadow 快照。

        参数：
            question: 用户原始问题。
            result: 物流 Data QA 正式结果。
            trace_id: 当前请求追踪号。
            guardrail_decision: 物流 LLM Guardrail 决策快照，可为空。
        返回：
            可 JSON 序列化的 query_plan_v2 快照。
        业务逻辑：从正式结果反推 shadow strategy，不执行 Data QA 查询。
        """

        rule_plan = result.query_plan
        strategy = self._logistics_strategy(rule_plan=rule_plan, result=result)
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
            sub_queries=self._logistics_sub_queries(rule_plan),
            clarification_questions=list(result.clarification_questions or rule_plan.clarification_questions or []),
            no_answer_reason=self._logistics_no_answer_reason(result),
            unsupported_reason=rule_plan.unsupported_reason if strategy == "UNSUPPORTED" else None,
            guardrail_decision=self._logistics_guardrail_decision(guardrail_decision),
            rule_plan=rule_plan.model_dump(mode="json"),
        )
        routed = self.router.route(plan)
        routed.audit.trace_id = trace_id
        return routed.model_dump(mode="json")

    def build_plan_bom_snapshot(
        self,
        *,
        question: str,
        response: PlanBomQaResponse,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """构建计划 BOM 问答 query_plan_v2 shadow 快照。

        参数：
            question: 用户原始问题。
            response: BOM QA 正式响应。
            trace_id: 当前请求追踪号。
        返回：
            可 JSON 序列化的 query_plan_v2 快照。
        业务逻辑：复用 BOM NLU Center 输出，不触发 PlanBomQaService.ask 或任何查询。
        """

        candidate = response.nlu
        strategy = self._plan_bom_strategy(response)
        plan = QueryPlanningV2Plan(
            domain="plan_bom",
            original_question=question,
            strategy=strategy,
            intent=candidate.intent,
            query_key=candidate.intent if strategy == "DIRECT_RETRIEVAL" else None,
            slots=QueryPlanningV2Slots(filters=dict(candidate.slots or {})),
            clarification_questions=self._plan_bom_clarification_questions(candidate, response) if strategy == "CLARIFY" else [],
            no_answer_reason=response.answer_summary if strategy == "NO_ANSWER" else None,
            unsupported_reason=response.answer_summary if strategy == "UNSUPPORTED" else None,
            guardrail_decision=QueryPlanningV2GuardrailDecision(
                guardrail_enabled=True,
                guardrail_mode=candidate.provider_mode,
                final_source="nlu_center",
                policy_locked=True,
                accepted=strategy not in {"UNSUPPORTED", "NO_ANSWER"},
                notes=list(candidate.guardrail_notes or []) + ["从 BOM QA 正式响应构建 Query Planning V2 shadow 快照。"],
                raw_decision={
                    "provider_mode": candidate.provider_mode,
                    "confidence": candidate.confidence,
                    "missing_slots": list(candidate.missing_slots or []),
                    "classification": response.classification,
                    "status": response.status.model_dump(mode="json"),
                },
            ),
            rule_plan={
                "nlu": candidate.model_dump(mode="json"),
                "classification": response.classification,
                "status": response.status.model_dump(mode="json"),
            },
        )
        routed = self.router.route(plan)
        routed.audit.trace_id = trace_id
        return routed.model_dump(mode="json")

    @staticmethod
    def _logistics_strategy(*, rule_plan: LogisticsDataQaPlan, result: LogisticsDataQaResult) -> str:
        """根据物流正式结果推导 shadow 策略。"""

        status_code = result.status.code if result.status else ""
        if rule_plan.unsupported_reason or not result.supported or rule_plan.intent == "unsupported":
            return "UNSUPPORTED"
        if status_code == "EMPTY_RESULT":
            return "NO_ANSWER"
        if result.needs_clarification or rule_plan.needs_clarification or rule_plan.intent == "clarification":
            return "CLARIFY"
        if rule_plan.query_key == "composite_decomposed":
            return "QUERY_DECOMPOSITION"
        if rule_plan.query_key:
            return "DIRECT_RETRIEVAL"
        return "CLARIFY"

    @staticmethod
    def _logistics_no_answer_reason(result: LogisticsDataQaResult) -> str | None:
        """空结果时生成 NO_ANSWER 原因；非空结果返回 None。"""

        if result.status and result.status.code == "EMPTY_RESULT":
            return result.answer_summary or result.status.message
        return None

    @staticmethod
    def _logistics_guardrail_decision(
        decision: LogisticsLlmGuardrailDecision | None,
    ) -> QueryPlanningV2GuardrailDecision:
        """把物流 Guardrail 决策转换成 Query Planning V2 摘要。"""

        if decision is None:
            return QueryPlanningV2GuardrailDecision(
                guardrail_enabled=True,
                guardrail_mode="rule",
                final_source="rule",
                policy_locked=True,
                accepted=True,
                notes=["正式结果未携带 LLM Guardrail 决策；按规则 planner 快照记录。"],
            )
        raw_decision = decision.model_dump(mode="json")
        return QueryPlanningV2GuardrailDecision(
            guardrail_enabled=decision.guardrail_enabled,
            guardrail_mode=decision.guardrail_mode,
            final_source=decision.final_source,
            policy_locked=decision.policy_locked,
            accepted=not bool(decision.blocked_reason),
            blocked_reason=decision.blocked_reason,
            notes=[
                "复用物流 LLM Understanding Guardrail 决策。",
                f"最终来源：{decision.final_source}。",
            ],
            raw_decision=raw_decision,
        )

    @staticmethod
    def _logistics_sub_queries(rule_plan: LogisticsDataQaPlan) -> list[QueryPlanningV2SubQuery]:
        """从物流 composite_decomposed 计划提取受控子查询。"""

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
                    merge_policy="按受控 composite_decomposed 子查询独立展示并合并结果。",
                    guardrail_notes=["子查询来自正式物流 Data QA composite_decomposed 计划。"],
                )
            )
        return sub_queries

    @staticmethod
    def _plan_bom_strategy(response: PlanBomQaResponse) -> str:
        """根据 BOM QA 响应推导 shadow 策略。"""

        if response.classification == "C" or response.status.code == "UNSUPPORTED_QUESTION" or response.nlu.intent == "unsupported":
            return "UNSUPPORTED"
        if response.status.code == "EMPTY_RESULT":
            return "NO_ANSWER"
        if response.classification == "B" or response.status.code == "CLARIFICATION_REQUIRED" or response.nlu.missing_slots:
            return "CLARIFY"
        return "DIRECT_RETRIEVAL"

    @staticmethod
    def _plan_bom_clarification_questions(candidate: PlanBomNluCandidate, response: PlanBomQaResponse) -> list[str]:
        """按 BOM 缺失槽位生成 shadow 澄清问题。"""

        questions: list[str] = []
        missing = set(candidate.missing_slots or [])
        if "order_id" in missing:
            questions.append("请补充订单号、BOM 文件名或客户实例，以便缩窄到明确的计划 BOM。")
        if "compare_orders" in missing:
            questions.append("请补充至少两个订单号、BOM 文件名或客户实例，以便进行对比或表格汇总。")
        if "material_category" in missing:
            questions.append("请补充要查询的材料类别，例如玻璃、焊带、汇流条、接线盒或胶膜。")
        if "target_power_ratio" in missing:
            questions.append("请补充目标功率档位及比例，例如“620W 占比 60%”。")
        if response.answer_summary and response.answer_summary not in questions:
            questions.append(response.answer_summary)
        if not questions:
            questions.append("当前计划 BOM 问题缺少可执行条件，请补充订单、版本、物料或目标功率等信息。")
        return questions


__all__ = ["QueryPlanningV2ShadowSnapshotBuilder"]

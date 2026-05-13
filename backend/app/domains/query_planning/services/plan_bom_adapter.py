from __future__ import annotations

from typing import Any

from backend.app.domains.plan_bom.schemas.qa import PlanBomNluCandidate
from backend.app.domains.query_planning.schemas.query_plan_v2 import (
    QueryPlanningV2GuardrailDecision,
    QueryPlanningV2Plan,
    QueryPlanningV2Slots,
)


class PlanBomQueryPlanningAdapter:
    """计划 BOM Query Planning V2 适配器。

    说明：
        1. 只调用 PlanBomNluCenterService.understand，复用已有 NLU / Guardrail；
        2. 不调用 PlanBomQaService.ask，避免查数、写历史或生成最终答案；
        3. Phase 3 默认 use_llm=False，先以规则 NLU shadow 诊断为主。
    """

    def __init__(self, nlu_service: Any) -> None:
        """初始化 BOM 适配器。

        参数：
            nlu_service: 计划 BOM NLU Center 或测试 fake service。
        返回：无返回值。
        """

        self.nlu_service = nlu_service

    def build_candidate(
        self,
        question: str,
        *,
        trace_id: str | None = None,
    ) -> QueryPlanningV2Plan:
        """构建计划 BOM 领域 query_plan_v2 候选。

        参数：
            question: 用户原始问题。
            trace_id: 可选追踪号。
        返回：
            计划 BOM 统一 query_plan_v2。
        """

        candidate: PlanBomNluCandidate = self.nlu_service.understand(question, use_llm=False)
        strategy = self._strategy_from_candidate(candidate)
        query_key = self._query_key_from_candidate(candidate, strategy)
        clarification_questions = self._clarification_questions(candidate) if strategy == "CLARIFY" else []
        unsupported_reason = "当前计划 BOM 数据源暂不支持该类问题。" if strategy == "UNSUPPORTED" else None

        plan = QueryPlanningV2Plan(
            domain="plan_bom",
            original_question=question,
            strategy=strategy,
            intent=candidate.intent,
            query_key=query_key,
            slots=QueryPlanningV2Slots(filters=dict(candidate.slots or {})),
            clarification_questions=clarification_questions,
            unsupported_reason=unsupported_reason,
            guardrail_decision=QueryPlanningV2GuardrailDecision(
                guardrail_enabled=True,
                guardrail_mode=candidate.provider_mode,
                final_source="nlu_center",
                policy_locked=True,
                accepted=True,
                notes=list(candidate.guardrail_notes or []) + ["Phase 3 仅调用 NLU Center，不执行 PlanBomQaService.ask。"],
                raw_decision={
                    "provider_mode": candidate.provider_mode,
                    "confidence": candidate.confidence,
                    "missing_slots": list(candidate.missing_slots or []),
                },
            ),
            rule_plan=candidate.model_dump(mode="json"),
        )
        plan.audit.trace_id = trace_id
        return plan

    @staticmethod
    def _strategy_from_candidate(candidate: PlanBomNluCandidate) -> str:
        """根据 BOM NLU 候选推导初始策略。"""

        if candidate.intent == "unsupported":
            return "UNSUPPORTED"
        if candidate.intent == "clarification" or candidate.missing_slots:
            return "CLARIFY"
        return "DIRECT_RETRIEVAL"

    @staticmethod
    def _query_key_from_candidate(candidate: PlanBomNluCandidate, strategy: str) -> str | None:
        """把 BOM intent 映射到受控 query_key。

        当前 Plan BOM 主链路以 intent 驱动受控 service；Phase 3 先保留 intent 作为
        可执行 key 的候选，不引入新的自由 query_key。
        """

        if strategy != "DIRECT_RETRIEVAL":
            return None
        return candidate.intent

    @staticmethod
    def _clarification_questions(candidate: PlanBomNluCandidate) -> list[str]:
        """按缺失槽位生成确定性澄清问题。"""

        missing = set(candidate.missing_slots or [])
        questions: list[str] = []
        if "order_id" in missing:
            questions.append("请补充订单号、BOM 文件名或客户实例，以便缩窄到明确的计划 BOM。")
        if "target_power_ratio" in missing:
            questions.append("请补充目标功率档位及比例，例如“620W 占比 60%”。")
        if not questions:
            questions.append("当前计划 BOM 问题缺少可执行条件，请补充订单、版本、物料或目标功率等信息。")
        return questions


__all__ = ["PlanBomQueryPlanningAdapter"]

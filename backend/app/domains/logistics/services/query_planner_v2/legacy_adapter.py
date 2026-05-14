from __future__ import annotations

from typing import Any

from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaPlan
from backend.app.domains.logistics.services.query_planner_v2.llm_parser import LogisticsQueryPlannerV2Candidate
from backend.app.domains.logistics.services.query_planner_v2.validator import LogisticsQueryPlannerV2ValidationResult
from backend.app.domains.query_planning.schemas.query_plan_v2 import (
    QueryPlanningV2GuardrailDecision,
    QueryPlanningV2Plan,
    QueryPlanningV2Slots,
)


class LogisticsQueryPlannerV2LegacyAdapter:
    """物流 Query Planner V2 与现有 LogisticsDataQaPlan 的适配器。

    业务逻辑：
        1. V2 校验通过后，只转换为既有白名单 plan 结构；
        2. 不生成 SQL，不调用 Repository，不计算答案；
        3. 当前阶段只用于 shadow/diagnose，不替换正式 QA 主链路。
    """

    def to_logistics_plan(self, candidate: LogisticsQueryPlannerV2Candidate) -> LogisticsDataQaPlan:
        """把已校验候选转换成现有物流受控 plan。

        参数：
            candidate: Validator accepted 的候选。
        返回：
            可被既有 service/repository 理解的 LogisticsDataQaPlan。
        """

        if candidate.unsupported_reason:
            return LogisticsDataQaPlan(
                intent="unsupported",
                unsupported_reason=candidate.unsupported_reason,
                unsupported_category="query_planner_v2_unsupported",
            )
        if candidate.clarification_questions:
            return LogisticsDataQaPlan(
                intent="clarification",
                needs_clarification=True,
                clarification_questions=list(candidate.clarification_questions),
                clarification_category="query_planner_v2_missing_slots",
            )
        return LogisticsDataQaPlan(
            intent=candidate.intent or "aggregate",
            query_key=candidate.query_key,
            metrics=list(candidate.metrics),
            dimensions=list(candidate.dimensions),
            filters=dict(candidate.filters),
            group_by=list(candidate.group_by),
        )

    def to_query_plan(
        self,
        *,
        candidate: LogisticsQueryPlannerV2Candidate,
        validation: LogisticsQueryPlannerV2ValidationResult,
        original_question: str,
        trace_id: str | None = None,
        legacy_rule_plan: LogisticsDataQaPlan | None = None,
        mode: str = "shadow",
    ) -> QueryPlanningV2Plan:
        """把 V2 候选转换成 QueryPlanningV2Plan shadow 快照。

        参数：
            candidate: 归一后的候选。
            validation: Validator 校验结果。
            original_question: 用户原始问题。
            trace_id: 请求追踪号。
            legacy_rule_plan: 旧规则 planner 快照，用于对比和 fallback 审计。
            mode: 当前 V2 模式，默认 shadow。
        返回：
            统一 QueryPlanningV2Plan，不执行正式查询。
        """

        accepted = validation.accepted
        strategy = "DIRECT_RETRIEVAL" if accepted and candidate.query_key else "CLARIFY"
        clarification_questions = [] if accepted else self._clarification_from_errors(validation.errors)
        plan = QueryPlanningV2Plan(
            domain="logistics",
            original_question=original_question,
            strategy=strategy,
            intent=candidate.intent if accepted else "clarification",
            query_key=candidate.query_key if accepted else None,
            slots=QueryPlanningV2Slots(
                metrics=list(candidate.metrics),
                dimensions=list(candidate.dimensions),
                filters=dict(candidate.filters),
                time_range=dict(candidate.time_range),
                group_by=list(candidate.group_by),
                aggregations=list(candidate.aggregations),
                compare_mode=candidate.compare_mode,
            ),
            clarification_questions=clarification_questions,
            guardrail_decision=QueryPlanningV2GuardrailDecision(
                guardrail_enabled=True,
                guardrail_mode="llm_query_planner_v2",
                final_source=f"llm_query_planner_v2_{mode}",
                policy_locked=True,
                accepted=accepted,
                blocked_reason=None if accepted else ";".join(validation.errors),
                notes=[
                    "LLM 只生成 QueryPlan 候选；后端 Validator 已完成白名单和业务边界校验。",
                    "当前阶段保持 shadow，不替换正式物流 Data QA 主链路。",
                ],
                raw_decision={
                    "validation_errors": list(validation.errors),
                    "validation_warnings": list(validation.warnings),
                    "provider_mode": candidate.provider_mode,
                    "provider_error": candidate.provider_error,
                    "time_range": dict(candidate.time_range),
                },
            ),
            rule_plan=legacy_rule_plan.model_dump(mode="json") if legacy_rule_plan else {},
            llm_result=self._candidate_dump(candidate),
            confidence=candidate.confidence,
        )
        plan.audit.trace_id = trace_id
        return plan

    @staticmethod
    def _candidate_dump(candidate: LogisticsQueryPlannerV2Candidate) -> dict[str, Any]:
        """生成可序列化候选快照。"""

        return candidate.model_dump(mode="json")

    @staticmethod
    def _clarification_from_errors(errors: list[str]) -> list[str]:
        """把阻断原因转换成业务可理解的澄清问题。"""

        if any(error.startswith("multi_hop_route") for error in errors):
            return ["当前只支持单一始发地到单一目的地的线路运价，请明确要查询哪一段路线。"]
        if any(error.startswith("origin_not_normalized") for error in errors):
            return ["请确认始发地是否为当前历史台账支持的合肥或阜宁，或补充可匹配的始发地口径。"]
        if any(error.startswith("time_scope_mismatch") for error in errors):
            return ["当前历史线路运价只支持 2023-2025 历史台账；2026 系统数据请改问系统数据口径。"]
        if any(error.startswith("low_confidence") for error in errors):
            return ["当前问题语义识别置信度不足，请补充年份、始发地、目的地、车型和运费口径。"]
        return ["当前 Query Planner V2 候选未通过后端安全校验，请补充明确的时间、线路、车型和指标口径。"]


__all__ = ["LogisticsQueryPlannerV2LegacyAdapter"]

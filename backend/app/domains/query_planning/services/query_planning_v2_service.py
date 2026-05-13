from __future__ import annotations

from backend.app.domains.query_planning.schemas.query_plan_v2 import (
    QueryPlanningV2GuardrailDecision,
    QueryPlanningV2Plan,
)
from backend.app.domains.query_planning.services.logistics_adapter import LogisticsQueryPlanningAdapter
from backend.app.domains.query_planning.services.plan_bom_adapter import PlanBomQueryPlanningAdapter
from backend.app.domains.query_planning.services.query_plan_v2_audit_writer import QueryPlanV2AuditWriter
from backend.app.domains.query_planning.services.strategy_router import QueryPlanningV2StrategyRouter


class QueryPlanningV2Service:
    """Query Planning V2 统一服务。

    说明：
        1. 位于业务员原始问题进入正式检索 / SQL / RAG 之前；
        2. 通过领域 adapter 复用现有物流 planner 和 BOM NLU Center；
        3. Phase 3 只输出 shadow query_plan，不替换正式主链路。
    """

    def __init__(
        self,
        *,
        logistics_adapter: LogisticsQueryPlanningAdapter,
        plan_bom_adapter: PlanBomQueryPlanningAdapter,
        audit_writer: QueryPlanV2AuditWriter | None = None,
        strategy_router: QueryPlanningV2StrategyRouter | None = None,
    ) -> None:
        """初始化统一服务。

        参数：
            logistics_adapter: 物流领域适配器。
            plan_bom_adapter: 计划 BOM 领域适配器。
            audit_writer: JSONL 审计写入器。
            strategy_router: 策略路由器。
        返回：无返回值。
        """

        self.logistics_adapter = logistics_adapter
        self.plan_bom_adapter = plan_bom_adapter
        self.audit_writer = audit_writer or QueryPlanV2AuditWriter()
        self.strategy_router = strategy_router or QueryPlanningV2StrategyRouter()

    def plan(
        self,
        *,
        question: str,
        domain: str | None = None,
        trace_id: str | None = None,
        write_audit: bool = True,
    ) -> QueryPlanningV2Plan:
        """生成 Query Planning V2 shadow 计划。
d
        参数：
            question: 用户原始问题。
            domain: 可选业务域；缺省时轻量判断物流 / 计划 BOM。
            trace_id: 请求追踪号。
            write_audit: 是否写入 JSONL 审计。
        返回：
            统一 query_plan_v2。
        业务逻辑：只规划和记录，不执行正式查询，不生成最终业务答案。
        """

        resolved_domain = self._resolve_domain(question, domain)
        if resolved_domain == "logistics":
            candidate = self.logistics_adapter.build_candidate(question, trace_id=trace_id)
        elif resolved_domain == "plan_bom":
            candidate = self.plan_bom_adapter.build_candidate(question, trace_id=trace_id)
        else:
            candidate = self._fail_closed_plan(question=question, domain=resolved_domain, trace_id=trace_id)

        routed = self.strategy_router.route(candidate)
        routed.audit.trace_id = trace_id
        if write_audit:
            return self.audit_writer.write(plan=routed, trace_id=trace_id)
        return routed

    @staticmethod
    def _resolve_domain(question: str, domain: str | None) -> str:
        """解析业务域。

        参数：
            question: 用户原始问题。
            domain: 调用方显式领域。
        返回：
            logistics、plan_bom 或 unknown。
        """

        normalized_domain = (domain or "").strip().lower().replace("-", "_")
        if normalized_domain in {"logistics", "plan_bom"}:
            return normalized_domain
        if normalized_domain:
            return "unknown"
        compact = "".join(question.split()).lower()
        if any(keyword in compact for keyword in ("bom", "订单", "评审", "玻璃", "焊带", "汇流条", "接线盒", "功率")):
            return "plan_bom"
        if any(keyword in compact for keyword in ("物流", "发运", "发货", "承运", "运费", "车辆", "司机")):
            return "logistics"
        return "unknown"

    @staticmethod
    def _fail_closed_plan(*, question: str, domain: str, trace_id: str | None) -> QueryPlanningV2Plan:
        """未知领域 fail closed 到澄清。

        参数：
            question: 用户原始问题。
            domain: 解析后的未知领域。
            trace_id: 追踪号。
        返回：
            CLARIFY 策略计划。
        """

        plan = QueryPlanningV2Plan(
            domain=domain or "unknown",
            original_question=question,
            strategy="CLARIFY",
            intent="clarification",
            clarification_questions=["请明确问题属于物流数据问答还是计划 BOM 问答，并补充关键查询条件。"],
            guardrail_decision=QueryPlanningV2GuardrailDecision(
                guardrail_enabled=True,
                guardrail_mode="fail_closed",
                final_source="fail_closed",
                policy_locked=True,
                accepted=False,
                blocked_reason="无法确定业务域，未进入任何正式查询链路。",
                notes=["未知领域必须澄清，不能默认套用物流或 BOM 口径。"],
            ),
        )
        plan.audit.trace_id = trace_id
        return plan


__all__ = ["QueryPlanningV2Service"]

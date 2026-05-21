from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy.orm import Session

from backend.app.domains.business_analysis.repositories.inventory_sales_production_query_repository import (
    InventorySalesProductionQueryRepository,
)
from backend.app.domains.business_analysis.schemas.inventory_sales_production_query import (
    InventorySalesProductionQueryPlan,
    InventorySalesProductionQueryResult,
    InventorySalesProductionQueryRow,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.aggregation_policy import (
    InventorySalesProductionAggregationPolicy,
    InventorySalesProductionPolicyDecision,
)

_DECIMAL_SCALE = Decimal("0.00000001")


class InventorySalesProductionQueryExecutor:
    """产销存 QueryPlan 查询执行器。

    职责：
        1. 接收已结构化的受控 QueryPlan；
        2. 先经聚合策略校验，确认指标、维度、期间和业务口径安全；
        3. 调用固定仓储查询模板执行，不让 LLM 生成 SQL 或计算业务数字；
        4. 返回业务化摘要和结构化事实，供 M4 智能问答展示层复用。
    """

    def __init__(self, db: Session) -> None:
        self.repository = InventorySalesProductionQueryRepository(db)
        self.policy = InventorySalesProductionAggregationPolicy(self.repository)

    def execute(self, plan: InventorySalesProductionQueryPlan) -> InventorySalesProductionQueryResult:
        """执行产销存 QueryPlan。

        参数：plan 产销存受控 QueryPlan。
        返回：InventorySalesProductionQueryResult；阻断/空结果不会继续查相近指标。
        """

        decision = self.policy.resolve(plan)
        if not decision.accepted:
            return self._blocked_result(plan=plan, decision=decision)

        if plan.query_key == "ba_isp_budget_achievement":
            return self._execute_budget_achievement(plan=plan, decision=decision)

        if plan.query_key == "ba_isp_period_compare":
            return self._execute_period_compare(plan=plan, decision=decision)

        dimensions = list(decision.dimensions)
        if plan.query_key == "ba_isp_metric_trend" and "business_month" not in dimensions:
            dimensions.append("business_month")

        assert decision.metric is not None
        rows_payload = self.repository.aggregate_metric(
            metric=decision.metric,
            year=plan.period.year,
            months=decision.months,
            dimensions=dimensions,
            filters=decision.filters,
            aggregation_type=decision.aggregation_type or decision.metric.aggregation_type,
        )
        if not rows_payload:
            return self._empty_result(plan=plan, decision=decision)

        warnings = list(decision.warnings)
        if decision.aggregation_type == "period_end" and decision.months:
            warnings.append(f"库存/存货/寄存类时点指标按最后已发布月份 {max(decision.months)} 月取数。")

        rows = [InventorySalesProductionQueryRow(**payload) for payload in rows_payload]
        return InventorySalesProductionQueryResult(
            status="success",
            answer_summary=self._build_success_summary(plan=plan, rows=rows, decision=decision),
            rows=rows,
            warnings=warnings,
            calculation_policy=decision.calculation_policy,
            period_label=decision.period_label,
            query_key=plan.query_key,
        )

    def _execute_budget_achievement(
        self,
        *,
        plan: InventorySalesProductionQueryPlan,
        decision: InventorySalesProductionPolicyDecision,
    ) -> InventorySalesProductionQueryResult:
        """执行预算达成率重算。

        参数：plan/decision 已校验计划与策略。
        返回：预算达成率结果；缺少预算或预算为 0 时返回澄清。
        """

        assert decision.metric is not None
        actual_value, actual_count, actual_months = self.repository.sum_metric(
            metric_code=decision.metric.metric_code,
            year=plan.period.year,
            months=decision.months,
            filters=decision.filters,
        )
        budget_value, budget_count, budget_months = self.repository.sum_metric(
            metric_code="production_budget",
            year=plan.period.year,
            months=decision.months,
            filters=decision.filters,
        )
        if actual_value is None or not actual_count:
            return InventorySalesProductionQueryResult(
                status="empty_result",
                answer_summary="当前期间没有找到实际产量数据，无法计算预算达成率。",
                rows=[],
                warnings=decision.warnings,
                calculation_policy="calculated_ratio",
                period_label=decision.period_label,
                query_key=plan.query_key,
            )
        if budget_value is None or not budget_count or budget_value == 0:
            return InventorySalesProductionQueryResult(
                status="clarification",
                answer_summary="缺少预算数据或预算为 0，无法可靠计算预算达成率，请补充预算口径后再查询。",
                rows=[],
                warnings=decision.warnings,
                calculation_policy="calculated_ratio",
                period_label=decision.period_label,
                query_key=plan.query_key,
            )

        ratio = ((actual_value / budget_value) * Decimal("100")).quantize(_DECIMAL_SCALE, rounding=ROUND_HALF_UP)
        months_covered = sorted(set(actual_months) | set(budget_months))
        row = InventorySalesProductionQueryRow(
            dimensions={},
            metric_code=f"{decision.metric.metric_code}_budget_achievement_rate",
            metric_name="预算达成率",
            value_decimal=ratio,
            unit_standard="percent",
            aggregation_type="calculated_ratio",
            months_covered=months_covered,
            row_count=actual_count + budget_count,
            extra={
                "actual_metric_code": decision.metric.metric_code,
                "budget_metric_code": "production_budget",
                "actual_value": str(actual_value.quantize(_DECIMAL_SCALE, rounding=ROUND_HALF_UP)),
                "budget_value": str(budget_value.quantize(_DECIMAL_SCALE, rounding=ROUND_HALF_UP)),
            },
        )
        return InventorySalesProductionQueryResult(
            status="success",
            answer_summary=f"{decision.period_label or plan.period.year} 预算达成率为 {row.value_decimal}%。",
            rows=[row],
            warnings=decision.warnings,
            calculation_policy="calculated_ratio",
            period_label=decision.period_label,
            query_key=plan.query_key,
        )

    def _execute_period_compare(
        self,
        *,
        plan: InventorySalesProductionQueryPlan,
        decision: InventorySalesProductionPolicyDecision,
    ) -> InventorySalesProductionQueryResult:
        """执行期间对比查询（同比/环比/月区间）。

        参数：
            plan: 已校验的 M4 QueryPlan。
            decision: 已校验的聚合策略。
        返回：
            按月份拆分的明细结果；同比/环比口径在摘要中说明。
        """

        assert decision.metric is not None
        dimensions = list(decision.dimensions)
        if plan.query_key == "ba_isp_period_compare":
            if "business_month" not in dimensions:
                dimensions.append("business_month")
        rows_payload = self.repository.aggregate_metric(
            metric=decision.metric,
            year=plan.period.year,
            months=decision.months,
            dimensions=dimensions,
            filters=decision.filters,
            aggregation_type=decision.aggregation_type or decision.metric.aggregation_type,
        )
        if not rows_payload:
            return self._empty_result(plan=plan, decision=decision)

        warnings = list(decision.warnings)
        if "同比" in (plan.period.period_type or ""):
            warnings.append("同比结果按当前期间和去年同期分别展示，不自动计算增长率。")
        if "环比" in (plan.period.period_type or ""):
            warnings.append("环比结果按当前期间和上一期间分别展示，不自动计算变化率。")
        rows = [InventorySalesProductionQueryRow(**payload) for payload in rows_payload]
        return InventorySalesProductionQueryResult(
            status="success",
            answer_summary=f"{decision.period_label or plan.period.year} 期间对比结果，按月份展示。",
            rows=rows,
            warnings=warnings,
            calculation_policy=decision.calculation_policy or "period_compare",
            period_label=decision.period_label,
            query_key=plan.query_key,
        )

    def _blocked_result(
        self,
        *,
        plan: InventorySalesProductionQueryPlan,
        decision: InventorySalesProductionPolicyDecision,
    ) -> InventorySalesProductionQueryResult:
        """构造校验阻断结果。"""

        return InventorySalesProductionQueryResult(
            status=decision.status,  # type: ignore[arg-type]
            answer_summary=decision.message,
            rows=[],
            warnings=decision.warnings,
            calculation_policy=decision.calculation_policy,
            period_label=decision.period_label,
            query_key=plan.query_key,
        )

    def _empty_result(
        self,
        *,
        plan: InventorySalesProductionQueryPlan,
        decision: InventorySalesProductionPolicyDecision,
    ) -> InventorySalesProductionQueryResult:
        """构造空结果，不自动放宽用户条件。"""

        return InventorySalesProductionQueryResult(
            status="empty_result",
            answer_summary="当前期间和筛选条件下没有找到匹配的产销存数据，未自动放宽条件。",
            rows=[],
            warnings=decision.warnings,
            calculation_policy=decision.calculation_policy,
            period_label=decision.period_label,
            query_key=plan.query_key,
        )

    def _build_success_summary(
        self,
        *,
        plan: InventorySalesProductionQueryPlan,
        rows: list[InventorySalesProductionQueryRow],
        decision: InventorySalesProductionPolicyDecision,
    ) -> str:
        """生成业务化成功摘要。

        说明：M3 只生成简洁确定性摘要，M4 可在此基础上接入 LLM 润色，但不得改写事实。
        """

        period_label = decision.period_label or str(plan.period.year)
        if len(rows) == 1 and not rows[0].dimensions:
            unit = "%" if rows[0].unit_standard == "percent" else rows[0].unit_standard
            return f"{period_label} {rows[0].metric_name}为 {rows[0].value_decimal} {unit}。"
        return f"{period_label} 已按指定维度完成 {rows[0].metric_name} 拆分，共 {len(rows)} 项结果。"


__all__ = ["InventorySalesProductionQueryExecutor"]

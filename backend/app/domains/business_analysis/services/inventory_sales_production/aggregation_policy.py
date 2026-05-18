from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.domains.business_analysis.models import BaIspMetric
from backend.app.domains.business_analysis.repositories.inventory_sales_production_query_repository import (
    DIMENSION_COLUMN_MAP,
    FILTER_COLUMN_MAP,
    QUERY_CONTROL_FILTERS,
    InventorySalesProductionQueryRepository,
)
from backend.app.domains.business_analysis.schemas.inventory_sales_production_query import (
    InventorySalesProductionQueryPlan,
)

SUPPORTED_QUERY_KEYS = {
    "ba_isp_metric_summary",
    "ba_isp_metric_breakdown",
    "ba_isp_metric_trend",
    "ba_isp_budget_achievement",
    "ba_isp_inventory_snapshot",
    "ba_isp_period_compare",
}
ALLOWED_PLAN_FILTERS = set(FILTER_COLUMN_MAP) | QUERY_CONTROL_FILTERS | {"business_year", "business_month"}


@dataclass(slots=True)
class InventorySalesProductionPolicyDecision:
    """产销存聚合策略决策结果。

    参数：
        accepted: 是否允许执行。
        status/message: 拒绝时的业务状态和说明。
        metric: 实际执行指标。
        months: 已发布月份列表。
        dimensions/filters: 校验后的维度和过滤条件。
        aggregation_type/calculation_policy: 实际聚合策略。
        warnings: 业务口径提醒。
    返回：
        执行器可直接消费的策略决策。
    """

    accepted: bool
    status: str = "success"
    message: str = ""
    metric: BaIspMetric | None = None
    months: list[int] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    aggregation_type: str | None = None
    calculation_policy: str | None = None
    period_label: str | None = None
    warnings: list[str] = field(default_factory=list)


class InventorySalesProductionAggregationPolicy:
    """产销存 QueryPlan 校验与聚合策略选择器。

    职责：
        1. 校验指标、维度、过滤、期间和 query_key 是否在白名单内；
        2. 将 period 展开为已发布月份，阻断未来/未发布月份；
        3. 选择 flow_sum、period_end、calculated_ratio 等后端确定性策略；
        4. 对 2024 销量默认对外口径等业务规则做确定性归一。
    """

    def __init__(self, repository: InventorySalesProductionQueryRepository) -> None:
        self.repository = repository

    def resolve(self, plan: InventorySalesProductionQueryPlan) -> InventorySalesProductionPolicyDecision:
        """校验 QueryPlan 并返回执行策略。

        参数：plan 产销存受控 QueryPlan。
        返回：InventorySalesProductionPolicyDecision；accepted=False 时执行器不得查数。
        """

        basic_error = self._validate_basic_plan(plan)
        if basic_error:
            return basic_error

        requested_metric_code = plan.metrics[0]
        metric = self.repository.get_metric(requested_metric_code)
        if metric is None:
            return self._blocked("unsupported", f"暂不支持该产销存指标：{requested_metric_code}")

        invoice_error = self._validate_invoice_policy(plan, metric)
        if invoice_error:
            return invoice_error

        filter_error = self._validate_filters(plan, plan.filters)
        if filter_error:
            return filter_error
        filters = self._normalize_filters(plan.filters)

        effective_metric, metric_warnings = self._resolve_effective_metric(plan, metric, filters)
        dimensions = list(plan.dimensions)
        period_months, period_label, period_warnings, period_error = self._resolve_period_months(plan)
        if period_error:
            return period_error

        query_key_error = self._validate_query_key_policy(plan, effective_metric, dimensions)
        if query_key_error:
            return query_key_error

        aggregation_type = self._resolve_aggregation_type(plan, effective_metric)
        warnings = [*metric_warnings, *period_warnings]
        return InventorySalesProductionPolicyDecision(
            accepted=True,
            metric=effective_metric,
            months=period_months,
            dimensions=dimensions,
            filters=filters,
            aggregation_type=aggregation_type,
            calculation_policy=aggregation_type,
            period_label=period_label,
            warnings=warnings,
        )

    def _validate_basic_plan(self, plan: InventorySalesProductionQueryPlan) -> InventorySalesProductionPolicyDecision | None:
        """校验领域、query_key、指标数量和维度白名单。"""

        if plan.domain != "business_analysis" or plan.sub_domain != "inventory_sales_production":
            return self._blocked("unsupported", "该计划不是产销存经营分析问题，已停止执行。")
        if plan.query_key not in SUPPORTED_QUERY_KEYS:
            return self._blocked("unsupported", f"暂不支持该产销存查询能力：{plan.query_key}")
        if len(plan.metrics) != 1:
            return self._blocked("unsupported", "MVP 阶段每次只支持一个产销存主指标。")
        for dimension in plan.dimensions:
            if dimension not in DIMENSION_COLUMN_MAP:
                return self._blocked("unsupported", f"暂不支持该拆分维度：{dimension}")
        return None

    def _validate_invoice_policy(
        self,
        plan: InventorySalesProductionQueryPlan,
        metric: BaIspMetric,
    ) -> InventorySalesProductionPolicyDecision | None:
        """校验开票销量必须由显式问法触发。"""

        if metric.metric_code == "invoice_sales_volume" and not bool(plan.filters.get("explicit_invoice")):
            return self._blocked("clarification", "如需查询开票销量，请在问题中明确说明“开票”口径。")
        return None

    def _validate_filters(
        self,
        plan: InventorySalesProductionQueryPlan,
        filters: dict[str, Any],
    ) -> InventorySalesProductionPolicyDecision | None:
        """校验过滤条件白名单和年份一致性。"""

        for key in filters:
            if key not in ALLOWED_PLAN_FILTERS:
                return self._blocked("unsupported", f"暂不支持该产销存过滤条件：{key}")
        filter_year = filters.get("business_year")
        if filter_year is not None:
            try:
                normalized_filter_year = int(filter_year)
            except (TypeError, ValueError):
                return self._blocked("clarification", "查询年份格式不清楚，请确认要查询的业务年份。")
            if normalized_filter_year != plan.period.year:
                return self._blocked("clarification", "查询年份与过滤年份不一致，请确认要查询的业务年份。")
        return None

    def _normalize_filters(self, filters: dict[str, Any]) -> dict[str, Any]:
        """归一化过滤条件。

        说明：业务年份和月份由 period 统一控制，保留在 filters 中仅用于一致性校验，不进入仓储过滤。
        """

        normalized = dict(filters)
        normalized.pop("business_year", None)
        normalized.pop("business_month", None)
        return normalized

    def _resolve_effective_metric(
        self,
        plan: InventorySalesProductionQueryPlan,
        metric: BaIspMetric,
        filters: dict[str, Any],
    ) -> tuple[BaIspMetric, list[str]]:
        """根据业务口径确定实际执行指标。

        业务逻辑：2024 年用户默认问“销量/发货量”时，采用组件事业部剔除内部交易的对外销量口径；
        用户显式要求包含内部交易时不做该替换。
        """

        warnings: list[str] = []
        if (
            metric.metric_code == "shipment_volume"
            and plan.period.year == 2024
            and not bool(filters.get("include_internal"))
            and self.repository.has_metric_for_year(metric_code="shipment_external_excluding_internal", year=2024)
        ):
            external_metric = self.repository.get_metric("shipment_external_excluding_internal")
            if external_metric is not None:
                warnings.append("2024 年销量默认采用组件事业部剔除内部交易的对外销量口径。")
                return external_metric, warnings
        return metric, warnings

    def _resolve_period_months(
        self,
        plan: InventorySalesProductionQueryPlan,
    ) -> tuple[list[int], str, list[str], InventorySalesProductionPolicyDecision | None]:
        """将期间规格展开为已发布月份。"""

        period = plan.period
        available_months = self.repository.list_available_months(year=period.year)
        if not available_months:
            return [], str(period.year), [], self._blocked("clarification", f"尚未导入 {period.year} 年产销存数据，无法回答。")

        warnings: list[str] = []
        if period.period_type == "month":
            assert period.month is not None
            if period.month not in available_months:
                return [], f"{period.year}-{period.month:02d}", [], self._blocked(
                    "clarification",
                    f"{period.year} 年 {period.month} 月数据尚未发布或未导入，不能按 0 处理。",
                )
            return [period.month], f"{period.year}-{period.month:02d}", warnings, None

        if period.period_type == "quarter":
            assert period.quarter is not None
            start = (period.quarter - 1) * 3 + 1
            candidate_months = list(range(start, start + 3))
            months = [month for month in candidate_months if month in available_months]
            if not months:
                return [], f"{period.year}-Q{period.quarter}", [], self._blocked(
                    "clarification",
                    f"{period.year} 年 Q{period.quarter} 数据尚未发布或未导入。",
                )
            if len(months) < 3:
                warnings.append(f"{period.year} 年 Q{period.quarter} 仅使用已发布月份：{','.join(map(str, months))} 月。")
            return months, f"{period.year}-Q{period.quarter}", warnings, None

        end_month = period.end_month or max(available_months)
        months = [month for month in available_months if month <= end_month]
        if not months:
            return [], f"{period.year}-YTD", [], self._blocked("clarification", f"{period.year} 年指定期间尚无已发布数据。")
        if end_month > max(available_months):
            warnings.append(f"{period.year} 年目前只发布到 {max(available_months)} 月，未发布月份不参与计算。")
        if period.period_type == "year" and max(available_months) < 12:
            warnings.append(f"{period.year} 年全年查询仅使用已发布月份 1-{max(available_months)} 月。")
        if period.year == 2023 and period.period_type == "year":
            warnings.append("2023 年年度结果按 1-12 月月度事实重新计算。")
        period_label = f"{period.year}-YTD" if period.period_type == "ytd" else str(period.year)
        return months, period_label, warnings, None

    def _validate_query_key_policy(
        self,
        plan: InventorySalesProductionQueryPlan,
        metric: BaIspMetric,
        dimensions: list[str],
    ) -> InventorySalesProductionPolicyDecision | None:
        """校验 query_key 与指标聚合策略是否匹配。"""

        if plan.query_key == "ba_isp_metric_summary" and dimensions:
            return self._blocked("unsupported", "单指标汇总不支持同时指定拆分维度，请使用拆分查询能力。")
        if plan.query_key == "ba_isp_metric_breakdown" and not dimensions:
            return self._blocked("clarification", "请说明需要按哪个维度拆分，例如基地或版型。")
        if plan.query_key == "ba_isp_inventory_snapshot" and metric.aggregation_type != "period_end":
            return self._blocked("unsupported", "库存时点查询只支持库存、存货或寄存等时点指标。")
        if plan.query_key == "ba_isp_budget_achievement" and metric.metric_code == "production_budget":
            return self._blocked("unsupported", "预算达成率需要实际产量作为主指标，预算只作为分母。")
        if plan.query_key == "ba_isp_budget_achievement" and dimensions:
            return self._blocked("unsupported", "MVP 阶段预算达成率暂不支持按维度拆分。")
        return None

    def _resolve_aggregation_type(self, plan: InventorySalesProductionQueryPlan, metric: BaIspMetric) -> str:
        """确定实际聚合策略。"""

        if plan.query_key == "ba_isp_budget_achievement":
            return "calculated_ratio"
        return metric.aggregation_type

    @staticmethod
    def _blocked(status: str, message: str) -> InventorySalesProductionPolicyDecision:
        """构造阻断决策。"""

        return InventorySalesProductionPolicyDecision(accepted=False, status=status, message=message)


__all__ = [
    "InventorySalesProductionAggregationPolicy",
    "InventorySalesProductionPolicyDecision",
]

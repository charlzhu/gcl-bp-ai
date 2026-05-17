from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LogisticsQueryPlannerV2Capability:
    """物流 Query Planner V2 的单个 query_key 能力声明。

    参数：
        query_key: 后端白名单查询键。
        description: 面向 LLM prompt 和审计日志的能力说明。
        allowed_filters: 允许出现的受控过滤字段。
        required_filters: 必填过滤字段。
        required_any_filters: 至少命中一个字段的组合，例如 city/province 二选一。
        allowed_metrics: 允许输出的指标槽位。
        allowed_dimensions: 允许输出的维度槽位。
        allowed_group_by: 允许分组字段。
        allowed_aggregations: 允许聚合算子。
        allowed_compare_modes: 允许对比模式。
        time_scope: 数据源时间边界。
        executable_service: 后续可复用的确定性 service 名称。
        allow_assist: 是否允许未来进入 assist 灰度。
    返回：
        不可变的能力声明对象。
    """

    query_key: str
    description: str
    allowed_filters: set[str] = field(default_factory=set)
    required_filters: set[str] = field(default_factory=set)
    required_any_filters: list[set[str]] = field(default_factory=list)
    allowed_metrics: set[str] = field(default_factory=set)
    allowed_dimensions: set[str] = field(default_factory=set)
    allowed_group_by: set[str] = field(default_factory=set)
    allowed_aggregations: set[str] = field(default_factory=set)
    allowed_compare_modes: set[str] = field(default_factory=set)
    time_scope: str = "historical_2023_2025"
    executable_service: str = "LogisticsDataQaService"
    allow_assist: bool = False

    def to_prompt_dict(self) -> dict[str, Any]:
        """转换为 prompt 中的精简 JSON 能力说明。"""

        return {
            "query_key": self.query_key,
            "description": self.description,
            "allowed_filters": sorted(self.allowed_filters),
            "required_filters": sorted(self.required_filters),
            "required_any_filters": [sorted(item) for item in self.required_any_filters],
            "allowed_metrics": sorted(self.allowed_metrics),
            "allowed_dimensions": sorted(self.allowed_dimensions),
            "allowed_group_by": sorted(self.allowed_group_by),
            "allowed_aggregations": sorted(self.allowed_aggregations),
            "allowed_compare_modes": sorted(self.allowed_compare_modes),
            "time_scope": self.time_scope,
            "executable_service": self.executable_service,
            "allow_assist": self.allow_assist,
        }


class LogisticsQueryPlannerV2CapabilityRegistry:
    """物流 Query Planner V2 query_key 能力注册表。

    业务逻辑：
        1. 只声明后端已经审计过的白名单能力；
        2. Validator 以本注册表为唯一放行依据；
        3. LLM prompt 只能看到本注册表暴露的受控 query_key，不能自由发明查询。
    """

    def __init__(self, capabilities: dict[str, LogisticsQueryPlannerV2Capability] | None = None) -> None:
        """初始化能力表；测试可以注入精简能力集合。"""

        self._capabilities = capabilities or self._default_capabilities()

    def get(self, query_key: str | None) -> LogisticsQueryPlannerV2Capability | None:
        """按 query_key 获取能力声明；不存在返回 None。"""

        if not query_key:
            return None
        return self._capabilities.get(query_key)

    def allowed_query_keys(self) -> set[str]:
        """返回当前允许候选的全部 query_key。"""

        return set(self._capabilities.keys())

    def prompt_payload(self, allowed_query_keys: list[str] | set[str] | None = None) -> list[dict[str, Any]]:
        """返回给 prompt_builder 使用的能力 JSON 列表。

        参数：
            allowed_query_keys: 可选配置白名单；传入后只暴露这些能力，避免 prompt 诱导 LLM 选择未灰度 query_key。
        返回：
            可序列化的能力声明列表。
        """

        if allowed_query_keys:
            keys = [key for key in sorted(set(allowed_query_keys)) if key in self._capabilities]
        else:
            keys = sorted(self._capabilities)
        return [self._capabilities[key].to_prompt_dict() for key in keys]

    @staticmethod
    def _default_capabilities() -> dict[str, LogisticsQueryPlannerV2Capability]:
        """构造 MVP 首批能力声明。"""

        route_filters = {
            "years",
            "months",
            "origin_place",
            "city",
            "province",
            "vehicle_type",
            "view_mode",
            "price_metric",
        }
        return {
            "hist_route_pricing_analysis": LogisticsQueryPlannerV2Capability(
                query_key="hist_route_pricing_analysis",
                description="历史台账中，按始发地、目的城市/省份、车型和年份分析线路平均运费、单车均费或月度趋势。",
                allowed_filters=route_filters,
                required_filters={"years", "origin_place", "vehicle_type", "view_mode", "price_metric"},
                required_any_filters=[{"city", "province"}],
                allowed_metrics={"avg_fee", "total_fee", "row_count"},
                allowed_dimensions={"year", "month", "origin_place", "city", "province", "vehicle_type"},
                allowed_group_by={"year", "month", "origin_place", "city", "province", "vehicle_type"},
                allowed_aggregations={"avg", "sum", "count"},
                allowed_compare_modes={"none", "year_compare", "month_over_month", "year_over_year", "monthly_trend"},
                time_scope="historical_2023_2025",
                executable_service="LogisticsDataQaService.hist_route_pricing_analysis",
                allow_assist=True,
            ),
            "hist_total_fee_city_rank": LogisticsQueryPlannerV2Capability(
                query_key="hist_total_fee_city_rank",
                description="历史台账中，按年份、省份或区域统计城市总费用排名。",
                allowed_filters={"years", "province", "region", "top_n", "sort_order"},
                required_filters={"years"},
                required_any_filters=[{"province", "region"}],
                allowed_metrics={"total_fee", "row_count"},
                allowed_dimensions={"city", "province", "region", "year"},
                allowed_group_by={"city", "province", "region", "year"},
                allowed_aggregations={"sum", "count"},
                allowed_compare_modes={"none", "year_compare"},
                executable_service="LogisticsDataQaService.hist_total_fee_city_rank",
                allow_assist=False,
            ),
            "hist_avg_fee_by_month": LogisticsQueryPlannerV2Capability(
                query_key="hist_avg_fee_by_month",
                description="历史台账中，按月份统计平均运费走势。",
                allowed_filters=route_filters,
                required_filters={"years"},
                required_any_filters=[],
                allowed_metrics={"avg_fee", "total_fee", "row_count"},
                allowed_dimensions={"month", "year", "origin_place", "city", "province", "vehicle_type"},
                allowed_group_by={"month", "year"},
                allowed_aggregations={"avg", "sum", "count"},
                allowed_compare_modes={"none", "month_over_month", "year_over_year", "monthly_trend"},
                executable_service="LogisticsDataQaService.hist_avg_fee_by_month",
                allow_assist=False,
            ),
            "hist_carrier_kpi_by_year": LogisticsQueryPlannerV2Capability(
                query_key="hist_carrier_kpi_by_year",
                description="历史台账中，按年份和承运商统计运量、运费、车次等经营指标。",
                allowed_filters={"years", "carrier", "region", "province", "city", "top_n", "sort_order"},
                required_filters={"years"},
                required_any_filters=[],
                allowed_metrics={"shipment_mw", "total_fee", "trip_count", "row_count", "avg_fee"},
                allowed_dimensions={"year", "carrier", "region", "province", "city"},
                allowed_group_by={"year", "carrier", "region", "province", "city"},
                allowed_aggregations={"sum", "avg", "count"},
                allowed_compare_modes={"none", "year_compare"},
                executable_service="LogisticsDataQaService.hist_carrier_kpi_by_year",
                allow_assist=False,
            ),
        }


__all__ = ["LogisticsQueryPlannerV2Capability", "LogisticsQueryPlannerV2CapabilityRegistry"]

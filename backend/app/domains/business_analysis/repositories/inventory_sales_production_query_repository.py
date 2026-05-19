from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import InstrumentedAttribute, Query, Session

from backend.app.domains.business_analysis.models import BaIspMetric, BaIspMonthlyFact

# 说明：维度白名单同时服务 QueryPlan 校验和固定查询模板，禁止上游传入任意字段名。
DIMENSION_COLUMN_MAP: dict[str, InstrumentedAttribute] = {
    "base_name": BaIspMonthlyFact.base_name,
    "factory_name": BaIspMonthlyFact.factory_name,
    "model_type": BaIspMonthlyFact.model_type,
    "production_mode": BaIspMonthlyFact.production_mode,
    "trade_scope": BaIspMonthlyFact.trade_scope,
    "business_month": BaIspMonthlyFact.business_month,
}

# 说明：过滤白名单只允许业务维度，不接受 SQL/where/table 等自由片段。
FILTER_COLUMN_MAP: dict[str, InstrumentedAttribute] = {
    "base_name": BaIspMonthlyFact.base_name,
    "factory_name": BaIspMonthlyFact.factory_name,
    "model_type": BaIspMonthlyFact.model_type,
    "production_mode": BaIspMonthlyFact.production_mode,
    "trade_scope": BaIspMonthlyFact.trade_scope,
    "is_outsourced": BaIspMonthlyFact.is_outsourced,
    "is_consigned": BaIspMonthlyFact.is_consigned,
    "is_default_external_sales": BaIspMonthlyFact.is_default_external_sales,
}

QUERY_CONTROL_FILTERS = {"explicit_invoice", "include_internal"}


class InventorySalesProductionQueryRepository:
    """产销存受控查询仓储。

    职责：
        1. 只查询 M2 标准事实长表和指标维表；
        2. 根据执行器传入的受控参数拼装固定 ORM 查询；
        3. 不接收 SQL 字符串、不暴露表名字段给用户回答层。
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_metric(self, metric_code: str) -> BaIspMetric | None:
        """按指标编码读取启用的标准指标。

        参数：metric_code 标准指标编码。
        返回：BaIspMetric 或 None。
        """

        return (
            self.db.query(BaIspMetric)
            .filter(BaIspMetric.metric_code == metric_code, BaIspMetric.is_active == 1)
            .one_or_none()
        )

    def list_available_months(self, *, year: int) -> list[int]:
        """返回某业务年份已导入且已发布的月份列表。

        参数：year 业务年份。
        返回：升序月份列表；若年份未导入则为空。
        """

        rows = (
            self.db.query(BaIspMonthlyFact.business_month)
            .filter(BaIspMonthlyFact.business_year == year, BaIspMonthlyFact.is_published_month == 1)
            .distinct()
            .order_by(BaIspMonthlyFact.business_month.asc())
            .all()
        )
        return [int(row[0]) for row in rows]

    def has_metric_for_year(self, *, metric_code: str, year: int) -> bool:
        """判断某年份是否存在指定指标事实。

        参数：metric_code 指标编码；year 业务年份。
        返回：存在返回 True。
        """

        return (
            self.db.query(BaIspMonthlyFact.id)
            .filter(
                BaIspMonthlyFact.business_year == year,
                BaIspMonthlyFact.metric_code == metric_code,
                BaIspMonthlyFact.is_published_month == 1,
            )
            .limit(1)
            .first()
            is not None
        )

    def aggregate_metric(
        self,
        *,
        metric: BaIspMetric,
        year: int,
        months: list[int],
        dimensions: list[str],
        filters: dict[str, Any],
        aggregation_type: str,
    ) -> list[dict[str, Any]]:
        """执行单指标聚合查询。

        参数：
            metric: 指标维表记录。
            year/months: 已通过策略校验的业务期间。
            dimensions: 白名单维度。
            filters: 白名单过滤条件。
            aggregation_type: flow_sum 或 period_end。
        返回：
            字典列表，包含维度、数值、事实行数和覆盖月份。
        """

        effective_months = self._resolve_effective_months_for_aggregation(
            metric_code=metric.metric_code,
            year=year,
            months=months,
            filters=filters,
            aggregation_type=aggregation_type,
        )
        if not effective_months:
            return []
        base_query = self._base_fact_query(metric_code=metric.metric_code, year=year, months=effective_months, filters=filters)
        if dimensions:
            return self._aggregate_with_dimensions(
                base_query=base_query,
                metric=metric,
                dimensions=dimensions,
                aggregation_type=aggregation_type,
                months=effective_months,
            )
        return self._aggregate_without_dimensions(
            base_query=base_query,
            metric=metric,
            aggregation_type=aggregation_type,
            months=effective_months,
        )

    def sum_metric(
        self,
        *,
        metric_code: str,
        year: int,
        months: list[int],
        filters: dict[str, Any],
    ) -> tuple[Decimal | None, int, list[int]]:
        """对指定指标按月求和，用于预算达成率分子/分母。

        参数：metric_code 指标编码；year/months 期间；filters 业务过滤。
        返回：三元组 `(合计值, 行数, 实际覆盖月份)`。
        """

        query = self._base_fact_query(metric_code=metric_code, year=year, months=months, filters=filters)
        value, row_count = query.with_entities(func.sum(BaIspMonthlyFact.value_decimal), func.count(BaIspMonthlyFact.id)).one()
        covered_months = self._list_months_with_data(metric_code=metric_code, year=year, months=months, filters=filters)
        return value, int(row_count or 0), covered_months

    def _resolve_effective_months_for_aggregation(
        self,
        *,
        metric_code: str,
        year: int,
        months: list[int],
        filters: dict[str, Any],
        aggregation_type: str,
    ) -> list[int]:
        """根据聚合策略确定实际查询月份。"""

        covered_months = self._list_months_with_data(metric_code=metric_code, year=year, months=months, filters=filters)
        if aggregation_type == "period_end":
            return [max(covered_months)] if covered_months else []
        return covered_months

    def _base_fact_query(self, *, metric_code: str, year: int, months: Iterable[int], filters: dict[str, Any]) -> Query:
        """构建固定事实查询基础条件。"""

        query = self.db.query(BaIspMonthlyFact).filter(
            BaIspMonthlyFact.business_year == year,
            BaIspMonthlyFact.metric_code == metric_code,
            BaIspMonthlyFact.business_month.in_(list(months)),
            BaIspMonthlyFact.is_published_month == 1,
        )
        return self._apply_filters(query, filters)

    def _apply_filters(self, query: Query, filters: dict[str, Any]) -> Query:
        """应用白名单过滤条件。"""

        for key, value in filters.items():
            if key in QUERY_CONTROL_FILTERS or value in (None, "", []):
                continue
            column = FILTER_COLUMN_MAP.get(key)
            if column is None:
                continue
            if isinstance(value, (list, tuple, set)):
                query = query.filter(column.in_(list(value)))
            else:
                query = query.filter(column == value)
        return query

    def _aggregate_without_dimensions(
        self,
        *,
        base_query: Query,
        metric: BaIspMetric,
        aggregation_type: str,
        months: list[int],
    ) -> list[dict[str, Any]]:
        """执行无维度聚合。"""

        value, row_count = base_query.with_entities(func.sum(BaIspMonthlyFact.value_decimal), func.count(BaIspMonthlyFact.id)).one()
        if not row_count or value is None:
            return []
        return [
            {
                "dimensions": {},
                "metric_code": metric.metric_code,
                "metric_name": metric.metric_name,
                "value_decimal": value,
                "unit_standard": metric.unit_standard,
                "aggregation_type": aggregation_type,
                "months_covered": months,
                "row_count": int(row_count),
            }
        ]

    def _aggregate_with_dimensions(
        self,
        *,
        base_query: Query,
        metric: BaIspMetric,
        dimensions: list[str],
        aggregation_type: str,
        months: list[int],
    ) -> list[dict[str, Any]]:
        """执行维度分组聚合。"""

        dimension_columns = [DIMENSION_COLUMN_MAP[dimension].label(dimension) for dimension in dimensions]
        value_expr = func.sum(BaIspMonthlyFact.value_decimal).label("value_decimal")
        count_expr = func.count(BaIspMonthlyFact.id).label("row_count")
        rows = (
            base_query.with_entities(*dimension_columns, value_expr, count_expr)
            .group_by(*dimension_columns)
            .order_by(value_expr.desc(), *dimension_columns)
            .all()
        )
        result: list[dict[str, Any]] = []
        for row in rows:
            row_map = row._asdict()
            dimensions_payload = {dimension: row_map.get(dimension) for dimension in dimensions}
            result.append(
                {
                    "dimensions": dimensions_payload,
                    "metric_code": metric.metric_code,
                    "metric_name": metric.metric_name,
                    "value_decimal": row_map.get("value_decimal"),
                    "unit_standard": metric.unit_standard,
                    "aggregation_type": aggregation_type,
                    "months_covered": months,
                    "row_count": int(row_map.get("row_count") or 0),
                }
            )
        return result

    def _list_months_with_data(self, *, metric_code: str, year: int, months: list[int], filters: dict[str, Any]) -> list[int]:
        """返回指定指标在过滤条件下实际有事实数据的月份。"""

        query = self._base_fact_query(metric_code=metric_code, year=year, months=months, filters=filters)
        rows = query.with_entities(BaIspMonthlyFact.business_month).distinct().order_by(BaIspMonthlyFact.business_month.asc()).all()
        return [int(row[0]) for row in rows]


__all__ = [
    "DIMENSION_COLUMN_MAP",
    "FILTER_COLUMN_MAP",
    "InventorySalesProductionQueryRepository",
]

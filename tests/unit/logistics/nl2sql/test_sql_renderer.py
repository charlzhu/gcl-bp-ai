from __future__ import annotations

from copy import deepcopy

import pytest

from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader
from backend.app.domains.logistics.services.nl2sql.sql_plan import LogisticsSqlPlanValidator
from backend.app.domains.logistics.services.nl2sql.sql_renderer import LogisticsSqlRenderer, render_logistics_sql


def test_renderer_renders_valid_aggregate_with_parameterized_default_years() -> None:
    """aggregate SQL 必须来自 M3 通过的 normalized plan，并使用参数绑定默认 2023-2026 年份。"""

    validation = _validate(
        _valid_candidate(
            plan={
                "query_type": "aggregate",
                "metrics": ["shipment_mw", "row_count"],
                "dimensions": [],
                "group_by": [],
                "order_by": [],
                "limit": None,
            }
        )
    )

    rendered = render_logistics_sql(validation)

    assert rendered.sql.startswith("SELECT ")
    assert "SELECT *" not in rendered.sql.upper()
    assert "SUM(dws_logistics_detail_union.shipment_watt) AS shipment_mw" in rendered.sql
    assert "COUNT(1) AS row_count" in rendered.sql
    assert "dws_logistics_detail_union.biz_year IN (:p0, :p1, :p2, :p3)" in rendered.sql
    assert rendered.params == {"p0": 2023, "p1": 2024, "p2": 2025, "p3": 2026}
    assert rendered.limit is None
    assert rendered.referenced_tables == ["dws_logistics_detail_union"]
    assert ("dws_logistics_detail_union", "shipment_watt") in rendered.referenced_columns
    assert rendered.explicit_year_buckets == [2023, 2024, 2025, 2026]


def test_renderer_renders_ranking_group_order_limit_and_weighted_average_metric() -> None:
    """ranking SQL 必须包含 GROUP BY/ORDER BY/LIMIT，并锁定均价 SUM(total_fee)/SUM(车次) 口径。"""

    validation = _validate(
        _valid_candidate(
            catalog_refs=[
                {"catalog_id": "metric:avg_fee_per_trip", "catalog_version": "logistics_nl2sql_catalog.v1"},
                {"catalog_id": "metric:total_fee", "catalog_version": "logistics_nl2sql_catalog.v1"},
                {"catalog_id": "metric:shipment_trip_count", "catalog_version": "logistics_nl2sql_catalog.v1"},
            ],
            plan={
                "query_type": "ranking",
                "metrics": ["avg_fee_per_trip", "total_fee", "shipment_trip_count"],
                "dimensions": ["logistics_company_name"],
                "filters": [_filter("biz_year", "in", [2023, 2024])],
                "group_by": ["logistics_company_name"],
                "order_by": [{"metric": "avg_fee_per_trip", "direction": "desc"}],
                "business_rules": [],
                "explicit_year_buckets": [2023, 2024],
                "limit": 10,
            },
        )
    )

    rendered = LogisticsSqlRenderer().render(validation)

    assert "AVG(total_fee)" not in rendered.sql.upper()
    assert "SUM(dws_logistics_detail_union.total_fee) / SUM(dws_logistics_detail_union.shipment_trip_count)" in rendered.sql
    assert "GROUP BY dws_logistics_detail_union.logistics_company_name" in rendered.sql
    assert "ORDER BY avg_fee_per_trip DESC" in rendered.sql
    assert "LIMIT :p2" in rendered.sql
    assert rendered.params == {"p0": 2023, "p1": 2024, "p2": 10}
    assert rendered.limit == 10
    assert rendered.explicit_year_buckets == [2023, 2024]


def test_renderer_renders_detail_with_bound_filters_and_controlled_limit() -> None:
    """detail SQL 必须绑定客户等用户过滤值，并强制受控 LIMIT，不能无限明细。"""

    validation = _validate(
        _valid_candidate(
            catalog_refs=[{"catalog_id": "dimension:customer_name", "catalog_version": "logistics_nl2sql_catalog.v1"}],
            plan={
                "query_type": "detail",
                "metrics": ["shipment_mw"],
                "dimensions": ["customer_name"],
                "filters": [_filter("biz_year", "=", [2025]), _filter("customer_name", "=", ["广州客户"])],
                "group_by": [],
                "order_by": [{"dimension": "customer_name", "direction": "asc"}],
                "business_rules": [],
                "explicit_year_buckets": [2025],
                "limit": 50,
            },
        )
    )

    rendered = LogisticsSqlRenderer().render(validation)

    assert "dws_logistics_detail_union.customer_name AS customer_name" in rendered.sql
    assert "dws_logistics_detail_union.shipment_watt AS shipment_mw" in rendered.sql
    assert "广州客户" not in rendered.sql
    assert "dws_logistics_detail_union.customer_name = :p1" in rendered.sql
    assert "LIMIT :p2" in rendered.sql
    assert rendered.params == {"p0": 2025, "p1": "广州客户", "p2": 50}
    assert rendered.limit == 50


def test_renderer_rejects_failed_validation_result() -> None:
    """M4 renderer 只能消费 M3 validator 通过的结果，不能直接消费失败或未校验 plan。"""

    validation = _validate(_valid_candidate(plan={"requested_unit": "吨"}))

    with pytest.raises(ValueError, match="sql_renderer_requires_validated_plan"):
        LogisticsSqlRenderer().render(validation)


def test_renderer_rejects_reversed_left_join_direction() -> None:
    """LEFT JOIN 必须保持 catalog 左表到右表方向，不能为了连通性反向渲染。"""

    catalog = LogisticsSemanticCatalogLoader().load()
    join = next(item for item in catalog.joins if item.join_id == "system_task_assign")
    renderer = LogisticsSqlRenderer(catalog=catalog)

    with pytest.raises(ValueError, match="sql_renderer_left_join_direction_invalid::system_task_assign"):
        renderer._render_join_clause(join, {join.right_table}, [])


def _validate(candidate: dict):
    """使用真实 catalog 执行 M3 validator，保证 M4 单测从通过边界进入。"""

    return LogisticsSqlPlanValidator(catalog=LogisticsSemanticCatalogLoader().load()).validate(candidate)


def _filter(dimension: str, operator: str, values: list) -> dict:
    """生成测试用过滤条件。"""

    return {"dimension": dimension, "operator": operator, "values": values}


def _valid_candidate(**overrides) -> dict:
    """生成一份 M3 可通过的 SQLPlan candidate，测试按需覆盖。"""

    candidate = {
        "schema_version": "logistics_sqlplan_candidate.v1",
        "domain": "logistics",
        "strategy": "sql_direct",
        "catalog_version": "logistics_nl2sql_catalog.v1",
        "catalog_refs": [
            {"catalog_id": "table:dws_logistics_detail_union", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "metric:shipment_mw", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "metric:row_count", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "dimension:biz_year", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "dimension:logistics_company_name", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "rule:default_time_range", "catalog_version": "logistics_nl2sql_catalog.v1"},
        ],
        "plan": {
            "query_type": "ranking",
            "tables": ["dws_logistics_detail_union"],
            "joins": [],
            "metrics": ["shipment_mw", "row_count"],
            "dimensions": ["logistics_company_name"],
            "filters": [_filter("biz_year", "in", [2023, 2024, 2025, 2026])],
            "group_by": ["logistics_company_name"],
            "order_by": [{"metric": "shipment_mw", "direction": "desc"}],
            "business_rules": ["default_time_range"],
            "explicit_year_buckets": [2023, 2024, 2025, 2026],
            "requested_unit": "MW",
            "limit": 20,
        },
        "clarification_questions": [],
        "unsupported_reason": None,
        "confidence": 0.91,
    }
    return _deep_merge(candidate, overrides)


def _deep_merge(base: dict, overrides: dict) -> dict:
    """递归合并测试覆盖字段，列表和值直接替换，额外 catalog_refs 追加。"""

    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        elif isinstance(value, list) and key == "catalog_refs":
            merged[key] = [*merged[key], *value]
        else:
            merged[key] = value
    return merged

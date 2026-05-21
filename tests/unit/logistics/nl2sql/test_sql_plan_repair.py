from __future__ import annotations

import pytest

from backend.app.domains.logistics.services.nl2sql.sql_plan_repair import (
    LogisticsSqlPlanRepairResult,
    repair_logistics_sql_plan,
)


# ── RED 测试 1：正常 plan 不需要修复 ──────────────────

def test_repair_accepts_valid_plan() -> None:
    """合法的 SQLPlan 应通过 repair，不产生修复建议。"""
    result = repair_logistics_sql_plan({
        "schema_version": "logistics_sqlplan_candidate.v1",
        "domain": "logistics",
        "strategy": "sql_direct",
        "catalog_version": "logistics_nl2sql_catalog.v1",
        "catalog_refs": [
            {"catalog_id": "table:dws_logistics_detail_union", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "metric:shipment_mw", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "dimension:biz_year", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "rule:default_time_range", "catalog_version": "logistics_nl2sql_catalog.v1"},
        ],
        "plan": {
            "query_type": "aggregate",
            "tables": ["dws_logistics_detail_union"],
            "metrics": ["shipment_mw"],
            "dimensions": [],
            "filters": [{"dimension": "biz_year", "operator": "in", "values": [2023, 2024, 2025, 2026]}],
            "group_by": [],
            "order_by": [],
            "business_rules": ["default_time_range"],
            "explicit_year_buckets": [2023, 2024, 2025, 2026],
            "requested_unit": "MW",
            "limit": None,
        },
    })
    assert result.repaired is False
    assert result.modifications == []


# ── RED 测试 2：缺失 default_time_range 规则 ──────────

def test_repair_adds_missing_default_time_range() -> None:
    """缺失 default_time_range 和年份数据时，repair 应补充。"""
    result = repair_logistics_sql_plan({
        "schema_version": "logistics_sqlplan_candidate.v1",
        "domain": "logistics",
        "strategy": "sql_direct",
        "catalog_version": "logistics_nl2sql_catalog.v1",
        "catalog_refs": [
            {"catalog_id": "table:dws_logistics_detail_union", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "metric:shipment_mw", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "dimension:biz_year", "catalog_version": "logistics_nl2sql_catalog.v1"},
        ],
        "plan": {
            "query_type": "aggregate",
            "tables": ["dws_logistics_detail_union"],
            "metrics": ["shipment_mw"],
            "dimensions": [],
            "filters": [{"dimension": "biz_year", "operator": "in", "values": [2025]}],
            "group_by": [],
            "order_by": [],
            "business_rules": [],
            "explicit_year_buckets": [],
            "requested_unit": "MW",
            "limit": None,
        },
    })
    assert result.repaired is True
    # 年份过滤值 [2025] 不是默认4年，不应补充 default_time_range
    default_time_range_added = any(
        m["type"] == "add_business_rule" and m["value"] == "default_time_range"
        for m in result.modifications
    )
    if default_time_range_added:
        assert result.patch["plan"]["business_rules"] == ["default_time_range"]
    # explicit_year_buckets 必然补充
    assert any(m["type"] == "add_explicit_year_buckets" for m in result.modifications)
    assert result.patch["plan"]["explicit_year_buckets"] == [2025]


# ── RED 测试 3：缺失 explicit_year_buckets ────────────

def test_repair_adds_missing_explicit_year_buckets() -> None:
    """多年份过滤时，repair 应补充 explicit_year_buckets。"""
    result = repair_logistics_sql_plan({
        "schema_version": "logistics_sqlplan_candidate.v1",
        "domain": "logistics",
        "strategy": "sql_direct",
        "catalog_version": "logistics_nl2sql_catalog.v1",
        "catalog_refs": [
            {"catalog_id": "table:dws_logistics_detail_union", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "metric:shipment_mw", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "dimension:biz_year", "catalog_version": "logistics_nl2sql_catalog.v1"},
        ],
        "plan": {
            "query_type": "aggregate",
            "tables": ["dws_logistics_detail_union"],
            "metrics": ["shipment_mw"],
            "dimensions": [],
            "filters": [{"dimension": "biz_year", "operator": "in", "values": [2023, 2024, 2025, 2026]}],
            "group_by": [],
            "order_by": [],
            "business_rules": ["default_time_range"],
            "explicit_year_buckets": [],
            "requested_unit": "MW",
            "limit": None,
        },
    })
    assert result.repaired is True
    assert any(m["type"] == "add_explicit_year_buckets" for m in result.modifications)
    assert result.patch["plan"]["explicit_year_buckets"] == [2023, 2024, 2025, 2026]


# ── RED 测试 4：缺失 catalog_refs ─────────────────────

def test_repair_adds_missing_catalog_refs() -> None:
    """plan 中引用了业务规则但缺少对应的 catalog_ref，应补充。"""
    result = repair_logistics_sql_plan({
        "schema_version": "logistics_sqlplan_candidate.v1",
        "domain": "logistics",
        "strategy": "sql_direct",
        "catalog_version": "logistics_nl2sql_catalog.v1",
        "catalog_refs": [
            {"catalog_id": "table:dws_logistics_detail_union", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "metric:shipment_mw", "catalog_version": "logistics_nl2sql_catalog.v1"},
        ],
        "plan": {
            "query_type": "aggregate",
            "tables": ["dws_logistics_detail_union"],
            "metrics": ["shipment_mw"],
            "dimensions": [],
            "filters": [{"dimension": "biz_year", "operator": "in", "values": [2023, 2024, 2025, 2026]}],
            "group_by": [],
            "order_by": [],
            "business_rules": ["default_time_range"],
            "explicit_year_buckets": [2023, 2024, 2025, 2026],
            "requested_unit": "MW",
            "limit": None,
        },
    })
    assert result.repaired is True
    ref_ids = {r["catalog_id"] for r in result.patch.get("catalog_refs", [])}
    assert "dimension:biz_year" in ref_ids or "rule:default_time_range" in ref_ids


# ── RED 测试 5：order_by 中的 dimension 未在 plan 中声明 ──

def test_repair_adds_missing_dimension_from_order_by() -> None:
    """plan.metrics/dimensions 缺失 ORDER BY 引用的维度，应补充。"""
    result = repair_logistics_sql_plan({
        "schema_version": "logistics_sqlplan_candidate.v1",
        "domain": "logistics",
        "strategy": "sql_direct",
        "catalog_version": "logistics_nl2sql_catalog.v1",
        "catalog_refs": [
            {"catalog_id": "table:dws_logistics_detail_union", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "metric:shipment_mw", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "dimension:biz_year", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "dimension:logistics_company_name", "catalog_version": "logistics_nl2sql_catalog.v1"},
        ],
        "plan": {
            "query_type": "ranking",
            "tables": ["dws_logistics_detail_union"],
            "metrics": ["shipment_mw"],
            "dimensions": ["biz_year"],
            "filters": [{"dimension": "biz_year", "operator": "in", "values": [2025]}],
            "group_by": ["logistics_company_name"],
            "order_by": [{"dimension": "logistics_company_name", "direction": "desc"}],
            "business_rules": ["default_time_range"],
            "explicit_year_buckets": [2025],
            "requested_unit": "MW",
            "limit": 100,
        },
    })
    assert result.repaired is True
    # group_by 中的 logistics_company_name 不在 dimensions 中，应补充
    assert "logistics_company_name" in result.patch["plan"]["dimensions"]


# ── RED 测试 6：缺失 limit ────────────────────────────

def test_repair_adds_missing_limit() -> None:
    """ranking 或 detail 类型缺少 limit 时，应补充安全默认值。"""
    result = repair_logistics_sql_plan({
        "schema_version": "logistics_sqlplan_candidate.v1",
        "domain": "logistics",
        "strategy": "sql_direct",
        "catalog_version": "logistics_nl2sql_catalog.v1",
        "catalog_refs": [
            {"catalog_id": "table:dws_logistics_detail_union", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "metric:shipment_mw", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "dimension:biz_year", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "dimension:logistics_company_name", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "rule:default_time_range", "catalog_version": "logistics_nl2sql_catalog.v1"},
        ],
        "plan": {
            "query_type": "ranking",
            "tables": ["dws_logistics_detail_union"],
            "metrics": ["shipment_mw"],
            "dimensions": ["logistics_company_name"],
            "filters": [{"dimension": "biz_year", "operator": "in", "values": [2025]}],
            "group_by": [],
            "order_by": [],
            "business_rules": ["default_time_range"],
            "explicit_year_buckets": [2025],
            "requested_unit": "MW",
            "limit": None,
        },
    })
    assert result.repaired is True
    assert any(m["type"] == "add_limit" for m in result.modifications)
    assert result.patch["plan"]["limit"] is not None

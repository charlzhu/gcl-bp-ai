from __future__ import annotations

from copy import deepcopy

import pytest

from backend.app.domains.business_analysis.services.inventory_sales_production.semantic_catalog import (
    InventorySalesProductionCatalogColumn,
    InventorySalesProductionCatalogTable,
    InventorySalesProductionSemanticCatalogLoader,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.sql_plan import (
    InventorySalesProductionSqlPlanValidator,
)

CATALOG_VERSION = "business_analysis_inventory_sales_production_catalog.v1"


def test_isp_sql_plan_validator_accepts_catalog_aligned_summary_without_sql_strings() -> None:
    """合法产销存 SQLPlan 只能引用 catalog ID，且 normalized plan 不携带 SQL 字符串。"""

    result = _validate(_valid_candidate())

    assert result.ok is True, result.errors
    assert result.error_codes == []
    assert result.normalized_plan is not None
    assert result.normalized_plan.domain == "business_analysis"
    assert result.normalized_plan.sub_domain == "inventory_sales_production"
    assert result.normalized_plan.query_key == "ba_isp_metric_summary"
    assert result.normalized_plan.metrics == ["shipment_volume"]

    normalized_payload = result.normalized_plan.model_dump_json().lower()
    for forbidden in ("select ", " where ", " from ", "sum(", "raw_sql", "free_sql"):
        assert forbidden not in normalized_payload


def test_isp_sql_plan_validator_rejects_non_middle_db_tables_and_sql_payload_without_echoing_values() -> None:
    """LLM candidate 不能夹带原始工作簿表、raw_sql/sql-like 字符串，错误码不能回显原文。"""

    candidate = _valid_candidate(
        raw_sql="select * from ods_ba_isp_excel_workbook",
        catalog_refs=[{"catalog_id": "table:ods_ba_isp_excel_workbook", "catalog_version": CATALOG_VERSION}],
        plan={
            "tables": ["ods_ba_isp_excel_workbook"],
            "filters": [_filter("business_year", "=", ["2024 OR 1=1"])],
        },
    )

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_forbidden_key::raw_sql" in result.error_codes
    assert "sqlplan_forbidden_sql_string::raw_sql" in result.error_codes
    assert "sqlplan_forbidden_sql_string::plan.filters[0].values[0]" in result.error_codes
    assert "sqlplan_table_not_allowed::ods_ba_isp_excel_workbook" in result.error_codes
    assert all("2024 OR 1=1" not in error for error in result.error_codes)
    assert result.normalized_plan is None


def test_isp_sql_plan_validator_requires_catalog_refs_and_matching_versions() -> None:
    """SQLPlan metric/table/dimension 必须来自当前 M5 Semantic Catalog 版本，不能使用旧版本或虚构 catalog ID。"""

    missing_ref = _valid_candidate(plan={"metrics": ["invented_metric"]})
    stale_version = _valid_candidate(
        catalog_refs=[{"catalog_id": "metric:shipment_volume", "catalog_version": "old_catalog"}]
    )

    missing_result = _validate(missing_ref)
    stale_result = _validate(stale_version)

    assert missing_result.ok is False
    assert "sqlplan_metric_not_found::invented_metric" in missing_result.error_codes
    assert stale_result.ok is False
    assert "sqlplan_catalog_version_mismatch::metric:shipment_volume::old_catalog" in stale_result.error_codes


def test_isp_sql_plan_validator_uses_catalog_query_key_gate_for_metric_dimension_policy() -> None:
    """query_key、metric、dimension 组合必须复用 catalog support gate，而不是让 candidate 自由组合。"""

    summary_with_dimension = _valid_candidate(plan={"dimensions": ["base_name"], "group_by": ["base_name"]})
    invoice_without_explicit_phrase = _valid_candidate(
        catalog_refs=[{"catalog_id": "metric:invoice_sales_volume", "catalog_version": CATALOG_VERSION}],
        plan={"metrics": ["invoice_sales_volume"]},
    )

    summary_result = _validate(summary_with_dimension)
    invoice_result = _validate(invoice_without_explicit_phrase)

    assert summary_result.ok is False
    assert (
        "sqlplan_catalog_support_error::catalog_query_key_dimension_mismatch::ba_isp_metric_summary::base_name"
        in summary_result.error_codes
    )
    assert invoice_result.ok is False
    assert (
        "sqlplan_catalog_support_error::catalog_metric_requires_explicit_phrase::invoice_sales_volume"
        in invoice_result.error_codes
    )


def test_isp_sql_plan_validator_blocks_period_end_inventory_annual_sum() -> None:
    """库存/存货/寄存属于期末时点指标，年度问题也不能被 candidate 改成 SUM 聚合。"""

    candidate = _valid_candidate(
        catalog_refs=[{"catalog_id": "metric:ending_inventory_volume", "catalog_version": CATALOG_VERSION}],
        plan={
            "query_key": "ba_isp_inventory_snapshot",
            "metrics": ["ending_inventory_volume"],
            "period_type": "year",
            "calculation_policy": "sum",
        },
    )

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_period_end_metric_cannot_sum::ending_inventory_volume" in result.error_codes


@pytest.mark.parametrize(
    ("plan_overrides", "expected_error"),
    [
        ({"period_type": "month_range", "start_month": 1, "end_month": 3}, "sqlplan_period_type_not_supported::month_range"),
        ({"business_rules": ["year_over_year"]}, "sqlplan_time_comparison_not_supported::year_over_year"),
        ({"business_rules": ["month_over_month"]}, "sqlplan_time_comparison_not_supported::month_over_month"),
        ({"business_rules": ["unpublished_month"], "period_type": "month", "month": 12}, "sqlplan_unpublished_month_blocks_sql_direct"),
    ],
)
def test_isp_sql_plan_validator_blocks_unsupported_period_boundaries(plan_overrides: dict, expected_error: str) -> None:
    """任意月份区间、同比/环比、未发布月份必须在 SQLPlan 门禁 fail-closed。"""

    result = _validate(_valid_candidate(plan=plan_overrides))

    assert result.ok is False
    assert expected_error in result.error_codes


def test_isp_sql_plan_validator_rechecks_catalog_field_boundaries_even_with_polluted_catalog() -> None:
    """即使注入污染 catalog，validator 也必须二次校验表域、字段白名单和 source/raw/trace 字段。"""

    catalog = InventorySalesProductionSemanticCatalogLoader().load()
    polluted_table = InventorySalesProductionCatalogTable(
        table_name="dwd_ba_isp_monthly_fact",
        display_name="污染事实表",
        domain="business_analysis",
        sub_domain="inventory_sales_production",
        source_system="middle_db",
        allowed_read=True,
        columns=[
            *catalog.tables[0].columns,
            InventorySalesProductionCatalogColumn(name="raw_payload", data_type="text", semantic_role="trace"),
        ],
    )
    polluted_catalog = catalog.model_copy(update={"tables": [polluted_table, *catalog.tables[1:]]})

    result = _validate(_valid_candidate(), catalog=polluted_catalog)

    assert result.ok is False
    assert "sqlplan_table_column_not_allowed::dwd_ba_isp_monthly_fact.raw_payload" in result.error_codes


def test_isp_sql_plan_validator_redacts_sql_like_segments_from_all_error_codes() -> None:
    """所有动态错误段都不能回显 SQL-like candidate 值，只能暴露安全路径或脱敏占位。"""

    candidate = _valid_candidate(
        catalog_version="select version from secret_catalog",
        catalog_refs=[
            {"catalog_id": "table:dwd_ba_isp_monthly_fact", "catalog_version": "select version from secret_refs"},
            {"catalog_id": "metric:select password from secret_metric", "catalog_version": CATALOG_VERSION},
        ],
        plan={
            "tables": ["select * from secret_table"],
            "metrics": ["sum(select password from secret_metric)"],
            "dimensions": ["where 1=1"],
            "filters": [_filter("select * from secret_filter", "=", ["select token from secret_filter_value"])],
        },
    )

    result = _validate(candidate)

    assert result.ok is False
    joined_errors = "\n".join(result.error_codes).lower()
    for leaked in (
        "select version from secret_catalog",
        "select version from secret_refs",
        "select password from secret_metric",
        "select * from secret_table",
        "where 1=1",
        "select * from secret_filter",
        "select token from secret_filter_value",
    ):
        assert leaked not in joined_errors
    assert "redacted" in joined_errors


def test_isp_sql_plan_validator_enforces_fixed_catalog_version_even_with_injected_catalog() -> None:
    """candidate 不能通过注入旧版本 catalog 让版本号自洽，validator 必须固定到 M5 catalog v1。"""

    catalog = InventorySalesProductionSemanticCatalogLoader().load()
    stale_catalog = catalog.model_copy(update={"catalog_version": "old_catalog"})
    candidate = _valid_candidate(
        catalog_version="old_catalog",
        catalog_refs=[
            {"catalog_id": "table:dwd_ba_isp_monthly_fact", "catalog_version": "old_catalog"},
            {"catalog_id": "metric:shipment_volume", "catalog_version": "old_catalog"},
            {"catalog_id": "dimension:business_year", "catalog_version": "old_catalog"},
        ],
    )

    result = _validate(candidate, catalog=stale_catalog)

    assert result.ok is False
    assert "sqlplan_catalog_version_invalid::old_catalog::business_analysis_inventory_sales_production_catalog.v1" in result.error_codes
    assert (
        "sqlplan_candidate_catalog_version_mismatch::old_catalog::business_analysis_inventory_sales_production_catalog.v1"
        in result.error_codes
    )


def test_isp_sql_plan_validator_blocks_start_end_month_smuggling_outside_ytd() -> None:
    """candidate 不能把任意月份区间藏在 year/month/quarter 等支持 period_type 里绕过 month_range 拒绝。"""

    result = _validate(_valid_candidate(plan={"period_type": "year", "start_month": 3, "end_month": 5}))

    assert result.ok is False
    assert "sqlplan_period_start_end_range_not_supported::year" in result.error_codes


def test_isp_sql_plan_validator_blocks_unflagged_unpublished_months() -> None:
    """即使 candidate 没有声明 unpublished_month 规则，显式未发布月份也必须 deterministic fail-closed。"""

    result = _validate(_valid_candidate(plan={"period_type": "month", "year": 2026, "month": 5}))

    assert result.ok is False
    assert "sqlplan_unpublished_month_blocks_sql_direct::2026::5::4" in result.error_codes


def test_isp_sql_plan_validator_redacts_sql_like_values_from_non_scanner_errors() -> None:
    """非扫描器错误码也不能回显 LLM 夹带的 SQL-like table/metric/catalog_version 原文。"""

    candidate = _valid_candidate()
    candidate["catalog_version"] = "business_analysis_inventory_sales_production_catalog.v1 OR 1=1"
    candidate["catalog_refs"] = [
        {
            "catalog_id": "table:select * from sys_query_log",
            "catalog_version": "business_analysis_inventory_sales_production_catalog.v1 OR 1=1",
        },
        {
            "catalog_id": "metric:select password from sys_query_log",
            "catalog_version": CATALOG_VERSION,
        },
    ]
    candidate["plan"]["tables"] = ["select * from sys_query_log"]
    candidate["plan"]["metrics"] = ["select password from sys_query_log"]
    candidate["plan"]["dimensions"] = ["business_year OR 1=1"]
    candidate["plan"]["filters"] = [_filter("business_year OR 1=1", "=", [2024])]

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_forbidden_sql_string::catalog_version" in result.error_codes
    assert "sqlplan_forbidden_sql_string::plan.tables[0]" in result.error_codes
    assert any(error.endswith("::redacted") for error in result.error_codes)
    leaked_error_text = "\n".join(result.error_codes).lower()
    for leaked_fragment in ("select *", "select password", "or 1=1", "sys_query_log"):
        assert leaked_fragment not in leaked_error_text


def test_isp_sql_plan_validator_requires_fixed_canonical_catalog_version_even_when_catalog_injected() -> None:
    """注入 catalog 的 catalog_version 也必须固定为 M5 v1，不能让 candidate 与污染 catalog 串通通过。"""

    polluted_version = "business_analysis_inventory_sales_production_catalog.v2"
    catalog = InventorySalesProductionSemanticCatalogLoader().load().model_copy(update={"catalog_version": polluted_version})
    candidate = _valid_candidate()
    candidate["catalog_version"] = polluted_version
    for ref in candidate["catalog_refs"]:
        ref["catalog_version"] = polluted_version

    result = _validate(candidate, catalog=catalog)

    assert result.ok is False
    assert (
        f"sqlplan_catalog_version_invalid::{polluted_version}::business_analysis_inventory_sales_production_catalog.v1"
        in result.error_codes
    )
    assert result.normalized_plan is None


def test_isp_sql_plan_validator_rejects_start_end_month_when_period_type_is_not_month_range() -> None:
    """start_month/end_month 只能随 month_range 出现；其他期间带月份区间必须业务化澄清。"""

    result = _validate(_valid_candidate(plan={"period_type": "year", "start_month": 1, "end_month": 3}))

    assert result.ok is False
    assert "sqlplan_period_start_end_range_not_supported::year" in result.error_codes
    assert result.normalized_plan is None


def test_isp_sql_plan_validator_redacts_sql_expression_metric_ids_from_error_codes() -> None:
    """函数式 SQL 表达式伪装成指标 ID 时，非扫描器错误也不能回显表达式原文。"""

    candidate = _valid_candidate(plan={"metrics": ["sum(secret_col)"]})

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_metric_not_found::redacted" in result.error_codes
    assert "sum(secret_col)" not in "\n".join(result.error_codes).lower()
    assert result.normalized_plan is None


def test_isp_sql_plan_validator_redacts_sql_like_extra_field_names_from_schema_errors() -> None:
    """额外字段名本身也可能是 LLM 注入载荷，schema 错误路径不能回显 SQL-like 字段名。"""

    candidate = _valid_candidate(plan={"sum(secret_col)": "ignored"})

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_schema_invalid::plan.redacted::extra_forbidden" in result.error_codes
    assert "sum(secret_col)" not in "\n".join(result.error_codes).lower()
    assert result.normalized_plan is None


def test_isp_sql_plan_validator_blocks_group_by_dimension_smuggling_for_summary_query_key() -> None:
    """summary query_key 不能把拆分维度藏在 group_by 里绕过 catalog support gate。"""

    candidate = _valid_candidate(
        catalog_refs=[{"catalog_id": "dimension:base_name", "catalog_version": CATALOG_VERSION}],
        plan={"group_by": ["base_name"]},
    )

    result = _validate(candidate)

    assert result.ok is False
    assert (
        "sqlplan_catalog_support_error::catalog_query_key_dimension_mismatch::ba_isp_metric_summary::base_name"
        in result.error_codes
    )
    assert result.normalized_plan is None


@pytest.mark.parametrize(
    ("plan_overrides", "expected_error"),
    [
        ({"period_type": "year", "month": 5}, "sqlplan_period_month_not_allowed::year"),
        ({"period_type": "year", "quarter": 2}, "sqlplan_period_quarter_not_allowed::year"),
        ({"period_type": "month", "month": 4, "quarter": 2}, "sqlplan_period_quarter_not_allowed::month"),
        ({"period_type": "quarter", "quarter": 2, "month": 4}, "sqlplan_period_month_not_allowed::quarter"),
    ],
)
def test_isp_sql_plan_validator_rejects_period_field_smuggling(plan_overrides: dict, expected_error: str) -> None:
    """month/quarter 字段只能出现在匹配的 period_type 下，避免 downstream renderer 误消费。"""

    result = _validate(_valid_candidate(plan=plan_overrides))

    assert result.ok is False
    assert expected_error in result.error_codes
    assert result.normalized_plan is None


def test_isp_sql_plan_validator_redacts_sql_expression_calculation_policy_errors() -> None:
    """聚合策略错误码也属于非扫描器错误，不能回显函数式 SQL 表达式。"""

    candidate = _valid_candidate(plan={"calculation_policy": "sum(secret_col)"})

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_metric_calculation_policy_mismatch::shipment_volume::redacted" in result.error_codes
    assert "sum(secret_col)" not in "\n".join(result.error_codes).lower()
    assert result.normalized_plan is None


def test_isp_sql_plan_validator_redacts_sql_like_extra_field_names_from_scanner_paths() -> None:
    """扫描器路径中的动态字段名也必须脱敏，不能通过 forbidden_sql_string 路径泄露。"""

    candidate = _valid_candidate(plan={"sum(secret_col)": "select token from sys_query_log"})

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_forbidden_sql_string::plan.redacted" in result.error_codes
    assert "sqlplan_schema_invalid::plan.redacted::extra_forbidden" in result.error_codes
    assert "sum(secret_col)" not in "\n".join(result.error_codes).lower()
    assert result.normalized_plan is None


def test_isp_sql_plan_validator_redacts_standalone_internal_log_table_identifiers() -> None:
    """日志/审计类内部表名即使未组成 SELECT 语句，也不能出现在任何错误码动态片段中。"""

    candidate = _valid_candidate()
    candidate["catalog_refs"] = [
        {"catalog_id": "table:sys_query_log", "catalog_version": CATALOG_VERSION},
        {"catalog_id": "metric:sys_query_log", "catalog_version": CATALOG_VERSION},
        {"catalog_id": "dimension:sys_query_log", "catalog_version": CATALOG_VERSION},
    ]
    candidate["plan"]["tables"] = ["sys_query_log"]
    candidate["plan"]["metrics"] = ["sys_query_log"]
    candidate["plan"]["dimensions"] = ["sys_query_log"]
    candidate["plan"]["filters"] = [_filter("sys_query_log", "=", ["sys_query_log"])]
    candidate["plan"]["business_flags"] = {"sys_query_log": True}

    result = _validate(candidate)

    assert result.ok is False
    joined_errors = "\n".join(result.error_codes).lower()
    assert "sys_query_log" not in joined_errors
    assert "redacted" in joined_errors
    assert result.normalized_plan is None


@pytest.mark.parametrize(
    ("flag_name", "expected_error"),
    [
        ("yoy", "sqlplan_time_comparison_not_supported::yoy"),
        ("year_over_year", "sqlplan_time_comparison_not_supported::year_over_year"),
        ("mom", "sqlplan_time_comparison_not_supported::mom"),
        ("month_over_month", "sqlplan_time_comparison_not_supported::month_over_month"),
    ],
)
def test_isp_sql_plan_validator_blocks_time_comparison_flags_in_business_flags(
    flag_name: str,
    expected_error: str,
) -> None:
    """同比/环比开关即使藏在 business_flags 中，也必须在 SQLPlan 门禁 fail-closed。"""

    result = _validate(_valid_candidate(plan={"business_flags": {flag_name: True}}))

    assert result.ok is False
    assert expected_error in result.error_codes
    assert result.normalized_plan is None


def test_isp_sql_plan_validator_rejects_unknown_business_flags() -> None:
    """business_flags 只允许已知控制开关，未知开关不能被带入后续 renderer。"""

    result = _validate(_valid_candidate(plan={"business_flags": {"unsafe_flag": True}}))

    assert result.ok is False
    assert "sqlplan_business_flag_not_allowed::unsafe_flag" in result.error_codes
    assert result.normalized_plan is None


@pytest.mark.parametrize(
    ("plan_overrides", "expected_error"),
    [
        ({"period_type": "year", "month": 13}, "sqlplan_month_out_of_range::13"),
        ({"period_type": "year", "quarter": 5}, "sqlplan_quarter_out_of_range::5"),
        ({"period_type": "year", "month": 5, "year": 2026}, "sqlplan_unpublished_month_blocks_sql_direct::2026::5::4"),
    ],
)
def test_isp_sql_plan_validator_checks_supplied_month_quarter_even_when_period_type_differs(
    plan_overrides: dict,
    expected_error: str,
) -> None:
    """candidate 不能把非法月份/季度塞到非活跃 period_type 字段里绕过时间门禁。"""

    result = _validate(_valid_candidate(plan=plan_overrides))

    assert result.ok is False
    assert expected_error in result.error_codes
    assert result.normalized_plan is None


@pytest.mark.parametrize(
    ("filter_item", "expected_error"),
    [
        ({"dimension": "business_month", "operator": "=", "values": [13]}, "sqlplan_month_value_out_of_range::13"),
        ({"dimension": "business_month", "operator": "=", "values": [5]}, "sqlplan_unpublished_month_blocks_sql_direct::2026::5::4"),
        ({"dimension": "business_month", "operator": "between", "values": [1, 3]}, "sqlplan_month_filter_operator_unsupported::between"),
    ],
)
def test_isp_sql_plan_validator_checks_business_month_filter_boundaries(filter_item: dict, expected_error: str) -> None:
    """business_month 过滤值也必须校验月份范围、已发布月份和任意区间禁用边界。"""

    result = _validate(_valid_candidate(plan={"year": 2026, "filters": [filter_item]}))

    assert result.ok is False
    assert expected_error in result.error_codes
    assert result.normalized_plan is None


def _validate(candidate: dict, *, catalog=None):
    """使用真实 catalog 或测试传入的污染 catalog 执行产销存 SQLPlan 校验。"""

    return InventorySalesProductionSqlPlanValidator(
        catalog=catalog or InventorySalesProductionSemanticCatalogLoader().load()
    ).validate(candidate)


def _filter(dimension: str, operator: str, values: list) -> dict:
    """生成测试用过滤条件。"""

    return {"dimension": dimension, "operator": operator, "values": values}


def _valid_candidate(**overrides) -> dict:
    """生成一份合法的产销存 SQLPlan candidate，并允许测试按需覆盖。"""

    candidate = {
        "schema_version": "business_analysis_inventory_sales_production_sqlplan_candidate.v1",
        "domain": "business_analysis",
        "sub_domain": "inventory_sales_production",
        "strategy": "sql_direct",
        "catalog_version": CATALOG_VERSION,
        "catalog_refs": [
            {"catalog_id": "table:dwd_ba_isp_monthly_fact", "catalog_version": CATALOG_VERSION},
            {"catalog_id": "metric:shipment_volume", "catalog_version": CATALOG_VERSION},
            {"catalog_id": "dimension:business_year", "catalog_version": CATALOG_VERSION},
        ],
        "plan": {
            "query_key": "ba_isp_metric_summary",
            "tables": ["dwd_ba_isp_monthly_fact"],
            "metrics": ["shipment_volume"],
            "dimensions": [],
            "filters": [_filter("business_year", "=", [2024])],
            "group_by": [],
            "order_by": [],
            "business_rules": [],
            "business_flags": {},
            "period_type": "year",
            "year": 2024,
            "month": None,
            "quarter": None,
            "start_month": None,
            "end_month": None,
            "calculation_policy": "sum",
            "limit": None,
        },
        "clarification_questions": [],
        "unsupported_reason": None,
        "confidence": 0.91,
    }
    return _deep_merge(candidate, overrides)


def _deep_merge(base: dict, overrides: dict) -> dict:
    """递归合并测试覆盖字段，列表和值直接替换。"""

    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        elif isinstance(value, list) and key == "catalog_refs":
            merged[key] = [*merged[key], *value]
        else:
            merged[key] = value
    return merged

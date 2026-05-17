from __future__ import annotations

from copy import deepcopy

import pytest

from backend.app.domains.logistics.services.nl2sql.semantic_catalog import (
    LogisticsCatalogColumn,
    LogisticsCatalogTable,
    LogisticsSemanticCatalogLoader,
)
from backend.app.domains.logistics.services.nl2sql.sql_plan import LogisticsSqlPlanValidator


def test_sql_plan_validator_accepts_catalog_aligned_plan_without_sql_strings() -> None:
    """合法 SQLPlan 只能引用 catalog ID，并补齐默认 2023-2026 时间过滤。"""

    result = _validate(_valid_candidate())

    assert result.ok is True, result.errors
    assert result.error_codes == []
    assert result.normalized_plan is not None
    assert result.normalized_plan.domain == "logistics"
    assert result.normalized_plan.filters[0].dimension == "biz_year"
    assert result.normalized_plan.filters[0].values == [2023, 2024, 2025, 2026]
    assert result.normalized_plan.limit == 20

    normalized_payload = result.normalized_plan.model_dump_json().lower()
    for forbidden in ("select ", " where ", " having ", " from ", "sum(", "raw_sql", "free_sql"):
        assert forbidden not in normalized_payload


def test_sql_plan_validator_rejects_non_whitelisted_table() -> None:
    """M3 不能消费非物流中间库白名单表，即使 LLM candidate 给了 catalog_ref。"""

    candidate = _valid_candidate(
        catalog_refs=[{"catalog_id": "table:sys_query_log", "catalog_version": "logistics_nl2sql_catalog.v1"}],
        plan={"tables": ["sys_query_log"]},
    )

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_table_not_allowed::sys_query_log" in result.error_codes
    assert result.normalized_plan is None


@pytest.mark.parametrize("source_columns", [[], ["missing_fee"]])
def test_sql_plan_validator_rechecks_metric_source_columns(source_columns: list[str]) -> None:
    """即使 canonical catalog 被污染，指标依赖字段缺失或未知也必须 fail-closed。"""

    catalog = LogisticsSemanticCatalogLoader().load()
    broken_metrics = [
        metric.model_copy(update={"source_columns": source_columns}) if metric.metric_id == "shipment_mw" else metric
        for metric in catalog.metrics
    ]
    broken_catalog = catalog.model_copy(update={"metrics": broken_metrics})

    result = _validate(_valid_candidate(), catalog=broken_catalog)

    assert result.ok is False
    if source_columns:
        assert (
            "sqlplan_metric_column_not_allowed::shipment_mw::dws_logistics_detail_union.missing_fee"
            in result.error_codes
        )
    else:
        assert "sqlplan_metric_source_columns_required::shipment_mw" in result.error_codes


def test_sql_plan_validator_rechecks_dimension_columns_and_table_scope() -> None:
    """维度字段必须存在且所属表必须进入当前 plan，不能跨表错配。"""

    catalog = LogisticsSemanticCatalogLoader().load()
    broken_dimensions = [
        dimension.model_copy(update={"column": "missing_city"}) if dimension.dimension_id == "city" else dimension
        for dimension in catalog.dimensions
    ]
    broken_catalog = catalog.model_copy(update={"dimensions": broken_dimensions})
    candidate = _valid_candidate(
        catalog_refs=[{"catalog_id": "dimension:city", "catalog_version": "logistics_nl2sql_catalog.v1"}],
        plan={"filters": [_filter("city", "=", ["广州"])]},
    )

    result = _validate(candidate, catalog=broken_catalog)

    assert result.ok is False
    assert "sqlplan_dimension_column_not_allowed::city::dwd_logistics_hist_shipment_detail.missing_city" in result.error_codes
    assert "sqlplan_dimension_table_not_in_plan::city::dwd_logistics_hist_shipment_detail" in result.error_codes


def test_sql_plan_validator_rejects_unknown_filter_group_and_order_fields() -> None:
    """filter/group_by/order_by 只能引用 catalog 中存在且当前 plan 表范围内的字段。"""

    candidate = _valid_candidate(
        plan={
            "filters": [_filter("missing_dimension", "=", ["x"])],
            "group_by": ["missing_dimension"],
            "order_by": [{"dimension": "missing_dimension", "direction": "desc"}],
        }
    )

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_dimension_not_found::missing_dimension" in result.error_codes
    assert "sqlplan_group_by_dimension_not_found::missing_dimension" in result.error_codes
    assert "sqlplan_order_by_reference_not_found::missing_dimension" in result.error_codes


def test_sql_plan_validator_rechecks_join_grammar_and_declared_sides() -> None:
    """SQLPlan validator 必须再次校验 join.on，不能只信 M1 loader 的结果。"""

    catalog = LogisticsSemanticCatalogLoader().load()
    broken_joins = [
        join.model_copy(update={"on": ["dwd_logistics_assign_task.ship_task_id = dwd_logistics_ship_task.task_id OR 1=1"]})
        if join.join_id == "system_task_assign"
        else join
        for join in catalog.joins
    ]
    broken_catalog = catalog.model_copy(update={"joins": broken_joins})
    candidate = _valid_candidate(
        catalog_refs=[
            {"catalog_id": "table:dwd_logistics_ship_task", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "table:dwd_logistics_assign_task", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "join:system_task_assign", "catalog_version": "logistics_nl2sql_catalog.v1"},
        ],
        plan={"tables": ["dwd_logistics_ship_task", "dwd_logistics_assign_task"], "joins": ["system_task_assign"]},
    )

    result = _validate(candidate, catalog=broken_catalog)

    assert result.ok is False
    assert "sqlplan_join_on_expression_invalid::system_task_assign" in result.error_codes


def test_sql_plan_validator_rejects_raw_sql_keys_and_sql_like_strings() -> None:
    """LLM candidate 任意层级夹带 raw_sql/sql/where/free_sql 或 SQL 片段时必须阻断。"""

    candidate = _valid_candidate(
        raw_sql="select * from sys_query_log",
        plan={"filters": [_filter("biz_year", "in", ["2023 OR 1=1"])]},
    )

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_forbidden_key::raw_sql" in result.error_codes
    assert "sqlplan_forbidden_sql_string::raw_sql" in result.error_codes
    assert "sqlplan_forbidden_sql_string::plan.filters[0].values[0]" in result.error_codes
    assert all("2023 OR 1=1" not in error for error in result.error_codes)
    assert result.normalized_plan is None


@pytest.mark.parametrize("unsafe_value", ["EXPLAIN SELECT 1", "2023 UNION SELECT password", "2023 -- bypass", "1=1"])
def test_sql_plan_validator_rejects_extended_sql_like_filter_values(unsafe_value: str) -> None:
    """SQL-like 扫描必须覆盖 EXPLAIN/UNION/注释/裸 1=1，且错误码不回显原文。"""

    candidate = _valid_candidate(plan={"filters": [_filter("biz_year", "in", [unsafe_value])]})

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_forbidden_sql_string::plan.filters[0].values[0]" in result.error_codes
    assert all(unsafe_value not in error for error in result.error_codes)


def test_sql_plan_validator_rejects_non_scalar_filter_values() -> None:
    """过滤值只能是安全标量，不能把 dict/list 这类非结构化对象交给后续 renderer。"""

    candidate = _valid_candidate(plan={"filters": [_filter("biz_year", "in", [{"year": 2025}])]})

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_filter_value_not_scalar::biz_year" in result.error_codes


def test_sql_plan_validator_blocks_clarification_and_unsupported_states() -> None:
    """存在澄清或不支持原因时，validator 必须阻止后续 SQL 生成状态。"""

    clarify_result = _validate(_valid_candidate(clarification_questions=["请补充时间范围"]))
    unsupported_result = _validate(_valid_candidate(unsupported_reason="当前不支持吨数口径"))

    assert clarify_result.ok is False
    assert "sqlplan_blocked_by_clarification" in clarify_result.error_codes
    assert unsupported_result.ok is False
    assert "sqlplan_blocked_by_unsupported" in unsupported_result.error_codes


def test_sql_plan_validator_requires_default_time_filter_or_explicit_error() -> None:
    """未给时间时必须在 plan 中显式携带 2023-2026 默认年份过滤，否则 M3 fail-closed。"""

    candidate = _valid_candidate(plan={"filters": [], "business_rules": ["default_time_range"]})

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_missing_default_time_filter::2023_2026" in result.error_codes


def test_sql_plan_validator_rejects_years_outside_middle_db_scope() -> None:
    """即使未声明 default_time_range，候选年份也不能越过当前 2023-2026 物流边界。"""

    candidate = _valid_candidate(
        plan={
            "filters": [_filter("biz_year", "in", [2022, 2027])],
            "business_rules": [],
            "explicit_year_buckets": [2022, 2027],
        }
    )

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_year_out_of_scope::2022" in result.error_codes
    assert "sqlplan_year_out_of_scope::2027" in result.error_codes


def test_sql_plan_validator_requires_explicit_buckets_for_multi_year_filters() -> None:
    """多年份过滤必须显式携带年份桶，避免后续静默丢失 0 行年份。"""

    candidate = _valid_candidate(
        plan={
            "filters": [_filter("biz_year", "in", [2023, 2024, 2025])],
            "business_rules": [],
            "explicit_year_buckets": [],
        }
    )

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_explicit_year_buckets_required::2023,2024,2025" in result.error_codes


def test_sql_plan_validator_checks_all_biz_year_filters() -> None:
    """多个年份过滤都必须被检查，不能只看第一组合法年份后放过后续越界年份。"""

    candidate = _valid_candidate(
        plan={
            "filters": [
                _filter("biz_year", "in", [2023, 2024, 2025, 2026]),
                _filter("biz_year", "in", [2027]),
            ],
            "explicit_year_buckets": [2023, 2024, 2025, 2026, 2027],
        }
    )

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_year_out_of_scope::2027" in result.error_codes


def test_sql_plan_validator_rejects_unsupported_year_filter_operators() -> None:
    """年份范围不能用半开条件交给后续渲染器猜边界，必须 fail-closed。"""

    candidate = _valid_candidate(
        plan={
            "filters": [_filter("biz_year", ">=", [2023])],
            "business_rules": [],
            "explicit_year_buckets": [2023],
        }
    )

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_year_filter_operator_unsupported::>=" in result.error_codes


def test_sql_plan_validator_rejects_unbounded_between_year_ranges() -> None:
    """between 年份必须先校验边界再展开，避免大范围候选导致 validator 资源耗尽。"""

    candidate = _valid_candidate(
        plan={
            "filters": [_filter("biz_year", "between", [1900, 2100])],
            "business_rules": [],
            "explicit_year_buckets": [1900, 2100],
        }
    )

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_year_between_range_out_of_scope::1900::2100" in result.error_codes


@pytest.mark.parametrize("year_value", [2023.5, "2023.5", True])
def test_sql_plan_validator_rejects_non_integral_year_values(year_value) -> None:
    """年份过滤必须是明确整数年份，不能用 int() 强制截断小数或布尔值。"""

    candidate = _valid_candidate(
        plan={
            "filters": [_filter("biz_year", "in", [year_value])],
            "business_rules": [],
            "explicit_year_buckets": [2023],
        }
    )

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_year_value_invalid::plan.filters[0].values[0]" in result.error_codes


def test_sql_plan_validator_blocks_unsupported_tonnage_rule_even_if_unit_is_rewritten() -> None:
    """LLM 把吨数问题改写成 MW 时，只要带 unsupported_tonnage 规则就不能进入 sql_direct。"""

    candidate = _valid_candidate(
        catalog_refs=[{"catalog_id": "rule:unsupported_tonnage", "catalog_version": "logistics_nl2sql_catalog.v1"}],
        plan={"business_rules": ["unsupported_tonnage"], "requested_unit": "MW"},
    )

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_unsupported_tonnage_rule_blocks_sql_direct" in result.error_codes


def test_sql_plan_validator_rejects_candidate_schema_version_mismatch() -> None:
    """SQLPlan candidate schema_version 必须精确匹配，避免旧结构被当作 M3 合法输入。"""

    candidate = _valid_candidate(schema_version="legacy_sqlplan.v0")

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_schema_version_mismatch::legacy_sqlplan.v0" in result.error_codes


def test_sql_plan_validator_rejects_polluted_injected_catalog_table_allowlist() -> None:
    """即使测试或上游注入了污染 catalog，validator 也必须复核硬白名单。"""

    catalog = LogisticsSemanticCatalogLoader().load()
    polluted_table = LogisticsCatalogTable(
        table_name="sys_query_log",
        display_name="查询日志",
        domain="logistics",
        source_system="middle_db",
        allowed_read=True,
        columns=[LogisticsCatalogColumn(name="biz_year", data_type="int")],
    )
    polluted_catalog = catalog.model_copy(update={"tables": [*catalog.tables, polluted_table]})
    candidate = _valid_candidate(
        catalog_refs=[{"catalog_id": "table:sys_query_log", "catalog_version": "logistics_nl2sql_catalog.v1"}],
        plan={"tables": ["sys_query_log"]},
    )

    result = _validate(candidate, catalog=polluted_catalog)

    assert result.ok is False
    assert "sqlplan_table_not_allowed::sys_query_log" in result.error_codes


def test_sql_plan_validator_rejects_polluted_injected_catalog_domain() -> None:
    """注入 catalog 的顶层 domain 也必须在 M3 validator 复核，不能只依赖 loader。"""

    catalog = LogisticsSemanticCatalogLoader().load()
    polluted_catalog = catalog.model_copy(update={"domain": "finance"})

    result = _validate(_valid_candidate(), catalog=polluted_catalog)

    assert result.ok is False
    assert "sqlplan_catalog_domain_invalid::finance" in result.error_codes


def test_sql_plan_validator_rejects_tonnage_substitution_to_mw() -> None:
    """吨数/运输吨位当前不支持，不能被 candidate 替换为 MW 发运量指标。"""

    candidate = _valid_candidate(plan={"requested_unit": "吨"})

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_unsupported_unit::吨" in result.error_codes


def test_sql_plan_validator_requires_candidate_requested_unit() -> None:
    """candidate 必须显式携带用户请求单位，不能省略后把吨数问题伪装成 MW。"""

    candidate = _valid_candidate(plan={"requested_unit": None})

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_requested_unit_required" in result.error_codes


def test_sql_plan_validator_requires_join_coverage_for_multi_table_plan() -> None:
    """多表 plan 必须有受控 join 覆盖，不能把后续 renderer 推向隐式笛卡尔关系。"""

    candidate = _valid_candidate(
        catalog_refs=[
            {"catalog_id": "table:dwd_logistics_hist_shipment_detail", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "dimension:city", "catalog_version": "logistics_nl2sql_catalog.v1"},
        ],
        plan={
            "tables": ["dws_logistics_detail_union", "dwd_logistics_hist_shipment_detail"],
            "joins": [],
            "filters": [_filter("city", "=", ["广州"]), _filter("biz_year", "in", [2025])],
            "explicit_year_buckets": [2025],
        },
    )

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_join_required_for_multi_table_plan" in result.error_codes


def test_sql_plan_validator_preserves_explicit_year_buckets() -> None:
    """显式多年对比必须保留完整年份桶，不能静默丢失 0 行年份。"""

    candidate = _valid_candidate(
        plan={
            "filters": [_filter("biz_year", "in", [2023, 2024, 2025])],
            "explicit_year_buckets": [2023, 2025],
        }
    )

    result = _validate(candidate)

    assert result.ok is False
    assert "sqlplan_explicit_year_buckets_mismatch::2023,2024,2025::2023,2025" in result.error_codes


def test_sql_plan_validator_requires_m2_catalog_refs_and_matching_version() -> None:
    """SQLPlan 只能引用 M2 召回返回的 catalog_id/catalog_version，并由后端回查 canonical catalog。"""

    missing_ref = _valid_candidate(plan={"metrics": ["invented_metric"]})
    stale_version = _valid_candidate(
        catalog_refs=[{"catalog_id": "metric:shipment_mw", "catalog_version": "old_catalog"}]
    )

    missing_result = _validate(missing_ref)
    stale_result = _validate(stale_version)

    assert missing_result.ok is False
    assert "sqlplan_metric_not_found::invented_metric" in missing_result.error_codes
    assert stale_result.ok is False
    assert "sqlplan_catalog_version_mismatch::metric:shipment_mw::old_catalog" in stale_result.error_codes


def _validate(candidate: dict, *, catalog=None):
    """使用真实 catalog 或测试传入的污染 catalog 执行 SQLPlan 校验。"""

    return LogisticsSqlPlanValidator(catalog=catalog or LogisticsSemanticCatalogLoader().load()).validate(candidate)


def _filter(dimension: str, operator: str, values: list) -> dict:
    """生成测试用过滤条件。"""

    return {"dimension": dimension, "operator": operator, "values": values}


def _valid_candidate(**overrides) -> dict:
    """生成一份合法的 SQLPlan candidate，并允许测试按需覆盖。"""

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

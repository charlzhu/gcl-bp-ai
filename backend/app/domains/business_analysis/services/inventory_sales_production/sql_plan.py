from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from backend.app.domains.business_analysis.schemas.inventory_sales_production_query import (
    InventorySalesProductionQueryKey,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.semantic_catalog import (
    ISP_ALLOWED_READ_TABLES,
    ISP_BLOCKED_ALLOWED_COLUMN_PREFIXES,
    InventorySalesProductionCatalogDimension,
    InventorySalesProductionCatalogMetric,
    InventorySalesProductionCatalogTable,
    InventorySalesProductionSemanticCatalog,
    InventorySalesProductionSemanticCatalogLoader,
)

FORBIDDEN_SQLPLAN_KEYS = {"raw_sql", "sql", "where", "having", "free_sql"}
SQL_LIKE_STRING_RE = re.compile(
    r"\b(select|insert|update|delete|drop|alter|truncate|create|merge|call|copy|from|where|having|explain|union)\b"
    r"|\b(or|and)\s+1\s*=\s*1\b|(?<![\w.])1\s*=\s*1(?![\w.])|--|/\*|\*/|;\s*\w+"
    r"|\b[a-z_][a-z0-9_.]*\s*\([^)]*\)",
    re.IGNORECASE,
)
# 内部日志/审计表标识属于治理和追溯资产，不能作为 NL2SQL 业务候选值回显。
INTERNAL_IDENTIFIER_RE = re.compile(
    r"\b(?:[a-z0-9_]*_)?(?:query_log|audit_log|sys_query_log)(?:_[a-z0-9_]+)?\b",
    re.IGNORECASE,
)
SAFE_FILTER_VALUE_TYPES = (str, int, float, bool)
ISP_SQLPLAN_CANDIDATE_SCHEMA_VERSION = "business_analysis_inventory_sales_production_sqlplan_candidate.v1"
REQUIRED_ISP_SEMANTIC_CATALOG_VERSION = "business_analysis_inventory_sales_production_catalog.v1"
DEFAULT_ISP_YEARS = [2023, 2024, 2025, 2026]
DEFAULT_ISP_MAX_PUBLISHED_MONTH_BY_YEAR = {2023: 12, 2024: 12, 2025: 12, 2026: 4}
ALLOWED_YEAR_FILTER_OPERATORS = {"=", "in", "between"}
ALLOWED_MONTH_FILTER_OPERATORS = {"=", "in"}
ALLOWED_BUSINESS_FLAGS = {"explicit_invoice", "include_internal"}
UNSUPPORTED_TIME_RULES = {
    "year_over_year": "sqlplan_time_comparison_not_supported::year_over_year",
    "month_over_month": "sqlplan_time_comparison_not_supported::month_over_month",
    "yoy": "sqlplan_time_comparison_not_supported::yoy",
    "mom": "sqlplan_time_comparison_not_supported::mom",
    "arbitrary_month_range": "sqlplan_period_type_not_supported::month_range",
    "unpublished_month": "sqlplan_unpublished_month_blocks_sql_direct",
}


class InventorySalesProductionSqlPlanCatalogRef(BaseModel):
    """M5 Semantic Catalog 召回命中的受控引用。"""

    model_config = ConfigDict(extra="forbid")

    catalog_id: str
    catalog_version: str


class InventorySalesProductionSqlPlanFilter(BaseModel):
    """产销存 SQLPlan 中的受控过滤条件，不承载 SQL 片段。"""

    model_config = ConfigDict(extra="forbid")

    dimension: str
    operator: Literal["=", "in", "between", ">=", "<=", "like"] = "="
    values: list[Any] = Field(default_factory=list)
    source: str | None = None


class InventorySalesProductionSqlPlanOrderBy(BaseModel):
    """产销存 SQLPlan 中的受控排序条件。"""

    model_config = ConfigDict(extra="forbid")

    metric: str | None = None
    dimension: str | None = None
    direction: Literal["asc", "desc"] = "desc"

    @model_validator(mode="after")
    def _require_one_reference(self) -> "InventorySalesProductionSqlPlanOrderBy":
        """排序必须且只能引用一个 catalog 对象。"""

        if bool(self.metric) == bool(self.dimension):
            raise ValueError("sqlplan_order_by_reference_required")
        return self


class InventorySalesProductionSqlPlan(BaseModel):
    """M5 产销存 NL2SQL shadow 阶段的受控 SQLPlan 结构。

    业务逻辑：
        本对象只表达 query_key、目录表、指标、维度、过滤、分组、排序、期间和聚合策略；
        它不是 SQL，也不会连接或查询数据库。后续 renderer/executor 只能消费校验通过的结构。
    """

    model_config = ConfigDict(extra="forbid")

    query_key: InventorySalesProductionQueryKey
    domain: Literal["business_analysis"] = "business_analysis"
    sub_domain: Literal["inventory_sales_production"] = "inventory_sales_production"
    tables: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: list[InventorySalesProductionSqlPlanFilter] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    order_by: list[InventorySalesProductionSqlPlanOrderBy] = Field(default_factory=list)
    business_rules: list[str] = Field(default_factory=list)
    business_flags: dict[str, Any] = Field(default_factory=dict)
    period_type: Literal["month", "quarter", "year", "ytd", "month_range"] = "year"
    year: int
    month: int | None = None
    quarter: int | None = None
    start_month: int | None = None
    end_month: int | None = None
    calculation_policy: str | None = None
    limit: int | None = None


class InventorySalesProductionSqlPlanCandidate(BaseModel):
    """LLM 或上游规划器产出的产销存 SQLPlan candidate。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = ISP_SQLPLAN_CANDIDATE_SCHEMA_VERSION
    domain: Literal["business_analysis"] = "business_analysis"
    sub_domain: Literal["inventory_sales_production"] = "inventory_sales_production"
    strategy: Literal["sql_direct", "clarify", "unsupported"] = "sql_direct"
    catalog_version: str
    catalog_refs: list[InventorySalesProductionSqlPlanCatalogRef] = Field(default_factory=list)
    plan: InventorySalesProductionSqlPlan
    clarification_questions: list[str] = Field(default_factory=list)
    unsupported_reason: str | None = None
    confidence: float | None = None


class InventorySalesProductionSqlPlanValidationResult(BaseModel):
    """产销存 SQLPlan validator 的确定性返回。"""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    normalized_plan: InventorySalesProductionSqlPlan | None = None
    errors: list[str] = Field(default_factory=list)

    @property
    def error_codes(self) -> list[str]:
        """返回稳定错误码列表，方便单测和 shadow 审计记录。"""

        return list(self.errors)


class InventorySalesProductionSqlPlanValidator:
    """产销存 NL2SQL SQLPlan 确定性校验器。

    业务逻辑：
        1. 只接受 business_analysis / inventory_sales_production 域；
        2. 先递归扫描 raw candidate，阻断 raw_sql/sql/where/free_sql 与 SQL-like 字符串；
        3. 用 catalog_id/catalog_version 回查 canonical Semantic Catalog；
        4. 复核表、指标、维度、过滤、分组、排序、期间和聚合策略边界；
        5. 任何错误均 fail-closed，不返回 normalized_plan。
    """

    def __init__(self, catalog: InventorySalesProductionSemanticCatalog | None = None) -> None:
        """初始化 validator，可在单测中注入污染 catalog 验证二次校验。"""

        self.catalog = catalog or InventorySalesProductionSemanticCatalogLoader().load()
        self._strict_allowed_table_names = set(ISP_ALLOWED_READ_TABLES)
        self._catalog_boundary_errors = self._validate_catalog_boundary()
        self._tables = {table.table_name: table for table in self.catalog.tables}
        self._metrics = {metric.metric_id: metric for metric in self.catalog.metrics}
        self._dimensions = {dimension.dimension_id: dimension for dimension in self.catalog.dimensions}
        self._column_index = {
            table.table_name: {column.name for column in table.columns}
            for table in self.catalog.allowed_tables()
            if self._is_strict_allowed_table(table)
        }
        self._allowed_catalog_ids = self._build_allowed_catalog_ids()

    def validate(
        self,
        candidate_payload: InventorySalesProductionSqlPlanCandidate | dict[str, Any],
    ) -> InventorySalesProductionSqlPlanValidationResult:
        """校验 SQLPlan candidate 并返回 fail-closed 结果。"""

        raw_payload = (
            candidate_payload.model_dump(mode="python")
            if isinstance(candidate_payload, BaseModel)
            else candidate_payload
        )
        errors = _dedupe_errors([*self._catalog_boundary_errors, *_scan_forbidden_sql_payload(raw_payload)])
        try:
            candidate = InventorySalesProductionSqlPlanCandidate.model_validate(raw_payload)
        except ValidationError as exc:
            errors.extend(_schema_error_codes(exc))
            # raw_sql/sql/where 等字段必须保留 schema 错误；但为了审计能同时看到
            # plan 内的白名单越界，移除已被扫描器标记的 forbidden keys 后再做一次
            # 只用于错误收集的解析。若仍不合法，则 fail-closed 返回已有错误。
            try:
                candidate = InventorySalesProductionSqlPlanCandidate.model_validate(
                    _strip_forbidden_sqlplan_keys(raw_payload)
                )
            except ValidationError:
                return self._result(errors)

        errors.extend(self._validate_candidate_boundary(candidate))
        valid_ref_ids = self._validate_catalog_refs(candidate.catalog_refs, errors)
        plan = candidate.plan
        errors.extend(self._validate_tables(plan, valid_ref_ids))
        errors.extend(self._validate_metrics(plan, valid_ref_ids))
        errors.extend(self._validate_dimensions(plan, valid_ref_ids))
        errors.extend(self._validate_filters(plan, valid_ref_ids))
        errors.extend(self._validate_group_by(plan, valid_ref_ids))
        errors.extend(self._validate_order_by(plan, valid_ref_ids))
        errors.extend(self._validate_business_flags(plan))
        errors.extend(self._validate_query_key_support(plan))
        errors.extend(self._validate_period(plan))
        errors.extend(self._validate_calculation_policy(plan))
        errors.extend(self._validate_limit(plan))
        return self._result(errors, normalized_plan=plan)

    def _validate_catalog_boundary(self) -> list[str]:
        """在 validator 层复核 canonical catalog 边界，防止污染 catalog 绕过 loader。"""

        errors: list[str] = []
        if self.catalog.catalog_version != REQUIRED_ISP_SEMANTIC_CATALOG_VERSION:
            errors.append(
                "sqlplan_catalog_version_invalid::"
                f"{_safe_error_value(self.catalog.catalog_version)}::{REQUIRED_ISP_SEMANTIC_CATALOG_VERSION}"
            )
        if self.catalog.domain != "business_analysis":
            errors.append(f"sqlplan_catalog_domain_invalid::{_safe_error_value(self.catalog.domain)}")
        if self.catalog.sub_domain != "inventory_sales_production":
            errors.append(f"sqlplan_catalog_sub_domain_invalid::{_safe_error_value(self.catalog.sub_domain)}")
        seen_tables: set[str] = set()
        for table in self.catalog.tables:
            if table.table_name in seen_tables:
                errors.append(f"sqlplan_catalog_table_duplicate::{_safe_error_value(table.table_name)}")
            seen_tables.add(table.table_name)
            if not self._is_strict_allowed_table(table):
                errors.append(f"sqlplan_catalog_table_not_allowed::{_safe_error_value(table.table_name)}")
                continue
            errors.extend(self._validate_table_columns(table))
        return errors

    def _is_strict_allowed_table(self, table: InventorySalesProductionCatalogTable) -> bool:
        """表必须同时满足硬白名单、经营分析产销存域、中间库和 allowed_read。"""

        return (
            table.allowed_read
            and table.table_name in self._strict_allowed_table_names
            and table.domain == "business_analysis"
            and table.sub_domain == "inventory_sales_production"
            and table.source_system == "middle_db"
        )

    @staticmethod
    def _validate_table_columns(table: InventorySalesProductionCatalogTable) -> list[str]:
        """复核 allowed_read 表不暴露来源、原始行或链路追踪字段。"""

        errors: list[str] = []
        for column in table.columns:
            normalized_name = column.name.strip().lower()
            blocked_by_name = normalized_name.startswith(ISP_BLOCKED_ALLOWED_COLUMN_PREFIXES)
            blocked_by_role = str(column.semantic_role or "").strip().lower() == "trace"
            if blocked_by_name or blocked_by_role:
                errors.append(f"sqlplan_table_column_not_allowed::{_safe_error_value(f'{table.table_name}.{column.name}')}")
        return errors

    def _validate_candidate_boundary(self, candidate: InventorySalesProductionSqlPlanCandidate) -> list[str]:
        """校验 candidate 顶层边界和阻断状态。"""

        errors: list[str] = []
        if candidate.schema_version != ISP_SQLPLAN_CANDIDATE_SCHEMA_VERSION:
            errors.append(f"sqlplan_schema_version_mismatch::{_safe_error_value(candidate.schema_version)}")
        if candidate.catalog_version != REQUIRED_ISP_SEMANTIC_CATALOG_VERSION:
            errors.append(
                "sqlplan_candidate_catalog_version_mismatch::"
                f"{_safe_error_value(candidate.catalog_version)}::{REQUIRED_ISP_SEMANTIC_CATALOG_VERSION}"
            )
        if candidate.strategy == "clarify" or candidate.clarification_questions:
            errors.append("sqlplan_blocked_by_clarification")
        if candidate.strategy == "unsupported" or candidate.unsupported_reason:
            errors.append("sqlplan_blocked_by_unsupported")
        return errors

    def _validate_catalog_refs(
        self,
        refs: list[InventorySalesProductionSqlPlanCatalogRef],
        errors: list[str],
    ) -> set[str]:
        """校验 catalog_id/catalog_version，并返回版本匹配引用集合。"""

        valid_ref_ids: set[str] = set()
        seen: set[tuple[str, str]] = set()
        for ref in refs:
            key = (ref.catalog_id, ref.catalog_version)
            if key in seen:
                continue
            seen.add(key)
            if ref.catalog_id not in self._allowed_catalog_ids:
                errors.append(f"sqlplan_catalog_id_not_found::{_safe_error_value(ref.catalog_id)}")
                continue
            if ref.catalog_version != REQUIRED_ISP_SEMANTIC_CATALOG_VERSION:
                errors.append(
                    f"sqlplan_catalog_version_mismatch::{_safe_error_value(ref.catalog_id)}::"
                    f"{_safe_error_value(ref.catalog_version)}"
                )
                continue
            valid_ref_ids.add(ref.catalog_id)
        return valid_ref_ids

    def _validate_tables(self, plan: InventorySalesProductionSqlPlan, valid_ref_ids: set[str]) -> list[str]:
        """校验 plan.tables 只引用可读白名单表。"""

        errors: list[str] = []
        if not plan.tables:
            errors.append("sqlplan_tables_required")
        for table_name in plan.tables:
            table = self._tables.get(table_name)
            if table_name not in self._strict_allowed_table_names or table is None or not self._is_strict_allowed_table(table):
                errors.append(f"sqlplan_table_not_allowed::{_safe_error_value(table_name)}")
                continue
            self._require_ref(f"table:{table_name}", valid_ref_ids, errors)
        return errors

    def _validate_metrics(self, plan: InventorySalesProductionSqlPlan, valid_ref_ids: set[str]) -> list[str]:
        """校验指标存在、来源表和依赖字段均在 catalog 中。"""

        errors: list[str] = []
        for metric_id in plan.metrics:
            metric = self._metrics.get(metric_id)
            if metric is None:
                errors.append(f"sqlplan_metric_not_found::{_safe_error_value(metric_id)}")
                continue
            self._require_ref(f"metric:{metric_id}", valid_ref_ids, errors)
            errors.extend(self._validate_metric_catalog_entry(metric, plan_tables=set(plan.tables)))
        return errors

    def _validate_dimensions(self, plan: InventorySalesProductionSqlPlan, valid_ref_ids: set[str]) -> list[str]:
        """校验输出维度存在且表范围匹配。"""

        errors: list[str] = []
        for dimension_id in plan.dimensions:
            dimension = self._dimensions.get(dimension_id)
            if dimension is None:
                errors.append(f"sqlplan_dimension_not_found::{_safe_error_value(dimension_id)}")
                continue
            self._require_ref(f"dimension:{dimension_id}", valid_ref_ids, errors)
            errors.extend(self._validate_dimension_catalog_entry(dimension, plan_tables=set(plan.tables)))
        return errors

    def _validate_filters(self, plan: InventorySalesProductionSqlPlan, valid_ref_ids: set[str]) -> list[str]:
        """校验过滤条件维度存在、值为安全标量且表范围匹配。"""

        errors: list[str] = []
        for item in plan.filters:
            for value in item.values:
                if value is None or not isinstance(value, SAFE_FILTER_VALUE_TYPES):
                    errors.append(f"sqlplan_filter_value_not_scalar::{_safe_error_value(item.dimension)}")
                    break
            dimension = self._dimensions.get(item.dimension)
            if dimension is None:
                errors.append(f"sqlplan_dimension_not_found::{_safe_error_value(item.dimension)}")
                continue
            self._require_ref(f"dimension:{item.dimension}", valid_ref_ids, errors)
            errors.extend(self._validate_dimension_catalog_entry(dimension, plan_tables=set(plan.tables)))
        return errors

    def _validate_group_by(self, plan: InventorySalesProductionSqlPlan, valid_ref_ids: set[str]) -> list[str]:
        """校验 group_by 只能引用 catalog 维度。"""

        errors: list[str] = []
        for dimension_id in plan.group_by:
            dimension = self._dimensions.get(dimension_id)
            if dimension is None:
                errors.append(f"sqlplan_group_by_dimension_not_found::{_safe_error_value(dimension_id)}")
                continue
            self._require_ref(f"dimension:{dimension_id}", valid_ref_ids, errors)
            errors.extend(self._validate_dimension_catalog_entry(dimension, plan_tables=set(plan.tables)))
        return errors

    def _validate_order_by(self, plan: InventorySalesProductionSqlPlan, valid_ref_ids: set[str]) -> list[str]:
        """校验 order_by 只能引用 catalog 指标或维度。"""

        errors: list[str] = []
        for item in plan.order_by:
            if item.metric:
                metric = self._metrics.get(item.metric)
                if metric is None:
                    errors.append(f"sqlplan_order_by_reference_not_found::{_safe_error_value(item.metric)}")
                    continue
                self._require_ref(f"metric:{item.metric}", valid_ref_ids, errors)
                errors.extend(self._validate_metric_catalog_entry(metric, plan_tables=set(plan.tables)))
            elif item.dimension:
                dimension = self._dimensions.get(item.dimension)
                if dimension is None:
                    errors.append(f"sqlplan_order_by_reference_not_found::{_safe_error_value(item.dimension)}")
                    continue
                self._require_ref(f"dimension:{item.dimension}", valid_ref_ids, errors)
                errors.extend(self._validate_dimension_catalog_entry(dimension, plan_tables=set(plan.tables)))
        return errors

    @staticmethod
    def _validate_business_flags(plan: InventorySalesProductionSqlPlan) -> list[str]:
        """校验 business_flags 仅包含已知控制开关，并阻断同比/环比等时间比较能力。"""

        errors: list[str] = []
        for flag_name in plan.business_flags:
            blocked_error = UNSUPPORTED_TIME_RULES.get(flag_name)
            if blocked_error:
                errors.append(blocked_error)
            if flag_name not in ALLOWED_BUSINESS_FLAGS:
                errors.append(f"sqlplan_business_flag_not_allowed::{_safe_error_value(flag_name)}")
        return errors

    def _validate_query_key_support(self, plan: InventorySalesProductionSqlPlan) -> list[str]:
        """复用 Semantic Catalog QueryPlan support gate 校验能力边界。"""

        # group_by 同样会影响 renderer 输出维度，必须纳入 catalog query_key 能力门禁，
        # 避免 summary 类 query_key 把拆分维度藏在 group_by 中绕过校验。
        support_dimensions = list(dict.fromkeys([*plan.dimensions, *plan.group_by]))
        try:
            self.catalog.validate_query_plan_support(
                query_key=plan.query_key,
                metrics=plan.metrics,
                dimensions=support_dimensions,
                filters=plan.business_flags,
            )
        except ValueError as exc:
            return [f"sqlplan_catalog_support_error::{_safe_error_value(str(exc))}"]
        return []

    def _validate_period(self, plan: InventorySalesProductionSqlPlan) -> list[str]:
        """校验年份、月份、季度和当前不支持的时间边界。"""

        errors: list[str] = []
        if plan.year not in DEFAULT_ISP_YEARS:
            errors.append(f"sqlplan_year_out_of_scope::{plan.year}")
        for rule_id in plan.business_rules:
            blocked_error = UNSUPPORTED_TIME_RULES.get(rule_id)
            if blocked_error:
                errors.append(blocked_error)
        if plan.period_type == "month_range":
            errors.append("sqlplan_period_type_not_supported::month_range")
        elif plan.start_month is not None or plan.end_month is not None:
            errors.append(f"sqlplan_period_start_end_range_not_supported::{plan.period_type}")
        if plan.period_type == "month":
            if plan.month is None:
                errors.append("sqlplan_month_required")
        if plan.month is not None:
            if plan.month < 1 or plan.month > 12:
                errors.append(f"sqlplan_month_out_of_range::{plan.month}")
            else:
                errors.extend(self._validate_published_month_boundary(plan.year, plan.month))
            if plan.period_type != "month":
                errors.append(f"sqlplan_period_month_not_allowed::{plan.period_type}")
        if plan.period_type == "quarter":
            if plan.quarter is None:
                errors.append("sqlplan_quarter_required")
        if plan.quarter is not None:
            if plan.quarter not in {1, 2, 3, 4}:
                errors.append(f"sqlplan_quarter_out_of_range::{plan.quarter}")
            else:
                quarter_end_month = plan.quarter * 3
                errors.extend(self._validate_published_month_boundary(plan.year, quarter_end_month))
            if plan.period_type != "quarter":
                errors.append(f"sqlplan_period_quarter_not_allowed::{plan.period_type}")
        for attr_name in ("start_month", "end_month"):
            value = getattr(plan, attr_name)
            if value is not None and (value < 1 or value > 12):
                errors.append(f"sqlplan_{attr_name}_out_of_range::{value}")
        if plan.start_month is not None and plan.end_month is not None and plan.start_month > plan.end_month:
            errors.append("sqlplan_period_start_after_end")
        errors.extend(self._validate_year_filter_shapes(plan.filters))
        errors.extend(self._validate_month_filter_shapes(plan.filters, plan.year))
        return errors

    @staticmethod
    def _validate_published_month_boundary(year: int, requested_month: int) -> list[str]:
        """校验显式月份/季度没有越过当前产销存已发布月份边界。"""

        max_published_month = DEFAULT_ISP_MAX_PUBLISHED_MONTH_BY_YEAR.get(year)
        if max_published_month is not None and requested_month > max_published_month:
            return [f"sqlplan_unpublished_month_blocks_sql_direct::{year}::{requested_month}::{max_published_month}"]
        return []

    @staticmethod
    def _validate_year_filter_shapes(filters: list[InventorySalesProductionSqlPlanFilter]) -> list[str]:
        """校验 business_year 过滤形态，防止半开条件和越界年份进入 renderer。"""

        errors: list[str] = []
        min_year = min(DEFAULT_ISP_YEARS)
        max_year = max(DEFAULT_ISP_YEARS)
        for filter_index, item in enumerate(filters):
            if item.dimension != "business_year":
                continue
            if item.operator not in ALLOWED_YEAR_FILTER_OPERATORS:
                errors.append(f"sqlplan_year_filter_operator_unsupported::{item.operator}")
                continue
            parsed_years: list[int] = []
            has_invalid_year_value = False
            for value_index, value in enumerate(item.values):
                parsed_year = _parse_year_filter_value(value)
                if parsed_year is None:
                    errors.append(f"sqlplan_year_value_invalid::plan.filters[{filter_index}].values[{value_index}]")
                    has_invalid_year_value = True
                else:
                    parsed_years.append(parsed_year)
            if has_invalid_year_value:
                continue
            if item.operator == "between":
                if len(parsed_years) != 2:
                    errors.append("sqlplan_year_between_requires_two_values")
                    continue
                start, end = sorted(parsed_years)
                if start < min_year or end > max_year:
                    errors.append(f"sqlplan_year_between_range_out_of_scope::{start}::{end}")
            for year in parsed_years:
                if year not in DEFAULT_ISP_YEARS:
                    errors.append(f"sqlplan_year_out_of_scope::{year}")
        return errors

    def _validate_month_filter_shapes(
        self,
        filters: list[InventorySalesProductionSqlPlanFilter],
        year: int,
    ) -> list[str]:
        """校验 business_month 过滤形态，防止月份条件绕过 period 字段的发布边界。"""

        errors: list[str] = []
        for filter_index, item in enumerate(filters):
            if item.dimension != "business_month":
                continue
            if item.operator not in ALLOWED_MONTH_FILTER_OPERATORS:
                errors.append(f"sqlplan_month_filter_operator_unsupported::{_safe_error_value(item.operator)}")
                continue
            parsed_months: list[int] = []
            has_invalid_month_value = False
            for value_index, value in enumerate(item.values):
                parsed_month = _parse_month_filter_value(value)
                if parsed_month is None:
                    errors.append(f"sqlplan_month_value_invalid::plan.filters[{filter_index}].values[{value_index}]")
                    has_invalid_month_value = True
                else:
                    parsed_months.append(parsed_month)
            if has_invalid_month_value:
                continue
            for month in parsed_months:
                if month < 1 or month > 12:
                    errors.append(f"sqlplan_month_value_out_of_range::{month}")
                    continue
                errors.extend(self._validate_published_month_boundary(year, month))
        return errors

    def _validate_calculation_policy(self, plan: InventorySalesProductionSqlPlan) -> list[str]:
        """校验聚合策略遵守产销存业务口径。"""

        errors: list[str] = []
        if not plan.calculation_policy:
            return errors
        for metric_id in plan.metrics:
            metric = self._metrics.get(metric_id)
            if metric is None:
                continue
            policy = plan.calculation_policy
            if metric.aggregation == "period_end" and policy == "sum":
                errors.append(f"sqlplan_period_end_metric_cannot_sum::{metric.metric_id}")
                continue
            if metric.aggregation == "period_end" and policy not in {"period_end", metric.aggregation}:
                errors.append(
                    f"sqlplan_metric_calculation_policy_mismatch::{metric.metric_id}::"
                    f"{_safe_error_value(policy)}"
                )
                continue
            if plan.query_key == "ba_isp_budget_achievement" and policy == "calculated_ratio":
                continue
            if metric.aggregation == "calculated_ratio" and policy != "calculated_ratio":
                errors.append(
                    f"sqlplan_metric_calculation_policy_mismatch::{metric.metric_id}::"
                    f"{_safe_error_value(policy)}"
                )
                continue
            if metric.aggregation not in {"period_end", "calculated_ratio"} and policy not in {"sum", metric.aggregation}:
                errors.append(
                    f"sqlplan_metric_calculation_policy_mismatch::{metric.metric_id}::"
                    f"{_safe_error_value(policy)}"
                )
        return errors

    @staticmethod
    def _validate_limit(plan: InventorySalesProductionSqlPlan) -> list[str]:
        """校验 limit 的安全范围。"""

        if plan.limit is None:
            return []
        if plan.limit < 1 or plan.limit > 500:
            return [f"sqlplan_limit_out_of_range::{plan.limit}"]
        return []

    def _validate_metric_catalog_entry(
        self,
        metric: InventorySalesProductionCatalogMetric,
        *,
        plan_tables: set[str],
    ) -> list[str]:
        """二次校验指标 catalog 条目，避免污染 catalog 绕过 M5。"""

        errors: list[str] = []
        if metric.support_status != "supported":
            errors.append(f"sqlplan_metric_not_supported::{_safe_error_value(metric.metric_id)}")
        if not metric.table:
            errors.append(f"sqlplan_metric_table_required::{_safe_error_value(metric.metric_id)}")
            return errors
        if metric.table not in self._strict_allowed_table_names:
            errors.append(
                f"sqlplan_metric_table_not_allowed::{_safe_error_value(metric.metric_id)}::"
                f"{_safe_error_value(metric.table)}"
            )
            return errors
        if metric.table not in plan_tables:
            errors.append(
                f"sqlplan_metric_table_not_in_plan::{_safe_error_value(metric.metric_id)}::"
                f"{_safe_error_value(metric.table)}"
            )
        if not metric.source_columns:
            errors.append(f"sqlplan_metric_source_columns_required::{_safe_error_value(metric.metric_id)}")
            return errors
        available_columns = self._column_index.get(metric.table, set())
        for column_name in metric.source_columns:
            if column_name not in available_columns:
                errors.append(
                    f"sqlplan_metric_column_not_allowed::{_safe_error_value(metric.metric_id)}::"
                    f"{_safe_error_value(f'{metric.table}.{column_name}')}"
                )
        for dependency in metric.depends_on_metrics:
            if dependency == metric.metric_id or dependency not in self._metrics:
                errors.append(
                    f"sqlplan_metric_dependency_not_allowed::{_safe_error_value(metric.metric_id)}::"
                    f"{_safe_error_value(dependency)}"
                )
        return errors

    def _validate_dimension_catalog_entry(
        self,
        dimension: InventorySalesProductionCatalogDimension,
        *,
        plan_tables: set[str],
    ) -> list[str]:
        """二次校验维度 catalog 条目和当前 plan 表范围。"""

        errors: list[str] = []
        if dimension.support_status != "supported":
            errors.append(f"sqlplan_dimension_not_supported::{_safe_error_value(dimension.dimension_id)}")
        if not dimension.table:
            errors.append(f"sqlplan_dimension_table_required::{_safe_error_value(dimension.dimension_id)}")
            return errors
        if dimension.table not in self._strict_allowed_table_names:
            errors.append(
                f"sqlplan_dimension_table_not_allowed::{_safe_error_value(dimension.dimension_id)}::"
                f"{_safe_error_value(dimension.table)}"
            )
            return errors
        if dimension.table not in plan_tables:
            errors.append(
                f"sqlplan_dimension_table_not_in_plan::{_safe_error_value(dimension.dimension_id)}::"
                f"{_safe_error_value(dimension.table)}"
            )
        available_columns = self._column_index.get(dimension.table, set())
        if dimension.column not in available_columns:
            errors.append(
                f"sqlplan_dimension_column_not_allowed::{_safe_error_value(dimension.dimension_id)}::"
                f"{_safe_error_value(f'{dimension.table}.{dimension.column}')}"
            )
        return errors

    def _build_allowed_catalog_ids(self) -> set[str]:
        """从 canonical catalog 构造允许被 M5 引用的 ID 集合。"""

        ids: set[str] = set()
        ids.update(
            f"table:{table.table_name}"
            for table in self.catalog.allowed_tables()
            if self._is_strict_allowed_table(table)
        )
        ids.update(f"metric:{metric.metric_id}" for metric in self.catalog.metrics)
        ids.update(f"dimension:{dimension.dimension_id}" for dimension in self.catalog.dimensions)
        return ids

    @staticmethod
    def _require_ref(catalog_id: str, valid_ref_ids: set[str], errors: list[str]) -> None:
        """要求 plan 中每个引用都来自 M5 catalog_refs。"""

        if catalog_id not in valid_ref_ids:
            errors.append(f"sqlplan_missing_catalog_ref::{_safe_error_value(catalog_id)}")

    @staticmethod
    def _result(
        errors: list[str],
        *,
        normalized_plan: InventorySalesProductionSqlPlan | None = None,
    ) -> InventorySalesProductionSqlPlanValidationResult:
        """构造 fail-closed 结果对象。"""

        deduped = _dedupe_errors(errors)
        if deduped:
            return InventorySalesProductionSqlPlanValidationResult(ok=False, normalized_plan=None, errors=deduped)
        return InventorySalesProductionSqlPlanValidationResult(ok=True, normalized_plan=normalized_plan, errors=[])


def validate_inventory_sales_production_sql_plan_candidate(
    candidate_payload: InventorySalesProductionSqlPlanCandidate | dict[str, Any],
    *,
    catalog: InventorySalesProductionSemanticCatalog | None = None,
) -> InventorySalesProductionSqlPlanValidationResult:
    """函数式入口：校验产销存 SQLPlan candidate。"""

    return InventorySalesProductionSqlPlanValidator(catalog=catalog).validate(candidate_payload)


def _scan_forbidden_sql_payload(payload: Any, path: str = "root") -> list[str]:
    """递归扫描 candidate 原始 payload 中的 SQL 字段和 SQL-like 字符串。

    错误码只暴露字段路径，不回显 LLM 原文，避免把疑似 SQL/密钥片段写入审计或用户侧材料。
    """

    errors: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            normalized_key = key_text.strip().lower()
            child_path = _child_error_path(path, key_text)
            if normalized_key in FORBIDDEN_SQLPLAN_KEYS:
                errors.append(f"sqlplan_forbidden_key::{child_path}")
            if SQL_LIKE_STRING_RE.search(key_text) or INTERNAL_IDENTIFIER_RE.search(key_text):
                errors.append(f"sqlplan_forbidden_sql_string::{child_path}")
            errors.extend(_scan_forbidden_sql_payload(value, child_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            errors.extend(_scan_forbidden_sql_payload(value, f"{path}[{index}]"))
    elif isinstance(payload, str) and (SQL_LIKE_STRING_RE.search(payload) or INTERNAL_IDENTIFIER_RE.search(payload)):
        errors.append(f"sqlplan_forbidden_sql_string::{path}")
    return errors

def _child_error_path(parent_path: str, child_key: str) -> str:
    """拼接扫描器错误路径，动态字段名先脱敏后进入审计错误码。"""

    safe_child_key = _safe_error_value(child_key)
    if parent_path == "root":
        return safe_child_key
    return f"{parent_path}.{safe_child_key}"


def _strip_forbidden_sqlplan_keys(payload: Any) -> Any:
    """移除 raw_sql/sql/where/free_sql 等已被扫描器记录的字段，用于继续收集 plan 白名单错误。"""

    if isinstance(payload, dict):
        return {
            key: _strip_forbidden_sqlplan_keys(value)
            for key, value in payload.items()
            if str(key).strip().lower() not in FORBIDDEN_SQLPLAN_KEYS
        }
    if isinstance(payload, list):
        return [_strip_forbidden_sqlplan_keys(value) for value in payload]
    return payload


def _schema_error_codes(exc: ValidationError) -> list[str]:
    """把 Pydantic 校验错误转换为稳定错误码，动态路径片段统一脱敏。"""

    codes: list[str] = []
    for error in exc.errors():
        loc = _safe_error_path(error.get("loc", ()))
        error_type = str(error.get("type") or "invalid")
        codes.append(f"sqlplan_schema_invalid::{loc}::{error_type}")
    return codes


def _parse_year_filter_value(value: Any) -> int | None:
    """把 business_year 过滤值解析为整数年份；小数、布尔值和非年份字符串均 fail-closed。"""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        text = value.strip()
        if re.fullmatch(r"\d{4}", text):
            return int(text)
    return None


def _parse_month_filter_value(value: Any) -> int | None:
    """把 business_month 过滤值解析为整数月份；布尔、小数和复合日期字符串均 fail-closed。"""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        text = value.strip()
        if re.fullmatch(r"\d{1,2}", text):
            return int(text)
    return None


def _safe_error_path(parts: Any) -> str:
    """把 Pydantic loc 路径转换为安全错误路径，防止额外字段名泄露 SQL-like 载荷。"""

    safe_parts = [_safe_error_value(part) for part in parts]
    return ".".join(safe_parts) or "root"


def _safe_error_value(value: Any) -> str:
    """返回可进入审计错误码的安全片段，SQL-like 输入只保留 redacted 标记。

    业务逻辑：validator 的扫描器已经记录了危险字段路径；其他白名单/目录错误码只需要
    表达失败类别，不能二次回显 LLM 夹带的 SQL、日志表名或注入片段。
    """

    text = str(value).strip()
    if not text:
        return "redacted"
    if SQL_LIKE_STRING_RE.search(text) or INTERNAL_IDENTIFIER_RE.search(text):
        return "redacted"
    return text


def _dedupe_errors(errors: list[str]) -> list[str]:
    """保持顺序去重错误码，避免同一对象在多个路径重复报警。"""

    seen: set[str] = set()
    deduped: list[str] = []
    for error in errors:
        if error not in seen:
            seen.add(error)
            deduped.append(error)
    return deduped


__all__ = [
    "InventorySalesProductionSqlPlan",
    "InventorySalesProductionSqlPlanCandidate",
    "InventorySalesProductionSqlPlanCatalogRef",
    "InventorySalesProductionSqlPlanFilter",
    "InventorySalesProductionSqlPlanOrderBy",
    "InventorySalesProductionSqlPlanValidationResult",
    "InventorySalesProductionSqlPlanValidator",
    "validate_inventory_sales_production_sql_plan_candidate",
]

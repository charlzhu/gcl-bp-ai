from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from backend.app.domains.logistics.services.nl2sql.semantic_catalog import (
    LOGISTICS_NL2SQL_ALLOWED_READ_TABLES,
    LogisticsCatalogDimension,
    LogisticsCatalogJoin,
    LogisticsCatalogMetric,
    LogisticsCatalogRule,
    LogisticsCatalogTable,
    LogisticsSemanticCatalog,
    LogisticsSemanticCatalogLoader,
)

FORBIDDEN_SQLPLAN_KEYS = {"raw_sql", "sql", "where", "having", "free_sql"}
SQL_LIKE_STRING_RE = re.compile(
    r"\b(select|insert|update|delete|drop|alter|truncate|create|merge|call|copy|from|where|having|explain|union)\b"
    r"|\b(or|and)\s+1\s*=\s*1\b|(?<![\w.])1\s*=\s*1(?![\w.])|--|/\*|\*/|;\s*\w+",
    re.IGNORECASE,
)
SAFE_FILTER_VALUE_TYPES = (str, int, float, bool)
JOIN_ON_RE = re.compile(
    r"\s*([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*"
)
DEFAULT_LOGISTICS_YEARS = [2023, 2024, 2025, 2026]
ALLOWED_YEAR_FILTER_OPERATORS = {"=", "in", "between"}
UNSUPPORTED_TONNAGE_UNITS = {"吨", "吨数", "运输吨位", "重量", "吨位", "ton", "tons"}


class LogisticsSqlPlanCatalogRef(BaseModel):
    """M2 Semantic Catalog 召回命中的引用。

    参数：
        catalog_id: M2 召回返回的受控 catalog ID，例如 metric:shipment_mw。
        catalog_version: M2 命中时的 catalog 版本，必须与当前后端 canonical catalog 一致。
    返回：
        只用于回查 canonical catalog 的引用，不携带 SQL 或字段表达式。
    """

    model_config = ConfigDict(extra="forbid")

    catalog_id: str
    catalog_version: str


class LogisticsSqlPlanFilter(BaseModel):
    """SQLPlan 中的受控过滤条件。

    参数：
        dimension: 过滤维度 ID，必须存在于 Semantic Catalog。
        operator: 受控操作符，M3 只表达结构，不渲染 SQL。
        values: 过滤值列表，用户值后续由 M4 参数绑定消费。
        source: 过滤来源，例如 default_time_range 或 user_explicit。
    返回：
        结构化过滤条件；不允许 raw where/free SQL。
    """

    model_config = ConfigDict(extra="forbid")

    dimension: str
    operator: Literal["=", "in", "between", ">=", "<=", "like"] = "="
    values: list[Any] = Field(default_factory=list)
    source: str | None = None


class LogisticsSqlPlanOrderBy(BaseModel):
    """SQLPlan 中的受控排序条件。

    参数：
        metric: 按指标排序时的 metric_id。
        dimension: 按维度排序时的 dimension_id。
        direction: 排序方向。
    返回：
        受控排序条件；metric 与 dimension 必须且只能填写一个。
    """

    model_config = ConfigDict(extra="forbid")

    metric: str | None = None
    dimension: str | None = None
    direction: Literal["asc", "desc"] = "desc"

    @model_validator(mode="after")
    def _require_one_reference(self) -> "LogisticsSqlPlanOrderBy":
        """排序必须精确引用一个 catalog 对象。"""

        if bool(self.metric) == bool(self.dimension):
            raise ValueError("sqlplan_order_by_reference_required")
        return self


class LogisticsSqlPlan(BaseModel):
    """M3 阶段的受控 SQLPlan 结构。

    业务逻辑：
        本对象只描述表、指标、维度、过滤、分组、排序、规则和 limit 等结构；它不是 SQL、
        不包含 SQL 字符串，也不会连接或查询数据库。M4 之后的 renderer 只能消费校验通过的对象。
    """

    model_config = ConfigDict(extra="forbid")

    query_type: Literal["aggregate", "ranking", "detail"] = "aggregate"
    domain: Literal["logistics"] = "logistics"
    tables: list[str] = Field(default_factory=list)
    joins: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: list[LogisticsSqlPlanFilter] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    order_by: list[LogisticsSqlPlanOrderBy] = Field(default_factory=list)
    business_rules: list[str] = Field(default_factory=list)
    explicit_year_buckets: list[int] = Field(default_factory=list)
    requested_unit: str | None = None
    limit: int | None = None


class LogisticsSqlPlanCandidate(BaseModel):
    """LLM 或上游规划器产出的 SQLPlan candidate。

    业务逻辑：
        candidate 只是待校验输入。LLM 最多产生本结构；后端必须用 catalog_id/catalog_version
        回查 canonical catalog，再执行 fail-closed 校验，不能把 candidate 当成可执行命令。
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "logistics_sqlplan_candidate.v1"
    domain: Literal["logistics"] = "logistics"
    strategy: Literal["sql_direct", "clarify", "unsupported"] = "sql_direct"
    catalog_version: str
    catalog_refs: list[LogisticsSqlPlanCatalogRef] = Field(default_factory=list)
    plan: LogisticsSqlPlan
    clarification_questions: list[str] = Field(default_factory=list)
    unsupported_reason: str | None = None
    confidence: float | None = None


class LogisticsSqlPlanValidationResult(BaseModel):
    """SQLPlan validator 的确定性返回。"""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    normalized_plan: LogisticsSqlPlan | None = None
    errors: list[str] = Field(default_factory=list)

    @property
    def error_codes(self) -> list[str]:
        """返回稳定错误码列表，方便单测、审计和后续 shadow 记录。"""

        return list(self.errors)


class LogisticsSqlPlanValidator:
    """物流 NL2SQL M3 SQLPlan 确定性校验器。

    业务逻辑：
        1. 只接受 logistics 域、智能助手中间库 Semantic Catalog；
        2. 先扫描 raw candidate，阻断 raw_sql/sql/where/having/free_sql 和 SQL-like 字符串；
        3. 再用 M2 catalog_id/catalog_version 回查 canonical catalog；
        4. 最后校验表、指标、维度、Join、时间默认、吨数不支持和显式年份桶。
    """

    def __init__(self, catalog: LogisticsSemanticCatalog | None = None) -> None:
        """初始化 validator。

        参数：
            catalog: 可选 canonical Semantic Catalog；单测可注入污染对象验证二次校验。
        返回：
            无。
        """

        self.catalog = catalog or LogisticsSemanticCatalogLoader().load()
        self._strict_allowed_table_names = set(LOGISTICS_NL2SQL_ALLOWED_READ_TABLES)
        self._catalog_boundary_errors = self._validate_catalog_boundary()
        self._tables = {table.table_name: table for table in self.catalog.tables}
        self._metrics = {metric.metric_id: metric for metric in self.catalog.metrics}
        self._dimensions = {dimension.dimension_id: dimension for dimension in self.catalog.dimensions}
        self._joins = {join.join_id: join for join in self.catalog.joins}
        self._rules = {rule.rule_id: rule for rule in self.catalog.rules}
        self._column_index = {
            table.table_name: {column.name for column in table.columns}
            for table in self.catalog.allowed_tables()
            if self._is_strict_allowed_table(table)
        }
        self._allowed_catalog_ids = self._build_allowed_catalog_ids()

    def validate(self, candidate_payload: LogisticsSqlPlanCandidate | dict[str, Any]) -> LogisticsSqlPlanValidationResult:
        """校验 SQLPlan candidate 并返回 normalized plan。

        参数：
            candidate_payload: LLM 或上游规划器产出的 dict/Pydantic candidate。
        返回：
            ok=True 时附带 normalized_plan；任何错误都 fail-closed 且 normalized_plan=None。
        """

        raw_payload = (
            candidate_payload.model_dump(mode="python")
            if isinstance(candidate_payload, BaseModel)
            else candidate_payload
        )
        errors = _dedupe_errors([*self._catalog_boundary_errors, *_scan_forbidden_sql_payload(raw_payload)])
        try:
            candidate = LogisticsSqlPlanCandidate.model_validate(raw_payload)
        except ValidationError as exc:
            errors.extend(_schema_error_codes(exc))
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
        errors.extend(self._validate_joins(plan, valid_ref_ids))
        errors.extend(self._validate_business_rules(plan, valid_ref_ids))
        errors.extend(self._validate_limit(plan))

        return self._result(errors, normalized_plan=plan)

    def _validate_catalog_boundary(self) -> list[str]:
        """在 validator 层复核 canonical catalog 边界，防止注入污染 catalog 绕过 loader。"""

        errors: list[str] = []
        if self.catalog.domain != "logistics":
            errors.append(f"sqlplan_catalog_domain_invalid::{self.catalog.domain}")
        seen_tables: set[str] = set()
        for table in self.catalog.tables:
            if table.table_name in seen_tables:
                errors.append(f"sqlplan_catalog_table_duplicate::{table.table_name}")
            seen_tables.add(table.table_name)
            if not self._is_strict_allowed_table(table):
                errors.append(f"sqlplan_catalog_table_not_allowed::{table.table_name}")
        return errors

    def _is_strict_allowed_table(self, table: LogisticsCatalogTable) -> bool:
        """表必须同时满足硬白名单、物流域、中间库和 allowed_read。"""

        return (
            table.allowed_read
            and table.table_name in self._strict_allowed_table_names
            and table.domain == "logistics"
            and table.source_system == "middle_db"
        )

    def _validate_candidate_boundary(self, candidate: LogisticsSqlPlanCandidate) -> list[str]:
        """校验 candidate 顶层边界和阻断状态。"""

        errors: list[str] = []
        if candidate.schema_version != "logistics_sqlplan_candidate.v1":
            errors.append(f"sqlplan_schema_version_mismatch::{candidate.schema_version}")
        if candidate.catalog_version != self.catalog.catalog_version:
            errors.append(
                f"sqlplan_candidate_catalog_version_mismatch::{candidate.catalog_version}::{self.catalog.catalog_version}"
            )
        if candidate.strategy == "clarify" or candidate.clarification_questions:
            errors.append("sqlplan_blocked_by_clarification")
        if candidate.strategy == "unsupported" or candidate.unsupported_reason:
            errors.append("sqlplan_blocked_by_unsupported")
        return errors

    def _validate_catalog_refs(
        self,
        refs: list[LogisticsSqlPlanCatalogRef],
        errors: list[str],
    ) -> set[str]:
        """校验 M2 catalog_id/catalog_version，并返回版本匹配的引用集合。"""

        valid_ref_ids: set[str] = set()
        seen: set[tuple[str, str]] = set()
        for ref in refs:
            key = (ref.catalog_id, ref.catalog_version)
            if key in seen:
                continue
            seen.add(key)
            if ref.catalog_id not in self._allowed_catalog_ids:
                errors.append(f"sqlplan_catalog_id_not_found::{ref.catalog_id}")
                continue
            if ref.catalog_version != self.catalog.catalog_version:
                errors.append(f"sqlplan_catalog_version_mismatch::{ref.catalog_id}::{ref.catalog_version}")
                continue
            valid_ref_ids.add(ref.catalog_id)
        return valid_ref_ids

    def _validate_tables(self, plan: LogisticsSqlPlan, valid_ref_ids: set[str]) -> list[str]:
        """校验 plan.tables 只引用可读白名单表。"""

        errors: list[str] = []
        allowed = self._strict_allowed_table_names
        if not plan.tables:
            errors.append("sqlplan_tables_required")
        for table_name in plan.tables:
            table = self._tables.get(table_name)
            if table_name not in allowed or table is None or not self._is_strict_allowed_table(table):
                errors.append(f"sqlplan_table_not_allowed::{table_name}")
                continue
            if table.source_system != "middle_db":
                errors.append(f"sqlplan_table_source_system_invalid::{table_name}::{table.source_system}")
            if table.domain != "logistics":
                errors.append(f"sqlplan_table_domain_invalid::{table_name}::{table.domain}")
            self._require_ref(f"table:{table_name}", valid_ref_ids, errors)
        return errors

    def _validate_metrics(self, plan: LogisticsSqlPlan, valid_ref_ids: set[str]) -> list[str]:
        """校验指标存在、来源表和依赖字段均在 catalog 中。"""

        errors: list[str] = []
        for metric_id in plan.metrics:
            metric = self._metrics.get(metric_id)
            if metric is None:
                errors.append(f"sqlplan_metric_not_found::{metric_id}")
                continue
            self._require_ref(f"metric:{metric_id}", valid_ref_ids, errors)
            errors.extend(self._validate_metric_catalog_entry(metric, plan_tables=set(plan.tables)))
        return errors

    def _validate_dimensions(self, plan: LogisticsSqlPlan, valid_ref_ids: set[str]) -> list[str]:
        """校验输出维度存在且表范围匹配。"""

        errors: list[str] = []
        for dimension_id in plan.dimensions:
            dimension = self._dimensions.get(dimension_id)
            if dimension is None:
                errors.append(f"sqlplan_dimension_not_found::{dimension_id}")
                continue
            self._require_ref(f"dimension:{dimension_id}", valid_ref_ids, errors)
            errors.extend(self._validate_dimension_catalog_entry(dimension, plan_tables=set(plan.tables)))
        return errors

    def _validate_filters(self, plan: LogisticsSqlPlan, valid_ref_ids: set[str]) -> list[str]:
        """校验过滤条件维度存在且表范围匹配。"""

        errors: list[str] = []
        for item in plan.filters:
            for value in item.values:
                if value is None or not isinstance(value, SAFE_FILTER_VALUE_TYPES):
                    errors.append(f"sqlplan_filter_value_not_scalar::{item.dimension}")
                    break
            dimension = self._dimensions.get(item.dimension)
            if dimension is None:
                errors.append(f"sqlplan_dimension_not_found::{item.dimension}")
                continue
            self._require_ref(f"dimension:{item.dimension}", valid_ref_ids, errors)
            errors.extend(self._validate_dimension_catalog_entry(dimension, plan_tables=set(plan.tables)))
        return errors

    def _validate_group_by(self, plan: LogisticsSqlPlan, valid_ref_ids: set[str]) -> list[str]:
        """校验 group_by 只能引用 catalog 维度。"""

        errors: list[str] = []
        for dimension_id in plan.group_by:
            dimension = self._dimensions.get(dimension_id)
            if dimension is None:
                errors.append(f"sqlplan_group_by_dimension_not_found::{dimension_id}")
                continue
            self._require_ref(f"dimension:{dimension_id}", valid_ref_ids, errors)
            errors.extend(self._validate_dimension_catalog_entry(dimension, plan_tables=set(plan.tables)))
        return errors

    def _validate_order_by(self, plan: LogisticsSqlPlan, valid_ref_ids: set[str]) -> list[str]:
        """校验 order_by 只能引用 catalog 指标或维度。"""

        errors: list[str] = []
        for item in plan.order_by:
            if item.metric:
                metric = self._metrics.get(item.metric)
                if metric is None:
                    errors.append(f"sqlplan_order_by_reference_not_found::{item.metric}")
                    continue
                self._require_ref(f"metric:{item.metric}", valid_ref_ids, errors)
                errors.extend(self._validate_metric_catalog_entry(metric, plan_tables=set(plan.tables)))
            elif item.dimension:
                dimension = self._dimensions.get(item.dimension)
                if dimension is None:
                    errors.append(f"sqlplan_order_by_reference_not_found::{item.dimension}")
                    continue
                self._require_ref(f"dimension:{item.dimension}", valid_ref_ids, errors)
                errors.extend(self._validate_dimension_catalog_entry(dimension, plan_tables=set(plan.tables)))
        return errors

    def _validate_joins(self, plan: LogisticsSqlPlan, valid_ref_ids: set[str]) -> list[str]:
        """校验 join ID、左右表和 on 表达式。"""

        errors: list[str] = []
        plan_tables = set(plan.tables)
        if len(plan_tables) > 1 and not plan.joins:
            errors.append("sqlplan_join_required_for_multi_table_plan")
        joined_tables: set[str] = set()
        for join_id in plan.joins:
            join = self._joins.get(join_id)
            if join is None:
                errors.append(f"sqlplan_join_not_found::{join_id}")
                continue
            joined_tables.update({join.left_table, join.right_table})
            self._require_ref(f"join:{join_id}", valid_ref_ids, errors)
            errors.extend(self._validate_join_catalog_entry(join, plan_tables=plan_tables))
        if len(plan_tables) > 1 and plan.joins:
            missing_joined_tables = sorted(plan_tables - joined_tables)
            for table_name in missing_joined_tables:
                errors.append(f"sqlplan_join_missing_table_coverage::{table_name}")
        return errors

    def _validate_business_rules(self, plan: LogisticsSqlPlan, valid_ref_ids: set[str]) -> list[str]:
        """校验业务规则：默认时间、吨数拒答、显式年份桶。"""

        errors: list[str] = []
        for rule_id in plan.business_rules:
            rule = self._rules.get(rule_id)
            if rule is None:
                errors.append(f"sqlplan_rule_not_found::{rule_id}")
                continue
            self._require_ref(f"rule:{rule_id}", valid_ref_ids, errors)
            self._validate_rule_catalog_entry(rule, errors)
            if rule.rule_id == "unsupported_tonnage":
                errors.append("sqlplan_unsupported_tonnage_rule_blocks_sql_direct")

        requested_unit = str(plan.requested_unit or "").strip().lower()
        if not requested_unit:
            errors.append("sqlplan_requested_unit_required")
        elif requested_unit in UNSUPPORTED_TONNAGE_UNITS:
            errors.append(f"sqlplan_unsupported_unit::{plan.requested_unit}")

        errors.extend(self._validate_year_filter_shapes(plan.filters))
        year_values = _extract_year_filter_values(plan.filters)
        if not year_values:
            errors.append("sqlplan_missing_default_time_filter::2023_2026")
        else:
            for year in year_values:
                if year not in DEFAULT_LOGISTICS_YEARS:
                    errors.append(f"sqlplan_year_out_of_scope::{year}")
            if "default_time_range" in plan.business_rules and year_values != DEFAULT_LOGISTICS_YEARS:
                errors.append("sqlplan_missing_default_time_filter::2023_2026")
            if len(year_values) > 1 and not plan.explicit_year_buckets:
                expected = ",".join(str(year) for year in sorted(year_values))
                errors.append(f"sqlplan_explicit_year_buckets_required::{expected}")

        if plan.explicit_year_buckets and year_values:
            if sorted(plan.explicit_year_buckets) != sorted(year_values):
                expected = ",".join(str(year) for year in sorted(year_values))
                actual = ",".join(str(year) for year in sorted(plan.explicit_year_buckets))
                errors.append(f"sqlplan_explicit_year_buckets_mismatch::{expected}::{actual}")
        return errors

    @staticmethod
    def _validate_year_filter_shapes(filters: list[LogisticsSqlPlanFilter]) -> list[str]:
        """校验 biz_year 过滤形态，防止半开条件和大范围 between 留给后续渲染器解释。"""

        errors: list[str] = []
        min_year = min(DEFAULT_LOGISTICS_YEARS)
        max_year = max(DEFAULT_LOGISTICS_YEARS)
        for filter_index, item in enumerate(filters):
            if item.dimension != "biz_year":
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
        return errors

    @staticmethod
    def _validate_limit(plan: LogisticsSqlPlan) -> list[str]:
        """校验 detail/ranking limit 的安全范围。"""

        if plan.query_type not in {"detail", "ranking"}:
            return []
        if plan.limit is None:
            return [f"sqlplan_limit_required::{plan.query_type}"]
        if plan.limit < 1 or plan.limit > 500:
            return [f"sqlplan_limit_out_of_range::{plan.limit}"]
        return []

    def _validate_metric_catalog_entry(self, metric: LogisticsCatalogMetric, *, plan_tables: set[str]) -> list[str]:
        """二次校验指标 catalog 条目，避免污染 catalog 绕过 M3。"""

        errors: list[str] = []
        if not metric.table:
            errors.append(f"sqlplan_metric_table_required::{metric.metric_id}")
            return errors
        if metric.table not in self._strict_allowed_table_names:
            errors.append(f"sqlplan_metric_table_not_allowed::{metric.metric_id}::{metric.table}")
            return errors
        if metric.table not in plan_tables:
            errors.append(f"sqlplan_metric_table_not_in_plan::{metric.metric_id}::{metric.table}")
        if metric.aggregation != "count" and not metric.source_columns:
            errors.append(f"sqlplan_metric_source_columns_required::{metric.metric_id}")
            return errors
        available_columns = self._column_index.get(metric.table, set())
        for column_name in metric.source_columns:
            if column_name not in available_columns:
                errors.append(f"sqlplan_metric_column_not_allowed::{metric.metric_id}::{metric.table}.{column_name}")
        return errors

    def _validate_dimension_catalog_entry(
        self,
        dimension: LogisticsCatalogDimension,
        *,
        plan_tables: set[str],
    ) -> list[str]:
        """二次校验维度 catalog 条目和当前 plan 表范围。"""

        errors: list[str] = []
        if not dimension.table:
            errors.append(f"sqlplan_dimension_table_required::{dimension.dimension_id}")
            return errors
        if dimension.table not in self._strict_allowed_table_names:
            errors.append(f"sqlplan_dimension_table_not_allowed::{dimension.dimension_id}::{dimension.table}")
            return errors
        if dimension.table not in plan_tables:
            errors.append(f"sqlplan_dimension_table_not_in_plan::{dimension.dimension_id}::{dimension.table}")
        available_columns = self._column_index.get(dimension.table, set())
        if dimension.column not in available_columns:
            errors.append(
                f"sqlplan_dimension_column_not_allowed::{dimension.dimension_id}::{dimension.table}.{dimension.column}"
            )
        return errors

    def _validate_join_catalog_entry(self, join: LogisticsCatalogJoin, *, plan_tables: set[str]) -> list[str]:
        """二次校验 join catalog 条目。"""

        errors: list[str] = []
        allowed_tables = self._strict_allowed_table_names
        if join.left_table == join.right_table:
            errors.append(f"sqlplan_join_same_table_not_allowed::{join.join_id}")
        for table_name in (join.left_table, join.right_table):
            if table_name not in allowed_tables:
                errors.append(f"sqlplan_join_table_not_allowed::{join.join_id}::{table_name}")
            if table_name not in plan_tables:
                errors.append(f"sqlplan_join_table_not_in_plan::{join.join_id}::{table_name}")
        if len(join.on) != 1:
            errors.append(f"sqlplan_join_on_expression_invalid::{join.join_id}")
            return errors
        expression = join.on[0]
        match = JOIN_ON_RE.fullmatch(expression)
        if not match:
            errors.append(f"sqlplan_join_on_expression_invalid::{join.join_id}")
            return errors
        left_table, left_column, right_table, right_column = match.groups()
        referenced_tables = {left_table, right_table}
        declared_tables = {join.left_table, join.right_table}
        if referenced_tables != declared_tables:
            if not referenced_tables <= declared_tables:
                for table_name in sorted(referenced_tables - declared_tables):
                    errors.append(f"sqlplan_join_on_table_not_in_join::{join.join_id}::{table_name}")
            else:
                errors.append(f"sqlplan_join_on_missing_join_side::{join.join_id}")
        for table_name, column_name in ((left_table, left_column), (right_table, right_column)):
            if column_name not in self._column_index.get(table_name, set()):
                errors.append(f"sqlplan_join_column_not_allowed::{join.join_id}::{table_name}.{column_name}")
        return errors

    @staticmethod
    def _validate_rule_catalog_entry(rule: LogisticsCatalogRule, errors: list[str]) -> None:
        """校验关键业务规则自身未被污染。"""

        if rule.rule_id == "unsupported_tonnage" and rule.action != "reject":
            errors.append("sqlplan_rule_unsupported_tonnage_must_reject")
        if rule.rule_id == "default_time_range" and rule.value != DEFAULT_LOGISTICS_YEARS:
            errors.append("sqlplan_rule_default_time_range_invalid")

    def _build_allowed_catalog_ids(self) -> set[str]:
        """从 canonical catalog 构造允许被 M2 引用的 ID 集合。"""

        ids: set[str] = set()
        ids.update(
            f"table:{table.table_name}"
            for table in self.catalog.allowed_tables()
            if self._is_strict_allowed_table(table)
        )
        ids.update(f"metric:{metric.metric_id}" for metric in self.catalog.metrics)
        ids.update(f"dimension:{dimension.dimension_id}" for dimension in self.catalog.dimensions)
        ids.update(f"join:{join.join_id}" for join in self.catalog.joins)
        ids.update(f"rule:{rule.rule_id}" for rule in self.catalog.rules)
        return ids

    @staticmethod
    def _require_ref(catalog_id: str, valid_ref_ids: set[str], errors: list[str]) -> None:
        """要求 plan 中每个引用都来自 M2 catalog_refs。"""

        if catalog_id not in valid_ref_ids:
            errors.append(f"sqlplan_missing_catalog_ref::{catalog_id}")

    @staticmethod
    def _result(
        errors: list[str],
        *,
        normalized_plan: LogisticsSqlPlan | None = None,
    ) -> LogisticsSqlPlanValidationResult:
        """构造 fail-closed 结果对象。"""

        deduped = _dedupe_errors(errors)
        if deduped:
            return LogisticsSqlPlanValidationResult(ok=False, normalized_plan=None, errors=deduped)
        return LogisticsSqlPlanValidationResult(ok=True, normalized_plan=normalized_plan, errors=[])


def validate_logistics_sql_plan_candidate(
    candidate_payload: LogisticsSqlPlanCandidate | dict[str, Any],
    *,
    catalog: LogisticsSemanticCatalog | None = None,
) -> LogisticsSqlPlanValidationResult:
    """函数式入口：校验物流 SQLPlan candidate。

    参数：
        candidate_payload: LLM/upstream candidate。
        catalog: 可选 canonical Semantic Catalog。
    返回：
        SQLPlanValidationResult；M3 不生成 SQL、不执行 SQL。
    """

    return LogisticsSqlPlanValidator(catalog=catalog).validate(candidate_payload)


def _scan_forbidden_sql_payload(payload: Any, path: str = "root") -> list[str]:
    """递归扫描 candidate 原始 payload 中的 SQL 字段和 SQL-like 字符串。

    错误码只暴露字段路径，不回显 LLM 原文，避免把疑似 SQL/密钥片段写入审计或用户侧材料。
    """

    errors: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            normalized_key = key_text.strip().lower()
            child_path = key_text if path == "root" else f"{path}.{key_text}"
            if normalized_key in FORBIDDEN_SQLPLAN_KEYS:
                errors.append(f"sqlplan_forbidden_key::{child_path}")
            errors.extend(_scan_forbidden_sql_payload(value, child_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            errors.extend(_scan_forbidden_sql_payload(value, f"{path}[{index}]"))
    elif isinstance(payload, str) and SQL_LIKE_STRING_RE.search(payload):
        errors.append(f"sqlplan_forbidden_sql_string::{path}")
    return errors


def _schema_error_codes(exc: ValidationError) -> list[str]:
    """把 Pydantic 校验错误转换为稳定错误码。"""

    codes: list[str] = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", ())) or "root"
        error_type = str(error.get("type") or "invalid")
        codes.append(f"sqlplan_schema_invalid::{loc}::{error_type}")
    return codes


def _parse_year_filter_value(value: Any) -> int | None:
    """把 biz_year 过滤值解析为整数年份；小数、布尔值和非年份字符串均 fail-closed。

    参数：
        value: LLM candidate 提供的年份过滤值。
    返回：
        合法整数年份返回 int；否则返回 None，由调用方生成稳定错误码。
    """

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


def _extract_year_filter_values(filters: list[LogisticsSqlPlanFilter]) -> list[int]:
    """提取所有 biz_year 过滤中的年份列表。"""

    years: set[int] = set()
    for item in filters:
        if item.dimension != "biz_year":
            continue
        values: list[int] = []
        for value in item.values:
            parsed_year = _parse_year_filter_value(value)
            if parsed_year is None:
                return []
            values.append(parsed_year)
        if item.operator == "between" and len(values) == 2:
            start, end = sorted(values)
            if start < min(DEFAULT_LOGISTICS_YEARS) or end > max(DEFAULT_LOGISTICS_YEARS):
                years.update({start, end})
            else:
                years.update(range(start, end + 1))
        else:
            years.update(values)
    return sorted(years)


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
    "LogisticsSqlPlan",
    "LogisticsSqlPlanCandidate",
    "LogisticsSqlPlanCatalogRef",
    "LogisticsSqlPlanFilter",
    "LogisticsSqlPlanOrderBy",
    "LogisticsSqlPlanValidationResult",
    "LogisticsSqlPlanValidator",
    "validate_logistics_sql_plan_candidate",
]

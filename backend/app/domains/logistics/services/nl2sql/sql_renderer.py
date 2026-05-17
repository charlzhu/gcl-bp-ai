from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domains.logistics.services.nl2sql.semantic_catalog import (
    LogisticsCatalogDimension,
    LogisticsCatalogJoin,
    LogisticsCatalogMetric,
    LogisticsSemanticCatalog,
    LogisticsSemanticCatalogLoader,
)
from backend.app.domains.logistics.services.nl2sql.sql_plan import (
    LogisticsSqlPlan,
    LogisticsSqlPlanFilter,
    LogisticsSqlPlanValidationResult,
)


class LogisticsRenderedSql(BaseModel):
    """物流 NL2SQL M4 渲染结果。

    参数：
        sql: 由受控 SQLPlan 渲染出来的只读 SELECT SQL，用户值只能以命名参数占位。
        params: SQL 命名参数字典，例如 `{p0: 2025}`。
        referenced_tables: SQL 引用的表白名单，用于 safety 二次校验。
        referenced_columns: SQL 引用的 `(table, column)` 字段白名单，用于 safety 二次校验。
        referenced_joins: 使用的 catalog join_id 列表。
        limit: SQL 中的受控 LIMIT；aggregate 可为空。
        warnings: 渲染期非阻断提示，只用于 shadow/审计。
        explicit_year_buckets: M3 保留下来的显式年份桶，供后续 0 行年份补齐使用。
    返回：
        不包含用户原始问题、不包含 LLM 原文、不包含可执行写操作。
    """

    model_config = ConfigDict(extra="forbid")

    sql: str
    params: dict[str, Any] = Field(default_factory=dict)
    referenced_tables: list[str] = Field(default_factory=list)
    referenced_columns: list[tuple[str, str]] = Field(default_factory=list)
    referenced_joins: list[str] = Field(default_factory=list)
    limit: int | None = None
    warnings: list[str] = Field(default_factory=list)
    explicit_year_buckets: list[int] = Field(default_factory=list)


class _ParamBinder:
    """渲染期命名参数分配器。"""

    def __init__(self) -> None:
        """初始化参数序号和参数字典。"""

        self.params: dict[str, Any] = {}
        self._index = 0

    def bind(self, value: Any) -> str:
        """绑定一个用户/受控值并返回 SQL 占位符。

        参数：
            value: 需要传给 DB driver 的参数值。
        返回：
            `:pN` 形式占位符；真实值只进入 params，不拼进 SQL 字符串。
        """

        name = f"p{self._index}"
        self._index += 1
        self.params[name] = value
        return f":{name}"


class LogisticsSqlRenderer:
    """物流 NL2SQL M4 确定性 SQL Renderer。

    业务逻辑：
        Renderer 只消费 M3 `LogisticsSqlPlanValidator` 通过的 normalized plan；它不读取
        LLM 原文、不接正式 QA 主链路、不连接数据库，只把受控 catalog ID 渲染为参数化 SELECT。
    """

    def __init__(self, catalog: LogisticsSemanticCatalog | None = None, *, max_limit: int = 500) -> None:
        """初始化 renderer。

        参数：
            catalog: 可注入的 canonical Semantic Catalog；默认读取物流域 YAML catalog。
            max_limit: detail/ranking 的最大安全 LIMIT。
        返回：
            无。
        """

        self.catalog = catalog or LogisticsSemanticCatalogLoader().load()
        self.max_limit = max_limit
        self._tables = {table.table_name: table for table in self.catalog.allowed_tables()}
        self._metrics = {metric.metric_id: metric for metric in self.catalog.metrics}
        self._dimensions = {dimension.dimension_id: dimension for dimension in self.catalog.dimensions}
        self._joins = {join.join_id: join for join in self.catalog.joins}

    def render(self, validation_result: LogisticsSqlPlanValidationResult) -> LogisticsRenderedSql:
        """把 M3 校验通过结果渲染为参数化 SQL。

        参数：
            validation_result: `LogisticsSqlPlanValidator.validate` 的返回值。
        返回：
            `LogisticsRenderedSql`；所有用户值已进入 params。
        业务逻辑：
            若 M3 未通过或 normalized_plan 缺失，立即 fail-closed，避免绕过 validator。
        """

        if not validation_result.ok or validation_result.normalized_plan is None:
            joined_errors = ",".join(validation_result.error_codes)
            raise ValueError(f"sql_renderer_requires_validated_plan::{joined_errors}")

        plan = validation_result.normalized_plan
        binder = _ParamBinder()
        referenced_columns: list[tuple[str, str]] = []

        select_sql = self._render_select_items(plan, referenced_columns)
        from_sql = self._render_from_and_joins(plan, referenced_columns)
        where_sql = self._render_where(plan.filters, binder, referenced_columns)
        group_sql = self._render_group_by(plan, referenced_columns)
        order_sql = self._render_order_by(plan, referenced_columns)
        limit_sql, limit_value = self._render_limit(plan, binder)

        parts = [f"SELECT {select_sql}", from_sql]
        if where_sql:
            parts.append(where_sql)
        if group_sql:
            parts.append(group_sql)
        if order_sql:
            parts.append(order_sql)
        if limit_sql:
            parts.append(limit_sql)

        return LogisticsRenderedSql(
            sql=" ".join(parts),
            params=binder.params,
            referenced_tables=list(plan.tables),
            referenced_columns=_dedupe_pairs(referenced_columns),
            referenced_joins=list(plan.joins),
            limit=limit_value,
            warnings=[],
            explicit_year_buckets=list(plan.explicit_year_buckets),
        )

    def _render_select_items(self, plan: LogisticsSqlPlan, referenced_columns: list[tuple[str, str]]) -> str:
        """渲染 SELECT 明确列清单，禁止 SELECT *。"""

        items: list[str] = []
        selected_aliases: set[str] = set()
        for dimension_id in plan.dimensions:
            dimension = self._get_dimension(dimension_id)
            expression = self._qualified_column(dimension.table, dimension.column, referenced_columns)
            items.append(f"{expression} AS {dimension.dimension_id}")
            selected_aliases.add(dimension.dimension_id)

        for metric_id in plan.metrics:
            metric = self._get_metric(metric_id)
            expression = self._metric_expression(metric, plan.query_type, referenced_columns)
            items.append(f"{expression} AS {metric.metric_id}")
            selected_aliases.add(metric.metric_id)

        if not items:
            raise ValueError("sql_renderer_select_items_required")
        if len(items) != len(selected_aliases):
            raise ValueError("sql_renderer_duplicate_select_alias")
        return ", ".join(items)

    def _render_from_and_joins(self, plan: LogisticsSqlPlan, referenced_columns: list[tuple[str, str]]) -> str:
        """渲染 FROM 与受控 JOIN 子句。"""

        if not plan.tables:
            raise ValueError("sql_renderer_tables_required")
        for table_name in plan.tables:
            self._require_table(table_name)

        sql = f"FROM {plan.tables[0]}"
        joined_tables = {plan.tables[0]}
        for join_id in plan.joins:
            join = self._get_join(join_id)
            join_sql, new_table = self._render_join_clause(join, joined_tables, referenced_columns)
            sql = f"{sql} {join_sql}"
            joined_tables.add(new_table)
        return sql

    def _render_join_clause(
        self,
        join: LogisticsCatalogJoin,
        joined_tables: set[str],
        referenced_columns: list[tuple[str, str]],
    ) -> tuple[str, str]:
        """渲染单个 catalog join。

        参数：
            join: catalog 中人工审计过的 join 条目。
            joined_tables: 已经进入 FROM/JOIN 链的表集合。
            referenced_columns: 收集字段引用的列表。
        返回：
            `(join_sql, newly_joined_table)`。
        业务逻辑：
            join.on 只能来自 catalog loader/M3 validator 已校验的 `table.column = table.column`。
        """

        if len(join.on) != 1:
            raise ValueError(f"sql_renderer_join_on_invalid::{join.join_id}")
        join_kind = join.join_type.lower()
        if join_kind == "left":
            if join.left_table in joined_tables:
                next_table = join.right_table
            elif join.right_table in joined_tables:
                # LEFT JOIN 不能为了连通性反向渲染，否则会改变外连接保留行语义。
                raise ValueError(f"sql_renderer_left_join_direction_invalid::{join.join_id}")
            else:
                # 对链式 join，当前 MVP 要求 plan.tables 顺序和 join 链可连通；不能偷偷做笛卡尔扩展。
                raise ValueError(f"sql_renderer_join_not_connected::{join.join_id}")
            join_type = "LEFT JOIN"
        else:
            if join.left_table in joined_tables:
                next_table = join.right_table
            elif join.right_table in joined_tables:
                next_table = join.left_table
            else:
                # INNER JOIN 可双向连通，但仍不得凭空引入未连接表。
                raise ValueError(f"sql_renderer_join_not_connected::{join.join_id}")
            join_type = "INNER JOIN"
        for table_name, column_name in _parse_qualified_columns(join.on[0]):
            referenced_columns.append((table_name, column_name))
        return f"{join_type} {next_table} ON {join.on[0]}", next_table

    def _render_where(
        self,
        filters: list[LogisticsSqlPlanFilter],
        binder: _ParamBinder,
        referenced_columns: list[tuple[str, str]],
    ) -> str:
        """渲染 WHERE 条件，所有值都进入参数绑定。"""

        clauses: list[str] = []
        for item in filters:
            dimension = self._get_dimension(item.dimension)
            column_expr = self._qualified_column(dimension.table, dimension.column, referenced_columns)
            clauses.append(self._render_filter_clause(column_expr, item, binder))
        return f"WHERE {' AND '.join(clauses)}" if clauses else ""

    @staticmethod
    def _render_filter_clause(column_expr: str, item: LogisticsSqlPlanFilter, binder: _ParamBinder) -> str:
        """按受控操作符渲染单个过滤条件。"""

        if item.operator == "=":
            if len(item.values) != 1:
                raise ValueError(f"sql_renderer_filter_value_count_invalid::{item.dimension}")
            return f"{column_expr} = {binder.bind(item.values[0])}"
        if item.operator == "in":
            if not item.values:
                raise ValueError(f"sql_renderer_filter_values_required::{item.dimension}")
            placeholders = ", ".join(binder.bind(value) for value in item.values)
            return f"{column_expr} IN ({placeholders})"
        if item.operator == "between":
            if len(item.values) != 2:
                raise ValueError(f"sql_renderer_between_requires_two_values::{item.dimension}")
            return f"{column_expr} BETWEEN {binder.bind(item.values[0])} AND {binder.bind(item.values[1])}"
        if item.operator in {">=", "<=", "like"}:
            if len(item.values) != 1:
                raise ValueError(f"sql_renderer_filter_value_count_invalid::{item.dimension}")
            return f"{column_expr} {item.operator.upper()} {binder.bind(item.values[0])}"
        raise ValueError(f"sql_renderer_filter_operator_unsupported::{item.operator}")

    def _render_group_by(self, plan: LogisticsSqlPlan, referenced_columns: list[tuple[str, str]]) -> str:
        """渲染 GROUP BY 维度字段。"""

        if not plan.group_by:
            return ""
        columns = []
        for dimension_id in plan.group_by:
            dimension = self._get_dimension(dimension_id)
            columns.append(self._qualified_column(dimension.table, dimension.column, referenced_columns))
        return f"GROUP BY {', '.join(columns)}"

    def _render_order_by(self, plan: LogisticsSqlPlan, referenced_columns: list[tuple[str, str]]) -> str:
        """渲染 ORDER BY，优先使用已渲染的安全 alias。"""

        if not plan.order_by:
            return ""
        clauses: list[str] = []
        selected_metrics = set(plan.metrics)
        selected_dimensions = set(plan.dimensions)
        for item in plan.order_by:
            direction = item.direction.upper()
            if item.metric:
                if item.metric not in selected_metrics:
                    raise ValueError(f"sql_renderer_order_metric_not_selected::{item.metric}")
                clauses.append(f"{item.metric} {direction}")
            elif item.dimension:
                if item.dimension in selected_dimensions:
                    clauses.append(f"{item.dimension} {direction}")
                else:
                    dimension = self._get_dimension(item.dimension)
                    clauses.append(f"{self._qualified_column(dimension.table, dimension.column, referenced_columns)} {direction}")
        return f"ORDER BY {', '.join(clauses)}"

    def _render_limit(self, plan: LogisticsSqlPlan, binder: _ParamBinder) -> tuple[str, int | None]:
        """渲染受控 LIMIT，并对 detail/ranking 做二次上限保护。"""

        if plan.limit is None:
            if plan.query_type in {"detail", "ranking"}:
                raise ValueError(f"sql_renderer_limit_required::{plan.query_type}")
            return "", None
        if plan.limit < 1 or plan.limit > self.max_limit:
            raise ValueError(f"sql_renderer_limit_out_of_range::{plan.limit}")
        return f"LIMIT {binder.bind(plan.limit)}", plan.limit

    def _metric_expression(
        self,
        metric: LogisticsCatalogMetric,
        query_type: str,
        referenced_columns: list[tuple[str, str]],
    ) -> str:
        """渲染指标表达式并记录依赖字段。

        业务逻辑：
            detail 明细不应把 SUM/CASE 这类聚合表达式混入逐行明细；若指标只有一个来源字段，
            明细查询选择该字段并沿用 metric alias。aggregate/ranking 使用 catalog 公式。
        """

        if not metric.table:
            raise ValueError(f"sql_renderer_metric_table_required::{metric.metric_id}")
        self._require_table(metric.table)
        for column_name in metric.source_columns:
            referenced_columns.append((metric.table, column_name))

        if query_type == "detail" and metric.aggregation != "count" and len(metric.source_columns) == 1:
            return self._qualified_column(metric.table, metric.source_columns[0], referenced_columns)

        expression = metric.sql_expression.strip()
        if expression.upper() == "COUNT(*)":
            return "COUNT(1)"
        return self._qualify_metric_expression(expression, metric)

    def _qualify_metric_expression(self, expression: str, metric: LogisticsCatalogMetric) -> str:
        """把 catalog 指标表达式中的来源字段替换为 `table.column` 形式。"""

        if not metric.table:
            raise ValueError(f"sql_renderer_metric_table_required::{metric.metric_id}")
        qualified = expression
        for column_name in sorted(metric.source_columns, key=len, reverse=True):
            qualified_column = f"{metric.table}.{column_name}"
            qualified = re.sub(rf"(?<![\w.]){re.escape(column_name)}(?![\w.])", qualified_column, qualified)
        return qualified

    def _qualified_column(
        self,
        table_name: str | None,
        column_name: str,
        referenced_columns: list[tuple[str, str]],
    ) -> str:
        """返回 `table.column` 并记录字段引用。"""

        if not table_name:
            raise ValueError(f"sql_renderer_column_table_required::{column_name}")
        self._require_table(table_name)
        referenced_columns.append((table_name, column_name))
        return f"{table_name}.{column_name}"

    def _require_table(self, table_name: str) -> None:
        """确认表来自 canonical catalog 可读白名单。"""

        if table_name not in self._tables:
            raise ValueError(f"sql_renderer_table_not_allowed::{table_name}")

    def _get_metric(self, metric_id: str) -> LogisticsCatalogMetric:
        """按 metric_id 获取 catalog 指标。"""

        metric = self._metrics.get(metric_id)
        if metric is None:
            raise ValueError(f"sql_renderer_metric_not_found::{metric_id}")
        return metric

    def _get_dimension(self, dimension_id: str) -> LogisticsCatalogDimension:
        """按 dimension_id 获取 catalog 维度。"""

        dimension = self._dimensions.get(dimension_id)
        if dimension is None:
            raise ValueError(f"sql_renderer_dimension_not_found::{dimension_id}")
        return dimension

    def _get_join(self, join_id: str) -> LogisticsCatalogJoin:
        """按 join_id 获取 catalog join。"""

        join = self._joins.get(join_id)
        if join is None:
            raise ValueError(f"sql_renderer_join_not_found::{join_id}")
        return join


def render_logistics_sql(
    validation_result: LogisticsSqlPlanValidationResult,
    *,
    catalog: LogisticsSemanticCatalog | None = None,
) -> LogisticsRenderedSql:
    """函数式入口：渲染物流 NL2SQL SQLPlan。

    参数：
        validation_result: M3 validator 通过的结果。
        catalog: 可选 canonical catalog。
    返回：
        `LogisticsRenderedSql`。
    """

    return LogisticsSqlRenderer(catalog=catalog).render(validation_result)


def _parse_qualified_columns(expression: str) -> list[tuple[str, str]]:
    """从受控 join.on 表达式提取字段引用。"""

    return re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\b", expression)


def _dedupe_pairs(values: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """保持顺序去重 `(table, column)` 引用。"""

    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


__all__ = ["LogisticsRenderedSql", "LogisticsSqlRenderer", "render_logistics_sql"]

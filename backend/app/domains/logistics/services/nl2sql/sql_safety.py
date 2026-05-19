from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domains.logistics.services.nl2sql.semantic_catalog import (
    LOGISTICS_NL2SQL_ALLOWED_READ_TABLES,
    LogisticsCatalogJoin,
    LogisticsSemanticCatalog,
    LogisticsSemanticCatalogLoader,
)
from backend.app.domains.logistics.services.nl2sql.sql_renderer import LogisticsRenderedSql


FORBIDDEN_SQL_TOKENS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "merge",
    "call",
    "copy",
    "replace",
    "grant",
    "revoke",
    "into",
    "outfile",
    "dumpfile",
}
FORBIDDEN_FUNCTIONS = {"sleep", "benchmark", "load_file", "xp_cmdshell"}
PARAM_RE = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")
QUALIFIED_COLUMN_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\b")
TABLE_RE = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.IGNORECASE)
FROM_TABLE_RE = re.compile(r"\bFROM\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.IGNORECASE)
SELECT_LIST_RE = re.compile(r"^\s*SELECT\s+(?:DISTINCT\s+|ALL\s+)?(?P<select>.*?)\s+FROM\b", re.IGNORECASE | re.DOTALL)
STRING_LITERAL_RE = re.compile(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"")
LIMIT_ANY_RE = re.compile(r"\bLIMIT\b", re.IGNORECASE)
LIMIT_RENDERER_RE = re.compile(r"\bLIMIT\s+(?::([A-Za-z_][A-Za-z0-9_]*)|(\d+))\s*$", re.IGNORECASE)
ALIAS_RE = re.compile(r"\bAS\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.IGNORECASE)
IDENTIFIER_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
SQL_KEYWORDS_AND_FUNCTIONS = {
    "select",
    "from",
    "where",
    "group",
    "by",
    "order",
    "limit",
    "as",
    "and",
    "or",
    "not",
    "in",
    "between",
    "like",
    "case",
    "when",
    "then",
    "else",
    "end",
    "null",
    "is",
    "asc",
    "desc",
    "distinct",
    "all",
    "on",
    "left",
    "inner",
    "join",
    "sum",
    "count",
    "avg",
    "min",
    "max",
}
JOIN_CLAUSE_RE = re.compile(
    r"\b(?P<join_type>LEFT\s+JOIN|INNER\s+JOIN|JOIN)\s+"
    r"(?P<table>[A-Za-z_][A-Za-z0-9_]*)\s+ON\s+"
    r"(?P<on>.*?)\s*(?=\bLEFT\s+JOIN\b|\bINNER\s+JOIN\b|\bJOIN\b|\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|$)",
    re.IGNORECASE | re.DOTALL,
)


class LogisticsSqlSafetyResult(BaseModel):
    """SQL Safety Checker 的确定性返回。"""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    errors: list[str] = Field(default_factory=list)

    @property
    def error_codes(self) -> list[str]:
        """返回稳定错误码列表，便于审计和单测。"""

        return list(self.errors)


class LogisticsSqlSafetyChecker:
    """物流 NL2SQL M4 SQL 二次安全校验器。

    业务逻辑：
        即使 SQL 来自 renderer，也要在 EXPLAIN/试执行前再次 fail-closed 校验：只读 SELECT、
        单语句、无注释/UNION/危险函数、表字段 allow-list、参数绑定和 LIMIT 上限。
    """

    def __init__(self, catalog: LogisticsSemanticCatalog | None = None, *, max_limit: int = 500) -> None:
        """初始化 safety checker。

        参数：
            catalog: canonical Semantic Catalog；默认加载物流 NL2SQL catalog。
            max_limit: detail/ranking/试执行允许的最大 LIMIT。
        返回：
            无。
        """

        self.catalog = catalog or LogisticsSemanticCatalogLoader().load()
        self.max_limit = max_limit
        strict_allowed = set(LOGISTICS_NL2SQL_ALLOWED_READ_TABLES)
        self._allowed_tables = {
            table.table_name
            for table in self.catalog.allowed_tables()
            if table.table_name in strict_allowed
            and table.domain == "logistics"
            and table.source_system == "middle_db"
        }
        self._column_index = {
            table.table_name: {column.name for column in table.columns}
            for table in self.catalog.allowed_tables()
            if table.table_name in self._allowed_tables
        }
        self._joins = {join.join_id: join for join in self.catalog.joins}

    def check(self, rendered: LogisticsRenderedSql) -> LogisticsSqlSafetyResult:
        """校验 renderer 产物是否可进入 EXPLAIN/试执行。

        参数：
            rendered: `LogisticsRenderedSql`。
        返回：
            ok=True 表示可交给只读 executor；否则返回稳定错误码。
        """

        errors: list[str] = []
        sql = rendered.sql.strip()
        lower_sql = sql.lower()

        errors.extend(self._check_statement_shape(sql, lower_sql))
        errors.extend(self._check_tokens_and_literals(sql, lower_sql))
        errors.extend(self._check_renderer_shape(sql))
        errors.extend(self._check_tables_and_columns(sql, rendered))
        errors.extend(self._check_params(sql, rendered.params))
        errors.extend(self._check_limit(sql, rendered))
        errors.extend(self._check_join_boundary(sql, rendered))

        deduped = _dedupe_errors(errors)
        return LogisticsSqlSafetyResult(ok=not deduped, errors=deduped)

    @staticmethod
    def _check_statement_shape(sql: str, lower_sql: str) -> list[str]:
        """校验只读单 SELECT 语句形态。"""

        errors: list[str] = []
        if ";" in sql:
            errors.append("sql_safety_forbidden_token::multi_statement")
        if lower_sql.startswith("explain"):
            errors.append("sql_safety_explain_nested_forbidden")
        elif not lower_sql.startswith("select"):
            errors.append("sql_safety_not_select")
        select_list_match = SELECT_LIST_RE.search(sql)
        select_list = select_list_match.group("select") if select_list_match else ""
        select_list_without_count_star = re.sub(r"\bCOUNT\s*\(\s*\*\s*\)", "COUNT_ONE", select_list, flags=re.IGNORECASE)
        if re.search(r"(?<![\w.])\*(?![\w.])", select_list_without_count_star) or re.search(
            r"\b[A-Za-z_][A-Za-z0-9_]*\s*\.\s*\*",
            sql,
        ):
            errors.append("sql_safety_select_star_forbidden")
        return errors

    @staticmethod
    def _check_tokens_and_literals(sql: str, lower_sql: str) -> list[str]:
        """校验危险 token、注释、字符串字面量和危险函数。"""

        errors: list[str] = []
        if "--" in sql or "#" in sql or "/*" in sql or "*/" in sql:
            errors.append("sql_safety_forbidden_token::comment")
        if re.search(r"\bunion\b", lower_sql):
            errors.append("sql_safety_forbidden_token::union")
        if re.search(r"\btemporary\b|\btemp\s+table\b", lower_sql):
            errors.append("sql_safety_forbidden_token::temporary_table")
        for token in FORBIDDEN_SQL_TOKENS:
            if re.search(rf"\b{re.escape(token)}\b", lower_sql):
                errors.append(f"sql_safety_forbidden_token::{token}")
        for function_name in FORBIDDEN_FUNCTIONS:
            if re.search(rf"\b{re.escape(function_name)}\s*\(", lower_sql):
                errors.append(f"sql_safety_forbidden_function::{function_name}")
        if re.search(r"\bor\s+1\s*=\s*1\b|(?<![\w.])1\s*=\s*1(?![\w.])", lower_sql):
            errors.append("sql_safety_forbidden_token::or_true_condition")
        if STRING_LITERAL_RE.search(sql):
            # Renderer 对用户值一律参数化；MVP catalog 公式不需要字符串字面量，因此出现字符串直接拒绝。
            errors.append("sql_safety_string_literal_forbidden")
        return errors

    def _check_renderer_shape(self, sql: str) -> list[str]:
        """校验 SQL 文本仍保持 renderer 约定形态。

        参数：
            sql: 待校验 SQL 文本。
        返回：
            稳定错误码列表。
        业务逻辑：
            M4 renderer 不输出反引号标识符、系统变量、无 FROM 查询，也不输出裸字段名。
            这里把 `table.column`、`:param` 先从扫描文本中剥离，只允许 SQL 关键字、受控函数、
            catalog 表名和 `AS alias` 继续以裸标识符形式存在；其他裸标识符一律 fail-closed。
        """

        errors: list[str] = []
        if "`" in sql:
            errors.append("sql_safety_quoted_identifier_forbidden")
        if "@@" in sql:
            errors.append("sql_safety_system_variable_forbidden")
        if not TABLE_RE.search(sql):
            errors.append("sql_safety_table_required")

        aliases = {alias.lower() for alias in ALIAS_RE.findall(sql)}
        allowed_identifiers = set(SQL_KEYWORDS_AND_FUNCTIONS)
        allowed_identifiers.update(table_name.lower() for table_name in self._allowed_tables)
        allowed_identifiers.update(PARAM_RE.findall(sql))

        scan_sql = QUALIFIED_COLUMN_RE.sub(" ", sql)
        scan_sql = PARAM_RE.sub(" ", scan_sql)
        # `AS alias` 本身是 renderer 合法输出，但 alias 不能反过来放行 SELECT 中的裸字段。
        scan_sql = ALIAS_RE.sub(" AS ", scan_sql)
        scan_sql = _strip_allowed_order_by_aliases(scan_sql, aliases)
        for token in IDENTIFIER_RE.findall(scan_sql):
            normalized = token.lower()
            if normalized in allowed_identifiers:
                continue
            # renderer 只会输出 `table.column` 或受控 alias；其他裸标识符一律视为绕过。
            errors.append(f"sql_safety_unqualified_identifier::{token}")
        return errors

    def _check_tables_and_columns(self, sql: str, rendered: LogisticsRenderedSql) -> list[str]:
        """校验 SQL 文本和 renderer 元数据中的表字段均在 allow-list 内。"""

        errors: list[str] = []
        sql_tables = set(TABLE_RE.findall(sql))
        metadata_tables = set(rendered.referenced_tables)
        for table_name in sorted(sql_tables | metadata_tables):
            if table_name not in self._allowed_tables:
                errors.append(f"sql_safety_table_not_allowed::{table_name}")

        sql_columns = set(QUALIFIED_COLUMN_RE.findall(sql))
        metadata_columns = set(tuple(item) for item in rendered.referenced_columns)
        for table_name, column_name in sorted(sql_columns | metadata_columns):
            if table_name not in self._allowed_tables or column_name not in self._column_index.get(table_name, set()):
                errors.append(f"sql_safety_column_not_allowed::{table_name}.{column_name}")
        return errors

    @staticmethod
    def _check_params(sql: str, params: dict[str, Any]) -> list[str]:
        """校验 SQL placeholder 与 params 完整一致。"""

        errors: list[str] = []
        placeholders = set(PARAM_RE.findall(sql))
        param_keys = set(params)
        for name in sorted(placeholders - param_keys):
            errors.append(f"sql_safety_param_missing::{name}")
        for name in sorted(param_keys - placeholders):
            errors.append(f"sql_safety_param_unused::{name}")
        for name, value in params.items():
            if isinstance(value, (dict, list, tuple, set)):
                errors.append(f"sql_safety_param_not_scalar::{name}")
        return errors

    def _check_limit(self, sql: str, rendered: LogisticsRenderedSql) -> list[str]:
        """校验 LIMIT 只能是 renderer 形态，并且参数值不超过安全上限。

        业务逻辑：
            M4 renderer 只会在 SQL 末尾输出 `LIMIT :pN`。Safety 不接受 `LIMIT ALL`、
            `LIMIT offset,count` 或 `OFFSET` 变体，避免 trial 层误以为已有安全 LIMIT 而不追加上限。
        """

        errors: list[str] = []
        if rendered.limit is not None and (rendered.limit < 0 or rendered.limit > self.max_limit):
            errors.append(f"sql_safety_limit_out_of_range::{rendered.limit}")

        if not LIMIT_ANY_RE.search(sql):
            return errors

        limit_match = LIMIT_RENDERER_RE.search(sql)
        if not limit_match:
            errors.append("sql_safety_limit_syntax_invalid")
            return errors

        param_name, literal_value = limit_match.groups()
        if param_name:
            value = rendered.params.get(param_name)
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(f"sql_safety_limit_param_invalid::{param_name}")
                return errors
            limit_value = value
        else:
            limit_value = int(literal_value)

        if limit_value < 0 or limit_value > self.max_limit:
            errors.append(f"sql_safety_limit_out_of_range::{limit_value}")
        return errors

    def _check_join_boundary(self, sql: str, rendered: LogisticsRenderedSql) -> list[str]:
        """校验 JOIN 子句必须逐条匹配 catalog join。

        参数：
            sql: renderer 产出的 SQL 文本。
            rendered: renderer 元数据，包含 referenced_joins。
        返回：
            错误码列表。
        业务逻辑：
            不能只检查 referenced_joins 非空；被伪造的 `LogisticsRenderedSql` 可能携带任意 join_id。
            因此 Safety 重新解析 SQL 中的 JOIN/ON，并与 catalog 中人工审计的 join_type、两侧表和
            on 表达式精确比对。
        """

        join_clauses = list(JOIN_CLAUSE_RE.finditer(sql))
        if not join_clauses and not rendered.referenced_joins:
            return []
        if join_clauses and not rendered.referenced_joins:
            return ["sql_safety_join_not_catalog_controlled"]
        if len(join_clauses) != len(rendered.referenced_joins):
            return ["sql_safety_join_count_mismatch"]

        errors: list[str] = []
        base_match = FROM_TABLE_RE.search(sql)
        joined_tables: set[str] = {base_match.group(1)} if base_match else set()
        for match, join_id in zip(join_clauses, rendered.referenced_joins, strict=True):
            join = self._joins.get(join_id)
            if join is None:
                errors.append(f"sql_safety_join_not_found::{join_id}")
                continue
            if not _join_clause_matches_catalog(match, join, joined_tables):
                errors.append(f"sql_safety_join_clause_not_catalog_controlled::{join_id}")
                continue
            joined_tables.add(match.group("table"))
        return errors


def check_logistics_sql_safety(
    rendered: LogisticsRenderedSql,
    *,
    catalog: LogisticsSemanticCatalog | None = None,
) -> LogisticsSqlSafetyResult:
    """函数式入口：校验物流 NL2SQL renderer 产物。"""

    return LogisticsSqlSafetyChecker(catalog=catalog).check(rendered)


def _strip_allowed_order_by_aliases(sql: str, aliases: set[str]) -> str:
    """从 ORDER BY 片段移除 renderer 产生的合法别名。

    参数：
        sql: 已去掉限定字段和参数后的 SQL 文本。
        aliases: SELECT 列表中 `AS alias` 提取出的别名。
    返回：
        将 ORDER BY 中合法 alias 替换为空白后的 SQL 文本。
    业务逻辑：
        alias 只允许在 ORDER BY 里引用，不能全局放行，否则 `secret AS secret` 会绕过裸字段校验。
    """

    if not aliases:
        return sql
    match = re.search(r"\bORDER\s+BY\b(?P<order>.*?)(?=\bLIMIT\b|$)", sql, re.IGNORECASE | re.DOTALL)
    if not match:
        return sql
    order_segment = match.group("order")
    sanitized_order = order_segment
    for alias in aliases:
        sanitized_order = re.sub(rf"\b{re.escape(alias)}\b", " ", sanitized_order, flags=re.IGNORECASE)
    return f"{sql[: match.start('order')]}{sanitized_order}{sql[match.end('order') :]}"


def _join_clause_matches_catalog(match: re.Match[str], join: LogisticsCatalogJoin, joined_tables: set[str]) -> bool:
    """判断 SQL JOIN 子句是否与 catalog join 精确一致。

    参数：
        match: `JOIN_CLAUSE_RE` 匹配到的 SQL JOIN 子句。
        join: canonical catalog 中人工审计的 join。
    返回：
        完全匹配返回 True；任何表、类型或 ON 表达式差异返回 False。
    """

    if len(join.on) != 1:
        return False
    expected_type = "LEFT JOIN" if join.join_type.lower() == "left" else "INNER JOIN"
    actual_type = " ".join(match.group("join_type").upper().split())
    if actual_type == "JOIN":
        actual_type = "INNER JOIN"
    if actual_type != expected_type:
        return False

    joined_table = match.group("table")
    join_kind = join.join_type.lower()
    if join_kind == "left":
        # LEFT JOIN 必须从 catalog left_table 所在的已连接集合，继续连接到 right_table。
        if join.left_table not in joined_tables or joined_table != join.right_table:
            return False
    elif joined_table == join.left_table:
        if join.right_table not in joined_tables:
            return False
    elif joined_table == join.right_table:
        if join.left_table not in joined_tables:
            return False
    else:
        return False

    return _normalize_sql_expression(match.group("on")) == _normalize_sql_expression(join.on[0])


def _normalize_sql_expression(expression: str) -> str:
    """归一化受控 SQL 表达式空白，便于和 renderer/catalog 输出比对。"""

    compact = " ".join(expression.strip().split())
    compact = re.sub(r"\s*=\s*", " = ", compact)
    return compact.lower()


def _dedupe_errors(errors: list[str]) -> list[str]:
    """保持顺序去重错误码。"""

    seen: set[str] = set()
    deduped: list[str] = []
    for error in errors:
        if error not in seen:
            seen.add(error)
            deduped.append(error)
    return deduped


__all__ = ["LogisticsSqlSafetyChecker", "LogisticsSqlSafetyResult", "check_logistics_sql_safety"]

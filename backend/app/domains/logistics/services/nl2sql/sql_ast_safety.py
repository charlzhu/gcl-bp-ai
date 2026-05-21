from __future__ import annotations

from typing import Any

import sqlglot
from sqlglot import exp as sqlglot_exp

from backend.app.domains.logistics.services.nl2sql.semantic_catalog import (
    LOGISTICS_NL2SQL_ALLOWED_READ_TABLES,
    LogisticsSemanticCatalog,
    LogisticsSemanticCatalogLoader,
)
from backend.app.domains.logistics.services.nl2sql.sql_renderer import LogisticsRenderedSql

# ── 安全配置 ───────────────────────────────────────────────

# 受控聚合/条件函数白名单
_ALLOWED_FUNCTIONS = frozenset({
    "sum", "count", "avg", "min", "max",
    "case", "coalesce", "ifnull", "nullif",
})

# 危险函数黑名单（即使上层 Safety 已检查，AST 层二次 fail-closed）
# 注意：BENCHMARK 在 sqlglot 中被 parse 为 Anonymous(func_name="BENCHMARK", ...)
_FORBIDDEN_FUNCTIONS = frozenset({
    "sleep", "benchmark", "load_file", "xp_cmdshell",
    "exec", "execute", "sp_executesql",
})

# SQL 运算符（AND/OR/NOT/IN/BETWEEN/LIKE/EXISTS 等），不是真正的函数调用
_SQL_OPERATOR_FUNCS = frozenset({
    "and", "or", "not", "between", "in", "like", "is",
    "any", "all", "exists",
})


class LogisticsSqlAstSafetyResult:
    """AST 安全校验结果。"""

    def __init__(self, *, ok: bool, errors: list[str] | None = None) -> None:
        self.ok = ok
        self.errors = list(errors or [])

    @property
    def error_codes(self) -> list[str]:
        return list(self.errors)


def _collect_tables(node: sqlglot_exp.Expression) -> set[str]:
    """遍历 AST 收集 FROM 和 JOIN 中引用的表名。

    参数：
        node: SQL AST 根节点。
    返回：
        all_tables: FROM 和 JOIN 中的所有表名。
    """
    all_tables: set[str] = set()
    for subnode in node.walk():
        if isinstance(subnode, sqlglot_exp.From):
            from_ref = subnode.this
            if isinstance(from_ref, sqlglot_exp.Table):
                all_tables.add(from_ref.name)
        elif isinstance(subnode, sqlglot_exp.Join):
            join_ref = subnode.this
            if isinstance(join_ref, sqlglot_exp.Table):
                all_tables.add(join_ref.name)
    return all_tables


def _extract_function_name(node: sqlglot_exp.Func) -> str:
    """从 Func 节点提取规范化函数名。

    sqlglot 30.x 中特殊函数（BENCHMARK、LOAD_FILE 等）被 parse 为 Anonymous 类型，
    sql_name() 返回 ANONYMOUS 而不是真实函数名。需要通过检查 func_name 属性或
    Anonymous 的父节点 SQL 文本来提取真实名称。

    参数：
        node: Func 类型节点。
    返回：
        小写函数名。
    """
    if isinstance(node, sqlglot_exp.Anonymous):
        # Anonymous 节点：从父 SQL 函数调用中提取函数名
        # 例如 "BENCHMARK(1, MD5('a'))" → 提取 "benchmark"
        if hasattr(node, "this"):
            # 有些 Anonymous 版本的 this 是函数名标识符
            name = node.this.name if hasattr(node.this, "name") else str(node.this)
            return name.lower()
        # 回退：直接尝试从 sql() 提取
        sql_text = node.sql()
        paren_pos = sql_text.find("(")
        if paren_pos > 0:
            return sql_text[:paren_pos].strip().lower()
        return "anonymous"
    # 标准 Func 子类
    return node.sql_name().lower()


class LogisticsSqlAstSafetyChecker:
    """物流 NL2SQL M10-D3 SQLGlot AST 安全校验器。

    业务逻辑：
        D3 在现有 regex-based `LogisticsSqlSafetyChecker` 之后串联执行，
        利用 SQLGlot AST 解析对 SQL 进行结构级安全校验，覆盖正则无法可靠检测
        的嵌套/子查询/函数参数等形态。
    """

    def __init__(self, catalog: LogisticsSemanticCatalog | None = None, *, max_limit: int = 500) -> None:
        """初始化 AST safety checker。

        参数：
            catalog: canonical Semantic Catalog；默认加载物流 NL2SQL catalog。
            max_limit: 允许的最大 LIMIT 值。
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

    def check(self, rendered: LogisticsRenderedSql) -> LogisticsSqlAstSafetyResult:
        """对 renderer 产物进行 AST 级安全校验。

        参数：
            rendered: renderer 产出的参数化 SQL。
        返回：
            ok=True 表示 AST 结构安全；否则返回稳定错误码。
        """
        errors: list[str] = []
        sql = rendered.sql.strip()

        # 1. 尝试 parse AST
        try:
            parsed = sqlglot.parse(sql, dialect="mysql")
        except Exception:  # noqa: BLE001 - parse 失败需 fail-closed
            errors.append("sql_ast_safety_parse_failed")
            return LogisticsSqlAstSafetyResult(ok=False, errors=errors)

        # 2. 多语句检查
        if not parsed or len(parsed) > 1 or parsed[0] is None:
            errors.append("sql_ast_safety_multi_statement")
            return LogisticsSqlAstSafetyResult(ok=False, errors=errors)

        tree = parsed[0]

        # 3. 检查是否为 SELECT 或集合操作类型，拒绝 DDL/DML
        if not isinstance(tree, (sqlglot_exp.Select, sqlglot_exp.Union,
                                 sqlglot_exp.Intersect, sqlglot_exp.Except,
                                 sqlglot_exp.SetOperation)):
            # TruncateTable 特殊处理（不在标准 MRO 中）
            tree_class_name = type(tree).__name__
            stmt_names = {
                "Insert": "insert", "Update": "update", "Delete": "delete",
                "Drop": "drop", "Create": "create", "Alter": "alter",
                "Merge": "merge", "Rename": "rename", "Copy": "copy",
                "Call": "call", "TruncateTable": "truncate",
            }
            if tree_class_name in stmt_names:
                errors.append(f"sql_ast_safety_forbidden_statement::{stmt_names[tree_class_name]}")
                return LogisticsSqlAstSafetyResult(ok=False, errors=errors)
            # sqlglot 30.x 中 EXPLAIN SELECT 被 parse 为 Describe 类型
            if tree_class_name in ("Explain", "Describe"):
                errors.append("sql_ast_safety_forbidden_statement::explain")
                return LogisticsSqlAstSafetyResult(ok=False, errors=errors)
            errors.append("sql_ast_safety_not_select")
            return LogisticsSqlAstSafetyResult(ok=False, errors=errors)

        # 4. 集合操作（UNION / INTERSECT / EXCEPT）拒绝
        if isinstance(tree, (sqlglot_exp.Union, sqlglot_exp.Intersect,
                             sqlglot_exp.Except, sqlglot_exp.SetOperation)):
            errors.append("sql_ast_safety_set_operation_forbidden")
            return LogisticsSqlAstSafetyResult(ok=False, errors=errors)

        # 5. 子查询检查
        if self._has_subquery(tree):
            errors.append("sql_ast_safety_subquery_forbidden")

        # 6. LIMIT 校验（只校验已存在的 LIMIT，不强制要求必须带 LIMIT）
        limit_expr = tree.args.get("limit")
        offset_expr = tree.args.get("offset")
        if limit_expr is not None:
            if offset_expr is not None:
                errors.append("sql_ast_safety_limit_invalid")  # OFFSET 不允许
            else:
                self._check_limit_value(limit_expr, errors, rendered.params)

        # 7. SELECT * 检查
        if self._has_select_star(tree):
            errors.append("sql_ast_safety_select_star_forbidden")

        # 8. FROM 子句检查
        from_node = tree.args.get("from_")
        if from_node is None:
            errors.append("sql_ast_safety_no_from_clause")

        # 9. 函数安全
        function_errors = self._check_functions(tree)
        errors.extend(function_errors)

        # 10. 字段引用检查
        column_errors = self._check_column_references(tree)
        errors.extend(column_errors)

        # 11. GROUP BY 和 HAVING 拒绝（GROUP BY 允许，HAVING 拒绝）
        if tree.args.get("having"):
            errors.append("sql_ast_safety_having_forbidden")

        # 12. ORDER BY
        order_errors = self._check_order_by(tree)
        errors.extend(order_errors)

        # 13. 窗口函数拒绝
        if self._has_window_function(tree):
            errors.append("sql_ast_safety_window_function_forbidden")

        deduped = self._dedupe(errors)
        return LogisticsSqlAstSafetyResult(ok=not deduped, errors=deduped)

    # ── 内部校验方法 ──────────────────────────────────────

    @staticmethod
    def _has_subquery(node: sqlglot_exp.Expression) -> bool:
        """递归检查 AST 中是否存在子查询。"""
        for subnode in node.walk():
            if isinstance(subnode, sqlglot_exp.Subquery):
                return True
            if isinstance(subnode, sqlglot_exp.Exists):
                return True
            if isinstance(subnode, sqlglot_exp.In):
                # 检查 IN 的右侧是否为子查询
                in_expr = subnode.this
                if isinstance(in_expr, sqlglot_exp.Subquery):
                    return True
        return False

    @staticmethod
    def _has_select_star(node: sqlglot_exp.Select) -> bool:
        """检查 SELECT 列表中是否有 *。"""
        select_expressions = node.args.get("expressions")
        if not select_expressions:
            return False
        for expr in select_expressions:
            if isinstance(expr, sqlglot_exp.Star):
                return True
            if isinstance(expr, sqlglot_exp.Column) and isinstance(expr.this, sqlglot_exp.Star):
                return True
        return False

    def _check_limit_value(self, limit_node: sqlglot_exp.Limit, errors: list[str],
                           params: dict[str, Any]) -> None:
        """校验 LIMIT 表达式值是否在安全范围内。

        sqlglot 30.x 中 LIMIT :param 的结构为 Limit(expression=Placeholder(this=name))。
        """
        limit_value = limit_node.args.get("expression")
        if limit_value is None:
            errors.append("sql_ast_safety_limit_invalid")
            return

        if isinstance(limit_value, sqlglot_exp.Placeholder):
            # 参数化 LIMIT :param_name
            param_name = limit_value.name
            actual = params.get(param_name)
            if actual is not None:
                if not isinstance(actual, int) or actual < 0:
                    errors.append("sql_ast_safety_limit_invalid")
                elif actual > self.max_limit:
                    errors.append("sql_ast_safety_limit_out_of_range")
        elif isinstance(limit_value, sqlglot_exp.Literal):
            try:
                actual = int(limit_value.output_name)
                if actual < 0 or actual > self.max_limit:
                    errors.append("sql_ast_safety_limit_out_of_range")
            except (ValueError, TypeError):
                errors.append("sql_ast_safety_limit_invalid")
        else:
            errors.append("sql_ast_safety_limit_invalid")

    def _check_functions(self, node: sqlglot_exp.Expression) -> list[str]:
        """校验函数是否在受控白名单内或属于危险黑名单。

        sqlglot 30.x 中特殊函数（BENCHMARK 等）被 parse 为 Anonymous 类型，
        需要通过 _extract_function_name() 提取真实函数名。
        """
        errors: list[str] = []
        for subnode in node.walk():
            if not isinstance(subnode, sqlglot_exp.Func):
                continue
            func_name = _extract_function_name(subnode)

            # 跳过 SQL 运算符（AND、OR、BETWEEN、IN、LIKE 等），它们不是真正的函数调用
            if func_name in _SQL_OPERATOR_FUNCS:
                continue
            # sqlglot 把 CASE WHEN 的每个 WHEN 子句内部表示为 If 节点，
            # 这些 If 节点是 Case.ifs 的子节点，不是真正的 IF() 函数调用
            if isinstance(subnode, sqlglot_exp.If):
                # 检查 If 是否在 Case 节点内
                is_case_child = any(
                    isinstance(parent, sqlglot_exp.Case)
                    for parent in self._get_ancestors(node, subnode)
                )
                if is_case_child:
                    continue

            if func_name in _ALLOWED_FUNCTIONS:
                continue
            if func_name in _FORBIDDEN_FUNCTIONS:
                errors.append(f"sql_ast_safety_forbidden_function::{func_name}")
                continue
            # 未知函数一律拒绝
            errors.append(f"sql_ast_safety_unallowed_function::{func_name}")
        return errors

    @staticmethod
    def _get_ancestors(root: sqlglot_exp.Expression, target: sqlglot_exp.Expression) -> list[sqlglot_exp.Expression]:
        """获取 target 节点在 AST 中的祖先链（根到父）。"""
        ancestors: list[sqlglot_exp.Expression] = []

        def _walk(current: sqlglot_exp.Expression, path: list[sqlglot_exp.Expression]) -> None:
            if current is target:
                ancestors.extend(path)
                return
            for child in current.args.values():
                if isinstance(child, list):
                    for item in child:
                        if isinstance(item, sqlglot_exp.Expression):
                            _walk(item, path + [current])
                elif isinstance(child, sqlglot_exp.Expression):
                    _walk(child, path + [current])

        _walk(root, [])
        return ancestors

    def _check_column_references(self, node: sqlglot_exp.Expression) -> list[str]:
        """校验所有限定列引用（t.col）的 t 是否在 FROM/JOIN 表中。"""
        all_tables = _collect_tables(node)
        errors: list[str] = []
        for subnode in node.walk():
            if not isinstance(subnode, sqlglot_exp.Column):
                continue
            table_name = subnode.table
            if not table_name:
                continue  # 非限定列由 _check_order_by 覆盖
            if isinstance(table_name, sqlglot_exp.Identifier):
                table_name_str = table_name.name
            else:
                table_name_str = str(table_name)
            if table_name_str not in all_tables:
                errors.append(f"sql_ast_safety_column_table_mismatch::{table_name_str}.{subnode.name}")
        return errors

    def _check_order_by(self, node: sqlglot_exp.Expression) -> list[str]:
        """校验 ORDER BY 只允许限定列引用（t.col）或 SELECT 别名，不允许其他裸字段。

        renderer 产出的 ranking 类型 SQL 中 ORDER BY 使用 SELECT 列的别名
        （如 ORDER BY shipment_mw DESC），此时 `shipment_mw` 是 SELECT 列表
        中 `SUM(t.shipment_mw) AS shipment_mw` 的别名，属于合法用法。
        """
        errors: list[str] = []
        if isinstance(node, (sqlglot_exp.Union, sqlglot_exp.Intersect,
                             sqlglot_exp.Except, sqlglot_exp.SetOperation)):
            return errors
        order = node.args.get("order")
        if order is None:
            return errors

        # 收集 SELECT 列表中的别名（只有显式 AS 别名才算）
        select_aliases: set[str] = set()
        if isinstance(node, sqlglot_exp.Select):
            for expr in (node.args.get("expressions") or []):
                if isinstance(expr, sqlglot_exp.Alias):
                    select_aliases.add(expr.alias_or_name.lower())

        for expr in order.expressions:
            ordered_expr = expr.this if hasattr(expr, "this") else expr
            if isinstance(ordered_expr, sqlglot_exp.Column):
                if not ordered_expr.table:
                    bare_name = ordered_expr.name.lower()
                    if bare_name not in select_aliases:
                        errors.append(f"sql_ast_safety_bare_column_in_order_by::{ordered_expr.name}")
            elif isinstance(ordered_expr, sqlglot_exp.Literal):
                pass  # ORDER BY 1 等位置排序允许
            else:
                if hasattr(ordered_expr, "name"):
                    bare_name = ordered_expr.name.lower()
                    if bare_name not in select_aliases:
                        errors.append(f"sql_ast_safety_bare_column_in_order_by::{ordered_expr.name}")
        return errors

    @staticmethod
    def _has_window_function(node: sqlglot_exp.Expression) -> bool:
        """检查 AST 中是否存在窗口函数。"""
        for subnode in node.walk():
            if isinstance(subnode, sqlglot_exp.Window):
                return True
        return False

    @staticmethod
    def _dedupe(errors: list[str]) -> list[str]:
        """保持顺序去重错误码。"""
        seen: set[str] = set()
        deduped: list[str] = []
        for error in errors:
            if error not in seen:
                seen.add(error)
                deduped.append(error)
        return deduped


__all__ = ["LogisticsSqlAstSafetyChecker", "LogisticsSqlAstSafetyResult"]

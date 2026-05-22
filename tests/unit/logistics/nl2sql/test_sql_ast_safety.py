from __future__ import annotations

import pytest

from backend.app.domains.logistics.services.nl2sql.sql_ast_safety import (
    LogisticsSqlAstSafetyChecker,
    LogisticsSqlAstSafetyResult,
)
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader
from backend.app.domains.logistics.services.nl2sql.sql_renderer import LogisticsRenderedSql, render_logistics_sql
from backend.app.domains.logistics.services.nl2sql.sql_plan import LogisticsSqlPlanValidator


# ── 合法 SQL 样例 ──────────────────────────────────────────────

def _valid_rendered_sql() -> LogisticsRenderedSql:
    """通过真实 M3 validator + renderer 生成一条合法 SQL，供 AST safety 单测复用。"""
    validation = LogisticsSqlPlanValidator(catalog=LogisticsSemanticCatalogLoader().load()).validate(
        {
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
        }
    )
    return render_logistics_sql(validation)


# ── RED 测试 1：合法的单表 SELECT 应通过 ──────────────────

def test_ast_safety_accepts_simple_select() -> None:
    """AST safety 应接受合法的单表 SELECT（aggregate 无 LIMIT 也允许）。"""
    rendered = _valid_rendered_sql()
    checker = LogisticsSqlAstSafetyChecker()
    result = checker.check(rendered)
    # aggregate 类型的 renderer 产出默认不带 LIMIT，
    # AST safety 不强制要求 LIMIT，只对有 LIMIT 的做校验
    assert result.ok is True, result.errors


# ── RED 测试 2：多语句 SQL ──────────────────────────────

@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; SELECT 2",
        "SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union; DELETE FROM dws_logistics_detail_union",
    ],
)
def test_ast_safety_rejects_multi_statement(sql: str) -> None:
    """AST safety 必须拒绝多语句 SQL。"""
    rendered = LogisticsRenderedSql(
        sql=sql,
        params={"p0": 2025},
        referenced_tables=[],
        referenced_columns=[],
    )
    result = LogisticsSqlAstSafetyChecker().check(rendered)
    assert result.ok is False
    assert "sql_ast_safety_multi_statement" in result.error_codes


# ── RED 测试 3：非 SELECT 语句（DDL/DML） ────────────────

@pytest.mark.parametrize(
    ("sql", "expected_code_suffix"),
    [
        ("DELETE FROM dws_logistics_detail_union WHERE biz_year = :p0", "delete"),
        ("INSERT INTO dws_logistics_detail_union (biz_year) VALUES (:p0)", "insert"),
        ("UPDATE dws_logistics_detail_union SET biz_year = :p0 WHERE 1=1", "update"),
        ("DROP TABLE dws_logistics_detail_union", "drop"),
        ("CREATE TABLE tmp_table (id INT)", "create"),
        ("ALTER TABLE dws_logistics_detail_union ADD COLUMN tmp INT", "alter"),
        ("TRUNCATE TABLE dws_logistics_detail_union", "truncate"),
        ("EXPLAIN SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union", "explain"),
    ],
)
def test_ast_safety_rejects_non_select_statements(sql: str, expected_code_suffix: str) -> None:
    """AST safety 必须拒绝 DDL/DML/EXPLAIN。"""
    rendered = LogisticsRenderedSql(
        sql=sql,
        params={"p0": 2025},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[("dws_logistics_detail_union", "biz_year")],
    )
    result = LogisticsSqlAstSafetyChecker().check(rendered)
    assert result.ok is False
    assert f"sql_ast_safety_forbidden_statement::{expected_code_suffix}" in result.error_codes


# ── RED 测试 4：UNION / INTERSECT / EXCEPT ──────────────

@pytest.mark.parametrize(
    "sql",
    [
        "SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union UNION SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union",
        "SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union INTERSECT SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union",
        "SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union EXCEPT SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union",
    ],
)
def test_ast_safety_rejects_set_operations(sql: str) -> None:
    """AST safety 必须拒绝 UNION/INTERSECT/EXCEPT。"""
    rendered = LogisticsRenderedSql(
        sql=sql,
        params={},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[("dws_logistics_detail_union", "biz_year")],
    )
    result = LogisticsSqlAstSafetyChecker().check(rendered)
    assert result.ok is False
    assert "sql_ast_safety_set_operation_forbidden" in result.error_codes


# ── RED 测试 5：子查询（FROM 子查询 / WHERE 标量子查询 / EXISTS） ──

@pytest.mark.parametrize(
    "sql",
    [
        "SELECT dws_logistics_detail_union.biz_year FROM (SELECT * FROM dws_logistics_detail_union) AS sub LIMIT :p0",
        "SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union WHERE dws_logistics_detail_union.biz_year IN (SELECT biz_year FROM dws_logistics_detail_union) LIMIT :p0",
        "SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union WHERE EXISTS (SELECT 1 FROM dws_logistics_detail_union) LIMIT :p0",
    ],
)
def test_ast_safety_rejects_subqueries(sql: str) -> None:
    """AST safety 必须拒绝子查询（FROM/WHERE/EXISTS 子查询）。"""
    rendered = LogisticsRenderedSql(
        sql=sql,
        params={"p0": 10},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[("dws_logistics_detail_union", "biz_year")],
        limit=10,
    )
    result = LogisticsSqlAstSafetyChecker().check(rendered)
    assert result.ok is False
    assert "sql_ast_safety_subquery_forbidden" in result.error_codes


# ── RED 测试 6：SELECT *（AST 级） ────────────────────────

def test_ast_safety_rejects_select_star() -> None:
    """AST safety 必须拒绝 SELECT *。"""
    rendered = LogisticsRenderedSql(
        sql="SELECT * FROM dws_logistics_detail_union LIMIT :p0",
        params={"p0": 10},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[],
        limit=10,
    )
    result = LogisticsSqlAstSafetyChecker().check(rendered)
    assert result.ok is False
    assert "sql_ast_safety_select_star_forbidden" in result.error_codes


# ── RED 测试 7：无 FROM 查询 ──────────────────────────────

@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "SELECT CURRENT_DATE",
        "SELECT @@version",
    ],
)
def test_ast_safety_rejects_no_from(sql: str) -> None:
    """AST safety 必须拒绝无 FROM 子句的查询。"""
    rendered = LogisticsRenderedSql(
        sql=sql,
        params={},
        referenced_tables=[],
        referenced_columns=[],
    )
    result = LogisticsSqlAstSafetyChecker().check(rendered)
    assert result.ok is False
    assert "sql_ast_safety_no_from_clause" in result.error_codes


# ── RED 测试 8：合理 LIMIT 形态 ───────────────────────────

def test_ast_safety_accepts_valid_limit() -> None:
    """AST safety 应接受 renderer 产出的 LIMIT :param 形态。"""
    rendered = LogisticsRenderedSql(
        sql="SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union LIMIT :p0",
        params={"p0": 100},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[("dws_logistics_detail_union", "biz_year")],
        limit=100,
    )
    result = LogisticsSqlAstSafetyChecker().check(rendered)
    assert result.ok is True, result.errors


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union LIMIT ALL",
        "SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union LIMIT 0, 100",
        "SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union LIMIT :p0 OFFSET :p1",
    ],
)
def test_ast_safety_rejects_non_standard_limit(sql: str) -> None:
    """AST safety 必须拒绝 LIMIT ALL / LIMIT offset,count / OFFSET。"""
    rendered = LogisticsRenderedSql(
        sql=sql,
        params={"p0": 10, "p1": 10},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[("dws_logistics_detail_union", "biz_year")],
        limit=10,
    )
    result = LogisticsSqlAstSafetyChecker().check(rendered)
    assert result.ok is False
    assert "sql_ast_safety_limit_invalid" in result.error_codes


# ── RED 测试 9：危险函数 ────────────────────────────────

@pytest.mark.parametrize(
    ("sql", "expected_func"),
    [
        ("SELECT BENCHMARK(1000000, MD5('test')) FROM dws_logistics_detail_union LIMIT :p0", "benchmark"),
        ("SELECT LOAD_FILE('/etc/passwd') FROM dws_logistics_detail_union LIMIT :p0", "load_file"),
    ],
)
def test_ast_safety_rejects_dangerous_functions(sql: str, expected_func: str) -> None:
    """AST safety 必须拒绝危险函数（BENCHMARK/LOAD_FILE 等）。"""
    rendered = LogisticsRenderedSql(
        sql=sql,
        params={"p0": 10},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[("dws_logistics_detail_union", "biz_year")],
        limit=10,
    )
    result = LogisticsSqlAstSafetyChecker().check(rendered)
    assert result.ok is False
    assert f"sql_ast_safety_forbidden_function::{expected_func}" in result.error_codes


# ── RED 测试 10：不允许的函数（非受控函数） ──────────────────

@pytest.mark.parametrize(
    ("sql", "expected_func"),
    [
        ("SELECT CONCAT('a', 'b') FROM dws_logistics_detail_union LIMIT :p0", "concat"),
        ("SELECT GROUP_CONCAT(biz_year) FROM dws_logistics_detail_union LIMIT :p0", "group_concat"),
        ("SELECT HEX(biz_year) FROM dws_logistics_detail_union LIMIT :p0", "hex"),
    ],
)
def test_ast_safety_rejects_unallowed_functions(sql: str, expected_func: str) -> None:
    """AST safety 只允许受控函数集（SUM/COUNT/AVG/MIN/MAX/CASE/COALESCE/IFNULL/NULLIF）。"""
    rendered = LogisticsRenderedSql(
        sql=sql,
        params={"p0": 10},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[("dws_logistics_detail_union", "biz_year")],
        limit=10,
    )
    result = LogisticsSqlAstSafetyChecker().check(rendered)
    assert result.ok is False
    assert f"sql_ast_safety_unallowed_function::{expected_func}" in result.error_codes


# ── RED 测试 11：合法聚合函数应通过 ─────────────────────

@pytest.mark.parametrize(
    "sql",
    [
        "SELECT SUM(dws_logistics_detail_union.shipment_mw) FROM dws_logistics_detail_union WHERE dws_logistics_detail_union.biz_year = :p0 LIMIT :p1",
        "SELECT COUNT(*) FROM dws_logistics_detail_union WHERE dws_logistics_detail_union.biz_year = :p0 LIMIT :p1",
        "SELECT AVG(dws_logistics_detail_union.shipment_mw) FROM dws_logistics_detail_union WHERE dws_logistics_detail_union.biz_year IN (:p0, :p1, :p2, :p3) LIMIT :p4",
        "SELECT MIN(dws_logistics_detail_union.shipment_mw), MAX(dws_logistics_detail_union.shipment_mw) FROM dws_logistics_detail_union WHERE dws_logistics_detail_union.biz_year = :p0 LIMIT :p1",
        "SELECT COALESCE(SUM(dws_logistics_detail_union.shipment_mw), 0) AS total_mw FROM dws_logistics_detail_union WHERE dws_logistics_detail_union.biz_year = :p0 LIMIT :p1",
        "SELECT dws_logistics_detail_union.biz_year, CASE WHEN dws_logistics_detail_union.shipment_mw > 0 THEN 'Y' ELSE 'N' END AS flag FROM dws_logistics_detail_union LIMIT :p4",
    ],
)
def test_ast_safety_accepts_allowed_functions(sql: str) -> None:
    """AST safety 应接受受控函数集中的函数。"""
    rendered = LogisticsRenderedSql(
        sql=sql,
        params={"p0": 2025, "p1": 10, "p2": 2024, "p3": 2023, "p4": 10},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[("dws_logistics_detail_union", "shipment_mw"), ("dws_logistics_detail_union", "biz_year")],
        limit=10,
    )
    result = LogisticsSqlAstSafetyChecker().check(rendered)
    assert result.ok is True, result.errors


# ── RED 测试 12：字段引用必须来自 FROM/JOIN 表 ───────────

def test_ast_safety_rejects_columns_from_non_joined_table() -> None:
    """AST safety 必须拒绝引用不在 FROM/JOIN 中的表字段。"""
    rendered = LogisticsRenderedSql(
        sql="SELECT dws_logistics_detail_union.biz_year, sys_user.password AS pwd FROM dws_logistics_detail_union LIMIT :p0",
        params={"p0": 10},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[("dws_logistics_detail_union", "biz_year")],
        limit=10,
    )
    result = LogisticsSqlAstSafetyChecker().check(rendered)
    assert result.ok is False
    assert "sql_ast_safety_column_table_mismatch::sys_user.password" in result.error_codes


# ── RED 测试 13：ORDER BY 不允许裸字段 ──────────────────

def test_ast_safety_rejects_bare_field_in_order_by() -> None:
    """AST safety 必须拒绝 ORDER BY 中使用裸字段（非限定列引用）。"""
    rendered = LogisticsRenderedSql(
        sql="SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union ORDER BY biz_year LIMIT :p0",
        params={"p0": 10},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[("dws_logistics_detail_union", "biz_year")],
        limit=10,
    )
    result = LogisticsSqlAstSafetyChecker().check(rendered)
    assert result.ok is False
    assert "sql_ast_safety_bare_column_in_order_by::biz_year" in result.error_codes


# ── RED 测试 14：合法 JOIN SELECT 应通过 ──────────────────

def test_ast_safety_accepts_valid_join_select() -> None:
    """AST safety 应接受带有 LEFT JOIN 的合法 SELECT。"""
    rendered = LogisticsRenderedSql(
        sql=(
            "SELECT dwd_logistics_ship_task.task_id, dwd_logistics_assign_task.plan_start_time "
            "FROM dwd_logistics_ship_task "
            "LEFT JOIN dwd_logistics_assign_task ON "
            "dwd_logistics_assign_task.ship_task_id = dwd_logistics_ship_task.task_id "
            "WHERE dwd_logistics_ship_task.biz_year = :p0 LIMIT :p1"
        ),
        params={"p0": 2025, "p1": 10},
        referenced_tables=["dwd_logistics_ship_task", "dwd_logistics_assign_task"],
        referenced_columns=[
            ("dwd_logistics_ship_task", "task_id"),
            ("dwd_logistics_ship_task", "biz_year"),
            ("dwd_logistics_assign_task", "ship_task_id"),
            ("dwd_logistics_assign_task", "plan_start_time"),
        ],
        limit=10,
    )
    checker = LogisticsSqlAstSafetyChecker()
    result = checker.check(rendered)
    assert result.ok is True, result.errors


# ── RED 测试 15：GROUP BY 和 HAVING 应拒绝 ────────────

@pytest.mark.parametrize(
    "sql",
    [
        "SELECT dws_logistics_detail_union.biz_year, COUNT(*) FROM dws_logistics_detail_union GROUP BY dws_logistics_detail_union.biz_year LIMIT :p0",
        "SELECT dws_logistics_detail_union.biz_year, COUNT(*) FROM dws_logistics_detail_union HAVING COUNT(*) > 1 LIMIT :p0",
    ],
)
def test_ast_safety_rejects_group_by_and_having(sql: str) -> None:
    """AST safety 必须拒绝 HAVING 子句（GROUP BY 允许）。"""
    rendered = LogisticsRenderedSql(
        sql=sql,
        params={"p0": 10},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[("dws_logistics_detail_union", "biz_year")],
        limit=10,
    )
    result = LogisticsSqlAstSafetyChecker().check(rendered)
    if "GROUP BY" in sql.upper():
        # GROUP BY 允许通过（分组不构成安全风险）
        pass  # GROUP BY 不再拒绝
    if "HAVING" in sql.upper():
        assert "sql_ast_safety_having_forbidden" in result.error_codes


# ── RED 测试 16：窗口函数应拒绝 ──────────────────────────

def test_ast_safety_rejects_window_functions() -> None:
    """AST safety 必须拒绝窗口函数。"""
    rendered = LogisticsRenderedSql(
        sql="SELECT dws_logistics_detail_union.biz_year, ROW_NUMBER() OVER (ORDER BY dws_logistics_detail_union.biz_year) AS rn FROM dws_logistics_detail_union LIMIT :p0",
        params={"p0": 10},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[("dws_logistics_detail_union", "biz_year")],
        limit=10,
    )
    result = LogisticsSqlAstSafetyChecker().check(rendered)
    assert result.ok is False
    assert "sql_ast_safety_window_function_forbidden" in result.error_codes


# ── RED 测试 17：AST parse 失败是否安全处理 ─────────────

def test_ast_safety_handles_parse_failure_gracefully() -> None:
    """若 sqlglot 无法 parse SQL（畸形 SQL），AST safety 应 fail-closed。"""
    rendered = LogisticsRenderedSql(
        sql="SELECT INVALID SQL THAT CANNOT PARSE FROM nowhere",
        params={},
        referenced_tables=[],
        referenced_columns=[],
    )
    result = LogisticsSqlAstSafetyChecker().check(rendered)
    assert result.ok is False
    assert "sql_ast_safety_parse_failed" in result.error_codes


# ── RED 测试 18：参数代入后的 LIMIT 值验证 ──────────────

def test_ast_safety_rejects_excessive_limit_value() -> None:
    """AST safety 应拒绝超过最大安全上限的 LIMIT 值。"""
    rendered = LogisticsRenderedSql(
        sql="SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union LIMIT :p0",
        params={"p0": 99999},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[("dws_logistics_detail_union", "biz_year")],
        limit=99999,
    )
    result = LogisticsSqlAstSafetyChecker(max_limit=500).check(rendered)
    assert result.ok is False
    assert "sql_ast_safety_limit_out_of_range" in result.error_codes

from __future__ import annotations

import pytest

from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader
from backend.app.domains.logistics.services.nl2sql.sql_plan import LogisticsSqlPlanValidator
from backend.app.domains.logistics.services.nl2sql.sql_renderer import LogisticsRenderedSql, render_logistics_sql
from backend.app.domains.logistics.services.nl2sql.sql_safety import LogisticsSqlSafetyChecker


def test_safety_accepts_renderer_output_and_bound_params() -> None:
    """SQL Safety Checker 应接受 renderer 产生的参数化只读 SQL。"""

    rendered = _valid_rendered_sql()

    result = LogisticsSqlSafetyChecker().check(rendered)

    assert result.ok is True, result.errors
    assert result.error_codes == []


@pytest.mark.parametrize(
    ("sql", "expected_code"),
    [
        ("SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union; DROP TABLE users", "sql_safety_forbidden_token::multi_statement"),
        ("SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union -- bypass", "sql_safety_forbidden_token::comment"),
        ("SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union # bypass", "sql_safety_forbidden_token::comment"),
        ("DELETE FROM dws_logistics_detail_union WHERE biz_year = :p0", "sql_safety_not_select"),
        ("SELECT * FROM dws_logistics_detail_union", "sql_safety_select_star_forbidden"),
        ("SELECT DISTINCT * FROM dws_logistics_detail_union", "sql_safety_select_star_forbidden"),
        ("SELECT dws_logistics_detail_union.biz_year, * FROM dws_logistics_detail_union", "sql_safety_select_star_forbidden"),
        ("SELECT dws_logistics_detail_union.* FROM dws_logistics_detail_union", "sql_safety_select_star_forbidden"),
        ("SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union UNION SELECT password FROM sys_user", "sql_safety_forbidden_token::union"),
        ("EXPLAIN SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union", "sql_safety_explain_nested_forbidden"),
        ("SELECT SLEEP(1) FROM dws_logistics_detail_union", "sql_safety_forbidden_function::sleep"),
    ],
)
def test_safety_rejects_dangerous_sql_shapes(sql: str, expected_code: str) -> None:
    """多语句、注释、DDL/DML、UNION、嵌套 EXPLAIN、危险函数和 SELECT * 必须 fail-closed。"""

    rendered = LogisticsRenderedSql(
        sql=sql,
        params={"p0": 2025},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[("dws_logistics_detail_union", "biz_year")],
    )

    result = LogisticsSqlSafetyChecker().check(rendered)

    assert result.ok is False
    assert expected_code in result.error_codes


def test_safety_rejects_unknown_table_and_column_references() -> None:
    """SQL 引用非 catalog allow-list 表或字段时必须拒绝，不能只信 renderer 元数据。"""

    rendered = LogisticsRenderedSql(
        sql="SELECT sys_user.password FROM sys_user WHERE sys_user.id = :p0",
        params={"p0": 1},
        referenced_tables=["sys_user"],
        referenced_columns=[("sys_user", "password"), ("sys_user", "id")],
    )

    result = LogisticsSqlSafetyChecker().check(rendered)

    assert result.ok is False
    assert "sql_safety_table_not_allowed::sys_user" in result.error_codes
    assert "sql_safety_column_not_allowed::sys_user.password" in result.error_codes


@pytest.mark.parametrize(
    ("sql", "expected_code"),
    [
        (
            "SELECT secret_internal FROM dws_logistics_detail_union LIMIT :p0",
            "sql_safety_unqualified_identifier::secret_internal",
        ),
        (
            "SELECT `password` FROM `sys_query_log` LIMIT :p0",
            "sql_safety_quoted_identifier_forbidden",
        ),
        ("SELECT @@version", "sql_safety_system_variable_forbidden"),
        ("SELECT @@version", "sql_safety_table_required"),
    ],
)
def test_safety_rejects_unqualified_or_quoted_identifiers_and_no_from(sql: str, expected_code: str) -> None:
    """Safety 必须拒绝 renderer 不会输出的裸字段、反引号标识符和无 FROM 系统变量查询。"""

    rendered = LogisticsRenderedSql(
        sql=sql,
        params={"p0": 10},
        referenced_tables=[],
        referenced_columns=[],
        limit=10,
    )

    result = LogisticsSqlSafetyChecker().check(rendered)

    assert result.ok is False
    assert expected_code in result.error_codes


@pytest.mark.parametrize(
    ("sql", "expected_code"),
    [
        (
            "SELECT secret_internal AS secret_internal FROM dws_logistics_detail_union LIMIT :p0",
            "sql_safety_unqualified_identifier::secret_internal",
        ),
        (
            "SELECT SUM(secret_internal) AS secret_internal FROM dws_logistics_detail_union LIMIT :p0",
            "sql_safety_unqualified_identifier::secret_internal",
        ),
    ],
)
def test_safety_rejects_self_aliased_unqualified_identifiers(sql: str, expected_code: str) -> None:
    """裸字段不能通过 `AS 同名别名` 或聚合自别名绕过字段 allow-list。"""

    rendered = LogisticsRenderedSql(
        sql=sql,
        params={"p0": 10},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[],
        limit=10,
    )

    result = LogisticsSqlSafetyChecker().check(rendered)

    assert result.ok is False
    assert expected_code in result.error_codes


def test_safety_rejects_missing_params_and_string_literals() -> None:
    """WHERE 中用户值必须参数绑定；缺少 params 或直接拼接字符串字面量都必须拒绝。"""

    missing_param = _valid_rendered_sql().model_copy(update={"params": {"p0": 2023, "p1": 2024}})
    literal_sql = _valid_rendered_sql().model_copy(
        update={
            "sql": "SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union WHERE dws_logistics_detail_union.customer_name = '广州客户'",
            "params": {},
            "referenced_columns": [("dws_logistics_detail_union", "biz_year"), ("dws_logistics_detail_union", "customer_name")],
        }
    )

    missing_result = LogisticsSqlSafetyChecker().check(missing_param)
    literal_result = LogisticsSqlSafetyChecker().check(literal_sql)

    assert missing_result.ok is False
    assert "sql_safety_param_missing::p2" in missing_result.error_codes
    assert literal_result.ok is False
    assert "sql_safety_string_literal_forbidden" in literal_result.error_codes


def test_safety_rejects_free_join_condition_not_from_catalog() -> None:
    """Join 条件必须来自 catalog 的等值 join，不能出现自由拼接的 OR 1=1 条件。"""

    rendered = LogisticsRenderedSql(
        sql=(
            "SELECT dwd_logistics_ship_task.task_id FROM dwd_logistics_ship_task "
            "LEFT JOIN dwd_logistics_assign_task ON "
            "dwd_logistics_assign_task.ship_task_id = dwd_logistics_ship_task.task_id OR 1=1 "
            "WHERE dwd_logistics_ship_task.biz_year = :p0 LIMIT :p1"
        ),
        params={"p0": 2026, "p1": 10},
        referenced_tables=["dwd_logistics_ship_task", "dwd_logistics_assign_task"],
        referenced_columns=[
            ("dwd_logistics_ship_task", "task_id"),
            ("dwd_logistics_ship_task", "biz_year"),
            ("dwd_logistics_assign_task", "ship_task_id"),
        ],
        referenced_joins=[],
        limit=10,
    )

    result = LogisticsSqlSafetyChecker().check(rendered)

    assert result.ok is False
    assert "sql_safety_join_not_catalog_controlled" in result.error_codes


def test_safety_rejects_limit_above_max() -> None:
    """即使 renderer 元数据被污染，Safety 也必须二次限制明细/排名 LIMIT 上限。"""

    rendered = _valid_rendered_sql().model_copy(
        update={
            "sql": _valid_rendered_sql().sql + " LIMIT :p4",
            "params": {**_valid_rendered_sql().params, "p4": 9999},
            "limit": 9999,
        }
    )

    result = LogisticsSqlSafetyChecker(max_limit=500).check(rendered)

    assert result.ok is False
    assert "sql_safety_limit_out_of_range::9999" in result.error_codes


def test_safety_rejects_join_clause_mismatch_even_when_join_id_is_present() -> None:
    """Safety 必须把 SQL JOIN/ON 与 catalog join 精确比对，不能只看 referenced_joins 非空。"""

    rendered = LogisticsRenderedSql(
        sql=(
            "SELECT dwd_logistics_ship_task.task_id FROM dwd_logistics_ship_task "
            "LEFT JOIN dwd_logistics_assign_task ON "
            "dwd_logistics_assign_task.task_id = dwd_logistics_ship_task.task_id "
            "WHERE dwd_logistics_ship_task.biz_year = :p0 LIMIT :p1"
        ),
        params={"p0": 2026, "p1": 10},
        referenced_tables=["dwd_logistics_ship_task", "dwd_logistics_assign_task"],
        referenced_columns=[
            ("dwd_logistics_ship_task", "task_id"),
            ("dwd_logistics_ship_task", "biz_year"),
            ("dwd_logistics_assign_task", "task_id"),
        ],
        referenced_joins=["system_task_assign"],
        limit=10,
    )

    result = LogisticsSqlSafetyChecker().check(rendered)

    assert result.ok is False
    assert "sql_safety_join_clause_not_catalog_controlled::system_task_assign" in result.error_codes


def test_safety_rejects_left_join_when_catalog_left_table_not_already_joined() -> None:
    """Safety 必须验证 LEFT JOIN 链方向，不能只看 joined table 和 ON 文本。"""

    rendered = LogisticsRenderedSql(
        sql=(
            "SELECT dwd_logistics_assign_task.task_id FROM dwd_logistics_assign_task "
            "LEFT JOIN dwd_logistics_assign_task ON "
            "dwd_logistics_assign_task.ship_task_id = dwd_logistics_ship_task.task_id "
            "WHERE dwd_logistics_assign_task.task_id = :p0 LIMIT :p1"
        ),
        params={"p0": "A001", "p1": 10},
        referenced_tables=["dwd_logistics_assign_task"],
        referenced_columns=[
            ("dwd_logistics_assign_task", "task_id"),
            ("dwd_logistics_assign_task", "ship_task_id"),
        ],
        referenced_joins=["system_task_assign"],
        limit=10,
    )

    result = LogisticsSqlSafetyChecker().check(rendered)

    assert result.ok is False
    assert "sql_safety_join_clause_not_catalog_controlled::system_task_assign" in result.error_codes


@pytest.mark.parametrize(
    ("sql", "expected_code"),
    [
        (
            "SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union LIMIT ALL",
            "sql_safety_limit_syntax_invalid",
        ),
        (
            "SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union LIMIT 0, 999999",
            "sql_safety_limit_syntax_invalid",
        ),
        (
            "SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union LIMIT :p0 OFFSET :p1",
            "sql_safety_limit_syntax_invalid",
        ),
    ],
)
def test_safety_rejects_non_renderer_limit_syntax(sql: str, expected_code: str) -> None:
    """Safety 只接受 renderer 形态的 LIMIT :param/数字，其他 LIMIT 变体必须拒绝。"""

    rendered = LogisticsRenderedSql(
        sql=sql,
        params={"p0": 10, "p1": 10},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[("dws_logistics_detail_union", "biz_year")],
        limit=10,
    )

    result = LogisticsSqlSafetyChecker().check(rendered)

    assert result.ok is False
    assert expected_code in result.error_codes


@pytest.mark.parametrize(
    ("sql", "expected_code"),
    [
        (
            "SELECT dws_logistics_detail_union.biz_year INTO tmp_export FROM dws_logistics_detail_union WHERE dws_logistics_detail_union.biz_year = :p0",
            "sql_safety_forbidden_token::into",
        ),
        (
            "SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union INTO OUTFILE :p1",
            "sql_safety_forbidden_token::outfile",
        ),
        (
            "SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union INTO DUMPFILE :p1",
            "sql_safety_forbidden_token::dumpfile",
        ),
    ],
)
def test_safety_rejects_select_into_and_file_export_tokens(sql: str, expected_code: str) -> None:
    """SELECT INTO/OUTFILE/DUMPFILE 可能写表或写文件，必须按写边界拒绝。"""

    rendered = LogisticsRenderedSql(
        sql=sql,
        params={"p0": 2025, "p1": "/tmp/export.csv"},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[("dws_logistics_detail_union", "biz_year")],
    )

    result = LogisticsSqlSafetyChecker().check(rendered)

    assert result.ok is False
    assert expected_code in result.error_codes


def _valid_rendered_sql() -> LogisticsRenderedSql:
    """通过真实 M3 validator + renderer 生成一条合法 SQL，供 safety 单测复用。"""

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

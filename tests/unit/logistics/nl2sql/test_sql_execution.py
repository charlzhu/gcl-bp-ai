from __future__ import annotations

from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader
from backend.app.domains.logistics.services.nl2sql.sql_execution import (
    FakeLogisticsSqlExecutor,
    LogisticsSqlExecutionService,
)
from backend.app.domains.logistics.services.nl2sql.sql_plan import LogisticsSqlPlanValidator
from backend.app.domains.logistics.services.nl2sql.sql_renderer import LogisticsRenderedSql, render_logistics_sql


def test_explain_uses_safety_passed_sql_and_passes_bound_params() -> None:
    """EXPLAIN 只接受 safety passed SQL，并把参数绑定原样传给 executor。"""

    rendered = _aggregate_rendered_sql()
    executor = FakeLogisticsSqlExecutor(explain_rows=[{"select_type": "SIMPLE"}])
    service = LogisticsSqlExecutionService(executor=executor)

    result = service.explain(rendered)

    assert result.ok is True, result.error
    assert result.rows == [{"select_type": "SIMPLE"}]
    assert len(executor.calls) == 1
    assert executor.calls[0].mode == "explain"
    assert executor.calls[0].sql.startswith("EXPLAIN SELECT ")
    assert executor.calls[0].params == rendered.params


def test_trial_appends_limit_zero_for_unlimited_aggregate() -> None:
    """trial execution 对 aggregate 这类无限 SQL 默认追加 LIMIT 0，避免全表返回。"""

    rendered = _aggregate_rendered_sql()
    executor = FakeLogisticsSqlExecutor(trial_rows=[])
    service = LogisticsSqlExecutionService(executor=executor)

    result = service.trial(rendered)

    assert result.ok is True, result.error
    assert len(executor.calls) == 1
    assert executor.calls[0].mode == "trial"
    assert executor.calls[0].sql.endswith(" LIMIT :__trial_limit")
    assert executor.calls[0].params["__trial_limit"] == 0


def test_safety_failure_skips_executor() -> None:
    """Safety 失败时不得调用 executor，避免危险 SQL 进入 EXPLAIN/试执行层。"""

    unsafe = LogisticsRenderedSql(
        sql="SELECT dws_logistics_detail_union.biz_year, * FROM dws_logistics_detail_union WHERE dws_logistics_detail_union.biz_year = :p0",
        params={"p0": 2025},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[("dws_logistics_detail_union", "biz_year")],
    )
    executor = FakeLogisticsSqlExecutor()
    service = LogisticsSqlExecutionService(executor=executor)

    result = service.trial(unsafe)

    assert result.ok is False
    assert "sql_safety_select_star_forbidden" in result.error_codes
    assert executor.calls == []


def test_explain_safety_failure_skips_executor() -> None:
    """EXPLAIN 同样必须在 safety 失败时跳过 executor。"""

    unsafe = LogisticsRenderedSql(
        sql="SELECT secret_internal AS secret_internal FROM dws_logistics_detail_union LIMIT :p0",
        params={"p0": 10},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[],
        limit=10,
    )
    executor = FakeLogisticsSqlExecutor()
    service = LogisticsSqlExecutionService(executor=executor)

    result = service.explain(unsafe)

    assert result.ok is False
    assert "sql_safety_unqualified_identifier::secret_internal" in result.error_codes
    assert executor.calls == []


def test_trial_rejects_uncontrolled_limit_syntax_before_executor() -> None:
    """trial 不能因 SQL 中出现任意 LIMIT token 就绕过安全限行校验。"""

    unsafe = LogisticsRenderedSql(
        sql="SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union LIMIT 0, 999999",
        params={},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[("dws_logistics_detail_union", "biz_year")],
        limit=10,
    )
    executor = FakeLogisticsSqlExecutor()
    service = LogisticsSqlExecutionService(executor=executor)

    result = service.trial(unsafe)

    assert result.ok is False
    assert "sql_safety_limit_syntax_invalid" in result.error_codes
    assert executor.calls == []


def test_executor_exception_is_sanitized() -> None:
    """executor 异常返回必须脱敏，不泄露 password/token/DSN。"""

    rendered = _aggregate_rendered_sql()
    executor = FakeLogisticsSqlExecutor(
        raise_message="mysql://user:secretpass@localhost/db password=abc123 token=tok_abcdef api_key=key_123 Bearer bearer_secret sk-abcdef123456"
    )
    service = LogisticsSqlExecutionService(executor=executor)

    result = service.explain(rendered)

    assert result.ok is False
    assert result.error is not None
    assert "secretpass" not in result.error
    assert "abc123" not in result.error
    assert "tok_abcdef" not in result.error
    assert "key_123" not in result.error
    assert "bearer_secret" not in result.error
    assert "sk-abcdef123456" not in result.error
    assert "[REDACTED]" in result.error


def _aggregate_rendered_sql() -> LogisticsRenderedSql:
    """生成一条 M3+M4 通过的 aggregate SQL。"""

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

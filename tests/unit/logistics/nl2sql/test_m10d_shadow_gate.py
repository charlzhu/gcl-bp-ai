from __future__ import annotations

from typing import Any

from backend.app.domains.logistics.services.nl2sql.m10d_shadow_gate import (
    LogisticsNl2SqlM10DShadowGate,
    LogisticsNl2SqlM10DShadowGateConfig,
)
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader
from backend.app.domains.logistics.services.nl2sql.sql_execution import FakeLogisticsSqlExecutor
from backend.app.domains.logistics.services.nl2sql.sql_plan import LogisticsSqlPlanValidator
from backend.app.domains.logistics.services.nl2sql.sql_renderer import LogisticsRenderedSql, render_logistics_sql


class _ForbiddenExecutorFactory:
    """默认关闭测试用 executor 工厂：若被调用则说明 gate 没有做到懒加载。"""

    def __call__(self) -> FakeLogisticsSqlExecutor:
        """默认关闭时不允许构造任何 executor，避免未来误连真实库。"""

        raise AssertionError("M10-D 默认关闭时不应构造 executor")


def test_m10d_gate_default_disabled_does_not_build_executor_or_hash_sql() -> None:
    """M10-D gate 默认关闭时应返回 disabled 摘要，不构造 executor，也不记录 SQL hash。"""

    gate = LogisticsNl2SqlM10DShadowGate(
        config=LogisticsNl2SqlM10DShadowGateConfig(),
        executor_factory=_ForbiddenExecutorFactory(),
    )

    report = gate.run(rendered_sql=_safe_rendered_sql())
    payload = report.model_dump_json()

    assert report.schema_version == "logistics_nl2sql_m10d_shadow_gate.v1"
    assert report.enabled is False
    assert report.shadow_only is True
    assert report.status == "disabled"
    assert report.stage == "disabled"
    assert report.explain_status == "disabled"
    assert report.trial_status == "disabled"
    assert report.sql_hash is None
    assert report.error_codes == ["m10d_shadow_gate_disabled"]
    assert "SELECT " not in payload
    assert "dws_logistics_detail_union" not in payload
    assert "2025" not in payload


def test_m10d_gate_explain_success_uses_fake_executor_and_redacted_schema() -> None:
    """显式开启 EXPLAIN 时只返回脱敏 schema，不输出 SQL、表名、字段名或参数值。"""

    executor = FakeLogisticsSqlExecutor(explain_rows=[{"select_type": "SIMPLE", "table": "secret_table"}])
    gate = LogisticsNl2SqlM10DShadowGate(
        config=LogisticsNl2SqlM10DShadowGateConfig(enabled=True, explain_enabled=True, trial_enabled=False),
        executor_factory=lambda: executor,
    )

    report = gate.run(rendered_sql=_safe_rendered_sql(), candidate_gate_reason_code="allowed")
    payload = report.model_dump_json()

    assert report.enabled is True
    assert report.status == "success"
    assert report.stage == "explain"
    assert report.explain_status == "success"
    assert report.trial_status == "disabled"
    assert report.row_count == 0
    assert report.row_cap_applied is False
    assert report.timeout_ms == 1000
    assert report.sql_hash is not None and len(report.sql_hash) == 64
    assert report.candidate_gate_reason_code == "allowed"
    assert [call.mode for call in executor.calls] == ["explain"]
    assert "SELECT " not in payload
    assert "dws_logistics_detail_union" not in payload
    assert "shipment_mw" not in payload
    assert "secret_table" not in payload
    assert "2025" not in payload


def test_m10d_gate_trial_success_caps_rows_without_returning_values() -> None:
    """trial 成功时只能返回行数和 row cap 摘要，不能回传任何业务行值。"""

    executor = FakeLogisticsSqlExecutor(
        explain_rows=[{"select_type": "SIMPLE"}],
        trial_rows=[
            {"logistics_company_name": "承运商A", "shipment_mw": 10},
            {"logistics_company_name": "承运商B", "shipment_mw": 20},
            {"logistics_company_name": "承运商C", "shipment_mw": 30},
        ],
    )
    gate = LogisticsNl2SqlM10DShadowGate(
        config=LogisticsNl2SqlM10DShadowGateConfig(
            enabled=True,
            explain_enabled=True,
            trial_enabled=True,
            row_cap=2,
            timeout_ms=800,
        ),
        executor_factory=lambda: executor,
    )

    report = gate.run(rendered_sql=_safe_rendered_sql())
    payload = report.model_dump_json()

    assert report.status == "success"
    assert report.stage == "trial"
    assert report.explain_status == "success"
    assert report.trial_status == "success"
    assert report.row_count == 2
    assert report.row_cap_applied is True
    assert report.timeout_ms == 800
    assert [call.mode for call in executor.calls] == ["explain", "trial"]
    assert "承运商A" not in payload
    assert "承运商B" not in payload
    assert "承运商C" not in payload
    assert "shipment_mw" not in payload


def test_m10d_gate_explain_failure_fail_closed_and_skips_trial_with_redacted_report() -> None:
    """EXPLAIN 失败必须 fail-closed，跳过 trial，报告只保留稳定错误码。"""

    executor = FakeLogisticsSqlExecutor(
        raise_message=(
            "EXPLAIN SELECT password=unit-secret token=tok_unitsecret "
            "FROM dws_logistics_detail_union mysql://user:secretpass@127.0.0.1/db"
        )
    )
    gate = LogisticsNl2SqlM10DShadowGate(
        config=LogisticsNl2SqlM10DShadowGateConfig(enabled=True, explain_enabled=True, trial_enabled=True),
        executor_factory=lambda: executor,
    )

    report = gate.run(rendered_sql=_safe_rendered_sql())
    payload = report.model_dump_json()

    assert report.status == "failed"
    assert report.stage == "explain"
    assert report.explain_status == "failed"
    assert report.trial_status == "skipped"
    assert "m10d_explain_failed" in report.error_codes
    assert [call.mode for call in executor.calls] == ["explain"]
    assert "unit-secret" not in payload
    assert "tok_unitsecret" not in payload
    assert "secretpass" not in payload
    assert "SELECT" not in payload
    assert "dws_logistics_detail_union" not in payload


def test_m10d_gate_rejects_non_middle_db_source_before_executor() -> None:
    """M10-D 只允许智能助手中间库；sap_mid/oracle 等来源必须在 executor 前跳过。"""

    executor = FakeLogisticsSqlExecutor(explain_rows=[{"select_type": "SIMPLE"}], trial_rows=[])
    gate = LogisticsNl2SqlM10DShadowGate(
        config=LogisticsNl2SqlM10DShadowGateConfig(enabled=True, explain_enabled=True, trial_enabled=True),
        executor_factory=lambda: executor,
    )

    report = gate.run(rendered_sql=_safe_rendered_sql(), source_system="sap_mid")

    assert report.status == "skipped"
    assert report.stage == "source_system"
    assert report.explain_status == "skipped"
    assert report.trial_status == "skipped"
    assert report.error_codes == ["m10d_source_system_not_supported"]
    assert executor.calls == []


def test_m10d_gate_trial_cannot_bypass_disabled_explain() -> None:
    """trial gate 开启但 EXPLAIN gate 关闭时必须 fail-closed，不能直接构造 executor。"""

    executor = FakeLogisticsSqlExecutor(explain_rows=[{"select_type": "SIMPLE"}], trial_rows=[])
    gate = LogisticsNl2SqlM10DShadowGate(
        config=LogisticsNl2SqlM10DShadowGateConfig(enabled=True, explain_enabled=False, trial_enabled=True),
        executor_factory=lambda: executor,
    )

    report = gate.run(rendered_sql=_safe_rendered_sql())
    payload = report.model_dump_json()

    assert report.status == "failed"
    assert report.stage == "explain"
    assert report.explain_status == "disabled"
    assert report.trial_status == "skipped"
    assert report.error_codes == ["m10d_trial_requires_successful_explain"]
    assert executor.calls == []
    assert "SELECT" not in payload
    assert "dws_logistics_detail_union" not in payload


def test_m10d_gate_safety_failure_fail_closed_before_executor() -> None:
    """即使上游声称已过 safety，M10-D gate 也必须复核 SQL 文本并在失败时阻断 executor。"""

    executor = FakeLogisticsSqlExecutor(explain_rows=[{"select_type": "SIMPLE"}], trial_rows=[])
    gate = LogisticsNl2SqlM10DShadowGate(
        config=LogisticsNl2SqlM10DShadowGateConfig(enabled=True, explain_enabled=True, trial_enabled=True),
        executor_factory=lambda: executor,
    )
    unsafe = LogisticsRenderedSql(
        sql="SELECT * FROM dws_logistics_detail_union WHERE dws_logistics_detail_union.biz_year = :p0 LIMIT :p1",
        params={"p0": 2025, "p1": 10},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[("dws_logistics_detail_union", "biz_year")],
        limit=10,
    )

    report = gate.run(rendered_sql=unsafe)
    payload = report.model_dump_json()

    assert report.status == "failed"
    assert report.stage == "safety"
    assert report.explain_status == "skipped"
    assert report.trial_status == "skipped"
    assert report.safety_reason_code == "sql_safety_select_star_forbidden"
    assert "m10d_safety_failed" in report.error_codes
    assert executor.calls == []
    assert "SELECT" not in payload
    assert "dws_logistics_detail_union" not in payload
    assert "2025" not in payload


def test_m10d_gate_limit_above_safety_cap_fail_closed_before_executor() -> None:
    """超过 safety 上限的 LIMIT 必须在 M10-D gate 内 fail-closed，不能进入 fake/真实 executor。"""

    executor = FakeLogisticsSqlExecutor(explain_rows=[{"select_type": "SIMPLE"}], trial_rows=[])
    gate = LogisticsNl2SqlM10DShadowGate(
        config=LogisticsNl2SqlM10DShadowGateConfig(enabled=True, explain_enabled=True, trial_enabled=True),
        executor_factory=lambda: executor,
    )
    base = _safe_rendered_sql()
    unsafe = base.model_copy(
        update={
            "sql": f"{base.sql} LIMIT :p_limit",
            "params": {**base.params, "p_limit": 9999},
            "limit": 9999,
        }
    )

    report = gate.run(rendered_sql=unsafe)
    payload = report.model_dump_json()

    assert report.status == "failed"
    assert report.stage == "safety"
    assert report.explain_status == "skipped"
    assert report.trial_status == "skipped"
    assert report.safety_reason_code == "sql_safety_limit_out_of_range"
    assert "m10d_safety_failed" in report.error_codes
    assert executor.calls == []
    assert "SELECT" not in payload
    assert "dws_logistics_detail_union" not in payload
    assert "9999" not in payload


def _safe_rendered_sql() -> LogisticsRenderedSql:
    """生成一条 renderer/safety 可通过的物流 aggregate SQL，用于 M10-D gate 测试。"""

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
    assert validation.ok, validation.error_codes
    return render_logistics_sql(validation)

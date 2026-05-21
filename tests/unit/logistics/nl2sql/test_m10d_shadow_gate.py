from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.app.domains.logistics.services.nl2sql.m10d_shadow_gate import (
    LogisticsNl2SqlM10DShadowGate,
    LogisticsNl2SqlM10DShadowGateConfig,
)
from backend.app.domains.logistics.services.nl2sql.readonly_middle_db import (
    LogisticsReadonlyMiddleDbConfig,
    LogisticsReadonlyMiddleDbExecutor,
    load_readonly_middle_db_config,
)
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader
from backend.app.domains.logistics.services.nl2sql.sql_execution import FakeLogisticsSqlExecutor, LogisticsSqlExecutor
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
            "FROM dws_logistics_detail_union mysql://user:***@127.0.0.1/db"
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


# =============================================================================
# M10-D2 测试：真实只读中间库 EXPLAIN smoke gate
# =============================================================================


class _RejectRealExecutorFactory:
    """如果 D2 gate 配置了 real_db_access_enabled=False，不应尝试创建真实 executor。"""

    def __call__(self) -> LogisticsSqlExecutor:
        raise AssertionError("real_db_access_enabled=False 时不应构造真实 executor")


def test_m10d2_real_db_access_disabled_uses_fake_executor() -> None:
    """real_db_access_enabled=False（默认）时即使 gate 开启，仍使用注入的 fake executor。

    D2 核心保护：默认不连库。
    """
    executor = FakeLogisticsSqlExecutor(explain_rows=[{"select_type": "SIMPLE"}])
    config = LogisticsNl2SqlM10DShadowGateConfig(
        enabled=True,
        explain_enabled=True,
    )
    gate = LogisticsNl2SqlM10DShadowGate(
        config=config,
        executor_factory=lambda: executor,
    )

    report = gate.run(rendered_sql=_safe_rendered_sql())

    assert report.status == "success"
    assert report.stage == "explain"
    assert report.explain_status == "success"
    assert report.error_codes == []
    assert [call.mode for call in executor.calls] == ["explain"]


def test_m10d2_real_db_access_enabled_no_env_falls_back_to_fake() -> None:
    """real_db_access_enabled=True 但 env_path 指向不存在文件时，应静默 fallback 到 fake executor。

    不抛出异常，不因 env 缺失而 fail-closed gate。
    """
    executor = FakeLogisticsSqlExecutor(explain_rows=[{"select_type": "SIMPLE"}])
    config = LogisticsNl2SqlM10DShadowGateConfig(
        enabled=True,
        explain_enabled=True,
        real_db_access_enabled=True,
        env_path="/tmp/nonexistent_dir/.env",
    )
    gate = LogisticsNl2SqlM10DShadowGate(
        config=config,
        executor_factory=lambda: executor,
    )

    report = gate.run(rendered_sql=_safe_rendered_sql())
    payload = report.model_dump_json()

    assert report.status == "success"
    assert report.stage == "explain"
    assert report.explain_status == "success"
    assert report.error_codes == []
    assert [call.mode for call in executor.calls] == ["explain"]
    assert "SELECT " not in payload


# =============================================================================
# M10-D2-2 测试：EXPLAIN smoke runner（基于真实 env 配置的 M10D shadow gate）
# =============================================================================


def test_m10d2_smoke_runner_env_unavailable_writes_deidentified_blocked_artifact(tmp_path: Path) -> None:
    """env 不可用时 smoke runner 必须写入 blocked 状态 artifact，不泄露 SQL/参数/env 值。"""
    from backend.app.domains.logistics.services.nl2sql.m10d2_explain_smoke import (
        run_logistics_nl2sql_m10d2_explain_smoke,
    )

    result = run_logistics_nl2sql_m10d2_explain_smoke(
        env_path=tmp_path / "missing.env",
        artifact_dir=tmp_path / "m10d2-artifacts",
    )

    assert result.live_smoke_executed is False
    assert result.environment_status == "environment_unavailable"
    assert result.report.by_status == {"blocked": 1}
    assert result.records_path.exists()
    assert result.report_path.exists()
    payload = (result.records_path.read_text(encoding="utf-8")
               + result.report_path.read_text(encoding="utf-8"))
    assert "password" not in payload.lower()
    assert "mysql://" not in payload
    assert "Bearer" not in payload
    assert "sk-" not in payload


def test_m10d2_smoke_runner_stub_executor_success_generates_deidentified_artifacts(tmp_path: Path) -> None:
    """stub executor 成功时生成 EXPLAIN 成功记录，artifact 不泄露 SQL/表名/env 值。"""
    from backend.app.domains.logistics.services.nl2sql.m10d2_explain_smoke import (
        run_logistics_nl2sql_m10d2_explain_smoke,
        LogisticsNl2SqlM10D2ExplainSmokeSample,
    )
    from backend.app.domains.logistics.services.nl2sql.sql_plan import LogisticsSqlPlanValidator
    from backend.app.domains.logistics.services.nl2sql.sql_renderer import render_logistics_sql
    from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader

    catalog = LogisticsSemanticCatalogLoader().load()
    validator = LogisticsSqlPlanValidator(catalog=catalog)
    validation = validator.validate({
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
    })
    assert validation.ok, validation.error_codes

    env_path = _write_d2_env(tmp_path)
    artifact_dir = tmp_path / "m10d2-artifacts"
    samples = [
        LogisticsNl2SqlM10D2ExplainSmokeSample(
            sample_id="m10d2_stub_aggregate",
            description="stub aggregate EXPLAIN smoke",
            rendered_sql=render_logistics_sql(validation),
        ),
    ]

    result = run_logistics_nl2sql_m10d2_explain_smoke(
        env_path=env_path,
        artifact_dir=artifact_dir,
        samples=samples,
        executor_factory=lambda _config: _StubM10d2Executor(),
    )

    assert result.live_smoke_executed is True
    assert result.environment_status == "available"
    assert len(result.outcomes) >= 1
    assert all(o.report.status == "success" and o.report.explain_status == "success"
               for o in result.outcomes)
    payload = (result.records_path.read_text(encoding="utf-8")
               + result.report_path.read_text(encoding="utf-8"))
    assert "SELECT " not in payload
    assert "dws_logistics_detail_union" not in payload
    assert "shipment_mw" not in payload
    assert "db.internal" not in payload
    assert "admin_user" not in payload
    assert "unit-password" not in payload
    assert "mysql://" not in payload
    assert "Bearer" not in payload
    assert "sk-" not in payload


def test_m10d2_smoke_runner_stub_explain_failed_records_failure_without_leak(tmp_path: Path) -> None:
    """EXPLAIN 失败时 smoke runner 进入 explain_failed，artifact 不含原始错误。"""
    from backend.app.domains.logistics.services.nl2sql.m10d2_explain_smoke import (
        run_logistics_nl2sql_m10d2_explain_smoke,
        LogisticsNl2SqlM10D2ExplainSmokeSample,
    )
    from backend.app.domains.logistics.services.nl2sql.sql_plan import LogisticsSqlPlanValidator
    from backend.app.domains.logistics.services.nl2sql.sql_renderer import render_logistics_sql
    from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader

    catalog = LogisticsSemanticCatalogLoader().load()
    validator = LogisticsSqlPlanValidator(catalog=catalog)
    validation = validator.validate({
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
    })
    assert validation.ok, validation.error_codes

    env_path = _write_d2_env(tmp_path)
    artifact_dir = tmp_path / "m10d2-artifacts"
    samples = [
        LogisticsNl2SqlM10D2ExplainSmokeSample(
            sample_id="m10d2_stub_aggregate",
            description="stub aggregate EXPLAIN smoke",
            rendered_sql=render_logistics_sql(validation),
        ),
    ]

    result = run_logistics_nl2sql_m10d2_explain_smoke(
        env_path=env_path,
        artifact_dir=artifact_dir,
        samples=samples,
        executor_factory=lambda _config: _StubM10d2Executor(mode="explain_failed"),
    )

    assert result.live_smoke_executed is True
    assert result.report.by_status.get("failed", 0) >= 1
    payload = (result.records_path.read_text(encoding="utf-8")
               + result.report_path.read_text(encoding="utf-8"))
    assert "unit-password" not in payload
    assert "db.internal" not in payload
    assert "SELECT " not in payload


class _StubM10d2Executor:
    """M10-D2 smoke runner 单测用 stub executor，不连接真实库。"""

    def __init__(self, *, mode: str = "success") -> None:
        self.mode = mode

    def explain(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        if self.mode == "explain_failed":
            raise RuntimeError("db.internal explain failed password=unit-password")
        return [{"select_type": "SIMPLE"}]

    def trial(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        return [{"ok": 1}]


def _write_d2_env(tmp_path: Path) -> Path:
    """写入 D2 smoke 单测专用 .env。"""
    env_path = tmp_path / ".env"
    env_path.write_text(
        "MYSQL_HOST=db.internal\nMYSQL_PORT=3307\nMYSQL_DB=logistics_ai\n"
        "MYSQL_USER=admin_user\nMYSQL_PASSWORD=unit-password\nMYSQL_CHARSET=utf8mb4\n",
        encoding="utf-8",
    )
    return env_path

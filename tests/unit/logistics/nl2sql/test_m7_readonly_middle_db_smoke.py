from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend.app.domains.logistics.services.nl2sql.m7_readonly_smoke import (
    build_default_logistics_nl2sql_m7_readonly_smoke_samples,
    run_logistics_nl2sql_m7_readonly_smoke,
)
from backend.app.domains.logistics.services.nl2sql.readonly_middle_db import (
    LogisticsReadonlyMiddleDbConfig,
    LogisticsReadonlyMiddleDbExecutor,
    load_readonly_middle_db_config,
)
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader
from backend.app.domains.logistics.services.nl2sql.sql_execution import LogisticsSqlExecutionService
from backend.app.domains.logistics.services.nl2sql.sql_plan import LogisticsSqlPlanValidator
from backend.app.domains.logistics.services.nl2sql.sql_renderer import LogisticsRenderedSql, render_logistics_sql
from backend.app.domains.logistics.services.nl2sql.sql_safety import LogisticsSqlSafetyChecker


class _FakeCursor:
    """M7 只读 executor 单测用游标，记录 SQL 与参数但不连接数据库。"""

    def __init__(self, calls: list[tuple[str, dict[str, Any]]]) -> None:
        """初始化调用记录列表。"""

        self.calls = calls

    def __enter__(self) -> "_FakeCursor":
        """进入上下文并返回自身。"""

        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """退出上下文，无需清理真实资源。"""

        return None

    def execute(self, sql: str, params: dict[str, Any]) -> None:
        """记录即将交给 DB driver 的 SQL 与参数。"""

        self.calls.append((sql, dict(params)))

    def fetchall(self) -> list[dict[str, Any]]:
        """返回小样本行，模拟 EXPLAIN/SELECT 结果。"""

        return [{"ok": 1}]


class _FakeConnection:
    """M7 只读 executor 单测用连接。"""

    def __init__(self, calls: list[tuple[str, dict[str, Any]]]) -> None:
        """初始化连接的共享调用记录。"""

        self.calls = calls
        self.closed = False

    def cursor(self) -> _FakeCursor:
        """返回记录型 fake cursor。"""

        return _FakeCursor(self.calls)

    def close(self) -> None:
        """标记连接已关闭。"""

        self.closed = True


def test_m7_config_loader_missing_env_fail_closed_without_secret_values(tmp_path: Path) -> None:
    """缺少 backend/.env 时必须 fail-closed，且结果中不泄露 host/user/password/DSN。"""

    missing_env = tmp_path / "backend" / ".env"

    result = load_readonly_middle_db_config(missing_env)
    payload = result.model_dump_json()

    assert result.ok is False
    assert result.error_code == "readonly_middle_db_env_missing"
    assert result.config is None
    assert "mysql://" not in payload
    assert "unit-password" not in payload
    assert "db.internal" not in payload
    assert "admin_user" not in payload


def test_m7_config_loader_missing_required_key_redacts_existing_env_values(tmp_path: Path) -> None:
    """配置不完整时可以说明缺失键名，但不能把已存在的真实配置值带入错误结果。"""

    env_path = tmp_path / ".env"
    env_path.write_text(
        "MYSQL_HOST=db.internal\nMYSQL_PORT=3306\nMYSQL_USER=admin_user\nMYSQL_PASSWORD=unit-password\n",
        encoding="utf-8",
    )

    result = load_readonly_middle_db_config(env_path)
    payload = result.model_dump_json()

    assert result.ok is False
    assert result.error_code == "readonly_middle_db_config_missing"
    assert "MYSQL_DB" in result.missing_keys
    assert "db.internal" not in payload
    assert "admin_user" not in payload
    assert "unit-password" not in payload
    assert "mysql://" not in payload


def test_m7_config_loader_accepts_backend_env_and_only_exposes_redacted_summary(tmp_path: Path) -> None:
    """有效 .env 只返回内部 config 与脱敏摘要，JSON 序列化不出现连接明文。"""

    env_path = tmp_path / ".env"
    env_path.write_text(
        "MYSQL_HOST=db.internal\nMYSQL_PORT=3307\nMYSQL_DB=logistics_ai\n"
        "MYSQL_USER=admin_user\nMYSQL_PASSWORD=unit-password\nMYSQL_CHARSET=utf8mb4\n",
        encoding="utf-8",
    )

    result = load_readonly_middle_db_config(env_path)
    payload = result.model_dump_json()

    assert result.ok is True
    assert result.config is not None
    assert result.safe_summary["configured"] is True
    assert result.safe_summary["host_configured"] is True
    assert result.safe_summary["database_configured"] is True
    assert "db.internal" not in payload
    assert "logistics_ai" not in payload
    assert "admin_user" not in payload
    assert "unit-password" not in payload
    assert "mysql://" not in payload


def test_m7_readonly_executor_runs_explain_and_bounded_trial_select_with_driver_params() -> None:
    """M7 executor 只能把 EXPLAIN SELECT 与带 LIMIT 的 SELECT 交给 driver，参数保持绑定。"""

    calls: list[tuple[str, dict[str, Any]]] = []
    executor = LogisticsReadonlyMiddleDbExecutor(
        config=_unit_config(),
        connection_factory=lambda _config: _FakeConnection(calls),
    )
    service = LogisticsSqlExecutionService(
        executor=executor,
        safety_checker=LogisticsSqlSafetyChecker(max_limit=20),
        trial_limit=5,
    )
    rendered = _aggregate_rendered_sql()

    explain = service.explain(rendered)
    trial = service.trial(rendered)

    assert explain.ok is True, explain.error
    assert trial.ok is True, trial.error
    assert len(calls) == 2
    assert calls[0][0].startswith("EXPLAIN SELECT ")
    assert "%(p0)s" in calls[0][0]
    assert calls[0][1] == rendered.params
    assert calls[1][0].startswith("SELECT ")
    assert calls[1][0].endswith(" LIMIT %(__trial_limit)s")
    assert calls[1][1]["__trial_limit"] == 5
    assert calls[1][1]["__trial_limit"] <= 20


def test_m7_readonly_executor_rejects_non_select_and_unbounded_trial_before_driver() -> None:
    """即使被直接调用，M7 executor 也必须在 driver 前拒绝非 SELECT 与无界 trial SQL。"""

    calls: list[tuple[str, dict[str, Any]]] = []
    executor = LogisticsReadonlyMiddleDbExecutor(
        config=_unit_config(),
        connection_factory=lambda _config: _FakeConnection(calls),
    )

    with pytest.raises(RuntimeError, match="readonly_middle_db_trial_limit_required"):
        executor.trial("SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union", {})
    with pytest.raises(RuntimeError, match="readonly_middle_db_not_select"):
        executor.trial("DELETE FROM dws_logistics_detail_union LIMIT 1", {})

    assert calls == []


@pytest.mark.parametrize(
    "unsafe_sql",
    [
        "SELECT biz_year FROM dws_logistics_detail_union INTO OUTFILE '/tmp/leak.csv' LIMIT 1",
        "SELECT biz_year FROM dws_logistics_detail_union INTO DUMPFILE '/tmp/leak.bin' LIMIT 1",
        "SELECT biz_year FROM dws_logistics_detail_union UNION SELECT user FROM mysql.user LIMIT 1",
        "SELECT LOAD_FILE('/etc/passwd') FROM dws_logistics_detail_union LIMIT 1",
        "SELECT biz_year FROM dws_logistics_detail_union -- comment\n LIMIT 1",
        "SELECT biz_year FROM dws_logistics_detail_union /* hidden */ LIMIT 1",
        "SELECT biz_year FROM dws_logistics_detail_union # comment\n LIMIT 1",
        "SELECT biz_year FROM dws_logistics_detail_union LIMIT 1 FOR UPDATE",
        "SELECT biz_year FROM dws_logistics_detail_union LIMIT 1 LOCK IN SHARE MODE",
        "SELECT biz_year FROM dws_logistics_detail_union PROCEDURE ANALYSE() LIMIT 1",
        "SELECT SLEEP(1) FROM dws_logistics_detail_union LIMIT 1",
        "SELECT BENCHMARK(100, MD5('x')) FROM dws_logistics_detail_union LIMIT 1",
    ],
)
def test_m7_readonly_executor_rejects_dangerous_select_tokens_before_driver(unsafe_sql: str) -> None:
    """即使 SQL 以 SELECT 开头且 bounded，真实 DB executor 仍需在 driver 前 fail-closed 拒绝危险只读绕过。"""

    calls: list[tuple[str, dict[str, Any]]] = []
    executor = LogisticsReadonlyMiddleDbExecutor(
        config=_unit_config(),
        connection_factory=lambda _config: _FakeConnection(calls),
    )

    with pytest.raises(RuntimeError, match="readonly_middle_db_unsafe_select"):
        executor.trial(unsafe_sql, {})

    assert calls == []


def test_m7_runner_clamps_cli_supplied_limits_to_m7_upper_bound(tmp_path: Path) -> None:
    """即使 CLI/调用方传入更大 max_limit，M7 runner 也必须把真实 DB safety 与 trial 上限钳制在 20 以内。"""

    result = run_logistics_nl2sql_m7_readonly_smoke(
        env_path=_write_valid_env(tmp_path),
        artifact_dir=tmp_path / "m7-artifacts",
        samples=build_default_logistics_nl2sql_m7_readonly_smoke_samples()[1:],
        executor_factory=lambda _config: _StubLogisticsReadonlyExecutor(assert_limit_at_most=20),
        trial_limit=99,
        max_limit=99,
    )

    assert result.live_smoke_executed is True
    assert result.report.by_status["success"] == 1


def test_m7_safety_rejection_skips_readonly_executor_for_excessive_limit() -> None:
    """超过 M7 上限的 LIMIT 应由 safety 拒绝，并且只读 executor 不得被调用。"""

    calls: list[tuple[str, dict[str, Any]]] = []
    executor = LogisticsReadonlyMiddleDbExecutor(
        config=_unit_config(),
        connection_factory=lambda _config: _FakeConnection(calls),
    )
    service = LogisticsSqlExecutionService(
        executor=executor,
        safety_checker=LogisticsSqlSafetyChecker(max_limit=20),
        trial_limit=5,
    )
    unsafe = LogisticsRenderedSql(
        sql="SELECT dws_logistics_detail_union.biz_year FROM dws_logistics_detail_union LIMIT :p0",
        params={"p0": 100},
        referenced_tables=["dws_logistics_detail_union"],
        referenced_columns=[("dws_logistics_detail_union", "biz_year")],
        limit=100,
    )

    result = service.trial(unsafe)

    assert result.ok is False
    assert "sql_safety_limit_out_of_range::100" in result.error_codes
    assert calls == []


def test_m7_runner_missing_env_writes_environment_unavailable_report_and_records(tmp_path: Path) -> None:
    """真实库环境不可用时 M7 runner 必须记录 blocked/environment_unavailable，而不是伪造成成功。"""

    artifact_dir = tmp_path / "m7-artifacts"

    result = run_logistics_nl2sql_m7_readonly_smoke(
        env_path=tmp_path / "missing.env",
        artifact_dir=artifact_dir,
    )

    assert result.live_smoke_executed is False
    assert result.environment_status == "environment_unavailable"
    assert result.environment_error_code == "readonly_middle_db_env_missing"
    assert result.report.by_status == {"blocked": 1}
    assert result.records_path == artifact_dir / "m7-shadow-smoke-records.jsonl"
    assert result.report_path == artifact_dir / "m7-shadow-smoke-report.md"
    assert result.records_path.exists()
    assert result.report_path.exists()
    payload = result.records_path.read_text(encoding="utf-8") + result.report_path.read_text(encoding="utf-8")
    assert "success" not in result.report.by_status
    assert "mysql://" not in payload
    assert "password" not in payload.lower()
    assert "Bearer" not in payload
    assert "sk-" not in payload


def test_m7_runner_stub_executor_generates_success_artifacts_without_env_secret_leak(tmp_path: Path) -> None:
    """M7 runner 在 stub executor 路径应生成成功记录与报表，但 artifact 不得泄露 .env 明文值或 SQL 原文。"""

    env_path = _write_valid_env(tmp_path)
    artifact_dir = tmp_path / "m7-artifacts"
    samples = build_default_logistics_nl2sql_m7_readonly_smoke_samples()[:1]

    result = run_logistics_nl2sql_m7_readonly_smoke(
        env_path=env_path,
        artifact_dir=artifact_dir,
        samples=samples,
        executor_factory=lambda _config: _StubLogisticsReadonlyExecutor(),
    )

    assert result.live_smoke_executed is True
    assert result.environment_status == "available"
    assert result.report.success_count == 1
    assert result.report.by_status["success"] == 1
    payload = result.records_path.read_text(encoding="utf-8") + result.report_path.read_text(encoding="utf-8")
    assert "SELECT " not in payload
    assert "EXPLAIN " not in payload
    assert "db.internal" not in payload
    assert "logistics_ai" not in payload
    assert "admin_user" not in payload
    assert "unit-password" not in payload
    assert "mysql://" not in payload
    assert "Bearer" not in payload
    assert "sk-" not in payload


def test_m7_runner_records_explain_failed_without_leaking_executor_error(tmp_path: Path) -> None:
    """EXPLAIN 失败应进入 explain_failed，并且报告只保留稳定错误码与脱敏错误。"""

    result = run_logistics_nl2sql_m7_readonly_smoke(
        env_path=_write_valid_env(tmp_path),
        artifact_dir=tmp_path / "m7-artifacts",
        samples=build_default_logistics_nl2sql_m7_readonly_smoke_samples()[:1],
        executor_factory=lambda _config: _StubLogisticsReadonlyExecutor(mode="explain_failed"),
    )

    assert result.live_smoke_executed is True
    assert result.report.by_status["explain_failed"] == 1
    payload = result.records_path.read_text(encoding="utf-8") + result.report_path.read_text(encoding="utf-8")
    assert "unit-password" not in payload
    assert "db.internal" not in payload
    assert "SELECT " not in payload


def test_m7_runner_records_trial_failed_without_leaking_executor_error(tmp_path: Path) -> None:
    """trial SELECT 失败应进入 trial_failed，并且不把 SQL 或参数值写入 artifact。"""

    result = run_logistics_nl2sql_m7_readonly_smoke(
        env_path=_write_valid_env(tmp_path),
        artifact_dir=tmp_path / "m7-artifacts",
        samples=build_default_logistics_nl2sql_m7_readonly_smoke_samples()[:1],
        executor_factory=lambda _config: _StubLogisticsReadonlyExecutor(mode="trial_failed"),
    )

    assert result.live_smoke_executed is True
    assert result.report.by_status["trial_failed"] == 1
    payload = result.records_path.read_text(encoding="utf-8") + result.report_path.read_text(encoding="utf-8")
    assert "raw_param_value" not in payload
    assert "SELECT " not in payload
    assert "EXPLAIN " not in payload


class _StubLogisticsReadonlyExecutor:
    """M7 runner 单测用 executor，不连接真实库。"""

    def __init__(self, *, mode: str = "success", assert_limit_at_most: int | None = None) -> None:
        """初始化 stub 模式，用于覆盖成功、EXPLAIN 失败、trial 失败与 LIMIT 钳制断言。"""

        self.mode = mode
        self.assert_limit_at_most = assert_limit_at_most

    def explain(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """模拟 EXPLAIN；失败模式返回含敏感词的异常以验证脱敏。"""

        if self.mode == "explain_failed":
            raise RuntimeError("db.internal explain failed password=unit-password")
        return [{"select_type": "SIMPLE"}]

    def trial(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """模拟 SELECT trial；失败模式返回含参数值的异常以验证脱敏。"""

        if self.mode == "trial_failed":
            raise RuntimeError("trial failed raw_param_value SELECT * FROM dws_logistics_detail_union")
        if self.assert_limit_at_most is not None:
            limit_value = params.get("__trial_limit")
            assert isinstance(limit_value, int)
            assert limit_value <= self.assert_limit_at_most
        return [{"sample_metric": 1}]


def _write_valid_env(tmp_path: Path) -> Path:
    """写入单测专用 .env，真实 artifact 不得泄漏其中任何值。"""

    env_path = tmp_path / ".env"
    env_path.write_text(
        "MYSQL_HOST=db.internal\nMYSQL_PORT=3307\nMYSQL_DB=logistics_ai\n"
        "MYSQL_USER=admin_user\nMYSQL_PASSWORD=unit-password\nMYSQL_CHARSET=utf8mb4\n",
        encoding="utf-8",
    )
    return env_path


def _unit_config() -> LogisticsReadonlyMiddleDbConfig:
    """生成单测专用脱敏中间库配置。"""

    return LogisticsReadonlyMiddleDbConfig(
        host="db.internal",
        port=3307,
        database="logistics_ai",
        user="admin_user",
        password="unit-password",
        charset="utf8mb4",
    )


def _aggregate_rendered_sql() -> LogisticsRenderedSql:
    """生成一条 M7 可用于 EXPLAIN/trial 的 aggregate SQL。"""

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

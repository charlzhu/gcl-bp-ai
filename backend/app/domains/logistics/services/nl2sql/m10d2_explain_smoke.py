from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domains.logistics.services.nl2sql.evaluation_log import (
    LogisticsNl2SqlEvaluationLogRecord,
    redact_evaluation_text,
)
from backend.app.domains.logistics.services.nl2sql.evaluation_report import (
    LogisticsNl2SqlEvaluationReport,
    build_logistics_nl2sql_evaluation_report,
    render_logistics_nl2sql_evaluation_report_markdown,
)
from backend.app.domains.logistics.services.nl2sql.m10d_shadow_gate import (
    LogisticsNl2SqlM10DShadowGate,
    LogisticsNl2SqlM10DShadowGateConfig,
    LogisticsNl2SqlM10DShadowGateReport,
)
from backend.app.domains.logistics.services.nl2sql.readonly_middle_db import (
    LogisticsReadonlyMiddleDbConfig,
    LogisticsReadonlyMiddleDbExecutor,
    load_readonly_middle_db_config,
)
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader
from backend.app.domains.logistics.services.nl2sql.sql_execution import LogisticsSqlExecutionService, LogisticsSqlExecutor
from backend.app.domains.logistics.services.nl2sql.sql_plan import LogisticsSqlPlanValidator
from backend.app.domains.logistics.services.nl2sql.sql_renderer import LogisticsRenderedSql, render_logistics_sql
from backend.app.domains.logistics.services.nl2sql.sql_safety import LogisticsSqlSafetyChecker

M10D2_EXPLAIN_SMOKE_VERSION = "logistics_nl2sql_m10d2_explain_smoke.v1"
DEFAULT_M10D2_RECORDS_FILENAME = "m10d2-explain-smoke-records.jsonl"
DEFAULT_M10D2_REPORT_FILENAME = "m10d2-explain-smoke-report.md"
EnvironmentStatus = Literal["available", "environment_unavailable"]

ReadonlyExecutorFactory = Callable[[LogisticsReadonlyMiddleDbConfig], LogisticsSqlExecutor]


class LogisticsNl2SqlM10D2ExplainSmokeSample(BaseModel):
    """M10-D2 EXPLAIN smoke 样例定义。

    参数：
        sample_id: 样例唯一标识。
        description: 业务描述。
        rendered_sql: 经过 SQLPlan validator 和 renderer 产出的安全 SQL，直接喂给 M10-D gate。
    """

    model_config = ConfigDict(extra="forbid")

    sample_id: str
    description: str
    rendered_sql: LogisticsRenderedSql


class LogisticsNl2SqlM10D2ExplainSmokeOutcome(BaseModel):
    """M10-D2 单条例样执行结果。

    参数：
        sample: 原始样例定义。
        report: M10-D shadow gate 的脱敏报告（不含 SQL/表名/参数值）。
        evaluation_log_record: 脱敏评估日志记录。
    """

    model_config = ConfigDict(extra="forbid")

    sample: LogisticsNl2SqlM10D2ExplainSmokeSample
    report: LogisticsNl2SqlM10DShadowGateReport
    evaluation_log_record: LogisticsNl2SqlEvaluationLogRecord


class LogisticsNl2SqlM10D2ExplainSmokeRunResult(BaseModel):
    """M10-D2 EXPLAIN smoke 总返回。

    参数：
        outcomes: 每条样例的执行结果。
        evaluation_log_records: 脱敏评估日志记录列表。
        report: 汇总评估报表。
        records_path: JSONL artifact 路径。
        report_path: Markdown artifact 路径。
        live_smoke_executed: 是否成功执行了真实 EXPLAIN。
        environment_status: 数据库环境状态。
        environment_error_code: 环境不可用时的稳定错误码。
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    outcomes: list[LogisticsNl2SqlM10D2ExplainSmokeOutcome] = Field(default_factory=list)
    evaluation_log_records: list[LogisticsNl2SqlEvaluationLogRecord] = Field(default_factory=list)
    report: LogisticsNl2SqlEvaluationReport
    records_path: Path
    report_path: Path
    live_smoke_executed: bool
    environment_status: EnvironmentStatus
    environment_error_code: str | None = None


def build_default_logistics_nl2sql_m10d2_explain_smoke_samples() -> list[LogisticsNl2SqlM10D2ExplainSmokeSample]:
    """构造 M10-D2 默认 EXPLAIN smoke 样例。

    返回：
        使用 M10-D gate 测试中的 _safe_rendered_sql 相同方式，生成两条已验证的 SQLPlan 样例。
    """
    catalog = LogisticsSemanticCatalogLoader().load()
    validator = LogisticsSqlPlanValidator(catalog=catalog)

    aggregate_plan = {
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
    aggregate_validation = validator.validate(aggregate_plan)
    assert aggregate_validation.ok, aggregate_validation.error_codes

    return [
        LogisticsNl2SqlM10D2ExplainSmokeSample(
            sample_id="m10d2_success_valid_aggregate",
            description="合法 SQLPlan + 真实只读中间库 EXPLAIN smoke（aggregate）",
            rendered_sql=render_logistics_sql(aggregate_validation),
        ),
    ]


def run_logistics_nl2sql_m10d2_explain_smoke(
    *,
    env_path: str | Path = Path("backend/.env"),
    artifact_dir: str | Path = Path("ai/outbox/kanban/t_df3a6b13/m10d2-explain-smoke"),
    samples: list[LogisticsNl2SqlM10D2ExplainSmokeSample] | None = None,
    executor_factory: ReadonlyExecutorFactory | None = None,
) -> LogisticsNl2SqlM10D2ExplainSmokeRunResult:
    """运行 M10-D2 EXPLAIN smoke：连接真实只读中间库，对所有样例执行 EXPLAIN gate。

    业务逻辑：
        1. 读 backend/.env 加载中间库配置；缺失或配置不完整时 fail-closed。
        2. 对每个样例构造 M10-D shadow gate（real_db_access_enabled=True，explain_enabled=True）。
        3. 直接通过 gate.run() 对预先 render 好的 SQL 执行 EXPLAIN。
        4. 只做 EXPLAIN（不启用 trial），避免返回行值。
        5. 写出脱敏 JSONL 记录和 Markdown 报表。

    参数：
        env_path: backend/.env 路径；缺失或配置不完整时 fail-closed。
        artifact_dir: 验收材料目录，runner 只在该目录下写 JSONL/Markdown。
        samples: 可选样例集；默认使用 M10-D2 scoped 样例（aggregate + ranking）。
        executor_factory: 可选 executor 工厂，单测可注入 stub；生产 smoke 默认使用 PyMySQL 只读 executor。
    返回：
        结构化 run 结果；不包含 SQL 原文、参数值或数据库连接明文。
    """
    resolved_artifact_dir = Path(artifact_dir)
    resolved_artifact_dir.mkdir(parents=True, exist_ok=True)
    records_path = resolved_artifact_dir / DEFAULT_M10D2_RECORDS_FILENAME
    report_path = resolved_artifact_dir / DEFAULT_M10D2_REPORT_FILENAME
    _reset_artifact(records_path)
    _reset_artifact(report_path)

    resolved_samples = samples or build_default_logistics_nl2sql_m10d2_explain_smoke_samples()

    config_result = load_readonly_middle_db_config(env_path)
    if not config_result.ok or config_result.config is None:
        error_code = config_result.error_code or "readonly_middle_db_config_unavailable"
        record = _build_environment_unavailable_record(error_code)
        report = build_logistics_nl2sql_evaluation_report(
            [record],
            sample_ids={record.trace_id: "m10d2_environment_unavailable"},
            sample_descriptions={
                record.trace_id: "backend/.env 中间库只读配置不可用，M10-D2 EXPLAIN smoke 已阻塞",
            },
            warnings=["M10-D2 EXPLAIN smoke blocked by environment configuration; no live explain executed"],
        )
        _write_records(records_path, [record])
        _write_report(report_path, report)
        return LogisticsNl2SqlM10D2ExplainSmokeRunResult(
            outcomes=[],
            evaluation_log_records=[record],
            report=report,
            records_path=records_path,
            report_path=report_path,
            live_smoke_executed=False,
            environment_status="environment_unavailable",
            environment_error_code=error_code,
        )

    # 构建 executor 工厂：传入 executor_factory 时外部构造，否则交给 gate 自行连库
    executor = (
        executor_factory(config_result.config)
        if executor_factory
        else None
    )

    outcomes: list[LogisticsNl2SqlM10D2ExplainSmokeOutcome] = []
    records: list[LogisticsNl2SqlEvaluationLogRecord] = []
    sample_ids_by_trace: dict[str, str] = {}
    descriptions_by_trace: dict[str, str] = {}
    secret_values = _secret_values_from_config(config_result.config)

    for sample in resolved_samples:
        try:
            # 如果调用方传入了 executor_factory，使用工厂模式（不连真实库）
            use_real_db = executor_factory is None
            # 工厂模式时传入外部构造的 executor，真实模式时让 gate 自行构造
            ef = (lambda: executor) if executor_factory else None
            gate = LogisticsNl2SqlM10DShadowGate(
                config=LogisticsNl2SqlM10DShadowGateConfig(
                    enabled=True,
                    explain_enabled=True,
                    trial_enabled=False,
                    real_db_access_enabled=use_real_db,
                    env_path=str(env_path) if use_real_db else "",
                ),
                executor_factory=ef,
                safety_checker=LogisticsSqlSafetyChecker(),
            )
            gate_report = gate.run(rendered_sql=sample.rendered_sql)

            # 构造 evaluation log record
            record = LogisticsNl2SqlEvaluationLogRecord.from_pipeline(
                trace_id=f"m10d2-{sample.sample_id}",
                request_id=None,
                question=sample.description,
                rewritten_question=None,
                domain="logistics",
                source_system="middle_db",
                status=gate_report.status,
                stage=gate_report.stage,
                error_codes=gate_report.error_codes,
                error_message=None,
                catalog_ids=[],
                catalog_versions=[],
                sql_hash=gate_report.sql_hash,
                sql_param_keys=[],
                validation_errors=[],
                safety_errors=[],
                explain_ok=gate_report.explain_status == "success",
                trial_ok=False,
                row_count=gate_report.row_count,
                sample_row_count=0,
                duration_ms=gate_report.elapsed_ms,
                pipeline_version=M10D2_EXPLAIN_SMOKE_VERSION,
                warnings=[],
            )
        except Exception as exc:  # noqa: BLE001 - runner 必须单样例 fail-closed 后继续
            gate_report = LogisticsNl2SqlM10DShadowGateReport(
                enabled=True,
                status="failed",
                stage="runner",
                error_codes=["m10d2_explain_smoke_sample_failed"],
                explain_status="failed",
                trial_status="disabled",
                shadow_only=True,
            )
            record = LogisticsNl2SqlEvaluationLogRecord.from_pipeline(
                trace_id=f"m10d2-sample-exception-{sample.sample_id}",
                request_id=None,
                question=sample.description,
                rewritten_question=None,
                domain="logistics",
                source_system="middle_db",
                status="render_failed",
                stage="runner",
                error_codes=["m10d2_explain_smoke_sample_failed"],
                error_message=redact_evaluation_text(str(exc)),
                catalog_ids=[],
                catalog_versions=[],
                sql_hash=None,
                sql_param_keys=[],
                validation_errors=[],
                safety_errors=[],
                explain_ok=False,
                trial_ok=False,
                row_count=0,
                sample_row_count=0,
                duration_ms=0,
                pipeline_version=M10D2_EXPLAIN_SMOKE_VERSION,
                warnings=["single sample failed; runner continued"],
            )

        safe_record = _sanitize_record_for_m10d2(record, secret_values=secret_values)
        outcomes.append(
            LogisticsNl2SqlM10D2ExplainSmokeOutcome(
                sample=sample,
                report=gate_report,
                evaluation_log_record=safe_record,
            )
        )
        records.append(safe_record)
        sample_ids_by_trace[safe_record.trace_id] = sample.sample_id
        descriptions_by_trace[safe_record.trace_id] = sample.description

    environment_error_code = _detect_environment_unavailable_error(records)
    report = build_logistics_nl2sql_evaluation_report(
        records,
        sample_ids=sample_ids_by_trace,
        sample_descriptions=descriptions_by_trace,
        warnings=_build_run_warnings(environment_error_code),
    )
    _write_records(records_path, records)
    _write_report(report_path, report)
    return LogisticsNl2SqlM10D2ExplainSmokeRunResult(
        outcomes=outcomes,
        evaluation_log_records=records,
        report=report,
        records_path=records_path,
        report_path=report_path,
        live_smoke_executed=environment_error_code is None,
        environment_status="environment_unavailable" if environment_error_code else "available",
        environment_error_code=environment_error_code,
    )


def _build_environment_unavailable_record(error_code: str) -> LogisticsNl2SqlEvaluationLogRecord:
    """生成环境不可用 synthetic record，不携带 .env 键值或 SQL。"""
    return LogisticsNl2SqlEvaluationLogRecord.from_pipeline(
        trace_id="m10d2-environment-unavailable",
        request_id=None,
        question="M10-D2 EXPLAIN middle-db smoke",
        rewritten_question=None,
        domain="logistics",
        source_system="middle_db",
        status="blocked",
        stage="environment",
        error_codes=[error_code],
        error_message=None,
        catalog_ids=[],
        catalog_versions=[],
        sql_hash=None,
        sql_param_keys=[],
        validation_errors=[],
        safety_errors=[],
        explain_ok=False,
        trial_ok=False,
        row_count=0,
        sample_row_count=0,
        duration_ms=0,
        pipeline_version=M10D2_EXPLAIN_SMOKE_VERSION,
        warnings=["environment_unavailable"],
    )


def _sanitize_record_for_m10d2(
    record: LogisticsNl2SqlEvaluationLogRecord,
    *,
    secret_values: set[str],
) -> LogisticsNl2SqlEvaluationLogRecord:
    """对 M10-D2 artifact record 做二次脱敏，额外移除实际 host/user/db 等配置值。"""
    payload = _sanitize_payload(record.model_dump(mode="json"), secret_values=secret_values)
    return LogisticsNl2SqlEvaluationLogRecord.model_validate(payload)


def _sanitize_payload(value: Any, *, secret_values: set[str]) -> Any:
    """递归脱敏 payload，避免嵌套字段绕过。"""
    if isinstance(value, dict):
        return {str(key): _sanitize_payload(item, secret_values=secret_values) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_payload(item, secret_values=secret_values) for item in value]
    if isinstance(value, str):
        return _sanitize_m10d2_text(value, secret_values=secret_values)
    return value


def _sanitize_m10d2_text(value: str, *, secret_values: set[str]) -> str:
    """M10-D2 artifact 文本脱敏：移除 SQL、token、Bearer、host/user/db/password 明文。"""
    safe = redact_evaluation_text(value)
    for secret_value in sorted(secret_values, key=len, reverse=True):
        if secret_value:
            safe = safe.replace(secret_value, "[REDACTED]")
    safe = re.sub(r"(?i)\\bBearer\\s+\\[REDACTED\\]", "[TOKEN_REDACTED]", safe)
    safe = re.sub(
        r"(?i)\\b(password|passwd|token|api[_-]?key|secret)\\b\\s*[:=]\\s*\\[REDACTED\\]",
        "credential=[REDACTED]",
        safe,
    )
    return safe


def _secret_values_from_config(config: LogisticsReadonlyMiddleDbConfig) -> set[str]:
    """提取不允许进入 artifact 的连接配置值。"""
    return {
        str(config.host),
        str(config.database),
        str(config.user),
        str(config.password),
        f"{config.host}:{config.port}",
    }


def _detect_environment_unavailable_error(records: list[LogisticsNl2SqlEvaluationLogRecord]) -> str | None:
    """根据稳定错误摘要判断是否属于连接/驱动环境不可用。"""
    environment_error_codes = {
        "readonly_middle_db_connection_failed",
        "readonly_middle_db_driver_unavailable",
    }
    for record in records:
        text_parts = [record.error_message or "", *record.error_codes]
        for text in text_parts:
            for error_code in environment_error_codes:
                if error_code in text:
                    return error_code
    return None


def _build_run_warnings(environment_error_code: str | None) -> list[str]:
    """生成 M10-D2 run 级别 warning。"""
    warnings = [
        "M10-D2 EXPLAIN middle-db smoke only; production QA chain is not connected",
    ]
    if environment_error_code:
        warnings.append(f"environment_unavailable::{environment_error_code}")
    return warnings


def _write_records(path: Path, records: list[LogisticsNl2SqlEvaluationLogRecord]) -> None:
    """写出 JSONL 记录；只使用已脱敏 record。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n")


def _write_report(path: Path, report: LogisticsNl2SqlEvaluationReport) -> None:
    """写出 M10-D2 Markdown 报表。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_m10d2_markdown(report), encoding="utf-8")


def _render_m10d2_markdown(report: LogisticsNl2SqlEvaluationReport) -> str:
    """复用通用报表渲染器，并替换标题为 M10-D2 EXPLAIN smoke。"""
    markdown = render_logistics_nl2sql_evaluation_report_markdown(report)
    return markdown.replace(
        "# NL2SQL Logistics Shadow Smoke Evaluation Report",
        "# NL2SQL Logistics M10-D2 Readonly Middle DB EXPLAIN Smoke Evaluation Report",
        1,
    )


def _reset_artifact(path: Path) -> None:
    """每次 runner 开始前清理旧同名 artifact，避免多次运行 append 误判。"""
    if path.exists():
        path.unlink()


__all__ = [
    "DEFAULT_M10D2_RECORDS_FILENAME",
    "DEFAULT_M10D2_REPORT_FILENAME",
    "M10D2_EXPLAIN_SMOKE_VERSION",
    "LogisticsNl2SqlM10D2ExplainSmokeOutcome",
    "LogisticsNl2SqlM10D2ExplainSmokeRunResult",
    "LogisticsNl2SqlM10D2ExplainSmokeSample",
    "build_default_logistics_nl2sql_m10d2_explain_smoke_samples",
    "run_logistics_nl2sql_m10d2_explain_smoke",
]

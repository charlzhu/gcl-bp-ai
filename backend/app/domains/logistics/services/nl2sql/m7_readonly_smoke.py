from __future__ import annotations

from pathlib import Path
import json
import re
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
from backend.app.domains.logistics.services.nl2sql.readonly_middle_db import (
    LogisticsReadonlyMiddleDbConfig,
    LogisticsReadonlyMiddleDbExecutor,
    load_readonly_middle_db_config,
)
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader
from backend.app.domains.logistics.services.nl2sql.shadow_pipeline import (
    LogisticsNl2SqlShadowPipeline,
    LogisticsNl2SqlShadowPipelineRequest,
    LogisticsNl2SqlShadowPipelineResult,
)
from backend.app.domains.logistics.services.nl2sql.shadow_smoke import build_default_logistics_nl2sql_shadow_smoke_samples
from backend.app.domains.logistics.services.nl2sql.sql_execution import LogisticsSqlExecutionService, LogisticsSqlExecutor
from backend.app.domains.logistics.services.nl2sql.sql_safety import LogisticsSqlSafetyChecker

M7_READONLY_SMOKE_VERSION = "logistics_nl2sql_m7_readonly_middle_db_smoke.v1"
M7_HARD_MAX_LIMIT = 20
DEFAULT_M7_RECORDS_FILENAME = "m7-shadow-smoke-records.jsonl"
DEFAULT_M7_REPORT_FILENAME = "m7-shadow-smoke-report.md"
EnvironmentStatus = Literal["available", "environment_unavailable"]
ReadonlyExecutorFactory = Callable[[LogisticsReadonlyMiddleDbConfig], LogisticsSqlExecutor]


class LogisticsNl2SqlM7ReadonlySmokeSample(BaseModel):
    """M7 只读中间库 shadow smoke 样例。

    业务逻辑：
        样例只保存业务问题模板和受控 SQLPlan candidate；真实数据库连接由 runner 读取 backend/.env 后
        显式注入，只用于本阶段 shadow smoke，不接正式 QA 主链路。
    """

    model_config = ConfigDict(extra="forbid")

    sample_id: str
    description: str
    request: LogisticsNl2SqlShadowPipelineRequest


class LogisticsNl2SqlM7ReadonlySmokeOutcome(BaseModel):
    """M7 单条样例执行结果。"""

    model_config = ConfigDict(extra="forbid")

    sample: LogisticsNl2SqlM7ReadonlySmokeSample
    result: LogisticsNl2SqlShadowPipelineResult
    evaluation_log_record: LogisticsNl2SqlEvaluationLogRecord


class LogisticsNl2SqlM7ReadonlySmokeRunResult(BaseModel):
    """M7 只读中间库 shadow smoke 总返回。"""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    outcomes: list[LogisticsNl2SqlM7ReadonlySmokeOutcome] = Field(default_factory=list)
    evaluation_log_records: list[LogisticsNl2SqlEvaluationLogRecord] = Field(default_factory=list)
    report: LogisticsNl2SqlEvaluationReport
    records_path: Path
    report_path: Path
    live_smoke_executed: bool
    environment_status: EnvironmentStatus
    environment_error_code: str | None = None

    def render_markdown(self) -> str:
        """把 M7 安全评估报表渲染为 Markdown。"""

        return _render_m7_markdown(self.report)


def build_default_logistics_nl2sql_m7_readonly_smoke_samples() -> list[LogisticsNl2SqlM7ReadonlySmokeSample]:
    """构造 M7 默认只读 smoke 样例。

    返回：
        复用 M6 已审计的 SQLPlan success 样例，覆盖 ranking 与 aggregate 两类最小只读闭环。
    """

    m6_samples = build_default_logistics_nl2sql_shadow_smoke_samples()
    return [
        LogisticsNl2SqlM7ReadonlySmokeSample(
            sample_id="m7_success_valid_ranking",
            description="合法 SQLPlan + 真实只读中间库 EXPLAIN/trial smoke（ranking）",
            request=m6_samples[0].request.model_copy(update={"request_id": "m7-success-ranking"}, deep=True),
        ),
        LogisticsNl2SqlM7ReadonlySmokeSample(
            sample_id="m7_success_valid_aggregate",
            description="合法 SQLPlan + 真实只读中间库 EXPLAIN/trial smoke（aggregate）",
            request=m6_samples[7].request.model_copy(update={"request_id": "m7-success-aggregate"}, deep=True),
        ),
    ]


def run_logistics_nl2sql_m7_readonly_smoke(
    *,
    env_path: str | Path = Path("backend/.env"),
    artifact_dir: str | Path = Path("ai/outbox/kanban/t_1fceb427"),
    samples: list[LogisticsNl2SqlM7ReadonlySmokeSample] | None = None,
    executor_factory: ReadonlyExecutorFactory | None = None,
    trial_limit: int = 5,
    max_limit: int = 20,
) -> LogisticsNl2SqlM7ReadonlySmokeRunResult:
    """运行 M7 只读中间库 shadow smoke，并写出 JSONL/Markdown 脱敏报告。

    参数：
        env_path: backend/.env 路径；缺失或配置不完整时 fail-closed。
        artifact_dir: M7 验收材料目录，runner 只在该目录下写 JSONL/Markdown。
        samples: 可选样例集；默认使用 M7 scoped 样例。
        executor_factory: 可选 executor 工厂，单测可注入 stub；生产 smoke 默认使用 PyMySQL 只读 executor。
        trial_limit: 无 LIMIT SQL 在 trial 阶段追加的小样本 LIMIT，默认 5。
        max_limit: M7 safety/trial 上限，默认 20。
    返回：
        结构化 run 结果；不包含 SQL 原文、参数值或数据库连接明文。
    """

    resolved_artifact_dir = Path(artifact_dir)
    resolved_artifact_dir.mkdir(parents=True, exist_ok=True)
    records_path = resolved_artifact_dir / DEFAULT_M7_RECORDS_FILENAME
    report_path = resolved_artifact_dir / DEFAULT_M7_REPORT_FILENAME
    _reset_artifact(records_path)
    _reset_artifact(report_path)

    resolved_samples = samples or build_default_logistics_nl2sql_m7_readonly_smoke_samples()
    config_result = load_readonly_middle_db_config(env_path)
    if not config_result.ok or config_result.config is None:
        error_code = config_result.error_code or "readonly_middle_db_config_unavailable"
        record = _build_environment_unavailable_record(error_code)
        report = build_logistics_nl2sql_evaluation_report(
            [record],
            sample_ids={record.trace_id: "m7_environment_unavailable"},
            sample_descriptions={record.trace_id: "backend/.env 中间库只读配置不可用，M7 live smoke 已阻塞"},
            warnings=["M7 readonly middle-db smoke blocked by environment configuration; no live query executed"],
        )
        _write_records(records_path, [record])
        _write_report(report_path, report)
        return LogisticsNl2SqlM7ReadonlySmokeRunResult(
            outcomes=[],
            evaluation_log_records=[record],
            report=report,
            records_path=records_path,
            report_path=report_path,
            live_smoke_executed=False,
            environment_status="environment_unavailable",
            environment_error_code=error_code,
        )

    effective_max_limit = _clamp_positive_limit(max_limit, upper_bound=M7_HARD_MAX_LIMIT)
    effective_trial_limit = _clamp_positive_limit(trial_limit, upper_bound=effective_max_limit)
    catalog = LogisticsSemanticCatalogLoader().load()
    safety_checker = LogisticsSqlSafetyChecker(catalog=catalog, max_limit=effective_max_limit)
    executor = executor_factory(config_result.config) if executor_factory else LogisticsReadonlyMiddleDbExecutor(config=config_result.config)
    execution_service = LogisticsSqlExecutionService(
        executor=executor,
        safety_checker=safety_checker,
        trial_limit=effective_trial_limit,
    )
    pipeline = LogisticsNl2SqlShadowPipeline(
        catalog=catalog,
        safety_checker=safety_checker,
        execution_service=execution_service,
        pipeline_version=M7_READONLY_SMOKE_VERSION,
    )

    outcomes: list[LogisticsNl2SqlM7ReadonlySmokeOutcome] = []
    records: list[LogisticsNl2SqlEvaluationLogRecord] = []
    sample_ids_by_trace: dict[str, str] = {}
    descriptions_by_trace: dict[str, str] = {}
    secret_values = _secret_values_from_config(config_result.config)
    for sample in resolved_samples:
        try:
            raw_result = pipeline.run(sample.request)
            raw_record = raw_result.evaluation_log_record
        except Exception as exc:  # noqa: BLE001 - runner 必须单样例 fail-closed 后继续
            raw_record = _build_sample_exception_record(sample, exc)
            raw_result = _result_from_record(raw_record)
        safe_record = _sanitize_record_for_m7(raw_record, secret_values=secret_values)
        safe_result = raw_result.model_copy(update={"evaluation_log_record": safe_record, "error_message": safe_record.error_message})
        outcomes.append(
            LogisticsNl2SqlM7ReadonlySmokeOutcome(
                sample=sample,
                result=safe_result,
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
    return LogisticsNl2SqlM7ReadonlySmokeRunResult(
        outcomes=outcomes,
        evaluation_log_records=records,
        report=report,
        records_path=records_path,
        report_path=report_path,
        live_smoke_executed=environment_error_code is None,
        environment_status="environment_unavailable" if environment_error_code else "available",
        environment_error_code=environment_error_code,
    )


def _clamp_positive_limit(value: int, *, upper_bound: int) -> int:
    """把外部传入的 smoke LIMIT 钳制到 M7 固定安全上限内。"""

    try:
        numeric_value = int(value)
    except (TypeError, ValueError):
        numeric_value = upper_bound
    return max(1, min(numeric_value, upper_bound))


def _build_environment_unavailable_record(error_code: str) -> LogisticsNl2SqlEvaluationLogRecord:
    """生成环境不可用 synthetic record，不携带 .env 键值或 SQL。"""

    return LogisticsNl2SqlEvaluationLogRecord.from_pipeline(
        trace_id="m7-environment-unavailable",
        request_id=None,
        question="M7 readonly middle-db shadow smoke",
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
        pipeline_version=M7_READONLY_SMOKE_VERSION,
        warnings=["environment_unavailable"],
    )


def _build_sample_exception_record(
    sample: LogisticsNl2SqlM7ReadonlySmokeSample,
    exc: Exception,
) -> LogisticsNl2SqlEvaluationLogRecord:
    """把单样例 runner 异常收敛为可报告的受控失败 record。"""

    return LogisticsNl2SqlEvaluationLogRecord.from_pipeline(
        trace_id=f"m7-sample-exception-{sample.sample_id}",
        request_id=sample.request.request_id,
        question=sample.request.question,
        rewritten_question=sample.request.rewritten_question,
        domain=sample.request.domain,
        source_system=sample.request.source_system,
        status="render_failed",
        stage="runner",
        error_codes=["m7_readonly_smoke_sample_failed"],
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
        pipeline_version=M7_READONLY_SMOKE_VERSION,
        warnings=["single sample failed; runner continued"],
    )


def _result_from_record(record: LogisticsNl2SqlEvaluationLogRecord) -> LogisticsNl2SqlShadowPipelineResult:
    """从 synthetic record 构造 pipeline result，供 runner 异常路径复用。"""

    return LogisticsNl2SqlShadowPipelineResult(
        status="render_failed",
        stage=record.stage,
        error_codes=list(record.error_codes),
        error_message=record.error_message,
        trace_id=record.trace_id,
        sql_hash=record.sql_hash,
        sql_param_keys=list(record.sql_param_keys),
        row_count=record.row_count,
        sample_row_count=record.sample_row_count,
        explain_ok=record.explain_ok,
        trial_ok=record.trial_ok,
        evaluation_log_record=record,
        log_error=None,
    )


def _sanitize_record_for_m7(
    record: LogisticsNl2SqlEvaluationLogRecord,
    *,
    secret_values: set[str],
) -> LogisticsNl2SqlEvaluationLogRecord:
    """对 M7 artifact record 做二次脱敏，额外移除实际 host/user/db 等配置值。"""

    payload = _sanitize_payload(record.model_dump(mode="json"), secret_values=secret_values)
    return LogisticsNl2SqlEvaluationLogRecord.model_validate(payload)


def _sanitize_payload(value: Any, *, secret_values: set[str]) -> Any:
    """递归脱敏 payload，避免嵌套字段绕过。"""

    if isinstance(value, dict):
        return {str(key): _sanitize_payload(item, secret_values=secret_values) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_payload(item, secret_values=secret_values) for item in value]
    if isinstance(value, str):
        return _sanitize_m7_text(value, secret_values=secret_values)
    return value


def _sanitize_m7_text(value: str, *, secret_values: set[str]) -> str:
    """M7 artifact 文本脱敏：移除 SQL、token、Bearer、host/user/db/password 明文。"""

    safe = redact_evaluation_text(value)
    for secret_value in sorted(secret_values, key=len, reverse=True):
        if secret_value:
            safe = safe.replace(secret_value, "[REDACTED]")
    safe = re.sub(r"(?i)\bBearer\s+\[REDACTED\]", "[TOKEN_REDACTED]", safe)
    safe = re.sub(r"(?i)\b(password|passwd|token|api[_-]?key|secret)\b\s*[:=]\s*\[REDACTED\]", "credential=[REDACTED]", safe)
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
    """生成 M7 run 级别 warning，不包含 SQL 或连接明文。"""

    warnings = ["M7 readonly middle-db shadow smoke only; production QA chain is not connected"]
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
    """写出 M7 Markdown 报表。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_m7_markdown(report), encoding="utf-8")


def _render_m7_markdown(report: LogisticsNl2SqlEvaluationReport) -> str:
    """复用 M6 报表渲染器，并替换标题为 M7 只读 smoke。"""

    markdown = render_logistics_nl2sql_evaluation_report_markdown(report)
    return markdown.replace(
        "# NL2SQL Logistics M6 Shadow Smoke Evaluation Report",
        "# NL2SQL Logistics M7 Readonly Middle DB Shadow Smoke Evaluation Report",
        1,
    )


def _reset_artifact(path: Path) -> None:
    """每次 runner 开始前清理旧同名 artifact，避免多次运行 append 误判。"""

    if path.exists():
        path.unlink()


__all__ = [
    "DEFAULT_M7_RECORDS_FILENAME",
    "DEFAULT_M7_REPORT_FILENAME",
    "M7_READONLY_SMOKE_VERSION",
    "LogisticsNl2SqlM7ReadonlySmokeOutcome",
    "LogisticsNl2SqlM7ReadonlySmokeRunResult",
    "LogisticsNl2SqlM7ReadonlySmokeSample",
    "build_default_logistics_nl2sql_m7_readonly_smoke_samples",
    "run_logistics_nl2sql_m7_readonly_smoke",
]

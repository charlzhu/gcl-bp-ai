from __future__ import annotations

import hashlib
import time
from typing import Any, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domains.logistics.services.nl2sql.evaluation_log import (
    InMemoryLogisticsNl2SqlEvaluationLogSink,
    LogisticsNl2SqlEvaluationLogRecord,
    LogisticsNl2SqlEvaluationLogSink,
    redact_evaluation_text,
)
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalog, LogisticsSemanticCatalogLoader
from backend.app.domains.logistics.services.nl2sql.sql_execution import (
    FakeLogisticsSqlExecutor,
    LogisticsSqlExecutionService,
)
from backend.app.domains.logistics.services.nl2sql.sql_plan import (
    LogisticsSqlPlanValidationResult,
    LogisticsSqlPlanValidator,
)
from backend.app.domains.logistics.services.nl2sql.sql_renderer import LogisticsRenderedSql, LogisticsSqlRenderer
from backend.app.domains.logistics.services.nl2sql.sql_safety import LogisticsSqlSafetyChecker

SHADOW_PIPELINE_VERSION = "logistics_nl2sql_shadow.v1"
ShadowPipelineStatus = Literal[
    "success",
    "unsupported",
    "validation_failed",
    "render_failed",
    "safety_failed",
    "explain_failed",
    "trial_failed",
    "skipped",
]


class LogisticsNl2SqlRendererProtocol(Protocol):
    """shadow pipeline 使用的 renderer 协议，方便单测注入 fake renderer。"""

    def render(self, validation_result: LogisticsSqlPlanValidationResult) -> LogisticsRenderedSql:
        """把通过 M3 校验的 plan 渲染为参数化 SQL。"""


class LogisticsNl2SqlShadowPipelineRequest(BaseModel):
    """物流 NL2SQL shadow pipeline 请求。

    参数：
        question: 原始用户问题，仅进入脱敏评估日志，不暴露给正式回答链路。
        rewritten_question: 可选 query rewrite 输出。
        domain: 业务域，MVP 仅允许 logistics。
        source_system: 数据来源边界，MVP 仅允许 middle_db。
        candidate: 受控 SQLPlan candidate；MVP 可由测试或上游 shadow wrapper 注入。
        request_id: 上游请求追踪 ID。
        dry_run: 预留字段；MVP 始终只做 shadow/dry-run，不接正式 QA 主链路。
    返回：
        Pydantic 请求对象。
    """

    model_config = ConfigDict(extra="forbid")

    question: str
    rewritten_question: str | None = None
    domain: str = "logistics"
    source_system: str = "middle_db"
    candidate: dict[str, Any] | None = None
    request_id: str | None = None
    dry_run: bool = True


class LogisticsNl2SqlShadowPipelineResult(BaseModel):
    """物流 NL2SQL shadow pipeline 返回。

    业务逻辑：
        结果只保留状态、错误码、SQL hash、参数 key、执行摘要和 evaluation log；不返回 SQL 原文、
        参数值或数据库连接信息，避免内部技术 trace 泄露到用户可见路径。
    """

    model_config = ConfigDict(extra="forbid")

    status: ShadowPipelineStatus
    stage: str
    error_codes: list[str] = Field(default_factory=list)
    error_message: str | None = None
    trace_id: str
    sql_hash: str | None = None
    sql_param_keys: list[str] = Field(default_factory=list)
    row_count: int = 0
    sample_row_count: int = 0
    explain_ok: bool = False
    trial_ok: bool = False
    evaluation_log_record: LogisticsNl2SqlEvaluationLogRecord
    log_error: str | None = None


class LogisticsNl2SqlShadowPipeline:
    """物流 NL2SQL 影子流水线。

    业务逻辑：
        该流水线只用于内部 shadow/evaluation，串联 M3 SQLPlan Validator、M4 Renderer、M4 Safety、
        EXPLAIN/trial execution 与 evaluation log。它不接正式物流 QA 主链路，不读取 `.env` 凭据，默认
        使用 fake executor，只有调用方显式注入执行服务时才会触达外部资源。
    """

    def __init__(
        self,
        *,
        catalog: LogisticsSemanticCatalog | None = None,
        validator: LogisticsSqlPlanValidator | None = None,
        renderer: LogisticsNl2SqlRendererProtocol | None = None,
        safety_checker: LogisticsSqlSafetyChecker | None = None,
        execution_service: LogisticsSqlExecutionService | None = None,
        log_sink: LogisticsNl2SqlEvaluationLogSink | None = None,
        pipeline_version: str = SHADOW_PIPELINE_VERSION,
    ) -> None:
        """初始化 shadow pipeline。"""

        resolved_catalog = catalog or LogisticsSemanticCatalogLoader().load()
        self.validator = validator or LogisticsSqlPlanValidator(catalog=resolved_catalog)
        self.renderer = renderer or LogisticsSqlRenderer(catalog=resolved_catalog)
        self.safety_checker = safety_checker or LogisticsSqlSafetyChecker(catalog=resolved_catalog)
        self.execution_service = execution_service or LogisticsSqlExecutionService(
            executor=FakeLogisticsSqlExecutor(),
            safety_checker=self.safety_checker,
        )
        self.log_sink = log_sink or InMemoryLogisticsNl2SqlEvaluationLogSink()
        self.pipeline_version = pipeline_version

    def run(self, request: LogisticsNl2SqlShadowPipelineRequest) -> LogisticsNl2SqlShadowPipelineResult:
        """执行一次 shadow pipeline。

        参数：
            request: shadow 请求，包含用户问题与受控 SQLPlan candidate。
        返回：
            shadow 状态、错误码、执行摘要和脱敏 evaluation log。
        """

        started = time.perf_counter()
        trace_id = uuid4().hex
        catalog_ids, catalog_versions = _catalog_trace(request.candidate)
        sql_hash: str | None = None
        sql_param_keys: list[str] = []
        validation_errors: list[str] = []
        safety_errors: list[str] = []
        warnings: list[str] = []
        error_message: str | None = None
        row_count = 0
        sample_row_count = 0
        explain_ok = False
        trial_ok = False

        if request.domain != "logistics":
            return self._finish(
                request=request,
                trace_id=trace_id,
                started=started,
                status="skipped",
                stage="domain",
                error_codes=[f"shadow_domain_not_supported::{request.domain}"],
                error_message=None,
                catalog_ids=catalog_ids,
                catalog_versions=catalog_versions,
            )
        if request.source_system != "middle_db":
            return self._finish(
                request=request,
                trace_id=trace_id,
                started=started,
                status="skipped",
                stage="source_system",
                error_codes=[f"shadow_source_system_not_supported::{request.source_system}"],
                error_message=None,
                catalog_ids=catalog_ids,
                catalog_versions=catalog_versions,
            )
        if not request.candidate:
            return self._finish(
                request=request,
                trace_id=trace_id,
                started=started,
                status="skipped",
                stage="candidate",
                error_codes=["shadow_candidate_missing"],
                error_message=None,
                catalog_ids=catalog_ids,
                catalog_versions=catalog_versions,
            )

        strategy = str(request.candidate.get("strategy") or "")
        if strategy != "sql_direct":
            return self._finish(
                request=request,
                trace_id=trace_id,
                started=started,
                status="unsupported",
                stage="candidate",
                error_codes=[f"shadow_strategy_not_sql_direct::{strategy or 'missing'}"],
                error_message=None,
                catalog_ids=catalog_ids,
                catalog_versions=catalog_versions,
            )

        validation_result = self.validator.validate(request.candidate)
        if not validation_result.ok:
            validation_errors = validation_result.error_codes
            return self._finish(
                request=request,
                trace_id=trace_id,
                started=started,
                status="validation_failed",
                stage="validation",
                error_codes=validation_errors,
                error_message=None,
                catalog_ids=catalog_ids,
                catalog_versions=catalog_versions,
                validation_errors=validation_errors,
            )

        try:
            rendered = self.renderer.render(validation_result)
        except Exception as exc:  # noqa: BLE001 - renderer 是 shadow 边界，失败需转为评估日志
            error_message = redact_evaluation_text(str(exc))
            return self._finish(
                request=request,
                trace_id=trace_id,
                started=started,
                status="render_failed",
                stage="render",
                error_codes=["shadow_render_failed"],
                error_message=error_message,
                catalog_ids=catalog_ids,
                catalog_versions=catalog_versions,
                validation_errors=validation_errors,
            )

        sql_hash = _hash_sql(rendered.sql)
        sql_param_keys = list(rendered.params)
        warnings = list(rendered.warnings)

        safety_result = self.safety_checker.check(rendered)
        if not safety_result.ok:
            safety_errors = safety_result.error_codes
            return self._finish(
                request=request,
                trace_id=trace_id,
                started=started,
                status="safety_failed",
                stage="safety",
                error_codes=safety_errors,
                error_message=None,
                catalog_ids=catalog_ids,
                catalog_versions=catalog_versions,
                sql_hash=sql_hash,
                sql_param_keys=sql_param_keys,
                validation_errors=validation_errors,
                safety_errors=safety_errors,
                warnings=warnings,
            )

        explain_result = self.execution_service.explain(rendered)
        explain_ok = explain_result.ok
        if not explain_result.ok:
            error_message = explain_result.error
            return self._finish(
                request=request,
                trace_id=trace_id,
                started=started,
                status="explain_failed",
                stage="explain",
                error_codes=explain_result.error_codes,
                error_message=error_message,
                catalog_ids=catalog_ids,
                catalog_versions=catalog_versions,
                sql_hash=sql_hash,
                sql_param_keys=sql_param_keys,
                validation_errors=validation_errors,
                safety_errors=safety_errors,
                explain_ok=explain_ok,
                warnings=warnings,
            )

        trial_result = self.execution_service.trial(rendered)
        trial_ok = trial_result.ok
        if not trial_result.ok:
            error_message = trial_result.error
            return self._finish(
                request=request,
                trace_id=trace_id,
                started=started,
                status="trial_failed",
                stage="trial",
                error_codes=trial_result.error_codes,
                error_message=error_message,
                catalog_ids=catalog_ids,
                catalog_versions=catalog_versions,
                sql_hash=sql_hash,
                sql_param_keys=sql_param_keys,
                validation_errors=validation_errors,
                safety_errors=safety_errors,
                explain_ok=explain_ok,
                trial_ok=trial_ok,
                warnings=warnings,
            )

        row_count = len(trial_result.rows)
        sample_row_count = len(trial_result.rows)
        return self._finish(
            request=request,
            trace_id=trace_id,
            started=started,
            status="success",
            stage="trial",
            error_codes=[],
            error_message=None,
            catalog_ids=catalog_ids,
            catalog_versions=catalog_versions,
            sql_hash=sql_hash,
            sql_param_keys=sql_param_keys,
            validation_errors=validation_errors,
            safety_errors=safety_errors,
            explain_ok=explain_ok,
            trial_ok=trial_ok,
            row_count=row_count,
            sample_row_count=sample_row_count,
            warnings=warnings,
        )

    def _finish(
        self,
        *,
        request: LogisticsNl2SqlShadowPipelineRequest,
        trace_id: str,
        started: float,
        status: ShadowPipelineStatus,
        stage: str,
        error_codes: list[str],
        error_message: str | None,
        catalog_ids: list[str],
        catalog_versions: list[str],
        sql_hash: str | None = None,
        sql_param_keys: list[str] | None = None,
        validation_errors: list[str] | None = None,
        safety_errors: list[str] | None = None,
        explain_ok: bool = False,
        trial_ok: bool = False,
        row_count: int = 0,
        sample_row_count: int = 0,
        warnings: list[str] | None = None,
    ) -> LogisticsNl2SqlShadowPipelineResult:
        """构造评估日志并返回 shadow 结果。

        业务逻辑：
            evaluation log 写失败只记录到 `log_error`，不改变 shadow 主状态，避免评估链路影响主流程。
        """

        duration_ms = int((time.perf_counter() - started) * 1000)
        record = LogisticsNl2SqlEvaluationLogRecord.from_pipeline(
            trace_id=trace_id,
            request_id=request.request_id,
            question=request.question,
            rewritten_question=request.rewritten_question,
            domain=request.domain,
            source_system=request.source_system,
            status=status,
            stage=stage,
            error_codes=error_codes,
            error_message=error_message,
            catalog_ids=catalog_ids,
            catalog_versions=catalog_versions,
            sql_hash=sql_hash,
            sql_param_keys=sql_param_keys or [],
            validation_errors=validation_errors or [],
            safety_errors=safety_errors or [],
            explain_ok=explain_ok,
            trial_ok=trial_ok,
            row_count=row_count,
            sample_row_count=sample_row_count,
            duration_ms=duration_ms,
            pipeline_version=self.pipeline_version,
            warnings=warnings or [],
        )
        log_error = self._write_log(record)
        return LogisticsNl2SqlShadowPipelineResult(
            status=status,
            stage=stage,
            error_codes=list(record.error_codes),
            error_message=record.error_message,
            trace_id=trace_id,
            sql_hash=sql_hash,
            sql_param_keys=list(record.sql_param_keys),
            row_count=max(0, int(row_count)),
            sample_row_count=max(0, int(sample_row_count)),
            explain_ok=explain_ok,
            trial_ok=trial_ok,
            evaluation_log_record=record,
            log_error=log_error,
        )

    def _write_log(self, record: LogisticsNl2SqlEvaluationLogRecord) -> str | None:
        """写评估日志；失败时返回脱敏错误。"""

        try:
            self.log_sink.write(record)
            return None
        except Exception as exc:  # noqa: BLE001 - 日志 sink 失败不能阻断 shadow 结果
            return redact_evaluation_text(str(exc))


def _catalog_trace(candidate: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    """从 candidate.catalog_refs 中提取 catalog 追踪信息。"""

    if not candidate:
        return [], []
    catalog_ids: list[str] = []
    catalog_versions: list[str] = []
    refs = candidate.get("catalog_refs") or []
    if not isinstance(refs, list):
        return [], []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        catalog_id = str(ref.get("catalog_id") or "").strip()
        catalog_version = str(ref.get("catalog_version") or "").strip()
        if catalog_id and catalog_id not in catalog_ids:
            catalog_ids.append(catalog_id)
        if catalog_version and catalog_version not in catalog_versions:
            catalog_versions.append(catalog_version)
    return catalog_ids, catalog_versions


def _hash_sql(sql: str) -> str:
    """返回 SQL 文本 SHA256，日志与结果只保留 hash，不保留 SQL 原文。"""

    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


__all__ = [
    "SHADOW_PIPELINE_VERSION",
    "LogisticsNl2SqlShadowPipeline",
    "LogisticsNl2SqlShadowPipelineRequest",
    "LogisticsNl2SqlShadowPipelineResult",
]

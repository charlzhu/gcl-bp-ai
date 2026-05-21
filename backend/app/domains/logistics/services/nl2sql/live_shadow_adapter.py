from __future__ import annotations

import os
import re
import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaResult
from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import LogisticsCatalogRecallService
from backend.app.domains.logistics.services.nl2sql.evaluation_log import redact_evaluation_text
from backend.app.domains.logistics.services.nl2sql.m9_sqlplan_generation import (
    LogisticsNl2SqlDomainRouter,
    LogisticsNl2SqlQueryRewriteService,
    LogisticsSqlPlanGenerationResult,
    LogisticsSqlPlanGenerator,
    _rewrite_unsupported_error_codes,
    _slot_summary,
)
from backend.app.domains.logistics.services.nl2sql.shadow_pipeline import (
    LogisticsNl2SqlShadowPipeline,
    LogisticsNl2SqlShadowPipelineRequest,
)

LIVE_SHADOW_ENV_FLAG = "LOGISTICS_NL2SQL_LIVE_SHADOW_ENABLED"
LIVE_SHADOW_SUMMARY_SCHEMA_VERSION = "logistics_nl2sql_live_shadow_summary.v1"
_TRUTHY_VALUES = {"1", "true", "yes", "y", "on", "enabled"}
_SAFE_STATUS_CODES = {"disabled", "skipped", "success", "error", "validation_failed"}
_SAFE_STAGE_CODES = {"disabled", "rewrite", "route", "generation", "candidate_sql_gate", "pipeline", "adapter", "trial", "explain"}
_CANDIDATE_SQL_GATE_REASON_CODES = {
    "allowed",
    "empty_sql",
    "multi_statement",
    "comment_forbidden",
    "union_forbidden",
    "not_select",
    "missing_limit",
    "structure_uncertain",
    "limit_out_of_range",
    "into_outfile_forbidden",
    "into_forbidden",
    "load_file_forbidden",
    "sleep_forbidden",
    "benchmark_forbidden",
    "lock_forbidden",
    "for_update_forbidden",
    "transaction_forbidden",
    "write_or_ddl_forbidden",
}
_SAFE_EXACT_ERROR_CODES = {
    "ok",
    "m10c_live_shadow_disabled",
    "m10c_route_skipped",
    "m10c_live_shadow_error",
    "m10c_live_shadow_audit_error",
    "m10c_error_redacted",
}
_SAFE_GENERATION_STATUS_CODES = {"error", "skipped", "validation_failed", "blocked", "unsupported"}
_SAFE_AUDIT_ERROR_MESSAGES = {"shadow audit failed"}
_SAFE_TOKEN_RE = re.compile(r"[^a-z0-9_]+")


def _stable_code_token(value: Any) -> str:
    """把任意错误片段收敛成小写安全 token，避免表字段/SQL 进入历史摘要。"""

    return _SAFE_TOKEN_RE.sub("_", str(value or "").strip().lower()).strip("_")[:80]


def _safe_candidate_gate_reason(value: Any) -> str | None:
    """仅允许 M10-B candidate SQL gate 的固定原因码进入摘要。"""

    reason = _stable_code_token(value)
    if reason in _CANDIDATE_SQL_GATE_REASON_CODES:
        return reason
    return "redacted" if reason else None


def _safe_live_shadow_error_code(value: Any) -> str | None:
    """把 live-shadow 任意错误码映射为历史可见的稳定白名单码。

    业务逻辑：
        历史详情可能被前端查询，因此不能把 provider/debug、SQLPlan 内部码、表名或字段名
        原样写入 `response_meta`。只有 M10-C 自有稳定码和 M10-B candidate gate 白名单码可带后缀。
    """

    text = redact_evaluation_text(str(value or "")).strip()
    if not text:
        return None
    token = text.split()[0]
    if "::" in token:
        prefix, suffix = token.split("::", 1)
        prefix_token = _stable_code_token(prefix)
        suffix_token = _stable_code_token(suffix)
        if prefix_token == "m10c_generation_not_ok":
            safe_status = suffix_token if suffix_token in _SAFE_GENERATION_STATUS_CODES else "redacted"
            return f"m10c_generation_not_ok::{safe_status}"
        if prefix_token == "candidate_sql_gate_rejected":
            safe_reason = _safe_candidate_gate_reason(suffix_token) or "redacted"
            return f"candidate_sql_gate_rejected::{safe_reason}"
        return "m10c_error_redacted"
    token = _stable_code_token(token)
    if not token:
        return None
    if token in _SAFE_EXACT_ERROR_CODES:
        return token
    if token in _CANDIDATE_SQL_GATE_REASON_CODES:
        return f"candidate_sql_gate_rejected::{token}"
    return "m10c_error_redacted"


class LogisticsNl2SqlLiveShadowSummary(BaseModel):
    """物流正式 QA 旁路 NL2SQL shadow 的脱敏摘要。

    参数：
        schema_version: 摘要结构版本。
        enabled: 本次旁路是否显式开启。
        shadow_only: 固定为 True，表示不得接管正式回答。
        status: disabled/skipped/success/error 等稳定状态。
        stage: 停止阶段，例如 rewrite/recall/generation/pipeline。
        error_codes: 脱敏错误码列表，禁止包含 SQL 原文或密钥。
        error_message: 脱敏错误摘要，可为空。
        trace_id: 上游正式 QA trace_id，仅用于审计串联。
        formal_status: 正式 QA 的业务状态摘要，不含 query_key。
        sql_hash: pipeline 产物 SQL hash；非 64 位十六进制会被丢弃。
        row_count: shadow 试执行摘要行数。
        candidate_sql_gate_*: M10-B raw candidate SQL 门禁脱敏摘要。
        duration_ms: 本次旁路耗时毫秒。
    返回：
        可安全写入服务端历史快照的 JSON 对象；不面向用户展示。
    """

    model_config = ConfigDict(extra="forbid", validate_default=True)

    schema_version: str = LIVE_SHADOW_SUMMARY_SCHEMA_VERSION
    enabled: bool = False
    shadow_only: bool = True
    status: str
    stage: str
    error_codes: list[str] = Field(default_factory=list)
    error_message: str | None = None
    trace_id: str | None = None
    formal_status: str | None = None
    sql_hash: str | None = None
    row_count: int = 0
    candidate_sql_gate_allowed: bool | None = None
    candidate_sql_gate_rejected: bool | None = None
    candidate_sql_gate_reason_code: str | None = None
    duration_ms: int = 0

    @field_validator("status", mode="before")
    @classmethod
    def _sanitize_status(cls, value: Any) -> str:
        """状态字段只允许固定枚举，异常输入收敛为 error。"""

        status = _stable_code_token(value)
        return status if status in _SAFE_STATUS_CODES else "error"

    @field_validator("stage", mode="before")
    @classmethod
    def _sanitize_stage(cls, value: Any) -> str:
        """阶段字段只允许固定枚举，异常输入收敛为 pipeline。"""

        stage = _stable_code_token(value)
        return stage if stage in _SAFE_STAGE_CODES else "pipeline"

    @field_validator("error_message", mode="before")
    @classmethod
    def _sanitize_error_message(cls, value: Any) -> str | None:
        """错误描述不保存 provider/debug 原文，只保留少量业务安全文案。"""

        if value is None:
            return None
        text = redact_evaluation_text(str(value)).strip()
        if not text:
            return None
        if text in _SAFE_AUDIT_ERROR_MESSAGES:
            return text
        return "shadow error redacted"

    @field_validator(
        "schema_version",
        "trace_id",
        "formal_status",
        mode="before",
    )
    @classmethod
    def _sanitize_text(cls, value: Any) -> str | None:
        """对摘要文本字段统一脱敏，避免 SQL/密钥进入历史快照。"""

        if value is None:
            return None
        text = redact_evaluation_text(str(value)).strip()
        return text[:240] if text else None

    @field_validator("candidate_sql_gate_reason_code", mode="before")
    @classmethod
    def _sanitize_candidate_sql_gate_reason_code(cls, value: Any) -> str | None:
        """candidate SQL gate reason 只允许固定枚举，防止下游拼入表字段。"""

        return _safe_candidate_gate_reason(value)

    @field_validator("error_codes", mode="before")
    @classmethod
    def _sanitize_error_codes(cls, value: Any) -> list[str]:
        """错误码列表只保留历史可见白名单稳定码。"""

        if value is None:
            raw_items: list[Any] = []
        elif isinstance(value, str):
            raw_items = [value]
        elif isinstance(value, (list, tuple, set)):
            raw_items = list(value)
        else:
            raw_items = [value]
        result: list[str] = []
        seen: set[str] = set()
        for item in raw_items:
            text = _safe_live_shadow_error_code(item)
            if text and text not in seen:
                seen.add(text)
                result.append(text)
        return result

    @field_validator("sql_hash", mode="before")
    @classmethod
    def _sanitize_sql_hash(cls, value: Any) -> str | None:
        """SQL hash 只允许 64 位十六进制，防止误写 SQL 原文。"""

        if value is None:
            return None
        text = str(value).strip().lower()
        if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
            return text
        return None

    @field_validator("row_count", "duration_ms", mode="before")
    @classmethod
    def _sanitize_non_negative_int(cls, value: Any) -> int:
        """计数字段统一收敛为非负整数。"""

        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return 0


class LogisticsNl2SqlLiveShadowAdapter:
    """物流正式 QA 主链路旁路 NL2SQL live-provider shadow adapter。

    业务逻辑：
        1. 默认关闭，不构造召回、LLM 或 pipeline 外部依赖；
        2. 显式开启后按 M9 query rewrite -> domain route -> catalog recall -> SQLPlan generator -> M10-B shadow pipeline 执行；
        3. 任一异常都 fail-closed 成脱敏摘要，不改变正式物流 QA 结果；
        4. 返回对象仅供服务端审计，不进入用户可见回答。
    """

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        rewrite_service: LogisticsNl2SqlQueryRewriteService | None = None,
        domain_router: LogisticsNl2SqlDomainRouter | None = None,
        recall_service_factory: Callable[[], Any] | None = None,
        generator_factory: Callable[[], Any] | None = None,
        pipeline_factory: Callable[[], Any] | None = None,
        env_flag: str = LIVE_SHADOW_ENV_FLAG,
    ) -> None:
        """初始化 adapter。

        参数：
            enabled: 显式开关；None 时读取环境变量，缺省为关闭。
            rewrite_service: Query Rewrite 服务，默认本地轻量实现。
            domain_router: 领域路由器，默认只允许物流中间库。
            recall_service_factory: 召回服务工厂，开启后才会调用。
            generator_factory: SQLPlan 生成器工厂，开启后才会调用。
            pipeline_factory: shadow pipeline 工厂，开启后才会调用。
            env_flag: 环境变量名，测试可覆盖。
        返回：无返回值。
        """

        self._enabled_override = enabled
        self.env_flag = env_flag
        self.rewrite_service = rewrite_service or LogisticsNl2SqlQueryRewriteService()
        self.domain_router = domain_router or LogisticsNl2SqlDomainRouter()
        self.recall_service_factory = recall_service_factory or (lambda: LogisticsCatalogRecallService())
        self.generator_factory = generator_factory or (lambda: LogisticsSqlPlanGenerator())
        self.pipeline_factory = pipeline_factory or (lambda: LogisticsNl2SqlShadowPipeline())

    def run_shadow(
        self,
        *,
        question: str,
        trace_id: str | None = None,
        formal_result: LogisticsDataQaResult | None = None,
        formal_status: str | None = None,
        raw_candidate_sql: str | None = None,
        domain: str = "logistics",
    ) -> LogisticsNl2SqlLiveShadowSummary:
        """执行一次正式 QA 旁路 shadow，并返回脱敏审计摘要。

        参数：
            question: 用户原始问题，仅进入 shadow provider 和脱敏审计。
            trace_id: 正式 QA 请求追踪号。
            formal_result: 已完成的正式 QA 结果；只用于生成状态摘要，不读取 query_key。
            formal_status: 调用方显式传入的正式状态，优先级高于 formal_result 推导。
            raw_candidate_sql: 可选原始候选 SQL，只允许交给 M10-B gate 审计，绝不执行。
            domain: 业务域名称，用于路由识别；默认 logistics。
        返回：
            `LogisticsNl2SqlLiveShadowSummary` 脱敏摘要。
        """

        enabled = self._is_enabled()
        if not enabled:
            return LogisticsNl2SqlLiveShadowSummary(
                enabled=False,
                status="disabled",
                stage="disabled",
                trace_id=trace_id,
                formal_status=formal_status or self._formal_status(formal_result),
                error_codes=["m10c_live_shadow_disabled"],
            )

        started = time.perf_counter()
        resolved_formal_status = formal_status or self._formal_status(formal_result)
        try:
            rewrite = self.rewrite_service.rewrite(question)
            rewrite_error_codes = _rewrite_unsupported_error_codes(rewrite)
            if rewrite_error_codes:
                return self._summary(
                    started=started,
                    status="skipped",
                    stage="rewrite",
                    trace_id=trace_id,
                    formal_status=resolved_formal_status,
                    error_codes=rewrite_error_codes,
                )

            route = self.domain_router.route(rewrite.normalized_question)
            if not route.should_process:
                return self._summary(
                    started=started,
                    status="skipped",
                    stage="route",
                    trace_id=trace_id,
                    formal_status=resolved_formal_status,
                    error_codes=[route.reason_code or "m10c_route_skipped"],
                )

            recall_result = self.recall_service_factory().recall(
                question=question,
                normalized_question=rewrite.normalized_question,
                slot_summary=_slot_summary(rewrite),
            )
            generation = self.generator_factory().generate(
                original_question=question,
                normalized_question=rewrite.normalized_question,
                route=route,
                recall_result=recall_result,
            )
            if not isinstance(generation, LogisticsSqlPlanGenerationResult):
                generation = LogisticsSqlPlanGenerationResult.model_validate(generation)
            if generation.status != "ok" or not generation.candidate:
                return self._summary(
                    started=started,
                    status="error" if generation.status == "error" else "skipped",
                    stage="generation",
                    trace_id=trace_id,
                    formal_status=resolved_formal_status,
                    error_codes=[f"m10c_generation_not_ok::{generation.status}", *generation.error_codes],
                    error_message=generation.error_message,
                )

            pipeline_result = self.pipeline_factory().run(
                LogisticsNl2SqlShadowPipelineRequest(
                    question=question,
                    rewritten_question=rewrite.normalized_question,
                    domain=route.domain,
                    source_system=route.source_system,
                    candidate=generation.candidate,
                    raw_candidate_sql=raw_candidate_sql,
                    request_id=trace_id,
                    dry_run=True,
                )
            )
            return self._summary_from_pipeline(
                started=started,
                trace_id=trace_id,
                formal_status=resolved_formal_status,
                pipeline_result=pipeline_result,
            )
        except Exception as exc:  # noqa: BLE001 - shadow 旁路必须 fail-closed，不影响正式 QA。
            return self._summary(
                started=started,
                status="error",
                stage="adapter",
                trace_id=trace_id,
                formal_status=resolved_formal_status,
                error_codes=["m10c_live_shadow_error"],
                error_message=str(exc),
            )

    def _is_enabled(self) -> bool:
        """解析显式或环境变量开关；缺省必须关闭。"""

        if self._enabled_override is not None:
            return bool(self._enabled_override)
        return str(os.getenv(self.env_flag, "")).strip().lower() in _TRUTHY_VALUES

    def _summary_from_pipeline(
        self,
        *,
        started: float,
        trace_id: str | None,
        formal_status: str | None,
        pipeline_result: Any,
    ) -> LogisticsNl2SqlLiveShadowSummary:
        """把 M10-B shadow pipeline 返回收敛成服务端脱敏摘要。"""

        return self._summary(
            started=started,
            status=str(getattr(pipeline_result, "status", "error") or "error"),
            stage=str(getattr(pipeline_result, "stage", "pipeline") or "pipeline"),
            trace_id=trace_id,
            formal_status=formal_status,
            error_codes=list(getattr(pipeline_result, "error_codes", []) or []),
            error_message=getattr(pipeline_result, "error_message", None),
            sql_hash=getattr(pipeline_result, "sql_hash", None),
            row_count=getattr(pipeline_result, "row_count", 0),
            candidate_sql_gate_allowed=getattr(pipeline_result, "candidate_sql_gate_allowed", None),
            candidate_sql_gate_rejected=getattr(pipeline_result, "candidate_sql_gate_rejected", None),
            candidate_sql_gate_reason_code=getattr(pipeline_result, "candidate_sql_gate_reason_code", None),
        )

    @staticmethod
    def _summary(
        *,
        started: float,
        status: str,
        stage: str,
        trace_id: str | None,
        formal_status: str | None,
        error_codes: list[str] | None = None,
        error_message: str | None = None,
        sql_hash: str | None = None,
        row_count: int = 0,
        candidate_sql_gate_allowed: bool | None = None,
        candidate_sql_gate_rejected: bool | None = None,
        candidate_sql_gate_reason_code: str | None = None,
    ) -> LogisticsNl2SqlLiveShadowSummary:
        """统一构造摘要，确保耗时和脱敏规则一致。"""

        return LogisticsNl2SqlLiveShadowSummary(
            enabled=True,
            status=status,
            stage=stage,
            trace_id=trace_id,
            formal_status=formal_status,
            error_codes=error_codes or [],
            error_message=error_message,
            sql_hash=sql_hash,
            row_count=row_count,
            candidate_sql_gate_allowed=candidate_sql_gate_allowed,
            candidate_sql_gate_rejected=candidate_sql_gate_rejected,
            candidate_sql_gate_reason_code=candidate_sql_gate_reason_code,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    @staticmethod
    def _formal_status(result: LogisticsDataQaResult | None) -> str | None:
        """从正式 QA 结果推导业务状态摘要，不暴露 query_key 或内部 planner 信息。"""

        if result is None:
            return None
        if result.needs_clarification:
            return "CLARIFICATION"
        if not result.supported:
            return "UNSUPPORTED"
        if result.status and result.status.code == "EXECUTION_ERROR":
            return "ERROR"
        if result.status and result.status.code == "EMPTY_RESULT":
            return "EMPTY_RESULT"
        if not result.result_table.rows:
            return "EMPTY_RESULT"
        return "SUCCESS"


__all__ = [
    "LIVE_SHADOW_ENV_FLAG",
    "LIVE_SHADOW_SUMMARY_SCHEMA_VERSION",
    "LogisticsNl2SqlLiveShadowAdapter",
    "LogisticsNl2SqlLiveShadowSummary",
]

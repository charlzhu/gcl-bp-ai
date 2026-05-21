from __future__ import annotations
import hashlib
import time
from collections.abc import Callable
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from backend.app.domains.logistics.services.nl2sql.evaluation_log import redact_evaluation_text
from backend.app.domains.logistics.services.nl2sql.sql_execution import (
    FakeLogisticsSqlExecutor,
    LogisticsSqlExecutionService,
    LogisticsSqlExecutor,
)
from backend.app.domains.logistics.services.nl2sql.sql_renderer import LogisticsRenderedSql
from backend.app.domains.logistics.services.nl2sql.sql_safety import LogisticsSqlSafetyChecker
M10D_SHADOW_GATE_SCHEMA_VERSION = "logistics_nl2sql_m10d_shadow_gate.v1"
M10D_ALLOWED_SOURCE_SYSTEM = "middle_db"
M10DGateStatus = Literal["success", "failed", "skipped", "disabled"]
M10DStepStatus = Literal["success", "failed", "skipped", "disabled"]
class LogisticsNl2SqlM10DShadowGateConfig(BaseModel):
    """物流 NL2SQL M10-D shadow gate 配置。
    参数：
        enabled: M10-D gate 总开关，默认关闭，关闭时不得构造 executor。
        explain_enabled: 是否运行 EXPLAIN gate；默认关闭。
        trial_enabled: 是否运行 readonly trial gate；默认关闭，且必须依赖 EXPLAIN 成功。
        real_db_access_enabled: 是否允许访问真实 MySQL 中间库；默认关闭。
        timeout_ms: 本次 gate 期望超时时间，仅记录脱敏审计摘要；D1 fake executor 不做真实计时中断。
        row_cap: trial 行数摘要上限，只影响报告中的 row_count，不返回业务行值。
        env_path: 非空时指向 backend/.env 路径，用于加载中间库配置。
    返回：
        可注入 gate 的只读配置对象。
    """
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    explain_enabled: bool = False
    trial_enabled: bool = False
    real_db_access_enabled: bool = False
    timeout_ms: int = 1000
    row_cap: int = 0
    env_path: str = ""
    @field_validator("timeout_ms", mode="before")
    @classmethod
    def _sanitize_timeout_ms(cls, value: object) -> int:
        """超时时间收敛为非负整数，避免非法配置进入报告。"""
        try:
            parsed = int(value)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001 - 配置边界统一兜底
            return 1000
        return max(0, parsed)
    @field_validator("row_cap", mode="before")
    @classmethod
    def _sanitize_row_cap(cls, value: object) -> int:
        """trial row cap 收敛为非负整数，0 表示报告不暴露任何行值数量之外的数据。"""
        try:
            parsed = int(value)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001 - 配置边界统一兜底
            return 0
        return max(0, parsed)
class LogisticsNl2SqlM10DShadowGateReport(BaseModel):
    """物流 NL2SQL M10-D gate 脱敏报告。
    业务逻辑：
        该报告只允许输出 D0 设计中的安全字段：状态、阶段、稳定错误码、EXPLAIN/trial 状态、行数摘要、
        timeout/elapsed、SQL hash 与 gate reason code。禁止输出 SQL 原文、参数值、表名、字段名、连接串、
        executor 异常原文或 trial 行值。
    """
    model_config = ConfigDict(extra="forbid", validate_default=True)
    schema_version: str = M10D_SHADOW_GATE_SCHEMA_VERSION
    enabled: bool
    status: M10DGateStatus
    stage: str
    error_codes: list[str] = Field(default_factory=list)
    explain_status: M10DStepStatus = "disabled"
    trial_status: M10DStepStatus = "disabled"
    row_count: int = 0
    row_cap_applied: bool = False
    timeout_ms: int = 1000
    elapsed_ms: int = 0
    sql_hash: str | None = None
    candidate_gate_reason_code: str | None = None
    safety_reason_code: str | None = None
    shadow_only: bool = True
    @field_validator("stage", "candidate_gate_reason_code", "safety_reason_code", mode="before")
    @classmethod
    def _sanitize_text_code(cls, value: object) -> str | None:
        """文本字段只保留稳定脱敏短码，防止外部 SQL/密钥进入报告。"""
        return _safe_code(value)
    @field_validator("error_codes", mode="before")
    @classmethod
    def _sanitize_error_codes(cls, value: object) -> list[str]:
        """错误码列表统一脱敏、去重并丢弃空值。"""
        if not isinstance(value, list):
            return []
        safe_codes: list[str] = []
        for item in value:
            safe = _safe_code(item)
            if safe and safe not in safe_codes:
                safe_codes.append(safe)
        return safe_codes
    @field_validator("row_count", "timeout_ms", "elapsed_ms", mode="before")
    @classmethod
    def _sanitize_non_negative_int(cls, value: object) -> int:
        """报告计数字段只能是非负整数。"""
        try:
            parsed = int(value)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001 - 报告字段统一兜底
            return 0
        return max(0, parsed)
    @field_validator("sql_hash", mode="before")
    @classmethod
    def _sanitize_sql_hash(cls, value: object) -> str | None:
        """SQL hash 只允许 64 位十六进制，其余内容一律丢弃。"""
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower()
        if len(normalized) == 64 and all(char in "0123456789abcdef" for char in normalized):
            return normalized
        return None
class LogisticsNl2SqlM10DShadowGate:
    """物流 NL2SQL M10-D EXPLAIN / readonly trial shadow gate。
    业务逻辑：
        D1 仅提供 fake executor 下的 gate schema 与报告能力。默认关闭且懒加载 executor；显式开启后仍只允许
        `middle_db` 来源，进入 executor 前再次执行 SQL safety 复核，EXPLAIN 失败时 fail-closed 并跳过 trial。
    """
    def __init__(
        self,
        *,
        config: LogisticsNl2SqlM10DShadowGateConfig | None = None,
        executor_factory: Callable[[], LogisticsSqlExecutor] | None = None,
        safety_checker: LogisticsSqlSafetyChecker | None = None,
    ) -> None:
        """初始化 M10-D gate。
        参数：
            config: gate 开关与摘要配置，默认全部关闭。
            executor_factory: executor 懒加载工厂；缺省为 fake executor，不连接真实库。
            safety_checker: 可注入 SQL safety checker，缺省使用物流 catalog safety。
        返回：
            无。
        """
        self.config = config or LogisticsNl2SqlM10DShadowGateConfig()
        self.executor_factory = executor_factory or (lambda: FakeLogisticsSqlExecutor())
        self.safety_checker = safety_checker or LogisticsSqlSafetyChecker()
    def run(
        self,
        *,
        rendered_sql: LogisticsRenderedSql | None,
        source_system: str = M10D_ALLOWED_SOURCE_SYSTEM,
        candidate_gate_reason_code: str | None = None,
        safety_reason_code: str | None = None,
    ) -> LogisticsNl2SqlM10DShadowGateReport:
        """执行一次 M10-D shadow gate。
        参数：
            rendered_sql: 经过 SQLPlan validator/renderer 产出的 SQL；为 None 时跳过。
            source_system: 数据来源边界，D1 只允许智能助手中间库 `middle_db`。
            candidate_gate_reason_code: 上游 candidate SQL gate 的脱敏原因码。
            safety_reason_code: 上游 safety 的脱敏原因码；本方法仍会重新复核 safety。
        返回：
            不含 SQL/参数/表字段/行值/连接信息的 gate 报告。
        """
        started = time.perf_counter()
        if not self.config.enabled:
            return self._report(
                started=started,
                status="disabled",
                stage="disabled",
                error_codes=["m10d_shadow_gate_disabled"],
                explain_status="disabled",
                trial_status="disabled",
                candidate_gate_reason_code=candidate_gate_reason_code,
                safety_reason_code=safety_reason_code,
            )
        if source_system != M10D_ALLOWED_SOURCE_SYSTEM:
            return self._report(
                started=started,
                status="skipped",
                stage="source_system",
                error_codes=["m10d_source_system_not_supported"],
                explain_status="skipped",
                trial_status="skipped",
                candidate_gate_reason_code=candidate_gate_reason_code,
                safety_reason_code=safety_reason_code,
            )
        if rendered_sql is None:
            return self._report(
                started=started,
                status="skipped",
                stage="render",
                error_codes=["m10d_rendered_sql_missing"],
                explain_status="skipped",
                trial_status="skipped",
                candidate_gate_reason_code=candidate_gate_reason_code,
                safety_reason_code=safety_reason_code,
            )
        sql_hash = _hash_sql(rendered_sql.sql)
        safety = self.safety_checker.check(rendered_sql)
        resolved_safety_reason = safety_reason_code
        if not safety.ok:
            resolved_safety_reason = _first_safe_code(safety.error_codes) or safety_reason_code
            return self._report(
                started=started,
                status="failed",
                stage="safety",
                error_codes=["m10d_safety_failed", *safety.error_codes],
                explain_status="skipped",
                trial_status="skipped",
                sql_hash=sql_hash,
                candidate_gate_reason_code=candidate_gate_reason_code,
                safety_reason_code=resolved_safety_reason,
            )
        if not self.config.explain_enabled and not self.config.trial_enabled:
            return self._report(
                started=started,
                status="disabled",
                stage="disabled",
                error_codes=["m10d_explain_trial_disabled"],
                explain_status="disabled",
                trial_status="disabled",
                sql_hash=sql_hash,
                candidate_gate_reason_code=candidate_gate_reason_code,
                safety_reason_code=resolved_safety_reason,
            )
        if self.config.trial_enabled and not self.config.explain_enabled:
            return self._report(
                started=started,
                status="failed",
                stage="explain",
                error_codes=["m10d_trial_requires_successful_explain"],
                explain_status="disabled",
                trial_status="skipped",
                sql_hash=sql_hash,
                candidate_gate_reason_code=candidate_gate_reason_code,
                safety_reason_code=resolved_safety_reason,
            )
        execution_service = self._build_execution_service()
        explain_result = execution_service.explain(rendered_sql)
        if not explain_result.ok:
            return self._report(
                started=started,
                status="failed",
                stage="explain",
                error_codes=["m10d_explain_failed", *explain_result.error_codes],
                explain_status="failed",
                trial_status="skipped" if self.config.trial_enabled else "disabled",
                sql_hash=sql_hash,
                candidate_gate_reason_code=candidate_gate_reason_code,
                safety_reason_code=resolved_safety_reason,
            )
        if not self.config.trial_enabled:
            return self._report(
                started=started,
                status="success",
                stage="explain",
                error_codes=[],
                explain_status="success",
                trial_status="disabled",
                sql_hash=sql_hash,
                candidate_gate_reason_code=candidate_gate_reason_code,
                safety_reason_code=resolved_safety_reason,
            )
        trial_result = execution_service.trial(rendered_sql)
        if not trial_result.ok:
            return self._report(
                started=started,
                status="failed",
                stage="trial",
                error_codes=["m10d_trial_failed", *trial_result.error_codes],
                explain_status="success",
                trial_status="failed",
                sql_hash=sql_hash,
                candidate_gate_reason_code=candidate_gate_reason_code,
                safety_reason_code=resolved_safety_reason,
            )
        observed_row_count = len(trial_result.rows)
        capped_row_count = min(observed_row_count, self.config.row_cap)
        return self._report(
            started=started,
            status="success",
            stage="trial",
            error_codes=[],
            explain_status="success",
            trial_status="success",
            row_count=capped_row_count,
            row_cap_applied=observed_row_count > self.config.row_cap,
            sql_hash=sql_hash,
            candidate_gate_reason_code=candidate_gate_reason_code,
            safety_reason_code=resolved_safety_reason,
        )
    def _build_execution_service(self) -> LogisticsSqlExecutionService:
        """根据配置懒加载 fake 或真实只读 executor。
        D2 新增逻辑：
        - 默认使用 executor_factory（D1 默认 fake executor）。
        - 若 real_db_access_enabled=True 且 env_path 非空，尝试基于中间库配置构建
          LogisticsReadonlyMiddleDbExecutor。
        - 若 real_db_access_enabled=True 但加载失败，静默 fallback 到 executor_factory 提供的 executor。

        """
        if self.config.real_db_access_enabled and self.config.env_path:
            from backend.app.domains.logistics.services.nl2sql.readonly_middle_db import (
                LogisticsReadonlyMiddleDbExecutor,
                load_readonly_middle_db_config,
            )
            load_result = load_readonly_middle_db_config(self.config.env_path)
            if load_result.ok and load_result.config is not None:
                real_executor: LogisticsSqlExecutor = LogisticsReadonlyMiddleDbExecutor(
                    config=load_result.config,
                )
                return LogisticsSqlExecutionService(
                    executor=real_executor,
                    safety_checker=self.safety_checker,
                )
        # 默认使用注入的 executor_factory（单测场景为 fake executor，生产为预设 factory）
        return LogisticsSqlExecutionService(
            executor=self.executor_factory(),
            safety_checker=self.safety_checker,
        )
    def _report(
        self,
        *,
        started: float,
        status: M10DGateStatus,
        stage: str,
        error_codes: list[str],
        explain_status: M10DStepStatus,
        trial_status: M10DStepStatus,
        row_count: int = 0,
        row_cap_applied: bool = False,
        sql_hash: str | None = None,
        candidate_gate_reason_code: str | None = None,
        safety_reason_code: str | None = None,
    ) -> LogisticsNl2SqlM10DShadowGateReport:
        """构造统一脱敏报告，所有路径都从这里出站。"""
        return LogisticsNl2SqlM10DShadowGateReport(
            enabled=self.config.enabled,
            status=status,
            stage=stage,
            error_codes=error_codes,
            explain_status=explain_status,
            trial_status=trial_status,
            row_count=row_count,
            row_cap_applied=row_cap_applied,
            timeout_ms=self.config.timeout_ms,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            sql_hash=sql_hash,
            candidate_gate_reason_code=candidate_gate_reason_code,
            safety_reason_code=safety_reason_code,
            shadow_only=True,
        )
def _hash_sql(sql: str) -> str:
    """返回 SQL 文本 hash；报告只保留 hash，不输出 SQL 原文。"""
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()
def _first_safe_code(codes: list[str]) -> str | None:
    """从错误码列表中取第一个脱敏稳定码。"""
    for code in codes:
        safe = _safe_code(code)
        if safe:
            return safe
    return None
def _safe_code(value: object) -> str | None:
    """把外部文本收敛为稳定短码。
    参数：
        value: 可能来自上游 gate、safety 或异常路径的文本。
    返回：
        脱敏后的短码；包含 SQL/密钥形态时会替换为通用 redacted 码，`::` 后缀会被去除以避免表字段泄露。
    """
    if value is None:
        return None
    text = redact_evaluation_text(str(value)).strip()
    if not text:
        return None
    if "[SQL_REDACTED]" in text or "[DSN_REDACTED]" in text or "[REDACTED]" in text:
        return "m10d_error_redacted"
    head = text.split("::", 1)[0]
    safe_chars = [char if (char.isalnum() or char in "_-.") else "_" for char in head]
    safe = "".join(safe_chars).strip("_")
    return safe[:120] or None
__all__ = [
    "M10D_SHADOW_GATE_SCHEMA_VERSION",
    "LogisticsNl2SqlM10DShadowGate",
    "LogisticsNl2SqlM10DShadowGateConfig",
    "LogisticsNl2SqlM10DShadowGateReport",
]

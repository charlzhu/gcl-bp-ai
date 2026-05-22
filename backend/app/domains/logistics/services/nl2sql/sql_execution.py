from __future__ import annotations

import asyncio
import re
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domains.logistics.services.nl2sql.sql_renderer import LogisticsRenderedSql
from backend.app.domains.logistics.services.nl2sql.sql_safety import LogisticsSqlSafetyChecker


SECRET_PATTERNS = (
    re.compile(r"(password\s*=\s*)[^\s,;]+", re.IGNORECASE),
    re.compile(r"(token\s*=\s*)[^\s,;]+", re.IGNORECASE),
    re.compile(r"(api[_-]?key\s*=\s*)[^\s,;]+", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"(://[^:/\s]+:)([^@\s]+)(@)"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{6,}\b"),
    re.compile(r"\btok_[A-Za-z0-9_\-]{6,}\b"),
)


class LogisticsSqlExecutorCall(BaseModel):
    """测试 fake executor 记录的调用。"""

    model_config = ConfigDict(extra="forbid")

    mode: str
    sql: str
    params: dict[str, Any]


class LogisticsSqlExecutor(Protocol):
    """EXPLAIN/试执行 executor 协议。

    业务逻辑：
        真实实现必须只读、限时、限行并使用 DB driver 参数绑定；M4 单测默认使用 fake executor，
        不连接真实数据库、不读取 `.env` 凭据。
    """

    def explain(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """执行 EXPLAIN 并返回小型行集。"""

        raise NotImplementedError

    def trial(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """执行受控小 LIMIT 试执行并返回小型行集。"""

        raise NotImplementedError


class FakeLogisticsSqlExecutor:
    """单测用 fake executor。

    参数：
        explain_rows: EXPLAIN 返回行。
        trial_rows: trial 返回行。
        raise_message: 若提供，则 explain/trial 抛出该错误，用于验证脱敏。
    返回：
        记录调用但不连接数据库。
    """

    def __init__(
        self,
        *,
        explain_rows: list[dict[str, Any]] | None = None,
        trial_rows: list[dict[str, Any]] | None = None,
        raise_message: str | None = None,
    ) -> None:
        """初始化 fake executor。"""

        self.explain_rows = explain_rows if explain_rows is not None else []
        self.trial_rows = trial_rows if trial_rows is not None else []
        self.raise_message = raise_message
        self.calls: list[LogisticsSqlExecutorCall] = []

    def explain(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """记录 EXPLAIN 调用并返回预置结果。"""

        return self._record("explain", sql, params, self.explain_rows)

    def trial(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """记录 trial 调用并返回预置结果。"""

        return self._record("trial", sql, params, self.trial_rows)

    def _record(
        self,
        mode: str,
        sql: str,
        params: dict[str, Any],
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """公共记录逻辑；需要时模拟 executor 异常。"""

        self.calls.append(LogisticsSqlExecutorCall(mode=mode, sql=sql, params=dict(params)))
        if self.raise_message:
            raise RuntimeError(self.raise_message)
        return rows


class LogisticsSqlExecutionResult(BaseModel):
    """EXPLAIN/试执行闭环返回。"""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    mode: str
    rows: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
    errors: list[str] = Field(default_factory=list)

    @property
    def error_codes(self) -> list[str]:
        """返回稳定错误码列表。"""

        return list(self.errors)


class LogisticsSqlExecutionService:
    """物流 NL2SQL EXPLAIN / 试执行闭环服务。

    业务逻辑：
        该服务只接受 Safety passed 的 renderer 产物；executor 可注入，默认 fake/单测路径不连接真实库。
        Safety 失败时绝不调用 executor，executor 异常返回脱敏错误。
    """

    def __init__(
        self,
        *,
        executor: LogisticsSqlExecutor,
        safety_checker: LogisticsSqlSafetyChecker | None = None,
        trial_limit: int = 0,
        execute_timeout: float = 0.0,
    ) -> None:
        """初始化执行闭环服务。

        参数：
            executor: 实际 EXPLAIN/trial 执行器或 fake executor。
            safety_checker: 可注入 safety checker。
            trial_limit: 无 LIMIT SQL 的默认 trial LIMIT；MVP 默认 0。
            execute_timeout: 单次 EXPLAIN/trial 执行超时秒数；0 表示不设超时。
        返回：
            无。
        """

        self.executor = executor
        self.safety_checker = safety_checker or LogisticsSqlSafetyChecker()
        self.trial_limit = trial_limit
        self.execute_timeout = execute_timeout

    def explain(self, rendered: LogisticsRenderedSql) -> LogisticsSqlExecutionResult:
        """对安全 SQL 执行 EXPLAIN。"""

        safety = self.safety_checker.check(rendered)
        if not safety.ok:
            return LogisticsSqlExecutionResult(ok=False, mode="explain", errors=safety.error_codes)
        try:
            rows = self._run_with_timeout(
                "explain",
                self.executor.explain,
                f"EXPLAIN {rendered.sql}",
                dict(rendered.params),
            )
            return LogisticsSqlExecutionResult(ok=True, mode="explain", rows=rows)
        except asyncio.TimeoutError:
            return LogisticsSqlExecutionResult(
                ok=False, mode="explain", error="explain_timeout", errors=["sql_execution_timeout::explain"]
            )
        except Exception as exc:  # noqa: BLE001 - executor 边界必须兜底并脱敏
            return LogisticsSqlExecutionResult(
                ok=False,
                mode="explain",
                error=_sanitize_error(str(exc)),
                errors=["sql_execution_executor_failed::explain"],
            )

    def trial(self, rendered: LogisticsRenderedSql) -> LogisticsSqlExecutionResult:
        """对安全 SQL 执行受控小 LIMIT 试执行。"""

        trial_rendered = self._build_trial_rendered_sql(rendered)
        safety = self.safety_checker.check(trial_rendered)
        if not safety.ok:
            return LogisticsSqlExecutionResult(ok=False, mode="trial", errors=safety.error_codes)
        try:
            rows = self._run_with_timeout(
                "trial",
                self.executor.trial,
                trial_rendered.sql,
                dict(trial_rendered.params),
            )
            return LogisticsSqlExecutionResult(ok=True, mode="trial", rows=rows)
        except asyncio.TimeoutError:
            return LogisticsSqlExecutionResult(
                ok=False, mode="trial", error="trial_timeout", errors=["sql_execution_timeout::trial"]
            )
        except Exception as exc:  # noqa: BLE001 - executor 边界必须兜底并脱敏
            return LogisticsSqlExecutionResult(
                ok=False,
                mode="trial",
                error=_sanitize_error(str(exc)),
                errors=["sql_execution_executor_failed::trial"],
            )

    def _run_with_timeout(
        self,
        mode: str,
        fn: Any,
        sql: str,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """对同步 executor 调用施加超时。无超时设置时直接调用。"""
        if self.execute_timeout <= 0:
            return fn(sql, params)
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                asyncio.wait_for(
                    loop.run_in_executor(None, fn, sql, params),
                    timeout=self.execute_timeout,
                )
            )
            return result  # type: ignore[return-value]
        except asyncio.TimeoutError:
            raise
        finally:
            loop.close()

    def _build_trial_rendered_sql(self, rendered: LogisticsRenderedSql) -> LogisticsRenderedSql:
        """为无 LIMIT SQL 追加默认 trial LIMIT。

        业务逻辑：
            aggregate SQL 通常不带 LIMIT；试执行阶段只验证列形状/可执行性，默认 LIMIT 0，避免返回
            大量数据。已有 LIMIT 的 detail/ranking SQL 保持 renderer 的受控 LIMIT。
        """

        if re.search(r"\bLIMIT\b", rendered.sql, re.IGNORECASE):
            return rendered
        params = dict(rendered.params)
        params["__trial_limit"] = self.trial_limit
        return rendered.model_copy(
            update={
                "sql": f"{rendered.sql} LIMIT :__trial_limit",
                "params": params,
                "limit": self.trial_limit,
            }
        )


def _sanitize_error(message: str) -> str:
    """脱敏 executor 异常文本。

    参数：
        message: executor 抛出的原始异常文本，可能包含 DSN、password、token、API key。
    返回：
        可写入日志/验收材料的脱敏文本。
    """

    sanitized = message
    for pattern in SECRET_PATTERNS:
        if pattern.pattern.startswith("(://"):
            sanitized = pattern.sub(r"\1[REDACTED]\3", sanitized)
        elif pattern.pattern.startswith("Bearer"):
            sanitized = pattern.sub("Bearer [REDACTED]", sanitized)
        elif "tok_" in pattern.pattern or "sk-" in pattern.pattern:
            sanitized = pattern.sub("[REDACTED]", sanitized)
        else:
            sanitized = pattern.sub(r"\1[REDACTED]", sanitized)
    return sanitized


__all__ = [
    "FakeLogisticsSqlExecutor",
    "LogisticsSqlExecutionResult",
    "LogisticsSqlExecutionService",
    "LogisticsSqlExecutor",
    "LogisticsSqlExecutorCall",
]

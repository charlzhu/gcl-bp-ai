from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Protocol

from pydantic import BaseModel, ConfigDict, Field

MYSQL_NAMED_PARAM_RE = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")
TRIAL_LIMIT_RE = re.compile(r"\bLIMIT\s+(?::([A-Za-z_][A-Za-z0-9_]*)|%\(([A-Za-z_][A-Za-z0-9_]*)\)s|(\d+))\s*$", re.IGNORECASE)
REQUIRED_ENV_KEYS: tuple[str, ...] = ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_DB", "MYSQL_USER", "MYSQL_PASSWORD")
UNSAFE_SELECT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:/\*|\*/|--|#)"),
    re.compile(r"\bINTO\s+(?:OUTFILE|DUMPFILE)\b", re.IGNORECASE),
    re.compile(r"\bLOAD_FILE\s*\(", re.IGNORECASE),
    re.compile(r"\bUNION\b", re.IGNORECASE),
    re.compile(r"\bFOR\s+UPDATE\b", re.IGNORECASE),
    re.compile(r"\bLOCK\s+IN\s+SHARE\s+MODE\b", re.IGNORECASE),
    re.compile(r"\bPROCEDURE\s+ANALYSE\b", re.IGNORECASE),
    re.compile(r"\bSLEEP\s*\(", re.IGNORECASE),
    re.compile(r"\bBENCHMARK\s*\(", re.IGNORECASE),
)


class _ReadonlyConnection(Protocol):
    """M7 只读 MySQL 连接最小协议，便于单测注入 fake connection。"""

    def cursor(self) -> Any:
        """返回 DB-API cursor 或支持上下文管理的 cursor。"""

    def close(self) -> None:
        """关闭连接，真实连接与 fake 连接都应提供该方法。"""


class LogisticsReadonlyMiddleDbConfig(BaseModel):
    """物流 NL2SQL M7 只读中间库连接配置。

    业务逻辑：
        该对象只在内存中传递给只读 executor，不应直接写入日志、报告或 kanban 产物。
        上层 `LogisticsReadonlyMiddleDbConfigLoadResult` 会在 JSON 序列化时排除本对象，避免泄漏
        host/user/password/full DSN。
    """

    model_config = ConfigDict(extra="forbid")

    host: str = Field(repr=False)
    port: int
    database: str = Field(repr=False)
    user: str = Field(repr=False)
    password: str = Field(repr=False)
    charset: str = "utf8mb4"
    connect_timeout: int = 3
    read_timeout: int = 10
    max_trial_limit: int = 20


class LogisticsReadonlyMiddleDbConfigLoadResult(BaseModel):
    """backend/.env 读取结果，默认 JSON 输出只包含脱敏摘要和稳定错误码。"""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    error_code: str | None = None
    missing_keys: list[str] = Field(default_factory=list)
    invalid_keys: list[str] = Field(default_factory=list)
    safe_summary: dict[str, bool] = Field(default_factory=dict)
    config: LogisticsReadonlyMiddleDbConfig | None = Field(default=None, exclude=True)


def load_readonly_middle_db_config(env_path: str | Path) -> LogisticsReadonlyMiddleDbConfigLoadResult:
    """从指定 backend/.env 读取 M7 只读中间库配置。

    参数：
        env_path: 项目 backend/.env 路径或单测临时 .env 路径。
    返回：
        成功时包含内存 config；失败时 fail-closed，只返回稳定错误码、缺失键名和布尔摘要。
    """

    resolved_env_path = Path(env_path)
    if not resolved_env_path.exists():
        return LogisticsReadonlyMiddleDbConfigLoadResult(
            ok=False,
            error_code="readonly_middle_db_env_missing",
            safe_summary=_safe_summary({}),
        )

    values = _parse_env_file(resolved_env_path)
    missing_keys = [key for key in REQUIRED_ENV_KEYS if not str(values.get(key) or "").strip()]
    if missing_keys:
        return LogisticsReadonlyMiddleDbConfigLoadResult(
            ok=False,
            error_code="readonly_middle_db_config_missing",
            missing_keys=missing_keys,
            safe_summary=_safe_summary(values),
        )

    invalid_keys: list[str] = []
    try:
        port = int(str(values["MYSQL_PORT"]).strip())
    except (TypeError, ValueError):
        invalid_keys.append("MYSQL_PORT")
        port = 0
    if port <= 0 or port > 65535:
        invalid_keys.append("MYSQL_PORT")
    if invalid_keys:
        return LogisticsReadonlyMiddleDbConfigLoadResult(
            ok=False,
            error_code="readonly_middle_db_config_invalid",
            invalid_keys=sorted(set(invalid_keys)),
            safe_summary=_safe_summary(values),
        )

    config = LogisticsReadonlyMiddleDbConfig(
        host=str(values["MYSQL_HOST"]).strip(),
        port=port,
        database=str(values["MYSQL_DB"]).strip(),
        user=str(values["MYSQL_USER"]).strip(),
        password=str(values["MYSQL_PASSWORD"]).strip(),
        charset=str(values.get("MYSQL_CHARSET") or "utf8mb4").strip() or "utf8mb4",
    )
    return LogisticsReadonlyMiddleDbConfigLoadResult(
        ok=True,
        safe_summary=_safe_summary(values, configured=True),
        config=config,
    )


ReadonlyConnectionFactory = Callable[[LogisticsReadonlyMiddleDbConfig], _ReadonlyConnection]


class LogisticsReadonlyMiddleDbExecutor:
    """物流 NL2SQL M7 真实 MySQL 只读执行器。

    业务逻辑：
        本 executor 只接受上层 safety 通过后的 `EXPLAIN SELECT ...` 与有界 `SELECT ... LIMIT N`。
        它负责把 renderer 的 `:p0` 命名参数转换为 PyMySQL 的 `%(p0)s`，并交给 DB driver 做
        参数绑定；任何非 SELECT、无 LIMIT trial 或 DB 异常都转为稳定错误码，避免报告泄漏连接信息。
    """

    def __init__(
        self,
        *,
        config: LogisticsReadonlyMiddleDbConfig,
        connection_factory: ReadonlyConnectionFactory | None = None,
    ) -> None:
        """初始化只读 executor。"""

        self.config = config
        self.connection_factory = connection_factory or _default_connection_factory

    def explain(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """执行 `EXPLAIN SELECT ...`，并返回小型执行计划行集。"""

        self._assert_explain_sql(sql)
        return self._execute(sql, params)

    def trial(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """执行有界 `SELECT ... LIMIT N`，并返回小样本行集。"""

        self._assert_trial_sql(sql, params)
        return self._execute(sql, params)

    @staticmethod
    def _assert_explain_sql(sql: str) -> None:
        """只允许 EXPLAIN 包裹单条 SELECT。"""

        normalized = sql.strip()
        lower_sql = normalized.lower()
        if ";" in normalized:
            raise RuntimeError("readonly_middle_db_multi_statement_forbidden")
        if not lower_sql.startswith("explain select"):
            raise RuntimeError("readonly_middle_db_explain_select_required")
        _assert_no_unsafe_select_tokens(normalized)

    def _assert_trial_sql(self, sql: str, params: dict[str, Any]) -> None:
        """只允许单条有界 SELECT，小样本 LIMIT 不得超过配置上限。"""

        normalized = sql.strip()
        lower_sql = normalized.lower()
        if ";" in normalized:
            raise RuntimeError("readonly_middle_db_multi_statement_forbidden")
        if not lower_sql.startswith("select"):
            raise RuntimeError("readonly_middle_db_not_select")
        _assert_no_unsafe_select_tokens(normalized)
        limit_match = TRIAL_LIMIT_RE.search(normalized)
        if not limit_match:
            raise RuntimeError("readonly_middle_db_trial_limit_required")
        colon_param, pymysql_param, literal_limit = limit_match.groups()
        if literal_limit is not None:
            limit_value = int(literal_limit)
        else:
            param_name = colon_param or pymysql_param or ""
            value = params.get(param_name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise RuntimeError("readonly_middle_db_trial_limit_invalid")
            limit_value = value
        if limit_value < 0 or limit_value > self.config.max_trial_limit:
            raise RuntimeError("readonly_middle_db_trial_limit_out_of_range")

    def _execute(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """创建短连接执行只读语句，所有外部异常收敛为稳定错误码。"""

        driver_sql = _convert_colon_params_to_pymysql(sql)
        connection: _ReadonlyConnection | None = None
        try:
            connection = self.connection_factory(self.config)
            return _execute_with_connection(connection, driver_sql, dict(params))
        except RuntimeError:
            raise
        except Exception as exc:  # noqa: BLE001 - DB 边界不能把原始异常写入报告
            if _looks_like_connection_failure(exc):
                raise RuntimeError("readonly_middle_db_connection_failed") from None
            raise RuntimeError("readonly_middle_db_query_failed") from None
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:  # noqa: BLE001 - close 失败不能覆盖主错误
                    pass


def _default_connection_factory(config: LogisticsReadonlyMiddleDbConfig) -> _ReadonlyConnection:
    """使用 PyMySQL 创建只读短连接；连接失败只抛稳定错误码。"""

    try:
        import pymysql
        import pymysql.cursors
    except Exception:  # noqa: BLE001 - 依赖缺失也要 fail-closed
        raise RuntimeError("readonly_middle_db_driver_unavailable") from None

    try:
        return pymysql.connect(
            host=config.host,
            port=config.port,
            database=config.database,
            user=config.user,
            password=config.password,
            charset=config.charset,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            connect_timeout=config.connect_timeout,
            read_timeout=config.read_timeout,
            write_timeout=config.read_timeout,
        )
    except Exception:  # noqa: BLE001 - 不向上抛出含 host/user 的驱动错误
        raise RuntimeError("readonly_middle_db_connection_failed") from None


def _assert_no_unsafe_select_tokens(sql: str) -> None:
    """DB 边界二次 fail-closed：拒绝可读文件/写文件/组合查询/锁表/耗时函数等危险 SELECT 变体。"""

    if any(pattern.search(sql) for pattern in UNSAFE_SELECT_PATTERNS):
        raise RuntimeError("readonly_middle_db_unsafe_select")


def _execute_with_connection(connection: _ReadonlyConnection, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """兼容真实 cursor 与 fake cursor 的执行辅助函数。"""

    cursor_obj = connection.cursor()
    if hasattr(cursor_obj, "__enter__") and hasattr(cursor_obj, "__exit__"):
        with cursor_obj as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
    else:
        cursor = cursor_obj
        try:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        finally:
            close = getattr(cursor, "close", None)
            if callable(close):
                close()
    return [dict(row) for row in rows]


def _convert_colon_params_to_pymysql(sql: str) -> str:
    """把 renderer 的 `:name` 参数占位符转换为 PyMySQL 支持的 `%(name)s`。"""

    return MYSQL_NAMED_PARAM_RE.sub(lambda match: f"%({match.group(1)})s", sql)


def _parse_env_file(path: Path) -> dict[str, str]:
    """解析简单 KEY=VALUE .env 文件，不展开变量、不执行任何内容。"""

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_key = key.strip().upper()
        normalized_value = value.strip()
        if (
            len(normalized_value) >= 2
            and normalized_value[0] == normalized_value[-1]
            and normalized_value[0] in {"'", '"'}
        ):
            normalized_value = normalized_value[1:-1]
        values[normalized_key] = normalized_value
    return values


def _safe_summary(values: dict[str, str], *, configured: bool = False) -> dict[str, bool]:
    """生成不含配置值的布尔摘要，供报告或调试确认环境状态。"""

    return {
        "configured": configured,
        "host_configured": bool(str(values.get("MYSQL_HOST") or "").strip()),
        "database_configured": bool(str(values.get("MYSQL_DB") or "").strip()),
        "user_configured": bool(str(values.get("MYSQL_USER") or "").strip()),
        "credential_configured": bool(str(values.get("MYSQL_PASSWORD") or "").strip()),
    }


def _looks_like_connection_failure(exc: Exception) -> bool:
    """尽量把驱动连接类错误归为环境不可用，不暴露原始错误文本。"""

    exc_type = type(exc).__name__.lower()
    return "connect" in exc_type or "operational" in exc_type or "timeout" in exc_type


__all__ = [
    "LogisticsReadonlyMiddleDbConfig",
    "LogisticsReadonlyMiddleDbConfigLoadResult",
    "LogisticsReadonlyMiddleDbExecutor",
    "ReadonlyConnectionFactory",
    "load_readonly_middle_db_config",
]

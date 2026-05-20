from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
import json
import re
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

EVALUATION_LOG_SCHEMA_VERSION = "logistics_nl2sql_evaluation_log.v1"
MAX_EVALUATION_TEXT_CHARS = 800
SECRET_REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?i)\b(?:mysql|postgresql|postgres|mariadb|oracle|mssql|sqlserver|sqlite)(?:\+[a-z0-9_]+)?://[^\s,;\]}]+"
        ),
        "[DSN_REDACTED]",
    ),
    (
        re.compile(
            r"(?i)(\b(?:api[_-]?key|password|passwd|token|access[_-]?token|refresh[_-]?token|secret)\b\s*[:=]\s*)[^\s,;\]}]+"
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"(?i)([\"'](?:api[_-]?key|password|passwd|token|access[_-]?token|refresh[_-]?token|secret)[\"']\s*:\s*[\"'])[^\"']+([\"'])"
        ),
        r"\1[REDACTED]\2",
    ),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]+"), "Bearer [REDACTED]"),
    (re.compile(r"(://[^:/\s]+:)([^@\s]+)(@)"), r"\1[REDACTED]\3"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{6,}\b"), "[REDACTED]"),
    (re.compile(r"\btok_[A-Za-z0-9_\-]{6,}\b"), "[REDACTED]"),
)
SQL_TEXT_PATTERN = re.compile(
    r"(?is)\bWITH\b\s+.+?\bSELECT\b\s+.+|\b(?:SELECT|EXPLAIN)\b\s+.+|\b(?:INSERT|UPDATE|DELETE|ALTER|DROP|CREATE|TRUNCATE)\b\s+.+"
)
SQL_HASH_PATTERN = re.compile(r"\A[a-fA-F0-9]{64}\Z")


class LogisticsNl2SqlEvaluationLogRecord(BaseModel):
    """物流 NL2SQL shadow 评估日志记录。

    参数：
        schema_version: 日志 schema 版本。
        pipeline_version: 生成该记录的 shadow pipeline 版本。
        trace_id: 单次 shadow 运行追踪 ID。
        request_id: 上游请求 ID，可为空。
        question: 脱敏后的用户问题摘要。
        rewritten_question: 脱敏后的改写问题摘要。
        domain: 业务域，MVP 固定 logistics。
        source_system: 数据来源边界，MVP 固定 middle_db。
        status: shadow 运行结果状态。
        stage: 结束阶段。
        error_codes: 稳定错误码列表。
        error_message: 脱敏错误摘要。
        catalog_ids/catalog_versions: 本次候选引用的 catalog 追踪信息。
        sql_hash/sql_param_keys: SQL 只保留 hash 和参数 key，禁止持久化 SQL 原文和值。
        validation_errors/safety_errors: M3/M4 边界错误。
        explain_ok/trial_ok: EXPLAIN 与 trial 是否通过。
        row_count/sample_row_count: 试执行返回行数摘要。
        duration_ms: shadow 运行耗时。
        warnings: 非阻塞告警。
        candidate_sql_gate_*: M10-B raw candidate SQL 门禁摘要，只记录布尔状态、原因码、脱敏原因和修复建议，
            禁止记录 raw SQL 原文。
        created_at: ISO8601 创建时间。
    返回：
        可写入内存 sink 或 JSONL sink 的结构化日志对象。
    """

    model_config = ConfigDict(extra="forbid", validate_default=True)

    schema_version: str = EVALUATION_LOG_SCHEMA_VERSION
    pipeline_version: str
    trace_id: str
    request_id: str | None = None
    question: str
    rewritten_question: str | None = None
    domain: str = "logistics"
    source_system: str = "middle_db"
    status: str
    stage: str
    error_codes: list[str] = Field(default_factory=list)
    error_message: str | None = None
    catalog_ids: list[str] = Field(default_factory=list)
    catalog_versions: list[str] = Field(default_factory=list)
    sql_hash: str | None = None
    sql_param_keys: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    safety_errors: list[str] = Field(default_factory=list)
    explain_ok: bool = False
    trial_ok: bool = False
    row_count: int = 0
    sample_row_count: int = 0
    duration_ms: int = 0
    warnings: list[str] = Field(default_factory=list)
    candidate_sql_gate_allowed: bool | None = None
    candidate_sql_gate_rejected: bool | None = None
    candidate_sql_gate_reason_code: str | None = None
    candidate_sql_gate_sanitized_reason: str | None = None
    candidate_sql_gate_repair_info: dict[str, Any] | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    @field_validator(
        "schema_version",
        "pipeline_version",
        "trace_id",
        "request_id",
        "question",
        "rewritten_question",
        "domain",
        "source_system",
        "status",
        "stage",
        "error_message",
        "candidate_sql_gate_reason_code",
        "candidate_sql_gate_sanitized_reason",
        "created_at",
        mode="before",
    )
    @classmethod
    def _sanitize_text_field(cls, value: Any) -> str | None:
        """校验并脱敏所有日志文本字段，防止直接构造绕过 from_pipeline。"""

        return _safe_text(value)

    @field_validator(
        "error_codes",
        "catalog_ids",
        "catalog_versions",
        "sql_param_keys",
        "validation_errors",
        "safety_errors",
        "warnings",
        mode="before",
    )
    @classmethod
    def _sanitize_list_field(cls, value: Any) -> list[str]:
        """校验并脱敏日志列表字段。"""

        return _safe_string_list(_coerce_string_list(value))

    @field_validator("sql_hash", mode="before")
    @classmethod
    def _sanitize_sql_hash_field(cls, value: Any) -> str | None:
        """SQL hash 只允许 64 位十六进制，其他内容一律丢弃。"""

        return _safe_sql_hash(value)

    @field_validator("row_count", "sample_row_count", "duration_ms", mode="before")
    @classmethod
    def _sanitize_non_negative_int_field(cls, value: Any) -> int:
        """日志计数字段只保留非负整数。"""

        return _safe_non_negative_int(value)

    @field_validator("candidate_sql_gate_repair_info", mode="before")
    @classmethod
    def _sanitize_gate_repair_info(cls, value: Any) -> dict[str, Any] | None:
        """门禁修复提示只保留脱敏 JSON 对象，防止 raw SQL 或密钥经 dict 字段落盘。"""

        return _safe_json_object(value)

    @classmethod
    def from_pipeline(
        cls,
        *,
        trace_id: str,
        request_id: str | None,
        question: str,
        rewritten_question: str | None,
        domain: str,
        source_system: str,
        status: str,
        stage: str,
        error_codes: list[str],
        error_message: str | None,
        catalog_ids: list[str],
        catalog_versions: list[str],
        sql_hash: str | None,
        sql_param_keys: list[str],
        validation_errors: list[str],
        safety_errors: list[str],
        explain_ok: bool,
        trial_ok: bool,
        row_count: int,
        sample_row_count: int,
        duration_ms: int,
        pipeline_version: str,
        warnings: list[str] | None = None,
        candidate_sql_gate_allowed: bool | None = None,
        candidate_sql_gate_rejected: bool | None = None,
        candidate_sql_gate_reason_code: str | None = None,
        candidate_sql_gate_sanitized_reason: str | None = None,
        candidate_sql_gate_repair_info: dict[str, Any] | None = None,
    ) -> "LogisticsNl2SqlEvaluationLogRecord":
        """从 shadow pipeline 中间结果生成脱敏评估日志。"""

        return cls(
            pipeline_version=pipeline_version,
            trace_id=trace_id,
            request_id=_safe_text(request_id),
            question=_safe_text(question) or "",
            rewritten_question=_safe_text(rewritten_question),
            domain=_safe_text(domain) or "",
            source_system=_safe_text(source_system) or "",
            status=_safe_text(status) or "",
            stage=_safe_text(stage) or "",
            error_codes=_safe_string_list(error_codes),
            error_message=_safe_text(error_message),
            catalog_ids=_safe_string_list(catalog_ids),
            catalog_versions=_safe_string_list(catalog_versions),
            sql_hash=_safe_sql_hash(sql_hash),
            sql_param_keys=sorted(_safe_string_list(sql_param_keys)),
            validation_errors=_safe_string_list(validation_errors),
            safety_errors=_safe_string_list(safety_errors),
            explain_ok=explain_ok,
            trial_ok=trial_ok,
            row_count=max(0, int(row_count)),
            sample_row_count=max(0, int(sample_row_count)),
            duration_ms=max(0, int(duration_ms)),
            warnings=_safe_string_list(warnings or []),
            candidate_sql_gate_allowed=candidate_sql_gate_allowed,
            candidate_sql_gate_rejected=candidate_sql_gate_rejected,
            candidate_sql_gate_reason_code=_safe_text(candidate_sql_gate_reason_code),
            candidate_sql_gate_sanitized_reason=_safe_text(candidate_sql_gate_sanitized_reason),
            candidate_sql_gate_repair_info=_safe_json_object(candidate_sql_gate_repair_info),
        )


class LogisticsNl2SqlEvaluationLogSummary(BaseModel):
    """评估日志汇总结果。"""

    model_config = ConfigDict(extra="forbid")

    total: int
    by_status: dict[str, int]
    success_count: int
    failure_count: int
    skipped_count: int
    unsupported_count: int = 0


class LogisticsNl2SqlEvaluationLogSink(Protocol):
    """评估日志 sink 协议，便于测试注入内存或失败 sink。"""

    def write(self, record: LogisticsNl2SqlEvaluationLogRecord) -> None:
        """写入一条评估日志。"""


class InMemoryLogisticsNl2SqlEvaluationLogSink:
    """单测/内部评估用内存日志 sink。"""

    def __init__(self) -> None:
        """初始化空记录列表。"""

        self.records: list[LogisticsNl2SqlEvaluationLogRecord] = []

    def write(self, record: LogisticsNl2SqlEvaluationLogRecord) -> None:
        """追加一条日志记录，保持对象不可变且重新校验后的快照。"""

        safe_record = LogisticsNl2SqlEvaluationLogRecord.model_validate(record.model_dump(mode="json"))
        self.records.append(safe_record.model_copy(deep=True))


class JsonlLogisticsNl2SqlEvaluationLogSink:
    """受控 JSONL 文件日志 sink。

    业务逻辑：
        JSONL 仅用于 shadow/evaluation 离线分析，不接正式 QA 主链路。路径必须位于显式 root_dir
        下，避免因错误配置写出工作区或覆盖系统文件。
    """

    def __init__(self, path: str | Path, *, root_dir: str | Path) -> None:
        """初始化 JSONL sink 并校验路径边界。"""

        self.root_dir = Path(root_dir).resolve()
        self.path = Path(path).resolve()
        if not self.path.is_relative_to(self.root_dir):
            raise ValueError(f"evaluation_log_path_outside_root::{self.path}")

    def write(self, record: LogisticsNl2SqlEvaluationLogRecord) -> None:
        """以一行 JSON 写入重新校验后的日志记录。"""

        safe_record = LogisticsNl2SqlEvaluationLogRecord.model_validate(record.model_dump(mode="json"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(safe_record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(payload + "\n")


def summarize_evaluation_logs(
    records: list[LogisticsNl2SqlEvaluationLogRecord],
) -> LogisticsNl2SqlEvaluationLogSummary:
    """按状态汇总评估日志。

    参数：
        records: shadow pipeline 产生的评估日志列表。
    返回：
        总数、各状态数量、成功/失败/跳过/不支持数量。
    """

    status_counter = Counter(record.status for record in records)
    skipped_statuses = {"skipped"}
    unsupported_statuses = {"unsupported"}
    success_count = status_counter.get("success", 0)
    skipped_count = sum(status_counter.get(status, 0) for status in skipped_statuses)
    unsupported_count = sum(status_counter.get(status, 0) for status in unsupported_statuses)
    failure_count = len(records) - success_count - skipped_count - unsupported_count
    return LogisticsNl2SqlEvaluationLogSummary(
        total=len(records),
        by_status=dict(status_counter),
        success_count=success_count,
        failure_count=max(0, failure_count),
        skipped_count=skipped_count,
        unsupported_count=unsupported_count,
    )


def redact_evaluation_text(value: str) -> str:
    """脱敏评估日志文本。

    参数：
        value: 可能包含 DSN、password、token、API key、Bearer token 的原始文本。
    返回：
        脱敏后的文本；敏感值统一替换为 `[REDACTED]`。
    """

    redacted = str(value or "")
    for pattern, replacement in SECRET_REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    if SQL_TEXT_PATTERN.search(redacted):
        return "[SQL_REDACTED]"
    return redacted


def _safe_text(value: Any, *, max_chars: int = MAX_EVALUATION_TEXT_CHARS) -> str | None:
    """把任意日志文本转为脱敏、截断后的安全摘要。"""

    if value is None:
        return None
    text = redact_evaluation_text(str(value))
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _safe_sql_hash(value: Any) -> str | None:
    """校验 SQL hash 形态，防止误把 SQL 原文或密钥文本写入日志。"""

    if value is None:
        return None
    text = str(value).strip()
    if SQL_HASH_PATTERN.fullmatch(text):
        return text.lower()
    return None


def _safe_non_negative_int(value: Any) -> int:
    """将计数字段收敛为非负整数。"""

    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, number)


def _coerce_string_list(value: Any) -> list[str]:
    """把任意输入收敛为字符串列表，供列表字段脱敏使用。"""

    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def _dedupe_strings(values: list[str]) -> list[str]:
    """稳定去重字符串列表。"""

    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _safe_string_list(values: list[str]) -> list[str]:
    """对日志列表字段逐项脱敏、截断并稳定去重。"""

    sanitized = [_safe_text(value) or "" for value in values]
    return _dedupe_strings(sanitized)


def _safe_json_value(value: Any) -> Any:
    """递归脱敏 JSON 值，供 gate repair_info 这类结构化摘要字段使用。"""

    if isinstance(value, dict):
        return _safe_json_object(value) or {}
    if isinstance(value, list):
        return [_safe_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_safe_json_value(item) for item in value]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _safe_text(value)


def _safe_json_object(value: Any) -> dict[str, Any] | None:
    """把任意 dict 收敛为脱敏 JSON 对象；非 dict 输入直接丢弃。"""

    if value is None:
        return None
    if not isinstance(value, dict):
        return None
    result: dict[str, Any] = {}
    for key, item in value.items():
        safe_key = _safe_text(key, max_chars=120)
        if not safe_key:
            continue
        result[safe_key] = _safe_json_value(item)
    return result


__all__ = [
    "EVALUATION_LOG_SCHEMA_VERSION",
    "InMemoryLogisticsNl2SqlEvaluationLogSink",
    "JsonlLogisticsNl2SqlEvaluationLogSink",
    "LogisticsNl2SqlEvaluationLogRecord",
    "LogisticsNl2SqlEvaluationLogSink",
    "LogisticsNl2SqlEvaluationLogSummary",
    "redact_evaluation_text",
    "summarize_evaluation_logs",
]

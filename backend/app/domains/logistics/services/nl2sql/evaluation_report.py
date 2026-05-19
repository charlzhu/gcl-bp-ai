from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domains.logistics.services.nl2sql.evaluation_log import (
    LogisticsNl2SqlEvaluationLogRecord,
    redact_evaluation_text,
)

EVALUATION_REPORT_SCHEMA_VERSION = "logistics_nl2sql_evaluation_report.v1"
FAIL_CLOSED_STATUSES = {"validation_failed", "render_failed", "safety_failed", "explain_failed", "trial_failed"}
EXECUTION_FAILURE_STATUSES = {"explain_failed", "trial_failed"}
SQL_HASH_ELIGIBLE_STATUSES = {"success", "safety_failed", "explain_failed", "trial_failed"}


class LogisticsNl2SqlEvaluationReportTopError(BaseModel):
    """物流 NL2SQL 评估报表中的高频错误码。"""

    model_config = ConfigDict(extra="forbid")

    error_code: str
    count: int

    @field_validator("error_code", mode="before")
    @classmethod
    def _sanitize_error_code(cls, value: Any) -> str:
        """直接构造 top error 时也要脱敏错误码文本。"""

        return _safe_report_text(str(value or "")) or ""

    @field_validator("count", mode="before")
    @classmethod
    def _sanitize_count(cls, value: Any) -> int:
        """错误次数收敛为非负整数。"""

        return _safe_report_non_negative_int(value)


class LogisticsNl2SqlEvaluationReportSampleOutcome(BaseModel):
    """单条离线样例的安全结果摘要。

    业务逻辑：
        样例摘要只保留样例 ID、业务描述、状态、阶段和稳定错误码；不暴露 SQL 原文、参数 key、
        参数值、用户问题或 executor 错误文本，避免报表从评估日志回流内部 trace。
    """

    model_config = ConfigDict(extra="forbid")

    sample_id: str
    description: str
    status: str
    stage: str
    error_codes: list[str] = Field(default_factory=list)

    @field_validator("sample_id", "description", "status", "stage", mode="before")
    @classmethod
    def _sanitize_text_field(cls, value: Any) -> str:
        """直接构造样例摘要时也要脱敏所有文本字段。"""

        return _safe_report_text(str(value or "")) or ""

    @field_validator("error_codes", mode="before")
    @classmethod
    def _sanitize_error_codes(cls, value: Any) -> list[str]:
        """样例错误码列表统一脱敏和去重。"""

        return _dedupe_report_texts(_coerce_report_text_list(value))


class LogisticsNl2SqlEvaluationReport(BaseModel):
    """物流 NL2SQL shadow smoke 确定性评估报表。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = EVALUATION_REPORT_SCHEMA_VERSION
    total: int
    by_status: dict[str, int]
    by_stage: dict[str, int]
    by_error_code: dict[str, int]
    success_count: int
    failure_count: int
    skipped_count: int
    unsupported_count: int
    success_rate: float
    fail_closed_count: int
    safety_block_count: int
    execution_failure_count: int
    sql_hash_coverage: float
    by_metric_id: dict[str, int] = Field(default_factory=dict)
    by_dimension_id: dict[str, int] = Field(default_factory=dict)
    by_table_id: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_business_case: dict[str, int] = Field(default_factory=dict)
    by_metric_family: dict[str, int] = Field(default_factory=dict)
    expected_status_match_count: int = 0
    expected_status_mismatch_count: int = 0
    expected_status_match_rate: float = 0.0
    safety_pass_count: int = 0
    executor_touched_count: int = 0
    executor_not_touched_count: int = 0
    catalog_ref_coverage: float = 0.0
    distinct_catalog_ref_count: int = 0
    top_errors: list[LogisticsNl2SqlEvaluationReportTopError] = Field(default_factory=list)
    sample_outcomes: list[LogisticsNl2SqlEvaluationReportSampleOutcome] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _sanitize_schema_version(cls, value: Any) -> str:
        """schema 版本也按普通报表文本脱敏。"""

        return _safe_report_text(str(value or "")) or EVALUATION_REPORT_SCHEMA_VERSION

    @field_validator(
        "by_status",
        "by_stage",
        "by_error_code",
        "by_metric_id",
        "by_dimension_id",
        "by_table_id",
        "by_category",
        "by_business_case",
        "by_metric_family",
        mode="before",
    )
    @classmethod
    def _sanitize_counter_dict(cls, value: Any) -> dict[str, int]:
        """报表聚合 key 可能来自外部状态/错误码，直接构造时也要脱敏。"""

        return _safe_counter_dict(value)

    @field_validator(
        "total",
        "success_count",
        "failure_count",
        "skipped_count",
        "unsupported_count",
        "fail_closed_count",
        "safety_block_count",
        "execution_failure_count",
        "distinct_catalog_ref_count",
        "expected_status_match_count",
        "expected_status_mismatch_count",
        "safety_pass_count",
        "executor_touched_count",
        "executor_not_touched_count",
        mode="before",
    )
    @classmethod
    def _sanitize_count_field(cls, value: Any) -> int:
        """报表计数字段收敛为非负整数。"""

        return _safe_report_non_negative_int(value)

    @field_validator("success_rate", "sql_hash_coverage", "catalog_ref_coverage", "expected_status_match_rate", mode="before")
    @classmethod
    def _sanitize_ratio_field(cls, value: Any) -> float:
        """比例字段限制在 0-1 范围。"""

        return _safe_report_ratio(value)

    @field_validator("warnings", mode="before")
    @classmethod
    def _sanitize_warnings(cls, value: Any) -> list[str]:
        """报表告警列表统一脱敏。"""

        return _dedupe_report_texts(_coerce_report_text_list(value))


def build_logistics_nl2sql_evaluation_report(
    records: Iterable[LogisticsNl2SqlEvaluationLogRecord],
    *,
    sample_ids: dict[str, str] | None = None,
    sample_descriptions: dict[str, str] | None = None,
    warnings: list[str] | None = None,
    include_catalog_breakdown: bool = False,
    sample_metadata: dict[str, dict[str, Any]] | None = None,
) -> LogisticsNl2SqlEvaluationReport:
    """基于 M5 evaluation log 生成 M6 离线评估报表。

    参数：
        records: M5 shadow pipeline 产生的脱敏日志记录。
        sample_ids: 可选 trace_id 到业务样例 ID 的映射，smoke runner 用它还原稳定样例 ID。
        sample_descriptions: 可选 trace_id 到业务描述的映射。
        warnings: 报表级别告警，会执行同一套脱敏逻辑。
        include_catalog_breakdown: 是否输出 catalog ref 的指标/维度/表覆盖聚合；默认关闭，避免 M6/M7
            通用报表扩大内部表名暴露面。M8 shadow-only 评估显式开启。
        sample_metadata: 可选 trace_id 到样例评估元数据的映射，用于 M8 输出 category、metric_family
            和 expected_status 一致率；默认关闭，不影响 M6/M7 旧报表。
    返回：
        可 JSON 序列化、可 Markdown 渲染的安全报表对象。
    """

    safe_records = [LogisticsNl2SqlEvaluationLogRecord.model_validate(record.model_dump(mode="json")) for record in records]
    status_counter = Counter(record.status for record in safe_records)
    stage_counter = Counter(record.stage for record in safe_records)
    error_counter: Counter[str] = Counter()
    first_seen_error_order: dict[str, int] = {}
    for record in safe_records:
        for error_code in record.error_codes:
            safe_error = _safe_report_text(error_code)
            if not safe_error:
                continue
            if safe_error not in first_seen_error_order:
                first_seen_error_order[safe_error] = len(first_seen_error_order)
            error_counter[safe_error] += 1

    total = len(safe_records)
    success_count = status_counter.get("success", 0)
    skipped_count = status_counter.get("skipped", 0)
    unsupported_count = status_counter.get("unsupported", 0)
    failure_count = max(0, total - success_count - skipped_count - unsupported_count)
    eligible_hash_records = [record for record in safe_records if record.status in SQL_HASH_ELIGIBLE_STATUSES]
    hash_present_count = sum(1 for record in eligible_hash_records if record.sql_hash)
    metric_counter, dimension_counter, table_counter, records_with_catalog_refs, distinct_catalog_refs = _catalog_breakdown(
        safe_records,
        enabled=include_catalog_breakdown,
    )
    metadata_summary = _sample_metadata_summary(safe_records, sample_metadata or {})
    safety_pass_count = sum(1 for record in safe_records if record.sql_hash and record.status != "safety_failed")
    executor_touched_count = sum(1 for record in safe_records if record.stage in {"explain", "trial"})

    report_warnings = _dedupe_report_texts(
        [*(warnings or []), *(warning for record in safe_records for warning in record.warnings)]
    )
    sample_ids = sample_ids or {}
    sample_descriptions = sample_descriptions or {}

    return LogisticsNl2SqlEvaluationReport(
        total=total,
        by_status=dict(status_counter),
        by_stage=dict(stage_counter),
        by_error_code=dict(error_counter),
        success_count=success_count,
        failure_count=failure_count,
        skipped_count=skipped_count,
        unsupported_count=unsupported_count,
        success_rate=(success_count / total) if total else 0.0,
        fail_closed_count=sum(status_counter.get(status, 0) for status in FAIL_CLOSED_STATUSES),
        safety_block_count=status_counter.get("safety_failed", 0),
        execution_failure_count=sum(status_counter.get(status, 0) for status in EXECUTION_FAILURE_STATUSES),
        sql_hash_coverage=(hash_present_count / len(eligible_hash_records)) if eligible_hash_records else 0.0,
        by_metric_id=dict(metric_counter),
        by_dimension_id=dict(dimension_counter),
        by_table_id=dict(table_counter),
        by_category=dict(metadata_summary["by_category"]),
        by_business_case=dict(metadata_summary["by_business_case"]),
        by_metric_family=dict(metadata_summary["by_metric_family"]),
        expected_status_match_count=metadata_summary["expected_status_match_count"],
        expected_status_mismatch_count=metadata_summary["expected_status_mismatch_count"],
        expected_status_match_rate=metadata_summary["expected_status_match_rate"],
        safety_pass_count=safety_pass_count,
        executor_touched_count=executor_touched_count,
        executor_not_touched_count=max(0, total - executor_touched_count),
        catalog_ref_coverage=(records_with_catalog_refs / total) if include_catalog_breakdown and total else 0.0,
        distinct_catalog_ref_count=len(distinct_catalog_refs) if include_catalog_breakdown else 0,
        top_errors=[
            LogisticsNl2SqlEvaluationReportTopError(error_code=error_code, count=count)
            for error_code, count in sorted(error_counter.items(), key=lambda item: (-item[1], first_seen_error_order[item[0]]))[:10]
        ],
        sample_outcomes=[
            LogisticsNl2SqlEvaluationReportSampleOutcome(
                sample_id=_safe_report_text(sample_ids.get(record.trace_id) or record.trace_id) or record.trace_id,
                description=_safe_report_text(sample_descriptions.get(record.trace_id) or "") or "",
                status=_safe_report_text(record.status) or "",
                stage=_safe_report_text(record.stage) or "",
                error_codes=[_safe_report_text(error_code) or "" for error_code in record.error_codes],
            )
            for record in safe_records
        ],
        warnings=report_warnings,
    )


def render_logistics_nl2sql_evaluation_report_markdown(report: LogisticsNl2SqlEvaluationReport) -> str:
    """把 M6 评估报表渲染为可读 Markdown。

    参数：
        report: 已经脱敏和聚合后的报表对象。
    返回：
        不含 SQL 原文、参数值或密钥的 Markdown 文本。
    """

    safe_report = LogisticsNl2SqlEvaluationReport.model_validate(report.model_dump(mode="json"))
    lines: list[str] = [
        "# NL2SQL Logistics Shadow Smoke Evaluation Report",
        "",
        "## Summary",
        f"- total: {safe_report.total}",
        f"- success_count: {safe_report.success_count}",
        f"- failure_count: {safe_report.failure_count}",
        f"- skipped_count: {safe_report.skipped_count}",
        f"- unsupported_count: {safe_report.unsupported_count}",
        f"- success_rate: {safe_report.success_rate:.4f}",
        f"- fail_closed_count: {safe_report.fail_closed_count}",
        f"- safety_block_count: {safe_report.safety_block_count}",
        f"- safety_pass_count: {safe_report.safety_pass_count}",
        f"- executor_touched_count: {safe_report.executor_touched_count}",
        f"- executor_not_touched_count: {safe_report.executor_not_touched_count}",
        f"- expected_status_match_count: {safe_report.expected_status_match_count}",
        f"- expected_status_mismatch_count: {safe_report.expected_status_mismatch_count}",
        f"- expected_status_match_rate: {safe_report.expected_status_match_rate:.4f}",
        f"- execution_failure_count: {safe_report.execution_failure_count}",
        f"- sql_hash_coverage: {safe_report.sql_hash_coverage:.4f}",
        f"- catalog_ref_coverage: {safe_report.catalog_ref_coverage:.4f}",
        f"- distinct_catalog_ref_count: {safe_report.distinct_catalog_ref_count}",
        "",
        "## By Status",
    ]
    lines.extend(f"- {key}: {value}" for key, value in safe_report.by_status.items())
    lines.extend(["", "## By Stage"])
    lines.extend(f"- {key}: {value}" for key, value in safe_report.by_stage.items())
    lines.extend(["", "## Top Errors"])
    if safe_report.top_errors:
        lines.extend(f"- {item.error_code}: {item.count}" for item in safe_report.top_errors)
    else:
        lines.append("- none")
    if safe_report.by_metric_id:
        lines.extend(["", "## By Metric"])
        lines.extend(f"- {key}: {value}" for key, value in safe_report.by_metric_id.items())
    if safe_report.by_dimension_id:
        lines.extend(["", "## By Dimension"])
        lines.extend(f"- {key}: {value}" for key, value in safe_report.by_dimension_id.items())
    if safe_report.by_table_id:
        lines.extend(["", "## By Table"])
        lines.extend(f"- {key}: {value}" for key, value in safe_report.by_table_id.items())
    if safe_report.by_category:
        lines.extend(["", "## By Category"])
        lines.extend(f"- {key}: {value}" for key, value in safe_report.by_category.items())
    if safe_report.by_business_case:
        lines.extend(["", "## By Business Case"])
        lines.extend(f"- {key}: {value}" for key, value in safe_report.by_business_case.items())
    if safe_report.by_metric_family:
        lines.extend(["", "## By Metric Family"])
        lines.extend(f"- {key}: {value}" for key, value in safe_report.by_metric_family.items())
    lines.extend(["", "## Sample Outcomes", "| sample_id | description | status | stage | error_codes |", "| --- | --- | --- | --- | --- |"])
    for outcome in safe_report.sample_outcomes:
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(outcome.sample_id),
                    _markdown_cell(outcome.description),
                    _markdown_cell(outcome.status),
                    _markdown_cell(outcome.stage),
                    _markdown_cell(", ".join(outcome.error_codes)),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Warnings"])
    if safe_report.warnings:
        lines.extend(f"- {_safe_report_text(warning)}" for warning in safe_report.warnings)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def _catalog_breakdown(
    records: list[LogisticsNl2SqlEvaluationLogRecord],
    *,
    enabled: bool,
) -> tuple[Counter[str], Counter[str], Counter[str], int, set[str]]:
    """按 catalog ref 聚合 M8 shadow-only 评估维度。

    默认报表不输出该聚合；M8 显式开启后，只从 evaluation log 的 `catalog_ids` 中解析
    `metric:*` / `dimension:*` / `table:*`，不读取 SQL 原文或参数值。
    """

    metric_counter: Counter[str] = Counter()
    dimension_counter: Counter[str] = Counter()
    table_counter: Counter[str] = Counter()
    records_with_catalog_refs = 0
    distinct_catalog_refs: set[str] = set()
    if not enabled:
        return metric_counter, dimension_counter, table_counter, records_with_catalog_refs, distinct_catalog_refs

    for record in records:
        safe_ids = _dedupe_report_texts(list(record.catalog_ids))
        if safe_ids:
            records_with_catalog_refs += 1
        for catalog_id in safe_ids:
            if ":" not in catalog_id:
                continue
            ref_type, ref_value = catalog_id.split(":", 1)
            ref_value = (_safe_report_text(ref_value) or "").strip()
            if not ref_value:
                continue
            distinct_catalog_refs.add(catalog_id)
            if ref_type == "metric":
                metric_counter[ref_value] += 1
            elif ref_type == "dimension":
                dimension_counter[ref_value] += 1
            elif ref_type == "table":
                table_counter[ref_value] += 1
    return metric_counter, dimension_counter, table_counter, records_with_catalog_refs, distinct_catalog_refs


def _sample_metadata_summary(
    records: list[LogisticsNl2SqlEvaluationLogRecord],
    metadata_by_trace: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """汇总 M8 样例元数据维度。

    参数：
        records: 已脱敏 evaluation log 记录。
        metadata_by_trace: trace_id 到样例元数据的映射，可包含 category、business_case、
            metric_family、expected_status。
    返回：
        计数器和 expected-vs-actual 一致率；未提供元数据时返回空聚合，兼容旧 M6/M7 报表。
    业务逻辑：
        只聚合稳定枚举/样例标签，不读取 SQL 文本或参数值。
    """

    by_category: Counter[str] = Counter()
    by_business_case: Counter[str] = Counter()
    by_metric_family: Counter[str] = Counter()
    match_count = 0
    mismatch_count = 0
    expected_count = 0
    for record in records:
        metadata = metadata_by_trace.get(record.trace_id) or {}
        category = _safe_report_text(str(metadata.get("category") or "")) or ""
        business_case = _safe_report_text(str(metadata.get("business_case") or "")) or ""
        metric_family = _safe_report_text(str(metadata.get("metric_family") or "")) or ""
        expected_status = _safe_report_text(str(metadata.get("expected_status") or "")) or ""
        if category:
            by_category[category] += 1
        if business_case:
            by_business_case[business_case] += 1
        if metric_family:
            by_metric_family[metric_family] += 1
        if expected_status:
            expected_count += 1
            if expected_status == record.status:
                match_count += 1
            else:
                mismatch_count += 1
    return {
        "by_category": by_category,
        "by_business_case": by_business_case,
        "by_metric_family": by_metric_family,
        "expected_status_match_count": match_count,
        "expected_status_mismatch_count": mismatch_count,
        "expected_status_match_rate": (match_count / expected_count) if expected_count else 0.0,
    }


def _safe_report_text(value: str | None) -> str | None:
    """报表文本统一脱敏，避免聚合层重新泄露敏感片段。"""

    if value is None:
        return None
    return redact_evaluation_text(str(value))


def _safe_report_non_negative_int(value: Any) -> int:
    """将报表计数字段收敛为非负整数。"""

    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, number)


def _safe_report_ratio(value: Any) -> float:
    """将报表比例字段收敛到 0-1。"""

    try:
        ratio = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(1.0, max(0.0, ratio))


def _safe_counter_dict(value: Any) -> dict[str, int]:
    """对报表 Counter/字典的 key 脱敏，并合并脱敏后相同的 key。"""

    if not isinstance(value, dict):
        return {}
    result: dict[str, int] = {}
    for raw_key, raw_count in value.items():
        key = (_safe_report_text(str(raw_key or "")) or "").strip()
        if not key:
            continue
        result[key] = result.get(key, 0) + _safe_report_non_negative_int(raw_count)
    return result


def _coerce_report_text_list(value: Any) -> list[str]:
    """把任意报表文本列表输入收敛为字符串列表。"""

    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def _dedupe_report_texts(values: list[str]) -> list[str]:
    """脱敏并稳定去重报表告警文本。"""

    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = (_safe_report_text(value) or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _markdown_cell(value: str) -> str:
    """转义 Markdown 表格单元格。"""

    return (_safe_report_text(value) or "").replace("|", "\\|").replace("\n", " ")


__all__ = [
    "EVALUATION_REPORT_SCHEMA_VERSION",
    "LogisticsNl2SqlEvaluationReport",
    "LogisticsNl2SqlEvaluationReportSampleOutcome",
    "LogisticsNl2SqlEvaluationReportTopError",
    "build_logistics_nl2sql_evaluation_report",
    "render_logistics_nl2sql_evaluation_report_markdown",
]

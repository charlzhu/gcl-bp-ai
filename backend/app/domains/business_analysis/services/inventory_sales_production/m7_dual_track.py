from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field


# === 对比项枚举 ===
DualTrackCompareDimension = Literal[
    "status_classification",   # 状态分类一致性
    "metric_consistency",      # 指标口径一致性
    "period_consistency",      # 期间口径一致性
    "row_count_magnitude",     # 结果行数量级
    "key_value_consistency",   # 关键数值
    "technical_leak_safety",   # 技术泄露检查
]


# === 单条对比记录 ===
class InventorySalesProductionM7DualTrackRecord(BaseModel):
    """M7 双轨对比单条记录。

    参数：
        sample_id: M6.2 样本 ID。
        question: 用户原始问法。
        m4_status: M4 确定性问答的状态分类。
        m4_summary: M4 确定性问答的摘要（脱敏后记录）。
        m4_row_count: M4 结果行数；无结果时为 0。
        m6_actual_status: M6 shadow gate 的实际状态（matched/validation_failed/shadow_error）。
        m6_provider_live_called: M6 是否实际调用了 provider。
        m6_sqlplan_validation_ok: M6 SQLPlan 校验是否通过。
        compare_dimensions: 各维度对比结果。
        mismatch_flags: 不一致标记列表。
        technical_leak_detected: 是否发现技术泄露。
        risk_notes: 风险记录。
    """

    model_config = ConfigDict(extra="forbid")

    sample_id: str
    question: str
    m4_status: str = ""
    m4_summary: str = ""
    m4_row_count: int = 0
    m6_actual_status: str = ""
    m6_provider_live_called: bool = False
    m6_sqlplan_validation_ok: bool = False
    compare_dimensions: dict[str, str] = Field(default_factory=dict)
    mismatch_flags: list[str] = Field(default_factory=list)
    technical_leak_detected: bool = False
    risk_notes: list[str] = Field(default_factory=list)


class InventorySalesProductionM7DualTrackReport(BaseModel):
    """M7 双轨对比报告。

    参数：
        version: 报告版本。
        total: 总样本数。
        matched_count: M4 与 M6 状态一致的样本数。
        mismatch_count: 状态不一致的样本数。
        mismatch_records: 不一致样本记录。
        all_technical_leak_clean: 是否全部无技术泄露。
        provider_live_called_count: 调用 provider 的样本数。
        records: 完整对比记录。
    """

    model_config = ConfigDict(extra="forbid")

    version: str = "business_analysis_inventory_sales_production_m7_dual_track.v1"
    total: int = 0
    matched_count: int = 0
    mismatch_count: int = 0
    mismatch_records: list[InventorySalesProductionM7DualTrackRecord] = Field(default_factory=list)
    all_technical_leak_clean: bool = True
    provider_live_called_count: int = 0
    records: list[InventorySalesProductionM7DualTrackRecord] = Field(default_factory=list)


def _status_m4_to_canonical(m4_status_code: str) -> str:
    """把 M4 QA 状态码映射为标准对比枚举。"""
    mapping = {
        "OK": "matched",
        "CLARIFICATION_REQUIRED": "clarify",
        "UNSUPPORTED": "unsupported",
        "EXECUTION_ERROR": "error",
        "EMPTY": "empty_result",
    }
    return mapping.get(m4_status_code, "unknown")


def _status_m6_to_canonical(m6_actual_status: str) -> str:
    """把 M6 shadow gate 实际状态映射为标准对比枚举。"""
    mapping = {
        "matched": "matched",
        "empty": "empty_result",
        "validation_failed": "unsupported",
        "shadow_error": "error",
    }
    return mapping.get(m6_actual_status, "unknown")


def compare_single(
    *,
    sample_id: str,
    question: str,
    m4_status_code: str,
    m4_summary: str,
    m4_row_count: int,
    m6_actual_status: str,
    m6_provider_live_called: bool,
    m6_sqlplan_validation_ok: bool,
) -> InventorySalesProductionM7DualTrackRecord:
    """执行 M4 与 M6 轨道的单条对比。"""

    m4_canonical = _status_m4_to_canonical(m4_status_code)
    m6_canonical = _status_m6_to_canonical(m6_actual_status)

    compare_dims: dict[str, str] = {}
    mismatches: list[str] = []
    risk_notes: list[str] = []

    # 维度 1：状态分类对比
    dim_status = f"m4={m4_canonical}/m6={m6_canonical}"
    if m4_canonical != m6_canonical:
        mismatches.append(f"status_classification::{dim_status}")
        risk_notes.append(f"状态分类不一致：M4={m4_canonical}，M6={m6_canonical}")
    compare_dims["status_classification"] = dim_status

    # 维度 2：指标口径/期间口径通过 M4 摘要内容判断
    has_period_end = "最后已发布月份" in m4_summary or "时点" in m4_summary
    has_yoy = "同比" in m4_summary or "暂不" in m4_summary
    compare_dims["metric_consistency"] = "period_end" if has_period_end else "flow_sum"
    if has_yoy:
        compare_dims["period_consistency"] = "unsupported"

    # 维度 3：行数量级
    compare_dims["row_count_magnitude"] = f"m4={m4_row_count}"

    # 维度 4：技术泄露检查
    forbidden = ("SQL", "query_key", "planner", "guardrail", "schema", "raw", "debug", "ba_isp", "metric_code")
    text = json.dumps({"m4_summary": m4_summary}, ensure_ascii=False).lower()
    leak_detected = any(word.lower() in text for word in forbidden)

    return InventorySalesProductionM7DualTrackRecord(
        sample_id=sample_id,
        question=question,
        m4_status=m4_status_code,
        m4_summary=m4_summary,
        m4_row_count=m4_row_count,
        m6_actual_status=m6_actual_status,
        m6_provider_live_called=m6_provider_live_called,
        m6_sqlplan_validation_ok=m6_sqlplan_validation_ok,
        compare_dimensions=compare_dims,
        mismatch_flags=mismatches,
        technical_leak_detected=leak_detected,
        risk_notes=risk_notes,
    )


def run_dual_track_comparison(
    *,
    samples: list[dict[str, Any]],
    m4_ask: Callable[[str], dict[str, Any]],
    m6_run_sample: Callable[[str], dict[str, Any]],
    artifact_dir: Path | None = None,
) -> InventorySalesProductionM7DualTrackReport:
    """执行 M4 vs M6 双轨对比。

    参数：
        samples: 样本列表，每项含 sample_id、question、expected_status。
        m4_ask: M4 QA 服务的 ask 函数，接受 question 返回 dict。
        m6_run_sample: M6 shadow gate 的运行函数，接受 question 返回 dict。
        artifact_dir: 可选验收材料目录。
    返回：
        InventorySalesProductionM7DualTrackReport。
    """

    records: list[InventorySalesProductionM7DualTrackRecord] = []
    mismatches: list[InventorySalesProductionM7DualTrackRecord] = []
    technical_leak_clean = True
    provider_called_count = 0

    for sample in samples:
        sid = sample.get("sample_id", "")
        question = sample.get("question", "")

        # M4 轨道
        try:
            m4_result = m4_ask(question)
            m4_status = (m4_result.get("status") or {}).get("code", "")
            m4_summary = m4_result.get("answer_summary", "")
            m4_rows = m4_result.get("result_table")
            m4_row_count = len(m4_rows.get("rows", [])) if isinstance(m4_rows, dict) else 0
        except Exception:  # noqa: BLE001
            m4_status = "EXECUTION_ERROR"
            m4_summary = ""
            m4_row_count = 0

        # M6 轨道
        try:
            m6_result = m6_run_sample(question)
            m6_status = m6_result.get("actual_status", "shadow_error")
            m6_live = bool(m6_result.get("provider_live_called", False))
            m6_valid = bool(m6_result.get("sqlplan_validation_ok", False))
        except Exception:  # noqa: BLE001
            m6_status = "shadow_error"
            m6_live = False
            m6_valid = False

        if m6_live:
            provider_called_count += 1

        record = compare_single(
            sample_id=sid,
            question=question,
            m4_status_code=m4_status,
            m4_summary=m4_summary,
            m4_row_count=m4_row_count,
            m6_actual_status=m6_status,
            m6_provider_live_called=m6_live,
            m6_sqlplan_validation_ok=m6_valid,
        )

        records.append(record)
        if record.mismatch_flags:
            mismatches.append(record)
        if record.technical_leak_detected:
            technical_leak_clean = False

    report = InventorySalesProductionM7DualTrackReport(
        total=len(samples),
        matched_count=len(samples) - len(mismatches),
        mismatch_count=len(mismatches),
        mismatch_records=mismatches,
        all_technical_leak_clean=technical_leak_clean,
        provider_live_called_count=provider_called_count,
        records=records,
    )

    if artifact_dir:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "m7-dual-track-report.json").write_text(
            report.model_dump_json(indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (artifact_dir / "m7-dual-track-records.jsonl").write_text(
            "\n".join(
                json.dumps(r.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
                for r in records
            ) + "\n",
            encoding="utf-8",
        )

    return report


__all__ = [
    "InventorySalesProductionM7DualTrackRecord",
    "InventorySalesProductionM7DualTrackReport",
    "compare_single",
    "run_dual_track_comparison",
]

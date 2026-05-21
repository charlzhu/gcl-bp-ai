# -*- coding: utf-8 -*-
"""M7 NL2SQL shadow 与 M4 QA 双轨对比模块。

业务定位：
    1. 将 M6 live provider 产出的 SQLPlan shadow 执行结果与 M4 确定性 QA 结果做逐维度对比。
    2. 对比维度：状态分类、指标口径、期间口径、结果行数、关键数值、用户可见文案安全性。
    3. M4 仍作为正式答案源，M7 只记录 shadow 对比报告，不修改 M4 或 M6 主链路。
    4. 所有异常 fail-closed，不暴露内部表名、SQL、provider 或密钥。

依赖：
    - M4: InventorySalesProductionNlQueryPlanner + InventorySalesProductionQueryExecutor
    - M6: InventorySalesProductionM6SqlPlanGenerator + InventorySalesProductionM6ReadonlyMiddleDbShadowExecutor
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

M7_ISP_SHADOW_QA_COMPARE_VERSION = "business_analysis_inventory_sales_production_m7_shadow_qa_compare.v1"
DEFAULT_M7_RECORDS_FILENAME = "m7-shadow-qa-compare-records.jsonl"
DEFAULT_M7_REPORT_FILENAME = "m7-shadow-qa-compare-report.json"

# ---------------------------------------------------------------------------
# 对比维度定义
# ---------------------------------------------------------------------------

M7_COMPARE_DIMENSIONS: list[dict[str, str]] = [
    {
        "dimension": "status_classification",
        "label": "状态分类",
        "description": "对比 M4 QA 状态分类与 M6 shadow 执行状态是否一致",
    },
    {
        "dimension": "metric_caliber",
        "label": "指标口径",
        "description": "对比 M4 和 M6 解析出的业务指标编码是否一致",
    },
    {
        "dimension": "period_caliber",
        "label": "期间口径",
        "description": "对比 M4 和 M6 解析出的年份、月份、季度等期间参数是否一致",
    },
    {
        "dimension": "row_count",
        "label": "结果行数",
        "description": "对比 M4 和 M6 返回的结果行数是否一致",
    },
    {
        "dimension": "key_value",
        "label": "关键数值",
        "description": "对比 M4 和 M6 返回的关键数值是否一致（容忍 Decimal scale 差异）",
    },
    {
        "dimension": "text_safety",
        "label": "用户可见文案安全性",
        "description": "检查 M4 回答中是否泄露内部表名、SQL、query_key 等技术实现细节",
    },
]

# ---------------------------------------------------------------------------
# 内部安全检测正则
# ---------------------------------------------------------------------------

_FORBIDDEN_TEXT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("internal_table_name", re.compile(r"\bdwd_ba_isp\w*\b|\bdim_ba_isp\w*\b|\bods_ba_isp\w*\b", re.IGNORECASE)),
    ("sql_keyword", re.compile(r"\b(select|insert|update|delete|from|where|having)\b.*\b(from|where)\b", re.IGNORECASE)),
    ("query_key_exposure", re.compile(r"\bquery_key\b|ba_isp_\w+", re.IGNORECASE)),
    ("planner_internal", re.compile(r"\bplanner\b|\bguardrail\b|\bschema\b|raw_payload|debug\b", re.IGNORECASE)),
    ("llm_internal", re.compile(r"\bllm\b|\bembedding\b|\brerank\b|\bvector\b", re.IGNORECASE)),
    ("numeric_sql_like", re.compile(r"\bmetric_code\b|\bsqlplan\b|\bcatalog_version\b", re.IGNORECASE)),
]

_SECRET_VALUE_RE = re.compile(r"sk-[A-Za-z0-9_-]{6,}|Bearer\s+[^\s,'\"}]+", re.IGNORECASE)
_URL_RE = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s,'\")]+")
_HOST_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d{2,5})?\b")


# ---------------------------------------------------------------------------
# 样例声明
# ---------------------------------------------------------------------------

class InventorySalesProductionM7ShadowQaCompareSample(BaseModel):
    """M7 产销存 QA 双轨对比样例声明。

    参数：
        sample_id: 样例唯一标识。
        question: 用户自然语言问题。
        question_category: 问题类别，如 sales_summary、inventory_snapshot、budget_achievement。
    """

    model_config = ConfigDict(extra="forbid")

    sample_id: str
    question: str
    question_category: str


# ---------------------------------------------------------------------------
# 对比记录
# ---------------------------------------------------------------------------

class InventorySalesProductionM7ShadowQaCompareRecord(BaseModel):
    """M7 脱敏对比记录（可持久化）。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = M7_ISP_SHADOW_QA_COMPARE_VERSION
    sample_id: str
    question_category: str
    overall_match: bool
    comparisons: list[dict[str, Any]] = Field(default_factory=list)
    m4_status: str = ""
    m6_status: str = ""
    m4_row_count: int = 0
    m6_row_count: int = 0
    shadow_only: bool = True
    formal_qa_executed: bool = False


# ---------------------------------------------------------------------------
# 运行结果
# ---------------------------------------------------------------------------

class InventorySalesProductionM7ShadowQaCompareRunResult(BaseModel):
    """M7 shadow QA compare 运行结果。"""

    model_config = ConfigDict(extra="forbid")

    records: list[InventorySalesProductionM7ShadowQaCompareRecord] = Field(default_factory=list)
    records_path: Path
    report_path: Path
    report: dict[str, Any] = Field(default_factory=dict)
    shadow_only: bool = True
    formal_qa_executed: bool = False


# ---------------------------------------------------------------------------
# 核心对比函数
# ---------------------------------------------------------------------------

def compare_m4_m6_results(
    *,
    m4_result: dict[str, Any],
    m6_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """对 M4 QA 结果与 M6 shadow 结果做六维度对比。

    参数：
        m4_result: M4 确定性 QA 的执行结果，必须包含 status、classification、
                   plan_metrics、plan_period、row_count、rows、answer_summary 等字段。
        m6_result: M6 live provider shadow 执行结果，必须包含 status、
                   plan_metrics、plan_period、row_count、rows 等字段。
    返回：
        六个维度的对比结果列表，每项包含 dimension、m4_value、m6_value、match、detail。
    异常处理：
        任何单维度对比异常不应中断其他维度；异常维度会标记为 match=False 并记录错误原因。
    """
    comparisons: list[dict[str, Any]] = []

    # 1. 状态分类对比
    comparisons.append(_compare_status_classification(m4_result, m6_result))

    # 2. 指标口径对比
    comparisons.append(_compare_metric_caliber(m4_result, m6_result))

    # 3. 期间口径对比
    comparisons.append(_compare_period_caliber(m4_result, m6_result))

    # 4. 结果行数对比
    comparisons.append(_compare_row_count(m4_result, m6_result))

    # 5. 关键数值对比
    comparisons.append(_compare_key_value(m4_result, m6_result))

    # 6. 文案安全性检查
    comparisons.append(_check_text_safety(m4_result))

    return comparisons


def _compare_status_classification(
    m4_result: dict[str, Any],
    m6_result: dict[str, Any],
) -> dict[str, Any]:
    """对比 M4 QA 状态分类与 M6 shadow 执行状态。

    业务逻辑：
        M4 的 success→A、clarification→B、empty_result/unsupported→C、error→D；
        M6 的 matched 应对应 M4 的 success；
        其他 M6 状态（empty/validation_failed/shadow_error）应在报告中标记不匹配。
    """
    try:
        m4_status = str(m4_result.get("status") or "")
        m4_classification = str(m4_result.get("classification") or "")
        m6_status = str(m6_result.get("status") or "")

        # 映射 M4 status 到 classification
        m4_effective = m4_classification if m4_classification else _status_to_classification(m4_status)
        # 映射 M6 status 到可比分类
        m6_effective = _m6_status_to_comparable(m6_status)

        match = m4_effective == m6_effective
        detail = None if match else f"M4分类={m4_effective}, M6状态={m6_effective}"

        return {
            "dimension": "status_classification",
            "m4_value": f"status={m4_status}, classification={m4_classification}",
            "m6_value": f"status={m6_status}",
            "match": match,
            "detail": detail,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "dimension": "status_classification",
            "m4_value": None,
            "m6_value": None,
            "match": False,
            "detail": f"status_compare_error::{_safe_error_text(str(exc))}",
        }


def _compare_metric_caliber(
    m4_result: dict[str, Any],
    m6_result: dict[str, Any],
) -> dict[str, Any]:
    """对比 M4 和 M6 解析出的业务指标编码。

    业务逻辑：
        从 M4 plan_metrics 和 M6 plan_metrics 中各取指标编码集合，比较是否一致。
        空指标视为不匹配。
    """
    try:
        m4_metrics = set(str(m or "") for m in (m4_result.get("plan_metrics") or []))
        m6_metrics = set(str(m or "") for m in (m6_result.get("plan_metrics") or []))

        if not m4_metrics and not m6_metrics:
            match = True
        else:
            match = m4_metrics == m6_metrics

        detail = None if match else f"M4指标={sorted(m4_metrics)}, M6指标={sorted(m6_metrics)}"

        return {
            "dimension": "metric_caliber",
            "m4_value": sorted(m4_metrics),
            "m6_value": sorted(m6_metrics),
            "match": match,
            "detail": detail,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "dimension": "metric_caliber",
            "m4_value": None,
            "m6_value": None,
            "match": False,
            "detail": f"metric_compare_error::{_safe_error_text(str(exc))}",
        }


def _compare_period_caliber(
    m4_result: dict[str, Any],
    m6_result: dict[str, Any],
) -> dict[str, Any]:
    """对比 M4 和 M6 解析出的期间参数。

    业务逻辑：
        从 plan_period 字典中比较 period_type、year、month 等关键期间参数。
    """
    try:
        m4_period = m4_result.get("plan_period") or {}
        m6_period = m6_result.get("plan_period") or {}

        m4_normalized = {
            "period_type": str(m4_period.get("period_type") or ""),
            "year": m4_period.get("year"),
            "month": m4_period.get("month"),
        }
        m6_normalized = {
            "period_type": str(m6_period.get("period_type") or ""),
            "year": m6_period.get("year"),
            "month": m6_period.get("month"),
        }

        match = m4_normalized == m6_normalized
        detail = None if match else f"M4期间={m4_normalized}, M6期间={m6_normalized}"

        return {
            "dimension": "period_caliber",
            "m4_value": m4_normalized,
            "m6_value": m6_normalized,
            "match": match,
            "detail": detail,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "dimension": "period_caliber",
            "m4_value": None,
            "m6_value": None,
            "match": False,
            "detail": f"period_compare_error::{_safe_error_text(str(exc))}",
        }


def _compare_row_count(
    m4_result: dict[str, Any],
    m6_result: dict[str, Any],
) -> dict[str, Any]:
    """对比 M4 和 M6 返回的结果行数。"""
    try:
        m4_count = int(m4_result.get("row_count") or 0)
        m6_count = int(m6_result.get("row_count") or 0)

        match = m4_count == m6_count
        detail = None if match else f"M4行数={m4_count}, M6行数={m6_count}"

        return {
            "dimension": "row_count",
            "m4_value": m4_count,
            "m6_value": m6_count,
            "match": match,
            "detail": detail,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "dimension": "row_count",
            "m4_value": None,
            "m6_value": None,
            "match": False,
            "detail": f"row_count_compare_error::{_safe_error_text(str(exc))}",
        }


def _compare_key_value(
    m4_result: dict[str, Any],
    m6_result: dict[str, Any],
) -> dict[str, Any]:
    """对比 M4 和 M6 返回的关键数值。

    业务逻辑：
        取首行 value_decimal 对比，使用 Decimal 归一化比较，容忍 scale 差异。
        若结果为空则跳过数值对比（已在行数维度体现）。
    """
    try:
        m4_rows = m4_result.get("rows") or []
        m6_rows = m6_result.get("rows") or []

        m4_value = _safe_decimal(_first_row_value(m4_rows))
        m6_value = _safe_decimal(_first_row_value(m6_rows))

        if m4_value is None and m6_value is None:
            match = True
        elif m4_value is not None and m6_value is not None:
            match = m4_value == m6_value
        else:
            match = False

        detail = None if match else f"M4数值={m4_value}, M6数值={m6_value}"

        return {
            "dimension": "key_value",
            "m4_value": str(m4_value) if m4_value is not None else None,
            "m6_value": str(m6_value) if m6_value is not None else None,
            "match": match,
            "detail": detail,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "dimension": "key_value",
            "m4_value": None,
            "m6_value": None,
            "match": False,
            "detail": f"key_value_compare_error::{_safe_error_text(str(exc))}",
        }


def _check_text_safety(m4_result: dict[str, Any]) -> dict[str, Any]:
    """检查 M4 用户可见文案中是否有内部技术泄露。

    业务逻辑：
        扫描 answer_summary、result_table、presentation 等用户可见字段，
        检测是否包含内部表名、SQL 关键词、query_key、planner 等禁止泄露内容。
    """
    try:
        # 收集所有用户可见文本
        visible_texts: list[str] = []
        for key in ("answer_summary",):
            value = m4_result.get(key)
            if isinstance(value, str) and value.strip():
                visible_texts.append(value)
        for key in ("warnings",):
            value = m4_result.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item.strip():
                        visible_texts.append(item)
        # result_table 中的数值和列名也检查
        result_table = m4_result.get("result_table")
        if isinstance(result_table, dict):
            visible_texts.append(json.dumps(result_table, ensure_ascii=False, default=str))

        combined = " ".join(visible_texts)
        findings: list[str] = []

        for label, pattern in _FORBIDDEN_TEXT_PATTERNS:
            if pattern.search(combined):
                findings.append(label)

        match = len(findings) == 0
        detail = None if match else f"发现泄露: {', '.join(findings)}"

        return {
            "dimension": "text_safety",
            "m4_value": "clean" if match else f"leaks_detected: {findings}",
            "m6_value": "N/A（仅检查 M4 文案）",
            "match": match,
            "detail": detail,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "dimension": "text_safety",
            "m4_value": None,
            "m6_value": None,
            "match": False,
            "detail": f"text_safety_check_error::{_safe_error_text(str(exc))}",
        }


# ---------------------------------------------------------------------------
# M7 Runner
# ---------------------------------------------------------------------------

class InventorySalesProductionM7ShadowQaCompareRunner:
    """M7 产销存 QA 双轨对比运行器。

    业务逻辑：
        1. 逐个样例执行 M4 QA 和 M6 shadow，获取结果。
        2. 对每对结果执行六维度对比。
        3. 写入 JSONL 记录和 JSON 对比报告。
        4. 全程不修改 M4 正式 QA 链路，shadow_only=True 且 formal_qa_executed=False。
    """

    def __init__(
        self,
        *,
        m4_qa_callable: Callable[[str], dict[str, Any]],
        m6_shadow_callable: Callable[[str], dict[str, Any]],
    ) -> None:
        """初始化 M7 runner。

        参数：
            m4_qa_callable: 接受问题字符串，返回 M4 QA 结果字典。
            m6_shadow_callable: 接受问题字符串，返回 M6 shadow 结果字典。
        """
        self.m4_qa_callable = m4_qa_callable
        self.m6_shadow_callable = m6_shadow_callable
        # 显式暴露不接管正式 QA 的合同
        self.shadow_only = True
        self.formal_qa_executed = False

    def run(
        self,
        *,
        samples: list[InventorySalesProductionM7ShadowQaCompareSample],
        artifact_dir: Path,
    ) -> InventorySalesProductionM7ShadowQaCompareRunResult:
        """执行 M7 shadow QA 双轨对比并写入验收材料。

        参数：
            samples: 要对比的样例列表。
            artifact_dir: 产物输出目录。
        返回：
            包含记录、报告路径和汇总信息的运行结果。
        """
        artifact_dir.mkdir(parents=True, exist_ok=True)
        records_path = artifact_dir / DEFAULT_M7_RECORDS_FILENAME
        report_path = artifact_dir / DEFAULT_M7_REPORT_FILENAME

        records: list[InventorySalesProductionM7ShadowQaCompareRecord] = []
        matched_count = 0
        mismatch_count = 0

        for sample in samples:
            record = self._run_one(sample)
            records.append(record)
            if record.overall_match:
                matched_count += 1
            else:
                mismatch_count += 1

        report = {
            "version": M7_ISP_SHADOW_QA_COMPARE_VERSION,
            "total": len(samples),
            "matched_count": matched_count,
            "mismatch_count": mismatch_count,
            "shadow_only": True,
            "formal_qa_executed": False,
            "by_dimension": self._dimension_summary(records),
        }

        # 写入 JSONL records
        records_lines = [
            json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
            for record in records
        ]
        records_path.write_text("\n".join(records_lines) + "\n", encoding="utf-8")

        # 写入 JSON report
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        return InventorySalesProductionM7ShadowQaCompareRunResult(
            records=records,
            records_path=records_path,
            report_path=report_path,
            report=report,
        )

    def _run_one(self, sample: InventorySalesProductionM7ShadowQaCompareSample) -> InventorySalesProductionM7ShadowQaCompareRecord:
        """执行单条样例的 M4/M6 双轨对比；异常 fail-closed。"""
        m4_status = ""
        m6_status = ""
        m4_row_count = 0
        m6_row_count = 0
        comparisons: list[dict[str, Any]] = []

        try:
            # 执行 M4 QA
            m4_result = self.m4_qa_callable(sample.question)
            m4_status = str(m4_result.get("status") or "")
            m4_row_count = int(m4_result.get("row_count") or 0)
        except Exception as exc:  # noqa: BLE001
            m4_result = {
                "status": "error",
                "classification": "D",
                "plan_metrics": [],
                "plan_period": {},
                "row_count": 0,
                "rows": [],
                "answer_summary": "",
                "warnings": [],
                "result_table": None,
            }
            m4_status = f"m4_error::{_safe_error_text(str(exc))}"

        try:
            # 执行 M6 shadow
            m6_result = self.m6_shadow_callable(sample.question)
            m6_status = str(m6_result.get("status") or "")
            m6_row_count = int(m6_result.get("row_count") or 0)
        except Exception as exc:  # noqa: BLE001
            m6_result = {
                "status": "shadow_error",
                "plan_metrics": [],
                "plan_period": {},
                "row_count": 0,
                "rows": [],
                "readonly_middle_db_shadow_executed": False,
            }
            m6_status = f"m6_error::{_safe_error_text(str(exc))}"

        # 执行对比
        comparisons = compare_m4_m6_results(m4_result=m4_result, m6_result=m6_result)
        overall_match = all(comp.get("match", False) for comp in comparisons)

        return InventorySalesProductionM7ShadowQaCompareRecord(
            sample_id=sample.sample_id,
            question_category=sample.question_category,
            overall_match=overall_match,
            comparisons=comparisons,
            m4_status=m4_status,
            m6_status=m6_status,
            m4_row_count=m4_row_count,
            m6_row_count=m6_row_count,
        )

    @staticmethod
    def _dimension_summary(
        records: list[InventorySalesProductionM7ShadowQaCompareRecord],
    ) -> dict[str, dict[str, int]]:
        """按维度汇总匹配/不匹配计数。"""
        summary: dict[str, dict[str, int]] = {}
        for dim_def in M7_COMPARE_DIMENSIONS:
            dim = dim_def["dimension"]
            matched = 0
            mismatched = 0
            for record in records:
                for comp in record.comparisons:
                    if comp.get("dimension") == dim:
                        if comp.get("match"):
                            matched += 1
                        else:
                            mismatched += 1
                        break
            summary[dim] = {"matched": matched, "mismatched": mismatched}
        return summary


# ---------------------------------------------------------------------------
# 安全摘要渲染
# ---------------------------------------------------------------------------

def render_safe_m7_shadow_qa_compare_summary_json(
    result: InventorySalesProductionM7ShadowQaCompareRunResult,
) -> str:
    """渲染 M7 shadow QA compare CLI 安全 JSON 摘要。

    参数：
        result: M7 运行结果。
    返回：
        脱敏 JSON 字符串，不含内部表名、SQL、密钥等。
    业务逻辑：
        CLI stdout 可能进入日志或前端可读上下文，因此必须过滤所有内部技术细节。
    """
    report = result.report
    safe = {
        "version": M7_ISP_SHADOW_QA_COMPARE_VERSION,
        "total": report.get("total", 0),
        "matched_count": report.get("matched_count", 0),
        "mismatch_count": report.get("mismatch_count", 0),
        "shadow_only": True,
        "formal_qa_executed": False,
        "records_path": str(result.records_path),
        "report_path": str(result.report_path),
    }
    # 按维度汇总
    by_dimension = report.get("by_dimension", {})
    if by_dimension:
        safe["by_dimension"] = {
            dim: {
                "matched": counts.get("matched", 0),
                "mismatched": counts.get("mismatched", 0),
            }
            for dim, counts in by_dimension.items()
        }

    safe_json = json.dumps(safe, ensure_ascii=False, sort_keys=True)
    lower = safe_json.lower()
    # 二次确认无泄露
    for pattern_label, pattern in _FORBIDDEN_TEXT_PATTERNS:
        if pattern.search(lower):
            return json.dumps(
                {"version": M7_ISP_SHADOW_QA_COMPARE_VERSION, "error": "summary_redacted"},
                ensure_ascii=False,
                sort_keys=True,
            )
    return safe_json


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _status_to_classification(status: str) -> str:
    """将 M4 executor status 映射到 QA classification。"""
    mapping = {
        "success": "A",
        "clarification": "B",
        "empty_result": "C",
        "unsupported": "C",
        "error": "D",
    }
    return mapping.get(status, "D")


def _m6_status_to_comparable(status: str) -> str:
    """将 M6 shadow status 映射到与 M4 classification 可比的分类。"""
    mapping = {
        "matched": "A",
        "empty": "C",
        "validation_failed": "D",
        "shadow_error": "D",
    }
    return mapping.get(status, "D")


def _first_row_value(rows: list[dict[str, Any]]) -> Any:
    """从结果行列表中取首行的 value_decimal。"""
    if not rows:
        return None
    first = rows[0]
    if isinstance(first, dict):
        return first.get("value_decimal")
    return None


def _safe_decimal(value: Any) -> Decimal | None:
    """安全地将值转换为 Decimal。"""
    if value is None:
        return None
    try:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except Exception:
        return None


def _safe_error_text(text: str) -> str:
    """对错误文本做脱敏处理，移除密钥和连接信息。"""
    if not text:
        return "unknown_error"
    # 移除 Bearer token
    text = _SECRET_VALUE_RE.sub("***", text)
    # 移除 URL
    text = _URL_RE.sub("***", text)
    # 移除 IP:port
    text = _HOST_RE.sub("***", text)
    # 截断过长的错误信息
    if len(text) > 200:
        text = text[:200] + "..."
    return text


# ---------------------------------------------------------------------------
# 默认样例构建
# ---------------------------------------------------------------------------

def build_default_inventory_sales_production_m7_shadow_samples(
    *,
    max_samples: int | None = None,
) -> list[InventorySalesProductionM7ShadowQaCompareSample]:
    """构造产销存 M7 shadow QA 双轨对比默认样例。

    参数：
        max_samples: 可选上限限制，用于快速测试截取。
    返回：
        覆盖核心指标、不同期间、同义问法和 fail-closed 场景的样例列表。
    业务逻辑：
        样例应覆盖 M4 已支持的 query_key（销量、库存、预算达成率等），
        并包括 M4 不支持/需澄清的问法以验证双轨对比在异常路径的正确性。
    """
    samples = [
        InventorySalesProductionM7ShadowQaCompareSample(
            sample_id="m7_sales_year_2025",
            question="2025年销量是多少？",
            question_category="sales_summary",
        ),
        InventorySalesProductionM7ShadowQaCompareSample(
            sample_id="m7_sales_quarter_2025_q1",
            question="2025年Q1销量是多少？",
            question_category="sales_summary",
        ),
        InventorySalesProductionM7ShadowQaCompareSample(
            sample_id="m7_sales_ytd_2026",
            question="2026年截至4月累计销量是多少？",
            question_category="sales_summary",
        ),
        InventorySalesProductionM7ShadowQaCompareSample(
            sample_id="m7_inventory_snapshot_2026_04",
            question="2026年4月存货合计是多少？",
            question_category="inventory_snapshot",
        ),
        InventorySalesProductionM7ShadowQaCompareSample(
            sample_id="m7_consigned_inventory_2026_04",
            question="2026年4月寄存仓还有多少？",
            question_category="inventory_snapshot",
        ),
        InventorySalesProductionM7ShadowQaCompareSample(
            sample_id="m7_budget_achievement_2023",
            question="2023年预算达成率是多少？",
            question_category="budget_achievement",
        ),
        InventorySalesProductionM7ShadowQaCompareSample(
            sample_id="m7_sales_with_factory_breakdown",
            question="2025年各基地销量是多少？",
            question_category="sales_breakdown",
        ),
        InventorySalesProductionM7ShadowQaCompareSample(
            sample_id="m7_sales_monthly_trend_2025",
            question="2025年每月销量趋势？",
            question_category="sales_trend",
        ),
        InventorySalesProductionM7ShadowQaCompareSample(
            sample_id="m7_invoice_sales_2025",
            question="2025年开票销量是多少？",
            question_category="sales_summary",
        ),
        # fail-closed 场景：无时间条件
        InventorySalesProductionM7ShadowQaCompareSample(
            sample_id="m7_unsupported_no_year",
            question="销量是多少？",
            question_category="clarification",
        ),
        # fail-closed 场景：M4 不支持的同比
        InventorySalesProductionM7ShadowQaCompareSample(
            sample_id="m7_unsupported_yoy",
            question="2025年比2024年销量增长了多少？",
            question_category="unsupported",
        ),
    ]
    if max_samples is not None and max_samples > 0:
        return samples[:max_samples]
    return samples

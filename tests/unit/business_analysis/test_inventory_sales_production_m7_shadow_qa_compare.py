# -*- coding: utf-8 -*-
"""M7 NL2SQL shadow 与 M4 QA 双轨对比 — 单元测试。

测试范围：
    1. M7 模块可导入且版本号正确。
    2. 对比维度常量完整覆盖六项：状态分类、指标口径、期间口径、结果行数、关键数值、文案安全。
    3. 对比引擎可对两个模拟结果生成逐维度对比记录。
    4. 状态分类维度可正确匹配/不匹配 M4 QA 状态与 M6 shadow 状态。
    5. 指标口径维度可检测 M4/M6 指标编码不一致。
    6. 期间口径维度可检测年度/月度/季度差异。
    7. 结果行数维度可检测行数差异。
    8. 关键数值维度可检测数值差异，并容忍 Decimal 精度差异。
    9. 文案安全性维度可对 M4 回答结果做技术泄露检查。
   10. M7 runner 不干涉 M4 正式 QA 链路（formal_qa_executed=False）。
   11. 异常场景 fail-closed，不会把内部异常暴露到用户可见文案。
   12. 对比报告可直接序列化为 JSON 且不含敏感信息。
"""

from __future__ import annotations

import importlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# 测试辅助函数
# ---------------------------------------------------------------------------

M7_VERSION = "business_analysis_inventory_sales_production_m7_shadow_qa_compare.v1"


def _m7_module():
    """加载产销存 M7 shadow QA compare 模块；RED 阶段应因模块尚未实现而失败。"""
    return importlib.import_module(
        "backend.app.domains.business_analysis.services.inventory_sales_production.m7_shadow_qa_compare"
    )


def _safe_text(payload: object) -> str:
    """把对象转成小写 JSON 文本，便于统一检查脱敏结果。"""
    return json.dumps(payload, ensure_ascii=False, default=str).lower()


def _build_fake_m4_result(
    *,
    status: str = "success",
    classification: str = "A",
    metric_code: str = "shipment_volume",
    year: int = 2025,
    month: int | None = None,
    row_count: int = 1,
    value: Decimal | None = None,
    unit: str = "MW",
    answer_summary: str = "2025年销量为100.00000000 MW",
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """构造模拟 M4 QA 执行结果，用于测试对比引擎。"""
    return {
        "status": status,
        "classification": classification,
        "plan_metrics": [metric_code],
        "plan_period": {"period_type": "year" if month is None else "month", "year": year, "month": month},
        "row_count": row_count,
        "rows": [
            {
                "metric_code": metric_code,
                "metric_name": "发货量",
                "value_decimal": value or Decimal("100.00000000"),
                "unit_standard": unit,
                "months_covered": list(range(1, 13)) if month is None else [month],
            }
        ] if row_count > 0 and status == "success" else [],
        "answer_summary": answer_summary,
        "warnings": warnings or [],
        "result_table": {"columns": ["指标", "数值"], "rows": [{"指标": "发货量", "数值": "100.00000000"}]} if row_count > 0 else None,
    }


def _build_fake_m6_result(
    *,
    status: str = "matched",
    metrics: list[str] | None = None,
    period_type: str = "year",
    year: int = 2025,
    month: int | None = None,
    row_count: int = 1,
    value: Decimal | None = None,
    unit: str = "MW",
) -> dict[str, Any]:
    """构造模拟 M6 live provider shadow 执行结果，用于测试对比引擎。"""
    return {
        "status": status,
        "sqlplan_validation_ok": status != "validation_failed",
        "plan_metrics": metrics or ["shipment_volume"],
        "plan_period": {"period_type": period_type, "year": year, "month": month},
        "row_count": row_count,
        "rows": [
            {
                "metric_code": (metrics or ["shipment_volume"])[0],
                "value_decimal": value or Decimal("100.00000000"),
                "unit_standard": unit,
            }
        ] if row_count > 0 and status == "matched" else [],
        "readonly_middle_db_shadow_executed": status == "matched",
    }


# ---------------------------------------------------------------------------
# 1. 模块导入与版本号
# ---------------------------------------------------------------------------

def test_m7_module_importable_and_version_correct() -> None:
    """M7 模块应可导入，版本号固定为 v1。"""
    m7 = _m7_module()
    assert m7.M7_ISP_SHADOW_QA_COMPARE_VERSION == M7_VERSION


# ---------------------------------------------------------------------------
# 2. 对比维度完整性
# ---------------------------------------------------------------------------

def test_m7_compare_dimensions_cover_all_six() -> None:
    """M7 对比维度必须覆盖状态分类、指标口径、期间口径、结果行数、关键数值、文案安全六项。"""
    m7 = _m7_module()
    dimensions = m7.M7_COMPARE_DIMENSIONS
    assert isinstance(dimensions, list)
    assert len(dimensions) == 6
    dim_names = {d["dimension"] for d in dimensions}
    assert dim_names == {
        "status_classification",
        "metric_caliber",
        "period_caliber",
        "row_count",
        "key_value",
        "text_safety",
    }


# ---------------------------------------------------------------------------
# 3. 单条样例对比
# ---------------------------------------------------------------------------

def test_m7_compare_single_sample_matched_all_dimensions() -> None:
    """当 M4 和 M6 结果完全一致时，所有维度应返回 match=True。"""
    m7 = _m7_module()
    m4_result = _build_fake_m4_result()
    m6_result = _build_fake_m6_result()

    comparisons = m7.compare_m4_m6_results(m4_result=m4_result, m6_result=m6_result)
    assert len(comparisons) == 6
    for comp in comparisons:
        assert comp["match"] is True, f"维度 {comp['dimension']} 应匹配但未匹配: {comp.get('detail')}"


def test_m7_compare_status_classification_mismatch() -> None:
    """状态分类不一致时应正确检测。"""
    m7 = _m7_module()
    m4_result = _build_fake_m4_result(status="success", classification="A")
    m6_result = _build_fake_m6_result(status="empty")

    comparisons = m7.compare_m4_m6_results(m4_result=m4_result, m6_result=m6_result)
    status_comp = [c for c in comparisons if c["dimension"] == "status_classification"][0]
    assert status_comp["match"] is False
    assert "A" in str(status_comp.get("m4_value", "")) or "success" in str(status_comp.get("m4_value", ""))


def test_m7_compare_metric_caliber_mismatch() -> None:
    """指标口径不一致时应正确检测。"""
    m7 = _m7_module()
    m4_result = _build_fake_m4_result(metric_code="shipment_volume")
    m6_result = _build_fake_m6_result(metrics=["ending_inventory_volume"])

    comparisons = m7.compare_m4_m6_results(m4_result=m4_result, m6_result=m6_result)
    metric_comp = [c for c in comparisons if c["dimension"] == "metric_caliber"][0]
    assert metric_comp["match"] is False


def test_m7_compare_period_caliber_mismatch() -> None:
    """期间口径不一致时应正确检测。"""
    m7 = _m7_module()
    m4_result = _build_fake_m4_result(year=2025, month=None)
    m6_result = _build_fake_m6_result(year=2024, period_type="year")

    comparisons = m7.compare_m4_m6_results(m4_result=m4_result, m6_result=m6_result)
    period_comp = [c for c in comparisons if c["dimension"] == "period_caliber"][0]
    assert period_comp["match"] is False


def test_m7_compare_row_count_mismatch() -> None:
    """结果行数不一致时应正确检测。"""
    m7 = _m7_module()
    m4_result = _build_fake_m4_result(row_count=3)
    m6_result = _build_fake_m6_result(row_count=1)

    comparisons = m7.compare_m4_m6_results(m4_result=m4_result, m6_result=m6_result)
    row_comp = [c for c in comparisons if c["dimension"] == "row_count"][0]
    assert row_comp["match"] is False
    assert row_comp["m4_value"] == 3
    assert row_comp["m6_value"] == 1


def test_m7_compare_key_value_mismatch() -> None:
    """关键数值不一致时应正确检测，并容忍 Decimal 精度差异。"""
    m7 = _m7_module()
    m4_result = _build_fake_m4_result(value=Decimal("100.00000000"))
    m6_result = _build_fake_m6_result(value=Decimal("200.00000000"))

    comparisons = m7.compare_m4_m6_results(m4_result=m4_result, m6_result=m6_result)
    value_comp = [c for c in comparisons if c["dimension"] == "key_value"][0]
    assert value_comp["match"] is False


def test_m7_compare_key_value_decimal_tolerance() -> None:
    """微小的 Decimal 精度差异（如 scale 不同）应视为匹配。"""
    m7 = _m7_module()
    m4_result = _build_fake_m4_result(value=Decimal("100.00000000"))
    m6_result = _build_fake_m6_result(value=Decimal("100.0"))  # 不同 scale，相同值

    comparisons = m7.compare_m4_m6_results(m4_result=m4_result, m6_result=m6_result)
    value_comp = [c for c in comparisons if c["dimension"] == "key_value"][0]
    assert value_comp["match"] is True


def test_m7_compare_text_safety_leak_detection() -> None:
    """M4 回答中包含内部技术词时应被文案安全检查捕获。"""
    m7 = _m7_module()
    m4_result = _build_fake_m4_result(
        answer_summary="查询成功，使用了 query_key=ba_isp_metric_summary 和表 dwd_ba_isp_monthly_fact"
    )
    m6_result = _build_fake_m6_result()

    comparisons = m7.compare_m4_m6_results(m4_result=m4_result, m6_result=m6_result)
    safety_comp = [c for c in comparisons if c["dimension"] == "text_safety"][0]
    assert safety_comp["match"] is False


def test_m7_compare_text_safety_clean() -> None:
    """干净的业务化文案应通过安全检查。"""
    m7 = _m7_module()
    m4_result = _build_fake_m4_result(
        answer_summary="2025年组件事业部发货量合计为100.00000000 MW，覆盖1-12月。"
    )
    m6_result = _build_fake_m6_result()

    comparisons = m7.compare_m4_m6_results(m4_result=m4_result, m6_result=m6_result)
    safety_comp = [c for c in comparisons if c["dimension"] == "text_safety"][0]
    assert safety_comp["match"] is True


# ---------------------------------------------------------------------------
# 4. M4 正式链路不受干扰
# ---------------------------------------------------------------------------

def test_m7_runner_declares_shadow_only_and_formal_qa_not_executed() -> None:
    """M7 runner 必须声明 shadow_only=True 且 formal_qa_executed=False。"""
    m7 = _m7_module()
    runner = m7.InventorySalesProductionM7ShadowQaCompareRunner(
        m4_qa_callable=lambda q: _build_fake_m4_result(),
        m6_shadow_callable=lambda q: _build_fake_m6_result(),
    )
    assert runner.shadow_only is True
    assert runner.formal_qa_executed is False


# ---------------------------------------------------------------------------
# 5. 异常 fail-closed
# ---------------------------------------------------------------------------

def test_m7_compare_m4_error_fail_closed() -> None:
    """M4 执行异常时不应崩溃，应返回 fail-closed 对比记录。"""
    m7 = _m7_module()
    m4_result = _build_fake_m4_result(status="error", classification="D")
    m6_result = _build_fake_m6_result()

    comparisons = m7.compare_m4_m6_results(m4_result=m4_result, m6_result=m6_result)
    status_comp = [c for c in comparisons if c["dimension"] == "status_classification"][0]
    # M4 是 error/M6 是 matched，状态应不匹配
    assert status_comp["match"] is False


def test_m7_compare_m6_shadow_error_fail_closed() -> None:
    """M6 shadow 异常时不应崩溃，应返回 fail-closed 对比记录。"""
    m7 = _m7_module()
    m4_result = _build_fake_m4_result()
    m6_result = _build_fake_m6_result(status="shadow_error")

    comparisons = m7.compare_m4_m6_results(m4_result=m4_result, m6_result=m6_result)
    status_comp = [c for c in comparisons if c["dimension"] == "status_classification"][0]
    assert status_comp["match"] is False


# ---------------------------------------------------------------------------
# 6. 对比报告
# ---------------------------------------------------------------------------

def test_m7_run_generates_report_with_correct_structure(tmp_path: Path) -> None:
    """M7 runner 应生成结构化对比报告，包含总量、匹配数、不匹配数和详细记录。"""
    m7 = _m7_module()

    samples = [
        m7.InventorySalesProductionM7ShadowQaCompareSample(
            sample_id="m7_sample_001",
            question="2025年销量是多少？",
            question_category="sales_summary",
        ),
        m7.InventorySalesProductionM7ShadowQaCompareSample(
            sample_id="m7_sample_002",
            question="2025年存货是多少？",
            question_category="inventory_snapshot",
        ),
    ]

    def fake_m4(q: str) -> dict[str, Any]:
        if "销量" in q:
            return _build_fake_m4_result(metric_code="shipment_volume")
        return _build_fake_m4_result(metric_code="ending_inventory_volume", value=Decimal("50.0"))

    def fake_m6(q: str) -> dict[str, Any]:
        if "销量" in q:
            return _build_fake_m6_result(metrics=["shipment_volume"])
        return _build_fake_m6_result(metrics=["ending_inventory_volume"], value=Decimal("50.0"))

    runner = m7.InventorySalesProductionM7ShadowQaCompareRunner(
        m4_qa_callable=fake_m4,
        m6_shadow_callable=fake_m6,
    )
    result = runner.run(samples=samples, artifact_dir=tmp_path)

    assert result.report["total"] == 2
    assert result.report["matched_count"] == 2
    assert result.report["mismatch_count"] == 0
    assert len(result.records) == 2
    assert result.records_path.exists()
    assert result.report_path.exists()

    # 验证 records.jsonl 可解析
    lines = result.records_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    for line in lines:
        record = json.loads(line)
        assert "sample_id" in record
        assert "comparisons" in record
        assert len(record["comparisons"]) == 6


def test_m7_report_json_no_sensitive_leakage(tmp_path: Path) -> None:
    """对比报告 JSON 不应包含表名、SQL、密钥等内部信息。"""
    m7 = _m7_module()

    samples = [
        m7.InventorySalesProductionM7ShadowQaCompareSample(
            sample_id="m7_secure_001",
            question="2025年销量是多少？",
            question_category="sales_summary",
        ),
    ]

    runner = m7.InventorySalesProductionM7ShadowQaCompareRunner(
        m4_qa_callable=lambda q: _build_fake_m4_result(),
        m6_shadow_callable=lambda q: _build_fake_m6_result(),
    )
    result = runner.run(samples=samples, artifact_dir=tmp_path)

    report_text = result.report_path.read_text(encoding="utf-8").lower()
    for forbidden in ("dwd_ba_isp", "sql", "query_key", "planner", "api_key", "password", "token"):
        assert forbidden not in report_text, f"报告中不应包含 '{forbidden}'"


def test_m7_cli_safe_summary_renders_without_sensitive_data(tmp_path: Path) -> None:
    """CLI 安全摘要不应包含内部技术细节。"""
    m7 = _m7_module()

    samples = [
        m7.InventorySalesProductionM7ShadowQaCompareSample(
            sample_id="m7_cli_001",
            question="2025年销量是多少？",
            question_category="sales_summary",
        ),
    ]

    runner = m7.InventorySalesProductionM7ShadowQaCompareRunner(
        m4_qa_callable=lambda q: _build_fake_m4_result(),
        m6_shadow_callable=lambda q: _build_fake_m6_result(),
    )
    result = runner.run(samples=samples, artifact_dir=tmp_path)
    safe_json = m7.render_safe_m7_shadow_qa_compare_summary_json(result)
    lower = safe_json.lower()

    assert "m7" in lower or "shadow" in lower
    for forbidden in ("dwd_ba_isp", "sql", "query_key", "planner", "api_key", "password", "token"):
        assert forbidden not in lower, f"CLI 摘要中不应包含 '{forbidden}'"

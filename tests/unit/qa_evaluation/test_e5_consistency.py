"""NQE-E5 focused tests：评测结果一致性评估。

业务逻辑：
    验证 EvaluationReport + EvaluationResult 的一致性校验逻辑：
    - 状态匹配：expected_status vs actual_status。
    - 行数匹配：expected_row_count vs actual_row_count。
    - 数值误差百分比：回答中关键数字与预期的误差。
    - 技术泄露检测：leak_found 检查。
    - 分级：fail/pass/warning。

TDD 流程：RED → GREEN → REFACTOR。
"""

from __future__ import annotations

import pytest

from backend.app.domains.qa_evaluation.schema import (
    EvaluationReport,
    EvaluationResult,
)


# =============================================================================
# 辅助函数：构造基础 EvaluationReport（含若干结果）
# =============================================================================


def _make_report_with_results(
    *results: EvaluationResult,
    suite_name: str = "一致性评测套件",
) -> EvaluationReport:
    """构造包含给定结果的 EvaluationReport，自动计算 passed/failed 计数。"""
    passed = sum(1 for r in results if r.matched_status)
    failed = len(results) - passed
    return EvaluationReport(
        suite_name=suite_name,
        domain="logistics",
        total_cases=len(results),
        passed_cases=passed,
        failed_cases=failed,
        results=list(results),
    )


def _make_result(
    case_id: str = "case_001",
    matched_status: bool = True,
    key_numbers_match: bool | None = None,
    text_similarity: float | None = None,
    leak_found: bool = False,
    numeric_error_pct: float | None = None,
    **kwargs,
) -> EvaluationResult:
    """构造单条 EvaluationResult。"""
    return EvaluationResult(
        case_id=case_id,
        matched_status=matched_status,
        key_numbers_match=key_numbers_match,
        text_similarity=text_similarity,
        leak_found=leak_found,
        numeric_error_pct=numeric_error_pct,
        **kwargs,
    )


# =============================================================================
# RED 测试 1：EvaluationResult 新增字段 existence
# =============================================================================


def test_result_has_consistency_grade_field() -> None:
    """EvaluationResult 必须有 consistency_grade 字段（fail/pass/warning）。"""
    result = EvaluationResult(case_id="case_001", matched_status=True)
    # consistency_grade 应存在并有默认值
    d = result.model_dump(mode="json")
    assert "consistency_grade" in d, "EvaluationResult 缺少 consistency_grade 字段"
    assert d["consistency_grade"] == "pass"


def test_result_has_numeric_error_pct_field() -> None:
    """EvaluationResult 必须有 numeric_error_pct 字段（关键数值误差百分比）。"""
    result = EvaluationResult(
        case_id="case_001",
        matched_status=True,
        numeric_error_pct=0.05,
    )
    d = result.model_dump(mode="json")
    assert "numeric_error_pct" in d, "EvaluationResult 缺少 numeric_error_pct 字段"
    assert d["numeric_error_pct"] == 0.05


def test_result_numeric_error_pct_default() -> None:
    """numeric_error_pct 默认值为 None（未计算）。"""
    result = EvaluationResult(case_id="case_001", matched_status=True)
    assert result.numeric_error_pct is None


def test_result_consistency_grade_default() -> None:
    """consistency_grade 默认值为 "pass"。"""
    result = EvaluationResult(case_id="case_001", matched_status=True)
    assert result.consistency_grade == "pass"


# =============================================================================
# RED 测试 2：EvaluationReport.evaluate_consistency() 方法
# =============================================================================


def test_report_evaluate_consistency_exists() -> None:
    """EvaluationReport 必须有 evaluate_consistency() 方法。"""
    assert hasattr(EvaluationReport, "evaluate_consistency"), (
        "EvaluationReport 缺少 evaluate_consistency 方法"
    )
    assert callable(EvaluationReport.evaluate_consistency)


def test_evaluate_consistency_returns_self() -> None:
    """evaluate_consistency() 返回 self，支持链式调用。"""
    report = _make_report_with_results(
        _make_result("case_001", matched_status=True),
    )
    result_report = report.evaluate_consistency()
    assert result_report is report


def test_evaluate_consistency_does_not_change_counts() -> None:
    """evaluate_consistency() 不应改变 passed_cases/failed_cases 计数。"""
    r1 = _make_result("c1", matched_status=True)
    r2 = _make_result("c2", matched_status=False)
    report = _make_report_with_results(r1, r2)
    report.evaluate_consistency()
    assert report.passed_cases == 1
    assert report.failed_cases == 1


# =============================================================================
# RED 测试 3：一致性分级 —— fail/pass/warning
# =============================================================================


def test_consistency_pass_all_match() -> None:
    """全部匹配 → consistency_grade 为 "pass"。"""
    result = _make_result(
        "case_001",
        matched_status=True,
        key_numbers_match=True,
        text_similarity=0.95,
        leak_found=False,
    )
    report = _make_report_with_results(result)
    report.evaluate_consistency()
    assert report.results[0].consistency_grade == "pass"


def test_consistency_fail_on_leak() -> None:
    """技术泄露 → consistency_grade 为 "fail"，即使其他指标均匹配。"""
    result = _make_result(
        "case_001",
        matched_status=True,
        key_numbers_match=True,
        text_similarity=1.0,
        leak_found=True,
    )
    report = _make_report_with_results(result)
    report.evaluate_consistency()
    assert report.results[0].consistency_grade == "fail"


def test_consistency_fail_on_status_mismatch() -> None:
    """状态不匹配 → consistency_grade 为 "fail"。"""
    result = _make_result(
        "case_001",
        matched_status=False,
        key_numbers_match=None,
        leak_found=False,
        actual_status="clarification",
        mismatch_detail="状态不匹配：预期 success，实际 clarification",
    )
    report = _make_report_with_results(result)
    report.evaluate_consistency()
    assert report.results[0].consistency_grade == "fail"


def test_consistency_fail_on_row_count_mismatch() -> None:
    """行数不匹配（key_numbers_match=False）→ consistency_grade 为 "fail"。"""
    result = _make_result(
        "case_001",
        matched_status=True,  # 状态匹配，但行数不匹配
        key_numbers_match=False,
        leak_found=False,
        actual_row_count=3,
    )
    report = _make_report_with_results(result)
    report.evaluate_consistency()
    assert report.results[0].consistency_grade == "fail"


def test_consistency_warning_on_low_similarity() -> None:
    """文本相似度低于 0.5 → consistency_grade 为 "warning"。"""
    result = _make_result(
        "case_001",
        matched_status=True,
        key_numbers_match=True,
        text_similarity=0.30,
        leak_found=False,
    )
    report = _make_report_with_results(result)
    report.evaluate_consistency()
    assert report.results[0].consistency_grade == "warning"


def test_consistency_warning_on_high_numeric_error() -> None:
    """数值误差超过 10% → consistency_grade 为 "warning"。"""
    result = _make_result(
        "case_001",
        matched_status=True,
        key_numbers_match=True,
        leak_found=False,
        numeric_error_pct=0.15,
    )
    report = _make_report_with_results(result)
    report.evaluate_consistency()
    assert report.results[0].consistency_grade == "warning"


def test_consistency_warning_on_zero_similarity() -> None:
    """text_similarity=0.0 → consistency_grade 为 "warning"（无泄露且状态匹配时）。"""
    result = _make_result(
        "case_001",
        matched_status=True,
        key_numbers_match=None,
        text_similarity=0.0,
        leak_found=False,
    )
    report = _make_report_with_results(result)
    report.evaluate_consistency()
    assert report.results[0].consistency_grade == "warning"


def test_consistency_pass_with_good_similarity() -> None:
    """text_similarity >= 0.5 → consistency_grade 为 "pass"（无其他失败条件时）。"""
    result = _make_result(
        "case_001",
        matched_status=True,
        key_numbers_match=None,
        text_similarity=0.75,
        leak_found=False,
    )
    report = _make_report_with_results(result)
    report.evaluate_consistency()
    assert report.results[0].consistency_grade == "pass"


# =============================================================================
# RED 测试 4：fail 优先级 > warning
# =============================================================================


def test_fail_overrides_warning() -> None:
    """同时满足 fail 和 warning 条件时，应判定为 fail。"""
    result = _make_result(
        "case_001",
        matched_status=False,  # fail 条件
        text_similarity=0.10,  # warning 条件
        leak_found=False,
    )
    report = _make_report_with_results(result)
    report.evaluate_consistency()
    assert report.results[0].consistency_grade == "fail"


def test_fail_leak_overrides_warning_similarity() -> None:
    """技术泄露（fail）覆盖低相似度（warning）。"""
    result = _make_result(
        "case_001",
        matched_status=True,
        key_numbers_match=True,
        text_similarity=0.10,  # warning
        leak_found=True,  # fail
    )
    report = _make_report_with_results(result)
    report.evaluate_consistency()
    assert report.results[0].consistency_grade == "fail"


# =============================================================================
# RED 测试 5：warning 接近阈值边界
# =============================================================================


def test_consistency_warning_similarity_at_threshold() -> None:
    """text_similarity 恰好等于 0.5 时应为 pass（非 warning）。"""
    result = _make_result(
        "case_001",
        matched_status=True,
        key_numbers_match=None,
        text_similarity=0.50,
        leak_found=False,
    )
    report = _make_report_with_results(result)
    report.evaluate_consistency()
    assert report.results[0].consistency_grade == "pass"


def test_consistency_warning_numeric_error_at_threshold() -> None:
    """numeric_error_pct 恰好等于 0.10 时应为 pass（非 warning）。"""
    result = _make_result(
        "case_001",
        matched_status=True,
        key_numbers_match=None,
        leak_found=False,
        numeric_error_pct=0.10,
    )
    report = _make_report_with_results(result)
    report.evaluate_consistency()
    assert report.results[0].consistency_grade == "pass"


def test_consistency_warning_numeric_error_just_over() -> None:
    """numeric_error_pct=0.11 → 应判定为 warning。"""
    result = _make_result(
        "case_001",
        matched_status=True,
        key_numbers_match=None,
        leak_found=False,
        numeric_error_pct=0.11,
    )
    report = _make_report_with_results(result)
    report.evaluate_consistency()
    assert report.results[0].consistency_grade == "warning"


# =============================================================================
# RED 测试 6：多结果批量一致性评测
# =============================================================================


def test_multi_result_consistency_grading() -> None:
    """包含多条结果的报告应正确给每条结果分级。"""
    r1 = _make_result("c1", matched_status=True, key_numbers_match=True,
                      leak_found=False, text_similarity=0.9)
    r2 = _make_result("c2", matched_status=False, leak_found=False,
                      mismatch_detail="状态不匹配")
    r3 = _make_result("c3", matched_status=True, leak_found=True)
    r4 = _make_result("c4", matched_status=True, key_numbers_match=None,
                      text_similarity=0.3, leak_found=False)
    r5 = _make_result("c5", matched_status=True, key_numbers_match=True,
                      numeric_error_pct=0.15, leak_found=False)

    report = _make_report_with_results(r1, r2, r3, r4, r5)
    report.evaluate_consistency()

    assert report.results[0].consistency_grade == "pass"     # 全匹配
    assert report.results[1].consistency_grade == "fail"     # 状态不匹配
    assert report.results[2].consistency_grade == "fail"     # 泄露
    assert report.results[3].consistency_grade == "warning"  # 低相似度
    assert report.results[4].consistency_grade == "warning"  # 数值误差超标


# =============================================================================
# RED 测试 7：consistency_grade 可手动显式指定（不改默认行为）
# =============================================================================


def test_consistency_grade_explicit_set() -> None:
    """允许显式设置 consistency_grade，保留评测员手动覆盖能力。"""
    result = _make_result(
        "case_001",
        matched_status=True,
        consistency_grade="warning",
    )
    assert result.consistency_grade == "warning"


def test_evaluate_consistency_overwrites_grade() -> None:
    """evaluate_consistency() 应覆盖已有的 consistency_grade 值。"""
    result = _make_result(
        "case_001",
        matched_status=True,
        key_numbers_match=True,
        leak_found=False,
        consistency_grade="pass",
    )
    report = _make_report_with_results(result)
    report.evaluate_consistency()
    # 应保持为 pass（原始值正确）
    assert report.results[0].consistency_grade == "pass"

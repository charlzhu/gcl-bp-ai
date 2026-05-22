"""NQE-E6 评测门禁 focused tests（RED 阶段）。

业务逻辑：
    验证 CIGate 能根据 pass_rate 阈值（默认 90%）和技术泄露检测
    决定 CI 是否通过，返回明确的 exit code。
"""

from __future__ import annotations

import pytest
from backend.app.domains.qa_evaluation.schema import (
    EvaluationReport,
    EvaluationResult,
)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _make_result(
    case_id: str = "c001",
    matched_status: bool = True,
    key_numbers_match: bool | None = None,
    leak_found: bool = False,
    actual_status: str = "success",
    actual_answer_summary: str | None = "回答摘要",
    actual_row_count: int | None = 1,
    mismatch_detail: str | None = None,
    consistency_grade: str = "pass",
) -> EvaluationResult:
    """构造一条评测结果。"""
    return EvaluationResult(
        case_id=case_id,
        matched_status=matched_status,
        key_numbers_match=key_numbers_match,
        leak_found=leak_found,
        actual_status=actual_status,
        actual_answer_summary=actual_answer_summary,
        actual_row_count=actual_row_count,
        mismatch_detail=mismatch_detail,
        consistency_grade=consistency_grade,
    )


def _make_report(
    suite_name: str = "评测集",
    total_cases: int = 10,
    passed_cases: int = 9,
    failed_cases: int = 1,
    results: list[EvaluationResult] | None = None,
) -> EvaluationReport:
    """构造评测报告。"""
    if results is None:
        results = [
            _make_result(f"c{i:03d}") for i in range(passed_cases)
        ] + [
            _make_result(
                f"c{fail_i:03d}", matched_status=False,
                actual_status="clarification",
                mismatch_detail="状态不匹配",
                consistency_grade="fail",
            ) for fail_i in range(failed_cases)
        ]
    return EvaluationReport(
        suite_name=suite_name,
        domain="logistics",
        total_cases=total_cases,
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        results=results,
    )


# ===================================================================
# RED 测试：通过率门禁
# ===================================================================


class TestCIGatePassRate:
    """通过率门禁 test。"""

    def test_gate_passes_at_90_percent(self):
        """RED: pass_rate=90% 时门禁应通过。"""
        from backend.app.domains.qa_evaluation.ci_gate import CIGate

        report = _make_report(total_cases=10, passed_cases=9, failed_cases=1)
        gate = CIGate(pass_rate_threshold=0.90)
        result = gate.check(report)

        assert result.passed is True
        assert result.exit_code == 0

    def test_gate_passes_at_100_percent(self):
        """RED: pass_rate=100% 时门禁应通过。"""
        from backend.app.domains.qa_evaluation.ci_gate import CIGate

        report = _make_report(total_cases=10, passed_cases=10, failed_cases=0)
        gate = CIGate(pass_rate_threshold=0.90)
        result = gate.check(report)

        assert result.passed is True

    def test_gate_fails_at_89_percent(self):
        """RED: pass_rate=89% 时门禁应失败。"""
        from backend.app.domains.qa_evaluation.ci_gate import CIGate

        report = _make_report(total_cases=100, passed_cases=89, failed_cases=11)
        gate = CIGate(pass_rate_threshold=0.90)
        result = gate.check(report)

        assert result.passed is False
        assert result.exit_code == 1

    def test_gate_fails_at_50_percent(self):
        """RED: pass_rate=50% 时门禁应失败。"""
        from backend.app.domains.qa_evaluation.ci_gate import CIGate

        report = _make_report(total_cases=10, passed_cases=5, failed_cases=5)
        gate = CIGate(pass_rate_threshold=0.90)
        result = gate.check(report)

        assert result.passed is False

    def test_gate_passes_empty_suite(self):
        """RED: 空套件（0 条 case）门禁应通过。"""
        from backend.app.domains.qa_evaluation.ci_gate import CIGate

        report = _make_report(total_cases=0, passed_cases=0, failed_cases=0, results=[])
        gate = CIGate(pass_rate_threshold=0.90)
        result = gate.check(report)

        assert result.passed is True

    def test_custom_threshold(self):
        """RED: 自定义阈值为 80% 时，81% 通过。"""
        from backend.app.domains.qa_evaluation.ci_gate import CIGate

        report = _make_report(total_cases=100, passed_cases=81, failed_cases=19)
        gate = CIGate(pass_rate_threshold=0.80)
        result = gate.check(report)

        assert result.passed is True

    def test_custom_threshold_fails_below(self):
        """RED: 自定义阈值为 80% 时，79% 失败。"""
        from backend.app.domains.qa_evaluation.ci_gate import CIGate

        report = _make_report(total_cases=100, passed_cases=79, failed_cases=21)
        gate = CIGate(pass_rate_threshold=0.80)
        result = gate.check(report)

        assert result.passed is False


# ===================================================================
# RED 测试：技术泄露门禁
# ===================================================================


class TestCIGateLeakDetection:
    """技术泄露门禁 test。"""

    def test_gate_fails_when_leak_found(self):
        """RED: 发现技术泄露时门禁应失败，即使 pass_rate 达标。"""
        from backend.app.domains.qa_evaluation.ci_gate import CIGate

        results = [
            _make_result("c001"),
            _make_result("c002"),
            _make_result("c003", leak_found=True, matched_status=False,
                         mismatch_detail="检测到技术泄露", consistency_grade="fail"),
        ]
        report = _make_report(
            total_cases=3, passed_cases=2, failed_cases=1, results=results,
        )
        gate = CIGate(pass_rate_threshold=0.90)
        result = gate.check(report)

        assert result.passed is False
        assert result.exit_code == 1
        # 原因应包含泄露
        assert "泄露" in result.reason or "leak" in result.reason.lower()

    def test_gate_passes_no_leak(self):
        """RED: 无技术泄露且 pass_rate 达标时门禁应通过。"""
        from backend.app.domains.qa_evaluation.ci_gate import CIGate

        results = [
            _make_result("c001"),
            _make_result("c002"),
            _make_result("c003"),
        ]
        report = _make_report(
            total_cases=3, passed_cases=3, failed_cases=0, results=results,
        )
        gate = CIGate(pass_rate_threshold=0.90)
        result = gate.check(report)

        assert result.passed is True

    def test_multiple_leaks_still_one_failure(self):
        """RED: 多条泄露仍是门禁失败。"""
        from backend.app.domains.qa_evaluation.ci_gate import CIGate

        results = [
            _make_result("c001", leak_found=True, matched_status=False,
                         mismatch_detail="泄露1", consistency_grade="fail"),
            _make_result("c002", leak_found=True, matched_status=False,
                         mismatch_detail="泄露2", consistency_grade="fail"),
        ]
        report = _make_report(
            total_cases=2, passed_cases=0, failed_cases=2, results=results,
        )
        gate = CIGate(pass_rate_threshold=0.90)
        result = gate.check(report)

        assert result.passed is False

    def test_leak_but_pass_rate_ok_still_fails(self):
        """RED: 有泄露但 pass_rate 刚好 100% 也应该失败。"""
        from backend.app.domains.qa_evaluation.ci_gate import CIGate

        results = [
            _make_result("c001"),
            _make_result("c002"),
            _make_result("c003"),
            _make_result("c004"),
            _make_result("c005", leak_found=True, matched_status=False,
                         mismatch_detail="技术泄露", consistency_grade="fail"),
        ]
        report = _make_report(
            total_cases=5, passed_cases=4, failed_cases=1, results=results,
        )
        gate = CIGate(pass_rate_threshold=0.90)
        result = gate.check(report)

        # pass_rate = 80% 已经低于 90%，且泄露
        assert result.passed is False


# ===================================================================
# RED 测试：门禁结果结构
# ===================================================================


class TestCIGateResult:
    """门禁结果结构 test。"""

    def test_gate_result_has_pass_rate(self):
        """RED: 门禁结果应包含当前通过率。"""
        from backend.app.domains.qa_evaluation.ci_gate import CIGate

        report = _make_report(total_cases=10, passed_cases=7, failed_cases=3)
        gate = CIGate(pass_rate_threshold=0.90)
        result = gate.check(report)

        assert result.pass_rate == pytest.approx(0.70)

    def test_gate_result_has_total_cases(self):
        """RED: 门禁结果应包含总用例数。"""
        from backend.app.domains.qa_evaluation.ci_gate import CIGate

        report = _make_report(total_cases=42, passed_cases=38, failed_cases=4)
        gate = CIGate(pass_rate_threshold=0.90)
        result = gate.check(report)

        assert result.total_cases == 42

    def test_gate_result_has_leak_count(self):
        """RED: 门禁结果应包含泄露数量。"""
        from backend.app.domains.qa_evaluation.ci_gate import CIGate

        results = [
            _make_result("c001", leak_found=True, matched_status=False,
                         consistency_grade="fail"),
            _make_result("c002"),
            _make_result("c003", leak_found=True, matched_status=False,
                         consistency_grade="fail"),
        ]
        report = _make_report(
            total_cases=3, passed_cases=1, failed_cases=2, results=results,
        )
        gate = CIGate(pass_rate_threshold=0.90)
        result = gate.check(report)

        assert result.leak_count == 2

    def test_gate_result_has_reason(self):
        """RED: 门禁结果应包含失败原因字符串。"""
        from backend.app.domains.qa_evaluation.ci_gate import CIGate

        report = _make_report(total_cases=10, passed_cases=8, failed_cases=2)
        gate = CIGate(pass_rate_threshold=0.90)
        result = gate.check(report)

        assert isinstance(result.reason, str)
        assert len(result.reason) > 0


# ===================================================================
# RED 测试：多报告门禁
# ===================================================================


class TestCIGateMultipleReports:
    """多报告门禁 test。"""

    def test_gate_checks_multiple_reports(self):
        """RED: 门禁应能检查多个 EvaluationReport。"""
        from backend.app.domains.qa_evaluation.ci_gate import CIGate

        report1 = _make_report(
            suite_name="物流评测集", total_cases=5, passed_cases=5, failed_cases=0,
        )
        report2 = _make_report(
            suite_name="BOM评测集", total_cases=5, passed_cases=5, failed_cases=0,
        )
        gate = CIGate(pass_rate_threshold=0.90)
        result = gate.check_multiple([report1, report2])

        assert result.passed is True

    def test_gate_fails_if_any_report_fails(self):
        """RED: 多报告中任一失败门禁就失败。"""
        from backend.app.domains.qa_evaluation.ci_gate import CIGate

        report1 = _make_report(
            suite_name="物流评测集", total_cases=5, passed_cases=5, failed_cases=0,
        )
        report2 = _make_report(
            suite_name="BOM评测集", total_cases=5, passed_cases=2, failed_cases=3,
        )
        gate = CIGate(pass_rate_threshold=0.90)
        result = gate.check_multiple([report1, report2])

        assert result.passed is False

    def test_gate_multiple_aggregates_stats(self):
        """RED: 多报告门禁应汇总全部统计信息。"""
        from backend.app.domains.qa_evaluation.ci_gate import CIGate

        report1 = _make_report(
            suite_name="物流评测集", total_cases=5, passed_cases=5, failed_cases=0,
        )
        report2 = _make_report(
            suite_name="BOM评测集", total_cases=3, passed_cases=3, failed_cases=0,
        )
        gate = CIGate(pass_rate_threshold=0.90)
        result = gate.check_multiple([report1, report2])

        assert result.total_cases == 8

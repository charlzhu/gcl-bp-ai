"""NQE-E6 评测历史对比 focused tests（RED 阶段）。

业务逻辑：
    验证 EvalHistory 能对比当前评测报告与上次评测报告，
    识别新增失败、修复的 case、通过率变化趋势。
"""

from __future__ import annotations

import json
from pathlib import Path

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
    domain: str = "logistics",
    total_cases: int = 3,
    passed_cases: int = 3,
    failed_cases: int = 0,
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
        domain=domain,
        total_cases=total_cases,
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        results=results,
    )


# ===================================================================
# RED 测试：基本对比功能
# ===================================================================


class TestEvalHistoryCompare:
    """历史对比基本功能 test。"""

    def test_compare_detects_new_failures(self):
        """RED: 上次通过、本次失败的 case 应被识别为新增失败。"""
        from backend.app.domains.qa_evaluation.history import EvalHistory

        prev = _make_report(
            total_cases=3, passed_cases=3, failed_cases=0,
            results=[
                _make_result("c001"),
                _make_result("c002"),
                _make_result("c003"),
            ],
        )
        curr = _make_report(
            total_cases=3, passed_cases=2, failed_cases=1,
            results=[
                _make_result("c001"),
                _make_result("c002"),
                _make_result(
                    "c003", matched_status=False, actual_status="error",
                    mismatch_detail="执行异常", consistency_grade="fail",
                ),
            ],
        )
        history = EvalHistory()
        comparison = history.compare(previous=prev, current=curr)

        assert len(comparison.new_failures) == 1
        assert comparison.new_failures[0].case_id == "c003"

    def test_compare_detects_fixed_cases(self):
        """RED: 上次失败、本次通过的 case 应被识别为已修复。"""
        from backend.app.domains.qa_evaluation.history import EvalHistory

        prev = _make_report(
            total_cases=3, passed_cases=2, failed_cases=1,
            results=[
                _make_result("c001"),
                _make_result("c002"),
                _make_result(
                    "c003", matched_status=False, actual_status="error",
                    mismatch_detail="执行异常", consistency_grade="fail",
                ),
            ],
        )
        curr = _make_report(
            total_cases=3, passed_cases=3, failed_cases=0,
            results=[
                _make_result("c001"),
                _make_result("c002"),
                _make_result("c003"),
            ],
        )
        history = EvalHistory()
        comparison = history.compare(previous=prev, current=curr)

        assert len(comparison.fixed_cases) == 1
        assert comparison.fixed_cases[0].case_id == "c003"

    def test_compare_no_change(self):
        """RED: 全部一致时应无变化。"""
        from backend.app.domains.qa_evaluation.history import EvalHistory

        results = [
            _make_result("c001"),
            _make_result("c002"),
        ]
        prev = _make_report(
            total_cases=2, passed_cases=2, failed_cases=0, results=results,
        )
        curr = _make_report(
            total_cases=2, passed_cases=2, failed_cases=0, results=results,
        )
        history = EvalHistory()
        comparison = history.compare(previous=prev, current=curr)

        assert len(comparison.new_failures) == 0
        assert len(comparison.fixed_cases) == 0


# ===================================================================
# RED 测试：新增/删除 case
# ===================================================================


class TestEvalHistoryNewCases:
    """新增/删除 case test。"""

    def test_detects_newly_added_cases(self):
        """RED: 本次新增的 case（上次不存在）应被识别。"""
        from backend.app.domains.qa_evaluation.history import EvalHistory

        prev = _make_report(
            total_cases=2, passed_cases=2, failed_cases=0,
            results=[_make_result("c001"), _make_result("c002")],
        )
        curr = _make_report(
            total_cases=3, passed_cases=3, failed_cases=0,
            results=[
                _make_result("c001"),
                _make_result("c002"),
                _make_result("c003"),  # 新增
            ],
        )
        history = EvalHistory()
        comparison = history.compare(previous=prev, current=curr)

        assert len(comparison.new_cases) == 1
        assert comparison.new_cases[0].case_id == "c003"

    def test_detects_removed_cases(self):
        """RED: 本次移除的 case（上次存在本次没有）应被识别。"""
        from backend.app.domains.qa_evaluation.history import EvalHistory

        prev = _make_report(
            total_cases=3, passed_cases=3, failed_cases=0,
            results=[
                _make_result("c001"),
                _make_result("c002"),
                _make_result("c003"),
            ],
        )
        curr = _make_report(
            total_cases=2, passed_cases=2, failed_cases=0,
            results=[_make_result("c001"), _make_result("c002")],
        )
        history = EvalHistory()
        comparison = history.compare(previous=prev, current=curr)

        assert len(comparison.removed_cases) == 1
        assert comparison.removed_cases[0].case_id == "c003"

    def test_new_case_that_fails(self):
        """RED: 新增的 case 如果失败，应同时出现在新总用例和新增失败中。"""
        from backend.app.domains.qa_evaluation.history import EvalHistory

        prev = _make_report(
            total_cases=2, passed_cases=2, failed_cases=0,
            results=[_make_result("c001"), _make_result("c002")],
        )
        curr = _make_report(
            total_cases=3, passed_cases=2, failed_cases=1,
            results=[
                _make_result("c001"),
                _make_result("c002"),
                _make_result(
                    "c003", matched_status=False, actual_status="error",
                    mismatch_detail="新case失败", consistency_grade="fail",
                ),
            ],
        )
        history = EvalHistory()
        comparison = history.compare(previous=prev, current=curr)

        assert len(comparison.new_cases) == 1
        # 新增失败也应包含此 case
        assert any(f.case_id == "c003" for f in comparison.new_failures)


# ===================================================================
# RED 测试：通过率趋势
# ===================================================================


class TestEvalHistoryTrends:
    """通过率趋势 test。"""

    def test_trend_improved(self):
        """RED: 通过率上升时 trend 应为 improved。"""
        from backend.app.domains.qa_evaluation.history import EvalHistory

        prev = _make_report(total_cases=10, passed_cases=7, failed_cases=3)
        curr = _make_report(total_cases=10, passed_cases=9, failed_cases=1)
        history = EvalHistory()
        comparison = history.compare(previous=prev, current=curr)

        assert comparison.trend == "improved"

    def test_trend_degraded(self):
        """RED: 通过率下降时 trend 应为 degraded。"""
        from backend.app.domains.qa_evaluation.history import EvalHistory

        prev = _make_report(total_cases=10, passed_cases=9, failed_cases=1)
        curr = _make_report(total_cases=10, passed_cases=7, failed_cases=3)
        history = EvalHistory()
        comparison = history.compare(previous=prev, current=curr)

        assert comparison.trend == "degraded"

    def test_trend_stable(self):
        """RED: 通过率不变时 trend 应为 stable。"""
        from backend.app.domains.qa_evaluation.history import EvalHistory

        prev = _make_report(total_cases=10, passed_cases=8, failed_cases=2)
        curr = _make_report(total_cases=10, passed_cases=8, failed_cases=2)
        history = EvalHistory()
        comparison = history.compare(previous=prev, current=curr)

        assert comparison.trend == "stable"


# ===================================================================
# RED 测试：泄露对比
# ===================================================================


class TestEvalHistoryLeaks:
    """泄露对比 test。"""

    def test_new_leak_detected(self):
        """RED: 本次新出现的技术泄露应被识别。"""
        from backend.app.domains.qa_evaluation.history import EvalHistory

        prev = _make_report(
            total_cases=2, passed_cases=2, failed_cases=0,
            results=[_make_result("c001"), _make_result("c002")],
        )
        curr = _make_report(
            total_cases=2, passed_cases=1, failed_cases=1,
            results=[
                _make_result("c001"),
                _make_result(
                    "c002", leak_found=True, matched_status=False,
                    mismatch_detail="检测到技术泄露", consistency_grade="fail",
                ),
            ],
        )
        history = EvalHistory()
        comparison = history.compare(previous=prev, current=curr)

        assert len(comparison.new_leaks) == 1
        assert comparison.new_leaks[0].case_id == "c002"

    def test_leak_fixed(self):
        """RED: 上次有泄露本次已修复的 case 应被识别。"""
        from backend.app.domains.qa_evaluation.history import EvalHistory

        prev = _make_report(
            total_cases=2, passed_cases=1, failed_cases=1,
            results=[
                _make_result("c001"),
                _make_result(
                    "c002", leak_found=True, matched_status=False,
                    mismatch_detail="检测到技术泄露", consistency_grade="fail",
                ),
            ],
        )
        curr = _make_report(
            total_cases=2, passed_cases=2, failed_cases=0,
            results=[_make_result("c001"), _make_result("c002")],
        )
        history = EvalHistory()
        comparison = history.compare(previous=prev, current=curr)

        assert len(comparison.fixed_leaks) == 1
        assert comparison.fixed_leaks[0].case_id == "c002"


# ===================================================================
# RED 测试：历史持久化
# ===================================================================


class TestEvalHistoryPersistence:
    """历史持久化 test。"""

    def test_save_and_load_history(self, tmp_path):
        """RED: save_history() 保存后 load_history() 可还原。"""
        from backend.app.domains.qa_evaluation.history import EvalHistory

        report = _make_report(
            total_cases=3, passed_cases=3, failed_cases=0,
            results=[
                _make_result("c001"),
                _make_result("c002"),
                _make_result("c003"),
            ],
        )
        history = EvalHistory()
        history_path = tmp_path / "eval_history.json"
        history.save(report, str(history_path))

        assert history_path.exists()
        loaded = history.load(str(history_path))
        assert loaded is not None
        assert loaded.total_cases == 3
        assert loaded.pass_rate == pytest.approx(1.0)

    def test_load_nonexistent_history_returns_none(self, tmp_path):
        """RED: 加载不存在的历史文件应返回 None。"""
        from backend.app.domains.qa_evaluation.history import EvalHistory

        history = EvalHistory()
        loaded = history.load(str(tmp_path / "nonexistent.json"))
        assert loaded is None

    def test_save_overwrites_previous(self, tmp_path):
        """RED: save_history() 应覆盖上次文件。"""
        from backend.app.domains.qa_evaluation.history import EvalHistory

        report1 = _make_report(
            suite_name="首次评测", total_cases=3, passed_cases=3, failed_cases=0,
        )
        report2 = _make_report(
            suite_name="第二次评测", total_cases=5, passed_cases=4, failed_cases=1,
        )
        history = EvalHistory()
        history_path = tmp_path / "eval_history.json"

        history.save(report1, str(history_path))
        history.save(report2, str(history_path))

        loaded = history.load(str(history_path))
        assert loaded is not None
        assert loaded.total_cases == 5
        assert loaded.passed_cases == 4


# ===================================================================
# RED 测试：对比结果摘要
# ===================================================================


class TestEvalHistorySummary:
    """对比结果摘要 test。"""

    def test_comparison_has_summary_text(self):
        """RED: 对比结果应包含人类可读的摘要文本。"""
        from backend.app.domains.qa_evaluation.history import EvalHistory

        prev = _make_report(total_cases=10, passed_cases=9, failed_cases=1)
        curr = _make_report(total_cases=10, passed_cases=7, failed_cases=3)
        history = EvalHistory()
        comparison = history.compare(previous=prev, current=curr)

        assert isinstance(comparison.summary, str)
        assert len(comparison.summary) > 0

    def test_comparison_has_prev_pass_rate(self):
        """RED: 对比结果应包含上次通过率。"""
        from backend.app.domains.qa_evaluation.history import EvalHistory

        prev = _make_report(total_cases=10, passed_cases=8, failed_cases=2)
        curr = _make_report(total_cases=10, passed_cases=9, failed_cases=1)
        history = EvalHistory()
        comparison = history.compare(previous=prev, current=curr)

        assert comparison.prev_pass_rate == pytest.approx(0.80)

    def test_comparison_has_curr_pass_rate(self):
        """RED: 对比结果应包含本次通过率。"""
        from backend.app.domains.qa_evaluation.history import EvalHistory

        prev = _make_report(total_cases=10, passed_cases=8, failed_cases=2)
        curr = _make_report(total_cases=10, passed_cases=9, failed_cases=1)
        history = EvalHistory()
        comparison = history.compare(previous=prev, current=curr)

        assert comparison.curr_pass_rate == pytest.approx(0.90)

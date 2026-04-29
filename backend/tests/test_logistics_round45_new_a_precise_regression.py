from __future__ import annotations

from scripts.logistics_round45_new_a_precise_regression import (
    evaluate_round45_precise_regression,
)


def test_round45_new_a_precise_regression_passes() -> None:
    """验证 Round4 / Round5 新进 A 题精确断言回归当前全通过。"""
    report = evaluate_round45_precise_regression()
    assert report["summary"]["total_questions"] == 5
    assert report["summary"]["passed_questions"] == 5
    assert report["summary"]["failed_questions"] == 0

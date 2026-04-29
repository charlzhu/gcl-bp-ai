from __future__ import annotations

from scripts.logistics_a_stability_round2_regression import (
    evaluate_precise_regression,
)


def test_a_stability_round2_precise_regression_passes() -> None:
    """验证 A-稳定增强池 Round2 精确断言回归当前全通过。"""

    report = evaluate_precise_regression()
    assert report["summary"]["total_questions"] == 34
    assert report["summary"]["passed_questions"] == 34
    assert report["summary"]["failed_questions"] == 0

"""评测 CI 门禁（CIGate）。

业务逻辑：
    提供评测结果的 CI 门禁检查，根据 pass_rate 阈值（默认 90%）和
    技术泄露检测决定 CI 是否通过。

设计原则：
    1. 门禁 fail-closed：任一条件不满足即返回失败。
    2. 技术泄露是硬性阻断条件，与通过率独立。
    3. 支持自定义阈值和单/多套件检查。
    4. 门禁结果包含详细原因说明，可对接 CI/CD 流水线。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.domains.qa_evaluation.schema import EvaluationReport


# ---------------------------------------------------------------------------
# 门禁结果（中文注释）
# ---------------------------------------------------------------------------


@dataclass
class GateResult:
    """CI 门禁检查结果。

    参数：
        passed: 是否通过门禁。
        exit_code: 退出码（0=通过，1=失败）。
        reason: 失败原因描述（通过时为空字符串）。
        pass_rate: 本次评测通过率（0.0~1.0）。
        total_cases: 总用例数。
        leak_count: 技术泄露数量。
    """

    passed: bool
    exit_code: int
    reason: str = ""
    pass_rate: float = 1.0
    total_cases: int = 0
    leak_count: int = 0


# ---------------------------------------------------------------------------
# CI 门禁（中文注释）
# ---------------------------------------------------------------------------


class CIGate:
    """评测 CI 门禁。

    检查评测报告是否满足 CI 准入门槛，支持自定义通过率阈值。

    参数：
        pass_rate_threshold: 最低通过率阈值，默认 0.90（90%）。
    """

    def __init__(self, *, pass_rate_threshold: float = 0.90) -> None:
        """初始化门禁。

        参数：
            pass_rate_threshold: 最低通过率阈值，范围 0.0~1.0。
        """
        self._threshold = pass_rate_threshold

    # -------------------------------------------------------------------
    # 公共方法：单套件检查
    # -------------------------------------------------------------------

    def check(self, report: EvaluationReport) -> GateResult:
        """对单个 EvaluationReport 执行门禁检查。

        参数：
            report: 评测报告。
        返回：
            GateResult，包含通过/失败指示和详细原因。
        """
        leak_count = self._count_leaks(report)
        rate = report.pass_rate
        total = report.total_cases

        reasons: list[str] = []

        # 一、技术泄露检查（硬性阻断，优先级最高）
        if leak_count > 0:
            reasons.append(
                f"检测到 {leak_count} 条技术泄露（SQL/表名/字段名等），"
                f"必须修复后才能通过门禁"
            )
            return GateResult(
                passed=False,
                exit_code=1,
                reason="；".join(reasons),
                pass_rate=rate,
                total_cases=total,
                leak_count=leak_count,
            )

        # 二、通过率检查
        if total > 0 and rate < self._threshold:
            reasons.append(
                f"通过率 {rate:.1%} 低于阈值 {self._threshold:.0%}，"
                f"当前 {report.passed_cases}/{total} 通过"
            )

        if reasons:
            return GateResult(
                passed=False,
                exit_code=1,
                reason="；".join(reasons),
                pass_rate=rate,
                total_cases=total,
                leak_count=leak_count,
            )

        # 全部通过
        return GateResult(
            passed=True,
            exit_code=0,
            reason=f"通过率 {rate:.1%} >= {self._threshold:.0%}，"
            f"无技术泄露",
            pass_rate=rate,
            total_cases=total,
            leak_count=leak_count,
        )

    # -------------------------------------------------------------------
    # 公共方法：多套件检查
    # -------------------------------------------------------------------

    def check_multiple(self, reports: list[EvaluationReport]) -> GateResult:
        """对多个 EvaluationReport 执行门禁检查。

        参数：
            reports: 多个评测报告列表。
        返回：
            GateResult，汇总全部统计信息。
        业务逻辑：
            1. 汇总所有套件的统计信息。
            2. 检查全部泄露（任一报告有泄露即失败）。
            3. 计算总体通过率并检查阈值。
        """
        total_all = sum(r.total_cases for r in reports)
        passed_all = sum(r.passed_cases for r in reports)
        leak_all = sum(self._count_leaks(r) for r in reports)
        rate_all = passed_all / total_all if total_all > 0 else 1.0

        reasons: list[str] = []

        # 一、技术泄露（任一报告有泄露即失败）
        if leak_all > 0:
            reasons.append(
                f"检测到 {leak_all} 条技术泄露（SQL/表名/字段名等），"
                f"必须修复后才能通过门禁"
            )
            return GateResult(
                passed=False,
                exit_code=1,
                reason="；".join(reasons),
                pass_rate=rate_all,
                total_cases=total_all,
                leak_count=leak_all,
            )

        # 二、通过率检查
        if total_all > 0 and rate_all < self._threshold:
            reasons.append(
                f"总体通过率 {rate_all:.1%} 低于阈值 {self._threshold:.0%}，"
                f"当前 {passed_all}/{total_all} 通过"
            )

        if reasons:
            return GateResult(
                passed=False,
                exit_code=1,
                reason="；".join(reasons),
                pass_rate=rate_all,
                total_cases=total_all,
                leak_count=leak_all,
            )

        return GateResult(
            passed=True,
            exit_code=0,
            reason=f"总体通过率 {rate_all:.1%} >= {self._threshold:.0%}，"
            f"无技术泄露",
            pass_rate=rate_all,
            total_cases=total_all,
            leak_count=leak_all,
        )

    # -------------------------------------------------------------------
    # 内部方法
    # -------------------------------------------------------------------

    @staticmethod
    def _count_leaks(report: EvaluationReport) -> int:
        """统计报告中技术泄露的 case 数量。

        参数：
            report: 评测报告。
        返回：
            泄露数量。
        """
        return sum(1 for r in report.results if r.leak_found)

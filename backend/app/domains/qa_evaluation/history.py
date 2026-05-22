"""评测历史对比（EvalHistory）。

业务逻辑：
    提供评测报告的历史对比功能，支持：
    1. 当前 vs 上次评测的逐 case 对比。
    2. 识别新增失败、已修复 case、新增 case、删除 case。
    3. 识别新增/修复的技术泄露。
    4. 通过率趋势分析（improved/degraded/stable）。
    5. 评测报告持久化加载/保存。

设计原则：
    1. 对比基于 case_id 进行 case 级别匹配。
    2. 本次不存在的 case 视为"已删除"。
    3. 上次不存在的 case 视为"新增"。
    4. 趋势判断基于通过率变化方向。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from backend.app.domains.qa_evaluation.schema import (
    EvaluationReport,
    EvaluationResult,
)


# ---------------------------------------------------------------------------
# 对比结果（中文注释）
# ---------------------------------------------------------------------------


@dataclass
class HistoryComparison:
    """历史对比结果。

    参数：
        trend: 趋势方向（improved/degraded/stable）。
        prev_pass_rate: 上次通过率。
        curr_pass_rate: 本次通过率。
        new_failures: 新增失败 case 列表。
        fixed_cases: 已修复 case 列表。
        new_cases: 新增 case 列表。
        removed_cases: 已删除 case 列表。
        new_leaks: 新增泄露 case 列表。
        fixed_leaks: 已修复泄露 case 列表。
        summary: 人类可读的摘要文本。
    """

    trend: str = "stable"
    prev_pass_rate: float = 1.0
    curr_pass_rate: float = 1.0
    new_failures: list[EvaluationResult] = field(default_factory=list)
    fixed_cases: list[EvaluationResult] = field(default_factory=list)
    new_cases: list[EvaluationResult] = field(default_factory=list)
    removed_cases: list[EvaluationResult] = field(default_factory=list)
    new_leaks: list[EvaluationResult] = field(default_factory=list)
    fixed_leaks: list[EvaluationResult] = field(default_factory=list)
    summary: str = ""


# ---------------------------------------------------------------------------
# 历史对比（中文注释）
# ---------------------------------------------------------------------------


class EvalHistory:
    """评测历史管理器。

    提供评测报告的前后对比和历史持久化功能。
    """

    # -------------------------------------------------------------------
    # 公共方法：对比
    # -------------------------------------------------------------------

    def compare(
        self, *, previous: EvaluationReport, current: EvaluationReport,
    ) -> HistoryComparison:
        """对比当前与上次评测报告。

        参数：
            previous: 上次评测报告。
            current: 本次评测报告。
        返回：
            HistoryComparison，包含逐项对比结果和趋势分析。

        业务逻辑：
            1. 按 case_id 匹配两次的每条 case。
            2. 识别状态变化（pass→fail、fail→pass）。
            3. 识别泄露变化。
            4. 识别新增/删除 case。
            5. 计算通过率趋势。
            6. 生成人类可读摘要。
        """
        prev_map: dict[str, EvaluationResult] = {
            r.case_id: r for r in previous.results
        }
        curr_map: dict[str, EvaluationResult] = {
            r.case_id: r for r in current.results
        }

        # 新增失败（上次通过/不存在 → 本次失败）
        new_failures: list[EvaluationResult] = []
        # 已修复（上次失败 → 本次通过）
        fixed_cases: list[EvaluationResult] = []
        # 新增 case（上次不存在）
        new_cases: list[EvaluationResult] = []
        # 已删除 case（本次不存在）
        removed_cases: list[EvaluationResult] = []
        # 新增泄露
        new_leaks: list[EvaluationResult] = []
        # 已修复泄露
        fixed_leaks: list[EvaluationResult] = []

        for case_id, curr_result in curr_map.items():
            prev_result = prev_map.get(case_id)

            if prev_result is None:
                # 上一次不存在的 case → 新增
                new_cases.append(curr_result)
                if not curr_result.matched_status:
                    new_failures.append(curr_result)
                if curr_result.leak_found:
                    new_leaks.append(curr_result)
            else:
                # 已存在 case → 对比变化
                prev_pass = prev_result.matched_status
                curr_pass = curr_result.matched_status

                if prev_pass and not curr_pass:
                    new_failures.append(curr_result)
                elif not prev_pass and curr_pass:
                    fixed_cases.append(curr_result)

                # 泄露变化
                prev_leak = prev_result.leak_found
                curr_leak = curr_result.leak_found
                if not prev_leak and curr_leak:
                    new_leaks.append(curr_result)
                elif prev_leak and not curr_leak:
                    fixed_leaks.append(curr_result)

        # 已删除 case（上次存在 → 本次不存在）
        for case_id, prev_result in prev_map.items():
            if case_id not in curr_map:
                removed_cases.append(prev_result)

        # 趋势分析
        prev_rate = previous.pass_rate
        curr_rate = current.pass_rate
        if curr_rate > prev_rate:
            trend = "improved"
        elif curr_rate < prev_rate:
            trend = "degraded"
        else:
            trend = "stable"

        # 摘要文本
        summary = self._build_summary(
            trend=trend,
            prev_rate=prev_rate,
            curr_rate=curr_rate,
            new_failures=len(new_failures),
            fixed_cases=len(fixed_cases),
            new_cases=len(new_cases),
            removed_cases=len(removed_cases),
            new_leaks=len(new_leaks),
            fixed_leaks=len(fixed_leaks),
        )

        return HistoryComparison(
            trend=trend,
            prev_pass_rate=prev_rate,
            curr_pass_rate=curr_rate,
            new_failures=new_failures,
            fixed_cases=fixed_cases,
            new_cases=new_cases,
            removed_cases=removed_cases,
            new_leaks=new_leaks,
            fixed_leaks=fixed_leaks,
            summary=summary,
        )

    # -------------------------------------------------------------------
    # 公共方法：持久化
    # -------------------------------------------------------------------

    def save(self, report: EvaluationReport, path: str) -> None:
        """将评测报告保存为历史文件（JSON 格式）。

        参数：
            report: 评测报告。
            path: 保存路径，覆盖写入。
        """
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 使用 model_dump(mode="json") 确保序列化正确
        data = report.model_dump(mode="json")
        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load(self, path: str) -> EvaluationReport | None:
        """从历史文件加载评测报告。

        参数：
            path: 历史文件路径。
        返回：
            EvaluationReport 或 None（文件不存在或格式错误时）。

        业务逻辑：
            捕获 JSON 解析异常并返回 None，不中断上层流程。
        """
        file_path = Path(path)
        if not file_path.exists():
            return None

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            return EvaluationReport.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            # JSON 格式错误或 Schema 不匹配 → 返回 None
            return None

    # -------------------------------------------------------------------
    # 内部方法
    # -------------------------------------------------------------------

    @staticmethod
    def _build_summary(
        *,
        trend: str,
        prev_rate: float,
        curr_rate: float,
        new_failures: int,
        fixed_cases: int,
        new_cases: int,
        removed_cases: int,
        new_leaks: int,
        fixed_leaks: int,
    ) -> str:
        """生成人类可读的对比摘要文本。

        参数：
            trend: 趋势方向。
            prev_rate: 上次通过率。
            curr_rate: 本次通过率。
            new_failures: 新增失败数。
            fixed_cases: 已修复数。
            new_cases: 新增 case 数。
            removed_cases: 删除 case 数。
            new_leaks: 新增泄露数。
            fixed_leaks: 修复泄露数。
        返回：
            中文摘要文本。
        """
        trend_label = {
            "improved": "上升 ↑",
            "degraded": "下降 ↓",
            "stable": "持平 →",
        }.get(trend, trend)

        lines: list[str] = [
            f"通过率：{prev_rate:.1%} → {curr_rate:.1%}（{trend_label}）",
        ]

        parts: list[str] = []
        if new_failures > 0:
            parts.append(f"新增 {new_failures} 条失败")
        if fixed_cases > 0:
            parts.append(f"修复 {fixed_cases} 条")
        if new_cases > 0:
            parts.append(f"新增 {new_cases} 条用例")
        if removed_cases > 0:
            parts.append(f"移除 {removed_cases} 条用例")
        if new_leaks > 0:
            parts.append(f"新增 {new_leaks} 条技术泄露")
        if fixed_leaks > 0:
            parts.append(f"修复 {fixed_leaks} 条技术泄露")

        if parts:
            lines.append("；".join(parts))
        else:
            lines.append("无变化")

        return "\n".join(lines)

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.app.domains.logistics.services.nl2sql.m9_sqlplan_generation import (
    LogisticsNl2SqlM9ShadowReport,
)
from backend.app.domains.logistics.services.nl2sql.m10_shadow_gate_runner import (
    LogisticsNl2SqlM10ShadowGateRunReport,
)

M12_UNIFIED_REPORT_VERSION = "logistics_nl2sql_m12_unified_report.v1"


class LogisticsNl2SqlUnifiedReportRenderer(BaseModel):
    """物流 NL2SQL 统一全景评估报告渲染器。

    将 M9、M10、M11 各阶段的评估结果标准化为同一格式的全景报告。

    参数：
        m9_report: M9 SQLPlan 生成评估报告。
        m10_report: M10 shadow gate 评估报告。
        version: 渲染器版本。
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    m9_report: LogisticsNl2SqlM9ShadowReport | None = None
    m10_report: LogisticsNl2SqlM10ShadowGateRunReport | None = None
    version: str = M12_UNIFIED_REPORT_VERSION

    def render(self) -> str:
        """渲染统一全景 Markdown 报告。"""
        lines: list[str] = [
            "# 物流 NL2SQL 统一全景评估报告",
            "",
            f"- 版本: {self.version}",
            "",
            "## 总览",
            "",
            "| 阶段 | 总样本 | 通过 | 核心指标 |",
            "|------|--------|------|----------|",
        ]

        if self.m9_report:
            m9 = self.m9_report
            total = m9.total or 0
            ok = m9.success_count or 0
            rate = f"{ok * 100 // max(total, 1)}%"
            lines.append(
                f"| M9 SQLPlan 生成 | {total} | {ok} | 通过率 {rate} |"
            )

        if self.m10_report:
            m10 = self.m10_report
            total = m10.total or 0
            ok = m10.status_match_count or 0
            rate = f"{ok * 100 // max(total, 1)}%"
            lines.append(
                f"| M10 Shadow Gate | {total} | {ok} | 匹配率 {rate} |"
            )

        lines.append("")

        # ── M9 详情 ──
        if self.m9_report:
            m9 = self.m9_report
            lines.append("---")
            lines.append("")
            lines.append("## M9 SQLPlan 生成")
            lines.append("")
            lines.append(f"- 总样本: {m9.total}")
            lines.append(f"- 生成成功: {m9.generated_count}")
            lines.append(f"- 校验通过: {m9.validation_pass_count}")
            lines.append(f"- 校验失败: {m9.validation_failed_count}")
            lines.append(f"- 语义召回失败: {m9.recall_failed_count}")
            lines.append(f"- 候选 SQL gate 允许: {m9.candidate_sql_gate_allowed_count}")
            lines.append(f"- 候选 SQL gate 拒绝: {m9.candidate_sql_gate_rejected_count}")
            lines.append("")

        # ── M10 详情 ──
        if self.m10_report:
            m10 = self.m10_report
            lines.append("---")
            lines.append("")
            lines.append("## M10 Shadow Gate")
            lines.append("")
            lines.append(f"- 总样本: {m10.total}")
            lines.append(f"- 状态匹配: {m10.status_match_count}")
            lines.append(f"- 阶段匹配: {m10.stage_match_count}")
            if m10.by_expected_status:
                lines.append("")
                lines.append("### 期望状态分布")
                for key, value in sorted(m10.by_expected_status.items()):
                    lines.append(f"- {key}: {value}")
            if m10.by_actual_status:
                lines.append("")
                lines.append("### 实际状态分布")
                for key, value in sorted(m10.by_actual_status.items()):
                    lines.append(f"- {key}: {value}")
            if m10.by_category:
                lines.append("")
                lines.append("### 分类分布")
                for key, value in sorted(m10.by_category.items()):
                    lines.append(f"- {key}: {value}")
            lines.append("")

        return "\n".join(lines)


__all__ = [
    "M12_UNIFIED_REPORT_VERSION",
    "LogisticsNl2SqlUnifiedReportRenderer",
]

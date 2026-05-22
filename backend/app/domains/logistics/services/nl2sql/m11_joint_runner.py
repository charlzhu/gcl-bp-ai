from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domains.logistics.services.nl2sql.m9_sqlplan_generation import (
    LogisticsNl2SqlM9ShadowRun,
    LogisticsNl2SqlM9ShadowOutcome,
    build_default_logistics_nl2sql_m9_shadow_samples,
    run_logistics_nl2sql_m9_shadow_sqlplan_generation,
)
from backend.app.domains.logistics.services.nl2sql.m10_shadow_gate_runner import (
    LogisticsNl2SqlM10ShadowGateRunResult,
    build_default_logistics_nl2sql_m10_shadow_gate_samples,
    run_logistics_nl2sql_m10_shadow_gate,
)

M11_JOINT_RUNNER_VERSION = "logistics_nl2sql_m11_joint_runner.v1"
DEFAULT_M11_RECORDS_FILENAME = "m11-joint-shadow-records.jsonl"
DEFAULT_M11_REPORT_FILENAME = "m11-joint-shadow-report.md"


class LogisticsNl2SqlM11JointRunResult(BaseModel):
    """M11 联合 shadow runner 返回。

    参数：
        version: runner 版本标识。
        shadow_only: 是否仅 shadow 模式（始终为 True）。
        m9_result: M9 runner 的结果。
        m10_result: M10 runner 的结果。
        records_path: JSONL artifact 路径。
        report_path: Markdown artifact 路径。
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    version: str = M11_JOINT_RUNNER_VERSION
    shadow_only: bool = True
    m9_result: LogisticsNl2SqlM9ShadowRun
    m10_result: LogisticsNl2SqlM10ShadowGateRunResult
    records_path: Path
    report_path: Path

    def render_markdown(self) -> str:
        """渲染联合脱敏评估 Markdown 报表。"""
        m9 = self.m9_result
        m10 = self.m10_result

        lines = [
            "# M11 NL2SQL 联合 Shadow 评估报告",
            "",
            f"- version: {self.version}",
            f"- shadow_only: {self.shadow_only}",
            "",
            "## 总览",
            "",
            f"| 阶段 | 总样本 | 通过 | 失败 / 拦截 |",
            "|------|--------|------|-------------|",
            f"| M9 SQLPlan 生成 | {m9.report.total} | {m9.report.success_count} | {m9.report.validation_failed_count} |",
            f"| M10 Shadow Gate | {m10.report.total} | {m10.report.status_match_count} | {m10.report.total - m10.report.status_match_count} |",
            "",
            "---",
            "",
            m9.render_markdown(),
            "",
            "---",
            "",
            "## M10 Shadow Gate",
            "",
            f"- total: {m10.report.total}",
            f"- status_match_count: {m10.report.status_match_count}",
            f"- stage_match_count: {m10.report.stage_match_count}",
            f"- shadow_only: True",
            "",
            "### By Expected Status",
        ]
        for key, value in sorted(m10.report.by_expected_status.items()):
            lines.append(f"- {key}: {value}")
        if m10.report.by_actual_status:
            lines.append("")
            lines.append("### By Actual Status")
            for key, value in sorted(m10.report.by_actual_status.items()):
                lines.append(f"- {key}: {value}")
        if m10.report.by_category:
            lines.append("")
            lines.append("### By Category")
            for key, value in sorted(m10.report.by_category.items()):
                lines.append(f"- {key}: {value}")

        return "\n".join(lines)


def run_logistics_nl2sql_m11_joint_shadow(
    *,
    artifact_dir: str | Path | None = None,
) -> LogisticsNl2SqlM11JointRunResult:
    """运行 M9 + M10 联合 shadow 评估。

    业务逻辑：
        1. 分别跑 M9 和 M10 的默认样例集（离线模式，不连接真实 provider 或 DB）。
        2. 将两个结果合并为统一脱敏报告。
        3. 写出 JSONL 和 Markdown artifact。

    参数：
        artifact_dir: artifact 输出目录；缺省使用默认联合评估目录。

    返回：
        联合评估结果，不包含 SQL 原文、参数值、表名或字段名。
    """
    artifact_path = Path(artifact_dir or "ai/outbox/kanban/t_940b9b58")
    artifact_path.mkdir(parents=True, exist_ok=True)
    records_path = artifact_path / DEFAULT_M11_RECORDS_FILENAME
    report_path = artifact_path / DEFAULT_M11_REPORT_FILENAME

    # 1. 跑 M9 （离线模式，不带 live provider smoke）
    m9_result = run_logistics_nl2sql_m9_shadow_sqlplan_generation(
        live_provider_smoke=False,
    )

    # 2. 跑 M10
    m10_result = run_logistics_nl2sql_m10_shadow_gate()

    # 3. 构造联合结果
    result = LogisticsNl2SqlM11JointRunResult(
        m9_result=m9_result,
        m10_result=m10_result,
        records_path=records_path,
        report_path=report_path,
    )

    # 4. 写出 artifact
    records_path.write_text(
        json.dumps(
            {
                "version": result.version,
                "shadow_only": result.shadow_only,
                "m9_result": m9_result.model_dump(mode="json"),
                "m10_result": m10_result.model_dump(mode="json"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    )
    report_path.write_text(result.render_markdown())

    return result


__all__ = [
    "M11_JOINT_RUNNER_VERSION",
    "LogisticsNl2SqlM11JointRunResult",
    "run_logistics_nl2sql_m11_joint_shadow",
]

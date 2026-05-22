#!/usr/bin/env python
"""M11-3：M9+M10 联合 Shadow Runner focused tests。

目标：
    验证 M11JointShadowRunner 能分别跑 M9 和 M10 的默认样例集，
    并产生联合脱敏评估报告。
"""

from __future__ import annotations

from pathlib import Path

from backend.app.domains.logistics.services.nl2sql.m11_joint_runner import (
    M11_JOINT_RUNNER_VERSION,
    LogisticsNl2SqlM11JointRunResult,
    run_logistics_nl2sql_m11_joint_shadow,
)


def test_joint_runner_runs_default_samples() -> None:
    """联合 runner 应能跑完 M9 + M10 的所有默认样本不抛异常。"""
    result = run_logistics_nl2sql_m11_joint_shadow()
    assert isinstance(result, LogisticsNl2SqlM11JointRunResult)
    assert result.version == M11_JOINT_RUNNER_VERSION
    assert result.shadow_only is True
    assert result.m9_result is not None
    assert result.m10_result is not None
    assert result.m9_result.report.total >= 3  # M9 默认 3 个样本
    assert result.m10_result.report.total >= 12  # M10 默认 ≥12 个样本


def test_joint_runner_report_contains_both_summaries() -> None:
    """联合报表应包含 M9 和 M10 的两部分汇总。"""
    result = run_logistics_nl2sql_m11_joint_shadow()
    markdown = result.render_markdown()
    assert "M9 NL2SQL Shadow SQLPlan Generation" in markdown
    assert "M10 Shadow Gate" in markdown
    assert "总览" in markdown
    assert "total: 17" in markdown
    # M10 样本数随新增样例变化，使用动态断言
    assert "M10 Shadow Gate" in markdown
    assert "total:" in markdown
    assert "status_match_count:" in markdown


def test_joint_runner_writes_artifacts(tmp_path: Path) -> None:
    """给定 artifact_dir 时应写出 JSONL 和 Markdown。"""
    result = run_logistics_nl2sql_m11_joint_shadow(artifact_dir=str(tmp_path))
    assert result.records_path is not None
    assert result.report_path is not None
    assert result.records_path.exists()
    assert result.report_path.exists()
    # 验证 JSONL 包含 M9 和 M10 两部分
    content = result.records_path.read_text()
    assert "m9_result" in content
    assert "m10_result" in content


def test_joint_runner_final_report_markdown_is_desensitized() -> None:
    """联合报表应脱敏，不输出 SQL 原文、表名、字段名。"""
    result = run_logistics_nl2sql_m11_joint_shadow()
    markdown = result.render_markdown()
    assert "dws_logistics_detail_union" not in markdown
    assert "shipment_mw" not in markdown

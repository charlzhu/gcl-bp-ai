#!/usr/bin/env python
"""M12-1：统一评估报告 focused tests。

目标：
    验证 LogisticsNl2SqlUnifiedReportRenderer 能将 M9、M10、M11
    各阶段评估结果标准化为统一的全景报告格式。
"""

from __future__ import annotations

from backend.app.domains.logistics.services.nl2sql.m12_unified_report import (
    LogisticsNl2SqlUnifiedReportRenderer,
    M12_UNIFIED_REPORT_VERSION,
)
from backend.app.domains.logistics.services.nl2sql.m9_sqlplan_generation import (
    LogisticsNl2SqlM9ShadowReport,
    LogisticsNl2SqlM9ShadowRun,
)
from backend.app.domains.logistics.services.nl2sql.m10_shadow_gate_runner import (
    LogisticsNl2SqlM10ShadowGateRunReport,
    LogisticsNl2SqlM10ShadowGateRunResult,
)


def _fake_m9_report() -> LogisticsNl2SqlM9ShadowReport:
    """构造 M9 假报告。"""
    return LogisticsNl2SqlM9ShadowReport(
        total=3,
        success_count=1,
        recall_failed_count=1,
        generated_count=1,
        validation_pass_count=1,
        validation_failed_count=1,
        candidate_sql_gate_allowed_count=1,
        candidate_sql_gate_rejected_count=0,
    )


def _fake_m10_report() -> LogisticsNl2SqlM10ShadowGateRunReport:
    """构造 M10 假报告。"""
    return LogisticsNl2SqlM10ShadowGateRunReport(
        total=13,
        status_match_count=10,
        stage_match_count=9,
        by_expected_status={"success": 3, "failed": 10},
        by_actual_status={"success": 1, "skipped": 12},
        by_category={"success": 3, "guard": 3, "edge": 2, "safety": 5},
    )


# ── 基本渲染 ──────────────────────────────────────────────


def test_renderer_accepts_m9_and_m10_reports() -> None:
    """渲染器应能同时接收 M9 和 M10 的报告并输出 Markdown。"""
    m9r = _fake_m9_report()
    m10r = _fake_m10_report()
    renderer = LogisticsNl2SqlUnifiedReportRenderer(
        m9_report=m9r,
        m10_report=m10r,
    )
    md = renderer.render()
    assert isinstance(md, str)
    assert len(md) > 50
    assert "全景评估报告" in md

def test_renderer_contains_all_three_sections() -> None:
    """统一报告应包含总览、M9 摘要、M10 摘要三个部分。"""
    renderer = LogisticsNl2SqlUnifiedReportRenderer(
        m9_report=_fake_m9_report(),
        m10_report=_fake_m10_report(),
    )
    md = renderer.render()
    assert "## 总览" in md
    assert "## M9" in md
    assert "## M10" in md


def test_renderer_shows_correct_metrics() -> None:
    """渲染结果应正确显示各阶段核心指标。"""
    renderer = LogisticsNl2SqlUnifiedReportRenderer(
        m9_report=_fake_m9_report(),
        m10_report=_fake_m10_report(),
    )
    md = renderer.render()
    assert "3" in md  # total
    assert "1" in md  # success_count
    assert "13" in md  # m10 total
    assert "10" in md  # status_match_count


def test_renderer_includes_unified_summary_table() -> None:
    """统一报告应有一张汇总表对比各阶段核心指标。"""
    renderer = LogisticsNl2SqlUnifiedReportRenderer(
        m9_report=_fake_m9_report(),
        m10_report=_fake_m10_report(),
    )
    md = renderer.render()
    assert "阶段" in md
    assert "|" in md
    assert "通过率" in md


# ── 脱敏 ──────────────────────────────────────────────────


def test_renderer_never_exposes_sql_or_table_names() -> None:
    """统一报告不输出 SQL 原文、表名、字段名。"""
    renderer = LogisticsNl2SqlUnifiedReportRenderer(
        m9_report=_fake_m9_report(),
        m10_report=_fake_m10_report(),
    )
    md = renderer.render()
    assert "dws_logistics_detail_union" not in md
    assert "shipment_mw" not in md
    assert "SELECT" not in md


# ── 空报告处理 ──────────────────────────────────────────────


def test_renderer_handles_empty_m9_report() -> None:
    """空 M9 报告不抛出异常。"""
    empty = LogisticsNl2SqlM9ShadowReport()
    renderer = LogisticsNl2SqlUnifiedReportRenderer(
        m9_report=empty,
        m10_report=_fake_m10_report(),
    )
    md = renderer.render()
    assert md


def test_renderer_handles_minimal_m10_report() -> None:
    """最小 M10 报告不抛出异常。"""
    minimal = LogisticsNl2SqlM10ShadowGateRunReport(
        total=0,
        status_match_count=0,
        stage_match_count=0,
        by_expected_status={},
        by_actual_status={},
        by_category={},
    )
    renderer = LogisticsNl2SqlUnifiedReportRenderer(
        m9_report=_fake_m9_report(),
        m10_report=minimal,
    )
    md = renderer.render()
    assert md

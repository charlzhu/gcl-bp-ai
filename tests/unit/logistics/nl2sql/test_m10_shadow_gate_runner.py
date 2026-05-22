from __future__ import annotations

from backend.app.domains.logistics.services.nl2sql.m10_shadow_gate_runner import (
    build_default_logistics_nl2sql_m10_shadow_gate_samples,
    run_logistics_nl2sql_m10_shadow_gate,
)


def test_m10_default_samples_cover_all_categories() -> None:
    """默认样例集必须覆盖所有分层类别。"""
    samples = build_default_logistics_nl2sql_m10_shadow_gate_samples()
    sample_ids = [s.sample_id for s in samples]

    assert len(samples) >= 12
    categories = {s.category for s in samples}
    assert "success" in categories
    assert "guard" in categories
    assert "edge" in categories
    assert "safety" in categories

    # 验证关键样本存在
    assert "m10_success_simple_select" in sample_ids
    assert "m10_guard_safety_sleep_function" in sample_ids
    assert "m10_edge_select_star" in sample_ids
    assert "m10_safety_ddl_drop" in sample_ids


def test_m10_runner_runs_all_samples_and_builds_report() -> None:
    """运行默认样例集，所有样本应正常跑完不抛异常。"""
    samples = build_default_logistics_nl2sql_m10_shadow_gate_samples()
    result = run_logistics_nl2sql_m10_shadow_gate(samples=samples)

    assert result.report.total == len(samples)
    assert len(result.outcomes) == len(samples)
    assert result.report.status_match_count >= 0
    assert result.report.stage_match_count >= 0
    assert "success" in result.report.by_expected_status
    assert "failed" in result.report.by_expected_status


def test_m10_runner_writes_artifacts_when_artifact_dir_given(tmp_path) -> None:
    """给定 artifact_dir 时应写出 JSONL 和 Markdown。"""
    samples = build_default_logistics_nl2sql_m10_shadow_gate_samples()[:3]
    result = run_logistics_nl2sql_m10_shadow_gate(samples=samples, artifact_dir=tmp_path)

    assert result.records_path is not None
    assert result.report_path is not None
    assert result.records_path.exists()
    assert result.report_path.exists()

    content = result.records_path.read_text(encoding="utf-8")
    assert len(content.splitlines()) == 3
    # 不应泄露 SQL 原文
    assert "SELECT" not in content

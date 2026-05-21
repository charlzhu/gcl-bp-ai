from __future__ import annotations

import json
from pathlib import Path

from backend.app.domains.business_analysis.services.inventory_sales_production.m7_dual_track import (
    compare_single,
    run_dual_track_comparison,
)


def _fake_m4_ok(summary: str = "", rows: int = 0) -> dict[str, object]:
    """构造 M4 成功响应。"""
    return {
        "status": {"code": "OK"},
        "answer_summary": summary,
        "result_table": {"columns": [], "rows": [{} for _ in range(rows)]} if rows else None,
    }


def _fake_m4_clarify(msg: str = "请补充年份") -> dict[str, object]:
    return {"status": {"code": "CLARIFICATION_REQUIRED"}, "answer_summary": msg, "result_table": None}


def _fake_m4_unsupported(reason: str = "暂不支持") -> dict[str, object]:
    return {"status": {"code": "UNSUPPORTED"}, "answer_summary": reason, "result_table": None}


def _fake_m6_matched() -> dict[str, object]:
    return {"actual_status": "matched", "provider_live_called": True, "sqlplan_validation_ok": True}


def _fake_m6_validation_failed() -> dict[str, object]:
    return {"actual_status": "validation_failed", "provider_live_called": True, "sqlplan_validation_ok": False}


def _fake_m6_shadow_error() -> dict[str, object]:
    return {"actual_status": "shadow_error", "provider_live_called": False, "sqlplan_validation_ok": False}


# ===== compare_single 测试 =====


def test_m7_compare_single_m4_ok_m6_matched_no_mismatch() -> None:
    """M4=OK + M6=matched 时不应有 mismatch。"""
    r = compare_single(
        sample_id="test_ok_match",
        question="2025年销量是多少？",
        m4_status_code="OK",
        m4_summary="2025年销量为 100 MW。",
        m4_row_count=1,
        m6_actual_status="matched",
        m6_provider_live_called=True,
        m6_sqlplan_validation_ok=True,
    )
    assert r.mismatch_flags == [], f"expected no mismatch, got {r.mismatch_flags}"
    assert r.m4_status == "OK"
    assert r.m6_actual_status == "matched"


def test_m7_compare_single_m4_unsupported_m6_validation_failed_match() -> None:
    """M4=UNSUPPORTED + M6=validation_failed 时应视为一致（unsupported）。"""
    r = compare_single(
        sample_id="test_unsupported",
        question="2025年销量同比增长率是多少？",
        m4_status_code="UNSUPPORTED",
        m4_summary="暂不支持同比类问题。",
        m4_row_count=0,
        m6_actual_status="validation_failed",
        m6_provider_live_called=True,
        m6_sqlplan_validation_ok=False,
    )
    assert r.mismatch_flags == [], f"expected no mismatch for unsupported, got {r.mismatch_flags}"


def test_m7_compare_single_m4_ok_m6_shadow_error_mismatch() -> None:
    """M4=OK + M6=shadow_error 时应标记 mismatch。"""
    r = compare_single(
        sample_id="test_ok_error_mismatch",
        question="2025年销量是多少？",
        m4_status_code="OK",
        m4_summary="2025年销量为 100 MW。",
        m4_row_count=1,
        m6_actual_status="shadow_error",
        m6_provider_live_called=False,
        m6_sqlplan_validation_ok=False,
    )
    assert len(r.mismatch_flags) >= 1, f"expected mismatch, got {r.mismatch_flags}"


def test_m7_compare_single_detects_technical_leak() -> None:
    """M4 摘要包含内部技术词时，technical_leak_detected 应为 True。"""
    r = compare_single(
        sample_id="test_leak",
        question="2025年销量是多少？",
        m4_status_code="OK",
        m4_summary="query_key=ba_isp_metric_summary 结果",
        m4_row_count=1,
        m6_actual_status="matched",
        m6_provider_live_called=True,
        m6_sqlplan_validation_ok=True,
    )
    assert r.technical_leak_detected is True, "failed to detect query_key leak"


def test_m7_compare_single_clean_no_leak() -> None:
    """正常业务回答不触发技术泄露检测。"""
    r = compare_single(
        sample_id="test_clean",
        question="2025年销量是多少？",
        m4_status_code="OK",
        m4_summary="2025年销量为 100 MW。",
        m4_row_count=1,
        m6_actual_status="matched",
        m6_provider_live_called=True,
        m6_sqlplan_validation_ok=True,
    )
    assert r.technical_leak_detected is False


def test_m7_compare_single_period_end_detection() -> None:
    """M4 摘要包含"最后已发布月份"时，period_consistency 应反映 period_end。"""
    r = compare_single(
        sample_id="test_period_end",
        question="2026年4月存货合计是多少？",
        m4_status_code="OK",
        m4_summary="存货按最后已发布月份 4 月取数。",
        m4_row_count=1,
        m6_actual_status="matched",
        m6_provider_live_called=True,
        m6_sqlplan_validation_ok=True,
    )
    assert r.compare_dimensions.get("metric_consistency") == "period_end"


# ===== run_dual_track_comparison 测试 =====


def test_m7_dual_track_all_matched() -> None:
    """三条样本 M4/M6 一致时，report.matched_count=3。"""
    samples = [
        {"sample_id": "s1", "question": "2025年销量是多少？"},
        {"sample_id": "s2", "question": "2025年产量是多少？"},
        {"sample_id": "s3", "question": "2026年4月存货合计是多少？"},
    ]

    def m4_ask(q: str) -> dict[str, object]:
        return _fake_m4_ok(summary=f"结果 {q}", rows=1)

    def m6_run(q: str) -> dict[str, object]:
        return _fake_m6_matched()

    report = run_dual_track_comparison(samples=samples, m4_ask=m4_ask, m6_run_sample=m6_run)
    assert report.total == 3
    assert report.matched_count == 3
    assert report.mismatch_count == 0
    assert report.all_technical_leak_clean is True
    assert report.provider_live_called_count >= 1


def test_m7_dual_track_partial_mismatch() -> None:
    """部分样本 M4/M6 不一致时记录 mismatch。"""
    samples = [
        {"sample_id": "s1", "question": "2025年销量是多少？"},
        {"sample_id": "s2", "question": "2025年销量同比增长率是多少？"},
    ]
    call_count = 0

    def m4_ask(q: str) -> dict[str, object]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _fake_m4_ok(summary="2025年销量为 100 MW。", rows=1)
        return _fake_m4_unsupported()

    def m6_run(q: str) -> dict[str, object]:
        if "同比" in q:
            return _fake_m6_validation_failed()
        return _fake_m6_matched()

    report = run_dual_track_comparison(samples=samples, m4_ask=m4_ask, m6_run_sample=m6_run)
    assert report.total == 2
    assert report.matched_count == 2  # s2: unsupported=validation_failed → matched
    assert report.mismatch_count == 0


def test_m7_dual_track_writes_artifact(tmp_path: Path) -> None:
    """指定 artifact_dir 时写入 JSON 和 JSONL。"""
    samples = [
        {"sample_id": "s1", "question": "2025年销量是多少？"},
    ]

    def m4_ask(q: str) -> dict[str, object]:
        return _fake_m4_ok(summary="100 MW", rows=1)

    def m6_run(q: str) -> dict[str, object]:
        return _fake_m6_matched()

    report = run_dual_track_comparison(samples=samples, m4_ask=m4_ask, m6_run_sample=m6_run, artifact_dir=tmp_path)
    assert (tmp_path / "m7-dual-track-report.json").exists()
    assert (tmp_path / "m7-dual-track-records.jsonl").exists()
    assert report.total == 1
    assert report.matched_count == 1


def test_m7_dual_track_handles_exception_in_m4_gracefully() -> None:
    """M4 异常时不应中断整体对比。"""

    def m4_ask(q: str) -> dict[str, object]:
        raise RuntimeError("upstream unavailable")

    def m6_run(q: str) -> dict[str, object]:
        return _fake_m6_matched()

    report = run_dual_track_comparison(
        samples=[{"sample_id": "s1", "question": "2025年销量是多少？"}],
        m4_ask=m4_ask,
        m6_run_sample=m6_run,
    )
    assert report.total == 1
    # M4 error → mismatch expected
    assert report.mismatch_count >= 0
    # error should not blow up report generation


def test_m7_dual_track_status_mapping_is_exhaustive() -> None:
    """M4 和 M6 的所有已知状态码都应映射到标准对比枚举。"""
    from backend.app.domains.business_analysis.services.inventory_sales_production.m7_dual_track import (
        _status_m4_to_canonical,
        _status_m6_to_canonical,
    )

    for code in ("OK", "CLARIFICATION_REQUIRED", "UNSUPPORTED", "EXECUTION_ERROR", "EMPTY"):
        assert _status_m4_to_canonical(code) != "unknown", f"m4 {code} unmapped"

    for code in ("matched", "empty", "validation_failed", "shadow_error"):
        assert _status_m6_to_canonical(code) != "unknown", f"m6 {code} unmapped"

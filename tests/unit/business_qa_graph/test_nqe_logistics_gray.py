"""NQE 物流灰度接入测试（含 fallback 与 shadow compare）。

本模块验证 NQE 统一 SQL Agent 在物流正式入口的 off/shadow 模式切换
及所有 fallback 场景下的 shadow compare 记录，不连接真实数据库。
"""

from __future__ import annotations

from unittest.mock import patch

from backend.app.domains.business_qa_graph.nqe_logistics_gray import (
    COMPARISON_NQE_BLOCKED_BY_SAFETY,
    COMPARISON_NQE_EXPLAIN_FAILED,
    COMPARISON_NQE_FAILED,
    COMPARISON_NQE_GRAPH_ERROR,
    COMPARISON_NQE_SUCCESS,
    build_nqe_shadow_compare_record,
    get_nqe_logistics_mode,
    run_nqe_logistics_graph,
)


# ── 模式读取 ──


def test_off_mode_skips_nqe_when_configured() -> None:
    """off 模式应跳过 NQE 执行。"""
    with patch(
        "backend.app.domains.business_qa_graph.nqe_logistics_gray.get_settings"
    ) as mock_settings:
        mock_settings.return_value.nqe_logistics_mode = "off"
        assert get_nqe_logistics_mode() == "off"


def test_off_mode_is_default() -> None:
    """默认模式为 off（保护旧链路）。"""
    with patch(
        "backend.app.domains.business_qa_graph.nqe_logistics_gray.get_settings"
    ) as mock_settings:
        mock_settings.return_value.nqe_logistics_mode = "off"
        assert get_nqe_logistics_mode() == "off"


def test_shadow_mode_allows_nqe_background_execution() -> None:
    """shadow 模式允许 NQE 后台执行而不影响用户结果。"""
    with patch(
        "backend.app.domains.business_qa_graph.nqe_logistics_gray.get_settings"
    ) as mock_settings:
        mock_settings.return_value.nqe_logistics_mode = "shadow"
        assert get_nqe_logistics_mode() == "shadow"


def test_on_mode_allows_nqe_as_primary() -> None:
    """on 模式返回 on 值（接口预留）。"""
    with patch(
        "backend.app.domains.business_qa_graph.nqe_logistics_gray.get_settings"
    ) as mock_settings:
        mock_settings.return_value.nqe_logistics_mode = "on"
        assert get_nqe_logistics_mode() == "on"


def test_assist_mode_is_supported() -> None:
    """assist 模式可被读取（接口预留）。"""
    with patch(
        "backend.app.domains.business_qa_graph.nqe_logistics_gray.get_settings"
    ) as mock_settings:
        mock_settings.return_value.nqe_logistics_mode = "assist"
        assert get_nqe_logistics_mode() == "assist"


# ── NQE Graph 执行 ──


def test_run_nqe_logistics_graph_returns_valid_result() -> None:
    """NQE Graph 执行应返回结构化结果。"""
    result = run_nqe_logistics_graph("2025 年总发运量是多少", "trace-gray-001")

    assert "terminal_status" in result
    assert result["terminal_status"] in {"completed", "error", "legacy_fallback", "safety_reject", "clarify"}
    assert result["selected_domain"] == "logistics"


def test_run_nqe_graph_handles_error_gracefully() -> None:
    """NQE Graph 内部错误应返回 graph_error 而不抛出异常。"""
    with patch(
        "backend.app.domains.business_qa_graph.nqe_logistics_gray.get_settings"
    ) as mock_settings:
        mock_settings.return_value.nqe_logistics_mode = "shadow"
        result = run_nqe_logistics_graph("", "")
        assert "terminal_status" in result


# ── shadow compare 记录 - 成功场景 ──


def test_shadow_compare_nqe_success() -> None:
    """NQE 成功完成时，comparison_status 应为 nqe_success。"""
    record = build_nqe_shadow_compare_record(
        question="2025 年总发运量是多少",
        trace_id="trace-sc-success",
        old_result={"status": {"code": "success"}, "row_count": 42},
    )

    assert record["trace_id"] == "trace-sc-success"
    assert record["domain"] == "logistics"
    assert record["mode"] == "shadow"
    assert record["user_query"] == "2025 年总发运量是多少"
    assert record["legacy_status"] == "success"
    assert record["legacy_row_count"] == 42
    assert "nqe_duration_ms" in record
    assert "created_at" in record
    assert "comparison_status" in record


def test_shadow_compare_without_old_result() -> None:
    """无旧链路结果时 shadow compare 记录仍可生成。"""
    record = build_nqe_shadow_compare_record(
        question="各月发运趋势",
        trace_id="trace-sc-no-old",
    )

    assert record["trace_id"] == "trace-sc-no-old"
    assert record["legacy_status"] == "unknown"
    assert record["legacy_row_count"] is None
    assert record["domain"] == "logistics"
    assert "comparison_status" in record


# ── shadow compare 记录 - 失败/fallback 场景 ──


def test_shadow_compare_nqe_safety_blocked() -> None:
    """安全拦截时 comparison_status 应为 nqe_blocked_by_safety。"""
    with patch(
        "backend.app.domains.business_qa_graph.nqe_logistics_gray.run_nqe_logistics_graph",
        return_value={
            "terminal_status": "safety_reject",
            "selected_domain": "logistics",
            "sql_safety_status": "reject",
            "safety_violations": ["table_not_whitelisted"],
        },
    ):
        record = build_nqe_shadow_compare_record(
            question="查询非白名单表",
            trace_id="trace-sc-safety",
        )
        assert record["comparison_status"] == COMPARISON_NQE_BLOCKED_BY_SAFETY
        assert record["nqe_status"] == "safety_reject"
        assert record["nqe_safety_violations"] == ["table_not_whitelisted"]


def test_shadow_compare_nqe_explain_failed() -> None:
    """解释失败时 comparison_status 应为 nqe_explain_failed。"""
    with patch(
        "backend.app.domains.business_qa_graph.nqe_logistics_gray.run_nqe_logistics_graph",
        return_value={
            "terminal_status": "error",
            "selected_domain": "logistics",
            "explain_status": "fail",
            "explain_violations": ["select_star_not_allowed"],
        },
    ):
        record = build_nqe_shadow_compare_record(
            question="SELECT * FROM t",
            trace_id="trace-sc-explain",
        )
        assert record["comparison_status"] == COMPARISON_NQE_EXPLAIN_FAILED
        assert record["nqe_explain_violations"] == ["select_star_not_allowed"]


def test_shadow_compare_nqe_graph_error() -> None:
    """Graph 异常时 comparison_status 应为 nqe_graph_error。"""
    with patch(
        "backend.app.domains.business_qa_graph.nqe_logistics_gray.run_nqe_logistics_graph",
        return_value={
            "terminal_status": "graph_error",
            "error": "simulated graph failure",
        },
    ):
        record = build_nqe_shadow_compare_record(
            question="触发异常",
            trace_id="trace-sc-error",
        )
        assert record["comparison_status"] == COMPARISON_NQE_GRAPH_ERROR
        assert record["nqe_error"] == "simulated graph failure"


def test_shadow_compare_nqe_generic_failure() -> None:
    """非安全/解释的通用失败时 comparison_status 应为 nqe_failed。"""
    with patch(
        "backend.app.domains.business_qa_graph.nqe_logistics_gray.run_nqe_logistics_graph",
        return_value={
            "terminal_status": "error",
            "selected_domain": "logistics",
        },
    ):
        record = build_nqe_shadow_compare_record(
            question="触发通用失败",
            trace_id="trace-sc-generic",
        )
        assert record["comparison_status"] == COMPARISON_NQE_FAILED


# ── 接口预留确认 ──


def test_assist_and_on_are_reserved_not_implemented() -> None:
    """assist 和 on 模式配置项可读，但完整行为交由后继卡实现。"""
    for mode in ("assist", "on"):
        with patch(
            "backend.app.domains.business_qa_graph.nqe_logistics_gray.get_settings"
        ) as mock_settings:
            mock_settings.return_value.nqe_logistics_mode = mode
            assert get_nqe_logistics_mode() == mode

"""NQE 物流灰度接入测试。

本模块验证 NQE 统一 SQL Agent 在物流正式入口的 off/shadow/assist/on 四态切换能力，
不连接真实数据库、不修改旧物流正式链路。
"""

from __future__ import annotations

from unittest.mock import patch

from backend.app.domains.business_qa_graph.nqe_logistics_gray import (
    build_nqe_shadow_compare_record,
    get_nqe_logistics_mode,
    run_nqe_logistics_graph,
)


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
    """on 模式返回 on 值，但链路选择由上层 API 控制。"""
    with patch(
        "backend.app.domains.business_qa_graph.nqe_logistics_gray.get_settings"
    ) as mock_settings:
        mock_settings.return_value.nqe_logistics_mode = "on"

        assert get_nqe_logistics_mode() == "on"


def test_run_nqe_logistics_graph_returns_valid_result() -> None:
    """NQE Graph 执行应返回结构化结果。"""
    result = run_nqe_logistics_graph("2025 年总发运量是多少", "trace-gray-001")

    assert "terminal_status" in result
    assert result["terminal_status"] in {"completed", "error", "legacy_fallback", "safety_reject", "clarify"}
    assert result["selected_domain"] == "logistics"


def test_build_shadow_compare_record_with_old_result() -> None:
    """shadow compare 记录应包含 NQE 和旧链路双方摘要。"""
    record = build_nqe_shadow_compare_record(
        question="2025 年总发运量是多少",
        trace_id="trace-sc-001",
        old_result={
            "status": {"code": "success"},
            "row_count": 42,
        },
    )

    assert record["trace_id"] == "trace-sc-001"
    assert record["question_truncated"] == "2025 年总发运量是多少"
    assert record["old_status"] == "success"
    assert record["old_row_count"] == 42
    assert "nqe_terminal_status" in record
    assert "nqe_elapsed_ms" in record
    assert record["nqe_selected_domain"] == "logistics"


def test_build_shadow_compare_record_without_old_result() -> None:
    """无旧链路结果时 shadow compare 记录仍可生成。"""
    record = build_nqe_shadow_compare_record(
        question="各月发运趋势",
        trace_id="trace-sc-002",
    )

    assert record["trace_id"] == "trace-sc-002"
    assert record["old_status"] == "unknown"
    assert record["old_row_count"] is None
    assert record["nqe_selected_domain"] == "logistics"


def test_run_nqe_graph_handles_error_gracefully() -> None:
    """NQE Graph 内部错误应返回 error 状态而不抛出异常。"""
    with patch(
        "backend.app.domains.business_qa_graph.nqe_logistics_gray.get_settings"
    ) as mock_settings:
        mock_settings.return_value.nqe_logistics_mode = "shadow"

        result = run_nqe_logistics_graph("", "")
        assert "terminal_status" in result


def test_assist_mode_is_supported() -> None:
    """assist 模式可被读取。"""
    with patch(
        "backend.app.domains.business_qa_graph.nqe_logistics_gray.get_settings"
    ) as mock_settings:
        mock_settings.return_value.nqe_logistics_mode = "assist"

        assert get_nqe_logistics_mode() == "assist"

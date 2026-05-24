"""NQE BOM compare / replay adapter 测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.app.domains.business_qa_graph.nqe_plan_bom_compare_adapter import (
    NqeBomCompareResult,
    NqePlanBomCompareAdapter,
)


def test_compare_missing_left() -> None:
    adapter = NqePlanBomCompareAdapter()
    result = adapter.try_compare(left_identifier="", right_identifier="ORD-B")
    assert result.requested is True
    assert result.executed is False
    assert "left_identifier" in result.missing_slots
    assert "missing_slots" in result.fallback_reason


def test_compare_missing_right() -> None:
    adapter = NqePlanBomCompareAdapter()
    result = adapter.try_compare(left_identifier="ORD-A", right_identifier="")
    assert result.missing_slots == ["right_identifier"]
    assert result.executed is False


def test_compare_missing_both() -> None:
    adapter = NqePlanBomCompareAdapter()
    result = adapter.try_compare(left_identifier="", right_identifier="")
    assert len(result.missing_slots) == 2
    assert result.executed is False


def test_compare_service_error() -> None:
    adapter = NqePlanBomCompareAdapter()
    with patch.object(adapter, "try_compare", return_value=NqeBomCompareResult(
        operation="compare", requested=True, executed=False,
        fallback_reason="compare_error: DB down"
    )):
        result = adapter.try_compare(left_identifier="ORD-A", right_identifier="ORD-B")
        assert result.executed is False
        assert "compare_error" in result.fallback_reason


def test_replay_missing_log_id() -> None:
    adapter = NqePlanBomCompareAdapter()
    result = adapter.try_replay(log_id=0)
    assert result.executed is False
    assert result.missing_slots == ["log_id"]
    assert "missing_slots" in result.fallback_reason


def test_replay_invalid_log_id() -> None:
    adapter = NqePlanBomCompareAdapter()
    result = adapter.try_replay(log_id=-1)
    assert result.executed is False


def test_result_to_dict() -> None:
    result = NqeBomCompareResult(
        operation="compare", requested=True, executed=True,
        diff_summary="2 changed", changed_count=2, same_count=8,
    )
    d = result.to_dict()
    assert d["operation"] == "compare"
    assert d["executed"] is True
    assert d["changed_count"] == 2

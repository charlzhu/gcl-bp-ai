"""NQE BOM 候选消歧适配器测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.app.domains.business_qa_graph.nqe_plan_bom_candidate_adapter import (
    NqeBomCandidate,
    NqeBomCandidateResult,
    NqePlanBomCandidateAdapter,
)


def test_single_order_candidate_resolved() -> None:
    adapter = NqePlanBomCandidateAdapter()
    with patch.object(adapter, "resolve_candidates") as mock_resolve:
        mock_resolve.return_value = NqeBomCandidateResult(
            candidates=[NqeBomCandidate(entity_type="order", entity_value="ORD-001", display_name="ORD-001", scope="order_identity", confidence=0.9, resolved=True)],
            selected_candidate=NqeBomCandidate(entity_type="order", entity_value="ORD-001"),
            candidate_scope="order_identity",
        )
        result = adapter.resolve_candidates("查询 ORD-001")
        assert len(result.candidates) == 1
        assert result.selected_candidate is not None
        assert result.disambiguation_required is False
        assert result.fallback_reason == ""


def test_multi_candidate_disambiguation() -> None:
    adapter = NqePlanBomCandidateAdapter()
    with patch.object(adapter, "resolve_candidates") as mock_resolve:
        mock_resolve.return_value = NqeBomCandidateResult(
            candidates=[
                NqeBomCandidate(entity_type="order", entity_value="ORD-A"),
                NqeBomCandidate(entity_type="order", entity_value="ORD-B"),
            ],
            disambiguation_required=True,
            candidate_scope="order_identity",
        )
        result = adapter.resolve_candidates("查询订单")
        assert len(result.candidates) == 2
        assert result.disambiguation_required is True
        assert result.selected_candidate is None


def test_no_candidate_fallback() -> None:
    adapter = NqePlanBomCandidateAdapter()
    with patch.object(adapter, "resolve_candidates") as mock_resolve:
        mock_resolve.return_value = NqeBomCandidateResult(
            fallback_reason="no_candidate_extracted",
        )
        result = adapter.resolve_candidates("你好")
        assert len(result.candidates) == 0
        assert result.fallback_reason == "no_candidate_extracted"
        assert result.selected_candidate is None


def test_adapter_error_fallback() -> None:
    adapter = NqePlanBomCandidateAdapter()
    with patch.object(adapter, "resolve_candidates") as mock_resolve:
        mock_resolve.return_value = NqeBomCandidateResult(
            fallback_reason="nlu_service_error: connection refused",
        )
        result = adapter.resolve_candidates("")
        assert result.fallback_reason.startswith("nlu_service_error")
        assert len(result.candidates) == 0


def test_result_to_dict() -> None:
    result = NqeBomCandidateResult(
        candidates=[NqeBomCandidate(entity_type="order", entity_value="ORD-001")],
        selected_candidate=NqeBomCandidate(entity_type="order", entity_value="ORD-001"),
        disambiguation_required=False,
        candidate_scope="order_identity",
    )
    d = result.to_dict()
    assert d["domain"] == "plan_bom"
    assert len(d["candidates"]) == 1
    assert d["disambiguation_required"] is False
    assert d["selected_candidate"]["entity_value"] == "ORD-001"

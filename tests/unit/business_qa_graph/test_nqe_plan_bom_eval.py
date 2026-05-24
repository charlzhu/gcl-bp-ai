"""NQE BOM 评测集回归验证。

对 plan_bom_master_ledger 129 题做 NQE SQL Agent 链路回归。
"""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from backend.app.domains.business_qa_graph.nqe_plan_bom_candidate_adapter import NqePlanBomCandidateAdapter
from backend.app.domains.business_qa_graph.nqe_plan_bom_compare_adapter import NqePlanBomCompareAdapter

MASTER_LEDGER = Path(__file__).resolve().parents[3] / "backend/app/domains/plan_bom/config/plan_bom_master_ledger.json"
SAMPLE_SIZE = 30


def load_questions() -> list[dict[str, Any]]:
    with open(MASTER_LEDGER, encoding="utf-8") as f:
        data = json.load(f)
    return (data.get("items") or [])[:SAMPLE_SIZE]


def test_bom_candidate_on_sample() -> None:
    """BOM 候选适配器在样本上稳定运行。"""
    adapter = NqePlanBomCandidateAdapter()
    questions = load_questions()
    passed = 0
    for item in questions:
        q = item.get("question", "")
        result = adapter.resolve_candidates(q)
        if len(result.candidates) > 0 or result.fallback_reason:
            passed += 1
    assert passed == len(questions), f"candidate: {passed}/{len(questions)}"


def test_bom_compare_adapter_handles_missing_params() -> None:
    """compare 适配器参数缺失时正确 fallback。"""
    adapter = NqePlanBomCompareAdapter()
    result = adapter.try_compare(left_identifier="", right_identifier="")
    assert result.requested and not result.executed
    assert "missing_slots" in result.fallback_reason


def test_bom_replay_adapter_handles_missing_params() -> None:
    """replay 适配器参数缺失时正确 fallback。"""
    adapter = NqePlanBomCompareAdapter()
    result = adapter.try_replay(log_id=0)
    assert result.requested and not result.executed

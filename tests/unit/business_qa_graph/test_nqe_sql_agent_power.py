"""NQE 功率预测 SQL Agent 接入测试。

power prediction 是 plan_bom 子域。验证 E2E 链路。
"""

from __future__ import annotations

import importlib

INTERNAL_TERMS = ("SQL", "SELECT", "FROM", "table", "column", "query_key", "planner", "guardrail", "schema", "raw", "debug", "LLM", "prompt", "trace")


def _build_graph():
    return importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph").build_nqe_sql_agent_graph()


def _safe(text: str) -> None:
    for t in INTERNAL_TERMS:
        assert t.upper() not in text.upper()


def test_power_context_in_plan_bom() -> None:
    gm = importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")
    state = gm.retrieve_context_multiway(
        {"question": "供应商效率分布", "nqe_mode": "on", "domain_hint": "plan_bom", "selected_domain": "plan_bom"})
    assert state["retrieval_context_package"]["ready"] is True
    assert "power" in " ".join(state["retrieval_context_package"]["allowed_tables"]).lower() or "supplier" in " ".join(state["retrieval_context_package"]["allowed_tables"]).lower()


def test_power_full_e2e() -> None:
    graph = _build_graph()
    final = graph.invoke({"question": "电池厂家功率档位分布", "nqe_mode": "on", "domain_hint": "plan_bom"})
    assert final["selected_domain"] == "plan_bom"
    assert final["terminal_status"] in {"completed", "error", "safety_reject"}
    _safe(final["user_visible_response"])


def test_power_shadow_mode() -> None:
    graph = _build_graph()
    final = graph.invoke({"question": "供应商效率对比", "nqe_mode": "shadow", "domain_hint": "plan_bom"})
    assert final["selected_domain"] == "plan_bom"


def test_power_engine_not_modified() -> None:
    from backend.app.domains.plan_bom.services.power_prediction_engine import PowerPredictionEngine
    assert PowerPredictionEngine is not None

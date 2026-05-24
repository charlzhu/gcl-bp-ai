"""NQE BOM SQL Agent 接入测试。

验证统一 SQL Agent 在计划 BOM 域下的上下文构建和 E2E 链路。
"""

from __future__ import annotations

import importlib


def _build_graph():
    return importlib.import_module(
        "backend.app.domains.business_qa_graph.nqe_sql_agent_graph"
    ).build_nqe_sql_agent_graph()


def test_bom_context_ready() -> None:
    graph_module = importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")
    state = graph_module.retrieve_context_multiway(
        {"question": "BOM 评审号有哪些", "nqe_mode": "on", "domain_hint": "plan_bom", "selected_domain": "plan_bom"}
    )
    assert state["retrieval_context_package"]["ready"] is True
    assert state["retrieval_context_package"]["domain_code"] == "plan_bom"
    assert len(state["retrieval_context_package"]["allowed_tables"]) > 0


def test_bom_full_e2e() -> None:
    graph = _build_graph()
    final = graph.invoke({"question": "查询 BOM 评审号", "nqe_mode": "on", "domain_hint": "plan_bom"})
    assert final["selected_domain"] == "plan_bom"
    assert final["terminal_status"] in {"completed", "error"}

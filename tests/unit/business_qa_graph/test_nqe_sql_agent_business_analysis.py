"""NQE 产销存/经营分析 SQL Agent 接入测试。

本模块验证统一 SQL Agent 在产销存/经营分析业务域下的元数据同步和上下文构建，
不连接真实数据库、不修改旧产销存正式入口。
"""

from __future__ import annotations

import importlib
from typing import Any


INTERNAL_TERMS = (
    "SQL", "SELECT", "FROM", "table", "column",
    "query_key", "planner", "guardrail", "schema",
    "raw", "debug", "LLM", "prompt", "trace",
)


def _assert_business_safe_text(text: str) -> None:
    upper_text = text.upper()
    for term in INTERNAL_TERMS:
        assert term.upper() not in upper_text


def _build_graph():
    graph_module = importlib.import_module(
        "backend.app.domains.business_qa_graph.nqe_sql_agent_graph"
    )
    return graph_module.build_nqe_sql_agent_graph()


# ── 元数据同步与上下文 ──


def test_business_analysis_auto_context_ready() -> None:
    """产销存域应在白名单中，可自动构造元数据上下文。"""
    graph_module = importlib.import_module(
        "backend.app.domains.business_qa_graph.nqe_sql_agent_graph"
    )
    state = graph_module.retrieve_context_multiway(
        {
            "question": "2024 年组件产量是多少",
            "nqe_mode": "on",
            "domain_hint": "business_analysis",
            "selected_domain": "business_analysis",
        }
    )
    package = state["retrieval_context_package"]
    assert package["ready"] is True
    assert package["domain_code"] == "business_analysis"
    assert len(package["allowed_tables"]) > 0


def test_business_analysis_retrieval_candidates_set() -> None:
    """产销存域 auto-context 应设置 retrieval_candidates。"""
    graph_module = importlib.import_module(
        "backend.app.domains.business_qa_graph.nqe_sql_agent_graph"
    )
    state = graph_module.retrieve_context_multiway(
        {
            "question": "2025 年各月预算达成率",
            "nqe_mode": "shadow",
            "domain_hint": "business_analysis",
            "selected_domain": "business_analysis",
        }
    )
    candidates = state["retrieval_candidates"]
    assert candidates[0]["domain_code"] == "business_analysis"


def test_logistics_domain_still_works_after_business_analysis_added() -> None:
    """添加产销存域后物流域 auto-context 仍正常运行。"""
    graph_module = importlib.import_module(
        "backend.app.domains.business_qa_graph.nqe_sql_agent_graph"
    )
    state = graph_module.retrieve_context_multiway(
        {
            "question": "2024 年哪个承运商发运量最高",
            "nqe_mode": "on",
            "domain_hint": "logistics",
            "selected_domain": "logistics",
        }
    )
    package = state["retrieval_context_package"]
    assert package["ready"] is True
    assert package["domain_code"] == "logistics"


# ── 产销存端到端完整链路 ──


def test_business_analysis_full_e2e_pipeline() -> None:
    """产销存 on 模式走完整 SQL Agent 链路。"""
    graph = _build_graph()
    final_state = graph.invoke(
        {
            "question": "2024 年组件产量是多少",
            "nqe_mode": "on",
            "domain_hint": "business_analysis",
        }
    )
    assert final_state["selected_domain"] == "business_analysis"
    assert final_state["terminal_status"] in {"completed", "error"}
    assert final_state["sql_safety_result"]["status"] == "pass"
    _assert_business_safe_text(final_state["user_visible_response"])


def test_business_analysis_safety_reject_on_ddl() -> None:
    """产销存域 DDL 注入必须被安全预检拒绝。"""
    graph = _build_graph()
    final_state = graph.invoke(
        {
            "question": "删除所有数据",
            "nqe_mode": "on",
            "domain_hint": "business_analysis",
            "retrieval_context_package": {
                "ready": True,
                "allowed_tables": ["ba_metric_view"],
                "generated_sql_candidate": "DROP TABLE ba_metric_view",
            },
            "context_readiness": "pass",
        }
    )
    assert final_state["terminal_status"] == "safety_reject"
    _assert_business_safe_text(final_state["user_visible_response"])


def test_business_analysis_shadow_mode_context() -> None:
    """产销存 shadow 模式仍构建上下文。"""
    graph = _build_graph()
    final_state = graph.invoke(
        {
            "question": "2024 年库存周转率",
            "nqe_mode": "shadow",
            "domain_hint": "business_analysis",
        }
    )
    assert final_state["selected_domain"] == "business_analysis"
    assert final_state["retrieval_context_package"]["ready"] is True

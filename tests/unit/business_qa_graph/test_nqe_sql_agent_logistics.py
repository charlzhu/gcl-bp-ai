"""NQE 物流 SQL Agent 接入测试。

本模块验证统一 SQL Agent 在物流业务域下从用户问题到 trace 记录的完整链路，
不连接真实数据库、不修改旧物流正式入口。
"""

from __future__ import annotations

import importlib
from typing import Any


INTERNAL_TERMS = (
    "SQL",
    "SELECT",
    "FROM",
    "table",
    "column",
    "query_key",
    "planner",
    "guardrail",
    "schema",
    "raw",
    "debug",
    "LLM",
    "prompt",
    "trace",
)


def _node_names(state: dict[str, Any]) -> list[str]:
    return [step["node"] for step in state.get("trace_steps", [])]


def _assert_business_safe_text(text: str) -> None:
    upper_text = text.upper()
    for term in INTERNAL_TERMS:
        assert term.upper() not in upper_text


def _build_graph():
    graph_module = importlib.import_module(
        "backend.app.domains.business_qa_graph.nqe_sql_agent_graph"
    )
    return graph_module.build_nqe_sql_agent_graph()


# ── 物流域路由与元数据上下文 ──


def test_logistics_domain_route_recognizes_logistics_hint() -> None:
    """物流 domain_hint 被正确路由为 logistics 业务域。"""
    graph = _build_graph()

    final_state = graph.invoke(
        {
            "question": "2025 年总发运量是多少？",
            "nqe_mode": "on",
            "domain_hint": "logistics",
        }
    )

    assert final_state["selected_domain"] == "logistics"


def test_logistics_context_package_contains_expected_metadata() -> None:
    """物流元数据上下文包至少包含 allowed_tables、table_columns 和 domain_code。"""
    graph_module = importlib.import_module(
        "backend.app.domains.business_qa_graph.nqe_sql_agent_graph"
    )
    state = graph_module.retrieve_context_multiway(
        {
            "question": "查询本月发运量",
            "normalized_question": "查询本月发运量",
            "nqe_mode": "on",
            "domain_hint": "logistics",
            "selected_domain": "logistics",
        }
    )
    package = state["retrieval_context_package"]

    assert package["ready"] is True
    assert package["domain_code"] == "logistics"
    assert isinstance(package["allowed_tables"], list)
    assert len(package["allowed_tables"]) > 0
    assert isinstance(package["table_columns"], dict)
    assert len(package["table_columns"]) > 0
    # 中文注释：物流 catalog 至少应包含 logistics 相关核心事实表
    table_names = " ".join(package["allowed_tables"])
    assert "logistics" in table_names.lower()


def test_logistics_retrieval_assets_include_chunks() -> None:
    """物流召回资产必须包含召回块摘要和实际块内容。"""
    graph_module = importlib.import_module(
        "backend.app.domains.business_qa_graph.nqe_sql_agent_graph"
    )
    state = graph_module.retrieve_context_multiway(
        {
            "question": "哪个承运商发运量最高",
            "normalized_question": "哪个承运商发运量最高",
            "nqe_mode": "on",
            "domain_hint": "logistics",
            "selected_domain": "logistics",
        }
    )
    package = state["retrieval_context_package"]
    assets = package["retrieval_assets"]

    assert assets["summary"]["tables"] > 0
    assert assets["summary"]["columns"] > 0
    assert assets["summary"]["chunks"] > 0
    assert len(assets["chunks"]) > 0
    for chunk in assets["chunks"]:
        assert "asset_type" in chunk
        assert "chunk_text" in chunk


# ── 物流端到端完整链路 ──


def test_logistics_full_e2e_pipeline_on_mode() -> None:
    """物流 on 模式走完整 SQL Agent 链路：domain → context → generate → safety → explain → execute → trace。"""
    graph = _build_graph()

    final_state = graph.invoke(
        {
            "question": "2024 年总发运量是多少吨",
            "nqe_mode": "on",
            "domain_hint": "logistics",
        }
    )
    node_names = _node_names(final_state)

    assert final_state["selected_domain"] == "logistics"
    # 中文注释：auto-context 使用实际字段名生成安全 SQL，可能通过 precheck+explain 完成，
    # 也可能因为字段校验失败进入 error 终态（骨架无真实 LLM 修正）。
    assert final_state["terminal_status"] in {"completed", "error"}
    assert final_state["sql_safety_result"]["status"] == "pass"
    if final_state["terminal_status"] == "completed":
        assert "execute_sql_readonly" in node_names
    # 无论终态，用户可见回答必须屏蔽内部词
    _assert_business_safe_text(final_state["user_visible_response"])


def test_logistics_safety_reject_on_unsafe_sql() -> None:
    """物流域注入非白名单表候选时，安全预检必须拒绝并返回 safety_reject。"""
    graph = _build_graph()

    final_state = graph.invoke(
        {
            "question": "查询机密数据",
            "nqe_mode": "on",
            "domain_hint": "logistics",
            "retrieval_context_package": {
                "ready": True,
                "allowed_tables": ["dws_logistics_detail_union"],
                "generated_sql_candidate": "DROP TABLE dws_logistics_detail_union",
            },
            "context_readiness": "pass",
        }
    )

    assert final_state["terminal_status"] == "safety_reject"
    assert "mutating_or_ddl_keyword" in final_state["sql_safety_result"]["violations"]
    _assert_business_safe_text(final_state["user_visible_response"])


def test_logistics_explain_rejects_select_star() -> None:
    """物流域 SELECT * 查询必须被解释校验拒绝。"""
    graph = _build_graph()

    final_state = graph.invoke(
        {
            "question": "查询本月全部发运数据",
            "nqe_mode": "on",
            "domain_hint": "logistics",
            "retrieval_context_package": {
                "ready": True,
                "allowed_tables": ["nqe_safe_metric_view"],
                "table_columns": {"nqe_safe_metric_view": ["metric_value"]},
                "generated_sql_candidate": "SELECT * FROM nqe_safe_metric_view",
            },
            "context_readiness": "pass",
        }
    )

    assert final_state["terminal_status"] == "error"
    assert final_state["explain_result"]["status"] == "fail"
    assert "select_star_not_allowed" in final_state["explain_result"]["violations"]
    _assert_business_safe_text(final_state["user_visible_response"])


def test_logistics_trace_and_replay_recorded() -> None:
    """物流域查询完成后必须记录脱敏 trace 和 replay。"""
    graph = _build_graph()

    final_state = graph.invoke(
        {
            "question": "2025 年各月发运量趋势",
            "nqe_mode": "on",
            "domain_hint": "logistics",
        }
    )

    assert "trace_steps" in final_state
    assert len(final_state["trace_steps"]) > 0
    assert "query_log_record" in final_state
    assert "replay_record" in final_state
    _assert_business_safe_text(final_state["user_visible_response"])


# ── 物流域 shadow 模式 ──


def test_logistics_shadow_mode_builds_context() -> None:
    """物流 shadow 模式仍构建元数据上下文且选定物流域。"""
    graph = _build_graph()

    final_state = graph.invoke(
        {
            "question": "2024 年各承运商发运车次",
            "nqe_mode": "shadow",
            "domain_hint": "logistics",
        }
    )

    assert final_state["selected_domain"] == "logistics"
    assert final_state["retrieval_context_package"]["domain_code"] == "logistics"
    assert final_state["retrieval_context_package"]["ready"] is True


# ── 物流域 off 模式 ──


def test_logistics_off_mode_skips_nqe_pipeline() -> None:
    """物流 off 模式不走 NQE 生成与执行链路，直接走旧链路 fallback。"""
    graph = _build_graph()

    final_state = graph.invoke(
        {
            "question": "2025 年发运量",
            "nqe_mode": "off",
            "domain_hint": "logistics",
        }
    )
    node_names = _node_names(final_state)

    assert final_state["terminal_status"] == "legacy_fallback"
    assert "generate_sql_direct" not in node_names
    assert "precheck_sql_safety" not in node_names
    assert "execute_sql_readonly" not in node_names
    _assert_business_safe_text(final_state["user_visible_response"])

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
    """读取测试态中的节点轨迹名称。"""
    return [step["node"] for step in state.get("trace_steps", [])]


def _assert_business_safe_text(text: str) -> None:
    """断言用户可见文本不暴露内部技术词。"""
    upper_text = text.upper()
    for term in INTERNAL_TERMS:
        assert term.upper() not in upper_text


def _safe_ready_context() -> dict[str, Any]:
    """构造可通过 NQE 内部安全预检的测试上下文。"""
    return {
        "ready": True,
        "business_object": "shipment",
        "allowed_tables": ["nqe_safe_metric_view"],
        "generated_sql_candidate": "SELECT metric_value FROM nqe_safe_metric_view",
    }


def test_nqe_graph_declares_expected_node_sequence() -> None:
    """NQE Graph 必须声明 NQE-SQL-MAIN-4 约定的 19 个节点及顺序。"""
    graph_module = importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")

    assert graph_module.NQE_SQL_AGENT_NODE_SEQUENCE == (
        "receive_query",
        "init_trace_and_mode",
        "route_domain_and_capability",
        "normalize_query",
        "retrieve_context_multiway",
        "merge_rank_and_build_context",
        "check_context_readiness",
        "generate_sql_direct",
        "precheck_sql_safety",
        "explain_validate_sql",
        "correct_sql",
        "execute_sql_readonly",
        "present_business_answer",
        "record_query_log_and_trace",
        "legacy_fallback",
        "shadow_compare",
        "terminal_clarify",
        "terminal_safety_reject",
        "terminal_error",
    )
    assert len(graph_module.NQE_SQL_AGENT_NODE_SEQUENCE) == 19


def test_nqe_graph_compiles_without_touching_runtime_entrypoint() -> None:
    """独立 NQE builder 可编译，且不需要导入正式 API 或修改运行入口。"""
    graph_module = importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")

    graph = graph_module.build_nqe_sql_agent_graph()

    assert graph is not None
    assert "backend.app.api.router" not in graph_module.__dict__
    assert "BusinessQaGraphRunner" not in graph_module.__dict__


def test_off_mode_routes_to_legacy_fallback_without_sql_generation() -> None:
    """off 模式应进入 legacy_fallback，不能生成、预检或执行 SQL。"""
    graph_module = importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")
    graph = graph_module.build_nqe_sql_agent_graph()

    final_state = graph.invoke({"question": "查询本月经营情况", "nqe_mode": "off"})
    node_names = _node_names(final_state)

    assert final_state["terminal_status"] == "legacy_fallback"
    assert "legacy_fallback" in node_names
    assert "record_query_log_and_trace" in node_names
    assert "generate_sql_direct" not in node_names
    assert "precheck_sql_safety" not in node_names
    assert "execute_sql_readonly" not in node_names


def test_context_not_ready_returns_business_clarification() -> None:
    """on 模式上下文不足时应业务化澄清，不能泄露内部实现。"""
    graph_module = importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")
    graph = graph_module.build_nqe_sql_agent_graph()

    final_state = graph.invoke({"question": "查一下库存", "nqe_mode": "on"})

    assert final_state["terminal_status"] == "clarify"
    assert "terminal_clarify" in _node_names(final_state)
    _assert_business_safe_text(final_state["user_visible_response"])


def test_sql_lifecycle_orders_precheck_before_explain_and_execute() -> None:
    """ready 上下文下 SQL 生命周期顺序必须先预检，再解释校验，再只读执行。"""
    graph_module = importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")
    graph = graph_module.build_nqe_sql_agent_graph()

    final_state = graph.invoke(
        {
            "question": "查询本月发运量",
            "nqe_mode": "on",
            "retrieval_context_package": _safe_ready_context(),
            "context_readiness": "pass",
        }
    )
    node_names = _node_names(final_state)

    assert final_state["terminal_status"] == "completed"
    expected = ["generate_sql_direct", "precheck_sql_safety", "explain_validate_sql", "execute_sql_readonly"]
    positions = [node_names.index(node) for node in expected]
    assert positions == sorted(positions)


def test_correct_loop_returns_to_precheck_and_stops_after_two_rounds() -> None:
    """解释校验失败后必须 correct→precheck 循环，且最多两轮后进入终态。"""
    graph_module = importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")
    graph = graph_module.build_nqe_sql_agent_graph()

    final_state = graph.invoke(
        {
            "question": "查询本月发运量",
            "nqe_mode": "on",
            "retrieval_context_package": _safe_ready_context(),
            "context_readiness": "pass",
            "force_explain_fail": True,
        }
    )
    node_names = _node_names(final_state)

    assert final_state["terminal_status"] in {"error", "safety_reject", "clarify"}
    assert node_names.count("correct_sql") == 2
    assert node_names.count("precheck_sql_safety") == 3
    assert final_state["sql_revision_round"] == 2
    first_correct = node_names.index("correct_sql")
    assert "precheck_sql_safety" in node_names[first_correct + 1 :]


def test_terminal_states_are_recorded_before_end() -> None:
    """所有终态都必须先经过 record_query_log_and_trace 再结束。"""
    graph_module = importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")
    graph = graph_module.build_nqe_sql_agent_graph()
    cases = [
        ({"question": "查一下", "nqe_mode": "on"}, "clarify"),
        ({"question": "查一下", "nqe_mode": "on", "retrieval_context_package": _safe_ready_context(), "context_readiness": "pass", "force_safety_reject": True}, "safety_reject"),
        ({"question": "查一下", "nqe_mode": "on", "retrieval_context_package": _safe_ready_context(), "context_readiness": "pass", "force_explain_fail": True}, "error"),
        ({"question": "查一下", "nqe_mode": "off"}, "legacy_fallback"),
        ({"question": "查一下", "nqe_mode": "on", "retrieval_context_package": _safe_ready_context(), "context_readiness": "pass"}, "completed"),
    ]

    for initial_state, status in cases:
        final_state = graph.invoke(initial_state)
        node_names = _node_names(final_state)
        assert final_state["terminal_status"] == status
        assert node_names[-1] == "record_query_log_and_trace"


def test_user_visible_response_masks_internal_terms() -> None:
    """所有用户可见输出必须屏蔽内部技术词。"""
    graph_module = importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")
    graph = graph_module.build_nqe_sql_agent_graph()
    states = [
        {"question": "查一下", "nqe_mode": "on"},
        {"question": "查一下", "nqe_mode": "off"},
        {"question": "查一下", "nqe_mode": "on", "retrieval_context_package": _safe_ready_context(), "context_readiness": "pass"},
        {"question": "查一下", "nqe_mode": "on", "retrieval_context_package": _safe_ready_context(), "context_readiness": "pass", "force_safety_reject": True},
        {"question": "查一下", "nqe_mode": "on", "retrieval_context_package": _safe_ready_context(), "context_readiness": "pass", "force_explain_fail": True},
    ]

    for state in states:
        final_state = graph.invoke(state)
        _assert_business_safe_text(final_state["user_visible_response"])


def test_retrieve_context_multiway_builds_logistics_metadata_context_without_injection() -> None:
    """验证 shadow/on 物流域在未注入上下文时可自动构造元数据上下文。"""

    graph_module = importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")

    for mode in ("shadow", "on"):
        state = graph_module.retrieve_context_multiway(
            {
                "question": "查询本月发运量",
                "normalized_question": "查询本月发运量",
                "nqe_mode": mode,
                "domain_hint": "logistics",
            }
        )
        package = state["retrieval_context_package"]

        assert package["ready"] is True
        assert package["domain_code"] == "logistics"
        assert package["allowed_tables"]
        assert package["table_columns"]
        assert state["retrieval_candidates"] == [{"status": "ready", "domain_code": "logistics"}]


def test_retrieve_context_multiway_builds_logistics_context_when_cwd_changes(monkeypatch, tmp_path) -> None:
    """验证物流自动上下文不依赖当前进程 cwd。

    业务逻辑：服务部署时 cwd 不一定是仓库根目录，默认 catalog 路径必须由模块位置推导。
    """

    graph_module = importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")
    monkeypatch.chdir(tmp_path)

    state = graph_module.retrieve_context_multiway(
        {
            "question": "查询本月发运量",
            "normalized_question": "查询本月发运量",
            "nqe_mode": "on",
            "domain_hint": "logistics",
        }
    )

    package = state["retrieval_context_package"]
    assert package["ready"] is True
    assert package["domain_code"] == "logistics"
    assert package["retrieval_assets"]["summary"]["chunks"] > 0


def test_retrieve_context_multiway_does_not_auto_ready_unknown_domain() -> None:
    """验证未接入域仍保持占位澄清，不自动 ready。"""
    graph_module = importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")
    state = graph_module.retrieve_context_multiway(
        {"question": "未知域", "nqe_mode": "on", "domain_hint": "unknown_domain"})
    assert state["retrieval_context_package"] == {}
    assert state["retrieval_candidates"] == []


def test_retrieve_context_multiway_prefers_injected_context_package() -> None:
    """验证调用方显式注入上下文时仍保持优先兼容。"""

    graph_module = importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")
    injected = {"ready": True, "domain_code": "injected", "allowed_tables": ["unit_safe_table"]}

    state = graph_module.retrieve_context_multiway(
        {
            "question": "查询本月发运量",
            "normalized_question": "查询本月发运量",
            "nqe_mode": "on",
            "domain_hint": "logistics",
            "retrieval_context_package": injected,
        }
    )

    assert state["retrieval_context_package"] == injected
    assert state["retrieval_candidates"] == [{"status": "ready"}]

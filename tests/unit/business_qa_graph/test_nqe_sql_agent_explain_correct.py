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
    """读取 Graph 测试态中的节点名称。"""
    return [step["node"] for step in state.get("trace_steps", [])]


def _assert_business_safe_text(text: str) -> None:
    """断言用户可见文本不暴露内部技术词。"""
    upper_text = text.upper()
    for term in INTERNAL_TERMS:
        assert term.upper() not in upper_text


def _assert_subsequence(items: list[str], expected: list[str]) -> None:
    """断言 expected 节点按顺序出现在实际轨迹中。"""
    cursor = 0
    for item in items:
        if cursor < len(expected) and item == expected[cursor]:
            cursor += 1
    assert cursor == len(expected)


def _unknown_column_context(
    *,
    correction_candidates: list[str] | None = None,
    generated_sql_candidate: str = "SELECT missing_metric FROM nqe_safe_metric_view",
) -> dict[str, Any]:
    """构造含字段元数据和错误字段候选的 NQE 测试上下文。"""
    context: dict[str, Any] = {
        "ready": True,
        "business_object": "shipment",
        "allowed_tables": ["nqe_safe_metric_view"],
        "table_columns": {"nqe_safe_metric_view": ["metric_value"]},
        "generated_sql_candidate": generated_sql_candidate,
    }
    if correction_candidates is not None:
        context["sql_correction_candidates"] = correction_candidates
    return context


def _build_graph():
    """构建 NQE SQL Agent 独立测试 Graph。"""
    graph_module = importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")
    return graph_module.build_nqe_sql_agent_graph()


def test_explain_validate_rejects_unknown_column_before_execution() -> None:
    """解释校验必须基于字段元数据拦截未知字段，且不能进入只读执行。"""
    graph = _build_graph()

    final_state = graph.invoke(
        {
            "question": "查询本月发运量",
            "nqe_mode": "on",
            "retrieval_context_package": _unknown_column_context(),
            "context_readiness": "pass",
        }
    )
    node_names = _node_names(final_state)

    assert final_state["terminal_status"] == "error"
    assert final_state["explain_result"]["status"] == "fail"
    assert "unknown_column" in final_state["explain_result"]["violations"]
    assert "execute_sql_readonly" not in node_names
    assert node_names.count("correct_sql") == 2
    assert node_names.count("precheck_sql_safety") == 3
    assert final_state["sql_revision_round"] == 2
    _assert_business_safe_text(final_state["user_visible_response"])


def test_explain_validate_rejects_unknown_projection_expressions() -> None:
    """解释校验必须拦截函数和引用符包裹的未知字段，避免投影校验绕过。"""
    for candidate in (
        "SELECT SUM(missing_metric) FROM nqe_safe_metric_view",
        'SELECT "missing_metric" FROM nqe_safe_metric_view',
    ):
        graph = _build_graph()
        final_state = graph.invoke(
            {
                "question": "查询本月发运量",
                "nqe_mode": "on",
                "retrieval_context_package": _unknown_column_context(generated_sql_candidate=candidate),
                "context_readiness": "pass",
            }
        )
        node_names = _node_names(final_state)

        assert final_state["terminal_status"] == "error"
        assert final_state["explain_result"]["status"] == "fail"
        assert "unknown_column" in final_state["explain_result"]["violations"]
        assert "execute_sql_readonly" not in node_names
        _assert_business_safe_text(final_state["user_visible_response"])


def test_explain_validate_rejects_select_star_before_execution() -> None:
    """解释校验必须拒绝 SELECT *，避免过宽字段绕过执行前校验。"""
    graph = _build_graph()

    final_state = graph.invoke(
        {
            "question": "查询本月发运量",
            "nqe_mode": "on",
            "retrieval_context_package": _unknown_column_context(
                generated_sql_candidate="SELECT * FROM nqe_safe_metric_view"
            ),
            "context_readiness": "pass",
        }
    )
    node_names = _node_names(final_state)

    assert final_state["terminal_status"] == "error"
    assert final_state["explain_result"]["status"] == "fail"
    assert "select_star_not_allowed" in final_state["explain_result"]["violations"]
    assert "execute_sql_readonly" not in node_names


def test_explain_validate_rejects_unknown_filter_columns_before_execution() -> None:
    """解释校验必须校验 WHERE 条件字段，避免过滤条件未知字段绕过。"""
    graph = _build_graph()

    final_state = graph.invoke(
        {
            "question": "查询本月发运量",
            "nqe_mode": "on",
            "retrieval_context_package": _unknown_column_context(
                generated_sql_candidate="SELECT metric_value FROM nqe_safe_metric_view WHERE missing_metric = 1"
            ),
            "context_readiness": "pass",
        }
    )
    node_names = _node_names(final_state)

    assert final_state["terminal_status"] == "error"
    assert final_state["explain_result"]["status"] == "fail"
    assert "unknown_column" in final_state["explain_result"]["violations"]
    assert "execute_sql_readonly" not in node_names


def test_correct_sql_uses_context_candidate_and_rechecks_safety_before_completion() -> None:
    """受控修正候选必须回写后重新预检，再解释校验并只读执行。"""
    graph = _build_graph()
    corrected_sql = "SELECT metric_value FROM nqe_safe_metric_view"

    final_state = graph.invoke(
        {
            "question": "查询本月发运量",
            "nqe_mode": "on",
            "retrieval_context_package": _unknown_column_context(correction_candidates=[corrected_sql]),
            "context_readiness": "pass",
        }
    )
    node_names = _node_names(final_state)

    assert final_state["terminal_status"] == "completed"
    _assert_subsequence(
        node_names,
        [
            "precheck_sql_safety",
            "explain_validate_sql",
            "correct_sql",
            "precheck_sql_safety",
            "explain_validate_sql",
            "execute_sql_readonly",
        ],
    )
    assert node_names.count("correct_sql") == 1
    assert node_names.count("precheck_sql_safety") == 2
    assert node_names.count("explain_validate_sql") == 2
    assert final_state["sql_revision_round"] == 1
    assert final_state["generated_sql"] == corrected_sql
    assert final_state["safe_sql_candidate"] == f"{corrected_sql} LIMIT 200"
    _assert_business_safe_text(final_state["user_visible_response"])

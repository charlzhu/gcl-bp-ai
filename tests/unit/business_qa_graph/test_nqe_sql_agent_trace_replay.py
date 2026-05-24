from __future__ import annotations

import importlib
from typing import Any


FORBIDDEN_LOG_KEYS = {
    "generated_sql",
    "safe_sql_candidate",
    "execution_result_internal",
    "retrieval_context_package",
    "user_visible_response",
}
FORBIDDEN_TEXT_FRAGMENTS = (
    "SELECT metric_value",
    "FROM nqe_safe_metric_view",
    "LIMIT 200",
)


def _safe_ready_context(candidate: str = "SELECT metric_value FROM nqe_safe_metric_view") -> dict[str, Any]:
    """构造可通过 NQE 内部链路的测试上下文。"""
    return {
        "ready": True,
        "business_object": "shipment",
        "allowed_tables": ["nqe_safe_metric_view"],
        "table_columns": {"nqe_safe_metric_view": ["metric_value"]},
        "generated_sql_candidate": candidate,
    }


def _build_graph_module():
    """加载 NQE 独立 Graph 模块。"""
    return importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")


def _node_names(state: dict[str, Any]) -> list[str]:
    """读取最终态中的节点轨迹名称。"""
    return [step["node"] for step in state.get("trace_steps", [])]


def test_record_node_writes_sanitized_query_log_and_replay_record() -> None:
    """记录节点必须写入脱敏 query log 与可重放记录，且不把内部候选文本放进 query log。"""
    graph_module = _build_graph_module()
    graph = graph_module.build_nqe_sql_agent_graph()

    final_state = graph.invoke(
        {
            "question": "查询本月发运量",
            "nqe_mode": "on",
            "trace_id": "trace-test-001",
            "domain_hint": "logistics",
            "retrieval_context_package": {
                **_safe_ready_context(),
                "password": "SENSITIVE_MARKER_PASSWORD",
                "nested": {"api_key": "SENSITIVE_MARKER_API", "note": "ok"},
                "ignored_blob": {"raw": "SENSITIVE_MARKER_RAW"},
            },
            "client_context": {"api_key": "SENSITIVE_MARKER_CLIENT"},
            "user_context": {"token": "SENSITIVE_MARKER_USER"},
            "context_readiness": "pass",
        }
    )

    query_log = final_state["query_log_record"]
    replay_record = final_state["replay_record"]

    assert final_state["terminal_status"] == "completed"
    assert query_log["schema_version"] == "nqe_query_log.v1"
    assert query_log["trace_id"] == "trace-test-001"
    assert query_log["terminal_status"] == "completed"
    assert query_log["execution_status"] == "executed"
    assert query_log["row_count"] == 1
    assert query_log["question_digest"]
    assert query_log["question_length"] == len("查询本月发运量")
    assert query_log["trace_summary"][-1]["node"] == "record_query_log_and_trace"
    assert query_log["safety_summary"]["status"] == "pass"
    assert query_log["explain_summary"]["status"] == "pass"
    assert not (FORBIDDEN_LOG_KEYS & set(query_log))
    assert replay_record["schema_version"] == "nqe_replay.v1"
    assert replay_record["query_log_id"] == query_log["log_id"]
    replay_input = replay_record["replay_input"]
    assert replay_input["question"] != "查询本月发运量"
    assert replay_input["replay_context_summary"]["question_digest"]
    assert replay_input["replay_context_summary"]["had_retrieval_context"] is True
    assert replay_input["replay_context_summary"]["sensitive_key_seen"] is True
    assert replay_record["expected_summary"]["terminal_status"] == "completed"
    assert "retrieval_context_package" not in replay_input
    assert "client_context" not in replay_input
    assert "user_context" not in replay_input
    assert "generated_sql_candidate" not in str(replay_input)
    assert "table_columns" not in str(replay_input)
    assert "SECRET" not in str(replay_record)

    query_log_text = str(query_log)
    for fragment in FORBIDDEN_TEXT_FRAGMENTS:
        assert fragment not in query_log_text


def test_replay_record_reproduces_terminal_status_and_trace_shape() -> None:
    """replay_record 应能重放同一骨架路径，并复现终态与节点顺序摘要。"""
    graph_module = _build_graph_module()
    graph = graph_module.build_nqe_sql_agent_graph()
    final_state = graph.invoke(
        {
            "question": "查询本月发运量",
            "nqe_mode": "shadow",
            "trace_id": "trace-test-002",
            "domain_hint": "logistics",
            "retrieval_context_package": _safe_ready_context(),
            "context_readiness": "pass",
        }
    )

    replay_state = graph_module.replay_nqe_sql_agent_record(final_state["replay_record"])

    assert replay_state["terminal_status"] == final_state["terminal_status"]
    assert replay_state["query_log_record"]["terminal_status"] == final_state["query_log_record"]["terminal_status"]
    assert replay_state["query_log_record"]["row_count"] == final_state["query_log_record"]["row_count"]
    assert _node_names(replay_state) == _node_names(final_state)
    assert replay_state["replay_summary"]["matched"] is True
    assert replay_state["replay_summary"]["expected_terminal_status"] == "completed"
    assert replay_state["replay_summary"]["actual_terminal_status"] == "completed"


def test_query_log_is_written_for_safety_reject_without_leaking_candidate_text() -> None:
    """安全拒绝路径也必须记录结构化日志，但 query log 不能保存被拒绝候选文本。"""
    graph_module = _build_graph_module()
    graph = graph_module.build_nqe_sql_agent_graph()

    final_state = graph.invoke(
        {
            "question": "查询本月发运量",
            "nqe_mode": "on",
            "trace_id": "trace-test-003",
            "retrieval_context_package": _safe_ready_context("SELECT metric_value FROM nqe_other_metric_view"),
            "context_readiness": "pass",
        }
    )

    query_log = final_state["query_log_record"]

    assert final_state["terminal_status"] == "safety_reject"
    assert query_log["terminal_status"] == "safety_reject"
    assert query_log["execution_status"] == "skipped"
    assert query_log["safety_summary"]["status"] == "reject"
    assert "table_not_whitelisted" in query_log["safety_summary"]["violations"]
    assert "nqe_other_metric_view" not in str(query_log)
    assert "SELECT metric_value" not in str(query_log)

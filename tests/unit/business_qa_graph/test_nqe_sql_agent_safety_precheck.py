from __future__ import annotations

import importlib
from typing import Any

from backend.app.domains.business_qa_graph.nqe_sql_safety import precheck_nqe_sql_safety


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


def _safe_package(candidate: str = "SELECT metric_value FROM nqe_safe_metric_view") -> dict[str, Any]:
    """构造带白名单和候选文本的安全测试上下文。"""
    return {
        "ready": True,
        "allowed_tables": ["nqe_safe_metric_view"],
        "generated_sql_candidate": candidate,
    }


def test_precheck_allows_whitelisted_select_and_builds_safe_candidate() -> None:
    """白名单内的单条只读查询应通过，并生成带结果上限的安全候选。"""
    result = precheck_nqe_sql_safety(
        "SELECT metric_value FROM nqe_safe_metric_view",
        {"allowed_tables": ["nqe_safe_metric_view"]},
        "logistics",
    )

    assert result["status"] == "pass"
    assert result["reason_code"] == "safe"
    assert result["safe_sql"] == "SELECT metric_value FROM nqe_safe_metric_view LIMIT 200"
    assert result["limit_applied"] is True
    assert result["allowed_tables"] == ["nqe_safe_metric_view"]


def test_precheck_rejects_non_whitelisted_table() -> None:
    """候选文本引用非白名单对象时必须拒绝。"""
    result = precheck_nqe_sql_safety(
        "SELECT metric_value FROM nqe_other_metric_view",
        {"allowed_tables": ["nqe_safe_metric_view"]},
        "logistics",
    )

    assert result["status"] == "reject"
    assert "table_not_whitelisted" in result["violations"]
    assert result["safe_sql"] == ""


def test_precheck_rejects_dml_and_ddl_keywords() -> None:
    """写入、变更结构或过程调用类语句必须拒绝。"""
    dml_result = precheck_nqe_sql_safety(
        "UPDATE nqe_safe_metric_view SET metric_value = 1",
        {"allowed_tables": ["nqe_safe_metric_view"]},
        "logistics",
    )
    ddl_result = precheck_nqe_sql_safety(
        "DROP TABLE nqe_safe_metric_view",
        {"allowed_tables": ["nqe_safe_metric_view"]},
        "logistics",
    )

    assert dml_result["status"] == "reject"
    assert ddl_result["status"] == "reject"
    assert "mutating_or_ddl_keyword" in dml_result["violations"]
    assert "mutating_or_ddl_keyword" in ddl_result["violations"]


def test_precheck_rejects_multiple_statements() -> None:
    """多语句候选必须拒绝，避免绕过后续只读边界。"""
    result = precheck_nqe_sql_safety(
        "SELECT metric_value FROM nqe_safe_metric_view; SELECT metric_value FROM nqe_safe_metric_view",
        {"allowed_tables": ["nqe_safe_metric_view"]},
        "logistics",
    )

    assert result["status"] == "reject"
    assert "multiple_statements" in result["violations"]


def test_precheck_rejects_system_or_high_risk_objects() -> None:
    """系统库或高风险对象必须拒绝，即使上下文误配白名单也不能放行。"""
    result = precheck_nqe_sql_safety(
        "SELECT table_name FROM information_schema.tables",
        {"allowed_tables": ["information_schema.tables"]},
        "logistics",
    )

    assert result["status"] == "reject"
    assert "system_object" in result["violations"]


def test_precheck_rejects_dangerous_functions_and_export_expressions() -> None:
    """危险函数和导出类表达式必须拒绝。"""
    function_result = precheck_nqe_sql_safety(
        "SELECT sleep(1) FROM nqe_safe_metric_view",
        {"allowed_tables": ["nqe_safe_metric_view"]},
        "logistics",
    )
    export_result = precheck_nqe_sql_safety(
        "SELECT metric_value FROM nqe_safe_metric_view INTO OUTFILE '/tmp/a.txt'",
        {"allowed_tables": ["nqe_safe_metric_view"]},
        "logistics",
    )

    assert function_result["status"] == "reject"
    assert export_result["status"] == "reject"
    assert "dangerous_expression" in function_result["violations"]
    assert "dangerous_expression" in export_result["violations"]


def test_precheck_rejects_missing_whitelist_fail_closed() -> None:
    """缺少上下文白名单时必须 fail-closed 拒绝。"""
    result = precheck_nqe_sql_safety("SELECT metric_value FROM nqe_safe_metric_view", {}, "logistics")

    assert result["status"] == "reject"
    assert "missing_whitelist" in result["violations"]
    assert result["safe_sql"] == ""


def test_precheck_rejects_comma_join_non_whitelisted_table() -> None:
    """逗号连接中的每个对象都必须纳入白名单校验。"""
    result = precheck_nqe_sql_safety(
        "SELECT a.metric_value FROM nqe_safe_metric_view a, nqe_secret_metric_view b",
        {"allowed_tables": ["nqe_safe_metric_view"]},
        "logistics",
    )

    assert result["status"] == "reject"
    assert "table_not_whitelisted" in result["violations"]
    assert "nqe_secret_metric_view" in result["referenced_tables"]


def test_precheck_rejects_schema_qualified_basename_bypass() -> None:
    """候选带 schema 时不能只凭同名表 basename 放行。"""
    result = precheck_nqe_sql_safety(
        "SELECT metric_value FROM other_schema.nqe_safe_metric_view",
        {"allowed_tables": ["nqe_safe_metric_view"]},
        "logistics",
    )

    assert result["status"] == "reject"
    assert "table_not_whitelisted" in result["violations"]


def test_precheck_rejects_database_file_and_external_access_functions() -> None:
    """数据库文件读取、外联和命令类函数必须保守拒绝。"""
    result = precheck_nqe_sql_safety(
        "SELECT pg_read_file('/etc/passwd') FROM nqe_safe_metric_view",
        {"allowed_tables": ["nqe_safe_metric_view"]},
        "logistics",
    )

    assert result["status"] == "reject"
    assert "dangerous_expression" in result["violations"]


def test_precheck_rejects_dblink_family_functions() -> None:
    """dblink 下划线同族函数可能建立外部连接或读取远端结果，必须统一拒绝。"""
    for sql in (
        "SELECT dblink_connect('x') FROM nqe_safe_metric_view",
        "SELECT dblink_get_result('x') FROM nqe_safe_metric_view",
        "SELECT dblink_disconnect('x') FROM nqe_safe_metric_view",
    ):
        result = precheck_nqe_sql_safety(sql, {"allowed_tables": ["nqe_safe_metric_view"]}, "logistics")

        assert result["status"] == "reject"
        assert "dangerous_expression" in result["violations"]
        assert result["safe_sql"] == ""


def test_precheck_rejects_nested_subquery_comma_join_non_whitelisted_table() -> None:
    """嵌套子查询中的逗号连接也必须抽取每个对象，不能只校验外层 FROM。"""
    result = precheck_nqe_sql_safety(
        "SELECT metric_value FROM nqe_safe_metric_view "
        "WHERE EXISTS (SELECT 1 FROM nqe_safe_metric_view a, nqe_secret_metric_view b)",
        {"allowed_tables": ["nqe_safe_metric_view"]},
        "logistics",
    )

    assert result["status"] == "reject"
    assert "table_not_whitelisted" in result["violations"]
    assert "nqe_secret_metric_view" in result["referenced_tables"]


def test_graph_writes_safe_candidate_after_whitelisted_precheck() -> None:
    """Graph 安全预检通过后应写入安全候选和结构化预检结果。"""
    graph_module = importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")
    graph = graph_module.build_nqe_sql_agent_graph()

    final_state = graph.invoke(
        {
            "question": "查询本月发运量",
            "nqe_mode": "on",
            "retrieval_context_package": _safe_package(),
            "context_readiness": "pass",
        }
    )

    assert final_state["terminal_status"] == "completed"
    assert final_state["sql_safety_result"]["status"] == "pass"
    assert final_state["safe_sql_candidate"].endswith("LIMIT 200")


def test_safety_reject_still_records_trace_and_masks_user_response() -> None:
    """安全拒绝终态仍必须记录运行摘要，且用户回答不暴露内部技术词。"""
    graph_module = importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")
    graph = graph_module.build_nqe_sql_agent_graph()

    final_state = graph.invoke(
        {
            "question": "查询本月发运量",
            "nqe_mode": "on",
            "retrieval_context_package": _safe_package("SELECT metric_value FROM nqe_other_metric_view"),
            "context_readiness": "pass",
        }
    )
    node_names = _node_names(final_state)

    assert final_state["terminal_status"] == "safety_reject"
    assert node_names[-1] == "record_query_log_and_trace"
    assert "terminal_safety_reject" in node_names
    assert "table_not_whitelisted" in final_state["sql_safety_result"]["violations"]
    assert "safe_sql_candidate" not in final_state
    _assert_business_safe_text(final_state["user_visible_response"])


def test_correct_sql_returns_to_safety_precheck() -> None:
    """修正循环后必须重新经过安全预检，不能直接进入后续校验。"""
    graph_module = importlib.import_module("backend.app.domains.business_qa_graph.nqe_sql_agent_graph")
    graph = graph_module.build_nqe_sql_agent_graph()

    final_state = graph.invoke(
        {
            "question": "查询本月发运量",
            "nqe_mode": "on",
            "retrieval_context_package": _safe_package(),
            "context_readiness": "pass",
            "force_explain_fail": True,
        }
    )
    node_names = _node_names(final_state)

    assert final_state["terminal_status"] == "error"
    assert final_state["sql_revision_round"] == 2
    assert node_names.count("correct_sql") == 2
    assert node_names.count("precheck_sql_safety") == 3
    first_correct = node_names.index("correct_sql")
    assert node_names[first_correct + 1] == "precheck_sql_safety"

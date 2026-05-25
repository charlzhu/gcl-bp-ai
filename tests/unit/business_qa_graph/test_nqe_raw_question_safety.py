"""NQE raw question safety gate 单元测试。"""

import pytest
from backend.app.domains.business_qa_graph.nqe_raw_question_safety import check_raw_question_safety


def test_empty_question_not_blocked():
    r = check_raw_question_safety("")
    assert r["safe"] == False
    assert "empty_question" in r["matched_rules"]
    assert r["blocked_before_llm"] == False  # 空问题不归类为安全攻击

def test_empty_question_whitespace():
    r = check_raw_question_safety("   ")
    assert r["safe"] == False
    assert "empty_question" in r["matched_rules"]

def test_drop_table_blocked():
    r = check_raw_question_safety("DROP TABLE users")
    assert r["safe"] == False
    assert "drop_statement" in r["matched_rules"]
    assert r["blocked_before_llm"] == True

def test_update_table_set_blocked():
    r = check_raw_question_safety("UPDATE dws_logistics_detail_union SET name='x'")
    assert r["safe"] == False
    assert any("update" in m for m in r["matched_rules"])

def test_update_schema_table_blocked():
    r = check_raw_question_safety("UPDATE dbo.users SET name='x'")
    assert r["safe"] == False

def test_delete_from_blocked():
    r = check_raw_question_safety("DELETE FROM orders WHERE id=1")
    assert r["safe"] == False
    assert "delete_statement" in r["matched_rules"]

def test_delete_schema_table_blocked():
    r = check_raw_question_safety("DELETE FROM sales.orders WHERE id=1")
    assert r["safe"] == False

def test_information_schema_blocked():
    r = check_raw_question_safety("SELECT * FROM information_schema.tables")
    assert r["safe"] == False
    assert "system_schema_access" in r["matched_rules"]

def test_union_select_blocked():
    r = check_raw_question_safety("SELECT 1 UNION SELECT password FROM users")
    assert r["safe"] == False
    assert "union_injection" in r["matched_rules"]

def test_tautology_or_1_eq_1_blocked():
    r = check_raw_question_safety("SELECT * FROM users WHERE name='admin' OR 1=1")
    assert r["safe"] == False
    assert "tautology_injection" in r["matched_rules"]

def test_comment_dash_injection_blocked():
    r = check_raw_question_safety("SELECT * FROM users WHERE name='admin' --")
    assert r["safe"] == False
    assert any("comment_injection" in m for m in r["matched_rules"])

def test_comment_block_injection():
    r = check_raw_question_safety("SELECT /* hack */ * FROM users")
    assert r["safe"] == False
    assert any("comment_injection" in m for m in r["matched_rules"])

def test_comment_hash_injection():
    r = check_raw_question_safety("SELECT * FROM users # admin")
    assert r["safe"] == False
    assert any("comment_injection" in m for m in r["matched_rules"])

def test_multi_statement_injection():
    r = check_raw_question_safety("SELECT 1; DROP TABLE users")
    assert r["safe"] == False
    assert "multi_statement_injection" in r["matched_rules"]

# ====== Normal business questions must NOT be blocked ======

def test_normal_logistics_query():
    r = check_raw_question_safety("2024年运输记录数")
    assert r["safe"] == True

def test_normal_production_query():
    r = check_raw_question_safety("2024年组件产量")
    assert r["safe"] == True

def test_normal_bom_query():
    r = check_raw_question_safety("BOM订单明细")
    assert r["safe"] == True

def test_normal_power_query():
    r = check_raw_question_safety("功率模型版本")
    assert r["safe"] == True

def test_normal_chinese_delete_not_blocked():
    r = check_raw_question_safety("查询被删除的订单记录")
    assert r["safe"] == True, "中文'删除'不应被拦截"

def test_normal_chinese_update_not_blocked():
    r = check_raw_question_safety("查询更新后的BOM版本")
    assert r["safe"] == True, "中文'更新'不应被拦截"

def test_normal_with_numbers():
    r = check_raw_question_safety("2023年各月运输量")
    assert r["safe"] == True

def test_normal_origin_place():
    r = check_raw_question_safety("合肥到安徽的发运明细")
    assert r["safe"] == True

def test_regular_select_not_blocked():
    r = check_raw_question_safety("SELECT COUNT(*) FROM orders")
    assert r["safe"] == True, "正常的SELECT不应被拦截"


# ====== Graph-level routing tests ======

def test_empty_question_routes_to_clarify():
    """空问题在 graph 中路由到 clarify 终态，不进入 LLM/Milvus。"""
    from backend.app.domains.business_qa_graph.nqe_sql_agent_graph import build_nqe_sql_agent_graph
    g = build_nqe_sql_agent_graph()
    f = g.invoke({"question": "", "nqe_mode": "on", "domain_hint": "logistics", "trace_id": "empty-test"})
    assert f.get("terminal_status") in ("clarify", "clarify_required"), f"got {f.get('terminal_status')}"

def test_empty_question_not_enter_llm():
    """空问题不应生成 SQL。"""
    from backend.app.domains.business_qa_graph.nqe_sql_agent_graph import build_nqe_sql_agent_graph
    g = build_nqe_sql_agent_graph()
    f = g.invoke({"question": "", "nqe_mode": "on", "domain_hint": "logistics", "trace_id": "empty-llm"})
    assert not f.get("generated_sql"), "空问题不应调用 LLM 生成 SQL"

def test_drop_table_routes_to_safety_reject_graph():
    """DROP TABLE 在 graph 中路由到 safety_reject。"""
    from backend.app.domains.business_qa_graph.nqe_sql_agent_graph import build_nqe_sql_agent_graph
    g = build_nqe_sql_agent_graph()
    f = g.invoke({"question": "DROP TABLE users", "nqe_mode": "on", "domain_hint": "logistics", "trace_id": "drop-test"})
    assert f.get("terminal_status") == "safety_reject"

def test_drop_table_not_generated_sql():
    """DROP TABLE 不应进入 SQL 生成路径。"""
    from backend.app.domains.business_qa_graph.nqe_sql_agent_graph import build_nqe_sql_agent_graph
    g = build_nqe_sql_agent_graph()
    f = g.invoke({"question": "DROP TABLE users", "nqe_mode": "on", "domain_hint": "logistics", "trace_id": "drop-sql"})
    assert not f.get("generated_sql"), "危险问题不应生成 SQL"

def test_normal_question_passes_graph():
    """正常问题通过 raw safety gate。"""
    from backend.app.domains.business_qa_graph.nqe_sql_agent_graph import build_nqe_sql_agent_graph
    g = build_nqe_sql_agent_graph()
    f = g.invoke({"question": "2024年运输记录数", "nqe_mode": "on", "domain_hint": "logistics", "trace_id": "normal-test"})
    assert f.get("terminal_status") == "completed"

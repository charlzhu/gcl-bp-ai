"""
gcl-bp-ai 统一问数 Graph（v2 融合版）。

融合骨架层领域路由 + 掌柜对齐层 catalog-driven SQL 生成，单 Graph 全流程：
  receive → domain_route(LLM语义) → extract_keywords
  → 并行三路recall → merge → 并行filter
  → add_extra_context → generate_sql(LLM直接出SQL) → validate_sql
  → 循环: [correct_sql → validate_sql] ≤3次 → execute_sql → END
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from backend.app.domains.business_qa_graph.nodes.add_extra_context_node import add_extra_context_node
from backend.app.domains.business_qa_graph.nodes.clarify_node import clarify_node
from backend.app.domains.business_qa_graph.nodes.correct_sql_node import correct_sql_node
from backend.app.domains.business_qa_graph.nodes.domain_route_node import domain_route_node
from backend.app.domains.business_qa_graph.nodes.error_node import error_node
from backend.app.domains.business_qa_graph.nodes.execute_sql_node import execute_sql_node
from backend.app.domains.business_qa_graph.nodes.extract_keywords_node import extract_keywords_node
from backend.app.domains.business_qa_graph.nodes.filter_metric_node import filter_metric_node
from backend.app.domains.business_qa_graph.nodes.filter_table_node import filter_table_node
from backend.app.domains.business_qa_graph.nodes.generate_sql_node import generate_sql_node
from backend.app.domains.business_qa_graph.nodes.merge_retrieved_info_node import merge_retrieved_info_node
from backend.app.domains.business_qa_graph.nodes.recall_column_node import recall_column_node
from backend.app.domains.business_qa_graph.nodes.recall_metric_node import recall_metric_node
from backend.app.domains.business_qa_graph.nodes.recall_value_node import recall_value_node
from backend.app.domains.business_qa_graph.nodes.receive_node import receive_node
from backend.app.domains.business_qa_graph.nodes.validate_sql_node import validate_sql_node
from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState


# ---- 路由函数 ----

def _route_after_domain(state: BusinessQaGraphState) -> str:
    """domain 路由分发：known → extract_keywords，unknown → clarify。"""
    domain = state.get("domain", "unknown")
    status = state.get("status", "")
    if domain == "unknown" or status == "CLARIFY":
        return "clarify"
    return "extract_keywords"


def _route_after_validate_sql(state: BusinessQaGraphState) -> str:
    """SQL 验证分发：成功 → execute，失败 → correct（最多 3 次）。"""
    error = state.get("error")
    if not error:
        return "execute_sql"
    retry_count = state.get("_sql_retry_count", 0)
    if retry_count < 3:
        state["_sql_retry_count"] = retry_count + 1
        return "correct_sql"
    return "error_handler"


# ---- Graph 构建 ----

def build_unified_graph(
    *,
    db_session: Any = None,
):
    """构建 13 节点统一问数 Graph（v2 融合版）。

    参数：
        db_session: 可选的 SQLAlchemy 数据库会话，注入到初始 state 和 execute_sql。
    返回：
        已 compile 的 LangGraph graph。
    """
    graph = StateGraph(BusinessQaGraphState)

    # ================================================================
    # 注册全部 13 个节点（骨架层 + 掌柜对齐层）
    # ================================================================
    graph.add_node("receive", receive_node)
    graph.add_node("domain_route", domain_route_node)
    graph.add_node("extract_keywords", extract_keywords_node)
    # 三路并行召回
    graph.add_node("recall_column", recall_column_node)
    graph.add_node("recall_value", recall_value_node)
    graph.add_node("recall_metric", recall_metric_node)
    # 合并 + 过滤
    graph.add_node("merge_retrieved_info", merge_retrieved_info_node)
    graph.add_node("filter_table", filter_table_node)
    graph.add_node("filter_metric", filter_metric_node)
    # 上下文
    graph.add_node("add_extra_context", add_extra_context_node)
    # SQL 生成 / 验证 / 校正 / 执行
    graph.add_node("generate_sql", generate_sql_node)
    graph.add_node("validate_sql", validate_sql_node)
    graph.add_node("correct_sql", correct_sql_node)
    graph.add_node("execute_sql", execute_sql_node)
    # 终端节点
    graph.add_node("clarify", clarify_node)
    graph.add_node("error_handler", error_node)

    # ================================================================
    # 线性主线: START → receive → domain_route
    # ================================================================
    graph.add_edge(START, "receive")
    graph.add_edge("receive", "domain_route")

    # ================================================================
    # 条件路由: domain_route → extract_keywords 或 clarify
    # ================================================================
    graph.add_conditional_edges(
        "domain_route",
        _route_after_domain,
        {"extract_keywords": "extract_keywords", "clarify": "clarify"},
    )

    # ================================================================
    # 三路并行召回: extract_keywords → recall_column / recall_value / recall_metric
    # ================================================================
    graph.add_edge("extract_keywords", "recall_column")
    graph.add_edge("extract_keywords", "recall_value")
    graph.add_edge("extract_keywords", "recall_metric")

    # ================================================================
    # 合并三路召回 → 并行过滤
    # ================================================================
    graph.add_edge("recall_column", "merge_retrieved_info")
    graph.add_edge("recall_value", "merge_retrieved_info")
    graph.add_edge("recall_metric", "merge_retrieved_info")

    graph.add_edge("merge_retrieved_info", "filter_table")
    graph.add_edge("merge_retrieved_info", "filter_metric")

    # ================================================================
    # 过滤后汇流: add_extra_context → generate_sql
    # ================================================================
    graph.add_edge("filter_table", "add_extra_context")
    graph.add_edge("filter_metric", "add_extra_context")
    graph.add_edge("add_extra_context", "generate_sql")

    # ================================================================
    # SQL 链路: generate_sql → validate_sql → 条件(execute/correct)
    # ================================================================
    graph.add_edge("generate_sql", "validate_sql")

    graph.add_conditional_edges(
        "validate_sql",
        _route_after_validate_sql,
        {
            "execute_sql": "execute_sql",
            "correct_sql": "correct_sql",
            "error_handler": "error_handler",
        },
    )
    # correct_sql 修正后回到 validate_sql（循环）
    graph.add_edge("correct_sql", "validate_sql")

    # ================================================================
    # 执行 → END，终端节点 → END
    # ================================================================
    graph.add_edge("execute_sql", END)
    graph.add_edge("clarify", END)
    graph.add_edge("error_handler", END)

    return graph.compile()


# ---- 兼容旧接口 ----

def build_business_qa_graph(
    *,
    logistics_service: Any = None,
    plan_bom_service: Any = None,
):
    """兼容旧接口：调用新 build_unified_graph。"""
    return build_unified_graph()

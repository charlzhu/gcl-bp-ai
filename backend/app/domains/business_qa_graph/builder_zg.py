"""
掌柜问数对齐版 LangGraph Builder（12 节点）。

完全对齐掌柜问数 data-agent/app/agent/graph.py 的流程结构：

START
  → extract_keywords
  → 并行: recall_column / recall_value / recall_metric
  → merge_retrieved_info
  → 并行: filter_table / filter_metric
  → add_extra_context
  → generate_sql
  → validate_sql
  → 条件: execute_sql (成功) / correct_sql (失败)
  → execute_sql → END

技术栈保留 gcl-bp-ai 现有:
- 向量库: Milvus (非 Qdrant)
- 维度值检索: SQL 中间库 (非 ES)
- SQL 生成: 受控 SQLPlan (非 LLM 自由 SQL)
- 安全校验: AST + candidate gate + safety checker + EXPLAIN smoke
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from backend.app.domains.business_qa_graph.nodes.extract_keywords_node import extract_keywords_node
from backend.app.domains.business_qa_graph.nodes.recall_column_node import recall_column_node
from backend.app.domains.business_qa_graph.nodes.recall_metric_node import recall_metric_node
from backend.app.domains.business_qa_graph.nodes.recall_value_node import recall_value_node
from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState
from backend.app.domains.business_qa_graph.schemas.zg_state import ZG_BUSINESS_QA_GRAPH_VERSION

# Phase 2/3 节点延迟导入（先声明接口，后续实现后自动激活）
try:
    from backend.app.domains.business_qa_graph.nodes.merge_retrieved_info_node import merge_retrieved_info_node
except ImportError:
    merge_retrieved_info_node = None  # type: ignore[assignment]

try:
    from backend.app.domains.business_qa_graph.nodes.filter_table_node import filter_table_node
except ImportError:
    filter_table_node = None  # type: ignore[assignment]

try:
    from backend.app.domains.business_qa_graph.nodes.filter_metric_node import filter_metric_node
except ImportError:
    filter_metric_node = None  # type: ignore[assignment]

try:
    from backend.app.domains.business_qa_graph.nodes.add_extra_context_node import add_extra_context_node
except ImportError:
    add_extra_context_node = None  # type: ignore[assignment]

try:
    from backend.app.domains.business_qa_graph.nodes.generate_sql_node import generate_sql_node
except ImportError:
    generate_sql_node = None  # type: ignore[assignment]

try:
    from backend.app.domains.business_qa_graph.nodes.validate_sql_node import validate_sql_node
except ImportError:
    validate_sql_node = None  # type: ignore[assignment]

try:
    from backend.app.domains.business_qa_graph.nodes.correct_sql_node import correct_sql_node
except ImportError:
    correct_sql_node = None  # type: ignore[assignment]

try:
    from backend.app.domains.business_qa_graph.nodes.execute_sql_node import execute_sql_node
except ImportError:
    execute_sql_node = None  # type: ignore[assignment]


def _route_after_validate_sql(state: dict[str, Any]) -> str:
    """validate_sql 之后的条件路由（与掌柜问数完全一致）。

    参数：
        state: 当前 Graph 运行态。
    返回：
        "execute_sql" 或 "correct_sql"。
    业务逻辑：
        SQL 校验通过 → 执行 SQL；
        SQL 校验失败 → 进入校正节点。
    """
    error = state.get("error")
    if error is None:
        return "execute_sql"
    return "correct_sql"


def build_zg_business_qa_graph() -> Any:
    """构建掌柜问数对齐版 12 节点 LangGraph。

    返回：
        已 compile 的 LangGraph graph。

    节点映射（掌柜问数 → gcl-bp-ai）：

    | 掌柜节点 | gcl-bp-ai 节点 | 说明 |
    |---------|---------------|------|
    | extract_keywords | extract_keywords_node | jieba 分词 |
    | recall_column | recall_column_node | Milvus 向量检索字段/维度 |
    | recall_value | recall_value_node | SQL 查询中间库维度表 |
    | recall_metric | recall_metric_node | Milvus 向量检索指标 |
    | merge_retrieved_info | merge_retrieved_info_node | 合并 + JOIN 发现 |
    | filter_table | filter_table_node | LLM 过滤表/字段 |
    | filter_metric | filter_metric_node | LLM 过滤指标 |
    | add_extra_context | add_extra_context_node | 日期 + DB 方言 |
    | generate_sql | generate_sql_node | **受控 SQLPlan**（非自由 SQL）|
    | validate_sql | validate_sql_node | EXPLAIN 验证 |
    | correct_sql | correct_sql_node | SQLPlan repair |
    | execute_sql | execute_sql_node | 执行并返回 |
    """
    graph = StateGraph(BusinessQaGraphState)

    # ============================================================
    # 注册所有节点
    # ============================================================

    graph.add_node("extract_keywords", extract_keywords_node)
    graph.add_node("recall_column", recall_column_node)
    graph.add_node("recall_value", recall_value_node)
    graph.add_node("recall_metric", recall_metric_node)

    # Phase 2/3 节点：如果已实现则注册，否则用 pass-through 占位
    if merge_retrieved_info_node:
        graph.add_node("merge_retrieved_info", merge_retrieved_info_node)
    else:
        graph.add_node("merge_retrieved_info", _passthrough_node("合并召回信息"))

    if filter_table_node:
        graph.add_node("filter_table", filter_table_node)
    else:
        graph.add_node("filter_table", _passthrough_node("过滤表格"))

    if filter_metric_node:
        graph.add_node("filter_metric", filter_metric_node)
    else:
        graph.add_node("filter_metric", _passthrough_node("过滤指标"))

    if add_extra_context_node:
        graph.add_node("add_extra_context", add_extra_context_node)
    else:
        graph.add_node("add_extra_context", _passthrough_node("添加额外上下文信息"))

    if generate_sql_node:
        graph.add_node("generate_sql", generate_sql_node)
    else:
        graph.add_node("generate_sql", _passthrough_node("生成SQL"))

    if validate_sql_node:
        graph.add_node("validate_sql", validate_sql_node)
    else:
        graph.add_node("validate_sql", _passthrough_node("验证SQL"))

    if correct_sql_node:
        graph.add_node("correct_sql", correct_sql_node)
    else:
        graph.add_node("correct_sql", _passthrough_node("校正SQL"))

    if execute_sql_node:
        graph.add_node("execute_sql", execute_sql_node)
    else:
        graph.add_node("execute_sql", _passthrough_node("执行SQL"))

    # ============================================================
    # 连线：完全对齐掌柜问数 graph.py 的边结构
    # ============================================================

    # START → extract_keywords
    graph.add_edge(START, "extract_keywords")

    # extract_keywords → 三路并行召回（与掌柜问数完全一致）
    graph.add_edge("extract_keywords", "recall_column")
    graph.add_edge("extract_keywords", "recall_value")
    graph.add_edge("extract_keywords", "recall_metric")

    # 三路召回 → merge_retrieved_info
    graph.add_edge("recall_column", "merge_retrieved_info")
    graph.add_edge("recall_value", "merge_retrieved_info")
    graph.add_edge("recall_metric", "merge_retrieved_info")

    # merge_retrieved_info → 并行过滤（与掌柜问数完全一致）
    graph.add_edge("merge_retrieved_info", "filter_table")
    graph.add_edge("merge_retrieved_info", "filter_metric")

    # 过滤 → add_extra_context
    graph.add_edge("filter_table", "add_extra_context")
    graph.add_edge("filter_metric", "add_extra_context")

    # add_extra_context → generate_sql
    graph.add_edge("add_extra_context", "generate_sql")

    # generate_sql → validate_sql
    graph.add_edge("generate_sql", "validate_sql")

    # validate_sql → 条件路由（与掌柜问数完全一致）
    graph.add_conditional_edges(
        "validate_sql",
        _route_after_validate_sql,
        {
            "execute_sql": "execute_sql",
            "correct_sql": "correct_sql",
        },
    )

    # correct_sql → execute_sql（校正后重新执行）
    graph.add_edge("correct_sql", "execute_sql")

    # execute_sql → END
    graph.add_edge("execute_sql", END)

    return graph.compile()


def _passthrough_node(step_name: str):
    """生成占位直通节点（Phase 未实现时的临时节点）。

    参数：
        step_name: 步骤名称，用于日志。
    返回：
        可注册到 LangGraph 的直通函数。
    """
    import logging
    _logger = logging.getLogger(__name__)

    def _passthrough(state: dict[str, Any]) -> dict[str, Any]:
        _logger.info("zg_passthrough step=%s", step_name)
        return {}
    return _passthrough

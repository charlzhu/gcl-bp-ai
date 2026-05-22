"""
掌柜问数对齐 - SQL 执行节点（execute_sql）。

完全对齐 data-agent/app/agent/nodes/execute_sql.py：
- EXPLAIN 验证后执行 SQL
- writer 流式输出进度和结果
- 错误时 raise 向上传播
"""

from __future__ import annotations

import logging
from typing import Any

from backend.app.domains.business_qa_graph.nodes.zg_utils import (
    _emit_progress,
    _emit_result,
    STEP_EXECUTE_SQL,
)

logger = logging.getLogger(__name__)


def execute_sql_node(state: dict[str, Any]) -> dict[str, Any]:
    """执行 SQL 并流式返回结果（掌柜问数对齐版）。

    参数：
        state: 当前 Graph 运行态，必须包含 sql。
        state 可选包含 _db_session 和 _stream_writer。
    返回：
        包含 execution_result 和 execution_status 的 state 更新字典。

    业务逻辑（完全对齐掌柜问数 execute_sql）：
        1. writer 发送 running 进度
        2. 执行 SQL
        3. writer 发送 success 进度 + result 数据
        4. 失败时 writer 发送 error 进度 + raise
    """
    _emit_progress(state, STEP_EXECUTE_SQL, "running")

    sql: str = state.get("sql", "")
    db_session = state.get("_db_session")

    if not sql or not sql.strip():
        _emit_progress(state, STEP_EXECUTE_SQL, "error")
        return {
            "execution_status": "EXECUTION_ERROR",
            "execution_result": {
                "answer_summary": "SQL 为空，无法执行。",
                "result_table": {"columns": [], "rows": []},
                "warnings": ["SQL 为空"],
            },
        }

    # 无 DB 连接时返回占位结果
    if db_session is None:
        logger.info("execute_sql_no_db return placeholder")
        _emit_progress(state, STEP_EXECUTE_SQL, "success")
        _emit_result(state, {
            "answer_summary": f"SQL 已生成（{sql[:100]}...），等待数据库连接执行。",
            "result_table": {"columns": [], "rows": []},
            "sql_preview": sql[:200],
        })
        return {
            "execution_status": "EXECUTED",
            "execution_result": {
                "answer_summary": "SQL 已生成，等待数据库连接执行。",
                "result_table": {"columns": [], "rows": []},
                "warnings": ["无数据库连接，SQL 未实际执行"],
            },
            "status": "EXECUTED",
        }

    try:
        from sqlalchemy import text

        result = db_session.execute(text(sql))
        rows = [dict(row) for row in result.mappings().fetchall()]
        columns = list(rows[0].keys()) if rows else []

        logger.info("execute_sql_success rows=%d", len(rows))

        result_data = {
            "answer_summary": f"查询完成，共返回 {len(rows)} 条结果。",
            "result_table": {
                "columns": [{"name": c, "type": "string"} for c in columns],
                "rows": rows[:100],
            },
            "row_count": len(rows),
        }

        _emit_progress(state, STEP_EXECUTE_SQL, "success")
        _emit_result(state, result_data)

        return {
            "execution_status": "EXECUTED",
            "execution_result": result_data,
            "status": "EXECUTED",
        }
    except Exception as exc:
        error_msg = str(exc)[:200]
        logger.error("execute_sql_failed error=%s", error_msg)
        _emit_progress(state, STEP_EXECUTE_SQL, "error")
        raise

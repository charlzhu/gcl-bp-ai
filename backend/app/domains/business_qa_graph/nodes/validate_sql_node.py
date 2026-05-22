"""
掌柜问数对齐 - SQL 验证节点（validate_sql）。

完全对齐 data-agent/app/agent/nodes/validate_sql.py：
- EXPLAIN SQL 验证语法
- writer 流式进度
- 失败返回 error 字符串供 correct_sql 使用
"""

from __future__ import annotations

import logging
from typing import Any

from backend.app.domains.business_qa_graph.nodes.zg_utils import (
    _emit_progress,
    STEP_VALIDATE_SQL,
)

logger = logging.getLogger(__name__)


def validate_sql_node(state: dict[str, Any]) -> dict[str, Any]:
    """验证 SQL 语法（掌柜问数对齐版）。"""
    _emit_progress(state, STEP_VALIDATE_SQL, "running")

    sql: str = state.get("sql", "")
    db_session = state.get("_db_session")

    if not sql or not sql.strip():
        _emit_progress(state, STEP_VALIDATE_SQL, "error")
        return {"error": "SQL 为空，无法验证。"}

    # 无 DB 连接时跳过验证（标记为无错误，让 execute_sql 兜底）
    if db_session is None:
        logger.info("validate_sql_no_db skip validation")
        _emit_progress(state, STEP_VALIDATE_SQL, "success")
        return {"error": None}

    try:
        from sqlalchemy import text
        db_session.execute(text(f"EXPLAIN {sql}"))
        logger.info("validate_sql_success")
        _emit_progress(state, STEP_VALIDATE_SQL, "success")
        return {"error": None}

    except Exception as exc:
        error_str = str(exc)[:500]
        logger.error("validate_sql_failed error=%s", error_str)
        _emit_progress(state, STEP_VALIDATE_SQL, "error")
        return {"error": error_str}

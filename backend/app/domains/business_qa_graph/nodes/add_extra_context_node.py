"""
掌柜问数对齐 - 添加额外上下文节点（add_extra_context）。

完全对齐 data-agent/app/agent/nodes/add_extra_context.py：
- 日期/星期/季度 + DB 方言
- writer 流式进度
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from backend.app.domains.business_qa_graph.nodes.zg_utils import (
    _emit_progress,
    STEP_ADD_CONTEXT,
)

logger = logging.getLogger(__name__)


def add_extra_context_node(state: dict[str, Any]) -> dict[str, Any]:
    """添加额外上下文信息（掌柜问数对齐版）。"""
    _emit_progress(state, STEP_ADD_CONTEXT, "running")

    try:
        today = datetime.today()
        date_info = {
            "date": today.strftime("%Y-%m-%d"),
            "weekday": today.strftime("%A"),
            "quarter": f"Q{(today.month - 1) // 3 + 1}",
            "year": today.year,
            "month": today.month,
        }
        db_session = state.get("_db_session")
        db_info = _get_db_info(db_session)

        logger.info("add_extra_context date=%s", date_info["date"])
        _emit_progress(state, STEP_ADD_CONTEXT, "success")
        return {"date_info": date_info, "db_info": db_info}

    except Exception as exc:
        logger.error("add_extra_context_failed error=%s", exc)
        _emit_progress(state, STEP_ADD_CONTEXT, "error")
        raise


def _get_db_info(db_session: Any = None) -> dict[str, Any]:
    if db_session is None:
        return {"dialect": "mysql", "version": "8.0"}
    try:
        from sqlalchemy import text
        result = db_session.execute(text("SELECT VERSION()"))
        version = result.scalar()
        dialect = db_session.get_bind().dialect.name
        return {"dialect": dialect, "version": str(version) if version else "unknown"}
    except Exception:
        return {"dialect": "mysql", "version": "8.0"}

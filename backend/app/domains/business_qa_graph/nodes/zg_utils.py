"""
掌柜问数对齐 - 节点共享工具。

提供所有节点共用的 _emit_progress 函数，
用于向 LangGraph custom stream writer 发送 SSE 进度事件。
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

# 进度步骤名称常量（与掌柜问数完全一致）
STEP_EXTRACT_KEYWORDS = "抽取关键字"
STEP_RECALL_COLUMN = "召回字段"
STEP_RECALL_VALUE = "召回字段取值"
STEP_RECALL_METRIC = "召回指标"
STEP_MERGE = "合并召回信息"
STEP_FILTER_TABLE = "过滤表格"
STEP_FILTER_METRIC = "过滤指标"
STEP_ADD_CONTEXT = "添加额外上下文信息"
STEP_GENERATE_SQL = "生成SQL"
STEP_VALIDATE_SQL = "验证SQL"
STEP_CORRECT_SQL = "校正SQL"
STEP_EXECUTE_SQL = "执行SQL"


def _emit_progress(state: dict[str, Any], step: str, status: str) -> None:
    """向 LangGraph stream writer 发送进度事件（与掌柜问数格式完全一致）。

    参数：
        state: 当前 Graph 运行态，需包含 _stream_writer 回调。
        step: 步骤名称，如 "抽取关键字"。
        status: 状态，running / success / error。
    """
    writer: Callable | None = state.get("_stream_writer")
    if writer is None:
        return
    try:
        writer({"type": "progress", "step": step, "status": status})
    except Exception:
        # writer 异常不应中断节点执行
        pass


def _emit_result(state: dict[str, Any], data: dict[str, Any]) -> None:
    """向 LangGraph stream writer 发送结果事件。

    参数：
        state: 当前 Graph 运行态。
        data: 查询结果字典。
    """
    writer: Callable | None = state.get("_stream_writer")
    if writer is None:
        return
    try:
        writer({"type": "result", "data": data})
    except Exception:
        pass

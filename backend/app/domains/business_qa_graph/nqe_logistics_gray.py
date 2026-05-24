"""NQE 统一 SQL Agent 物流域灰度接入。

本模块为物流正式问答入口提供 off/shadow/assist/on 四态灰度切换能力，
不删除旧 LogisticsDataQaService、不修改旧链路主逻辑。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


def get_nqe_logistics_mode() -> str:
    """读取当前物流 NQE 灰度模式。

    返回 "off" / "shadow" / "assist" / "on" 之一。
    默认值由 Settings.nqe_logistics_mode 控制（默认 "off"）。
    """
    try:
        return get_settings().nqe_logistics_mode
    except Exception:
        return "off"


def run_nqe_logistics_graph(
    question: str, trace_id: str = "", *, domain_hint: str = "logistics", nqe_mode: str = "shadow"
) -> dict[str, Any]:
    """执行 NQE SQL Agent Graph 并返回脱敏运行结果。

    参数：
        question: 用户原始问题。
        trace_id: 查询追踪号。
        domain_hint: 业务域提示（默认 logistics）。
        nqe_mode: NQE 运行模式（默认 shadow，调用方应在 off 时跳过本函数）。
    返回：
        包含 terminal_status、selected_domain、nqe_mode 等字段的脱敏结果字典。
        失败时返回 {"terminal_status": "error", "error": str(exc)}。
    """
    try:
        from backend.app.domains.business_qa_graph.nqe_sql_agent_graph import (
            build_nqe_sql_agent_graph,
        )

        graph = build_nqe_sql_agent_graph()
        final_state = graph.invoke(
            {
                "question": question,
                "nqe_mode": nqe_mode,
                "domain_hint": domain_hint,
                "trace_id": trace_id,
            }
        )
        return {
            "terminal_status": final_state.get("terminal_status", "unknown"),
            "selected_domain": final_state.get("selected_domain"),
            "nqe_mode": final_state.get("nqe_mode"),
            "context_readiness": final_state.get("context_readiness"),
            "sql_safety_status": (
                final_state.get("sql_safety_result", {}).get("status")
                if isinstance(final_state.get("sql_safety_result"), dict)
                else None
            ),
            "explain_status": (
                final_state.get("explain_result", {}).get("status")
                if isinstance(final_state.get("explain_result"), dict)
                else None
            ),
            "execution_status": final_state.get("execution_status"),
            "trace_steps_count": len(final_state.get("trace_steps", [])),
            "user_response_truncated": _truncate_user_response(final_state.get("user_visible_response", "")),
        }
    except Exception as exc:
        logger.warning("NQE logistics graph execution failed: %s", exc)
        return {"terminal_status": "error", "error": str(exc)}


def build_nqe_shadow_compare_record(
    question: str,
    trace_id: str,
    *,
    old_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构建 NQE shadow compare 记录。

    参数：
        question: 用户原始问题。
        trace_id: 查询追踪号。
        old_result: 旧链路返回结果（可选）。
    返回：
        shadow compare 脱敏字典。
    """
    nqe_start = time.monotonic()
    nqe_result = run_nqe_logistics_graph(question, trace_id, nqe_mode="shadow")
    nqe_elapsed_ms = int((time.monotonic() - nqe_start) * 1000)

    old_status = "unknown"
    old_row_count = None
    if old_result and isinstance(old_result, dict):
        status_info = old_result.get("status")
        if isinstance(status_info, dict):
            old_status = status_info.get("code", "unknown")
        old_row_count = old_result.get("row_count")

    return {
        "trace_id": trace_id,
        "question_truncated": _truncate_question(question),
        "nqe_elapsed_ms": nqe_elapsed_ms,
        "nqe_terminal_status": nqe_result.get("terminal_status"),
        "nqe_selected_domain": nqe_result.get("selected_domain"),
        "nqe_sql_safety_status": nqe_result.get("sql_safety_status"),
        "nqe_explain_status": nqe_result.get("explain_status"),
        "nqe_execution_status": nqe_result.get("execution_status"),
        "nqe_trace_steps_count": nqe_result.get("trace_steps_count"),
        "old_status": old_status,
        "old_row_count": old_row_count,
        "nqe_error": nqe_result.get("error"),
    }


def _truncate_user_response(text: str, max_len: int = 200) -> str:
    """截断用户可见文本，避免在 shadow 记录中存储过长回答。"""
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    return text[:max_len] + ("…" if len(text) > max_len else "")


def _truncate_question(text: str, max_len: int = 500) -> str:
    """截断用户问题文本。"""
    if not text:
        return ""
    return text[:max_len] + ("…" if len(text) > max_len else "")

"""NQE 统一 SQL Agent 物流域灰度接入。

本模块为物流正式问答入口提供 off/shadow/assist/on 四态灰度切换能力，
不删除旧 LogisticsDataQaService、不修改旧链路主逻辑。

NQE-SQL-MAIN-17: 完善 fallback 与 shadow compare 记录。
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)

# ── shadow compare 比较状态枚举 ──
COMPARISON_NQE_SUCCESS = "nqe_success"
COMPARISON_NQE_FAILED = "nqe_failed"
COMPARISON_NQE_BLOCKED_BY_SAFETY = "nqe_blocked_by_safety"
COMPARISON_NQE_EXPLAIN_FAILED = "nqe_explain_failed"
COMPARISON_NQE_EMPTY_RESULT = "nqe_empty_result"
COMPARISON_NQE_TIMEOUT = "nqe_timeout"
COMPARISON_NQE_GRAPH_ERROR = "nqe_graph_error"


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
        包含 terminal_status、selected_domain 等字段的脱敏结果字典。
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
        explain_violations = None
        if isinstance(final_state.get("explain_result"), dict):
            explain_violations = final_state["explain_result"].get("violations")
        safety_violations = None
        if isinstance(final_state.get("sql_safety_result"), dict):
            safety_violations = final_state["sql_safety_result"].get("violations")

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
            "safety_violations": safety_violations,
            "explain_status": (
                final_state.get("explain_result", {}).get("status")
                if isinstance(final_state.get("explain_result"), dict)
                else None
            ),
            "explain_violations": explain_violations,
            "execution_status": final_state.get("execution_status"),
            "trace_steps_count": len(final_state.get("trace_steps", [])),
            "sql_revision_round": final_state.get("sql_revision_round", 0),
            "user_response_truncated": _truncate_user_response(final_state.get("user_visible_response", "")),
        }
    except Exception as exc:
        logger.warning("NQE logistics graph execution failed: %s", exc)
        return {"terminal_status": "graph_error", "error": str(exc)}


def _determine_comparison_status(nqe_result: dict[str, Any]) -> str:
    """根据 NQE 运行结果判断比较状态。

    参数：
        nqe_result: run_nqe_logistics_graph 返回的结果字典。
    返回：
        COMPARISON_NQE_* 常量之一。
    业务逻辑：
        按优先级判断：图形错误 > 安全拦截 > 解释失败 > 成功/失败。
    """
    terminal = nqe_result.get("terminal_status", "unknown")

    if terminal == "graph_error":
        return COMPARISON_NQE_GRAPH_ERROR
    if terminal == "safety_reject":
        return COMPARISON_NQE_BLOCKED_BY_SAFETY
    if terminal == "error":
        explain_status = nqe_result.get("explain_status")
        if explain_status == "fail":
            return COMPARISON_NQE_EXPLAIN_FAILED
        return COMPARISON_NQE_FAILED
    if terminal in ("completed",):
        return COMPARISON_NQE_SUCCESS
    return COMPARISON_NQE_FAILED


def build_nqe_shadow_compare_record(
    question: str,
    trace_id: str,
    *,
    old_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构建 NQE shadow compare 脱敏记录。

    参数：
        question: 用户原始问题。
        trace_id: 查询追踪号。
        old_result: 旧链路返回结果（可选）。
    返回：
        shadow compare 脱敏字典，包含 NQE/旧链路双方摘要、比较状态、时间戳。

    安全边界：
        - 不记录密钥、连接串、敏感凭证。
        - user_query 和 nqe_sql_summary 均做脱敏截断。
        - 不把内部 SQL/表名/字段名暴露给普通用户（仅用于审计）。
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

    comparison_status = _determine_comparison_status(nqe_result)

    return {
        "trace_id": trace_id,
        "domain": "logistics",
        "mode": "shadow",
        "user_query": _truncate_question(question, max_len=300),
        "legacy_status": old_status,
        "legacy_row_count": old_row_count,
        "nqe_status": nqe_result.get("terminal_status"),
        "nqe_sql_safety": nqe_result.get("sql_safety_status"),
        "nqe_explain": nqe_result.get("explain_status"),
        "nqe_execution": nqe_result.get("execution_status"),
        "nqe_selected_domain": nqe_result.get("selected_domain"),
        "nqe_duration_ms": nqe_elapsed_ms,
        "nqe_error": nqe_result.get("error"),
        "nqe_safety_violations": nqe_result.get("safety_violations"),
        "nqe_explain_violations": nqe_result.get("explain_violations"),
        "nqe_trace_steps": nqe_result.get("trace_steps_count"),
        "nqe_sql_revision_round": nqe_result.get("sql_revision_round"),
        "comparison_status": comparison_status,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ── fallback 行为说明（NQE-SQL-MAIN-17 文档） ──


FALLBACK_BEHAVIOR = {
    "off": "不调用 NQE，完全走旧物流链路。",
    "shadow": "旧链路返回用户结果；NQE 后台执行并记录 shadow compare。NQE 失败不影响用户。",
    "assist": "接口预留。NQE 参与辅助，失败时 fallback 旧链路。（NQE-17 未完整实现）",
    "on": "接口预留。NQE 作为主链路，旧链路 fallback。（NQE-17 未完整实现）",
}

FALLBACK_SCENARIOS = {
    COMPARISON_NQE_SUCCESS: "NQE 成功生成并校验 SQL。结果记录在 shadow compare 中。",
    COMPARISON_NQE_BLOCKED_BY_SAFETY: "NQE SQL 被安全预检拒绝（如 DDL/DML/非白名单表）。用户不受影响，继续走旧链路。",
    COMPARISON_NQE_EXPLAIN_FAILED: "NQE SQL 解释校验失败（如未知字段/SELECT *）。用户不受影响，继续走旧链路。",
    COMPARISON_NQE_GRAPH_ERROR: "NQE Graph 执行异常。用户不受影响，异常摘要记录在 shadow compare 中。",
    COMPARISON_NQE_FAILED: "NQE 执行失败（非安全/解释原因）。用户不受影响，继续走旧链路。",
    COMPARISON_NQE_EMPTY_RESULT: "NQE 返回空结果。用户不受影响，继续走旧链路。",
    COMPARISON_NQE_TIMEOUT: "NQE 执行超时。用户不受影响，继续走旧链路。（超时未在本卡中显式设置阈值）",
}


# ── 辅助函数 ──


def _truncate_user_response(text: str, max_len: int = 200) -> str:
    """截断用户可见文本。"""
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    return text[:max_len] + ("…" if len(text) > max_len else "")


def _truncate_question(text: str, max_len: int = 500) -> str:
    """截断用户问题文本。"""
    if not text:
        return ""
    return text[:max_len] + ("…" if len(text) > max_len else "")

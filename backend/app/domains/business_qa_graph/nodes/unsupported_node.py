"""LQG-4 unsupported_node：生成业务化拒答消息。

本节点读取 plan_validate_node 写入的 validation_details，生成用户可见的业务化拒答。
绝对禁止在输出中暴露 SQL、表名、字段名、query_key、planner、guardrail、schema、
raw/debug、LLM 等技术内容。
"""

from __future__ import annotations

import re

from backend.app.domains.business_qa_graph.schemas.event import BusinessQaGraphEvent
from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState

# 需要在用户可见消息中剔除的技术关键词（大小写不敏感）
_SANITIZE_PATTERNS = [
    r"\bSQL\b",
    r"\bSELECT\b",
    r"\bDROP\b",
    r"\bINSERT\b",
    r"\bDELETE\b",
    r"\bUNION\b",
    r"\bTABLE\b",
    r"\bquery_key\b",
    r"\bSQLPlan\b",
    r"\bguardrail\b",
    r"\bschema\b",
    r"\bplanner\b",
    r"\brawResponse\b",
    r"\bdebug\b",
    r"\bllm_prompt\b",
    r"\blogistics_[a-z_]+\b",
]
"""用户可见消息中需剔除的技术关键词模式。"""


def _sanitize_unsupported_reason(reason: str) -> str:
    """清理内部技术标识，确保用户可见消息业务化。

    参数：
        reason: 内部审计用的 unsupported_reason（可能包含技术关键词）。
    返回：
        清理后适合用户可见的消息。
    业务逻辑：
        1. 检测是否为安全/技术检测类内部消息，若是则转为通用业务化表达。
        2. 将 SQL/表名/query_key 等技术关键词替换为通用表达。
    """
    # ---- 检测是否为内部安全/技术审计消息 ----
    internal_triggers = ["检测到", "阻断", "trigger", "blocked", "tech_leak", "safety_danger"]
    is_internal = any(t in reason.lower() for t in internal_triggers)

    if is_internal:
        # 安全/技术类内部消息：转为完全业务化的通用拒答
        return (
            "您的提问涉及系统不支持的操作方式，无法继续处理。"
            "请使用业务语言描述您的查询需求，例如：「2024 年合肥物流发运量是多少？」"
        )

    # ---- 普通拒答：清理技术关键词 ----
    sanitized = reason
    for pattern in _SANITIZE_PATTERNS:
        sanitized = re.sub(pattern, "系统", sanitized, flags=re.IGNORECASE)
    # 清理多余空格和重复标点
    sanitized = re.sub(r"\s{2,}", " ", sanitized)
    sanitized = re.sub(r"，{2,}", "，", sanitized)
    sanitized = sanitized.strip()

    # 兜底：如果清理后为空或太短
    if not sanitized or len(sanitized) < 5:
        sanitized = (
            "您的问题暂不在当前系统覆盖的业务范围内。"
            "当前支持物流运输数据查询和计划 BOM 材料查询，如需其他业务支持请联系管理员。"
        )

    return sanitized


def unsupported_node(state: BusinessQaGraphState) -> BusinessQaGraphState:
    """生成业务化拒答消息。

    参数：
        state: 包含 validation_details 的 Graph 运行态。
    返回：
        写入 user_visible_message 的新 state。
    业务逻辑：
        1. 从 validation_details 中提取 unsupported_reason。
        2. 对原因进行 sanitize，确保不包含内部技术标识。
        3. 状态永远保持 UNSUPPORTED，不能变成任何成功类状态。
    """
    trace = list(state.get("trace") or [])
    question = str(state.get("question") or "").strip()
    validation_details = state.get("validation_details") or {}
    shadow_plan_raw = state.get("shadow_plan_raw") or {}
    domain = state.get("domain", "unknown")

    # ---- 构造业务化拒答消息 ----
    raw_reason = str(
        validation_details.get("unsupported_reason")
        or shadow_plan_raw.get("unsupported_reason")
        or ""
    ).strip()

    if not raw_reason:
        # 兜底：通用拒答
        raw_reason = (
            "您的问题暂不在当前系统覆盖的业务范围内。"
            "当前支持物流运输数据查询和计划 BOM 材料查询，如需其他业务支持请联系管理员。"
        )

    # Sanitize：剔除可能泄露的技术关键词
    user_message = _sanitize_unsupported_reason(raw_reason)

    # ---- 写入 trace ----
    event = BusinessQaGraphEvent(
        node="unsupported",
        event_type="unsupported_response_generated",
        message=f"已为 domain={domain} 生成业务化拒答消息。",
        payload={
            "user_visible_message_preview": user_message[:200],
            "domain": domain,
        },
    )

    next_state = dict(state)
    next_state["trace"] = [*trace, event.model_dump(mode="json")]
    next_state["user_visible_message"] = user_message
    # 确保状态永远保持 UNSUPPORTED
    next_state["status"] = "UNSUPPORTED"
    return next_state

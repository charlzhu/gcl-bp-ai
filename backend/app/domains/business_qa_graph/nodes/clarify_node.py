"""LQG-4 clarify_node：生成业务化追问消息。

本节点读取 plan_validate_node 写入的 validation_details，生成用户可见的业务化追问。
绝对禁止在输出中暴露 SQL、表名、字段名、query_key、planner、guardrail、schema、
raw/debug、LLM 等技术内容。
"""

from __future__ import annotations

from backend.app.domains.business_qa_graph.schemas.event import BusinessQaGraphEvent
from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState


def clarify_node(state: BusinessQaGraphState) -> BusinessQaGraphState:
    """生成业务化澄清追问消息。

    参数：
        state: 包含 validation_details 的 Graph 运行态。
    返回：
        写入 user_visible_message 的新 state。
    业务逻辑：
        1. 从 validation_details 中提取 clarification_reason。
        2. 从 shadow_plan_raw 中提取 clarification_questions（如有）。
        3. 组合成业务化追问文本。
        4. 绝对不暴露内部 slot 名称、query_key、技术标识。
    """
    trace = list(state.get("trace") or [])
    question = str(state.get("question") or "").strip()
    validation_details = state.get("validation_details") or {}
    shadow_plan_raw = state.get("shadow_plan_raw") or {}
    domain = state.get("domain", "unknown")

    # ---- 构造业务化追问消息 ----
    # 优先使用 clarification_questions（来自 NLU 的业务化追问列表）
    clarification_questions = (
        shadow_plan_raw.get("clarification_questions")
        or validation_details.get("clarification_questions")
        or []
    )

    # 其次使用 clarification_reason
    clarification_reason = str(validation_details.get("clarification_reason", "")).strip()

    if clarification_questions:
        # 有明确的业务化追问问题
        questions_text = "\n".join(f"· {q}" for q in clarification_questions)
        user_message = (
            f"为了更好地为您查询，需要补充以下信息：\n\n"
            f"{questions_text}\n\n"
            f"请提供上述信息后重新提问。"
        )
    elif clarification_reason:
        user_message = clarification_reason
    else:
        # 兜底：通用追问
        user_message = f"您的提问「{question}」需要补充更多信息，请提供具体的查询条件（如时间范围、订单号等）后重试。"

    # ---- 写入 trace ----
    event = BusinessQaGraphEvent(
        node="clarify",
        event_type="clarification_generated",
        message=f"已为 domain={domain} 生成业务化追问消息。",
        payload={
            "user_visible_message_preview": user_message[:200],
            "domain": domain,
        },
    )

    next_state = dict(state)
    next_state["trace"] = [*trace, event.model_dump(mode="json")]
    next_state["user_visible_message"] = user_message
    next_state["status"] = "CLARIFY"
    return next_state

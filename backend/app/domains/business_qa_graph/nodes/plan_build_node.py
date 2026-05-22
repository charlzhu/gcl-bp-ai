"""LQG-3 plan_build_node：读取 shadow_plan_raw 并分类策略，决定后续路由。

本节点不查库、不执行 SQL、不计算业务事实，只做计划分类与边界守卫。
CLARIFY / UNSUPPORTED / UNSAFE 策略阻止进入执行态。
"""

from __future__ import annotations

from backend.app.domains.business_qa_graph.schemas.event import BusinessQaGraphEvent
from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState


def plan_build_node(state: BusinessQaGraphState) -> BusinessQaGraphState:
    """读取 question_understanding_node 写入的 shadow_plan_raw，分类策略。

    参数：
        state: 包含 shadow_plan_raw 的 Graph 运行态。
    返回：
        写入 plan 分类结果的新 state。
    业务逻辑：
        1. 若 understanding_status 为 UNSUPPORTED/UNSAFE，直接阻止并写入 CLARIFY/UNSUPPORTED。
        2. PLANNED 策略确认可进入后续执行（LQG-5/6 才真正执行）。
        3. CLARIFY_NEEDED 标记为需要澄清，不进入执行。
    """
    trace = list(state.get("trace") or [])
    understanding_status = state.get("understanding_status", "UNSAFE")
    shadow_plan_raw = state.get("shadow_plan_raw") or {}

    # ---- UNSAFE / UNSUPPORTED 直接阻止 ----
    if understanding_status == "UNSAFE":
        event = BusinessQaGraphEvent(
            node="plan_build",
            event_type="plan_blocked_unsafe",
            message="当前 query plan 未通过安全分类，已阻止执行。",
            payload={"understanding_status": understanding_status},
        )
        next_state: BusinessQaGraphState = dict(state)
        next_state["trace"] = [*trace, event.model_dump(mode="json")]
        next_state["status"] = "CLARIFY"
        next_state["understanding_status"] = "UNSAFE"
        return next_state

    if understanding_status == "UNSUPPORTED":
        event = BusinessQaGraphEvent(
            node="plan_build",
            event_type="plan_blocked_unsupported",
            message="当前问题不在受控能力范围内，已阻止执行。",
            payload={
                "understanding_status": understanding_status,
                "unsupported_reason": shadow_plan_raw.get("unsupported_reason"),
            },
        )
        next_state = dict(state)
        next_state["trace"] = [*trace, event.model_dump(mode="json")]
        next_state["status"] = "UNSUPPORTED"
        return next_state

    # ---- CLARIFY_NEEDED：需要澄清，不进入执行 ----
    if understanding_status == "CLARIFY_NEEDED":
        event = BusinessQaGraphEvent(
            node="plan_build",
            event_type="plan_clarification_required",
            message="查询计划缺少可执行条件，需要用户补充信息。",
            payload={
                "understanding_status": understanding_status,
                "clarification_questions": shadow_plan_raw.get("clarification_questions", []),
            },
        )
        next_state = dict(state)
        next_state["trace"] = [*trace, event.model_dump(mode="json")]
        next_state["status"] = "CLARIFY"
        return next_state

    # ---- PLANNED：计划有效，可进入后续执行（LQG-5/6） ----
    if understanding_status == "PLANNED":
        event = BusinessQaGraphEvent(
            node="plan_build",
            event_type="plan_built",
            message="受控查询计划已构建完成，等待后续执行节点处理。",
            payload={
                "understanding_status": understanding_status,
                "strategy": shadow_plan_raw.get("strategy"),
                "intent": shadow_plan_raw.get("intent"),
            },
        )
        next_state = dict(state)
        next_state["trace"] = [*trace, event.model_dump(mode="json")]
        next_state["status"] = "PLAN_BUILT"
        return next_state

    # ---- 兜底：未知状态视为 UNSAFE ----
    event = BusinessQaGraphEvent(
        node="plan_build",
        event_type="plan_blocked_unknown",
        message=f"未预期的 understanding_status={understanding_status}，视为不安全。",
        payload={"understanding_status": understanding_status},
    )
    next_state = dict(state)
    next_state["trace"] = [*trace, event.model_dump(mode="json")]
    next_state["status"] = "CLARIFY"
    next_state["understanding_status"] = "UNSAFE"
    return next_state

from __future__ import annotations

from backend.app.domains.business_qa_graph.schemas.event import BusinessQaGraphEvent
from backend.app.domains.business_qa_graph.schemas.state import (
    DEFAULT_BUSINESS_QA_GRAPH_BOUNDARY_NOTES,
    DEFAULT_BUSINESS_QA_GRAPH_VERSION,
    BusinessQaGraphState,
)


def receive_node(state: BusinessQaGraphState) -> BusinessQaGraphState:
    """接收统一业务问数请求并写入 trace。

    参数：
        state: LangGraph 当前运行态，包含 question、domain_hint、trace_id 和已有 trace。
    返回：
        写入 receive 事件后的新 state。
    业务逻辑：
        LQG-1 只建立 START→receive→END 骨架；本节点不查中间库、不调用 NL2SQL、
        不生成 SQL、不做业务计算，也不改写结构化事实。
    """

    question = str(state.get("question") or "").strip()
    domain_hint = state.get("domain_hint")
    trace_id = state.get("trace_id")
    trace = list(state.get("trace") or [])
    event = BusinessQaGraphEvent(
        node="receive",
        event_type="question_received",
        message="已接收业务问数请求，等待后续受控编排节点处理。",
        payload={
            "question": question,
            "domain_hint": domain_hint,
            "trace_id": trace_id,
        },
    )

    next_state: BusinessQaGraphState = dict(state)
    next_state["question"] = question
    next_state["domain_hint"] = domain_hint
    next_state["trace_id"] = trace_id
    next_state["trace"] = [*trace, event.model_dump(mode="json")]
    next_state["status"] = "RECEIVED"
    next_state["graph_version"] = state.get("graph_version", DEFAULT_BUSINESS_QA_GRAPH_VERSION)
    next_state["execution_mode"] = "graph_skeleton_only"
    next_state["boundary_notes"] = list(state.get("boundary_notes", DEFAULT_BUSINESS_QA_GRAPH_BOUNDARY_NOTES))
    return next_state

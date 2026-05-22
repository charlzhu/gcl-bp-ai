"""LQG-4 error_node：安全异常处理节点。

本节点处理系统内部异常，生成用户可见的安全降级消息。
绝对禁止在输出中暴露堆栈信息、数据库连接串、密钥、内部错误详情。
"""

from __future__ import annotations

from backend.app.domains.business_qa_graph.schemas.event import BusinessQaGraphEvent
from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState

# 安全降级通用消息（不暴露任何技术细节）
_GENERIC_ERROR_MESSAGE = (
    "系统处理您的请求时遇到问题，请稍后重试。如问题持续出现，请联系管理员。"
)


def error_node(state: BusinessQaGraphState) -> BusinessQaGraphState:
    """安全处理异常，生成用户可见降级消息。

    参数：
        state: 包含 validation_details（error_type/error_message）的 Graph 运行态。
    返回：
        写入安全化 user_visible_message 的新 state。
    业务逻辑：
        1. 内部错误详情只写入 trace（审计日志），不暴露给用户。
        2. 用户可见消息始终使用通用降级文案。
        3. 状态转为 UNSUPPORTED（对外不暴露 ERROR 语义）。
    """
    trace = list(state.get("trace") or [])
    question = str(state.get("question") or "").strip()
    validation_details = state.get("validation_details") or {}
    domain = state.get("domain", "unknown")

    # ---- 内部错误信息（只用于审计 trace，不对用户暴露） ----
    error_type = str(validation_details.get("error_type", "")).strip()
    error_message = str(validation_details.get("error_message", "")).strip()

    # ---- 用户可见消息始终通用降级 ----
    user_message = _GENERIC_ERROR_MESSAGE

    # ---- 写入 trace（审计信息） ----
    event = BusinessQaGraphEvent(
        node="error_handler",
        event_type="error_handled",
        message=f"内部异常已安全降级 domain={domain} error_type={error_type or 'unknown'}。",
        payload={
            "domain": domain,
            # 内部错误类型仅记录在 trace 中，不暴露给用户
            "internal_error_type": error_type or "unknown",
        },
    )

    next_state = dict(state)
    next_state["trace"] = [*trace, event.model_dump(mode="json")]
    next_state["user_visible_message"] = user_message
    # 对外统一展示 UNSUPPORTED，不暴露 ERROR 状态
    next_state["status"] = "UNSUPPORTED"
    return next_state

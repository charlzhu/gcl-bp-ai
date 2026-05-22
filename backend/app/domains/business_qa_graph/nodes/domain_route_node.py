from __future__ import annotations

from backend.app.domains.business_qa_graph.domain_registry import BusinessQaDomainRegistry
from backend.app.domains.business_qa_graph.schemas.event import BusinessQaGraphEvent
from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState


def domain_route_node(state: BusinessQaGraphState) -> BusinessQaGraphState:
    """执行统一业务问数领域路由并写入 capability 标记。

    参数：
        state: 已经过 receive_node 的 Graph 运行态。
    返回：
        写入 domain_route、domain、capabilities 和 trace 后的新 state。
    业务逻辑：
        本节点只做 registry 白名单路由；不查数据库、不调用领域 service、不生成 SQL、不计算功率事实。
    """

    question = str(state.get("question") or "").strip()
    domain_hint = state.get("domain_hint")
    trace = list(state.get("trace") or [])
    registry = BusinessQaDomainRegistry.default()
    route = registry.route(question, domain_hint=domain_hint)
    route_payload = route.model_dump(mode="json")
    event_type = "domain_routed" if route.status == "ROUTED" else "domain_route_clarification"
    message = (
        "已识别业务域和受控能力，等待后续规划/执行节点处理。"
        if route.status == "ROUTED"
        else "无法安全识别业务域，已生成澄清候选。"
    )
    event = BusinessQaGraphEvent(
        node="domain_route",
        event_type=event_type,
        message=message,
        payload=route_payload,
    )

    next_state: BusinessQaGraphState = dict(state)
    next_state["trace"] = [*trace, event.model_dump(mode="json")]
    next_state["status"] = "DOMAIN_ROUTED" if route.status == "ROUTED" else "CLARIFY"
    next_state["execution_mode"] = "domain_routing_only"
    next_state["domain"] = route.domain
    next_state["capabilities"] = list(route.capabilities)
    next_state["domain_route"] = route_payload
    return next_state

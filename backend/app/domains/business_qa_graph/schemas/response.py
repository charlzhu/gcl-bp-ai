from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domains.business_qa_graph.schemas.domain import (
    BusinessQaCapabilityId,
    BusinessQaDomainId,
    BusinessQaDomainRouteResult,
)
from backend.app.domains.business_qa_graph.schemas.event import BusinessQaGraphEvent
from backend.app.domains.business_qa_graph.schemas.state import (
    DEFAULT_BUSINESS_QA_GRAPH_BOUNDARY_NOTES,
    DEFAULT_BUSINESS_QA_GRAPH_VERSION,
    BusinessQaGraphState,
)


class BusinessQaGraphResponse(BaseModel):
    """统一业务问数 Graph 的骨架响应。

    参数：
        status: 当前骨架状态。
        execution_mode: 执行模式，LQG-2 只允许 domain-routing、skeleton-only 或 disabled。
        question: 用户原始问题。
        domain_hint: 可选业务域提示。
        trace_id: 请求追踪号。
        graph_version: Graph 版本。
        trace: 节点事件列表。
        boundary_notes: 本卡安全边界说明。
        domain: 领域路由结果，无法识别时为 unknown。
        capabilities: 本轮仅允许后续节点使用的 capability 白名单。
        domain_route: 领域路由节点写入的完整审计结构。
    返回：
        调用方可审计的最小 Graph 响应。
    业务逻辑：
        该响应不包含业务事实结果；后续卡接入领域服务前，不能把它当成最终业务回答。
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["RECEIVED", "DOMAIN_ROUTED", "PLAN_BUILT", "UNSUPPORTED", "CLARIFY", "DISABLED", "ERROR", "EXECUTED"]
    execution_mode: Literal["graph_skeleton_only", "domain_routing_only", "disabled"]
    question: str
    domain_hint: str | None = None
    trace_id: str | None = None
    graph_version: str = DEFAULT_BUSINESS_QA_GRAPH_VERSION
    trace: list[BusinessQaGraphEvent] = Field(default_factory=list)
    boundary_notes: list[str] = Field(default_factory=lambda: list(DEFAULT_BUSINESS_QA_GRAPH_BOUNDARY_NOTES))
    domain: BusinessQaDomainId = "unknown"
    capabilities: list[BusinessQaCapabilityId] = Field(default_factory=list)
    domain_route: BusinessQaDomainRouteResult | None = None
    # LQG-5 新增：执行结果快照
    execution_status: str | None = None
    execution_result: dict[str, Any] | None = Field(default=None, description="领域服务执行结果快照（不含 SQL/表名/raw/debug）")

    @classmethod
    def from_state(cls, state: BusinessQaGraphState) -> "BusinessQaGraphResponse":
        """从 LangGraph state 构造响应。

        参数：
            state: compiled graph 执行后的最终 state。
        返回：
            Pydantic 响应对象。
        业务逻辑：
            将 trace 统一重新校验成 BusinessQaGraphEvent，确保节点写入结构稳定。
        """

        domain_route_payload = state.get("domain_route") or None
        return cls(
            status=state.get("status", "RECEIVED"),
            execution_mode=state.get("execution_mode", "graph_skeleton_only"),
            question=state.get("question", ""),
            domain_hint=state.get("domain_hint"),
            trace_id=state.get("trace_id"),
            graph_version=state.get("graph_version", DEFAULT_BUSINESS_QA_GRAPH_VERSION),
            trace=[BusinessQaGraphEvent.model_validate(event) for event in state.get("trace", [])],
            boundary_notes=list(state.get("boundary_notes", DEFAULT_BUSINESS_QA_GRAPH_BOUNDARY_NOTES)),
            domain=state.get("domain", "unknown"),
            capabilities=list(state.get("capabilities", [])),
            domain_route=BusinessQaDomainRouteResult.model_validate(domain_route_payload)
            if domain_route_payload
            else None,
            # LQG-5: 透传执行结果快照
            execution_status=state.get("execution_status"),
            execution_result=state.get("execution_result") or None,
        )

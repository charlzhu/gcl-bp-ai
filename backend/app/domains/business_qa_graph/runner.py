from __future__ import annotations

from typing import Any

from backend.app.core.config import Settings, get_settings
from backend.app.domains.business_qa_graph.builder import build_business_qa_graph
from backend.app.domains.business_qa_graph.schemas.request import BusinessQaGraphRequest
from backend.app.domains.business_qa_graph.schemas.response import BusinessQaGraphResponse
from backend.app.domains.business_qa_graph.schemas.state import (
    DEFAULT_BUSINESS_QA_GRAPH_BOUNDARY_NOTES,
    DEFAULT_BUSINESS_QA_GRAPH_VERSION,
    build_business_qa_initial_state,
)


class BusinessQaGraphRunner:
    """统一业务问数 LangGraph 运行器。

    参数：
        graph: 可选 compiled graph，测试或后续卡可注入。
        settings: 配置对象，默认读取项目 settings。
        enabled: 可选显式开关；不传时读取 settings.business_qa_langgraph_enabled。
    返回：
        可调用 run 的 Graph 运行器实例。
    业务逻辑：
        默认配置关闭，确保 LQG-1 不影响旧物流/BOM 接口；只有显式打开时才执行骨架 graph。
    """

    def __init__(self, *, graph: Any | None = None, settings: Settings | None = None, enabled: bool | None = None) -> None:
        self.settings = settings or get_settings()
        self.enabled = self.settings.business_qa_langgraph_enabled if enabled is None else enabled
        # Graph 采用懒加载：默认关闭时不构建 LangGraph，避免 LQG-1 对旧链路产生任何运行时副作用。
        self._graph = graph

    def run(self, request: BusinessQaGraphRequest) -> BusinessQaGraphResponse:
        """运行统一业务问数 Graph 骨架。

        参数：
            request: 入口请求，包含用户问题、业务域提示和 trace_id。
        返回：
            Graph 骨架响应。
        业务逻辑：
            配置关闭时返回 DISABLED 响应，不执行任何节点；配置打开时仅执行 receive 节点。
        """

        if not self.enabled:
            return BusinessQaGraphResponse(
                status="DISABLED",
                execution_mode="disabled",
                question=request.question,
                domain_hint=request.domain_hint,
                trace_id=request.trace_id,
                graph_version=DEFAULT_BUSINESS_QA_GRAPH_VERSION,
                trace=[],
                boundary_notes=list(DEFAULT_BUSINESS_QA_GRAPH_BOUNDARY_NOTES),
            )

        graph = self._graph or build_business_qa_graph()
        self._graph = graph
        final_state = graph.invoke(build_business_qa_initial_state(request))
        return BusinessQaGraphResponse.from_state(final_state)

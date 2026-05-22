from __future__ import annotations

from functools import partial
from typing import Any

from langgraph.graph import END, START, StateGraph

from backend.app.domains.business_qa_graph.nodes.clarify_node import clarify_node
from backend.app.domains.business_qa_graph.nodes.domain_route_node import domain_route_node
from backend.app.domains.business_qa_graph.nodes.error_node import error_node
from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node as _execute_node
from backend.app.domains.business_qa_graph.nodes.plan_build_node import plan_build_node
from backend.app.domains.business_qa_graph.nodes.plan_validate_node import plan_validate_node
from backend.app.domains.business_qa_graph.nodes.question_understanding_node import question_understanding_node
from backend.app.domains.business_qa_graph.nodes.receive_node import receive_node
from backend.app.domains.business_qa_graph.nodes.unsupported_node import unsupported_node
from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState


def _route_after_plan_validate(state: BusinessQaGraphState) -> str:
    """根据校验结果路由到对应的终端节点。

    参数：
        state: 经 plan_validate_node 处理后的 Graph 运行态。
    返回：
        下一节点名称：plan_build / clarify / unsupported / error_handler / END。
    业务逻辑：
        - ok → plan_build（进入后续执行节点）
        - clarify → clarify（生成业务化追问）
        - unsupported → unsupported（生成业务化拒答）
        - no_answer → END（当前无专门处理节点，直接结束）
        - error → error_handler（安全降级）
        - 其他值兜底为 END
    """
    validation_result = state.get("validation_result", "error")
    if validation_result == "ok":
        return "plan_build"
    if validation_result == "clarify":
        return "clarify"
    if validation_result == "unsupported":
        return "unsupported"
    if validation_result == "error":
        return "error_handler"
    if validation_result == "no_answer":
        # 空结果当前无专门节点，直接结束
        return END
    # 兜底：未知状态直接结束
    return END


def _route_after_plan_build(state: BusinessQaGraphState) -> str:
    """根据 domain 和执行状态路由到 execute 节点或直接结束。

    参数：
        state: 经 plan_build_node 处理后的 Graph 运行态。
    返回：
        "execute" 或 "__end__"。
    业务逻辑：
        - logistics/plan_bom 域且 status=PLAN_BUILT 且 understanding_status=PLANNED → execute（LQG-5/LQG-6）
        - 其他域或非 PLANNED 态 → END
    """
    domain = state.get("domain", "unknown")
    status = state.get("status", "")
    understanding_status = state.get("understanding_status", "UNSAFE")

    # LQG-5/LQG-6：物流域和计划 BOM 域 PLANNED 状态进入执行节点
    if domain in ("logistics", "plan_bom") and status == "PLAN_BUILT" and understanding_status == "PLANNED":
        return "execute"

    # 其他情况直接结束
    return END


def build_business_qa_graph(
    *,
    logistics_service: Any = None,
    plan_bom_service: Any = None,
):
    """构建统一业务问数 StateGraph（LQG-5/LQG-6 扩展版）。

    参数：
        logistics_service: 可注入的物流领域服务实例。
            传入时，execute_node 使用该服务执行物流业务查询；
            未传入时，execute_node 尝试构造默认 LogisticsDataQaService。
        plan_bom_service: 可注入的计划 BOM 领域服务实例。
            传入时，execute_node 使用该服务执行计划 BOM 业务查询；
            未传入时，execute_node 尝试构造默认 PlanBomQaService。
    返回：
        已 compile 的 LangGraph graph，包含 receive→domain_route→question_understanding
        →plan_validate→(条件路由)→plan_build→(条件路由: execute/END)。
    业务逻辑：
        LQG-5 在 LQG-4 基础上增加 execute_node，仅在 logistics 域且校验通过时
        调用 LogisticsDataQaService.query 执行业务查询。
        LQG-6 扩展 execute_node 支持 plan_bom 域，调用 PlanBomQaService.ask 执行。
    """

    graph = StateGraph(BusinessQaGraphState)

    # ---- 注册所有节点 ----
    graph.add_node("receive", receive_node)
    graph.add_node("domain_route", domain_route_node)
    graph.add_node("question_understanding", question_understanding_node)
    graph.add_node("plan_validate", plan_validate_node)
    graph.add_node("plan_build", plan_build_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("unsupported", unsupported_node)
    graph.add_node("error_handler", error_node)
    # LQG-5/LQG-6 新增：领域服务执行节点，注入 logistics_service 和 plan_bom_service
    if logistics_service is not None or plan_bom_service is not None:
        # 至少注入了一个服务，使用 partial 绑定
        kwargs: dict[str, Any] = {}
        if logistics_service is not None:
            kwargs["logistics_service"] = logistics_service
        if plan_bom_service is not None:
            kwargs["plan_bom_service"] = plan_bom_service
        graph.add_node("execute", partial(_execute_node, **kwargs))
    else:
        # 不注入时 execute_node 内部会尝试构造默认服务
        graph.add_node("execute", _execute_node)

    # ---- 线性连线: receive → domain_route → question_understanding → plan_validate ----
    graph.add_edge(START, "receive")
    graph.add_edge("receive", "domain_route")
    graph.add_edge("domain_route", "question_understanding")
    graph.add_edge("question_understanding", "plan_validate")

    # ---- 条件路由: plan_validate → 根据 validation_result 分发 ----
    graph.add_conditional_edges(
        "plan_validate",
        _route_after_plan_validate,
        {
            "plan_build": "plan_build",
            "clarify": "clarify",
            "unsupported": "unsupported",
            "error_handler": "error_handler",
            END: END,
        },
    )

    # ---- LQG-5: 条件路由 plan_build → execute 或 END ----
    graph.add_conditional_edges(
        "plan_build",
        _route_after_plan_build,
        {
            "execute": "execute",
            END: END,
        },
    )

    # ---- 终端节点 → END ----
    graph.add_edge("execute", END)
    graph.add_edge("clarify", END)
    graph.add_edge("unsupported", END)
    graph.add_edge("error_handler", END)

    return graph.compile()

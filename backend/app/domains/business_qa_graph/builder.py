from __future__ import annotations

from functools import partial
from typing import Any

from langgraph.graph import END, START, StateGraph

from backend.app.domains.business_qa_graph.nodes.clarify_node import clarify_node
# NQE-S2 新增：复合分解节点
from backend.app.domains.business_qa_graph.nodes.decomposition_node import decomposition_node
from backend.app.domains.business_qa_graph.nodes.domain_route_node import domain_route_node
from backend.app.domains.business_qa_graph.nodes.error_node import error_node
from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node as _execute_node
from backend.app.domains.business_qa_graph.nodes.plan_build_node import plan_build_node
from backend.app.domains.business_qa_graph.nodes.plan_validate_node import plan_validate_node
# NQE-S2 新增：子结果合并展示节点
from backend.app.domains.business_qa_graph.nodes.presentation_node import presentation_node
from backend.app.domains.business_qa_graph.nodes.question_understanding_node import question_understanding_node
from backend.app.domains.business_qa_graph.nodes.receive_node import receive_node
# NQE-S3 新增：shadow compare 对比节点
from backend.app.domains.business_qa_graph.nodes.shadow_compare_node import shadow_compare_node
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
        - NQE-S2: COMPOSITE_DECOMPOSED 状态也进入 execute（复合执行路径）
        - 其他域或非 PLANNED/COMPOSITE 态 → END
    """
    domain = state.get("domain", "unknown")
    status = state.get("status", "")
    understanding_status = state.get("understanding_status", "UNSAFE")

    # LQG-5/LQG-6：物流域和计划 BOM 域 PLANNED 状态进入执行节点
    if domain in ("logistics", "plan_bom") and status == "PLAN_BUILT" and understanding_status == "PLANNED":
        return "execute"

    # NQE-S2：COMPOSITE_DECOMPOSED 状态也进入 execute
    if domain in ("logistics",) and status == "PLAN_BUILT" and understanding_status == "COMPOSITE_DECOMPOSED":
        return "execute"

    # 其他情况直接结束
    return END


def _route_after_execute(state: BusinessQaGraphState) -> str:
    """根据 understanding_status 路由到 shadow_compare/presentation 节点或直接结束。

    参数：
        state: 经 execute_node 处理后的 Graph 运行态。
    返回：
        "shadow_compare"、"presentation" 或 "__end__"。
    业务逻辑：
        - NQE-S3: logistics 域先进入 shadow_compare（对比 NL2SQL 结果），然后自动路由到 presentation 或 END
        - NQE-S2: COMPOSITE_DECOMPOSED → presentation（合并子结果）
        - NQE-S3: 所有成功执行路径先进入 shadow_compare 再分发
    """
    domain = state.get("domain", "unknown")
    understanding_status = state.get("understanding_status", "UNSAFE")

    # NQE-S3：shadow compare 优先 —— 所有 logistics 域执行成功后先对比
    if domain == "logistics":
        return "shadow_compare"

    # NQE-S2：复合分解走 presentation
    if understanding_status == "COMPOSITE_DECOMPOSED":
        return "presentation"

    # plan_bom 等其他域不走 shadow compare，直接结束
    return END


def _route_after_shadow_compare(state: BusinessQaGraphState) -> str:
    """根据 understanding_status 路由到 presentation 或直接结束。

    参数：
        state: 经 shadow_compare_node 处理后的 Graph 运行态。
    返回：
        "presentation" 或 "__end__"。
    业务逻辑：
        - NQE-S2: COMPOSITE_DECOMPOSED → presentation
        - 其他 → END
    """
    understanding_status = state.get("understanding_status", "UNSAFE")
    if understanding_status == "COMPOSITE_DECOMPOSED":
        return "presentation"
    return END


def build_business_qa_graph(
    *,
    logistics_service: Any = None,
    plan_bom_service: Any = None,
    # NQE-S1 新增：NL2SQL shadow adapter
    nl2sql_adapter: Any = None,
    # NQE-S4 新增：assist 模式，问题理解走 NL2SQL 候选但 execute 仍用旧服务
    assist_mode: bool = False,
):
    """构建统一业务问数 StateGraph（LQG-5/LQG-6 + NQE-S1/S2/S3/S4 扩展版）。

    参数：
        logistics_service: 可注入的物流领域服务实例。
            传入时，execute_node 使用该服务执行物流业务查询；
            未传入时，execute_node 尝试构造默认 LogisticsDataQaService。
        plan_bom_service: 可注入的计划 BOM 领域服务实例。
            传入时，execute_node 使用该服务执行计划 BOM 业务查询；
            未传入时，execute_node 尝试构造默认 PlanBomQaService。
        nl2sql_adapter: 可注入的 NL2SQL shadow adapter（NQE-S1 新增）。
            传入时，question_understanding_node 在 capabilities 包含
            logistics_nl2sql_shadow 时使用该 adapter 生成 SQLPlan shadow；
            NQE-S3 扩展：也用于 shadow_compare_node 生成完整 NL2SQL 结果。
        assist_mode: NQE-S4 新增，assist 模式下物流问题理解走 NL2SQL 候选路径，
            但 execute_node 仍调用旧 LogisticsDataQaService；shadow_compare_node 对比结果。
    返回：
        已 compile 的 LangGraph graph，包含以下节点链：
        receive → domain_route → question_understanding → decomposition
        → plan_validate → (条件路由) → plan_build → (条件路由: execute/END)
        → execute → (条件路由: shadow_compare/END)
        → shadow_compare → (条件路由: presentation/END) → presentation → END。
    业务逻辑：
        LQG-5 在 LQG-4 基础上增加 execute_node。
        LQG-6 扩展 execute_node 支持 plan_bom 域。
        NQE-S1 在 question_understanding_node 增加 NL2SQL shadow 分支。
        NQE-S2 新增 decomposition_node（复合分解）和 presentation_node（结果合并）。
        NQE-S3 新增 shadow_compare_node（NL2SQL 与旧链路结果对比）。
        NQE-S4 新增 assist_mode（物流 assist 灰度接入 Graph）。
    """

    graph = StateGraph(BusinessQaGraphState)

    # ---- 注册所有节点 ----
    graph.add_node("receive", receive_node)
    graph.add_node("domain_route", domain_route_node)
    # NQE-S1/S4：将 nl2sql_adapter 和 assist_mode 注入 question_understanding_node
    qu_kwargs: dict[str, Any] = {}
    if nl2sql_adapter is not None:
        qu_kwargs["nl2sql_adapter"] = nl2sql_adapter
    if assist_mode:
        qu_kwargs["assist_mode"] = True
    if qu_kwargs:
        graph.add_node("question_understanding", partial(question_understanding_node, **qu_kwargs))
    else:
        graph.add_node("question_understanding", question_understanding_node)
    # NQE-S2 新增：复合分解节点（在 question_understanding 之后）
    graph.add_node("decomposition", decomposition_node)
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
    # NQE-S2 新增：子结果合并展示节点（在 execute 之后）
    graph.add_node("presentation", presentation_node)
    # NQE-S3 新增：shadow compare 对比节点（在 execute 之后，presentation 之前）
    # 注入 nl2sql_adapter 到 shadow_compare_node
    if nl2sql_adapter is not None:
        graph.add_node("shadow_compare", partial(shadow_compare_node, nl2sql_adapter=nl2sql_adapter))
    else:
        graph.add_node("shadow_compare", shadow_compare_node)

    # ---- 线性连线: receive → domain_route → question_understanding → decomposition → plan_validate ----
    graph.add_edge(START, "receive")
    graph.add_edge("receive", "domain_route")
    graph.add_edge("domain_route", "question_understanding")
    # NQE-S2：question_understanding 后进入 decomposition
    graph.add_edge("question_understanding", "decomposition")
    graph.add_edge("decomposition", "plan_validate")

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

    # ---- LQG-5 + NQE-S2: 条件路由 plan_build → execute 或 END ----
    graph.add_conditional_edges(
        "plan_build",
        _route_after_plan_build,
        {
            "execute": "execute",
            END: END,
        },
    )

    # ---- NQE-S3: 条件路由 execute → shadow_compare 或 presentation 或 END ----
    graph.add_conditional_edges(
        "execute",
        _route_after_execute,
        {
            "shadow_compare": "shadow_compare",
            "presentation": "presentation",
            END: END,
        },
    )

    # ---- NQE-S3: 条件路由 shadow_compare → presentation 或 END ----
    graph.add_conditional_edges(
        "shadow_compare",
        _route_after_shadow_compare,
        {
            "presentation": "presentation",
            END: END,
        },
    )

    # ---- 终端节点 → END ----
    graph.add_edge("presentation", END)
    graph.add_edge("clarify", END)
    graph.add_edge("unsupported", END)
    graph.add_edge("error_handler", END)

    return graph.compile()

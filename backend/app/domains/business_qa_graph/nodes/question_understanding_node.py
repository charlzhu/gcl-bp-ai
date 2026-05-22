"""LQG-3 question_understanding_node：根据业务域选择 adapter 生成 shadow plan。

本节点复用现有 LogisticsQueryPlanningAdapter / PlanBomQueryPlanningAdapter，
不查库、不执行 SQL、不计算业务事实，只生成受控 QueryPlanningV2Plan shadow。
"""

from __future__ import annotations

from typing import Any

from backend.app.domains.business_qa_graph.schemas.event import BusinessQaGraphEvent
from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState
from backend.app.domains.query_planning.schemas.query_plan_v2 import QueryPlanningV2Plan


def question_understanding_node(
    state: BusinessQaGraphState,
    *,
    logistics_adapter: Any = None,
    plan_bom_adapter: Any = None,
) -> BusinessQaGraphState:
    """根据 domain 路由选择 adapter 并构建 shadow_plan，写入 state。

    参数：
        state: 经过 domain_route_node 的 Graph 运行态。
        logistics_adapter: 可注入的物流 Query Planning adapter，默认构造 LogisticsQueryPlanningAdapter。
        plan_bom_adapter: 可注入的计划 BOM adapter，默认构造 PlanBomQueryPlanningAdapter。
    返回：
        写入 shadow_plan_raw 和 understanding_status 的新 state。
    业务逻辑：
        1. unknown 域直接标记 UNSUPPORTED，不调用 adapter。
        2. 物流域调用 LogisticsQueryPlanningAdapter.build_candidate。
        3. 计划 BOM 域调用 PlanBomQueryPlanningAdapter.build_candidate。
        4. 生成的 QueryPlanningV2Plan 全部落入 state.shadow_plan_raw（shadow only）。
        5. 根据 plan.strategy 分类设置 understanding_status。
    """
    question = str(state.get("question") or "").strip()
    domain = state.get("domain", "unknown")
    trace_id = state.get("trace_id")
    trace = list(state.get("trace") or [])

    # ---- 未知域：直接标记 UNSUPPORTED ----
    if domain == "unknown":
        event = BusinessQaGraphEvent(
            node="question_understanding",
            event_type="understanding_unsupported",
            message="当前问题不属于已注册业务域，无法生成受控查询计划。",
            payload={"domain": domain, "reason": "domain=unknown"},
        )
        next_state: BusinessQaGraphState = dict(state)
        next_state["trace"] = [*trace, event.model_dump(mode="json")]
        next_state["understanding_status"] = "UNSUPPORTED"
        next_state["shadow_plan_raw"] = {}
        return next_state

    # ---- 构造 domain adapter ----
    adapter = _resolve_adapter(domain, logistics_adapter, plan_bom_adapter)
    if adapter is None:
        event = BusinessQaGraphEvent(
            node="question_understanding",
            event_type="understanding_unsupported",
            message=f"业务域 {domain} 无可用 adapter，无法生成查询计划。",
            payload={"domain": domain, "reason": "no_adapter"},
        )
        next_state = dict(state)
        next_state["trace"] = [*trace, event.model_dump(mode="json")]
        next_state["understanding_status"] = "UNSUPPORTED"
        next_state["shadow_plan_raw"] = {}
        return next_state

    # ---- 调用 adapter 生成 shadow plan ----
    try:
        plan: QueryPlanningV2Plan = adapter.build_candidate(question, trace_id=trace_id)
    except Exception as exc:
        event = BusinessQaGraphEvent(
            node="question_understanding",
            event_type="understanding_failed",
            message=f"构建查询计划失败：{type(exc).__name__}。",
            payload={"domain": domain, "error": str(exc)[:200]},
        )
        next_state = dict(state)
        next_state["trace"] = [*trace, event.model_dump(mode="json")]
        next_state["understanding_status"] = "UNSUPPORTED"
        next_state["shadow_plan_raw"] = {}
        return next_state

    # ---- 按 strategy 设置 understanding_status ----
    strategy = plan.strategy
    if strategy in ("DIRECT_RETRIEVAL", "QUERY_DECOMPOSITION", "HYDE_RETRIEVAL", "QUERY_REWRITE_SIMPLIFY"):
        understanding_status = "PLANNED"
    elif strategy == "CLARIFY":
        understanding_status = "CLARIFY_NEEDED"
    elif strategy in ("UNSUPPORTED", "NO_ANSWER"):
        understanding_status = "UNSUPPORTED"
    else:
        understanding_status = "UNSAFE"

    plan_dict = plan.model_dump(mode="json")

    event = BusinessQaGraphEvent(
        node="question_understanding",
        event_type="understanding_complete",
        message=f"已生成 {domain} 域受控 shadow 计划，策略={strategy}。",
        payload={
            "domain": domain,
            "strategy": strategy,
            "intent": plan.intent,
            "query_key": plan.query_key,
            "understanding_status": understanding_status,
        },
    )

    next_state = dict(state)
    next_state["trace"] = [*trace, event.model_dump(mode="json")]
    next_state["shadow_plan_raw"] = plan_dict
    next_state["understanding_status"] = understanding_status
    return next_state


def _resolve_adapter(
    domain: str,
    logistics_adapter: Any = None,
    plan_bom_adapter: Any = None,
) -> Any:
    """根据 domain 构造或返回已注入的 adapter。

    参数：
        domain: 业务域标识。
        logistics_adapter: 可注入的物流 adapter。
        plan_bom_adapter: 可注入的 BOM adapter。
    返回：
        对应 domain 的 adapter 实例，或 None（无可用 adapter）。
    业务逻辑：
        默认构造使用现有受控服务，不引入新的查询能力。
    """
    if domain == "logistics":
        if logistics_adapter is not None:
            return logistics_adapter
        # 默认构造：复用现有 LogisticsQueryPlanningAdapter
        from backend.app.domains.logistics.services.data_qa_planner import (
            LogisticsDataQaPlanner,
        )
        from backend.app.domains.logistics.services.query_planner_v2 import (
            LogisticsQueryPlannerV2,
            LogisticsQueryPlannerV2Fallback,
        )
        from backend.app.domains.query_planning.services.logistics_adapter import (
            LogisticsQueryPlanningAdapter,
        )

        planner = LogisticsDataQaPlanner()
        planner_v2 = LogisticsQueryPlannerV2(
            fallback=LogisticsQueryPlannerV2Fallback(legacy_planner=planner)
        )
        return LogisticsQueryPlanningAdapter(planner=planner, planner_v2=planner_v2)

    if domain == "plan_bom":
        if plan_bom_adapter is not None:
            return plan_bom_adapter
        # 默认构造：复用现有 PlanBomQueryPlanningAdapter
        # 默认 BOM NLU service 需要 repository；若无法构造则返回 None，由上层标记 UNSUPPORTED
        try:
            from backend.app.domains.plan_bom.repositories.query_repository import (
                PlanBomQueryRepository,
            )
            from backend.app.domains.plan_bom.services.nlu_center_service import (
                PlanBomNluCenterService,
            )
            from backend.app.domains.query_planning.services.plan_bom_adapter import (
                PlanBomQueryPlanningAdapter,
            )

            # PlanBomQueryRepository 默认使用 settings 中的数据库连接
            repository = PlanBomQueryRepository()
            nlu_service = PlanBomNluCenterService(repository=repository)
            return PlanBomQueryPlanningAdapter(nlu_service=nlu_service)
        except Exception:
            # 默认构造失败（如缺 .env / 数据库不可达），返回 None
            return None

    return None

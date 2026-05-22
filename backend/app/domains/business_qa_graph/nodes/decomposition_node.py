"""NQE-S2 decomposition_node：将复合问题拆分为独立子问题并生成子计划。

职责：
1. 当 capabilities 包含 logistics_composite_decomposition 时激活。
2. 使用 LogisticsCompositeDecomposer 检测并拆分复合问题。
3. 对每个子问题调用 logistics adapter 生成受控查询计划。
4. 存储子计划到 state.sub_plans，设置 understanding_status=COMPOSITE_DECOMPOSED。
5. 非复合问题透传，不修改 state。

本节点不查库、不执行 SQL、不计算业务事实。
LLM 负责语义分解判断（通过 decomposer），确定性代码负责校验和子计划生成。
"""

from __future__ import annotations

from typing import Any

from backend.app.domains.business_qa_graph.schemas.event import BusinessQaGraphEvent
from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState
from backend.app.domains.business_qa_graph.services.logistics_composite_decomposer import (
    LogisticsCompositeDecomposer,
)


def decomposition_node(
    state: BusinessQaGraphState,
    *,
    logistics_adapter: Any = None,
    # 可注入分解器（测试用）
    decomposer: Any = None,
) -> BusinessQaGraphState:
    """检测并拆解复合问题为多个子计划。

    参数：
        state: Graph 运行态，需包含 question/domain/capabilities。
        logistics_adapter: 可注入的物流查询计划 adapter。
            用于为每个子问题生成受控子计划。
        decomposer: 可注入的 LogisticsCompositeDecomposer 实例（测试用）。
    返回：
        写入 sub_plans/composite_type/understanding_status 的新 state。
    业务逻辑：
        1. 仅在 capabilities 包含 logistics_composite_decomposition 时激活。
        2. 使用 decomposer.decompose() 检测问题是否复合。
        3. 复合时：对每个子问题调用 adapter.build_candidate() 生成计划。
        4. 存储子计划到 state.sub_plans。
        5. 非复合时：透传 state。
    """
    question = str(state.get("question") or "").strip()
    domain = state.get("domain", "unknown")
    capabilities = list(state.get("capabilities") or [])
    trace = list(state.get("trace") or [])

    # ---- 门控：仅物流域且 capability 包含 composite_decomposition 时激活 ----
    if domain != "logistics" or "logistics_composite_decomposition" not in capabilities:
        return _pass_through(state, trace)

    # ---- 构造分解器 ----
    comp_decomposer = decomposer or LogisticsCompositeDecomposer()

    # ---- 检测并拆解 ----
    decomp_result = comp_decomposer.decompose(question)

    if not decomp_result.get("is_composite"):
        # 非复合问题，透传
        return _pass_through(state, trace)

    # ---- 复合问题：为每个子问题生成子计划 ----
    sub_questions = decomp_result.get("sub_questions", [])
    if not sub_questions:
        return _pass_through(state, trace)

    # ---- 构造 logistics adapter ----
    adapter = logistics_adapter
    if adapter is None:
        adapter = _resolve_logistics_adapter()
    if adapter is None:
        # 无法构造 adapter，记录错误并透传
        event = BusinessQaGraphEvent(
            node="decomposition",
            event_type="decomposition_adapter_unavailable",
            message="无法构造物流查询计划 adapter，跳过复合分解。",
            payload={"reason": "no_logistics_adapter"},
        )
        next_state = dict(state)
        next_state["trace"] = [*trace, event.model_dump(mode="json")]
        return next_state

    # ---- 为每个子问题生成计划 ----
    sub_plans = []
    for sq in sub_questions:
        sub_question_text = sq.get("question", "")
        try:
            plan = adapter.build_candidate(sub_question_text)
            plan_dict = plan.model_dump(mode="json") if hasattr(plan, "model_dump") else {}
            sub_plans.append({
                "question": sub_question_text,
                "source_clause": sq.get("source_clause", ""),
                "filters": sq.get("filters", {}),
                "plan": plan_dict,
            })
        except Exception:
            # 某个子计划生成失败，该子查询结果标记为错误
            sub_plans.append({
                "question": sub_question_text,
                "source_clause": sq.get("source_clause", ""),
                "filters": sq.get("filters", {}),
                "plan": {},
                "error": "plan_generation_failed",
            })

    composite_type = decomp_result.get("composite_type", "composite")
    strategy = decomp_result.get("decomposition_strategy", "unknown")

    event = BusinessQaGraphEvent(
        node="decomposition",
        event_type="decomposition_complete",
        message=f"复合问题已拆分为 {len(sub_plans)} 个子计划，类型={composite_type}，策略={strategy}。",
        payload={
            "sub_plan_count": len(sub_plans),
            "composite_type": composite_type,
            "decomposition_strategy": strategy,
        },
    )

    next_state = dict(state)
    next_state["trace"] = [*trace, event.model_dump(mode="json")]
    next_state["sub_plans"] = sub_plans
    next_state["composite_type"] = composite_type
    next_state["understanding_status"] = "COMPOSITE_DECOMPOSED"
    next_state["sub_results"] = []
    return next_state


def _pass_through(state: BusinessQaGraphState, trace: list[dict[str, Any]]) -> BusinessQaGraphState:
    """非复合问题透传 state，不修改。

    参数：
        state: 当前 state。
        trace: 已有 trace 列表。
    返回：
        未修改的 state 副本（仅补充 NQE-S2 字段默认值）。
    """
    next_state = dict(state)
    # 确保 NQE-S2 字段存在
    if "sub_plans" not in next_state:
        next_state["sub_plans"] = []
    if "sub_results" not in next_state:
        next_state["sub_results"] = []
    if "composite_type" not in next_state:
        next_state["composite_type"] = "none"
    return next_state


def _resolve_logistics_adapter() -> Any:
    """延迟构造物流查询计划 adapter。

    参数：无。
    返回：
        LogisticsQueryPlanningAdapter 实例，或 None（构造失败时）。
    业务逻辑：
        复用现有 logistics adapter 构造逻辑，与 question_understanding_node 保持一致。
    """
    try:
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
    except Exception:
        return None

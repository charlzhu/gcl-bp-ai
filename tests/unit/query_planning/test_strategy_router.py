from __future__ import annotations

from backend.app.domains.query_planning.schemas.query_plan_v2 import (
    QueryPlanningV2Plan,
    QueryPlanningV2Slots,
    QueryPlanningV2SubQuery,
)
from backend.app.domains.query_planning.services.strategy_router import QueryPlanningV2StrategyRouter


def _route(plan: QueryPlanningV2Plan) -> QueryPlanningV2Plan:
    """调用策略路由器并返回更新后的计划。"""
    return QueryPlanningV2StrategyRouter().route(plan)


def test_strategy_router_keeps_unsupported_before_rewrite_or_hyde() -> None:
    """规则层 C 类边界必须优先，不能被 rewrite / HYDE 放行。"""
    plan = QueryPlanningV2Plan(
        domain="logistics",
        original_question="预测未来三个月各区域发运量。",
        strategy="QUERY_REWRITE_SIMPLIFY",
        intent="unsupported",
        query_key="hist_mw_by_region",
        rewritten_question="统计未来三个月各区域发运量。",
        hyde_text="未来发运量预测可能涉及历史趋势。",
        unsupported_reason="当前数据源不支持未来预测。",
    )

    routed = _route(plan)

    assert routed.strategy == "UNSUPPORTED"
    assert routed.execution_policy.executable is False
    assert routed.execution_policy.llm_can_execute is False


def test_strategy_router_keeps_clarify_before_direct() -> None:
    """缺槽澄清优先于白名单 query_key，避免乱查。"""
    plan = QueryPlanningV2Plan(
        domain="plan_bom",
        original_question="这个订单玻璃是什么？",
        strategy="DIRECT_RETRIEVAL",
        intent="single_order_material_specs",
        query_key="single_order_material_specs",
        clarification_questions=["请补充订单号、BOM 文件名或客户实例。"],
    )

    routed = _route(plan)

    assert routed.strategy == "CLARIFY"
    assert routed.execution_policy.executable is False


def test_strategy_router_routes_composite_before_direct() -> None:
    """composite_decomposed 必须走复合计划路径，不能被普通 DIRECT 吞掉。"""
    plan = QueryPlanningV2Plan(
        domain="logistics",
        original_question="统计24年高运费地址，并列出询比价和招标发运量。",
        strategy="DIRECT_RETRIEVAL",
        intent="composite",
        query_key="composite_decomposed",
        sub_queries=[
            QueryPlanningV2SubQuery(
                sub_query_id="sub_1",
                source_clause="24年高运费地址",
                intent="detail_list",
                query_key="hist_high_fee_addresses_by_customer",
                slots=QueryPlanningV2Slots(filters={"year": 2024}),
                executable=True,
            )
        ],
    )

    routed = _route(plan)

    assert routed.strategy == "QUERY_DECOMPOSITION"
    assert routed.execution_policy.executable is True
    assert routed.execution_policy.sql_generation_allowed is False
    assert "composite_decomposed" in routed.execution_policy.allowed_query_keys
    assert "hist_high_fee_addresses_by_customer" in routed.execution_policy.allowed_query_keys


def test_strategy_router_routes_direct_when_query_key_is_plain_whitelist_key() -> None:
    """普通白名单 query_key 且槽位完整时进入 DIRECT_RETRIEVAL。"""
    plan = QueryPlanningV2Plan(
        domain="logistics",
        original_question="2025年各承运商发运量是多少？",
        strategy="CLARIFY",
        intent="aggregate",
        query_key="hist_mw_by_carrier",
        slots=QueryPlanningV2Slots(filters={"year": 2025}),
    )

    routed = _route(plan)

    assert routed.strategy == "DIRECT_RETRIEVAL"
    assert routed.execution_policy.executable is True


def test_strategy_router_unknown_plan_fails_closed_to_clarify() -> None:
    """无法分类的问题必须 fail closed 到澄清。"""
    plan = QueryPlanningV2Plan(domain="unknown", original_question="帮我看看这个情况", strategy="DIRECT_RETRIEVAL")

    routed = _route(plan)

    assert routed.strategy == "CLARIFY"
    assert routed.clarification_questions
    assert routed.execution_policy.executable is False

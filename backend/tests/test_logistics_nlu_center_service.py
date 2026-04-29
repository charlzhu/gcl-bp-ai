from __future__ import annotations

from backend.app.domains.logistics.services.nlu_center_service import LogisticsNluCenterService


def test_nlu_center_recovers_a_variant_as_diagnostic_candidate() -> None:
    """验证 NLU Center 能把 A 类同构变体识别为可回答候选。

    说明：
        1. 这里不执行数据库查询；
        2. query_key 只是理解层候选；
        3. 正式执行仍需走 data-qa planner / Guardrail。
    """

    service = LogisticsNluCenterService()
    result = service.analyze("老板要看26年1月物流整体出货规模和总车数，先给我个数。", use_llm=False)

    assert result.intent == "aggregate"
    assert result.route_suggestion == "answerable"
    assert "sys_mw_and_trip_count" in result.candidate_query_keys
    assert "shipment_mw" in result.metrics
    assert "shipment_trip_count" in result.metrics
    assert "normalization_or_heuristic_candidate_only" in result.risk_flags


def test_nlu_center_keeps_b_boundary_as_clarification() -> None:
    """验证 B 类模糊问题仍保持澄清边界，不被 NLU 改成可回答。"""

    service = LogisticsNluCenterService()
    result = service.analyze("最近物流成本是不是变高了？", use_llm=False)

    assert result.intent == "clarification"
    assert result.route_suggestion == "clarification"
    assert result.needs_clarification is True
    assert result.candidate_query_keys == []
    assert "bc_boundary_locked_by_policy" in result.risk_flags


def test_nlu_center_keeps_c_boundary_as_unsupported() -> None:
    """验证 C 类预测题仍保持不支持边界，不被 NLU 改写。"""

    service = LogisticsNluCenterService()
    result = service.analyze("预测下个月物流费用会是多少？", use_llm=False)

    assert result.intent == "unsupported"
    assert result.route_suggestion == "unsupported"
    assert result.unsupported is True
    assert result.candidate_query_keys == []
    assert "bc_boundary_locked_by_policy" in result.risk_flags


def test_nlu_center_detects_multi_intent_without_execution() -> None:
    """验证多问题 PoC 只拆结构，不执行多个查询。"""

    service = LogisticsNluCenterService()
    result = service.analyze("帮我看下2026年1月总发运量和车次，再看一下各承运商运费排名。", use_llm=False)

    assert result.is_multi_intent is True
    assert result.intent == "multi_intent"
    assert result.route_suggestion == "multi_intent"
    assert len(result.sub_questions) == 2
    assert "multi_intent_not_executed" in result.risk_flags
    assert "sys_mw_and_trip_count" in result.candidate_query_keys

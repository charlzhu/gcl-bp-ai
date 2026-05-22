from __future__ import annotations

from unittest.mock import MagicMock

from backend.app.domains.business_analysis.schemas.inventory_sales_production_query import (
    InventorySalesProductionQueryPlan,
    InventorySalesProductionPeriodSpec,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.m5_shadow_compare import (
    InventorySalesProductionDualTrackCompareOutcome,
    InventorySalesProductionDualTrackCompareRunResult,
    InventorySalesProductionM5ShadowCompareSample,
    build_default_inventory_sales_production_m5_shadow_samples,
    run_dual_track_compare,
)


# ===== 基础功能：双轨对比 runner =====


def test_dual_track_compare_returns_result() -> None:
    """双轨对比必须返回 DualTrackCompareRunResult，包含 samples 数和分类计数。"""
    result = run_dual_track_compare()
    assert isinstance(result, InventorySalesProductionDualTrackCompareRunResult)
    assert result.total > 0
    assert result.total == len(result.outcomes)
    assert result.by_status is not None


def test_dual_track_compare_focuses_on_nl_variant_samples() -> None:
    """双轨对比默认只对 NL 变体样本执行。"""
    samples = build_default_inventory_sales_production_m5_shadow_samples()
    nl_variants = [s for s in samples if s.question_category == "nl_variant"]
    result = run_dual_track_compare()
    assert result.total == len(nl_variants) > 0


def test_dual_track_compare_each_outcome_has_required_fields() -> None:
    """每条双轨对比 outcome 必须有 sample、rule_signature/llm_signature 和签名匹配结果。"""
    result = run_dual_track_compare()
    for outcome in result.outcomes:
        assert isinstance(outcome, InventorySalesProductionDualTrackCompareOutcome)
        assert outcome.sample is not None
        assert outcome.sample.question_category == "nl_variant"
        # rule_signature 或 llm_signature 可能有一个为空（规划器无法处理时）
        # 但 signatures_match 必须是 bool 或 None
        assert outcome.signatures_match in (True, False, None)


# ===== 规则规划器 vs LLM 规划器（注入 mock） =====


def _make_mock_llm_planner(
    *,
    returns_query_plan: bool = True,
    returns_debug: bool = True,
) -> object:
    """构造一个模拟的 LLM 规划器。"""
    planner = MagicMock()
    if returns_query_plan:
        period = InventorySalesProductionPeriodSpec(period_type="year", year=2025)
        qp = InventorySalesProductionQueryPlan(
            query_key="ba_isp_metric_summary",
            metrics=["shipment_volume"],
            dimensions=[],
            period=period,
        )
        if returns_debug:
            planner.build_plan_with_debug.return_value = (qp, {"mode": "llm"})
        planner.build_plan.return_value = qp
    else:
        from backend.app.domains.business_analysis.services.inventory_sales_production.nl_query_planner import (
            InventorySalesProductionPlanningError,
        )
        planner.build_plan_with_debug.side_effect = InventorySalesProductionPlanningError(
            "clarification", "mock clarification"
        )
        planner.build_plan.side_effect = InventorySalesProductionPlanningError(
            "clarification", "mock clarification"
        )
    return planner


def test_dual_track_inject_mock_llm_planner() -> None:
    """注入 mock LLM 规划器后，双轨对比必须正常返回。"""
    samples = [
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="test_mock",
            description="test mock",
            question="2024年卖了多少？",
            question_category="nl_variant",
            expected_status="queryplan_clarification",
        ),
    ]
    mock_llm = _make_mock_llm_planner(returns_query_plan=True)
    result = run_dual_track_compare(samples=samples, llm_planner=mock_llm)
    assert result.total == 1
    assert result.outcomes[0].sample.sample_id == "test_mock"
    # mock 返回 QP，所以 llm_signature 不应为空
    assert result.outcomes[0].llm_signature is not None


def test_dual_track_mock_llm_fails_back_to_rule() -> None:
    """mock LLM 失败时，signature 为空，状态反映规则规划器结果。"""
    samples = [
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="test_llm_fail",
            description="test llm fail",
            question="2024年卖了多少？",
            question_category="nl_variant",
            expected_status="queryplan_clarification",
        ),
    ]
    mock_llm = _make_mock_llm_planner(returns_query_plan=False)
    result = run_dual_track_compare(samples=samples, llm_planner=mock_llm)
    assert result.total == 1
    # 规则规划器对"2024年卖了多少？"返回 clarification
    assert result.outcomes[0].rule_signature is None
    assert result.outcomes[0].llm_signature is None


def test_dual_track_match_when_both_same() -> None:
    """规则规划和 mock LLM 规划器返回相同签名时，signatures_match=True。"""
    samples = [
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="test_match",
            description="test match",
            question="2025年销量是多少？",  # 与 mock 年份一致
            question_category="nl_variant",
            expected_status="matched",
        ),
    ]
    # mock LLM 返回与规则规划器一样的 QP（2025年销量 → shipment_volume / year）
    period = InventorySalesProductionPeriodSpec(period_type="year", year=2025)
    qp = InventorySalesProductionQueryPlan(
        query_key="ba_isp_metric_summary",
        metrics=["shipment_volume"],
        dimensions=[],
        period=period,
    )
    mock_llm = MagicMock()
    mock_llm.build_plan_with_debug.return_value = (qp, {"mode": "llm"})
    mock_llm.build_plan.return_value = qp
    result = run_dual_track_compare(samples=samples, llm_planner=mock_llm)
    # "2025年销量是多少？"规则规划器能处理，应产生 rule_signature
    assert result.outcomes[0].rule_signature is not None
    assert result.outcomes[0].llm_signature is not None
    # mock 返回的签名（shipment_volume/2025）与规则规划器一致
    assert result.outcomes[0].signatures_match is True


# ===== 默认 samples 的双轨对比 =====


def test_dual_track_default_samples_pass_dry_run() -> None:
    """默认 NL 变体样本在无 LLM 规划器时必须全部 dry-run 通过。"""
    result = run_dual_track_compare()
    assert result.total >= 10  # S4 有 14 条 NL 变体
    # 没有 LLM 规划器时，所有 llm_signature 为 None
    # rule_only + both_fail 应该覆盖全部
    assert result.rule_only_count + result.both_fail_count == result.total


def test_dual_track_counters_sum_to_total() -> None:
    """分类计数之和必须等于 total。"""
    result = run_dual_track_compare()
    counted = (
        result.matched_count
        + result.mismatch_count
        + result.rule_only_count
        + result.llm_only_count
        + result.both_fail_count
    )
    assert counted == result.total, f"counted={counted}, total={result.total}"

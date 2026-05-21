from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.app.domains.business_analysis.schemas.inventory_sales_production_query import (
    InventorySalesProductionQueryPlan,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.nl_query_planner import (
    InventorySalesProductionNlQueryPlanner,
    InventorySalesProductionPlanningError,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.nl2sql_query_planner import (
    InventorySalesProductionNl2SqlQueryPlanner,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.semantic_catalog import (
    InventorySalesProductionSemanticCatalogLoader,
)

# 占位符 API Key，仅为通过静态扫描的硬编码检测
_TEST_KEY = "__test_only_placeholder__"


def _make_planner(
    fallback_on_error: bool = True,
    api_key: str = "",
) -> InventorySalesProductionNl2SqlQueryPlanner:
    """构造注入已知目录和已知 API Key 的 Nl2SqlQueryPlanner 测试实例。

    参数：
        fallback_on_error: LLM 失败时是否 fallback 到规则规划器。
        api_key: 注入的 LLM API Key；默认为空表示不配置 LLM。
    返回：
        可直接用于测试的 Nl2SqlQueryPlanner 实例。
    """
    catalog = InventorySalesProductionSemanticCatalogLoader().load()
    return InventorySalesProductionNl2SqlQueryPlanner(
        catalog=catalog,
        llm_api_key=api_key,
        llm_base_url="https://test.example.com/v1",
        llm_model="qwen-max",
        fallback_on_error=fallback_on_error,
    )


# ===== 基础功能：LLM Recall 成功 =====


@patch("openai.OpenAI")
def test_nl2sql_planner_llm_success(mock_openai_cls) -> None:
    """LLM 返回有效结构化结果时，build_plan 必须返回 QueryPlan。"""
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_response(
        '{"metric_code": "shipment_volume", "query_key": "ba_isp_metric_summary", '
        '"dimensions": [], "year": 2025, "period_type": "year", '
        '"month": null, "quarter": null, "start_month": null, "end_month": null, '
        '"clarification_needed": null, "unsupported_reason": null}'
    )
    planner = _make_planner(api_key=_TEST_KEY)
    plan = planner.build_plan("2025年销量是多少？")
    assert isinstance(plan, InventorySalesProductionQueryPlan)
    assert plan.query_key == "ba_isp_metric_summary"
    assert plan.metrics == ["shipment_volume"]
    assert plan.period.year == 2025
    assert plan.period.period_type == "year"


@patch("openai.OpenAI")
def test_nl2sql_planner_llm_with_dimensions(mock_openai_cls) -> None:
    """LLM 返回带维度的结果时，QueryPlan 必须包含维度。"""
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_response(
        '{"metric_code": "production_by_base", "query_key": "ba_isp_metric_breakdown", '
        '"dimensions": ["base_name"], "year": 2025, "period_type": "year", '
        '"month": null, "quarter": null, "start_month": null, "end_month": null, '
        '"clarification_needed": null, "unsupported_reason": null}'
    )
    planner = _make_planner(api_key=_TEST_KEY)
    plan = planner.build_plan("2025年各基地产量")
    assert plan.dimensions == ["base_name"]
    assert plan.query_key == "ba_isp_metric_breakdown"


@patch("openai.OpenAI")
def test_nl2sql_planner_period_compare_adds_month(mock_openai_cls) -> None:
    """同比/环比（period_compare）时自动添加 business_month 维度。"""
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_response(
        '{"metric_code": "shipment_volume", "query_key": "ba_isp_period_compare", '
        '"dimensions": [], "year": 2025, "period_type": "year", '
        '"month": null, "quarter": null, "start_month": 1, "end_month": 6, '
        '"clarification_needed": null, "unsupported_reason": null}'
    )
    planner = _make_planner(api_key=_TEST_KEY)
    plan = planner.build_plan("2025年上半年销量同比")
    assert "business_month" in plan.dimensions


# ===== fallback 行为 =====


@patch("openai.OpenAI")
def test_nl2sql_planner_fallback_to_rules(mock_openai_cls) -> None:
    """LLM 返回 clarification_needed 时自动 fallback 到规则规划器。"""
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_response(
        '{"metric_code": null, "query_key": null, "dimensions": [],'
        '"clarification_needed": "请补充年份", "unsupported_reason": null}'
    )
    planner = _make_planner(api_key=_TEST_KEY, fallback_on_error=True)
    plan = planner.build_plan("2024年产量是多少？")
    assert isinstance(plan, InventorySalesProductionQueryPlan)
    assert plan.metrics == ["production_actual_including_oem"]


@patch("openai.OpenAI")
def test_nl2sql_planner_no_fallback_raises_error(mock_openai_cls) -> None:
    """fallback_on_error=False 时，LLM 失败应抛出 PlanningError。"""
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_response(
        '{"metric_code": null, "query_key": null, "dimensions": [],'
        '"clarification_needed": "请补充年份", "unsupported_reason": null}'
    )
    planner = _make_planner(api_key=_TEST_KEY, fallback_on_error=False)
    try:
        planner.build_plan("2024年产量")
        assert False, "应抛出 InventorySalesProductionPlanningError"
    except InventorySalesProductionPlanningError:
        pass


# ===== 异常安全 =====


@patch("openai.OpenAI")
def test_nl2sql_planner_llm_exception_fallback(mock_openai_cls) -> None:
    """LLM 抛出异常时自动 fallback 到规则规划器。"""
    mock_openai_cls.return_value.chat.completions.create.side_effect = RuntimeError("timeout")
    planner = _make_planner(api_key=_TEST_KEY, fallback_on_error=True)
    plan = planner.build_plan("2024年产量是多少？")
    assert isinstance(plan, InventorySalesProductionQueryPlan)
    assert plan.metrics == ["production_actual_including_oem"]


def test_nl2sql_planner_no_api_key_fallback() -> None:
    """没有 API Key 时，CatalogRecallService 返回 fallback，planner 回退到规则。"""
    planner = _make_planner(api_key="", fallback_on_error=True)
    plan = planner.build_plan("2024年产量")
    assert isinstance(plan, InventorySalesProductionQueryPlan)
    assert plan.metrics == ["production_actual_including_oem"]


# ===== 空问题安全 =====


def test_nl2sql_planner_empty_question() -> None:
    """空问题必须抛出 clarification 异常（不依赖 LLM）。"""
    planner = _make_planner()
    try:
        planner.build_plan("")
        assert False, "应抛出 InventorySalesProductionPlanningError"
    except InventorySalesProductionPlanningError as exc:
        assert exc.status == "clarification"


# ===== build_plan_with_debug 接口 =====


@patch("openai.OpenAI")
def test_nl2sql_planner_debug_llm_mode(mock_openai_cls) -> None:
    """build_plan_with_debug 在 LLM 成功时返回 mode=llm。"""
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_response(
        '{"metric_code": "shipment_volume", "query_key": "ba_isp_metric_summary", '
        '"dimensions": [], "year": 2025, "period_type": "year", '
        '"month": null, "quarter": null, "start_month": null, "end_month": null, '
        '"clarification_needed": null, "unsupported_reason": null}'
    )
    planner = _make_planner(api_key=_TEST_KEY)
    plan, debug = planner.build_plan_with_debug("2025年销量")
    assert debug["mode"] == "llm"
    assert debug["recall_result"]["metric_code"] == "shipment_volume"


@patch("openai.OpenAI")
def test_nl2sql_planner_debug_fallback_mode(mock_openai_cls) -> None:
    """build_plan_with_debug 在 LLM 失败时返回 mode=fallback_rule。"""
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_response(
        '{"metric_code": null, "query_key": null, "dimensions": [],'
        '"clarification_needed": "请补充年份", "unsupported_reason": null}'
    )
    planner = _make_planner(api_key=_TEST_KEY, fallback_on_error=True)
    plan, debug = planner.build_plan_with_debug("2024年产量")
    assert debug["mode"] == "fallback_rule"
    assert debug["recall_result"] is not None


# ===== 接口一致性 =====


def test_nl2sql_planner_implements_same_interface() -> None:
    """Nl2SqlQueryPlanner 必须实现与 NlQueryPlanner 相同的 build_plan 接口。"""
    rule_planner = InventorySalesProductionNlQueryPlanner()
    nl2sql_planner = _make_planner()
    assert hasattr(nl2sql_planner, "build_plan")
    assert callable(nl2sql_planner.build_plan)
    # 返回类型必须一致
    result_rule = rule_planner.build_plan("2024年产量")
    result_nl2sql = nl2sql_planner.build_plan("2024年产量")
    assert type(result_nl2sql) == type(result_rule)  # noqa: E721
    assert isinstance(result_nl2sql, InventorySalesProductionQueryPlan)


# ===== helper =====


def _mock_response(content: str) -> object:
    """构造 mock OpenAI chat completion 返回值。"""
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp

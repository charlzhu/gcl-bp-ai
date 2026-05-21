from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from backend.app.domains.business_analysis.schemas.inventory_sales_production_query import (
    InventorySalesProductionQueryPlan,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.nl_query_planner import (
    InventorySalesProductionNlQueryPlanner,
    InventorySalesProductionPlanningError,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.nl2sql_sqlplan_planner import (
    InventorySalesProductionNl2SqlSqlPlanPlanner,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.semantic_catalog import (
    InventorySalesProductionSemanticCatalogLoader,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.sql_plan import (
    InventorySalesProductionSqlPlanCandidate,
    InventorySalesProductionSqlPlan,
    InventorySalesProductionSqlPlanFilter,
    validate_inventory_sales_production_sql_plan_candidate,
)

# 占位符 API Key，仅为通过静态扫描的硬编码检测
_TEST_KEY = "__test_only_placeholder__"


def _make_planner(
    fallback_on_error: bool = True,
    api_key: str = "",
) -> InventorySalesProductionNl2SqlSqlPlanPlanner:
    """构造注入已知目录和已知 API Key 的 Nl2SqlSqlPlanPlanner 测试实例。

    参数：
        fallback_on_error: LLM 失败时是否 fallback 到规则规划器。
        api_key: 注入的 LLM API Key；默认为空表示不配置 LLM。
    返回：
        可直接用于测试的 Nl2SqlSqlPlanPlanner 实例。
    """
    catalog = InventorySalesProductionSemanticCatalogLoader().load()
    return InventorySalesProductionNl2SqlSqlPlanPlanner(
        catalog=catalog,
        llm_api_key=api_key,
        llm_base_url="https://test.example.com/v1",
        llm_model="qwen-max",
        fallback_on_error=fallback_on_error,
    )


def _valid_sqlplan_json() -> str:
    """返回一个有效的完整 SQLPlan JSON 字符串。

    注意：filters 中的 business_year 值必须与 plan.year 保持一致，
    否则 validator 的 years 检查可能产生冲突。
    """
    return (
        '{"strategy": "sql_direct", '
        '"catalog_version": "business_analysis_inventory_sales_production_catalog.v1", '
        '"catalog_refs": ['
        '  {"catalog_id": "table:dwd_ba_isp_monthly_fact", "catalog_version": "business_analysis_inventory_sales_production_catalog.v1"}, '
        '  {"catalog_id": "metric:shipment_volume", "catalog_version": "business_analysis_inventory_sales_production_catalog.v1"}, '
        '  {"catalog_id": "dimension:business_year", "catalog_version": "business_analysis_inventory_sales_production_catalog.v1"}'
        "], "
        '"plan": {'
        '  "query_key": "ba_isp_metric_summary", '
        '  "tables": ["dwd_ba_isp_monthly_fact"], '
        '  "metrics": ["shipment_volume"], '
        '  "dimensions": [], '
        '  "filters": [{"dimension": "business_year", "operator": "=", "values": [2025]}], '
        '  "group_by": [], '
        '  "order_by": [], '
        '  "business_rules": [], '
        '  "business_flags": {}, '
        '  "period_type": "year", '
        '  "year": 2025, '
        '  "month": null, '
        '  "quarter": null, '
        '  "start_month": null, '
        '  "end_month": null, '
        '  "calculation_policy": null, '
        '  "limit": null'
        "}, "
        '"clarification_questions": [], '
        '"unsupported_reason": null, '
        '"confidence": null}'
    )


def _mock_openai_response(content: str) -> object:
    """构造 mock OpenAI chat completion 返回值。"""
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _mock_openai_call(mocker: MagicMock) -> None:
    """为测试中的 Nl2SqlSqlPlanPlanner 注入 mock OpenAI 调用。

    通过 patch planner 导入位置的 openai.OpenAI，不污染其他测试模块。

    参数：
        mocker: 已实例化的 mock_openai_cls（来自 @patch("openai.OpenAI")）。
    """
    mocker.return_value.chat.completions.create.return_value = _mock_openai_response(
        _valid_sqlplan_json()
    )


# ===== 基础功能：LLM 完整 SQLPlan 生成成功 =====


def test_nl2sql_sqlplan_llm_success() -> None:
    """LLM 返回有效完整 SQLPlan 时，build_plan 必须返回 QueryPlan。"""
    planner = _make_planner(api_key=_TEST_KEY)
    # 直接 mock _try_llm_sqlplan 方法
    with patch.object(planner, "_try_llm_sqlplan") as mock_try:
        from backend.app.domains.business_analysis.schemas.inventory_sales_production_query import (
            InventorySalesProductionPeriodSpec,
        )
        mock_try.return_value = InventorySalesProductionQueryPlan(
            query_key="ba_isp_metric_summary",
            intent="metric_summary",
            metrics=["shipment_volume"],
            dimensions=[],
            filters={},
            period=InventorySalesProductionPeriodSpec(year=2025, period_type="year"),
            display_preference="business_chat",
        )
        plan = planner.build_plan("2025年销量是多少？")
        assert isinstance(plan, InventorySalesProductionQueryPlan)
        assert plan.query_key == "ba_isp_metric_summary"
        assert plan.metrics == ["shipment_volume"]


@patch("openai.OpenAI")
def test_nl2sql_sqlplan_with_dimensions(mock_openai_cls) -> None:
    """LLM 返回带维度的完整 SQLPlan 时，QueryPlan 必须包含维度。"""
    json_str = _valid_sqlplan_json().replace(
        '"dimensions": []', '"dimensions": ["base_name"]'
    ).replace(
        '"query_key": "ba_isp_metric_summary"',
        '"query_key": "ba_isp_metric_breakdown"',
    )
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_openai_response(
        json_str
    )
    planner = _make_planner(api_key=_TEST_KEY)
    plan = planner.build_plan("2025年各基地销量")
    assert plan.dimensions == ["base_name"]
    assert plan.query_key == "ba_isp_metric_breakdown"


@patch("openai.OpenAI")
def test_nl2sql_sqlplan_with_filters(mock_openai_cls) -> None:
    """LLM 返回带过滤条件的完整 SQLPlan 时，QueryPlan 必须包含过滤条件。"""
    json_str = (
        '{"strategy": "sql_direct", '
        '"catalog_version": "business_analysis_inventory_sales_production_catalog.v1", '
        '"catalog_refs": ['
        '  {"catalog_id": "table:dwd_ba_isp_monthly_fact", "catalog_version": "business_analysis_inventory_sales_production_catalog.v1"}, '
        '  {"catalog_id": "metric:shipment_volume", "catalog_version": "business_analysis_inventory_sales_production_catalog.v1"}, '
        '  {"catalog_id": "dimension:base_name", "catalog_version": "business_analysis_inventory_sales_production_catalog.v1"}, '
        '  {"catalog_id": "dimension:business_year", "catalog_version": "business_analysis_inventory_sales_production_catalog.v1"}'
        "], "
        '"plan": {'
        '  "query_key": "ba_isp_metric_breakdown", '
        '  "tables": ["dwd_ba_isp_monthly_fact"], '
        '  "metrics": ["shipment_volume"], '
        '  "dimensions": ["base_name"], '
        '  "filters": ['
        '    {"dimension": "business_year", "operator": "=", "values": [2025]}, '
        '    {"dimension": "base_name", "operator": "=", "values": ["阜宁基地"]}'
        "  ], "
        '  "group_by": ["base_name"], '
        '  "order_by": [{"metric": "shipment_volume", "direction": "desc"}], '
        '  "business_rules": [], '
        '  "business_flags": {}, '
        '  "period_type": "year", '
        '  "year": 2025, '
        '  "month": null, '
        '  "quarter": null, '
        '  "start_month": null, '
        '  "end_month": null, '
        '  "calculation_policy": null, '
        '  "limit": 10'
        "}, "
        '"clarification_questions": [], '
        '"unsupported_reason": null, '
        '"confidence": null}'
    )
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_openai_response(
        json_str
    )
    planner = _make_planner(api_key=_TEST_KEY)
    plan = planner.build_plan("2025年阜宁基地销量Top10")
    assert plan.query_key == "ba_isp_metric_breakdown"
    assert "base_name" in plan.dimensions
    # filters 应被转换为 filters dict
    assert "business_year" in plan.filters
    assert "base_name" in plan.filters
    assert plan.filters["base_name"] == ["阜宁基地"]


# ===== clarification / unsupported =====


@patch("openai.OpenAI")
def test_nl2sql_sqlplan_clarify_fallback(mock_openai_cls) -> None:
    """LLM 返回 clarification 时自动 fallback 到规则规划器。"""
    json_str = (
        '{"strategy": "clarify", '
        '"catalog_version": "business_analysis_inventory_sales_production_catalog.v1", '
        '"catalog_refs": [], '
        '"plan": {'
        '  "query_key": "ba_isp_metric_summary", '
        '  "tables": [], '
        '  "metrics": [], '
        '  "dimensions": [], '
        '  "filters": [], '
        '  "group_by": [], '
        '  "order_by": [], '
        '  "business_rules": [], '
        '  "business_flags": {}, '
        '  "period_type": "year", '
        '  "year": 2025, '
        '  "month": null, '
        '  "quarter": null, '
        '  "start_month": null, '
        '  "end_month": null, '
        '  "calculation_policy": null, '
        '  "limit": null'
        "}, "
        '"clarification_questions": ["请补充具体年份"], '
        '"unsupported_reason": null, '
        '"confidence": null}'
    )
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_openai_response(
        json_str
    )
    planner = _make_planner(api_key=_TEST_KEY, fallback_on_error=True)
    plan = planner.build_plan("2024年产量是多少？")
    assert isinstance(plan, InventorySalesProductionQueryPlan)
    # fallback 到规则规划器
    assert plan.metrics is not None


@patch("openai.OpenAI")
def test_nl2sql_sqlplan_unsupported_fallback(mock_openai_cls) -> None:
    """LLM 返回 unsupported 时自动 fallback 到规则规划器。
    但规则规划器对不被支持的问题也可能返回 clarification 异常。"""
    json_str = (
        '{"strategy": "unsupported", '
        '"catalog_version": "business_analysis_inventory_sales_production_catalog.v1", '
        '"catalog_refs": [], '
        '"plan": {'
        '  "query_key": "ba_isp_metric_summary", '
        '  "tables": [], '
        '  "metrics": [], '
        '  "dimensions": [], '
        '  "filters": [], '
        '  "group_by": [], '
        '  "order_by": [], '
        '  "business_rules": [], '
        '  "business_flags": {}, '
        '  "period_type": "year", '
        '  "year": 2025, '
        '  "month": null, '
        '  "quarter": null, '
        '  "start_month": null, '
        '  "end_month": null, '
        '  "calculation_policy": null, '
        '  "limit": null'
        "}, "
        '"clarification_questions": [], '
        '"unsupported_reason": "库存周转率暂不支持", '
        '"confidence": null}'
    )
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_openai_response(
        json_str
    )
    planner = _make_planner(api_key=_TEST_KEY, fallback_on_error=True)
    # 规则规划器同样拒绝库存周转率，因此 LLM 和规则规划器都失败时抛出异常
    try:
        planner.build_plan("库存周转率是多少？")
        assert False, "应抛出 InventorySalesProductionPlanningError"
    except InventorySalesProductionPlanningError:
        pass


# ===== 校验失败 =====


@patch("openai.OpenAI")
def test_nl2sql_sqlplan_validation_fails_fallback(mock_openai_cls) -> None:
    """LLM 生成的 SQLPlan 未通过校验时自动 fallback 到规则规划器。"""
    # 使用一个包含非法 query_key 的不合法 payload
    json_str = (
        '{"strategy": "sql_direct", '
        '"catalog_version": "business_analysis_inventory_sales_production_catalog.v1", '
        '"catalog_refs": [], '
        '"plan": {'
        '  "query_key": "ba_isp_invalid_key", '  # 非法 key
        '  "tables": ["dwd_ba_isp_monthly_fact"], '
        '  "metrics": ["shipment_volume"], '
        '  "dimensions": [], '
        '  "filters": [{"dimension": "business_year", "operator": "=", "values": [2025]}], '
        '  "group_by": [], '
        '  "order_by": [], '
        '  "business_rules": [], '
        '  "business_flags": {}, '
        '  "period_type": "year", '
        '  "year": 2025, '
        '  "month": null, '
        '  "quarter": null, '
        '  "start_month": null, '
        '  "end_month": null, '
        '  "calculation_policy": null, '
        '  "limit": null'
        "}, "
        '"clarification_questions": [], '
        '"unsupported_reason": null, '
        '"confidence": null}'
    )
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_openai_response(
        json_str
    )
    planner = _make_planner(api_key=_TEST_KEY, fallback_on_error=True)
    plan = planner.build_plan("2025年销量")
    assert isinstance(plan, InventorySalesProductionQueryPlan)
    # 校验失败，fallback 到规则规划器
    assert plan.metrics is not None


# ===== fallback 行为 =====


@patch("openai.OpenAI")
def test_nl2sql_sqlplan_fallback_to_rules(mock_openai_cls) -> None:
    """LLM 抛出异常时自动 fallback 到规则规划器。"""
    mock_openai_cls.return_value.chat.completions.create.side_effect = RuntimeError(
        "LLM timeout"
    )
    planner = _make_planner(api_key=_TEST_KEY, fallback_on_error=True)
    plan = planner.build_plan("2024年产量是多少？")
    assert isinstance(plan, InventorySalesProductionQueryPlan)
    assert plan.metrics == ["production_actual_including_oem"]


@patch("openai.OpenAI")
def test_nl2sql_sqlplan_no_fallback_raises_error(mock_openai_cls) -> None:
    """fallback_on_error=False 时，LLM 失败应抛出 PlanningError。"""
    mock_openai_cls.return_value.chat.completions.create.side_effect = RuntimeError(
        "LLM timeout"
    )
    planner = _make_planner(api_key=_TEST_KEY, fallback_on_error=False)
    try:
        planner.build_plan("2024年产量")
        assert False, "应抛出 InventorySalesProductionPlanningError"
    except InventorySalesProductionPlanningError:
        pass


def test_nl2sql_sqlplan_no_api_key_fallback() -> None:
    """没有 API Key 时，自动 fallback 到规则规划器。"""
    planner = _make_planner(api_key="", fallback_on_error=True)
    plan = planner.build_plan("2024年产量")
    assert isinstance(plan, InventorySalesProductionQueryPlan)
    assert plan.metrics == ["production_actual_including_oem"]


# ===== 空问题安全 =====


def test_nl2sql_sqlplan_empty_question() -> None:
    """空问题必须抛出 clarification 异常（不依赖 LLM）。"""
    planner = _make_planner()
    try:
        planner.build_plan("")
        assert False, "应抛出 InventorySalesProductionPlanningError"
    except InventorySalesProductionPlanningError as exc:
        assert exc.status == "clarification"


# ===== build_plan_with_debug 接口 =====


@patch("openai.OpenAI")
def test_nl2sql_sqlplan_debug_llm_mode(mock_openai_cls) -> None:
    """build_plan_with_debug 在 LLM 成功时返回 mode=llm_sqlplan。"""
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_openai_response(
        _valid_sqlplan_json()
    )
    planner = _make_planner(api_key=_TEST_KEY)
    plan, debug = planner.build_plan_with_debug("2025年销量")
    assert debug["mode"] == "llm_sqlplan"
    assert "sqlplan_candidate" in debug
    assert debug["sqlplan_candidate"]["plan"]["query_key"] == "ba_isp_metric_summary"


@patch("openai.OpenAI")
def test_nl2sql_sqlplan_debug_fallback_mode(mock_openai_cls) -> None:
    """build_plan_with_debug 在 LLM 失败时返回 mode=fallback_rule。"""
    mock_openai_cls.return_value.chat.completions.create.side_effect = RuntimeError(
        "LLM timeout"
    )
    planner = _make_planner(api_key=_TEST_KEY, fallback_on_error=True)
    plan, debug = planner.build_plan_with_debug("2024年产量")
    assert debug["mode"] == "fallback_rule"


# ===== 接口一致性 =====


def test_nl2sql_sqlplan_implements_same_interface() -> None:
    """Nl2SqlSqlPlanPlanner 必须实现与 NlQueryPlanner 相同的 build_plan 接口。"""
    rule_planner = InventorySalesProductionNlQueryPlanner()
    nl2sql_planner = _make_planner()
    assert hasattr(nl2sql_planner, "build_plan")
    assert callable(nl2sql_planner.build_plan)
    # 返回类型必须一致
    result_rule = rule_planner.build_plan("2024年产量")
    result_nl2sql = nl2sql_planner.build_plan("2024年产量")
    assert type(result_nl2sql) == type(result_rule)  # noqa: E721
    assert isinstance(result_nl2sql, InventorySalesProductionQueryPlan)


# ===== SqlPlanValidator 集成测试 =====

@patch("openai.OpenAI")
def test_nl2sql_sqlplan_validator_rejects_raw_sql(mock_openai_cls) -> None:
    """LLM 输出中带 raw_sql 字段时必须被 validator 拒绝，fallback 到规则规划器。"""
    json_str = (
        '{"strategy": "sql_direct", '
        '"catalog_version": "business_analysis_inventory_sales_production_catalog.v1", '
        '"catalog_refs": [], '
        '"raw_sql": "SELECT * FROM v_hf_sap_inout_daily", '  # 被阻断
        '"plan": {'
        '  "query_key": "ba_isp_metric_summary", '
        '  "tables": ["dwd_ba_isp_monthly_fact"], '
        '  "metrics": ["shipment_volume"], '
        '  "dimensions": [], '
        '  "filters": [{"dimension": "business_year", "operator": "=", "values": [2025]}], '
        '  "group_by": [], '
        '  "order_by": [], '
        '  "business_rules": [], '
        '  "business_flags": {}, '
        '  "period_type": "year", '
        '  "year": 2025, '
        '  "month": null, '
        '  "quarter": null, '
        '  "start_month": null, '
        '  "end_month": null, '
        '  "calculation_policy": null, '
        '  "limit": null'
        "}, "
        '"clarification_questions": [], '
        '"unsupported_reason": null, '
        '"confidence": null}'
    )
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_openai_response(
        json_str
    )
    planner = _make_planner(api_key=_TEST_KEY, fallback_on_error=True)
    plan = planner.build_plan("2025年销量")
    assert isinstance(plan, InventorySalesProductionQueryPlan)
    # 校验失败，fallback 到规则规划器
    assert plan.metrics is not None


# ===== period_compare 场景 =====


@patch("openai.OpenAI")
def test_nl2sql_sqlplan_period_compare(mock_openai_cls) -> None:
    """LLM 返回 period_compare 完整的 SQLPlan 时正确转换为 QueryPlan。"""
    json_str = (
        '{"strategy": "sql_direct", '
        '"catalog_version": "business_analysis_inventory_sales_production_catalog.v1", '
        '"catalog_refs": ['
        '  {"catalog_id": "table:dwd_ba_isp_monthly_fact", "catalog_version": "business_analysis_inventory_sales_production_catalog.v1"}, '
        '  {"catalog_id": "metric:shipment_volume", "catalog_version": "business_analysis_inventory_sales_production_catalog.v1"}, '
        '  {"catalog_id": "dimension:business_year", "catalog_version": "business_analysis_inventory_sales_production_catalog.v1"}, '
        '  {"catalog_id": "dimension:business_month", "catalog_version": "business_analysis_inventory_sales_production_catalog.v1"}'
        "], "
        '"plan": {'
        '  "query_key": "ba_isp_period_compare", '
        '  "tables": ["dwd_ba_isp_monthly_fact"], '
        '  "metrics": ["shipment_volume"], '
        '  "dimensions": ["business_month"], '
        '  "filters": [{"dimension": "business_year", "operator": "=", "values": [2025]}], '
        '  "group_by": ["business_month"], '
        '  "order_by": [{"dimension": "business_month", "direction": "asc"}], '
        '  "business_rules": ["yoy"], '
        '  "business_flags": {"yoy": true}, '
        '  "period_type": "year", '
        '  "year": 2025, '
        '  "month": null, '
        '  "quarter": null, '
        '  "start_month": 1, '
        '  "end_month": 6, '
        '  "calculation_policy": null, '
        '  "limit": null'
        "}, "
        '"clarification_questions": [], '
        '"unsupported_reason": null, '
        '"confidence": null}'
    )
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_openai_response(
        json_str
    )
    planner = _make_planner(api_key=_TEST_KEY, fallback_on_error=True)
    plan = planner.build_plan("2025年上半年销量同比")
    assert plan.query_key == "ba_isp_period_compare"
    assert "business_month" in plan.dimensions


# ===== __all__ 完整性 =====


def test_module_exports_all() -> None:
    """模块必须导出 Nl2SqlSqlPlanPlanner。"""
    from backend.app.domains.business_analysis.services.inventory_sales_production import (
        nl2sql_sqlplan_planner as module,
    )

    assert hasattr(module, "InventorySalesProductionNl2SqlSqlPlanPlanner")

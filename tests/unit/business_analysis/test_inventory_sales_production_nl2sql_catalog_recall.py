from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.app.domains.business_analysis.services.inventory_sales_production.nl2sql_catalog_recall_service import (
    InventorySalesProductionCatalogRecallResult,
    InventorySalesProductionCatalogRecallService,
)


def _make_service(mock_openai: object = None) -> InventorySalesProductionCatalogRecallService:
    """构造一个 Catalog Recall Service，注入 mock LLM。"""
    from backend.app.domains.business_analysis.services.inventory_sales_production.semantic_catalog import (
        InventorySalesProductionSemanticCatalogLoader,
    )

    catalog = InventorySalesProductionSemanticCatalogLoader().load()
    svc = InventorySalesProductionCatalogRecallService(
        catalog=catalog,
        api_key=_TEST_KEY,
        model="qwen-max",
    )
    return svc


_TEST_KEY = "__test_only_placeholder__"


def _mock_response(content: str) -> object:
    """构造 mock OpenAI chat completion 返回值。"""
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ===== 基础功能：LLM 返回成功 =====


@patch("openai.OpenAI")
def test_recall_returns_structured_result(mock_openai_cls) -> None:
    """LLM 返回正确 JSON 时必须解析为结构化结果。"""
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_response(
        '{"metric_code": "shipment_volume", "query_key": "ba_isp_metric_summary", '
        '"dimensions": [], "year": 2025, "period_type": "year", '
        '"month": null, "quarter": null, "start_month": null, "end_month": null, '
        '"clarification_needed": null, "unsupported_reason": null}'
    )
    svc = _make_service(mock_openai_cls)
    result = svc.recall("2025年销量是多少？")
    assert result.metric_code == "shipment_volume"
    assert result.query_key == "ba_isp_metric_summary"
    assert result.year == 2025
    assert result.period_type == "year"
    assert result.clarification_needed is None
    assert result.unsupported_reason is None


@patch("openai.OpenAI")
def test_recall_to_query_plan_success(mock_openai_cls) -> None:
    """成功 Recall 后 recall_to_query_plan 必须生成 QueryPlan。"""
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_response(
        '{"metric_code": "shipment_volume", "query_key": "ba_isp_metric_summary", '
        '"dimensions": [], "year": 2025, "period_type": "year", '
        '"month": null, "quarter": null, "start_month": null, "end_month": null, '
        '"clarification_needed": null, "unsupported_reason": null}'
    )
    svc = _make_service(mock_openai_cls)
    qp = svc.recall_to_query_plan("2025年销量是多少？")
    assert qp is not None
    assert qp.query_key == "ba_isp_metric_summary"
    assert qp.metrics == ["shipment_volume"]
    assert qp.period.year == 2025
    assert qp.period.period_type == "year"


# ===== fallback 处理 =====


@patch("openai.OpenAI")
def test_recall_clarification_needed_fallback_to_none(mock_openai_cls) -> None:
    """LLM 返回 clarification_needed 时 recall_to_query_plan 返回 None。"""
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_response(
        '{"metric_code": null, "query_key": null, "dimensions": [],'
        '"clarification_needed": "请补充要查询的指标", "unsupported_reason": null}'
    )
    svc = _make_service(mock_openai_cls)
    result = svc.recall("你好")
    assert result.clarification_needed == "请补充要查询的指标"
    qp = svc.recall_to_query_plan("你好")
    assert qp is None


@patch("openai.OpenAI")
def test_recall_unsupported_fallback_to_none(mock_openai_cls) -> None:
    """LLM 返回 unsupported_reason 时 recall_to_query_plan 返回 None。"""
    mock_openai_cls.return_value.chat.completions.create.return_value = _mock_response(
        '{"metric_code": null, "query_key": null, "dimensions": [],'
        '"clarification_needed": null, "unsupported_reason": "暂不支持周转率"}'
    )
    svc = _make_service(mock_openai_cls)
    qp = svc.recall_to_query_plan("库存周转率")
    assert qp is None


# ===== 异常安全 =====


@patch("openai.OpenAI")
def test_recall_llm_exception_returns_clarification(mock_openai_cls) -> None:
    """LLM 抛出异常时返回 clarification fallback，不 crash。"""
    mock_openai_cls.return_value.chat.completions.create.side_effect = RuntimeError("timeout")
    svc = _make_service(mock_openai_cls)
    result = svc.recall("2025年销量")
    assert result.clarification_needed is not None
    qp = svc.recall_to_query_plan("2025年销量")
    assert qp is None


@patch("openai.OpenAI")
def test_recall_no_api_key_fallback(mock_openai_cls) -> None:
    """没有 API Key 时返回 clarification fallback。"""
    svc = InventorySalesProductionCatalogRecallService(api_key="")
    result = svc.recall("2025年销量")
    assert result.clarification_needed is not None
    assert "API Key" in result.clarification_needed


# ===== prompt 构建 =====


def test_recall_prompt_contains_catalog_metrics() -> None:
    """构建的 prompt 必须包含 catalog 中的指标。"""
    svc = _make_service()
    prompt = svc._build_prompt()
    assert "shipment_volume" in prompt
    assert "ending_inventory_volume" in prompt
    assert "发货量/销量" in prompt or "发货量" in prompt
    assert "period_compare" in prompt or "期间对比" in prompt


def test_recall_prompt_contains_dimension_examples() -> None:
    """prompt 必须包含维度的示例值。"""
    svc = _make_service()
    prompt = svc._build_prompt()
    assert "合肥基地" in prompt
    assert "阜宁基地" in prompt

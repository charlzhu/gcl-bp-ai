from __future__ import annotations

import json
from types import SimpleNamespace

from backend.app.domains.logistics.services.llm_understanding_service import LogisticsLlmUnderstandingService


class FakeChatCompletions:
    """假的 completions 接口。

    说明：
        1. 单测不依赖真实外部 LLM；
        2. 这里只负责返回预设 JSON 文本；
        3. 便于验证输出规范化、白名单过滤和 disabled/error 逻辑。
    """

    def __init__(self, content: str) -> None:
        self.content = content

    def create(self, **kwargs):  # noqa: ANN003
        _ = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class FakeOpenAIClient:
    """假的 OpenAI 客户端。"""

    def __init__(self, content: str) -> None:
        self.chat = SimpleNamespace(completions=FakeChatCompletions(content))


def test_llm_understanding_service_returns_disabled_when_config_missing() -> None:
    """验证未配置 LLM 时不会伪造 live 成功。"""
    service = LogisticsLlmUnderstandingService(base_url="", api_key="", model="")
    result = service.understand("26年1月发了多少MW，多少车？")
    assert result.provider_mode == "disabled"
    assert result.intent == "unknown"
    assert "LLM_BASE_URL" in (result.provider_error or "")


def test_llm_understanding_service_normalizes_live_payload() -> None:
    """验证 live 模型输出会被清洗成白名单内结构。"""
    payload = {
        "normalized_question": "2026年1月发运量和车次",
        "intent": "aggregate",
        "metrics": ["shipment_mw", "shipment_trip_count"],
        "dimensions": [],
        "filters": {"year": 2026, "months": [1]},
        "time_range": {"year": 2026, "months": [1]},
        "source_scope": "system_2026",
        "candidate_query_keys": ["sys_mw_and_trip_count", "fake_query_key"],
        "normalized_terms": {"运量": "发运量", "多少车": "车次"},
        "needs_clarification": False,
        "clarification_questions": [],
        "unsupported_reason": None,
        "confidence": 0.88,
    }
    service = LogisticsLlmUnderstandingService(
        base_url="http://example.com",
        api_key="token",
        model="demo-model",
        client=FakeOpenAIClient(json.dumps(payload, ensure_ascii=False)),
    )
    result = service.understand("26年1月发了多少MW，多少车？")
    assert result.provider_mode == "live"
    assert result.intent == "aggregate"
    assert result.candidate_query_keys == ["sys_mw_and_trip_count"]
    assert result.normalized_terms["运量"] == "发运量"
    assert result.confidence == 0.88


def test_llm_understanding_service_parses_json_code_block() -> None:
    """验证模型即使返回 fenced json，也能被解析。"""
    content = """```json
{"normalized_question":"预测下个月物流费用","intent":"unsupported","metrics":[],"dimensions":[],"filters":{},"time_range":{},"source_scope":"unknown","candidate_query_keys":[],"normalized_terms":{},"needs_clarification":false,"clarification_questions":[],"unsupported_reason":"当前属于预测类问题","confidence":0.31}
```"""
    service = LogisticsLlmUnderstandingService(
        base_url="http://example.com",
        api_key="token",
        model="demo-model",
        client=FakeOpenAIClient(content),
    )
    result = service.understand("预测下个月物流费用会是多少？")
    assert result.provider_mode == "live"
    assert result.intent == "unsupported"
    assert "预测" in (result.unsupported_reason or "")


def test_llm_understanding_service_prefers_unsupported_when_reason_exists() -> None:
    """验证模型同时返回澄清和不支持时，结果会统一收敛到不支持。"""
    payload = {
        "normalized_question": "设计一个在途风险评分模型",
        "intent": "unknown",
        "metrics": [],
        "dimensions": [],
        "filters": {},
        "time_range": {},
        "source_scope": "unknown",
        "candidate_query_keys": [],
        "normalized_terms": {},
        "needs_clarification": True,
        "clarification_questions": ["请说明评分维度。"],
        "unsupported_reason": "当前不支持模型设计类问题。",
        "confidence": 0.91,
    }
    service = LogisticsLlmUnderstandingService(
        base_url="http://example.com",
        api_key="token",
        model="demo-model",
        client=FakeOpenAIClient(json.dumps(payload, ensure_ascii=False)),
    )
    result = service.understand("设计一个在途风险评分模型")
    assert result.intent == "unsupported"
    assert result.needs_clarification is False
    assert result.clarification_questions == []


def test_llm_understanding_service_converts_vague_unsupported_to_business_clarification() -> None:
    """验证高频 B 类模糊题会被理解层后处理拉回业务化澄清。"""
    payload = {
        "normalized_question": "最近物流成本是不是变高了",
        "intent": "unsupported",
        "metrics": [],
        "dimensions": [],
        "filters": {},
        "time_range": {},
        "source_scope": "unknown",
        "candidate_query_keys": [],
        "normalized_terms": {},
        "needs_clarification": False,
        "clarification_questions": [],
        "unsupported_reason": "当前系统不支持趋势分析、同比/环比计算及波动归因，仅支持静态快照类统计查询。",
        "confidence": 0.3,
    }
    service = LogisticsLlmUnderstandingService(
        base_url="http://example.com",
        api_key="token",
        model="demo-model",
        client=FakeOpenAIClient(json.dumps(payload, ensure_ascii=False)),
    )
    result = service.understand("最近物流成本是不是变高了？")
    assert result.intent == "clarification"
    assert result.needs_clarification is True
    assert result.unsupported_reason is None
    assert any("时间范围" in item for item in result.clarification_questions)


def test_llm_understanding_service_clears_redundant_clarification_for_high_confidence_a_candidate() -> None:
    """验证高置信单候选 A 类 query_key 不会因为模型过度保守而继续保留澄清标记。"""
    payload = {
        "normalized_question": "华东地区不同运输方式的平均元瓦各是多少，按低到高",
        "intent": "unknown",
        "metrics": ["平均元瓦"],
        "dimensions": ["运输方式"],
        "filters": {"region_name": "华东"},
        "time_range": {},
        "source_scope": "historical",
        "candidate_query_keys": ["hist_avg_fee_per_watt_by_transport"],
        "normalized_terms": {},
        "needs_clarification": True,
        "clarification_questions": ["请确认是否按运输方式拆分。"],
        "unsupported_reason": None,
        "confidence": 0.95,
    }
    service = LogisticsLlmUnderstandingService(
        base_url="http://example.com",
        api_key="token",
        model="demo-model",
        client=FakeOpenAIClient(json.dumps(payload, ensure_ascii=False)),
    )
    result = service.understand("华东地区不同运输方式的平均元瓦各是多少，按低到高")
    assert result.intent == "unknown"
    assert result.candidate_query_keys == ["hist_avg_fee_per_watt_by_transport"]
    assert result.needs_clarification is False
    assert result.clarification_questions == []

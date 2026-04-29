from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaPlan
from backend.app.domains.logistics.services.llm_understanding_guardrail_service import (
    LogisticsLlmUnderstandingGuardrailService,
)
from backend.app.domains.logistics.services.llm_understanding_service import LogisticsLlmUnderstandingService


class FakeChatCompletions:
    """假的 completions 接口。

    说明：
        1. Guardrail 单测不依赖真实外部模型；
        2. 这里直接返回预设 JSON；
        3. 便于验证 guardrail 是否只在 A 类候选上放行。
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


def _build_live_service(payload: dict) -> LogisticsLlmUnderstandingService:
    """构造一个固定返回 live payload 的 LLM 服务。"""
    return LogisticsLlmUnderstandingService(
        base_url="http://example.com",
        api_key="token",
        model="demo-model",
        client=FakeOpenAIClient(json.dumps(payload, ensure_ascii=False)),
    )


def test_guardrail_allows_a_variant_candidate_assist() -> None:
    """验证 shadow 模式下 A 类同构变体只形成建议，不直接改动正式结果。"""
    llm_service = _build_live_service(
        {
            "normalized_question": "26年1月发了多少MW，多少车",
            "intent": "unknown",
            "candidate_query_keys": ["sys_mw_and_trip_count"],
            "metrics": ["shipment_mw", "shipment_trip_count"],
            "dimensions": [],
            "filters": {"year": 2026, "months": [1]},
            "time_range": {"year": 2026, "months": [1]},
            "source_scope": "system_2026",
            "normalized_terms": {"运量": "发运量", "多少车": "车次"},
            "needs_clarification": False,
            "clarification_questions": [],
            "unsupported_reason": None,
            "confidence": 0.95,
        }
    )
    service = LogisticsLlmUnderstandingGuardrailService(llm_service=llm_service, enabled=True, mode="shadow", audit_enabled=False)
    decision = service.evaluate(
        question="26年1月发了多少MW，多少车？",
        rule_plan=LogisticsDataQaPlan(
            intent="clarification",
            needs_clarification=True,
            clarification_questions=[
                "当前 MVP 只支持时间聚合、区域筛选、承运商排名、费用/运量统计等结构化数据问题。",
                "请补充明确的时间、指标和维度，例如“2025年华东区域总运费”或“2026年1月总发运量”。",
            ],
        ),
    )
    assert decision.eligible_for_assist is True
    assert decision.assist_recommended is True
    assert decision.assist_applied is False
    assert decision.final_source == "rule"
    assert decision.final_needs_clarification is True
    assert decision.blocked_reason == "shadow_mode_no_apply"


def test_guardrail_assist_mode_applies_a_variant_candidate() -> None:
    """验证 assist 模式下高置信白名单 A 类候选会进入正式增强。"""
    llm_service = _build_live_service(
        {
            "normalized_question": "26年1月发了多少MW，多少车",
            "intent": "unknown",
            "candidate_query_keys": ["sys_mw_and_trip_count"],
            "metrics": ["shipment_mw", "shipment_trip_count"],
            "dimensions": [],
            "filters": {"year": 2026, "months": [1]},
            "time_range": {"year": 2026, "months": [1]},
            "source_scope": "system_2026",
            "normalized_terms": {"运量": "发运量", "多少车": "车次"},
            "needs_clarification": False,
            "clarification_questions": [],
            "unsupported_reason": None,
            "confidence": 0.95,
        }
    )
    service = LogisticsLlmUnderstandingGuardrailService(
        llm_service=llm_service,
        enabled=True,
        mode="assist",
        sample_rate=1.0,
        audit_enabled=False,
    )
    decision = service.evaluate(
        question="26年1月发了多少MW，多少车？",
        rule_plan=LogisticsDataQaPlan(
            intent="clarification",
            needs_clarification=True,
            clarification_questions=[
                "当前 MVP 只支持时间聚合、区域筛选、承运商排名、费用/运量统计等结构化数据问题。",
                "请补充明确的时间、指标和维度，例如“2025年华东区域总运费”或“2026年1月总发运量”。",
            ],
        ),
    )
    assert decision.assist_recommended is True
    assert decision.assist_applied is True
    assert decision.final_source == "llm_assist"
    assert decision.final_query_key == "sys_mw_and_trip_count"
    assert decision.final_supported is True


def test_guardrail_keeps_b_question_rule_locked() -> None:
    """验证 B 类问题即使 LLM 想改写，也必须继续由规则层澄清。"""
    llm_service = _build_live_service(
        {
            "normalized_question": "最近物流成本是不是变高了",
            "intent": "unsupported",
            "candidate_query_keys": [],
            "metrics": [],
            "dimensions": [],
            "filters": {},
            "time_range": {},
            "source_scope": "unknown",
            "normalized_terms": {},
            "needs_clarification": False,
            "clarification_questions": [],
            "unsupported_reason": "当前不支持趋势分析。",
            "confidence": 0.3,
        }
    )
    service = LogisticsLlmUnderstandingGuardrailService(llm_service=llm_service, enabled=True, mode="shadow", audit_enabled=False)
    decision = service.evaluate(
        question="最近物流成本是不是变高了？",
        rule_plan=LogisticsDataQaPlan(
            intent="clarification",
            needs_clarification=True,
            clarification_questions=[
                "请先明确时间范围，例如近7天、近30天、本月或今年。",
                "请明确指标口径，例如总费用、单瓦成本、签收率、异常率或车次。",
            ],
        ),
    )
    assert decision.policy_locked is True
    assert decision.assist_applied is False
    assert decision.final_source == "rule"
    assert decision.final_needs_clarification is True
    assert decision.blocked_reason == "policy_locked::clarification::vague_status"


def test_guardrail_keeps_c_question_rule_locked() -> None:
    """验证 C 类问题必须继续由规则层返回不支持。"""
    llm_service = _build_live_service(
        {
            "normalized_question": "预测下个月物流费用会是多少",
            "intent": "aggregate",
            "candidate_query_keys": ["hist_avg_fee_by_month"],
            "metrics": ["total_fee"],
            "dimensions": ["biz_month"],
            "filters": {},
            "time_range": {},
            "source_scope": "unknown",
            "normalized_terms": {},
            "needs_clarification": False,
            "clarification_questions": [],
            "unsupported_reason": None,
            "confidence": 0.98,
        }
    )
    service = LogisticsLlmUnderstandingGuardrailService(llm_service=llm_service, enabled=True, mode="shadow", audit_enabled=False)
    decision = service.evaluate(
        question="预测下个月物流费用会是多少？",
        rule_plan=LogisticsDataQaPlan(
            intent="unsupported",
            unsupported_reason="当前问题属于预测分析，MVP 暂未实现预测模型。",
        ),
    )
    assert decision.policy_locked is True
    assert decision.assist_applied is False
    assert decision.final_source == "rule"
    assert decision.final_supported is False
    assert decision.blocked_reason == "policy_locked::unsupported::forecast"


def test_guardrail_blocks_low_confidence_candidate() -> None:
    """验证即使是 A 类候选，低置信度也不能进入正式增强。"""
    llm_service = _build_live_service(
        {
            "normalized_question": "26年1月运量和车次",
            "intent": "aggregate",
            "candidate_query_keys": ["sys_mw_and_trip_count"],
            "metrics": ["shipment_mw", "shipment_trip_count"],
            "dimensions": [],
            "filters": {"year": 2026, "months": [1]},
            "time_range": {"year": 2026, "months": [1]},
            "source_scope": "system_2026",
            "normalized_terms": {},
            "needs_clarification": False,
            "clarification_questions": [],
            "unsupported_reason": None,
            "confidence": 0.72,
        }
    )
    service = LogisticsLlmUnderstandingGuardrailService(
        llm_service=llm_service,
        enabled=True,
        mode="shadow",
        min_confidence=0.9,
        audit_enabled=False,
    )
    decision = service.evaluate(
        question="26年1月运量和车次",
        rule_plan=LogisticsDataQaPlan(
            intent="clarification",
            needs_clarification=True,
            clarification_questions=[
                "当前 MVP 只支持时间聚合、区域筛选、承运商排名、费用/运量统计等结构化数据问题。",
                "请补充明确的时间、指标和维度，例如“2025年华东区域总运费”或“2026年1月总发运量”。",
            ],
        ),
    )
    assert decision.eligible_for_assist is True
    assert decision.assist_applied is False
    assert decision.final_source == "rule"
    assert decision.blocked_reason == "llm_low_confidence"


def test_guardrail_assist_mode_respects_sample_rate() -> None:
    """验证 assist 模式在 sample_rate=0 时不会放行候选增强。"""
    llm_service = _build_live_service(
        {
            "normalized_question": "26年1月发了多少MW，多少车",
            "intent": "unknown",
            "candidate_query_keys": ["sys_mw_and_trip_count"],
            "metrics": ["shipment_mw", "shipment_trip_count"],
            "dimensions": [],
            "filters": {"year": 2026, "months": [1]},
            "time_range": {"year": 2026, "months": [1]},
            "source_scope": "system_2026",
            "normalized_terms": {},
            "needs_clarification": False,
            "clarification_questions": [],
            "unsupported_reason": None,
            "confidence": 0.95,
        }
    )
    service = LogisticsLlmUnderstandingGuardrailService(
        llm_service=llm_service,
        enabled=True,
        mode="assist",
        sample_rate=0.0,
        audit_enabled=False,
    )
    decision = service.evaluate(
        question="26年1月发了多少MW，多少车？",
        rule_plan=LogisticsDataQaPlan(
            intent="clarification",
            needs_clarification=True,
            clarification_questions=[
                "当前 MVP 只支持时间聚合、区域筛选、承运商排名、费用/运量统计等结构化数据问题。",
                "请补充明确的时间、指标和维度，例如“2025年华东区域总运费”或“2026年1月总发运量”。",
            ],
        ),
    )
    assert decision.sampled_in is False
    assert decision.assist_applied is False
    assert decision.blocked_reason == "guardrail_not_sampled_in"


def test_guardrail_off_mode_returns_pure_rule_result() -> None:
    """验证 off 模式下会完整退回纯规则裁决。"""
    llm_service = _build_live_service(
        {
            "normalized_question": "26年1月发了多少MW，多少车",
            "intent": "unknown",
            "candidate_query_keys": ["sys_mw_and_trip_count"],
            "metrics": ["shipment_mw", "shipment_trip_count"],
            "dimensions": [],
            "filters": {"year": 2026, "months": [1]},
            "time_range": {"year": 2026, "months": [1]},
            "source_scope": "system_2026",
            "normalized_terms": {},
            "needs_clarification": False,
            "clarification_questions": [],
            "unsupported_reason": None,
            "confidence": 0.95,
        }
    )
    service = LogisticsLlmUnderstandingGuardrailService(
        llm_service=llm_service,
        enabled=True,
        mode="off",
        audit_enabled=False,
    )
    decision = service.evaluate(
        question="26年1月发了多少MW，多少车？",
        rule_plan=LogisticsDataQaPlan(
            intent="clarification",
            needs_clarification=True,
            clarification_questions=[
                "当前 MVP 只支持时间聚合、区域筛选、承运商排名、费用/运量统计等结构化数据问题。",
                "请补充明确的时间、指标和维度，例如“2025年华东区域总运费”或“2026年1月总发运量”。",
            ],
        ),
    )
    assert decision.assist_applied is False
    assert decision.final_source == "rule"
    assert decision.final_needs_clarification is True
    assert decision.blocked_reason == "guardrail_mode_off"


def test_guardrail_writes_audit_log(tmp_path: Path) -> None:
    """验证 Guardrail 审计日志会写入 JSONL，便于未来小流量追踪。"""
    llm_service = _build_live_service(
        {
            "normalized_question": "26年1月发了多少MW，多少车",
            "intent": "unknown",
            "candidate_query_keys": ["sys_mw_and_trip_count"],
            "metrics": ["shipment_mw", "shipment_trip_count"],
            "dimensions": [],
            "filters": {"year": 2026, "months": [1]},
            "time_range": {"year": 2026, "months": [1]},
            "source_scope": "system_2026",
            "normalized_terms": {},
            "needs_clarification": False,
            "clarification_questions": [],
            "unsupported_reason": None,
            "confidence": 0.95,
        }
    )
    audit_path = tmp_path / "guardrail-audit.jsonl"
    service = LogisticsLlmUnderstandingGuardrailService(
        llm_service=llm_service,
        enabled=True,
        mode="shadow",
        sample_rate=1.0,
        audit_enabled=True,
        audit_path=audit_path,
    )
    decision = service.evaluate(
        question="26年1月发了多少MW，多少车？",
        trace_id="trace-1",
        rule_plan=LogisticsDataQaPlan(
            intent="clarification",
            needs_clarification=True,
            clarification_questions=[
                "当前 MVP 只支持时间聚合、区域筛选、承运商排名、费用/运量统计等结构化数据问题。",
                "请补充明确的时间、指标和维度，例如“2025年华东区域总运费”或“2026年1月总发运量”。",
            ],
        ),
    )
    assert decision.assist_recommended is True
    assert decision.assist_applied is False
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["trace_id"] == "trace-1"
    assert payload["final_source"] == "rule"
    assert payload["llm_top_query_key"] == "sys_mw_and_trip_count"
    assert payload["assist_recommended"] is True

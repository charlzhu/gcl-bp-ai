from __future__ import annotations

import json
from types import SimpleNamespace

from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.llm_clarification_assist_service import (
    LogisticsLlmClarificationAssistService,
)


class _FakeClarificationChatCompletions:
    """假的 completions 接口。

    说明：
        1. 澄清辅助测试不依赖真实外部 LLM；
        2. 这里只负责返回预设 JSON 文本；
        3. 便于稳定验证缺口径识别和追问候选生成。
    """

    def __init__(self, content: str) -> None:
        self.content = content

    def create(self, **kwargs):  # noqa: ANN003
        _ = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class _FakeClarificationOpenAIClient:
    """假的 OpenAI 客户端。"""

    def __init__(self, content: str) -> None:
        self.chat = SimpleNamespace(completions=_FakeClarificationChatCompletions(content))


def test_clarification_assist_improves_questions_for_allowed_category() -> None:
    """验证允许增强的澄清类别会用 LLM 追问候选覆盖规则模板。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2024Q1的物流发运车次或车辆数是多少？")
    assert plan.needs_clarification is True
    assert plan.clarification_category == "quarter_trip_metric_scope"

    payload = {
        "missing_slots": ["metric_definition", "source_scope"],
        "slot_reasons": {
            "metric_definition": "车次和车辆数是两个不同统计口径。",
            "source_scope": "需要确认是否只看历史台账。",
        },
        "suggested_questions": [
            "请确认这里统计的是车次，还是唯一车辆数。",
            "请确认是否只看 2023–2025 历史台账口径，不混入 2026 系统数据。",
        ],
        "business_summary": "当前问题还需要先确认统计口径，避免把车次和车辆数混算。",
        "confidence": 0.93,
    }
    service = LogisticsLlmClarificationAssistService(
        base_url="http://example.com",
        api_key="token",
        model="demo-model",
        client=_FakeClarificationOpenAIClient(json.dumps(payload, ensure_ascii=False)),
        enabled=True,
        mode="assist",
        sample_rate=1.0,
        min_confidence=0.7,
        audit_enabled=False,
    )

    updated_plan, summary = service.apply(question="2024Q1的物流发运车次或车辆数是多少？", plan=plan)
    assert updated_plan.needs_clarification is True
    assert updated_plan.clarification_assist_used is True
    assert updated_plan.clarification_assist_provider_mode == "live"
    assert updated_plan.clarification_missing_slots == ["metric_definition", "source_scope"]
    assert "车次" in updated_plan.clarification_questions[0]
    assert "统计口径" in summary


def test_clarification_assist_keeps_rule_questions_when_disabled() -> None:
    """验证澄清辅助关闭时，会稳定回退到规则模板。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("按运输方式统计，公路对应的发运记录数是多少？")
    original_questions = list(plan.clarification_questions)

    service = LogisticsLlmClarificationAssistService(
        base_url="",
        api_key="",
        model="",
        enabled=False,
        mode="off",
        audit_enabled=False,
    )
    updated_plan, summary = service.apply(question="按运输方式统计，公路对应的发运记录数是多少？", plan=plan)
    assert updated_plan.clarification_assist_used is False
    assert updated_plan.clarification_questions == original_questions
    assert "口径" in summary


def test_clarification_assist_only_changes_questions_not_boundary() -> None:
    """验证澄清辅助不会把规则层 clarification 改判成 success。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("最近物流成本是不是变高了？")
    payload = {
        "missing_slots": ["time_range", "evaluation_metric"],
        "slot_reasons": {
            "time_range": "最近需要明确成近7天、近30天或本月。",
            "evaluation_metric": "成本变高可以按总费用或单瓦成本判断。",
        },
        "suggested_questions": [
            "请先确认时间范围，例如近7天、近30天、本月或今年。",
            "请确认要看总费用、单瓦成本，还是签收率等指标。",
        ],
        "business_summary": "当前问题还需要先明确时间范围和评价指标，系统才能继续判断。",
        "confidence": 0.91,
    }
    service = LogisticsLlmClarificationAssistService(
        base_url="http://example.com",
        api_key="token",
        model="demo-model",
        client=_FakeClarificationOpenAIClient(json.dumps(payload, ensure_ascii=False)),
        enabled=True,
        mode="assist",
        sample_rate=1.0,
        min_confidence=0.7,
        audit_enabled=False,
    )

    updated_plan, _ = service.apply(question="最近物流成本是不是变高了？", plan=plan)
    assert updated_plan.intent == "clarification"
    assert updated_plan.needs_clarification is True
    assert updated_plan.query_key is None


def test_clarification_assist_keeps_rule_missing_slots_as_floor() -> None:
    """验证 LLM 只补充缺口径，不会把规则层已识别出的口径抹掉。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2026年物流任务中状态为SIGNEDFOR的任务数量及占比是多少？")
    assert plan.clarification_category == "system_status_ratio_scope"
    assert plan.clarification_missing_slots == ["denominator_scope", "statistic_scope"]

    payload = {
        "missing_slots": ["denominator_scope"],
        "slot_reasons": {
            "denominator_scope": "占比需要先确认分母。",
        },
        "suggested_questions": [
            "请确认占比是按全部任务作为分母，还是按有效任务作为分母。",
        ],
        "business_summary": "当前问题还需要先确认占比分母口径。",
        "confidence": 0.9,
    }
    service = LogisticsLlmClarificationAssistService(
        base_url="http://example.com",
        api_key="token",
        model="demo-model",
        client=_FakeClarificationOpenAIClient(json.dumps(payload, ensure_ascii=False)),
        enabled=True,
        mode="assist",
        sample_rate=1.0,
        min_confidence=0.7,
        audit_enabled=False,
    )

    updated_plan, _ = service.apply(
        question="2026年物流任务中状态为SIGNEDFOR的任务数量及占比是多少？",
        plan=plan,
    )
    assert updated_plan.clarification_missing_slots == ["denominator_scope", "statistic_scope"]


def test_clarification_assist_supplements_rule_questions_when_llm_is_incomplete() -> None:
    """验证模型追问不完整时，会自动补回规则模板，避免追问变差。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2024-01从合肥始发的订单中，平均每车装载托数是多少？")
    assert plan.clarification_category == "route_loading_scope"

    payload = {
        "missing_slots": ["statistic_scope"],
        "slot_reasons": {
            "statistic_scope": "需要先确认按车次还是按任务平均。",
        },
        "suggested_questions": [
            "请确认这里的平均托数是按车次平均，还是按任务平均。",
        ],
        "business_summary": "当前问题还需要先确认平均口径。",
        "confidence": 0.88,
    }
    service = LogisticsLlmClarificationAssistService(
        base_url="http://example.com",
        api_key="token",
        model="demo-model",
        client=_FakeClarificationOpenAIClient(json.dumps(payload, ensure_ascii=False)),
        enabled=True,
        mode="assist",
        sample_rate=1.0,
        min_confidence=0.7,
        audit_enabled=False,
    )

    updated_plan, _ = service.apply(
        question="2024-01从合肥始发的订单中，平均每车装载托数是多少？",
        plan=plan,
    )
    assert len(updated_plan.clarification_questions) >= 2
    assert any("空值" in item for item in updated_plan.clarification_questions)


def test_clarification_assist_derives_confidence_from_structured_output() -> None:
    """验证模型把 confidence 写成 0 时，仍可按结构质量派生保守置信度。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2024Q1的物流发运车次或车辆数是多少？")
    payload = {
        "missing_slots": ["metric_definition", "source_scope"],
        "slot_reasons": {
            "metric_definition": "车次和车辆数是两个不同统计口径。",
            "source_scope": "需要确认是否只看历史台账。",
        },
        "suggested_questions": [
            "请问您要查的是发运车次，还是去重后的唯一车辆数？",
            "是否只按历史台账口径统计，不包含后续系统数据？",
        ],
        "business_summary": "当前问题还需要先明确统计对象和数据来源口径，避免混算。",
        "confidence": 0.0,
    }
    service = LogisticsLlmClarificationAssistService(
        base_url="http://example.com",
        api_key="token",
        model="demo-model",
        client=_FakeClarificationOpenAIClient(json.dumps(payload, ensure_ascii=False)),
        enabled=True,
        mode="assist",
        sample_rate=1.0,
        min_confidence=0.7,
        audit_enabled=False,
    )

    updated_plan, summary = service.apply(
        question="2024Q1的物流发运车次或车辆数是多少？",
        plan=plan,
    )
    assert updated_plan.clarification_assist_used is True
    assert updated_plan.clarification_assist_provider_mode == "live"
    assert "统计对象" in summary


def test_clarification_assist_improves_status_risk_questions() -> None:
    """验证状态风险类问题也能用 LLM 生成更业务化的追问。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("当任务长期停留在ALLOCATED状态时，应如何识别潜在履约风险并给出优先排查清单？")
    assert plan.clarification_category == "status_risk_scope"

    payload = {
        "missing_slots": ["evaluation_metric", "time_range"],
        "slot_reasons": {
            "evaluation_metric": "需要先确认风险是按滞留时长、未签收时长还是费用异常判断。",
            "time_range": "需要明确看当前在途、近30天还是全年正式任务。",
        },
        "suggested_questions": [
            "请先确认这里的“风险”按什么口径判断，例如状态滞留时长、未签收时长，还是费用异常。",
            "请确认统计范围，例如当前在途任务、2026年正式任务，还是近30天内的任务。",
        ],
        "business_summary": "当前问题还需要先确认风险判定标准和统计范围，系统才能给出排查清单。",
        "confidence": 0.9,
    }
    service = LogisticsLlmClarificationAssistService(
        base_url="http://example.com",
        api_key="token",
        model="demo-model",
        client=_FakeClarificationOpenAIClient(json.dumps(payload, ensure_ascii=False)),
        enabled=True,
        mode="assist",
        sample_rate=1.0,
        min_confidence=0.7,
        audit_enabled=False,
    )

    updated_plan, summary = service.apply(
        question="当任务长期停留在ALLOCATED状态时，应如何识别潜在履约风险并给出优先排查清单？",
        plan=plan,
    )
    assert updated_plan.clarification_assist_used is True
    assert updated_plan.clarification_missing_slots == ["evaluation_metric", "time_range"]
    assert any("风险" in item for item in updated_plan.clarification_questions)
    assert "风险判定标准" in summary


def test_clarification_assist_improves_comparison_basis_questions() -> None:
    """验证比较标准类问题也能用 LLM 生成更业务化的追问。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2023-2025区域发运份额变化最大的区域是哪一个？")
    assert plan.clarification_category == "comparison_basis_scope"

    payload = {
        "missing_slots": ["evaluation_metric", "aggregation_basis"],
        "slot_reasons": {
            "evaluation_metric": "需要先明确发运份额按件数、MW还是车次统计。",
            "aggregation_basis": "需要先确认变化大小按同比差值、占比波动还是绝对变化量判断。",
        },
        "suggested_questions": [
            "请先确认这里的“发运份额”按件数、MW，还是按车次来统计。",
            "请确认“变化最大”按什么标准判断，例如同比差值、占比波动，还是绝对变化量排序。",
        ],
        "business_summary": "当前问题还需要先明确比较指标和判断标准，系统才能稳定比较区域份额变化。",
        "confidence": 0.9,
    }
    service = LogisticsLlmClarificationAssistService(
        base_url="http://example.com",
        api_key="token",
        model="demo-model",
        client=_FakeClarificationOpenAIClient(json.dumps(payload, ensure_ascii=False)),
        enabled=True,
        mode="assist",
        sample_rate=1.0,
        min_confidence=0.7,
        audit_enabled=False,
    )

    updated_plan, summary = service.apply(
        question="2023-2025区域发运份额变化最大的区域是哪一个？",
        plan=plan,
    )
    assert updated_plan.clarification_assist_used is True
    assert updated_plan.clarification_missing_slots == ["evaluation_metric", "aggregation_basis"]
    assert "发运份额" in updated_plan.clarification_questions[0]
    assert "比较指标" in summary


def test_clarification_assist_improves_quarter_area_metric_questions() -> None:
    """验证季度区域统计类问题也能用 LLM 生成更业务化的追问。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2023年一季度各区域运费分别是多少？请按区域排序展示。")
    assert plan.clarification_category == "quarter_area_metric_scope"

    payload = {
        "missing_slots": ["source_scope", "sort_order"],
        "slot_reasons": {
            "source_scope": "需要先确认季度统计是否统一只看历史台账。",
            "sort_order": "需要先确认区域展示按指标排序还是按固定区域顺序。",
        },
        "suggested_questions": [
            "请确认这里的一季度统计是否统一只看 2023–2025 历史台账口径，不混入 2026 正式系统数据。",
            "请确认“按区域排序展示”是按运费从高到低排序，还是按固定区域顺序展示。",
        ],
        "business_summary": "当前问题还需要先确认季度统计口径和排序方式，避免把季度累计和展示顺序混在一起。",
        "confidence": 0.91,
    }
    service = LogisticsLlmClarificationAssistService(
        base_url="http://example.com",
        api_key="token",
        model="demo-model",
        client=_FakeClarificationOpenAIClient(json.dumps(payload, ensure_ascii=False)),
        enabled=True,
        mode="assist",
        sample_rate=1.0,
        min_confidence=0.7,
        audit_enabled=False,
    )

    updated_plan, summary = service.apply(
        question="2023年一季度各区域运费分别是多少？请按区域排序展示。",
        plan=plan,
    )
    assert updated_plan.clarification_assist_used is True
    assert updated_plan.clarification_missing_slots == ["source_scope", "sort_order"]
    assert any("排序" in item for item in updated_plan.clarification_questions)
    assert "排序方式" in summary


def test_clarification_assist_improves_carrier_unit_fee_questions() -> None:
    """验证承运商全年单瓦成本类问题也能用 LLM 生成更业务化的追问。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2023年晶茂物流全年平均单瓦运输成本是多少？")
    assert plan.clarification_category == "carrier_unit_fee_scope"

    payload = {
        "missing_slots": ["dimension_split", "fee_scope", "metric_definition"],
        "slot_reasons": {
            "dimension_split": "需要先确认公司名称按承运商还是客户理解。",
            "fee_scope": "需要先确认额外费用是否计入分子。",
            "metric_definition": "需要确认单瓦成本的计算公式。",
        },
        "suggested_questions": [
            "请确认“晶茂物流”在这里按承运商统计，还是按客户名称统计？",
            "请确认单瓦运输成本是否按总运费除以总瓦数计算，并且是否把额外费用计入分子？",
        ],
        "business_summary": "当前问题还需要先确认主体口径和单瓦成本费用口径。",
        "confidence": 0.91,
    }
    service = LogisticsLlmClarificationAssistService(
        base_url="http://example.com",
        api_key="token",
        model="demo-model",
        client=_FakeClarificationOpenAIClient(json.dumps(payload, ensure_ascii=False)),
        enabled=True,
        mode="assist",
        sample_rate=1.0,
        min_confidence=0.7,
        audit_enabled=False,
    )

    updated_plan, summary = service.apply(
        question="2023年晶茂物流全年平均单瓦运输成本是多少？",
        plan=plan,
    )
    assert updated_plan.clarification_assist_used is True
    assert updated_plan.clarification_missing_slots == ["dimension_split", "fee_scope", "metric_definition"]
    assert any("晶茂物流" in item for item in updated_plan.clarification_questions)
    assert "主体口径" in summary

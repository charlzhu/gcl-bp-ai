from __future__ import annotations

import json
from typing import Any

from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaPlan
from backend.app.domains.logistics.services.query_planner_v2.capability_registry import (
    LogisticsQueryPlannerV2CapabilityRegistry,
)
from backend.app.domains.logistics.services.query_planner_v2.fallback import LogisticsQueryPlannerV2Fallback
from backend.app.domains.logistics.services.query_planner_v2.legacy_adapter import LogisticsQueryPlannerV2LegacyAdapter
from backend.app.domains.logistics.services.query_planner_v2.llm_parser import LogisticsQueryPlannerV2LlmParser
from backend.app.domains.logistics.services.query_planner_v2.normalizer import LogisticsQueryPlannerV2Normalizer
from backend.app.domains.logistics.services.query_planner_v2.planner import LogisticsQueryPlannerV2
from backend.app.domains.logistics.services.query_planner_v2.prompt_builder import LogisticsQueryPlannerV2PromptBuilder
from backend.app.domains.logistics.services.query_planner_v2.validator import LogisticsQueryPlannerV2Validator


class _FakeLlmParser:
    """测试用 LLM Parser：按问题返回固定 QueryPlan 候选，不触发真实外部调用。"""

    def __init__(self, payload_by_question: dict[str, dict[str, Any]]) -> None:
        self.payload_by_question = payload_by_question
        self.calls: list[dict[str, Any]] = []

    def parse(self, *, question: str, system_prompt: str, user_prompt: str, allowed_query_keys: list[str]):
        self.calls.append(
            {
                "question": question,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "allowed_query_keys": allowed_query_keys,
            }
        )
        parser = LogisticsQueryPlannerV2LlmParser(enabled=True, client=None)
        payload = self.payload_by_question[question]
        return parser.parse_text(json.dumps(payload, ensure_ascii=False), question=question)


class _FakeLegacyPlanner:
    """测试用旧 planner：用于验证 fallback 不查数，只回退到旧受控 plan。"""

    def __init__(self, plan: LogisticsDataQaPlan) -> None:
        self.plan = plan
        self.questions: list[str] = []

    def build_plan(self, question: str) -> LogisticsDataQaPlan:
        self.questions.append(question)
        return self.plan


def _route_payload(question: str, **overrides: Any) -> dict[str, Any]:
    """构造路线运价 QueryPlan 候选。"""
    payload: dict[str, Any] = {
        "intent": "aggregate",
        "query_key": "hist_route_pricing_analysis",
        "filters": {
            "years": [2025],
            "origin_place": "合肥",
            "city": "马鞍山",
            "vehicle_type": "17.5",
            "view_mode": "avg_fee",
            "price_metric": "total_fee",
        },
        "metrics": ["avg_fee", "row_count"],
        "dimensions": [],
        "group_by": [],
        "aggregations": ["avg"],
        "compare_mode": None,
        "time_range": {"years": [2025]},
        "confidence": 0.95,
        "clarification_questions": [],
        "unsupported_reason": None,
        "normalized_question": question,
    }
    for key, value in overrides.items():
        if key == "filters":
            payload["filters"] = {**payload["filters"], **value}
        else:
            payload[key] = value
    return payload


def test_capability_registry_declares_mvp_query_keys_and_route_pricing_contract() -> None:
    """能力表必须覆盖首批 MVP query_key，并声明路线运价可执行白名单。"""
    registry = LogisticsQueryPlannerV2CapabilityRegistry()

    assert registry.allowed_query_keys() >= {
        "hist_route_pricing_analysis",
        "hist_total_fee_city_rank",
        "hist_avg_fee_by_month",
        "hist_carrier_kpi_by_year",
    }
    capability = registry.get("hist_route_pricing_analysis")
    assert capability is not None
    assert capability.allow_assist is True
    assert capability.time_scope == "historical_2023_2025"
    assert capability.executable_service == "LogisticsDataQaService.hist_route_pricing_analysis"
    assert {"years", "origin_place", "vehicle_type", "view_mode", "price_metric"} <= capability.required_filters
    assert {"city", "province"} in capability.required_any_filters
    assert {"avg_fee", "total_fee", "row_count"} <= capability.allowed_metrics
    assert {"avg", "count"} <= capability.allowed_aggregations


def test_prompt_builder_contains_safety_contract_and_allowed_query_keys() -> None:
    """Prompt 必须声明 LLM 只做规划，禁止 SQL/查库/计算答案。"""
    prompt = LogisticsQueryPlannerV2PromptBuilder().build_system_prompt(LogisticsQueryPlannerV2CapabilityRegistry())

    assert "查询规划器" in prompt
    assert "不能生成 SQL" in prompt
    assert "不能查数据库" in prompt
    assert "不能计算业务数值" in prompt
    assert "严格 JSON" in prompt
    assert "hist_route_pricing_analysis" in prompt
    for forbidden in ("where_clause", "table_name", "answer", "computed_value", "python_code", "tool_call"):
        assert forbidden in prompt


def test_prompt_builder_respects_configured_query_key_subset() -> None:
    """Prompt 能力表应按灰度 query_key 裁剪，避免诱导 LLM 选择未放行能力。"""
    prompt = LogisticsQueryPlannerV2PromptBuilder().build_system_prompt(
        LogisticsQueryPlannerV2CapabilityRegistry(),
        allowed_query_keys=["hist_route_pricing_analysis"],
    )

    assert "hist_route_pricing_analysis" in prompt
    assert "hist_carrier_kpi_by_year" not in prompt
    assert "hist_total_fee_city_rank" not in prompt


def test_non_route_capability_does_not_receive_route_only_default_filters() -> None:
    """非线路运价 query_key 不应被注入 view_mode/price_metric 这类线路专属默认槽位。"""
    normalizer = LogisticsQueryPlannerV2Normalizer()
    validator = LogisticsQueryPlannerV2Validator(registry=LogisticsQueryPlannerV2CapabilityRegistry())
    payload = {
        "intent": "aggregate",
        "query_key": "hist_total_fee_city_rank",
        "filters": {"years": [2025], "province": "江苏省"},
        "metrics": ["total_fee", "row_count"],
        "dimensions": ["city", "province"],
        "group_by": ["city"],
        "aggregations": ["sum", "count"],
        "compare_mode": "none",
        "time_range": {"years": [2025]},
        "confidence": 0.95,
        "clarification_questions": [],
        "unsupported_reason": None,
        "normalized_question": "2025年江苏省城市总费用排名",
    }

    candidate = normalizer.normalize(payload, question="2025年江苏省城市总费用排名")
    validation = validator.validate(candidate, original_question="2025年江苏省城市总费用排名")

    assert "view_mode" not in candidate.filters
    assert "price_metric" not in candidate.filters
    assert candidate.filters["province"] == "江苏"
    assert validation.accepted, validation.errors


def test_llm_parser_accepts_strict_json_and_fail_closes_forbidden_payload() -> None:
    """Parser 只接受严格 JSON，遇到 SQL / answer / computed_value 等危险字段必须 fail closed。"""
    parser = LogisticsQueryPlannerV2LlmParser(enabled=True, client=None)

    ok = parser.parse_text(
        json.dumps(_route_payload("2025年合肥到马鞍山17.5米车平均运费"), ensure_ascii=False),
        question="2025年合肥到马鞍山17.5米车平均运费",
    )
    assert ok.provider_mode == "live"
    assert ok.query_key == "hist_route_pricing_analysis"
    assert ok.confidence == 0.95

    markdown_wrapped = parser.parse_text(
        "```json\n" + json.dumps(_route_payload("2025年合肥到马鞍山17.5米车平均运费"), ensure_ascii=False) + "\n```",
        question="2025年合肥到马鞍山17.5米车平均运费",
    )
    assert markdown_wrapped.provider_mode == "error"
    assert "json_parse_error" in (markdown_wrapped.provider_error or "")

    nan_payload = json.dumps(_route_payload("2025年合肥到马鞍山17.5米车平均运费"), ensure_ascii=False).replace(
        '"confidence": 0.95', '"confidence": NaN'
    )
    bad_nan = parser.parse_text(nan_payload, question="2025年合肥到马鞍山17.5米车平均运费")
    assert bad_nan.provider_mode == "error"
    assert "json_parse_error" in (bad_nan.provider_error or "")

    bad_where = parser.parse_text(
        json.dumps({**_route_payload("危险输出"), "where": "1=1"}, ensure_ascii=False),
        question="危险输出",
    )
    assert bad_where.provider_mode == "error"
    assert "forbidden_field::where" in (bad_where.provider_error or "")

    bad_nested_where = parser.parse_text(
        json.dumps(
            {**_route_payload("危险输出"), "filters": {**_route_payload("危险输出")["filters"], "nested": {"where": "1=1"}}},
            ensure_ascii=False,
        ),
        question="危险输出",
    )
    assert bad_nested_where.provider_mode == "error"
    assert "forbidden_field::where" in (bad_nested_where.provider_error or "")

    bad_unknown = parser.parse_text(
        json.dumps({**_route_payload("危险输出"), "debug_extra": "不允许的自由字段"}, ensure_ascii=False),
        question="危险输出",
    )
    assert bad_unknown.provider_mode == "error"
    assert "unexpected_field::debug_extra" in (bad_unknown.provider_error or "")

    bad = parser.parse_text(
        json.dumps({**_route_payload("危险输出"), "sql": "select * from dwd_logistics_hist_shipment_detail"}, ensure_ascii=False),
        question="危险输出",
    )
    assert bad.provider_mode == "error"
    assert bad.query_key is None
    assert "forbidden_field::sql" in (bad.provider_error or "")

    bad_answer = parser.parse_text(
        json.dumps({**_route_payload("危险输出"), "answer": "平均运费是 7005 元"}, ensure_ascii=False),
        question="危险输出",
    )
    assert bad_answer.provider_mode == "error"
    assert "forbidden_field::answer" in (bad_answer.provider_error or "")


def test_normalizer_and_validator_accept_route_pricing_semantic_variants() -> None:
    """多种线路问法应由 LLM 候选 + 后端归一校验统一到 hist_route_pricing_analysis。"""
    questions = [
        "2025年合肥发马鞍山17.5米车的平均运费",
        "2025年合肥至马鞍山17.5米车的平均运费",
        "2025年合肥到马鞍山17.5米车的平均运费",
        "2025年从合肥运到马鞍山17.5米车平均多少钱",
        "2025年合肥往马鞍山发17米五车均费",
    ]
    normalizer = LogisticsQueryPlannerV2Normalizer()
    validator = LogisticsQueryPlannerV2Validator(registry=LogisticsQueryPlannerV2CapabilityRegistry())
    legacy_adapter = LogisticsQueryPlannerV2LegacyAdapter()

    for question in questions:
        candidate = normalizer.normalize(_route_payload(question, filters={"vehicle_type": "17米五"}), question=question)
        validation = validator.validate(candidate, original_question=question)
        assert validation.accepted, validation.errors
        legacy_plan = legacy_adapter.to_logistics_plan(validation.candidate)
        assert legacy_plan.query_key == "hist_route_pricing_analysis"
        assert legacy_plan.filters == {
            "years": [2025],
            "origin_place": "合肥",
            "city": "马鞍山",
            "vehicle_type": "17.5",
            "view_mode": "avg_fee",
            "price_metric": "total_fee",
        }
        assert legacy_plan.metrics == ["avg_fee", "row_count"]


def test_validator_rejects_invalid_query_key_filter_low_confidence_2026_and_bc_boundary() -> None:
    """Validator 必须拦截非法 query_key/filter、低置信、历史/系统年份混用和 B/C 越界。"""
    normalizer = LogisticsQueryPlannerV2Normalizer()
    validator = LogisticsQueryPlannerV2Validator(registry=LogisticsQueryPlannerV2CapabilityRegistry(), min_confidence=0.9)

    cases = [
        ("bad_key", _route_payload("bad_key", query_key="free_sql"), "unknown_query_key"),
        ("bad_filter", _route_payload("bad_filter", filters={"raw_sql": "1=1"}), "filter_not_allowed::raw_sql"),
        ("low_conf", _route_payload("low_conf", confidence=0.5), "low_confidence"),
        ("year_2026", _route_payload("year_2026", filters={"years": [2026]}, time_range={"years": [2026]}), "time_scope_mismatch"),
        (
            "bad_source_scope",
            _route_payload("2025年合肥到马鞍山17.5米车平均运费", time_range={"years": [2025], "source_scope": "system_2026"}),
            "time_scope_mismatch::source_scope",
        ),
        (
            "bad_time_scope_when_source_scope_matches",
            _route_payload(
                "2025年合肥到马鞍山17.5米车平均运费",
                time_range={"years": [2025], "source_scope": "historical_2023_2025", "time_scope": "system_2026"},
            ),
            "time_scope_mismatch::time_scope",
        ),
        (
            "bad_time_range_key",
            _route_payload("2025年合肥到马鞍山17.5米车平均运费", time_range={"years": [2025], "free_scope": "x"}),
            "time_range_key_not_allowed::free_scope",
        ),
        (
            "bc_boundary",
            _route_payload("预测未来三个月各区域发运量", filters={"years": [2025]}),
            "policy_locked",
        ),
    ]
    for question, payload, expected_error in cases:
        candidate = normalizer.normalize(payload, question=question)
        validation = validator.validate(candidate, original_question=question)
        assert not validation.accepted
        assert any(error.startswith(expected_error) for error in validation.errors), validation.errors


def test_validator_rejects_year_rewrite_against_original_question() -> None:
    """原问题中的显式年份必须由 Validator 独立校验，不能信任 LLM 改写后的年份。"""
    normalizer = LogisticsQueryPlannerV2Normalizer()
    validator = LogisticsQueryPlannerV2Validator(registry=LogisticsQueryPlannerV2CapabilityRegistry())

    single_2026_question = "2026年合肥到马鞍山17.5米车平均运费"
    single_2026_candidate = normalizer.normalize(
        _route_payload(single_2026_question, filters={"years": [2025]}, time_range={"years": [2025]}),
        question=single_2026_question,
    )
    single_2026_result = validator.validate(single_2026_candidate, original_question=single_2026_question)

    assert not single_2026_result.accepted
    assert "time_scope_mismatch::question_historical_2023_2025" in single_2026_result.errors
    assert "question_candidate_years_conflict" in single_2026_result.errors

    mixed_year_question = "2025和2026年合肥到马鞍山17.5米车平均运费对比"
    malicious_candidate = normalizer.normalize(
        _route_payload(mixed_year_question, filters={"years": [2025]}, time_range={"years": [2025]}),
        question="2025年合肥到马鞍山17.5米车平均运费",
    )
    mixed_year_result = validator.validate(malicious_candidate, original_question=mixed_year_question)

    assert not mixed_year_result.accepted
    assert "time_scope_mismatch::question_historical_2023_2025" in mixed_year_result.errors
    assert "question_candidate_years_conflict" in mixed_year_result.errors


def test_validator_rejects_invalid_plan_axes_and_confidence_range() -> None:
    """非法指标、维度、分组、聚合、对比模式和置信度范围都必须 fail closed。"""
    normalizer = LogisticsQueryPlannerV2Normalizer()
    validator = LogisticsQueryPlannerV2Validator(registry=LogisticsQueryPlannerV2CapabilityRegistry(), min_confidence=0.9)
    cases = [
        (_route_payload("bad_metric", metrics=["profit"]), "metric_not_allowed::profit"),
        (_route_payload("bad_dimension", dimensions=["raw_table"]), "dimension_not_allowed::raw_table"),
        (_route_payload("bad_group_by", group_by=["sql_group"]), "group_by_not_allowed::sql_group"),
        (_route_payload("bad_aggregation", aggregations=["median"]), "aggregation_not_allowed::median"),
        (_route_payload("bad_compare", compare_mode="free_compare"), "compare_mode_not_allowed::free_compare"),
        (_route_payload("bad_confidence", confidence=1.5), "invalid_confidence_range::1.500"),
    ]

    for payload, expected_error in cases:
        candidate = normalizer.normalize(payload, question=str(payload["normalized_question"]))
        validation = validator.validate(candidate, original_question=str(payload["normalized_question"]))
        assert not validation.accepted
        assert expected_error in validation.errors


def test_validator_rejects_unknown_origin_and_multihop_route() -> None:
    """未知始发地、多段路径必须澄清，不能被 LLM 候选反向放行。"""
    normalizer = LogisticsQueryPlannerV2Normalizer()
    validator = LogisticsQueryPlannerV2Validator(registry=LogisticsQueryPlannerV2CapabilityRegistry())

    unknown_origin = normalizer.normalize(
        _route_payload("2025年广德至马鞍山17.5米车的平均运费", filters={"origin_place": "广德"}),
        question="2025年广德至马鞍山17.5米车的平均运费",
    )
    unknown_result = validator.validate(unknown_origin, original_question="2025年广德至马鞍山17.5米车的平均运费")
    assert not unknown_result.accepted
    assert "origin_not_normalized::广德" in unknown_result.errors

    multihop = normalizer.normalize(
        _route_payload("2025年合肥至马鞍山到南京17.5米车的平均运费"),
        question="2025年合肥至马鞍山到南京17.5米车的平均运费",
    )
    multihop_result = validator.validate(multihop, original_question="2025年合肥至马鞍山到南京17.5米车的平均运费")
    assert not multihop_result.accepted
    assert "multi_hop_route_requires_clarification" in multihop_result.errors


def test_planner_builds_shadow_query_plan_without_replacing_legacy_fallback() -> None:
    """编排器应生成 shadow QueryPlan；旧 planner 仍作为正式 fallback，不被自动替换。"""
    question = "2025年合肥到马鞍山17.5米车平均运费"
    old_plan = LogisticsDataQaPlan(intent="clarification", needs_clarification=True, clarification_questions=["旧 planner 澄清"])
    fake_parser = _FakeLlmParser({question: _route_payload(question)})
    planner = LogisticsQueryPlannerV2(
        enabled=True,
        mode="shadow",
        llm_parser=fake_parser,
        fallback=LogisticsQueryPlannerV2Fallback(legacy_planner=_FakeLegacyPlanner(old_plan)),
    )

    plan = planner.build_shadow_plan(question, trace_id="trace-v2")

    assert plan.domain == "logistics"
    assert plan.strategy == "DIRECT_RETRIEVAL"
    assert plan.query_key == "hist_route_pricing_analysis"
    assert plan.confidence == 0.95
    assert plan.slots.filters["origin_place"] == "合肥"
    assert plan.slots.filters["city"] == "马鞍山"
    assert plan.slots.time_range == {"years": [2025]}
    assert plan.slots.aggregations == ["avg"]
    assert plan.execution_policy.shadow_only is True
    assert plan.execution_policy.llm_can_execute is False
    assert plan.guardrail_decision.final_source == "llm_query_planner_v2_shadow"
    assert plan.rule_plan["intent"] == "clarification"
    assert fake_parser.calls[0]["allowed_query_keys"]
    assert "hist_route_pricing_analysis" in fake_parser.calls[0]["system_prompt"]


def test_planner_fails_closed_when_allowed_query_key_config_has_no_valid_entries() -> None:
    """灰度 query_key 配置全无效时必须 fail closed，不能退化为全能力放行。"""
    question = "2025年合肥到马鞍山17.5米车平均运费"
    old_plan = LogisticsDataQaPlan(intent="clarification", needs_clarification=True, clarification_questions=["旧 planner 澄清"])
    fake_parser = _FakeLlmParser({question: _route_payload(question)})
    planner = LogisticsQueryPlannerV2(
        enabled=True,
        mode="shadow",
        allowed_query_keys=["typo_query_key"],
        llm_parser=fake_parser,
        fallback=LogisticsQueryPlannerV2Fallback(legacy_planner=_FakeLegacyPlanner(old_plan)),
    )

    plan = planner.build_shadow_plan(question, trace_id="trace-invalid-config")

    assert planner.should_use() is False
    assert fake_parser.calls == []
    assert plan.strategy == "CLARIFY"
    assert plan.guardrail_decision.final_source == "legacy_rule_planner_fallback"
    assert "config_invalid::allowed_query_keys_no_valid_entries" in (plan.guardrail_decision.blocked_reason or "")


def test_fallback_returns_legacy_rule_plan_when_llm_disabled_or_validation_fails() -> None:
    """LLM 不可用或校验失败时必须回退旧 planner，并保留 fail-closed 审计原因。"""
    question = "2025年合肥到马鞍山17.5米车平均运费"
    old_plan = LogisticsDataQaPlan(intent="clarification", needs_clarification=True, clarification_questions=["旧 planner 澄清"])
    legacy = _FakeLegacyPlanner(old_plan)
    fallback = LogisticsQueryPlannerV2Fallback(legacy_planner=legacy)

    plan = fallback.to_query_plan(question=question, trace_id="trace-fb", reason="llm_disabled")

    assert legacy.questions == [question]
    assert plan.strategy == "CLARIFY"
    assert plan.query_key is None
    assert plan.clarification_questions == ["旧 planner 澄清"]
    assert plan.guardrail_decision.accepted is False
    assert plan.guardrail_decision.blocked_reason == "llm_disabled"
    assert plan.execution_policy.shadow_only is True

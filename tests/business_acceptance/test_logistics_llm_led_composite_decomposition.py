"""物流综合型问题必须由 LLM 主导拆分的回归测试。

本文件覆盖用户反馈：综合型问题可以回答，但拆分应建立在 LLM 语义理解之上，
规则层只能做安全校验、白名单回构和边界保护，不能纯靠规则直接拆分。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
from backend.app.domains.logistics.schemas.llm_understanding import LogisticsLlmGuardrailDecision, LogisticsLlmUnderstandingResult
from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.domains.logistics.services.llm_answer_presentation_service import LogisticsLlmAnswerPresentationService
from backend.app.domains.logistics.services.llm_understanding_guardrail_service import LogisticsLlmUnderstandingGuardrailService

COMPOSITE_QUESTION = "统计一下24年创维客户发货的项目地运费金额超过20万的收货地址，并分别列出询比价和招标的发运量"


def _llm_composite_sub_plans() -> list[dict[str, Any]]:
    """构造测试用的 LLM 结构化拆分结果。

    参数：无。
    返回值：LLM 候选拆分出的两个受控子计划；后续仍由 planner 校验 query_key、年份、客户和阈值。
    业务逻辑：第一个子问题查 2024 年创维历史高运费收货地址，第二个子问题查 2026 系统侧采购方式发运量。
    """

    return [
        {
            "section_label": "历史高运费收货地址",
            "source_clause": "24年创维客户发货的项目地运费金额超过20万的收货地址",
            "intent": "detail_list",
            "query_key": "hist_high_fee_addresses_by_customer",
            "metrics": ["total_fee", "shipment_mw"],
            "dimensions": ["address"],
            "filters": {"year": 2024, "customer_name": "创维", "threshold_fee": 200000},
            "group_by": ["address"],
            "sort": [{"field": "total_fee", "direction": "desc"}],
        },
        {
            "section_label": "2026采购方式发运量",
            "source_clause": "分别列出询比价和招标的发运量",
            "intent": "aggregate",
            "query_key": "sys_mw_by_procurement_type",
            "metrics": ["shipment_mw"],
            "dimensions": ["procurement_type"],
            "filters": {"year": 2026, "default_system_year": True},
            "group_by": ["procurement_type"],
            "sort": [{"field": "shipment_mw", "direction": "desc"}],
        },
    ]


class _FakeDb:
    """测试用空数据库会话，只承接历史快照提交/回滚。"""

    def commit(self) -> None:
        """提交测试事务；无需真实落库。"""

    def rollback(self) -> None:
        """回滚测试事务；无需真实落库。"""


class _FakeQueryLogRepository:
    """测试用查询日志仓库，避免依赖真实 sys_query_log。"""

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:  # noqa: ARG002
        """返回固定日志 ID，证明主链路已走完。"""
        return 1


class _NoopGuardrailService:
    """测试用 Guardrail：不提供 LLM 拆分候选。"""

    def evaluate(self, *, question: str, rule_plan: Any, trace_id: str | None = None, write_audit: bool = False) -> LogisticsLlmGuardrailDecision:  # noqa: ARG002
        """保持规则计划，不触发 LLM 候选增强。"""
        return LogisticsLlmGuardrailDecision(
            question=question,
            rule_intent=rule_plan.intent,
            rule_query_key=rule_plan.query_key,
            rule_needs_clarification=rule_plan.needs_clarification,
            rule_supported=rule_plan.intent not in {"clarification", "unsupported"},
            final_intent=rule_plan.intent,
            final_query_key=rule_plan.query_key,
            final_needs_clarification=rule_plan.needs_clarification,
            final_supported=rule_plan.intent not in {"clarification", "unsupported"},
        )

    def write_audit_log(self, *, trace_id: str | None, decision: LogisticsLlmGuardrailDecision) -> None:  # noqa: ARG002
        """测试场景不写审计日志。"""


class _LlmCompositeGuardrailService:
    """测试用 Guardrail：模拟 LLM 高置信识别出可拆分综合问题。"""

    def __init__(self, *, sub_plans: list[dict[str, Any]] | None = None) -> None:
        """保存本次测试注入的 LLM 子计划。"""
        self.sub_plans = sub_plans or _llm_composite_sub_plans()

    def evaluate(self, *, question: str, rule_plan: Any, trace_id: str | None = None, write_audit: bool = False) -> LogisticsLlmGuardrailDecision:  # noqa: ARG002
        """返回 LLM 主导的 composite_decomposed 候选，供 planner 做受控回构。"""
        return LogisticsLlmGuardrailDecision(
            question=question,
            guardrail_enabled=True,
            guardrail_mode="assist",
            sampled_in=True,
            entered_guardrail=True,
            llm_invoked=True,
            eligible_for_assist=True,
            assist_recommended=True,
            assist_applied=True,
            final_source="llm_assist",
            rule_intent=rule_plan.intent,
            rule_query_key=rule_plan.query_key,
            rule_needs_clarification=rule_plan.needs_clarification,
            rule_supported=rule_plan.intent not in {"clarification", "unsupported"},
            final_intent="composite",
            final_query_key="composite_decomposed",
            final_needs_clarification=False,
            final_supported=True,
            allowed_query_key_whitelist=["composite_decomposed"],
            llm_intent="comparison",
            llm_top_query_key="composite_decomposed",
            llm_candidate_query_keys=["composite_decomposed"],
            llm_filters={
                "decomposition_strategy": "top_level_conjunction",
                "sub_plans": self.sub_plans,
            },
            llm_confidence=0.97,
            llm_provider_mode="live",
        )

    def write_audit_log(self, *, trace_id: str | None, decision: LogisticsLlmGuardrailDecision) -> None:  # noqa: ARG002
        """测试场景不写审计日志。"""


class _FakeLlmUnderstandingService:
    """测试用 LLM 理解服务：返回可审计的复合拆分候选。"""

    def __init__(self, *, sub_plans: list[dict[str, Any]] | None = None) -> None:
        """保存测试用子计划并记录调用次数。"""
        self.sub_plans = sub_plans or _llm_composite_sub_plans()
        self.calls = 0
        self.allowed_query_keys: list[str] | None = None

    def understand(
        self,
        question: str,
        *,
        allowed_query_keys: list[str] | None = None,
    ) -> LogisticsLlmUnderstandingResult:
        """模拟真实 LLM 输出 composite_decomposed 顶层候选。

        参数：
            question: 原始业务问题。
            allowed_query_keys: Guardrail 下发给 LLM 的白名单。
        返回值：LLM 结构化理解结果，包含顶层拆分策略和子计划列表。
        """
        self.calls += 1
        self.allowed_query_keys = allowed_query_keys
        return LogisticsLlmUnderstandingResult(
            normalized_question=question,
            intent="comparison",
            filters={
                "decomposition_strategy": "top_level_conjunction",
                "sub_plans": self.sub_plans,
            },
            source_scope="mixed",
            candidate_query_keys=["composite_decomposed"],
            confidence=0.97,
            provider_mode="live",
        )


class _FakeNonCompositeLlmUnderstandingService(_FakeLlmUnderstandingService):
    """测试用 LLM 理解服务：在复合策略例外场景中返回非 composite 候选。"""

    def understand(
        self,
        question: str,
        *,
        allowed_query_keys: list[str] | None = None,
    ) -> LogisticsLlmUnderstandingResult:
        """模拟 LLM 错误地把复合策略例外改写成普通 A 类 query_key。"""
        self.calls += 1
        self.allowed_query_keys = allowed_query_keys
        return LogisticsLlmUnderstandingResult(
            normalized_question=question,
            intent="ranking",
            filters={"year": 2024},
            source_scope="historical",
            candidate_query_keys=["hist_total_fee_city_rank"],
            confidence=0.97,
            provider_mode="live",
        )


class _FakeLogisticsRepository:
    """测试用物流仓库，只实现复合拆分涉及的两个子查询。"""

    def hist_high_fee_addresses_by_customer(self, *, year: int, customer_name: str, threshold_fee: int) -> list[dict[str, Any]]:
        """返回历史高运费收货地址测试数据。"""
        assert year == 2024
        assert customer_name == "创维"
        assert threshold_fee == 200000
        return [
            {
                "address": "安徽省合肥市测试项目地",
                "province": "安徽",
                "city": "合肥",
                "total_fee": 260000,
                "shipment_mw": 18.5,
                "row_count": 3,
            }
        ]

    def sys_mw_by_procurement_type(self, *, year: int) -> list[dict[str, Any]]:
        """返回 2026 系统侧采购方式发运量测试数据。"""
        assert year == 2026
        return [
            {"procurement_type": "询比价", "shipment_mw": 12.3, "task_count": 2},
            {"procurement_type": "招标", "shipment_mw": 45.6, "task_count": 4},
        ]


def _build_service(*, guardrail_service: Any) -> LogisticsDataQaService:
    """构造隔离外部依赖的物流问答服务。

    参数：
        guardrail_service: 测试注入的 Guardrail 服务。
    返回值：可直接执行 query 的服务实例。
    """

    return LogisticsDataQaService(
        db=_FakeDb(),
        repository=_FakeLogisticsRepository(),
        planner=LogisticsDataQaPlanner(),
        query_log_repository=_FakeQueryLogRepository(),
        guardrail_service=guardrail_service,
        answer_presentation_service=LogisticsLlmAnswerPresentationService(enabled=False),
    )


def test_rule_planner_must_not_decompose_composite_without_llm() -> None:
    """规则 planner 不能纯靠关键词直接拆分综合型问题。

    参数：无。
    返回值：无；通过断言确认没有 LLM 候选时不会产生 composite_decomposed 计划。
    业务逻辑：复合问题是否可拆、如何拆，应由 LLM 语义理解主导；规则层最多保守拒答/追问。
    """

    plan = LogisticsDataQaPlanner().build_plan(COMPOSITE_QUESTION)

    assert plan.query_key != "composite_decomposed"
    assert plan.intent in {"clarification", "unsupported"}


def test_service_does_not_answer_composite_when_llm_decomposition_missing() -> None:
    """没有 LLM 拆分候选时，服务不能用规则兜底强行回答综合型问题。

    参数：无。
    返回值：无；通过断言确认 no-op Guardrail 下不会执行复合拆分。
    业务逻辑：如果 LLM 不可用或未给出可信拆分，系统应保持保守边界，而不是用规则猜测拆分。
    """

    service = _build_service(guardrail_service=_NoopGuardrailService())
    result = service.query(LogisticsDataQaQueryRequest(question=COMPOSITE_QUESTION), trace_id="no-llm-composite")

    assert result.query_plan.query_key != "composite_decomposed"
    assert not result.supported


def test_guardrail_allows_llm_composite_candidate_for_policy_locked_question() -> None:
    """规则层命中旧拒答策略时，仍允许 LLM 给出顶层复合拆分候选。

    参数：无。
    返回值：无；断言真实 Guardrail 会调用 LLM，并只放行 composite_decomposed 白名单候选。
    业务逻辑：旧规则只能说明“历史高运费地址内部采购方式拆分”不可靠，不能阻止 LLM 将整句理解成两个独立子问题。
    """

    rule_plan = LogisticsDataQaPlanner().build_plan(COMPOSITE_QUESTION)
    fake_llm = _FakeLlmUnderstandingService()
    guardrail = LogisticsLlmUnderstandingGuardrailService(
        llm_service=fake_llm,  # type: ignore[arg-type]
        enabled=True,
        mode="assist",
        sample_rate=1.0,
        min_confidence=0.8,
        audit_enabled=False,
    )

    decision = guardrail.evaluate(question=COMPOSITE_QUESTION, rule_plan=rule_plan, write_audit=False)

    assert fake_llm.calls == 1
    assert fake_llm.allowed_query_keys is not None
    assert "composite_decomposed" in fake_llm.allowed_query_keys
    assert decision.assist_applied
    assert decision.final_query_key == "composite_decomposed"
    assert decision.final_source == "llm_assist"


def test_guardrail_rejects_non_composite_candidate_for_policy_locked_question() -> None:
    """旧拒答策略例外只允许 LLM 输出 composite_decomposed，不允许改写成其它 A 类 query_key。

    参数：无。
    返回值：无；断言 Guardrail 不会借复合例外放行普通候选。
    业务逻辑：复合例外只解决“是否是两个独立子问”的判断，不是通用 unsupported 绕行通道。
    """

    rule_plan = LogisticsDataQaPlanner().build_plan(COMPOSITE_QUESTION)
    fake_llm = _FakeNonCompositeLlmUnderstandingService()
    guardrail = LogisticsLlmUnderstandingGuardrailService(
        llm_service=fake_llm,  # type: ignore[arg-type]
        enabled=True,
        mode="assist",
        sample_rate=1.0,
        min_confidence=0.8,
        audit_enabled=False,
    )

    decision = guardrail.evaluate(question=COMPOSITE_QUESTION, rule_plan=rule_plan, write_audit=False)

    assert fake_llm.calls == 1
    assert not decision.assist_applied
    assert decision.final_query_key != "hist_total_fee_city_rank"
    assert decision.blocked_reason == "composite_policy_requires_composite_candidate"


def test_service_uses_llm_led_decomposition_then_rules_validate_and_execute() -> None:
    """LLM 给出可信拆分后，规则层校验并执行白名单子查询。

    参数：无。
    返回值：无；通过断言验证最终计划带有 LLM 来源标记，并合并两个子查询结果。
    业务逻辑：LLM 负责识别顶层并列子问题；后端规则负责校验 query_key、字段能力和过滤条件，再执行确定性仓储查询。
    """

    service = _build_service(guardrail_service=_LlmCompositeGuardrailService())
    result = service.query(LogisticsDataQaQueryRequest(question=COMPOSITE_QUESTION), trace_id="llm-led-composite")

    assert result.supported
    assert result.query_plan.query_key == "composite_decomposed"
    assert result.query_plan.filters["decomposition_source"] == "llm_guardrail"
    assert result.query_plan.filters["sub_query_keys"] == [
        "hist_high_fee_addresses_by_customer",
        "sys_mw_by_procurement_type",
    ]
    assert len(result.result_table.rows) == 3
    assert any(row.get("section") == "历史高运费收货地址" for row in result.result_table.rows)
    assert any(row.get("procurement_type") == "询比价" for row in result.result_table.rows)
    assert "LLM" in "\n".join(result.calculation_logic + result.warnings)


def test_llm_led_decomposition_keeps_ton_unit_guard() -> None:
    """即使 LLM 给出拆分，用户明确要吨口径时也不能替换成 MW 子查询。

    参数：无。
    返回值：无；断言规则安全校验会拒绝不支持的吨口径。
    业务逻辑：LLM 负责语义拆分，但单位能力边界仍由后端规则 fail-closed 保护。
    """

    question = "统计一下24年创维客户发货的项目地运费金额超过20万的收货地址，并分别列出询比价和招标的发运量吨"
    sub_plans = _llm_composite_sub_plans()
    sub_plans[1] = {**sub_plans[1], "source_clause": "分别列出询比价和招标的发运量吨"}
    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))

    result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-ton-guard")

    assert result.query_plan.query_key != "composite_decomposed"
    assert not result.supported
    assert result.needs_clarification
    assert "吨重" in "\n".join(result.clarification_questions + result.warnings + result.calculation_logic)


def test_llm_led_decomposition_rejects_back_reference_subset_split() -> None:
    """LLM 拆分结果如果把“这些地址”回指误当全局采购方式，也必须拒绝执行。

    参数：无。
    返回值：无；断言后端规则不会把历史子集采购方式拆分替换成 2026 全局统计。
    业务逻辑：LLM 主导不等于盲信；规则层必须拦截回指前一个子结果的二次拆分。
    """

    question = "统计一下24年创维客户发货的项目地运费金额超过20万的收货地址，并把这些地址分别列出询比价和招标的发运量"
    sub_plans = _llm_composite_sub_plans()
    sub_plans[1] = {**sub_plans[1], "source_clause": "把这些地址分别列出询比价和招标的发运量"}
    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))

    result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-backref-guard")

    assert result.query_plan.query_key != "composite_decomposed"
    assert not result.supported


def test_llm_led_decomposition_rejects_back_reference_even_when_llm_omits_it() -> None:
    """原问题含“这些地址”回指时，LLM source_clause 省略回指也必须拒绝。

    参数：无。
    返回值：无；断言回指保护基于原始问题定位，而不是盲信 LLM 子句。
    业务逻辑：避免 LLM 把历史子集采购方式拆分改写成 2026 全局采购方式统计。
    """

    question = "统计一下24年创维客户发货的项目地运费金额超过20万的收货地址，并把这些地址分别列出询比价和招标的发运量"
    service = _build_service(guardrail_service=_LlmCompositeGuardrailService())

    result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-backref-omitted")

    assert result.query_plan.query_key != "composite_decomposed"
    assert not result.supported


def test_llm_led_decomposition_rejects_extra_or_unknown_sub_plan() -> None:
    """LLM 返回额外子计划时必须 fail-closed，不能静默丢弃漏答。

    参数：无。
    返回值：无；断言含第三个子问的拆分不会被回构成复合计划。
    业务逻辑：综合问题必须完整回答，未知/额外子计划不能被忽略。
    """

    sub_plans = _llm_composite_sub_plans() + [
        {
            "source_clause": "再按承运商列出费用排名",
            "intent": "ranking",
            "query_key": "carrier_metric_ranking",
            "filters": {"year": 2024},
        }
    ]
    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))

    result = service.query(LogisticsDataQaQueryRequest(question=COMPOSITE_QUESTION), trace_id="llm-extra-subplan")

    assert result.query_plan.query_key != "composite_decomposed"
    assert not result.supported


def test_llm_led_decomposition_rejects_ungrounded_source_clause() -> None:
    """LLM 子句必须来自原始问题，幻觉出来的子句不能回构受控计划。

    参数：无。
    返回值：无；断言 source_clause 无法在原问题中定位时拒绝执行。
    业务逻辑：LLM 负责语义拆分，但每个子句必须可追溯到用户原文。
    """

    sub_plans = _llm_composite_sub_plans()
    sub_plans[0] = {**sub_plans[0], "source_clause": "2025年某客户高运费地址超过50万"}
    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))

    result = service.query(LogisticsDataQaQueryRequest(question=COMPOSITE_QUESTION), trace_id="llm-ungrounded-clause")

    assert result.query_plan.query_key != "composite_decomposed"
    assert not result.supported


def test_llm_led_decomposition_rejects_slot_conflict_with_original_question() -> None:
    """LLM 槽位与原问题确定性抽取冲突时必须拒绝，不能采信错误槽位。

    参数：无。
    返回值：无；断言 24 年问题被 LLM 写成 2023 年时不会执行。
    业务逻辑：规则层只做校验和回构，关键槽位必须与原文一致。
    """

    sub_plans = deepcopy(_llm_composite_sub_plans())
    sub_plans[0]["filters"]["year"] = 2023
    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))

    result = service.query(LogisticsDataQaQueryRequest(question=COMPOSITE_QUESTION), trace_id="llm-slot-conflict")

    assert result.query_plan.query_key != "composite_decomposed"
    assert not result.supported


def test_llm_led_decomposition_rejects_uncovered_original_subquestion() -> None:
    """原问题还有未被 LLM source_clause 覆盖的第三诉求时必须拒绝。

    参数：无。
    返回值：无；断言 LLM 漏报第三子问时不会静默漏答后仍返回 composite。
    业务逻辑：LLM 主导拆分必须完整覆盖用户综合问题，规则层负责校验覆盖性。
    """

    question = f"{COMPOSITE_QUESTION}，并统计2026年华东总运费"
    service = _build_service(guardrail_service=_LlmCompositeGuardrailService())

    result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-uncovered-subquestion")

    assert result.query_plan.query_key != "composite_decomposed"
    assert not result.supported


def test_llm_led_decomposition_rejects_overbroad_overlapping_source_clause() -> None:
    """LLM source_clause 覆盖整句或与另一子句重叠时必须拒绝。

    参数：无。
    返回值：无；断言过宽 source_clause 不能通过覆盖性校验。
    业务逻辑：避免 LLM 用整句作为某个子计划 source_clause，从而掩盖漏报第三诉求。
    """

    question = f"{COMPOSITE_QUESTION}，并统计2026年华东总运费"
    sub_plans = deepcopy(_llm_composite_sub_plans())
    sub_plans[0]["source_clause"] = question
    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))

    result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-overbroad-clause")

    assert result.query_plan.query_key != "composite_decomposed"
    assert not result.supported


def test_llm_led_decomposition_rejects_procurement_clause_with_unsupported_customer_filter() -> None:
    """采购方式全局统计子句带客户限定时必须拒绝，不能静默丢弃限定。

    参数：无。
    返回值：无；断言当前全局采购方式 query_key 不会忽略客户过滤条件后执行。
    业务逻辑：LLM 可以提出子计划，但规则层必须校验目标子查询是否支持原文限定。
    """

    question = "统计一下24年创维客户发货的项目地运费金额超过20万的收货地址，并分别列出创维客户询比价和招标的发运量"
    sub_plans = deepcopy(_llm_composite_sub_plans())
    sub_plans[1]["source_clause"] = "分别列出创维客户询比价和招标的发运量"
    sub_plans[1]["filters"]["customer_name"] = "创维"
    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))

    result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-procurement-extra-filter")

    assert result.query_plan.query_key != "composite_decomposed"
    assert not result.supported


def test_llm_led_decomposition_rejects_procurement_clause_with_implicit_customer_qualifier() -> None:
    """采购方式子句出现无“客户”后缀的客户名时也必须拒绝。

    参数：无。
    返回值：无；断言 `创维询比价发运量` 不会被降级为全局采购方式发运量。
    业务逻辑：采购方式子查询当前不支持客户限定，规则层必须用高运费子句中的客户槽位反查子句文本。
    """

    question = "统计一下24年创维客户发货的项目地运费金额超过20万的收货地址，并分别列出创维询比价和招标的发运量"
    sub_plans = deepcopy(_llm_composite_sub_plans())
    sub_plans[1]["source_clause"] = "分别列出创维询比价和招标的发运量"
    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))

    result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-procurement-implicit-customer")

    assert result.query_plan.query_key != "composite_decomposed"
    assert not result.supported


def test_llm_led_decomposition_rejects_procurement_clause_with_region_or_month_qualifier() -> None:
    """采购方式子句出现区域或月份限定时必须拒绝，不能静默查全局。

    参数：无。
    返回值：无；断言 `华东1月询比价发运量` 不会被降级为 2026 全局采购方式发运量。
    业务逻辑：当前 sys_mw_by_procurement_type 不支持区域/月度限定，LLM 省略 filters 也要基于子句 fail-closed。
    """

    question = "统计一下24年创维客户发货的项目地运费金额超过20万的收货地址，并分别列出华东1月询比价和招标的发运量"
    sub_plans = deepcopy(_llm_composite_sub_plans())
    sub_plans[1]["source_clause"] = "分别列出华东1月询比价和招标的发运量"
    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))

    result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-procurement-region-month")

    assert result.query_plan.query_key != "composite_decomposed"
    assert not result.supported


def test_llm_led_decomposition_rejects_procurement_clause_with_nonfirst_implicit_qualifier() -> None:
    """采购方式子句在第二个采购方式词附近出现隐式实体限定时也必须拒绝。

    参数：无。
    返回值：无；断言 `询比价和海尔招标` 不会被当作全局采购方式发运量。
    业务逻辑：字段能力校验要覆盖整句残留实体，而不是只检查第一个采购方式词前缀。
    """

    question = "统计一下24年创维客户发货的项目地运费金额超过20万的收货地址，并分别列出询比价和海尔招标的发运量"
    sub_plans = deepcopy(_llm_composite_sub_plans())
    sub_plans[1]["source_clause"] = "分别列出询比价和海尔招标的发运量"
    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))

    result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-procurement-nonfirst-qualifier")

    assert result.query_plan.query_key != "composite_decomposed"
    assert not result.supported


def test_llm_led_decomposition_rejects_high_fee_subplan_with_unsupported_extra_filter() -> None:
    """高运费地址子计划携带未支持 filters 时必须拒绝，不能静默忽略。

    参数：无。
    返回值：无；断言 LLM 给 high_fee 子计划加入 region_name 时不会执行。
    业务逻辑：规则回构只能接受实际执行子查询支持的槽位，额外过滤条件必须 fail-closed。
    """

    sub_plans = deepcopy(_llm_composite_sub_plans())
    sub_plans[0]["filters"]["region_name"] = "华东"
    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))

    result = service.query(LogisticsDataQaQueryRequest(question=COMPOSITE_QUESTION), trace_id="llm-high-fee-extra-filter")

    assert result.query_plan.query_key != "composite_decomposed"
    assert not result.supported


def test_llm_led_decomposition_rejects_high_fee_source_clause_with_unsupported_region_qualifier() -> None:
    """高运费地址 source_clause 自身包含区域限定时也必须拒绝。

    参数：无。
    返回值：无；断言 LLM 未写 filters 但 source_clause 含华东时不会静默忽略区域。
    业务逻辑：字段能力边界不能只依赖 LLM filters，原文子句中的 unsupported qualifier 也必须 fail-closed。
    """

    question = "统计一下24年华东创维客户发货的项目地运费金额超过20万的收货地址，并分别列出询比价和招标的发运量"
    sub_plans = deepcopy(_llm_composite_sub_plans())
    sub_plans[0]["source_clause"] = "24年华东创维客户发货的项目地运费金额超过20万的收货地址"
    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))

    result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-high-fee-source-region")

    assert result.query_plan.query_key != "composite_decomposed"
    assert not result.supported

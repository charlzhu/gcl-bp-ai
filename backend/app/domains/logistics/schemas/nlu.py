from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


LogisticsNluIntent = Literal[
    "aggregate",
    "ranking",
    "comparison",
    "detail",
    "status_quality",
    "clarification",
    "unsupported",
    "multi_intent",
    "unknown",
]
LogisticsNluSource = Literal["rule", "llm", "hybrid"]
LogisticsNluSourceScope = Literal["historical_2023_2025", "system_2026", "mixed", "unknown"]
LogisticsNluRouteSuggestion = Literal["answerable", "clarification", "unsupported", "multi_intent"]


class LogisticsNluSubQuestion(BaseModel):
    """物流域多问题拆解后的子问题结构。

    参数：
        raw_question: 子问题原始文本。
        normalized_question: 子问题术语归一后的文本。
        intent: 子问题意图类型。
        metrics: 子问题涉及的指标槽位。
        dimensions: 子问题涉及的维度槽位。
        filters: 子问题过滤条件槽位。
        time_range: 子问题时间槽位。
        source_scope: 子问题数据来源层判断。
        candidate_query_keys: 子问题候选 query_key。
        route_suggestion: 子问题建议路由。
        needs_clarification: 子问题是否需要澄清。
        missing_slots: 子问题当前缺失的关键口径槽位。
        unsupported: 子问题是否暂不支持。

    返回：
        只描述理解层结果，不触发多 query 执行。
    """

    raw_question: str = ""
    normalized_question: str = ""
    intent: LogisticsNluIntent = "unknown"
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    time_range: dict[str, Any] = Field(default_factory=dict)
    source_scope: LogisticsNluSourceScope = "unknown"
    candidate_query_keys: list[str] = Field(default_factory=list)
    route_suggestion: LogisticsNluRouteSuggestion = "clarification"
    needs_clarification: bool = False
    missing_slots: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    unsupported: bool = False
    unsupported_reason: str = ""
    confidence: float = 0.0


class LogisticsNluResult(BaseModel):
    """物流域自然语言理解中枢统一输出结构。

    说明：
        1. 本结构只用于后端内部诊断、评测和未来受控接入，不直接替代 data-qa 响应；
        2. LLM 只能贡献候选理解结果，不能直接驱动 SQL、查询或最终边界裁决；
        3. B/C 边界以规则层和 Guardrail 为最终依据，NLU Center 只输出可解释证据。

    参数：
        raw_question: 用户原始问题。
        normalized_question: 术语归一后的问题。
        is_multi_intent: 是否识别为多问题。
        intent: 主意图类型。
        sub_questions: 多问题拆解结果。
        metrics: 指标槽位。
        dimensions: 维度槽位。
        filters: 条件槽位。
        time_range: 时间槽位。
        source_scope: 数据来源层。
        candidate_query_keys: 候选 query_key 列表。
        needs_clarification: 是否建议澄清。
        missing_slots: 当前缺失的关键口径槽位，用于 B 类追问和审计。
        clarification_questions: 澄清问题。
        unsupported: 是否建议暂不支持。
        unsupported_reason: 不支持原因。
        confidence: 理解层置信度。
        nlu_source: 理解结果来源。
        guardrail_decision: Guardrail 诊断决策摘要。
        route_suggestion: 理解层建议路由。
        risk_flags: 风险标记。
        normalized_terms: 术语归一命中映射。
        rule_plan: 规则 planner 原始结果快照。
        llm_result: LLM 理解候选快照。

    返回：
        可被 planner / guardrail / 评测脚本消费的统一理解结果。
    """

    raw_question: str
    normalized_question: str = ""
    is_multi_intent: bool = False
    intent: LogisticsNluIntent = "unknown"
    sub_questions: list[LogisticsNluSubQuestion] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    time_range: dict[str, Any] = Field(default_factory=dict)
    source_scope: LogisticsNluSourceScope = "unknown"
    candidate_query_keys: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    missing_slots: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    unsupported: bool = False
    unsupported_reason: str = ""
    confidence: float = 0.0
    nlu_source: LogisticsNluSource = "rule"
    guardrail_decision: str = ""
    route_suggestion: LogisticsNluRouteSuggestion = "clarification"
    risk_flags: list[str] = Field(default_factory=list)
    normalized_terms: dict[str, str] = Field(default_factory=dict)
    rule_plan: dict[str, Any] = Field(default_factory=dict)
    llm_result: dict[str, Any] = Field(default_factory=dict)

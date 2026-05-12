from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LogisticsLlmUnderstandingResult(BaseModel):
    """物流域 LLM 理解层输出结构。

    说明：
        1. 当前结构只用于影子模式 / PoC，不直接暴露给前端；
        2. LLM 只能输出语言理解层候选，不允许直接生成 SQL 或最终业务答案；
        3. candidate_query_keys 必须仍受现有白名单约束，最终裁决仍由规则层执行。
    """

    normalized_question: str = ""
    intent: Literal[
        "aggregate",
        "ranking",
        "comparison",
        "detail",
        "composite",
        "clarification",
        "unsupported",
        "unknown",
    ] = "unknown"
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    time_range: dict[str, Any] = Field(default_factory=dict)
    source_scope: Literal["historical", "system_2026", "mixed", "unknown"] = "unknown"
    candidate_query_keys: list[str] = Field(default_factory=list)
    normalized_terms: dict[str, str] = Field(default_factory=dict)
    needs_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)
    unsupported_reason: str | None = None
    confidence: float = 0.0
    provider_mode: Literal["live", "disabled", "error"] = "disabled"
    provider_error: str | None = None
    llm_model_name: str | None = None


class LogisticsLlmClarificationAssistResult(BaseModel):
    """物流域澄清辅助输出结构。

    说明：
        1. 当前结构只服务于“规则层已明确判定必须澄清”的问题；
        2. LLM 只能补充缺口径识别和业务化追问候选，不能把问题改判成 success / unsupported；
        3. 最终是否采用这些追问，仍由规则层和受控服务层决定。
    """

    normalized_question: str = ""
    clarification_category: str | None = None
    missing_slots: list[str] = Field(default_factory=list)
    slot_reasons: dict[str, str] = Field(default_factory=dict)
    suggested_questions: list[str] = Field(default_factory=list)
    business_summary: str | None = None
    confidence: float = 0.0
    provider_mode: Literal["live", "disabled", "error"] = "disabled"
    provider_error: str | None = None
    llm_model_name: str | None = None


class LogisticsLlmClarificationAssistAuditRecord(BaseModel):
    """物流域澄清辅助审计日志结构。

    说明：
        1. 用于记录规则澄清类别、LLM 识别出的缺口径以及最终采用情况；
        2. 当前按 JSONL 记审计，不引入新的数据库表；
        3. 便于后续复盘“业务问题为什么这样追问”。
    """

    created_at: str
    trace_id: str | None = None
    question: str
    clarification_category: str | None = None
    clarification_reason: str | None = None
    rule_missing_slots: list[str] = Field(default_factory=list)
    rule_questions: list[str] = Field(default_factory=list)
    assist_enabled: bool = False
    assist_mode: Literal["off", "shadow", "assist"] = "off"
    sampled_in: bool = False
    llm_invoked: bool = False
    llm_provider_mode: Literal["live", "disabled", "error"] = "disabled"
    llm_missing_slots: list[str] = Field(default_factory=list)
    llm_confidence: float = 0.0
    applied: bool = False
    final_missing_slots: list[str] = Field(default_factory=list)
    final_questions: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None


class LogisticsLlmUnsupportedAssistResult(BaseModel):
    """物流域拒答解释辅助输出结构。

    说明：
        1. 当前结构只服务于“规则层已明确判定 unsupported”的问题；
        2. LLM 只能把拒答原因改写得更业务可理解，并给出可改问方向；
        3. LLM 不能把 C 类改成 A 类，也不能生成 SQL、查数或编造结果。
    """

    normalized_question: str = ""
    unsupported_category: str | None = None
    business_reason: str = ""
    suggestions: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    provider_mode: Literal["live", "disabled", "error"] = "disabled"
    provider_error: str | None = None
    llm_model_name: str | None = None


class LogisticsLlmUnsupportedAssistAuditRecord(BaseModel):
    """物流域拒答解释辅助审计日志结构。

    说明：
        1. 记录规则拒答类别、规则原因、LLM 解释和最终是否采用；
        2. 当前按 JSONL 写入，避免提前增加数据库表；
        3. 便于复盘真实用户问法为什么被拒答以及给出了什么可改问方向。
    """

    created_at: str
    trace_id: str | None = None
    question: str
    unsupported_category: str | None = None
    rule_reason: str | None = None
    rule_suggestions: list[str] = Field(default_factory=list)
    assist_enabled: bool = False
    assist_mode: Literal["off", "shadow", "assist"] = "off"
    sampled_in: bool = False
    llm_invoked: bool = False
    llm_provider_mode: Literal["live", "disabled", "error"] = "disabled"
    llm_business_reason: str = ""
    llm_confidence: float = 0.0
    applied: bool = False
    final_reason: str | None = None
    final_suggestions: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None


class LogisticsLlmShadowComparison(BaseModel):
    """物流域影子模式对比结果。

    说明：
        1. 该结构用于比较规则 planner 与 LLM 理解层输出；
        2. 不会改变当前正式 data-qa 主链路的最终执行结果；
        3. 便于 PoC 报告统计一致率、误判和潜在收益。
    """

    question: str
    rule_intent: str
    rule_query_key: str | None = None
    rule_needs_clarification: bool = False
    rule_supported: bool = True
    llm_intent: str
    llm_top_query_key: str | None = None
    llm_needs_clarification: bool = False
    llm_supported: bool = True
    llm_confidence: float = 0.0
    same_query_key: bool = False
    llm_helped_recover_query_key: bool = False
    llm_misjudged: bool = False


class LogisticsLlmGuardrailDecision(BaseModel):
    """物流域 LLM Guardrail 决策结果。

    说明：
        1. 该结构用于“规则优先、LLM 只做 A 类候选增强”的 PoC 决策记录；
        2. 当前只服务于影子模式 / candidate assist，不直接替换正式 planner；
        3. 重点用于审计：为什么允许增强、为什么被拦截、最终仍由谁裁决。
    """

    question: str
    guardrail_enabled: bool = False
    guardrail_mode: Literal["off", "shadow", "assist"] = "off"
    sampled_in: bool = False
    entered_guardrail: bool = False
    llm_invoked: bool = False
    rule_intent: str
    rule_query_key: str | None = None
    rule_needs_clarification: bool = False
    rule_supported: bool = True
    policy_locked: bool = False
    policy_decision_type: Literal["clarification", "unsupported"] | None = None
    policy_category: str | None = None
    eligible_for_assist: bool = False
    assist_recommended: bool = False
    assist_applied: bool = False
    final_source: Literal["rule", "llm_assist"] = "rule"
    final_intent: str = "unknown"
    final_query_key: str | None = None
    final_needs_clarification: bool = False
    final_supported: bool = True
    allowed_query_key_whitelist: list[str] = Field(default_factory=list)
    llm_intent: str = "unknown"
    llm_top_query_key: str | None = None
    llm_candidate_query_keys: list[str] = Field(default_factory=list)
    llm_filters: dict[str, Any] = Field(default_factory=dict)
    llm_time_range: dict[str, Any] = Field(default_factory=dict)
    llm_normalized_terms: dict[str, str] = Field(default_factory=dict)
    llm_confidence: float = 0.0
    llm_provider_mode: Literal["live", "disabled", "error"] = "disabled"
    blocked_reason: str | None = None
    rollback_reason: str | None = None


class LogisticsLlmGuardrailAuditRecord(BaseModel):
    """物流域 Guardrail 审计日志结构。

    说明：
        1. 当前用于未来小流量 Candidate Assist 的审计留痕；
        2. 记录规则结果、LLM 候选、是否采样命中以及最终裁决来源；
        3. 当前写入 JSONL，避免提前引入新的数据库表。
    """

    created_at: str
    trace_id: str | None = None
    question: str
    guardrail_enabled: bool = False
    guardrail_mode: Literal["off", "shadow", "assist"] = "off"
    sampled_in: bool = False
    entered_guardrail: bool = False
    llm_invoked: bool = False
    policy_locked: bool = False
    policy_decision_type: Literal["clarification", "unsupported"] | None = None
    policy_category: str | None = None
    rule_intent: str
    rule_query_key: str | None = None
    rule_needs_clarification: bool = False
    rule_supported: bool = True
    llm_provider_mode: Literal["live", "disabled", "error"] = "disabled"
    llm_top_query_key: str | None = None
    llm_confidence: float = 0.0
    assist_recommended: bool = False
    assist_applied: bool = False
    final_source: Literal["rule", "llm_assist"] = "rule"
    final_intent: str = "unknown"
    final_query_key: str | None = None
    final_needs_clarification: bool = False
    final_supported: bool = True
    allowed_query_key_whitelist: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None
    rollback_reason: str | None = None

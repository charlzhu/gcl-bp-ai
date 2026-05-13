from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

QueryPlanningV2Strategy = Literal[
    "DIRECT_RETRIEVAL",
    "HYDE_RETRIEVAL",
    "QUERY_DECOMPOSITION",
    "QUERY_REWRITE_SIMPLIFY",
    "CLARIFY",
    "NO_ANSWER",
    "UNSUPPORTED",
]


class QueryPlanningV2Slots(BaseModel):
    """Query Planning V2 统一槽位结构。

    参数：
        metrics: 指标槽位，如 shipment_mw、total_fee。
        dimensions: 维度槽位，如 carrier、year。
        filters: 过滤条件，只承载受控字段和值，不承载 SQL。
        time_range: 时间范围快照，保留 LLM 候选或后端归一后的年份/月度范围。
        group_by: 分组字段。
        aggregations: 聚合算子槽位，如 avg、sum、count。
        compare_mode: 对比或趋势模式，如 year_compare、monthly_trend。
        sort: 排序字段和方向。
        limit: 结果条数限制。
        entities: 领域实体槽位，供订单、客户、供应商等实体归一化使用。

    返回：
        可审计、可回放的查询槽位快照。
    """

    model_config = ConfigDict(extra="forbid")

    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    time_range: dict[str, Any] = Field(default_factory=dict)
    group_by: list[str] = Field(default_factory=list)
    aggregations: list[str] = Field(default_factory=list)
    compare_mode: str | None = None
    sort: list[dict[str, Any]] = Field(default_factory=list)
    limit: int | None = None
    entities: dict[str, Any] = Field(default_factory=dict)


class QueryPlanningV2ExecutionPolicy(BaseModel):
    """Query Planning V2 执行安全策略。

    参数：
        shadow_only: 是否仅 shadow 诊断。Phase 3 默认只 shadow。
        executable: 是否可由既有受控 service/repository 执行。
        retrieval_only: 是否仅可用于检索增强，不能进入结构化查询。
        llm_can_execute: LLM 是否允许执行查询；必须恒为 False。
        sql_generation_allowed: 是否允许生成 SQL；必须恒为 False。
        allowed_query_keys: 可执行白名单 query_key。
        allowed_services: 可调用的受控服务名。

    返回：
        策略路由后的安全边界说明。
    """

    model_config = ConfigDict(extra="forbid")

    shadow_only: bool = True
    executable: bool = False
    retrieval_only: bool = False
    llm_can_execute: bool = False
    sql_generation_allowed: bool = False
    allowed_query_keys: list[str] = Field(default_factory=list)
    allowed_services: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_llm_and_sql_denied(self) -> "QueryPlanningV2ExecutionPolicy":
        """强制关闭 LLM 执行和 SQL 生成能力。

        参数：无。
        返回：归一化后的执行策略。
        业务逻辑：Query Planning V2 只规划，不让 LLM 查数或生成 SQL。
        """

        self.llm_can_execute = False
        self.sql_generation_allowed = False
        self.shadow_only = True
        return self


class QueryPlanningV2GuardrailDecision(BaseModel):
    """统一 Guardrail 决策摘要。

    参数：
        guardrail_enabled: 是否进入 Guardrail 流程。
        guardrail_mode: Guardrail 模式，如 rule、shadow、assist。
        final_source: 最终采用来源，Phase 3 通常为 rule / nlu_center / fail_closed。
        policy_locked: 是否被安全策略锁定，不能被 LLM 改写。
        accepted: 候选是否被接纳。
        blocked_reason: 拦截原因。
        notes: 可读审计说明。
        raw_decision: 原领域 Guardrail / NLU 决策快照。

    返回：
        可写入 query_plan 的 Guardrail 决策摘要。
    """

    model_config = ConfigDict(extra="forbid")

    guardrail_enabled: bool = True
    guardrail_mode: str = "rule"
    final_source: str = "rule"
    policy_locked: bool = True
    accepted: bool = True
    blocked_reason: str | None = None
    notes: list[str] = Field(default_factory=list)
    raw_decision: dict[str, Any] = Field(default_factory=dict)


class QueryPlanningV2AuditInfo(BaseModel):
    """Query Planning V2 审计信息。

    参数：
        trace_id: 请求追踪号。
        audit_logged: 本次计划是否已写入审计日志。
        audit_log_path: JSONL 审计日志路径。
        audit_message: 写日志失败等非阻断说明。

    返回：
        计划回放和问题定位所需的最小审计信息。
    """

    model_config = ConfigDict(extra="forbid")

    trace_id: str | None = None
    audit_logged: bool = False
    audit_log_path: str | None = None
    audit_message: str | None = None


class QueryPlanningV2SubQuery(BaseModel):
    """Query Planning V2 受控子查询。

    参数：
        sub_query_id: 子查询稳定 ID。
        source_clause: 子查询可回溯的原问题片段。
        domain: 子查询所属领域，默认继承物流。
        intent: 子查询意图。
        query_key: 子查询白名单 query_key。
        slots: 子查询槽位。
        executable: 是否可由受控 service 执行。
        merge_policy: 合并策略说明。
        guardrail_notes: 子查询 Guardrail 说明。

    返回：
        QUERY_DECOMPOSITION 策略下的受控子查询。
    """

    model_config = ConfigDict(extra="forbid")

    sub_query_id: str
    source_clause: str
    domain: str = "logistics"
    intent: str | None = None
    query_key: str | None = None
    slots: QueryPlanningV2Slots = Field(default_factory=QueryPlanningV2Slots)
    executable: bool = False
    merge_policy: str | None = None
    guardrail_notes: list[str] = Field(default_factory=list)


class QueryPlanningV2Plan(BaseModel):
    """Query Planning V2 统一查询计划。

    参数：
        schema_version: 稳定 schema 版本。
        domain: 问题所属业务域。
        original_question: 用户原始问题，必须保留。
        strategy: 策略枚举。
        intent: 受控意图。
        query_key: 白名单 query_key，不允许自由 SQL。
        slots: 统一槽位结构。
        rewritten_question: 改写问题，仅可辅助检索 / planner，不覆盖原问题。
        hyde_text: HYDE 假设文本，仅可辅助检索，不能作为事实答案。
        sub_queries: 受控子查询列表。
        clarification_questions: 澄清问题。
        no_answer_reason: 无答案原因。
        unsupported_reason: 不支持原因。
        guardrail_decision: Guardrail 决策。
        execution_policy: 执行安全策略。
        confidence: LLM QueryPlan 候选置信度；规则 planner 包装时可为空。
        rule_plan: 原规则 planner / NLU 结果快照。
        llm_result: LLM 候选快照。
        audit: 审计信息。
        warnings: 非阻断警告。

    返回：
        正式查询前的 shadow query_plan_v2 JSON。
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "query_plan_v2.0"
    domain: str
    original_question: str
    strategy: QueryPlanningV2Strategy
    intent: str | None = None
    query_key: str | None = None
    slots: QueryPlanningV2Slots = Field(default_factory=QueryPlanningV2Slots)
    rewritten_question: str | None = None
    hyde_text: str | None = None
    sub_queries: list[QueryPlanningV2SubQuery] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    no_answer_reason: str | None = None
    unsupported_reason: str | None = None
    guardrail_decision: QueryPlanningV2GuardrailDecision = Field(default_factory=QueryPlanningV2GuardrailDecision)
    execution_policy: QueryPlanningV2ExecutionPolicy = Field(default_factory=QueryPlanningV2ExecutionPolicy)
    confidence: float | None = None
    rule_plan: dict[str, Any] = Field(default_factory=dict)
    llm_result: dict[str, Any] = Field(default_factory=dict)
    audit: QueryPlanningV2AuditInfo = Field(default_factory=QueryPlanningV2AuditInfo)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_strategy_policy(self) -> "QueryPlanningV2Plan":
        """按策略强制归一执行边界。

        参数：无。
        返回：归一化后的 query_plan。
        业务逻辑：HYDE、改写、澄清和拒答均不能进入结构化执行；DIRECT / DECOMPOSE
        也只能由白名单 query_key 和既有受控服务执行。
        """

        policy = self.execution_policy
        policy.llm_can_execute = False
        policy.sql_generation_allowed = False
        if self.query_key and self.query_key not in policy.allowed_query_keys:
            policy.allowed_query_keys.append(self.query_key)

        if self.strategy == "HYDE_RETRIEVAL":
            policy.retrieval_only = True
            policy.executable = False
        elif self.strategy in {"QUERY_REWRITE_SIMPLIFY", "CLARIFY", "NO_ANSWER", "UNSUPPORTED"}:
            policy.executable = False
            if self.strategy != "QUERY_REWRITE_SIMPLIFY":
                policy.retrieval_only = False
        elif self.strategy == "DIRECT_RETRIEVAL":
            policy.retrieval_only = False
            policy.executable = bool(self.query_key)
        elif self.strategy == "QUERY_DECOMPOSITION":
            policy.retrieval_only = False
            policy.executable = bool(self.sub_queries or self.query_key == "composite_decomposed")
        return self


class QueryPlanningV2DiagnoseRequest(BaseModel):
    """Query Planning V2 诊断请求。

    参数：
        question: 用户原始问题。
        domain: 可选业务域；不填时服务按轻量规则路由。
        write_audit: 是否写入 JSONL 审计日志。

    返回：
        诊断接口请求模型。
    """

    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1, description="业务员自然语言问题")
    domain: str | None = Field(default=None, description="可选业务域：logistics / plan_bom")
    write_audit: bool = Field(default=True, description="是否写入 Query Planning V2 JSONL 审计日志")


__all__ = [
    "QueryPlanningV2AuditInfo",
    "QueryPlanningV2DiagnoseRequest",
    "QueryPlanningV2ExecutionPolicy",
    "QueryPlanningV2GuardrailDecision",
    "QueryPlanningV2Plan",
    "QueryPlanningV2Slots",
    "QueryPlanningV2Strategy",
    "QueryPlanningV2SubQuery",
]

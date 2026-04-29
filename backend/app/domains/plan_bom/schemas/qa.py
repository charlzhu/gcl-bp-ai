from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PlanBomNluCandidate(BaseModel):
    """计划 BOM 自然语言理解候选。

    参数：
        question: 用户原始问题。
        intent: 受控意图编码。
        slots: 已抽取并归一的槽位。
        missing_slots: 当前回答仍缺失的关键槽位。
        confidence: 规则和可选 LLM 辅助后的置信度。
        provider_mode: 理解来源，rule 表示规则层，live 表示 LLM 候选参与但仍已受控校验。
        guardrail_notes: Guardrail 决策说明，记录 LLM 候选是否被采纳或拦截。

    返回：
        本模型作为 QA 服务内部和评测脚本的可审计 NLU 输出。
    """

    question: str
    intent: str
    slots: dict[str, Any] = Field(default_factory=dict)
    missing_slots: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    provider_mode: Literal["rule", "disabled", "live", "error"] = "rule"
    guardrail_notes: list[str] = Field(default_factory=list)


class PlanBomQaStatus(BaseModel):
    """计划 BOM 问答状态。

    参数：
        code: 状态码，覆盖 OK、CLARIFICATION_REQUIRED、UNSUPPORTED_QUESTION、EMPTY_RESULT、EXECUTION_ERROR。
        message: 面向业务用户的状态说明。
        success: 接口主链路是否成功返回。
        severity: 前端展示级别。

    返回：
        统一状态结构，避免前端硬编码推断 A/B/C。
    """

    code: str
    message: str
    success: bool = True
    severity: Literal["info", "warning", "error"] = "info"


class PlanBomTableSpec(BaseModel):
    """计划 BOM 展示表格。

    参数：
        columns: 表格列名。
        rows: 表格行数据，所有事实必须来自 BOM 查询结果。

    返回：
        前端可直接渲染的结构化表格。
    """

    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class PlanBomPresentation(BaseModel):
    """计划 BOM 答案表达层输出。

    参数：
        display_type: 展示类型。
        title: 业务化标题。
        answer: 业务化主回答。
        highlights: 关键结论。
        table_spec: 明细表格。
        caveats: 数据口径和边界提醒。
        follow_up: B 类追问。
        unsupported_explanation: C 类拒答说明。
        debug: 调试信息，记录 fallback 和 LLM 状态。

    返回：
        BOM API 的 presentation 字段；LLM 校验失败时由确定性 fallback 生成。
    """

    display_type: Literal[
        "narrative",
        "table",
        "comparison_table",
        "summary_cards",
        "clarification",
        "unsupported",
        "empty_result",
        "mixed",
        "error",
    ] = "narrative"
    title: str = ""
    answer: str = ""
    highlights: list[str] = Field(default_factory=list)
    table_spec: PlanBomTableSpec | None = None
    caveats: list[str] = Field(default_factory=list)
    follow_up: dict[str, Any] | None = None
    unsupported_explanation: dict[str, Any] | None = None
    debug: dict[str, Any] = Field(default_factory=dict)


class PlanBomQaRequest(BaseModel):
    """计划 BOM 自然语言问答请求。

    参数：
        question: 用户自然语言问题。
        trace_id: 可选追踪号，用于脚本和 API 联调。

    返回：
        请求模型自身不返回业务数据，只承载输入。
    """

    question: str = Field(..., min_length=1, description="计划 BOM 自然语言问题")
    trace_id: str | None = None


class PlanBomQaResponse(BaseModel):
    """计划 BOM 自然语言问答响应。

    参数：
        question: 原始问题。
        domain: 固定为 plan_bom。
        classification: A/B/C/D 分类。
        status: 统一状态。
        nlu: NLU 受控候选。
        answer_summary: 确定性主回答摘要。
        result_table: 结构化结果表。
        raw_result: 既有 detail / compare 服务的原始受控结果快照。
        presentation: 展示编排层输出。
        warnings: 业务口径提醒。
        trace_events: 问答主链路明细节点，用于排查输入、理解、查询和表达过程。

    返回：
        面向前端和回归脚本的统一 BOM QA 结果。
    """

    question: str
    domain: Literal["plan_bom"] = "plan_bom"
    classification: Literal["A", "B", "C", "D"]
    status: PlanBomQaStatus
    nlu: PlanBomNluCandidate
    answer_summary: str
    result_table: PlanBomTableSpec = Field(default_factory=PlanBomTableSpec)
    raw_result: dict[str, Any] = Field(default_factory=dict)
    presentation: PlanBomPresentation | None = None
    warnings: list[str] = Field(default_factory=list)
    trace_events: list[dict[str, Any]] = Field(default_factory=list)


__all__ = [
    "PlanBomNluCandidate",
    "PlanBomPresentation",
    "PlanBomQaRequest",
    "PlanBomQaResponse",
    "PlanBomQaStatus",
    "PlanBomTableSpec",
]

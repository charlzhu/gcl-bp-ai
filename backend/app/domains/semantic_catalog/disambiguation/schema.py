"""
多候选消歧统一交互 — Schema 定义。

业务逻辑：
    本模块定义统一的多候选消歧数据结构。当业务值解析器（BusinessValueResolver）
    返回多个候选时，消歧服务使用这些 Schema 生成结构化的消歧请求和响应，
    让前端复用 BusinessChatPage 的对话式体验而不新增独立弹出式选择器。

    Schema 分为三组：
    1. 候选实体：DisambiguationCandidate（单个消歧候选）
    2. 消歧流程：DisambiguationRequest / DisambiguationResponse（请求与响应）
    3. 消歧确认：DisambiguationResolveRequest / DisambiguationResolveResponse（用户选择确认）

约束：
    - 不暴露 SQL、表名、字段名、query_key 等内部技术内容。
    - LLM 不直接计算或改写候选值。
    - 候选列表为空时服务层应返回空追问，不应生成假候选。
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DisambiguationCandidate(BaseModel):
    """消歧候选实体。

    参数：
        candidate_id: 候选唯一标识，用于后续消歧确认。
            格式建议为 "{entity_type}_{去重键}"（如 "carrier_顺丰物流"）。
        entity_type: 实体类型，如 carrier、customer、order_identity、filename、
            customer_instance、version。
        entity_value: 实体的实际值，消歧确认后传递给下游服务使用。
        display_label: 业务展示标签，前端显示给用户看的文本。
        description: 可选的辅助说明（如订单日期、版本号等）。
    """

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(..., description="候选唯一标识")
    entity_type: str = Field(..., description="实体类型")
    entity_value: str = Field(..., description="实际值")
    display_label: str = Field(..., description="业务展示标签")
    description: str | None = Field(default=None, description="辅助说明信息")


class DisambiguationRequest(BaseModel):
    """消歧请求（服务内部使用）。

    参数：
        session_id: 会话 ID，用于关联前后端交互。
        question: 原始用户问题，保留用于后续路由。
        domain: 业务域（logistics、plan_bom、business_analysis）。
        entity_type: 实体类型，与 DisambiguationCandidate 中的对应。
        candidates: 候选列表，至少包含 2 个候选才有消歧意义。
        context: 可选的额外上下文，如 user_id、trace_id 等。
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., description="会话 ID")
    question: str = Field(..., description="原始用户问题")
    domain: str = Field(..., description="业务域")
    entity_type: str = Field(..., description="实体类型")
    candidates: list[DisambiguationCandidate] = Field(
        ..., min_length=1, description="候选列表（至少 1 个）"
    )
    context: dict | None = Field(default=None, description="额外上下文")


class DisambiguationResponse(BaseModel):
    """消歧响应（返回给前端）。

    参数：
        session_id: 会话 ID。
        status: 消歧状态。
            - "needs_selection"：需要用户从候选列表中选择。
            - "resolved"：用户已完成选择，下游可继续执行。
        question: 原始用户问题。
        domain: 业务域。
        entity_type: 实体类型。
        candidates: 候选列表。
        follow_up_question: 业务化追问文本（如"找到多个匹配的承运商，请选择一个："）。
        resolved_candidate: 消歧完成后填充的用户选择结果；needs_selection 时为 None。
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., description="会话 ID")
    status: str = Field(default="needs_selection", description="消歧状态")
    question: str = Field(..., description="原始用户问题")
    domain: str = Field(..., description="业务域")
    entity_type: str = Field(..., description="实体类型")
    candidates: list[DisambiguationCandidate] = Field(
        ..., description="候选列表"
    )
    follow_up_question: str = Field(..., description="业务化追问文本")
    resolved_candidate: DisambiguationCandidate | None = Field(
        default=None, description="消歧完成后的用户选择"
    )


class DisambiguationResolveRequest(BaseModel):
    """消歧确认请求（前端 → 后端）。

    参数：
        session_id: 会话 ID。
        selected_candidate_id: 用户在候选列表中选择的 candidate_id。
        original_question: 可选的原始问题，用于后续路由。
        candidates: 可选的候选列表。前端在消歧 resolve 阶段需传入原候选列表
            供服务端校验。若未传入，服务端从会话存储中查找（当前 MVP 未实现会话存储，
            因此前端必须传入）。
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., description="会话 ID")
    selected_candidate_id: str = Field(..., description="用户选择的候选 ID")
    original_question: str | None = Field(default=None, description="原始问题")
    candidates: list[DisambiguationCandidate] = Field(
        default_factory=list,
        description="候选列表，供服务端校验用户选择",
    )


class DisambiguationResolveResponse(BaseModel):
    """消歧确认响应（后端 → 前端）。

    参数：
        session_id: 会话 ID。
        status: 固定为 "resolved"。
        selected: 用户选择的消歧候选。
        original_question: 原始问题，供前端继续问答流程。
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., description="会话 ID")
    status: str = Field(default="resolved", description="消歧状态")
    selected: DisambiguationCandidate = Field(..., description="用户选择的候选")
    original_question: str | None = Field(default=None, description="原始问题")


__all__ = [
    "DisambiguationCandidate",
    "DisambiguationRequest",
    "DisambiguationResponse",
    "DisambiguationResolveRequest",
    "DisambiguationResolveResponse",
]

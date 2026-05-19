from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

InventorySalesProductionQaClassification = Literal["A", "B", "C", "D"]


class InventorySalesProductionQaRequest(BaseModel):
    """产销存自然语言问答请求。

    参数：
        question: 用户自然语言问题。
        trace_id: 前端或网关传入的链路 ID，可为空。
        include_query_plan_v2_meta: 预留给后续统一 NL2SQL shadow 的开关；M4 默认不向用户暴露。
    返回：
        FastAPI 会将请求体校验为该模型后交给 QA 服务。
    """

    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1, max_length=1000)
    trace_id: str | None = None
    include_query_plan_v2_meta: bool = False


class InventorySalesProductionQaResponse(BaseModel):
    """产销存自然语言问答响应。

    参数：
        question: 用户原问题。
        domain/sub_domain: 经营分析产销存域标识，供前端会话归类。
        classification: A 成功、B 需澄清、C 暂不支持/无结果、D 系统错误。
        status: 用户可见状态，不包含内部 query_key、SQL 或表字段。
        answer_summary: 业务化摘要。
        result_table: 用户可见结构化结果表。
        presentation: 前端统一智能问答展示结构。
        warnings: 业务口径提示。
        trace_id: 链路 ID。
    返回：
        可被 WebUI 与流式 done 事件直接消费的响应对象。
    """

    model_config = ConfigDict(extra="forbid")

    question: str
    domain: str = "business_analysis"
    sub_domain: str = "inventory_sales_production"
    classification: InventorySalesProductionQaClassification
    status: dict[str, Any]
    answer_summary: str
    result_table: dict[str, Any] | None = None
    presentation: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
    trace_id: str | None = None


__all__ = [
    "InventorySalesProductionQaClassification",
    "InventorySalesProductionQaRequest",
    "InventorySalesProductionQaResponse",
]

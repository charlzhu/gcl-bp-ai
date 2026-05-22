"""LQG-8：统一业务问数流式接口的请求与响应 schema。

统一入口允许前端在 auto/logistics/plan_bom 三种模式下提交问题，
后端负责领域路由、确定性查询、LLM 流式表达和最终结果聚合。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BusinessQaStreamRequest(BaseModel):
    """统一业务问数流式请求。

    参数：
        question: 用户自然语言问题，禁止为空。
        domain_hint: 可选业务域提示（auto/logistics/plan_bom），
            auto 表示由后端自动识别；仅 logistics/plan_bom 在本轮接入。

    业务逻辑：
        经营分析/产销存暂不纳入本轮统一入口；若传入 business_analysis
        作为 domain_hint，后端按 unsupported 处理。
    """

    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1, description="用户自然语言问题")
    domain_hint: Literal["auto", "logistics", "plan_bom"] | None = Field(
        default="auto",
        description="可选业务域提示；仅 logistics/plan_bom 已接入",
    )

    @field_validator("question")
    @classmethod
    def _question_must_not_be_blank(cls, value: str) -> str:
        """校验问题不能为空。"""
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be blank")
        return normalized


# 后端内部使用的统一流式事件 stage 常量。
# 前端只关注 event 字符串，不依赖 stage 枚举；这里保留为后端内部常量。
UNIFIED_STREAM_STAGES = (
    "received",          # 请求已接收
    "understanding",     # 领域识别/意图理解完成
    "plan_ready",        # 查询计划就绪
    "deterministic_result_ready",  # 确定性查询完成
    "answer_streaming",  # LLM 流式表达中（前端通过 delta 事件感知）
    "done",              # 全部完成
    "error",             # 异常
)


__all__ = [
    "BusinessQaStreamRequest",
    "UNIFIED_STREAM_STAGES",
]

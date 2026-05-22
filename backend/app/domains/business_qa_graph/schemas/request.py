from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BusinessQaGraphRequest(BaseModel):
    """统一业务问数 Graph 的入口请求。

    参数：
        question: 用户原始问题，仅作为编排上下文传递，不在本卡中执行查数。
        domain_hint: 可选业务域提示，例如 auto、logistics、plan_bom；其他值会在路由节点 fail-closed。
        trace_id: 调用方传入的追踪号，用于串联后续审计。
        metadata: 预留的非敏感扩展上下文。
    返回：
        可转换成 LangGraph 初始 state 的请求对象。
    业务逻辑：
        本对象不包含 SQL、表名、字段名或自由工具调用参数；后续真实查询仍必须走受控服务。
    """

    model_config = ConfigDict(extra="forbid")

    question: str
    domain_hint: str | None = None
    trace_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("question")
    @classmethod
    def _question_must_not_be_blank(cls, value: str) -> str:
        """校验问题不能为空。

        参数：
            value: 原始问题文本。
        返回：
            去除首尾空白后的问题文本。
        业务逻辑：
            空问题无法进入任何受控领域服务，因此在 Graph 入口 fail-fast。
        """

        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be blank")
        return normalized

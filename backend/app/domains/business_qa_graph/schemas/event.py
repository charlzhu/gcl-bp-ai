from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BusinessQaGraphEvent(BaseModel):
    """统一业务问数 Graph 的节点事件。

    参数：
        node: 产生事件的节点名称。
        event_type: 事件类型，使用稳定英文枚举便于审计检索。
        message: 面向内部日志的中文说明，不作为用户可见回答。
        payload: 节点写入的最小上下文快照。
    返回：
        可序列化、可写入 state.trace 的事件对象。
    业务逻辑：
        本事件只记录外层编排进度，不承载 SQL、表名、字段名或原始调试 payload。
    """

    model_config = ConfigDict(extra="forbid")

    node: str
    event_type: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)

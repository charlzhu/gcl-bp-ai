from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class QueryLogItem(BaseModel):
    """查询历史单条记录。

    说明：
    1. 该结构面向前端查询历史页；
    2. 保留必要的平铺字段，避免前端每次自己解析 request_payload；
    3. 同时保留原始 JSON，便于联调时查看完整快照。
    """

    id: int
    trace_id: str | None = None
    query_type: str
    question: str = "-"
    execution_mode: str | None = None
    route_type: str | None = None
    metric_type: str | None = None
    result_count: int = 0
    status: str
    status_code: str | None = None
    status_message: str | None = None
    template_hit: bool = False
    template_id: str | None = None
    message: str | None = None
    created_at: datetime | None = None
    parsed: dict[str, Any] | None = None
    execution_binding: dict[str, Any] | None = None
    execution_summary: dict[str, Any] | None = None
    request_payload_json: Any | None = None


class QueryLogDetailResponse(QueryLogItem):
    """查询历史详情响应。

    说明：
    1. 该结构用于“查询历史详情接口”；
    2. 会把前端直依赖的 response_meta 和 query_result 快照整理出来；
    3. 这里的 query_result 是历史快照，不保证等同于实时再次执行的结果。
    """

    response_meta: dict[str, Any] | None = None
    query_result: dict[str, Any] | None = None


class QueryLogListResponse(BaseModel):
    """查询历史列表响应。"""

    total: int = Field(default=0)
    items: list[QueryLogItem] = Field(default_factory=list)
    load_warning: str | None = None

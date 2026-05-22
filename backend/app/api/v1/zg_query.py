"""
掌柜问数对齐版 API 端点。

提供 SSE 流式查询接口：
POST /api/v1/zg/query
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from backend.app.domains.business_qa_graph.builder_v2 import build_unified_graph
from backend.app.domains.business_qa_graph.services.zg_query_service import ZgQueryService

zg_router = APIRouter(prefix="/zg", tags=["掌柜问数对齐版"])


class ZgQueryRequest(BaseModel):
    """掌柜问数查询请求体（与掌柜问数 QuerySchema 对齐）。

    参数：
        question: 用户自然语言问题。
    """
    question: str = Field(..., min_length=1, max_length=2000, description="用户自然语言问题")


@zg_router.post("/query")
async def zg_query(request: ZgQueryRequest):
    """掌柜问数对齐版查询接口（SSE 流式）。

    参数：
        request: 包含 question 的查询请求。
    返回：
        SSE 流式响应，进度事件和最终结果。
    业务逻辑：
        完全对齐掌柜问数 FastAPI query_router：
        - 接收 POST /api/query
        - 返回 StreamingResponse
        - 流式输出 Graph 执行进度
    """
    service = ZgQueryService(graph=build_unified_graph())
    return StreamingResponse(
        service.query(request.question),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 禁用缓冲
        },
    )

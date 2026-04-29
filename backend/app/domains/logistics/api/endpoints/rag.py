from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from backend.app.api.deps import get_logistics_rag_service
from backend.app.domains.logistics.schemas.rag import (
    LogisticsRagQueryRequest,
    LogisticsRagRebuildResponse,
)
from backend.app.domains.logistics.services.rag_service import LogisticsRagService
from backend.app.schemas.common import ApiResponse

router = APIRouter()


@router.post("/rebuild-index", response_model=ApiResponse)
def rebuild_logistics_rag_index(
    request: Request,
    service: LogisticsRagService = Depends(get_logistics_rag_service),
) -> ApiResponse:
    """重建物流 RAG 本地索引。"""
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    index_meta = service.rebuild_index()
    result = LogisticsRagRebuildResponse(message="物流 RAG 索引已重建", index_meta=index_meta)
    return ApiResponse.success(result, trace_id=trace_id)


@router.post("/query", response_model=ApiResponse)
def query_logistics_rag(
    payload: LogisticsRagQueryRequest,
    request: Request,
    service: LogisticsRagService = Depends(get_logistics_rag_service),
) -> ApiResponse:
    """执行物流文档型问答。"""
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    result = service.query(payload)
    return ApiResponse.success(result, trace_id=trace_id)

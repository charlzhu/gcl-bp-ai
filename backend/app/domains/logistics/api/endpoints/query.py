from fastapi import APIRouter, Depends, Request

from backend.app.api.deps import get_domain_query_service
from backend.app.domains.logistics.schemas.query import (
    LogisticsAggregateQuery,
    LogisticsCompareQuery,
    LogisticsDetailQuery,
)
from backend.app.domains.logistics.services.query_service import LogisticsQueryService
from backend.app.schemas.common import ApiResponse

router = APIRouter()


@router.post("/aggregate", response_model=ApiResponse)
def aggregate_query(
    payload: LogisticsAggregateQuery,
    request: Request,
    service: LogisticsQueryService = Depends(get_domain_query_service),
) -> ApiResponse:
    """统计查询入口。

    这里不做业务编排，只负责：
    1. 接收并校验请求；
    2. 透传 trace_id；
    3. 统一包装响应结构。
    """
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    result = service.aggregate(payload, trace_id=trace_id)
    return ApiResponse.success(result, trace_id=trace_id)


@router.post("/detail", response_model=ApiResponse)
def detail_query(
    payload: LogisticsDetailQuery,
    request: Request,
    service: LogisticsQueryService = Depends(get_domain_query_service),
) -> ApiResponse:
    """明细查询入口。"""
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    result = service.detail(payload, trace_id=trace_id)
    return ApiResponse.success(result, trace_id=trace_id)


@router.post("/compare", response_model=ApiResponse)
def compare_query(
    payload: LogisticsCompareQuery,
    request: Request,
    service: LogisticsQueryService = Depends(get_domain_query_service),
) -> ApiResponse:
    """跨时间窗/跨来源对比查询入口。"""
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    result = service.compare(payload, trace_id=trace_id)
    return ApiResponse.success(result, trace_id=trace_id)

from fastapi import APIRouter, Depends, Request

from backend.app.api.deps import get_domain_nl2query_service
from backend.app.domains.logistics.schemas.query import LogisticsNLQuery
from backend.app.domains.logistics.services.nl2query_service import LogisticsNL2QueryService
from backend.app.schemas.common import ApiResponse

router = APIRouter()


@router.post("/parse-and-query", response_model=ApiResponse)
def parse_and_query(
    payload: LogisticsNLQuery,
    request: Request,
    service: LogisticsNL2QueryService = Depends(get_domain_nl2query_service),
) -> ApiResponse:
    """规则版自然语言查询入口。"""
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    result = service.parse_and_query(payload, trace_id=trace_id)
    return ApiResponse.success(result, trace_id=trace_id)
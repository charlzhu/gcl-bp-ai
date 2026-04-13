from fastapi import APIRouter, Depends, Request

from backend.app.api.deps import get_domain_serving_refresh_service
from backend.app.domains.logistics.schemas.import_history import LogisticsServingRefreshRequest
from backend.app.domains.logistics.services.serving_refresh_service import LogisticsServingRefreshService
from backend.app.schemas.common import ApiResponse

router = APIRouter()


@router.post("/run", response_model=ApiResponse)
def refresh_serving(
    payload: LogisticsServingRefreshRequest,
    request: Request,
    service: LogisticsServingRefreshService = Depends(get_domain_serving_refresh_service),
) -> ApiResponse:
    """历史 ETL 功能：刷新 DWS/DM 服务层。"""
    result = service.refresh(payload)
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    return ApiResponse.success(result, trace_id=trace_id)

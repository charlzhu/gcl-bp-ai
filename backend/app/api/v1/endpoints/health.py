from fastapi import APIRouter, Depends, Request

from backend.app.api.deps import get_health_service
from backend.app.schemas.common import ApiResponse
from backend.app.services.health_service import HealthService

router = APIRouter()


@router.get("/health", response_model=ApiResponse)
def health_check(
    request: Request,
    health_service: HealthService = Depends(get_health_service),
) -> ApiResponse:
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    return ApiResponse.success(health_service.check().model_dump(), trace_id=trace_id)

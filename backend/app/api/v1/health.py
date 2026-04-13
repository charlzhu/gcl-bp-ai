from fastapi import APIRouter, Depends, Request

from backend.app.api.deps import get_health_service
from backend.app.core.response import ResponseEnvelope, success_response
from backend.app.schemas.health import HealthData
from backend.app.services.health_service import HealthService

router = APIRouter()


@router.get("/health", response_model=ResponseEnvelope[HealthData])
def health_check(
    request: Request,
    health_service: HealthService = Depends(get_health_service),
) -> ResponseEnvelope[HealthData]:
    data = health_service.check()
    return success_response(request, data)

from fastapi import APIRouter, Depends, Request

from backend.app.api.deps import get_domain_serving_refresh_service
from backend.app.core.response import ResponseEnvelope, success_response
from backend.app.domains.logistics.schemas.import_history import (
    LogisticsServingRefreshRequest,
    LogisticsServingRefreshResult,
)
from backend.app.domains.logistics.services.serving_refresh_service import LogisticsServingRefreshService

router = APIRouter(prefix="/etl")


@router.post("/refresh", response_model=ResponseEnvelope[LogisticsServingRefreshResult])
def refresh_logistics_serving(
    payload: LogisticsServingRefreshRequest,
    request: Request,
    service: LogisticsServingRefreshService = Depends(get_domain_serving_refresh_service),
) -> ResponseEnvelope[LogisticsServingRefreshResult]:
    # 历史 ETL 功能：为统一查询服务刷新 HIST/SYS 汇总层，保留一个顶层别名入口便于联调。
    data = service.refresh(payload)
    return success_response(request, data)

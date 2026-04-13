from fastapi import APIRouter, Depends, Query, Request

from backend.app.api.deps import get_health_service, get_query_log_service
from backend.app.core.response import ResponseEnvelope, success_response
from backend.app.schemas.health import SystemConfigData
from backend.app.schemas.query_log import QueryLogDetailResponse, QueryLogListResponse
from backend.app.services.health_service import HealthService
from backend.app.services.query_log_service import QueryLogService

router = APIRouter()


@router.get("/system/config", response_model=ResponseEnvelope[SystemConfigData])
def get_system_config(
    request: Request,
    health_service: HealthService = Depends(get_health_service),
) -> ResponseEnvelope[SystemConfigData]:
    data = health_service.system_config()
    return success_response(request, data)


@router.get("/sys/query/log", response_model=ResponseEnvelope[QueryLogListResponse])
def list_query_logs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    query_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
    query_log_service: QueryLogService = Depends(get_query_log_service),
) -> ResponseEnvelope[QueryLogListResponse]:
    """查询历史列表接口。

    说明：
    1. 当前优先服务前端查询历史页；
    2. 返回结构已经把 request_payload 做了可读化整理；
    3. 若日志表尚未初始化，接口仍返回 200，并在 data.load_warning 中给出提示。
    """
    data = query_log_service.list_query_logs(
        limit=limit,
        query_type=query_type,
        status=status,
        trace_id=trace_id,
    )
    return success_response(request, data)


@router.get("/sys/query/log/{log_id}", response_model=ResponseEnvelope[QueryLogDetailResponse])
def get_query_log_detail(
    log_id: int,
    request: Request,
    query_log_service: QueryLogService = Depends(get_query_log_service),
) -> ResponseEnvelope[QueryLogDetailResponse]:
    """查询历史详情接口。

    说明：
    1. 当前前端第二版会优先通过该接口查看单次查询的完整上下文；
    2. 详情返回会补齐 response_meta 和 query_result 快照；
    3. 如果记录不存在，会由 service 层返回明确的 404。
    """
    data = query_log_service.get_query_log_detail(log_id=log_id)
    return success_response(request, data)

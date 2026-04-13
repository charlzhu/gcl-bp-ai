from fastapi import APIRouter, Depends, Request

from backend.app.api.deps import get_domain_sync_service
from backend.app.domains.logistics.schemas.sync import LogisticsSystemSyncRequest
from backend.app.domains.logistics.services.sync_service import LogisticsSystemSyncService
from backend.app.schemas.common import ApiResponse

router = APIRouter()


@router.post("/run", response_model=ApiResponse)
def run_system_sync(
    payload: LogisticsSystemSyncRequest,
    request: Request,
    service: LogisticsSystemSyncService = Depends(get_domain_sync_service),
) -> ApiResponse:
    """物流系统正式数据同步入口。

    这里保持 controller 层足够薄，只负责：
    1. 接收/校验请求；
    2. 透传 trace_id；
    3. 返回统一响应。
    """
    result = service.sync_formal_data(payload)
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    return ApiResponse.success(result, trace_id=trace_id)

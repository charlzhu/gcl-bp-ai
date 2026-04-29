from fastapi import APIRouter, Depends, Request

from backend.app.api.deps import get_logistics_data_qa_service
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.schemas.common import ApiResponse

router = APIRouter()


@router.post("/query", response_model=ApiResponse)
def logistics_data_qa_query(
    payload: LogisticsDataQaQueryRequest,
    request: Request,
    service: LogisticsDataQaService = Depends(get_logistics_data_qa_service),
) -> ApiResponse:
    """物流数据问答入口。"""
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    try:
        result = service.query(payload, trace_id=trace_id)
        return ApiResponse.success(result, trace_id=trace_id)
    except Exception as exc:  # noqa: BLE001
        # 物流数据问答正式页需要把错误态也纳入查询历史，便于业务回看。
        service.write_error_log(question=payload.question, trace_id=trace_id, message=str(exc))
        raise

from fastapi import APIRouter, Depends, File, Request, UploadFile

from backend.app.api.deps import get_domain_import_service
from backend.app.domains.logistics.schemas.import_history import LogisticsHistoryImportRequest
from backend.app.domains.logistics.services.import_service import LogisticsHistoryImportService
from backend.app.schemas.common import ApiResponse

router = APIRouter()


@router.post("/excel", response_model=ApiResponse)
async def import_history_excel(
    request: Request,
    file: UploadFile = File(...),
    service: LogisticsHistoryImportService = Depends(get_domain_import_service),
) -> ApiResponse:
    result = await service.import_excel(file)
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    return ApiResponse.success(result, trace_id=trace_id)


@router.post("/run", response_model=ApiResponse)
def run_history_import(
    payload: LogisticsHistoryImportRequest,
    request: Request,
    service: LogisticsHistoryImportService = Depends(get_domain_import_service),
) -> ApiResponse:
    """执行历史 Excel ETL。

    支持直接传 `file_path`，也支持先上传文件再传 `upload_id`。
    """
    result = service.run_import(payload)
    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", ""))
    return ApiResponse.success(result, trace_id=trace_id)

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from backend.app.api.deps import get_domain_import_service, get_task_service, get_upload_service
from backend.app.core.response import ResponseEnvelope, success_response
from backend.app.domains.logistics.schemas.import_history import LogisticsHistoryImportRequest
from backend.app.domains.logistics.services.import_service import LogisticsHistoryImportService
from backend.app.schemas.logistics_task import (
    HistoryImportRequest,
    HistoryUploadResponse,
    SystemSyncRequest,
    TaskListResponse,
    TaskSnapshot,
)
from backend.app.services.task_service import TaskService
from backend.app.services.upload_service import UploadService

router = APIRouter(prefix="/logistics/data")


@router.post("/hist/upload", response_model=ResponseEnvelope[HistoryUploadResponse])
async def upload_history_file(
    request: Request,
    file: UploadFile = File(...),
    operator: str | None = Form(default=None),
    upload_service: UploadService = Depends(get_upload_service),
) -> ResponseEnvelope[HistoryUploadResponse]:
    data = await upload_service.save_history_file(file=file, operator=operator)
    return success_response(request, data)


@router.post("/hist/import", response_model=ResponseEnvelope[TaskSnapshot])
def create_history_import_task(
    payload: HistoryImportRequest,
    request: Request,
    history_import_service: LogisticsHistoryImportService = Depends(get_domain_import_service),
    task_service: TaskService = Depends(get_task_service),
) -> ResponseEnvelope[TaskSnapshot]:
    result = history_import_service.run_import(
        LogisticsHistoryImportRequest(
            upload_id=payload.upload_id,
            source_year=payload.source_year,
            source_factory=payload.source_factory,
            sheet_names=payload.sheet_names,
            import_batch_no=payload.import_batch_no,
            refresh_serving=payload.refresh_serving,
            truncate_current_batch_before_import=payload.truncate_current_batch_before_import,
        )
    )
    data = task_service.record_history_import_result(
        payload,
        task_id=result.task_id,
        result=result.model_dump(),
    )
    return success_response(request, data)


@router.get("/hist/import/tasks", response_model=ResponseEnvelope[TaskListResponse])
def list_history_import_tasks(
    request: Request,
    task_service: TaskService = Depends(get_task_service),
) -> ResponseEnvelope[TaskListResponse]:
    data = task_service.list_tasks(task_type="history_import")
    return success_response(request, data)


@router.get("/hist/import/task/{task_id}", response_model=ResponseEnvelope[TaskSnapshot])
def get_history_import_task(
    task_id: str,
    request: Request,
    task_service: TaskService = Depends(get_task_service),
) -> ResponseEnvelope[TaskSnapshot]:
    data = task_service.get_task(task_id=task_id, expected_task_type="history_import")
    return success_response(request, data)


@router.post("/sys/sync", response_model=ResponseEnvelope[TaskSnapshot])
def create_system_sync_task(
    payload: SystemSyncRequest,
    request: Request,
    task_service: TaskService = Depends(get_task_service),
) -> ResponseEnvelope[TaskSnapshot]:
    data = task_service.create_system_sync_task(payload)
    return success_response(request, data)


@router.get("/sys/sync/tasks", response_model=ResponseEnvelope[TaskListResponse])
def list_system_sync_tasks(
    request: Request,
    task_service: TaskService = Depends(get_task_service),
) -> ResponseEnvelope[TaskListResponse]:
    data = task_service.list_tasks(task_type="system_sync")
    return success_response(request, data)


@router.get("/sys/sync/task/{task_id}", response_model=ResponseEnvelope[TaskSnapshot])
def get_system_sync_task(
    task_id: str,
    request: Request,
    task_service: TaskService = Depends(get_task_service),
) -> ResponseEnvelope[TaskSnapshot]:
    data = task_service.get_task(task_id=task_id, expected_task_type="system_sync")
    return success_response(request, data)

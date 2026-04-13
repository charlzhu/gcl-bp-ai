from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.app.schemas.common import MonthRange

TaskStatus = Literal["pending", "running", "completed", "failed"]
TaskType = Literal["history_upload", "history_import", "system_sync"]


class HistoryImportRequest(BaseModel):
    upload_id: str = Field(..., min_length=8, max_length=64)
    source_year: int = Field(..., ge=2023, le=2025)
    source_factory: str | None = Field(default=None, max_length=50)
    sheet_names: list[str] | None = None
    import_batch_no: str | None = Field(default=None, max_length=64)
    refresh_serving: bool = True
    truncate_current_batch_before_import: bool = False
    operator: str | None = Field(default=None, max_length=50)


class SystemSyncRequest(BaseModel):
    source_name: str = Field(default="source_logistics", max_length=50)
    period: MonthRange
    force: bool = False
    operator: str | None = Field(default=None, max_length=50)


class TaskSnapshot(BaseModel):
    task_id: str
    task_type: TaskType
    status: TaskStatus
    payload: dict[str, Any]
    result: dict[str, Any]
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    total: int
    items: list[TaskSnapshot]


class HistoryUploadResponse(BaseModel):
    upload_id: str
    file_name: str
    file_path: str
    file_size: int
    task: TaskSnapshot

import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile

from backend.app.core.config import Settings
from backend.app.core.exceptions import AppException
from backend.app.domains.logistics.constants import SUPPORTED_UPLOAD_SUFFIXES
from backend.app.repositories.task_repo import InMemoryTaskRepository
from backend.app.schemas.logistics_task import HistoryUploadResponse
from backend.app.services.task_service import TaskService


class UploadService:
    def __init__(self, *, task_repository: InMemoryTaskRepository, settings: Settings) -> None:
        self.task_repository = task_repository
        self.settings = settings

    async def save_history_file(
        self,
        *,
        file: UploadFile,
        operator: str | None = None,
    ) -> HistoryUploadResponse:
        if not file.filename:
            raise AppException("上传文件名不能为空", code=4002, status_code=400)

        suffix = Path(file.filename).suffix.lower()
        if suffix not in SUPPORTED_UPLOAD_SUFFIXES:
            raise AppException(
                "仅支持 xls、xlsx、csv 文件",
                code=4003,
                status_code=400,
                details={"suffix": suffix},
            )

        safe_name = self._sanitize_file_name(file.filename)
        upload_id = self.task_repository.create_task(
            task_type="history_upload",
            status="pending",
            payload={},
        ).task_id
        target_dir = self.settings.file_storage_root / "history_uploads"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{upload_id}_{safe_name}"

        total_size = 0
        try:
            with target_path.open("wb") as target:
                while chunk := await file.read(1024 * 1024):
                    total_size += len(chunk)
                    if total_size > self.settings.max_upload_size_mb * 1024 * 1024:
                        raise AppException(
                            f"上传文件不能超过 {self.settings.max_upload_size_mb} MB",
                            code=4004,
                            status_code=400,
                    )
                    target.write(chunk)
        except AppException:
            if target_path.exists():
                target_path.unlink()
            self.task_repository.update_task(
                upload_id,
                status="failed",
                error_message="文件大小超限或格式不合法",
            )
            raise
        except OSError as exc:
            if target_path.exists():
                target_path.unlink()
            self.task_repository.update_task(
                upload_id,
                status="failed",
                error_message="文件写入失败",
            )
            raise AppException(
                "文件写入失败",
                code=5003,
                status_code=500,
                details={"reason": str(exc)},
            ) from exc

        if total_size == 0:
            if target_path.exists():
                target_path.unlink()
            self.task_repository.update_task(
                upload_id,
                status="failed",
                error_message="空文件不允许导入",
            )
            raise AppException("空文件不允许导入", code=4005, status_code=400)

        task = self.task_repository.update_task(
            upload_id,
            status="completed",
            result={"file_size": total_size},
        )
        final_task = self.task_repository.get_task(upload_id)
        if final_task is None:
            raise AppException("上传任务创建失败", code=5002, status_code=500)
        final_task.payload = {
            "operator": operator,
            "original_file_name": file.filename,
            "stored_file_path": str(target_path),
            "content_type": file.content_type,
        }
        final_task.updated_at = datetime.now(timezone.utc)

        task_snapshot = TaskService._to_snapshot(final_task)
        return HistoryUploadResponse(
            upload_id=upload_id,
            file_name=file.filename,
            file_path=str(target_path),
            file_size=total_size,
            task=task_snapshot,
        )

    @staticmethod
    def _sanitize_file_name(file_name: str) -> str:
        return re.sub(r"[^A-Za-z0-9._-]+", "_", file_name)

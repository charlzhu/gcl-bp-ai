from backend.app.core.exceptions import AppException
from backend.app.repositories.task_repo import InMemoryTaskRepository, TaskRecord
from backend.app.schemas.logistics_task import (
    HistoryImportRequest,
    SystemSyncRequest,
    TaskListResponse,
    TaskSnapshot,
)


class TaskService:
    def __init__(self, task_repository: InMemoryTaskRepository) -> None:
        self.task_repository = task_repository

    def create_history_import_task(self, request: HistoryImportRequest) -> TaskSnapshot:
        upload_task = self.task_repository.get_task(request.upload_id)
        if upload_task is None or upload_task.task_type != "history_upload":
            raise AppException("上传文件不存在，请先完成文件上传", code=4041, status_code=404)

        task = self.task_repository.create_task(
            task_type="history_import",
            status="running",
            payload={
                "upload_id": request.upload_id,
                "operator": request.operator,
                "source_file": upload_task.payload.get("original_file_name"),
            },
        )
        completed_task = self.task_repository.update_task(
            task.task_id,
            status="completed",
            result={
                "imported_rows": 0,
                "source_file": upload_task.payload.get("original_file_name"),
                "stored_file_path": upload_task.payload.get("stored_file_path"),
                "note": "一期初始化版本已完成文件接收与任务编排，真实 ETL 可在 services/etl 中继续接入。",
            },
        )
        return self._to_snapshot(completed_task or task)

    def create_system_sync_task(self, request: SystemSyncRequest) -> TaskSnapshot:
        task = self.task_repository.create_task(
            task_type="system_sync",
            status="running",
            payload=request.model_dump(),
        )
        completed_task = self.task_repository.update_task(
            task.task_id,
            status="completed",
            result={
                "synced_tables": [
                    "ods_ship_task",
                    "ods_ship_product",
                    "ods_assign_task",
                    "ods_assign_detail",
                ],
                "period": request.period.model_dump(),
                "force": request.force,
                "note": "当前版本提供同步任务入口与状态流转，真实 MySQL 抽取逻辑可接入 services/etl/mysql_sync。",
            },
        )
        return self._to_snapshot(completed_task or task)

    def record_history_import_result(
        self,
        request: HistoryImportRequest,
        *,
        task_id: str,
        result: dict,
        status: str = "completed",
        error_message: str | None = None,
    ) -> TaskSnapshot:
        """把真实 ETL 结果同步到当前项目的轻量任务仓库。

        这样旧的 `/logistics/data/hist/import/tasks` 查询接口还能继续返回结果，
        不需要立刻把前端全部切到 `sys_task_log`。
        """
        task = self.task_repository.create_task(
            task_type="history_import",
            status=status,
            payload=request.model_dump(),
            result=result,
            task_id=task_id,
        )
        if error_message:
            task = self.task_repository.update_task(
                task.task_id,
                status="failed",
                error_message=error_message,
                result=result,
            ) or task
        return self._to_snapshot(task)

    def list_tasks(self, *, task_type: str) -> TaskListResponse:
        tasks = self.task_repository.list_tasks(task_type=task_type)
        return TaskListResponse(total=len(tasks), items=[self._to_snapshot(task) for task in tasks])

    def get_task(self, *, task_id: str, expected_task_type: str) -> TaskSnapshot:
        task = self.task_repository.get_task(task_id)
        if task is None or task.task_type != expected_task_type:
            raise AppException("任务不存在", code=4042, status_code=404)
        return self._to_snapshot(task)

    @staticmethod
    def _to_snapshot(task: TaskRecord) -> TaskSnapshot:
        return TaskSnapshot(
            task_id=task.task_id,
            task_type=task.task_type,
            status=task.status,
            payload=task.payload,
            result=task.result,
            error_message=task.error_message,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

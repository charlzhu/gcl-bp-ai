from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any
from uuid import uuid4


@dataclass
class TaskRecord:
    task_id: str
    task_type: str
    status: str
    payload: dict[str, Any]
    result: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = RLock()

    def create_task(
        self,
        *,
        task_type: str,
        status: str,
        payload: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> TaskRecord:
        with self._lock:
            actual_task_id = task_id or uuid4().hex
            task = TaskRecord(
                task_id=actual_task_id,
                task_type=task_type,
                status=status,
                payload=payload or {},
                result=result or {},
            )
            self._tasks[actual_task_id] = task
            return task

    def update_task(
        self,
        task_id: str,
        *,
        status: str | None = None,
        result: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> TaskRecord | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            if status is not None:
                task.status = status
            if result is not None:
                task.result = result
            if error_message is not None:
                task.error_message = error_message
            task.updated_at = datetime.now(timezone.utc)
            return task

    def get_task(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self, *, task_type: str | None = None) -> list[TaskRecord]:
        with self._lock:
            tasks = list(self._tasks.values())
        if task_type:
            tasks = [task for task in tasks if task.task_type == task_type]
        return sorted(tasks, key=lambda item: item.created_at, reverse=True)

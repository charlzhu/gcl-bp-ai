#!/usr/bin/env python3
"""一人公司任务状态机。"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TASKS_ROOT = PROJECT_ROOT / "ai" / "tasks"
TZ = ZoneInfo("America/Los_Angeles")

VALID_STATES: dict[str, str] = {
    "DRAFT": "draft",
    "PLANNING": "planning",
    "WAIT_CONFIRM": "wait_confirm",
    "RUNNING": "running",
    "TESTING": "testing",
    "REVIEWING": "reviewing",
    "WAIT_ACCEPT": "wait_accept",
    "DONE": "done",
    "FAILED": "failed",
    "PAUSED": "paused",
    "ROLLED_BACK": "rolled_back",
}


def now_iso() -> str:
    """返回当前时间。"""
    return datetime.now(TZ).isoformat(timespec="seconds")


def ensure_task_dirs() -> None:
    """确保所有状态目录存在。"""
    for dirname in VALID_STATES.values():
        (TASKS_ROOT / dirname).mkdir(parents=True, exist_ok=True)


def task_dir_for(state: str, task_id: str) -> Path:
    """根据状态和任务 ID 返回目录。"""
    return TASKS_ROOT / VALID_STATES[state] / task_id


def find_task_dir(task_id: str) -> Path:
    """在所有状态目录下查找任务目录。"""
    for dirname in VALID_STATES.values():
        candidate = TASKS_ROOT / dirname / task_id
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Task not found: {task_id}")


def find_latest_task_dir() -> Path:
    """查找最近修改的任务目录。"""
    ensure_task_dirs()
    candidates = [p for p in TASKS_ROOT.glob("*/TASK-*") if p.is_dir()]
    if not candidates:
        raise FileNotFoundError("No TASK-* directories found under ai/tasks")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def write_state(task_dir: Path, task_id: str, state: str, message: str = "") -> None:
    """写入 state.json。"""
    data = {
        "task_id": task_id,
        "state": state,
        "state_dir": VALID_STATES[state],
        "updated_at": now_iso(),
        "message": message,
    }
    with (task_dir / "state.json").open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def move_task(task_id: str, new_state: str, message: str = "") -> Path:
    """把任务目录移动到新状态目录，并更新 state.json。"""
    ensure_task_dirs()
    old_dir = find_task_dir(task_id)
    new_dir = task_dir_for(new_state, task_id)
    if old_dir.resolve() != new_dir.resolve():
        if new_dir.exists():
            raise FileExistsError(f"Target task dir already exists: {new_dir}")
        shutil.move(str(old_dir), str(new_dir))
    write_state(new_dir, task_id, new_state, message)
    return new_dir

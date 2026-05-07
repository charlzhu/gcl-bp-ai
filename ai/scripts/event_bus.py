#!/usr/bin/env python3
"""一人公司任务事件日志。

本模块只依赖 Python 标准库，用于把 Hermes 技术经理、Codex Runner、测试、质量检查等阶段的
事件统一写入 TASK 目录下的 event.jsonl，方便窗口关闭后恢复现场。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Los_Angeles")


def now_iso() -> str:
    """返回带时区的当前时间字符串。"""
    return datetime.now(TZ).isoformat(timespec="seconds")


def append_event(
    task_dir: Path,
    task_id: str,
    role: str,
    stage: str,
    message: str,
    level: str = "info",
) -> None:
    """追加一条任务事件。

    参数：
        task_dir: 当前 TASK 目录。
        task_id: 任务编号。
        role: 事件来源角色，例如 hermes.technical_manager / codex / tester。
        stage: 当前阶段，例如 planning / running / testing / reviewing。
        message: 事件内容。
        level: 事件级别，默认 info。
    """
    task_dir.mkdir(parents=True, exist_ok=True)
    event_file = task_dir / "event.jsonl"
    event = {
        "ts": now_iso(),
        "task_id": task_id,
        "role": role,
        "stage": stage,
        "level": level,
        "message": message,
    }
    with event_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def read_events(task_dir: Path, limit: int | None = None) -> list[dict]:
    """读取任务事件。

    参数：
        task_dir: 当前 TASK 目录。
        limit: 只返回最后 N 条；为空时返回全部。
    """
    event_file = task_dir / "event.jsonl"
    if not event_file.exists():
        return []
    rows: list[dict] = []
    with event_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows.append({"ts": "", "level": "warn", "role": "event_bus", "stage": "parse", "message": line})
    if limit is not None:
        return rows[-limit:]
    return rows


def print_event(role: str, stage: str, message: str, level: str = "info") -> None:
    """按统一格式实时打印事件，供 Hermes TUI 直接显示。"""
    print(f"[{level.upper()}][{role}][{stage}] {message}", flush=True)

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable


class LogisticsConfigWatcher:
    """配置监测器（V5）。

    作用：
    1. 扫描模板和字典相关 YAML 文件；
    2. 基于文件路径 + 修改时间生成版本号；
    3. 为热更新服务提供“配置是否发生变化”的判断依据。
    """

    @staticmethod
    def build_snapshot(files: Iterable[Path]) -> dict[str, int]:
        snapshot: dict[str, int] = {}
        for file_path in files:
            if not file_path.exists():
                continue
            snapshot[str(file_path.resolve())] = file_path.stat().st_mtime_ns
        return snapshot

    @staticmethod
    def build_version(snapshot: dict[str, int]) -> str:
        """把当前快照转成稳定版本号。"""
        raw = '|'.join(f'{path}:{mtime}' for path, mtime in sorted(snapshot.items()))
        return hashlib.md5(raw.encode('utf-8')).hexdigest()[:12] if raw else 'empty-config'

    @staticmethod
    def has_changed(old_snapshot: dict[str, int], new_snapshot: dict[str, int]) -> bool:
        return old_snapshot != new_snapshot

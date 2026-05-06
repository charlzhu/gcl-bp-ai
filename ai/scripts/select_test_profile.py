#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Hermes 自动测试档位选择脚本。

本脚本只根据当前 Git 改动路径选择 smoke/full，不读取业务数据、不修改仓库。
它的定位是给 `run_tests.sh auto` 提供稳定、可解释的测试模式。
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


IGNORED_PREFIXES = (
    "ai/reports/",
    "ai/tasks/running/",
    "ai/tasks/done/",
    ".pytest_cache/",
    "__pycache__/",
)


def repo_root() -> Path:
    """返回 Git 根目录。

    参数：无。
    返回值：Git 根目录；如果当前目录不在 Git 仓库内，则返回当前工作目录。
    """
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return Path(result.stdout.strip()).resolve()
    return Path.cwd().resolve()


def changed_paths(root: Path) -> list[str]:
    """读取当前非报告类改动路径。

    参数：
        root：Git 根目录。
    返回值：
        已过滤 ai/reports、轮次任务产物和缓存目录后的改动路径列表。
    """
    result = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []

    paths: list[str] = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if path.startswith(IGNORED_PREFIXES) or "/__pycache__/" in path:
            continue
        paths.append(path)
    return paths


def select_profile(paths: list[str]) -> tuple[str, str]:
    """根据改动路径选择测试档位。

    参数：
        paths：当前 Git 改动路径列表。
    返回值：
        二元组 `(profile, reason)`，profile 只会是 `smoke` 或 `full`。

    业务逻辑：
        自动化流水线默认保守选 `smoke`，确保语法、构建和基础 smoke 能跑。
        若显式设置 `HERMES_AUTO_FULL=1`，或改动测试、依赖声明、业务主入口，
        则升级为 `full`，避免大改动只跑轻量检查。
    """
    if os.getenv("HERMES_AUTO_FULL") == "1":
        return "full", "HERMES_AUTO_FULL=1，强制使用 full。"

    full_prefixes = (
        "backend/tests/",
        "frontend/tests/",
        "tests/",
    )
    full_files = {
        "backend/requirements.txt",
        "frontend/package.json",
        "frontend/package-lock.json",
        "package.json",
        "package-lock.json",
        "pyproject.toml",
        "pytest.ini",
    }
    broad_source_prefixes = (
        "backend/app/",
        "frontend/src/",
        "scripts/trial_",
        "scripts/logistics_",
    )

    for path in paths:
        if path in full_files or path.startswith(full_prefixes):
            return "full", f"检测到测试或依赖相关改动：{path}"
        if path.startswith(broad_source_prefixes):
            return "full", f"检测到业务主链路相关改动：{path}"

    return "smoke", "未检测到需要 full 的改动，使用 smoke。"


def main() -> int:
    """命令行入口。

    参数：无显式参数，读取当前 Git 状态。
    返回值：进程退出码，固定返回 0。
    """
    root = repo_root()
    profile, reason = select_profile(changed_paths(root))
    print(profile)
    print(reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

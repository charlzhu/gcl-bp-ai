#!/usr/bin/env python3
"""技术经理质量检查。

检查 Codex 改动范围、敏感文件、diff 行数、必要产物是否齐全，并给出 PASS/WARN/FAIL/BLOCKED。
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

SENSITIVE_PATTERNS = [
    ".env",
    "settings.py",
    "config.py",
    "docker-compose",
    "migration",
    "alembic",
    "auth",
    "permission",
    "security",
    "secret",
    "password",
]

FORBIDDEN_DIRS = [".git", ".venv", "node_modules", "__pycache__"]
MAX_DIFF_LINES = 500


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    """执行命令并返回退出码和合并输出。"""
    p = subprocess.run(cmd, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout


def get_changed_files(project_root: Path) -> list[str]:
    """读取 git diff 中的修改文件。"""
    _, output = run(["git", "diff", "--name-only"], project_root)
    return [line.strip() for line in output.splitlines() if line.strip()]


def get_diff_line_count(project_root: Path) -> int:
    """统计 diff 增删行数。"""
    _, output = run(["git", "diff", "--numstat"], project_root)
    total = 0
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            for item in parts[:2]:
                if item.isdigit():
                    total += int(item)
    return total


def review(task_dir: Path, project_root: Path) -> tuple[str, dict]:
    """执行质量检查。"""
    changed_files = get_changed_files(project_root)
    diff_lines = get_diff_line_count(project_root)
    issues: list[str] = []
    warnings: list[str] = []

    if not changed_files:
        warnings.append("没有检测到 git diff。若本任务只生成报告或检查环境，可以接受；若是开发任务，需要人工确认。")

    for file in changed_files:
        normalized = file.replace("\\", "/")
        if any(normalized.startswith(d + "/") or normalized == d for d in FORBIDDEN_DIRS):
            issues.append(f"修改了禁止目录或文件：{file}")
        lowered = normalized.lower()
        if any(pattern in lowered for pattern in SENSITIVE_PATTERNS):
            warnings.append(f"涉及敏感文件或敏感模块：{file}")
        if normalized.startswith("ai/inbox/attachments/"):
            issues.append(f"禁止修改 inbox 原始附件：{file}")

    if diff_lines > MAX_DIFF_LINES:
        warnings.append(f"diff 行数较大：{diff_lines} 行，超过阈值 {MAX_DIFF_LINES} 行。")

    for name in ["codex_final.md", "test.log", "diff.patch"]:
        if not (task_dir / name).exists():
            warnings.append(f"缺少必要产物：{name}")

    stderr_file = task_dir / "codex_stderr.log"
    if stderr_file.exists() and stderr_file.read_text(encoding="utf-8", errors="ignore").strip():
        warnings.append("Codex stderr 非空，需要人工检查。")

    status = "PASS"
    if warnings:
        status = "WARN"
    if issues:
        status = "FAIL"

    result = {
        "status": status,
        "changed_files": changed_files,
        "diff_lines": diff_lines,
        "issues": issues,
        "warnings": warnings,
    }
    return status, result


def write_outputs(task_dir: Path, result: dict) -> None:
    """写入质量检查 JSON 和 Markdown。"""
    (task_dir / "quality_review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# 技术经理质量检查结果",
        "",
        f"## 状态：{result['status']}",
        "",
        f"## Diff 行数：{result['diff_lines']}",
        "",
        "## 修改文件",
        "",
    ]
    lines += [f"- {f}" for f in result["changed_files"]] or ["- 无"]
    lines += ["", "## 问题", ""]
    lines += [f"- {i}" for i in result["issues"]] or ["- 无"]
    lines += ["", "## 警告", ""]
    lines += [f"- {w}" for w in result["warnings"]] or ["- 无"]
    (task_dir / "quality_review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()
    status, result = review(Path(args.task_dir), Path(args.project_root))
    write_outputs(Path(args.task_dir), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if status == "FAIL":
        return 2
    if status == "WARN":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

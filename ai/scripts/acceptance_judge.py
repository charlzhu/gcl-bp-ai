#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Hermes 单轮验收判定脚本。

本脚本把测试结果、Reviewer 结论和安全门禁统一归一成四类 verdict：
PASS、FAIL_REPAIRABLE、FAIL_UNREPAIRABLE、BLOCKED。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


VERDICT_PASS = "PASS"
VERDICT_REPAIRABLE = "FAIL_REPAIRABLE"
VERDICT_UNREPAIRABLE = "FAIL_UNREPAIRABLE"
VERDICT_BLOCKED = "BLOCKED"

AUTOMATION_OUTPUT_PREFIXES = (
    "ai/reports/",
    "ai/tasks/running/",
    "ai/tasks/done/",
)

SENSITIVE_RE = re.compile(
    r"(^|/)(\.env$|\.env\.local$|auth\.json$|.*\.(pem|key|p12)$)|"
    r"(secret|token|password|credential|证书|密钥)",
    re.IGNORECASE,
)

IGNORED_SOURCE_RE = re.compile(
    r"^(backend|frontend/src|scripts|ai/scripts|ai/roles|ai/company|docs)/.*"
    r"\.(py|sh|ts|tsx|vue|md|json|yaml|yml)$"
)


def read_text(path: Path, default: str = "") -> str:
    """读取文本文件。

    参数：
        path：文件路径。
        default：文件不存在或读取失败时返回的默认文本。
    返回值：
        文件内容或默认文本。
    """
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return default
    return default


def git_status_lines(root: Path, ignored: bool = False) -> list[str]:
    """读取 Git status 行。

    参数：
        root：Git 根目录。
        ignored：是否包含被 .gitignore 忽略的文件。
    返回值：
        `git status --short` 输出行列表。
    """
    cmd = ["git", "status", "--short", "--untracked-files=all"]
    if ignored:
        cmd.insert(2, "--ignored")
    result = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return result.stdout.splitlines()


def normalize_status_path(line: str) -> str:
    """从 Git status 行中提取路径。

    参数：
        line：一行 `git status --short` 输出。
    返回值：
        规范化后的相对路径。
    """
    if len(line) < 4:
        return ""
    path = line[3:].strip()
    if " -> " in path:
        path = path.rsplit(" -> ", 1)[-1].strip()
    return path


def changed_files(root: Path) -> list[str]:
    """返回非报告类改动文件列表。

    参数：
        root：Git 根目录。
    返回值：
        去除 ai/reports 和轮次任务产物后的改动路径列表。
    """
    files: list[str] = []
    for line in git_status_lines(root):
        path = normalize_status_path(line)
        if not path:
            continue
        if path.startswith(AUTOMATION_OUTPUT_PREFIXES):
            continue
        if "__pycache__/" in path or path.endswith(".pyc"):
            continue
        files.append(path)
    return files


def sensitive_changed(files: list[str]) -> list[str]:
    """筛选敏感文件改动。

    参数：
        files：改动文件列表。
    返回值：
        命中敏感路径规则的文件列表。
    """
    return [path for path in files if SENSITIVE_RE.search(path)]


def ignored_source_risks(root: Path) -> list[str]:
    """检查被 .gitignore 忽略的源码风险。

    参数：
        root：Git 根目录。
    返回值：
        看起来像源码/配置却被忽略的路径列表，仅用于报告风险，不直接判失败。
    """
    risks: list[str] = []
    excluded_parts = (
        "__pycache__/",
        ".pytest_cache/",
        ".venv/",
        "venv/",
        "node_modules/",
        "dist/",
        "coverage/",
        "ai/reports/",
        "tmp/",
    )
    for line in git_status_lines(root, ignored=True):
        if not line.startswith("!! "):
            continue
        path = normalize_status_path(line)
        if not path or any(part in path for part in excluded_parts):
            continue
        if IGNORED_SOURCE_RE.match(path):
            risks.append(path)
    return risks


def reviewer_blocks(reviewer_text: str, reviewer_exit: int, skip_review: bool) -> tuple[bool, str]:
    """判断 Reviewer 是否阻塞。

    参数：
        reviewer_text：Reviewer 报告文本。
        reviewer_exit：Reviewer 进程退出码。
        skip_review：本轮是否跳过 Reviewer。
    返回值：
        `(is_blocking, reason)`，用于验收 verdict 归因。
    """
    if skip_review:
        return False, "本轮按参数跳过 Reviewer。"
    if reviewer_exit == 4:
        return True, "Reviewer 调用 Codex CLI 失败，疑似环境阻塞。"
    if reviewer_exit != 0:
        return True, f"Reviewer 进程退出码非 0：{reviewer_exit}。"
    if "不通过" in reviewer_text:
        return True, "Reviewer 明确给出不通过。"
    allow_part = reviewer_text.split("是否允许进入人工验收", 1)[-1]
    if "否" in allow_part[:80]:
        return True, "Reviewer 不允许进入人工验收。"
    return False, "Reviewer 未阻塞。"


def judge(args: argparse.Namespace) -> dict[str, Any]:
    """执行单轮验收判定。

    参数：
        args：命令行参数命名空间。
    返回值：
        可 JSON 序列化的判定结果。
    """
    root = Path(args.root).resolve()
    round_dir = Path(args.round_dir).resolve()
    reviewer_text = read_text(round_dir / "codex-reviewer-result.md")
    files = changed_files(root)
    sensitive_files = sensitive_changed(files)
    ignored_risks = ignored_source_risks(root)

    reasons: list[str] = []
    stop_reason = ""
    verdict = VERDICT_PASS

    if args.safety_exit != 0:
        verdict = VERDICT_BLOCKED
        stop_reason = f"安全检查失败，退出码 {args.safety_exit}。"
        reasons.append(stop_reason)
    elif args.fullstack_exit == 4 or args.reviewer_exit == 4:
        verdict = VERDICT_BLOCKED
        stop_reason = "Codex CLI 不可用或 Worker 环境阻塞。"
        reasons.append(stop_reason)
    elif sensitive_files:
        verdict = VERDICT_UNREPAIRABLE
        stop_reason = "检测到敏感文件相关改动。"
        reasons.append(stop_reason)
    elif len(files) > args.max_changed_files:
        verdict = VERDICT_UNREPAIRABLE
        stop_reason = f"改动文件数 {len(files)} 超过上限 {args.max_changed_files}。"
        reasons.append(stop_reason)
    elif args.no_diff_streak >= 2:
        verdict = VERDICT_UNREPAIRABLE
        stop_reason = "连续两轮没有实质 diff。"
        reasons.append(stop_reason)
    else:
        reviewer_blocked, reviewer_reason = reviewer_blocks(
            reviewer_text,
            args.reviewer_exit,
            args.skip_review,
        )
        if args.fullstack_exit != 0:
            verdict = VERDICT_REPAIRABLE
            reasons.append(f"Codex 开发阶段退出码非 0：{args.fullstack_exit}。")
        if args.test_exit != 0:
            verdict = VERDICT_REPAIRABLE
            reasons.append(f"测试退出码非 0：{args.test_exit}。")
        if reviewer_blocked:
            verdict = VERDICT_REPAIRABLE
            reasons.append(reviewer_reason)
        if verdict == VERDICT_PASS:
            reasons.append("测试通过且 Reviewer 未阻塞。")

    if ignored_risks:
        reasons.append(".gitignore 可能忽略了新增源码文件，需人工确认。")

    return {
        "verdict": verdict,
        "passed": verdict == VERDICT_PASS,
        "repairable": verdict == VERDICT_REPAIRABLE,
        "stop_reason": stop_reason,
        "reasons": reasons,
        "changed_file_count": len(files),
        "changed_files": files,
        "sensitive_files": sensitive_files,
        "ignored_source_risks": ignored_risks,
        "round_had_substantive_diff": args.round_had_substantive_diff,
        "no_diff_streak": args.no_diff_streak,
    }


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    参数：无。
    返回值：argparse 参数解析器。
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--round-dir", required=True)
    parser.add_argument("--safety-exit", type=int, default=0)
    parser.add_argument("--fullstack-exit", type=int, default=0)
    parser.add_argument("--test-exit", type=int, default=0)
    parser.add_argument("--reviewer-exit", type=int, default=0)
    parser.add_argument("--skip-review", action="store_true")
    parser.add_argument("--round-had-substantive-diff", action="store_true")
    parser.add_argument("--no-diff-streak", type=int, default=0)
    parser.add_argument("--max-changed-files", type=int, default=30)
    parser.add_argument("--output", required=True)
    return parser


def main() -> int:
    """命令行入口。

    参数：通过 argparse 读取。
    返回值：0 表示判定文件写入成功。
    """
    args = build_parser().parse_args()
    result = judge(args)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

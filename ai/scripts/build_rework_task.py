#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Hermes 返工任务卡生成脚本。

当某一轮测试失败或 Reviewer 不通过时，本脚本把上一轮证据整理成下一轮
Codex Reworker 可执行的任务卡，确保返工不是凭空重试。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


MAX_SNIPPET_CHARS = 12000


def read_text(path: Path, default: str = "") -> str:
    """读取文本文件。

    参数：
        path：文件路径。
        default：文件不存在时使用的默认文本。
    返回值：
        文件内容；不存在时返回默认文本。
    """
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8", errors="replace")


def tail_text(text: str, limit: int = MAX_SNIPPET_CHARS) -> str:
    """截取文本尾部，避免任务卡过大。

    参数：
        text：原始文本。
        limit：最多保留字符数。
    返回值：
        原文不超过 limit 时返回原文，否则返回尾部片段。
    """
    if len(text) <= limit:
        return text
    return "[前文已截断，仅保留尾部关键证据]\n" + text[-limit:]


def load_verdict(path: Path) -> dict:
    """读取验收判定 JSON。

    参数：
        path：`acceptance-verdict.json` 路径。
    返回值：
        判定字典；读取失败时返回空字典。
    """
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {}


def build_task(
    task_id: str,
    requirement: str,
    previous_round_dir: Path,
    next_round: int,
) -> str:
    """生成返工任务卡正文。

    参数：
        task_id：原始任务编号。
        requirement：用户原始需求。
        previous_round_dir：上一轮报告目录。
        next_round：下一轮轮次编号。
    返回值：
        Markdown 格式的返工任务卡。
    """
    verdict = load_verdict(previous_round_dir / "acceptance-verdict.json")
    reasons = verdict.get("reasons") or []
    reason_text = "\n".join(f"- {item}" for item in reasons) if reasons else "- 未读取到明确失败原因。"

    return f"""# {task_id} 第 {next_round} 轮返工任务

## 执行角色

你是 Codex Reworker 返工龙虾。

## 原始需求

{requirement.strip()}

## 上一轮验收结论

- Verdict: {verdict.get("verdict", "UNKNOWN")}
- 是否达标: {verdict.get("passed", False)}
- 是否可自动返工: {verdict.get("repairable", False)}
- 停止原因: {verdict.get("stop_reason") or "无"}

## 失败原因

{reason_text}

## 返工要求

1. 只修复上一轮失败原因，不做任务外优化。
2. 不修改 `.env`、token、auth.json、数据库配置、业务核心代码和前端业务页面。
3. 不自动 commit、merge、push 或部署。
4. 保持小步修改，复杂判断必须写中文注释。
5. 修复后输出清楚改了哪些文件、运行了哪些命令、还有哪些风险。

## 上一轮 test.log

```text
{tail_text(read_text(previous_round_dir / "test.log", "未找到 test.log。"))}
```

## 上一轮 Reviewer 结果

```text
{tail_text(read_text(previous_round_dir / "codex-reviewer-result.md", "未找到 Reviewer 结果。"))}
```

## 上一轮 Diff 摘要

```text
{tail_text(read_text(previous_round_dir / "diff-summary.md", "未找到 diff-summary.md。"))}
```

## 上一轮 changed-files

```text
{tail_text(read_text(previous_round_dir / "changed-files.txt", "未找到 changed-files.txt。"))}
```
"""


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    参数：无。
    返回值：argparse 参数解析器。
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--requirement-file", required=True)
    parser.add_argument("--previous-round-dir", required=True)
    parser.add_argument("--next-round", required=True, type=int)
    parser.add_argument("--output", required=True)
    return parser


def main() -> int:
    """命令行入口。

    参数：通过 argparse 读取。
    返回值：0 表示返工任务卡写入成功。
    """
    args = build_parser().parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    task = build_task(
        task_id=args.task_id,
        requirement=read_text(Path(args.requirement_file), ""),
        previous_round_dir=Path(args.previous_round_dir),
        next_round=args.next_round,
    )
    output.write_text(task, encoding="utf-8")
    print(f"Rework task written: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""技术经理交付报告生成器。"""
from __future__ import annotations

import argparse
from pathlib import Path

from event_bus import read_events


def read_text(path: Path, default: str = "") -> str:
    """安全读取文本文件。"""
    if path.exists():
        return path.read_text(encoding="utf-8", errors="ignore")
    return default


def build_report(task_id: str, task_dir: Path, conclusion: str = "WAIT_ACCEPT") -> Path:
    """生成 report.md。"""
    requirement = read_text(task_dir / "requirement.md", "未找到 requirement.md")
    manifest = read_text(task_dir / "attachments_manifest.md", "未找到 attachments_manifest.md")
    attachment_summary = read_text(task_dir / "attachments_summary.md", "未找到 attachments_summary.md")
    plan = read_text(task_dir / "plan.md", "未找到 plan.md")
    acceptance = read_text(task_dir / "acceptance.md", "未找到 acceptance.md")
    codex_final = read_text(task_dir / "codex_final.md", "未找到 codex_final.md")
    git_status = read_text(task_dir / "git_status.txt", "未找到 git_status.txt")
    diff_stat = read_text(task_dir / "diff_stat.txt", "未找到 diff_stat.txt")
    test_log = read_text(task_dir / "test.log", "未找到 test.log")
    quality_review = read_text(task_dir / "quality_review.md", "未找到 quality_review.md")

    event_lines = []
    for event in read_events(task_dir, limit=120):
        event_lines.append(
            f"- {event.get('ts')} [{event.get('level')}] {event.get('role')}/{event.get('stage')}: {event.get('message')}"
        )

    report = f"""# {task_id} 技术经理交付报告

## 1. 技术经理结论

当前结论：**{conclusion}**

本报告由本地一人公司流水线自动生成。当前未自动 commit、未自动 push、未自动部署，需要用户人工验收后再决定后续动作。

## 2. 需求原文

{requirement}

## 3. 附件清单

{manifest}

## 4. 附件摘要

{attachment_summary[:12000]}

## 5. 执行计划

{plan}

## 6. 验收标准

{acceptance}

## 7. Codex 最终反馈

{codex_final}

## 8. 测试结果摘要

```text
{test_log[-12000:]}
```

## 9. 技术经理质量检查

{quality_review}

## 10. Git 状态

```text
{git_status}
```

## 11. Diff 摘要

```text
{diff_stat}
```

## 12. 最近事件

{chr(10).join(event_lines) if event_lines else '- 无事件'}

## 13. 建议人工检查点

1. 需求是否被正确理解，是否存在跑偏。
2. 附件内容是否被正确引用，是否存在误读。
3. 修改文件是否都在预期范围内。
4. 前端页面、后端接口、业务口径是否符合现有项目边界。
5. 测试通过是否足够支撑本次变更。
6. 是否需要补充业务回归用例。

## 14. 后续动作

- 可以查看 `diff.patch` 做人工 code review。
- 可以查看 `event.jsonl` 恢复任务过程。
- 可以查看 `test.log` 判断环境和测试结果。
- 验收通过后，由用户手动决定是否 commit / push / 部署。
"""
    output = task_dir / "report.md"
    output.write_text(report, encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--conclusion", default="WAIT_ACCEPT")
    args = parser.parse_args()
    report_file = build_report(args.task_id, Path(args.task_dir), args.conclusion)
    print(f"[Report] Generated: {report_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Hermes 本地 AI 总控脚本 v2

功能：
1. 读取 ai/inbox/requirement.md 或指定任务文件。
2. 生成 Codex 全栈开发任务卡。
3. 调用 Codex CLI 执行开发。
4. 运行统一测试脚本。
5. 收集 git diff。
6. 调用 Codex Reviewer 审查。
7. 生成 final-acceptance.md。

安全边界：
- 不自动 commit。
- 不自动 merge。
- 不自动 push。
- 不自动 deploy。
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: list[str], cwd: Path, log_file: Path | None = None, check: bool = False) -> int:
    text_cmd = " ".join(cmd)
    print(f"\n$ {text_cmd}")

    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    output_lines: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="")
        output_lines.append(line)

    code = process.wait()

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as f:
            f.write(f"\n$ {text_cmd}\n")
            f.writelines(output_lines)
            f.write(f"\n[exit_code={code}]\n")

    if check and code != 0:
        raise RuntimeError(f"Command failed: {text_cmd}, exit={code}")
    return code


def read_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def append_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(content)


def get_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return Path(result.stdout.strip()).resolve()
    return Path.cwd().resolve()


def ensure_layout(root: Path) -> None:
    dirs = [
        "ai/company",
        "ai/context",
        "ai/roles",
        "ai/inbox",
        "ai/memory",
        "ai/tasks/pending",
        "ai/tasks/running",
        "ai/tasks/done",
        "ai/tasks/rejected",
        "ai/reports",
        "ai/scripts",
    ]
    for d in dirs:
        (root / d).mkdir(parents=True, exist_ok=True)


def check_required_files(root: Path) -> list[str]:
    required = [
        "ai/company/COMPANY_RULES.md",
        "ai/company/DELIVERY_STANDARD.md",
        "ai/company/RISK_CONTROL.md",
        "ai/context/PROJECT_CONTEXT.md",
        "ai/context/CURRENT_STATUS.md",
        "ai/context/BUSINESS_RULES.md",
        "ai/roles/CODEX_FULLSTACK.md",
        "ai/roles/CODEX_REVIEWER.md",
        "ai/scripts/run_codex_worker.sh",
        "ai/scripts/run_tests.sh",
        "ai/scripts/collect_diff.sh",
        "ai/scripts/safety_check.sh",
    ]
    return [p for p in required if not (root / p).exists()]


def make_task_id() -> str:
    return "TASK-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def build_fullstack_task(root: Path, task_id: str, requirement: str, report_dir: Path) -> str:
    return f"""# {task_id} 全栈开发任务

## 用户原始需求

{requirement.strip()}

## 执行角色

你是 Codex 全栈开发龙虾。

## 任务目标

请基于用户需求，在当前仓库中完成最小可行修改。

## 必读文件

请优先阅读：

- ai/company/COMPANY_RULES.md
- ai/company/DELIVERY_STANDARD.md
- ai/company/RISK_CONTROL.md
- ai/context/PROJECT_CONTEXT.md
- ai/context/CURRENT_STATUS.md
- ai/context/BUSINESS_RULES.md
- AGENTS.md
- README_WORKSPACE.md
- docs/CURRENT_STATUS.md
- docs/HANDOFF.md
- docs/NEXT_TASK.md

## 修改要求

1. 只完成当前需求，不做任务外优化。
2. 优先小步修改。
3. 不要大范围重构。
4. 不要修改密钥、token、账号、密码、证书。
5. 不要自动 commit、merge、push 或部署。
6. 修改后请尽量运行相关测试或构建命令。
7. 如果测试无法运行，请说明具体原因。

## 输出要求

请在最终回复中包含：

1. 完成摘要。
2. 修改文件列表。
3. 每个文件改了什么。
4. 执行过的命令。
5. 测试结果。
6. 风险点。
7. 是否需要人工确认。

## 报告位置

Hermes 会将你的输出保存到：

{report_dir.relative_to(root)}/codex-fullstack-result.md
"""


def build_tester_task(root: Path, task_id: str, requirement: str, report_dir: Path) -> str:
    return f"""# {task_id} 测试验收任务

## 用户原始需求

{requirement.strip()}

## 执行角色

你是 Codex 测试验收龙虾。

## 测试材料

请阅读：

- {report_dir.relative_to(root)}/codex-fullstack-result.md
- {report_dir.relative_to(root)}/test.log
- {report_dir.relative_to(root)}/git-status.txt
- {report_dir.relative_to(root)}/diffstat.txt
- {report_dir.relative_to(root)}/diff.patch

## 测试目标

判断本轮修改是否具备基本验收条件。优先不改业务代码，如确需补充测试，只新增或修改测试文件。

## 输出格式

## 测试结论

通过 / 不通过 / 无法完整测试

## 已执行命令

## 测试结果

## 发现问题

## 是否允许进入审查

是 / 否
"""


def build_review_task(root: Path, task_id: str, requirement: str, report_dir: Path, tester_enabled: bool) -> str:
    tester_line = f"- {report_dir.relative_to(root)}/codex-tester-result.md" if tester_enabled else ""
    return f"""# {task_id} 代码审查任务

## 用户原始需求

{requirement.strip()}

## 执行角色

你是 Codex Reviewer 审查龙虾。

## 审查材料

请阅读：

- {report_dir.relative_to(root)}/codex-fullstack-result.md
- {report_dir.relative_to(root)}/test.log
- {report_dir.relative_to(root)}/git-status.txt
- {report_dir.relative_to(root)}/diffstat.txt
- {report_dir.relative_to(root)}/diff.patch
{tester_line}

## 审查目标

判断全栈开发龙虾的修改是否满足用户需求，并判断是否存在风险。

## 必须检查

1. 是否完成用户需求。
2. 是否有明显无关改动。
3. 是否可能破坏已有功能。
4. 是否存在硬编码。
5. 是否修改敏感文件。
6. 是否暴露内部异常、密钥或敏感信息。
7. 测试是否执行。
8. 测试失败是否可以接受。
9. 是否允许进入人工验收。

## 输出格式

请严格输出以下结构：

## 审查结论

通过 / 有条件通过 / 不通过

## 阻塞问题

没有则写“无”。

## 非阻塞建议

没有则写“无”。

## 风险等级

低 / 中 / 高

## 是否允许进入人工验收

是 / 否

## 返工建议

如果不通过，请写清楚应返工哪些点。
"""


def reviewer_allows_acceptance(reviewer: str, test_exit: int) -> str:
    if "不通过" in reviewer:
        return "否"
    if "是否允许进入人工验收" in reviewer and "否" in reviewer.split("是否允许进入人工验收", 1)[-1][:50]:
        return "否"
    if test_exit != 0:
        return "需人工判断"
    if "通过" in reviewer or "有条件通过" in reviewer:
        return "是"
    return "需人工判断"


def build_final_acceptance(
    task_id: str,
    requirement: str,
    report_dir: Path,
    fullstack_exit: int,
    test_exit: int,
    tester_exit: int | None,
    reviewer_exit: int,
) -> str:
    fullstack = read_text(report_dir / "codex-fullstack-result.md", "未找到开发报告。")
    tester = read_text(report_dir / "codex-tester-result.md", "未启用测试验收龙虾。")
    reviewer = read_text(report_dir / "codex-reviewer-result.md", "未找到审查报告。")
    diffstat = read_text(report_dir / "diffstat.txt", "未找到 diffstat。")
    status = read_text(report_dir / "git-status.txt", "未找到 git status。")

    acceptance = reviewer_allows_acceptance(reviewer, test_exit)
    tester_cell = "未启用" if tester_exit is None else str(tester_exit)

    return f"""# {task_id} 最终验收报告

## 一、用户需求

{requirement.strip()}

## 二、自动化执行结果

| 项目 | 结果 |
|---|---|
| Codex 全栈开发退出码 | {fullstack_exit} |
| 自动测试退出码 | {test_exit} |
| Codex Tester 退出码 | {tester_cell} |
| Codex Reviewer 退出码 | {reviewer_exit} |
| 是否建议进入人工验收 | {acceptance} |

## 三、Git 状态

```text
{status}
```

## 四、Diff 摘要

```text
{diffstat}
```

## 五、开发报告摘要

```text
{fullstack[-6000:]}
```

## 六、测试龙虾报告摘要

```text
{tester[-3000:]}
```

## 七、Reviewer 审查结果

```text
{reviewer[-6000:]}
```

## 八、Hermes 结论

- 本流程不会自动 commit、merge、push 或部署。
- 如果测试退出码为 0，且 Reviewer 没有“不通过”结论，可以进入人工验收。
- 如果测试失败或 Reviewer 不通过，请先阅读 `codex-reviewer-result.md` 和 `test.log`。

## 九、建议下一步

1. 查看 `diff.patch`。
2. 本地运行关键功能。
3. 确认无误后再手动 `git add` / `git commit`。
"""


def run_pipeline(mode: str, task_file: str | None, with_tester: bool, skip_codex: bool) -> int:
    root = get_root()
    ensure_layout(root)

    missing = check_required_files(root)
    if missing:
        print("缺少必要文件：")
        for p in missing:
            print(f"- {p}")
        return 10

    if task_file:
        requirement_path = root / task_file
    else:
        requirement_path = root / "ai/inbox/requirement.md"

    requirement = read_text(requirement_path).strip()
    if not requirement or requirement.startswith("# Requirement Inbox"):
        print(f"{requirement_path.relative_to(root)} 还没有写入真实需求。")
        return 11

    task_id = make_task_id()
    report_dir = root / "ai/reports" / task_id
    report_dir.mkdir(parents=True, exist_ok=True)
    write_text(root / "ai/reports/latest.txt", str(report_dir.relative_to(root)))

    run_log = report_dir / "hermes-run.log"
    append_text(run_log, f"# Hermes run {task_id}\nmode={mode}\nwith_tester={with_tester}\nskip_codex={skip_codex}\n\n")

    print(f"Task ID: {task_id}")
    print(f"Report Dir: {report_dir}")

    safety_code = run_cmd(
        ["bash", "ai/scripts/safety_check.sh", str(report_dir.relative_to(root))],
        cwd=root,
        log_file=run_log,
        check=False,
    )
    if safety_code != 0 and mode == "safe":
        print("安全检查未通过，safe 模式停止。")
        return safety_code

    fullstack_task_path = root / "ai/tasks/running" / f"{task_id}-fullstack.md"
    write_text(fullstack_task_path, build_fullstack_task(root, task_id, requirement, report_dir))

    if skip_codex:
        fullstack_exit = 0
        write_text(report_dir / "codex-fullstack-result.md", "skip_codex=true，本轮未调用 Codex 全栈开发。")
    else:
        fullstack_exit = run_cmd(
            [
                "bash",
                "ai/scripts/run_codex_worker.sh",
                "ai/roles/CODEX_FULLSTACK.md",
                str(fullstack_task_path.relative_to(root)),
                str((report_dir / "codex-fullstack-result.md").relative_to(root)),
            ],
            cwd=root,
            log_file=run_log,
            check=False,
        )

    test_exit = run_cmd(
        ["bash", "ai/scripts/run_tests.sh", str(report_dir.relative_to(root))],
        cwd=root,
        log_file=run_log,
        check=False,
    )

    run_cmd(
        ["bash", "ai/scripts/collect_diff.sh", str(report_dir.relative_to(root))],
        cwd=root,
        log_file=run_log,
        check=False,
    )

    tester_exit: int | None = None
    if with_tester and not skip_codex:
        tester_task_path = root / "ai/tasks/running" / f"{task_id}-tester.md"
        write_text(tester_task_path, build_tester_task(root, task_id, requirement, report_dir))
        tester_exit = run_cmd(
            [
                "bash",
                "ai/scripts/run_codex_worker.sh",
                "ai/roles/CODEX_TESTER.md",
                str(tester_task_path.relative_to(root)),
                str((report_dir / "codex-tester-result.md").relative_to(root)),
            ],
            cwd=root,
            log_file=run_log,
            check=False,
        )

    review_task_path = root / "ai/tasks/running" / f"{task_id}-review.md"
    write_text(review_task_path, build_review_task(root, task_id, requirement, report_dir, with_tester and not skip_codex))

    if skip_codex:
        reviewer_exit = 0
        write_text(report_dir / "codex-reviewer-result.md", "skip_codex=true，本轮未调用 Codex Reviewer。")
    else:
        reviewer_exit = run_cmd(
            [
                "bash",
                "ai/scripts/run_codex_worker.sh",
                "ai/roles/CODEX_REVIEWER.md",
                str(review_task_path.relative_to(root)),
                str((report_dir / "codex-reviewer-result.md").relative_to(root)),
            ],
            cwd=root,
            log_file=run_log,
            check=False,
        )

    final_report = build_final_acceptance(
        task_id=task_id,
        requirement=requirement,
        report_dir=report_dir,
        fullstack_exit=fullstack_exit,
        test_exit=test_exit,
        tester_exit=tester_exit,
        reviewer_exit=reviewer_exit,
    )
    write_text(report_dir / "final-acceptance.md", final_report)

    done_task_path = root / "ai/tasks/done" / f"{task_id}.md"
    write_text(done_task_path, read_text(fullstack_task_path))

    print("\n流程完成。")
    print(f"最终报告：{report_dir / 'final-acceptance.md'}")
    print(f"最新报告指针：{root / 'ai/reports/latest.txt'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--mode", default="safe", choices=["safe", "force"])
    parser.add_argument("--task", default=None, help="可选：指定任务文件，例如 ai/tasks/pending/TASK-001.md")
    parser.add_argument("--with-tester", action="store_true", help="调用 Codex Tester 龙虾做额外测试验收")
    parser.add_argument("--skip-codex", action="store_true", help="只跑脚本链路，不调用 Codex，用于自检")
    args = parser.parse_args()

    if args.command == "run":
        return run_pipeline(
            mode=args.mode,
            task_file=args.task,
            with_tester=args.with_tester,
            skip_codex=args.skip_codex,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

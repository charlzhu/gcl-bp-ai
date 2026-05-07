#!/usr/bin/env python3
"""Hermes 技术经理模式主控脚本。

用法：
  python ai/scripts/company_orchestrator.py new --from-inbox
  python ai/scripts/company_orchestrator.py run --from-inbox --manager-mode
  python ai/scripts/company_orchestrator.py status --latest

职责：创建 TASK、复制附件、生成附件摘要、生成 Codex Prompt、调用 Codex、运行测试、质量检查、定向修复、生成报告。
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from attachment_manager import build_attachments_summary, copy_inbox_attachments
from event_bus import append_event, print_event, read_events
from task_state import ensure_task_dirs, find_latest_task_dir, find_task_dir, move_task, task_dir_for, write_state

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INBOX_REQUIREMENT = PROJECT_ROOT / "ai" / "inbox" / "requirement.md"
TZ = ZoneInfo("America/Los_Angeles")
MAX_RETRY = 2


def new_task_id() -> str:
    """生成任务 ID。"""
    return "TASK-" + datetime.now(TZ).strftime("%Y%m%d-%H%M%S")


def run_shell(cmd: list[str], task_dir: Path, task_id: str, stage: str, log_file: str | None = None) -> int:
    """执行命令，实时打印并写入任务事件。"""
    append_event(task_dir, task_id, "orchestrator", stage, f"开始执行命令：{' '.join(cmd)}")
    print_event("orchestrator", stage, f"开始执行命令：{' '.join(cmd)}")

    log_handle = None
    if log_file:
        log_handle = (task_dir / log_file).open("a", encoding="utf-8")

    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            if log_handle:
                log_handle.write(line)
                log_handle.flush()
            clean = line.strip()
            if clean:
                append_event(task_dir, task_id, "shell", stage, clean)
        rc = process.wait()
        if rc == 0:
            append_event(task_dir, task_id, "orchestrator", stage, "命令执行成功")
        else:
            append_event(task_dir, task_id, "orchestrator", stage, f"命令执行失败：{rc}", level="error")
        return rc
    finally:
        if log_handle:
            log_handle.close()


def create_task_from_inbox() -> tuple[str, Path]:
    """从 ai/inbox 创建新任务，并复制附件。"""
    ensure_task_dirs()
    if not INBOX_REQUIREMENT.exists():
        raise FileNotFoundError(f"Missing requirement file: {INBOX_REQUIREMENT}")

    task_id = new_task_id()
    task_dir = task_dir_for("DRAFT", task_id)
    task_dir.mkdir(parents=True, exist_ok=False)

    shutil.copyfile(INBOX_REQUIREMENT, task_dir / "requirement.md")
    copied = copy_inbox_attachments(task_dir)
    build_attachments_summary(task_dir)
    write_state(task_dir, task_id, "DRAFT", "任务已创建，附件已复制并生成摘要")

    append_event(task_dir, task_id, "hermes.technical_manager", "draft", f"已从 inbox 创建任务，附件数量：{len(copied)}")
    print_event("hermes.technical_manager", "draft", f"已创建任务：{task_id}，附件数量：{len(copied)}")
    return task_id, task_dir


def generate_plan_files(task_id: str, task_dir: Path) -> None:
    """生成 plan.md、acceptance.md、codex_prompt.md。"""
    requirement = (task_dir / "requirement.md").read_text(encoding="utf-8", errors="ignore")
    manifest = (task_dir / "attachments_manifest.md").read_text(encoding="utf-8", errors="ignore")
    attachment_summary = (task_dir / "attachments_summary.md").read_text(encoding="utf-8", errors="ignore")

    plan = f"""# {task_id} 技术经理执行计划

## 1. 需求理解

{requirement}

## 2. 附件处理

- 附件目录：`{task_dir / 'attachments'}`
- 附件清单：`attachments_manifest.md`
- 附件摘要：`attachments_summary.md`
- 原始附件默认只读，禁止覆盖 `ai/inbox/attachments`。

## 3. 技术经理执行边界

1. Hermes 负责理解需求、拆任务、检查质量、纠错和报告。
2. Codex 只作为受控执行工程师。
3. 不自动 commit。
4. 不自动 push。
5. 不自动部署。
6. 不修改 .env、密钥、生产配置。
7. 如涉及数据库结构变更、权限、安全逻辑、大范围重构，必须暂停并报告。

## 4. 标准执行步骤

1. 安全检查。
2. Codex 首轮实现。
3. 运行基础测试。
4. 收集 diff。
5. 技术经理质量检查。
6. 如失败，最多 2 次定向修复。
7. 生成交付报告。
8. 进入 WAIT_ACCEPT，等待用户验收。
"""

    acceptance = f"""# {task_id} 验收标准

1. 需求符合 `requirement.md`。
2. 附件使用符合 `attachments_manifest.md` 和 `attachments_summary.md`。
3. 不修改 `ai/inbox/attachments` 原始附件。
4. 修改范围不超出需求边界。
5. `python -m compileall backend scripts ai/scripts` 通过。
6. 如存在 `tests`，`pytest tests -q` 通过。
7. 如存在 `frontend/package.json`，`npm run build --prefix frontend` 通过。
8. 已生成 `event.jsonl`、`state.json`、`test.log`、`diff.patch`、`quality_review.md`、`report.md`。
9. 未自动 commit、push、deploy。
"""

    codex_prompt = f"""你是本地项目中的受控 Codex 工程师。Hermes 是技术经理，你必须严格按技术经理给出的任务执行。

# 原始需求

{requirement}

# 附件清单

{manifest}

# 附件摘要

{attachment_summary[:12000]}

# 执行计划

{plan}

# 工作规则

1. 先审查当前仓库状态，再做增量修改。
2. 只做本需求相关修改，不做无关重构。
3. 不要自动 commit。
4. 不要自动 push。
5. 不要部署。
6. 不要修改 `.env`、密钥、生产配置。
7. 不要修改 `ai/inbox/attachments` 下的原始附件。
8. 如发现需求不清、附件冲突、需要数据库结构变更、权限/安全逻辑变更，请停止并在最终反馈中说明。
9. 引用附件结论时，必须说明来自哪个附件或附件摘要。
10. 所有新增和修改代码必须保持项目现有风格，复杂业务逻辑写中文注释。

# 最终反馈必须包含

1. 当前仓库能力判断。
2. 修改了哪些文件。
3. 每个文件改了什么。
4. 如何使用了附件。
5. 是否存在风险。
6. 建议运行哪些测试。
"""

    (task_dir / "plan.md").write_text(plan, encoding="utf-8")
    (task_dir / "acceptance.md").write_text(acceptance, encoding="utf-8")
    (task_dir / "codex_prompt.md").write_text(codex_prompt, encoding="utf-8")
    append_event(task_dir, task_id, "hermes.technical_manager", "planning", "已生成 plan.md / acceptance.md / codex_prompt.md")
    print_event("hermes.technical_manager", "planning", "已生成计划、验收标准和 Codex Prompt")


def generate_repair_prompt(task_id: str, task_dir: Path, round_no: int) -> str:
    """根据测试日志和质量检查生成定向修复 Prompt。"""
    test_log = (task_dir / "test.log").read_text(encoding="utf-8", errors="ignore") if (task_dir / "test.log").exists() else "未找到 test.log"
    quality = (task_dir / "quality_review.md").read_text(encoding="utf-8", errors="ignore") if (task_dir / "quality_review.md").exists() else "未找到 quality_review.md"
    diff_stat = (task_dir / "diff_stat.txt").read_text(encoding="utf-8", errors="ignore") if (task_dir / "diff_stat.txt").exists() else "未找到 diff_stat.txt"

    prompt = f"""# Codex 定向修复任务：{task_id} / round {round_no}

你刚才执行的任务没有通过测试或技术经理质量检查。不要重新自由发挥，只做定向修复。

## 当前测试日志摘要

```text
{test_log[-12000:]}
```

## 当前质量检查结果

{quality}

## 当前 diff 摘要

```text
{diff_stat}
```

## 修复要求

1. 不要推翻已有实现。
2. 只修复当前失败点或质量检查问题。
3. 不要新增无关功能。
4. 不要大范围重构。
5. 不要修改 `.env`、生产配置、数据库迁移。
6. 不要修改 `ai/inbox/attachments` 原始附件。
7. 修复后说明具体修了什么。
8. 如果无法修复，明确说明原因。

## 输出要求

1. 修复了哪些文件。
2. 修复了什么问题。
3. 是否还有风险。
4. 建议重新运行哪些测试。
"""
    filename = f"repair_prompt_round_{round_no}.md"
    (task_dir / filename).write_text(prompt, encoding="utf-8")
    append_event(task_dir, task_id, "hermes.technical_manager", "repair", f"已生成定向修复 prompt：{filename}")
    return filename


def run_codex_once(task_id: str, task_dir: Path, prompt_file: str, model: str | None = None) -> int:
    """执行一次 Codex。"""
    cmd = [
        sys.executable,
        "ai/scripts/codex_runner.py",
        "--task-id",
        task_id,
        "--task-dir",
        str(task_dir),
        "--project-root",
        str(PROJECT_ROOT),
        "--prompt-file",
        prompt_file,
    ]
    if model:
        cmd.extend(["--model", model])
    return run_shell(cmd, task_dir, task_id, "codex", "codex_runner.log")


def run_testing(task_id: str, task_dir: Path, test_mode: str = "basic") -> int:
    """运行测试。"""
    return run_shell(["bash", "ai/scripts/run_tests.sh", test_mode], task_dir, task_id, "testing", "test.log")


def collect_diff(task_id: str, task_dir: Path) -> int:
    """收集 diff。"""
    return run_shell(["bash", "ai/scripts/collect_diff.sh", str(task_dir)], task_dir, task_id, "reviewing", "collect_diff.log")


def run_quality_review(task_id: str, task_dir: Path) -> int:
    """运行技术经理质量检查。"""
    return run_shell(
        [sys.executable, "ai/scripts/quality_review.py", "--task-dir", str(task_dir), "--project-root", str(PROJECT_ROOT)],
        task_dir,
        task_id,
        "quality_review",
        "quality_review.log",
    )


def build_report(task_id: str, task_dir: Path, conclusion: str) -> int:
    """生成报告。"""
    return run_shell(
        [sys.executable, "ai/scripts/report_builder.py", "--task-id", task_id, "--task-dir", str(task_dir), "--conclusion", conclusion],
        task_dir,
        task_id,
        "report",
        "report_builder.log",
    )


def run_manager_loop(task_id: str, task_dir: Path, model: str | None = None, test_mode: str = "basic") -> tuple[int, str]:
    """技术经理闭环：Codex -> 测试 -> diff -> 质量检查 -> 必要时定向修复。"""
    prompt_file = "codex_prompt.md"
    for attempt in range(MAX_RETRY + 1):
        append_event(task_dir, task_id, "hermes.technical_manager", "attempt", f"开始第 {attempt + 1} 次执行，prompt={prompt_file}")
        print_event("hermes.technical_manager", "attempt", f"开始第 {attempt + 1} 次执行，prompt={prompt_file}")

        codex_rc = run_codex_once(task_id, task_dir, prompt_file=prompt_file, model=model)
        task_dir = move_task(task_id, "TESTING", "Codex 执行结束，开始测试")
        test_rc = run_testing(task_id, task_dir, test_mode=test_mode)
        task_dir = move_task(task_id, "REVIEWING", "测试结束，开始收集 diff 和质量检查")
        collect_diff(task_id, task_dir)
        quality_rc = run_quality_review(task_id, task_dir)

        if codex_rc == 0 and test_rc == 0 and quality_rc == 0:
            append_event(task_dir, task_id, "hermes.technical_manager", "quality_pass", "测试和质量检查通过")
            return 0, "PASS"

        if codex_rc == 0 and test_rc == 0 and quality_rc == 1:
            append_event(task_dir, task_id, "hermes.technical_manager", "quality_warn", "测试通过，但质量检查有警告，进入人工验收", level="warn")
            return 0, "WARN"

        if attempt >= MAX_RETRY:
            append_event(task_dir, task_id, "hermes.technical_manager", "retry_exhausted", "已达到最大重试次数，停止自动修复", level="error")
            return 1, "FAIL"

        prompt_file = generate_repair_prompt(task_id, task_dir, attempt + 1)
        task_dir = move_task(task_id, "RUNNING", f"进入第 {attempt + 2} 次定向修复")

    return 1, "FAIL"


def run_task(task_id: str, task_dir: Path, manager_mode: bool = False, model: str | None = None, test_mode: str = "basic") -> int:
    """执行任务。"""
    task_dir = move_task(task_id, "PLANNING", "进入规划阶段")
    append_event(task_dir, task_id, "hermes.technical_manager", "planning", "进入规划阶段")
    build_attachments_summary(task_dir)
    generate_plan_files(task_id, task_dir)

    task_dir = move_task(task_id, "WAIT_CONFIRM", "等待用户确认执行。CLI 模式已由调用方确认后继续。")
    append_event(task_dir, task_id, "hermes.technical_manager", "wait_confirm", "已生成计划，等待确认。当前由命令参数继续执行。")

    task_dir = move_task(task_id, "RUNNING", "开始执行")
    safety_rc = run_shell(["bash", "ai/scripts/safety_check.sh"], task_dir, task_id, "safety", "safety.log")
    if safety_rc != 0:
        failed_dir = move_task(task_id, "FAILED", "安全检查失败")
        build_report(task_id, failed_dir, "FAILED")
        return safety_rc

    if manager_mode:
        rc, conclusion = run_manager_loop(task_id, task_dir, model=model, test_mode=test_mode)
    else:
        rc = run_codex_once(task_id, task_dir, prompt_file="codex_prompt.md", model=model)
        task_dir = move_task(task_id, "TESTING", "开始测试")
        test_rc = run_testing(task_id, task_dir, test_mode=test_mode)
        task_dir = move_task(task_id, "REVIEWING", "开始收集 diff 和质量检查")
        collect_diff(task_id, task_dir)
        quality_rc = run_quality_review(task_id, task_dir)
        rc = 0 if rc == 0 and test_rc == 0 and quality_rc in (0, 1) else 1
        conclusion = "PASS" if quality_rc == 0 else "WARN" if quality_rc == 1 and rc == 0 else "FAIL"

    current_dir = find_task_dir(task_id)
    if rc == 0:
        build_report(task_id, current_dir, conclusion)
        wait_dir = move_task(task_id, "WAIT_ACCEPT", f"自动执行完成，技术经理结论：{conclusion}")
        append_event(wait_dir, task_id, "hermes.technical_manager", "wait_accept", f"任务完成，等待人工验收，结论：{conclusion}")
        print_event("hermes.technical_manager", "wait_accept", f"任务完成，报告：{wait_dir / 'report.md'}")
        return 0

    build_report(task_id, current_dir, "FAILED")
    failed_dir = move_task(task_id, "FAILED", "自动执行失败或达到最大重试次数")
    append_event(failed_dir, task_id, "hermes.technical_manager", "failed", "任务失败，已生成失败报告", level="error")
    print_event("hermes.technical_manager", "failed", f"任务失败，报告：{failed_dir / 'report.md'}", level="error")
    return 1


def print_status(task_dir: Path) -> None:
    """打印任务状态和最近事件。"""
    state_file = task_dir / "state.json"
    print(f"task_dir={task_dir}")
    if state_file.exists():
        print(state_file.read_text(encoding="utf-8"))
    else:
        print("state.json not found")
    print("\nRecent events:")
    for event in read_events(task_dir, limit=30):
        print(f"- {event.get('ts')} [{event.get('level')}] {event.get('role')}/{event.get('stage')}: {event.get('message')}")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    new_parser = sub.add_parser("new")
    new_parser.add_argument("--from-inbox", action="store_true")

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--from-inbox", action="store_true")
    run_parser.add_argument("--task-id", default=None)
    run_parser.add_argument("--manager-mode", action="store_true")
    run_parser.add_argument("--model", default=None)
    run_parser.add_argument("--test-mode", default="basic", choices=["basic", "full"])

    status_parser = sub.add_parser("status")
    status_parser.add_argument("--task-id", default=None)
    status_parser.add_argument("--latest", action="store_true")

    args = parser.parse_args()

    if args.command == "new":
        task_id, task_dir = create_task_from_inbox()
        print(f"task_id={task_id}")
        print(f"task_dir={task_dir}")
        return 0

    if args.command == "run":
        if args.from_inbox:
            task_id, task_dir = create_task_from_inbox()
        else:
            if not args.task_id:
                raise ValueError("--task-id is required when not using --from-inbox")
            task_id = args.task_id
            task_dir = find_task_dir(task_id)
        return run_task(task_id, task_dir, manager_mode=args.manager_mode, model=args.model, test_mode=args.test_mode)

    if args.command == "status":
        if args.latest:
            print_status(find_latest_task_dir())
            return 0
        if not args.task_id:
            raise ValueError("--task-id or --latest is required")
        print_status(find_task_dir(args.task_id))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

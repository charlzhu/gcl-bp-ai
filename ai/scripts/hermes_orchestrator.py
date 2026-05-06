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
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, TypeVar


T = TypeVar("T")
STAGE_ORDER = [
    "safety_check",
    "codex_fullstack",
    "run_tests",
    "collect_diff",
    "codex_reviewer",
    "acceptance_judge",
    "final_report",
]

AUTOMATION_OUTPUT_PREFIXES = (
    "ai/reports/",
    "ai/tasks/running/",
    "ai/tasks/done/",
)


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


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    """读取 JSON 文件。

    参数：
        path：JSON 文件路径。
        default：文件不存在或解析失败时返回的默认字典。

    返回值：
        JSON 对象字典；读取失败时返回 default 或空字典。
    """
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def timed_stage(name: str, timings: dict[str, float], run_log: Path, action: Callable[[], T]) -> T:
    """记录单个流水线阶段耗时。

    参数：
        name：阶段名称，写入 hermes-run.log 并用于 final-acceptance.md 汇总。
        timings：阶段耗时字典，键为阶段名称，值为秒数。
        run_log：Hermes 本轮运行日志文件。
        action：实际要执行的阶段函数。

    返回值：
        返回 action 的原始返回值，便于调用方继续沿用原有退出码逻辑。
    """
    started_at = dt.datetime.now().isoformat(timespec="seconds")
    append_text(run_log, f"\n[stage:{name}] start={started_at}\n")
    start = time.perf_counter()
    try:
        return action()
    finally:
        elapsed = time.perf_counter() - start
        timings[name] = elapsed
        append_text(run_log, f"[stage:{name}] elapsed={elapsed:.3f}s\n")


def filtered_status_lines(root: Path) -> list[str]:
    """读取排除 Hermes 产物后的 Git 状态。

    参数：
        root：项目 Git 根目录。

    返回值：
        已过滤 ai/reports 和轮次任务产物后的 `git status --short` 行。
    """
    status = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if status.returncode != 0:
        return []

    lines: list[str] = []
    for line in status.stdout.splitlines():
        path = line[3:].strip() if len(line) >= 4 else ""
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[-1].strip()
        if path.startswith(AUTOMATION_OUTPUT_PREFIXES):
            continue
        if "__pycache__/" in path or path.endswith(".pyc"):
            continue
        lines.append(line)
    return lines


def git_state_fingerprint(root: Path) -> str:
    """计算当前实质 diff 指纹。

    参数：
        root：项目 Git 根目录。

    返回值：
        由非报告 Git 状态和 tracked diff 内容计算出的 SHA256 摘要。

    说明：
        用于判断某一轮 Codex 是否产生了新的实质变更。报告文件和运行任务卡
        不参与指纹，避免自动化产物误触发“有 diff”。
    """
    diff = subprocess.run(
        [
            "git",
            "diff",
            "--",
            ".",
            ":(exclude)ai/reports/**",
            ":(exclude)ai/tasks/running/**",
            ":(exclude)ai/tasks/done/**",
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    status_text = "\n".join(filtered_status_lines(root))
    payload = status_text + "\n---diff---\n" + (diff.stdout if diff.returncode == 0 else "")
    return hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()


def has_code_diff(root: Path) -> bool:
    """判断本轮是否存在代码或项目事实源 diff。

    参数：
        root：项目 Git 根目录。

    返回值：
        存在已跟踪文件 diff 或未跟踪源码文件时返回 True；否则返回 False。

    说明：
        这里同时检查 git diff 和未跟踪源码文件，避免新增代码文件被漏判。
        ai/reports、IDE 缓存和 macOS 本地文件不计入判断，防止报告产物影响加速逻辑。
    """
    result = subprocess.run(["git", "diff", "--quiet", "--exit-code"], cwd=str(root))
    if result.returncode != 0:
        return True

    status = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if status.returncode != 0:
        return False

    ignored_untracked = (
        "ai/reports/",
        ".idea/",
        ".pytest_cache/",
        ".playwright-cli/",
        "__pycache__/",
    )
    source_prefixes = (
        "backend/",
        "frontend/",
        "scripts/",
        "ai/scripts/",
        "ai/company/",
        "ai/context/",
        "ai/roles/",
        "docs/",
    )
    source_files = {"AGENTS.md", "README_WORKSPACE.md"}

    for line in status.stdout.splitlines():
        if not line.startswith("?? "):
            continue
        path = line[3:].strip()
        if path in {"~", ".DS_Store"} or path.endswith(".pyc"):
            continue
        if path.startswith(ignored_untracked) or "__pycache__/" in path:
            continue
        if path.startswith(source_prefixes) or path in source_files:
            return True
    return False


def write_skipped_test_log(report_dir: Path, test_mode: str, reason: str) -> None:
    """写入跳过测试时的占位测试日志。

    参数：
        report_dir：本轮报告目录。
        test_mode：本轮选择的测试模式。
        reason：跳过 run_tests.sh 的原因。

    返回值：
        无返回值，直接写入 test.log，保证 final-acceptance.md 仍有可追溯测试材料。
    """
    write_text(
        report_dir / "test.log",
        "\n".join(
            [
                "== Test Runner ==",
                f"Mode: {test_mode}",
                f"Skipped: {reason}",
                "",
            ]
        ),
    )


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
        "ai/roles/CODEX_REWORKER.md",
        "ai/roles/CODEX_REVIEWER.md",
        "ai/scripts/acceptance_judge.py",
        "ai/scripts/build_rework_task.py",
        "ai/scripts/run_codex_worker.sh",
        "ai/scripts/run_tests.sh",
        "ai/scripts/collect_diff.sh",
        "ai/scripts/select_test_profile.py",
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
    run_options: dict[str, str],
    round_results: list[dict[str, Any]],
    final_verdict: str,
    final_stop_reason: str,
) -> str:
    """生成支持多轮返工的最终验收报告。

    参数：
        task_id：任务编号。
        requirement：用户原始需求。
        report_dir：任务总报告目录。
        run_options：本次运行参数。
        round_results：每轮执行结果列表。
        final_verdict：最终验收判定。
        final_stop_reason：未达标或停止时的原因。

    返回值：
        Markdown 格式的最终验收报告。
    """
    last_round_dir = Path(round_results[-1]["round_dir"]) if round_results else report_dir
    status = read_text(last_round_dir / "git-status.txt", "未找到 git status。")
    diffstat = read_text(last_round_dir / "diffstat.txt", "未找到 diffstat。")

    is_passed = final_verdict == "PASS"
    display_root = report_dir.parent.parent.parent
    options_rows = "\n".join(f"| {key} | {value} |" for key, value in run_options.items())
    round_rows = "\n".join(
        "| {index} | {verdict} | {passed} | {fullstack} | {test} | {reviewer} | {diff} | {streak} | {path} |".format(
            index=item["round_index"],
            verdict=item.get("verdict", "UNKNOWN"),
            passed="是" if item.get("passed") else "否",
            fullstack=item.get("fullstack_exit", "NA"),
            test=item.get("test_exit", "NA"),
            reviewer=item.get("reviewer_exit", "NA"),
            diff="是" if item.get("round_had_substantive_diff") else "否",
            streak=item.get("no_diff_streak", 0),
            path=Path(item["round_dir"]).relative_to(display_root),
        )
        for item in round_results
    )
    if not round_rows:
        round_rows = "| 无 | 无 | 否 | NA | NA | NA | 否 | 0 | 无 |"

    round_sections: list[str] = []
    for item in round_results:
        timings = item.get("stage_timings", {})
        timing_rows = "\n".join(
            f"| {stage} | {timings.get(stage, 0.0):.2f}s |" for stage in STAGE_ORDER
        )
        notes = item.get("stage_notes") or ["无"]
        reasons = item.get("reasons") or ["无"]
        ignored_risks = item.get("ignored_source_risks") or []
        ignored_text = "\n".join(f"- {path}" for path in ignored_risks) if ignored_risks else "- 无"
        round_sections.append(
            """### Round {index}

- 报告目录：`{round_path}`
- Verdict：`{verdict}`
- 停止原因：{stop_reason}
- 失败/通过原因：
{reasons}

阶段耗时：

| 阶段 | 耗时 |
|---|---|
{timings}

阶段说明：
{notes}

.gitignore 风险：
{ignored}
""".format(
                index=item["round_index"],
                round_path=Path(item["round_dir"]).relative_to(display_root),
                verdict=item.get("verdict", "UNKNOWN"),
                stop_reason=item.get("stop_reason") or "无",
                reasons="\n".join(f"- {reason}" for reason in reasons),
                timings=timing_rows,
                notes="\n".join(f"- {note}" for note in notes),
                ignored=ignored_text,
            )
        )

    final_stop = final_stop_reason or ("已达标。" if is_passed else "未记录停止原因。")

    return f"""# {task_id} 最终验收报告

## 一、用户需求

{requirement.strip()}

## 二、本轮使用参数

| 参数 | 值 |
|---|---|
{options_rows}

## 三、最终 Verdict

| 项目 | 结果 |
|---|---|
| 总轮数 | {len(round_results)} |
| 最终 verdict | {final_verdict} |
| 是否达标 | {"是" if is_passed else "否"} |
| 停止原因 | {final_stop} |

## 四、每轮结果

| Round | Verdict | 达标 | Fullstack Exit | Test Exit | Reviewer Exit | 本轮实质 diff | 无 diff 连续轮数 | 报告目录 |
|---|---|---|---|---|---|---|---|---|
{round_rows}

## 五、每轮详情

{chr(10).join(round_sections)}

## 六、最后一轮 Git 状态

```text
{status}
```

## 七、最后一轮 Diff 摘要

```text
{diffstat}
```

## 八、Hermes 结论

- 本流程不会自动 commit、merge、push 或部署。
- `PASS` 表示测试通过且 Reviewer 未阻塞。
- `FAIL_REPAIRABLE` 表示测试失败或 Reviewer 未通过，且仍可在返工轮次内继续修复。
- `FAIL_UNREPAIRABLE` 表示触发文件数、敏感文件或连续无 diff 等停止条件。
- `BLOCKED` 表示安全检查或执行环境阻塞。

## 九、人工复核点

- 请人工查看最后一轮 `diff.patch`。
- 是否提交、合并、推送或部署仍需用户人工确认。
"""


def run_pipeline(
    mode: str,
    task_file: str | None,
    with_tester: bool,
    skip_codex: bool,
    skip_tests: bool,
    skip_review: bool,
    test_mode: str,
    until_pass: bool,
    max_repair_rounds: int,
    repair_on_fail: bool,
) -> int:
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

    repair_enabled = (until_pass or repair_on_fail) and not skip_codex
    max_repair_rounds = max(0, max_repair_rounds)
    max_total_rounds = 1 + (max_repair_rounds if repair_enabled else 0)
    run_options = {
        "mode": mode,
        "task": task_file or "ai/inbox/requirement.md",
        "with_tester": str(with_tester),
        "skip_codex": str(skip_codex),
        "skip_tests": str(skip_tests),
        "skip_review": str(skip_review),
        "test_mode": test_mode,
        "until_pass": str(until_pass),
        "repair_on_fail": str(repair_on_fail),
        "max_repair_rounds": str(max_repair_rounds),
        "repair_enabled": str(repair_enabled),
    }
    write_text(
        report_dir / "hermes-run.log",
        "# Hermes run {task_id}\n{options}\n\n".format(
            task_id=task_id,
            options="\n".join(f"{key}={value}" for key, value in run_options.items()),
        ),
    )

    print(f"Task ID: {task_id}")
    print(f"Report Dir: {report_dir}")

    rounds_root = report_dir / "rounds"
    rounds_root.mkdir(parents=True, exist_ok=True)
    current_task_path = root / "ai/tasks/running" / f"{task_id}-round-1-fullstack.md"
    write_text(current_task_path, build_fullstack_task(root, task_id, requirement, rounds_root / "round-1"))
    current_role = "ai/roles/CODEX_FULLSTACK.md"

    round_results: list[dict[str, Any]] = []
    no_diff_streak = 0
    final_verdict = "BLOCKED"
    final_stop_reason = ""
    fingerprint_before_round = git_state_fingerprint(root)

    for round_index in range(1, max_total_rounds + 1):
        round_dir = rounds_root / f"round-{round_index}"
        round_dir.mkdir(parents=True, exist_ok=True)
        run_log = round_dir / "hermes-run.log"
        stage_timings: dict[str, float] = {}
        stage_notes: list[str] = []
        append_text(
            run_log,
            "# Hermes round {round_index}/{max_rounds}\n{options}\n\n".format(
                round_index=round_index,
                max_rounds=max_total_rounds,
                options="\n".join(f"{key}={value}" for key, value in run_options.items()),
            ),
        )
        append_text(
            report_dir / "hermes-run.log",
            f"[round-{round_index}] start={dt.datetime.now().isoformat(timespec='seconds')}\n",
        )

        print(f"\n== Round {round_index}/{max_total_rounds} ==")
        safety_code = timed_stage(
            "safety_check",
            stage_timings,
            run_log,
            lambda: run_cmd(
                ["bash", "ai/scripts/safety_check.sh", str(round_dir.relative_to(root))],
                cwd=root,
                log_file=run_log,
                check=False,
            ),
        )

        fullstack_exit = 0
        test_exit = 0
        tester_exit: int | None = None
        reviewer_exit = 0
        reviewer_was_skipped = False
        code_diff_detected = has_code_diff(root)
        round_had_substantive_diff = False

        if safety_code != 0 and mode == "safe":
            stage_notes.append("安全检查未通过，safe 模式停止本轮后续开发、测试和审查。")
            write_text(round_dir / "codex-fullstack-result.md", "安全检查未通过，本轮未调用 Codex。")
            write_skipped_test_log(round_dir, test_mode, "安全检查未通过。")
            write_text(round_dir / "codex-reviewer-result.md", "安全检查未通过，本轮未调用 Reviewer。")
            reviewer_was_skipped = True
        else:
            def run_fullstack_stage() -> int:
                """执行或跳过本轮 Codex 开发/返工阶段。"""
                if skip_codex:
                    stage_notes.append("codex_fullstack：已按 --skip-codex 跳过。")
                    write_text(round_dir / "codex-fullstack-result.md", "skip_codex=true，本轮未调用 Codex。")
                    return 0
                return run_cmd(
                    [
                        "bash",
                        "ai/scripts/run_codex_worker.sh",
                        current_role,
                        str(current_task_path.relative_to(root)),
                        str((round_dir / "codex-fullstack-result.md").relative_to(root)),
                    ],
                    cwd=root,
                    log_file=run_log,
                    check=False,
                )

            fullstack_exit = timed_stage("codex_fullstack", stage_timings, run_log, run_fullstack_stage)
            fingerprint_after_fullstack = git_state_fingerprint(root)
            round_had_substantive_diff = fingerprint_after_fullstack != fingerprint_before_round
            if round_had_substantive_diff:
                no_diff_streak = 0
            else:
                no_diff_streak += 1

            code_diff_detected = has_code_diff(root)
            append_text(run_log, f"\ncode_diff_after_codex_fullstack={code_diff_detected}\n")
            append_text(run_log, f"round_had_substantive_diff={round_had_substantive_diff}\n")
            append_text(run_log, f"no_diff_streak={no_diff_streak}\n")

            def run_tests_stage() -> int:
                """根据参数和 diff 状态执行或跳过统一测试脚本。"""
                if skip_tests:
                    reason = "已按 --skip-tests 跳过 run_tests.sh。"
                    stage_notes.append(f"run_tests：{reason}")
                    write_skipped_test_log(round_dir, test_mode, reason)
                    return 0
                if not code_diff_detected:
                    reason = "未检测到代码 diff，自动跳过 run_tests.sh。"
                    stage_notes.append(f"run_tests：{reason}")
                    write_skipped_test_log(round_dir, test_mode, reason)
                    return 0
                return run_cmd(
                    ["bash", "ai/scripts/run_tests.sh", str(round_dir.relative_to(root)), test_mode],
                    cwd=root,
                    log_file=run_log,
                    check=False,
                )

            test_exit = timed_stage("run_tests", stage_timings, run_log, run_tests_stage)

        timed_stage(
            "collect_diff",
            stage_timings,
            run_log,
            lambda: run_cmd(
                ["bash", "ai/scripts/collect_diff.sh", str(round_dir.relative_to(root))],
                cwd=root,
                log_file=run_log,
                check=False,
            ),
        )

        if (
            safety_code == 0
            and with_tester
            and not skip_codex
            and code_diff_detected
            and not skip_tests
        ):
            tester_task_path = root / "ai/tasks/running" / f"{task_id}-round-{round_index}-tester.md"
            write_text(tester_task_path, build_tester_task(root, task_id, requirement, round_dir))
            tester_exit = run_cmd(
                [
                    "bash",
                    "ai/scripts/run_codex_worker.sh",
                    "ai/roles/CODEX_TESTER.md",
                    str(tester_task_path.relative_to(root)),
                    str((round_dir / "codex-tester-result.md").relative_to(root)),
                ],
                cwd=root,
                log_file=run_log,
                check=False,
            )

        def run_reviewer_stage() -> int:
            """根据参数和 diff 状态执行或跳过 Reviewer。"""
            nonlocal reviewer_was_skipped
            if safety_code != 0 and mode == "safe":
                reviewer_was_skipped = True
                return 0
            if skip_codex:
                reason = "skip_codex=true，本轮未调用 Codex Reviewer。"
                stage_notes.append("codex_reviewer：已按 --skip-codex 跳过。")
                write_text(round_dir / "codex-reviewer-result.md", reason)
                reviewer_was_skipped = True
                return 0
            if skip_review:
                reason = "skip_review=true，本轮按 --skip-review 跳过 Codex Reviewer。"
                stage_notes.append("codex_reviewer：已按 --skip-review 跳过。")
                write_text(round_dir / "codex-reviewer-result.md", reason)
                reviewer_was_skipped = True
                return 0
            if not code_diff_detected:
                reason = "未检测到代码 diff，本轮自动跳过 Codex Reviewer。"
                stage_notes.append(f"codex_reviewer：{reason}")
                write_text(round_dir / "codex-reviewer-result.md", reason)
                reviewer_was_skipped = True
                return 0

            review_task_path = root / "ai/tasks/running" / f"{task_id}-round-{round_index}-review.md"
            write_text(
                review_task_path,
                build_review_task(root, task_id, requirement, round_dir, with_tester and tester_exit is not None),
            )
            return run_cmd(
                [
                    "bash",
                    "ai/scripts/run_codex_worker.sh",
                    "ai/roles/CODEX_REVIEWER.md",
                    str(review_task_path.relative_to(root)),
                    str((round_dir / "codex-reviewer-result.md").relative_to(root)),
                ],
                cwd=root,
                log_file=run_log,
                check=False,
            )

        reviewer_exit = timed_stage("codex_reviewer", stage_timings, run_log, run_reviewer_stage)

        judge_cmd = [
            "python",
            "ai/scripts/acceptance_judge.py",
            "--root",
            str(root),
            "--round-dir",
            str(round_dir),
            "--safety-exit",
            str(safety_code),
            "--fullstack-exit",
            str(fullstack_exit),
            "--test-exit",
            str(test_exit),
            "--reviewer-exit",
            str(reviewer_exit),
            "--no-diff-streak",
            str(no_diff_streak),
            "--max-changed-files",
            "30",
            "--output",
            str(round_dir / "acceptance-verdict.json"),
        ]
        if reviewer_was_skipped:
            judge_cmd.append("--skip-review")
        if round_had_substantive_diff:
            judge_cmd.append("--round-had-substantive-diff")

        judge_exit = timed_stage(
            "acceptance_judge",
            stage_timings,
            run_log,
            lambda: run_cmd(judge_cmd, cwd=root, log_file=run_log, check=False),
        )
        verdict_data = load_json(round_dir / "acceptance-verdict.json")
        if judge_exit != 0 or not verdict_data:
            verdict_data = {
                "verdict": "BLOCKED",
                "passed": False,
                "repairable": False,
                "stop_reason": "acceptance_judge.py 执行失败。",
                "reasons": ["验收判定脚本执行失败。"],
            }
            write_text(
                round_dir / "acceptance-verdict.json",
                json.dumps(verdict_data, ensure_ascii=False, indent=2),
            )

        round_result = {
            "round_index": round_index,
            "round_dir": str(round_dir),
            "safety_exit": safety_code,
            "fullstack_exit": fullstack_exit,
            "test_exit": test_exit,
            "tester_exit": tester_exit,
            "reviewer_exit": reviewer_exit,
            "stage_timings": stage_timings,
            "stage_notes": stage_notes,
            **verdict_data,
        }
        round_results.append(round_result)
        final_verdict = str(verdict_data.get("verdict", "BLOCKED"))

        append_text(
            report_dir / "hermes-run.log",
            f"[round-{round_index}] verdict={final_verdict} passed={verdict_data.get('passed')}\n",
        )

        if verdict_data.get("passed"):
            final_stop_reason = "已达标。"
            break
        if final_verdict != "FAIL_REPAIRABLE":
            final_stop_reason = str(verdict_data.get("stop_reason") or "触发不可自动返工条件。")
            break
        if not repair_enabled:
            final_stop_reason = "未启用 --until-pass 或 --repair-on-fail，单轮失败后停止。"
            break
        if round_index >= max_total_rounds:
            final_stop_reason = f"已达到最大返工轮数 {max_repair_rounds}。"
            break

        next_round = round_index + 1
        current_task_path = root / "ai/tasks/running" / f"{task_id}-round-{next_round}-rework.md"
        build_rework_code = run_cmd(
            [
                "python",
                "ai/scripts/build_rework_task.py",
                "--task-id",
                task_id,
                "--requirement-file",
                str(requirement_path),
                "--previous-round-dir",
                str(round_dir),
                "--next-round",
                str(next_round),
                "--output",
                str(current_task_path),
            ],
            cwd=root,
            log_file=run_log,
            check=False,
        )
        if build_rework_code != 0:
            final_verdict = "BLOCKED"
            final_stop_reason = "返工任务卡生成失败。"
            break
        current_role = "ai/roles/CODEX_REWORKER.md"
        fingerprint_before_round = git_state_fingerprint(root)

    final_start = time.perf_counter()
    final_report = build_final_acceptance(
        task_id=task_id,
        requirement=requirement,
        report_dir=report_dir,
        run_options=run_options,
        round_results=round_results,
        final_verdict=final_verdict,
        final_stop_reason=final_stop_reason,
    )
    write_text(report_dir / "final-acceptance.md", final_report)
    append_text(
        report_dir / "hermes-run.log",
        f"[stage:final_report] elapsed={time.perf_counter() - final_start:.3f}s\n",
    )

    done_task_path = root / "ai/tasks/done" / f"{task_id}.md"
    write_text(done_task_path, read_text(root / "ai/tasks/running" / f"{task_id}-round-1-fullstack.md"))

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
    parser.add_argument("--skip-tests", action="store_true", help="跳过 run_tests.sh，加速只收集 diff 和报告的流程")
    parser.add_argument("--skip-review", action="store_true", help="跳过 Codex Reviewer 审查阶段")
    parser.add_argument("--until-pass", action="store_true", help="未达标时持续返工，直到 PASS 或触发停止条件")
    parser.add_argument("--repair-on-fail", action="store_true", help="测试失败或 Reviewer 不通过时自动生成返工任务并再次调用 Codex")
    parser.add_argument("--max-repair-rounds", type=int, default=3, help="最大返工轮数，默认 3")
    # business-import 是显式验收档位；auto 仍只由 select_test_profile.py 自动收敛到 smoke/full。
    parser.add_argument("--test-mode", default="smoke", choices=["auto", "smoke", "full", "business-import"], help="测试模式，auto 会自动选择 smoke/full，business-import 运行业务导入验收")
    args = parser.parse_args()

    if args.command == "run":
        return run_pipeline(
            mode=args.mode,
            task_file=args.task,
            with_tester=args.with_tester,
            skip_codex=args.skip_codex,
            skip_tests=args.skip_tests,
            skip_review=args.skip_review,
            test_mode=args.test_mode,
            until_pass=args.until_pass,
            max_repair_rounds=args.max_repair_rounds,
            repair_on_fail=args.repair_on_fail,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

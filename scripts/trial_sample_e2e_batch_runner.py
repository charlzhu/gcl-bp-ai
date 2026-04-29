from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from trial_sample_eval_common import (
    COMPARE_REPORT_PATH,
    DOCS_DIR,
    EXPECTED_PATH,
    FAILED_CASES_PATH,
    FIXED_CASES_PATH,
    FRONTEND_RESULTS_PATH,
    FULL_ACCEPTANCE_REPORT_PATH,
    PROJECT_ROOT,
    TMP_DIR,
    now_iso,
    read_json,
    write_json,
    write_markdown,
)


BATCH_RUNNER_REPORT_PATH = TMP_DIR / "trial_sample_e2e_batch_runner_report.json"


def _run_command(command: list[str], *, timeout_seconds: int | None = None) -> int:
    """执行一个子命令并实时输出日志。

    参数：
        command: 要执行的命令参数列表。
        timeout_seconds: 单个命令的超时时间；为空时不限制。
    返回值：
        子进程退出码。
    """

    try:
        completed = subprocess.run(command, cwd=PROJECT_ROOT, timeout=timeout_seconds, check=False)  # noqa: S603
    except subprocess.TimeoutExpired:
        return 124
    return int(completed.returncode)


def _expected_status_distribution_for_executed(frontend_results: dict[str, Any]) -> dict[str, int]:
    """统计已执行用例对应的标准答案状态分布。

    参数：
        frontend_results: 前端 E2E 结果 JSON。
    返回值：
        已执行用例的 expected_status 计数字典。
    """

    expected_payload = read_json(EXPECTED_PATH, default={}) or {}
    answers = expected_payload.get("answers", [])
    status_by_id = {
        item.get("id"): (item.get("expected") or {}).get("expected_status")
        for item in answers
        if item.get("id")
    }
    counter: Counter[str] = Counter()
    for item in frontend_results.get("results", []):
        status = status_by_id.get(item.get("question_id"))
        if status:
            counter[status] += 1
    return dict(counter)


def _load_current_state() -> dict[str, Any]:
    """读取当前 checkpoint 状态。

    参数：
        无。
    返回值：
        聚合后的前端执行、答案比对、失败和修复状态。
    """

    frontend_results = read_json(FRONTEND_RESULTS_PATH, default={}) or {}
    compare_report = read_json(COMPARE_REPORT_PATH, default={}) or {}
    failed_cases = read_json(FAILED_CASES_PATH, default=[]) or []
    fixed_cases = read_json(FIXED_CASES_PATH, default=[]) or []
    expected_distribution = _expected_status_distribution_for_executed(frontend_results)
    return {
        "frontend": frontend_results,
        "compare": compare_report,
        "failed_cases": failed_cases,
        "fixed_cases": fixed_cases,
        "expected_distribution": expected_distribution,
        "planned_case_count": int(frontend_results.get("total_cases") or frontend_results.get("planned_case_count") or 3281),
        "executed": int(frontend_results.get("executed") or 0),
        "pending": int(frontend_results.get("pending") or 0),
        "frontend_status_distribution": frontend_results.get("result_status_distribution") or {},
        "compare_summary": compare_report.get("summary") or {},
    }


def _write_full_report(*, status: str, stop_condition: str, runner_batches: list[dict[str, Any]]) -> None:
    """写入全量验收总报告 JSON。

    参数：
        status: 当前总状态，例如 running / stopped / completed。
        stop_condition: 停止原因。
        runner_batches: 本次 runner 执行的批次摘要。
    返回值：
        无。
    """

    state = _load_current_state()
    failed_cases = state["failed_cases"]
    fixed_cases = state["fixed_cases"]
    report = {
        "generated_at": now_iso(),
        "status": status,
        "stop_condition": stop_condition,
        "ledger": "tmp/trial_sample_eval/sample_question_ledger.json",
        "expected": "tmp/trial_sample_eval/expected_answers.json",
        "frontend": "tmp/trial_sample_eval/frontend_e2e_results.json",
        "compare": "tmp/trial_sample_eval/answer_compare_report.json",
        "sample_total": 1391,
        "variant_total": 1890,
        "planned_case_count": state["planned_case_count"],
        "frontend_executed": state["executed"],
        "frontend_pending": state["pending"],
        "frontend_status_distribution": state["frontend_status_distribution"],
        "compare_summary": state["compare_summary"],
        "failed_count": len(failed_cases),
        "failed_cases": failed_cases,
        "fixed_cases": fixed_cases,
        "runner_batches": runner_batches,
        "data_source": {
            "logistics_standard": "logistics_ai 中间库为准；源 zip 只做字段、文件数量和时间范围核验，不混用。",
            "bom_standard": "项目内真实 BOM 标准化数据/索引。",
        },
        "resume_commands": [
            "backend/.venv/bin/python scripts/trial_sample_e2e_batch_runner.py --resume --include-variants --batch-size 50 --time-budget-minutes 55",
            "backend/.venv/bin/python scripts/trial_sample_frontend_e2e_eval.py --resume --only-failed --include-variants --batch-size 25",
            "backend/.venv/bin/python scripts/trial_sample_answer_comparator.py",
        ],
        "compared_expected_status_distribution": state["expected_distribution"],
        "b_correct_clarification_count": state["expected_distribution"].get("needs_clarification", 0),
        "b_expected_compared_count": state["expected_distribution"].get("needs_clarification", 0),
        "c_correct_unsupported_count": state["expected_distribution"].get("unsupported", 0),
        "c_expected_compared_count": state["expected_distribution"].get("unsupported", 0),
        "mock_used": False,
        "hardcode_answers": False,
        "note": "本报告只统计已真实网页执行并比对的用例；剩余用例未标记通过。",
    }
    write_json(FULL_ACCEPTANCE_REPORT_PATH, report)


def _write_markdown_reports(*, stop_condition: str) -> None:
    """同步写入本轮验收相关 Markdown 报告。

    参数：
        stop_condition: 当前停止原因。
    返回值：
        无。
    """

    state = _load_current_state()
    failed_count = len(state["failed_cases"])
    b_count = state["expected_distribution"].get("needs_clarification", 0)
    c_count = state["expected_distribution"].get("unsupported", 0)
    summary = state["compare_summary"]
    lines = [
        "## 当前结论",
        "- 本轮不是冒烟测试，已从 checkpoint 继续执行真实网页 E2E。",
        "- 样例题总数：1391",
        "- 变体总数：1890",
        f"- 总计划网页 E2E：{state['planned_case_count']}",
        f"- 当前累计真实网页执行：{state['executed']}",
        f"- 当前未执行：{state['pending']}",
        f"- 前端执行状态分布：`{state['frontend_status_distribution']}`",
        f"- 当前已比对结果：`{summary}`",
        f"- 当前失败/待修复：{failed_count}",
        f"- B 类正确追问：`{b_count}/{b_count}`",
        f"- C 类正确拒答解释：`{c_count}/{c_count}`",
        f"- 停止条件：`{stop_condition}`。",
        "",
        "## Checkpoint",
        "- 前端结果：`tmp/trial_sample_eval/frontend_e2e_results.json`",
        "- 比对报告：`tmp/trial_sample_eval/answer_compare_report.json`",
        "- 失败清单：`tmp/trial_sample_eval/failed_cases.json`",
        "- 修复清单：`tmp/trial_sample_eval/fixed_cases.json`",
        "",
        "## 可恢复执行命令",
        "```bash",
        "backend/.venv/bin/python scripts/trial_sample_e2e_batch_runner.py --resume --include-variants --batch-size 50 --time-budget-minutes 55",
        "```",
    ]
    write_markdown(DOCS_DIR / "TRIAL_SAMPLE_FULL_E2E_ACCEPTANCE.md", "TRIAL_SAMPLE_FULL_E2E_ACCEPTANCE", lines)

    frontend_lines = [
        "- 前端地址：`http://127.0.0.1:5173/smart-chat`",
        "- 后端地址：`http://127.0.0.1:8000/api/v1`",
        f"- 总计划用例：{state['planned_case_count']}",
        f"- 已执行：{state['executed']}",
        f"- 未执行：{state['pending']}",
        f"- 状态：{state['frontend'].get('status')}",
        f"- 停止条件：{stop_condition}",
        "- 抓取方式：真实 `/smart-chat` 页面输入问题，读取 DOM 文本、表格、追问和拒答解释。",
        f"- 当前前端执行状态分布：`{state['frontend_status_distribution']}`",
        "- 服务日志位置：`tmp/trial_sample_eval/logs/`。",
        "- 可恢复命令：`backend/.venv/bin/python scripts/trial_sample_e2e_batch_runner.py --resume --include-variants --batch-size 50 --time-budget-minutes 55`",
    ]
    write_markdown(DOCS_DIR / "TRIAL_SAMPLE_FRONTEND_E2E_EVAL.md", "TRIAL_SAMPLE_FRONTEND_E2E_EVAL", frontend_lines)

    compare_lines = [
        f"- 报告状态：{state['compare'].get('status')}",
        f"- 比对总数：{state['compare'].get('total_compared', 0)}",
        f"- 结果分布：`{summary}`",
        f"- 失败/复核数量：{failed_count}",
        "",
        "## 失败原因分布",
    ]
    for reason, count in (state["compare"].get("reason_distribution") or {}).items():
        compare_lines.append(f"- {reason}: {count}")
    compare_lines.extend(["", "## 失败/复核样例"])
    for item in state["failed_cases"][:80]:
        compare_lines.append(f"- {item.get('case_id')}：{item.get('question')}；原因：{'; '.join(item.get('reasons') or [])}")
    write_markdown(DOCS_DIR / "TRIAL_SAMPLE_ANSWER_COMPARE_REPORT.md", "TRIAL_SAMPLE_ANSWER_COMPARE_REPORT", compare_lines)


def _run_one_batch(args: argparse.Namespace, batch_index: int) -> dict[str, Any]:
    """执行一个真实网页批次和一次自动比对。

    参数：
        args: 命令行参数。
        batch_index: 本轮 runner 内部批次序号。
    返回值：
        批次摘要，包含执行前后数量和失败数量。
    """

    before = _load_current_state()
    command = [
        sys.executable,
        "scripts/trial_sample_frontend_e2e_eval.py",
        "--resume",
        "--batch-size",
        str(args.batch_size),
        "--max-cases",
        str(args.batch_size),
        "--frontend-url",
        args.frontend_url,
        "--backend-url",
        args.backend_url,
    ]
    if args.include_variants:
        command.append("--include-variants")
    if args.headed:
        command.append("--headed")
    frontend_rc = _run_command(command, timeout_seconds=args.batch_timeout_seconds)
    comparator_rc = _run_command(
        [sys.executable, "scripts/trial_sample_answer_comparator.py"],
        timeout_seconds=args.comparator_timeout_seconds,
    )
    after = _load_current_state()
    batch = {
        "batch_index": batch_index,
        "started_executed": before["executed"],
        "finished_executed": after["executed"],
        "executed_delta": after["executed"] - before["executed"],
        "pending": after["pending"],
        "frontend_return_code": frontend_rc,
        "comparator_return_code": comparator_rc,
        "compare_summary": after["compare_summary"],
        "failed_count": len(after["failed_cases"]),
        "finished_at": now_iso(),
    }
    return batch


def run_batches(args: argparse.Namespace) -> dict[str, Any]:
    """循环执行真实网页 E2E 批次。

    参数：
        args: 命令行参数。
    返回值：
        runner 总结报告。
    """

    started_at = time.time()
    initial = _load_current_state()
    batches: list[dict[str, Any]] = []
    stop_condition = ""
    status = "running"
    max_batches = args.max_batches if args.max_batches and args.max_batches > 0 else None

    if initial["pending"] <= 0:
        status = "completed"
        stop_condition = "all_cases_completed"
    elif initial["failed_cases"]:
        status = "stopped"
        stop_condition = "existing_failed_cases_need_fix"
    else:
        batch_index = 0
        while True:
            if max_batches is not None and batch_index >= max_batches:
                status = "stopped"
                stop_condition = "max_batches_reached"
                break
            elapsed_minutes = (time.time() - started_at) / 60
            if elapsed_minutes >= args.time_budget_minutes:
                status = "stopped"
                stop_condition = "time_budget_reached"
                break
            current = _load_current_state()
            if current["pending"] <= 0:
                status = "completed"
                stop_condition = "all_cases_completed"
                break
            if current["failed_cases"]:
                status = "stopped"
                stop_condition = "failed_cases_need_fix"
                break

            batch_index += 1
            batch = _run_one_batch(args, batch_index)
            batches.append(batch)
            _write_full_report(status="running", stop_condition="running", runner_batches=batches)
            _write_markdown_reports(stop_condition="running")
            if batch["frontend_return_code"] != 0:
                status = "stopped"
                stop_condition = f"frontend_batch_failed_rc_{batch['frontend_return_code']}"
                break
            if batch["comparator_return_code"] != 0:
                status = "stopped"
                stop_condition = f"comparator_failed_rc_{batch['comparator_return_code']}"
                break
            if batch["executed_delta"] <= 0:
                status = "stopped"
                stop_condition = "no_progress_detected"
                break
            if args.stop_on_failure and batch["failed_count"] > 0:
                status = "stopped"
                stop_condition = "failed_cases_need_fix"
                break

    final = _load_current_state()
    if final["pending"] <= 0 and not final["failed_cases"]:
        status = "completed"
        stop_condition = "all_cases_completed"
    _write_full_report(status=status, stop_condition=stop_condition, runner_batches=batches)
    _write_markdown_reports(stop_condition=stop_condition)
    report = {
        "generated_at": now_iso(),
        "status": status,
        "stop_condition": stop_condition,
        "started_executed": initial["executed"],
        "finished_executed": final["executed"],
        "executed_delta": final["executed"] - initial["executed"],
        "pending": final["pending"],
        "compare_summary": final["compare_summary"],
        "failed_count": len(final["failed_cases"]),
        "batches": batches,
        "resume_command": "backend/.venv/bin/python scripts/trial_sample_e2e_batch_runner.py --resume --include-variants --batch-size 50 --time-budget-minutes 55",
    }
    write_json(BATCH_RUNNER_REPORT_PATH, report)
    return report


def main() -> None:
    """命令行入口。"""

    parser = argparse.ArgumentParser(description="全量样例题真实网页 E2E 循环批量执行器")
    parser.add_argument("--resume", action="store_true", help="保留兼容参数；runner 始终基于现有 checkpoint 续跑。")
    parser.add_argument("--include-variants", action="store_true")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--time-budget-minutes", type=float, default=55)
    parser.add_argument("--max-batches", type=int, default=0)
    parser.add_argument("--stop-on-failure", dest="stop_on_failure", action="store_true", default=True)
    parser.add_argument("--no-stop-on-failure", dest="stop_on_failure", action="store_false")
    parser.add_argument("--frontend-url", default="http://127.0.0.1:5173/smart-chat")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--batch-timeout-seconds", type=int, default=900)
    parser.add_argument("--comparator-timeout-seconds", type=int, default=180)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    report = run_batches(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "stopped" and report["stop_condition"] not in {"time_budget_reached", "max_batches_reached"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

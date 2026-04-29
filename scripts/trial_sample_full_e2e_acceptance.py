from __future__ import annotations

import argparse
import subprocess
import sys
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
    LEDGER_PATH,
    now_iso,
    read_json,
    write_json,
    write_markdown,
)


def _run_step(name: str, command: list[str], *, allow_failure: bool = False) -> dict[str, Any]:
    """执行子脚本并记录结果。

    参数：
        name: 步骤名称；
        command: 命令数组；
        allow_failure: 是否允许失败后继续汇总报告。
    返回值：
        步骤执行摘要。
    """
    started = now_iso()
    process = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True)  # noqa: S603
    result = {
        "name": name,
        "command": command,
        "started_at": started,
        "finished_at": now_iso(),
        "returncode": process.returncode,
        "stdout": process.stdout[-4000:],
        "stderr": process.stderr[-4000:],
        "success": process.returncode == 0,
    }
    if process.returncode != 0 and not allow_failure:
        raise RuntimeError(f"{name} failed: {process.stderr or process.stdout}")
    return result


def _write_frontend_doc(frontend_report: dict) -> None:
    """输出真实网页 E2E 报告文档。"""
    lines = [
        f"- 报告状态：{frontend_report.get('status')}",
        f"- 前端地址：`{frontend_report.get('frontend_url')}`",
        f"- 后端地址：`{frontend_report.get('backend_url')}`",
        f"- 全量计划用例：{frontend_report.get('planned_case_count', frontend_report.get('total_cases', 0))}",
        f"- 本次应执行用例：{frontend_report.get('total_cases', 0)}",
        f"- 已执行用例：{frontend_report.get('executed', 0)}",
    ]
    if frontend_report.get("status") == "blocked":
        lines.extend(
            [
                "",
                "## 阻塞说明",
                f"- 停止条件：{frontend_report.get('stop_condition')}",
                f"- 信息：{frontend_report.get('message') or frontend_report.get('error')}",
                f"- 安装命令：`{frontend_report.get('install_command', '')}`",
            ]
        )
    lines.extend(
        [
            "",
            "## 验收边界",
            "- 本脚本只从真实 `/smart-chat` 页面输入问题和读取 DOM 展示内容。",
            "- 不调用 QA service 代替前端验收。",
            "- 每道题的 DOM 文本、表格、追问和错误会写入 JSON 报告。",
        ]
    )
    write_markdown(DOCS_DIR / "TRIAL_SAMPLE_FRONTEND_E2E_EVAL.md", "TRIAL_SAMPLE_FRONTEND_E2E_EVAL", lines)


def _write_full_doc(report: dict) -> None:
    """输出最终验收总报告文档。"""
    ledger = report.get("ledger") or {}
    expected = report.get("expected") or {}
    frontend = report.get("frontend") or {}
    compare = report.get("compare") or {}
    lines = [
        "## 总览",
        f"- 样例题来源：`{ledger.get('question_file')}`",
        f"- 样例题总数：{ledger.get('total_questions')}",
        f"- 业务域分布：`{ledger.get('domain_distribution')}`",
        f"- 变体总数：{ledger.get('variant_total')}",
        f"- 标准答案状态分布：`{expected.get('status_distribution')}`",
        f"- 前端 E2E 状态：{frontend.get('status')}",
        f"- 是否限制批量执行：{frontend.get('is_limited_run')}",
        f"- 全量计划用例：{frontend.get('planned_case_count', frontend.get('total_cases', 0))}",
        f"- 前端 E2E 执行数：{frontend.get('executed', 0)} / {frontend.get('total_cases', 0)}",
        f"- 比对结果：`{compare.get('summary')}`",
        "",
        "## 数据源口径",
        "- 物流标准答案以 `logistics_ai` 中间库表时间和数据为准。",
        "- 用户提供的 23-25 物流 zip、2026 物流 zip 和 BOM zip 均记录在标准答案报告中，用于源文件核验和差异说明。",
        "- BOM 标准答案来自真实标准化 BOM 材料数据。",
        "",
        "## 执行步骤",
    ]
    for step in report.get("steps", []):
        lines.append(f"- {step['name']}: returncode={step['returncode']} success={step['success']}")
    if frontend.get("status") == "blocked":
        lines.extend(
            [
                "",
                "## 当前阻塞",
                f"- 停止条件：{frontend.get('stop_condition')}",
                f"- 说明：{frontend.get('message') or frontend.get('error')}",
                "- 已完成台账解析和标准答案构建，但未伪造网页 E2E 结果。",
            ]
        )
    failed = read_json(FAILED_CASES_PATH, default=[])
    lines.extend(["", "## 失败/待复核样例"])
    for item in failed[:80]:
        lines.append(f"- {item.get('case_id')}：{item.get('question')}；原因：{'; '.join(item.get('reasons') or [])}")
    write_markdown(DOCS_DIR / "TRIAL_SAMPLE_FULL_E2E_ACCEPTANCE.md", "TRIAL_SAMPLE_FULL_E2E_ACCEPTANCE", lines)


def main() -> None:
    """统一编排入口。"""
    parser = argparse.ArgumentParser(description="全量样例题真实网页端到端验收编排")
    parser.add_argument("--question-file", type=Path, default=None)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--only-failed", action="store_true")
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--include-variants", action="store_true", default=True)
    parser.add_argument("--frontend-url", default="http://127.0.0.1:5173/smart-chat")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000/api/v1")
    args = parser.parse_args()

    python = sys.executable
    steps: list[dict[str, Any]] = []
    ledger_cmd = [python, "scripts/trial_sample_question_ledger.py"]
    if args.question_file:
        ledger_cmd += ["--question-file", str(args.question_file)]
    steps.append(_run_step("ledger", ledger_cmd))
    steps.append(_run_step("expected_answers", [python, "scripts/trial_sample_expected_answer_builder.py"]))
    e2e_cmd = [
        python,
        "scripts/trial_sample_frontend_e2e_eval.py",
        "--frontend-url",
        args.frontend_url,
        "--backend-url",
        args.backend_url,
        "--batch-size",
        str(args.batch_size),
    ]
    if args.resume:
        e2e_cmd.append("--resume")
    if args.only_failed:
        e2e_cmd.append("--only-failed")
    if args.include_variants:
        e2e_cmd.append("--include-variants")
    if args.max_cases:
        e2e_cmd += ["--max-cases", str(args.max_cases)]
    steps.append(_run_step("frontend_e2e", e2e_cmd, allow_failure=True))
    frontend_report = read_json(FRONTEND_RESULTS_PATH, default={})
    _write_frontend_doc(frontend_report)
    if frontend_report.get("status") != "blocked":
        steps.append(_run_step("answer_compare", [python, "scripts/trial_sample_answer_comparator.py"]))
    else:
        write_json(COMPARE_REPORT_PATH, {"generated_at": now_iso(), "status": "blocked", "summary": {}})
        write_json(FAILED_CASES_PATH, [])
    write_json(FIXED_CASES_PATH, [])

    report = {
        "generated_at": now_iso(),
        "status": "blocked"
        if frontend_report.get("status") == "blocked"
        else ("partial" if frontend_report.get("is_limited_run") else "completed"),
        "ledger": read_json(LEDGER_PATH, default={}),
        "expected": read_json(EXPECTED_PATH, default={}),
        "frontend": frontend_report,
        "compare": read_json(COMPARE_REPORT_PATH, default={}),
        "steps": steps,
        "fixed_cases": [],
    }
    write_json(FULL_ACCEPTANCE_REPORT_PATH, report)
    _write_full_doc(report)
    print(f"trial_sample_full_e2e_acceptance_report written: {FULL_ACCEPTANCE_REPORT_PATH}")
    print(f"status={report['status']}")
    if report["status"] == "blocked":
        raise SystemExit(2)


if __name__ == "__main__":
    main()

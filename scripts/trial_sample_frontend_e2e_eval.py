from __future__ import annotations

import argparse
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

from trial_sample_eval_common import (
    FAILED_CASES_PATH,
    FRONTEND_RESULTS_PATH,
    LEDGER_PATH,
    PROJECT_ROOT,
    SCREENSHOT_DIR,
    sanitize_filename,
    now_iso,
    read_json,
    write_json,
)


LOG_DIR = PROJECT_ROOT / "tmp" / "trial_sample_eval" / "logs"


def _open_service_log(name: str):
    """打开服务日志文件，避免长跑时将后端/前端业务日志刷满终端。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return (LOG_DIR / name).open("a", encoding="utf-8")


def _http_ok(url: str, timeout: float = 3.0) -> bool:
    """检查服务 URL 是否可访问。"""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
            return 200 <= response.status < 500
    except (urllib.error.URLError, TimeoutError):
        return False


def _wait_until(url: str, *, timeout_seconds: int) -> bool:
    """等待服务启动。"""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _http_ok(url):
            return True
        time.sleep(1)
    return False


def _start_backend(backend_url: str) -> subprocess.Popen | None:
    """必要时启动真实后端服务。"""
    health_url = backend_url.rstrip("/") + "/health"
    if _http_ok(health_url):
        return None
    python_bin = PROJECT_ROOT / "backend" / ".venv" / "bin" / "python"
    cmd = [
        str(python_bin if python_bin.exists() else "python"),
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]
    log_file = _open_service_log("backend_uvicorn.log")
    return subprocess.Popen(cmd, cwd=PROJECT_ROOT, stdout=log_file, stderr=subprocess.STDOUT)  # noqa: S603


def _start_frontend(frontend_url: str) -> subprocess.Popen | None:
    """必要时启动真实前端服务。"""
    if _http_ok(frontend_url):
        return None
    cmd = ["npm", "run", "dev", "--prefix", "frontend", "--", "--host", "127.0.0.1", "--port", "5173"]
    log_file = _open_service_log("frontend_vite.log")
    return subprocess.Popen(cmd, cwd=PROJECT_ROOT, stdout=log_file, stderr=subprocess.STDOUT)  # noqa: S603,S607


def _build_cases(ledger: dict, *, include_variants: bool, only_failed: list[str] | None) -> tuple[list[dict[str, Any]], int]:
    """按台账生成原题和变体的网页输入用例。"""
    all_cases: list[dict[str, Any]] = []
    failed_set = set(only_failed or [])
    for item in ledger.get("items", []):
        original_case_id = f"{item['id']}:original"
        all_cases.append(
            {
                "case_id": original_case_id,
                "question_id": item["id"],
                "variant_index": 0,
                "question": item["question"],
                "domain": item["domain"],
                "question_type": item["question_type"],
                "is_variant": False,
            }
        )
        if include_variants:
            for index, variant in enumerate(item.get("variants", []), start=1):
                case_id = f"{item['id']}:v{index}"
                all_cases.append(
                    {
                        "case_id": case_id,
                        "question_id": item["id"],
                        "variant_index": index,
                        "question": variant,
                        "domain": item["domain"],
                        "question_type": item["question_type"],
                        "is_variant": True,
                    }
                )
    planned_count = len(all_cases)
    if failed_set:
        cases = [
            case
            for case in all_cases
            if case["case_id"] in failed_set or case["question_id"] in failed_set
        ]
    else:
        cases = all_cases
    return cases, planned_count


def _extract_table_rows(page) -> list[dict[str, Any]]:
    """从 Element Plus 表格 DOM 中读取表头和行文本。"""
    table = page.locator('[data-testid="result-table"]').last
    if table.count() == 0:
        return []
    headers = [value.strip() for value in table.locator(".el-table__header-wrapper th .cell").all_inner_texts()]
    body_rows = table.locator(".el-table__body-wrapper tbody tr")
    rows: list[dict[str, Any]] = []
    for index in range(body_rows.count()):
        cells = [value.strip() for value in body_rows.nth(index).locator("td .cell").all_inner_texts()]
        if cells:
            rows.append({headers[i] if i < len(headers) else f"列{i + 1}": value for i, value in enumerate(cells)})
    return rows


def _fill_question_input(page, question: str) -> None:
    """兼容 Element Plus textarea 属性透传位置，填入业务问题。"""
    selectors = [
        '[data-testid="question-input"] textarea',
        'textarea[data-testid="question-input"]',
        '[data-testid="question-input"] input',
        'input[data-testid="question-input"]',
        'textarea[placeholder="输入业务问题"]',
    ]
    for selector in selectors:
        locator = page.locator(selector).first
        if locator.count() > 0:
            locator.fill(question, timeout=5000)
            return
    raise RuntimeError("未找到可输入的问题文本框。")


def _run_browser_cases(args: argparse.Namespace, cases: list[dict[str, Any]], existing: dict[str, Any]) -> dict[str, Any]:
    """使用 Playwright 逐题驱动真实网页。"""
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "blocked",
            "stop_condition": "browser_automation_unavailable",
            "error": str(exc),
            "message": "当前 Python 环境缺少 playwright，无法执行真实网页自动化。",
            "install_command": "backend/.venv/bin/python -m pip install playwright && backend/.venv/bin/python -m playwright install chromium",
            "results": existing.get("results", []),
        }

    selected_case_ids = {case["case_id"] for case in cases}
    planned_case_count = int(getattr(args, "planned_case_count", len(cases)) or len(cases))
    current_question_by_id = {case["case_id"]: case.get("question") for case in cases}
    existing_by_id = {
        item["case_id"]: item
        for item in existing.get("results", [])
        if item.get("case_id")
        and not (args.only_failed and item.get("case_id") in selected_case_ids)
        # 变体生成规则可能修复；已有结果的问题文本不一致时必须重跑，避免复用旧错误变体。
        and (item.get("case_id") not in current_question_by_id or item.get("question") == current_question_by_id[item.get("case_id")])
    }
    results: list[dict[str, Any]] = list(existing_by_id.values())
    pending = [case for case in cases if not args.resume or case["case_id"] not in existing_by_id]
    # max-cases 表示本次从 checkpoint 后最多执行多少条，而不是截断全量计划的前 N 条；
    # 这样长跑可以稳定按批续跑，不会反复选中已经完成的前置用例。
    if args.max_cases:
        pending = pending[: args.max_cases]
    batch_summaries = list(existing.get("batch_summaries", [])) if args.resume and not args.only_failed else []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=args.headless)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(args.frontend_url, wait_until="domcontentloaded", timeout=args.page_timeout_ms)
        page.locator('[data-testid="business-chat-page"]').wait_for(timeout=args.page_timeout_ms)
        for offset, case in enumerate(pending, start=1):
            started = time.time()
            screenshot_path = ""
            status = "pass"
            error = ""
            dom_text = ""
            title = ""
            answer = ""
            table_rows: list[dict[str, Any]] = []
            follow_ups: list[str] = []
            suggestions: list[str] = []
            try:
                page.locator('[data-testid="nav-new-chat"]').click(timeout=5000)
                _fill_question_input(page, case["question"])
                page.locator('[data-testid="send-button"]').click(timeout=5000)
                page.locator('[data-testid="chat-message-assistant"]').last.wait_for(timeout=args.answer_timeout_ms)
                assistant = page.locator('[data-testid="chat-message-assistant"]').last
                assistant.locator('[data-testid="message-loading"]').wait_for(state="detached", timeout=args.answer_timeout_ms)
                try:
                    assistant.locator('[data-testid="assistant-result"]').wait_for(timeout=3000)
                except PlaywrightTimeoutError:
                    pass
                dom_text = assistant.inner_text(timeout=5000)
                title = assistant.locator('[data-testid="result-title"]').last.inner_text(timeout=1000) if assistant.locator('[data-testid="result-title"]').count() else ""
                answer = assistant.locator('[data-testid="result-answer"]').last.inner_text(timeout=1000) if assistant.locator('[data-testid="result-answer"]').count() else ""
                table_rows = _extract_table_rows(page)
                follow_ups = assistant.locator('[data-testid="result-follow-ups"] button').all_inner_texts()
                suggestions = assistant.locator('[data-testid="result-suggestions"] span').all_inner_texts()
                if assistant.locator('[data-testid="message-error"]').count():
                    status = "error"
                    error = assistant.locator('[data-testid="message-error"]').last.inner_text()
            except Exception as exc:  # noqa: BLE001
                status = "failed"
                error = str(exc)
                filename = sanitize_filename(case["case_id"]) + ".png"
                screenshot_path = str(SCREENSHOT_DIR / filename)
                try:
                    page.screenshot(path=screenshot_path, full_page=True)
                except Exception:  # noqa: BLE001
                    screenshot_path = ""
            result = {
                **case,
                "status": status,
                "error": error,
                "title": title,
                "answer": answer,
                "dom_text": dom_text,
                "table_rows": table_rows,
                "follow_ups": follow_ups,
                "suggestions": suggestions,
                "screenshot_path": screenshot_path,
                "elapsed_ms": int((time.time() - started) * 1000),
                "executed_at": now_iso(),
            }
            results.append(result)
            # 真实网页长跑单题耗时可能达到数十秒，逐题落盘可避免中断后丢失进度。
            write_json(
                args.output,
                {
                    "generated_at": now_iso(),
                    "status": "running",
                    "frontend_url": args.frontend_url,
                    "backend_url": args.backend_url,
                    "total_cases": planned_case_count,
                    "selected_case_count": len(cases),
                    "executed": len(results),
                    "pending": max(planned_case_count - len(results), 0),
                    "selected_pending": max(len(cases) - len([item for item in results if item.get("case_id") in selected_case_ids]), 0),
                    "last_case_id": result.get("case_id"),
                    "last_case_status": result.get("status"),
                    "batch_summaries": batch_summaries,
                    "result_status_distribution": dict(Counter(item.get("status") for item in results)),
                    "results": results,
                },
            )
            if args.progress_every_case or result.get("status") != "pass":
                print(
                    f"[trial-e2e] case={result.get('case_id')} status={result.get('status')} "
                    f"executed={len(results)}/{len(cases)} elapsed_ms={result.get('elapsed_ms')}",
                    flush=True,
                )
            if args.batch_size and offset % args.batch_size == 0:
                recent = results[-args.batch_size :]
                summary = {
                    "batch_id": len(batch_summaries) + 1,
                    "finished_at": now_iso(),
                    "executed_in_batch": len(recent),
                    "status_distribution": dict(Counter(item.get("status") for item in recent)),
                    "first_case_id": recent[0].get("case_id") if recent else "",
                    "last_case_id": recent[-1].get("case_id") if recent else "",
                }
                batch_summaries.append(summary)
                write_json(
                    args.output,
                    {
                        "generated_at": now_iso(),
                        "status": "running",
                    "frontend_url": args.frontend_url,
                    "backend_url": args.backend_url,
                    "total_cases": planned_case_count,
                    "selected_case_count": len(cases),
                    "executed": len(results),
                    "pending": max(planned_case_count - len(results), 0),
                    "selected_pending": max(len(cases) - len([item for item in results if item.get("case_id") in selected_case_ids]), 0),
                    "batch_summaries": batch_summaries,
                        "result_status_distribution": dict(Counter(item.get("status") for item in results)),
                        "results": results,
                    },
                )
                print(
                    f"[trial-e2e] batch={summary['batch_id']} executed={len(results)}/{len(cases)} "
                    f"status={summary['status_distribution']}",
                    flush=True,
                )
        browser.close()
    result_counter = Counter(item.get("status") for item in results)
    return {
        "generated_at": now_iso(),
        "status": "completed",
        "frontend_url": args.frontend_url,
        "backend_url": args.backend_url,
        "total_cases": planned_case_count,
        "selected_case_count": len(cases),
        "is_limited_run": bool(args.max_cases),
        "max_cases": args.max_cases,
        "executed": len(results),
        "pending": max(planned_case_count - len(results), 0),
        "selected_pending": max(len(cases) - len([item for item in results if item.get("case_id") in selected_case_ids]), 0),
        "only_failed": args.only_failed,
        "batch_summaries": batch_summaries,
        "result_status_distribution": dict(result_counter),
        "results": results,
    }


def _load_failed_ids() -> list[str]:
    """读取上一次比对失败清单，供 only-failed 精准复跑。"""
    failed = read_json(FAILED_CASES_PATH, default=[])
    ids: list[str] = []
    for item in failed or []:
        case_id = item.get("case_id")
        question_id = item.get("question_id")
        if case_id:
            ids.append(str(case_id))
        elif question_id:
            ids.append(str(question_id))
    return ids


def _backup_existing_results(output_path: Path) -> None:
    """在续跑写入前备份既有结果文件。

    参数：
        output_path: 前端 E2E 结果文件路径。
    返回值：
        无。

    重要业务逻辑：
        长跑验收依赖 checkpoint 断点续跑。续跑过程中一旦参数误用或进程异常，
        不能覆盖已经通过的真实网页结果，因此每次 resume 写入前先保留一份备份。
    """
    if not output_path.exists():
        return
    backup_path = output_path.with_name(f"{output_path.stem}.backup_{now_iso().replace(':', '')}{output_path.suffix}")
    shutil.copy2(output_path, backup_path)


def _write_empty_only_failed_payload(args: argparse.Namespace, existing: dict[str, Any], planned_case_count: int) -> None:
    """失败清单为空时快速结束 only-failed，不启动浏览器、不覆盖 checkpoint。

    参数：
        args: 命令行参数。
        existing: 已有前端 E2E checkpoint。
        planned_case_count: 原题加变体的完整计划量。
    返回值：
        无。
    """
    payload = dict(existing or {})
    payload.update(
        {
            "generated_at": now_iso(),
            "status": "completed",
            "frontend_url": args.frontend_url,
            "backend_url": args.backend_url,
            "total_cases": planned_case_count,
            "selected_case_count": 0,
            "selected_pending": 0,
            "only_failed": True,
            "empty_failed_cases": True,
            "message": "failed_cases.json 为空，only-failed 无需启动真实浏览器复跑。",
        }
    )
    write_json(args.output, payload)
    print(f"frontend_e2e_results written: {args.output}")
    print(f"status=completed executed={payload.get('executed', len(payload.get('results', [])))} total={planned_case_count}")


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="真实网页端到端样例题验收")
    parser.add_argument("--ledger", type=Path, default=LEDGER_PATH)
    parser.add_argument("--frontend-url", default="http://127.0.0.1:5173/smart-chat")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--only-failed", action="store_true")
    parser.add_argument("--include-variants", action="store_true")
    parser.add_argument("--headless", dest="headless", action="store_true", default=True)
    parser.add_argument("--headed", dest="headless", action="store_false")
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--page-timeout-ms", type=int, default=30000)
    parser.add_argument("--answer-timeout-ms", type=int, default=45000)
    parser.add_argument("--output", type=Path, default=FRONTEND_RESULTS_PATH)
    parser.add_argument("--progress-every-case", action="store_true")
    args = parser.parse_args()

    ledger = read_json(args.ledger)
    if not ledger:
        raise FileNotFoundError(f"缺少样例题台账：{args.ledger}")
    existing = read_json(args.output, default={}) if args.resume else {}
    failed_ids = _load_failed_ids() if args.only_failed else None
    cases, planned_case_count = _build_cases(
        ledger,
        include_variants=args.include_variants,
        only_failed=failed_ids,
    )
    # 写入 Namespace 供长跑 checkpoint 使用：total_cases 始终代表完整计划量。
    args.planned_case_count = planned_case_count
    if args.only_failed and not failed_ids:
        _write_empty_only_failed_payload(args, existing, planned_case_count)
        return
    if args.resume:
        _backup_existing_results(args.output)

    backend_process = _start_backend(args.backend_url)
    frontend_process = _start_frontend(args.frontend_url)
    try:
        backend_ready = _wait_until(args.backend_url.rstrip("/") + "/health", timeout_seconds=60)
        frontend_ready = _wait_until(args.frontend_url, timeout_seconds=90)
        if not backend_ready or not frontend_ready:
            payload = {
                "generated_at": now_iso(),
                "status": "blocked",
                "stop_condition": "frontend_or_backend_unavailable",
                "backend_ready": backend_ready,
                "frontend_ready": frontend_ready,
                "frontend_url": args.frontend_url,
                "backend_url": args.backend_url,
                "planned_case_count": planned_case_count,
                "is_limited_run": bool(args.max_cases),
                "max_cases": args.max_cases,
                "results": existing.get("results", []),
            }
        else:
            payload = _run_browser_cases(args, cases, existing)
            payload["planned_case_count"] = planned_case_count
        write_json(args.output, payload)
        print(f"frontend_e2e_results written: {args.output}")
        print(f"status={payload.get('status')} executed={payload.get('executed', 0)} total={payload.get('total_cases', len(cases))}")
        if payload.get("status") == "blocked":
            raise SystemExit(2)
    finally:
        for process in (frontend_process, backend_process):
            if process is not None and process.poll() is None:
                process.terminate()


if __name__ == "__main__":
    main()

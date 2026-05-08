from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 JSONL 文件。

    参数：path 为输入文件路径。
    返回值：逐行解析后的字典列表。
    业务逻辑：空行跳过，确保 E2E 用例来源可复查。
    """
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    """追加写入一条 JSONL 记录。

    参数：path 为输出路径，row 为记录。
    返回值：无。
    业务逻辑：逐题落盘，避免浏览器长跑中断后证据丢失。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def write_text(path: Path, text: str) -> None:
    """写入文本证据文件。

    参数：path 为输出路径，text 为 DOM/HTML 内容。
    返回值：无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def http_ok(url: str, timeout: float = 3.0) -> bool:
    """检查本地服务是否可访问。

    参数：url 为检查地址，timeout 为超时时间。
    返回值：可访问时 True，否则 False。
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            return 200 <= resp.status < 500
    except urllib.error.HTTPError as exc:
        # FastAPI 当前没有 /health 路由时会返回 404；只要服务进程已响应 HTTP，E2E 即可继续。
        return exc.code < 500
    except Exception:
        return False


def wait_until(url: str, timeout_seconds: int = 90) -> bool:
    """等待本地服务就绪。

    参数：url 为健康检查地址，timeout_seconds 为最大等待秒数。
    返回值：服务就绪 True，超时 False。
    """
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if http_ok(url):
            return True
        time.sleep(1)
    return False


def start_services(frontend_url: str, backend_url: str, no_start: bool, run_dir: Path) -> list[subprocess.Popen]:
    """按需启动后端和前端本地服务。

    参数：frontend_url、backend_url 为服务地址，no_start 控制是否只复用现有服务，run_dir 为日志目录。
    返回值：由本脚本启动的进程列表，调用方负责结束。
    业务逻辑：只启动本地开发服务，不修改数据库、不部署生产。
    """
    procs: list[subprocess.Popen] = []
    logs = run_dir / "service_logs"
    logs.mkdir(parents=True, exist_ok=True)
    if no_start:
        return procs
    if not http_ok(backend_url.rstrip("/") + "/health"):
        log = (logs / "backend_uvicorn.log").open("a", encoding="utf-8")
        procs.append(subprocess.Popen(["python", "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000"], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT))
    if not wait_until(backend_url.rstrip("/") + "/health", 90):
        raise RuntimeError("backend service not ready")
    if not http_ok(frontend_url):
        log = (logs / "frontend_vite.log").open("a", encoding="utf-8")
        procs.append(subprocess.Popen(["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"], cwd=ROOT / "frontend", stdout=log, stderr=subprocess.STDOUT))
    if not wait_until(frontend_url, 120):
        raise RuntimeError("frontend service not ready")
    return procs


def fill_question(page: Any, question: str) -> None:
    """在智能助手页面填入问题。

    参数：page 为 Playwright 页面对象，question 为用户问题。
    返回值：无。
    业务逻辑：兼容当前 Element Plus textarea 的多种 data-testid/placeholder 写法。
    """
    selectors = [
        '[data-testid="question-input"] textarea',
        'textarea[data-testid="question-input"]',
        '[data-testid="question-input"] input',
        'textarea[placeholder*="输入"]',
        'textarea',
    ]
    for selector in selectors:
        loc = page.locator(selector).first
        try:
            loc.wait_for(state="visible", timeout=8000)
            loc.fill(question, timeout=5000)
            return
        except Exception:
            # 页面首屏和路由切换存在异步加载，单个候选选择器不可见时继续尝试下一种写法。
            continue
    raise RuntimeError("未找到问题输入框")


def click_send(page: Any) -> None:
    """点击发送按钮。

    参数：page 为 Playwright 页面对象。
    返回值：无。
    """
    selectors = ['[data-testid="send-button"]', 'button:has-text("发送")', 'button:has-text("提问")']
    for selector in selectors:
        loc = page.locator(selector).first
        if loc.count() > 0:
            loc.click(timeout=5000)
            return
    raise RuntimeError("未找到发送按钮")


def extract_tables(page: Any) -> list[dict[str, Any]]:
    """提取页面表格 DOM。

    参数：page 为 Playwright 页面对象。
    返回值：表格行列表。
    业务逻辑：优先读取 Element Plus 表格，同时兼容普通 table。
    """
    rows: list[dict[str, Any]] = []
    tables = page.locator('[data-testid="result-table"], .el-table, table')
    if tables.count() == 0:
        return rows
    table = tables.last
    headers = [x.strip() for x in table.locator('th .cell, th').all_inner_texts() if x.strip()]
    body_rows = table.locator('tbody tr')
    for i in range(body_rows.count()):
        cells = [x.strip() for x in body_rows.nth(i).locator('td .cell, td').all_inner_texts()]
        if cells:
            rows.append({headers[j] if j < len(headers) else f"列{j+1}": cell for j, cell in enumerate(cells)})
    return rows


def classify_status(text: str, api_errors: list[str]) -> str:
    """根据页面文本和网络错误判断实际状态。

    参数：text 为助手可见文本，api_errors 为接口错误列表。
    返回值：success/clarification/no_answer/error。
    """
    if api_errors or any(x in text for x in ["请求失败", "服务器错误", "系统错误", "Traceback"]):
        return "error"
    if any(x in text for x in ["请补充", "请明确", "需要您补充", "追问"]):
        return "clarification"
    if any(x in text for x in ["无法回答", "暂不支持", "没有找到", "无数据", "未查询到"]):
        return "no_answer"
    return "success" if text.strip() else "error"


def run_case(page: Any, case: dict[str, Any], run_dir: Path, index: int, timeout_ms: int) -> dict[str, Any]:
    """执行单条浏览器问题验证。

    参数：page 为 Playwright 页面对象，case 为 expected 记录，run_dir 为运行目录，index 为序号，timeout_ms 为等待答案超时。
    返回值：actual_answers.jsonl 的一条记录。
    """
    console_errors: list[str] = []
    api_errors: list[str] = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type in {"error", "warning"} else None)
    page.on("response", lambda resp: api_errors.append(f"{resp.status} {resp.url}") if (resp.status >= 400 and "/api/" in resp.url) else None)
    qid = case["question_id"]
    html_path = run_dir / "page_html" / f"{index:04d}_{qid}.html"
    shot_path = run_dir / "screenshots" / f"{index:04d}_{qid}.png"
    started = time.time()
    visible_text = ""
    table_rows: list[dict[str, Any]] = []
    error = ""
    try:
        if page.locator('[data-testid="nav-new-chat"]').count() > 0:
            page.locator('[data-testid="nav-new-chat"]').click(timeout=3000)
        fill_question(page, case["question"])
        click_send(page)
        page.locator('[data-testid="chat-message-assistant"], .message-assistant, .assistant-message').last.wait_for(timeout=timeout_ms)
        assistant = page.locator('[data-testid="chat-message-assistant"], .message-assistant, .assistant-message').last
        try:
            assistant.locator('[data-testid="message-loading"], .is-loading').wait_for(state="detached", timeout=timeout_ms)
        except Exception:
            pass
        time.sleep(0.5)
        visible_text = assistant.inner_text(timeout=5000)
        table_rows = extract_tables(page)
    except Exception as exc:
        error = str(exc)
    html = page.content()
    write_text(html_path, html)
    try:
        page.screenshot(path=str(shot_path), full_page=True)
    except Exception as exc:
        error = error or f"screenshot failed: {exc}"
    status = "error" if error else classify_status(visible_text, api_errors)
    return {
        "question_id": qid,
        "question": case["question"],
        "expected_status": case.get("status"),
        "expected_capability": case.get("capability"),
        "status": status,
        "visible_answer_text": visible_text,
        "table_text": "\n".join(" | ".join(map(str, r.values())) for r in table_rows),
        "table_rows": table_rows,
        "screenshot_path": str(shot_path),
        "html_path": str(html_path),
        "console_errors": console_errors[-20:],
        "api_errors": api_errors[-20:],
        "error": error,
        "elapsed_ms": int((time.time() - started) * 1000),
    }


def main() -> int:
    """脚本入口。

    参数：无，使用命令行参数。
    返回值：进程退出码。
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument(
        "--statuses",
        default="expected",
        help="要执行的 expected status，逗号分隔；传 all 表示执行全部样例题。",
    )
    parser.add_argument("--frontend-url", default="http://127.0.0.1:5173/smart-chat")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    parser.add_argument("--no-start-services", action="store_true")
    parser.add_argument("--timeout-ms", type=int, default=45000)
    args = parser.parse_args()
    run_dir = ROOT / "ai" / "eval" / "runs" / args.run_id
    actual_path = run_dir / "actual_answers.jsonl"
    ui_path = run_dir / "ui_review_result.jsonl"
    for p in [actual_path, ui_path]:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("", encoding="utf-8")
    all_cases = read_jsonl(ROOT / "ai" / "eval" / "expected_answers" / "expected_answers.jsonl")
    if args.statuses.strip().lower() != "all":
        allowed_statuses = {item.strip() for item in args.statuses.split(",") if item.strip()}
        all_cases = [r for r in all_cases if r.get("status") in allowed_statuses]
    end = None if args.limit <= 0 else args.offset + args.limit
    cases = all_cases[args.offset:end]
    procs: list[subprocess.Popen] = []
    try:
        procs = start_services(args.frontend_url, args.backend_url, args.no_start_services, run_dir)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(args.frontend_url, wait_until="domcontentloaded", timeout=args.timeout_ms)
            for i, case in enumerate(cases, 1):
                row = run_case(page, case, run_dir, i, args.timeout_ms)
                append_jsonl(actual_path, row)
                append_jsonl(ui_path, {"question_id": row["question_id"], "status": row["status"], "screenshot_path": row["screenshot_path"], "html_path": row["html_path"], "console_errors": row["console_errors"], "api_errors": row["api_errors"]})
            browser.close()
    except Exception as exc:
        append_jsonl(actual_path, {"status": "BROWSER_TEST_ERROR", "error": str(exc)})
        raise
    finally:
        for proc in procs:
            proc.terminate()
    print(f"actual written: {actual_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from phase2_browser_e2e import ROOT, append_jsonl, run_case, start_services


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 JSONL 文件。

    参数：path 为文件路径。
    返回值：字典列表。
    """
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_variants(expected_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """生成少量鲁棒性问法变体。

    参数：expected_rows 为标准答案列表。
    返回值：变体用例列表。
    业务逻辑：不按完整问题硬编码答案，只复用同一 question_id 的 trace 作为期望链路，覆盖年份、指标、表格等常见表达变化。
    """
    by_id = {row["question_id"]: row for row in expected_rows}
    specs = [
        ("Q0013", "华东区域历史物流一共发运了多少件？"),
        ("Q0020", "2023到2025年江苏的物流总运费是多少？"),
        ("Q0026", "浙江历史发运总费用是多少元？"),
        ("Q0028", "历史台账里运输方式为公路的记录有多少条？"),
        ("Q0038", "24年一季度物流发运车辆数是多少？"),
        ("Q0043", "请把华东各运输方式平均元每瓦按从低到高列出来"),
        ("Q0059", "江苏省客户按总费用排前五，并列出总费用和总瓦数"),
        ("Q0067", "2023–2025 年各月物流总费用是多少？"),
    ]
    cases: list[dict[str, Any]] = []
    for index, (qid, question) in enumerate(specs, 1):
        base = by_id.get(qid)
        if not base:
            continue
        case = dict(base)
        case["question"] = question
        case["variant_id"] = f"R{index:03d}"
        cases.append(case)
    return cases


def answer_value_visible(row: dict[str, Any]) -> bool:
    """判断页面文本是否包含标准答案的关键数值。

    参数：row 为浏览器实际结果，内部包含 expected answer。
    返回值：关键数值可在页面文本中找到时 True。
    业务逻辑：鲁棒性题不能只看 success 状态，还要确认数值答案没有答偏；允许金额按元四舍五入展示。
    """

    answer = row.get("answer") or {}
    value = answer.get("value") if isinstance(answer, dict) else None
    if value is None:
        return bool(row.get("visible_answer_text"))
    text = re.sub(r"[,，\s]", "", row.get("visible_answer_text") or "")
    candidates = {str(value).replace(".0", "")}
    try:
        number = float(value)
        candidates.add(str(int(round(number))))
    except Exception:
        pass
    return any(candidate and candidate in text for candidate in candidates)


def main() -> int:
    """脚本入口。

    参数：无，读取命令行参数。
    返回值：退出码。
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--frontend-url", default="http://127.0.0.1:5173/smart-chat")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout-ms", type=int, default=45000)
    args = parser.parse_args()
    run_dir = ROOT / "ai" / "eval" / "runs" / args.run_id
    output = run_dir / "robustness_result.jsonl"
    output.write_text("", encoding="utf-8")
    expected = [r for r in read_jsonl(ROOT / "ai" / "eval" / "expected_answers" / "expected_answers.jsonl") if r.get("status") == "expected"]
    cases = build_variants(expected)
    procs: list[subprocess.Popen] = []
    try:
        procs = start_services(args.frontend_url, args.backend_url, False, run_dir)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(args.frontend_url, wait_until="domcontentloaded", timeout=args.timeout_ms)
            for index, case in enumerate(cases, 1):
                row = run_case(page, case, run_dir, 9000 + index, args.timeout_ms)
                row["variant_id"] = case.get("variant_id")
                row["answer"] = case.get("answer")
                row["robustness_passed"] = row.get("status") == "success" and answer_value_visible(row)
                append_jsonl(output, row)
            browser.close()
    finally:
        for proc in procs:
            proc.terminate()
    print(f"robustness written: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

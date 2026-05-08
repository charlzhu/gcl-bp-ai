from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 JSONL。

    参数：path 为文件路径。
    返回值：字典列表。
    """
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """写 JSONL。

    参数：path 为输出路径，rows 为记录列表。
    返回值：无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in rows) + ("\n" if rows else ""), encoding="utf-8")


def number_tokens(text: str) -> list[float]:
    """从文本中提取数字。

    参数：text 为待解析文本。
    返回值：数字列表。
    业务逻辑：用于粗粒度审计页面答案是否含有标准答案关键数值，不做严格字符串相等。
    """
    vals = []
    for token in re.findall(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?", text or ""):
        try:
            vals.append(float(token.replace(",", "")))
        except ValueError:
            pass
    return vals


def expected_numbers(value: Any) -> list[float]:
    """递归提取 expected 中的重要数字。

    参数：value 为 expected answer 对象。
    返回值：数字列表。
    """
    nums: list[float] = []
    if isinstance(value, dict):
        for k, v in value.items():
            if k in {"value", "total_fee", "shipment_watt", "vehicle_count", "avg_yuan_per_watt", "avg_unit_price_per_vehicle"} and isinstance(v, (int, float)):
                nums.append(float(v))
            else:
                nums.extend(expected_numbers(v))
    elif isinstance(value, list):
        for item in value[:10]:
            nums.extend(expected_numbers(item))
    return nums


def close_enough(expected: float, actuals: list[float]) -> bool:
    """判断 expected 数字是否在页面数字中出现。

    参数：expected 为标准数字，actuals 为页面数字列表。
    返回值：匹配则 True。
    业务逻辑：兼容四舍五入、万元/MW 等展示差异，设置相对误差和缩放因子检查。
    """
    if not actuals:
        return False
    scales = [1, 10000, 1 / 10000, 1000000, 1 / 1000000]
    for a in actuals:
        for scale in scales:
            target = expected * scale
            tol = max(1.0, abs(target) * 0.02)
            if math.isfinite(a) and abs(a - target) <= tol:
                return True
    return False


def compare_one(exp: dict[str, Any], act: dict[str, Any] | None) -> dict[str, Any]:
    """对比单题 expected 与 actual。

    参数：exp 为标准答案记录，act 为网页实际记录。
    返回值：对比结论。
    """
    if act is None:
        return {"question_id": exp["question_id"], "question": exp["question"], "compare_status": "MISSING_ACTUAL", "failure_type": "BROWSER_TEST_ERROR", "reason": "未采集到网页实际答案"}
    if act.get("status") in {"BROWSER_TEST_ERROR", "error"}:
        return {"question_id": exp["question_id"], "question": exp["question"], "compare_status": "FAIL", "failure_type": "FRONTEND_RENDER_ERROR", "reason": act.get("error") or ";".join(act.get("api_errors", [])), "actual_status": act.get("status"), "screenshot_path": act.get("screenshot_path")}
    text = (act.get("visible_answer_text") or "") + "\n" + (act.get("table_text") or "")
    if exp.get("capability") == "logistics_region_transport_avg_yuan_per_watt_sort":
        # 平均元/瓦题的 expected rows 同时保留 total_fee/shipment_watt 作为 trace 审计字段；
        # 页面当前只展示核心指标 avg_yuan_per_watt，所以对比时只校验核心指标，避免把未展示的审计字段误算为 FAIL。
        rows_for_metric = exp.get("answer", {}).get("rows") if isinstance(exp.get("answer"), dict) else []
        nums = [float(row["avg_yuan_per_watt"]) for row in rows_for_metric if isinstance(row, dict) and isinstance(row.get("avg_yuan_per_watt"), (int, float))]
    else:
        nums = expected_numbers(exp.get("answer"))
    actual_nums = number_tokens(text)
    matched = sum(1 for n in nums[:20] if close_enough(n, actual_nums))
    rows = exp.get("answer", {}).get("rows") if isinstance(exp.get("answer"), dict) else None
    if rows:
        key_texts = []
        for row in rows[:5]:
            if isinstance(row, dict):
                for k in ["year", "month", "customer", "transport_mode", "carrier", "material", "description"]:
                    if row.get(k) not in [None, ""]:
                        key_texts.append(str(row[k]))
        key_hits = sum(1 for k in key_texts[:20] if k in text)
        ok = (matched >= min(3, len(nums)) if nums else True) and (key_hits >= min(3, len(key_texts)) if key_texts else True)
    else:
        ok = matched >= max(1, min(3, len(nums))) if nums else bool(text.strip())
    return {
        "question_id": exp["question_id"],
        "question": exp["question"],
        "expected_status": exp.get("status"),
        "actual_status": act.get("status"),
        "compare_status": "PASS" if ok else "FAIL",
        "failure_type": "" if ok else "BACKEND_OR_NLU_OR_RENDER_MISMATCH",
        "reason": "关键数值/行匹配通过" if ok else f"expected 数字 {len(nums)} 个，命中 {matched} 个；页面文本长度 {len(text)}",
        "matched_numbers": matched,
        "expected_number_count": len(nums),
        "screenshot_path": act.get("screenshot_path"),
        "html_path": act.get("html_path"),
    }


def write_markdown(path: Path, title: str, rows: list[dict[str, Any]]) -> None:
    """写 Markdown 案例报告。

    参数：path 为输出路径，title 为标题，rows 为案例列表。
    返回值：无。
    """
    lines = [f"# {title}", ""]
    if not rows:
        lines.append("暂无。")
    for row in rows:
        lines += [f"## {row.get('question_id')}", "", f"- 问题：{row.get('question')}", f"- 结论：{row.get('compare_status')}", f"- 类型：{row.get('failure_type','')}", f"- 原因：{row.get('reason','')}", f"- 截图：{row.get('screenshot_path','')}", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    """脚本入口。

    参数：无，读取命令行。
    返回值：退出码。
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run_dir = ROOT / "ai" / "eval" / "runs" / args.run_id
    expected = [r for r in read_jsonl(ROOT / "ai" / "eval" / "expected_answers" / "expected_answers.jsonl") if r.get("status") == "expected"]
    actual_rows = read_jsonl(run_dir / "actual_answers.jsonl")
    actual_by_id = {r.get("question_id"): r for r in actual_rows if r.get("question_id")}
    # 只对已执行网页题进行对比，避免 limit 首轮把未执行题误判失败。
    executed_expected = [e for e in expected if e.get("question_id") in actual_by_id]
    results = [compare_one(e, actual_by_id.get(e.get("question_id"))) for e in executed_expected]
    write_jsonl(run_dir / "comparison_result.jsonl", results)
    failed = [r for r in results if r.get("compare_status") != "PASS"]
    counts = Counter(r.get("compare_status") for r in results)
    summary = ["# Phase 3 对比摘要", "", f"- 已对比题数：{len(results)}", f"- PASS：{counts.get('PASS',0)}", f"- FAIL：{counts.get('FAIL',0)}", f"- MISSING_ACTUAL：{counts.get('MISSING_ACTUAL',0)}", "", "## 失败类型", ""]
    for k, v in Counter(r.get("failure_type") for r in failed).items():
        summary.append(f"- {k}: {v}")
    (run_dir / "comparison_summary.md").write_text("\n".join(summary), encoding="utf-8")
    write_markdown(run_dir / "failed_cases.md", "失败案例", failed)
    write_markdown(run_dir / "no_answer_cases.md", "无答案案例", [])
    write_markdown(run_dir / "blocked_cases.md", "阻塞案例", [])
    print(f"comparison written: {run_dir / 'comparison_result.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

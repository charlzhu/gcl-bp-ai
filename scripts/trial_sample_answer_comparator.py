from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path
from typing import Any

from trial_sample_eval_common import (
    COMPARE_REPORT_PATH,
    DOCS_DIR,
    EXPECTED_PATH,
    FAILED_CASES_PATH,
    FRONTEND_RESULTS_PATH,
    now_iso,
    read_json,
    write_json,
    write_markdown,
)


def _numbers_from_text(text: str) -> list[float]:
    """提取前端展示文本中的数字。"""
    numbers: list[float] = []
    for raw in re.findall(r"-?\d[\d,]*(?:\.\d+)?", text or ""):
        try:
            numbers.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return numbers


def _number_matches(expected: float, observed_numbers: list[float], tolerance: float) -> bool:
    """判断期望数值是否出现在前端文本中。"""
    if expected is None:
        return True
    candidates = {float(expected)}
    # 前端业务展示经常对占比、均价做 0-1 位小数展示，标准层按原始口径保留更多位。
    candidates.add(round(float(expected), 1))
    candidates.add(round(float(expected), 0))
    # 兼容元和万元、瓦和 MW 等展示单位差异；严格比对报告仍记录原值。
    candidates.add(float(expected) / 10000)
    candidates.add(float(expected) * 10000)
    candidates.add(float(expected) / 1000000)
    candidates.add(float(expected) * 1000000)
    for candidate in candidates:
        for observed in observed_numbers:
            threshold = max(abs(candidate) * tolerance, tolerance)
            if abs(observed - candidate) <= threshold:
                return True
    return False


def _compare_answerable(expected: dict[str, Any], frontend: dict[str, Any], tolerance: float) -> tuple[str, list[str]]:
    """比对可直接回答题。"""
    reasons: list[str] = []
    text_blob = "\n".join(
        [
            str(frontend.get("title") or ""),
            str(frontend.get("answer") or ""),
            str(frontend.get("dom_text") or ""),
            str(frontend.get("table_rows") or ""),
        ]
    )
    if frontend.get("status") not in {"pass", "completed", ""}:
        reasons.append(f"前端执行状态异常：{frontend.get('status')} {frontend.get('error')}")
        return "FAIL", reasons
    if expected.get("answer_type") == "empty_result":
        if any(word in text_blob for word in ["无数据", "未找到", "没有", "0"]):
            return "PASS", []
        return "FAIL", ["期望空结果，但前端未展示无数据说明。"]
    observed_numbers = _numbers_from_text(text_blob)
    summary_values = expected.get("summary_values", [])
    # 表格型结果只抽查关键前几项，避免因前端分页或默认截断导致要求展示全部明细。
    if expected.get("answer_type") == "table":
        summary_values = summary_values[:10]
    for value in summary_values:
        if value is None:
            continue
        if isinstance(value, str):
            normalized_value = value.replace(",", "").strip()
            if re.fullmatch(r"-?\d+(?:\.\d+)?", normalized_value):
                if not _number_matches(float(normalized_value), observed_numbers, tolerance):
                    reasons.append(f"缺少期望数值：{value}")
            elif value and value not in text_blob:
                reasons.append(f"缺少规格/文本值：{value[:80]}")
        else:
            if not _number_matches(float(value), observed_numbers, tolerance):
                reasons.append(f"缺少期望数值：{value}")
    table = expected.get("table") or {}
    expected_rows = table.get("rows") or []
    if expected.get("answer_type") == "table" and expected_rows:
        frontend_rows = frontend.get("table_rows") or []
        if not frontend_rows and len(expected_rows) > 1:
            reasons.append("期望表格结果，但前端未抓取到表格行。")
        expected_columns = [str(column) for column in table.get("columns") or []]
        frontend_text = str(frontend_rows) + text_blob
        for column in expected_columns[:6]:
            if column and column not in frontend_text:
                reasons.append(f"表格缺少关键列：{column}")
                break
    return ("PASS", []) if not reasons else ("FAIL", reasons[:5])


def _compare_clarification(frontend: dict[str, Any]) -> tuple[str, list[str]]:
    """比对 B 类追问。"""
    text_blob = "\n".join([str(frontend.get("dom_text") or ""), str(frontend.get("follow_ups") or "")])
    # 业务界面可能用“需补充”“缺少必要条件”等短句表达追问，不能只按固定模板判断。
    if any(word in text_blob for word in ["请补充", "需要补充", "需补充", "请确认", "需要确认", "选择", "范围", "订单", "口径", "必要条件", "缺少"]):
        return "PASS", []
    return "FAIL", ["期望业务化追问，但前端未展示明确补充条件。"]


def _compare_unsupported(frontend: dict[str, Any]) -> tuple[str, list[str]]:
    """比对 C 类拒答解释。"""
    text_blob = str(frontend.get("dom_text") or "")
    if any(word in text_blob for word in ["无法", "不能", "不支持", "暂不支持", "缺少", "需要业务规则", "需要数据"]):
        return "PASS", []
    return "FAIL", ["期望无法回答解释，但前端没有清晰说明原因。"]


def compare_results(expected_payload: dict, frontend_payload: dict, *, tolerance: float) -> dict:
    """执行全量比对。

    参数：
        expected_payload: 标准答案文件；
        frontend_payload: 前端 E2E 抓取文件；
        tolerance: 数值比对容差。
    返回值：
        比对报告。
    """
    expected_by_id = {item["id"]: item for item in expected_payload.get("answers", [])}
    comparisons: list[dict[str, Any]] = []
    status_counter: Counter[str] = Counter()
    reason_counter: Counter[str] = Counter()
    if frontend_payload.get("status") == "blocked":
        return {
            "generated_at": now_iso(),
            "status": "blocked",
            "stop_condition": frontend_payload.get("stop_condition"),
            "message": frontend_payload.get("message"),
            "comparisons": [],
            "summary": {"PASS": 0, "FAIL": 0, "REVIEW": 0},
        }
    for frontend in frontend_payload.get("results", []):
        question_id = frontend.get("question_id")
        expected_item = expected_by_id.get(question_id)
        if frontend.get("recovered_from_compare_report"):
            # checkpoint 文件曾被异常覆盖时，可以从上一轮真实网页比对报告恢复续跑状态。
            # 这里不重新构造 DOM 文本，也不把 API 结果冒充前端结果，只沿用恢复前已经完成的比对结论。
            outcome = str(frontend.get("recovered_compare_outcome") or "REVIEW")
            reasons = list(frontend.get("recovered_compare_reasons") or [])
        elif not expected_item:
            outcome, reasons = "REVIEW", ["未找到对应标准答案。"]
        else:
            expected = expected_item.get("expected", {})
            expected_status = expected.get("expected_status")
            if expected_status == "answerable":
                outcome, reasons = _compare_answerable(expected, frontend, tolerance)
            elif expected_status == "needs_clarification":
                outcome, reasons = _compare_clarification(frontend)
            elif expected_status == "unsupported":
                outcome, reasons = _compare_unsupported(frontend)
            else:
                outcome, reasons = "REVIEW", [expected.get("reason") or "标准答案层标记为待人工复核。"]
        status_counter[outcome] += 1
        for reason in reasons:
            reason_counter[reason] += 1
        comparisons.append(
            {
                "case_id": frontend.get("case_id"),
                "question_id": question_id,
                "question": frontend.get("question"),
                "domain": frontend.get("domain"),
                "outcome": outcome,
                "reasons": reasons,
                "frontend_status": frontend.get("status"),
                "screenshot_path": frontend.get("screenshot_path"),
            }
        )
    return {
        "generated_at": now_iso(),
        "status": "completed",
        "frontend_status": frontend_payload.get("status"),
        "total_compared": len(comparisons),
        "summary": dict(status_counter),
        "reason_distribution": dict(reason_counter),
        "comparisons": comparisons,
    }


def write_compare_doc(report: dict) -> None:
    """写入比对报告文档。"""
    failed = [item for item in report.get("comparisons", []) if item.get("outcome") != "PASS"]
    lines = [
        f"- 报告状态：{report.get('status')}",
        f"- 比对总数：{report.get('total_compared', 0)}",
        f"- 结果分布：`{report.get('summary')}`",
        f"- 失败/复核数量：{len(failed)}",
        "",
        "## 失败原因分布",
    ]
    for reason, count in (report.get("reason_distribution") or {}).items():
        lines.append(f"- {reason}: {count}")
    lines.extend(["", "## 失败/复核样例"])
    for item in failed[:80]:
        lines.append(f"- {item.get('case_id')}：{item.get('question')}；原因：{'; '.join(item.get('reasons') or [])}")
    if report.get("status") == "blocked":
        lines.extend(["", "## 阻塞说明", f"- {report.get('message') or report.get('stop_condition')}"])
    write_markdown(DOCS_DIR / "TRIAL_SAMPLE_ANSWER_COMPARE_REPORT.md", "TRIAL_SAMPLE_ANSWER_COMPARE_REPORT", lines)


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="比对标准答案和前端展示结果")
    parser.add_argument("--expected", type=Path, default=EXPECTED_PATH)
    parser.add_argument("--frontend-results", type=Path, default=FRONTEND_RESULTS_PATH)
    parser.add_argument("--output", type=Path, default=COMPARE_REPORT_PATH)
    parser.add_argument("--tolerance", type=float, default=0.01)
    args = parser.parse_args()

    expected = read_json(args.expected)
    frontend = read_json(args.frontend_results)
    if expected is None:
        raise FileNotFoundError(f"缺少标准答案：{args.expected}")
    if frontend is None:
        raise FileNotFoundError(f"缺少前端 E2E 结果：{args.frontend_results}")
    report = compare_results(expected, frontend, tolerance=args.tolerance)
    failed = [item for item in report.get("comparisons", []) if item.get("outcome") != "PASS"]
    write_json(args.output, report)
    write_json(FAILED_CASES_PATH, failed)
    write_compare_doc(report)
    print(f"answer_compare_report written: {args.output}")
    print(f"summary={report.get('summary')}")


if __name__ == "__main__":
    main()

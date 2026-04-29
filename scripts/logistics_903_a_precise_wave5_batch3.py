from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import logistics_903_a_precise_wave3_batch1 as base


LEDGER_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_master_ledger.json"
QUESTION_SET_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_a_precise_wave5_batch3_questions.json"
BASELINE_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_a_precise_wave5_batch3_baseline.json"
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_a_precise_wave5_batch3_regression_report.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_A_PRECISE_WAVE5_BATCH3.md"


def _load_json(path: Path) -> Any:
    """读取 JSON 文件。

    参数：
        path: JSON 文件路径。

    返回：
        解析后的 JSON 对象。
    """

    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    """写出 JSON 文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _select_batch3_items(limit: int = 40) -> dict[str, Any]:
    """选择 Wave5 Batch3 精确断言增强题集。

    参数：
        limit: 批次数量上限，默认不少于本轮要求的 40 条。

    返回：
        Batch3 题集配置。

    业务规则：
        1. 只选择当前 A 且尚未进入精确断言的题；
        2. 优先覆盖未断言数量最多、业务价值高、易错的 query_key；
        3. 没有稳定 query_key 的题不进入精确断言，避免生成不可执行黄金基线。
    """

    ledger_items = _load_json(LEDGER_PATH)["items"]
    a_items = [item for item in ledger_items if item.get("current_status") == "A"]
    precise_count = sum(1 for item in a_items if item.get("in_precise_assertion"))
    uncovered = [
        item
        for item in a_items
        if not item.get("in_precise_assertion") and item.get("current_query_key")
    ]
    uncovered_query_counts = Counter(str(item.get("current_query_key") or "") for item in uncovered)
    high_value_query_key_order = {
        "hist_route_aggregate_summary": 0,
        "hist_monthly_trip_count_summary": 1,
        "hist_origin_vehicle_metric_summary": 2,
        "hist_vehicle_type_trip_count": 3,
        "hist_total_fee_summary": 4,
        "hist_mw_summary": 5,
        "sys_delivery_note_parse_status_distribution": 6,
        "sys_avg_loading_trucks_by_province": 7,
        "sys_extra_fee_summary": 8,
        "sys_task_status_province_ranking": 9,
    }

    def sort_key(item: dict[str, Any]) -> tuple[int, int, int, str, int]:
        remarks = item.get("remarks") or ""
        if "B-gap Wave4" in remarks:
            wave_priority = 0
        elif "B-gap Wave3" in remarks:
            wave_priority = 1
        elif "B-gap Wave2" in remarks:
            wave_priority = 2
        elif "B-gap Wave1" in remarks:
            wave_priority = 3
        elif "B->A" in remarks:
            wave_priority = 4
        else:
            wave_priority = 5
        query_key = str(item.get("current_query_key") or "")
        query_priority = high_value_query_key_order.get(query_key, 99)
        # 未覆盖数量越多，越优先补强，以提升总体精确断言覆盖面。
        uncovered_pressure = -uncovered_query_counts[query_key]
        return wave_priority, query_priority, uncovered_pressure, query_key, int(item["ledger_index"])

    selected = sorted(uncovered, key=sort_key)[:limit]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_ledger": str(LEDGER_PATH),
        "batch_id": "A-W5-P3",
        "coverage_before_batch": {
            "current_a_total": len(a_items),
            "precise_covered_before_batch": precise_count,
            "uncovered_a_before_batch": len(a_items) - precise_count,
            "selectable_uncovered_with_query_key": len(uncovered),
            "uncovered_query_key_breakdown": dict(uncovered_query_counts),
        },
        "selection_rule": "优先选择当前 A 中尚未精确断言、query_key 高频且业务价值高的题，重点补 Wave1/Wave2/Wave3/Wave4 新迁入 A。",
        "items": [
            {
                "plan_id": f"A-W5-P3-{index:03d}",
                "batch_id": "A-W5-P3",
                "question_id": item["question_id"],
                "question": item["question"],
                "source_group": item["source_group"],
                "family": item["family"],
                "query_key": item["current_query_key"],
                "standard_answer_source": "当前 logistics_ai 数据快照，经正式 data-qa 主链路执行后固化。",
                "assertion_scope": "精确断言 status.code、query_plan.query_key、answer_summary、result_table.columns、result_table.rows。",
                "assertion_fields": [
                    "status.code",
                    "query_plan.query_key",
                    "answer_summary",
                    "result_table.columns",
                    "result_table.rows",
                ],
            }
            for index, item in enumerate(selected, start=1)
        ],
    }


def _render_doc(*, baseline: dict[str, Any], report: dict[str, Any]) -> str:
    """渲染 Wave5 Batch3 精确断言报告文档。"""

    summary = report["summary"]
    coverage = report["coverage_before_batch"]
    lines = [
        "# 903 A 类精确断言增强 Wave5 Batch3",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 一、覆盖统计",
        "",
        f"- 当前 A 总数：`{coverage['current_a_total']}`",
        f"- 批次前已精确断言覆盖：`{coverage['precise_covered_before_batch']}`",
        f"- 批次前未覆盖 A：`{coverage['uncovered_a_before_batch']}`",
        f"- 可直接进入精确断言候选：`{coverage['selectable_uncovered_with_query_key']}`",
        "",
        "## 二、本批回归结论",
        "",
        f"- 本批题数：`{summary['total_questions']}`",
        f"- 通过：`{summary['passed_questions']}`",
        f"- 失败：`{summary['failed_questions']}`",
        f"- query_key 分布：`{summary['query_key_breakdown']}`",
        "",
        "## 三、标准答案来源与断言口径",
        "",
        "- 标准答案来源：当前 `logistics_ai` 数据快照，经正式 data-qa 主链路执行后固化。",
        "- 断言字段：`status.code`、`query_plan.query_key`、`answer_summary`、`result_table.columns`、`result_table.rows`。",
        "- 失败归因：query_key/status/columns 异常归为代码问题；answer_summary/rows 变化归为数据基线变化；预期 A 题进入澄清或不支持归为分层误判。",
        "",
        "## 四、题目清单",
        "",
        "| plan_id | 题号 | query_key | 问题 |",
        "| --- | --- | --- | --- |",
    ]
    for item in baseline["items"]:
        lines.append(f"| {item['plan_id']} | {item['question_id']} | {item['expected_query_key']} | {item['question']} |")
    lines.extend(["", "## 五、未通过题", ""])
    if report["failed_items"]:
        for item in report["failed_items"]:
            lines.append(f"- {item['plan_id']} / {item['question_id']}：{item['failure_classification']}，{item['failure_reason']}")
    else:
        lines.append("- 当前无未通过题。")
    return "\n".join(lines) + "\n"


def _patch_base_paths() -> None:
    """复用既有精确断言执行器并替换 Wave5 Batch3 路径。"""

    base.QUESTION_SET_PATH = QUESTION_SET_PATH
    base.BASELINE_PATH = BASELINE_PATH
    base.REPORT_PATH = REPORT_PATH
    base.DOC_PATH = DOC_PATH


def refresh_selection(limit: int = 40) -> dict[str, Any]:
    """刷新 Wave5 Batch3 题集。"""

    payload = _select_batch3_items(limit=limit)
    _write_json(QUESTION_SET_PATH, payload)
    return payload


def main() -> None:
    """命令行入口：生成 A 精确断言增强 Wave5 Batch3 并执行回归。"""

    parser = argparse.ArgumentParser(description="903 A 类精确断言增强 Wave5 Batch3")
    parser.add_argument("--refresh-selection", action="store_true", help="重新选择 Batch3 题集。")
    parser.add_argument("--refresh-baseline", action="store_true", help="重新生成 Batch3 精确断言基线。")
    parser.add_argument("--limit", type=int, default=40, help="Batch3 题数上限。")
    args = parser.parse_args()

    _patch_base_paths()
    if args.refresh_selection or not QUESTION_SET_PATH.exists():
        question_set = refresh_selection(limit=max(args.limit, 40))
    else:
        question_set = _load_json(QUESTION_SET_PATH)
    if args.refresh_baseline or not BASELINE_PATH.exists():
        baseline = base.refresh_baseline(question_set)
    else:
        baseline = _load_json(BASELINE_PATH)
    report = base.evaluate_regression()
    _write_json(REPORT_PATH, report)
    DOC_PATH.write_text(_render_doc(baseline=baseline, report=report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

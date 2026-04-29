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
QUESTION_SET_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_a_precise_acceptance_batch4_questions.json"
BASELINE_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_a_precise_acceptance_batch4_baseline.json"
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_a_precise_acceptance_batch4_regression_report.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_A_PRECISE_ACCEPTANCE_BATCH4.md"


def _load_json(path: Path) -> Any:
    """读取 JSON 文件。

    参数：
        path: JSON 文件路径。

    返回：
        解析后的 JSON 对象。
    """

    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    """写出 JSON 文件。

    参数：
        path: 输出路径。
        payload: 需要序列化的 JSON 对象。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _select_batch4_items(limit: int = 50) -> dict[str, Any]:
    """选择验收版 Batch4 精确断言题集。

    参数：
        limit: 题目数量下限，本轮不少于 50 条。

    返回：
        Batch4 题集配置。

    业务逻辑：
        只从当前 A 中选择尚未进入精确断言且具备稳定 query_key 的题；
        优先覆盖 Wave1-Wave4 新迁入 A、历史汇总高频 query_key 和系统侧高风险 query_key。
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
        "sys_mw_and_trip_count": 6,
        "sys_unit_fee_per_watt": 7,
        "sys_extra_fee_summary": 8,
        "sys_delivery_note_parse_status_distribution": 9,
        "sys_avg_loading_trucks_by_province": 10,
    }

    def sort_key(item: dict[str, Any]) -> tuple[int, int, int, str, int]:
        """给未覆盖 A 题排序。

        参数：
            item: 总账题目。

        返回：
            排序键，越小越优先进入 Batch4。
        """

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
        return wave_priority, query_priority, -uncovered_query_counts[query_key], query_key, int(item["ledger_index"])

    selected = sorted(uncovered, key=sort_key)[: max(limit, 50)]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_ledger": str(LEDGER_PATH),
        "batch_id": "A-ACCEPTANCE-B4",
        "coverage_before_batch": {
            "current_a_total": len(a_items),
            "precise_covered_before_batch": precise_count,
            "uncovered_a_before_batch": len(a_items) - precise_count,
            "selectable_uncovered_with_query_key": len(uncovered),
            "uncovered_query_key_breakdown": dict(uncovered_query_counts),
        },
        "selection_rule": "优先选择当前 A 中尚未精确断言、query_key 高频、业务价值高且易受口径变化影响的题。",
        "items": [
            {
                "plan_id": f"A-ACCEPT-B4-{index:03d}",
                "batch_id": "A-ACCEPTANCE-B4",
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
    """渲染 Batch4 精确断言交付文档。

    参数：
        baseline: 固化后的黄金答案基线。
        report: 回归执行报告。

    返回：
        Markdown 文档内容。
    """

    summary = report["summary"]
    coverage = report["coverage_before_batch"]
    lines = [
        "# 903 A 类精确断言增强 Batch4",
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
        "- 失败归因：query_key/status/columns 异常归为代码问题；answer_summary/rows 变化归为数据基线变化；A 题进入澄清或不支持归为分层误判。",
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
    """复用既有精确断言执行器，并替换为 Batch4 路径。"""

    base.QUESTION_SET_PATH = QUESTION_SET_PATH
    base.BASELINE_PATH = BASELINE_PATH
    base.REPORT_PATH = REPORT_PATH
    base.DOC_PATH = DOC_PATH


def refresh_selection(limit: int = 50) -> dict[str, Any]:
    """刷新 Batch4 题集。

    参数：
        limit: 题目数量下限。

    返回：
        写入后的题集配置。
    """

    payload = _select_batch4_items(limit=limit)
    _write_json(QUESTION_SET_PATH, payload)
    return payload


def main() -> None:
    """命令行入口：生成并执行验收版 Batch4 精确断言。"""

    parser = argparse.ArgumentParser(description="903 A 类精确断言增强 Batch4")
    parser.add_argument("--refresh-selection", action="store_true", help="重新选择 Batch4 题集。")
    parser.add_argument("--refresh-baseline", action="store_true", help="重新生成 Batch4 黄金答案基线。")
    parser.add_argument("--limit", type=int, default=50, help="Batch4 题数下限。")
    args = parser.parse_args()

    _patch_base_paths()
    if args.refresh_selection or not QUESTION_SET_PATH.exists():
        question_set = refresh_selection(limit=max(args.limit, 50))
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

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.db.session import SessionLocal
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.domains.logistics.services.error_code_registry import LogisticsErrorCodeRegistry


TOP200_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_top200_questions.json"
BASELINE_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_top200_p1_p2_a_precise_baseline.json"
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_top200_p1_p2_regression_report.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_TOP200_P1_P2_CLOSURE.md"
ROUND_REPORT_PATHS = [
    PROJECT_ROOT / "tmp/logistics_question_bank/logistics_top200_b_factory_round1_report.json",
    PROJECT_ROOT / "tmp/logistics_question_bank/logistics_top200_b_factory_round2_report.json",
    PROJECT_ROOT / "tmp/logistics_question_bank/logistics_top200_b_factory_round3_report.json",
    PROJECT_ROOT / "tmp/logistics_question_bank/logistics_top200_b_factory_round4_report.json",
    PROJECT_ROOT / "tmp/logistics_question_bank/logistics_top200_b_factory_round5_report.json",
]


class NoopQueryLogRepository:
    """无副作用查询日志仓储。

    说明：
        1. 批量回归必须真实调用当前 data-qa 主链路；
        2. 但不应把回归题写进正式业务查询历史；
        3. 因此脚本统一注入空日志仓储。
    """

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        _ = db, payload
        return 0


@dataclass
class PreciseBaselineItem:
    """P1/P2 A 类题精确断言基线。"""

    question_id: str
    priority: str
    question: str
    query_key: str | None
    standard_answer_source: str
    assertion_scope: str
    assertion_fields: list[str]
    expected_status_code: str
    expected_answer_summary: str
    expected_columns: list[str]
    expected_rows: list[dict[str, Any]]


@dataclass
class PreciseRegressionRecord:
    """P1/P2 A 类题精确回归结果。"""

    question_id: str
    priority: str
    question: str
    expected_query_key: str | None
    actual_query_key: str | None
    expected_status_code: str
    actual_status_code: str
    passed: bool
    failure_classification: str | None
    failure_reason: str | None


@dataclass
class ClosureRecord:
    """P1/P2 B 类题收口结果。"""

    question_id: str
    priority: str
    question: str
    expected_route: str
    actual_status_code: str
    actual_query_key: str | None
    closure_result: str
    closure_reason: str
    answer_summary: str


def _load_top200_items() -> list[dict[str, Any]]:
    """读取 Top200 正式清单。"""
    payload = json.loads(TOP200_PATH.read_text(encoding="utf-8"))
    return payload["items"]


def _load_promoted_a_question_ids() -> set[str]:
    """汇总 Round1-Round5 已推进进 A 的题号。

    说明：
        1. Top200 正式清单里的 current_classification 不会在每轮工厂化后立即重写；
        2. P1/P2 精确断言回归必须以“当前真实已推进进 A 的题”为准；
        3. 因此这里统一从 round 报告里汇总 promoted_question_ids，避免漏掉 Round4/5 新进 A 题。
    """
    promoted_ids: set[str] = set()
    for report_path in ROUND_REPORT_PATHS:
        if not report_path.exists():
            continue
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        promoted_ids.update(payload.get("promoted_question_ids", []))
    return promoted_ids


def _select_p1_p2_a_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """筛选 P1/P2 中当前已进入 A 类的题。

    说明：
        1. 一部分题在 Top200 正式清单里初始仍记为 B；
        2. 但经过 Round1-Round5 工厂化收口后，已经真实推进进 A；
        3. 精确断言回归必须把这些题一起纳入，不允许只看静态配置。
    """
    promoted_ids = _load_promoted_a_question_ids()
    return [
        item
        for item in items
        if item["priority"] in {"P1", "P2"}
        and (item["current_classification"] == "A" or item["question_id"] in promoted_ids)
    ]


def _select_p1_p2_b_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """筛选 P1/P2 中当前 B 类题。"""
    return [
        item
        for item in items
        if item["priority"] in {"P1", "P2"} and item["current_classification"] == "B"
    ]


def _run_query(service: LogisticsDataQaService, question: str) -> dict[str, Any]:
    """执行单题并返回 JSON 结果。"""
    result = service.query(
        LogisticsDataQaQueryRequest(question=question),
        trace_id="logistics-top200-p1-p2-regression",
    )
    return result.model_dump(mode="json")


def refresh_precise_baseline(
    *,
    output_path: Path = BASELINE_PATH,
) -> dict[str, Any]:
    """刷新 P1/P2 A 类题精确断言基线。

    说明：
        1. 当前基线直接来自 logistics_ai 真实主链路结果；
        2. 这是 P1/P2 A 类题第一版更严格的快照基线；
        3. 后续若回归失败，需要明确区分代码问题还是数据基线变化。
    """
    items = _load_top200_items()
    target_items = _select_p1_p2_a_items(items)
    db = SessionLocal()
    service = LogisticsDataQaService(db=db, query_log_repository=NoopQueryLogRepository())
    baseline_items: list[PreciseBaselineItem] = []
    try:
        for item in target_items:
            response = _run_query(service, item["question"])
            baseline_items.append(
                PreciseBaselineItem(
                    question_id=item["question_id"],
                    priority=item["priority"],
                    question=item["question"],
                    query_key=response.get("query_plan", {}).get("query_key"),
                    standard_answer_source="logistics_ai snapshot via scripts/logistics_top200_p1_p2_regression.py --refresh-baseline",
                    assertion_scope="answer_summary + result_table.columns + result_table.rows 精确快照断言",
                    assertion_fields=["answer_summary", "result_table.columns", "result_table.rows"],
                    expected_status_code=(response.get("status") or {}).get("code", "NO_STATUS"),
                    expected_answer_summary=response.get("answer_summary", ""),
                    expected_columns=(response.get("result_table") or {}).get("columns", []),
                    expected_rows=(response.get("result_table") or {}).get("rows", []),
                )
            )
    finally:
        db.close()

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "result_database": "logistics_ai",
        "selection_rule": "P1/P2 中静态 A 类题 + Round1-Round5 已推进进 A 的题，统一建立精确快照基线。",
        "items": [asdict(item) for item in baseline_items],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _resolve_precise_failure(
    *,
    baseline: PreciseBaselineItem,
    response: dict[str, Any],
) -> tuple[str | None, str | None]:
    """区分精确断言失败是代码问题还是数据基线变化。"""
    actual_query_key = response.get("query_plan", {}).get("query_key")
    actual_status_code = (response.get("status") or {}).get("code", "NO_STATUS")
    if actual_query_key != baseline.query_key:
        return "代码问题", f"预期 query_key={baseline.query_key}，实际为 {actual_query_key}"
    if actual_status_code != baseline.expected_status_code:
        return "代码问题", f"预期状态码={baseline.expected_status_code}，实际为 {actual_status_code}"
    if response.get("answer_summary", "") != baseline.expected_answer_summary:
        return "数据基线变化", "answer_summary 与当前精确基线不一致"
    result_table = response.get("result_table") or {}
    if result_table.get("columns", []) != baseline.expected_columns:
        return "代码问题", "result_table.columns 结构发生变化"
    if result_table.get("rows", []) != baseline.expected_rows:
        return "数据基线变化", "result_table.rows 与当前精确基线不一致"
    return None, None


def evaluate_precise_regression(
    *,
    baseline_path: Path = BASELINE_PATH,
) -> dict[str, Any]:
    """执行 P1/P2 A 类题精确断言回归。"""
    baseline_payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline_items = [PreciseBaselineItem(**item) for item in baseline_payload["items"]]
    db = SessionLocal()
    service = LogisticsDataQaService(db=db, query_log_repository=NoopQueryLogRepository())
    records: list[PreciseRegressionRecord] = []
    try:
        for baseline in baseline_items:
            response = _run_query(service, baseline.question)
            failure_classification, failure_reason = _resolve_precise_failure(
                baseline=baseline,
                response=response,
            )
            records.append(
                PreciseRegressionRecord(
                    question_id=baseline.question_id,
                    priority=baseline.priority,
                    question=baseline.question,
                    expected_query_key=baseline.query_key,
                    actual_query_key=response.get("query_plan", {}).get("query_key"),
                    expected_status_code=baseline.expected_status_code,
                    actual_status_code=(response.get("status") or {}).get("code", "NO_STATUS"),
                    passed=failure_classification is None,
                    failure_classification=failure_classification,
                    failure_reason=failure_reason,
                )
            )
    finally:
        db.close()

    return {
        "summary": {
            "total_questions": len(records),
            "passed_questions": sum(1 for item in records if item.passed),
            "failed_questions": sum(1 for item in records if not item.passed),
        },
        "items": [asdict(item) for item in records],
        "failed_items": [asdict(item) for item in records if not item.passed],
    }


def _resolve_b_closure_reason(question_id: str, status_code: str) -> tuple[str, str]:
    """把当前 B 类题的收口结果解释成业务可读原因。"""
    if status_code == LogisticsErrorCodeRegistry.OK:
        return "promoted_to_a", "当前主链路已能稳定落到受控 query_key，可作为下一批 A 类收口对象。"
    if question_id in {"RAW052", "RAW056"}:
        return "remain_b", "2026 基地过滤当前缺少稳定映射字段，只能先保留业务化澄清。"
    if question_id == "RAW038":
        return "remain_b", "高运费项目地继续要补采购方式口径，当前只能先澄清是否具备询比价/招标拆分条件。"
    if question_id == "RAW057":
        return "remain_b", "当前只有月份没有年份，单瓦成本口径仍需先确认统计年份和是否包含额外费用。"
    if question_id in {"RAW049", "RAW050"}:
        return "remain_b", "项目/客户总运量缺少年份，当前仍需先确认按单年还是按 2023–2025 历史累计统计。"
    if status_code == LogisticsErrorCodeRegistry.UNSUPPORTED_QUESTION:
        return "moved_to_c", "当前能力边界下不应继续澄清，应直接视为不支持。"
    return "remain_b", "当前仍需继续保留澄清，不应直接误落成功态。"


def evaluate_b_closure() -> dict[str, Any]:
    """执行 P1/P2 高价值 B 类题真实收口验证。"""
    items = _load_top200_items()
    target_items = _select_p1_p2_b_items(items)
    db = SessionLocal()
    service = LogisticsDataQaService(db=db, query_log_repository=NoopQueryLogRepository())
    records: list[ClosureRecord] = []
    try:
        for item in target_items:
            response = _run_query(service, item["question"])
            status_code = (response.get("status") or {}).get("code", "NO_STATUS")
            closure_result, closure_reason = _resolve_b_closure_reason(item["question_id"], status_code)
            records.append(
                ClosureRecord(
                    question_id=item["question_id"],
                    priority=item["priority"],
                    question=item["question"],
                    expected_route=item["current_route"],
                    actual_status_code=status_code,
                    actual_query_key=response.get("query_plan", {}).get("query_key"),
                    closure_result=closure_result,
                    closure_reason=closure_reason,
                    answer_summary=response.get("answer_summary", ""),
                )
            )
    finally:
        db.close()

    def _summary_for(priority: str) -> dict[str, int]:
        bucket = [item for item in records if item.priority == priority]
        return {
            "total": len(bucket),
            "promoted_to_a": sum(1 for item in bucket if item.closure_result == "promoted_to_a"),
            "remain_b": sum(1 for item in bucket if item.closure_result == "remain_b"),
            "moved_to_c": sum(1 for item in bucket if item.closure_result == "moved_to_c"),
        }

    return {
        "summary": {
            "total_questions": len(records),
            "promoted_to_a": sum(1 for item in records if item.closure_result == "promoted_to_a"),
            "remain_b": sum(1 for item in records if item.closure_result == "remain_b"),
            "moved_to_c": sum(1 for item in records if item.closure_result == "moved_to_c"),
            "priority_breakdown": {
                "P1": _summary_for("P1"),
                "P2": _summary_for("P2"),
            },
        },
        "items": [asdict(item) for item in records],
    }


def build_report(*, baseline_path: Path = BASELINE_PATH) -> dict[str, Any]:
    """构造 P1/P2 本轮收口综合报告。"""
    precise_payload = evaluate_precise_regression(baseline_path=baseline_path)
    closure_payload = evaluate_b_closure()
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "result_database": "logistics_ai",
        "scope": "P1/P2 高价值题收口",
        "a_precise_regression": precise_payload,
        "b_closure_progress": closure_payload,
    }


def render_markdown(report: dict[str, Any]) -> str:
    """渲染 P1/P2 收口摘要文档。"""
    a_summary = report["a_precise_regression"]["summary"]
    b_summary = report["b_closure_progress"]["summary"]
    lines: list[str] = []
    lines.append("# 物流域 Top200 P1/P2 收口进展")
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    lines.append(
        f"- P1/P2 中 A 类题当前已纳入更严格的精确断言回归：**{a_summary['passed_questions']}/{a_summary['total_questions']}** 通过。"
    )
    lines.append(
        f"- P1/P2 中高价值 B 类题本轮共验证 **{b_summary['total_questions']}** 条，其中已推进进 A 类 **{b_summary['promoted_to_a']}** 条。"
    )
    lines.append("")
    lines.append("## P1/P2 A 类精确回归")
    lines.append("")
    lines.append(
        f"- 总数：{a_summary['total_questions']}\n- 通过：{a_summary['passed_questions']}\n- 失败：{a_summary['failed_questions']}"
    )
    lines.append("")
    if report["a_precise_regression"]["failed_items"]:
        lines.append("### 未通过题")
        lines.append("")
        for item in report["a_precise_regression"]["failed_items"]:
            lines.append(
                f"- {item['question_id']}：{item['failure_classification']}，{item['failure_reason']}"
            )
        lines.append("")
    else:
        lines.append("### 未通过题")
        lines.append("")
        lines.append("- 当前无未通过题。")
        lines.append("")
    lines.append("## P1/P2 B 类收口进展")
    lines.append("")
    lines.append(
        f"- 总数：{b_summary['total_questions']}\n- 已推进进 A 类：{b_summary['promoted_to_a']}\n- 继续保留 B 类：{b_summary['remain_b']}\n- 本轮转入 C 类：{b_summary['moved_to_c']}"
    )
    lines.append("")
    lines.append("### 按批次统计")
    lines.append("")
    lines.append("| 批次 | 总数 | 已推进进 A 类 | 继续保留 B 类 | 转入 C 类 |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for priority, item in b_summary["priority_breakdown"].items():
        lines.append(
            f"| {priority} | {item['total']} | {item['promoted_to_a']} | {item['remain_b']} | {item['moved_to_c']} |"
        )
    lines.append("")
    lines.append("### 继续保留 B 类的代表题")
    lines.append("")
    for item in report["b_closure_progress"]["items"]:
        if item["closure_result"] == "remain_b":
            lines.append(f"- {item['question_id']}：{item['closure_reason']}")
    lines.append("")
    lines.append("## 当前判断")
    lines.append("")
    lines.append("- 物流数据问答 MVP 已收口。")
    lines.append("- P1/P2 中 A 类题已经开始进入更严格的精确断言回归。")
    lines.append("- P1/P2 中高价值 B 类题已经完成第一轮真实收口。")
    lines.append("- 但物流域 903 条题库仍未完全收口。")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="物流域 Top200 P1/P2 收口进展脚本")
    parser.add_argument("--refresh-baseline", action="store_true", help="刷新 P1/P2 A 类题精确基线")
    parser.add_argument("--baseline-output", default=str(BASELINE_PATH), help="精确基线输出路径")
    parser.add_argument("--output", default=str(REPORT_PATH), help="综合 JSON 报告输出路径")
    parser.add_argument("--doc-output", default=str(DOC_PATH), help="Markdown 摘要输出路径")
    args = parser.parse_args()

    baseline_path = Path(args.baseline_output)
    if args.refresh_baseline or not baseline_path.exists():
        refresh_precise_baseline(output_path=baseline_path)

    report = build_report(baseline_path=baseline_path)
    output_path = Path(args.output)
    doc_path = Path(args.doc_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    doc_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"a_precise_regression": report["a_precise_regression"]["summary"], "b_closure_progress": report["b_closure_progress"]["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

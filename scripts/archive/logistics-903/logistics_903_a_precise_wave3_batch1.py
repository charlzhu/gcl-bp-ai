from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
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


LEDGER_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_master_ledger.json"
QUESTION_SET_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_a_precise_wave3_batch1_questions.json"
BASELINE_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_a_precise_wave3_batch1_baseline.json"
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_a_precise_wave3_batch1_regression_report.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_A_PRECISE_WAVE3_BATCH1.md"


class NoopQueryLogRepository:
    """无副作用查询日志仓储。

    说明：
        A 精确断言增强批次必须真实调用 data-qa 主链路，但不应写入正式查询历史。
    """

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        """忽略查询日志写入请求。"""

        _ = db, payload
        return 0


@dataclass
class APreciseBaselineItem:
    """A 类精确断言增强单题基线。"""

    plan_id: str
    batch_id: str
    question_id: str
    question: str
    source_group: str
    family: str
    expected_query_key: str
    standard_answer_source: str
    assertion_scope: str
    assertion_fields: list[str]
    expected_status_code: str
    expected_answer_summary: str
    expected_columns: list[str]
    expected_rows: list[dict[str, Any]]


@dataclass
class APreciseRegressionRecord:
    """A 类精确断言增强单题回归结果。"""

    plan_id: str
    question_id: str
    question: str
    expected_query_key: str
    actual_query_key: str | None
    expected_status_code: str
    actual_status_code: str
    passed: bool
    failure_classification: str | None
    failure_reason: str | None


def _load_json(path: Path) -> Any:
    """读取 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    """写出 JSON 文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_service() -> tuple[Any, LogisticsDataQaService]:
    """构造真实 data-qa 服务。

    返回：
        数据库会话与 data-qa 服务实例。
    """

    db = SessionLocal()
    return db, LogisticsDataQaService(db=db, query_log_repository=NoopQueryLogRepository())


def _run_query(service: LogisticsDataQaService, question: str) -> dict[str, Any]:
    """执行单题查询并返回 JSON 响应。"""

    result = service.query(
        LogisticsDataQaQueryRequest(question=question),
        trace_id="logistics-903-a-precise-wave3-batch1",
    )
    return result.model_dump(mode="json")


def _load_ledger_items() -> list[dict[str, Any]]:
    """读取当前 903 总账题目。"""

    return _load_json(LEDGER_PATH)["items"]


def _select_batch_items(limit: int = 30) -> dict[str, Any]:
    """从当前 A 题中选择第一批精确断言增强对象。

    参数：
        limit: 批次数量上限。

    返回：
        精确断言增强题集配置。

    业务规则：
        优先选择 Wave1/Wave2/Wave3 新进 A 中尚未进入精确断言、且已有受控 query_key 的题。
    """

    ledger_items = _load_ledger_items()
    a_items = [item for item in ledger_items if item.get("current_status") == "A"]
    precise_count = sum(1 for item in a_items if item.get("in_precise_assertion"))
    uncovered = [
        item
        for item in a_items
        if not item.get("in_precise_assertion") and item.get("current_query_key")
    ]

    def sort_key(item: dict[str, Any]) -> tuple[int, str, int]:
        remarks = item.get("remarks") or ""
        if "B-gap Wave3" in remarks:
            priority = 0
        elif "B-gap Wave2" in remarks:
            priority = 1
        elif "B-gap Wave1" in remarks:
            priority = 2
        elif "B->A" in remarks:
            priority = 3
        else:
            priority = 4
        return priority, str(item.get("current_query_key") or ""), int(item["ledger_index"])

    selected = sorted(uncovered, key=sort_key)[:limit]
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_ledger": str(LEDGER_PATH),
        "batch_id": "A-W3-P1",
        "coverage_before_batch": {
            "current_a_total": len(a_items),
            "precise_covered_before_batch": precise_count,
            "uncovered_a_before_batch": len(a_items) - precise_count,
            "selectable_uncovered_with_query_key": len(uncovered),
        },
        "selection_rule": "优先选择 Wave1/Wave2/Wave3 新进 A 中尚未进入精确断言、且已有受控 query_key 的高价值题。",
        "items": [
            {
                "plan_id": f"A-W3-P1-{index:03d}",
                "batch_id": "A-W3-P1",
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
    return payload


def refresh_selection(limit: int = 30) -> dict[str, Any]:
    """刷新第一批精确断言增强题集。"""

    payload = _select_batch_items(limit=limit)
    _write_json(QUESTION_SET_PATH, payload)
    return payload


def refresh_baseline(question_set: dict[str, Any]) -> dict[str, Any]:
    """使用当前 data-qa 主链路生成精确断言基线。

    参数：
        question_set: 第一批精确断言增强题集。

    返回：
        固化后的基线 JSON。
    """

    db, service = _build_service()
    baseline_items: list[APreciseBaselineItem] = []
    try:
        for item in question_set["items"]:
            response = _run_query(service, item["question"])
            result_table = response.get("result_table") or {}
            baseline_items.append(
                APreciseBaselineItem(
                    plan_id=item["plan_id"],
                    batch_id=item["batch_id"],
                    question_id=item["question_id"],
                    question=item["question"],
                    source_group=item["source_group"],
                    family=item["family"],
                    expected_query_key=item["query_key"],
                    standard_answer_source=item["standard_answer_source"],
                    assertion_scope=item["assertion_scope"],
                    assertion_fields=item["assertion_fields"],
                    expected_status_code=(response.get("status") or {}).get("code", "NO_STATUS"),
                    expected_answer_summary=response.get("answer_summary", ""),
                    expected_columns=result_table.get("columns", []),
                    expected_rows=result_table.get("rows", []),
                )
            )
    finally:
        db.close()
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_question_set": str(QUESTION_SET_PATH),
        "batch_id": question_set["batch_id"],
        "coverage_before_batch": question_set["coverage_before_batch"],
        "selection_rule": question_set["selection_rule"],
        "items": [asdict(item) for item in baseline_items],
    }
    _write_json(BASELINE_PATH, payload)
    return payload


def _resolve_failure(
    *,
    baseline: APreciseBaselineItem,
    response: dict[str, Any],
) -> tuple[str | None, str | None]:
    """判定精确断言失败原因。

    返回：
        (失败分类, 失败原因)，均为 None 表示通过。
    """

    actual_query_key = response.get("query_plan", {}).get("query_key")
    actual_intent = response.get("query_plan", {}).get("intent")
    actual_status_code = (response.get("status") or {}).get("code", "NO_STATUS")
    if actual_query_key != baseline.expected_query_key:
        if actual_intent in {"clarification", "unsupported"}:
            return "题目分层误判", f"预期 A query_key={baseline.expected_query_key}，实际进入 {actual_intent}"
        return "代码问题", f"预期 query_key={baseline.expected_query_key}，实际 query_key={actual_query_key}"
    if actual_status_code != baseline.expected_status_code:
        return "代码问题", f"预期状态码={baseline.expected_status_code}，实际状态码={actual_status_code}"
    result_table = response.get("result_table") or {}
    if result_table.get("columns", []) != baseline.expected_columns:
        return "代码问题", "result_table.columns 结构发生变化"
    if response.get("answer_summary", "") != baseline.expected_answer_summary:
        return "数据基线变化", "answer_summary 与基线不一致"
    if result_table.get("rows", []) != baseline.expected_rows:
        return "数据基线变化", "result_table.rows 与基线不一致"
    return None, None


def evaluate_regression() -> dict[str, Any]:
    """执行第一批 A 精确断言增强回归。"""

    baseline_payload = _load_json(BASELINE_PATH)
    baseline_items = [APreciseBaselineItem(**item) for item in baseline_payload["items"]]
    db, service = _build_service()
    records: list[APreciseRegressionRecord] = []
    failure_counter: Counter[str] = Counter()
    query_key_counter: Counter[str] = Counter()
    try:
        for baseline in baseline_items:
            try:
                response = _run_query(service, baseline.question)
                failure_classification, failure_reason = _resolve_failure(
                    baseline=baseline,
                    response=response,
                )
                actual_query_key = response.get("query_plan", {}).get("query_key")
                actual_status_code = (response.get("status") or {}).get("code", "NO_STATUS")
                record = APreciseRegressionRecord(
                    plan_id=baseline.plan_id,
                    question_id=baseline.question_id,
                    question=baseline.question,
                    expected_query_key=baseline.expected_query_key,
                    actual_query_key=actual_query_key,
                    expected_status_code=baseline.expected_status_code,
                    actual_status_code=actual_status_code,
                    passed=failure_classification is None,
                    failure_classification=failure_classification,
                    failure_reason=failure_reason,
                )
            except Exception as exc:  # noqa: BLE001
                record = APreciseRegressionRecord(
                    plan_id=baseline.plan_id,
                    question_id=baseline.question_id,
                    question=baseline.question,
                    expected_query_key=baseline.expected_query_key,
                    actual_query_key=None,
                    expected_status_code=baseline.expected_status_code,
                    actual_status_code="EXCEPTION",
                    passed=False,
                    failure_classification="代码问题",
                    failure_reason=f"执行异常：{exc}",
                )
            records.append(record)
            query_key_counter[record.actual_query_key or "NONE"] += 1
            if record.failure_classification:
                failure_counter[record.failure_classification] += 1
    finally:
        db.close()
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "batch_id": baseline_payload["batch_id"],
        "coverage_before_batch": baseline_payload["coverage_before_batch"],
        "summary": {
            "total_questions": len(records),
            "passed_questions": sum(1 for record in records if record.passed),
            "failed_questions": sum(1 for record in records if not record.passed),
            "query_key_breakdown": dict(query_key_counter),
            "failure_classification_breakdown": dict(failure_counter),
        },
        "items": [asdict(record) for record in records],
        "failed_items": [asdict(record) for record in records if not record.passed],
    }


def _render_doc(*, baseline: dict[str, Any], report: dict[str, Any]) -> str:
    """渲染 A 精确断言增强 Markdown 文档。"""

    summary = report["summary"]
    coverage = report["coverage_before_batch"]
    lines = [
        "# 903 A 类精确断言增强 Wave3 Batch1",
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


def main() -> None:
    """命令行入口：生成 A 精确断言增强 Batch1 并执行回归。"""

    parser = argparse.ArgumentParser(description="903 A 类精确断言增强 Wave3 Batch1")
    parser.add_argument("--refresh-selection", action="store_true", help="重新选择 Batch1 题集。")
    parser.add_argument("--refresh-baseline", action="store_true", help="重新生成 Batch1 精确断言基线。")
    parser.add_argument("--limit", type=int, default=30, help="Batch1 题数上限。")
    args = parser.parse_args()

    if args.refresh_selection or not QUESTION_SET_PATH.exists():
        question_set = refresh_selection(limit=args.limit)
    else:
        question_set = _load_json(QUESTION_SET_PATH)
    if args.refresh_baseline or not BASELINE_PATH.exists():
        baseline = refresh_baseline(question_set)
    else:
        baseline = _load_json(BASELINE_PATH)
    report = evaluate_regression()
    _write_json(REPORT_PATH, report)
    DOC_PATH.write_text(_render_doc(baseline=baseline, report=report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

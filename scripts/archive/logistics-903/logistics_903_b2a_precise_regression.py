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


PLAN_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b2a_precise_batches.json"
BASELINE_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_b2a_p1_precise_baseline.json"
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_b2a_p1_precise_regression_report.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_B2A_P1_PRECISE_REGRESSION.md"
BATCH_ID = "B2A-P1"


def _set_batch_context(batch_id: str) -> None:
    """切换 B2A 精确断言批次上下文。

    参数：
        batch_id: B2A 批次编号，例如 B2A-P1、B2A-P2、B2A-P3。

    返回：
        无返回值；函数会更新本脚本后续读写使用的全局路径。

    说明：
        B2A 三个批次共用一套真实 data-qa 精确断言逻辑，但每批必须输出独立
        baseline、report 和 Markdown 文档，避免不同批次互相覆盖。
    """

    global BASELINE_PATH, REPORT_PATH, DOC_PATH, BATCH_ID

    normalized_batch_id = batch_id.strip().upper()
    slug = normalized_batch_id.lower().replace("-", "_")
    BATCH_ID = normalized_batch_id
    BASELINE_PATH = PROJECT_ROOT / f"backend/app/domains/logistics/config/logistics_{slug}_precise_baseline.json"
    REPORT_PATH = PROJECT_ROOT / f"tmp/logistics_question_bank/logistics_{slug}_precise_regression_report.json"
    DOC_PATH = PROJECT_ROOT / f"docs/LOGISTICS_{slug.upper()}_PRECISE_REGRESSION.md"


class NoopQueryLogRepository:
    """无副作用查询日志仓储。

    说明：
        1. B2A 精确断言必须真实调用 data-qa 主链路；
        2. 回归脚本不应污染正式业务查询历史；
        3. 因此统一注入空日志仓储实现。
    """

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        """忽略查询日志写入请求。"""

        _ = db, payload
        return 0


@dataclass
class B2APreciseBaselineItem:
    """B2A 单题精确断言基线。"""

    plan_id: str
    batch_id: str
    batch_name: str
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
class B2APreciseRegressionRecord:
    """B2A 单题精确断言回归结果。"""

    plan_id: str
    batch_id: str
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


def _load_batch_items() -> list[dict[str, Any]]:
    """读取当前 B2A 批次题目。"""

    payload = _load_json(PLAN_PATH)
    items = [item for item in payload["items"] if item["batch_id"] == BATCH_ID]
    items.sort(key=lambda item: item["plan_id"])
    return items


def _run_query(service: LogisticsDataQaService, question: str) -> dict[str, Any]:
    """执行单题查询并返回 JSON 响应。"""

    result = service.query(
        LogisticsDataQaQueryRequest(question=question),
        trace_id=f"logistics-{BATCH_ID.lower()}-precise-regression",
    )
    return result.model_dump(mode="json")


def refresh_precise_baseline() -> dict[str, Any]:
    """使用当前 data-qa 主链路刷新当前 B2A 批次精确断言基线。

    返回：
        包含批次基线题目和断言快照的 JSON 结构。

    重要业务规则：
        expected_query_key 必须来自治理计划，而不是当前响应。这样如果某题实际
        退回 clarification / unsupported，回归会失败，而不是被刷新成错误基线。
    """

    config_items = _load_batch_items()
    db = SessionLocal()
    service = LogisticsDataQaService(db=db, query_log_repository=NoopQueryLogRepository())
    baseline_items: list[B2APreciseBaselineItem] = []
    try:
        for item in config_items:
            response = _run_query(service, item["question"])
            result_table = response.get("result_table") or {}
            baseline_items.append(
                B2APreciseBaselineItem(
                    plan_id=item["plan_id"],
                    batch_id=item["batch_id"],
                    batch_name=item["batch_name"],
                    question_id=item["question_id"],
                    question=item["question"],
                    source_group=item["source_group"],
                    family=item["family"],
                    expected_query_key=item.get("query_key") or response.get("query_plan", {}).get("query_key"),
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
        "batch_id": BATCH_ID,
        "result_database": "logistics_ai",
        "selection_rule": f"B->A 正式迁移题中 {BATCH_ID} 批次 {len(baseline_items)} 条。",
        "items": [asdict(item) for item in baseline_items],
    }
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _resolve_failure(
    *,
    baseline: B2APreciseBaselineItem,
    response: dict[str, Any],
) -> tuple[str | None, str | None]:
    """把精确断言失败归类为代码问题、数据基线变化或分层误判。

    参数：
        baseline: 当前题目的精确断言基线。
        response: 当前 data-qa 主链路实时执行响应。

    返回：
        (失败分类, 失败原因)。均为 None 表示通过。

    归因口径：
        1. query_key 或状态码变化通常代表 planner / service 行为变化，归为代码问题；
        2. 结果摘要或行数据变化通常代表底层数据快照变化，归为数据基线变化；
        3. 预期 A 题实际进入澄清或不支持，归为题目分层误判。
    """

    actual_query_key = response.get("query_plan", {}).get("query_key")
    actual_intent = response.get("query_plan", {}).get("intent")
    actual_status_code = (response.get("status") or {}).get("code", "NO_STATUS")
    if actual_query_key != baseline.expected_query_key:
        if actual_intent in {"unsupported", "clarification"}:
            return (
                "题目分层误判",
                f"预期 A 类 query_key={baseline.expected_query_key}，实际进入 {actual_intent} 边界",
            )
        return "代码问题", f"预期 query_key={baseline.expected_query_key}，实际为 {actual_query_key}"
    if actual_status_code != baseline.expected_status_code:
        return "代码问题", f"预期状态码={baseline.expected_status_code}，实际为 {actual_status_code}"

    result_table = response.get("result_table") or {}
    actual_columns = result_table.get("columns", [])
    actual_rows = result_table.get("rows", [])
    if actual_columns != baseline.expected_columns:
        return "代码问题", "result_table.columns 结构发生变化"
    if response.get("answer_summary", "") != baseline.expected_answer_summary:
        return "数据基线变化", "answer_summary 与当前精确断言基线不一致"
    if actual_rows != baseline.expected_rows:
        return "数据基线变化", "result_table.rows 与当前精确断言基线不一致"
    return None, None


def evaluate_precise_regression() -> dict[str, Any]:
    """执行当前 B2A 批次精确断言回归。"""

    baseline_payload = _load_json(BASELINE_PATH)
    baseline_items = [B2APreciseBaselineItem(**item) for item in baseline_payload["items"]]
    db = SessionLocal()
    service = LogisticsDataQaService(db=db, query_log_repository=NoopQueryLogRepository())
    records: list[B2APreciseRegressionRecord] = []
    failure_counter: Counter[str] = Counter()
    try:
        for baseline in baseline_items:
            try:
                response = _run_query(service, baseline.question)
                failure_classification, failure_reason = _resolve_failure(
                    baseline=baseline,
                    response=response,
                )
                record = B2APreciseRegressionRecord(
                    plan_id=baseline.plan_id,
                    batch_id=baseline.batch_id,
                    question_id=baseline.question_id,
                    question=baseline.question,
                    expected_query_key=baseline.expected_query_key,
                    actual_query_key=response.get("query_plan", {}).get("query_key"),
                    expected_status_code=baseline.expected_status_code,
                    actual_status_code=(response.get("status") or {}).get("code", "NO_STATUS"),
                    passed=failure_classification is None,
                    failure_classification=failure_classification,
                    failure_reason=failure_reason,
                )
            except Exception as exc:  # noqa: BLE001
                record = B2APreciseRegressionRecord(
                    plan_id=baseline.plan_id,
                    batch_id=baseline.batch_id,
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
            if record.failure_classification:
                failure_counter[record.failure_classification] += 1
    finally:
        db.close()

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "batch_id": BATCH_ID,
        "result_database": "logistics_ai",
        "selection_rule": baseline_payload["selection_rule"],
        "summary": {
            "total_questions": len(records),
            "passed_questions": sum(1 for item in records if item.passed),
            "failed_questions": sum(1 for item in records if not item.passed),
            "failure_classification_breakdown": dict(failure_counter),
        },
        "items": [asdict(item) for item in records],
        "failed_items": [asdict(item) for item in records if not item.passed],
    }


def render_markdown(*, baseline_payload: dict[str, Any], report: dict[str, Any]) -> str:
    """渲染当前 B2A 批次精确断言回归文档。"""

    summary = report["summary"]
    lines = [
        f"# {report['batch_id']} B->A 新进 A 精确断言回归",
        "",
        "## 一、结论",
        "",
        (
            f"{report['batch_id']} 共纳管 **{summary['total_questions']}** 条 B->A 新迁入 A 题，"
            f"精确断言回归通过 **{summary['passed_questions']}** 条，"
            f"失败 **{summary['failed_questions']}** 条。"
        ),
        "",
        "## 二、标准答案来源与断言口径",
        "",
        "- 标准答案来源：当前 `logistics_ai` 数据快照，经正式 data-qa 主链路执行后固化。",
        "- 断言字段：`status.code`、`query_plan.query_key`、`answer_summary`、`result_table.columns`、`result_table.rows`。",
        "- 失败归因：query_key/status/columns 异常归为代码问题；answer_summary/rows 变化归为数据基线变化；预期 A 题实际进入 clarification/unsupported 时归为题目分层误判。",
        "",
        "## 三、题目清单",
        "",
        "| plan_id | 题号 | query_key | 断言字段 | 问题 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in baseline_payload["items"]:
        lines.append(
            f"| {item['plan_id']} | {item['question_id']} | {item['expected_query_key']} | "
            f"{'；'.join(item['assertion_fields'])} | {item['question']} |"
        )
    lines.extend(["", "## 四、未通过题", ""])
    if report["failed_items"]:
        for item in report["failed_items"]:
            lines.append(
                f"- {item['plan_id']} / {item['question_id']}：{item['failure_classification']}，{item['failure_reason']}"
            )
    else:
        lines.append("- 当前无未通过题。")
    lines.extend(
        [
            "",
            "## 五、边界",
            "",
            f"- 本轮只固化 {report['batch_id']} 已通过精确断言的新进 A 题，不扩 B/C 边界。",
            "- 未通过题不得纳入稳定精确基线，需回到总账迁移复核。",
            "- B/C 边界仍由规则层主导，不受本轮精确断言影响。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    """执行 B2A 精确断言基线刷新和回归。"""

    parser = argparse.ArgumentParser(description="903 B->A 新进 A 精确断言回归")
    parser.add_argument(
        "--batch-id",
        choices=["B2A-P1", "B2A-P2", "B2A-P3"],
        default=BATCH_ID,
        help="要执行的 B2A 精确断言批次。",
    )
    parser.add_argument(
        "--refresh-baseline",
        action="store_true",
        help="使用当前 data-qa 主链路刷新指定 B2A 批次的精确断言基线。",
    )
    args = parser.parse_args()
    _set_batch_context(args.batch_id)

    if args.refresh_baseline or not BASELINE_PATH.exists():
        baseline_payload = refresh_precise_baseline()
    else:
        baseline_payload = _load_json(BASELINE_PATH)

    report = evaluate_precise_regression()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC_PATH.write_text(render_markdown(baseline_payload=baseline_payload, report=report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

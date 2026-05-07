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


LEDGER_PATH = (
    PROJECT_ROOT
    / "backend/app/domains/logistics/config/logistics_903_master_ledger.json"
)
CONFIG_PATH = (
    PROJECT_ROOT
    / "backend/app/domains/logistics/config/logistics_a_stability_round3_questions.json"
)
BASELINE_PATH = (
    PROJECT_ROOT
    / "backend/app/domains/logistics/config/logistics_a_stability_round3_precise_baseline.json"
)
REPORT_PATH = (
    PROJECT_ROOT
    / "tmp/logistics_question_bank/logistics_a_stability_round3_regression_report.json"
)
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_A_STABILITY_ROUND3.md"


class NoopQueryLogRepository:
    """无副作用查询日志仓储。

    说明：
        1. Round3 仍然必须调用真实 data-qa 主链路；
        2. 但不应把回归执行写入正式业务查询历史；
        3. 因此这里继续统一注入空日志仓储。
    """

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        _ = db, payload
        return 0


@dataclass
class AStabilityRound3SelectionItem:
    """A-稳定增强池 Round3 选题配置。"""

    regression_id: str
    question_id: str
    question: str
    priority: str
    source_group: str
    family: str
    query_key: str | None
    standard_answer_source: str
    assertion_scope: str
    assertion_fields: list[str]
    selection_reason: str


@dataclass
class AStabilityRound3BaselineItem:
    """A-稳定增强池 Round3 精确断言基线。"""

    regression_id: str
    question_id: str
    question: str
    priority: str
    query_key: str | None
    standard_answer_source: str
    assertion_scope: str
    assertion_fields: list[str]
    expected_status_code: str
    expected_answer_summary: str
    expected_columns: list[str]
    expected_rows: list[dict[str, Any]]


@dataclass
class AStabilityRound3RegressionRecord:
    """A-稳定增强池 Round3 精确断言回归结果。"""

    regression_id: str
    question_id: str
    question: str
    priority: str
    expected_query_key: str | None
    actual_query_key: str | None
    expected_status_code: str
    actual_status_code: str
    passed: bool
    failure_classification: str | None
    failure_reason: str | None


def _load_json(path: Path) -> Any:
    """读取 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8"))


def refresh_selection_config(
    *,
    ledger_path: Path = LEDGER_PATH,
    output_path: Path = CONFIG_PATH,
) -> dict[str, Any]:
    """刷新 A-稳定增强池 Round3 选题配置。

    选题规则：
        1. 当前已经进入 A；
        2. 当前优先级为 P3；
        3. 当前仍未纳入更严格精确断言；
        4. 当前处于 Top200 范围内，作为 A 池收尾批统一纳管。
    """

    ledger_payload = _load_json(ledger_path)
    ledger_items = ledger_payload["items"]
    selected_rows = [
        item
        for item in ledger_items
        if item["current_status"] == "A"
        and not item["in_precise_assertion"]
        and item["current_priority"] == "P3"
        and item["in_top200"]
    ]
    selected_rows.sort(key=lambda item: (item["source_group"], item["question_id"]))

    items: list[AStabilityRound3SelectionItem] = []
    for index, item in enumerate(selected_rows, start=1):
        items.append(
            AStabilityRound3SelectionItem(
                regression_id=f"ASTABR3-{index:03d}",
                question_id=item["question_id"],
                question=item["question"],
                priority=item["current_priority"],
                source_group=item["source_group"],
                family=item["family"],
                query_key=item["current_query_key"],
                standard_answer_source=(
                    "logistics_ai snapshot via "
                    "scripts/logistics_a_stability_round3_regression.py --refresh-baseline"
                ),
                assertion_scope="answer_summary + result_table.columns + result_table.rows 精确快照断言",
                assertion_fields=["answer_summary", "result_table.columns", "result_table.rows"],
                selection_reason="当前已进入 A、业务优先级为 P3、尚未纳入更严格精确断言，作为 A-稳定增强池收尾批纳管。",
            )
        )

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "selection_rule": "当前已进入 A、优先级为 P3、已在 Top200、但仍未纳入更严格精确断言的题。",
        "summary": {
            "selected_questions": len(items),
        },
        "items": [asdict(item) for item in items],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _run_query(service: LogisticsDataQaService, question: str) -> dict[str, Any]:
    """执行单题查询并返回 JSON 响应。"""

    result = service.query(
        LogisticsDataQaQueryRequest(question=question),
        trace_id="logistics-a-stability-round3-regression",
    )
    return result.model_dump(mode="json")


def refresh_precise_baseline(
    *,
    config_path: Path = CONFIG_PATH,
    output_path: Path = BASELINE_PATH,
) -> dict[str, Any]:
    """刷新 A-稳定增强池 Round3 精确断言基线。"""

    config_items = _load_json(config_path)["items"]
    db = SessionLocal()
    service = LogisticsDataQaService(db=db, query_log_repository=NoopQueryLogRepository())
    baseline_items: list[AStabilityRound3BaselineItem] = []

    try:
        for item in config_items:
            response = _run_query(service, item["question"])
            baseline_items.append(
                AStabilityRound3BaselineItem(
                    regression_id=item["regression_id"],
                    question_id=item["question_id"],
                    question=item["question"],
                    priority=item["priority"],
                    query_key=response.get("query_plan", {}).get("query_key"),
                    standard_answer_source=item["standard_answer_source"],
                    assertion_scope=item["assertion_scope"],
                    assertion_fields=item["assertion_fields"],
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
        "selection_rule": "A-稳定增强池 Round3：当前已进入 A、优先级为 P3、尚未纳入更严格精确断言的 Top200 题。",
        "items": [asdict(item) for item in baseline_items],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _resolve_failure(
    *,
    baseline: AStabilityRound3BaselineItem,
    response: dict[str, Any],
) -> tuple[str | None, str | None]:
    """把精确断言失败归类为代码问题或数据基线变化。"""

    actual_query_key = response.get("query_plan", {}).get("query_key")
    actual_status_code = (response.get("status") or {}).get("code", "NO_STATUS")
    if actual_query_key != baseline.query_key:
        return "代码问题", f"预期 query_key={baseline.query_key}，实际为 {actual_query_key}"
    if actual_status_code != baseline.expected_status_code:
        return "代码问题", f"预期状态码={baseline.expected_status_code}，实际为 {actual_status_code}"

    result_table = response.get("result_table") or {}
    actual_columns = result_table.get("columns", [])
    actual_rows = result_table.get("rows", [])
    if response.get("answer_summary", "") != baseline.expected_answer_summary:
        return "数据基线变化", "answer_summary 与当前精确断言基线不一致"
    if actual_columns != baseline.expected_columns:
        return "代码问题", "result_table.columns 结构发生变化"
    if actual_rows != baseline.expected_rows:
        return "数据基线变化", "result_table.rows 与当前精确断言基线不一致"
    return None, None


def evaluate_precise_regression(
    *,
    baseline_path: Path = BASELINE_PATH,
) -> dict[str, Any]:
    """执行 A-稳定增强池 Round3 精确断言回归。"""

    baseline_payload = _load_json(baseline_path)
    baseline_items = [AStabilityRound3BaselineItem(**item) for item in baseline_payload["items"]]

    db = SessionLocal()
    service = LogisticsDataQaService(db=db, query_log_repository=NoopQueryLogRepository())
    records: list[AStabilityRound3RegressionRecord] = []
    failure_counter: Counter[str] = Counter()
    try:
        for baseline in baseline_items:
            try:
                response = _run_query(service, baseline.question)
                failure_classification, failure_reason = _resolve_failure(
                    baseline=baseline,
                    response=response,
                )
                record = AStabilityRound3RegressionRecord(
                    regression_id=baseline.regression_id,
                    question_id=baseline.question_id,
                    question=baseline.question,
                    priority=baseline.priority,
                    expected_query_key=baseline.query_key,
                    actual_query_key=response.get("query_plan", {}).get("query_key"),
                    expected_status_code=baseline.expected_status_code,
                    actual_status_code=(response.get("status") or {}).get("code", "NO_STATUS"),
                    passed=failure_classification is None,
                    failure_classification=failure_classification,
                    failure_reason=failure_reason,
                )
            except Exception as exc:  # noqa: BLE001
                record = AStabilityRound3RegressionRecord(
                    regression_id=baseline.regression_id,
                    question_id=baseline.question_id,
                    question=baseline.question,
                    priority=baseline.priority,
                    expected_query_key=baseline.query_key,
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


def render_markdown(
    *,
    selection_payload: dict[str, Any],
    report: dict[str, Any],
) -> str:
    """生成 A-稳定增强池 Round3 文档。"""

    summary = report["summary"]
    lines: list[str] = []
    lines.append("# A-稳定增强池 Round3 精确断言回归")
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    lines.append(
        f"当前 A-稳定增强池 Round3 共纳管 **{summary['total_questions']}** 条 P3 高价值 A 题，"
        f"精确断言回归结果为：通过 **{summary['passed_questions']}** 条，"
        f"失败 **{summary['failed_questions']}** 条。"
    )
    lines.append("")
    lines.append("## 选题规则")
    lines.append("")
    lines.append(
        "- 当前已进入 A；当前优先级为 P3；已在 Top200；但尚未纳入更严格精确断言。"
    )
    lines.append("")
    lines.append("## 题目清单")
    lines.append("")
    lines.append("| 回归编号 | 题号 | 优先级 | query_key | 断言口径 | 断言字段 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for item in selection_payload["items"]:
        lines.append(
            f"| {item['regression_id']} | {item['question_id']} | {item['priority']} | "
            f"{item['query_key']} | {item['assertion_scope']} | {'；'.join(item['assertion_fields'])} |"
        )
    lines.append("")
    lines.append("## 失败归因规则")
    lines.append("")
    lines.append("- `代码问题`：query_key 错误、状态码异常、结果结构变化、执行异常。")
    lines.append("- `数据基线变化`：answer_summary 或 result_table.rows 与当前精确断言基线不一致。")
    lines.append("")
    if report["failed_items"]:
        lines.append("## 当前未通过题")
        lines.append("")
        for item in report["failed_items"]:
            lines.append(
                f"- {item['regression_id']} / {item['question_id']}：{item['failure_classification']}，{item['failure_reason']}"
            )
        lines.append("")
    else:
        lines.append("## 当前未通过题")
        lines.append("")
        lines.append("- 当前无未通过题。")
        lines.append("")
    lines.append("## 当前边界")
    lines.append("")
    lines.append("- 这轮把 A-稳定增强池剩余 Top200 题全部纳入更严格精确断言，作为当前 A 池收尾批。")
    lines.append("- 后续若继续推进，应优先处理非 Top200 的 A 池长尾题，或转入项目级文档同步。")
    return "\n".join(lines) + "\n"


def main() -> None:
    """执行 A-稳定增强池 Round3 选题、基线刷新和精确断言回归。"""

    parser = argparse.ArgumentParser(description="A-稳定增强池 Round3 精确断言回归")
    parser.add_argument(
        "--refresh-selection",
        action="store_true",
        help="根据当前 903 总台账刷新 Round3 选题配置。",
    )
    parser.add_argument(
        "--refresh-baseline",
        action="store_true",
        help="使用当前 logistics_ai 主链路结果刷新精确断言基线。",
    )
    args = parser.parse_args()

    if args.refresh_selection or not CONFIG_PATH.exists():
        selection_payload = refresh_selection_config()
    else:
        selection_payload = _load_json(CONFIG_PATH)

    if args.refresh_baseline or not BASELINE_PATH.exists():
        refresh_precise_baseline()

    report = evaluate_precise_regression()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC_PATH.write_text(render_markdown(selection_payload=selection_payload, report=report), encoding="utf-8")

    print(
        json.dumps(
            {
                "selected": report["summary"]["total_questions"],
                "passed": report["summary"]["passed_questions"],
                "failed": report["summary"]["failed_questions"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

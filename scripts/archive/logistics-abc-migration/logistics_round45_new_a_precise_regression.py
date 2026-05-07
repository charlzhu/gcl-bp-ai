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


CONFIG_PATH = (
    PROJECT_ROOT
    / "backend/app/domains/logistics/config/logistics_round45_new_a_precise_questions.json"
)
REPORT_PATH = (
    PROJECT_ROOT
    / "tmp/logistics_question_bank/logistics_round45_new_a_precise_regression_report.json"
)
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_TOP200_ROUND45_NEW_A_PRECISE_REGRESSION.md"


class NoopQueryLogRepository:
    """无副作用查询日志仓储。

    说明：
        1. 精确断言回归需要调用真实 data-qa 主链路；
        2. 但不应把回归脚本的执行记录写进正式业务历史；
        3. 因此这里统一注入空实现。
    """

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        _ = db, payload
        return 0


@dataclass
class Round45PreciseRecord:
    """Round4 / Round5 新进 A 题精确断言结果。"""

    regression_id: str
    source_round: str
    question_id: str
    question: str
    query_key: str
    standard_answer_source: str
    assertion_scope: str
    assertion_fields: list[str]
    actual_query_key: str | None
    status_code: str
    passed: bool
    failure_classification: str | None
    failure_reason: str | None
    field_mismatches: list[str]
    answer_summary: str
    row_count: int


def _normalize_value(value: Any) -> str:
    """把结果字段统一转成可比较字符串。"""
    if value is None:
        return "None"
    return str(value)


def _compare_expected_row(
    *,
    expected_row: dict[str, Any],
    actual_rows: list[dict[str, Any]],
) -> list[str]:
    """比较首行关键字段是否与精确基线一致。"""
    if not actual_rows:
        return ["result_table.rows[0] 缺失"]
    actual_row = actual_rows[0]
    mismatches: list[str] = []
    for field_name, expected_value in expected_row.items():
        actual_value = actual_row.get(field_name)
        if _normalize_value(actual_value) != _normalize_value(expected_value):
            mismatches.append(
                f"{field_name}: expected={expected_value}, actual={actual_value}"
            )
    return mismatches


def _resolve_failure(
    *,
    expected_query_key: str,
    actual_query_key: str | None,
    status_code: str,
    supported: bool,
    needs_clarification: bool,
    answer_summary_matches: bool,
    field_mismatches: list[str],
) -> tuple[str | None, str | None]:
    """把失败归因为代码问题或数据基线变化。"""
    if actual_query_key != expected_query_key:
        return "代码问题", f"预期 query_key={expected_query_key}，实际为 {actual_query_key}"
    if needs_clarification:
        return "代码问题", "题目意外进入澄清态"
    if not supported:
        return "代码问题", "题目意外进入不支持态"
    if status_code != LogisticsErrorCodeRegistry.OK:
        return "代码问题", f"返回状态码异常：{status_code}"
    if not answer_summary_matches:
        return "数据基线变化", "answer_summary 与当前精确断言基线不一致"
    if field_mismatches:
        return "数据基线变化", "关键结果字段与当前精确断言基线不一致：" + "; ".join(field_mismatches)
    return None, None


def evaluate_round45_precise_regression(
    *,
    config_path: Path = CONFIG_PATH,
) -> dict[str, Any]:
    """执行 Round4 / Round5 新进 A 题精确断言回归。"""
    config_items = json.loads(config_path.read_text(encoding="utf-8"))

    db = SessionLocal()
    service = LogisticsDataQaService(db=db, query_log_repository=NoopQueryLogRepository())
    records: list[Round45PreciseRecord] = []
    counter: Counter[str] = Counter()

    try:
        for item in config_items:
            try:
                result = service.query(
                    LogisticsDataQaQueryRequest(question=item["question"]),
                    trace_id="round45-new-a-precise-regression",
                )
                response_dict = result.model_dump(mode="json")
                actual_query_key = response_dict.get("query_plan", {}).get("query_key")
                status_code = (response_dict.get("status") or {}).get("code", "NO_STATUS")
                answer_summary = response_dict.get("answer_summary", "")
                actual_rows = (response_dict.get("result_table") or {}).get("rows", [])
                answer_summary_matches = answer_summary == item["expected_answer_summary"]
                field_mismatches = _compare_expected_row(
                    expected_row=item["expected_row_assertions"],
                    actual_rows=actual_rows,
                )
                failure_classification, failure_reason = _resolve_failure(
                    expected_query_key=item["query_key"],
                    actual_query_key=actual_query_key,
                    status_code=status_code,
                    supported=response_dict.get("supported", True),
                    needs_clarification=response_dict.get("needs_clarification", False),
                    answer_summary_matches=answer_summary_matches,
                    field_mismatches=field_mismatches,
                )
                record = Round45PreciseRecord(
                    regression_id=item["regression_id"],
                    source_round=item["source_round"],
                    question_id=item["question_id"],
                    question=item["question"],
                    query_key=item["query_key"],
                    standard_answer_source=item["standard_answer_source"],
                    assertion_scope=item["assertion_scope"],
                    assertion_fields=item["assertion_fields"],
                    actual_query_key=actual_query_key,
                    status_code=status_code,
                    passed=failure_classification is None,
                    failure_classification=failure_classification,
                    failure_reason=failure_reason,
                    field_mismatches=field_mismatches,
                    answer_summary=answer_summary,
                    row_count=len(actual_rows),
                )
            except Exception as exc:  # noqa: BLE001
                record = Round45PreciseRecord(
                    regression_id=item["regression_id"],
                    source_round=item["source_round"],
                    question_id=item["question_id"],
                    question=item["question"],
                    query_key=item["query_key"],
                    standard_answer_source=item["standard_answer_source"],
                    assertion_scope=item["assertion_scope"],
                    assertion_fields=item["assertion_fields"],
                    actual_query_key=None,
                    status_code="EXCEPTION",
                    passed=False,
                    failure_classification="代码问题",
                    failure_reason=f"执行异常：{exc}",
                    field_mismatches=[],
                    answer_summary="",
                    row_count=0,
                )
            records.append(record)
            counter["total"] += 1
            counter["passed" if record.passed else "failed"] += 1
            counter[record.status_code] += 1
            if record.failure_classification:
                counter[f"class::{record.failure_classification}"] += 1
    finally:
        db.close()

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "result_database": "logistics_ai",
        "selection_rule": "Round4 / Round5 新推进进 A 的 5 条题单独抽出，做更严格精确断言回归。",
        "summary": {
            "total_questions": counter["total"],
            "passed_questions": counter["passed"],
            "failed_questions": counter["failed"],
            "status_code_breakdown": {
                key: value
                for key, value in counter.items()
                if key not in {"total", "passed", "failed"} and not key.startswith("class::")
            },
            "failure_classification_breakdown": {
                key.replace("class::", ""): value
                for key, value in counter.items()
                if key.startswith("class::")
            },
        },
        "items": [asdict(item) for item in records],
        "failed_items": [asdict(item) for item in records if not item.passed],
    }


def render_markdown(report: dict[str, Any]) -> str:
    """生成 Round4 / Round5 新进 A 题精确断言回归文档。"""
    summary = report["summary"]
    lines: list[str] = []
    lines.append("# Round4 / Round5 新进 A 题精确断言回归")
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    lines.append(
        f"当前 Round4 / Round5 新进 A 题共 **{summary['total_questions']}** 条，"
        f"精确断言回归结果为：通过 **{summary['passed_questions']}** 条，"
        f"失败 **{summary['failed_questions']}** 条。"
    )
    lines.append("")
    lines.append("## 题目清单")
    lines.append("")
    lines.append("| 回归编号 | 来源轮次 | 题号 | query_key | 标准答案来源 | 断言口径 | 断言字段 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for item in report["items"]:
        lines.append(
            f"| {item['regression_id']} | {item['source_round']} | {item['question_id']} | "
            f"{item['query_key']} | {item['standard_answer_source']} | {item['assertion_scope']} | "
            f"{'；'.join(item['assertion_fields'])} |"
        )
    lines.append("")
    lines.append("## 失败归因规则")
    lines.append("")
    lines.append("- `代码问题`：query_key 错误、误入澄清/不支持、状态码异常、执行异常。")
    lines.append("- `数据基线变化`：链路执行成功，但 answer_summary 或关键结果字段与当前精确断言基线不一致。")
    lines.append("")
    if report["failed_items"]:
        lines.append("## 当前未通过题")
        lines.append("")
        for item in report["failed_items"]:
            lines.append(
                f"- {item['regression_id']} / {item['question_id']}：{item['failure_classification']}，"
                f"{item['failure_reason']}"
            )
    else:
        lines.append("## 当前未通过题")
        lines.append("")
        lines.append("- 当前无未通过题。")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    """执行脚本入口。"""
    parser = argparse.ArgumentParser(description="Round4 / Round5 新进 A 题精确断言回归")
    parser.add_argument(
        "--config",
        default=str(CONFIG_PATH),
        help="Round4 / Round5 新进 A 题精确断言配置路径",
    )
    parser.add_argument(
        "--output",
        default=str(REPORT_PATH),
        help="JSON 报告输出路径",
    )
    parser.add_argument(
        "--doc-output",
        default=str(DOC_PATH),
        help="Markdown 文档输出路径",
    )
    args = parser.parse_args()

    report = evaluate_round45_precise_regression(config_path=Path(args.config))
    output_path = Path(args.output)
    doc_path = Path(args.doc_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    doc_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

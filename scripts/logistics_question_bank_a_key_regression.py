from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, asdict
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
from scripts.logistics_data_qa_mvp import _validate_question_result


KEY_QUESTIONS_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/question_bank_a_key_questions.json"
ACCEPTANCE_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/data_qa_acceptance_questions.json"
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_question_bank_A_key_regression_report.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_QUESTION_BANK_A_REGRESSION.md"


class NoopQueryLogRepository:
    """无副作用查询日志仓储。

    说明：
        1. 精确回归需要调用真实 data-qa 主链路；
        2. 但不应该把回归问题写进正式业务历史；
        3. 因此脚本内统一注入空日志仓储。
    """

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        _ = db, payload
        return 0


@dataclass
class GoldenRegressionRecord:
    """关键题精确答案断言结果。"""

    regression_id: str
    acceptance_id: str
    question_bank_id: str
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
    missing_expected_tokens: list[str]
    answer_summary: str
    row_count: int


def evaluate_key_questions(
    *,
    key_questions_path: Path = KEY_QUESTIONS_PATH,
    acceptance_path: Path = ACCEPTANCE_PATH,
) -> dict[str, Any]:
    """执行 A 类关键题精确断言回归。"""
    key_questions = json.loads(key_questions_path.read_text(encoding="utf-8"))
    acceptance_items = {
        item["id"]: item for item in json.loads(acceptance_path.read_text(encoding="utf-8"))
    }

    db = SessionLocal()
    service = LogisticsDataQaService(db=db, query_log_repository=NoopQueryLogRepository())
    records: list[GoldenRegressionRecord] = []
    counter: Counter[str] = Counter()

    try:
        for item in key_questions:
            acceptance_item = acceptance_items[item["acceptance_id"]]
            record = _run_single_key_question(
                service=service,
                key_item=item,
                acceptance_item=acceptance_item,
            )
            records.append(record)
            counter["total"] += 1
            counter["passed" if record.passed else "failed"] += 1
            counter[record.status_code] += 1
            if record.failure_classification:
                counter[f"class::{record.failure_classification}"] += 1
    finally:
        db.close()

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "result_database": "logistics_ai",
        "selection_rule": "当前第一批关键 A 题直接选用已通过的 20 条核心验收题，作为高价值黄金题集。",
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
    return payload


def _run_single_key_question(
    *,
    service: LogisticsDataQaService,
    key_item: dict[str, Any],
    acceptance_item: dict[str, Any],
) -> GoldenRegressionRecord:
    """执行单条关键题回归，并给出失败归因。"""
    try:
        result = service.query(
            LogisticsDataQaQueryRequest(question=key_item["question"]),
            trace_id="question-bank-a-key-regression",
        )
        response_dict = result.model_dump(mode="json")
        passed, missing = _validate_question_result(acceptance_item, response_dict)
        actual_query_key = response_dict.get("query_plan", {}).get("query_key")
        status_code = (response_dict.get("status") or {}).get("code", "NO_STATUS")
        failure_classification, failure_reason = _resolve_failure(
            expected_query_key=key_item["query_key"],
            actual_query_key=actual_query_key,
            status_code=status_code,
            supported=response_dict.get("supported", True),
            needs_clarification=response_dict.get("needs_clarification", False),
            missing_expected_tokens=missing,
        )
        return GoldenRegressionRecord(
            regression_id=key_item["regression_id"],
            acceptance_id=key_item["acceptance_id"],
            question_bank_id=key_item["question_bank_id"],
            question=key_item["question"],
            query_key=key_item["query_key"],
            standard_answer_source=key_item["standard_answer_source"],
            assertion_scope=key_item["assertion_scope"],
            assertion_fields=key_item["assertion_fields"],
            actual_query_key=actual_query_key,
            status_code=status_code,
            passed=passed and failure_classification is None,
            failure_classification=failure_classification,
            failure_reason=failure_reason,
            missing_expected_tokens=missing,
            answer_summary=response_dict.get("answer_summary", ""),
            row_count=len((response_dict.get("result_table") or {}).get("rows", [])),
        )
    except Exception as exc:  # noqa: BLE001
        return GoldenRegressionRecord(
            regression_id=key_item["regression_id"],
            acceptance_id=key_item["acceptance_id"],
            question_bank_id=key_item["question_bank_id"],
            question=key_item["question"],
            query_key=key_item["query_key"],
            standard_answer_source=key_item["standard_answer_source"],
            assertion_scope=key_item["assertion_scope"],
            assertion_fields=key_item["assertion_fields"],
            actual_query_key=None,
            status_code="EXCEPTION",
            passed=False,
            failure_classification="代码问题",
            failure_reason=f"执行异常：{exc}",
            missing_expected_tokens=[],
            answer_summary="",
            row_count=0,
        )


def _resolve_failure(
    *,
    expected_query_key: str,
    actual_query_key: str | None,
    status_code: str,
    supported: bool,
    needs_clarification: bool,
    missing_expected_tokens: list[str],
) -> tuple[str | None, str | None]:
    """把失败归因为代码问题或数据基线变化。"""
    if actual_query_key != expected_query_key:
        return "代码问题", f"预期 query_key={expected_query_key}，实际为 {actual_query_key}"
    if needs_clarification:
        return "代码问题", "关键 A 题意外进入澄清态"
    if not supported:
        return "代码问题", "关键 A 题意外进入不支持态"
    if status_code != LogisticsErrorCodeRegistry.OK:
        return "代码问题", f"返回状态码异常：{status_code}"
    if missing_expected_tokens:
        return "数据基线变化", "与当前官方验收基线不一致：" + ", ".join(missing_expected_tokens)
    return None, None


def render_markdown(report: dict[str, Any]) -> str:
    """生成关键题精确断言回归文档。"""
    lines: list[str] = []
    lines.append("# 物流域 A 类关键题精确答案断言回归")
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    summary = report["summary"]
    lines.append(
        f"当前第一批关键 A 题共 **{summary['total_questions']}** 条，"
        f"精确答案断言回归结果为：通过 **{summary['passed_questions']}** 条，"
        f"失败 **{summary['failed_questions']}** 条。"
    )
    lines.append("")
    lines.append("当前这批关键题直接选用已通过的 20 条核心验收题，原因是它们：")
    lines.append("- 覆盖了当前最核心的稳定 query_key；")
    lines.append("- 已有正式基线与业务确认口径；")
    lines.append("- 适合作为从行为级回归升级到黄金答案断言的第一批题集。")
    lines.append("")
    lines.append("## 关键题清单")
    lines.append("")
    lines.append("| 回归编号 | 题号 | 题库编号 | query_key | 标准答案来源 | 断言口径 | 断言字段 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for item in report["items"]:
        lines.append(
            f"| {item['regression_id']} | {item['acceptance_id']} | {item['question_bank_id']} | "
            f"{item['query_key']} | {item['standard_answer_source']} | {item['assertion_scope']} | "
            f"{'；'.join(item['assertion_fields'])} |"
        )
    lines.append("")
    lines.append("## 失败归因规则")
    lines.append("")
    lines.append("- `代码问题`：query_key 错误、误入澄清/不支持、状态码异常、执行异常。")
    lines.append("- `数据基线变化`：链路执行成功，但结果与当前官方验收基线不一致。")
    lines.append("")
    if report["failed_items"]:
        lines.append("## 当前未通过题")
        lines.append("")
        for item in report["failed_items"]:
            lines.append(
                f"- {item['regression_id']} / {item['acceptance_id']}：{item['failure_classification']}，"
                f"{item['failure_reason']}"
            )
        lines.append("")
    else:
        lines.append("## 当前未通过题")
        lines.append("")
        lines.append("- 当前无未通过题。")
        lines.append("")
    lines.append("## 当前边界")
    lines.append("")
    lines.append("- 物流数据问答 MVP 已收口。")
    lines.append("- A 类能力已经开始进入精确答案断言回归阶段。")
    lines.append("- B/C 类响应策略继续保持系统级固化，不回退。")
    lines.append("- 但物流域 903 条题库仍未完全收口。")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="物流域 A 类关键题精确答案断言回归")
    parser.add_argument("--output", default=str(REPORT_PATH), help="JSON 报告输出路径")
    parser.add_argument("--doc-output", default=str(DOC_PATH), help="Markdown 文档输出路径")
    args = parser.parse_args()

    report = evaluate_key_questions()
    output_path = Path(args.output)
    doc_path = Path(args.doc_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    doc_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

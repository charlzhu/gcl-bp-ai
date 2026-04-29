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


class NoopQueryLogRepository:
    """无副作用查询日志仓储。

    说明：
        1. A 类自动回归需要真实调用当前 data-qa 链路；
        2. 但本轮不希望把 75 条回归问题全部写进正式查询历史；
        3. 因此在脚本内注入空日志仓储，避免污染业务查询记录。
    """

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        _ = db, payload
        return 0


@dataclass
class RegressionRecord:
    """A 类自动回归单题结果。"""

    question_id: str
    question: str
    source_group: str
    expected_query_key: str | None
    actual_query_key: str | None
    status_code: str
    status_message: str
    passed: bool
    failure_reason: str | None
    answer_summary: str
    row_count: int


def evaluate_a_questions(classification_path: Path) -> dict[str, Any]:
    """执行 A 类题自动回归。

    返回：
        包含汇总统计、失败题清单和逐题结果的结构化字典。
    """
    payload = json.loads(classification_path.read_text(encoding="utf-8"))
    a_items = [item for item in payload["items"] if item["classification"] == "A"]

    db = SessionLocal()
    service = LogisticsDataQaService(db=db, query_log_repository=NoopQueryLogRepository())
    records: list[RegressionRecord] = []
    counters: Counter[str] = Counter()

    try:
        for item in a_items:
            record = _run_single_question(service=service, item=item)
            records.append(record)
            counters["total"] += 1
            counters["passed" if record.passed else "failed"] += 1
            counters[record.status_code] += 1
            if record.failure_reason:
                counters[f"failure::{record.failure_reason}"] += 1
    finally:
        db.close()

    failed_records = [asdict(record) for record in records if not record.passed]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_classification_json": str(classification_path),
        "assertion_rule": {
            "description": "A 类题当前按真实 data-qa 链路执行，要求 query_key 命中预期、返回成功态且非澄清/不支持/异常。",
            "allowed_status_codes": [LogisticsErrorCodeRegistry.OK],
        },
        "summary": {
            "total_questions": counters["total"],
            "passed_questions": counters["passed"],
            "failed_questions": counters["failed"],
            "status_code_breakdown": {
                key: value
                for key, value in counters.items()
                if key not in {"total", "passed", "failed"} and not key.startswith("failure::")
            },
            "failure_reason_breakdown": {
                key.replace("failure::", ""): value
                for key, value in counters.items()
                if key.startswith("failure::")
            },
        },
        "failed_questions": failed_records,
        "items": [asdict(record) for record in records],
    }


def _run_single_question(service: LogisticsDataQaService, item: dict[str, Any]) -> RegressionRecord:
    """执行单题回归并生成失败原因。"""
    try:
        result = service.query(LogisticsDataQaQueryRequest(question=item["question"]), trace_id="question-bank-a-regression")
        expected_query_key = item.get("query_key")
        actual_query_key = result.query_plan.query_key
        status_code = result.status.code if result.status else "NO_STATUS"
        status_message = result.status.message if result.status else "当前未返回状态码。"
        failure_reason = _resolve_failure_reason(
            expected_query_key=expected_query_key,
            actual_query_key=actual_query_key,
            status_code=status_code,
            supported=result.supported,
            needs_clarification=result.needs_clarification,
            row_count=len(result.result_table.rows),
        )
        return RegressionRecord(
            question_id=item["question_id"],
            question=item["question"],
            source_group=item["source_group"],
            expected_query_key=expected_query_key,
            actual_query_key=actual_query_key,
            status_code=status_code,
            status_message=status_message,
            passed=failure_reason is None,
            failure_reason=failure_reason,
            answer_summary=result.answer_summary,
            row_count=len(result.result_table.rows),
        )
    except Exception as exc:  # noqa: BLE001
        return RegressionRecord(
            question_id=item["question_id"],
            question=item["question"],
            source_group=item["source_group"],
            expected_query_key=item.get("query_key"),
            actual_query_key=None,
            status_code="EXCEPTION",
            status_message=str(exc),
            passed=False,
            failure_reason="execution_exception",
            answer_summary="",
            row_count=0,
        )


def _resolve_failure_reason(
    *,
    expected_query_key: str | None,
    actual_query_key: str | None,
    status_code: str,
    supported: bool,
    needs_clarification: bool,
    row_count: int,
) -> str | None:
    """按统一规则生成单题失败原因。"""
    if expected_query_key and actual_query_key != expected_query_key:
        return "query_key_mismatch"
    if needs_clarification:
        return "clarification_returned"
    if not supported:
        return "unsupported_returned"
    if status_code != LogisticsErrorCodeRegistry.OK:
        return f"unexpected_status::{status_code}"
    if row_count <= 0:
        return "empty_result"
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="物流域 A 类 75 条自动回归")
    parser.add_argument(
        "--classification-json",
        default="/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/tmp/logistics_question_bank/logistics_question_bank_classification.json",
        help="题库分层 JSON 路径",
    )
    parser.add_argument(
        "--output",
        default="/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/tmp/logistics_question_bank/logistics_question_bank_A_regression_report.json",
        help="A 类自动回归报告输出路径",
    )
    args = parser.parse_args()

    classification_path = Path(args.classification_json)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = evaluate_a_questions(classification_path)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

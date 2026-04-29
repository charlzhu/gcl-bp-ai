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


QUESTION_SET_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b2a_a_regression_questions.json"
)
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b2a_a_regression_report.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B2A_A_REGRESSION.md"


class NoopQueryLogRepository:
    """无副作用查询日志仓储。

    参数：
        db: data-qa 服务传入的数据库会话。
        payload: 原本要写入查询日志的内容。

    返回：
        固定返回 0，表示不写入业务查询历史。

    说明：
        B->A 新增 A 行为回归必须真实调用 data-qa 主链路，
        但批量回归不应污染用户查询历史，因此注入空日志仓储。
    """

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        """忽略查询日志写入请求。"""

        _ = db, payload
        return 0


@dataclass
class B2AARegressionRecord:
    """B->A 新增 A 行为回归单题结果。"""

    question_id: str
    question: str
    source_group: str
    family: str
    expected_query_key: str
    actual_query_key: str | None
    expected_status_code: str
    actual_status_code: str
    supported: bool
    needs_clarification: bool
    row_count: int
    passed: bool
    failure_reason: str | None
    answer_summary: str


def _load_json(path: Path) -> Any:
    """读取 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_failure(
    *,
    expected_query_key: str,
    actual_query_key: str | None,
    expected_status_code: str,
    actual_status_code: str,
    supported: bool,
    needs_clarification: bool,
    row_count: int,
) -> str | None:
    """判定行为回归失败原因。

    返回：
        None 表示通过；字符串表示明确失败原因。
    """

    if actual_query_key != expected_query_key:
        return "query_key_mismatch"
    if needs_clarification:
        return "clarification_returned"
    if not supported:
        return "unsupported_returned"
    if actual_status_code != expected_status_code:
        return f"unexpected_status::{actual_status_code}"
    if actual_status_code != LogisticsErrorCodeRegistry.OK:
        return f"unexpected_status::{actual_status_code}"
    if row_count <= 0:
        return "empty_result"
    return None


def _run_single(service: LogisticsDataQaService, item: dict[str, Any]) -> B2AARegressionRecord:
    """执行单题真实 data-qa 行为回归。"""

    try:
        result = service.query(
            LogisticsDataQaQueryRequest(question=item["question"]),
            trace_id="logistics-903-b2a-a-regression",
        )
        actual_query_key = result.query_plan.query_key
        actual_status_code = result.status.code if result.status else "NO_STATUS"
        row_count = len(result.result_table.rows)
        failure_reason = _resolve_failure(
            expected_query_key=item["expected_query_key"],
            actual_query_key=actual_query_key,
            expected_status_code=item["expected_status_code"],
            actual_status_code=actual_status_code,
            supported=bool(result.supported),
            needs_clarification=bool(result.needs_clarification),
            row_count=row_count,
        )
        return B2AARegressionRecord(
            question_id=item["question_id"],
            question=item["question"],
            source_group=item["source_group"],
            family=item["family"],
            expected_query_key=item["expected_query_key"],
            actual_query_key=actual_query_key,
            expected_status_code=item["expected_status_code"],
            actual_status_code=actual_status_code,
            supported=bool(result.supported),
            needs_clarification=bool(result.needs_clarification),
            row_count=row_count,
            passed=failure_reason is None,
            failure_reason=failure_reason,
            answer_summary=result.answer_summary,
        )
    except Exception as exc:  # noqa: BLE001
        return B2AARegressionRecord(
            question_id=item["question_id"],
            question=item["question"],
            source_group=item["source_group"],
            family=item["family"],
            expected_query_key=item["expected_query_key"],
            actual_query_key=None,
            expected_status_code=item["expected_status_code"],
            actual_status_code="EXCEPTION",
            supported=False,
            needs_clarification=False,
            row_count=0,
            passed=False,
            failure_reason=f"execution_exception::{exc}",
            answer_summary="",
        )


def evaluate(question_set_path: Path) -> dict[str, Any]:
    """执行 85 条 B->A 新增 A 行为回归。

    参数：
        question_set_path: 新增 A 行为回归题集路径。

    返回：
        包含汇总统计和逐题结果的报告。
    """

    question_set = _load_json(question_set_path)
    db = SessionLocal()
    service = LogisticsDataQaService(db=db, query_log_repository=NoopQueryLogRepository())
    records: list[B2AARegressionRecord] = []
    try:
        for item in question_set["items"]:
            records.append(_run_single(service, item))
    finally:
        db.close()

    failure_counter: Counter[str] = Counter(
        record.failure_reason for record in records if record.failure_reason
    )
    status_counter: Counter[str] = Counter(record.actual_status_code for record in records)
    query_key_counter: Counter[str] = Counter(record.actual_query_key or "NONE" for record in records)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_question_set": str(question_set_path),
        "summary": {
            "total_questions": len(records),
            "passed_questions": sum(1 for record in records if record.passed),
            "failed_questions": sum(1 for record in records if not record.passed),
            "status_code_breakdown": dict(status_counter),
            "query_key_breakdown": dict(query_key_counter),
            "failure_reason_breakdown": dict(failure_counter),
        },
        "items": [asdict(record) for record in records],
        "failed_items": [asdict(record) for record in records if not record.passed],
    }
    return report


def _render_doc(report: dict[str, Any]) -> str:
    """渲染行为回归 Markdown 报告。"""

    summary = report["summary"]
    lines = [
        "# 903 B->A 新增 A 行为回归",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 一、结论",
        "",
        (
            f"本轮新增 A 行为回归共 `{summary['total_questions']}` 条，"
            f"通过 `{summary['passed_questions']}` 条，失败 `{summary['failed_questions']}` 条。"
        ),
        "",
        "## 二、回归规则",
        "",
        "- 真实调用当前物流 data-qa 主链路。",
        "- 要求 query_key 命中预期。",
        "- 要求状态码 OK、supported=true、needs_clarification=false。",
        "- 要求结果表非空。",
        "",
        "## 三、query_key 分布",
        "",
    ]
    for key, value in summary["query_key_breakdown"].items():
        lines.append(f"- `{key}`：`{value}`")
    lines.extend(["", "## 四、未通过题", ""])
    if report["failed_items"]:
        for item in report["failed_items"]:
            lines.append(f"- {item['question_id']}：{item['failure_reason']} | {item['question']}")
    else:
        lines.append("- 当前无未通过题。")
    lines.extend(["", "## 五、代表题", "", "| 题号 | query_key | 问题 |", "| --- | --- | --- |"])
    for item in report["items"][:15]:
        lines.append(f"| {item['question_id']} | {item['actual_query_key']} | {item['question']} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    """命令行入口。"""

    parser = argparse.ArgumentParser(description="903 B->A 新增 A 行为回归")
    parser.add_argument(
        "--question-set",
        default=str(QUESTION_SET_PATH),
        help="B->A 新增 A 行为回归题集路径。",
    )
    parser.add_argument(
        "--output",
        default=str(REPORT_PATH),
        help="行为回归报告输出路径。",
    )
    parser.add_argument(
        "--doc-output",
        default=str(DOC_PATH),
        help="行为回归 Markdown 文档输出路径。",
    )
    args = parser.parse_args()
    report = evaluate(Path(args.question_set))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    doc_output_path = Path(args.doc_output)
    doc_output_path.parent.mkdir(parents=True, exist_ok=True)
    doc_output_path.write_text(_render_doc(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

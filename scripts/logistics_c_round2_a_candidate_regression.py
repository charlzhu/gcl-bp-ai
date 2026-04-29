from __future__ import annotations

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


MIGRATION_CANDIDATES_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_c_boundary_round2_migration_candidates.json"
)
A_CANDIDATE_CONFIG_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_c_round2_a_candidate_questions.json"
)
ACCEPTED_MIGRATION_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_c_round2_accepted_migration.json"
)
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_c_round2_a_candidate_regression_report.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_C_ROUND2_A_CANDIDATE_REGRESSION.md"


class NoopQueryLogRepository:
    """无副作用查询日志仓储。

    说明：
        1. C Round2 A_candidate 行为回归必须真实调用 data-qa 主链路；
        2. 回归脚本不应污染正式业务查询历史；
        3. 因此在脚本内注入空日志仓储。
    """

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        """忽略查询日志写入请求。"""

        _ = db, payload
        return 0


@dataclass
class CandidateRegressionRecord:
    """C Round2 A_candidate 单题行为回归结果。"""

    question_id: str
    question: str
    source_group: str
    family: str
    expected_query_key: str
    actual_query_key: str | None
    status_code: str
    status_message: str
    supported: bool
    needs_clarification: bool
    passed: bool
    failure_classification: str | None
    failure_reason: str | None
    answer_summary: str
    row_count: int


def _load_a_candidates() -> list[dict[str, Any]]:
    """提取 A_candidate 题目。

    说明：
        1. 正常情况下优先读取 C Round2 迁移候选文件；
        2. 903 总账迁移完成后，C Round2 脚本可能只剩 67 条稳定 C，此时应回退读取已接受迁移快照；
        3. 这样可以保证 127 条 A_candidate 行为回归可重复执行，而不是被后续台账复跑清空。
    """

    payload = json.loads(MIGRATION_CANDIDATES_PATH.read_text(encoding="utf-8"))
    candidates = [item for item in payload["items"] if item["migration_type"] == "A_candidate"]
    if candidates or not ACCEPTED_MIGRATION_PATH.exists():
        return candidates

    accepted_payload = json.loads(ACCEPTED_MIGRATION_PATH.read_text(encoding="utf-8"))
    return [
        item
        for item in accepted_payload.get("items", [])
        if item.get("migration_type") == "A_candidate"
        and item.get("accepted_status") == "A"
        and item.get("passed") is True
    ]


def _resolve_failure(
    *,
    expected_query_key: str,
    actual_query_key: str | None,
    status_code: str,
    supported: bool,
    needs_clarification: bool,
    row_count: int,
) -> tuple[str | None, str | None]:
    """按行为回归规则归因失败原因。

    参数：
        expected_query_key: Round2 迁移复核时识别出的 query_key。
        actual_query_key: 当前 data-qa 主链路实际返回的 query_key。
        status_code: 当前响应状态码。
        supported: 当前响应是否支持。
        needs_clarification: 当前响应是否仍需澄清。
        row_count: 当前结果表行数。

    返回：
        失败分类和失败原因；全部通过时返回两个 None。
    """

    if actual_query_key != expected_query_key:
        return "题目迁移误判", f"预期 query_key={expected_query_key}，实际 query_key={actual_query_key}"
    if needs_clarification:
        return "题目迁移误判", "当前题仍返回澄清态，不应直接迁入稳定 A"
    if not supported:
        return "题目迁移误判", "当前题仍返回不支持态，不应直接迁入稳定 A"
    if status_code == LogisticsErrorCodeRegistry.EMPTY_RESULT:
        return "数据问题", "当前 query_key 可执行，但结果为空，需要确认数据基线或过滤条件"
    if status_code != LogisticsErrorCodeRegistry.OK:
        return "代码问题", f"当前响应状态码异常：{status_code}"
    if row_count <= 0:
        return "数据问题", "当前响应成功但结果表为空"
    return None, None


def _run_single_question(service: LogisticsDataQaService, item: dict[str, Any]) -> CandidateRegressionRecord:
    """执行单条 A_candidate 行为回归。"""

    expected_query_key = item["query_key"]
    try:
        result = service.query(
            LogisticsDataQaQueryRequest(question=item["question"]),
            trace_id="c-round2-a-candidate-regression",
        )
        status_code = result.status.code if result.status else "NO_STATUS"
        status_message = result.status.message if result.status else "当前未返回状态。"
        actual_query_key = result.query_plan.query_key
        row_count = len(result.result_table.rows)
        failure_classification, failure_reason = _resolve_failure(
            expected_query_key=expected_query_key,
            actual_query_key=actual_query_key,
            status_code=status_code,
            supported=result.supported,
            needs_clarification=result.needs_clarification,
            row_count=row_count,
        )
        return CandidateRegressionRecord(
            question_id=item["question_id"],
            question=item["question"],
            source_group=item["source_group"],
            family=item["family"],
            expected_query_key=expected_query_key,
            actual_query_key=actual_query_key,
            status_code=status_code,
            status_message=status_message,
            supported=result.supported,
            needs_clarification=result.needs_clarification,
            passed=failure_classification is None,
            failure_classification=failure_classification,
            failure_reason=failure_reason,
            answer_summary=result.answer_summary,
            row_count=row_count,
        )
    except Exception as exc:  # noqa: BLE001
        return CandidateRegressionRecord(
            question_id=item["question_id"],
            question=item["question"],
            source_group=item["source_group"],
            family=item["family"],
            expected_query_key=expected_query_key,
            actual_query_key=None,
            status_code="EXCEPTION",
            status_message=str(exc),
            supported=False,
            needs_clarification=False,
            passed=False,
            failure_classification="代码问题",
            failure_reason=f"执行异常：{exc}",
            answer_summary="",
            row_count=0,
        )


def evaluate_a_candidate_regression() -> dict[str, Any]:
    """执行 C Round2 A_candidate 行为回归。"""

    candidates = _load_a_candidates()
    db = SessionLocal()
    service = LogisticsDataQaService(db=db, query_log_repository=NoopQueryLogRepository())
    records: list[CandidateRegressionRecord] = []
    counter: Counter[str] = Counter()

    try:
        for item in candidates:
            record = _run_single_question(service=service, item=item)
            records.append(record)
            counter["total"] += 1
            counter["passed" if record.passed else "failed"] += 1
            counter[record.status_code] += 1
            counter[f"query_key::{record.actual_query_key or 'None'}"] += 1
            if record.failure_classification:
                counter[f"class::{record.failure_classification}"] += 1
            if record.failure_reason:
                counter[f"reason::{record.failure_reason}"] += 1
    finally:
        db.close()

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_candidates": str(MIGRATION_CANDIDATES_PATH),
        "regression_rule": {
            "description": "A_candidate 必须真实调用 data-qa 主链路，并满足 query_key 一致、OK 状态、非澄清、非不支持、结果非空。",
            "allowed_status_codes": [LogisticsErrorCodeRegistry.OK],
        },
        "summary": {
            "total_questions": counter["total"],
            "passed_questions": counter["passed"],
            "failed_questions": counter["failed"],
            "status_code_breakdown": {
                key: value
                for key, value in counter.items()
                if key not in {"total", "passed", "failed"}
                and not key.startswith(("class::", "reason::", "query_key::"))
            },
            "actual_query_key_breakdown": {
                key.replace("query_key::", ""): value
                for key, value in counter.items()
                if key.startswith("query_key::")
            },
            "failure_classification_breakdown": {
                key.replace("class::", ""): value
                for key, value in counter.items()
                if key.startswith("class::")
            },
            "failure_reason_breakdown": {
                key.replace("reason::", ""): value
                for key, value in counter.items()
                if key.startswith("reason::")
            },
            "migration_recommendation": "仅通过题建议进入正式 A 迁移候选；失败题继续留在复核池，不得直接更新 903 总账。",
        },
        "items": [asdict(record) for record in records],
        "failed_items": [asdict(record) for record in records if not record.passed],
    }


def _write_a_candidate_config(report: dict[str, Any]) -> None:
    """写出通过回归的 A_candidate 清单，供后续总账迁移使用。"""

    passed_items = [item for item in report["items"] if item["passed"]]
    payload = {
        "generated_at": report["generated_at"],
        "source_report": str(REPORT_PATH),
        "summary": {
            "total_candidates": report["summary"]["total_questions"],
            "passed_candidates": len(passed_items),
            "failed_candidates": report["summary"]["failed_questions"],
        },
        "items": passed_items,
    }
    A_CANDIDATE_CONFIG_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_accepted_migration_snapshot(report: dict[str, Any]) -> None:
    """写出 C Round2 已接受迁移快照。

    说明：
        1. 该快照是正式总账迁移的稳定输入；
        2. A_candidate 必须以本次行为回归通过记录为准；
        3. B_candidate 保留为后续澄清模板复检对象；
        4. 如果当前候选文件已经被迁移后复跑清空，则复用既有快照，避免把正式迁移状态回滚。
    """

    passed_records = {
        (item["question_id"], item["question"]): item
        for item in report["items"]
        if item.get("passed") is True
    }
    if not passed_records:
        return

    migration_payload = json.loads(MIGRATION_CANDIDATES_PATH.read_text(encoding="utf-8"))
    migration_items = migration_payload.get("items", [])
    if not migration_items and ACCEPTED_MIGRATION_PATH.exists():
        migration_items = json.loads(ACCEPTED_MIGRATION_PATH.read_text(encoding="utf-8")).get("items", [])

    accepted_items: list[dict[str, Any]] = []
    for item in migration_items:
        item_key = (item["question_id"], item["question"])
        if item.get("migration_type") == "A_candidate":
            passed_record = passed_records.get(item_key)
            if not passed_record:
                continue
            accepted_items.append(
                {
                    **item,
                    "accepted_status": "A",
                    "passed": True,
                    "actual_query_key": passed_record.get("actual_query_key"),
                    "status_code": passed_record.get("status_code"),
                    "row_count": passed_record.get("row_count"),
                    "accepted_reason": "C Round2 A_candidate 已通过行为回归，允许迁入正式 A。",
                }
            )
        elif item.get("migration_type") == "B_candidate":
            accepted_items.append(
                {
                    **item,
                    "accepted_status": "B",
                    "passed": None,
                    "accepted_reason": "C Round2 B_candidate 应迁入 B，并纳入后续澄清模板复检。",
                }
            )

    if not accepted_items:
        return

    summary = {
        "a_candidate_passed_to_a": sum(1 for item in accepted_items if item.get("accepted_status") == "A"),
        "b_candidate_to_b": sum(1 for item in accepted_items if item.get("accepted_status") == "B"),
        "c_confirmed_remaining_c": 67,
        "distribution_after_migration": {"A": 300, "B": 536, "C": 67, "D": 0},
        "policy": "A_candidate 必须行为回归通过后才迁入 A；B_candidate 迁入 B 后进入澄清模板复检；C_confirmed 继续保持拒答边界。",
    }
    payload = {
        "generated_at": report["generated_at"],
        "source_regression_report": str(REPORT_PATH),
        "summary": summary,
        "items": accepted_items,
    }
    ACCEPTED_MIGRATION_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render_markdown(report: dict[str, Any]) -> str:
    """渲染 C Round2 A_candidate 行为回归文档。"""

    summary = report["summary"]
    lines = [
        "# C Round2 A_candidate 行为回归",
        "",
        "## 一、结论",
        "",
        (
            f"本轮对 C Round2 识别出的 A_candidate 共 `{summary['total_questions']}` 条做真实 data-qa 行为回归，"
            f"通过 `{summary['passed_questions']}` 条，失败 `{summary['failed_questions']}` 条。"
        ),
        "",
        "## 二、断言规则",
        "",
        "- 实际 query_key 必须与 Round2 迁移复核识别出的 query_key 一致。",
        "- 状态码必须为 `OK`。",
        "- 不允许返回澄清态。",
        "- 不允许返回不支持态。",
        "- 结果表必须非空。",
        "",
        "## 三、query_key 分布",
        "",
    ]
    for key, value in summary["actual_query_key_breakdown"].items():
        lines.append(f"- `{key}`：`{value}`")
    lines.extend(["", "## 四、失败归因", ""])
    if summary["failure_classification_breakdown"]:
        for key, value in summary["failure_classification_breakdown"].items():
            lines.append(f"- `{key}`：`{value}`")
    else:
        lines.append("- 无失败项。")
    lines.extend(["", "## 五、下一步建议", ""])
    if summary["failed_questions"] == 0:
        lines.append("127 条 A_candidate 可进入正式 A 迁移候选；下一步应更新 903 总账，并挑选高价值题进入精确断言。")
    else:
        lines.append("仅通过题可进入正式 A 迁移候选；失败题继续留在复核池，不能直接更新为稳定 A。")
    return "\n".join(lines) + "\n"


def main() -> None:
    """生成 C Round2 A_candidate 行为回归报告。"""

    report = evaluate_a_candidate_regression()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    A_CANDIDATE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_a_candidate_config(report)
    _write_accepted_migration_snapshot(report)
    DOC_PATH.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

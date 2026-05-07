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
from backend.app.domains.logistics.services.llm_clarification_assist_service import (
    LogisticsLlmClarificationAssistService,
)
from backend.app.domains.logistics.services.llm_unsupported_assist_service import (
    LogisticsLlmUnsupportedAssistService,
)
from backend.app.domains.logistics.services.llm_understanding_guardrail_service import (
    LogisticsLlmUnderstandingGuardrailService,
)


LEDGER_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_master_ledger.json"
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_c_unsupported_explanation_wave2_report.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_C_UNSUPPORTED_EXPLANATION_WAVE2.md"


class NoopQueryLogRepository:
    """无副作用查询日志仓储。"""

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        """忽略查询日志写入请求。"""

        _ = db, payload
        return 0


@dataclass
class CUnsupportedRecord:
    """C 类拒答解释复检单题记录。"""

    question_id: str
    question: str
    family: str
    status_code: str
    supported: bool
    needs_clarification: bool
    actual_query_key: str | None
    unsupported_category: str | None
    boundary_passed: bool
    explanation_available: bool
    provider_mode: str | None
    failure_reason: str | None
    answer_summary: str
    suggestions: list[str]


def _load_c_items() -> list[dict[str, Any]]:
    """读取当前总账 C 类题。"""

    payload = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    return [item for item in payload["items"] if item.get("current_status") == "C"]


def _build_service(use_live_llm: bool) -> tuple[Any, LogisticsDataQaService]:
    """构造真实 data-qa 服务，C 类解释辅助默认 dry-run/off。"""

    db = SessionLocal()
    unsupported_assist = LogisticsLlmUnsupportedAssistService(
        enabled=use_live_llm,
        mode="assist" if use_live_llm else "off",
        sample_rate=1.0 if use_live_llm else 0.0,
        audit_enabled=False,
    )
    service = LogisticsDataQaService(
        db=db,
        query_log_repository=NoopQueryLogRepository(),
        guardrail_service=LogisticsLlmUnderstandingGuardrailService(
            enabled=False,
            mode="off",
            sample_rate=0.0,
            audit_enabled=False,
        ),
        clarification_assist_service=LogisticsLlmClarificationAssistService(
            enabled=False,
            mode="off",
            sample_rate=0.0,
            audit_enabled=False,
        ),
        unsupported_assist_service=unsupported_assist,
    )
    return db, service


def _resolve_failure(result: Any) -> str | None:
    """判断 C 类边界是否被改坏。"""

    status_code = result.status.code if result.status else "NO_STATUS"
    if status_code != LogisticsErrorCodeRegistry.UNSUPPORTED_QUESTION:
        return f"unexpected_status::{status_code}"
    if result.supported:
        return "supported_true_for_c_boundary"
    if result.needs_clarification:
        return "clarification_returned_for_c_boundary"
    if result.query_plan.query_key:
        return f"query_key_returned::{result.query_plan.query_key}"
    return None


def evaluate(*, use_live_llm: bool, limit: int) -> dict[str, Any]:
    """执行 C=69 拒答解释增强复检。"""

    items = _load_c_items()
    if limit > 0:
        items = items[:limit]
    db, service = _build_service(use_live_llm)
    records: list[CUnsupportedRecord] = []
    try:
        for item in items:
            result = service.query(
                LogisticsDataQaQueryRequest(question=item["question"]),
                trace_id="logistics-903-c-unsupported-wave2",
            )
            failure_reason = _resolve_failure(result)
            unsupported = result.data_scope.get("unsupported", {}) if isinstance(result.data_scope, dict) else {}
            suggestions = list(unsupported.get("suggestions") or [])
            records.append(
                CUnsupportedRecord(
                    question_id=item["question_id"],
                    question=item["question"],
                    family=item["family"],
                    status_code=result.status.code if result.status else "NO_STATUS",
                    supported=bool(result.supported),
                    needs_clarification=bool(result.needs_clarification),
                    actual_query_key=result.query_plan.query_key,
                    unsupported_category=result.query_plan.unsupported_category,
                    boundary_passed=failure_reason is None,
                    explanation_available=bool(result.answer_summary and suggestions),
                    provider_mode=unsupported.get("assist_provider_mode"),
                    failure_reason=failure_reason,
                    answer_summary=result.answer_summary,
                    suggestions=suggestions,
                )
            )
    finally:
        db.close()

    failure_counter = Counter(record.failure_reason for record in records if record.failure_reason)
    category_counter = Counter(record.unsupported_category or "uncategorized" for record in records)
    provider_counter = Counter(record.provider_mode or "off" for record in records)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "use_live_llm": use_live_llm,
        "source_ledger": str(LEDGER_PATH),
        "summary": {
            "total_c_questions": len(records),
            "boundary_passed": sum(1 for record in records if record.boundary_passed),
            "boundary_failed": sum(1 for record in records if not record.boundary_passed),
            "explanation_available": sum(1 for record in records if record.explanation_available),
            "category_breakdown": dict(category_counter),
            "provider_mode_breakdown": dict(provider_counter),
            "failure_reason_breakdown": dict(failure_counter),
        },
        "items": [asdict(record) for record in records],
        "failed_items": [asdict(record) for record in records if not record.boundary_passed],
    }
    return report


def _render_doc(report: dict[str, Any]) -> str:
    """渲染 C 类拒答解释复检文档。"""

    summary = report["summary"]
    lines = [
        "# 903 C 类拒答解释 Wave2 复检",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 一、结论",
        "",
        f"- 是否真实调用 LLM：`{report['use_live_llm']}`",
        f"- C 类复检总数：`{summary['total_c_questions']}`",
        f"- 拒答边界通过：`{summary['boundary_passed']}`",
        f"- 拒答边界失败：`{summary['boundary_failed']}`",
        f"- 具备业务解释与改问建议：`{summary['explanation_available']}`",
        f"- unsupported 类别分布：`{summary['category_breakdown']}`",
        f"- provider mode 分布：`{summary['provider_mode_breakdown']}`",
        "",
        "## 二、治理原则",
        "",
        "- C 类最终裁决仍由规则层和 response policy 锁定。",
        "- LLM 只允许生成业务可理解解释和改问方向，不允许改判成 success。",
        "- 本轮默认 dry-run/off，不依赖 live LLM 作为基础回归条件。",
        "",
        "## 三、失败项",
        "",
    ]
    if report["failed_items"]:
        for item in report["failed_items"]:
            lines.append(f"- {item['question_id']} | {item['failure_reason']} | {item['question']}")
    else:
        lines.append("- 当前无 C 边界失败项。")
    lines.extend(["", "## 四、代表样例", ""])
    for item in report["items"][:20]:
        lines.append(f"- {item['question_id']} | {item['unsupported_category']} | {item['answer_summary']}")
    return "\n".join(lines) + "\n"


def main() -> None:
    """命令行入口。"""

    parser = argparse.ArgumentParser(description="903 C 类拒答解释 Wave2 复检")
    parser.add_argument("--with-live-llm", action="store_true", help="启用真实 LLM 生成拒答解释。")
    parser.add_argument("--limit", type=int, default=0, help="限制复检题数；0 表示全量 C 类。")
    args = parser.parse_args()
    report = evaluate(use_live_llm=bool(args.with_live_llm), limit=args.limit)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC_PATH.write_text(_render_doc(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

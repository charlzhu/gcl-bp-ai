from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
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
from backend.app.domains.logistics.services.llm_clarification_assist_service import LogisticsLlmClarificationAssistService
from backend.app.domains.logistics.services.llm_understanding_guardrail_service import (
    LogisticsLlmUnderstandingGuardrailService,
)
from backend.app.domains.logistics.services.llm_unsupported_assist_service import LogisticsLlmUnsupportedAssistService


GAP_REVIEW_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_migration_gap_review_report.json"
ROADMAP_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_gap_capability_roadmap.json"
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_gap_wave1_report.json"
CANDIDATES_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b_gap_wave1_migration_candidates.json"
)
REGRESSION_QUESTIONS_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b_gap_wave1_a_regression_questions.json"
)
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_GAP_WAVE1.md"


class NoopQueryLogRepository:
    """无副作用查询日志仓储。

    说明：
        B-gap Wave1 复核必须真实调用 data-qa 主链路，但不应污染正式查询历史。
    """

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        """忽略查询日志写入请求。"""

        _ = db, payload
        return 0


@dataclass
class Wave1ReviewRecord:
    """B-gap Wave1 单题复核记录。"""

    question_id: str
    question: str
    family: str
    category: str
    capability_id: str
    capability_name: str
    original_gap_type: str
    actual_query_key: str | None
    status_code: str
    supported: bool
    needs_clarification: bool
    row_count: int
    migration_decision: str
    failure_reason: str | None
    answer_summary: str


def _load_json(path: Path) -> Any:
    """读取 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8"))


def _build_capability_index() -> dict[tuple[str, str, str], dict[str, Any]]:
    """把 B-gap Wave1 P1 query_key_gap 能力项建立成索引。

    返回：
        key=(gap_type, family, category)，value=能力项配置。

    说明：
        gap_matrix_records 本身不带 capability_id，因此必须回到能力路线图，
        用题族 + 缺口类别映射到正式能力项，避免主观挑题。
    """

    roadmap = _load_json(ROADMAP_PATH)
    index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in roadmap["items"]:
        if (
            item.get("priority") == "P1"
            and item.get("gap_type") == "query_key_gap"
            and item.get("next_wave") == "B-gap Wave1：优先补可参数化 query_key"
        ):
            index[(item["gap_type"], item["family"], item["category"])] = item
    return index


def _load_wave1_records() -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """读取 B-gap Wave1 覆盖的原始 gap 记录。"""

    capability_index = _build_capability_index()
    route_metric_capability = next(
        (item for item in capability_index.values() if item.get("capability_id") == "B-GAP-002"),
        None,
    )
    gap_payload = _load_json(GAP_REVIEW_PATH)
    records: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for record in gap_payload["gap_matrix_records"]:
        key = (record["primary_gap_type"], record["family"], record["category"])
        capability = capability_index.get(key)
        if (
            capability is None
            and route_metric_capability
            and record["primary_gap_type"] == "query_key_gap"
            and record["category"] == "route_metric_scope"
            and record["family"] in {"区域/省份/基地汇总类", "综合统计类"}
        ):
            # 原始缺口矩阵里少量“始发地 + 车型 + 单车/单瓦”题被归到了
            # 区域/综合题族，但结构模式与 B-GAP-002 完全一致。这里按能力矩阵
            # 重新吸收到同一参数化 query_key 复核范围，避免已可答题被总账遗漏。
            capability = route_metric_capability
        if capability:
            records.append((record, capability))
    return records


def _resolve_decision(result: Any) -> tuple[str, str | None]:
    """根据真实 data-qa 结果判定是否可迁入 A。

    参数：
        result: LogisticsDataQaResult 实例。

    返回：
        (迁移结论, 失败/保留原因)。

    业务规则：
        1. 只有 OK、supported=true、needs_clarification=false、query_key 非空、结果表非空时才允许迁 A；
        2. 仍需澄清或不支持的题继续留 B/C 边界，不为了覆盖率强行迁移；
        3. 空结果通常代表数据基线不足，当前保持 B 或进入数据口径复核。
    """

    status_code = result.status.code if result.status else "NO_STATUS"
    if result.needs_clarification:
        return "remain_b_clarification", "仍需补充统计口径或关键槽位"
    if not result.supported:
        return "remain_b_not_answerable", "当前真实链路仍不支持或数据口径不足"
    if status_code != LogisticsErrorCodeRegistry.OK:
        return "remain_b_status_not_ok", f"当前状态码不是 OK：{status_code}"
    if not result.query_plan.query_key:
        return "remain_b_no_query_key", "未命中受控 query_key"
    if not result.result_table.rows:
        return "remain_b_empty_result", "当前结果为空，需确认数据基线或过滤条件"
    return "ready_for_a_migration", None


def _run_single(
    service: LogisticsDataQaService,
    *,
    record: dict[str, Any],
    capability: dict[str, Any],
) -> Wave1ReviewRecord:
    """执行单题 B-gap Wave1 迁移复核。"""

    try:
        result = service.query(
            LogisticsDataQaQueryRequest(question=record["question"]),
            trace_id="logistics-903-b-gap-wave1",
        )
        decision, failure_reason = _resolve_decision(result)
        return Wave1ReviewRecord(
            question_id=record["question_id"],
            question=record["question"],
            family=record["family"],
            category=record["category"],
            capability_id=capability["capability_id"],
            capability_name=f"{capability['family']} / {capability['category']}",
            original_gap_type=record["primary_gap_type"],
            actual_query_key=result.query_plan.query_key,
            status_code=result.status.code if result.status else "NO_STATUS",
            supported=bool(result.supported),
            needs_clarification=bool(result.needs_clarification),
            row_count=len(result.result_table.rows),
            migration_decision=decision,
            failure_reason=failure_reason,
            answer_summary=result.answer_summary,
        )
    except Exception as exc:  # noqa: BLE001
        return Wave1ReviewRecord(
            question_id=record["question_id"],
            question=record["question"],
            family=record["family"],
            category=record["category"],
            capability_id=capability["capability_id"],
            capability_name=f"{capability['family']} / {capability['category']}",
            original_gap_type=record["primary_gap_type"],
            actual_query_key=None,
            status_code="EXCEPTION",
            supported=False,
            needs_clarification=False,
            row_count=0,
            migration_decision="remain_b_execution_error",
            failure_reason=f"执行异常：{exc}",
            answer_summary="",
        )


def evaluate() -> dict[str, Any]:
    """执行 B-gap Wave1 P1 query_key_gap 迁移复核。"""

    wave_records = _load_wave1_records()
    db = SessionLocal()
    service = LogisticsDataQaService(
        db=db,
        query_log_repository=NoopQueryLogRepository(),
        # 批量复核必须验证规则 planner + 受控 query_key 的真实能力，不依赖 live LLM。
        # 因此这里显式关闭 Guardrail/澄清/拒答 assist，避免 200+ 条批量回归被网络调用拖慢或受额度影响。
        guardrail_service=LogisticsLlmUnderstandingGuardrailService(
            enabled=False,
            mode="off",
            audit_enabled=False,
        ),
        clarification_assist_service=LogisticsLlmClarificationAssistService(
            enabled=False,
            mode="off",
            audit_enabled=False,
        ),
        unsupported_assist_service=LogisticsLlmUnsupportedAssistService(
            enabled=False,
            mode="off",
            audit_enabled=False,
        ),
    )
    records: list[Wave1ReviewRecord] = []
    try:
        for record, capability in wave_records:
            records.append(_run_single(service, record=record, capability=capability))
    finally:
        db.close()

    decision_counter: Counter[str] = Counter(record.migration_decision for record in records)
    query_key_counter: Counter[str] = Counter(record.actual_query_key or "NONE" for record in records)
    capability_counter: Counter[str] = Counter(record.capability_id for record in records)
    family_counter: Counter[str] = Counter(record.family for record in records)
    capability_summary: defaultdict[str, dict[str, Any]] = defaultdict(
        lambda: {"total": 0, "ready_for_a_migration": 0, "remain_b": 0, "query_key_breakdown": Counter()}
    )
    for record in records:
        summary = capability_summary[record.capability_id]
        summary["total"] += 1
        if record.migration_decision == "ready_for_a_migration":
            summary["ready_for_a_migration"] += 1
        else:
            summary["remain_b"] += 1
        summary["query_key_breakdown"][record.actual_query_key or "NONE"] += 1

    normalized_capability_summary = {
        capability_id: {
            "total": item["total"],
            "ready_for_a_migration": item["ready_for_a_migration"],
            "remain_b": item["remain_b"],
            "query_key_breakdown": dict(item["query_key_breakdown"]),
        }
        for capability_id, item in capability_summary.items()
    }
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_gap_review": str(GAP_REVIEW_PATH),
        "source_roadmap": str(ROADMAP_PATH),
        "summary": {
            "reviewed_questions": len(records),
            "ready_for_a_migration": decision_counter.get("ready_for_a_migration", 0),
            "remain_b_total": len(records) - decision_counter.get("ready_for_a_migration", 0),
            "decision_breakdown": dict(decision_counter),
            "query_key_breakdown": dict(query_key_counter),
            "capability_breakdown": dict(capability_counter),
            "family_breakdown": dict(family_counter),
            "capability_summary": normalized_capability_summary,
        },
        "items": [asdict(record) for record in records],
        "migration_candidates": [
            asdict(record) for record in records if record.migration_decision == "ready_for_a_migration"
        ],
        "remaining_b_items": [
            asdict(record) for record in records if record.migration_decision != "ready_for_a_migration"
        ],
    }


def _write_candidate_configs(report: dict[str, Any]) -> None:
    """写出 B-gap Wave1 可迁 A 候选配置和行为回归题集。"""

    candidate_items = []
    regression_items = []
    for index, item in enumerate(report["migration_candidates"], start=1):
        candidate_items.append(
            {
                "migration_id": f"B-GAP-W1-{index:03d}",
                "question_id": item["question_id"],
                "question": item["question"],
                "source": "B-gap Wave1 P1 query_key_gap migration review",
                "family": item["family"],
                "category": item["category"],
                "capability_id": item["capability_id"],
                "query_key": item["actual_query_key"],
                "recommended_status": "A",
                "migration_reason": "B-gap Wave1 真实 data-qa 行为复核通过，命中受控 query_key 且返回 OK 非空结果。",
            }
        )
        regression_items.append(
            {
                "question_id": item["question_id"],
                "question": item["question"],
                "source_group": "B-gap Wave1",
                "family": item["family"],
                "expected_query_key": item["actual_query_key"],
                "expected_status_code": LogisticsErrorCodeRegistry.OK,
            }
        )

    CANDIDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGRESSION_QUESTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATES_PATH.write_text(
        json.dumps(
            {
                "generated_at": report["generated_at"],
                "source_report": str(REPORT_PATH),
                "migration_rule": "只有 B-gap Wave1 真实链路行为复核通过的题才允许迁入 A。",
                "items": candidate_items,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    REGRESSION_QUESTIONS_PATH.write_text(
        json.dumps(
            {
                "generated_at": report["generated_at"],
                "source_report": str(REPORT_PATH),
                "items": regression_items,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _render_markdown(report: dict[str, Any]) -> str:
    """渲染 B-gap Wave1 专项文档。"""

    summary = report["summary"]
    lines = [
        "# 903 B-gap Wave1 P1 query_key_gap 能力建设与迁移复核",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 一、结论",
        "",
        f"- 本轮复核 P1 query_key_gap 题：`{summary['reviewed_questions']}` 条。",
        f"- 真实链路稳定可答、建议迁入 A：`{summary['ready_for_a_migration']}` 条。",
        f"- 继续留 B：`{summary['remain_b_total']}` 条。",
        "",
        "## 二、本轮工程化能力",
        "",
        "- `hist_monthly_trip_count_summary`：历史某年某月总车次。",
        "- `hist_route_aggregate_summary`：历史始发地到省/市的平均运费或发运量 MW。",
        "- `hist_origin_vehicle_metric_summary`：历史始发地 + 车型的平均单车运费或平均单瓦价。",
        "",
        "## 三、能力项统计",
        "",
        "| capability_id | 复核数 | 可迁 A | 留 B | query_key 分布 |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for capability_id, item in summary["capability_summary"].items():
        lines.append(
            f"| {capability_id} | {item['total']} | {item['ready_for_a_migration']} | "
            f"{item['remain_b']} | {item['query_key_breakdown']} |"
        )
    lines.extend(["", "## 四、新增可迁 A 候选", ""])
    if report["migration_candidates"]:
        for item in report["migration_candidates"][:80]:
            lines.append(f"- {item['question_id']} | {item['actual_query_key']} | {item['question']}")
        if len(report["migration_candidates"]) > 80:
            lines.append(f"- 其余 {len(report['migration_candidates']) - 80} 条详见 JSON 报告。")
    else:
        lines.append("- 本轮没有新增可迁 A 候选。")
    lines.extend(["", "## 五、继续留 B 的边界", ""])
    for item in report["remaining_b_items"][:40]:
        lines.append(f"- {item['question_id']} | {item['migration_decision']} | {item['question']}")
    if len(report["remaining_b_items"]) > 40:
        lines.append(f"- 其余 {len(report['remaining_b_items']) - 40} 条详见 JSON 报告。")
    lines.extend(
        [
            "",
            "## 六、治理边界",
            "",
            "- 本轮只迁移真实 data-qa 主链路稳定可答的题。",
            "- 状态/映射一致性、异常原因、风险解释、业务定义不清的题继续保留 B，不强行迁 A。",
            "- B/C 正式边界仍由规则层与 response policy 主导，LLM/Guardrail 不参与改写。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    """命令行入口。"""

    parser = argparse.ArgumentParser(description="903 B-gap Wave1 P1 query_key_gap 迁移复核")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="写出可迁 A 候选配置和新增 A 行为回归题集。",
    )
    args = parser.parse_args()

    report = evaluate()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC_PATH.write_text(_render_markdown(report), encoding="utf-8")
    if args.apply:
        _write_candidate_configs(report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

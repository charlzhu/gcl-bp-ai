from __future__ import annotations

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


LEDGER_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_master_ledger.json"
SEMANTIC_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_semantic_closure_full_report.json"
FOLLOWUP_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_followup_closure_report.json"
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_migration_gap_review_report.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_MIGRATION_GAP_REVIEW.md"
CANDIDATE_CONFIG_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b2a_migration_review_candidates.json"


class NoopQueryLogRepository:
    """无副作用查询日志仓储。

    说明：
        1. 迁移复核必须真实调用 data-qa 主链路；
        2. 但复核脚本不应把批量验证问题写入业务查询历史；
        3. 因此这里提供空实现，只阻断日志写入副作用，不绕过查询逻辑。
    """

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        """兼容 LogisticsDataQaService 所需的日志写入接口。

        参数：
            db: 当前数据库会话。
            payload: 原本要写入查询日志的快照。

        返回：
            固定返回 0，表示未生成真实日志 ID。
        """

        _ = db, payload
        return 0


@dataclass
class MigrationReviewRecord:
    """B->A 迁移候选复核记录。"""

    question_id: str
    question: str
    family: str | None
    source_group: str | None
    expected_query_key: str | None
    actual_query_key: str | None
    status_code: str
    supported: bool
    needs_clarification: bool
    row_count: int
    passed_behavior_review: bool
    migration_decision: str
    failure_reason: str | None
    answer_summary: str


@dataclass
class FollowupClosureRecord:
    """B 类补槽后可答闭环复核记录。"""

    question_id: str
    question: str
    family: str | None
    initial_category: str | None
    final_query_key: str | None
    closure_decision: str
    closure_reason: str


@dataclass
class GapMatrixRecord:
    """仍需澄清 B 题的缺口矩阵记录。"""

    question_id: str
    question: str
    family: str | None
    category: str | None
    missing_slots: list[str]
    primary_gap_type: str
    gap_reason: str
    next_action: str


def _load_json(path: Path) -> dict[str, Any]:
    """读取 JSON 文件并返回字典。"""

    return json.loads(path.read_text(encoding="utf-8"))


def _load_ledger_index() -> dict[str, dict[str, Any]]:
    """读取 903 总账并按题号建立索引。"""

    payload = _load_json(LEDGER_PATH)
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("logistics_903_master_ledger.json 缺少 items 数组。")
    return {str(item.get("question_id")): item for item in items}


def _dedupe_direct_candidates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """提取并去重语义回归中的 B->A 直接可答候选。

    参数：
        records: 903 语义回归中的 B 类记录。

    返回：
        按题号去重后的直接迁移候选列表。
    """

    output: dict[str, dict[str, Any]] = {}
    for record in records:
        if record.get("behavior_outcome") != "answerable_migration_candidate":
            continue
        question_id = str(record.get("question_id") or "")
        if question_id:
            output[question_id] = record
    return list(output.values())


def _run_data_qa_review(candidates: list[dict[str, Any]], ledger_index: dict[str, dict[str, Any]]) -> list[MigrationReviewRecord]:
    """对 B->A 直接候选逐条执行真实 data-qa 复核。

    参数：
        candidates: 直接迁移候选列表。
        ledger_index: 903 总账题号索引。

    返回：
        逐题复核记录。
    """

    db = SessionLocal()
    service = LogisticsDataQaService(db=db, query_log_repository=NoopQueryLogRepository())
    records: list[MigrationReviewRecord] = []
    try:
        for candidate in candidates:
            question_id = str(candidate.get("question_id") or "")
            question = str(candidate.get("question") or "")
            ledger_item = ledger_index.get(question_id, {})
            expected_query_key = candidate.get("actual_query_key")
            try:
                result = service.query(
                    LogisticsDataQaQueryRequest(question=question),
                    trace_id="logistics-903-b2a-migration-review",
                )
                actual_query_key = result.query_plan.query_key
                status_code = result.status.code if result.status else "NO_STATUS"
                supported = bool(result.supported)
                needs_clarification = bool(result.needs_clarification)
                row_count = len(result.result_table.rows)
                failure_reason = _resolve_behavior_failure(
                    expected_query_key=expected_query_key,
                    actual_query_key=actual_query_key,
                    status_code=status_code,
                    supported=supported,
                    needs_clarification=needs_clarification,
                    row_count=row_count,
                )
                passed = failure_reason is None
                decision = "ready_for_a_migration" if passed else "keep_b_until_fixed"
                answer_summary = result.answer_summary
            except Exception as exc:  # noqa: BLE001
                actual_query_key = None
                status_code = "EXCEPTION"
                supported = False
                needs_clarification = False
                row_count = 0
                failure_reason = f"execution_exception::{exc}"
                passed = False
                decision = "keep_b_until_fixed"
                answer_summary = ""
            records.append(
                MigrationReviewRecord(
                    question_id=question_id,
                    question=question,
                    family=ledger_item.get("family"),
                    source_group=ledger_item.get("source_group"),
                    expected_query_key=expected_query_key,
                    actual_query_key=actual_query_key,
                    status_code=status_code,
                    supported=supported,
                    needs_clarification=needs_clarification,
                    row_count=row_count,
                    passed_behavior_review=passed,
                    migration_decision=decision,
                    failure_reason=failure_reason,
                    answer_summary=answer_summary,
                )
            )
    finally:
        db.close()
    return records


def _resolve_behavior_failure(
    *,
    expected_query_key: str | None,
    actual_query_key: str | None,
    status_code: str,
    supported: bool,
    needs_clarification: bool,
    row_count: int,
) -> str | None:
    """按统一规则判定迁移候选行为复核失败原因。"""

    if actual_query_key != expected_query_key:
        return "query_key_mismatch"
    if needs_clarification:
        return "still_clarification"
    if not supported:
        return "unsupported_or_failed"
    if status_code != LogisticsErrorCodeRegistry.OK:
        return f"unexpected_status::{status_code}"
    if row_count <= 0:
        return "empty_result"
    return None


def _build_followup_records(items: list[dict[str, Any]]) -> list[FollowupClosureRecord]:
    """提取“补槽后可答”的 B 类闭环记录。

    说明：
        这类题不直接把原问迁移到 A，因为原问本身仍需要用户补充口径。
        它们用于证明 B 类追问后可以回到受控 data-qa 链路。
    """

    records: list[FollowupClosureRecord] = []
    for item in items:
        if item.get("outcome") != "answerable_after_followup":
            continue
        records.append(
            FollowupClosureRecord(
                question_id=str(item.get("question_id") or ""),
                question=str(item.get("question") or ""),
                family=item.get("family"),
                initial_category=item.get("initial_category"),
                final_query_key=item.get("final_query_key"),
                closure_decision="keep_b_but_followup_can_answer",
                closure_reason="原问仍需澄清；用户补充口径后可进入受控 query_key，不应把原问直接迁入 A。",
            )
        )
    return records


def _build_gap_matrix(items: list[dict[str, Any]]) -> list[GapMatrixRecord]:
    """把补槽后仍需澄清的 B 题拆成缺口矩阵。"""

    records: list[GapMatrixRecord] = []
    for item in items:
        if item.get("outcome") != "still_clarification_after_followup":
            continue
        category = item.get("final_clarification_category") or item.get("initial_category")
        missing_slots = list(item.get("initial_missing_slots") or [])
        gap_type, reason, next_action = _classify_gap(
            question=str(item.get("question") or ""),
            family=item.get("family"),
            category=category,
            missing_slots=missing_slots,
        )
        records.append(
            GapMatrixRecord(
                question_id=str(item.get("question_id") or ""),
                question=str(item.get("question") or ""),
                family=item.get("family"),
                category=category,
                missing_slots=missing_slots,
                primary_gap_type=gap_type,
                gap_reason=reason,
                next_action=next_action,
            )
        )
    return records


def _classify_gap(
    *,
    question: str,
    family: str | None,
    category: str | None,
    missing_slots: list[str],
) -> tuple[str, str, str]:
    """把长期澄清题归入 query_key / 数据口径 / 业务定义三类缺口。

    参数：
        question: 原始问题。
        family: 题族。
        category: 澄清类别。
        missing_slots: 缺失槽位。

    返回：
        三元组：缺口类型、原因说明、下一处理动作。
    """

    slot_set = set(missing_slots)
    query_key_categories = {
        "route_or_address_scope",
        "route_metric_scope",
        "vehicle_or_trip_scope",
        "quarter_area_metric_scope",
        "quarter_trip_metric_scope",
        "route_loading_scope",
        "route_price_metric_scope",
        "transport_unit_fee_scope",
        "carrier_unit_fee_scope",
        "high_fee_address_scope",
        "state_breakdown_scope",
        "state_ranking_scope",
        "task_split_scope",
        "breakdown_scope",
        "shipment_quantity_scope",
        "transport_distance_scope",
        "parse_fail_ranking_scope",
    }
    data_scope_categories = {
        "data_consistency_scope",
        "data_quality_scope",
        "parse_status_scope",
        "mapping_consistency_scope",
        "field_alias_comparison_scope",
        "driver_identity_consistency_scope",
        "system_state_scope",
        "system_status_ratio_scope",
        "transport_record_scope",
        "product_spec_scope",
    }
    business_definition_categories = {
        "vague_status",
        "abnormal_or_reason_scope",
        "status_risk_scope",
        "ranking_basis_scope",
        "comparison_basis_scope",
        "cause_distribution_scope",
        "contract_carrier_scope",
        "procurement_metric_scope",
        "rate_distribution_scope",
        "short_context_scope",
    }
    if category in query_key_categories or slot_set & {"dimension_split", "result_metric", "price_metric"}:
        return (
            "query_key_gap",
            f"当前题族“{family or '未分类'}”需要新的受控 query_key、参数化维度或结果结构，现有 planner 补槽后仍不能稳定执行。",
            "进入 B-候选收口池，按题族设计 query_key/参数化能力，并补行为回归。",
        )
    if category in data_scope_categories or slot_set & {"source_scope", "mapping_field", "table_scope", "null_handling", "status_code_meaning"}:
        return (
            "data_scope_gap",
            "当前问题依赖字段可用性、映射一致性、状态含义或数据质量口径，必须先确认数据源和字段口径。",
            "进入数据口径复核池，由数据 owner 确认字段、来源、过滤范围和空值处理规则。",
        )
    if category in business_definition_categories or slot_set & {"evaluation_metric", "threshold_scope", "exception_threshold", "analysis_scope", "aggregation_basis"}:
        return (
            "business_definition_gap",
            "当前问题包含“异常、风险、最差、变化、原因、偏好、是否明显”等业务判断，需要先锁定评价标准。",
            "保留 B-长期澄清，优先优化追问模板；业务确认标准后再评估是否进入 A。",
        )
    if any(keyword in question for keyword in ("预测", "未来", "预计", "ETA", "到达")):
        return (
            "business_definition_gap",
            "题面接近预测、ETA 或复杂推理边界，当前不能直接按结构化统计回答。",
            "复核是否应转入 C-边界观察池，并固化拒答解释。",
        )
    return (
        "business_definition_gap",
        "当前缺口无法仅靠补时间或指标解决，仍需要业务补充统计对象、判断标准或输出口径。",
        "继续保留 B，并纳入下一轮业务化追问模板复检。",
    )


def _counter_by(records: list[Any], attr: str) -> dict[str, int]:
    """按 dataclass 属性统计数量。"""

    counter: Counter[str] = Counter()
    for record in records:
        counter[str(getattr(record, attr) or "未分类")] += 1
    return dict(counter)


def _nested_gap_summary(records: list[GapMatrixRecord]) -> dict[str, dict[str, int]]:
    """按缺口类型和题族生成嵌套统计。"""

    output: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        output[record.primary_gap_type][record.family or "未分类"] += 1
    return {gap_type: dict(counter) for gap_type, counter in output.items()}


def build_report() -> dict[str, Any]:
    """生成 B->A 迁移复核与 B 缺口矩阵报告。"""

    ledger_index = _load_ledger_index()
    semantic_report = _load_json(SEMANTIC_REPORT_PATH)
    followup_report = _load_json(FOLLOWUP_REPORT_PATH)
    direct_candidates = _dedupe_direct_candidates(semantic_report.get("b_clarification_records", []))
    migration_records = _run_data_qa_review(direct_candidates, ledger_index)
    followup_records = _build_followup_records(followup_report.get("items", []))
    gap_records = _build_gap_matrix(followup_report.get("items", []))
    passed_migrations = [record for record in migration_records if record.passed_behavior_review]
    failed_migrations = [record for record in migration_records if not record.passed_behavior_review]
    candidate_config = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_report": str(SEMANTIC_REPORT_PATH),
        "migration_rule": "仅包含原问已能通过真实 data-qa 行为复核的 B->A 直接迁移候选；补槽后才可答的题不直接迁移。",
        "items": [
            {
                "question_id": record.question_id,
                "question": record.question,
                "source_group": record.source_group,
                "family": record.family,
                "recommended_status": "A",
                "query_key": record.actual_query_key,
                "migration_basis": "真实 data-qa 主链路返回 OK、supported=true、非澄清、非拒答、query_key 稳定。",
            }
            for record in passed_migrations
        ],
    }
    CANDIDATE_CONFIG_PATH.write_text(json.dumps(candidate_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "direct_migration_candidates": len(migration_records),
        "ready_for_a_migration": len(passed_migrations),
        "keep_b_until_fixed": len(failed_migrations),
        "followup_answerable_but_keep_b": len(followup_records),
        "still_clarification_gap_total": len(gap_records),
        "migration_query_key_breakdown": _counter_by(migration_records, "actual_query_key"),
        "migration_family_breakdown": _counter_by(migration_records, "family"),
        "migration_failure_breakdown": _counter_by(failed_migrations, "failure_reason"),
        "gap_type_breakdown": _counter_by(gap_records, "primary_gap_type"),
        "gap_family_breakdown": _counter_by(gap_records, "family"),
        "gap_category_breakdown": _counter_by(gap_records, "category"),
        "gap_type_family_matrix": _nested_gap_summary(gap_records),
    }
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_reports": {
            "semantic_closure_full_report": str(SEMANTIC_REPORT_PATH),
            "b_followup_closure_report": str(FOLLOWUP_REPORT_PATH),
            "ledger": str(LEDGER_PATH),
        },
        "summary": summary,
        "migration_review_records": [asdict(record) for record in migration_records],
        "followup_closure_records": [asdict(record) for record in followup_records],
        "gap_matrix_records": [asdict(record) for record in gap_records],
        "candidate_config_path": str(CANDIDATE_CONFIG_PATH),
    }


def _render_doc(payload: dict[str, Any]) -> str:
    """渲染迁移复核与缺口矩阵文档。"""

    summary = payload["summary"]
    lines = [
        "# 物流域 903 B->A 迁移复核与 B 缺口矩阵",
        "",
        "## 一、结论",
        "",
        f"- 直接 B->A 可答迁移候选：`{summary['direct_migration_candidates']}`",
        f"- 行为复核通过、建议迁入 A：`{summary['ready_for_a_migration']}`",
        f"- 行为复核未通过、继续留 B：`{summary['keep_b_until_fixed']}`",
        f"- 补槽后可答但原问继续留 B：`{summary['followup_answerable_but_keep_b']}`",
        f"- 补槽后仍需澄清并纳入缺口矩阵：`{summary['still_clarification_gap_total']}`",
        "",
        "本轮不把需要用户补充口径的问题硬迁入 A。只有原问已经能通过真实 data-qa 主链路行为复核的题，才进入 A 迁移候选配置。",
        "",
        "## 二、B->A 迁移候选 query_key 分布",
        "",
    ]
    for query_key, count in sorted(summary["migration_query_key_breakdown"].items()):
        lines.append(f"- `{query_key}`：`{count}`")
    lines.extend(["", "## 三、441 条仍需澄清题缺口类型分布", ""])
    for gap_type, count in sorted(summary["gap_type_breakdown"].items()):
        lines.append(f"- `{gap_type}`：`{count}`")
    lines.extend(["", "## 四、缺口类型 × 题族矩阵", ""])
    for gap_type, family_map in sorted(summary["gap_type_family_matrix"].items()):
        lines.append(f"### {gap_type}")
        for family, count in sorted(family_map.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {family}：`{count}`")
        lines.append("")
    lines.extend(
        [
            "## 五、下一处理动作",
            "",
            "1. 对 `ready_for_a_migration` 题生成正式行为回归集，并按高价值题优先补精确断言。",
            "2. 对 `query_key_gap` 题按题族设计受控 query_key 或参数化查询能力。",
            "3. 对 `data_scope_gap` 题先由数据 owner 确认字段、来源、空值和映射口径。",
            "4. 对 `business_definition_gap` 题继续保持澄清，使用 LLM 辅助缺口径识别和业务化追问，但不改写边界。",
            "",
            "## 六、边界说明",
            "",
            "- LLM 不查数、不生成 SQL、不替代 planner。",
            "- B/C 边界仍由规则层和 Guardrail 锁定。",
            "- 本报告中的迁移候选只是“建议迁移”，正式更新 903 总账前仍需要台账变更脚本和回归保护。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    """脚本入口。"""

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = build_report()
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC_PATH.write_text(_render_doc(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

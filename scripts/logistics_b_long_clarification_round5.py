from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings
from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.llm_clarification_assist_service import (
    LogisticsLlmClarificationAssistService,
)


# Round5 是 B-长期澄清池收尾轮：覆盖剩余题，并按当前真实 planner 分流到 A / B / C。
ROUND5_ALLOWED_CATEGORIES = [
    "field_alias_comparison_scope",
    "cause_distribution_scope",
    "contract_carrier_scope",
    "data_quality_scope",
    "transport_distance_scope",
    "short_context_scope",
    "shipment_quantity_scope",
    "carrier_unit_fee_scope",
    "parse_fail_ranking_scope",
    "driver_identity_consistency_scope",
]

LEDGER_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_master_ledger.json"
ROUND_REPORT_TEMPLATE = "tmp/logistics_question_bank/logistics_b_long_clarification_round{round_no}_report.json"
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_b_long_clarification_round5_report.json"
LIVE_SAMPLE_SIZE = 10


def load_master_ledger() -> list[dict]:
    """读取 903 全量总台账中的题目明细。"""

    payload = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    return payload["items"]


def load_report(path: Path) -> dict:
    """读取既有 Round 报告。"""

    return json.loads(path.read_text(encoding="utf-8"))


def load_selected_pairs() -> set[tuple[str, str]]:
    """读取 Round1 / Round2 / Round3 / Round4 已处理题，避免 Round5 重复选题。"""

    selected: set[tuple[str, str]] = set()
    for round_no in range(1, 5):
        payload = load_report(PROJECT_ROOT / ROUND_REPORT_TEMPLATE.format(round_no=round_no))
        selected.update((item["question_id"], item["question"]) for item in payload["items"])
    return selected


def build_round5_selection(items: list[dict]) -> list[dict]:
    """从 B-长期澄清池里筛选 Round5 收尾对象。

    说明：
        1. Round5 必须基于原始 B 类长期池基线选题，不能受已叠加 Round5 后的 current_status 影响；
        2. Top200 和 TopN v2 候选收口池已经有独立治理链路，Round5 不重复处理；
        3. 当前 planner 已能稳定命中 query_key 的题进入 A；
        4. 当前 planner 已判 unsupported 的策略题进入 C；
        5. 仍需补口径的问题继续保持 B 类澄清。
    """

    planner = LogisticsDataQaPlanner()
    processed_pairs = load_selected_pairs()
    selected: list[dict] = []
    for item in items:
        if item.get("baseline_status") != "B":
            continue
        if item.get("in_top200"):
            continue
        if item.get("topn_v2_lane") == "B-候选收口":
            continue
        if (item["question_id"], item["question"]) in processed_pairs:
            continue
        plan = planner.build_plan(item["question"])
        final_status = "B"
        closure_result = "clarified"
        if plan.query_key:
            final_status = "A"
            closure_result = "promoted_to_a"
        elif plan.intent == "unsupported":
            final_status = "C"
            closure_result = "moved_to_c"
        selected.append(
            {
                "ledger_index": item["ledger_index"],
                "question_id": item["question_id"],
                "question": item["question"],
                "source_group": item["source_group"],
                "family": item["family"],
                "current_priority": item["current_priority"],
                "planner_intent": plan.intent,
                "actual_query_key": plan.query_key,
                "clarification_category": plan.clarification_category,
                "unsupported_reason": plan.unsupported_reason,
                "rule_reason": plan.clarification_reason,
                "rule_missing_slots": list(plan.clarification_missing_slots),
                "rule_questions": list(plan.clarification_questions),
                "final_status": final_status,
                "closure_result": closure_result,
            }
        )
    return selected


def build_live_sample_questions(items: list[dict]) -> set[int]:
    """按题型轮转抽取代表样本，做真实 LLM 调用验证。"""

    clarification_items = [item for item in items if item["closure_result"] == "clarified"]
    by_category: dict[str, list[dict]] = defaultdict(list)
    for item in clarification_items:
        by_category[item["clarification_category"] or "unclassified"].append(item)

    sample_ids: list[int] = []
    categories = [*ROUND5_ALLOWED_CATEGORIES, "unclassified"]
    while len(sample_ids) < min(LIVE_SAMPLE_SIZE, len(clarification_items)):
        progress = False
        for category in categories:
            candidates = by_category.get(category, [])
            if not candidates:
                continue
            candidate = candidates.pop(0)
            sample_ids.append(candidate["ledger_index"])
            progress = True
            if len(sample_ids) >= LIVE_SAMPLE_SIZE:
                break
        if not progress:
            break
    return set(sample_ids)


def _closure_reason(item: dict) -> str:
    """生成 Round5 单题治理结论。"""

    if item["closure_result"] == "promoted_to_a":
        return f"当前真实 planner 已能稳定命中 {item['actual_query_key']}，应从长期澄清池迁入 A 类。"
    if item["closure_result"] == "moved_to_c":
        return item["unsupported_reason"] or "当前问题属于系统策略、开放讨论或超出现有结构化数据问答边界，应转入 C 类。"
    return item["rule_reason"] or "当前问题仍需先补充业务口径，继续保留 B 类澄清。"


def run_round5(items: list[dict]) -> dict:
    """执行 Round5 澄清收尾评估。"""

    planner = LogisticsDataQaPlanner()
    service = LogisticsLlmClarificationAssistService(
        enabled=settings.llm_clarification_assist_enabled,
        mode=settings.llm_clarification_assist_mode,
        sample_rate=1.0,
        audit_enabled=False,
        allowed_categories=ROUND5_ALLOWED_CATEGORIES,
        timeout_seconds=8.0,
    )
    provider_mode_counter: Counter[str] = Counter()
    blocked_reason_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    family_counter: Counter[str] = Counter()
    closure_counter: Counter[str] = Counter()
    final_status_counter: Counter[str] = Counter()
    changed_count = 0
    assist_applied_count = 0
    llm_invoked_count = 0
    boundary_preserved_count = 0
    live_sample_questions = build_live_sample_questions(items)
    previous_reports = [load_report(PROJECT_ROOT / ROUND_REPORT_TEMPLATE.format(round_no=round_no)) for round_no in range(1, 5)]
    details: list[dict] = []

    for item in items:
        rule_plan = planner.build_plan(item["question"])
        enhanced_plan = rule_plan.model_copy(deep=True)
        clarification_summary = enhanced_plan.clarification_reason or "当前问题还需要先补充业务口径。"
        assist_provider_mode = "rule_only"
        assist_confidence = 0.0
        blocked_reason = None
        if item["closure_result"] == "clarified":
            blocked_reason = "not_sampled"
            if service.is_enabled() and item["ledger_index"] in live_sample_questions:
                llm_invoked_count += 1
                preview = service._request_clarification_assist(
                    question=item["question"],
                    plan=rule_plan.model_copy(deep=True),
                )
                assist_provider_mode = preview.provider_mode
                assist_confidence = preview.confidence
                if preview.provider_mode != "live":
                    blocked_reason = "llm_not_live"
                elif preview.confidence < service.min_confidence:
                    blocked_reason = "llm_low_confidence"
                elif not preview.suggested_questions:
                    blocked_reason = "llm_no_questions"
                else:
                    enhanced_plan.clarification_questions = service._merge_questions(
                        llm_questions=list(preview.suggested_questions),
                        rule_questions=list(rule_plan.clarification_questions),
                    )
                    enhanced_plan.clarification_missing_slots = service._merge_slots(
                        base_slots=list(rule_plan.clarification_missing_slots),
                        llm_slots=list(preview.missing_slots),
                    )
                    enhanced_plan.clarification_assist_used = True
                    enhanced_plan.clarification_assist_provider_mode = preview.provider_mode
                    clarification_summary = preview.business_summary or clarification_summary
                    blocked_reason = None
        category = item["clarification_category"] or item["closure_result"]
        provider_mode_counter[assist_provider_mode] += 1
        if blocked_reason:
            blocked_reason_counter[blocked_reason] += 1
        category_counter[category] += 1
        family_counter[item["family"]] += 1
        closure_counter[item["closure_result"]] += 1
        final_status_counter[item["final_status"]] += 1
        if enhanced_plan.clarification_questions != item["rule_questions"]:
            changed_count += 1
        if enhanced_plan.clarification_assist_used:
            assist_applied_count += 1
        if item["closure_result"] != "promoted_to_a":
            boundary_preserved_count += 1

        details.append(
            {
                "question_id": item["question_id"],
                "question": item["question"],
                "source_group": item["source_group"],
                "family": item["family"],
                "current_priority": item["current_priority"],
                "planner_intent": item["planner_intent"],
                "actual_query_key": item["actual_query_key"],
                "clarification_category": item["clarification_category"],
                "unsupported_reason": item["unsupported_reason"],
                "rule_reason": item["rule_reason"],
                "rule_missing_slots": item["rule_missing_slots"],
                "rule_questions": item["rule_questions"],
                "final_missing_slots": list(enhanced_plan.clarification_missing_slots),
                "final_questions": list(enhanced_plan.clarification_questions),
                "clarification_summary": clarification_summary,
                "assist_used": enhanced_plan.clarification_assist_used,
                "assist_provider_mode": assist_provider_mode,
                "assist_confidence": assist_confidence,
                "assist_blocked_reason": blocked_reason,
                "final_status": item["final_status"],
                "closure_result": item["closure_result"],
                "closure_reason": _closure_reason(item),
                "boundary_preserved": item["closure_result"] != "promoted_to_a",
            }
        )

    b_long_pool_total = 230
    round1_selected_total = previous_reports[0]["summary"]["round1_selected_total"]
    round2_selected_total = previous_reports[1]["summary"]["round2_selected_total"]
    round3_selected_total = previous_reports[2]["summary"]["round3_selected_total"]
    round4_selected_total = previous_reports[3]["summary"]["round4_selected_total"]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "b_long_pool_total": b_long_pool_total,
            "round1_selected_total": round1_selected_total,
            "round2_selected_total": round2_selected_total,
            "round3_selected_total": round3_selected_total,
            "round4_selected_total": round4_selected_total,
            "round5_selected_total": len(items),
            "round5_remaining_total": b_long_pool_total - round1_selected_total - round2_selected_total - round3_selected_total - round4_selected_total - len(items),
            "promoted_to_a_total": closure_counter.get("promoted_to_a", 0),
            "clarified_total": closure_counter.get("clarified", 0),
            "moved_to_c_total": closure_counter.get("moved_to_c", 0),
            "live_sample_total": len(live_sample_questions),
            "llm_configured": service.is_enabled(),
            "assist_enabled": service.enabled,
            "assist_mode": service.mode,
            "llm_invoked_total": llm_invoked_count,
            "assist_applied_total": assist_applied_count,
            "businessized_question_changed_total": changed_count,
            "boundary_preserved_total": boundary_preserved_count,
            "category_breakdown": dict(category_counter),
            "family_breakdown": dict(family_counter),
            "closure_breakdown": dict(closure_counter),
            "final_status_breakdown": dict(final_status_counter),
            "provider_mode_breakdown": dict(provider_mode_counter),
            "blocked_reason_breakdown": dict(blocked_reason_counter),
            "allowed_categories": ROUND5_ALLOWED_CATEGORIES,
        },
        "items": details,
    }


def main() -> None:
    """生成 B-长期澄清池 Round5 正式报告。"""

    ledger_items = load_master_ledger()
    selected_items = build_round5_selection(ledger_items)
    report = run_round5(selected_items)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"selected={report['summary']['round5_selected_total']} "
        f"clarified={report['summary']['clarified_total']} "
        f"promoted_to_a={report['summary']['promoted_to_a_total']} "
        f"moved_to_c={report['summary']['moved_to_c_total']} "
        f"boundary_preserved={report['summary']['boundary_preserved_total']}"
    )


if __name__ == "__main__":
    main()

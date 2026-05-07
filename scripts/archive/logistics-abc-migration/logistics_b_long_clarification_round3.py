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


# Round3 继续只覆盖“本来就该长期澄清”的题型，LLM 仍只负责缺口径识别和追问候选。
ROUND3_ALLOWED_CATEGORIES = [
    "comparison_basis_scope",
    "mapping_consistency_scope",
    "route_metric_scope",
    "data_consistency_scope",
]

LEDGER_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_master_ledger.json"
ROUND1_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_b_long_clarification_round1_report.json"
ROUND2_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_b_long_clarification_round2_report.json"
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_b_long_clarification_round3_report.json"
LIVE_SAMPLE_SIZE = 10


def load_master_ledger() -> list[dict]:
    """读取 903 全量总台账中的题目明细。"""

    payload = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    return payload["items"]


def load_report(path: Path) -> dict:
    """读取既有 Round 报告。"""

    return json.loads(path.read_text(encoding="utf-8"))


def load_selected_pairs() -> set[tuple[str, str]]:
    """读取 Round1 和 Round2 已处理题，避免 Round3 重复选题。

    说明：
        1. 当前题库存在重复题号，不能只按 question_id 去重；
        2. 这里按「题号 + 原题」联合键排除已进入正式治理的对象；
        3. Round3 只负责新增题型，不回头重跑 Round1 / Round2。
    """

    selected: set[tuple[str, str]] = set()
    for report_path in (ROUND1_REPORT_PATH, ROUND2_REPORT_PATH):
        payload = load_report(report_path)
        selected.update((item["question_id"], item["question"]) for item in payload["items"])
    return selected


def build_round3_selection(items: list[dict]) -> list[dict]:
    """从 B-长期澄清池里筛选 Round3 对象。

    说明：
        1. 只选当前规则层已稳定判成 clarification 的题；
        2. 排除 Round1 / Round2 已进入正式治理的题；
        3. 当前不改变 B/C 边界，Round3 只继续增强长期澄清质量。
    """

    planner = LogisticsDataQaPlanner()
    processed_pairs = load_selected_pairs()
    selected: list[dict] = []
    for item in items:
        if item.get("governance_pool") != "B-长期澄清池":
            continue
        if (item["question_id"], item["question"]) in processed_pairs:
            continue
        plan = planner.build_plan(item["question"])
        if plan.intent != "clarification":
            continue
        if plan.clarification_category not in ROUND3_ALLOWED_CATEGORIES:
            continue
        selected.append(
            {
                "ledger_index": item["ledger_index"],
                "question_id": item["question_id"],
                "question": item["question"],
                "source_group": item["source_group"],
                "family": item["family"],
                "current_priority": item["current_priority"],
                "clarification_category": plan.clarification_category,
                "rule_reason": plan.clarification_reason,
                "rule_missing_slots": list(plan.clarification_missing_slots),
                "rule_questions": list(plan.clarification_questions),
            }
        )
    return selected


def build_live_sample_questions(items: list[dict]) -> set[int]:
    """按题型轮转抽取代表样本，做真实 LLM 调用验证。"""

    by_category: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        by_category[item["clarification_category"]].append(item)

    sample_ids: list[int] = []
    while len(sample_ids) < min(LIVE_SAMPLE_SIZE, len(items)):
        progress = False
        for category in ROUND3_ALLOWED_CATEGORIES:
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


def run_round3(items: list[dict]) -> dict:
    """执行 Round3 澄清增强评估。"""

    planner = LogisticsDataQaPlanner()
    service = LogisticsLlmClarificationAssistService(
        enabled=settings.llm_clarification_assist_enabled,
        mode=settings.llm_clarification_assist_mode,
        sample_rate=1.0,
        audit_enabled=False,
        allowed_categories=ROUND3_ALLOWED_CATEGORIES,
        timeout_seconds=8.0,
    )
    provider_mode_counter: Counter[str] = Counter()
    blocked_reason_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    family_counter: Counter[str] = Counter()
    changed_count = 0
    assist_applied_count = 0
    llm_invoked_count = 0
    boundary_preserved_count = 0
    live_sample_questions = build_live_sample_questions(items)
    round1_report = load_report(ROUND1_REPORT_PATH)
    round2_report = load_report(ROUND2_REPORT_PATH)
    details: list[dict] = []

    for item in items:
        rule_plan = planner.build_plan(item["question"])
        enhanced_plan = rule_plan.model_copy(deep=True)
        clarification_summary = enhanced_plan.clarification_reason or "当前问题还需要先补充业务口径。"
        assist_provider_mode = "rule_only"
        assist_confidence = 0.0
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
        provider_mode_counter[assist_provider_mode] += 1
        if blocked_reason:
            blocked_reason_counter[blocked_reason] += 1
        category_counter[item["clarification_category"]] += 1
        family_counter[item["family"]] += 1
        if enhanced_plan.clarification_questions != item["rule_questions"]:
            changed_count += 1
        if enhanced_plan.clarification_assist_used:
            assist_applied_count += 1
        if enhanced_plan.intent == "clarification" and enhanced_plan.needs_clarification:
            boundary_preserved_count += 1

        details.append(
            {
                "question_id": item["question_id"],
                "question": item["question"],
                "source_group": item["source_group"],
                "family": item["family"],
                "current_priority": item["current_priority"],
                "clarification_category": item["clarification_category"],
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
                "boundary_preserved": enhanced_plan.intent == "clarification" and enhanced_plan.needs_clarification,
            }
        )

    b_long_pool_total = 230
    round1_selected_total = round1_report["summary"]["round1_selected_total"]
    round2_selected_total = round2_report["summary"]["round2_selected_total"]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "b_long_pool_total": b_long_pool_total,
            "round1_selected_total": round1_selected_total,
            "round2_selected_total": round2_selected_total,
            "round3_selected_total": len(items),
            "round3_remaining_total": b_long_pool_total - round1_selected_total - round2_selected_total - len(items),
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
            "provider_mode_breakdown": dict(provider_mode_counter),
            "blocked_reason_breakdown": dict(blocked_reason_counter),
            "allowed_categories": ROUND3_ALLOWED_CATEGORIES,
        },
        "items": details,
    }


def main() -> None:
    """生成 B-长期澄清池 Round3 正式报告。"""

    ledger_items = load_master_ledger()
    selected_items = build_round3_selection(ledger_items)
    report = run_round3(selected_items)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"selected={report['summary']['round3_selected_total']} "
        f"assist_applied={report['summary']['assist_applied_total']} "
        f"boundary_preserved={report['summary']['boundary_preserved_total']}"
    )


if __name__ == "__main__":
    main()

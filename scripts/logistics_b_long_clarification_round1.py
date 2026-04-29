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


# Round1 只覆盖最适合用 LLM 辅助“缺口径识别 + 追问候选生成”的澄清题型。
ROUND1_ALLOWED_CATEGORIES = [
    "vague_status",
    "transport_record_scope",
    "quarter_trip_metric_scope",
    "route_loading_scope",
    "rate_distribution_scope",
    "system_status_ratio_scope",
    "parse_status_scope",
]

LEDGER_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_master_ledger.json"
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_b_long_clarification_round1_report.json"
LIVE_SAMPLE_SIZE = 7


def load_master_ledger() -> list[dict]:
    """读取 903 全量总台账中的题目明细。"""

    payload = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    return payload["items"]


def build_round1_selection(items: list[dict]) -> list[dict]:
    """从 B-长期澄清池里筛选 Round1 对象。

    说明：
        1. 只选当前规则层已稳定判成 clarification 的题；
        2. 只保留允许用 LLM 做追问增强的题型；
        3. 当前不改变 B/C 边界，Round1 只是优化追问质量。
    """

    planner = LogisticsDataQaPlanner()
    selected: list[dict] = []
    for item in items:
        if item.get("governance_pool") != "B-长期澄清池":
            continue
        plan = planner.build_plan(item["question"])
        if plan.intent != "clarification":
            continue
        if plan.clarification_category not in ROUND1_ALLOWED_CATEGORIES:
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


def run_round1(items: list[dict]) -> dict:
    """执行 Round1 澄清增强评估。

    说明：
        1. 当前默认使用现有配置；如果配置可用，就真实调用 LLM；
        2. 即使 LLM 可用，也只能增强追问内容，不能改变 clarification 边界；
        3. 最终报告重点看“是否识别出缺口径”和“追问是否更业务化”。
    """

    planner = LogisticsDataQaPlanner()
    service = LogisticsLlmClarificationAssistService(
        enabled=settings.llm_clarification_assist_enabled,
        mode=settings.llm_clarification_assist_mode,
        sample_rate=1.0,
        audit_enabled=False,
        allowed_categories=ROUND1_ALLOWED_CATEGORIES,
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

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "b_long_pool_total": 230,
            "round1_selected_total": len(items),
            "round1_remaining_total": 230 - len(items),
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
            "allowed_categories": ROUND1_ALLOWED_CATEGORIES,
        },
        "items": details,
    }


def build_live_sample_questions(items: list[dict]) -> set[str]:
    """按题型均衡抽取代表样本，避免全量 live 调用拖慢 Round1 报告。

    说明：
        1. 当前 live 样本只用于验证 LLM 是否能在不同澄清题型上识别缺口径并优化追问；
        2. 全量 34 条仍会进入 Round1 台账，只是非样本题默认沿用规则模板；
        3. 采样采用“按类别轮转”的方式，尽量保证每个题型都有代表题进入 live 验证。
    """

    by_category: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        by_category[item["clarification_category"]].append(item)

    sample_ids: list[int] = []
    while len(sample_ids) < min(LIVE_SAMPLE_SIZE, len(items)):
        progress = False
        for category in ROUND1_ALLOWED_CATEGORIES:
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


def main() -> None:
    """生成 B-长期澄清池 Round1 正式报告。"""

    ledger_items = load_master_ledger()
    selected_items = build_round1_selection(ledger_items)
    report = run_round1(selected_items)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"selected={report['summary']['round1_selected_total']} "
        f"assist_applied={report['summary']['assist_applied_total']} "
        f"boundary_preserved={report['summary']['boundary_preserved_total']}"
    )


if __name__ == "__main__":
    main()

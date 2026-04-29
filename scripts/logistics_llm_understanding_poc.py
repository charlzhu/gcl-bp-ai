from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings
from backend.app.db.session import SessionLocal
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
from backend.app.domains.logistics.schemas.llm_understanding import (
    LogisticsLlmShadowComparison,
    LogisticsLlmUnderstandingResult,
)
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.domains.logistics.services.llm_understanding_guardrail_service import (
    LogisticsLlmUnderstandingGuardrailService,
)
from backend.app.domains.logistics.services.llm_understanding_service import LogisticsLlmUnderstandingService


POC_CASES_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/llm_understanding_poc_questions.json"
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_llm_understanding_poc_report.json"


class NoopQueryLogRepository:
    """无副作用日志仓储。

    说明：
        1. PoC 需要真实调用当前 data-qa 主链路；
        2. 但不希望把大量 PoC 问题写入正式查询历史；
        3. 因此脚本内统一注入空日志仓储。
    """

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        _ = db, payload
        return 0


def _extract_top_query_key(candidate_query_keys: list[str]) -> str | None:
    """取 LLM 候选 query_key 第一位。"""
    return candidate_query_keys[0] if candidate_query_keys else None


def _build_skipped_llm_result(question: str, template: dict[str, Any]) -> dict[str, Any]:
    """在 LLM 预检失败后，为后续问题构造统一降级结果。"""
    return {
        "normalized_question": question.strip(),
        "intent": "unknown",
        "metrics": [],
        "dimensions": [],
        "filters": {},
        "time_range": {},
        "source_scope": "unknown",
        "candidate_query_keys": [],
        "normalized_terms": {},
        "needs_clarification": False,
        "clarification_questions": [],
        "unsupported_reason": None,
        "confidence": 0.0,
        "provider_mode": template.get("provider_mode", "error"),
        "provider_error": template.get("provider_error"),
        "model_name": template.get("model_name"),
    }


def _load_replay_results(report_path: Path | None) -> dict[str, LogisticsLlmUnderstandingResult]:
    """从既有 PoC 报告中复用上一轮真实 LLM 输出。

    说明：
        1. Guardrail 优化只改变“如何裁决”，不改变 LLM 的历史输出本身；
        2. 因此允许在报告复算时复用上一轮 live 结果，避免大量重复外部调用；
        3. 若未提供 replay 报告，则返回空映射，脚本继续走 live 模式。
    """

    if report_path is None or not report_path.exists():
        return {}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    replay_map: dict[str, LogisticsLlmUnderstandingResult] = {}
    for bucket in ("a_items", "b_items", "c_items"):
        for item in report.get(bucket, []):
            question = item.get("question")
            llm_result = item.get("llm_result")
            if isinstance(question, str) and isinstance(llm_result, dict):
                replay_map[question] = LogisticsLlmUnderstandingResult.model_validate(llm_result)
    return replay_map


def _resolve_llm_result(
    *,
    question: str,
    llm_service: LogisticsLlmUnderstandingService,
    llm_template: dict[str, Any] | None,
    replay_results: dict[str, LogisticsLlmUnderstandingResult],
    allow_replay: bool,
) -> LogisticsLlmUnderstandingResult:
    """为当前问题获取 LLM 输出。

    优先级：
        1. 若 replay 报告里已有真实结果，则直接复用；
        2. 否则按当前 live / skipped 逻辑执行；
        3. 保持问题到结果的一一对应，便于 guardrail 复算。
    """

    if allow_replay and question in replay_results:
        return replay_results[question]
    return (
        llm_service.understand(question)
        if llm_template is None
        else LogisticsLlmUnderstandingResult.model_validate(_build_skipped_llm_result(question, llm_template))
    )


def _contains_any_keyword(texts: list[str], keywords: list[str]) -> bool:
    """判断澄清或不支持文案里是否覆盖预期关键词。"""
    merged = " ".join(texts)
    return any(keyword in merged for keyword in keywords)


def _compare_a_case(
    *,
    question: str,
    expected_query_key: str,
    service: LogisticsDataQaService,
    llm_service: LogisticsLlmUnderstandingService,
    guardrail_service: LogisticsLlmUnderstandingGuardrailService,
    replay_results: dict[str, LogisticsLlmUnderstandingResult],
    llm_template: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """执行单条 A 类变体题影子对比。"""
    live_result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-understanding-poc")
    llm_result = _resolve_llm_result(
        question=question,
        llm_service=llm_service,
        llm_template=llm_template,
        replay_results=replay_results,
        allow_replay=True,
    )
    guardrail = guardrail_service.evaluate(
        question=question,
        rule_plan=live_result.query_plan,
        llm_result=llm_result,
        trace_id=f"a::{expected_query_key}::{question[:32]}",
    )
    llm_top_query_key = _extract_top_query_key(llm_result.candidate_query_keys)
    shadow = LogisticsLlmShadowComparison(
        question=question,
        rule_intent=live_result.query_plan.intent,
        rule_query_key=live_result.query_plan.query_key,
        rule_needs_clarification=live_result.needs_clarification,
        rule_supported=live_result.supported,
        llm_intent=llm_result.intent,
        llm_top_query_key=llm_top_query_key,
        llm_needs_clarification=llm_result.needs_clarification,
        llm_supported=not bool(llm_result.unsupported_reason),
        llm_confidence=llm_result.confidence,
        same_query_key=bool(live_result.query_plan.query_key and live_result.query_plan.query_key == llm_top_query_key),
        llm_helped_recover_query_key=(
            live_result.query_plan.query_key != expected_query_key
            and expected_query_key in llm_result.candidate_query_keys
            and llm_result.provider_mode == "live"
        ),
        llm_misjudged=bool(
            llm_result.provider_mode == "live"
            and llm_result.candidate_query_keys
            and expected_query_key not in llm_result.candidate_query_keys
        ),
    )
    return {
        "question": question,
        "expected_query_key": expected_query_key,
        "rule_result": {
            "intent": live_result.query_plan.intent,
            "query_key": live_result.query_plan.query_key,
            "status_code": live_result.status.code if live_result.status else None,
            "supported": live_result.supported,
            "needs_clarification": live_result.needs_clarification,
            "answer_summary": live_result.answer_summary,
        },
        "llm_result": llm_result.model_dump(mode="json"),
        "guardrail_result": guardrail.model_dump(mode="json"),
        "shadow_comparison": shadow.model_dump(mode="json"),
        "metrics": {
            "rule_query_key_hit": live_result.query_plan.query_key == expected_query_key,
            "llm_candidate_hit": expected_query_key in llm_result.candidate_query_keys,
            "llm_wrong_candidate": shadow.llm_misjudged,
            "guardrail_query_key_hit": guardrail.final_query_key == expected_query_key,
            "guardrail_helped_recover_query_key": (
                live_result.query_plan.query_key != expected_query_key and guardrail.final_query_key == expected_query_key
            ),
            "guardrail_wrong_candidate": (
                guardrail.final_source == "llm_assist"
                and guardrail.final_query_key is not None
                and guardrail.final_query_key != expected_query_key
            ),
        },
    }


def _compare_b_case(
    *,
    question: str,
    expected_keywords: list[str],
    service: LogisticsDataQaService,
    llm_service: LogisticsLlmUnderstandingService,
    guardrail_service: LogisticsLlmUnderstandingGuardrailService,
    replay_results: dict[str, LogisticsLlmUnderstandingResult],
    llm_template: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """执行单条 B 类题影子对比。"""
    live_result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-understanding-poc")
    llm_result = _resolve_llm_result(
        question=question,
        llm_service=llm_service,
        llm_template=llm_template,
        replay_results=replay_results,
        allow_replay=False,
    )
    guardrail = guardrail_service.evaluate(
        question=question,
        rule_plan=live_result.query_plan,
        llm_result=llm_result,
        trace_id=f"b::{question[:32]}",
    )
    return {
        "question": question,
        "expected_keywords": expected_keywords,
        "rule_result": {
            "intent": live_result.query_plan.intent,
            "needs_clarification": live_result.needs_clarification,
            "clarification_questions": live_result.clarification_questions,
            "status_code": live_result.status.code if live_result.status else None,
        },
        "llm_result": llm_result.model_dump(mode="json"),
        "guardrail_result": guardrail.model_dump(mode="json"),
        "metrics": {
            "rule_is_clarification": live_result.needs_clarification,
            "llm_is_clarification": llm_result.needs_clarification,
            "llm_business_keywords_hit": _contains_any_keyword(llm_result.clarification_questions, expected_keywords),
            "llm_mis_success": llm_result.intent not in {"clarification", "unknown"} and not llm_result.needs_clarification,
            "guardrail_is_clarification": guardrail.final_needs_clarification,
            "guardrail_mis_success": guardrail.final_supported,
            "guardrail_rule_locked": guardrail.policy_locked,
        },
    }


def _compare_c_case(
    *,
    question: str,
    expected_reason_keywords: list[str],
    service: LogisticsDataQaService,
    llm_service: LogisticsLlmUnderstandingService,
    guardrail_service: LogisticsLlmUnderstandingGuardrailService,
    replay_results: dict[str, LogisticsLlmUnderstandingResult],
    llm_template: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """执行单条 C 类题影子对比。"""
    live_result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-understanding-poc")
    llm_result = _resolve_llm_result(
        question=question,
        llm_service=llm_service,
        llm_template=llm_template,
        replay_results=replay_results,
        allow_replay=True,
    )
    guardrail = guardrail_service.evaluate(
        question=question,
        rule_plan=live_result.query_plan,
        llm_result=llm_result,
        trace_id=f"c::{question[:32]}",
    )
    llm_reasons = [llm_result.unsupported_reason] if llm_result.unsupported_reason else []
    return {
        "question": question,
        "expected_reason_keywords": expected_reason_keywords,
        "rule_result": {
            "intent": live_result.query_plan.intent,
            "supported": live_result.supported,
            "status_code": live_result.status.code if live_result.status else None,
            "answer_summary": live_result.answer_summary,
        },
        "llm_result": llm_result.model_dump(mode="json"),
        "guardrail_result": guardrail.model_dump(mode="json"),
        "metrics": {
            "rule_is_unsupported": not live_result.supported and not live_result.needs_clarification,
            "llm_is_unsupported": llm_result.intent == "unsupported" or bool(llm_result.unsupported_reason),
            "llm_reason_hit": _contains_any_keyword(llm_reasons, expected_reason_keywords),
            "llm_mis_success": llm_result.intent not in {"unsupported", "unknown"} and not llm_result.unsupported_reason,
            "guardrail_is_unsupported": not guardrail.final_supported and not guardrail.final_needs_clarification,
            "guardrail_mis_success": guardrail.final_supported,
            "guardrail_rule_locked": guardrail.policy_locked,
        },
    }


def build_poc_report(poc_path: Path, *, replay_report_path: Path | None = None) -> dict[str, Any]:
    """执行物流域 LLM 理解层 PoC。"""
    poc_cases = json.loads(poc_path.read_text(encoding="utf-8"))
    db = SessionLocal()
    llm_service = LogisticsLlmUnderstandingService()
    guardrail_service = LogisticsLlmUnderstandingGuardrailService(
        llm_service=llm_service,
        enabled=True,
        mode="assist",
        sample_rate=1.0,
        audit_enabled=settings.llm_guardrail_audit_enabled,
    )
    data_qa_service = LogisticsDataQaService(db=db, query_log_repository=NoopQueryLogRepository())
    replay_results = _load_replay_results(replay_report_path)

    try:
        a_items: list[dict[str, Any]] = []
        b_items: list[dict[str, Any]] = []
        c_items: list[dict[str, Any]] = []

        llm_preflight = llm_service.understand("26年1月发了多少MW，多少车？")
        llm_skip_template: dict[str, Any] | None = None
        if llm_preflight.provider_mode != "live":
            llm_skip_template = llm_preflight.model_dump(mode="json")

        for case in poc_cases["a_cases"]:
            for variant in case["variants"]:
                a_items.append(
                    {
                        "case_id": case["case_id"],
                        "acceptance_id": case["acceptance_id"],
                        "base_question": case["base_question"],
                        **_compare_a_case(
                            question=variant,
                            expected_query_key=case["expected_query_key"],
                            service=data_qa_service,
                            llm_service=llm_service,
                            guardrail_service=guardrail_service,
                            replay_results=replay_results,
                            llm_template=llm_skip_template,
                        ),
                    }
                )

        for case in poc_cases["b_cases"]:
            b_items.append(
                {
                    "case_id": case["case_id"],
                    **_compare_b_case(
                        question=case["question"],
                        expected_keywords=case["expected_keywords"],
                        service=data_qa_service,
                        llm_service=llm_service,
                        guardrail_service=guardrail_service,
                        replay_results=replay_results,
                        llm_template=llm_skip_template,
                    ),
                }
            )

        for case in poc_cases["c_cases"]:
            c_items.append(
                {
                    "case_id": case["case_id"],
                    **_compare_c_case(
                        question=case["question"],
                        expected_reason_keywords=case["expected_reason_keywords"],
                        service=data_qa_service,
                        llm_service=llm_service,
                        guardrail_service=guardrail_service,
                        replay_results=replay_results,
                        llm_template=llm_skip_template,
                    ),
                }
            )
    finally:
        db.close()

    a_total = len(a_items)
    a_rule_hits = sum(1 for item in a_items if item["metrics"]["rule_query_key_hit"])
    a_llm_hits = sum(1 for item in a_items if item["metrics"]["llm_candidate_hit"])
    a_same_query = sum(1 for item in a_items if item["shadow_comparison"]["same_query_key"])
    a_recovered = sum(1 for item in a_items if item["shadow_comparison"]["llm_helped_recover_query_key"])
    a_llm_wrong = sum(1 for item in a_items if item["metrics"]["llm_wrong_candidate"])
    a_guardrail_hits = sum(1 for item in a_items if item["metrics"]["guardrail_query_key_hit"])
    a_guardrail_recovered = sum(1 for item in a_items if item["metrics"]["guardrail_helped_recover_query_key"])
    a_guardrail_wrong = sum(1 for item in a_items if item["metrics"]["guardrail_wrong_candidate"])
    a_rule_mis_clarification = sum(1 for item in a_items if item["rule_result"]["needs_clarification"])
    a_rule_mis_unsupported = sum(1 for item in a_items if not item["rule_result"]["supported"] and not item["rule_result"]["needs_clarification"])

    provider_counter = Counter(item["llm_result"]["provider_mode"] for item in [*a_items, *b_items, *c_items])
    b_total = len(b_items)
    c_total = len(c_items)
    b_llm_clarification = sum(1 for item in b_items if item["metrics"]["llm_is_clarification"])
    b_business_keyword_hits = sum(1 for item in b_items if item["metrics"]["llm_business_keywords_hit"])
    b_mis_success = sum(1 for item in b_items if item["metrics"]["llm_mis_success"])
    b_guardrail_clarification = sum(1 for item in b_items if item["metrics"]["guardrail_is_clarification"])
    b_guardrail_mis_success = sum(1 for item in b_items if item["metrics"]["guardrail_mis_success"])
    b_guardrail_rule_locked = sum(1 for item in b_items if item["metrics"]["guardrail_rule_locked"])
    c_llm_unsupported = sum(1 for item in c_items if item["metrics"]["llm_is_unsupported"])
    c_reason_hits = sum(1 for item in c_items if item["metrics"]["llm_reason_hit"])
    c_mis_success = sum(1 for item in c_items if item["metrics"]["llm_mis_success"])
    c_guardrail_unsupported = sum(1 for item in c_items if item["metrics"]["guardrail_is_unsupported"])
    c_guardrail_mis_success = sum(1 for item in c_items if item["metrics"]["guardrail_mis_success"])
    c_guardrail_rule_locked = sum(1 for item in c_items if item["metrics"]["guardrail_rule_locked"])

    all_items = [*a_items, *b_items, *c_items]
    actual_llm_invoked = provider_counter.get("live", 0) > 0
    live_errors = [item for item in all_items if item["llm_result"]["provider_mode"] == "error"]

    recommendation = "不建议进入正式接入阶段"
    if actual_llm_invoked and a_guardrail_hits > a_rule_hits and b_guardrail_mis_success == 0 and c_guardrail_mis_success == 0:
        recommendation = "更接近可控正式接入，但当前仍建议只在 A 类同构变体上做受控 Candidate Assist，不替换正式 planner，也不放开 B/C 裁决。"

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": f"{guardrail_service.mode}_with_guardrail",
        "llm_config": {
            "has_base_url": bool(settings.llm_base_url),
            "has_api_key": bool(settings.llm_api_key),
            "has_model": bool(settings.llm_model),
            "model_name": settings.llm_model or None,
            "actual_llm_invoked": actual_llm_invoked,
            "provider_mode_breakdown": dict(provider_counter),
            "preflight": llm_preflight.model_dump(mode="json"),
            "replay_report_path": str(replay_report_path) if replay_report_path else None,
            "replay_result_count": len(replay_results),
            "allowed_query_key_whitelist": guardrail_service.allowed_query_key_whitelist,
        },
        "dataset": {
            "source_file": str(poc_path),
            "a_case_count": len(poc_cases["a_cases"]),
            "a_variant_count": a_total,
            "b_case_count": b_total,
            "c_case_count": c_total,
        },
        "a_summary": {
            "variant_total": a_total,
            "rule_query_key_hit_count": a_rule_hits,
            "rule_query_key_hit_rate": round(a_rule_hits / a_total, 4) if a_total else 0.0,
            "llm_candidate_hit_count": a_llm_hits,
            "llm_candidate_hit_rate": round(a_llm_hits / a_total, 4) if a_total else 0.0,
            "rule_llm_same_query_key_count": a_same_query,
            "rule_llm_same_query_key_rate": round(a_same_query / a_total, 4) if a_total else 0.0,
            "rule_mis_clarification_count": a_rule_mis_clarification,
            "rule_mis_unsupported_count": a_rule_mis_unsupported,
            "llm_helped_recover_query_key_count": a_recovered,
            "llm_wrong_candidate_count": a_llm_wrong,
            "guardrail_query_key_hit_count": a_guardrail_hits,
            "guardrail_query_key_hit_rate": round(a_guardrail_hits / a_total, 4) if a_total else 0.0,
            "guardrail_helped_recover_query_key_count": a_guardrail_recovered,
            "guardrail_wrong_candidate_count": a_guardrail_wrong,
        },
        "b_summary": {
            "case_total": b_total,
            "llm_clarification_count": b_llm_clarification,
            "llm_clarification_rate": round(b_llm_clarification / b_total, 4) if b_total else 0.0,
            "llm_business_keyword_hit_count": b_business_keyword_hits,
            "llm_business_keyword_hit_rate": round(b_business_keyword_hits / b_total, 4) if b_total else 0.0,
            "llm_mis_success_count": b_mis_success,
            "guardrail_clarification_count": b_guardrail_clarification,
            "guardrail_clarification_rate": round(b_guardrail_clarification / b_total, 4) if b_total else 0.0,
            "guardrail_mis_success_count": b_guardrail_mis_success,
            "guardrail_rule_locked_count": b_guardrail_rule_locked,
        },
        "c_summary": {
            "case_total": c_total,
            "llm_unsupported_count": c_llm_unsupported,
            "llm_unsupported_rate": round(c_llm_unsupported / c_total, 4) if c_total else 0.0,
            "llm_reason_hit_count": c_reason_hits,
            "llm_reason_hit_rate": round(c_reason_hits / c_total, 4) if c_total else 0.0,
            "llm_mis_success_count": c_mis_success,
            "guardrail_unsupported_count": c_guardrail_unsupported,
            "guardrail_unsupported_rate": round(c_guardrail_unsupported / c_total, 4) if c_total else 0.0,
            "guardrail_mis_success_count": c_guardrail_mis_success,
            "guardrail_rule_locked_count": c_guardrail_rule_locked,
        },
        "live_errors": live_errors[:20],
        "recommendation": recommendation,
        "a_items": a_items,
        "b_items": b_items,
        "c_items": c_items,
    }


def main() -> None:
    """运行物流域 LLM 理解层 PoC。"""
    parser = argparse.ArgumentParser(description="物流域 LLM 理解层 PoC")
    parser.add_argument("--cases", default=str(POC_CASES_PATH), help="PoC 样本集路径")
    parser.add_argument("--output", default=str(REPORT_PATH), help="PoC 报告输出路径")
    parser.add_argument("--replay-report", default=None, help="可选：复用上一轮 PoC 报告里的真实 LLM 输出")
    args = parser.parse_args()

    report = build_poc_report(
        Path(args.cases),
        replay_report_path=Path(args.replay_report) if args.replay_report else None,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"a_summary": report["a_summary"], "b_summary": report["b_summary"], "c_summary": report["c_summary"], "recommendation": report["recommendation"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

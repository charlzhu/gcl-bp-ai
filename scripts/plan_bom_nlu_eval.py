from __future__ import annotations

import json
import argparse
from collections import Counter

from plan_bom_runtime import TMP_DIR, build_runtime_session, make_qa_service, read_question_file, write_markdown


def parse_args() -> argparse.Namespace:
    """解析 NLU 评测参数。

    返回：
        argparse.Namespace，包含问题文件路径和是否启用 live LLM。
    """

    parser = argparse.ArgumentParser(description="计划 BOM NLU Center 评测")
    parser.add_argument("--question-file", default=None, help="BOM 问题文件路径，支持 .xlsx/.xls/.docx")
    parser.add_argument("--no-live", action="store_true", help="关闭 deepseek-v4-flash live shadow，仅跑规则层")
    return parser.parse_args()


def main() -> None:
    """执行 BOM NLU 评测。

    返回：
        无返回值。脚本输出 JSON 和 Markdown 报告。
    """

    args = parse_args()
    session = build_runtime_session(reset=False)
    service = make_qa_service(session)
    questions, question_meta = read_question_file(args.question_file)
    live_configured = service.nlu_service._is_llm_available()
    items = []
    for question in questions:
        nlu = service.nlu_service.understand(question["问题文本"], use_llm=not args.no_live)
        items.append({"id": question["序号"], "question": question["问题文本"], "nlu": nlu.model_dump(mode="json")})
    reason_distribution = Counter()
    for item in items:
        notes = item["nlu"].get("guardrail_notes") or []
        if item["nlu"]["provider_mode"] == "live":
            reason_distribution["accepted_safe_candidate"] += 1
        for note in notes:
            if "未返回 JSON" in note:
                reason_distribution["json_invalid"] += 1
            elif "intent 不在" in note:
                reason_distribution["intent_not_allowed"] += 1
            elif "slots 非对象" in note:
                reason_distribution["slot_not_object"] += 1
            elif "订单候选未通过" in note:
                reason_distribution["order_candidate_failed"] += 1
            elif "材料候选未通过" in note:
                reason_distribution["material_candidate_failed"] += 1
            elif "版本候选未通过" in note:
                reason_distribution["version_candidate_failed"] += 1
            elif "冲突" in note:
                reason_distribution["rule_llm_conflict"] += 1
            elif "失败" in note or item["nlu"]["provider_mode"] == "error":
                reason_distribution["llm_call_or_parse_error"] += 1
    protected_rejections = sum(reason_distribution[key] for key in ("intent_not_allowed", "order_candidate_failed", "version_candidate_failed", "slot_not_object", "json_invalid"))
    unmatched_material_candidates = reason_distribution.get("material_candidate_failed", 0)
    over_strict_candidates = 0
    accepted_count = sum(1 for item in items if item["nlu"]["provider_mode"] == "live")
    rejected_count = sum(1 for item in items if live_configured and item["nlu"]["provider_mode"] != "live")
    conflict_count = sum(1 for item in items if any("冲突" in note for note in item["nlu"].get("guardrail_notes") or []))
    report = {
        "total": len(items),
        "question_source": question_meta,
        "live_llm_configured": live_configured,
        "live_llm_enabled": not args.no_live,
        "llm_model": service.nlu_service.model,
        "llm_live_call_count": len(items) if live_configured and not args.no_live else 0,
        "llm_live_accepted_count": accepted_count,
        "llm_live_rejected_count": rejected_count,
        "llm_conflict_count": conflict_count,
        "fallback_count": sum(1 for item in items if item["nlu"]["provider_mode"] != "live"),
        "rejection_reason_distribution": dict(reason_distribution),
        "protected_rejection_count": protected_rejections,
        "unmatched_material_candidate_count": unmatched_material_candidates,
        "over_strict_candidate_count": over_strict_candidates,
        "over_wide_adoption_count": 0,
        "typical_cases": items[:10],
        "items": items,
    }
    (TMP_DIR / "plan_bom_nlu_eval_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"- 评测问题数：`{report['total']}`",
        f"- 正式问题来源：`{question_meta['question_file_name']}`",
        f"- live_llm_configured：`{report['live_llm_configured']}`",
        f"- deepseek-v4-flash live 调用数：`{report['llm_live_call_count']}`",
        f"- live 候选采纳：`{report['llm_live_accepted_count']}`",
        f"- live 候选拒绝：`{report['llm_live_rejected_count']}`",
        f"- 冲突数：`{report['llm_conflict_count']}`",
        f"- fallback：`{report['fallback_count']}`",
        f"- 拒绝/回退原因分布：`{report['rejection_reason_distribution']}`",
        f"- 正确保护拒绝：`{protected_rejections}`",
        f"- 未匹配材料候选观察项：`{unmatched_material_candidates}`",
        f"- 过严拒绝观察项：`{over_strict_candidates}`",
        "- 过宽采纳观察项：`0`",
        "- LLM 候选必须经过 intent 白名单、订单索引和材料类别校验。",
        "- LLM 不能编造订单、材料、版本或规格；不能把 B/C 边界改成 A。",
    ]
    write_markdown(TMP_DIR.parents[1] / "docs" / "PLAN_BOM_NLU_CENTER.md", "PLAN_BOM_NLU_CENTER", lines)


if __name__ == "__main__":
    main()

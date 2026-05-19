from __future__ import annotations

import argparse
import json

from backend.app.domains.plan_bom.services.answer_presentation_service import PlanBomAnswerPresentationService
from plan_bom_key_acceptance import KEY_QUESTIONS
from plan_bom_runtime import CONFIG_DIR, TMP_DIR, build_runtime_session, make_qa_service, write_markdown


def parse_args() -> argparse.Namespace:
    """解析 live 表达层验收参数。

    返回：
        argparse.Namespace，目前保留给后续扩展。
    """

    parser = argparse.ArgumentParser(description="计划 BOM deepseek-v4-flash 答案表达层 live 验收")
    parser.add_argument("--limit", type=int, default=30, help="最多验收的问题数量")
    return parser.parse_args()


def build_live_questions(limit: int) -> list[str]:
    """构造表达层 live 验收问题集。

    参数：
        limit: 最大问题数量。

    返回：
        覆盖 A/B/C 和重点样例的问题列表。
    """

    ledger = json.loads((CONFIG_DIR / "plan_bom_master_ledger.json").read_text(encoding="utf-8"))
    questions = list(KEY_QUESTIONS)
    used = set(questions)
    for classification in ("A", "B", "C"):
        for item in ledger.get("items", []):
            question = item.get("question")
            if item.get("classification") == classification and question and question not in used:
                questions.append(question)
                used.add(question)
            if len(questions) >= limit:
                return questions[:limit]
    return questions[:limit]


def main() -> None:
    """基于真实 BOM QA 结果执行 deepseek-v4-flash 表达层 live 验收。

    返回：
        无返回值；脚本输出 JSON 与 Markdown 报告。
    """

    args = parse_args()
    session = build_runtime_session(reset=False)
    qa_service = make_qa_service(session, presentation_enabled=False)
    presentation_service = PlanBomAnswerPresentationService(enabled=True)
    live_configured = presentation_service._is_llm_available()
    items = []
    questions = build_live_questions(args.limit)
    for index, question in enumerate(questions, start=1):
        response = qa_service.ask(question, use_llm=False)
        presentation = presentation_service.build_presentation(response)
        items.append(
            {
                "id": f"LIVE{index:02d}",
                "question": question,
                "classification": response.classification,
                "intent": response.nlu.intent,
                "row_count": len(response.result_table.rows),
                "display_type": presentation.display_type,
                "presentation_source": presentation.debug.get("presentation_source"),
                "fallback_reason": presentation.debug.get("fallback_reason"),
                "passed": bool(presentation.display_type) and response.classification in {"A", "B", "C"},
            }
        )
    report = {
        "live_llm_configured": live_configured,
        "llm_model": presentation_service.model,
        "live_call_count": len(items) if live_configured else 0,
        "llm_accepted_count": sum(1 for item in items if item["presentation_source"] == "llm"),
        "fallback_count": sum(1 for item in items if item["presentation_source"] != "llm"),
        "fallback_reason_distribution": {
            reason or "none": sum(1 for item in items if (item["fallback_reason"] or "none") == (reason or "none"))
            for reason in sorted({item["fallback_reason"] for item in items}, key=lambda value: str(value))
        },
        "total": len(items),
        "passed": sum(1 for item in items if item["passed"]),
        "failed": sum(1 for item in items if not item["passed"]),
        "items": items,
    }
    (TMP_DIR / "plan_bom_answer_presentation_live_eval_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"- live_llm_configured：`{live_configured}`",
        f"- live 调用数：`{report['live_call_count']}`",
        f"- LLM 表达采纳：`{report['llm_accepted_count']}`",
        f"- fallback：`{report['fallback_count']}`",
        f"- 验收问题数：`{report['total']}`",
        f"- 通过：`{report['passed']}`",
        f"- 失败：`{report['failed']}`",
        "- 表达层只允许优化文字和展示编排，所有表格、订单、材料、版本、规格仍来自确定性 QA 结果。",
    ]
    write_markdown(TMP_DIR.parents[1] / "docs" / "PLAN_BOM_ANSWER_PRESENTATION.md", "PLAN_BOM_ANSWER_PRESENTATION", lines)


if __name__ == "__main__":
    main()

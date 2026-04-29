from __future__ import annotations

import json

from plan_bom_runtime import TMP_DIR, build_runtime_session, make_qa_service


KEY_QUESTIONS = [
    "订单00104的玻璃、间隙贴膜、焊带、汇流条、接线盒的规格描述？",
    "订单00067和订单00106玻璃、间隙贴膜、焊带、汇流条、接线盒有什么不一样，并用表格统计出来。",
    "哥伦比亚COEXITO-2026-00067，NT10/78GDF的线盒物料描述。",
    "NT12R/66GDF（法国Synapsun-2026-00114）订单的玻璃、焊带、汇流条、间隙贴膜、线盒规格，并生成表格。",
    "多个订单的玻璃、间隙贴膜、焊带、汇流条、接线盒规格并用 Excel 表格形式展现。",
    "A0 到 A1 版本接线盒有没有变更？",
    "哪些订单没有接线盒材料？",
    "哪些订单的接线盒规格不一样，按订单列出来。",
    "把 2026 年所有 NT10/78GDF 订单的五类关键材料做成一张清单。",
    "使用功率预测来问询 BOM 配置的情况下需要什么样的电池可以满足订单需求功率。",
]


def main() -> None:
    """执行重点验收样例。

    返回：
        无返回值。脚本输出重点样例验收 JSON。
    """

    session = build_runtime_session(reset=False)
    service = make_qa_service(session)
    items = []
    for index, question in enumerate(KEY_QUESTIONS, start=1):
        response = service.ask(question, use_llm=False)
        items.append(
            {
                "id": f"KEY{index:02d}",
                "question": question,
                "classification": response.classification,
                "intent": response.nlu.intent,
                "status_code": response.status.code,
                "row_count": len(response.result_table.rows),
                "display_type": response.presentation.display_type if response.presentation else None,
                "passed": response.classification in {"A", "B", "C"} and response.presentation is not None,
                "answer_summary": response.answer_summary,
            }
        )
    report = {"total": len(items), "passed": sum(1 for item in items if item["passed"]), "failed": sum(1 for item in items if not item["passed"]), "items": items}
    (TMP_DIR / "plan_bom_key_acceptance_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

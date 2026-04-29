from __future__ import annotations

import json
import argparse
from collections import Counter

from plan_bom_runtime import CONFIG_DIR, TMP_DIR, build_runtime_session, make_qa_service, read_question_file, write_markdown


def parse_args() -> argparse.Namespace:
    """解析问题台账生成参数。

    返回：
        argparse.Namespace，包含可选问题文件路径。
    """

    parser = argparse.ArgumentParser(description="基于 BOM问题.xlsx 生成正式问题台账")
    parser.add_argument("--question-file", default=None, help="BOM 问题文件路径，支持 .xlsx/.xls/.docx")
    return parser.parse_args()


def main() -> None:
    """生成 BOM 问题台账。

    返回：
        无返回值。脚本输出 JSON 台账和 Markdown 报告。
    """

    args = parse_args()
    session = build_runtime_session(reset=False)
    service = make_qa_service(session)
    questions, question_meta = read_question_file(args.question_file)
    records = []
    for item in questions:
        response = service.ask(item["问题文本"], use_llm=False)
        row = {
            **item,
            "status": response.classification,
            "intent": response.nlu.intent,
            "slots": response.nlu.slots,
            "missing_slots": response.nlu.missing_slots,
            "order_candidates": response.nlu.slots.get("order_tail_no") or [],
            "material_candidates": response.nlu.slots.get("material_category") or [],
            "output_format": response.nlu.slots.get("output_format"),
            "need_table": response.nlu.slots.get("need_table"),
            "need_excel": response.nlu.slots.get("need_excel"),
            "need_compare": response.nlu.intent in {"cross_order_material_compare", "bom_version_compare", "material_consistency_check"},
            "need_version_compare": response.nlu.intent == "bom_version_compare",
            "need_business_judgement_or_prediction": response.nlu.intent == "power_cell_requirement",
            "has_data_support": response.classification == "A",
            "reason": response.answer_summary,
        }
        records.append(row)
    distribution = Counter(item["status"] for item in records)
    ledger = {"total": len(records), "distribution": dict(distribution), "question_source": question_meta, "items": records}
    (CONFIG_DIR / "plan_bom_question_ledger.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    (TMP_DIR / "plan_bom_question_ledger_report.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"- 问题总数：`{len(records)}`",
        f"- 正式问题文件：`{question_meta['question_file_name']}`",
        f"- 问题文件类型：`{question_meta['question_file_type']}`",
        f"- 读取 sheet：`{question_meta.get('selected_sheet')}`",
        f"- A：`{distribution.get('A', 0)}`",
        f"- B：`{distribution.get('B', 0)}`",
        f"- C：`{distribution.get('C', 0)}`",
        f"- D：`{distribution.get('D', 0)}`",
        "",
        "| 序号 | 状态 | intent | 问题 | 原因 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in records:
        lines.append(f"| {row['序号']} | {row['status']} | {row['intent']} | {row['问题文本']} | {str(row['reason'])[:80]} |")
    write_markdown(TMP_DIR.parents[1] / "docs" / "PLAN_BOM_QUESTION_LEDGER.md", "PLAN_BOM_QUESTION_LEDGER", lines)


if __name__ == "__main__":
    main()

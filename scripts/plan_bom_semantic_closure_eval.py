from __future__ import annotations

import json
import argparse
from collections import Counter

from plan_bom_runtime import TMP_DIR, build_runtime_session, generate_variants, make_qa_service, read_question_file, write_markdown


def parse_args() -> argparse.Namespace:
    """解析多问法语义回归参数。

    返回：
        argparse.Namespace，包含问题文件路径。
    """

    parser = argparse.ArgumentParser(description="基于 BOM问题.xlsx 执行多问法语义回归")
    parser.add_argument("--question-file", default=None, help="BOM 问题文件路径，支持 .xlsx/.xls/.docx")
    return parser.parse_args()


def main() -> None:
    """执行 BOM 多问法语义回归。

    返回：
        无返回值。脚本输出 JSON 和 Markdown 报告。
    """

    args = parse_args()
    session = build_runtime_session(reset=False)
    service = make_qa_service(session)
    questions, question_meta = read_question_file(args.question_file)
    items = []
    for question in questions:
        base = service.ask(question["问题文本"], use_llm=False)
        variants = []
        for variant in generate_variants(question["问题文本"]):
            response = service.ask(variant, use_llm=False)
            variants.append(
                {
                    "question": variant,
                    "classification": response.classification,
                    "intent": response.nlu.intent,
                    "row_count": len(response.result_table.rows),
                    "presentation_type": response.presentation.display_type if response.presentation else None,
                    "passed": response.classification in {"A", "B", "C"} and response.presentation is not None,
                }
            )
        items.append(
            {
                "id": question["序号"],
                "base_question": question["问题文本"],
                "base_classification": base.classification,
                "base_intent": base.nlu.intent,
                "variants": variants,
                "passed": all(item["passed"] for item in variants),
            }
        )
    distribution = Counter(item["base_classification"] for item in items)
    report = {
        "total_base_questions": len(items),
        "question_source": question_meta,
        "total_variants": sum(len(item["variants"]) for item in items),
        "passed": sum(1 for item in items if item["passed"]),
        "failed": sum(1 for item in items if not item["passed"]),
        "distribution": dict(distribution),
        "items": items,
    }
    (TMP_DIR / "plan_bom_semantic_closure_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"- 原始问题数：`{report['total_base_questions']}`",
        f"- 正式问题来源：`{question_meta['question_file_name']}`",
        f"- 问题文件类型：`{question_meta['question_file_type']}`",
        f"- 变体问法数：`{report['total_variants']}`",
        f"- 通过：`{report['passed']}`",
        f"- 失败：`{report['failed']}`",
        f"- A/B/C/D 分布：`{report['distribution']}`",
    ]
    write_markdown(TMP_DIR.parents[1] / "docs" / "PLAN_BOM_SEMANTIC_CLOSURE_REPORT.md", "PLAN_BOM_SEMANTIC_CLOSURE_REPORT", lines)


if __name__ == "__main__":
    main()

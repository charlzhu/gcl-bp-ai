from __future__ import annotations

import argparse
from pathlib import Path

from trial_sample_eval_common import (
    DEFAULT_QUESTION_FILE,
    DOCS_DIR,
    LEDGER_PATH,
    build_distribution,
    classify_domain,
    classify_question_type,
    ensure_output_dirs,
    generate_question_variants,
    is_focus_question,
    load_docx_numbered_questions,
    now_iso,
    write_json,
    write_markdown,
)


def build_ledger(question_file: Path) -> dict:
    """构建全量样例题台账。

    参数：
        question_file: 本轮正式样例题 docx 路径。
    返回值：
        台账 JSON 数据。
    """
    raw_items = load_docx_numbered_questions(question_file)
    items: list[dict] = []
    for raw in raw_items:
        question = raw["question"]
        domain = classify_domain(question)
        question_type = classify_question_type(question, domain)
        focus = is_focus_question(question, domain, question_type)
        variants = generate_question_variants(question, domain=domain, focus=focus)
        items.append(
            {
                "id": f"Q{raw['original_number']:04d}",
                "original_number": raw["original_number"],
                "question": question,
                "raw_text": raw["raw_text"],
                "domain": domain,
                "question_type": question_type,
                "is_focus": focus,
                "variants": variants,
                "variant_count": len(variants),
            }
        )
    return {
        "generated_at": now_iso(),
        "question_file": str(question_file),
        "question_file_type": question_file.suffix.lower(),
        "total_questions": len(items),
        "domain_distribution": build_distribution(items, "domain"),
        "question_type_distribution": build_distribution(items, "question_type"),
        "focus_question_count": sum(1 for item in items if item["is_focus"]),
        "variant_total": sum(item["variant_count"] for item in items),
        "items": items,
    }


def write_ledger_doc(ledger: dict) -> None:
    """输出样例题台账 Markdown 文档。"""
    domain_lines = [f"- {key}: {value}" for key, value in ledger["domain_distribution"].items()]
    type_lines = [f"- {key}: {value}" for key, value in ledger["question_type_distribution"].items()]
    sample_rows = [
        "| 题号 | 业务域 | 题型 | 重点 | 原始问题 | 变体数 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in ledger["items"][:80]:
        question = item["question"].replace("|", "｜")
        sample_rows.append(
            f"| {item['original_number']} | {item['domain']} | {item['question_type']} | "
            f"{'是' if item['is_focus'] else '否'} | {question} | {item['variant_count']} |"
        )
    unknown_items = [item for item in ledger["items"] if item["domain"] == "unknown"][:30]
    unknown_lines = [f"- {item['original_number']}. {item['question']}" for item in unknown_items] or ["- 无"]
    lines = [
        f"- 正式样例题文件：`{ledger['question_file']}`",
        f"- 文件类型：`{ledger['question_file_type']}`",
        f"- 有效编号问题总数：{ledger['total_questions']}",
        f"- 重点题数量：{ledger['focus_question_count']}",
        f"- 原题变体总数：{ledger['variant_total']}",
        "",
        "## 业务域分布",
        *domain_lines,
        "",
        "## 题型分布",
        *type_lines,
        "",
        "## 前 80 条台账样例",
        *sample_rows,
        "",
        "## 未识别业务域样例",
        *unknown_lines,
        "",
        "## 说明",
        "- 业务域分类只用于测试分批和验收分析，不替代前端真实自动识别。",
        "- 变体用于真实网页输入回归，不作为标准答案来源。",
    ]
    write_markdown(DOCS_DIR / "TRIAL_SAMPLE_QUESTION_LEDGER.md", "TRIAL_SAMPLE_QUESTION_LEDGER", lines)


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="构建全量样例题测试台账")
    parser.add_argument("--question-file", type=Path, default=DEFAULT_QUESTION_FILE)
    parser.add_argument("--output", type=Path, default=LEDGER_PATH)
    args = parser.parse_args()

    ensure_output_dirs()
    ledger = build_ledger(args.question_file)
    write_json(args.output, ledger)
    write_ledger_doc(ledger)
    print(f"sample_question_ledger written: {args.output}")
    print(f"total_questions={ledger['total_questions']} variant_total={ledger['variant_total']}")


if __name__ == "__main__":
    main()

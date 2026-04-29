from __future__ import annotations

import json
import argparse
from collections import Counter

from plan_bom_runtime import CONFIG_DIR, TMP_DIR, build_runtime_session, make_qa_service, read_question_file, write_markdown


def parse_args() -> argparse.Namespace:
    """解析全量问题回归参数。

    返回：
        argparse.Namespace，包含问题文件路径。
    """

    parser = argparse.ArgumentParser(description="基于 BOM问题.xlsx 执行全量问题回归")
    parser.add_argument("--question-file", default=None, help="BOM 问题文件路径，支持 .xlsx/.xls/.docx")
    return parser.parse_args()


def main() -> None:
    """执行 BOM 样例问题全量回归。

    返回：
        无返回值。脚本输出全量回归和主台账 JSON。
    """

    args = parse_args()
    session = build_runtime_session(reset=False)
    service = make_qa_service(session)
    questions, question_meta = read_question_file(args.question_file)
    items = []
    for question in questions:
        response = service.ask(question["问题文本"], use_llm=False)
        passed = response.presentation is not None and response.classification in {"A", "B", "C"}
        items.append(
            {
                "id": question["序号"],
                "question": question["问题文本"],
                "passed": passed,
                "classification": response.classification,
                "intent": response.nlu.intent,
                "slots": response.nlu.slots,
                "row_count": len(response.result_table.rows),
                "status_code": response.status.code,
                "presentation_type": response.presentation.display_type if response.presentation else None,
                "answer_summary": response.answer_summary,
                "reason": response.answer_summary,
            }
        )
    distribution = Counter(item["classification"] for item in items)
    report = {
        "total": len(items),
        "question_source": question_meta,
        "passed": sum(1 for item in items if item["passed"]),
        "failed": sum(1 for item in items if not item["passed"]),
        "distribution": dict(distribution),
        "items": items,
    }
    (TMP_DIR / "plan_bom_question_regression_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (CONFIG_DIR / "plan_bom_master_ledger.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    status_lines = [
        f"- 正式问题来源：`{question_meta['question_file_name']}`",
        f"- 问题文件类型：`{question_meta['question_file_type']}`",
        f"- 有效问题总数：`{len(items)}`",
        f"- A：`{distribution.get('A', 0)}`",
        f"- B：`{distribution.get('B', 0)}`",
        f"- C：`{distribution.get('C', 0)}`",
        f"- D：`{distribution.get('D', 0)}`",
        "- B/C 分类保持由确定性 QA 结果决定，LLM 不允许把 B/C 包装成 A。",
        "- 本轮回归使用真实导入的 BOM 结构化数据，不使用 mock 或样例答案 hardcode。",
    ]
    write_markdown(TMP_DIR.parents[1] / "docs" / "PLAN_BOM_CURRENT_STATUS.md", "PLAN_BOM_CURRENT_STATUS", status_lines)
    business_rows = ["| 序号 | 问题 | 分类 | 需确认原因 |", "| --- | --- | --- | --- |"]
    unsupported_rows = ["| 序号 | 问题 | 分类 | 当前无法支持原因 |", "| --- | --- | --- | --- |"]
    for item in items:
        if item["classification"] == "B":
            business_rows.append(f"| {item['id']} | {item['question']} | B | {item['reason']} |")
        if item["classification"] == "C":
            unsupported_rows.append(f"| {item['id']} | {item['question']} | C | {item['reason']} |")
    write_markdown(
        TMP_DIR.parents[1] / "docs" / "PLAN_BOM_BUSINESS_CONFIRMATION_PACKAGE.md",
        "PLAN_BOM_BUSINESS_CONFIRMATION_PACKAGE",
        [f"- B 类问题数量：`{distribution.get('B', 0)}`", "", *business_rows],
    )
    write_markdown(
        TMP_DIR.parents[1] / "docs" / "PLAN_BOM_UNSUPPORTED_SCOPE.md",
        "PLAN_BOM_UNSUPPORTED_SCOPE",
        [f"- C 类问题数量：`{distribution.get('C', 0)}`", "", *unsupported_rows],
    )


if __name__ == "__main__":
    main()

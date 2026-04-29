from __future__ import annotations

import json
import argparse

from plan_bom_runtime import TMP_DIR, build_runtime_session, make_qa_service, read_question_file


def parse_args() -> argparse.Namespace:
    """解析表达层回归参数。

    返回：
        argparse.Namespace，包含问题文件路径。
    """

    parser = argparse.ArgumentParser(description="计划 BOM 答案表达层确定性回归")
    parser.add_argument("--question-file", default=None, help="BOM 问题文件路径，支持 .xlsx/.xls/.docx")
    return parser.parse_args()


def main() -> None:
    """执行 BOM 答案表达层回归。

    返回：
        无返回值。脚本输出表达层回归 JSON。
    """

    args = parse_args()
    session = build_runtime_session(reset=False)
    service = make_qa_service(session)
    questions, question_meta = read_question_file(args.question_file)
    items = []
    for question in questions:
        response = service.ask(question["问题文本"], use_llm=False)
        presentation = response.presentation
        items.append(
            {
                "id": question["序号"],
                "question": question["问题文本"],
                "passed": bool(presentation and presentation.display_type),
                "classification": response.classification,
                "display_type": presentation.display_type if presentation else None,
                "source": presentation.debug.get("presentation_source") if presentation else None,
                "fallback_reason": presentation.debug.get("fallback_reason") if presentation else None,
            }
        )
    report = {
        "total": len(items),
        "question_source": question_meta,
        "passed": sum(1 for item in items if item["passed"]),
        "failed": sum(1 for item in items if not item["passed"]),
        "items": items,
    }
    (TMP_DIR / "plan_bom_answer_presentation_regression_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

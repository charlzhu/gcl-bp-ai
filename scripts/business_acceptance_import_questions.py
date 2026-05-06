#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import zipfile
from pathlib import Path

from business_acceptance_importer import DEFAULT_OUTPUT_DIR, import_business_questions


def write_self_test_docx(path: Path) -> None:
    """写入最小自测 docx。

    参数：
        path：自测 docx 输出路径。
    返回值：无。

    业务逻辑：
        `business-import` 测试模式不能依赖用户本地业务文件，所以生成只含
        `word/document.xml` 的最小 docx，用来验证导入链路和产物结构。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    paragraphs = [
        "1. 2025年各承运商运量分别是多少？ 标准答案：按物流标准答案计算器结果填写",
        "2. A123订单用了哪些BOM物料？",
        "3. 明天物流费用会不会上涨？",
        "4. 这个问题怎么样？",
    ]
    body = "".join(
        "<w:p><w:r><w:t>{}</w:t></w:r></w:p>".format(html.escape(paragraph)) for paragraph in paragraphs
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body>"
        "</w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    参数：无。
    返回值：argparse 参数解析器。
    """

    parser = argparse.ArgumentParser(description="导入 Word/docx 业务问题集并生成 business_acceptance 产物")
    parser.add_argument("--question-file", type=Path, help="业务问题 docx 文件路径")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="产物输出目录")
    parser.add_argument("--self-test", action="store_true", help="生成最小自测 docx 并执行导入")
    return parser


def main() -> int:
    """命令行入口。

    参数：通过 argparse 读取。
    返回值：0 表示导入成功；参数缺失时 argparse 自动返回非 0。
    """

    args = build_parser().parse_args()
    question_file = args.question_file
    if args.self_test:
        question_file = args.output_dir / "_self_test" / "business_acceptance_sample.docx"
        write_self_test_docx(question_file)
    if question_file is None:
        raise SystemExit("必须提供 --question-file，或使用 --self-test 运行内置自测。")

    outputs = import_business_questions(question_file=question_file, output_dir=args.output_dir)
    print("business_acceptance import finished")
    for name, path in outputs.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

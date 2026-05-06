from __future__ import annotations

import html
import json
import sys
import unittest
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from business_acceptance_importer import import_business_questions, load_docx_questions


def write_minimal_docx(path: Path, paragraphs: list[str]) -> None:
    """写入测试用最小 docx。

    参数：
        path：目标文件路径。
        paragraphs：需要写入 Word 段落的文本列表。
    返回值：无。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
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


class BusinessAcceptanceImporterTest(unittest.TestCase):
    """business_acceptance 问题导入器回归测试。"""

    def test_import_business_questions_outputs_raw_normalized_and_report(self) -> None:
        """验证 docx 导入、业务域分类、oracle 状态和报告产物。

        参数：无。
        返回值：无。
        """

        work_dir = PROJECT_ROOT / "tmp" / "business_acceptance_test"
        question_file = work_dir / "questions.docx"
        output_dir = work_dir / "outputs"
        write_minimal_docx(
            question_file,
            [
                "1. 2025年各承运商运量分别是多少？ 标准答案：按物流中间库计算",
                "2. A123订单用了哪些BOM物料？",
                "3. 明天物流费用会不会上涨？",
                "4. 这个问题怎么样？",
            ],
        )

        outputs = import_business_questions(question_file, output_dir)
        raw = json.loads(outputs["raw"].read_text(encoding="utf-8"))
        normalized = json.loads(outputs["normalized"].read_text(encoding="utf-8"))
        report_text = outputs["report"].read_text(encoding="utf-8")

        self.assertEqual(raw["total_questions"], 4)
        self.assertEqual(normalized["total_cases"], 4)
        self.assertEqual(normalized["domain_distribution"]["logistics"], 2)
        self.assertEqual(normalized["domain_distribution"]["bom"], 1)
        self.assertEqual(normalized["domain_distribution"]["unknown"], 1)
        self.assertEqual(normalized["items"][0]["oracle_status"], "READY")
        self.assertEqual(normalized["items"][1]["oracle_status"], "NEED_ORACLE")
        self.assertEqual(normalized["items"][2]["oracle_status"], "UNSUPPORTED")
        self.assertEqual(normalized["items"][3]["oracle_status"], "NEED_DATA")
        self.assertIn("CASE_CLASSIFICATION_REPORT", report_text)

    def test_following_paragraph_oracle_is_attached_to_previous_question(self) -> None:
        """验证下一段标准答案可以归属到前一个编号问题。

        参数：无。
        返回值：无。
        """

        work_dir = PROJECT_ROOT / "tmp" / "business_acceptance_test"
        question_file = work_dir / "following_oracle.docx"
        write_minimal_docx(
            question_file,
            [
                "1、2026年系统物流总运量是多少？",
                "标准答案：按系统正式数据计算",
            ],
        )

        items = load_docx_questions(question_file)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["expected_answer"], "按系统正式数据计算")
        self.assertEqual(items[0]["oracle_source"], "following_paragraph")


if __name__ == "__main__":
    unittest.main()

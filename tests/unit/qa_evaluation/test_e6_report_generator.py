"""NQE-E6 评测报告生成器 focused tests（RED 阶段）。

业务逻辑：
    验证 ReportGenerator 能将 EvaluationReport 转换为 HTML/Markdown 格式，
    包含摘要统计、逐条结果详情、通过率、一致性分级分布等信息。
"""

from __future__ import annotations

import pytest
from backend.app.domains.qa_evaluation.schema import (
    EvaluationCase,
    EvaluationReport,
    EvaluationResult,
    EvaluationSuite,
)


# ---------------------------------------------------------------------------
# 辅助函数：构造测试用 EvaluationReport
# ---------------------------------------------------------------------------


def _make_result(
    case_id: str = "c001",
    matched_status: bool = True,
    key_numbers_match: bool | None = None,
    leak_found: bool = False,
    actual_status: str = "success",
    actual_answer_summary: str | None = "2024年合肥基地总发运量1,234车次。",
    actual_row_count: int | None = 1,
    mismatch_detail: str | None = None,
    consistency_grade: str = "pass",
    text_similarity: float | None = None,
) -> EvaluationResult:
    """构造一条评测结果。"""
    return EvaluationResult(
        case_id=case_id,
        matched_status=matched_status,
        key_numbers_match=key_numbers_match,
        leak_found=leak_found,
        actual_status=actual_status,
        actual_answer_summary=actual_answer_summary,
        actual_row_count=actual_row_count,
        mismatch_detail=mismatch_detail,
        consistency_grade=consistency_grade,
        text_similarity=text_similarity,
    )


def _make_report(
    suite_name: str = "物流核心问法评测集",
    domain: str = "logistics",
    total_cases: int = 3,
    passed_cases: int = 3,
    failed_cases: int = 0,
    results: list[EvaluationResult] | None = None,
    notes: str | None = None,
) -> EvaluationReport:
    """构造一个评测报告。"""
    if results is None:
        results = [
            _make_result(f"c{i:03d}") for i in range(passed_cases)
        ] + [
            _make_result(
                f"c{passed_cases + fail_i:03d}",
                matched_status=False,
                actual_status="clarification",
                mismatch_detail="状态不匹配",
                consistency_grade="fail",
            ) for fail_i in range(failed_cases)
        ]
    return EvaluationReport(
        suite_name=suite_name,
        domain=domain,
        total_cases=total_cases,
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        results=results,
        notes=notes,
    )


# ===================================================================
# RED 测试：报告生成器基本功能
# ===================================================================


class TestReportGeneratorBasic:
    """报告生成器基础功能 test。"""

    def test_generate_html_returns_string(self):
        """RED: generate_html() 应返回非空 HTML 字符串。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        report = _make_report(passed_cases=3, failed_cases=0, total_cases=3)
        generator = ReportGenerator()
        html = generator.generate_html(report)

        assert isinstance(html, str)
        assert len(html) > 0
        # HTML 基本结构检查
        assert "<html" in html.lower()
        assert "</html>" in html.lower()

    def test_generate_markdown_returns_string(self):
        """RED: generate_markdown() 应返回非空 Markdown 字符串。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        report = _make_report(passed_cases=3, failed_cases=0, total_cases=3)
        generator = ReportGenerator()
        md = generator.generate_markdown(report)

        assert isinstance(md, str)
        assert len(md) > 0
        # Markdown 基本结构检查
        assert "#" in md  # 至少有一个标题

    def test_html_contains_suite_name(self):
        """RED: HTML 报告应包含套件名称。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        report = _make_report(suite_name="物流核心问法评测集")
        generator = ReportGenerator()
        html = generator.generate_html(report)

        assert "物流核心问法评测集" in html

    def test_markdown_contains_suite_name(self):
        """RED: Markdown 报告应包含套件名称。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        report = _make_report(suite_name="物流核心问法评测集")
        generator = ReportGenerator()
        md = generator.generate_markdown(report)

        assert "物流核心问法评测集" in md


# ===================================================================
# RED 测试：通过率统计
# ===================================================================


class TestReportGeneratorStats:
    """报告生成器统计信息 test。"""

    def test_html_contains_pass_rate(self):
        """RED: HTML 报告应包含通过率信息。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        report = _make_report(passed_cases=7, failed_cases=3, total_cases=10)
        generator = ReportGenerator()
        html = generator.generate_html(report)

        assert "70" in html  # 70% 通过率
        assert "7" in html   # 通过数
        assert "3" in html   # 失败数
        assert "10" in html  # 总用例数

    def test_markdown_contains_pass_rate(self):
        """RED: Markdown 报告应包含通过率信息。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        report = _make_report(passed_cases=7, failed_cases=3, total_cases=10)
        generator = ReportGenerator()
        md = generator.generate_markdown(report)

        assert "70" in md
        assert "7" in md
        assert "3" in md
        assert "10" in md

    def test_html_100_percent_pass(self):
        """RED: 全部通过的 HTML 报告显示 100%。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        report = _make_report(passed_cases=10, failed_cases=0, total_cases=10)
        generator = ReportGenerator()
        html = generator.generate_html(report)

        assert "100" in html

    def test_html_zero_cases(self):
        """RED: 空套件的 HTML 报告不应崩溃。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        report = _make_report(passed_cases=0, failed_cases=0, total_cases=0, results=[])
        generator = ReportGenerator()
        html = generator.generate_html(report)

        assert isinstance(html, str)
        assert len(html) > 0


# ===================================================================
# RED 测试：一致性分级展示
# ===================================================================


class TestReportGeneratorConsistency:
    """一致性分级展示 test。"""

    def test_html_shows_consistency_grades(self):
        """RED: HTML 报告应展示 fail/pass/warning 分级统计。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        results = [
            _make_result("c001", consistency_grade="pass"),
            _make_result("c002", consistency_grade="fail", leak_found=True,
                         matched_status=False),
            _make_result("c003", consistency_grade="warning",
                         text_similarity=0.3),
        ]
        report = _make_report(
            total_cases=3, passed_cases=2, failed_cases=1, results=results,
        )
        generator = ReportGenerator()
        html = generator.generate_html(report)

        # 应包含分级数量或标签
        assert "fail" in html.lower() or "失败" in html
        assert "warning" in html.lower() or "警告" in html
        assert "pass" in html.lower() or "通过" in html

    def test_html_flags_leak_cases(self):
        """RED: 有技术泄露的 case 应在 HTML 中标记。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        results = [
            _make_result("c001", consistency_grade="pass"),
            _make_result("c002", consistency_grade="fail", leak_found=True,
                         matched_status=False,
                         mismatch_detail="检测到技术泄露（SQL/表名/字段名等）"),
        ]
        report = _make_report(
            total_cases=2, passed_cases=1, failed_cases=1, results=results,
        )
        generator = ReportGenerator()
        html = generator.generate_html(report)

        assert "泄露" in html


# ===================================================================
# RED 测试：逐条结果详情
# ===================================================================


class TestReportGeneratorDetails:
    """逐条结果详情 test。"""

    def test_html_contains_case_ids(self):
        """RED: HTML 报告应包含每条 case 的 case_id。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        results = [
            _make_result("case-abc-001"),
            _make_result("case-abc-002"),
        ]
        report = _make_report(
            total_cases=2, passed_cases=2, failed_cases=0, results=results,
        )
        generator = ReportGenerator()
        html = generator.generate_html(report)

        assert "case-abc-001" in html
        assert "case-abc-002" in html

    def test_html_contains_mismatch_details(self):
        """RED: 不匹配的 case 应在 HTML 中显示差异详情。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        results = [
            _make_result(
                "c001", matched_status=False, mismatch_detail="状态不匹配：预期 success，实际 error",
                consistency_grade="fail",
            ),
        ]
        report = _make_report(
            total_cases=1, passed_cases=0, failed_cases=1, results=results,
        )
        generator = ReportGenerator()
        html = generator.generate_html(report)

        assert "状态不匹配" in html

    def test_html_contains_actual_answer(self):
        """RED: HTML 报告应包含实际回答摘要。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        results = [
            _make_result(
                "c001", actual_answer_summary="2024年合肥基地总发运量1,234车次。",
            ),
        ]
        report = _make_report(
            total_cases=1, passed_cases=1, failed_cases=0, results=results,
        )
        generator = ReportGenerator()
        html = generator.generate_html(report)

        assert "2024年合肥基地总发运量" in html


# ===================================================================
# RED 测试：文件输出
# ===================================================================


class TestReportGeneratorFileOutput:
    """报告生成器文件输出 test。"""

    def test_generate_html_file(self, tmp_path):
        """RED: generate_html_file() 应将 HTML 写入指定路径。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        report = _make_report(passed_cases=1, failed_cases=0, total_cases=1)
        generator = ReportGenerator()
        output_path = tmp_path / "report.html"
        result_path = generator.generate_html_file(report, str(output_path))

        assert result_path == str(output_path)
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "<html" in content.lower()

    def test_generate_markdown_file(self, tmp_path):
        """RED: generate_markdown_file() 应将 Markdown 写入指定路径。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        report = _make_report(passed_cases=1, failed_cases=0, total_cases=1)
        generator = ReportGenerator()
        output_path = tmp_path / "report.md"
        result_path = generator.generate_markdown_file(report, str(output_path))

        assert result_path == str(output_path)
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "# " in content

    def test_generate_html_file_creates_parent_dirs(self, tmp_path):
        """RED: generate_html_file() 应自动创建父目录。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        report = _make_report(passed_cases=1, failed_cases=0, total_cases=1)
        generator = ReportGenerator()
        output_path = tmp_path / "deeply" / "nested" / "report.html"
        result_path = generator.generate_html_file(report, str(output_path))

        assert output_path.exists()


# ===================================================================
# RED 测试：多套件合并报告
# ===================================================================


class TestReportGeneratorMultiSuite:
    """多套件合并报告 test。"""

    def test_generate_combined_html(self):
        """RED: generate_combined_html() 应接受多个 EvaluationReport 并生成合并 HTML。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        report1 = _make_report(
            suite_name="物流评测集", domain="logistics",
            total_cases=2, passed_cases=2, failed_cases=0,
            results=[_make_result("c001"), _make_result("c002")],
        )
        report2 = _make_report(
            suite_name="BOM评测集", domain="plan_bom",
            total_cases=1, passed_cases=1, failed_cases=0,
            results=[_make_result("c003")],
        )
        generator = ReportGenerator()
        html = generator.generate_combined_html([report1, report2])

        assert "物流评测集" in html
        assert "BOM评测集" in html
        assert "c001" in html
        assert "c003" in html

    def test_generate_combined_markdown(self):
        """RED: generate_combined_markdown() 应接受多个 EvaluationReport 并生成合并 Markdown。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        report1 = _make_report(
            suite_name="物流评测集", domain="logistics",
            total_cases=2, passed_cases=2, failed_cases=0,
            results=[_make_result("c001"), _make_result("c002")],
        )
        report2 = _make_report(
            suite_name="BOM评测集", domain="plan_bom",
            total_cases=1, passed_cases=1, failed_cases=0,
            results=[_make_result("c003")],
        )
        generator = ReportGenerator()
        md = generator.generate_combined_markdown([report1, report2])

        assert "物流评测集" in md
        assert "BOM评测集" in md


# ===================================================================
# RED 测试：时间戳和元信息
# ===================================================================


class TestReportGeneratorMetadata:
    """报告元信息 test。"""

    def test_html_contains_domain(self):
        """RED: HTML 报告应包含业务域信息。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        report = _make_report(domain="plan_bom")
        generator = ReportGenerator()
        html = generator.generate_html(report)

        assert "plan_bom" in html

    def test_html_contains_notes_if_present(self):
        """RED: HTML 报告应包含备注信息（如有）。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        report = _make_report(notes="本轮评测基于 staging 环境数据，已通过回归验证。")
        generator = ReportGenerator()
        html = generator.generate_html(report)

        assert "staging" in html

    def test_html_omits_notes_if_none(self):
        """RED: HTML 报告无备注时不显示空备注段。"""
        from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

        report = _make_report(notes=None)
        generator = ReportGenerator()
        html = generator.generate_html(report)

        # 不验证具体内容，只确保不崩溃
        assert isinstance(html, str)

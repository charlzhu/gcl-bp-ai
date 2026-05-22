"""NQE-E6 conftest pytest 插件 focused tests。

业务逻辑：
    验证 --eval-report CLI 选项能正确注册、报告收集器能接收评测报告、
    会话结束时能生成 HTML/Markdown 报告文件。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.domains.qa_evaluation.schema import (
    EvaluationReport,
    EvaluationResult,
)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _make_result(case_id: str = "c001") -> EvaluationResult:
    """构造一条评测结果。"""
    return EvaluationResult(
        case_id=case_id,
        matched_status=True,
        actual_status="success",
        actual_answer_summary="测试回答",
    )


def _make_report() -> EvaluationReport:
    """构造一个评测报告。"""
    return EvaluationReport(
        suite_name="测试评测集",
        domain="logistics",
        total_cases=1,
        passed_cases=1,
        failed_cases=0,
        results=[_make_result("c001")],
    )


# ===================================================================
# 测试：收集器 fixture 可注入
# ===================================================================


class TestConftestCollectorFixture:
    """收集器 fixture test。"""

    def test_collector_fixture_available(self):
        """验证 eval_report_collector fixture 可导入。"""
        from tests.evaluation.conftest import _EvalReportCollector

        collector = _EvalReportCollector()
        assert collector.reports == []

    def test_collector_add_report(self):
        """验证 collector.add_report() 可将报告注册到全局列表。"""
        from tests.evaluation.conftest import (
            _EvalReportCollector,
            _register_report,
            _eval_reports,
        )

        # 清空上次残余
        _eval_reports.clear()

        collector = _EvalReportCollector()
        report = _make_report()
        collector.add_report(report)

        assert len(collector.reports) == 1
        assert len(_eval_reports) == 1
        assert _eval_reports[0] is report


# ===================================================================
# 测试：CLI 选项注册
# ===================================================================


class TestConftestCLIOption:
    """CLI 选项 test。"""

    def test_help_shows_eval_report_option(self):
        """验证 pytest --help 显示 --eval-report 选项。

        注意：需在 tests/evaluation/ 目录下运行，因为 conftest 的
        pytest_addoption 仅在该目录的 pytest 配置中注册。
        """
        import subprocess
        import sys

        eval_dir = str(Path(__file__).resolve().parent.parent.parent / "evaluation")
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--help"],
            capture_output=True,
            text=True,
            cwd=eval_dir,
            timeout=15,
        )
        assert "--eval-report" in result.stdout


# ===================================================================
# 测试：报告生成函数
# ===================================================================


class TestConftestGenerateReports:
    """报告生成 test。"""

    def test_generate_reports_single(self, tmp_path):
        """验证 _generate_reports 单个报告生成。"""
        from tests.evaluation.conftest import _generate_reports

        report = _make_report()
        report_dir = str(tmp_path / "eval_reports")
        _generate_reports([report], report_dir)

        # 验证生成的文件存在
        files = list(Path(report_dir).glob("*.html"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "测试评测集" in content

        md_files = list(Path(report_dir).glob("*.md"))
        assert len(md_files) == 1
        md_content = md_files[0].read_text(encoding="utf-8")
        assert "测试评测集" in md_content

    def test_generate_reports_multiple(self, tmp_path):
        """验证 _generate_reports 多报告合并生成。"""
        from tests.evaluation.conftest import _generate_reports

        report1 = _make_report()
        report2 = _make_report()
        report2.suite_name = "第二个评测集"

        report_dir = str(tmp_path / "eval_reports")
        _generate_reports([report1, report2], report_dir)

        files = list(Path(report_dir).glob("*combined*.html"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "测试评测集" in content
        assert "第二个评测集" in content

    def test_generate_reports_empty(self, tmp_path):
        """验证 _generate_reports 空列表不创建文件。"""
        from tests.evaluation.conftest import _generate_reports

        report_dir = str(tmp_path / "eval_reports")
        _generate_reports([], report_dir)

        # 空列表不应创建任何文件
        files = list(Path(report_dir).glob("*"))
        assert len(files) == 0

    def test_generate_reports_output_dir_created(self, tmp_path):
        """验证 _generate_reports 自动创建输出目录。"""
        from tests.evaluation.conftest import _generate_reports

        report = _make_report()
        report_dir = str(tmp_path / "deeply" / "nested" / "eval_reports")
        _generate_reports([report], report_dir)

        assert Path(report_dir).exists()
        files = list(Path(report_dir).glob("*.html"))
        assert len(files) == 1


# ===================================================================
# 测试：is_eval_report 判断
# ===================================================================


class TestIsEvalReport:
    """is_eval_report 辅助函数 test。"""

    def test_recognizes_eval_report(self):
        """验证 _is_eval_report 能识别 EvaluationReport。"""
        from tests.evaluation.conftest import _is_eval_report

        report = _make_report()
        assert _is_eval_report(report) is True

    def test_rejects_plain_dict(self):
        """验证 _is_eval_report 拒绝普通 dict。"""
        from tests.evaluation.conftest import _is_eval_report

        assert _is_eval_report({"suite_name": "test"}) is False

    def test_rejects_none(self):
        """验证 _is_eval_report 拒绝 None。"""
        from tests.evaluation.conftest import _is_eval_report

        assert _is_eval_report(None) is False

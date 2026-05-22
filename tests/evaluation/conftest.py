"""pytest conftest 插件：支持 --eval-report CLI 参数。

业务逻辑：
    新增 --eval-report CLI 参数，允许通过命令行指定评测报告输出目录。
    评测报告生成器在 pytest 会话结束时自动收集所有评测结果并生成
    HTML/Markdown 格式的评测报告。

使用示例：
    # 运行全部评测集并生成报告
    python -m pytest tests/evaluation/ --eval-report

    # 指定报告输出目录
    python -m pytest tests/evaluation/ --eval-report=ai/outbox/eval_reports/

    # 结合其他 pytest 参数
    python -m pytest tests/evaluation/ --eval-report -v --tb=short

设计原则：
    1. 不改变现有测试执行流程。
    2. 报告生成在所有测试完成后异步执行。
    3. 报告输出目录默认为 ai/outbox/eval_reports/。
    4. 若未指定 --eval-report，则不生成报告（向后兼容）。
    5. 使用模块级全局列表作为收集器（pytest session fixture 在 sessionfinish
       中不易访问）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# 模块级全局收集器（绕过 session fixture 访问限制）
# ---------------------------------------------------------------------------

# 评测报告收集列表，评测测试通过 _register_report() 注册
_eval_reports: list[Any] = []


def _register_report(report: Any) -> None:
    """注册一条评测报告。

    参数：
        report: EvaluationReport 实例。
    """
    _eval_reports.append(report)


# ---------------------------------------------------------------------------
# 命令行选项：--eval-report
# ---------------------------------------------------------------------------


def pytest_addoption(parser: Any) -> None:
    """添加 --eval-report 命令行选项。

    参数：
        parser: pytest 命令行参数解析器。
    """
    parser.addoption(
        "--eval-report",
        action="store",
        default=None,
        const="ai/outbox/eval_reports/",  # 无参数时的默认值
        nargs="?",
        help="生成评测 HTML/Markdown 报告到指定目录（默认: ai/outbox/eval_reports/）",
    )


# ---------------------------------------------------------------------------
# Session fixture：评测结果收集器（提供显式 fixture 给测试使用）
# ---------------------------------------------------------------------------


class _EvalReportCollector:
    """评测结果收集器。

    在测试执行期间收集所有 EvaluationReport，供会话结束时生成报告。
    同时将报告注册到模块级全局列表中以便 sessionfinish 访问。
    """

    def __init__(self) -> None:
        self.reports: list[Any] = []  # list[EvaluationReport]

    def add_report(self, report: Any) -> None:
        """添加一条评测报告。"""
        self.reports.append(report)
        _register_report(report)  # 同步注册到模块级全局


@pytest.fixture(scope="session")
def eval_report_collector() -> _EvalReportCollector:
    """Session 级别的评测结果收集器 fixture。

    返回：
        _EvalReportCollector 实例，评测测试可通过它注册报告。
    """
    return _EvalReportCollector()


# ---------------------------------------------------------------------------
# 自动收集 hook：从测试结果中提取 EvaluationReport
# ---------------------------------------------------------------------------


def _is_eval_report(value: Any) -> bool:
    """判断一个值是否为 EvaluationReport 类型。

    参数：
        value: 任意 Python 对象。
    返回：
        True 如果该对象有 suite_name、total_cases、passed_cases、pass_rate 等评测报告特征。
    """
    return all(
        hasattr(value, attr)
        for attr in ("suite_name", "total_cases", "passed_cases", "pass_rate")
    )


# ---------------------------------------------------------------------------
# Session 结束：生成报告
# ---------------------------------------------------------------------------


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    """pytest 会话结束时生成评测报告。

    参数：
        session: pytest 会话对象。
        exitstatus: 测试退出状态（0=成功）。

    业务逻辑：
        1. 检查是否指定了 --eval-report 选项。
        2. 从模块级全局 _eval_reports 收集所有评测报告。
        3. 生成 HTML 和 Markdown 报告。
        4. 报告生成失败不中断测试流程。
    """
    report_dir: str | None = session.config.getoption("--eval-report", default=None)
    if report_dir is None:
        return  # 未指定 --eval-report，不生成报告

    if not _eval_reports:
        return  # 无评测报告可生成

    try:
        _generate_reports(list(_eval_reports), report_dir)
    except Exception:
        # 报告生成失败不中断测试流程
        import sys
        print(
            "\n[WARNING] 评测报告生成失败，测试结果仍然有效。",
            file=sys.stderr,
        )


def _generate_reports(reports: list[Any], report_dir: str) -> None:
    """生成 HTML 和 Markdown 评测报告。

    参数：
        reports: EvaluationReport 列表。
        report_dir: 报告输出目录。
    """
    from backend.app.domains.qa_evaluation.report_generator import ReportGenerator

    generator = ReportGenerator()
    base = Path(report_dir)
    base.mkdir(parents=True, exist_ok=True)

    # 生成报告文件名（带时间戳，便于追溯）
    from datetime import datetime

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    html_path: Path | None = None
    md_path: Path | None = None

    if len(reports) == 1:
        # 单套件报告
        html_path = base / f"eval_report_{ts}.html"
        md_path = base / f"eval_report_{ts}.md"
        generator.generate_html_file(reports[0], str(html_path))
        generator.generate_markdown_file(reports[0], str(md_path))
    elif len(reports) > 1:
        # 多套件合并报告
        html_content = generator.generate_combined_html(reports)
        md_content = generator.generate_combined_markdown(reports)
        html_path = base / f"eval_report_combined_{ts}.html"
        md_path = base / f"eval_report_combined_{ts}.md"
        html_path.write_text(html_content, encoding="utf-8")
        md_path.write_text(md_content, encoding="utf-8")
    else:
        # 空报告列表，不生成文件
        return

    import sys
    if html_path:
        print(
            f"\n[评测报告] 已生成 HTML 报告：{html_path}",
            file=sys.stderr,
        )
    if md_path:
        print(
            f"[评测报告] 已生成 Markdown 报告：{md_path}",
            file=sys.stderr,
        )

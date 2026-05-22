"""评测报告生成器（ReportGenerator）。

业务逻辑：
    将 EvaluationReport 转换为 HTML / Markdown 格式的评测报告，
    包含摘要统计、逐条结果详情、通过率、一致性分级分布等信息。
    支持单套件报告和多套件合并报告。

设计原则：
    1. 报告内容完全由后端确定性代码生成，不依赖 LLM。
    2. HTML 使用内联样式，无需外部 CSS 文件。
    3. Markdown 使用标准 GFM 语法，兼容 GitHub/GitLab 渲染。
    4. 技术泄露的 case 在报告中以红色/警告标记突出显示。
"""

from __future__ import annotations

from pathlib import Path

from backend.app.domains.qa_evaluation.schema import EvaluationReport


class ReportGenerator:
    """评测报告生成器。

    将 EvaluationReport 转换为 HTML 或 Markdown 格式，支持命令行调用。
    """

    # -------------------------------------------------------------------
    # 公共方法：HTML 报告
    # -------------------------------------------------------------------

    def generate_html(self, report: EvaluationReport) -> str:
        """生成单套件的 HTML 报告。

        参数：
            report: 评测报告。
        返回：
            HTML 字符串。
        """
        return self._render_html_single(report)

    def generate_html_file(
        self, report: EvaluationReport, output_path: str,
    ) -> str:
        """生成 HTML 报告并写入文件。

        参数：
            report: 评测报告。
            output_path: 输出文件路径（自动创建父目录）。
        返回：
            实际写入的路径。
        """
        html = self.generate_html(report)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        return str(path)

    def generate_combined_html(self, reports: list[EvaluationReport]) -> str:
        """生成多个套件的合并 HTML 报告。

        参数：
            reports: 多个 EvaluationReport 列表。
        返回：
            合并的 HTML 字符串。
        """
        return self._render_html_combined(reports)

    # -------------------------------------------------------------------
    # 公共方法：Markdown 报告
    # -------------------------------------------------------------------

    def generate_markdown(self, report: EvaluationReport) -> str:
        """生成单套件的 Markdown 报告。

        参数：
            report: 评测报告。
        返回：
            Markdown 字符串。
        """
        return self._render_md_single(report)

    def generate_markdown_file(
        self, report: EvaluationReport, output_path: str,
    ) -> str:
        """生成 Markdown 报告并写入文件。

        参数：
            report: 评测报告。
            output_path: 输出文件路径（自动创建父目录）。
        返回：
            实际写入的路径。
        """
        md = self.generate_markdown(report)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(md, encoding="utf-8")
        return str(path)

    def generate_combined_markdown(self, reports: list[EvaluationReport]) -> str:
        """生成多个套件的合并 Markdown 报告。

        参数：
            reports: 多个 EvaluationReport 列表。
        返回：
            合并的 Markdown 字符串。
        """
        return self._render_md_combined(reports)

    # -------------------------------------------------------------------
    # 内部方法：HTML 渲染
    # -------------------------------------------------------------------

    @staticmethod
    def _render_html_single(report: EvaluationReport) -> str:
        """渲染单套件 HTML。"""
        parts: list[str] = []

        # 头部
        parts.append("<!DOCTYPE html>")
        parts.append('<html lang="zh-CN">')
        parts.append("<head>")
        parts.append('<meta charset="UTF-8">')
        parts.append(
            f"<title>评测报告 - {_escape_html(report.suite_name)}</title>"
        )
        parts.append("<style>")
        parts.append(_CSS_STYLES)
        parts.append("</style>")
        parts.append("</head>")
        parts.append("<body>")

        # 标题
        parts.append(f"<h1>评测报告：{_escape_html(report.suite_name)}</h1>")

        # 元信息
        if report.domain:
            parts.append(
                f"<p class='meta'>业务域：{_escape_html(report.domain)}</p>"
            )

        # 摘要统计
        parts.append("<h2>摘要统计</h2>")
        parts.append("<table class='summary'>")
        parts.append("<tr><th>指标</th><th>数值</th></tr>")
        parts.append(
            f"<tr><td>总用例数</td><td>{report.total_cases}</td></tr>"
        )
        parts.append(
            f"<tr><td>通过</td><td>{report.passed_cases}</td></tr>"
        )
        parts.append(
            f"<tr><td>失败</td><td>{report.failed_cases}</td></tr>"
        )
        parts.append(
            f"<tr><td>通过率</td><td>{report.pass_rate:.1%}</td></tr>"
        )
        parts.append("</table>")

        # 一致性分级统计
        parts.append("<h2>一致性分级</h2>")
        grade_counts = ReportGenerator._count_grades(report)
        parts.append("<table class='summary'>")
        parts.append("<tr><th>分级</th><th>数量</th></tr>")
        for grade_label, grade_key, css_class in [
            ("通过 (pass)", "pass", "grade-pass"),
            ("警告 (warning)", "warning", "grade-warning"),
            ("失败 (fail)", "fail", "grade-fail"),
        ]:
            count = grade_counts.get(grade_key, 0)
            parts.append(
                f"<tr class='{css_class}'><td>{grade_label}</td>"
                f"<td>{count}</td></tr>"
            )
        parts.append("</table>")

        # 逐条结果
        parts.append("<h2>逐条评测结果</h2>")
        parts.append("<table class='results'>")
        parts.append(
            "<tr><th>Case ID</th><th>状态</th><th>一致性</th>"
            "<th>行数</th><th>回答摘要</th><th>差异详情</th></tr>"
        )
        for result in report.results:
            grade = result.consistency_grade or "-"
            grade_class = f"grade-{grade}" if grade in ("pass", "fail", "warning") else ""

            row_count_str = (
                str(result.actual_row_count)
                if result.actual_row_count is not None
                else "-"
            )
            answer_str = _escape_html(
                result.actual_answer_summary or ""
            )[:100]
            detail_str = _escape_html(
                result.mismatch_detail or ""
            )[:200]

            leak_flag = ""
            if result.leak_found:
                leak_flag = " ⚠️泄露"

            parts.append(
                f"<tr class='{grade_class}'>"
                f"<td>{_escape_html(result.case_id)}</td>"
                f"<td>{_escape_html(result.actual_status or '-')}</td>"
                f"<td>{grade}{leak_flag}</td>"
                f"<td>{row_count_str}</td>"
                f"<td>{answer_str}</td>"
                f"<td>{detail_str}</td>"
                f"</tr>"
            )
        parts.append("</table>")

        # 备注
        if report.notes:
            parts.append("<h2>备注</h2>")
            parts.append(f"<p class='notes'>{_escape_html(report.notes)}</p>")

        parts.append("</body>")
        parts.append("</html>")

        return "\n".join(parts)

    @staticmethod
    def _render_html_combined(reports: list[EvaluationReport]) -> str:
        """渲染多套件合并 HTML。"""
        parts: list[str] = []

        # 头部
        parts.append("<!DOCTYPE html>")
        parts.append('<html lang="zh-CN">')
        parts.append("<head>")
        parts.append('<meta charset="UTF-8">')
        parts.append("<title>评测报告（合并）</title>")
        parts.append("<style>")
        parts.append(_CSS_STYLES)
        parts.append("</style>")
        parts.append("</head>")
        parts.append("<body>")

        parts.append("<h1>评测报告（合并）</h1>")

        # 全局汇总
        total_all = sum(r.total_cases for r in reports)
        passed_all = sum(r.passed_cases for r in reports)
        failed_all = sum(r.failed_cases for r in reports)
        rate_all = passed_all / total_all if total_all > 0 else 1.0

        parts.append("<h2>全局统计</h2>")
        parts.append("<table class='summary'>")
        parts.append("<tr><th>指标</th><th>数值</th></tr>")
        parts.append(f"<tr><td>总用例数</td><td>{total_all}</td></tr>")
        parts.append(f"<tr><td>通过</td><td>{passed_all}</td></tr>")
        parts.append(f"<tr><td>失败</td><td>{failed_all}</td></tr>")
        parts.append(f"<tr><td>通过率</td><td>{rate_all:.1%}</td></tr>")
        parts.append("</table>")

        # 逐套件
        for report in reports:
            parts.append(f"<hr>")
            parts.append(f"<h2>{_escape_html(report.suite_name)}</h2>")
            if report.domain:
                parts.append(
                    f"<p class='meta'>业务域：{_escape_html(report.domain)}</p>"
                )

            parts.append("<table class='summary'>")
            parts.append("<tr><th>指标</th><th>数值</th></tr>")
            parts.append(
                f"<tr><td>总用例数</td><td>{report.total_cases}</td></tr>"
            )
            parts.append(
                f"<tr><td>通过</td><td>{report.passed_cases}</td></tr>"
            )
            parts.append(
                f"<tr><td>失败</td><td>{report.failed_cases}</td></tr>"
            )
            parts.append(
                f"<tr><td>通过率</td><td>{report.pass_rate:.1%}</td></tr>"
            )
            parts.append("</table>")

            # 逐条结果表格
            parts.append("<table class='results'>")
            parts.append(
                "<tr><th>Case ID</th><th>状态</th><th>一致性</th>"
                "<th>行数</th><th>回答摘要</th><th>差异详情</th></tr>"
            )
            for result in report.results:
                grade = result.consistency_grade or "-"
                grade_class = (
                    f"grade-{grade}" if grade in ("pass", "fail", "warning") else ""
                )
                row_count_str = (
                    str(result.actual_row_count)
                    if result.actual_row_count is not None
                    else "-"
                )
                answer_str = _escape_html(
                    result.actual_answer_summary or ""
                )[:100]
                detail_str = _escape_html(
                    result.mismatch_detail or ""
                )[:200]
                leak_flag = " ⚠️泄露" if result.leak_found else ""

                parts.append(
                    f"<tr class='{grade_class}'>"
                    f"<td>{_escape_html(result.case_id)}</td>"
                    f"<td>{_escape_html(result.actual_status or '-')}</td>"
                    f"<td>{grade}{leak_flag}</td>"
                    f"<td>{row_count_str}</td>"
                    f"<td>{answer_str}</td>"
                    f"<td>{detail_str}</td>"
                    f"</tr>"
                )
            parts.append("</table>")

        parts.append("</body>")
        parts.append("</html>")

        return "\n".join(parts)

    # -------------------------------------------------------------------
    # 内部方法：Markdown 渲染
    # -------------------------------------------------------------------

    @staticmethod
    def _render_md_single(report: EvaluationReport) -> str:
        """渲染单套件 Markdown。"""
        lines: list[str] = []

        # 标题
        lines.append(f"# 评测报告：{report.suite_name}")
        lines.append("")

        # 元信息
        if report.domain:
            lines.append(f"**业务域**：{report.domain}")
            lines.append("")

        # 摘要统计
        lines.append("## 摘要统计")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 总用例数 | {report.total_cases} |")
        lines.append(f"| 通过 | {report.passed_cases} |")
        lines.append(f"| 失败 | {report.failed_cases} |")
        lines.append(f"| **通过率** | **{report.pass_rate:.1%}** |")
        lines.append("")

        # 一致性分级
        lines.append("## 一致性分级")
        lines.append("")
        grade_counts = ReportGenerator._count_grades(report)
        lines.append("| 分级 | 数量 |")
        lines.append("|------|------|")
        lines.append(
            f"| ✅ 通过 (pass) | {grade_counts.get('pass', 0)} |"
        )
        lines.append(
            f"| ⚠️ 警告 (warning) | {grade_counts.get('warning', 0)} |"
        )
        lines.append(
            f"| ❌ 失败 (fail) | {grade_counts.get('fail', 0)} |"
        )
        lines.append("")

        # 逐条结果
        lines.append("## 逐条评测结果")
        lines.append("")
        for result in report.results:
            grade_icon = {
                "pass": "✅",
                "warning": "⚠️",
                "fail": "❌",
            }.get(result.consistency_grade or "", "❓")

            leak_mark = " ⚠️**泄露**" if result.leak_found else ""
            lines.append(
                f"- {grade_icon} `{result.case_id}` "
                f"| 状态：{result.actual_status or '-'} "
                f"| 一致性：{result.consistency_grade or '-'}{leak_mark}"
            )
            if result.mismatch_detail:
                lines.append(f"  - 差异：{result.mismatch_detail}")
            if result.actual_answer_summary:
                summary = result.actual_answer_summary[:120]
                lines.append(f"  - 回答：{summary}")
        lines.append("")

        # 备注
        if report.notes:
            lines.append("## 备注")
            lines.append("")
            lines.append(report.notes)
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _render_md_combined(reports: list[EvaluationReport]) -> str:
        """渲染多套件合并 Markdown。"""
        lines: list[str] = []

        lines.append("# 评测报告（合并）")
        lines.append("")

        # 全局汇总
        total_all = sum(r.total_cases for r in reports)
        passed_all = sum(r.passed_cases for r in reports)
        failed_all = sum(r.failed_cases for r in reports)
        rate_all = passed_all / total_all if total_all > 0 else 1.0

        lines.append("## 全局统计")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 总用例数 | {total_all} |")
        lines.append(f"| 通过 | {passed_all} |")
        lines.append(f"| 失败 | {failed_all} |")
        lines.append(f"| **通过率** | **{rate_all:.1%}** |")
        lines.append("")

        # 逐套件
        for report in reports:
            lines.append("---")
            lines.append("")
            lines.append(f"## {report.suite_name}")
            lines.append("")
            if report.domain:
                lines.append(f"**业务域**：{report.domain}")
                lines.append("")

            lines.append("| 指标 | 数值 |")
            lines.append("|------|------|")
            lines.append(f"| 总用例数 | {report.total_cases} |")
            lines.append(f"| 通过 | {report.passed_cases} |")
            lines.append(f"| 失败 | {report.failed_cases} |")
            lines.append(f"| **通过率** | **{report.pass_rate:.1%}** |")
            lines.append("")

            for result in report.results:
                grade_icon = {
                    "pass": "✅",
                    "warning": "⚠️",
                    "fail": "❌",
                }.get(result.consistency_grade or "", "❓")
                leak_mark = " ⚠️**泄露**" if result.leak_found else ""
                lines.append(
                    f"- {grade_icon} `{result.case_id}` "
                    f"| 状态：{result.actual_status or '-'} "
                    f"| 一致性：{result.consistency_grade or '-'}{leak_mark}"
                )
                if result.mismatch_detail:
                    lines.append(f"  - 差异：{result.mismatch_detail}")
            lines.append("")

        return "\n".join(lines)

    # -------------------------------------------------------------------
    # 内部工具：一致性分级统计
    # -------------------------------------------------------------------

    @staticmethod
    def _count_grades(report: EvaluationReport) -> dict[str, int]:
        """统计各一致性分级的数量。

        参数：
            report: 评测报告。
        返回：
            {"pass": N, "fail": N, "warning": N} 字典。
        """
        counts: dict[str, int] = {"pass": 0, "fail": 0, "warning": 0}
        for result in report.results:
            grade = result.consistency_grade
            if grade in counts:
                counts[grade] += 1
        return counts


# -----------------------------------------------------------------------
# HTML 内联样式（中文注释）
# -----------------------------------------------------------------------

_CSS_STYLES = """
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
        'Helvetica Neue', Arial, sans-serif;
    max-width: 1200px;
    margin: 40px auto;
    padding: 0 20px;
    line-height: 1.6;
    color: #333;
    background: #fff;
}
h1 { color: #1a1a2e; border-bottom: 3px solid #0f3460; padding-bottom: 10px; }
h2 { color: #16213e; margin-top: 30px; }
.meta { color: #666; font-size: 14px; }
table {
    border-collapse: collapse;
    width: 100%;
    margin: 10px 0 20px 0;
    font-size: 14px;
}
th, td {
    border: 1px solid #ddd;
    padding: 8px 12px;
    text-align: left;
}
th { background: #f0f0f0; font-weight: 600; }
.summary td:first-child { font-weight: 600; width: 180px; }
.grade-pass { background: #e8f5e9; }
.grade-warning { background: #fff3e0; }
.grade-fail { background: #ffebee; }
.notes { color: #555; background: #f9f9f9; padding: 12px; border-left: 4px solid #999; }
"""


# -----------------------------------------------------------------------
# HTML 转义
# -----------------------------------------------------------------------

def _escape_html(text: str) -> str:
    """转义 HTML 特殊字符。

    参数：
        text: 原始文本。
    返回：
        转义后的安全文本。
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

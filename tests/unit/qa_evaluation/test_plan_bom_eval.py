"""NQE-E3 focused tests：计划 BOM 问法评测集接入 Graph。

业务逻辑：
    验证计划 BOM 评测样例集可加载为 EvaluationSuite，
    EvalGraphRunner 可对 plan_bom 域执行评测，
    样例集覆盖 BOM 各问法类型且无技术泄露。

TDD 流程：RED → GREEN → REFACTOR。
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.app.domains.business_qa_graph.schemas.response import BusinessQaGraphResponse
from backend.app.domains.qa_evaluation.schema import (
    EvaluationCase,
    EvaluationReport,
    EvaluationSuite,
)


# =============================================================================
# RED 测试 1：BOM 评测样例集可加载
# =============================================================================


def test_plan_bom_evaluation_samples_loadable() -> None:
    """计划 BOM 评测样例集可从 tests/evaluation/plan_bom/ 加载为 EvaluationSuite。

    RED：样例文件和加载函数尚未实现。
    """
    from tests.evaluation.plan_bom.samples import load_plan_bom_suite

    suite = load_plan_bom_suite()

    assert isinstance(suite, EvaluationSuite)
    assert suite.domain == "plan_bom"
    assert len(suite.cases) >= 8, (
        f"首批 BOM 评测样例应至少 8 条，实际 {len(suite.cases)} 条"
    )

    # 验证每条 case 的 domain 与 suite 一致
    for case in suite.cases:
        assert case.domain == "plan_bom", (
            f"case {case.case_id} 的 domain 应为 plan_bom，实际为 {case.domain}"
        )
        assert case.question, "每条 case 必须有 question"
        assert case.expected_status, "每条 case 必须有 expected_status"


# =============================================================================
# RED 测试 2：BOM 样例覆盖所有预期状态类型
# =============================================================================


def test_plan_bom_samples_cover_all_expected_statuses() -> None:
    """BOM 评测样例集应覆盖 success/clarification/unsupported/empty_result 四种状态。

    RED：样例集尚未实现或覆盖不全。
    """
    from tests.evaluation.plan_bom.samples import load_plan_bom_suite

    suite = load_plan_bom_suite()

    statuses = {case.expected_status for case in suite.cases}

    # 至少覆盖 success、clarification、unsupported
    assert "success" in statuses, "应包含 success 状态的 case"
    assert "clarification" in statuses, "应包含 clarification 状态的 case"
    assert "unsupported" in statuses, "应包含 unsupported 状态的 case"
    assert "empty_result" in statuses, "应包含 empty_result 状态的 case"

    # 统计分布
    success_count = sum(1 for c in suite.cases if c.expected_status == "success")
    clarification_count = sum(1 for c in suite.cases if c.expected_status == "clarification")
    unsupported_count = sum(1 for c in suite.cases if c.expected_status == "unsupported")
    empty_count = sum(1 for c in suite.cases if c.expected_status == "empty_result")

    assert success_count >= 4, f"success 至少 4 条，实际 {success_count} 条"
    assert clarification_count >= 2, f"clarification 至少 2 条，实际 {clarification_count} 条"
    assert unsupported_count >= 2, f"unsupported 至少 2 条，实际 {unsupported_count} 条"


# =============================================================================
# RED 测试 3：BOM 样例 case_id 唯一性
# =============================================================================


def test_plan_bom_samples_have_unique_case_ids() -> None:
    """BOM 评测样例集中每条 case 应有唯一的 case_id。

    RED：样例集尚未实现。
    """
    from tests.evaluation.plan_bom.samples import load_plan_bom_suite

    suite = load_plan_bom_suite()

    case_ids = [case.case_id for case in suite.cases]
    assert len(case_ids) == len(set(case_ids)), (
        f"case_id 应唯一，发现重复: {[cid for cid in case_ids if case_ids.count(cid) > 1]}"
    )


# =============================================================================
# RED 测试 4：BOM 样例 tags 分类完整
# =============================================================================


def test_plan_bom_samples_tags_present() -> None:
    """BOM 评测样例集中每条 case 应有 tags 标签，且覆盖关键分类。

    RED：样例集尚未实现。
    """
    from tests.evaluation.plan_bom.samples import load_plan_bom_suite

    suite = load_plan_bom_suite()

    all_tags: set[str] = set()
    for case in suite.cases:
        assert case.tags, f"case {case.case_id} 必须有 tags"
        assert isinstance(case.tags, list), f"case {case.case_id} 的 tags 应为 list"
        for tag in case.tags:
            all_tags.add(tag)

    # 验证关键标签存在
    assert "smoke" in all_tags, "应有 smoke 标签"
    assert "clarify" in all_tags, "应有 clarify 标签"
    assert "unsupported" in all_tags, "应有 unsupported 标签"


# =============================================================================
# RED 测试 5：EvalGraphRunner 对 plan_bom 域运行评测
# =============================================================================


def test_eval_runner_runs_plan_bom_suite() -> None:
    """EvalGraphRunner 可对 plan_bom 评测套件执行评测并生成报告。

    RED：plan_bom 域评测尚未验证。
    """
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner
    from tests.evaluation.plan_bom.samples import load_plan_bom_suite

    suite = load_plan_bom_suite()

    # 构造 fake GraphRunner，对每条 plan_bom case 返回对应的模拟响应
    fake_graph_runner = MagicMock()

    def _fake_response_for(case: EvaluationCase) -> BusinessQaGraphResponse:
        """根据 case 的 expected_status 返回对应的模拟响应。"""
        if case.expected_status == "success":
            return BusinessQaGraphResponse(
                status="EXECUTED",
                execution_mode="graph_skeleton_only",
                question=case.question,
                domain="plan_bom",
                execution_status="EXECUTED",
                execution_result={
                    "answer_summary": f"BOM 查询结果: {case.question[:30]}...",
                    "row_count": 1,
                },
            )
        elif case.expected_status == "clarification":
            return BusinessQaGraphResponse(
                status="CLARIFY",
                execution_mode="graph_skeleton_only",
                question=case.question,
                domain="plan_bom",
            )
        elif case.expected_status == "unsupported":
            return BusinessQaGraphResponse(
                status="UNSUPPORTED",
                execution_mode="graph_skeleton_only",
                question=case.question,
                domain="plan_bom",
            )
        elif case.expected_status == "empty_result":
            return BusinessQaGraphResponse(
                status="EXECUTED",
                execution_mode="graph_skeleton_only",
                question=case.question,
                domain="plan_bom",
                execution_status="EXECUTED",
                execution_result={
                    "answer_summary": "未找到匹配的 BOM 记录",
                    "row_count": 0,
                },
            )
        else:
            return BusinessQaGraphResponse(
                status="ERROR",
                execution_mode="graph_skeleton_only",
                question=case.question,
                domain="plan_bom",
            )

    fake_graph_runner.run.side_effect = [
        _fake_response_for(case) for case in suite.cases
    ]

    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    # 验证报告结构
    assert isinstance(report, EvaluationReport)
    assert report.domain == "plan_bom"
    assert report.total_cases == len(suite.cases)
    assert len(report.results) == len(suite.cases)

    # 验证每条 result 关联到对应 case
    for i, case in enumerate(suite.cases):
        assert report.results[i].case_id == case.case_id

    # 验证 fake runner 被调用了对应次数
    assert fake_graph_runner.run.call_count == len(suite.cases)


# =============================================================================
# RED 测试 6：plan_bom 域状态匹配逻辑
# =============================================================================


def test_eval_runner_plan_bom_status_matching_success() -> None:
    """plan_bom 评测 expected_status=success 对应 Graph EXECUTED 状态时 matched_status=True。"""
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    case = EvaluationCase(
        question="查一下NT12R/66GDF的BOM材料",
        domain="plan_bom",
        expected_status="success",
    )
    suite = EvaluationSuite(
        name="BOM 成功匹配测试",
        domain="plan_bom",
        cases=[case],
    )

    fake_graph_runner = MagicMock()
    fake_graph_runner.run.return_value = BusinessQaGraphResponse(
        status="EXECUTED",
        execution_mode="graph_skeleton_only",
        question="查一下NT12R/66GDF的BOM材料",
        domain="plan_bom",
        execution_status="EXECUTED",
        execution_result={"answer_summary": "NT12R/66GDF 材料规格...", "row_count": 1},
    )

    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    assert report.results[0].matched_status is True
    assert report.results[0].actual_status == "success"
    assert report.passed_cases == 1
    assert report.domain == "plan_bom"


def test_eval_runner_plan_bom_status_matching_clarification() -> None:
    """plan_bom 评测 expected_status=clarification 对应 Graph CLARIFY 状态时 matched_status=True。"""
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    case = EvaluationCase(
        question="玻璃规格是什么",
        domain="plan_bom",
        expected_status="clarification",
    )
    suite = EvaluationSuite(
        name="BOM 澄清匹配测试",
        domain="plan_bom",
        cases=[case],
    )

    fake_graph_runner = MagicMock()
    fake_graph_runner.run.return_value = BusinessQaGraphResponse(
        status="CLARIFY",
        execution_mode="graph_skeleton_only",
        question="玻璃规格是什么",
        domain="plan_bom",
    )

    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    assert report.results[0].matched_status is True
    assert report.results[0].actual_status == "clarification"


def test_eval_runner_plan_bom_status_matching_unsupported() -> None:
    """plan_bom 评测 expected_status=unsupported 对应 Graph UNSUPPORTED 状态时 matched_status=True。"""
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    case = EvaluationCase(
        question="帮我把BOM导出到Excel",
        domain="plan_bom",
        expected_status="unsupported",
    )
    suite = EvaluationSuite(
        name="BOM 不支持匹配测试",
        domain="plan_bom",
        cases=[case],
    )

    fake_graph_runner = MagicMock()
    fake_graph_runner.run.return_value = BusinessQaGraphResponse(
        status="UNSUPPORTED",
        execution_mode="graph_skeleton_only",
        question="帮我把BOM导出到Excel",
        domain="plan_bom",
    )

    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    assert report.results[0].matched_status is True
    assert report.results[0].actual_status == "unsupported"


def test_eval_runner_plan_bom_empty_result_matching() -> None:
    """plan_bom expected_status=empty_result 对应 Graph EXECUTED+row_count=0 时 matched_status=True。"""
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    case = EvaluationCase(
        question="查一下订单99999的BOM",
        domain="plan_bom",
        expected_status="empty_result",
        allow_empty_substitute=True,
    )
    suite = EvaluationSuite(
        name="BOM 空结果匹配测试",
        domain="plan_bom",
        cases=[case],
    )

    fake_graph_runner = MagicMock()
    fake_graph_runner.run.return_value = BusinessQaGraphResponse(
        status="EXECUTED",
        execution_mode="graph_skeleton_only",
        question="查一下订单99999的BOM",
        domain="plan_bom",
        execution_status="EXECUTED",
        execution_result={"answer_summary": "未找到匹配记录", "row_count": 0},
    )

    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    assert report.results[0].matched_status is True
    assert report.results[0].actual_status == "empty_result"
    assert report.results[0].actual_row_count == 0


# =============================================================================
# RED 测试 7：BOM 评测 JSONL 输出
# =============================================================================


def test_plan_bom_eval_jsonl_output() -> None:
    """plan_bom 域评测可输出 JSONL 文件。"""
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner
    from tests.evaluation.plan_bom.samples import load_plan_bom_suite

    suite = load_plan_bom_suite()

    fake_graph_runner = MagicMock()

    def _fake_for(case: EvaluationCase) -> BusinessQaGraphResponse:
        if case.expected_status == "success":
            return BusinessQaGraphResponse(
                status="EXECUTED",
                execution_mode="graph_skeleton_only",
                question=case.question,
                domain="plan_bom",
                execution_status="EXECUTED",
                execution_result={"answer_summary": "BOM 结果", "row_count": 1},
            )
        elif case.expected_status == "clarification":
            return BusinessQaGraphResponse(
                status="CLARIFY",
                execution_mode="graph_skeleton_only",
                question=case.question,
                domain="plan_bom",
            )
        elif case.expected_status == "unsupported":
            return BusinessQaGraphResponse(
                status="UNSUPPORTED",
                execution_mode="graph_skeleton_only",
                question=case.question,
                domain="plan_bom",
            )
        else:
            return BusinessQaGraphResponse(
                status="EXECUTED",
                execution_mode="graph_skeleton_only",
                question=case.question,
                domain="plan_bom",
                execution_status="EXECUTED",
                execution_result={"answer_summary": "空结果", "row_count": 0},
            )

    fake_graph_runner.run.side_effect = [
        _fake_for(case) for case in suite.cases
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "plan_bom_eval.jsonl"
        runner = EvalGraphRunner(
            graph_runner=fake_graph_runner,
            suite=suite,
            output_jsonl=str(output_path),
        )
        runner.run()

        # 验证 JSONL 文件已创建
        assert output_path.exists()

        # 读取并验证 JSONL 内容
        lines = output_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == len(suite.cases)

        for i, line in enumerate(lines):
            record = json.loads(line)
            assert record["case_id"] == suite.cases[i].case_id
            assert "matched_status" in record
            assert "actual_status" in record


# =============================================================================
# RED 测试 8：BOM 样例无技术泄露关键词
# =============================================================================


def test_plan_bom_samples_no_technical_leak_in_questions() -> None:
    """BOM 评测样例的 question 字段不应包含 SQL、表名、query_key 等技术细节。

    RED：样例集尚未实现。
    """
    from tests.evaluation.plan_bom.samples import load_plan_bom_suite

    suite = load_plan_bom_suite()

    # 技术泄露关键词
    leak_keywords = (
        "SELECT ", "FROM ", "WHERE ", "INSERT ", "UPDATE ", "DELETE ",
        "query_key", "planner", "guardrail", "schema",
        "raw_response", "debug", "LLM", "nl2sql", "SQLPlan",
    )

    for case in suite.cases:
        question_upper = case.question.upper()
        for kw in leak_keywords:
            assert kw.upper() not in question_upper, (
                f"case {case.case_id} 的 question 包含技术关键词 '{kw}': {case.question}"
            )

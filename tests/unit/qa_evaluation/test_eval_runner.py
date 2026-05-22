"""NQE-E2 focused tests：评测 Graph 运行器（EvalGraphRunner）。

业务逻辑：
    验证 EvalGraphRunner 能正确遍历评测套件、调用 GraphRunner、
    生成 EvaluationResult 和 EvaluationReport，并输出 JSONL。

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
    EvaluationResult,
    EvaluationSuite,
)


# =============================================================================
# RED 测试 1：EvalGraphRunner 基本运行 —— 遍历 suite 并生成报告
# =============================================================================


def test_eval_runner_runs_all_cases_and_returns_report() -> None:
    """遍历评测套件中的所有 case，调用 GraphRunner，返回 EvaluationReport。

    RED：EvalGraphRunner 尚未实现，此测试应失败。
    """
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    # 构造评测套件
    case1 = EvaluationCase(
        question="2024年合肥基地总发运量",
        domain="logistics",
        expected_status="success",
        tags=["smoke"],
    )
    case2 = EvaluationCase(
        question="2023年阜宁到广州的运价",
        domain="logistics",
        expected_status="success",
        expected_row_count=3,
        tags=["smoke"],
    )

    suite = EvaluationSuite(
        name="物流核心评测集",
        domain="logistics",
        cases=[case1, case2],
    )

    # 构造 fake GraphRunner，返回模拟响应
    fake_graph_runner = MagicMock()
    fake_graph_runner.run.side_effect = [
        BusinessQaGraphResponse(
            status="EXECUTED",
            execution_mode="graph_skeleton_only",
            question="2024年合肥基地总发运量",
            domain="logistics",
            execution_status="EXECUTED",
            execution_result={
                "answer_summary": "2024年合肥基地总发运量为 1,250 车次",
                "row_count": 1,
            },
        ),
        BusinessQaGraphResponse(
            status="EXECUTED",
            execution_mode="graph_skeleton_only",
            question="2023年阜宁到广州的运价",
            domain="logistics",
            execution_status="EXECUTED",
            execution_result={
                "answer_summary": "2023年阜宁到广州运价为 3,200 元/车",
                "row_count": 3,
            },
        ),
    ]

    # 运行评测
    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    # 验证报告
    assert isinstance(report, EvaluationReport)
    assert report.suite_name == "物流核心评测集"
    assert report.total_cases == 2
    assert report.passed_cases == 2
    assert report.failed_cases == 0
    assert report.pass_rate == 1.0
    assert len(report.results) == 2

    # 验证每个结果关联到对应 case
    assert report.results[0].case_id == case1.case_id
    assert report.results[1].case_id == case2.case_id

    # 验证 fake runner 被调用了两次
    assert fake_graph_runner.run.call_count == 2


# =============================================================================
# RED 测试 2：状态匹配逻辑
# =============================================================================


def test_eval_runner_status_matching_success() -> None:
    """expected_status=success 对应 Graph EXECUTED 状态时 matched_status=True。"""
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    case = EvaluationCase(
        question="2024年总发运量",
        domain="logistics",
        expected_status="success",
    )
    suite = EvaluationSuite(
        name="状态匹配测试",
        domain="logistics",
        cases=[case],
    )

    fake_graph_runner = MagicMock()
    fake_graph_runner.run.return_value = BusinessQaGraphResponse(
        status="EXECUTED",
        execution_mode="graph_skeleton_only",
        question="2024年总发运量",
        domain="logistics",
        execution_status="EXECUTED",
        execution_result={"answer_summary": "总发运量 1,250 车次", "row_count": 1},
    )

    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    assert report.results[0].matched_status is True
    assert report.results[0].actual_status == "success"
    assert report.passed_cases == 1


def test_eval_runner_status_matching_clarification() -> None:
    """expected_status=clarification 对应 Graph CLARIFY 状态时 matched_status=True。"""
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    case = EvaluationCase(
        question="运费多少",
        domain="logistics",
        expected_status="clarification",
    )
    suite = EvaluationSuite(
        name="澄清匹配测试",
        domain="logistics",
        cases=[case],
    )

    fake_graph_runner = MagicMock()
    fake_graph_runner.run.return_value = BusinessQaGraphResponse(
        status="CLARIFY",
        execution_mode="graph_skeleton_only",
        question="运费多少",
        domain="logistics",
    )

    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    assert report.results[0].matched_status is True
    assert report.results[0].actual_status == "clarification"
    assert report.passed_cases == 1


def test_eval_runner_status_matching_unsupported() -> None:
    """expected_status=unsupported 对应 Graph UNSUPPORTED 状态时 matched_status=True。"""
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    case = EvaluationCase(
        question="给我导出所有数据",
        domain="logistics",
        expected_status="unsupported",
    )
    suite = EvaluationSuite(
        name="不支持匹配测试",
        domain="logistics",
        cases=[case],
    )

    fake_graph_runner = MagicMock()
    fake_graph_runner.run.return_value = BusinessQaGraphResponse(
        status="UNSUPPORTED",
        execution_mode="graph_skeleton_only",
        question="给我导出所有数据",
        domain="logistics",
    )

    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    assert report.results[0].matched_status is True
    assert report.results[0].actual_status == "unsupported"
    assert report.passed_cases == 1


def test_eval_runner_status_matching_error() -> None:
    """expected_status=error 对应 Graph ERROR 状态时 matched_status=True。"""
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    case = EvaluationCase(
        question="非法查询",
        domain="logistics",
        expected_status="error",
    )
    suite = EvaluationSuite(
        name="错误匹配测试",
        domain="logistics",
        cases=[case],
    )

    fake_graph_runner = MagicMock()
    fake_graph_runner.run.return_value = BusinessQaGraphResponse(
        status="ERROR",
        execution_mode="graph_skeleton_only",
        question="非法查询",
        domain="logistics",
    )

    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    assert report.results[0].matched_status is True
    assert report.results[0].actual_status == "error"
    assert report.passed_cases == 1


def test_eval_runner_status_mismatch() -> None:
    """预期 success 但实际 CLARIFY 时 matched_status=False。"""
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    case = EvaluationCase(
        question="含糊不清的问题",
        domain="logistics",
        expected_status="success",
    )
    suite = EvaluationSuite(
        name="不匹配测试",
        domain="logistics",
        cases=[case],
    )

    fake_graph_runner = MagicMock()
    fake_graph_runner.run.return_value = BusinessQaGraphResponse(
        status="CLARIFY",
        execution_mode="graph_skeleton_only",
        question="含糊不清的问题",
        domain="logistics",
    )

    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    assert report.results[0].matched_status is False
    assert report.results[0].actual_status == "clarification"
    assert report.passed_cases == 0
    assert report.failed_cases == 1


# =============================================================================
# RED 测试 3：row_count 匹配
# =============================================================================


def test_eval_runner_row_count_match() -> None:
    """expected_row_count 与实际结果行数一致时 key_numbers_match=True。"""
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    case = EvaluationCase(
        question="2024年合肥基地按承运商分组的发运量",
        domain="logistics",
        expected_status="success",
        expected_row_count=5,
    )
    suite = EvaluationSuite(
        name="行数匹配测试",
        domain="logistics",
        cases=[case],
    )

    fake_graph_runner = MagicMock()
    fake_graph_runner.run.return_value = BusinessQaGraphResponse(
        status="EXECUTED",
        execution_mode="graph_skeleton_only",
        question="2024年合肥基地按承运商分组的发运量",
        domain="logistics",
        execution_status="EXECUTED",
        execution_result={
            "answer_summary": "按承运商分组结果共5条",
            "row_count": 5,
        },
    )

    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    assert report.results[0].matched_status is True
    assert report.results[0].key_numbers_match is True
    assert report.results[0].actual_row_count == 5


def test_eval_runner_row_count_mismatch() -> None:
    """expected_row_count 与实际结果行数不一致时 key_numbers_match=False。"""
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    case = EvaluationCase(
        question="2024年合肥基地按承运商分组的发运量",
        domain="logistics",
        expected_status="success",
        expected_row_count=5,
    )
    suite = EvaluationSuite(
        name="行数不匹配测试",
        domain="logistics",
        cases=[case],
    )

    fake_graph_runner = MagicMock()
    fake_graph_runner.run.return_value = BusinessQaGraphResponse(
        status="EXECUTED",
        execution_mode="graph_skeleton_only",
        question="2024年合肥基地按承运商分组的发运量",
        domain="logistics",
        execution_status="EXECUTED",
        execution_result={
            "answer_summary": "按承运商分组结果共3条",
            "row_count": 3,
        },
    )

    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    assert report.results[0].key_numbers_match is False
    assert report.results[0].actual_row_count == 3


# =============================================================================
# RED 测试 4：技术泄露检查
# =============================================================================


def test_eval_runner_leak_check_no_leak() -> None:
    """无技术泄露时 leak_found=False。"""
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    case = EvaluationCase(
        question="2024年总发运量",
        domain="logistics",
        expected_status="success",
    )
    suite = EvaluationSuite(name="无泄露测试", domain="logistics", cases=[case])

    fake_graph_runner = MagicMock()
    fake_graph_runner.run.return_value = BusinessQaGraphResponse(
        status="EXECUTED",
        execution_mode="graph_skeleton_only",
        question="2024年总发运量",
        domain="logistics",
        execution_status="EXECUTED",
        execution_result={
            "answer_summary": "2024年总发运量为1,250车次",
            "row_count": 1,
        },
    )

    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    assert report.results[0].leak_found is False


def test_eval_runner_leak_check_found() -> None:
    """发现 SQL 关键词泄露时 leak_found=True。"""
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    case = EvaluationCase(
        question="2024年总发运量",
        domain="logistics",
        expected_status="success",
    )
    suite = EvaluationSuite(name="泄露测试", domain="logistics", cases=[case])

    fake_graph_runner = MagicMock()
    fake_graph_runner.run.return_value = BusinessQaGraphResponse(
        status="EXECUTED",
        execution_mode="graph_skeleton_only",
        question="2024年总发运量",
        domain="logistics",
        execution_status="EXECUTED",
        execution_result={
            "answer_summary": "SELECT * FROM logistics_table WHERE year=2024 -- 1,250车次",
            "row_count": 1,
        },
    )

    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    assert report.results[0].leak_found is True
    # leak 会导致 matched_status 为 False（即使业务状态匹配）
    assert report.results[0].matched_status is False


# =============================================================================
# RED 测试 5：JSONL 输出
# =============================================================================


def test_eval_runner_jsonl_output() -> None:
    """output_jsonl 指定时输出评测结果到 JSONL 文件。"""
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    case1 = EvaluationCase(
        question="2024年合肥基地总发运量",
        domain="logistics",
        expected_status="success",
    )
    case2 = EvaluationCase(
        question="运费多少",
        domain="logistics",
        expected_status="clarification",
    )
    suite = EvaluationSuite(
        name="JSONL输出测试",
        domain="logistics",
        cases=[case1, case2],
    )

    fake_graph_runner = MagicMock()
    fake_graph_runner.run.side_effect = [
        BusinessQaGraphResponse(
            status="EXECUTED",
            execution_mode="graph_skeleton_only",
            question="2024年合肥基地总发运量",
            domain="logistics",
            execution_status="EXECUTED",
            execution_result={"answer_summary": "1,250 车次", "row_count": 1},
        ),
        BusinessQaGraphResponse(
            status="CLARIFY",
            execution_mode="graph_skeleton_only",
            question="运费多少",
            domain="logistics",
        ),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "eval_results.jsonl"
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
        assert len(lines) == 2

        line1 = json.loads(lines[0])
        assert line1["case_id"] == case1.case_id
        assert line1["matched_status"] is True
        assert line1["actual_status"] == "success"

        line2 = json.loads(lines[1])
        assert line2["case_id"] == case2.case_id
        assert line2["matched_status"] is True
        assert line2["actual_status"] == "clarification"


# =============================================================================
# RED 测试 6：空套件处理
# =============================================================================


def test_eval_runner_empty_suite() -> None:
    """空评测套件（cases=[]）应返回总用例 0、通过率 1.0 的报告。"""
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    suite = EvaluationSuite(
        name="空套件",
        domain="logistics",
        cases=[],
    )

    fake_graph_runner = MagicMock()

    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    assert report.total_cases == 0
    assert report.passed_cases == 0
    assert report.failed_cases == 0
    assert report.pass_rate == 1.0
    assert len(report.results) == 0
    # 空套件不应调用 GraphRunner
    assert fake_graph_runner.run.call_count == 0


# =============================================================================
# RED 测试 7：GraphRunner 异常处理
# =============================================================================


def test_eval_runner_graph_exception_produces_error_result() -> None:
    """GraphRunner 抛异常时应捕获并记录 error 结果，不中断评测流程。"""
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    case1 = EvaluationCase(
        question="正常问题",
        domain="logistics",
        expected_status="success",
    )
    case2 = EvaluationCase(
        question="会崩溃的问题",
        domain="logistics",
        expected_status="success",
    )
    suite = EvaluationSuite(
        name="异常处理测试",
        domain="logistics",
        cases=[case1, case2],
    )

    fake_graph_runner = MagicMock()
    fake_graph_runner.run.side_effect = [
        BusinessQaGraphResponse(
            status="EXECUTED",
            execution_mode="graph_skeleton_only",
            question="正常问题",
            domain="logistics",
            execution_status="EXECUTED",
            execution_result={"answer_summary": "正常回答", "row_count": 1},
        ),
        RuntimeError("模拟 Graph 内部异常"),
    ]

    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    # case1 正常通过
    assert report.results[0].matched_status is True
    assert report.results[0].actual_status == "success"

    # case2 异常应记录为 error
    assert report.results[1].actual_status == "error"
    assert report.results[1].matched_status is False  # 预期 success 但实际 error
    assert report.results[1].mismatch_detail is not None
    assert "RuntimeError" in report.results[1].mismatch_detail

    # 报告汇总
    assert report.total_cases == 2
    assert report.passed_cases == 1
    assert report.failed_cases == 1


# =============================================================================
# RED 测试 8：allow_empty_substitute 选项
# =============================================================================


def test_eval_runner_empty_result_with_allow_empty_true() -> None:
    """allow_empty_substitute=True 且实际为空结果时 matched_status=True。"""
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    case = EvaluationCase(
        question="2024年不存在的路线",
        domain="logistics",
        expected_status="empty_result",
        allow_empty_substitute=True,
    )
    suite = EvaluationSuite(name="空结果允许测试", domain="logistics", cases=[case])

    fake_graph_runner = MagicMock()
    fake_graph_runner.run.return_value = BusinessQaGraphResponse(
        status="EXECUTED",
        execution_mode="graph_skeleton_only",
        question="2024年不存在的路线",
        domain="logistics",
        execution_status="EXECUTED",
        execution_result={
            "answer_summary": "未找到匹配记录",
            "row_count": 0,
        },
    )

    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    assert report.results[0].actual_status == "empty_result"
    assert report.results[0].matched_status is True
    assert report.results[0].actual_row_count == 0
    assert report.passed_cases == 1


# =============================================================================
# RED 测试 9：expected_text 子串匹配
# =============================================================================


def test_eval_runner_expected_text_substring_match() -> None:
    """expected_text 包含在实际回答中时 text_similarity > 0（至少匹配长度比例）。"""
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    case = EvaluationCase(
        question="2024年合肥基地发运量",
        domain="logistics",
        expected_status="success",
        expected_text="1,250 车次",
    )
    suite = EvaluationSuite(name="文本匹配测试", domain="logistics", cases=[case])

    fake_graph_runner = MagicMock()
    fake_graph_runner.run.return_value = BusinessQaGraphResponse(
        status="EXECUTED",
        execution_mode="graph_skeleton_only",
        question="2024年合肥基地发运量",
        domain="logistics",
        execution_status="EXECUTED",
        execution_result={
            "answer_summary": "2024年合肥基地总发运量为 1,250 车次",
            "row_count": 1,
        },
    )

    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    assert report.results[0].text_similarity is not None
    assert report.results[0].text_similarity > 0.0
    assert report.results[0].matched_status is True


def test_eval_runner_expected_text_not_found() -> None:
    """expected_text 不在回答中时 text_similarity=0 且记录 mismatch。"""
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    case = EvaluationCase(
        question="2024年合肥基地发运量",
        domain="logistics",
        expected_status="success",
        expected_text="5,000 车次",
    )
    suite = EvaluationSuite(name="文本不匹配测试", domain="logistics", cases=[case])

    fake_graph_runner = MagicMock()
    fake_graph_runner.run.return_value = BusinessQaGraphResponse(
        status="EXECUTED",
        execution_mode="graph_skeleton_only",
        question="2024年合肥基地发运量",
        domain="logistics",
        execution_status="EXECUTED",
        execution_result={
            "answer_summary": "2024年合肥基地总发运量为 1,250 车次",
            "row_count": 1,
        },
    )

    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    # 文本不匹配不影响 matched_status（以状态为主要判断），
    # 但应记录在 mismatch_detail 中
    assert report.results[0].text_similarity == 0.0


# =============================================================================
# RED 测试 10：物流评测样例可加载
# =============================================================================


def test_logistics_evaluation_samples_loadable() -> None:
    """物流评测样例集可从 tests/evaluation/logistics/ 加载为 EvaluationSuite。

    RED：样例文件和加载函数尚未实现。
    """
    from tests.evaluation.logistics.samples import load_logistics_suite

    suite = load_logistics_suite()

    assert isinstance(suite, EvaluationSuite)
    assert suite.domain == "logistics"
    assert len(suite.cases) >= 5, f"首批物流评测样例应至少 5 条，实际 {len(suite.cases)} 条"

    # 验证每条 case 的 domain 与 suite 一致
    for case in suite.cases:
        assert case.domain == "logistics"
        assert case.question, f"每条 case 必须有 question"
        assert case.expected_status, f"每条 case 必须有 expected_status"


# =============================================================================
# NQE-E4 RED 测试：功率评测 EvalGraphRunner 支持
# =============================================================================


def test_eval_runner_power_prediction_domain_suite() -> None:
    """power_prediction 域的评测套件能被 EvalGraphRunner 正确执行。

    RED：domain_hint="power_prediction" 未被 domain_registry 识别，
    当前会落入 unknown → CLARIFY，导致 matched_status=False。
    """
    from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner

    case = EvaluationCase(
        question="615W 版型功率预测",
        domain="power_prediction",
        expected_status="success",
        tags=["smoke", "power"],
    )
    suite = EvaluationSuite(
        name="功率评测集",
        domain="power_prediction",
        cases=[case],
    )

    fake_graph_runner = MagicMock()
    fake_graph_runner.run.return_value = BusinessQaGraphResponse(
        status="EXECUTED",
        execution_mode="graph_skeleton_only",
        question="615W 版型功率预测",
        domain="plan_bom",
        execution_status="EXECUTED",
        execution_result={
            "answer_summary": "615W 版型功率预测结果：中心功率 615W",
            "row_count": 1,
        },
    )

    runner = EvalGraphRunner(graph_runner=fake_graph_runner, suite=suite)
    report = runner.run()

    assert isinstance(report, EvaluationReport)
    assert report.domain == "power_prediction"
    assert report.total_cases == 1
    assert report.results[0].matched_status is True, (
        f"预期 matched_status=True，实际 {report.results[0].matched_status}，"
        f"mismatch_detail={report.results[0].mismatch_detail}"
    )
    assert report.results[0].actual_status == "success"


def test_power_evaluation_samples_loadable() -> None:
    """功率评测样例集可从 tests/evaluation/plan_power/ 加载为 EvaluationSuite。

    RED：tests/evaluation/plan_power/samples.py 尚未创建。
    """
    from tests.evaluation.plan_power.samples import load_power_suite

    suite = load_power_suite()

    assert isinstance(suite, EvaluationSuite)
    assert suite.domain == "power_prediction"
    assert len(suite.cases) >= 5, (
        f"首批功率评测样例应至少 5 条，实际 {len(suite.cases)} 条"
    )

    for case in suite.cases:
        assert case.domain == "power_prediction"
        assert case.question, "每条 case 必须有 question"
        assert case.expected_status, "每条 case 必须有 expected_status"

"""统一业务问法评测集（NQE-Eval）Schema 的 focused tests。

业务逻辑：
    验证 EvaluationCase / EvaluationSuite / EvaluationResult / EvaluationReport
    四类核心 schema 的字段定义、业务规则和跨域（物流/BOM/功率）存储能力。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestEvaluationCase:
    """EvaluationCase schema 测试：单条评测用例的结构与约束。"""

    def test_question_required(self):
        """question 为必填字段，缺失时抛 ValidationError。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationCase

        with pytest.raises(ValidationError, match="question"):
            EvaluationCase(  # type: ignore[call-arg]
                domain="logistics",
                expected_status="success",
            )

    def test_domain_required(self):
        """domain 为必填字段，必须是已知业务域之一。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationCase

        with pytest.raises(ValidationError, match="domain"):
            EvaluationCase(  # type: ignore[call-arg]
                question="合肥到阜宁的运费是多少",
                expected_status="success",
            )

    def test_expected_status_required(self):
        """expected_status 为必填字段，标识本条的预期回答状态。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationCase

        with pytest.raises(ValidationError, match="expected_status"):
            EvaluationCase(  # type: ignore[call-arg]
                question="合肥到阜宁的运费是多少",
                domain="logistics",
            )

    def test_minimal_case_valid(self):
        """最少字段（question + domain + expected_status）可以构造有效用例。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationCase

        case = EvaluationCase(
            question="2023年合肥到广州的总运费",
            domain="logistics",
            expected_status="success",
        )
        assert case.question == "2023年合肥到广州的总运费"
        assert case.domain == "logistics"
        assert case.expected_status == "success"

    def test_expected_status_enum(self):
        """expected_status 须按业务定义允许的状态值。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationCase

        # 合法状态值应可构造
        for status in ("success", "clarification", "unsupported", "empty_result", "error"):
            case = EvaluationCase(
                question="测试问题",
                domain="logistics",
                expected_status=status,
            )
            assert case.expected_status == status

    def test_expected_status_invalid_raises(self):
        """非预期状态值应抛 ValidationError。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationCase

        with pytest.raises(ValidationError):
            EvaluationCase(
                question="测试",
                domain="logistics",
                expected_status="unknown_status_xyz",
            )

    def test_optional_fields_default(self):
        """可选的 expected_text / expected_row_count / caliber 应有合理默认值。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationCase

        case = EvaluationCase(
            question="2023年合肥基地发货量",
            domain="logistics",
            expected_status="success",
        )
        assert case.expected_text is None
        assert case.expected_row_count is None
        assert case.caliber is None
        # schema_version / tags / allow_empty_substitute 应有文档级说明即可
        assert isinstance(case.schema_version, str)
        assert case.schema_version == "1.0"

    def test_full_case_all_fields(self):
        """全字段构造用例，所有字段均可正确存取。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationCase

        case = EvaluationCase(
            question="2023年合肥基地发货量",
            domain="logistics",
            expected_status="success",
            expected_text="2023年合肥基地总发货量为 12,500 MW",
            expected_row_count=1,
            caliber="发货量=总费用/车次数，按合肥基地筛选",
            tags=["smoke", "logistics_route_price"],
            allow_empty_substitute=False,
            schema_version="1.0",
        )
        assert case.question == "2023年合肥基地发货量"
        assert case.domain == "logistics"
        assert case.expected_status == "success"
        assert case.expected_text == "2023年合肥基地总发货量为 12,500 MW"
        assert case.expected_row_count == 1
        assert case.caliber == "发货量=总费用/车次数，按合肥基地筛选"
        assert case.tags == ["smoke", "logistics_route_price"]
        assert case.allow_empty_substitute is False

    def test_domain_allows_logistics_bom_power(self):
        """domain 支持物流（logistics）、计划BOM（plan_bom）、功率（power_prediction）。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationCase

        for domain in ("logistics", "plan_bom", "power_prediction", "business_analysis"):
            case = EvaluationCase(
                question=f"{domain}域测试问题",
                domain=domain,
                expected_status="success",
            )
            assert case.domain == domain

    def test_tags_optional_default(self):
        """tags 为可选字段，默认空列表。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationCase

        case = EvaluationCase(
            question="测试",
            domain="logistics",
            expected_status="success",
        )
        assert case.tags == []

    def test_allow_empty_substitute_default(self):
        """allow_empty_substitute 默认 True（允许空结果回填预期）。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationCase

        case = EvaluationCase(
            question="测试",
            domain="logistics",
            expected_status="empty_result",
        )
        assert case.allow_empty_substitute is True

    def test_case_id_autogenerated(self):
        """case_id 在未显式传入时自动生成唯一标识。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationCase

        case1 = EvaluationCase(
            question="问题A",
            domain="logistics",
            expected_status="success",
        )
        case2 = EvaluationCase(
            question="问题B",
            domain="logistics",
            expected_status="success",
        )
        assert case1.case_id is not None
        assert case2.case_id is not None
        assert case1.case_id != case2.case_id, "自动生成的 case_id 应互不相同"


class TestEvaluationSuite:
    """EvaluationSuite schema 测试：评测套件的结构与约束。"""

    def test_name_required(self):
        """name 为必填字段。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationSuite

        with pytest.raises(ValidationError, match="name"):
            EvaluationSuite(  # type: ignore[call-arg]
                domain="logistics",
            )

    def test_domain_required(self):
        """domain 为必填字段。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationSuite

        with pytest.raises(ValidationError, match="domain"):
            EvaluationSuite(  # type: ignore[call-arg]
                name="物流基础问答回归",
            )

    def test_cases_default_empty_list(self):
        """cases 默认为空列表。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationSuite

        suite = EvaluationSuite(
            name="物流基础问答回归",
            domain="logistics",
        )
        assert suite.cases == []

    def test_suite_with_cases(self):
        """套件可包含多条 EvaluationCase。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationCase, EvaluationSuite

        case1 = EvaluationCase(
            question="2023年合肥到广州总运费",
            domain="logistics",
            expected_status="success",
            expected_row_count=5,
        )
        case2 = EvaluationCase(
            question="2024年阜宁基地发货量",
            domain="logistics",
            expected_status="success",
            expected_row_count=3,
        )
        suite = EvaluationSuite(
            name="物流核心问答",
            domain="logistics",
            cases=[case1, case2],
        )
        assert len(suite.cases) == 2
        assert suite.cases[0].question == "2023年合肥到广州总运费"
        assert suite.cases[1].question == "2024年阜宁基地发货量"

    def test_suite_domain_validation(self):
        """suite 的 domain 必须在白名单内，否则抛 ValidationError。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationSuite

        with pytest.raises(ValidationError, match="domain 必须是以下之一"):
            EvaluationSuite(
                name="未知域套件",
                domain="unknown_domain_xyz",
            )

    def test_suite_cases_domain_mismatch(self):
        """套件内 case 的 domain 与套件 domain 不一致时应抛 ValidationError。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationCase, EvaluationSuite

        case = EvaluationCase(
            question="BOM问题",
            domain="plan_bom",  # 与套件的 logistics 不一致
            expected_status="success",
        )
        with pytest.raises(ValidationError, match="domain.*不一致"):
            EvaluationSuite(
                name="物流套件",
                domain="logistics",
                cases=[case],
            )


class TestEvaluationResult:
    """EvaluationResult schema 测试：单条用例的评测结果。"""

    def test_case_id_required(self):
        """case_id 为必填字段，关联被评测的用例。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationResult

        with pytest.raises(ValidationError, match="case_id"):
            EvaluationResult(  # type: ignore[call-arg]
                matched_status=True,
            )

    def test_minimal_result_valid(self):
        """最少字段即可构造有效评测结果。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationResult

        result = EvaluationResult(
            case_id="case_001",
            matched_status=True,
        )
        assert result.case_id == "case_001"
        assert result.matched_status is True

    def test_full_result_all_fields(self):
        """全字段构造评测结果。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationResult

        result = EvaluationResult(
            case_id="case_001",
            matched_status=True,
            key_numbers_match=True,
            text_similarity=0.95,
            leak_found=False,
            actual_status="success",
            actual_answer_summary="2023年合肥基地总发货量为12,500 MW",
            actual_row_count=1,
            mismatch_detail="各项指标完全匹配，无差异",
        )
        assert result.case_id == "case_001"
        assert result.matched_status is True
        assert result.key_numbers_match is True
        assert result.text_similarity == 0.95
        assert result.leak_found is False
        assert result.actual_status == "success"
        assert result.actual_answer_summary == "2023年合肥基地总发货量为12,500 MW"
        assert result.actual_row_count == 1
        assert result.mismatch_detail == "各项指标完全匹配，无差异"

    def test_text_similarity_range(self):
        """text_similarity 应在 0.0~1.0 范围内。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationResult

        # 边界值通过
        for val in (0.0, 0.5, 1.0):
            result = EvaluationResult(
                case_id="case_001",
                matched_status=True,
                text_similarity=val,
            )
            assert result.text_similarity == val

    def test_default_values(self):
        """默认值：matched_status=False, key_numbers_match=None, leak_found=False。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationResult

        result = EvaluationResult(case_id="case_001")
        assert result.matched_status is False
        assert result.key_numbers_match is None
        assert result.leak_found is False


class TestEvaluationReport:
    """EvaluationReport schema 测试：套件级别的评测报告。"""

    def test_suite_name_required(self):
        """suite_name 为必填字段。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationReport

        with pytest.raises(ValidationError, match="suite_name"):
            EvaluationReport(  # type: ignore[call-arg]
                total_cases=10,
                passed_cases=8,
                failed_cases=2,
            )

    def test_basic_report(self):
        """基础报告包含总量/通过/失败统计。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationReport

        report = EvaluationReport(
            suite_name="物流核心问答回归",
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
        )
        assert report.suite_name == "物流核心问答回归"
        assert report.total_cases == 10
        assert report.passed_cases == 8
        assert report.failed_cases == 2

    def test_results_list_default(self):
        """results 默认为空列表。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationReport

        report = EvaluationReport(
            suite_name="物流核心问答回归",
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
        )
        assert report.results == []

    def test_full_report_with_results(self):
        """完整报告包含若干条 EvaluationResult。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationReport, EvaluationResult

        r1 = EvaluationResult(case_id="case_001", matched_status=True)
        r2 = EvaluationResult(case_id="case_002", matched_status=False)
        report = EvaluationReport(
            suite_name="物流核心问答回归",
            total_cases=2,
            passed_cases=1,
            failed_cases=1,
            results=[r1, r2],
        )
        assert len(report.results) == 2
        assert report.results[0].matched_status is True
        assert report.results[1].matched_status is False

    def test_pass_rate_computed(self):
        """pass_rate 可根据 passed/total 计算。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationReport

        report = EvaluationReport(
            suite_name="测试套件",
            total_cases=10,
            passed_cases=7,
            failed_cases=3,
        )
        assert report.pass_rate == pytest.approx(0.7)

    def test_consistency_check(self):
        """passed + failed 应与 total 一致，不一致时抛错误。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationReport

        with pytest.raises(ValidationError, match="passed_cases \\+ failed_cases 必须等于 total_cases"):
            EvaluationReport(
                suite_name="测试套件",
                total_cases=10,
                passed_cases=5,
                failed_cases=3,  # 5+3 != 10
            )

    def test_domain_field(self):
        """domain 字段应正确存储评测所属业务域。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationReport

        report = EvaluationReport(
            suite_name="BOM问答回归",
            domain="plan_bom",
            total_cases=5,
            passed_cases=5,
            failed_cases=0,
        )
        assert report.domain == "plan_bom"

    def test_results_count_mismatch(self):
        """results 列表长度与 total_cases 不一致时应抛 ValidationError。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationReport, EvaluationResult

        r1 = EvaluationResult(case_id="case_001", matched_status=True)
        with pytest.raises(ValidationError, match="results 长度"):
            EvaluationReport(
                suite_name="测试套件",
                total_cases=5,  # 声明 5 条，但只给了 1 条结果
                passed_cases=1,
                failed_cases=4,
                results=[r1],
            )


class TestCrossDomainStorage:
    """跨域存储测试：验证物流、BOM、功率的评测用例均可存入。"""

    def test_logistics_case_serialization(self):
        """物流域用例可序列化/反序列化。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationCase

        case = EvaluationCase(
            question="2023年合肥基地发运量",
            domain="logistics",
            expected_status="success",
            expected_text="2023年合肥基地总发运量约 2500 车次",
            expected_row_count=1,
            caliber="发运量=车次数，按合肥基地筛选",
            tags=["logistics", "smoke"],
        )
        # 验证 model_dump 返回所有关键字段
        d = case.model_dump(mode="json")
        assert d["question"] == "2023年合肥基地发运量"
        assert d["domain"] == "logistics"
        assert d["expected_status"] == "success"
        assert d["expected_row_count"] == 1
        assert d["caliber"] == "发运量=车次数，按合肥基地筛选"

    def test_bom_case_serialization(self):
        """计划BOM域用例可序列化/反序列化。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationCase

        case = EvaluationCase(
            question="BOM评审号 BM2024-00123 的物料清单",
            domain="plan_bom",
            expected_status="success",
            expected_row_count=15,
            caliber="按评审号 BM2024-00123 查询全部物料行",
            tags=["plan_bom", "bom_query"],
        )
        d = case.model_dump(mode="json")
        assert d["question"] == "BOM评审号 BM2024-00123 的物料清单"
        assert d["domain"] == "plan_bom"
        assert d["expected_status"] == "success"
        assert d["expected_row_count"] == 15

    def test_power_prediction_case_serialization(self):
        """功率预测域用例可序列化/反序列化。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationCase

        case = EvaluationCase(
            question="615功率 4mm² 线长400/200 的功率档位预测",
            domain="power_prediction",
            expected_status="success",
            expected_text="功率档位为第3档",
            caliber="基于GCL功率测试基准xlsm模型计算",
            tags=["power", "prediction"],
        )
        d = case.model_dump(mode="json")
        assert d["question"] == "615功率 4mm² 线长400/200 的功率档位预测"
        assert d["domain"] == "power_prediction"
        assert d["expected_status"] == "success"

    def test_suite_cross_domain(self):
        """评测套件可包含不同业务域的用例（由 suite domain 字段声明）。"""
        from backend.app.domains.qa_evaluation.schema import EvaluationCase, EvaluationSuite

        # 套件声明为 logistics，用例必须同域
        case = EvaluationCase(
            question="物流问题",
            domain="logistics",
            expected_status="success",
        )
        suite = EvaluationSuite(
            name="物流评测集",
            domain="logistics",
            cases=[case],
        )
        assert suite.domain == "logistics"
        assert len(suite.cases) == 1
        assert suite.cases[0].domain == "logistics"

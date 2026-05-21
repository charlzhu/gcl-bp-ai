"""M15：灰度门禁测试（RED — TDD 第一阶段）。

测试目标：
    LogisticsNl2SqlGrayscaleGate 支持风险分类、每类独立灰度开关、旧链路兜底和 A/B 对比。
"""

from __future__ import annotations

import pytest

from backend.app.domains.logistics.schemas.data_qa import (
    LogisticsDataQaPlan,
    LogisticsDataQaResult,
    LogisticsDataQaStatus,
    LogisticsDataQaTable,
)
from backend.app.domains.logistics.services.nl2sql.m15_grayscale_gate import (
    GrayscaleQuestionType,
    LogisticsNl2SqlGrayscaleConfig,
    LogisticsNl2SqlGrayscaleDecision,
    LogisticsNl2SqlGrayscaleGate,
)


def _make_formal_result(
    query_key: str = "simple_aggregate",
    row_count: int = 10,
    status_code: str = "SUCCESS",
) -> LogisticsDataQaResult:
    return LogisticsDataQaResult(
        answer_summary="测试结果",
        result_table=LogisticsDataQaTable(
            columns=["c1"],
            rows=[{"c1": i} for i in range(row_count)],
        ),
        query_plan=LogisticsDataQaPlan(intent="test", query_key=query_key),
        status=LogisticsDataQaStatus(code=status_code, message="test", success=True),
    )


class TestLogisticsNl2SqlGrayscaleGateInit:
    """灰度门禁初始化测试。"""

    def test_default_config_all_disabled(self) -> None:
        """默认配置下所有问题类型灰度开关为关闭。"""
        gate = LogisticsNl2SqlGrayscaleGate()
        for qt in GrayscaleQuestionType:
            assert gate.config.is_enabled(qt) is False

    def test_custom_config_enables_specific_types(self) -> None:
        """自定义配置只开启指定问题类型。"""
        config = LogisticsNl2SqlGrayscaleConfig(
            enabled_types={GrayscaleQuestionType.SIMPLE_AGGREGATE},
        )
        assert config.is_enabled(GrayscaleQuestionType.SIMPLE_AGGREGATE) is True
        assert config.is_enabled(GrayscaleQuestionType.DIMENSION_SPLIT) is False

    def test_serialization(self) -> None:
        """配置可 JSON 序列化。"""
        config = LogisticsNl2SqlGrayscaleConfig(
            enabled_types={GrayscaleQuestionType.SIMPLE_AGGREGATE, GrayscaleQuestionType.MULTI_METRIC_SUMMARY},
        )
        data = config.model_dump(mode="json")
        assert isinstance(data, dict)
        assert "simple_aggregate" in data["enabled_types"]

    def test_question_type_enum_values(self) -> None:
        """问题类型枚举值符合设计文档。"""
        types = set(GrayscaleQuestionType)
        assert GrayscaleQuestionType.SIMPLE_AGGREGATE in types
        assert GrayscaleQuestionType.DIMENSION_SPLIT in types
        assert GrayscaleQuestionType.MULTI_METRIC_SUMMARY in types


class TestLogisticsNl2SqlGrayscaleDecideSimpleAggregate:
    """简单 aggregate 类型灰度决策测试。"""

    def test_enabled_type_allows_grayscale(self) -> None:
        """开启灰度的问题类型允许灰度接管。"""
        config = LogisticsNl2SqlGrayscaleConfig(
            enabled_types={GrayscaleQuestionType.SIMPLE_AGGREGATE},
        )
        gate = LogisticsNl2SqlGrayscaleGate(config=config)
        formal = _make_formal_result(query_key="total_fee")
        decision = gate.decide(formal=formal)
        assert decision.should_grayscale is True
        assert decision.question_type == GrayscaleQuestionType.SIMPLE_AGGREGATE

    def test_disabled_type_fallback_to_formal(self) -> None:
        """未开启灰度的问题类型回退到正式链路。"""
        gate = LogisticsNl2SqlGrayscaleGate()  # 默认全部关闭
        formal = _make_formal_result(query_key="total_fee")
        decision = gate.decide(formal=formal)
        assert decision.should_grayscale is False
        assert decision.fallback_reason == "grayscale_disabled"


class TestLogisticsNl2SqlGrayscaleDecideDimensionSplit:
    """按维度拆分类型灰度决策测试。"""

    def test_dimension_split_enabled(self) -> None:
        """开启按维度拆分灰度。"""
        config = LogisticsNl2SqlGrayscaleConfig(
            enabled_types={GrayscaleQuestionType.DIMENSION_SPLIT},
        )
        gate = LogisticsNl2SqlGrayscaleGate(config=config)
        formal = _make_formal_result(query_key="yearly_mw_breakdown")
        decision = gate.decide(formal=formal)
        assert decision.should_grayscale is True
        assert decision.question_type == GrayscaleQuestionType.DIMENSION_SPLIT


class TestLogisticsNl2SqlGrayscaleDecideMultiMetric:
    """多指标汇总类型灰度决策测试。"""

    def test_multi_metric_enabled(self) -> None:
        """开启多指标汇总灰度。"""
        config = LogisticsNl2SqlGrayscaleConfig(
            enabled_types={GrayscaleQuestionType.MULTI_METRIC_SUMMARY},
        )
        gate = LogisticsNl2SqlGrayscaleGate(config=config)
        formal = _make_formal_result(query_key="multi_metric_comparison")
        decision = gate.decide(formal=formal)
        assert decision.should_grayscale is True


class TestLogisticsNl2SqlGrayscaleDecideQueryKeyClassification:
    """query_key 到问题类型的分类测试。"""

    def test_unknown_query_key_maps_to_unsupported(self) -> None:
        """未知 query_key 映射为 None 类型，灰度回退。"""
        config = LogisticsNl2SqlGrayscaleConfig(
            enabled_types={GrayscaleQuestionType.SIMPLE_AGGREGATE},
        )
        gate = LogisticsNl2SqlGrayscaleGate(config=config)
        formal = _make_formal_result(query_key="unknown_complex_query")
        decision = gate.decide(formal=formal)
        assert decision.should_grayscale is False
        assert decision.question_type is None

    def test_composite_decomposed_maps_to_dimension_split(self) -> None:
        """composite_decomposed query_key 映射为 DIMENSION_SPLIT。"""
        config = LogisticsNl2SqlGrayscaleConfig(
            enabled_types={GrayscaleQuestionType.DIMENSION_SPLIT},
        )
        gate = LogisticsNl2SqlGrayscaleGate(config=config)
        formal = _make_formal_result(query_key="composite_decomposed")
        decision = gate.decide(formal=formal)
        assert decision.should_grayscale is True
        assert decision.question_type == GrayscaleQuestionType.DIMENSION_SPLIT

    def test_hist_prefix_maps_to_simple_aggregate(self) -> None:
        """hist_ 前缀的 query_key 映射为 SIMPLE_AGGREGATE。"""
        config = LogisticsNl2SqlGrayscaleConfig(
            enabled_types={GrayscaleQuestionType.SIMPLE_AGGREGATE},
        )
        gate = LogisticsNl2SqlGrayscaleGate(config=config)
        formal = _make_formal_result(query_key="hist_total_fee_city_rank")
        decision = gate.decide(formal=formal)
        assert decision.should_grayscale is True
        assert decision.question_type == GrayscaleQuestionType.SIMPLE_AGGREGATE


class TestLogisticsNl2SqlGrayscaleDecisionModel:
    """决策结果模型测试。"""

    def test_serialization(self) -> None:
        """灰度决策可 JSON 序列化。"""
        decision = LogisticsNl2SqlGrayscaleDecision(
            should_grayscale=True,
            question_type=GrayscaleQuestionType.SIMPLE_AGGREGATE,
            fallback_reason=None,
        )
        data = decision.model_dump(mode="json")
        assert data["should_grayscale"] is True
        assert data["question_type"] == "simple_aggregate"

    def test_fallback_reason_set_when_disabled(self) -> None:
        """灰度关闭时 fallback_reason 不为空。"""
        decision = LogisticsNl2SqlGrayscaleDecision(
            should_grayscale=False,
            question_type=GrayscaleQuestionType.SIMPLE_AGGREGATE,
            fallback_reason="grayscale_disabled",
        )
        assert decision.fallback_reason is not None

    def test_default_decision_no_grayscale(self) -> None:
        """默认决策为不灰度。"""
        decision = LogisticsNl2SqlGrayscaleDecision()
        assert decision.should_grayscale is False
        assert decision.question_type is None


class TestLogisticsNl2SqlGrayscaleDomainScoped:
    """域粒度灰度配置测试。"""

    def test_domain_enabled_allows_grayscale(self) -> None:
        """域粒度的灰度配置应生效。"""
        config = LogisticsNl2SqlGrayscaleConfig(
            enabled_domains={"business_analysis"},
            domain_types={"business_analysis": {GrayscaleQuestionType.SIMPLE_AGGREGATE}},
        )
        gate = LogisticsNl2SqlGrayscaleGate(config=config)
        formal = _make_formal_result(query_key="total_fee")
        decision = gate.decide(formal=formal, domain="business_analysis")
        assert decision.should_grayscale is True
        assert decision.domain == "business_analysis"

    def test_domain_disabled_fallback(self) -> None:
        """未启用的域应回退。"""
        config = LogisticsNl2SqlGrayscaleConfig(
            enabled_domains={"logistics"},
            domain_types={"logistics": {GrayscaleQuestionType.SIMPLE_AGGREGATE}},
        )
        gate = LogisticsNl2SqlGrayscaleGate(config=config)
        formal = _make_formal_result(query_key="total_fee")
        decision = gate.decide(formal=formal, domain="business_analysis")
        assert decision.should_grayscale is False
        assert decision.fallback_reason == "grayscale_disabled"

    def test_default_domain_behavior(self) -> None:
        """默认 domain（logistics）应保持原有行为。"""
        config = LogisticsNl2SqlGrayscaleConfig(
            enabled_types={GrayscaleQuestionType.SIMPLE_AGGREGATE},
        )
        gate = LogisticsNl2SqlGrayscaleGate(config=config)
        formal = _make_formal_result(query_key="total_fee")
        decision = gate.decide(formal=formal)  # 不传 domain，默认 logistics
        assert decision.should_grayscale is True
        assert decision.domain == "logistics"

    def test_from_env_json_config(self, monkeypatch) -> None:
        """JSON 格式环境变量应正确解析。"""
        import json
        json_config = json.dumps({"business_analysis": ["simple_aggregate"]})
        monkeypatch.setenv("NL2SQL_GRAYSCALE_CONFIG", json_config)
        config = LogisticsNl2SqlGrayscaleConfig.from_env()
        assert "business_analysis" in config.enabled_domains
        assert "simple_aggregate" in config.domain_types.get("business_analysis", set())

    def test_from_env_legacy_format(self, monkeypatch) -> None:
        """旧格式环境变量应兼容。"""
        monkeypatch.setenv("LOGISTICS_NL2SQL_GRAYSCALE_TYPES", "simple_aggregate,dimension_split")
        config = LogisticsNl2SqlGrayscaleConfig.from_env()
        assert "logistics" in config.enabled_domains
        assert "simple_aggregate" in config.enabled_types
        assert "dimension_split" in config.enabled_types

    def test_from_env_empty(self) -> None:
        """空环境变量应返回全部关闭的配置。"""
        config = LogisticsNl2SqlGrayscaleConfig.from_env()
        assert not config.enabled_types
        assert not config.enabled_domains

    def test_decide_result_includes_domain(self) -> None:
        """决策结果应包含 domain 字段。"""
        config = LogisticsNl2SqlGrayscaleConfig(
            enabled_domains={"plan_bom"},
            domain_types={"plan_bom": {GrayscaleQuestionType.SIMPLE_AGGREGATE}},
        )
        gate = LogisticsNl2SqlGrayscaleGate(config=config)
        formal = _make_formal_result(query_key="total_fee")
        decision = gate.decide(formal=formal, domain="plan_bom")
        assert decision.should_grayscale is True
        assert decision.domain == "plan_bom"
        data = decision.model_dump(mode="json")
        assert data["domain"] == "plan_bom"

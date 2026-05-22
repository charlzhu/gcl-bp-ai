"""M14：Shadow 结果对比器测试（RED — TDD 第一阶段）。

测试目标：
    LogisticsNl2SqlShadowComparator 能对比 formal QA 结果与 NL2SQL shadow 摘要的结构化差异。
"""

from __future__ import annotations

import pytest

from backend.app.domains.logistics.schemas.data_qa import (
    LogisticsDataQaPlan,
    LogisticsDataQaResult,
    LogisticsDataQaStatus,
    LogisticsDataQaTable,
)
from backend.app.domains.logistics.services.nl2sql.live_shadow_adapter import (
    LIVE_SHADOW_SUMMARY_SCHEMA_VERSION,
    LogisticsNl2SqlLiveShadowSummary,
)
from backend.app.domains.logistics.services.nl2sql.m14_shadow_comparator import (
    LogisticsNl2SqlShadowComparison,
    LogisticsNl2SqlShadowComparator,
    LogisticsNl2SqlShadowComparatorConfig,
    ShadowCompareMode,
)


def _make_formal_result(
    status_code: str = "SUCCESS",
    row_count: int = 10,
    supported: bool = True,
    needs_clarification: bool = False,
) -> LogisticsDataQaResult:
    """构造常规物流正式 QA 结果。"""
    return LogisticsDataQaResult(
        answer_summary="测试结果",
        result_table=LogisticsDataQaTable(
            columns=["col1", "col2"],
            rows=[{"col1": f"val{i}", "col2": i} for i in range(row_count)],
        ),
        query_plan=LogisticsDataQaPlan(intent="test", query_key="test_query"),
        supported=supported,
        needs_clarification=needs_clarification,
        status=LogisticsDataQaStatus(
            code=status_code,
            message="test",
            success=status_code == "SUCCESS",
        ),
    )


def _make_shadow_summary(
    status: str = "success",
    stage: str = "pipeline",
    row_count: int = 10,
    error_codes: list[str] | None = None,
    enabled: bool = True,
    duration_ms: int = 500,
) -> LogisticsNl2SqlLiveShadowSummary:
    """构造 NL2SQL shadow 摘要。"""
    return LogisticsNl2SqlLiveShadowSummary(
        schema_version=LIVE_SHADOW_SUMMARY_SCHEMA_VERSION,
        enabled=enabled,
        status=status,
        stage=stage,
        row_count=row_count,
        error_codes=error_codes or [],
        duration_ms=duration_ms,
        formal_status="SUCCESS",
    )


class TestLogisticsNl2SqlShadowComparatorInit:
    """对比器初始化测试。"""

    def test_default_config(self) -> None:
        """默认配置必须与设计文档描述一致。"""
        comparator = LogisticsNl2SqlShadowComparator()
        assert comparator.config.compare_mode == ShadowCompareMode.LENIENT
        assert comparator.config.row_count_diff_threshold == 5
        assert comparator.config.row_count_diff_ratio == 0.1


class TestLogisticsNl2SqlShadowCompareFormalStatus:
    """formal_status 对比测试。"""

    def test_status_match_success(self) -> None:
        """formal 与 shadow 状态一致时，formal_status_match 为 True。"""
        formal = _make_formal_result()
        shadow = _make_shadow_summary(status="success")
        comparison = LogisticsNl2SqlShadowComparator().compare(formal=formal, shadow=shadow)
        assert comparison.formal_status_match is True

    def test_status_mismatch(self) -> None:
        """formal SUCCESS 但 shadow error 时，formal_status_match 为 False。"""
        formal = _make_formal_result()
        shadow = _make_shadow_summary(status="error")
        comparison = LogisticsNl2SqlShadowComparator().compare(formal=formal, shadow=shadow)
        assert comparison.formal_status_match is False
        assert "shadow_status_mismatch" in comparison.mismatch_flags

    def test_shadow_disabled_should_not_mismatch(self) -> None:
        """shadow 为 disabled 时，不标记 status 不匹配（属于正常关闭状态）。"""
        formal = _make_formal_result()
        shadow = _make_shadow_summary(enabled=False, status="disabled", row_count=0)
        comparison = LogisticsNl2SqlShadowComparator().compare(formal=formal, shadow=shadow)
        assert comparison.formal_status_match is True  # disabled 不计为不匹配


class TestLogisticsNl2SqlShadowCompareRowCount:
    """行数对比测试。"""

    def test_row_count_exact_match(self) -> None:
        """formal 与 shadow 行数完全一致时，row_count_match 为 True。"""
        formal = _make_formal_result(row_count=8)
        shadow = _make_shadow_summary(row_count=8)
        comparison = LogisticsNl2SqlShadowComparator().compare(formal=formal, shadow=shadow)
        assert comparison.row_count_match is True

    def test_row_count_within_threshold(self) -> None:
        """行数差异在阈值内（diff=3 < threshold=5）时，row_count_match 为 True。"""
        formal = _make_formal_result(row_count=10)
        shadow = _make_shadow_summary(row_count=7)
        comparison = LogisticsNl2SqlShadowComparator().compare(formal=formal, shadow=shadow)
        assert comparison.row_count_match is True

    def test_row_count_exceeds_threshold(self) -> None:
        """行数差异超出阈值（diff=8 > threshold=5）时，row_count_match 为 False。"""
        formal = _make_formal_result(row_count=20)
        shadow = _make_shadow_summary(row_count=2)
        comparison = LogisticsNl2SqlShadowComparator().compare(formal=formal, shadow=shadow)
        assert comparison.row_count_match is False
        assert "row_count_mismatch" in comparison.mismatch_flags

    def test_both_empty_counts_match(self) -> None:
        """formal 与 shadow 行数均为 0 时，行数匹配。"""
        formal = _make_formal_result(row_count=0)
        shadow = _make_shadow_summary(row_count=0)
        comparison = LogisticsNl2SqlShadowComparator().compare(formal=formal, shadow=shadow)
        assert comparison.row_count_match is True

    def test_formal_no_rows_shadow_nonzero(self) -> None:
        """formal 行数=0 但 shadow>0 时，标记 mismatch。"""
        formal = _make_formal_result(row_count=0)
        shadow = _make_shadow_summary(row_count=15)
        comparison = LogisticsNl2SqlShadowComparator().compare(formal=formal, shadow=shadow)
        assert comparison.row_count_match is False


class TestLogisticsNl2SqlShadowCompareErrorCodes:
    """错误码对比测试。"""

    def test_both_no_errors(self) -> None:
        """formal 无 status 且 shadow 无 error_codes 时，error_code_match 为 True。"""
        formal = _make_formal_result()
        shadow = _make_shadow_summary(status="success")
        comparison = LogisticsNl2SqlShadowComparator().compare(formal=formal, shadow=shadow)
        assert comparison.error_code_match is True

    def test_shadow_has_disabled_code(self) -> None:
        """shadow 只有 disable code 时不计为 error 不匹配。"""
        formal = _make_formal_result()
        shadow = _make_shadow_summary(enabled=False, status="disabled", error_codes=["m10c_live_shadow_disabled"])
        comparison = LogisticsNl2SqlShadowComparator().compare(formal=formal, shadow=shadow)
        assert comparison.error_code_match is True


class TestLogisticsNl2SqlShadowCompareStrictMode:
    """严格模式测试。"""

    def test_compare_mode_affects_threshold(self) -> None:
        """STRICT 模式下行数差异容忍更严。"""
        formal = _make_formal_result(row_count=10)
        shadow = _make_shadow_summary(row_count=6)  # diff=4
        config = LogisticsNl2SqlShadowComparatorConfig(compare_mode=ShadowCompareMode.STRICT)
        comparator = LogisticsNl2SqlShadowComparator(config=config)
        comparison = comparator.compare(formal=formal, shadow=shadow)
        # STRICT: threshold=2, diff=4 > 2 → mismatch
        assert comparison.row_count_match is False


class TestLogisticsNl2SqlShadowCompareDisabledShadow:
    """shadow disabled 场景测试。"""

    def test_shadow_disabled_no_comparison(self) -> None:
        """shadow disabled 时 comparison 的 match 全为 True。"""
        formal = _make_formal_result()
        shadow = _make_shadow_summary(enabled=False, status="disabled")
        comparison = LogisticsNl2SqlShadowComparator().compare(formal=formal, shadow=shadow)
        assert comparison.formal_status_match is True
        assert comparison.row_count_match is True
        assert comparison.error_code_match is True
        assert not comparison.mismatch_flags


class TestLogisticsNl2SqlShadowComparisonModel:
    """对比结果模型测试。"""

    def test_serialization(self) -> None:
        """LogisticsNl2SqlShadowComparison 可 JSON 序列化。"""
        comparison = LogisticsNl2SqlShadowComparison(
            formal_status="SUCCESS",
            shadow_status="success",
            formal_row_count=10,
            shadow_row_count=8,
            formal_status_match=True,
            row_count_match=True,
            error_code_match=True,
            mismatch_flags=[],
        )
        data = comparison.model_dump(mode="json")
        assert isinstance(data, dict)
        assert data["formal_status"] == "SUCCESS"
        assert data["formal_row_count"] == 10

    def test_overall_match_with_mismatches(self) -> None:
        """有 mismatch_flags 时 overall_match 为 False。"""
        comparison = LogisticsNl2SqlShadowComparison(
            formal_status="SUCCESS",
            shadow_status="error",
            formal_row_count=10,
            shadow_row_count=10,
            formal_status_match=False,
            row_count_match=True,
            error_code_match=True,
            mismatch_flags=["shadow_status_mismatch"],
        )
        assert comparison.overall_match is False

    def test_overall_match_perfect(self) -> None:
        """所有字段匹配时 overall_match 为 True。"""
        comparison = LogisticsNl2SqlShadowComparison(
            formal_status="SUCCESS",
            shadow_status="success",
            formal_row_count=10,
            shadow_row_count=10,
            formal_status_match=True,
            row_count_match=True,
            error_code_match=True,
            mismatch_flags=[],
        )
        assert comparison.overall_match is True

    def test_has_mismatch_helper(self) -> None:
        """has_mismatch() 按 flag 查询。"""
        comparison = LogisticsNl2SqlShadowComparison(
            formal_status="SUCCESS",
            shadow_status="error",
            formal_row_count=10,
            shadow_row_count=10,
            formal_status_match=False,
            row_count_match=True,
            error_code_match=True,
            mismatch_flags=["shadow_status_mismatch"],
        )
        assert comparison.has_mismatch("shadow_status_mismatch") is True
        assert comparison.has_mismatch("row_count_mismatch") is False

"""M14：Shadow 告警器测试（RED — TDD 第一阶段）。

测试目标：
    LogisticsNl2SqlShadowAlerter 能根据对比结果输出结构化告警，
    并支持累计差异率统计。
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
)
from backend.app.domains.logistics.services.nl2sql.m14_shadow_alerter import (
    LogisticsNl2SqlShadowAlerter,
    LogisticsNl2SqlShadowAlerterConfig,
    LogisticsNl2SqlShadowAlertRecord,
    LogisticsNl2SqlShadowAlertStats,
)


def _make_shadow_summary(
    status: str = "success",
    row_count: int = 10,
    enabled: bool = True,
    error_codes: list[str] | None = None,
) -> LogisticsNl2SqlLiveShadowSummary:
    return LogisticsNl2SqlLiveShadowSummary(
        schema_version=LIVE_SHADOW_SUMMARY_SCHEMA_VERSION,
        enabled=enabled,
        status=status,
        stage="pipeline",
        row_count=row_count,
        error_codes=error_codes or [],
        duration_ms=500,
        formal_status="SUCCESS",
    )


def _make_comparison(
    formal_status: str = "SUCCESS",
    shadow_status: str = "success",
    formal_row_count: int = 10,
    shadow_row_count: int = 10,
    mismatch_flags: list[str] | None = None,
) -> LogisticsNl2SqlShadowComparison:
    return LogisticsNl2SqlShadowComparison(
        formal_status=formal_status,
        shadow_status=shadow_status,
        formal_row_count=formal_row_count,
        shadow_row_count=shadow_row_count,
        formal_status_match=len([f for f in (mismatch_flags or []) if f == "shadow_status_mismatch"]) == 0,
        row_count_match=len([f for f in (mismatch_flags or []) if f == "row_count_mismatch"]) == 0,
        error_code_match=len([f for f in (mismatch_flags or []) if f == "error_code_mismatch"]) == 0,
        mismatch_flags=mismatch_flags or [],
    )


class TestLogisticsNl2SqlShadowAlerterInit:
    """告警器初始化测试。"""

    def test_default_config(self) -> None:
        """默认配置必须与设计文档描述一致。"""
        alerter = LogisticsNl2SqlShadowAlerter()
        assert alerter.config.warn_on_mismatch is True
        assert alerter.config.stats_window == 1000

    def test_custom_config(self) -> None:
        """自定义配置生效。"""
        config = LogisticsNl2SqlShadowAlerterConfig(warn_on_mismatch=False, stats_window=500)
        alerter = LogisticsNl2SqlShadowAlerter(config=config)
        assert alerter.config.warn_on_mismatch is False
        assert alerter.config.stats_window == 500


class TestLogisticsNl2SqlShadowAlertNoMismatch:
    """无差异时不告警测试。"""

    def test_no_alert_on_perfect_match(self) -> None:
        """完美匹配时 alert_fired 为 False。"""
        alerter = LogisticsNl2SqlShadowAlerter()
        comparison = _make_comparison()  # 全部匹配
        result = alerter.evaluate(
            comparison=comparison,
            trace_id="trace-001",
            question="test question",
        )
        assert result.alert_fired is False
        assert result.trace_id == "trace-001"

    def test_no_alert_on_disabled_shadow(self) -> None:
        """shadow disabled 时不触发告警。"""
        alerter = LogisticsNl2SqlShadowAlerter()
        comparison = _make_comparison(
            shadow_status="disabled",
            mismatch_flags=[],
        )
        result = alerter.evaluate(
            comparison=comparison,
            trace_id="trace-002",
            question="disabled shadow",
        )
        assert result.alert_fired is False


class TestLogisticsNl2SqlShadowAlertMismatch:
    """差异触发告警测试。"""

    def test_alert_on_status_mismatch(self) -> None:
        """formal/shadow 状态不匹配时告警。"""
        alerter = LogisticsNl2SqlShadowAlerter()
        comparison = _make_comparison(
            formal_status="SUCCESS",
            shadow_status="error",
            mismatch_flags=["shadow_status_mismatch"],
        )
        result = alerter.evaluate(
            comparison=comparison,
            trace_id="trace-003",
            question="status mismatch",
        )
        assert result.alert_fired is True
        assert "shadow_status_mismatch" in result.mismatch_flags

    def test_alert_on_row_count_mismatch(self) -> None:
        """行数不匹配时告警。"""
        alerter = LogisticsNl2SqlShadowAlerter()
        comparison = _make_comparison(
            formal_row_count=100,
            shadow_row_count=5,
            mismatch_flags=["row_count_mismatch"],
        )
        result = alerter.evaluate(
            comparison=comparison,
            trace_id="trace-004",
            question="row count mismatch",
        )
        assert result.alert_fired is True
        assert result.formal_row_count == 100
        assert result.shadow_row_count == 5

    def test_alert_on_multiple_mismatches(self) -> None:
        """多个 diff flag 同时触发告警。"""
        alerter = LogisticsNl2SqlShadowAlerter()
        comparison = _make_comparison(
            formal_status="SUCCESS",
            shadow_status="error",
            formal_row_count=50,
            shadow_row_count=2,
            mismatch_flags=["shadow_status_mismatch", "row_count_mismatch"],
        )
        result = alerter.evaluate(
            comparison=comparison,
            trace_id="trace-005",
            question="multiple mismatches",
        )
        assert result.alert_fired is True
        assert len(result.mismatch_flags) == 2
        assert "shadow_status_mismatch" in result.mismatch_flags
        assert "row_count_mismatch" in result.mismatch_flags

    def test_warn_on_mismatch_disabled_no_alert(self) -> None:
        """warn_on_mismatch=False 时不触发告警。"""
        config = LogisticsNl2SqlShadowAlerterConfig(warn_on_mismatch=False)
        alerter = LogisticsNl2SqlShadowAlerter(config=config)
        comparison = _make_comparison(
            mismatch_flags=["shadow_status_mismatch"],
        )
        result = alerter.evaluate(
            comparison=comparison,
            trace_id="trace-006",
            question="suppressed alert",
        )
        assert result.alert_fired is False


class TestLogisticsNl2SqlShadowAlerterStats:
    """累计统计测试。"""

    def test_stats_after_single_eval(self) -> None:
        """单次评估后统计应正确。"""
        alerter = LogisticsNl2SqlShadowAlerter()
        comparison = _make_comparison(mismatch_flags=[])
        alerter.evaluate(comparison=comparison, trace_id="t1", question="q1")
        stats = alerter.get_stats()
        assert stats.total_shadow == 1
        assert stats.diff_count == 0
        assert stats.diff_ratio == 0.0

    def test_stats_after_one_diff(self) -> None:
        """一次 diff 后 diff_count 应为 1。"""
        alerter = LogisticsNl2SqlShadowAlerter()
        match = _make_comparison(mismatch_flags=[])
        diff = _make_comparison(mismatch_flags=["row_count_mismatch"])
        alerter.evaluate(comparison=match, trace_id="t1", question="q1")
        alerter.evaluate(comparison=diff, trace_id="t2", question="q2")
        stats = alerter.get_stats()
        assert stats.total_shadow == 2
        assert stats.diff_count == 1
        assert stats.diff_ratio == 0.5

    def test_stats_window_limits(self) -> None:
        """stats_window 限制统计窗口内的数据量。"""
        config = LogisticsNl2SqlShadowAlerterConfig(stats_window=3)
        alerter = LogisticsNl2SqlShadowAlerter(config=config)
        for i in range(5):
            comparison = _make_comparison(
                mismatch_flags=["shadow_status_mismatch"] if i % 2 == 0 else [],
                shadow_status="error" if i % 2 == 0 else "success",
            )
            alerter.evaluate(
                comparison=comparison,
                trace_id=f"t{i}",
                question=f"q{i}",
            )
        stats = alerter.get_stats()
        assert stats.total_shadow == 3  # 只有最近 3 条
        # 窗口保留索引 2,3,4（最近3条），其中 2 和 4 是偶数索引(i%2==0)→diff
        # 所以 diff_count 应为 2
        assert stats.diff_count == 2

    def test_stats_report_format(self) -> None:
        """统计报表可序列化为 JSON。"""
        alerter = LogisticsNl2SqlShadowAlerter()
        for i in range(10):
            diff = i % 3 == 0
            comparison = _make_comparison(
                mismatch_flags=["row_count_mismatch"] if diff else [],
                formal_row_count=10 if not diff else 50,
                shadow_row_count=10 if not diff else 2,
            )
            alerter.evaluate(
                comparison=comparison,
                trace_id=f"t{i}",
                question=f"q{i}",
            )
        stats = alerter.get_stats()
        data = stats.model_dump(mode="json")
        assert data["total_shadow"] == 10
        assert data["diff_count"] == 4  # 0, 3, 6, 9 是 3 的倍数
        assert abs(data["diff_ratio"] - 0.4) < 0.001

    def test_reset_stats(self) -> None:
        """重置统计后 total_shadow 为 0。"""
        alerter = LogisticsNl2SqlShadowAlerter()
        for _ in range(5):
            alerter.evaluate(comparison=_make_comparison(), trace_id="t", question="q")
        alerter.reset_stats()
        stats = alerter.get_stats()
        assert stats.total_shadow == 0
        assert stats.diff_count == 0
        assert stats.diff_ratio == 0.0


class TestLogisticsNl2SqlShadowAlertRecord:
    """告警记录模型测试。"""

    def test_serialization(self) -> None:
        """告警记录可 JSON 序列化。"""
        record = LogisticsNl2SqlShadowAlertRecord(
            alert_fired=True,
            trace_id="trace-test",
            question="test question",
            mismatch_flags=["shadow_status_mismatch"],
            formal_status="SUCCESS",
            shadow_status="error",
            formal_row_count=10,
            shadow_row_count=10,
        )
        data = record.model_dump(mode="json")
        assert isinstance(data, dict)
        assert data["trace_id"] == "trace-test"
        assert data["alert_fired"] is True

    def test_question_truncation(self) -> None:
        """question 超长时应截断到前 200 字符。"""
        long_q = "x" * 500
        record = LogisticsNl2SqlShadowAlertRecord(
            alert_fired=True,
            trace_id="trace-trunc",
            question=long_q,
            mismatch_flags=[],
            formal_status="SUCCESS",
            shadow_status="success",
            formal_row_count=10,
            shadow_row_count=10,
        )
        assert len(record.question) <= 200

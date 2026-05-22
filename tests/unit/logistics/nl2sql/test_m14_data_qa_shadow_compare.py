"""M14：data_qa_service 串联工具函数测试。

测试目标：
    compare_nl2sql_shadow_and_attach 能正确对比 formal QA 结果与 shadow 摘要，
    并把 comparison 和 alert 附加到 response_meta。
"""

from __future__ import annotations

from unittest.mock import MagicMock

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
from backend.app.domains.logistics.services.nl2sql.m14_data_qa_shadow_compare import (
    compare_nl2sql_shadow_and_attach,
    get_global_shadow_alerter,
)


def _make_formal_result(row_count: int = 10, status_code: str = "SUCCESS") -> LogisticsDataQaResult:
    return LogisticsDataQaResult(
        answer_summary="测试结果",
        result_table=LogisticsDataQaTable(
            columns=["c1"],
            rows=[{"c1": i} for i in range(row_count)],
        ),
        query_plan=LogisticsDataQaPlan(intent="test", query_key="test_qk"),
        status=LogisticsDataQaStatus(code=status_code, message="test", success=True),
    )


def _make_shadow_dict(
    status: str = "success",
    enabled: bool = True,
    row_count: int = 10,
    formal_status: str = "SUCCESS",
) -> dict:
    summary = LogisticsNl2SqlLiveShadowSummary(
        schema_version=LIVE_SHADOW_SUMMARY_SCHEMA_VERSION,
        enabled=enabled,
        status=status,
        stage="pipeline",
        row_count=row_count,
        formal_status=formal_status,
        duration_ms=500,
    )
    return summary.model_dump(mode="json")


class TestCompareNl2SqlShadowAndAttach:
    """compare_nl2sql_shadow_and_attach 工具函数测试。"""

    def test_shadow_summary_none_skips(self) -> None:
        """nl2sql_shadow_summary_dict 为 None 时不修改 response_meta。"""
        meta: dict = {}
        compare_nl2sql_shadow_and_attach(
            result=_make_formal_result(),
            nl2sql_shadow_summary_dict=None,
            trace_id="t1",
            question="q1",
            response_meta=meta,
        )
        assert "nl2sql_live_shadow_comparison" not in meta

    def test_shadow_disabled_skips_comparison(self) -> None:
        """shadow disabled 时不对比，不附加 comparison。"""
        meta: dict = {}
        compare_nl2sql_shadow_and_attach(
            result=_make_formal_result(),
            nl2sql_shadow_summary_dict=_make_shadow_dict(enabled=False, status="disabled"),
            trace_id="t2",
            question="q2",
            response_meta=meta,
        )
        assert "nl2sql_live_shadow_comparison" not in meta

    def test_perfect_match_attaches_comparison(self) -> None:
        """完美匹配时 comparison 附加到 response_meta。"""
        meta: dict = {}
        compare_nl2sql_shadow_and_attach(
            result=_make_formal_result(row_count=10),
            nl2sql_shadow_summary_dict=_make_shadow_dict(row_count=10),
            trace_id="t3",
            question="q3",
            response_meta=meta,
        )
        comp = meta.get("nl2sql_live_shadow_comparison")
        assert comp is not None
        assert comp["formal_status_match"] is True
        assert comp["row_count_match"] is True
        assert comp["mismatch_flags"] == []

    def test_mismatch_attaches_flags(self) -> None:
        """不匹配时 comparison 包含 mismatch_flags。"""
        meta: dict = {}
        compare_nl2sql_shadow_and_attach(
            result=_make_formal_result(row_count=50),
            nl2sql_shadow_summary_dict=_make_shadow_dict(row_count=1, status="error"),
            trace_id="t4",
            question="q4",
            response_meta=meta,
        )
        comp = meta.get("nl2sql_live_shadow_comparison")
        assert comp is not None
        assert len(comp["mismatch_flags"]) >= 1

    def test_same_alerter_updates_stats(self) -> None:
        """使用全局 alerter 时，多次调用逐步累计统计。"""
        alerter = get_global_shadow_alerter()
        alerter.reset_stats()  # 先重置确保测试独立

        # 第一次：完美匹配
        compare_nl2sql_shadow_and_attach(
            result=_make_formal_result(row_count=5),
            nl2sql_shadow_summary_dict=_make_shadow_dict(row_count=5),
            trace_id="t-a",
            question="qa",
            response_meta={},
        )
        # 第二次：不匹配
        compare_nl2sql_shadow_and_attach(
            result=_make_formal_result(row_count=50),
            nl2sql_shadow_summary_dict=_make_shadow_dict(row_count=1, status="error"),
            trace_id="t-b",
            question="qb",
            response_meta={},
        )
        stats = alerter.get_stats()
        assert stats.total_shadow >= 2
        assert stats.diff_count >= 1

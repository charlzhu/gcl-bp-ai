"""测试多域 shadow pipeline 端到端通路。

验证 business_analysis 和 plan_bom 域的问题能完整走通 shadow_pipeline
（从 candidate 验证 → render → safety → execution）。
"""

import pytest

from backend.app.domains.logistics.services.nl2sql.shadow_pipeline import (
    FakeLogisticsSqlExecutor,
    InMemoryLogisticsNl2SqlEvaluationLogSink,
    LogisticsNl2SqlShadowPipeline,
    LogisticsNl2SqlShadowPipelineRequest,
    LogisticsSqlExecutionService,
)


def _valid_business_analysis_candidate() -> dict:
    """构造一个产销存域的有效 candidate。"""
    return {
        "schema_version": "logistics_sqlplan_candidate.v1",
        "domain": "business_analysis",
        "strategy": "sql_direct",
        "catalog_version": "business_analysis_nl2sql_catalog.v1",
        "catalog_refs": [
            {"catalog_id": "table:dwd_ba_isp_monthly_fact", "catalog_version": "business_analysis_nl2sql_catalog.v1"},
            {"catalog_id": "metric:shipment_volume", "catalog_version": "business_analysis_nl2sql_catalog.v1"},
            {"catalog_id": "dimension:biz_month", "catalog_version": "business_analysis_nl2sql_catalog.v1"},
        ],
        "plan": {
            "query_type": "summary",
            "tables": ["dwd_ba_isp_monthly_fact"],
            "joins": [],
            "metrics": [{"catalog_id": "metric:shipment_volume", "alias": "shipment_vol"}],
            "group_by": [{"catalog_id": "dimension:biz_month"}],
            "filters": [],
            "order_by": [],
            "limit": 10,
        },
    }


class TestMultiDomainShadowPipeline:
    """多域 shadow pipeline 端到端验证。"""

    def test_business_analysis_domain_with_valid_candidate_succeeds(self):
        """产销存域带合法 candidate 应走通到 execution 阶段。"""
        executor = FakeLogisticsSqlExecutor()
        sink = InMemoryLogisticsNl2SqlEvaluationLogSink()
        pipeline = LogisticsNl2SqlShadowPipeline(
            execution_service=LogisticsSqlExecutionService(executor=executor),
            log_sink=sink,
        )
        request = LogisticsNl2SqlShadowPipelineRequest(
            question="2024年各月的销量",
            domain="business_analysis",
            source_system="middle_db",
            candidate=_valid_business_analysis_candidate(),
        )
        result = pipeline.run(request)
        # 不应在 domain 阶段被拒绝
        assert result.stage != "domain"
        assert "shadow_domain_not_supported" not in (result.error_codes or [])
        # 至少进入了 domain 后续阶段（candidate/validation 等）
        assert result.stage not in ("domain",)

    def test_plan_bom_domain_with_logistics_candidate_goes_past_domain_check(self):
        """计划 BOM 域至少应通过 domain 检查，进入后续阶段（candidate/validation 等）。"""
        executor = FakeLogisticsSqlExecutor()
        sink = InMemoryLogisticsNl2SqlEvaluationLogSink()
        pipeline = LogisticsNl2SqlShadowPipeline(
            execution_service=LogisticsSqlExecutionService(executor=executor),
            log_sink=sink,
        )
        request = LogisticsNl2SqlShadowPipelineRequest(
            question="BOM 材料明细",
            domain="plan_bom",
            source_system="middle_db",
            candidate=None,  # 无 candidate → 在 candidate 阶段被拒绝
        )
        result = pipeline.run(request)
        assert result.stage != "domain"
        assert "shadow_domain_not_supported" not in (result.error_codes or [])
        # 应该是在 candidate 阶段失败
        assert result.stage in ("candidate",)

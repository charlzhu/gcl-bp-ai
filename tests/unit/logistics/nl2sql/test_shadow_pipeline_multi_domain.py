"""测试 M10-B shadow pipeline 多域支持。

TDD: RED → GREEN 验证非 logistics 域不再被硬编码拒绝。
"""

import pytest

from backend.app.domains.logistics.services.nl2sql.domain_registry import (
    DomainCatalogRegistration,
    Nl2SqlDomainRegistry,
    register_business_analysis_domain,
    register_plan_bom_domain,
)
from backend.app.domains.logistics.services.nl2sql.shadow_pipeline import (
    LogisticsNl2SqlShadowPipeline,
    LogisticsNl2SqlShadowPipelineRequest,
)


class TestShadowPipelineMultiDomain:
    """shadow pipeline 多域支持测试。"""

    def test_business_analysis_domain_not_rejected(self):
        """业务分析域问题不再被 domain != 'logistics' 拒绝。"""
        pipeline = LogisticsNl2SqlShadowPipeline()
        request = LogisticsNl2SqlShadowPipelineRequest(
            question="2024年各月的产量是多少",
            domain="business_analysis",
            source_system="middle_db",
            candidate=None,  # 无 candidate → 在 candidate 检查阶段失败，而非 domain 阶段
        )
        result = pipeline.run(request)
        # 不应在 domain 阶段被拒绝
        assert result.stage != "domain", "business_analysis domain should not be rejected at domain stage"
        assert "shadow_domain_not_supported" not in (result.error_codes or [])

    def test_plan_bom_domain_not_rejected(self):
        """计划 BOM 域问题不再被 domain != 'logistics' 拒绝。"""
        pipeline = LogisticsNl2SqlShadowPipeline()
        request = LogisticsNl2SqlShadowPipelineRequest(
            question="评审号XXX的材料明细",
            domain="plan_bom",
            source_system="middle_db",
            candidate=None,
        )
        result = pipeline.run(request)
        assert result.stage != "domain", "plan_bom domain should not be rejected at domain stage"
        assert "shadow_domain_not_supported" not in (result.error_codes or [])

    def test_logistics_domain_still_accepted(self):
        """物流域继续保持正常。"""
        pipeline = LogisticsNl2SqlShadowPipeline()
        request = LogisticsNl2SqlShadowPipelineRequest(
            question="2024年物流公司运价排名",
            domain="logistics",
            source_system="middle_db",
            candidate=None,
        )
        result = pipeline.run(request)
        assert result.stage != "domain"
        assert "shadow_domain_not_supported" not in (result.error_codes or [])

    def test_unknown_domain_still_rejected(self):
        """未知未注册域仍然被拒绝。"""
        pipeline = LogisticsNl2SqlShadowPipeline()
        request = LogisticsNl2SqlShadowPipelineRequest(
            question="未知域问题",
            domain="unknown_domain",
            source_system="middle_db",
            candidate=None,
        )
        result = pipeline.run(request)
        # 未知域应该在 domain 阶段拒绝
        assert result.stage == "domain" or "shadow_domain_not_supported" in (result.error_codes or [])

    def test_registry_has_all_three_domains(self):
        """域注册表包含全部三个业务域。"""
        registry = Nl2SqlDomainRegistry()
        register_business_analysis_domain(registry)
        register_plan_bom_domain(registry)
        # domains 是 dict 属性，不是方法
        domain_list = list(registry._domains.keys())
        assert "business_analysis" in domain_list
        assert "plan_bom" in domain_list

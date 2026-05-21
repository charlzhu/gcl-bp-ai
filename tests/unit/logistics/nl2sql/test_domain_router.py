"""DomainRouter + DomainRegistry 单元测试。"""

from __future__ import annotations

from backend.app.domains.logistics.services.nl2sql.domain_registry import (
    DomainCatalogRegistration,
    Nl2SqlDomainRegistry,
)
from backend.app.domains.logistics.services.nl2sql.domain_router import (
    Nl2SqlDomainRoute,
    Nl2SqlDomainRouter,
)


class TestNl2SqlDomainRegistry:
    """域注册表测试。"""

    def test_empty_registry_identify_returns_none(self):
        """空注册表应返回 None。"""
        registry = Nl2SqlDomainRegistry()
        assert registry.identify("物流发运明细") is None

    def test_register_and_identify(self):
        """注册后应能通过关键词识别。"""
        registry = Nl2SqlDomainRegistry()
        registry.register(DomainCatalogRegistration(
            domain="logistics",
            priority=10,
            keywords=["物流", "发运", "运输"],
        ))
        result = registry.identify("2023年物流发运明细")
        assert result is not None
        assert result[0] == "logistics"

    def test_priority_ordering(self):
        """高优先级域应先于低优先级域匹配。"""
        registry = Nl2SqlDomainRegistry()
        registry.register(DomainCatalogRegistration(
            domain="plan_bom",
            priority=5,
            keywords=["物料", "BOM"],
        ))
        registry.register(DomainCatalogRegistration(
            domain="material_management",
            priority=10,
            keywords=["物料", "库存"],
        ))
        # "物料匹配"包含"物料"，plan_bom 优先级 5 < material_management 优先级 10
        result = registry.identify("物料匹配查询")
        assert result is not None
        assert result[0] == "plan_bom"

    def test_identify_no_match(self):
        """无关键词匹配应返回 None。"""
        registry = Nl2SqlDomainRegistry()
        registry.register(DomainCatalogRegistration(
            domain="logistics",
            priority=10,
            keywords=["物流"],
        ))
        assert registry.identify("BOM 版本变更") is None

    def test_identify_empty_text(self):
        """空文本应返回 None。"""
        registry = Nl2SqlDomainRegistry()
        registry.register(DomainCatalogRegistration(
            domain="logistics",
            priority=10,
            keywords=["物流"],
        ))
        assert registry.identify("") is None
        assert registry.identify(None) is None  # type: ignore[arg-type]

    def test_get_catalog_no_loader(self):
        """未设置 catalog_loader 应返回 None。"""
        registry = Nl2SqlDomainRegistry()
        registry.register(DomainCatalogRegistration(
            domain="logistics",
            priority=10,
            keywords=["物流"],
        ))
        assert registry.get_catalog("logistics") is None

    def test_get_registration_nonexistent(self):
        """不存在的域应返回 None。"""
        registry = Nl2SqlDomainRegistry()
        assert registry.get_registration("nonexistent") is None

    def test_domains_property(self):
        """domains 属性应返回已注册域的副本。"""
        registry = Nl2SqlDomainRegistry()
        registry.register(DomainCatalogRegistration(
            domain="logistics",
            priority=10,
            keywords=["物流"],
        ))
        assert "logistics" in registry.domains
        assert len(registry.domains) == 1


class TestNl2SqlDomainRouter:
    """多域路由基类测试。"""

    def test_default_router_has_logistics_registry(self):
        """默认构造的 router 应自动注册物流域，物流问题 should_process=True。"""
        router = Nl2SqlDomainRouter()
        route = router.route("物流发运明细")
        assert isinstance(route, Nl2SqlDomainRoute)
        assert route.should_process is True
        assert route.domain == "logistics"

    def test_router_with_logistics_registry(self):
        """注册物流域后，应正确路由物流问题。"""
        registry = Nl2SqlDomainRegistry()
        registry.register(DomainCatalogRegistration(
            domain="logistics",
            priority=10,
            keywords=["物流", "发运", "运输"],
        ))
        router = Nl2SqlDomainRouter(registry)
        route = router.route("2023年物流发运明细")
        assert route.should_process is True
        assert route.domain == "logistics"
        assert route.reason_code is not None

    def test_router_returns_correct_reason_code(self):
        """路由成功时 reason_code 应包含域信息。"""
        registry = Nl2SqlDomainRegistry()
        registry.register(DomainCatalogRegistration(
            domain="logistics",
            priority=10,
            keywords=["物流"],
        ))
        router = Nl2SqlDomainRouter(registry)
        route = router.route("物流查询")
        assert route.reason_code == "domain_identified::logistics"

    def test_router_unknown_domain(self):
        """未识别域时 domain 应为 unknown。"""
        router = Nl2SqlDomainRouter()
        route = router.route("今天天气怎么样")
        assert route.should_process is False
        assert route.domain == "unknown"
        assert route.reason_code == "no_domain_identified"

    def test_business_analysis_domain_identified(self):
        """经营分析的问题应被路由到 business_analysis 域。"""
        router = Nl2SqlDomainRouter()
        route = router.route("2023年产销存分析报表")
        assert route.should_process is True
        assert route.domain == "business_analysis"

    def test_plan_bom_domain_identified(self):
        """BOM 类问题应被路由到 plan_bom 域。"""
        router = Nl2SqlDomainRouter()
        route = router.route("BOM 版型搭配查询")
        assert route.should_process is True
        assert route.domain == "plan_bom"

    def test_plan_bom_power_domain_identified(self):
        """功率测算类问题应被路由到 plan_bom 域。"""
        router = Nl2SqlDomainRouter()
        route = router.route("功率档位分布查询")
        assert route.should_process is True
        assert route.domain == "plan_bom"

    def test_router_with_rewrite_result_object(self):
        """兼容 LogisticsNl2SqlQueryRewriteResult 对象。"""
        registry = Nl2SqlDomainRegistry()
        registry.register(DomainCatalogRegistration(
            domain="logistics",
            priority=10,
            keywords=["物流"],
        ))
        router = Nl2SqlDomainRouter(registry)

        # 模拟 rewrite result 对象
        class MockRewriteResult:
            normalized_question = "物流发运明细"

        route = router.route(MockRewriteResult())
        assert route.should_process is True
        assert route.domain == "logistics"

    def test_router_route_model_defaults(self):
        """Nl2SqlDomainRoute 默认值验证。"""
        route = Nl2SqlDomainRoute(should_process=True, domain="logistics")
        assert route.source_system == "middle_db"
        assert route.mode == "shadow"
        assert route.reason_code is None

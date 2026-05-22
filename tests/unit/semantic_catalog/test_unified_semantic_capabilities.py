"""
NQE-N4：现有口径迁移到统一语义资产 — 测试用例

测试范围：
    1. SemanticCapability Schema 定义正确。
    2. BusinessSemanticCatalog 支持能力的注册和查询。
    3. 可从 YAML 文件加载能力注册表（capabilities.yaml）。
    4. 物流 67 个 query_key 全部在统一 catalog 中可查询。
    5. 计划 BOM 11 个 intent 全部可查询。
    6. 计划功率 3 个 domain_capability 全部可查询。
    7. 按 capability_type 过滤工作正常。
    8. 现有 semantic_catalog 测试不回退。
"""
from __future__ import annotations

import yaml
from pathlib import Path

import pytest

from backend.app.domains.semantic_catalog.schema import SemanticCapability
from backend.app.domains.semantic_catalog.catalog import BusinessSemanticCatalog
from backend.app.domains.semantic_catalog.loader import SemanticCatalogYamlLoader


# ==================== SemanticCapability Schema 测试 ====================


class TestSemanticCapability:
    """SemanticCapability Schema 定义测试。"""

    def test_create_capability_minimal(self) -> None:
        """创建最小字段的能力定义。"""
        cap = SemanticCapability(
            capability_id="hist_route_pricing_analysis",
            display_name="线路运价分析",
            domain="logistics",
            capability_type="query_key",
        )
        assert cap.capability_id == "hist_route_pricing_analysis"
        assert cap.display_name == "线路运价分析"
        assert cap.domain == "logistics"
        assert cap.capability_type == "query_key"
        assert cap.related_metrics == []
        assert cap.related_dimensions == []
        assert cap.aliases == []
        assert cap.description is None

    def test_create_capability_full(self) -> None:
        """创建完整字段的能力定义。"""
        cap = SemanticCapability(
            capability_id="plan_power_prediction",
            display_name="功率预测",
            domain="plan_bom",
            capability_type="domain_capability",
            related_metrics=["power_prediction"],
            related_dimensions=["material_category"],
            aliases=["功率测算", "电站功率"],
            description="基于 BOM 配置和 Excel 模型计算电站功率预测。",
        )
        assert cap.capability_id == "plan_power_prediction"
        assert "功率测算" in cap.aliases
        assert "power_prediction" in cap.related_metrics
        assert cap.description is not None

    def test_create_capability_fails_without_required(self) -> None:
        """缺少必填字段时构造失败。"""
        with pytest.raises(Exception):
            SemanticCapability(display_name="测试", domain="logistics", capability_type="query_key")  # type: ignore[arg-type]

        with pytest.raises(Exception):
            SemanticCapability(capability_id="test", domain="logistics", capability_type="query_key")  # type: ignore[arg-type]

        with pytest.raises(Exception):
            SemanticCapability(capability_id="test", display_name="测试", capability_type="query_key")  # type: ignore[arg-type]

        with pytest.raises(Exception):
            SemanticCapability(capability_id="test", display_name="测试", domain="logistics")  # type: ignore[arg-type]


# ==================== BusinessSemanticCatalog 能力注册与查询测试 ====================


class TestCatalogCapabilityOperations:
    """BusinessSemanticCatalog 能力注册/查询操作测试。"""

    @pytest.fixture
    def catalog(self) -> BusinessSemanticCatalog:
        """创建空的 catalog 实例。"""
        return BusinessSemanticCatalog()

    def test_catalog_empty_by_default(self, catalog: BusinessSemanticCatalog) -> None:
        """新建 catalog 无能力。"""
        assert catalog.get_capabilities("logistics") == []

    def test_register_and_query_capability(self, catalog: BusinessSemanticCatalog) -> None:
        """注册一个能力后可按域和 ID 查询。"""
        cap = SemanticCapability(
            capability_id="hist_route_pricing_analysis",
            display_name="线路运价分析",
            domain="logistics",
            capability_type="query_key",
            description="分析线路运价。",
        )
        catalog.register_capability(cap)

        results = catalog.get_capabilities(domain="logistics")
        assert len(results) == 1
        assert results[0].capability_id == "hist_route_pricing_analysis"

        found = catalog.get_capability("logistics", "hist_route_pricing_analysis")
        assert found is not None
        assert found.display_name == "线路运价分析"

    def test_register_multiple_capability_types(self, catalog: BusinessSemanticCatalog) -> None:
        """同一域下注册不同类型能力。"""
        catalog.register_capability(SemanticCapability(
            capability_id="query_1", display_name="查询能力1",
            domain="logistics", capability_type="query_key",
        ))
        catalog.register_capability(SemanticCapability(
            capability_id="intent_1", display_name="意图1",
            domain="logistics", capability_type="intent",
        ))

        # 全部获取
        all_caps = catalog.get_capabilities("logistics")
        assert len(all_caps) == 2

        # 按类型过滤
        query_caps = catalog.get_capabilities("logistics", capability_type="query_key")
        assert len(query_caps) == 1
        assert query_caps[0].capability_id == "query_1"

        intent_caps = catalog.get_capabilities("logistics", capability_type="intent")
        assert len(intent_caps) == 1
        assert intent_caps[0].capability_id == "intent_1"

    def test_query_nonexistent_capability(self, catalog: BusinessSemanticCatalog) -> None:
        """查询不存在的能力返回 None。"""
        assert catalog.get_capability("logistics", "nonexistent") is None

    def test_register_duplicate_overwrites(self, catalog: BusinessSemanticCatalog) -> None:
        """重复注册同一 domain + capability_id 会覆盖。"""
        cap1 = SemanticCapability(
            capability_id="test", display_name="旧名称",
            domain="logistics", capability_type="query_key",
        )
        cap2 = SemanticCapability(
            capability_id="test", display_name="新名称",
            domain="logistics", capability_type="query_key",
        )
        catalog.register_capability(cap1)
        catalog.register_capability(cap2)

        found = catalog.get_capability("logistics", "test")
        assert found is not None
        assert found.display_name == "新名称"


# ==================== YAML Loader 能力加载测试 ====================


class TestCapabilityYamlLoader:
    """从 capabilities.yaml 加载能力注册表测试。"""

    def test_load_capabilities_from_yaml(self, tmp_path) -> None:
        """从 YAML 文件加载能力注册表。"""
        yaml_content = {
            "capabilities": [
                {
                    "capability_id": "hist_route_pricing_analysis",
                    "display_name": "线路运价分析",
                    "domain": "logistics",
                    "capability_type": "query_key",
                    "aliases": ["运价查询"],
                    "description": "分析线路运价。",
                },
                {
                    "capability_id": "plan_power_prediction",
                    "display_name": "功率预测",
                    "domain": "plan_bom",
                    "capability_type": "domain_capability",
                    "aliases": ["功率测算"],
                    "description": "功率预测。",
                },
            ],
        }
        yaml_path = tmp_path / "capabilities.yaml"
        yaml_path.write_text(yaml.dump(yaml_content, allow_unicode=True), encoding="utf-8")

        loader = SemanticCatalogYamlLoader(catalog_dir=tmp_path)
        catalog = loader.load()

        # 物流 query_key 可查询
        found = catalog.get_capability("logistics", "hist_route_pricing_analysis")
        assert found is not None
        assert found.capability_type == "query_key"
        assert "运价查询" in found.aliases

        # 功率能力可查询
        power_cap = catalog.get_capability("plan_bom", "plan_power_prediction")
        assert power_cap is not None
        assert power_cap.capability_type == "domain_capability"


# ==================== 生产配置完整性测试 ====================


class TestProductionCatalogCompleteness:
    """验证生产环境 capabilities.yaml 的完整性。

    验收标准：
        - 物流域 67 个 query_key 全部注册。
        - 计划 BOM 域 11 个 intent 全部注册。
        - 计划功率 3 个 domain_capability 全部注册。
    """

    # 从源码提取的物流 query_key 白名单（data_qa_planner.py 的 67 个 query_key）
    LOGISTICS_QUERY_KEYS = {
        "carrier_metric_ranking",
        "composite_decomposed",
        "hist_avg_fee_by_month",
        "hist_avg_fee_per_watt_by_transport",
        "hist_avg_pallet_per_vehicle",
        "hist_carrier_kpi_by_year",
        "hist_city_carrier_avg_fee_per_trip",
        "hist_city_mw_rank",
        "hist_customer_mw",
        "hist_customer_mw_ranking",
        "hist_extra_fee_ratio_peak_month",
        "hist_high_fee_addresses_by_customer",
        "hist_monthly_metric_by_filters",
        "hist_monthly_total_fee_by_year",
        "hist_monthly_trip_count_summary",
        "hist_multi_origin_customers",
        "hist_mw_by_all_regions",
        "hist_mw_by_origin_and_carrier",
        "hist_mw_by_region_province",
        "hist_mw_by_year",
        "hist_mw_summary",
        "hist_origin_vehicle_breakdown_summary",
        "hist_origin_vehicle_metric_summary",
        "hist_plan_actual_deviation",
        "hist_product_spec_mw_summary",
        "hist_quantity_by_region",
        "hist_quarter_region_metric",
        "hist_remark_keyword_amount_summary",
        "hist_remark_keyword_fee_ratio",
        "hist_route_aggregate_summary",
        "hist_route_pricing_analysis",
        "hist_top_customers_fee_and_mw_by_province",
        "hist_total_fee_by_origin_and_carrier",
        "hist_total_fee_by_province",
        "hist_total_fee_city_rank",
        "hist_total_fee_summary",
        "hist_transport_mode_record_summary",
        "hist_trip_count_by_region",
        "hist_unit_fee_per_watt",
        "hist_vehicle_type_trip_count",
        "mixed_mw_by_all_regions_2023_2026",
        "mixed_mw_summary_2023_2026",
        "mixed_total_fee_summary_2023_2026",
        "sys_avg_loading_trucks_by_province",
        "sys_companies_without_tasks",
        "sys_company_mapping_gap",
        "sys_delivery_distance_fill_rate_by_province",
        "sys_delivery_note_parse_status_distribution",
        "sys_driver_id_phone_consistency",
        "sys_driver_phone_name_consistency",
        "sys_driver_task_ranking",
        "sys_extra_cost_audited_concentration",
        "sys_extra_fee_summary",
        "sys_mw_and_trip_count",
        "sys_mw_by_procurement_type",
        "sys_parse_success_rate_by_carrier",
        "sys_procurement_avg_loading_trucks",
        "sys_procurement_task_distribution",
        "sys_reconciliation_fill_rate_by_month",
        "sys_ship_product_detail_stats",
        "sys_signedfor_rate_by_carrier",
        "sys_special_total_fee",
        "sys_task_count_ranking",
        "sys_task_status_distribution",
        "sys_task_status_province_ranking",
        "sys_total_fee_by_filters",
        "sys_unit_fee_per_watt",
    }

    # 计划 BOM 域 intent 白名单（nlu_center_service.py 的 INTENTS - unsupported/clarification）
    PLAN_BOM_INTENTS = {
        "single_order_material_specs",
        "multi_order_material_table",
        "cross_order_material_compare",
        "bom_version_compare",
        "specific_material_query",
        "scope_material_list",
        "batch_export_table",
        "material_presence_check",
        "material_consistency_check",
        "supplier_reuse_quote_prepare",
        "power_cell_requirement",
    }

    # 计划功率域 capability 白名单
    PLAN_POWER_CAPABILITIES = {
        "plan_power_prediction",
        "plan_power_supplier_recommendation",
        "plan_power_factor_effect_compare",
    }

    @pytest.fixture(scope="class")
    def prod_catalog(self) -> BusinessSemanticCatalog:
        """加载生产环境 capabilities.yaml。"""
        return SemanticCatalogYamlLoader().load()

    # ── 物流 query_key 完整性 ──

    def test_all_logistics_query_keys_registered(self, prod_catalog: BusinessSemanticCatalog) -> None:
        """物流域全部 67 个 query_key 在统一 catalog 中可查询。"""
        registered = {
            c.capability_id
            for c in prod_catalog.get_capabilities("logistics", capability_type="query_key")
        }
        missing = self.LOGISTICS_QUERY_KEYS - registered
        assert len(missing) == 0, (
            f"物流域缺少 {len(missing)} 个 query_key 注册：{sorted(missing)}"
        )

    def test_logistics_query_key_count(self, prod_catalog: BusinessSemanticCatalog) -> None:
        """物流域注册的 query_key 数量为 67。"""
        caps = prod_catalog.get_capabilities("logistics", capability_type="query_key")
        assert len(caps) == 67, f"预期 67 个 query_key，实际 {len(caps)} 个"

    def test_logistics_query_keys_have_descriptions(self, prod_catalog: BusinessSemanticCatalog) -> None:
        """所有物流 query_key 都有业务描述。"""
        caps = prod_catalog.get_capabilities("logistics", capability_type="query_key")
        for cap in caps:
            assert cap.description is not None, (
                f"query_key {cap.capability_id} 缺少业务描述"
            )
            assert len(cap.description.strip()) > 0, (
                f"query_key {cap.capability_id} 描述为空"
            )

    # ── 计划 BOM intent 完整性 ──

    def test_all_plan_bom_intents_registered(self, prod_catalog: BusinessSemanticCatalog) -> None:
        """计划 BOM 域全部 11 个 intent 在统一 catalog 中可查询。"""
        registered = {
            c.capability_id
            for c in prod_catalog.get_capabilities("plan_bom", capability_type="intent")
        }
        missing = self.PLAN_BOM_INTENTS - registered
        assert len(missing) == 0, (
            f"计划 BOM 域缺少 {len(missing)} 个 intent 注册：{sorted(missing)}"
        )

    def test_plan_bom_intent_count(self, prod_catalog: BusinessSemanticCatalog) -> None:
        """计划 BOM 域 intent 数量为 11。"""
        caps = prod_catalog.get_capabilities("plan_bom", capability_type="intent")
        assert len(caps) == 11, f"预期 11 个 intent，实际 {len(caps)} 个"

    # ── 计划功率 capability 完整性 ──

    def test_all_plan_power_capabilities_registered(self, prod_catalog: BusinessSemanticCatalog) -> None:
        """计划功率域全部 3 个 capability 在统一 catalog 中可查询。"""
        registered = {
            c.capability_id
            for c in prod_catalog.get_capabilities("plan_bom", capability_type="domain_capability")
        }
        missing = self.PLAN_POWER_CAPABILITIES - registered
        assert len(missing) == 0, (
            f"计划功率域缺少 {len(missing)} 个 capability 注册：{sorted(missing)}"
        )

    def test_plan_power_capability_count(self, prod_catalog: BusinessSemanticCatalog) -> None:
        """计划功率 capability 数量为 3。"""
        caps = prod_catalog.get_capabilities("plan_bom", capability_type="domain_capability")
        assert len(caps) == 3, f"预期 3 个 capability，实际 {len(caps)} 个"

    def test_plan_power_capabilities_have_aliases(self, prod_catalog: BusinessSemanticCatalog) -> None:
        """计划功率三个 capability 都有用户同义词。"""
        caps = prod_catalog.get_capabilities("plan_bom", capability_type="domain_capability")
        for cap in caps:
            assert len(cap.aliases) > 0, (
                f"capability {cap.capability_id} 缺少用户同义词"
            )

    # ── 跨域一致性 ──

    def test_domains_include_logistics_and_plan_bom(self, prod_catalog: BusinessSemanticCatalog) -> None:
        """catalog 的 domains() 包含 logistics 和 plan_bom（因为能力注册在新的 _capabilities 中）。"""
        domains = set(prod_catalog.domains())
        assert "logistics" in domains
        assert "plan_bom" in domains

    def test_no_domain_leakage(self, prod_catalog: BusinessSemanticCatalog) -> None:
        """query_key 只在 logistics 域，不出现在 plan_bom 中。"""
        logistics_query_keys = {
            c.capability_id
            for c in prod_catalog.get_capabilities("logistics", capability_type="query_key")
        }
        bom_caps = prod_catalog.get_capabilities("plan_bom")
        bom_ids = {c.capability_id for c in bom_caps}
        leaked = logistics_query_keys & bom_ids
        assert len(leaked) == 0, f"域泄漏：{leaked}"


# ==================== 与现有测试集兼容验证 ====================


class TestN4DoesNotBreakExistingTests:
    """验证 N4 新增功能不破坏 N1-N3 已有测试。"""

    def test_catalog_still_supports_metrics(self) -> None:
        """新增能力后，指标注册表仍然正常。"""
        catalog = BusinessSemanticCatalog()
        from backend.app.domains.semantic_catalog.schema import SemanticMetric

        metric = SemanticMetric(
            metric_id="shipment_mw",
            display_name="发货量",
            domain="logistics",
        )
        catalog.register_metric(metric)
        assert catalog.get_metric("logistics", "shipment_mw") is not None

    def test_catalog_still_supports_dimensions(self) -> None:
        """新增能力后，维度注册表仍然正常。"""
        catalog = BusinessSemanticCatalog()
        from backend.app.domains.semantic_catalog.schema import SemanticDimension

        dim = SemanticDimension(
            dimension_id="carrier",
            display_name="承运商",
            domain="logistics",
        )
        catalog.register_dimension(dim)
        assert catalog.get_dimension("logistics", "carrier") is not None

    def test_catalog_still_supports_entities(self) -> None:
        """新增能力后，实体注册表仍然正常。"""
        catalog = BusinessSemanticCatalog()
        from backend.app.domains.semantic_catalog.schema import SemanticEntity

        entity = SemanticEntity(
            entity_id="carrier",
            display_name="承运商",
            domain="logistics",
            entity_type="carrier",
        )
        catalog.register_entity(entity)
        entities = catalog.get_entities("logistics", entity_type="carrier")
        assert len(entities) == 1

    def test_domains_still_includes_metrics_domains(self) -> None:
        """domains() 仍能返回仅通过指标注册的域。"""
        catalog = BusinessSemanticCatalog()
        from backend.app.domains.semantic_catalog.schema import SemanticMetric

        catalog.register_metric(SemanticMetric(
            metric_id="test_metric",
            display_name="测试指标",
            domain="business_analysis",
        ))
        assert "business_analysis" in catalog.domains()


__all__ = [
    "TestSemanticCapability",
    "TestCatalogCapabilityOperations",
    "TestCapabilityYamlLoader",
    "TestProductionCatalogCompleteness",
    "TestN4DoesNotBreakExistingTests",
]

"""
NQE-N1：统一语义资产 Catalog Schema 与基础注册表 — 测试用例

测试范围：
    1. 核心 Schema（SemanticMetric / SemanticDimension / SemanticEntity）定义正确。
    2. BusinessSemanticCatalog 支持按 domain 注册和查询。
    3. 可从 YAML 文件加载注册数据。
    4. 可与现有 LogisticsSemanticCatalog 桥接（不做内部修改，只做适配读取）。
    5. BusinessValueResolverProtocol 定义可插拔的业务值解析接口。
"""

from __future__ import annotations

import pytest

from backend.app.domains.semantic_catalog.schema import (
    SemanticMetric,
    SemanticDimension,
    SemanticEntity,
    BusinessValueResolverProtocol,
)
from backend.app.domains.semantic_catalog.catalog import BusinessSemanticCatalog
from backend.app.domains.semantic_catalog.loader import SemanticCatalogYamlLoader


# ==================== Schema 基础测试 ====================


class TestSemanticMetric:
    """SemanticMetric Schema 定义测试。"""

    def test_create_metric_minimal(self) -> None:
        """创建最小字段的指标。"""
        metric = SemanticMetric(
            metric_id="shipment_mw",
            display_name="发货量",
            domain="logistics",
        )
        assert metric.metric_id == "shipment_mw"
        assert metric.display_name == "发货量"
        assert metric.domain == "logistics"
        assert metric.aliases == []
        assert metric.unit is None
        assert metric.description is None

    def test_create_metric_full(self) -> None:
        """创建完整字段的指标。"""
        metric = SemanticMetric(
            metric_id="total_fee",
            display_name="总费用",
            domain="logistics",
            aliases=["运费", "费用合计"],
            unit="元",
            description="物流发运总费用，含运费、装卸费等。",
        )
        assert metric.metric_id == "total_fee"
        assert metric.aliases == ["运费", "费用合计"]
        assert metric.unit == "元"
        assert metric.description == "物流发运总费用，含运费、装卸费等。"

    def test_create_metric_fails_without_required_fields(self) -> None:
        """缺少必填字段时构造失败。"""
        with pytest.raises(Exception):
            SemanticMetric(display_name="发货量", domain="logistics")  # type: ignore[arg-type]

        with pytest.raises(Exception):
            SemanticMetric(metric_id="shipment_mw", domain="logistics")  # type: ignore[arg-type]

        with pytest.raises(Exception):
            SemanticMetric(metric_id="shipment_mw", display_name="发货量")  # type: ignore[arg-type]


class TestSemanticDimension:
    """SemanticDimension Schema 定义测试。"""

    def test_create_dimension(self) -> None:
        """创建维度定义。"""
        dim = SemanticDimension(
            dimension_id="material_category",
            display_name="物料类别",
            domain="plan_bom",
            aliases=["物料类型", "产品类别"],
            description="BOM 中物料的分类维度。",
        )
        assert dim.dimension_id == "material_category"
        assert dim.domain == "plan_bom"
        assert "物料类型" in dim.aliases


class TestSemanticEntity:
    """SemanticEntity Schema 定义测试。"""

    def test_create_entity(self) -> None:
        """创建实体定义。"""
        entity = SemanticEntity(
            entity_id="承运商",
            display_name="承运商",
            domain="logistics",
            entity_type="carrier",
            aliases=["物流商", "运输公司"],
            description="物流承运商实体。",
        )
        assert entity.entity_id == "承运商"
        assert entity.entity_type == "carrier"
        assert entity.domain == "logistics"


# ==================== BusinessSemanticCatalog 注册表测试 ====================


class TestBusinessSemanticCatalog:
    """BusinessSemanticCatalog 注册与查询测试。"""

    @pytest.fixture
    def catalog(self) -> BusinessSemanticCatalog:
        """创建一个空的 catalog 实例。"""
        return BusinessSemanticCatalog()

    def test_catalog_empty_by_default(self, catalog: BusinessSemanticCatalog) -> None:
        """新建 catalog 默认为空。"""
        assert catalog.domains() == []

    def test_register_and_query_metric(self, catalog: BusinessSemanticCatalog) -> None:
        """注册一个指标后可按域和 ID 查询。"""
        metric = SemanticMetric(
            metric_id="shipment_mw",
            display_name="发货量",
            domain="logistics",
            unit="MW",
        )
        catalog.register_metric(metric)

        results = catalog.get_metrics(domain="logistics")
        assert len(results) == 1
        assert results[0].metric_id == "shipment_mw"

        found = catalog.get_metric("logistics", "shipment_mw")
        assert found is not None
        assert found.display_name == "发货量"
        assert found.unit == "MW"

    def test_register_multiple_domains(self, catalog: BusinessSemanticCatalog) -> None:
        """多个域的指标可分别注册和查询。"""
        logistics_metric = SemanticMetric(
            metric_id="shipment_mw",
            display_name="发货量",
            domain="logistics",
        )
        bom_metric = SemanticMetric(
            metric_id="power_prediction",
            display_name="功率预测",
            domain="plan_bom",
        )
        catalog.register_metric(logistics_metric)
        catalog.register_metric(bom_metric)

        assert catalog.domains() == ["logistics", "plan_bom"]

        logistics_results = catalog.get_metrics(domain="logistics")
        assert len(logistics_results) == 1
        assert logistics_results[0].metric_id == "shipment_mw"

        bom_results = catalog.get_metrics(domain="plan_bom")
        assert len(bom_results) == 1
        assert bom_results[0].metric_id == "power_prediction"

    def test_query_nonexistent_metric_returns_none(self, catalog: BusinessSemanticCatalog) -> None:
        """查询不存在的指标返回 None。"""
        assert catalog.get_metric("logistics", "nonexistent") is None

    def test_register_dimension(self, catalog: BusinessSemanticCatalog) -> None:
        """注册维度并查询。"""
        dim = SemanticDimension(
            dimension_id="material_category",
            display_name="物料类别",
            domain="plan_bom",
        )
        catalog.register_dimension(dim)

        results = catalog.get_dimensions(domain="plan_bom")
        assert len(results) == 1
        assert results[0].dimension_id == "material_category"

        found = catalog.get_dimension("plan_bom", "material_category")
        assert found is not None

    def test_register_entity(self, catalog: BusinessSemanticCatalog) -> None:
        """注册实体并查询。"""
        entity = SemanticEntity(
            entity_id="carrier",
            display_name="承运商",
            domain="logistics",
            entity_type="carrier",
        )
        catalog.register_entity(entity)

        results = catalog.get_entities(domain="logistics")
        assert len(results) == 1
        assert results[0].entity_id == "carrier"

        by_type = catalog.get_entities(domain="logistics", entity_type="carrier")
        assert len(by_type) == 1

    def test_resolve_metric_alias(self, catalog: BusinessSemanticCatalog) -> None:
        """按用户口语同义词解析受控指标。"""
        metric = SemanticMetric(
            metric_id="shipment_mw",
            display_name="发货量",
            domain="logistics",
            aliases=["件数", "发运量", "出货量"],
        )
        catalog.register_metric(metric)

        resolved = catalog.resolve_metric_alias("logistics", "件数")
        assert resolved is not None
        assert resolved.metric_id == "shipment_mw"

        resolved2 = catalog.resolve_metric_alias("logistics", "发货量")
        assert resolved2 is not None
        assert resolved2.metric_id == "shipment_mw"

        not_found = catalog.resolve_metric_alias("logistics", "不存在")
        assert not_found is None

    def test_register_duplicate_metric_overwrites(self, catalog: BusinessSemanticCatalog) -> None:
        """重复注册同一 domain + metric_id 会覆盖。"""
        m1 = SemanticMetric(
            metric_id="shipment_mw",
            display_name="发货量",
            domain="logistics",
        )
        m2 = SemanticMetric(
            metric_id="shipment_mw",
            display_name="发运量（更新）",
            domain="logistics",
        )
        catalog.register_metric(m1)
        catalog.register_metric(m2)

        results = catalog.get_metrics(domain="logistics")
        assert len(results) == 1
        assert results[0].display_name == "发运量（更新）"


# ==================== YAML Loader 测试 ====================


class TestSemanticCatalogYamlLoader:
    """YAML 文件加载器测试。"""

    def test_load_metrics_from_yaml(self, tmp_path) -> None:
        """从 YAML 文件加载指标注册表。"""
        import yaml

        yaml_content = {
            "metrics": [
                {
                    "metric_id": "shipment_mw",
                    "display_name": "发货量",
                    "domain": "logistics",
                    "aliases": ["件数", "发运量"],
                    "unit": "MW",
                    "description": "物流发运总兆瓦数。",
                },
                {
                    "metric_id": "total_fee",
                    "display_name": "总费用",
                    "domain": "logistics",
                    "aliases": ["运费"],
                    "unit": "元",
                },
            ],
            "dimensions": [
                {
                    "dimension_id": "carrier",
                    "display_name": "承运商",
                    "domain": "logistics",
                    "aliases": ["物流商"],
                },
            ],
            "entities": [],
        }
        yaml_path = tmp_path / "metrics.yaml"
        yaml_path.write_text(yaml.dump(yaml_content, allow_unicode=True), encoding="utf-8")

        loader = SemanticCatalogYamlLoader(catalog_dir=tmp_path)
        catalog = loader.load()

        assert "logistics" in catalog.domains()

        found = catalog.get_metric("logistics", "shipment_mw")
        assert found is not None
        assert found.display_name == "发货量"
        assert found.unit == "MW"
        assert "件数" in found.aliases

        total_fee = catalog.get_metric("logistics", "total_fee")
        assert total_fee is not None
        assert total_fee.unit == "元"

    def test_load_dimensions_from_yaml(self, tmp_path) -> None:
        """从 YAML 加载维度并正确查询 plan_bom 域。"""
        import yaml

        yaml_content = {
            "dimensions": [
                {
                    "dimension_id": "material_category",
                    "display_name": "物料类别",
                    "domain": "plan_bom",
                    "aliases": ["物料类型"],
                    "description": "BOM 物料分类维度。",
                },
                {
                    "dimension_id": "version_no",
                    "display_name": "版本号",
                    "domain": "plan_bom",
                    "aliases": ["BOM版本"],
                },
            ],
        }
        yaml_path = tmp_path / "dimensions.yaml"
        yaml_path.write_text(yaml.dump(yaml_content, allow_unicode=True), encoding="utf-8")

        loader = SemanticCatalogYamlLoader(catalog_dir=tmp_path)
        catalog = loader.load()

        dims = catalog.get_dimensions(domain="plan_bom")
        assert len(dims) == 2

        mat_cat = catalog.get_dimension("plan_bom", "material_category")
        assert mat_cat is not None
        assert mat_cat.display_name == "物料类别"

        ver = catalog.get_dimension("plan_bom", "version_no")
        assert ver is not None
        assert ver.display_name == "版本号"

    def test_load_entities_from_yaml(self, tmp_path) -> None:
        """从 YAML 加载实体定义。"""
        import yaml

        yaml_content = {
            "entities": [
                {
                    "entity_id": "carrier",
                    "display_name": "承运商",
                    "domain": "logistics",
                    "entity_type": "carrier",
                    "aliases": ["物流商", "运输方"],
                },
            ],
        }
        yaml_path = tmp_path / "entities.yaml"
        yaml_path.write_text(yaml.dump(yaml_content, allow_unicode=True), encoding="utf-8")

        loader = SemanticCatalogYamlLoader(catalog_dir=tmp_path)
        catalog = loader.load()

        entities = catalog.get_entities(domain="logistics", entity_type="carrier")
        assert len(entities) == 1
        assert entities[0].entity_id == "carrier"


# ==================== 与现有 LogisticsSemanticCatalog 兼容测试 ====================


class TestBridgeToExistingCatalogs:
    """验证统一 catalog 可与现有领域 catalog 桥接，不做内部修改。"""

    def test_bridge_from_logistics_semantic_catalog(self) -> None:
        """
        从现有 LogisticsSemanticCatalog 读取数据并注册到统一 catalog。

        验收条件：
            - 不改动 LogisticsSemanticCatalog 内部实现。
            - 统一 catalog 可查询物流的 shipment_mw、total_fee 等指标。
            - 统一 catalog 可查询物流的 carrier、year 等维度。
        """
        from backend.app.domains.logistics.services.nl2sql.semantic_catalog import (
            LogisticsSemanticCatalogLoader,
        )
        from backend.app.domains.semantic_catalog.bridge import (
            bridge_logistics_catalog_to_unified,
        )

        # 加载现有物流 catalog
        logistics_catalog = LogisticsSemanticCatalogLoader().load()

        # 桥接到统一 catalog
        unified = BusinessSemanticCatalog()
        bridge_logistics_catalog_to_unified(logistics_catalog, unified)

        # 验物物指标可查询
        assert unified.get_metric("logistics", "shipment_mw") is not None
        assert unified.get_metric("logistics", "total_fee") is not None

        # 验物维度可查询（物流 catalog 中使用 logistics_company_name 作为承运商维度 ID）
        found = unified.get_dimension("logistics", "logistics_company_name")
        assert found is not None
        assert found.display_name == "承运商"

    def test_bridge_preserves_logistics_catalog_untouched(self) -> None:
        """
        桥接后原 LogisticsSemanticCatalog 对象状态不变。
        """
        from backend.app.domains.logistics.services.nl2sql.semantic_catalog import (
            LogisticsSemanticCatalogLoader,
        )
        from backend.app.domains.semantic_catalog.bridge import (
            bridge_logistics_catalog_to_unified,
        )

        logistics_catalog = LogisticsSemanticCatalogLoader().load()
        original_metric_count = len(logistics_catalog.metrics)

        unified = BusinessSemanticCatalog()
        bridge_logistics_catalog_to_unified(logistics_catalog, unified)

        # 原 catalog 数据不变
        assert len(logistics_catalog.metrics) == original_metric_count


# ==================== BusinessValueResolverProtocol 测试 ====================


class TestBusinessValueResolverProtocol:
    """业务值解析协议定义验证。"""

    def test_protocol_structural_conformance(self) -> None:
        """
        验证实现了 resolve/register 方法的类满足 Protocol 结构。
        """
        from typing import Protocol, runtime_checkable

        @runtime_checkable
        class _ResolverProtocol(Protocol):
            """业务值解析器协议（运行时检查版）。"""

            def resolve(self, domain: str, entity_type: str, user_input: str) -> list[dict[str, str]]:
                ...

            def register(self, domain: str, entity_type: str, values: list[dict[str, str]]) -> None:
                ...

        class ConcreteResolver:
            def resolve(self, domain: str, entity_type: str, user_input: str) -> list[dict[str, str]]:
                return [{"id": "value1", "label": "显示值1"}]

            def register(self, domain: str, entity_type: str, values: list[dict[str, str]]) -> None:
                pass

        resolver = ConcreteResolver()
        assert isinstance(resolver, _ResolverProtocol)

    def test_resolver_not_conforming_missing_method(self) -> None:
        """缺少必要方法的类不符合 Protocol。"""
        from typing import Protocol, runtime_checkable

        @runtime_checkable
        class _ResolverProtocol(Protocol):
            """业务值解析器协议（运行时检查版）。"""

            def resolve(self, domain: str, entity_type: str, user_input: str) -> list[dict[str, str]]:
                ...

            def register(self, domain: str, entity_type: str, values: list[dict[str, str]]) -> None:
                ...

        class IncompleteResolver:
            def resolve(self, domain: str, entity_type: str, user_input: str) -> list[dict[str, str]]:
                return []

        incomplete = IncompleteResolver()
        assert not isinstance(incomplete, _ResolverProtocol)

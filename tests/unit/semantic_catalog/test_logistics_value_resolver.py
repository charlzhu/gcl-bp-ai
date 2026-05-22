"""
NQE-N2：LogisticsValueResolver — 物流域实体值解析器测试

测试范围：
    1. 承运商解析：精确/模糊匹配，返回多候选。
    2. 客户解析：模糊匹配。
    3. 区域/线路/地址解析：候选返回。
    4. 未知实体类型返回空或明确错误。
    5. 误匹配时返回多候选而非单一硬匹配。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from backend.app.domains.semantic_catalog.value_resolver.base import BusinessValueResolver


# 模拟 LogisticsDataQaRepository 的承运商查询返回
MOCK_CARRIER_NAMES = [
    "顺丰物流有限公司",
    "德邦物流股份有限公司",
    "安能物流有限公司",
    "百世物流科技有限公司",
    "远成物流股份有限公司",
]


# 模拟客户/委托人查询返回
MOCK_CUSTOMER_NAMES = [
    "华为技术有限公司",
    "中兴通讯股份有限公司",
    "阳光电源股份有限公司",
    "晶科能源有限公司",
]


def _make_mock_db() -> MagicMock:
    """构造模拟的 SQLAlchemy Session。"""
    mock_db = MagicMock(spec=Session)
    return mock_db


# ── 承运商解析测试 ──

class TestLogisticsCarrierResolve:
    """承运商实体值解析测试。"""

    def test_resolve_carrier_exact_match(self) -> None:
        """精确匹配承运商名返回对应候选。"""
        from backend.app.domains.semantic_catalog.value_resolver.logistics_resolver import (
            LogisticsValueResolver,
        )

        resolver = LogisticsValueResolver(db=_make_mock_db())
        # 直接注入测试数据到 _carrier_cache
        resolver._carrier_cache = list(MOCK_CARRIER_NAMES)

        results = resolver.resolve("carrier", "顺丰物流有限公司")
        assert len(results) == 1
        assert results[0]["entity_type"] == "carrier"
        assert results[0]["value"] == "顺丰物流有限公司"
        assert results[0]["label"] == "顺丰物流有限公司"

    def test_resolve_carrier_fuzzy_match_multiple(self) -> None:
        """模糊匹配返回多个候选。"""
        from backend.app.domains.semantic_catalog.value_resolver.logistics_resolver import (
            LogisticsValueResolver,
        )

        resolver = LogisticsValueResolver(db=_make_mock_db())
        resolver._carrier_cache = list(MOCK_CARRIER_NAMES)

        results = resolver.resolve("carrier", "物流")
        # "物流" 匹配多个承运商名
        assert len(results) >= 3
        for r in results:
            assert r["entity_type"] == "carrier"
            assert "物流" in r["value"]

    def test_resolve_carrier_no_match_returns_empty(self) -> None:
        """完全无匹配时返回空列表，而非硬路由到随机承运商。"""
        from backend.app.domains.semantic_catalog.value_resolver.logistics_resolver import (
            LogisticsValueResolver,
        )

        resolver = LogisticsValueResolver(db=_make_mock_db())
        resolver._carrier_cache = list(MOCK_CARRIER_NAMES)

        results = resolver.resolve("carrier", "完全不存在的承运商名称XYZ123")
        assert results == []

    def test_resolve_carrier_partial_name_one_match(self) -> None:
        """部分名称匹配到唯一承运商时返回对应候选。"""
        from backend.app.domains.semantic_catalog.value_resolver.logistics_resolver import (
            LogisticsValueResolver,
        )

        resolver = LogisticsValueResolver(db=_make_mock_db())
        resolver._carrier_cache = list(MOCK_CARRIER_NAMES)

        results = resolver.resolve("carrier", "德邦")
        assert len(results) == 1
        assert "德邦" in results[0]["value"]


# ── 客户解析测试 ──

class TestLogisticsCustomerResolve:
    """客户/委托人实体值解析测试。"""

    def test_resolve_customer_fuzzy_match(self) -> None:
        """客户名模糊匹配返回多候选。"""
        from backend.app.domains.semantic_catalog.value_resolver.logistics_resolver import (
            LogisticsValueResolver,
        )

        resolver = LogisticsValueResolver(db=_make_mock_db())
        resolver._customer_cache = list(MOCK_CUSTOMER_NAMES)

        results = resolver.resolve("customer", "华为")
        assert len(results) == 1
        assert results[0]["entity_type"] == "customer"
        assert "华为" in results[0]["value"]

    def test_resolve_customer_no_match(self) -> None:
        """不存在的客户名返回空列表。"""
        from backend.app.domains.semantic_catalog.value_resolver.logistics_resolver import (
            LogisticsValueResolver,
        )

        resolver = LogisticsValueResolver(db=_make_mock_db())
        resolver._customer_cache = list(MOCK_CUSTOMER_NAMES)

        results = resolver.resolve("customer", "不存在的客户ABC")
        assert results == []


# ── candidates 候选列表测试 ──

class TestLogisticsCandidates:
    """candidates 方法测试。"""

    def test_candidates_carrier(self) -> None:
        """承运商 candidates 返回去重后的候选列表。"""
        from backend.app.domains.semantic_catalog.value_resolver.logistics_resolver import (
            LogisticsValueResolver,
        )

        resolver = LogisticsValueResolver(db=_make_mock_db())
        resolver._carrier_cache = list(MOCK_CARRIER_NAMES)

        results = resolver.candidates("carrier", limit=10)
        assert len(results) == len(MOCK_CARRIER_NAMES)
        for r in results:
            assert r["entity_type"] == "carrier"
            assert "value" in r
            assert "label" in r

    def test_candidates_customer(self) -> None:
        """客户 candidates 返回候选列表。"""
        from backend.app.domains.semantic_catalog.value_resolver.logistics_resolver import (
            LogisticsValueResolver,
        )

        resolver = LogisticsValueResolver(db=_make_mock_db())
        resolver._customer_cache = list(MOCK_CUSTOMER_NAMES)

        results = resolver.candidates("customer", limit=10)
        assert len(results) == len(MOCK_CUSTOMER_NAMES)
        for r in results:
            assert r["entity_type"] == "customer"

    def test_candidates_respects_limit(self) -> None:
        """candidates 遵守 limit 参数。"""
        from backend.app.domains.semantic_catalog.value_resolver.logistics_resolver import (
            LogisticsValueResolver,
        )

        resolver = LogisticsValueResolver(db=_make_mock_db())
        resolver._carrier_cache = list(MOCK_CARRIER_NAMES)

        results = resolver.candidates("carrier", limit=2)
        assert len(results) == 2


# ── 区域实体测试 ──

class TestLogisticsRegion:
    """区域实体值解析测试。"""

    def test_region_candidates_return_standard_regions(self) -> None:
        """区域 candidates 返回标准行政区划列表。"""
        from backend.app.domains.semantic_catalog.value_resolver.logistics_resolver import (
            LogisticsValueResolver,
        )

        resolver = LogisticsValueResolver(db=_make_mock_db())
        results = resolver.candidates("region", limit=50)

        # 至少包含华东、华南等标准区域
        assert len(results) >= 7
        region_names = [r["label"] for r in results]
        assert "华东" in region_names
        assert "华南" in region_names
        assert "华北" in region_names

    def test_region_resolve_by_name(self) -> None:
        """区域按名称精确解析。"""
        from backend.app.domains.semantic_catalog.value_resolver.logistics_resolver import (
            LogisticsValueResolver,
        )

        resolver = LogisticsValueResolver(db=_make_mock_db())
        results = resolver.resolve("region", "华东")

        assert len(results) == 1
        assert results[0]["value"] == "华东"


# ── unknown entity_type 测试 ──

class TestLogisticsUnknownEntity:
    """未知实体类型回退测试。"""

    def test_resolve_unknown_entity_type_returns_empty(self) -> None:
        """未知实体类型 resolve 返回空列表。"""
        from backend.app.domains.semantic_catalog.value_resolver.logistics_resolver import (
            LogisticsValueResolver,
        )

        resolver = LogisticsValueResolver(db=_make_mock_db())
        results = resolver.resolve("unknown_type", "测试")
        assert results == []

    def test_candidates_unknown_entity_type_returns_empty(self) -> None:
        """未知实体类型 candidates 返回空列表。"""
        from backend.app.domains.semantic_catalog.value_resolver.logistics_resolver import (
            LogisticsValueResolver,
        )

        resolver = LogisticsValueResolver(db=_make_mock_db())
        results = resolver.candidates("unknown_type")
        assert results == []


# ── 继承关系测试 ──

class TestLogisticsInheritance:
    """LogisticsValueResolver 正确继承 BusinessValueResolver。"""

    def test_is_instance_of_business_value_resolver(self) -> None:
        """LogisticsValueResolver 是 BusinessValueResolver 的子类。"""
        from backend.app.domains.semantic_catalog.value_resolver.logistics_resolver import (
            LogisticsValueResolver,
        )

        resolver = LogisticsValueResolver(db=_make_mock_db())
        assert isinstance(resolver, BusinessValueResolver)

    def test_domain_is_logistics(self) -> None:
        """domain 属性为 logistics。"""
        from backend.app.domains.semantic_catalog.value_resolver.logistics_resolver import (
            LogisticsValueResolver,
        )

        resolver = LogisticsValueResolver(db=_make_mock_db())
        assert resolver.domain == "logistics"


# ── resolve_multi 测试 ──

class TestLogisticsResolveMulti:
    """resolve_multi 批量解析测试。"""

    def test_resolve_multi_carrier_and_customer(self) -> None:
        """同时解析承运商和客户。"""
        from backend.app.domains.semantic_catalog.value_resolver.logistics_resolver import (
            LogisticsValueResolver,
        )

        resolver = LogisticsValueResolver(db=_make_mock_db())
        resolver._carrier_cache = list(MOCK_CARRIER_NAMES)
        resolver._customer_cache = list(MOCK_CUSTOMER_NAMES)

        results = resolver.resolve_multi([
            ("carrier", "顺丰"),
            ("customer", "华为"),
        ])

        assert len(results) == 2
        assert results[0]["entity_type"] == "carrier"
        assert results[1]["entity_type"] == "customer"
        assert "顺丰" in results[0]["value"]
        assert "华为" in results[1]["value"]

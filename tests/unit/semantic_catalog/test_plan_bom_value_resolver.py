"""
NQE-N2：PlanBomValueResolver — 计划 BOM 域实体值解析器测试

测试范围：
    1. 订单 identity 解析（订单号/订单名）。
    2. 文件名解析（file_instance_key / raw_file_name）。
    3. 客户实例解析（从订单名中提取客户名）。
    4. 版本号解析（version_no）。
    5. 误匹配时返回多候选。
    6. 未知实体类型返回空。
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from backend.app.domains.semantic_catalog.value_resolver.base import BusinessValueResolver


# ── 模拟 PlanBomHeader 数据 ──

def _make_mock_headers() -> list[dict]:
    """构造模拟 BOM 头数据，模拟 PlanBomHeader 字段。"""
    return [
        {
            "order_no": "PO2025-001",
            "order_name": "华为2025年光伏项目",
            "version_no": "A0",
            "order_identity_key": "excel_inst_abc001",
            "file_instance_key": "excel_file_f001",
            "raw_file_name": "华为光伏_BOM_A0.xlsx",
            "is_active": 1,
        },
        {
            "order_no": "PO2025-002",
            "order_name": "阳光电源2025储能项目",
            "version_no": "A1",
            "order_identity_key": "excel_inst_abc002",
            "file_instance_key": "excel_file_f002",
            "raw_file_name": "阳光电源储能_BOM_A1.xlsx",
            "is_active": 1,
        },
        {
            "order_no": "PO2025-003",
            "order_name": "华为2025储能项目",
            "version_no": "A0",
            "order_identity_key": "excel_inst_abc003",
            "file_instance_key": "excel_file_f003",
            "raw_file_name": "华为储能_BOM_A0.xlsx",
            "is_active": 1,
        },
        {
            "order_no": "PO2025-004",
            "order_name": "晶科能源2025项目",
            "version_no": "B0",
            "order_identity_key": "excel_inst_abc004",
            "file_instance_key": "excel_file_f004",
            "raw_file_name": "晶科_BOM_B0.xlsx",
            "is_active": 1,
        },
    ]


def _make_mock_db() -> MagicMock:
    """构造模拟 SQLAlchemy Session。"""
    return MagicMock(spec=Session)


def _make_mock_repo(headers: list[dict] | None = None) -> MagicMock:
    """构造模拟 PlanBomQueryRepository。"""
    repo = MagicMock()
    repo.list_active_headers.return_value = [_make_mock_header_obj(h) for h in (headers or _make_mock_headers())]
    repo.list_all_active_headers.return_value = [_make_mock_header_obj(h) for h in (headers or _make_mock_headers())]
    return repo


def _make_mock_header_obj(data: dict) -> MagicMock:
    """将 dict 转为模拟 PlanBomHeader 对象。"""
    obj = MagicMock()
    for key, value in data.items():
        setattr(obj, key, value)
    return obj


# ── 订单 identity 解析测试 ──

class TestPlanBomOrderResolve:
    """订单 identity 实体值解析测试。"""

    def test_resolve_order_by_order_no(self) -> None:
        """按订单号精确匹配。"""
        from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
            PlanBomValueResolver,
        )

        headers = _make_mock_headers()
        resolver = PlanBomValueResolver(db=_make_mock_db(), repo=_make_mock_repo(headers))

        results = resolver.resolve("order_identity", "PO2025-001")
        assert len(results) >= 1
        assert results[0]["entity_type"] == "order_identity"
        assert "PO2025-001" in results[0]["value"]

    def test_resolve_order_by_order_name_fragment(self) -> None:
        """按订单名片段模糊匹配返回多候选。"""
        from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
            PlanBomValueResolver,
        )

        headers = _make_mock_headers()
        resolver = PlanBomValueResolver(db=_make_mock_db(), repo=_make_mock_repo(headers))

        # "华为" 匹配两个订单
        results = resolver.resolve("order_identity", "华为")
        assert len(results) == 2
        for r in results:
            assert r["entity_type"] == "order_identity"
            assert "华为" in r["value"] or "华为" in r["label"]

    def test_resolve_order_no_match(self) -> None:
        """不存在时返回空列表。"""
        from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
            PlanBomValueResolver,
        )

        headers = _make_mock_headers()
        resolver = PlanBomValueResolver(db=_make_mock_db(), repo=_make_mock_repo(headers))

        results = resolver.resolve("order_identity", "不存在的订单XYZ")
        assert results == []


# ── 文件名解析测试 ──

class TestPlanBomFilenameResolve:
    """文件名实体值解析测试。"""

    def test_resolve_filename_exact(self) -> None:
        """按完整文件名匹配。"""
        from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
            PlanBomValueResolver,
        )

        headers = _make_mock_headers()
        resolver = PlanBomValueResolver(db=_make_mock_db(), repo=_make_mock_repo(headers))

        results = resolver.resolve("filename", "华为光伏_BOM_A0.xlsx")
        assert len(results) == 1
        assert results[0]["entity_type"] == "filename"
        assert "华为光伏" in results[0]["label"]

    def test_resolve_filename_fragment(self) -> None:
        """按文件名片段模糊匹配。"""
        from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
            PlanBomValueResolver,
        )

        headers = _make_mock_headers()
        resolver = PlanBomValueResolver(db=_make_mock_db(), repo=_make_mock_repo(headers))

        results = resolver.resolve("filename", "储能")
        assert len(results) == 2  # 阳光电源储能 + 华为储能
        for r in results:
            assert r["entity_type"] == "filename"

    def test_resolve_filename_no_match(self) -> None:
        """不存在时返回空列表。"""
        from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
            PlanBomValueResolver,
        )

        headers = _make_mock_headers()
        resolver = PlanBomValueResolver(db=_make_mock_db(), repo=_make_mock_repo(headers))

        results = resolver.resolve("filename", "不存在文件.xlsx")
        assert results == []


# ── 客户实例解析测试 ──

class TestPlanBomCustomerResolve:
    """客户实例实体值解析测试。"""

    def test_resolve_customer_by_name_fragment(self) -> None:
        """按客户名片段匹配。"""
        from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
            PlanBomValueResolver,
        )

        headers = _make_mock_headers()
        resolver = PlanBomValueResolver(db=_make_mock_db(), repo=_make_mock_repo(headers))

        results = resolver.resolve("customer_instance", "华为")
        assert len(results) == 2  # 华为2025年光伏 + 华为2025储能
        for r in results:
            assert r["entity_type"] == "customer_instance"
            assert "华为" in r["value"] or "华为" in r["label"]

    def test_resolve_customer_no_match(self) -> None:
        """不存在的客户返回空。"""
        from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
            PlanBomValueResolver,
        )

        headers = _make_mock_headers()
        resolver = PlanBomValueResolver(db=_make_mock_db(), repo=_make_mock_repo(headers))

        results = resolver.resolve("customer_instance", "不存在的客户XYZ")
        assert results == []


# ── 版本号解析测试 ──

class TestPlanBomVersionResolve:
    """版本号实体值解析测试。"""

    def test_resolve_version_exact(self) -> None:
        """按版本号精确匹配。"""
        from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
            PlanBomValueResolver,
        )

        headers = _make_mock_headers()
        resolver = PlanBomValueResolver(db=_make_mock_db(), repo=_make_mock_repo(headers))

        results = resolver.resolve("version", "A0")
        assert len(results) >= 2  # PO2025-001 A0 + PO2025-003 A0
        for r in results:
            assert r["entity_type"] == "version"
            assert r["value"] == "A0"

    def test_resolve_version_no_match(self) -> None:
        """不存在的版本号返回空。"""
        from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
            PlanBomValueResolver,
        )

        headers = _make_mock_headers()
        resolver = PlanBomValueResolver(db=_make_mock_db(), repo=_make_mock_repo(headers))

        results = resolver.resolve("version", "Z99")
        assert results == []


# ── candidates 候选列表测试 ──

class TestPlanBomCandidates:
    """candidates 方法测试。"""

    def test_candidates_order_identity(self) -> None:
        """订单 identity candidates 返回去重后的列表。"""
        from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
            PlanBomValueResolver,
        )

        headers = _make_mock_headers()
        resolver = PlanBomValueResolver(db=_make_mock_db(), repo=_make_mock_repo(headers))

        results = resolver.candidates("order_identity", limit=10)
        assert len(results) == 4
        for r in results:
            assert r["entity_type"] == "order_identity"

    def test_candidates_customer_instance(self) -> None:
        """客户实例 candidates 返回客户候选。"""
        from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
            PlanBomValueResolver,
        )

        headers = _make_mock_headers()
        resolver = PlanBomValueResolver(db=_make_mock_db(), repo=_make_mock_repo(headers))

        results = resolver.candidates("customer_instance", limit=10)
        # 提取的唯一客户名：华为(2个)、阳光电源、晶科能源
        assert len(results) >= 3

    def test_candidates_respects_limit(self) -> None:
        """candidates 遵守 limit 参数。"""
        from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
            PlanBomValueResolver,
        )

        headers = _make_mock_headers()
        resolver = PlanBomValueResolver(db=_make_mock_db(), repo=_make_mock_repo(headers))

        results = resolver.candidates("version", limit=2)
        # A0, A1, B0 → 只返回前 2 个
        assert len(results) <= 2
        for r in results:
            assert r["entity_type"] == "version"


# ── unknown entity_type 测试 ──

class TestPlanBomUnknownEntity:
    """未知实体类型测试。"""

    def test_resolve_unknown_type_returns_empty(self) -> None:
        """未知实体类型 resolve 返回空列表。"""
        from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
            PlanBomValueResolver,
        )

        resolver = PlanBomValueResolver(db=_make_mock_db(), repo=_make_mock_repo())
        results = resolver.resolve("unknown", "测试")
        assert results == []

    def test_candidates_unknown_type_returns_empty(self) -> None:
        """未知实体类型 candidates 返回空列表。"""
        from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
            PlanBomValueResolver,
        )

        resolver = PlanBomValueResolver(db=_make_mock_db(), repo=_make_mock_repo())
        results = resolver.candidates("unknown")
        assert results == []


# ── DB 异常降级测试 ──

class TestPlanBomDbExceptionSafety:
    """DB 异常时的安全降级测试。"""

    def test_resolve_returns_empty_when_repo_raises(self) -> None:
        """repo 抛异常时 resolve 返回空列表，不传播异常。"""
        from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
            PlanBomValueResolver,
        )

        repo = MagicMock()
        repo.list_all_active_headers.side_effect = RuntimeError("DB connection timeout")

        resolver = PlanBomValueResolver(db=_make_mock_db(), repo=repo)
        results = resolver.resolve("order_identity", "PO2025-001")
        assert results == []

    def test_candidates_returns_empty_when_repo_raises(self) -> None:
        """repo 抛异常时 candidates 返回空列表，不传播异常。"""
        from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
            PlanBomValueResolver,
        )

        repo = MagicMock()
        repo.list_all_active_headers.side_effect = RuntimeError("DB connection timeout")

        resolver = PlanBomValueResolver(db=_make_mock_db(), repo=repo)
        results = resolver.candidates("order_identity", limit=10)
        assert results == []

    def test_cache_reload_when_limit_exceeds_cached(self) -> None:
        """缓存数据量不足时自动重新加载更大数据集。"""
        from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
            PlanBomValueResolver,
        )

        # 构造 10 条数据
        headers = [
            {
                "order_no": f"PO2025-{i:03d}",
                "order_name": f"项目{i}",
                "version_no": "A0",
                "order_identity_key": f"key_{i}",
                "file_instance_key": f"file_{i}",
                "raw_file_name": f"file_{i}.xlsx",
                "is_active": 1,
            }
            for i in range(10)
        ]

        repo = MagicMock()
        # 第一次调用返回 3 条，第二次返回 10 条
        repo.list_all_active_headers.side_effect = [
            [_make_mock_header_obj(h) for h in headers[:3]],
            [_make_mock_header_obj(h) for h in headers],
        ]

        resolver = PlanBomValueResolver(db=_make_mock_db(), repo=repo)

        # 第一次请求 limit=2 → 缓存 3 条
        results = resolver.candidates("order_identity", limit=2)
        assert len(results) == 2

        # 第二次请求 limit=10 → 缓存只有 3 条，应重新加载
        results = resolver.candidates("order_identity", limit=10)
        # 缓存重新加载后应返回 10 条
        assert len(results) == 10


# ── 继承关系测试 ──

class TestPlanBomInheritance:
    """PlanBomValueResolver 继承关系。"""

    def test_is_instance_of_business_value_resolver(self) -> None:
        """PlanBomValueResolver 是 BusinessValueResolver 的子类。"""
        from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
            PlanBomValueResolver,
        )

        resolver = PlanBomValueResolver(db=_make_mock_db(), repo=_make_mock_repo())
        assert isinstance(resolver, BusinessValueResolver)

    def test_domain_is_plan_bom(self) -> None:
        """domain 属性为 plan_bom。"""
        from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
            PlanBomValueResolver,
        )

        resolver = PlanBomValueResolver(db=_make_mock_db(), repo=_make_mock_repo())
        assert resolver.domain == "plan_bom"

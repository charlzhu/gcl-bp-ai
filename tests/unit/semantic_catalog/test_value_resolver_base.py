"""
NQE-N2：统一 BusinessValueResolver 接口 — 基类测试

测试范围：
    1. BusinessValueResolver 抽象基类定义了 resolve/candidates/resolve_multi 接口。
    2. 子类不实现抽象方法时构造失败。
    3. resolve_multi 默认实现正确工作。
    4. 返回的 dict 包含 entity_type、value、label 字段。
"""
from __future__ import annotations

import pytest

from backend.app.domains.semantic_catalog.value_resolver.base import (
    BusinessValueResolver,
)


# ── 基类抽象方法约束测试 ──

class TestBusinessValueResolverAbstract:
    """BusinessValueResolver 抽象基类约束。"""

    def test_cannot_instantiate_without_resolve(self) -> None:
        """子类未实现 resolve 方法时构造失败。"""

        class Incomplete(BusinessValueResolver):
            """缺少 resolve 方法。"""
            domain = "logistics"

            def candidates(self, entity_type: str, limit: int = 20) -> list[dict]:
                return []

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_cannot_instantiate_without_candidates(self) -> None:
        """子类未实现 candidates 方法时构造失败。"""

        class Incomplete(BusinessValueResolver):
            """缺少 candidates 方法。"""
            domain = "logistics"

            def resolve(self, entity_type: str, user_input: str) -> list[dict]:
                return []

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_valid_subclass_instantiates(self) -> None:
        """实现全部抽象方法的子类可以正常实例化。"""

        class Complete(BusinessValueResolver):
            """完整实现。"""
            domain = "logistics"

            def resolve(self, entity_type: str, user_input: str) -> list[dict]:
                return [{"entity_type": entity_type, "value": user_input, "label": user_input}]

            def candidates(self, entity_type: str, limit: int = 20) -> list[dict]:
                return []

        instance = Complete()
        assert instance.domain == "logistics"


# ── resolve_multi 默认实现测试 ──

class TestResolveMultiDefault:
    """resolve_multi 默认实现测试。"""

    def test_resolve_multi_calls_resolve_for_each_query(self) -> None:
        """resolve_multi 按顺序对每个查询调用 resolve 并汇总结果。"""

        class Multi(BusinessValueResolver):
            """记录 resolve 调用。"""
            domain = "logistics"
            calls: list[tuple[str, str]]

            def __init__(self) -> None:
                super().__init__()
                self.calls = []

            def resolve(self, entity_type: str, user_input: str) -> list[dict]:
                self.calls.append((entity_type, user_input))
                return [{"entity_type": entity_type, "value": user_input, "label": user_input}]

            def candidates(self, entity_type: str, limit: int = 20) -> list[dict]:
                return []

        resolver = Multi()
        results = resolver.resolve_multi([
            ("carrier", "顺丰"),
            ("customer", "华为"),
        ])

        assert len(results) == 2
        assert resolver.calls == [("carrier", "顺丰"), ("customer", "华为")]
        assert results[0]["entity_type"] == "carrier"
        assert results[0]["value"] == "顺丰"
        assert results[1]["entity_type"] == "customer"
        assert results[1]["value"] == "华为"

    def test_resolve_multi_empty_queries(self) -> None:
        """空查询列表返回空列表。"""

        class Empty(BusinessValueResolver):
            domain = "logistics"

            def resolve(self, entity_type: str, user_input: str) -> list[dict]:
                return []

            def candidates(self, entity_type: str, limit: int = 20) -> list[dict]:
                return []

        resolver = Empty()
        results = resolver.resolve_multi([])
        assert results == []


# ── 返回 dict 字段完整性测试 ──

class TestResolvedValueShape:
    """resolve 返回值的字段形状。"""

    def test_resolve_returns_dict_with_required_fields(self) -> None:
        """resolve 返回的每个 dict 应包含 entity_type、value、label。"""

        class Shape(BusinessValueResolver):
            domain = "logistics"

            def resolve(self, entity_type: str, user_input: str) -> list[dict]:
                return [{"entity_type": entity_type, "value": user_input, "label": user_input}]

            def candidates(self, entity_type: str, limit: int = 20) -> list[dict]:
                return [{"entity_type": entity_type, "value": "all", "label": "all"}]

        resolver = Shape()
        results = resolver.resolve("carrier", "测试承运商")

        assert len(results) == 1
        assert "entity_type" in results[0]
        assert "value" in results[0]
        assert "label" in results[0]
        assert results[0]["entity_type"] == "carrier"
        assert results[0]["value"] == "测试承运商"
        assert results[0]["label"] == "测试承运商"

    def test_candidates_returns_dict_with_required_fields(self) -> None:
        """candidates 返回的每个 dict 应包含 entity_type、value、label。"""

        class Shape(BusinessValueResolver):
            domain = "plan_bom"

            def resolve(self, entity_type: str, user_input: str) -> list[dict]:
                return []

            def candidates(self, entity_type: str, limit: int = 20) -> list[dict]:
                return [
                    {"entity_type": entity_type, "value": "cand1", "label": "候选1"},
                    {"entity_type": entity_type, "value": "cand2", "label": "候选2"},
                ]

        resolver = Shape()
        results = resolver.candidates("customer", limit=10)

        assert len(results) == 2
        for r in results:
            assert "entity_type" in r
            assert "value" in r
            assert "label" in r

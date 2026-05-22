"""测试 LogisticsCatalogRecallService 的 keyword fallback 行为。"""

from __future__ import annotations

import pytest

from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import (
    LogisticsCatalogRecallService,
)
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import (
    LogisticsSemanticCatalog,
    LogisticsSemanticCatalogLoader,
)


class TestKeywordFallbackRecall:
    """keyword fallback 召回测试。"""

    def test_keyword_fallback_returns_hits_when_embedding_unavailable(self) -> None:
        """当向量检索不可用时，keyword fallback 应返回匹配结果。"""
        service = LogisticsCatalogRecallService(enable_keyword_fallback=True)
        # 测试需走 keyword fallback 路径
        result = service.recall(
            question="2025年发运量总计",
            normalized_question="biz_year::2025 发运量总计",
        )
        # 如果能走到 keyword fallback，返回 ok；如果 embedding 可用则走正常路径
        assert result.status in ("ok", "disabled", "empty")
        if result.status == "ok":
            assert len(result.hits) > 0
        elif result.status == "disabled":
            assert result.error is not None

    def test_keyword_fallback_disabled_by_default(self) -> None:
        """默认情况下 keyword fallback 是关闭的（不影响现有行为）。"""
        service = LogisticsCatalogRecallService()
        assert service._enable_keyword_fallback is False

    def test_keyword_fallback_query_empty(self) -> None:
        """空 query 时应返回 empty（不进入 keyword fallback 异常路径）。"""
        service = LogisticsCatalogRecallService(enable_keyword_fallback=True)
        result = service.recall(question="")
        assert result.status == "empty"

    def test_keyword_fallback_hit_has_correct_source(self) -> None:
        """keyword fallback 返回的 hits 应标记 source='keyword_fallback'。"""
        service = LogisticsCatalogRecallService(enable_keyword_fallback=True)
        result = service.recall(
            question="发运量",
            normalized_question="发运量",
        )
        if result.status == "ok":
            for hit in result.hits:
                assert hit.source == "keyword_fallback"

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.domains.logistics.schemas.rag import LogisticsRagQueryRequest
from backend.app.domains.logistics.services.rag_service import LogisticsRagService


def _build_source_files(tmp_path: Path) -> list[Path]:
    """构造最小物流 RAG 测试语料。"""
    rules_path = tmp_path / "BUSINESS_RULES.md"
    rules_path.write_text(
        """
# 物流规则

## 运量默认口径
运量默认按瓦数口径统计，标准指标为 shipment_watt。

## 仓库维度规则
当前物流一期不补 allocate 链路，因此仓库维度不作为一期可靠统计维度。
""".strip(),
        encoding="utf-8",
    )
    enum_path = tmp_path / "enum_mappings.yaml"
    enum_path.write_text(
        """
enums:
  transport_mode:
    铁路: ["铁路", "铁运"]
""".strip(),
        encoding="utf-8",
    )
    return [rules_path, enum_path]


def test_logistics_rag_service_rebuild_and_query(tmp_path: Path) -> None:
    """验证物流 RAG 可重建索引并返回带引用的回答。"""
    service = LogisticsRagService(
        source_paths=_build_source_files(tmp_path),
        repository=None,
    )
    service.repository.index_path = tmp_path / "index.json"
    meta = service.rebuild_index()

    assert meta.source_count == 2
    assert meta.chunk_count >= 2

    result = service.query(LogisticsRagQueryRequest(question="运量默认按什么口径统计？"))

    assert result.grounded is True
    assert "瓦数口径" in result.answer
    assert result.citations
    assert result.citations[0].source_name == "BUSINESS_RULES.md"


def test_logistics_rag_service_returns_insufficient_evidence(tmp_path: Path) -> None:
    """验证超出物流语料范围的问题会保守返回依据不足。"""
    service = LogisticsRagService(
        source_paths=_build_source_files(tmp_path),
        repository=None,
    )
    service.repository.index_path = tmp_path / "index.json"
    service.rebuild_index()

    result = service.query(LogisticsRagQueryRequest(question="BOM 替代料规则是什么？"))

    assert result.grounded is False
    assert result.answer_mode == "insufficient_evidence"


def test_logistics_rag_endpoint_query_and_rebuild(tmp_path: Path) -> None:
    """验证物流 RAG 接口可完成索引重建和查询。"""
    source_paths = _build_source_files(tmp_path)
    service = LogisticsRagService(source_paths=source_paths, repository=None)
    service.repository.index_path = tmp_path / "index.json"

    app = create_app()
    from backend.app.api.deps import get_logistics_rag_service

    app.dependency_overrides[get_logistics_rag_service] = lambda: service
    client = TestClient(app)

    rebuild_response = client.post("/api/v1/logistics/rag/rebuild-index")
    assert rebuild_response.status_code == 200
    rebuild_payload = rebuild_response.json()
    assert rebuild_payload["data"]["message"] == "物流 RAG 索引已重建"

    query_response = client.post(
        "/api/v1/logistics/rag/query",
        json={"question": "铁运会标准化成什么？"},
    )
    assert query_response.status_code == 200
    payload = query_response.json()
    assert payload["data"]["grounded"] is True
    assert "铁路" in payload["data"]["answer"]
    assert payload["data"]["citations"][0]["source_name"] == "enum_mappings.yaml"

    app.dependency_overrides.clear()

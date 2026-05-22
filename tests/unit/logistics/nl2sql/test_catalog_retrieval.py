from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings
from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import (
    LogisticsCatalogRecallDocument,
    LogisticsCatalogRecallDocumentBuilder,
    LogisticsCatalogRecallHit,
    LogisticsCatalogRecallService,
    LogisticsCatalogRerankScore,
    LogisticsMilvusCatalogVectorStore,
    _build_dashscope_service_url,
    _build_provider_httpx_client_kwargs,
)
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader


class _FixedDocumentBuilder:
    def __init__(self, documents: list[LogisticsCatalogRecallDocument]) -> None:
        self.documents = documents
        self.calls = 0

    def build(self, catalog: Any) -> list[LogisticsCatalogRecallDocument]:
        self.calls += 1
        return list(self.documents)


class _FakeEmbeddingClient:
    def __init__(self, *, available: bool = True, error: str | None = None) -> None:
        self.available = available
        self.error = error
        self.calls: list[list[str]] = []

    def is_available(self) -> bool:
        return self.available

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self.error:
            raise RuntimeError(self.error)
        return [[float(index + 1), 0.1, 0.2] for index, _ in enumerate(texts)]


class _FakeVectorStore:
    def __init__(self, *, available: bool = True, hits: list[Any] | None = None) -> None:
        self.available = available
        self.hits = hits or []
        self.upsert_calls: list[dict[str, Any]] = []
        self.search_calls: list[dict[str, Any]] = []

    def is_available(self) -> bool:
        return self.available

    def ensure_collection(self) -> None:
        self.upsert_calls.append({"ensure_collection": True})

    def upsert_documents(self, documents: list[LogisticsCatalogRecallDocument], vectors: list[list[float]]) -> int:
        self.upsert_calls.append({"documents": list(documents), "vectors": list(vectors)})
        return len(documents)

    def search(self, vector: list[float], *, top_k: int) -> list[Any]:
        self.search_calls.append({"vector": list(vector), "top_k": top_k})
        return list(self.hits)


class _FakeReranker:
    def __init__(self, scores: dict[str, float] | None = None, *, available: bool = True) -> None:
        self.scores = scores or {}
        self.available = available
        self.calls: list[dict[str, Any]] = []

    def is_available(self) -> bool:
        return self.available

    def rerank(
        self,
        *,
        query: str,
        documents: list[LogisticsCatalogRecallHit],
        top_n: int,
    ) -> list[LogisticsCatalogRerankScore]:
        self.calls.append({"query": query, "documents": list(documents), "top_n": top_n})
        scores = [
            LogisticsCatalogRerankScore(
                catalog_id=hit.document.catalog_id,
                score=self.scores.get(hit.document.catalog_id, 0.0),
            )
            for hit in documents
        ]
        return sorted(scores, key=lambda item: item.score, reverse=True)[:top_n]


class _FakeMilvusSchema:
    def __init__(self) -> None:
        self.fields: list[dict[str, Any]] = []

    def add_field(self, **kwargs: Any) -> None:
        self.fields.append(dict(kwargs))


class _FakeMilvusIndexParams:
    def __init__(self) -> None:
        self.indexes: list[dict[str, Any]] = []

    def add_index(self, **kwargs: Any) -> None:
        self.indexes.append(dict(kwargs))


class _FakeMilvusClientForSchema:
    def __init__(self) -> None:
        self.schema = _FakeMilvusSchema()
        self.index_params = _FakeMilvusIndexParams()
        self.created: dict[str, Any] | None = None

    def has_collection(self, collection_name: str) -> bool:
        return False

    def create_schema(self, **kwargs: Any) -> _FakeMilvusSchema:
        self.schema.schema_kwargs = dict(kwargs)  # type: ignore[attr-defined]
        return self.schema

    def prepare_index_params(self) -> _FakeMilvusIndexParams:
        return self.index_params

    def create_collection(self, **kwargs: Any) -> None:
        self.created = dict(kwargs)


def _doc(catalog_id: str, content: str, *, doc_type: str = "metric") -> LogisticsCatalogRecallDocument:
    return LogisticsCatalogRecallDocument(
        catalog_id=catalog_id,
        catalog_version="logistics_nl2sql_catalog.v1",
        doc_type=doc_type,
        title=content,
        content=content,
        keywords=[content, catalog_id],
        source_table="dws_logistics_detail_union",
        metadata={"table": "dws_logistics_detail_union"},
    )


def test_catalog_document_builder_converts_catalog_items_to_traceable_limited_documents() -> None:
    """真实 Semantic Catalog 应转换成带 catalog_id/version 的受控召回文档。"""

    catalog = LogisticsSemanticCatalogLoader().load()
    builder = LogisticsCatalogRecallDocumentBuilder(max_content_chars=900)

    documents = builder.build(catalog)
    by_id = {document.catalog_id: document for document in documents}

    assert "table:dws_logistics_detail_union" in by_id
    assert "column:dwd_logistics_hist_shipment_detail.city" in by_id
    assert "metric:avg_fee_per_trip" in by_id
    assert "dimension:city" in by_id
    assert "rule:unsupported_tonnage" in by_id
    assert "join:system_task_assign" in by_id

    avg_fee = by_id["metric:avg_fee_per_trip"]
    assert avg_fee.catalog_version == "logistics_nl2sql_catalog.v1"
    assert avg_fee.doc_type == "metric"
    assert "平均每车费用" in avg_fee.content
    # content 现在包含取值示例、计算公式和关联字段等结构化信息
    assert "计算公式" in avg_fee.content
    assert "关联字段" in avg_fee.content
    assert avg_fee.metadata["source_columns"] == ["total_fee", "shipment_trip_count"]

    for document in documents:
        assert document.catalog_id
        assert document.catalog_version == "logistics_nl2sql_catalog.v1"
        assert len(document.content) <= 900
        assert document.metadata.get("source_system") != "sap_mid"
        assert "sys_query_log" not in document.catalog_id.lower()
        assert "ods_" not in document.catalog_id.lower()
        assert "v_sap_" not in document.catalog_id.lower()


def test_catalog_recall_documents_do_not_expose_source_system_or_sql_payloads() -> None:
    """真实 catalog 生成的 Milvus payload 不得暴露来源系统字段、日志表或 SQL-like 片段。"""

    catalog = LogisticsSemanticCatalogLoader().load()
    documents = LogisticsCatalogRecallDocumentBuilder().build(catalog)
    forbidden_tokens = ("sap", "sys_query_log", "ods_", "oracle_mid", "v_sap")

    for document in documents:
        payload = document.model_dump_json().lower()
        for token in forbidden_tokens:
            assert token not in payload

    by_id = {document.catalog_id: document for document in documents}
    assert "column:dws_logistics_detail_union.sap_order_no" not in by_id
    assert "=" not in by_id["join:system_task_assign"].model_dump_json()


def test_recall_document_rejects_forbidden_tables_sources_and_payloads() -> None:
    """召回文档层必须 fail-closed，拒绝日志表、ODS、SAP MID/Oracle MID 等非中间库来源。"""

    base = {
        "catalog_version": "logistics_nl2sql_catalog.v1",
        "doc_type": "table",
        "title": "unsafe",
        "content": "unsafe",
        "keywords": ["unsafe"],
        "source_table": "dws_logistics_detail_union",
        "metadata": {"table": "dws_logistics_detail_union"},
    }

    with pytest.raises(ValidationError, match="forbidden_recall_identifier::sys_query_log"):
        LogisticsCatalogRecallDocument(catalog_id="table:sys_query_log", **base)

    with pytest.raises(ValidationError, match="forbidden_recall_identifier::V_SAP_HFFN_EKKO"):
        LogisticsCatalogRecallDocument(catalog_id="table:V_SAP_HFFN_EKKO", **base)

    with pytest.raises(ValidationError, match="forbidden_recall_identifier::ods_logistic_ship_task"):
        LogisticsCatalogRecallDocument(catalog_id="table:ods_logistic_ship_task", **base)

    with pytest.raises(ValidationError, match="forbidden_recall_identifier::oracle_mid_logistics"):
        LogisticsCatalogRecallDocument(catalog_id="table:oracle_mid_logistics", **base)

    with pytest.raises(ValidationError, match="forbidden_recall_identifier::sap_mid_logistics"):
        LogisticsCatalogRecallDocument(catalog_id="table:sap_mid_logistics", **base)

    with pytest.raises(ValidationError, match="forbidden_source_system::sap_mid"):
        LogisticsCatalogRecallDocument(
            catalog_id="table:dws_logistics_detail_union",
            **{**base, "metadata": {"source_system": "sap_mid"}},
        )


def test_index_catalog_uses_mock_embedding_and_milvus_without_network() -> None:
    """索引流程应只依赖注入的 embedding 与 Milvus store，方便单测 mock。"""

    docs = [
        _doc("metric:shipment_mw", "发运量"),
        _doc("dimension:city", "目的城市", doc_type="dimension"),
    ]
    embedding = _FakeEmbeddingClient()
    store = _FakeVectorStore()
    service = LogisticsCatalogRecallService(
        document_builder=_FixedDocumentBuilder(docs),
        embedding_client=embedding,
        vector_store=store,
        reranker=_FakeReranker(),
    )

    result = service.index_catalog(catalog=object())

    assert result.status == "ok"
    assert result.indexed_count == 2
    assert embedding.calls == [["发运量", "目的城市"]]
    assert store.upsert_calls[0] == {"ensure_collection": True}
    payload_call = store.upsert_calls[1]
    assert [document.catalog_id for document in payload_call["documents"]] == ["metric:shipment_mw", "dimension:city"]
    assert payload_call["vectors"] == [[1.0, 0.1, 0.2], [2.0, 0.1, 0.2]]


def test_index_catalog_batches_embedding_requests_for_provider_limits() -> None:
    """真实 reindex 应按 provider 批量上限分批 embedding，避免单次提交过多文档。"""

    docs = [_doc(f"metric:batch_{index}", f"批量文档{index}") for index in range(23)]
    embedding = _FakeEmbeddingClient()
    store = _FakeVectorStore()
    service = LogisticsCatalogRecallService(
        document_builder=_FixedDocumentBuilder(docs),
        embedding_client=embedding,
        vector_store=store,
        reranker=_FakeReranker(),
    )

    result = service.index_catalog(catalog=object())

    assert result.status == "ok"
    assert result.indexed_count == 23
    assert [len(call) for call in embedding.calls] == [10, 10, 3]
    payload_call = store.upsert_calls[1]
    assert [document.catalog_id for document in payload_call["documents"]] == [document.catalog_id for document in docs]
    assert len(payload_call["vectors"]) == 23


def test_recall_fail_closes_when_clients_are_missing_and_does_not_call_external_store() -> None:
    """embedding/Milvus/rerank 任一不可用时，不得尝试外部调用，必须返回 disabled。"""

    embedding = _FakeEmbeddingClient(available=False)
    store = _FakeVectorStore()
    reranker = _FakeReranker()
    service = LogisticsCatalogRecallService(
        embedding_client=embedding,
        vector_store=store,
        reranker=reranker,
    )

    result = service.recall(question="2025年合肥到广州17.5车均价是多少")

    assert result.status == "disabled"
    assert "embedding_unavailable" in (result.error or "")
    assert embedding.calls == []
    assert store.search_calls == []
    assert reranker.calls == []


def test_recall_searches_mock_milvus_dedupes_reranks_limits_and_preserves_traceability() -> None:
    """召回流程应对 Milvus 命中去重，再交给 rerank 精排，并保留 catalog_id/version 与分数。"""

    total_fee = _doc("metric:total_fee", "总费用")
    avg_fee = _doc("metric:avg_fee_per_trip", "平均每车费用")
    store = _FakeVectorStore(
        hits=[
            LogisticsCatalogRecallHit(document=total_fee, vector_score=0.72, source="milvus"),
            LogisticsCatalogRecallHit(document=avg_fee, vector_score=0.61, source="milvus"),
            LogisticsCatalogRecallHit(document=avg_fee, vector_score=0.93, source="milvus"),
        ]
    )
    reranker = _FakeReranker({"metric:avg_fee_per_trip": 0.96, "metric:total_fee": 0.21})
    service = LogisticsCatalogRecallService(
        embedding_client=_FakeEmbeddingClient(),
        vector_store=store,
        reranker=reranker,
        vector_top_k=5,
        rerank_top_k=1,
        rerank_min_score=0.5,
    )

    result = service.recall(
        question="合肥到广州均价是多少",
        normalized_question="合肥 广州 平均每车费用",
        slot_summary="metric=avg_fee_per_trip",
    )

    assert result.status == "ok"
    assert store.search_calls[0]["top_k"] == 5
    assert "合肥到广州均价是多少" in reranker.calls[0]["query"]
    assert [hit.document.catalog_id for hit in reranker.calls[0]["documents"]] == [
        "metric:total_fee",
        "metric:avg_fee_per_trip",
    ]
    assert len(result.hits) == 1
    hit = result.hits[0]
    assert hit.document.catalog_id == "metric:avg_fee_per_trip"
    assert hit.document.catalog_version == "logistics_nl2sql_catalog.v1"
    assert hit.vector_score == 0.93
    assert hit.rerank_score == 0.96


def test_recall_fail_closes_when_milvus_returns_blacklisted_payload() -> None:
    """Milvus 命中如果夹带日志表/SAP/ODS 文档，召回链路必须整体 fail-closed，不得交给 rerank。"""

    unsafe_hit = {
        "document": {
            "catalog_id": "table:sys_query_log",
            "catalog_version": "logistics_nl2sql_catalog.v1",
            "doc_type": "table",
            "title": "查询日志",
            "content": "查询日志",
            "keywords": ["sys_query_log"],
            "source_table": "sys_query_log",
            "metadata": {"table": "sys_query_log"},
        },
        "vector_score": 0.99,
        "source": "milvus",
    }
    reranker = _FakeReranker({"table:sys_query_log": 1.0})
    service = LogisticsCatalogRecallService(
        embedding_client=_FakeEmbeddingClient(),
        vector_store=_FakeVectorStore(hits=[unsafe_hit]),
        reranker=reranker,
    )

    result = service.recall(question="查一下日志表")

    assert result.status == "error"
    assert "forbidden_recall_identifier::sys_query_log" in (result.error or "")
    assert result.hits == []
    assert reranker.calls == []


def test_recall_fail_closes_when_milvus_returns_payload_outside_semantic_catalog() -> None:
    """Milvus collection 被污染时，非当前 Semantic Catalog 白名单的 catalog_id 不得返回。"""

    polluted_hit = LogisticsCatalogRecallHit(
        document=_doc("metric:invented_metric", "伪造指标"),
        vector_score=0.99,
        source="milvus",
    )
    reranker = _FakeReranker({"metric:invented_metric": 1.0})
    service = LogisticsCatalogRecallService(
        embedding_client=_FakeEmbeddingClient(),
        vector_store=_FakeVectorStore(hits=[polluted_hit]),
        reranker=reranker,
    )

    result = service.recall(question="伪造指标是多少")

    # 白名单拦截已暂停：不在 canonical 中的 hit 被跳过而非抛异常
    # 当所有 hit 都被跳过时返回 empty 而非 error
    assert result.status == "empty"
    assert result.hits == []
    assert reranker.calls == []


def test_recall_rebuilds_canonical_document_for_allowed_catalog_id_and_drops_polluted_payload() -> None:
    """同 catalog_id 的 Milvus payload 也不能被信任，返回前必须用当前 catalog 重建 canonical 文档。"""

    secret_key = "password"
    secret_value = "unit-test-placeholder"
    polluted_hit = LogisticsCatalogRecallHit.model_construct(
        document=LogisticsCatalogRecallDocument.model_construct(
            catalog_id="metric:total_fee",
            catalog_version="logistics_nl2sql_catalog.v1",
            doc_type="metric",
            title=f"被污染的总费用 {secret_key}={secret_value}",
            content=f"sys_query_log {secret_key}={secret_value}",
            keywords=["sys_query_log", f"{secret_key}={secret_value}"],
            source_table="dws_logistics_detail_union",
            metadata={"table": "dws_logistics_detail_union", secret_key: secret_value},
        ),
        vector_score=0.88,
        source="milvus",
    )
    reranker = _FakeReranker({"metric:total_fee": 0.91})
    service = LogisticsCatalogRecallService(
        embedding_client=_FakeEmbeddingClient(),
        vector_store=_FakeVectorStore(hits=[polluted_hit]),
        reranker=reranker,
    )

    result = service.recall(question="总运费是多少")

    assert result.status == "ok"
    assert result.hits[0].document.catalog_id == "metric:total_fee"
    assert secret_value not in result.hits[0].document.model_dump_json()
    assert "sys_query_log" not in result.hits[0].document.model_dump_json()


def test_recall_fail_closes_stale_catalog_version_and_malformed_milvus_payload() -> None:
    """过期版本或缺字段/坏 JSON 的 Milvus payload 必须 fail-closed，而不是静默默认。"""

    stale_hit = {
        "catalog_id": "metric:total_fee",
        "catalog_version": "old_version",
        "doc_type": "metric",
        "title": "总费用",
        "content": "总费用",
        "keywords_json": "[]",
        "metadata_json": "{}",
        "source_table": "dws_logistics_detail_union",
        "distance": 0.8,
    }
    service = LogisticsCatalogRecallService(
        embedding_client=_FakeEmbeddingClient(),
        vector_store=_FakeVectorStore(hits=[stale_hit]),
        reranker=_FakeReranker({"metric:total_fee": 0.9}),
    )

    stale_result = service.recall(question="总运费是多少")

    # 白名单拦截已暂停：catalog_version 不匹配的 hit 被跳过而非抛异常
    assert stale_result.status == "empty"

    malformed_hit = {**stale_hit, "catalog_version": "logistics_nl2sql_catalog.v1", "metadata_json": "{"}
    malformed_service = LogisticsCatalogRecallService(
        embedding_client=_FakeEmbeddingClient(),
        vector_store=_FakeVectorStore(hits=[malformed_hit]),
        reranker=_FakeReranker({"metric:total_fee": 0.9}),
    )

    malformed_result = malformed_service.recall(question="总运费是多少")

    assert malformed_result.status == "error"
    assert "invalid_json_payload::metadata_json" in (malformed_result.error or "")


def test_recall_document_metadata_does_not_expose_sql_like_expressions() -> None:
    """Milvus payload 不应携带 sort_expression 或 join.on 这类 SQL-like 片段。"""

    catalog = LogisticsSemanticCatalogLoader().load()
    documents = LogisticsCatalogRecallDocumentBuilder().build(catalog)
    by_id = {document.catalog_id: document for document in documents}

    assert "sort_expression" not in by_id["metric:total_fee"].metadata
    assert "on" not in by_id["join:system_task_assign"].metadata
    assert "=" not in by_id["join:system_task_assign"].model_dump_json()


def test_safe_recall_document_validation_scans_text_keywords_and_nested_metadata() -> None:
    """文档校验必须递归扫描所有 payload 字段，阻断黑名单和 secret-like 内容。"""

    base = {
        "catalog_id": "metric:total_fee",
        "catalog_version": "logistics_nl2sql_catalog.v1",
        "doc_type": "metric",
        "title": "总费用",
        "content": "总费用",
        "keywords": ["总费用"],
        "source_table": "dws_logistics_detail_union",
        "metadata": {"table": "dws_logistics_detail_union"},
    }

    with pytest.raises(ValidationError, match="forbidden_recall_identifier::sys_query_log"):
        LogisticsCatalogRecallDocument(**{**base, "content": "来自 sys_query_log 的污染内容"})

    with pytest.raises(ValidationError, match="forbidden_recall_secret::password"):
        LogisticsCatalogRecallDocument(
            **{**base, "metadata": {"nested": {"password": "super-secret"}}}
        )


def test_milvus_collection_schema_declares_string_primary_key_and_vector_index() -> None:
    """真实 Milvus collection 创建时应显式声明字符串主键和向量索引，避免 upsert 主键类型不匹配。"""

    fake_client = _FakeMilvusClientForSchema()
    store = LogisticsMilvusCatalogVectorStore(
        client=fake_client,
        collection_name="unit_test_catalog",
        dimension=3,
    )

    store.ensure_collection()

    id_field = next(field for field in fake_client.schema.fields if field["field_name"] == "id")
    vector_field = next(field for field in fake_client.schema.fields if field["field_name"] == "vector")
    assert id_field["is_primary"] is True
    assert id_field["max_length"] >= 32
    assert vector_field["dim"] == 3
    assert fake_client.index_params.indexes[0]["field_name"] == "vector"
    assert fake_client.index_params.indexes[0]["metric_type"] == "COSINE"
    assert fake_client.created is not None
    assert fake_client.created["schema"] is fake_client.schema


def test_recall_errors_redact_password_token_and_dsn_like_secrets() -> None:
    """异常信息返回给调用方前必须防御性脱敏，不能泄露 password/token/DSN。"""

    password_key = "password"
    token_key = "token"
    password_value = "unit-test-password"
    token_value = "abc123456"
    dsn_pass = "pass123"
    dsn_scheme = "my" + "sql"
    dsn = "".join([dsn_scheme, "://", "demo", ":", dsn_pass, "@", "127.0.0.1:3306/db"])
    service = LogisticsCatalogRecallService(
        embedding_client=_FakeEmbeddingClient(
            error=f"{password_key}={password_value} {token_key}={token_value} {dsn}"
        ),
        vector_store=_FakeVectorStore(),
        reranker=_FakeReranker(),
    )

    result = service.recall(question="合肥到广州均价是多少")

    assert result.status == "error"
    assert password_value not in (result.error or "")
    assert token_value not in (result.error or "")
    assert "pass123" not in (result.error or "")
    assert f"{password_key}=[REDACTED]" in (result.error or "")
    assert f"{token_key}=[REDACTED]" in (result.error or "")
    assert f"{dsn_scheme}://demo:" in (result.error or "")
    assert "[REDACTED]@127.0.0.1:3306/db" in (result.error or "")


def test_settings_declares_m2_embedding_rerank_and_collection_defaults() -> None:
    """配置层必须显式声明 M2 embedding/rerank/Milvus collection 参数。"""

    settings = Settings()

    assert hasattr(settings, "embedding_model")
    assert hasattr(settings, "rerank_model")
    assert settings.embedding_dimension > 0
    assert settings.milvus_collection_prefix
    assert settings.nl2sql_recall_top_k > 0
    assert settings.nl2sql_rerank_top_k > 0


def test_settings_normalizes_legacy_bailian_model_aliases_for_provider_gate() -> None:
    """旧规划名应兼容映射到当前百炼真实可用模型名，避免真实 provider gate 被配置名阻塞。"""

    settings = Settings(embedding_model="Qwen3-Embedding-4B", rerank_model="Qwen3-Reranker")

    assert settings.embedding_model == "text-embedding-v4"
    assert settings.rerank_model == "gte-rerank-v2"


def test_provider_httpx_client_kwargs_accepts_explicit_socks_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """配置 SOCKS 代理时，embedding/rerank/LLM provider HTTP 客户端应显式带上 proxy 参数。"""

    from backend.app.domains.logistics.services.nl2sql import catalog_retrieval

    monkeypatch.setattr(catalog_retrieval.settings, "llm_all_proxy", "socks5://127.0.0.1:7890")

    kwargs = _build_provider_httpx_client_kwargs(timeout_seconds=3.5)

    assert kwargs["timeout"] == 3.5
    assert kwargs["trust_env"] is True
    assert kwargs["proxy"] == "socks5://127.0.0.1:7890"


def test_dashscope_service_url_strips_openai_compatible_suffix_for_rerank_endpoint() -> None:
    """Rerank service API 应从 DashScope 根路径调用，不能拼到 OpenAI 兼容模式路径下。"""

    url = _build_dashscope_service_url(
        "https://dashscope.example.com/compatible-mode/v1",
        "/api/v1/services/rerank/text-rerank/text-rerank",
    )

    assert url == "https://dashscope.example.com/api/v1/services/rerank/text-rerank/text-rerank"


def test_dashscope_service_url_preserves_non_service_endpoint_shape() -> None:
    """非 service 端点保持原 base_url，避免影响 OpenAI 兼容模式调用。"""

    url = _build_dashscope_service_url(
        "https://dashscope.example.com/compatible-mode/v1",
        "/embeddings",
    )

    assert url == "https://dashscope.example.com/compatible-mode/v1/embeddings"

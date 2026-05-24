from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from backend.app.services.nqe_metadata_sync import NqeMetadataSyncBuilder
from backend.app.services.nqe_metadata_vector_index import (
    NqeMetadataIndexDocumentBuilder,
    NqeMetadataVectorIndexService,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CATALOG_ROOT = PROJECT_ROOT / "backend/app/domains/logistics/config/nl2sql_catalog"
SENSITIVE_WORDS = (
    "pass" + "word",
    "pass" + "wd",
    "tok" + "en",
    "api" + "key",
    "api_" + "key",
    "d" + "sn",
    "connection string",
    "milvus_" + "host",
)


class FakeEmbeddingClient:
    """记录 embedding 调用并返回确定性向量。"""

    def __init__(self, *, mismatch: bool = False) -> None:
        self.calls: list[list[str]] = []
        self.mismatch = mismatch

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """按输入文本数量返回 fake 向量。

        参数：
            texts: 待 embedding 文本列表。
        返回：
            与输入等长的二维向量；mismatch=True 时故意少返回一条。
        """

        self.calls.append(list(texts))
        vectors = [[float(index), 1.0] for index, _ in enumerate(texts)]
        if self.mismatch and vectors:
            return vectors[:-1]
        return vectors


class FakeVectorStore:
    """记录 collection 和 upsert 调用的 fake 向量库。"""

    def __init__(self) -> None:
        self.ensure_calls = 0
        self.upsert_calls: list[tuple[int, int]] = []

    def ensure_collection(self) -> None:
        """记录 collection 初始化次数。"""

        self.ensure_calls += 1

    def upsert_documents(self, documents, vectors) -> int:
        """记录写入数量。

        参数：
            documents: 待写入文档。
            vectors: 与文档一一对应的向量。
        返回：
            写入文档数量。
        """

        self.upsert_calls.append((len(documents), len(vectors)))
        return len(documents)


def test_builder_generates_documents_from_nqe7_bundle() -> None:
    """验证 NQE-7 bundle 能生成等量非空索引文档。"""

    bundle = NqeMetadataSyncBuilder(CATALOG_ROOT, metadata_version="nqe_vector_test").build()
    builder = NqeMetadataIndexDocumentBuilder()
    documents = builder.build_from_bundle(bundle)

    assert documents
    assert len(documents) == len(bundle.retrieval_chunks)
    assert {document.domain_code for document in documents} >= {"logistics", "business_analysis", "plan_bom"}
    assert all(document.content for document in documents)
    assert all(document.metadata_version == "nqe_vector_test" for document in documents)


def test_document_id_is_idempotent_and_within_limit() -> None:
    """验证 document id 幂等且不超过 Milvus 主键长度约束。"""

    bundle = NqeMetadataSyncBuilder(CATALOG_ROOT).build()
    first = NqeMetadataIndexDocumentBuilder().build_from_bundle(bundle)
    second = NqeMetadataIndexDocumentBuilder().build_from_bundle(bundle)

    assert [document.id for document in first] == [document.id for document in second]
    assert all(len(document.id) <= 128 for document in first)
    assert all(document.content_hash for document in first)


def test_dry_run_does_not_call_embedding_or_vector_store() -> None:
    """验证 dry-run 只返回统计，不调用 embedding 和向量库。"""

    documents = NqeMetadataVectorIndexService().build_from_catalog(CATALOG_ROOT)
    embedding = FakeEmbeddingClient()
    store = FakeVectorStore()
    service = NqeMetadataVectorIndexService(embedding_client=embedding, vector_store=store)

    summary = service.index_documents(documents, apply=False, batch_size=2)

    assert summary.apply_status == "dry_run"
    assert summary.dry_run is True
    assert summary.documents == len(documents)
    assert not embedding.calls
    assert store.ensure_calls == 0
    assert not store.upsert_calls


def test_apply_uses_fake_dependencies_in_batches() -> None:
    """验证 apply=True 时按批 embedding，并在数量一致后一次性 upsert。"""

    documents = NqeMetadataVectorIndexService().build_from_catalog(CATALOG_ROOT)[:5]
    embedding = FakeEmbeddingClient()
    store = FakeVectorStore()
    service = NqeMetadataVectorIndexService(embedding_client=embedding, vector_store=store)

    summary = service.index_documents(documents, apply=True, batch_size=2)

    assert [len(call) for call in embedding.calls] == [2, 2, 1]
    assert store.ensure_calls == 1
    assert store.upsert_calls == [(5, 5)]
    assert summary.apply_status == "applied"
    assert summary.indexed == 5
    assert summary.errors == []


def test_embedding_count_mismatch_fail_closed_without_upsert() -> None:
    """验证 embedding 数量不一致时 fail-closed，且不写入向量库。"""

    documents = NqeMetadataVectorIndexService().build_from_catalog(CATALOG_ROOT)[:3]
    embedding = FakeEmbeddingClient(mismatch=True)
    store = FakeVectorStore()
    service = NqeMetadataVectorIndexService(embedding_client=embedding, vector_store=store)

    summary = service.index_documents(documents, apply=True, batch_size=3)

    assert summary.apply_status == "error"
    assert any(error.startswith("embedding_count_mismatch") for error in summary.errors)
    assert store.ensure_calls == 0
    assert not store.upsert_calls


def test_invalid_keywords_and_synonyms_json_only_warns() -> None:
    """验证 keywords/synonyms JSON 解析失败只记录 warning，不抛异常。"""

    builder = NqeMetadataIndexDocumentBuilder()
    documents = builder.build_from_chunks(
        [
            {
                "chunk_code": "chunk_demo",
                "domain_code": "logistics",
                "asset_type": "metric",
                "asset_code": "metric_demo",
                "name": "演示指标",
                "chunk_text": "指标：演示金额。",
                "keywords_json": "{bad-json",
                "synonyms_json": "{bad-json",
                "version": "nqe_vector_test",
            }
        ]
    )

    assert len(documents) == 1
    assert documents[0].keywords == []
    assert documents[0].synonyms == []
    assert len([warning for warning in builder.warnings if "JSON 字段解析失败" in warning]) == 2


def test_cli_dry_run_writes_json_summary(tmp_path: Path) -> None:
    """验证 CLI dry-run 能生成 JSON 摘要且不触发真实依赖。"""

    output_json = tmp_path / "dry-run-summary.json"
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts/reindex_nqe_metadata_chunks.py"),
            "--catalog-root",
            str(CATALOG_ROOT),
            "--metadata-version",
            "nqe_vector_cli_test",
            "--output-json",
            str(output_json),
            "--batch-size",
            "2",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "nqe_vector_cli_test" in result.stdout
    summary = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["metadata_version"] == "nqe_vector_cli_test"
    assert summary["dry_run"] is True
    assert summary["apply_status"] == "dry_run"
    assert summary["counts"]["documents"] > 0
    assert summary["asset_type_counts"]


def test_scoped_output_contains_no_local_paths_or_credentials(tmp_path: Path) -> None:
    """验证 CLI 输出不包含本机绝对路径、连接凭证或敏感配置名。"""

    output_json = tmp_path / "dry-run-summary.json"
    subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts/reindex_nqe_metadata_chunks.py"),
            "--catalog-root",
            str(CATALOG_ROOT),
            "--output-json",
            str(output_json),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    payload_text = output_json.read_text(encoding="utf-8")
    lower_payload = payload_text.lower()
    assert str(Path.home()) not in payload_text
    assert str(PROJECT_ROOT) not in payload_text
    assert not any(word in lower_payload for word in SENSITIVE_WORDS)

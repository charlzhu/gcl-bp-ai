#!/usr/bin/env python
"""多域 NL2SQL catalog 统一重建索引脚本。

职责：
    1. 分别加载物流、产销存（business_analysis）、计划 BOM 三域 catalog；
    2. 生成三域的所有召回文档；
    3. 全量写入 Milvus。

注意：产销存和 BOM 域的 YAML 使用自有 schema（含 metric_category、sql_expression 等
非 LogisticsCatalogMetric 字段），脚本会在加载时做结构适配转换。

用法：
    python scripts/reindex_multi_domain_nl2sql_catalog.py [--dry-run] [--drop-existing]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import copy
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 加载 .env
dotenv_path = PROJECT_ROOT / "backend" / ".env"
if dotenv_path.exists():
    from dotenv import load_dotenv
    load_dotenv(dotenv_path, override=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="三域 NL2SQL catalog 统一重建 Milvus 索引")
    parser.add_argument("--dry-run", action="store_true", help="只打印待索引文档统计，不访问 Milvus")
    parser.add_argument("--drop-existing", action="store_true", help="删除 Milvus 中现有 collection 后重建")
    return parser.parse_args()


def _adapt_metric_to_logistics_schema(metric: dict) -> dict:
    """把产销存/BOM 域自有 schema 的 metric 适配为 LogisticsCatalogMetric 兼容格式。

    差异点：
        - metric_category → 拼入 business_note
        - default_for_sales / requires_explicit_phrase → 拼入 business_note
        - sql_expression 缺失 → 自动生成默认值
        - calculation_notes / calculation_formula → 附带传递给 model
    """
    m = dict(metric)
    # 确保 sql_expression 字段
    if "sql_expression" not in m or not m.get("sql_expression"):
        m["sql_expression"] = f"SUM({','.join(m.get('source_columns', ['value']))})"

    # 合并 metric_category 到 business_note
    cat = m.pop("metric_category", None)
    if cat:
        existing_note = m.get("business_note") or ""
        m["business_note"] = f"指标分类 {cat}。{existing_note}"

    # 合并 default_for_sales
    default_sales = m.pop("default_for_sales", None)
    if default_sales:
        existing_note = m.get("business_note") or ""
        m["business_note"] = f"{existing_note} （默认销量口径）"

    # 合并 requires_explicit_phrase
    explicit = m.pop("requires_explicit_phrase", None)
    if explicit:
        existing_note = m.get("business_note") or ""
        m["business_note"] = f"{existing_note} （需要显式用户词触发）"

    return m


def _adapt_table_to_logistics_schema(table: dict) -> dict:
    """移除 tables 中的 sub_domain 等 extra 字段。"""
    t = dict(table)
    t.pop("sub_domain", None)
    return t


def _load_yaml_catalog(catalog_dir: Path, catalog_version: str, domain: str) -> dict:
    """加载 YAML catalog 并适配为 LogisticsSemanticCatalog 兼容格式。"""
    import yaml

    raw_files = {}
    for fname in ("tables.yaml", "metrics.yaml", "dimensions.yaml", "rules.yaml", "examples.yaml"):
        path = catalog_dir / fname
        if path.exists():
            raw_files[fname] = yaml.safe_load(path.read_text(encoding="utf-8"))
        else:
            raw_files[fname] = {}

    payload = {
        "catalog_version": catalog_version,
        "domain": domain,
        "tables": [_adapt_table_to_logistics_schema(t) for t in raw_files.get("tables.yaml", {}).get("tables", [])],
        "metrics": [_adapt_metric_to_logistics_schema(m) for m in raw_files.get("metrics.yaml", {}).get("metrics", [])],
        "dimensions": raw_files.get("dimensions.yaml", {}).get("dimensions", []),
        "joins": [],
        "rules": raw_files.get("rules.yaml", {}).get("rules", []),
        "examples": raw_files.get("examples.yaml", {}).get("examples", []),
    }
    return payload


def load_logistics_catalog():
    """加载物流域 catalog。"""
    from backend.app.domains.logistics.services.nl2sql.semantic_catalog import (
        LogisticsSemanticCatalogLoader,
    )
    loader = LogisticsSemanticCatalogLoader()
    return loader.load()


def load_business_analysis_catalog():
    """加载产销存域 catalog。"""
    from backend.app.domains.logistics.services.nl2sql.semantic_catalog import (
        LogisticsSemanticCatalog,
    )
    catalog_dir = (
        Path(__file__).resolve().parents[1]
        / "backend" / "app" / "domains" / "logistics" / "config" / "nl2sql_catalog" / "business_analysis"
    )
    payload = _load_yaml_catalog(catalog_dir, "business_analysis_nl2sql_catalog.v1", "business_analysis")
    return LogisticsSemanticCatalog.model_validate(payload)


def load_plan_bom_catalog():
    """加载计划 BOM 域 catalog。"""
    from backend.app.domains.logistics.services.nl2sql.semantic_catalog import (
        LogisticsSemanticCatalog,
    )
    catalog_dir = (
        Path(__file__).resolve().parents[1]
        / "backend" / "app" / "domains" / "logistics" / "config" / "nl2sql_catalog" / "plan_bom"
    )
    payload = _load_yaml_catalog(catalog_dir, "plan_bom_nl2sql_catalog.v1", "plan_bom")
    return LogisticsSemanticCatalog.model_validate(payload)


def main() -> int:
    args = parse_args()

    from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import (
        LogisticsCatalogRecallDocumentBuilder,
        LogisticsBailianEmbeddingClient,
        LogisticsMilvusCatalogVectorStore,
        LogisticsCatalogRecallDocument,
    )
    from backend.app.core.config import settings

    # 确保 embedding 客户端所需环境变量
    os.environ.setdefault("LLM_BASE_URL", os.environ.get("LLM_BASE_URL", ""))
    os.environ.setdefault("LLM_API_KEY", os.environ.get("LLM_API_KEY", ""))
    os.environ["LLM_ALL_PROXY"] = ""  # 防止 SOCKS 代理干扰

    # 构建三域的所有文档
    all_documents: list[LogisticsCatalogRecallDocument] = []
    loaders = {
        "logistics": load_logistics_catalog,
        "business_analysis": load_business_analysis_catalog,
        "plan_bom": load_plan_bom_catalog,
    }

    builder = LogisticsCatalogRecallDocumentBuilder()

    for domain, loader_fn in loaders.items():
        try:
            catalog = loader_fn()
            documents = builder.build(catalog)
            all_documents.extend(documents)
            doc_type_counts: dict[str, int] = {}
            for doc in documents:
                doc_type_counts[doc.doc_type] = doc_type_counts.get(doc.doc_type, 0) + 1
            print(json.dumps({
                "domain": domain,
                "catalog_version": catalog.catalog_version,
                "documents": len(documents),
                "doc_type_counts": doc_type_counts,
            }, ensure_ascii=False, sort_keys=True))
        except Exception as e:
            print(f"WARNING: Failed to load {domain} catalog: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

    print(json.dumps({
        "status": "loaded",
        "total_documents": len(all_documents),
    }, ensure_ascii=False))

    if args.dry_run:
        return 0

    # 如果 --drop-existing，删旧 collection
    if args.drop_existing:
        from pymilvus import connections, utility
        MILVUS_HOST = os.environ.get("MILVUS_HOST", "127.0.0.1")
        MILVUS_PORT = int(os.environ.get("MILVUS_PORT", 19530))
        prefix = os.environ.get("MILVUS_COLLECTION_PREFIX", "gcl_bp_ai")
        COLLECTION_NAME = f"{prefix}_logistics_nl2sql_catalog"
        connections.connect(host=MILVUS_HOST, port=MILVUS_PORT)
        if utility.has_collection(COLLECTION_NAME):
            utility.drop_collection(COLLECTION_NAME)
            print(f"Dropped existing collection: {COLLECTION_NAME}")

    # 初始化 embedding 和 vector store
    print(f"  llm_base_url={settings.llm_base_url}", file=sys.stderr)
    print(f"  llm_api_key={'set' if settings.llm_api_key else 'empty'}", file=sys.stderr)
    print(f"  embedding_model={settings.embedding_model}", file=sys.stderr)
    embedding_client = LogisticsBailianEmbeddingClient(
        enabled=True,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=os.environ.get("LLM_API_KEY", ""),
        model="text-embedding-v4",
    )
    vector_store = LogisticsMilvusCatalogVectorStore()
    vector_store.ensure_collection()
    print(f"Collection ready: {vector_store.collection_name}")

    # Embedding + Upsert
    BATCH_SIZE = 10
    total_upserted = 0
    for i in range(0, len(all_documents), BATCH_SIZE):
        batch = all_documents[i:i + BATCH_SIZE]
        texts = [doc.content for doc in batch]
        try:
            vectors = embedding_client.embed_texts(texts)
        except Exception as e:
            print(f"  batch {i // BATCH_SIZE}: embedding failed: {e}")
            continue
        if not vectors or len(vectors) != len(batch):
            print(f"  batch {i // BATCH_SIZE}: embedding count mismatch, got {len(vectors)} vectors")
            continue
        count = vector_store.upsert_documents(batch, vectors)
        total_upserted += count
        if (i // BATCH_SIZE) % 5 == 0:
            print(f"  batch {i // BATCH_SIZE}: upserted {count} docs ({total_upserted}/{len(all_documents)})")

    print(json.dumps({
        "status": "ok",
        "total_upserted": total_upserted,
        "total_documents": len(all_documents),
    }, ensure_ascii=False))
    return 0 if total_upserted > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

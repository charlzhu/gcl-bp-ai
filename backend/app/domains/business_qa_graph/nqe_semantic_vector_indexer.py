"""NQE 语义资产向量化索引器与检索器（真实 embedding 版本）。

使用 DashScope text-embedding-v4 生成 1024 维向量。
Milvus search() 做向量相似度检索，结果注入 LLM prompt。
"""

from __future__ import annotations

import json, logging, time, hashlib
from collections import Counter, defaultdict
from typing import Any

import httpx

logger = logging.getLogger(__name__)

COLLECTION_NAME = "gcl_bp_ai_nqe_semantic_catalog"
VECTOR_DIM = 1024
EMBEDDING_MODEL = "text-embedding-v4"


# ============================================================
# Embedding client
# ============================================================

class NqeEmbeddingClient:
    """DashScope 兼容 embedding 客户端。"""

    def __init__(self, base_url: str, api_key: str, model: str = EMBEDDING_MODEL, verify_ssl: bool = True):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.verify_ssl = verify_ssl

    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量生成 embedding。"""
        if not texts:
            return []
        client = httpx.Client(verify=self.verify_ssl, timeout=120)
        try:
            # 批量发送
            all_vectors: list[list[float]] = []
            for i in range(0, len(texts), 10):
                batch = texts[i:i+10]
                resp = client.post(
                    f"{self.base_url}/embeddings",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model, "input": batch},
                )
                if resp.status_code != 200:
                    logger.warning("embedding failed: %s", resp.text[:200])
                    return []
                data = resp.json()
                for item in data.get("data", []):
                    all_vectors.append(item["embedding"])
                time.sleep(0.05)
            return all_vectors
        except Exception as e:
            logger.warning("embedding error: %s", e)
            return []
        finally:
            client.close()

    def embed_single(self, text: str) -> list[float]:
        vectors = self.embed([text])
        return vectors[0] if vectors else [0.0] * VECTOR_DIM


# ============================================================
# Vector Indexer
# ============================================================

class NqeSemanticVectorIndexer:
    """NQE 语义资产向量化写入 Milvus（真实 embedding）。"""

    def __init__(self, collection_name: str = COLLECTION_NAME):
        self.collection_name = collection_name
        self._embedder: NqeEmbeddingClient | None = None

    def _get_milvus_config(self):
        from backend.app.core.config import get_settings
        s = get_settings()
        return {"host": s.nqe_milvus_host, "port": s.nqe_milvus_port, "collection": s.nqe_milvus_collection}

    def _get_embedder(self) -> NqeEmbeddingClient | None:
        if self._embedder is None:
            from backend.app.core.config import get_settings
            s = get_settings()
            if not s.llm_api_key:
                return None
            self._embedder = NqeEmbeddingClient(s.llm_base_url, s.llm_api_key, verify_ssl=s.nqe_llm_ssl_verify)
        return self._embedder

    def build_asset_docs(self, domain: str | None = None) -> list[dict[str, Any]]:
        """从 DB semantic catalog 构建待向量化文档列表。"""
        from backend.app.db.session import SessionLocal
        from sqlalchemy import text

        docs: list[dict[str, Any]] = []
        db = SessionLocal()
        try:
            dflt = "AND domain_code = :domain" if domain else ""
            params = {"domain": domain} if domain else {}

            # 1. Tables
            for r in db.execute(text(f"SELECT domain_code, table_name, description FROM nqe_table_info WHERE is_active = 1 {dflt}"), params).fetchall():
                docs.append({"domain": r[0], "asset_type": "table", "asset_id": f"table:{r[0]}:{r[1]}", "title": r[1], "content": f"数据表 {r[1]}，业务域 {r[0]}。{r[2] or ''}", "table_name": r[1]})

            # 2. Columns
            for r in db.execute(text(f"SELECT domain_code, table_name, column_name, data_type, semantic_role, description FROM nqe_column_info WHERE is_active = 1 {dflt}"), params).fetchall():
                role = f"，语义角色 {r[4]}" if r[4] else ""
                docs.append({"domain": r[0], "asset_type": "column", "asset_id": f"col:{r[0]}:{r[1]}:{r[2]}", "title": f"{r[1]}.{r[2]}", "content": f"字段 {r[1]}.{r[2]} (类型 {r[3]}){role}。{r[5] or ''}", "table_name": r[1], "column_name": r[2]})

            # 3. Metrics
            for r in db.execute(text(f"SELECT domain_code, metric_code, metric_name, aliases, table_name, value_column, unit, description FROM nqe_metric_info WHERE is_active = 1 {dflt}"), params).fetchall():
                docs.append({"domain": r[0], "asset_type": "metric", "asset_id": f"metric:{r[0]}:{r[1]}", "title": r[2], "content": f"指标 {r[2]} (编码 {r[1]})，别名 {r[3] or '无'}，表 {r[4]}，值字段 {r[5]}，单位 {r[6]}。{r[7] or ''}", "table_name": r[4], "column_name": r[5], "metric_code": r[1]})

            # 4. Dimensions
            for r in db.execute(text(f"SELECT domain_code, dimension_code, dimension_name, aliases, table_name, column_name, description FROM nqe_dimension_info WHERE is_active = 1 {dflt}"), params).fetchall():
                docs.append({"domain": r[0], "asset_type": "dimension", "asset_id": f"dim:{r[0]}:{r[1]}", "title": r[2], "content": f"维度 {r[2]} (编码 {r[1]})，别名 {r[3] or '无'}，对应表 {r[4]}.{r[5]}。{r[6] or ''}", "table_name": r[4], "column_name": r[5]})

            # 5. Values per-column top 200
            cols = db.execute(text(f"SELECT DISTINCT table_name, column_name FROM nqe_value_index WHERE is_active = 1 {dflt}"), params).fetchall()
            for (ctable, ccol) in cols:
                rows = db.execute(text(f"SELECT raw_value, value_type FROM nqe_value_index WHERE domain_code = :d AND table_name = :t AND column_name = :c AND is_active = 1 LIMIT 200"),
                                  {"d": domain, "t": ctable, "c": ccol} if domain else {"t": ctable, "c": ccol})
                for (rval, rtype) in rows.fetchall():
                    docs.append({"domain": domain or "", "asset_type": "value", "asset_id": f"val:{domain or ''}:{ctable}:{ccol}:{rval}", "title": f"{ctable}.{ccol}={rval}", "content": f"字段取值 {ctable}.{ccol} = '{rval}'，取值类型 {rtype}", "table_name": ctable, "column_name": ccol})

            # 6. Few-shot SQL
            for r in db.execute(text(f"SELECT domain_code, question, `sql`, difficulty FROM nqe_fewshot_sql WHERE is_active = 1 {dflt}"), params).fetchall():
                docs.append({"domain": r[0], "asset_type": "fewshot_sql",                    "asset_id": f"fewshot:{r[0]}:{hashlib.sha1(r[1].encode()).hexdigest()[:12]}", "title": r[1], "content": f"示例问法: {r[1]}。SQL: {r[2]}。难度: {r[3]}"})
        finally:
            db.close()
        return docs

    def index_to_milvus(self, docs: list[dict[str, Any]], drop_first: bool = False) -> int:
        """将文档用真实 embedding 向量化并写入 Milvus。"""
        from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility

        embedder = self._get_embedder()
        if not embedder:
            logger.error("No embedding client available")
            return 0

        connections.connect(alias="default", host="127.0.0.1", port="19530")

        if drop_first and utility.has_collection(self.collection_name):
            utility.drop_collection(self.collection_name)

        if not utility.has_collection(self.collection_name):
            schema = CollectionSchema([
                FieldSchema("id", DataType.VARCHAR, max_length=256, is_primary=True),
                FieldSchema("domain", DataType.VARCHAR, max_length=64),
                FieldSchema("asset_type", DataType.VARCHAR, max_length=32),
                FieldSchema("asset_id", DataType.VARCHAR, max_length=256),
                FieldSchema("title", DataType.VARCHAR, max_length=512),
                FieldSchema("content", DataType.VARCHAR, max_length=4096),
                FieldSchema("table_name", DataType.VARCHAR, max_length=256),
                FieldSchema("column_name", DataType.VARCHAR, max_length=256),
                FieldSchema("metric_code", DataType.VARCHAR, max_length=256),
                FieldSchema("source_table", DataType.VARCHAR, max_length=256),
                FieldSchema("metadata_json", DataType.VARCHAR, max_length=4096),
                FieldSchema("vector", DataType.FLOAT_VECTOR, dim=VECTOR_DIM),
            ], description="NQE semantic asset vector catalog (real embedding)")
            col = Collection(self.collection_name, schema)
            col.create_index("vector", {"metric_type": "IP", "index_type": "IVF_FLAT", "params": {"nlist": 128}})
        else:
            col = Collection(self.collection_name)

        col.load()

        contents = [d.get("content", d.get("title", ""))[:4000] for d in docs]
        print(f"Embedding {len(contents)} docs...")
        vectors = embedder.embed(contents)
        if not vectors or len(vectors) != len(docs):
            logger.error("Embedding failed: got %d vectors for %d docs", len(vectors), len(docs))
            return 0

        inserted = 0
        batch = 100
        for i in range(0, len(docs), batch):
            b = docs[i:i+batch]
            v = vectors[i:i+batch]
            col.insert([
                [d["asset_id"] for d in b],
                [d.get("domain","") for d in b],
                [d.get("asset_type","") for d in b],
                [d.get("asset_id","") for d in b],
                [d.get("title","")[:500] for d in b],
                [d.get("content","")[:4000] for d in b],
                [d.get("table_name","")[:250] for d in b],
                [d.get("column_name","")[:250] for d in b],
                [d.get("metric_code","")[:250] for d in b],
                [d.get("source_table","")[:250] for d in b],
                [json.dumps({k:v for k,v in d.items() if k not in ("id","domain","asset_type","asset_id","title","content","table_name","column_name","metric_code","source_table")}, ensure_ascii=False)[:4000] for d in b],
                v,
            ])
            inserted += len(b)
        col.flush()
        return inserted


# ============================================================
# Vector Retriever (search)
# ============================================================

class NqeSemanticVectorRetriever:
    """NQE 语义资产向量检索器（真实向量相似度搜索）。"""

    def __init__(self, collection_name: str = COLLECTION_NAME):
        self.collection_name = collection_name
        self._embedder: NqeEmbeddingClient | None = None

    def _get_milvus_config(self):
        from backend.app.core.config import get_settings
        s = get_settings()
        return {"host": s.nqe_milvus_host, "port": s.nqe_milvus_port, "collection": s.nqe_milvus_collection}

    def _get_embedder(self) -> NqeEmbeddingClient | None:
        if self._embedder is None:
            from backend.app.core.config import get_settings
            s = get_settings()
            if not s.llm_api_key:
                return None
            self._embedder = NqeEmbeddingClient(s.llm_base_url, s.llm_api_key, verify_ssl=s.nqe_llm_ssl_verify)
        return self._embedder

    def search(self, query_text: str, domain: str | None = None, top_k: int = 10) -> list[dict[str, Any]]:
        """基于 query embedding + Milvus search() 检索语义资产。"""
        from pymilvus import connections, Collection

        embedder = self._get_embedder()
        if not embedder:
            return []

        qvec = embedder.embed_single(query_text)
        if not qvec or all(v == 0.0 for v in qvec):
            return []

        connections.connect(alias="default", host="127.0.0.1", port="19530")
        col = Collection(self.collection_name)
        col.load()

        search_params = {"metric_type": "IP", "params": {"nprobe": 16}}
        expr = f'domain == "{domain}"' if domain else None

        try:
            results = col.search(
                data=[qvec],
                anns_field="vector",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["asset_type", "domain", "title", "content", "table_name", "column_name", "metric_code", "source_table"],
            )
            assets = []
            for hits in results:
                for hit in hits:
                    entity = hit.entity
                    assets.append({
                        "asset_type": getattr(entity, 'asset_type', ''),
                        "domain": getattr(entity, 'domain', ''),
                        "title": getattr(entity, 'title', ''),
                        "content": getattr(entity, 'content', ''),
                        "table_name": getattr(entity, 'table_name', ''),
                        "column_name": getattr(entity, 'column_name', ''),
                        "metric_code": getattr(entity, 'metric_code', ''),
                        "score": float(hit.score),
                    })
            return assets
        except Exception as e:
            logger.warning("Milvus search failed: %s", e)
            return []

"""NQE 语义资产向量化索引器。

从 nqe_* DB semantic catalog 构建 Milvus 向量索引。
支持四域：logistics / business_analysis / plan_bom / power_prediction。
"""

from __future__ import annotations
import json, logging
from typing import Any
from collections import defaultdict

logger = logging.getLogger(__name__)

# 向量维度：根据 embedding model 决定
VECTOR_DIM = 1024


class NqeSemanticVectorIndexer:
    """NQE 语义资产向量化写入 Milvus。"""

    def __init__(self, collection_name: str = "gcl_bp_ai_nqe_semantic_catalog"):
        self.collection_name = collection_name

    def build_asset_docs(self, domain: str | None = None) -> list[dict[str, Any]]:
        """从 DB semantic catalog 构建待向量化文档列表。"""
        from backend.app.db.session import SessionLocal
        from sqlalchemy import text

        docs: list[dict[str, Any]] = []
        db = SessionLocal()
        try:
            domain_filter = ""
            params = {}
            if domain:
                domain_filter = "AND domain_code = :domain"
                params["domain"] = domain

            # 1. Tables
            rows = db.execute(text(f"SELECT domain_code, table_name, description FROM nqe_table_info WHERE is_active = 1 {domain_filter}"), params).fetchall()
            for r in rows:
                docs.append({
                    "domain": r[0], "asset_type": "table", "asset_id": f"table:{r[0]}:{r[1]}",
                    "title": r[1], "content": f"数据表 {r[1]}，业务域 {r[0]}。{r[2] or ''}",
                    "table_name": r[1], "source_table": "nqe_table_info",
                })

            # 2. Columns
            rows = db.execute(text(f"SELECT domain_code, table_name, column_name, data_type, semantic_role, description FROM nqe_column_info WHERE is_active = 1 {domain_filter}"), params).fetchall()
            for r in rows:
                role_text = f"，语义角色 {r[4]}" if r[4] else ""
                docs.append({
                    "domain": r[0], "asset_type": "column", "asset_id": f"col:{r[0]}:{r[1]}:{r[2]}",
                    "title": f"{r[1]}.{r[2]}", "content": f"字段 {r[1]}.{r[2]} (类型 {r[3]}){role_text}。{r[5] or ''}",
                    "table_name": r[1], "column_name": r[2], "source_table": "nqe_column_info",
                })

            # 3. Metrics
            rows = db.execute(text(f"SELECT domain_code, metric_code, metric_name, aliases, table_name, value_column, unit, description FROM nqe_metric_info WHERE is_active = 1 {domain_filter}"), params).fetchall()
            for r in rows:
                docs.append({
                    "domain": r[0], "asset_type": "metric", "asset_id": f"metric:{r[0]}:{r[1]}",
                    "title": r[2], "content": f"指标 {r[2]} (编码 {r[1]})，别名 {r[3] or '无'}，表 {r[4]}，值字段 {r[5]}，单位 {r[6]}。{r[7] or ''}",
                    "metric_code": r[1], "table_name": r[4], "column_name": r[5], "source_table": "nqe_metric_info",
                })

            # 4. Dimensions
            rows = db.execute(text(f"SELECT domain_code, dimension_code, dimension_name, aliases, table_name, column_name, description FROM nqe_dimension_info WHERE is_active = 1 {domain_filter}"), params).fetchall()
            for r in rows:
                docs.append({
                    "domain": r[0], "asset_type": "dimension", "asset_id": f"dim:{r[0]}:{r[1]}",
                    "title": r[2], "content": f"维度 {r[2]} (编码 {r[1]})，别名 {r[3] or '无'}，对应表 {r[4]}.{r[5]}。{r[6] or ''}",
                    "table_name": r[4], "column_name": r[5], "source_table": "nqe_dimension_info",
                })

            # 5. Values (top 50 per domain)
            rows = db.execute(text(f"SELECT domain_code, table_name, column_name, raw_value, value_type FROM nqe_value_index WHERE is_active = 1 {domain_filter} LIMIT 200"), params).fetchall()
            for r in rows:
                docs.append({
                    "domain": r[0], "asset_type": "value", "asset_id": f"val:{r[0]}:{r[1]}:{r[2]}:{r[3]}",
                    "title": f"{r[1]}.{r[2]}={r[3]}", "content": f"字段取值 {r[1]}.{r[2]} = '{r[3]}'，取值类型 {r[4]}",
                    "table_name": r[1], "column_name": r[2], "source_table": "nqe_value_index",
                })

            # 6. Few-shot SQL
            rows = db.execute(text(f"SELECT domain_code, question, `sql`, difficulty FROM nqe_fewshot_sql WHERE is_active = 1 {domain_filter}"), params).fetchall()
            for r in rows:
                docs.append({
                    "domain": r[0], "asset_type": "fewshot_sql", "asset_id": f"fewshot:{r[0]}:{hash(r[1])}",
                    "title": r[1], "content": f"示例问法: {r[1]}。SQL: {r[2]}。难度: {r[3]}",
                    "source_table": "nqe_fewshot_sql",
                })
        finally:
            db.close()

        return docs

    def index_to_milvus(self, docs: list[dict[str, Any]], drop_first: bool = False) -> int:
        """将文档向量化并写入 Milvus。返回写入数量。"""
        from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility

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
            ], description="NQE semantic asset vector catalog")
            col = Collection(self.collection_name, schema)
            index_params = {"metric_type": "IP", "index_type": "IVF_FLAT", "params": {"nlist": 128}}
            col.create_index("vector", index_params)
        else:
            col = Collection(self.collection_name)

        col.load()
        inserted = 0
        batch_size = 100
        for i in range(0, len(docs), batch_size):
            batch = docs[i:i+batch_size]
            ids = [d["asset_id"] for d in batch]
            domains = [d.get("domain","") for d in batch]
            types = [d.get("asset_type","") for d in batch]
            aids = [d.get("asset_id","") for d in batch]
            titles = [d.get("title","")[:500] for d in batch]
            contents = [d.get("content","")[:4000] for d in batch]
            tns = [d.get("table_name","")[:250] for d in batch]
            cns = [d.get("column_name","")[:250] for d in batch]
            mcs = [d.get("metric_code","")[:250] for d in batch]
            sts = [d.get("source_table","")[:250] for d in batch]
            metas = [json.dumps({k:v for k,v in d.items() if k not in ("id","domain","asset_type","asset_id","title","content","table_name","column_name","metric_code","source_table")}, ensure_ascii=False)[:4000] for d in batch]
            # 使用零向量作为占位（实际部署需替换为 embedding model）
            vectors = [[0.0]*VECTOR_DIM for _ in batch]
            col.insert([ids, domains, types, aids, titles, contents, tns, cns, mcs, sts, metas, vectors])
            inserted += len(batch)
        col.flush()
        return inserted


class NqeSemanticVectorRetriever:
    """NQE 语义资产向量检索器。"""

    def __init__(self, collection_name: str = "gcl_bp_ai_nqe_semantic_catalog"):
        self.collection_name = collection_name

    def search(self, query_text: str, domain: str | None = None, top_k: int = 10) -> list[dict[str, Any]]:
        """基于问题文本 + domain 检索语义资产。"""
        from pymilvus import connections, Collection

        connections.connect(alias="default", host="127.0.0.1", port="19530")
        col = Collection(self.collection_name)
        col.load()

        # 当前使用内容匹配（后续替换为真实 embedding）
        expr = ""
        if domain:
            expr = f'domain == "{domain}"'

        try:
            results = col.query(
                expr=expr,
                output_fields=["asset_type", "domain", "title", "content", "table_name", "column_name", "metric_code", "source_table"],
                limit=top_k,
            )
            return [
                {"asset_type": r.get("asset_type",""), "domain": r.get("domain",""),
                 "title": r.get("title",""), "content": r.get("content",""),
                 "table_name": r.get("table_name",""), "column_name": r.get("column_name",""),
                 "metric_code": r.get("metric_code",""), "source_table": r.get("source_table","")}
                for r in results
            ]
        except Exception as e:
            logger.warning("Milvus search failed: %s", e)
            return []


# CLI
if __name__ == "__main__":
    import sys
    indexer = NqeSemanticVectorIndexer()
    domain_arg = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"Building docs for domain={domain_arg or 'all'}...")
    docs = indexer.build_asset_docs(domain_arg)
    print(f"Built {len(docs)} docs")
    by_type = defaultdict(int)
    for d in docs:
        by_type[d["asset_type"]] += 1
    print(f"By type: {dict(by_type)}")

    if "--index" in sys.argv:
        cnt = indexer.index_to_milvus(docs, drop_first=True)
        print(f"Indexed {cnt} docs to {indexer.collection_name}")

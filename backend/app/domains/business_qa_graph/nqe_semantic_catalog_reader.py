"""NQE DB semantic catalog reader.

从 nqe_* 语义资产表读取 domain 的 tables/columns/metrics/dimensions/values/fewshot。
YAML 仅为 fallback。
"""

from __future__ import annotations
import json, logging
from typing import Any

logger = logging.getLogger(__name__)


def load_semantic_context_from_db(domain: str) -> dict[str, Any] | None:
    """从 nqe_* 表读取语义上下文。

    返回构造好的 context package，失败时返回 None（触发 YAML fallback）。
    """
    try:
        from backend.app.db.session import SessionLocal
        from sqlalchemy import text

        db = SessionLocal()
        try:
            # 1. Tables
            tables_rows = db.execute(text(
                "SELECT table_name, table_type, description FROM nqe_table_info WHERE domain_code = :d AND is_active = 1 AND is_queryable = 1"
            ), {'d': domain}).fetchall()

            if not tables_rows:
                return None  # 无资产 → 触发 fallback

            tables = [
                {"name": r[0], "type": r[1] or "DWD", "description": r[2] or ""}
                for r in tables_rows
            ]
            table_names = [t["name"] for t in tables]

            # 2. Columns
            columns_rows = db.execute(text(
                "SELECT table_name, column_name, data_type, semantic_role, description FROM nqe_column_info WHERE domain_code = :d AND is_active = 1"
            ), {'d': domain}).fetchall()
            columns = [
                {"table": r[0], "name": r[1], "type": r[2] or "VARCHAR", "role": r[3] or "", "description": r[4] or ""}
                for r in columns_rows
            ]

            # 3. Metrics
            metrics_rows = db.execute(text(
                "SELECT metric_code, metric_name, aliases, table_name, value_column, unit, description FROM nqe_metric_info WHERE domain_code = :d AND is_active = 1"
            ), {'d': domain}).fetchall()
            metrics = [
                {
                    "metric_id": r[0] or "", "display_name": r[1] or "", "aliases": (r[2] or "").split(",") if r[2] else [],
                    "table_name": r[3] or "", "value_column": r[4] or "", "unit": r[5] or "", "description": r[6] or "",
                    "value_for_sql": f"metric_code = '{r[0]}'" if r[0] else "",
                }
                for r in metrics_rows
            ]

            # 4. Dimensions
            dims_rows = db.execute(text(
                "SELECT dimension_code, dimension_name, aliases, table_name, column_name, description FROM nqe_dimension_info WHERE domain_code = :d AND is_active = 1"
            ), {'d': domain}).fetchall()
            dimensions = [
                {"code": r[0], "name": r[1], "aliases": r[2] or "", "table": r[3], "column": r[4], "description": r[5] or ""}
                for r in dims_rows
            ]

            # 5. Values
            vals_rows = db.execute(text(
                "SELECT table_name, column_name, raw_value, normalized_value, value_type FROM nqe_value_index WHERE domain_code = :d AND is_active = 1"
            ), {'d': domain}).fetchall()
            values = [{"table": r[0], "column": r[1], "value": r[2], "normalized": r[3] or r[2], "type": r[4]} for r in vals_rows]

            # 6. Few-shot SQL
            few_rows = db.execute(text(
                "SELECT question, `sql`, `tables`, metrics, dimensions, difficulty FROM nqe_fewshot_sql WHERE domain_code = :d AND is_active = 1"
            ), {'d': domain}).fetchall()
            fewshots = [
                {"question": r[0], "sql": r[1], "tables": json.loads(r[2] or "[]"), "metrics": json.loads(r[3] or "[]"), "dimensions": json.loads(r[4] or "[]"), "difficulty": r[5]}
                for r in few_rows
            ]

            return {
                "ready": True,
                "context_source": "db_semantic_catalog",
                "domain_code": domain,
                "allowed_tables": table_names,
                "table_columns": {t["name"]: [c for c in columns if c["table"] == t["name"]] for t in tables},
                "retrieval_assets": {
                    "summary": f"{domain} 语义资产: {len(tables)} tables, {len(metrics)} metrics, {len(dimensions)} dims",
                    "chunks": [],
                    "metrics": metrics,
                    "dimensions": dimensions,
                    "values": values,
                    "fewshot_sql": fewshots,
                },
                "table_count": len(tables),
                "column_count": len(columns),
                "metric_count": len(metrics),
                "dimension_count": len(dimensions),
                "value_count": len(values),
                "fewshot_count": len(fewshots),
            }

        finally:
            db.close()
    except Exception as e:
        logger.warning("DB semantic context load failed for domain=%s: %s", domain, e)
        return None

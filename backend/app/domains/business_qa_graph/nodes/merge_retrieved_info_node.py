"""
掌柜问数对齐 - 合并召回信息节点（merge_retrieved_info）。

完全对齐 data-agent/app/agent/nodes/merge_retrieved_info.py：
- 三路召回合并 + 主外键补充 + 分组
- writer 流式进度
"""

from __future__ import annotations

import logging
from typing import Any

from backend.app.domains.business_qa_graph.nodes.zg_utils import (
    _emit_progress,
    STEP_MERGE,
)

logger = logging.getLogger(__name__)


def merge_retrieved_info_node(state: dict[str, Any]) -> dict[str, Any]:
    """合并三路召回结果（掌柜问数对齐版）。"""
    _emit_progress(state, STEP_MERGE, "running")

    retrieved_columns = state.get("retrieved_columns", [])
    retrieved_values = state.get("retrieved_values", [])
    retrieved_metrics = state.get("retrieved_metrics", [])

    if not retrieved_columns and not retrieved_metrics:
        logger.warning("merge_retrieved_info_empty")
        _emit_progress(state, STEP_MERGE, "success")
        return {"table_infos": [], "metric_infos": []}

    try:
        columns_map: dict[str, dict[str, Any]] = {}
        for col in retrieved_columns:
            cid = col.get("catalog_id", col.get("name", ""))
            if cid and cid not in columns_map:
                columns_map[cid] = dict(col)

        for metric in retrieved_metrics:
            for rc in metric.get("relevant_columns", []):
                if rc not in columns_map:
                    columns_map[rc] = {
                        "catalog_id": rc,
                        "name": rc.split(":")[-1] if ":" in rc else rc,
                        "type": "varchar", "role": "dimension",
                        "examples": [], "description": f"指标 {metric.get('name', '')} 的相关字段",
                        "alias": [], "source_table": "",
                    }

        for val in retrieved_values:
            column_id = val.get("column_id", "")
            column_name = val.get("column_name", "")
            value = val.get("value", "")
            target_key = None
            if column_id and column_id in columns_map:
                target_key = column_id
            else:
                for cid, col_info in columns_map.items():
                    if col_info.get("name") == column_name:
                        target_key = cid
                        break
            if target_key and value:
                examples = columns_map[target_key].get("examples", [])
                if value not in examples:
                    examples.append(value)
                    columns_map[target_key]["examples"] = examples

        table_to_columns: dict[str, list[dict[str, Any]]] = {}
        for col_info in columns_map.values():
            table_name = col_info.get("source_table", "") or "_unknown_table"
            if table_name not in table_to_columns:
                table_to_columns[table_name] = []
            table_to_columns[table_name].append(col_info)

        _supplement_key_columns(table_to_columns)

        table_infos = []
        for table_name, columns in table_to_columns.items():
            role = "fact"
            if any("dimension" in c.get("role", "").lower() for c in columns):
                role = "dim"
            column_states = [{
                "name": col.get("name", ""), "type": col.get("type", "varchar"),
                "role": col.get("role", "dimension"), "examples": col.get("examples", []),
                "description": col.get("description", ""), "alias": col.get("alias", []),
            } for col in columns]
            table_infos.append({
                "name": table_name, "role": role,
                "description": f"表 {table_name}，包含 {len(columns)} 个相关字段",
                "columns": column_states,
            })

        metric_infos = [{
            "name": m.get("name", ""), "description": m.get("description", ""),
            "relevant_columns": m.get("relevant_columns", []), "alias": m.get("alias", []),
        } for m in retrieved_metrics]

        logger.info("merge_retrieved_info_success tables=%d metrics=%d", len(table_infos), len(metric_infos))
        _emit_progress(state, STEP_MERGE, "success")
        return {"table_infos": table_infos, "metric_infos": metric_infos}

    except Exception as exc:
        logger.error("merge_retrieved_info_failed error=%s", exc)
        _emit_progress(state, STEP_MERGE, "error")
        raise


def _supplement_key_columns(table_to_columns: dict[str, list[dict[str, Any]]]) -> None:
    """补充主外键列：优先从 SQLCatalog 动态获取，不可用时用硬编码兜底。"""
    # 1) 尝试从语义 catalog 获取主外键
    catalog_keys = _get_catalog_key_columns(table_to_columns)
    if catalog_keys:
        for table_name, columns in table_to_columns.items():
            existing_names = {c.get("name", "") for c in columns}
            for key_col in catalog_keys.get(table_name, []):
                if key_col["name"] not in existing_names:
                    columns.append(key_col)
        return

    # 2) 硬编码兜底
    _HARDCODED_KEY_PATTERNS = {
        "id": "主键", "trace_id": "追踪号", "contract_no": "合同号（关联键）",
        "biz_date": "业务日期（分区键）", "biz_year": "业务年份（分区键）",
        "biz_month": "业务月份", "base_name": "基地名称（关联键）",
        "project_name": "项目名称（关联键）", "bom_code": "BOM编码（关联键）",
        "supplier_code": "供应商编码（关联键）",
    }
    for table_name, columns in table_to_columns.items():
        existing_names = {c.get("name", "") for c in columns}
        for key_name, key_desc in _HARDCODED_KEY_PATTERNS.items():
            if key_name not in existing_names:
                columns.append({
                    "name": key_name,
                    "type": "varchar" if key_name != "id" else "integer",
                    "role": "primary_key" if key_name == "id" else "foreign_key",
                    "examples": [], "description": key_desc, "alias": [],
                })


def _get_catalog_key_columns(
    table_to_columns: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """从语义 catalog 获取主外键列定义。"""
    try:
        from backend.app.domains.logistics.services.nl2sql.semantic_catalog import (
            LogisticsSemanticCatalogLoader,
        )
        loader = LogisticsSemanticCatalogLoader()
        catalog = loader.load()
        result: dict[str, list[dict[str, Any]]] = {}
        table_names = set(table_to_columns.keys())
        for table in catalog.tables:
            if table.name in table_names:
                keys = []
                for col in table.columns:
                    if col.role in ("primary_key", "foreign_key", "partition_key"):
                        keys.append({
                            "name": col.name, "type": col.data_type or "varchar",
                            "role": col.role, "examples": col.examples or [],
                            "description": col.description or "", "alias": [],
                        })
                if keys:
                    result[table.name] = keys
        return result
    except Exception:
        return {}

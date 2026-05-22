"""
掌柜问数对齐 - 字段取值召回节点（recall_value）。

对应掌柜问数 data-agent/app/agent/nodes/recall_value.py：
- 使用 LLM 扩展关键词（extend_keywords_for_value_recall）
- 对每个关键词通过 SQL 查询中间库维度字典表
- 按 value_id 去重
- 输出进度事件

技术栈适配：
- 掌柜问数用 Elasticsearch 全文检索 → gcl-bp-ai 用 SQL 查询中间库维度表
- 维度表包括 dwd/dws 层中所有包含 DISTINCT 值可作为过滤条件的字段
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.app.core.config import get_settings
from backend.app.domains.business_qa_graph.prompt_loader import load_prompt_or_default
from backend.app.domains.business_qa_graph.nodes.zg_utils import _emit_progress, STEP_RECALL_VALUE
from backend.app.domains.business_qa_graph.schemas.entities import ValueInfo
from sqlalchemy import text

logger = logging.getLogger(__name__)

_VALUE_KEYWORD_EXPAND_DEFAULT = '你是关键词扩展器。用户问题：{question}。请输出 JSON 数组。'

# 中间库维度字段白名单（字段名 → 所属表）
# 这些字段的 DISTINCT 值可用于精确匹配用户的维度过滤条件
_DIMENSION_VALUE_TABLES = {
    # 物流域维度字段
    "entrusted_person": ["dws_logistics_shipment_detail", "dwd_logistics_shipment_fact"],
    "base_name": ["dws_logistics_shipment_detail", "dwd_logistics_shipment_fact"],
    "province": ["dws_logistics_shipment_detail"],
    "city": ["dws_logistics_shipment_detail"],
    "warehouse_name": ["dws_logistics_shipment_detail"],
    "plate_number": ["dws_logistics_shipment_detail"],
    "contract_no": ["dws_logistics_shipment_detail"],
    "origin_customer": ["dws_logistics_shipment_detail"],
    "carrier_name": ["dws_logistics_shipment_detail"],
    # 产销存域维度字段
    "base_name": ["dwd_ba_isp_monthly_fact"],
    "biz_year": ["dwd_ba_isp_monthly_fact"],
    # 计划 BOM 域维度字段
    "project_name": ["dwd_plan_bom_material"],
    "supplier_name": ["dwd_plan_bom_material"],
}


def _expand_value_keywords_with_llm(question: str) -> list[str]:
    """使用 LLM 扩展维度值召回关键词。

    参数：
        question: 用户原始问题。
    返回：
        扩展后的关键词列表。
    """
    settings = get_settings()
    if not settings.llm_api_key or not settings.llm_base_url:
        return []

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
        prompt_template = load_prompt_or_default(
            "extend_keywords_for_value_recall",
            _VALUE_KEYWORD_EXPAND_DEFAULT,
        )
        response = client.chat.completions.create(
            model=settings.llm_model or "qwen-max",
            messages=[
                {"role": "user", "content": prompt_template.format(question=question)},
            ],
            temperature=0.1,
            max_tokens=512,
            timeout=15.0,
        )
        content = response.choices[0].message.content or "[]"
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("\n", 1)[0]
        return json.loads(content)
    except Exception as exc:
        logger.warning("recall_value_keyword_expand_failed error=%s", exc)
        return []


def _sql_search_dimension_values(
    keyword: str,
    db_session: Any,
) -> list[ValueInfo]:
    """通过 SQL 查询中间库维度字典表，匹配维度取值。

    参数：
        keyword: 要搜索的关键词。
        db_session: SQLAlchemy 数据库会话。
    返回：
        匹配的维度取值列表，每项包含 value_id、column_name、value、table_name。
    
    业务逻辑：
        对 _DIMENSION_VALUE_TABLES 中的每个字段，在每个表中执行
        SELECT DISTINCT {column} FROM {table} WHERE {column} LIKE '%keyword%' LIMIT 10
    """
    results: list[ValueInfo] = []
    seen: set[str] = set()

    for column_name, tables in _DIMENSION_VALUE_TABLES.items():
        for table_name in tables:
            try:
                # 参数化查询：使用 LIKE 模糊匹配
                sql = text(
                    f"SELECT DISTINCT `{column_name}` AS value_ FROM `{table_name}` "
                    f"WHERE `{column_name}` LIKE :keyword LIMIT 10"
                )
                rows = db_session.execute(sql, {"keyword": f"%{keyword}%"}).fetchall()
                for row in rows:
                    val = str(row[0]) if row[0] is not None else ""
                    if not val:
                        continue
                    value_id = f"{table_name}.{column_name}:{val}"
                    if value_id in seen:
                        continue
                    seen.add(value_id)
                    results.append(ValueInfo(
                        value_id=value_id,
                        column_id=f"column:{column_name}",
                        column_name=column_name,
                        value=val,
                        table_name=table_name,
                        match_score=100.0,
                    ))
            except Exception as exc:
                # 表或字段可能不存在，静默跳过
                logger.debug(
                    "recall_value_table_skip table=%s column=%s error=%s",
                    table_name, column_name, exc,
                )
                continue

    return results


# rapidfuzz 模糊匹配分数阈值（0-100，类似掌柜问数 ES score_threshold=0.6）
_VALUE_FUZZY_THRESHOLD: int = 70
# 维度值内存缓存（key: 表名, value: list of dict）
_value_cache: dict[str, list[dict[str, Any]]] | None = None


def _fuzzy_search_dimension_values(
    keyword: str,
    db_session: Any,
    *,
    score_cutoff: int = 70,
    limit: int = 5,
) -> list[ValueInfo]:
    """使用 rapidfuzz 对维度表做模糊匹配（替代 ES/ik_max_word 分词）。

    参数：
        keyword: 搜索关键词（人名/地名/组织名等）。
        db_session: 数据库会话（用于首次加载维度值）。
        score_cutoff: 最低匹配分数（0-100），低于此阈值的结果丢弃。
        limit: 每张表最多返回的结果数。

    返回：
        匹配的维度值列表，每项含 value_id、value、column_name、table_name、match_score。
    """
    global _value_cache
    try:
        from rapidfuzz import process, fuzz
    except ImportError:
        return []

    # 首次调用时加载所有维度值到内存缓存
    if _value_cache is None and db_session is not None:
        _value_cache = _load_dimension_cache(db_session)

    if not _value_cache:
        return []

    results: list[ValueInfo] = []
    for table_name, rows in _value_cache.items():
        # 对每行构建搜索文本
        texts = [" ".join(f"{k}:{v}" for k, v in row.items()) for row in rows]
        matches = process.extract(keyword, texts, scorer=fuzz.WRatio, limit=limit, score_cutoff=score_cutoff)
        for match_text, score, idx in matches:
            row = rows[idx].copy()
            # rapidfuzz 分数保留到实体，便于后续排序、审计和兼容输出。
            results.append(ValueInfo(
                value_id=str(row.get("value_id", "")),
                value=str(row.get("value", "")),
                column_id=str(row.get("column_id", "")),
                column_name=str(row.get("column_name", "")),
                table_name=str(row.get("table_name", "")),
                match_score=float(score),
            ))

    # 按匹配分数降序排列
    results.sort(key=lambda x: x.match_score, reverse=True)
    return results[:limit * len(_value_cache)]


def _load_dimension_cache(db_session: Any) -> dict[str, list[dict[str, Any]]]:
    """从中间库维度表中加载所有 distinct 维度值到内存。"""
    from sqlalchemy import text
    cache: dict[str, list[dict[str, Any]]] = {}
    for column_name, tables in _DIMENSION_VALUE_TABLES.items():
        for table_name in tables:
            try:
                rows = db_session.execute(
                    text(f"SELECT DISTINCT {column_name} as value FROM {table_name} LIMIT 1000")
                ).mappings().fetchall()
                for row in rows:
                    val = str(row.get("value", "")) if row.get("value") is not None else ""
                    if not val:
                        continue
                    key = f"{table_name}::{column_name}"
                    if key not in cache:
                        cache[key] = []
                    # 缓存中保留完整实体字段，确保模糊召回可直接构造 ValueInfo。
                    cache[key].append({
                        "value_id": f"{table_name}.{column_name}:{val}",
                        "column_id": f"column:{column_name}",
                        "column_name": column_name,
                        "value": val,
                        "table_name": table_name,
                    })
            except Exception:
                continue
    return cache


def recall_value_node(state: dict[str, Any]) -> dict[str, Any]:
    """召回字段取值节点（掌柜问数对齐版，SQL 替代 ES）。"""
    _emit_progress(state, STEP_RECALL_VALUE, "running")
    question: str = state.get("question", "")
    keywords: list[str] = state.get("keywords", [])
    db_session = state.get("_db_session")  # 由 Graph context 或上层注入

    if not question:
        _emit_progress(state, STEP_RECALL_VALUE, "success")
        return {"retrieved_values": []}

    # 如果没有数据库会话，跳过 SQL 查询
    if db_session is None:
        logger.warning("recall_value_no_db_session skip sql search")
        _emit_progress(state, STEP_RECALL_VALUE, "success")
        return {"retrieved_values": []}

    try:
        # Step 1: LLM 扩展关键词
        expanded = _expand_value_keywords_with_llm(question)
        all_keywords = list(set(keywords + expanded))
        logger.info("recall_value expanded_keywords=%s", all_keywords)

        # Step 2: rapidfuzz 模糊匹配维度值（替代 SQL LIKE，类似掌柜问数 ES 全文检索）
        values_map: dict[str, ValueInfo] = {}
        threshold = _VALUE_FUZZY_THRESHOLD
        for keyword in all_keywords:
            if not keyword.strip():
                continue
            try:
                val_dicts = _fuzzy_search_dimension_values(keyword, db_session, score_cutoff=threshold)
                for v in val_dicts:
                    vid = v.value_id
                    if vid and vid not in values_map:
                        values_map[vid] = v
            except Exception as inner_exc:
                logger.debug("recall_value_fuzzy_failed keyword=%s error=%s", keyword, inner_exc)
                # rapidfuzz 失败时走 SQL LIKE 兜底
                try:
                    vals = _sql_search_dimension_values(keyword, db_session)
                    for v in vals:
                        vid = v.value_id
                        if vid and vid not in values_map:
                            values_map[vid] = v
                except Exception:
                    continue

        # Graph state 保持 dict，兼容后续 merge 节点按 get 读取。
        retrieved_values = [value.model_dump(mode="json") for value in values_map.values()]
        logger.info("recall_value_success count=%d", len(retrieved_values))
        _emit_progress(state, STEP_RECALL_VALUE, "success")
        return {"retrieved_values": retrieved_values}

    except Exception as exc:
        logger.error("recall_value_failed error=%s", exc)
        _emit_progress(state, STEP_RECALL_VALUE, "error")
        return {"retrieved_values": []}

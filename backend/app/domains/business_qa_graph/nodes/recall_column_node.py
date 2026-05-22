"""
掌柜问数对齐 - 字段召回节点（recall_column）。

对应掌柜问数 data-agent/app/agent/nodes/recall_column.py：
- 使用 LLM 扩展关键词（extend_keywords_for_column_recall）
- 对每个关键词生成 embedding 后通过 Milvus 向量检索字段信息
- 按 catalog_id 去重
- 输出进度事件：{type: progress, step: 召回字段, status: running/success/error}

技术栈适配：
- 掌柜问数用 Qdrant → gcl-bp-ai 用 Milvus
- 复用现有 LogisticsCatalogRecallService 的 Milvus 检索能力
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.app.core.config import get_settings
from backend.app.domains.business_qa_graph.prompt_loader import load_prompt_or_default
from backend.app.domains.business_qa_graph.nodes.zg_utils import _emit_progress, STEP_RECALL_COLUMN
from backend.app.domains.business_qa_graph.schemas.entities import ColumnInfo

logger = logging.getLogger(__name__)

# 默认 Prompt（文件不存在时的兜底）
_COLUMN_KEYWORD_EXPAND_DEFAULT = '你是一个关键词扩展器。用户问题：{question}。请输出 JSON 数组。'


def _expand_keywords_with_llm(question: str) -> list[str]:
    """使用 LLM 扩展字段召回关键词。

    参数：
        question: 用户原始问题。
    返回：
        扩展后的关键词列表；LLM 不可用时返回空列表。
    """
    settings = get_settings()
    if not settings.llm_api_key or not settings.llm_base_url:
        logger.warning("recall_column_llm_unavailable no_api_key")
        return []

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
        prompt_template = load_prompt_or_default(
            "extend_keywords_for_column_recall",
            _COLUMN_KEYWORD_EXPAND_DEFAULT,
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
        # 提取 JSON 数组
        content = content.strip()
        if content.startswith("```"):
            # 去掉 markdown 代码块包裹
            content = content.split("\n", 1)[-1].rsplit("\n", 1)[0]
        return json.loads(content)
    except Exception as exc:
        logger.warning("recall_column_keyword_expand_failed error=%s", exc)
        return []


def _milvus_search_column(embedding: list[float], top_k: int = 8, score_threshold: float = 0.6) -> list[ColumnInfo]:
    """通过 Milvus 向量检索字段/维度信息，过滤低质量匹配。

    参数：
        embedding: 查询文本的向量表示。
        top_k: 返回的最大结果数。
        score_threshold: 最低向量相似度阈值（0-1），低于此值的结果丢弃。
    """
    try:
        from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import (
            LogisticsCatalogRecallService,
        )

        recall_service = LogisticsCatalogRecallService()
        raw_hits = recall_service.vector_store.search(embedding, top_k=top_k, score_threshold=0.6)
        
        results: list[ColumnInfo] = []
        for hit in raw_hits:
            # 向量分数过滤（掌柜问数 score_threshold=0.6）
            vector_score = getattr(hit, "vector_score", 0.0) if not isinstance(hit, dict) else hit.get("vector_score", 0.0)
            if vector_score < score_threshold:
                continue
            # 只保留 column/dimension 类型的文档
            doc_type = hit.get("doc_type", "") if isinstance(hit, dict) else getattr(hit, "doc_type", "")
            if doc_type not in ("column", "dimension"):
                continue
            
            # 提取字段信息
            metadata = hit.get("metadata", {}) if isinstance(hit, dict) else getattr(hit, "metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            
            content = hit.get("content", "") if isinstance(hit, dict) else getattr(hit, "content", "")
            # 从 content 中解析字段名（content 格式: "维度；基地；维度标识 base_name；..."）
            name = ""
            parts = content.split("；")
            if len(parts) >= 3:
                name = parts[2].replace("维度标识 ", "").replace("指标标识 ", "").strip()
            
            results.append(ColumnInfo(
                catalog_id=hit.get("catalog_id", "") if isinstance(hit, dict) else getattr(hit, "catalog_id", ""),
                name=name or (hit.get("title", "") if isinstance(hit, dict) else getattr(hit, "title", "")),
                data_type=metadata.get("data_type", "varchar"),
                role=doc_type,
                examples=metadata.get("examples", []),
                description=content[:200],
                alias=[],
                source_table=hit.get("source_table", "") if isinstance(hit, dict) else getattr(hit, "source_table", ""),
            ))
        return results
    except Exception as exc:
        logger.warning("recall_column_milvus_failed error=%s", exc)
        return []


def recall_column_node(state: dict[str, Any]) -> dict[str, Any]:
    """召回字段信息节点（掌柜问数对齐版）。"""
    _emit_progress(state, STEP_RECALL_COLUMN, "running")

    question: str = state.get("question", "")
    keywords: list[str] = state.get("keywords", [])

    if not question:
        _emit_progress(state, STEP_RECALL_COLUMN, "success")
        return {"retrieved_columns": []}

    try:
        expanded = _expand_keywords_with_llm(question)
        all_keywords = list(set(keywords + expanded))
        logger.info("recall_column expanded_keywords=%s", all_keywords)

        from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import (
            LogisticsCatalogRecallService,
        )

        recall_service = LogisticsCatalogRecallService()
        retrieved_map: dict[str, ColumnInfo] = {}

        for keyword in all_keywords:
            if not keyword.strip():
                continue
            try:
                # 生成 embedding
                vectors = recall_service.embedding_client.embed_texts([keyword])
                if not vectors:
                    continue
                # Milvus 检索
                columns = _milvus_search_column(vectors[0], top_k=6)
                for col in columns:
                    cid = col.catalog_id
                    if cid and cid not in retrieved_map:
                        retrieved_map[cid] = col
            except Exception as inner_exc:
                logger.debug("recall_column_keyword_failed keyword=%s error=%s", keyword, inner_exc)
                continue

        # Graph state 仍写入旧 dict 结构，避免破坏 merge/generate 节点的既有读取逻辑。
        retrieved_columns = [col.to_legacy_dict() for col in retrieved_map.values()]
        logger.info("recall_column_success count=%d", len(retrieved_columns))
        _emit_progress(state, STEP_RECALL_COLUMN, "success")
        return {"retrieved_columns": retrieved_columns}

    except Exception as exc:
        logger.error("recall_column_failed error=%s", exc)
        _emit_progress(state, STEP_RECALL_COLUMN, "error")
        return {"retrieved_columns": []}

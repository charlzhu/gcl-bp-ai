"""
掌柜问数对齐 - 指标召回节点（recall_metric）。

对应掌柜问数 data-agent/app/agent/nodes/recall_metric.py：
- 使用 LLM 扩展关键词（extend_keywords_for_metric_recall）
- 对每个关键词生成 embedding 后通过 Milvus 向量检索指标信息
- 按 catalog_id 去重
- 输出进度事件：{type: progress, step: 召回指标, status: running/success/error}

技术栈适配：
- 掌柜问数用 Qdrant → gcl-bp-ai 用 Milvus
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.app.core.config import get_settings
from backend.app.domains.business_qa_graph.prompt_loader import load_prompt_or_default
from backend.app.domains.business_qa_graph.nodes.zg_utils import _emit_progress, STEP_RECALL_METRIC

logger = logging.getLogger(__name__)

_METRIC_KEYWORD_EXPAND_DEFAULT = '你是关键词扩展器。用户问题：{question}。请输出 JSON 数组。'


def _expand_metric_keywords_with_llm(question: str) -> list[str]:
    """使用 LLM 扩展指标召回关键词。

    参数：
        question: 用户原始问题。
    返回：
        扩展后的关键词列表；LLM 不可用时返回空列表。
    """
    settings = get_settings()
    if not settings.llm_api_key or not settings.llm_base_url:
        return []

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
        prompt_template = load_prompt_or_default(
            "extend_keywords_for_metric_recall",
            _METRIC_KEYWORD_EXPAND_DEFAULT,
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
        logger.warning("recall_metric_keyword_expand_failed error=%s", exc)
        return []


def _milvus_search_metric(embedding: list[float], top_k: int = 8) -> list[dict[str, Any]]:
    """通过 Milvus 向量检索指标信息。

    参数：
        embedding: 查询文本的向量表示。
        top_k: 返回的最大结果数。
    返回：
        召回的指标信息列表。
    """
    try:
        from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import (
            LogisticsCatalogRecallService,
        )

        recall_service = LogisticsCatalogRecallService()
        raw_hits = recall_service.vector_store.search(embedding, top_k=top_k)

        results = []
        for hit in raw_hits:
            doc_type = hit.get("doc_type", "") if isinstance(hit, dict) else getattr(hit, "doc_type", "")
            # 只保留 metric 类型的文档
            if doc_type != "metric":
                continue

            metadata = hit.get("metadata", {}) if isinstance(hit, dict) else getattr(hit, "metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

            content = hit.get("content", "") if isinstance(hit, dict) else getattr(hit, "content", "")
            # 从 content 解析指标名
            name = ""
            parts = content.split("；")
            if len(parts) >= 2:
                name = parts[1].strip()
            if not name:
                name = hit.get("title", "") if isinstance(hit, dict) else getattr(hit, "title", "")

            results.append({
                "catalog_id": hit.get("catalog_id", "") if isinstance(hit, dict) else getattr(hit, "catalog_id", ""),
                "name": name,
                "description": content[:300],
                "relevant_columns": metadata.get("relevant_columns", metadata.get("columns", [])),
                "alias": metadata.get("aliases", metadata.get("alias", [])),
                "unit": metadata.get("unit", ""),
            })
        return results
    except Exception as exc:
        logger.warning("recall_metric_milvus_failed error=%s", exc)
        return []


def recall_metric_node(state: dict[str, Any]) -> dict[str, Any]:
    """召回指标信息节点（掌柜问数对齐版）。"""
    _emit_progress(state, STEP_RECALL_METRIC, "running")
    question: str = state.get("question", "")
    keywords: list[str] = state.get("keywords", [])

    if not question:
        _emit_progress(state, STEP_RECALL_METRIC, "success")
        return {"retrieved_metrics": []}

    try:
        # Step 1: LLM 扩展关键词
        expanded = _expand_metric_keywords_with_llm(question)
        all_keywords = list(set(keywords + expanded))
        logger.info("recall_metric expanded_keywords=%s", all_keywords)

        # Step 2: Milvus 向量检索
        from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import (
            LogisticsCatalogRecallService,
        )

        recall_service = LogisticsCatalogRecallService()
        retrieved_map: dict[str, dict[str, Any]] = {}

        for keyword in all_keywords:
            if not keyword.strip():
                continue
            try:
                vectors = recall_service.embedding_client.embed_texts([keyword])
                if not vectors:
                    continue
                metrics = _milvus_search_metric(vectors[0], top_k=6)
                for metric in metrics:
                    mid = metric.get("catalog_id", "")
                    if mid and mid not in retrieved_map:
                        retrieved_map[mid] = metric
            except Exception as inner_exc:
                logger.debug("recall_metric_keyword_failed keyword=%s error=%s", keyword, inner_exc)
                continue

        retrieved_metrics = list(retrieved_map.values())
        logger.info("recall_metric_success count=%d", len(retrieved_metrics))
        _emit_progress(state, STEP_RECALL_METRIC, "success")
        return {"retrieved_metrics": retrieved_metrics}

    except Exception as exc:
        logger.error("recall_metric_failed error=%s", exc)
        _emit_progress(state, STEP_RECALL_METRIC, "error")
        return {"retrieved_metrics": []}

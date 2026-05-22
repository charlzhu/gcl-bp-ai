"""
掌柜问数对齐 - 关键字提取节点（extract_keywords）。

完全对齐 data-agent/app/agent/nodes/extract_keywords.py：
- jieba 分词 + 词性过滤
- SSE 进度流式输出
"""

from __future__ import annotations

import logging
from typing import Any

import jieba.analyse

from backend.app.domains.business_qa_graph.nodes.zg_utils import (
    _emit_progress,
    STEP_EXTRACT_KEYWORDS,
)

logger = logging.getLogger(__name__)

_ALLOW_POS = (
    "n", "nr", "ns", "nt", "nz",
    "v", "vn", "a", "an",
    "eng", "i", "l",
)


def extract_keywords_node(state: dict[str, Any]) -> dict[str, Any]:
    """提取用户问题中的关键字（掌柜问数对齐版）。"""
    _emit_progress(state, STEP_EXTRACT_KEYWORDS, "running")

    query: str = state.get("question", "")
    if not query or not query.strip():
        _emit_progress(state, STEP_EXTRACT_KEYWORDS, "success")
        return {"keywords": []}

    try:
        keywords = jieba.analyse.extract_tags(query, allowPOS=_ALLOW_POS)
        keywords = list(set(keywords + [query]))
        logger.info("extract_keywords query=%s keywords=%s", query[:80], keywords)
        _emit_progress(state, STEP_EXTRACT_KEYWORDS, "success")
        return {"keywords": keywords}
    except Exception as exc:
        logger.error("extract_keywords_failed error=%s", exc)
        _emit_progress(state, STEP_EXTRACT_KEYWORDS, "error")
        return {"keywords": [query]}

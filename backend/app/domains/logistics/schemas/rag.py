from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LogisticsRagCitation(BaseModel):
    """物流 RAG 单条引用来源。

    字段说明：
    - source_name：文档名，供前端或脚本直接展示；
    - section_title：命中的章节标题，便于定位原文；
    - snippet：命中的原文片段摘要；
    - score：检索相似度分数，当前仅用于排序参考，不对外承诺绝对语义。
    """

    source_name: str
    source_path: str
    section_title: str | None = None
    snippet: str
    score: float


class LogisticsRagIndexMeta(BaseModel):
    """物流 RAG 本地索引元信息。"""

    vector_backend: str
    source_count: int
    chunk_count: int
    built_at: str
    index_path: str
    source_names: list[str] = Field(default_factory=list)


class LogisticsRagQueryRequest(BaseModel):
    """物流 RAG 查询请求。

    参数说明：
    - question：用户问题；
    - top_k：最多返回多少条候选引用；
    - rebuild_if_missing：索引不存在时是否自动先重建索引。
    """

    question: str = Field(..., min_length=2, description="物流文档型问题")
    top_k: int = Field(default=4, ge=1, le=8)
    rebuild_if_missing: bool = Field(default=True)


class LogisticsRagQueryResult(BaseModel):
    """物流 RAG 查询结果。

    返回说明：
    - answer_mode：区分“有依据回答”还是“依据不足”；
    - grounded：是否找到足够依据；
    - citations：引用来源列表；
    - index_meta：当前命中的索引元信息，便于调试与验证。
    """

    question: str
    answer: str
    answer_mode: Literal["grounded_answer", "insufficient_evidence"]
    grounded: bool
    citations: list[LogisticsRagCitation] = Field(default_factory=list)
    index_meta: LogisticsRagIndexMeta


class LogisticsRagRebuildResponse(BaseModel):
    """物流 RAG 重建索引响应。"""

    message: str
    index_meta: LogisticsRagIndexMeta

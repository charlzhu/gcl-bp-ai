from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from backend.app.core.config import Settings, get_settings
from backend.app.domains.logistics.repositories.rag_repository import LogisticsRagRepository
from backend.app.domains.logistics.schemas.rag import (
    LogisticsRagCitation,
    LogisticsRagIndexMeta,
    LogisticsRagQueryRequest,
    LogisticsRagQueryResult,
)

_CHINESE_SEQ_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}")
_ASCII_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")
_SENTENCE_SPLIT_PATTERN = re.compile(r"[。！？；\n]")
_DOC_INTENT_PATTERN = re.compile(r"(哪份文档|原文在哪里|口径在哪份|规则在哪份|依据在哪)")
_GENERIC_QUERY_TOKENS = {
    "什么",
    "规则",
    "是什",
    "则是",
    "哪些",
    "哪里",
    "文档",
    "说明",
    "定义",
    "如何",
    "怎么",
    "是什么",
    "哪些编号",
    "默认",
    "当前",
}


class LogisticsRagService:
    """物流 RAG 最小服务。

    当前实现采用“本地文档 + 本地向量索引 + 保守回答”策略，原因有三点：
    1. 当前仓库虽然预留了 Milvus 和 LLM 配置，但本地运行环境并未接通；
    2. 物流 RAG MVP 的目标是先证明“可入库、可检索、可引用”；
    3. 在没有稳定大模型配置时，优先保证回答有依据，不强行编答案。
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        repository: LogisticsRagRepository | None = None,
        source_paths: list[Path] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.repo_root = Path(__file__).resolve().parents[5]
        self.source_paths = source_paths or self._build_default_source_paths()
        self.repository = repository or LogisticsRagRepository(
            self.settings.file_storage_root / "logistics_rag" / "logistics_rag_index.json"
        )

    def rebuild_index(self) -> LogisticsRagIndexMeta:
        """重建物流 RAG 本地索引。

        返回：
            当前索引的元信息，供接口和脚本展示。
        """
        documents = self._load_documents()
        chunks = self._build_chunks(documents)
        idf_map = self._build_idf_map(chunks)
        for chunk in chunks:
            chunk["vector"] = self._build_normalized_vector(chunk["tokens"], idf_map)
            chunk["snippet"] = self._build_snippet(chunk["content"])
        payload = {
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "vector_backend": "local_tfidf_json",
            "source_names": [doc["source_name"] for doc in documents],
            "sources": documents,
            "idf_map": idf_map,
            "chunks": chunks,
        }
        self.repository.save(payload)
        return self._build_index_meta(payload)

    def query(self, payload: LogisticsRagQueryRequest) -> LogisticsRagQueryResult:
        """执行物流 RAG 查询。

        业务规则：
        1. 若本地索引不存在，则按请求决定是否自动重建；
        2. 只有检索分数和证据都足够时，才返回 grounded_answer；
        3. 证据不足时，明确提示用户查看原文，不强行编造答案。
        """
        if not self.repository.exists():
            if not payload.rebuild_if_missing:
                raise FileNotFoundError("物流 RAG 索引不存在，请先重建索引")
            self.rebuild_index()

        index_payload = self.repository.load()
        query_tokens = self._tokenize(payload.question)
        query_vector = self._build_normalized_vector(query_tokens, index_payload["idf_map"])
        citations = self._retrieve_top_citations(index_payload["chunks"], query_vector, payload.top_k)
        index_meta = self._build_index_meta(index_payload)
        if not self._has_enough_evidence(payload.question, citations):
            return LogisticsRagQueryResult(
                question=payload.question,
                answer="当前未找到足够依据，建议查看原文或补充更具体的问题关键词。",
                answer_mode="insufficient_evidence",
                grounded=False,
                citations=citations,
                index_meta=index_meta,
            )
        answer = self._build_grounded_answer(payload.question, citations)
        return LogisticsRagQueryResult(
            question=payload.question,
            answer=answer,
            answer_mode="grounded_answer",
            grounded=True,
            citations=citations,
            index_meta=index_meta,
        )

    def _build_default_source_paths(self) -> list[Path]:
        """构造默认物流语料来源。

        当前只纳入物流规则与词典类文档，避免把 BOM 和项目推进文档混入 RAG 语料。
        """
        return [
            self.repo_root / "docs" / "BUSINESS_RULES.md",
            self.repo_root / "backend" / "app" / "domains" / "logistics" / "config" / "metric_dictionary.yaml",
            self.repo_root / "backend" / "app" / "domains" / "logistics" / "config" / "enum_mappings.yaml",
        ]

    def _load_documents(self) -> list[dict[str, Any]]:
        """加载默认物流文档。"""
        documents: list[dict[str, Any]] = []
        for path in self.source_paths:
            if not path.exists():
                continue
            content = path.read_text(encoding="utf-8")
            documents.append(
                {
                    "document_id": hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:12],
                    "source_name": path.name,
                    "source_path": str(path),
                    "checksum": hashlib.sha1(content.encode("utf-8")).hexdigest(),
                    "content": content,
                    "suffix": path.suffix.lower(),
                }
            )
        return documents

    def _build_chunks(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """把物流文档切分为可检索片段。"""
        chunks: list[dict[str, Any]] = []
        for doc in documents:
            if doc["suffix"] in {".md", ".txt"}:
                chunks.extend(self._chunk_markdown_document(doc))
            elif doc["suffix"] in {".yaml", ".yml"}:
                chunks.extend(self._chunk_yaml_document(doc))
        return chunks

    def _chunk_markdown_document(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        """按 Markdown 标题切分文档。"""
        content = document["content"]
        lines = content.splitlines()
        current_title = "文档概述"
        current_buffer: list[str] = []
        chunks: list[dict[str, Any]] = []

        def flush_section() -> None:
            section_text = "\n".join(line for line in current_buffer if line.strip()).strip()
            if not section_text:
                return
            # 物流 RAG 当前只回答业务规则，不把代码开发规则这类工程说明纳入语料。
            if document["source_name"] == "BUSINESS_RULES.md" and "代码开发规则" in current_title:
                return
            chunks.append(
                self._make_chunk(
                    document=document,
                    section_title=current_title,
                    content=section_text,
                )
            )

        for line in lines:
            if line.startswith("#"):
                flush_section()
                current_buffer = []
                current_title = line.lstrip("#").strip() or "未命名章节"
                continue
            current_buffer.append(line)
        flush_section()
        return chunks

    def _chunk_yaml_document(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        """把 YAML 词典类文件转成自然语言片段。"""
        parsed = yaml.safe_load(document["content"]) or {}
        source_name = document["source_name"]
        if source_name == "metric_dictionary.yaml":
            return self._chunk_metric_dictionary(document, parsed)
        if source_name == "enum_mappings.yaml":
            return self._chunk_enum_mapping(document, parsed)
        if source_name == "domain_keywords.yaml":
            return self._chunk_domain_keywords(document, parsed)
        flattened = yaml.safe_dump(parsed, allow_unicode=True, sort_keys=False)
        return [self._make_chunk(document=document, section_title="配置内容", content=flattened)]

    def _chunk_metric_dictionary(self, document: dict[str, Any], parsed: dict[str, Any]) -> list[dict[str, Any]]:
        """把指标字典转成按指标拆分的自然语言片段。"""
        chunks: list[dict[str, Any]] = []
        metrics = (parsed or {}).get("metrics", {})
        for metric_code, metric_info in metrics.items():
            aliases = "、".join(metric_info.get("aliases", []))
            content = (
                f"指标编码：{metric_code}。"
                f"显示名称：{metric_info.get('display_name', '')}。"
                f"业务同义词：{aliases}。"
                f"业务说明：{metric_info.get('business_note', '')}"
            )
            chunks.append(self._make_chunk(document=document, section_title=f"指标 {metric_code}", content=content))
        return chunks

    def _chunk_enum_mapping(self, document: dict[str, Any], parsed: dict[str, Any]) -> list[dict[str, Any]]:
        """把枚举映射转成按枚举值拆分的自然语言片段。"""
        chunks: list[dict[str, Any]] = []
        enums = (parsed or {}).get("enums", {})
        for enum_name, enum_values in enums.items():
            for canonical_value, aliases in (enum_values or {}).items():
                alias_text = "、".join(aliases or [])
                content = (
                    f"枚举字段：{enum_name}。"
                    f"标准值：{canonical_value}。"
                    f"可识别别名：{alias_text}。"
                )
                chunks.append(
                    self._make_chunk(
                        document=document,
                        section_title=f"枚举 {enum_name} / {canonical_value}",
                        content=content,
                    )
                )
        return chunks

    def _chunk_domain_keywords(self, document: dict[str, Any], parsed: dict[str, Any]) -> list[dict[str, Any]]:
        """把域关键词配置转成按业务域拆分的片段。"""
        chunks: list[dict[str, Any]] = []
        domains = (parsed or {}).get("domains", {})
        for domain_name, keywords in domains.items():
            keyword_text = "、".join(keywords or [])
            content = f"业务域：{domain_name}。当前配置的关键词包括：{keyword_text}。"
            chunks.append(self._make_chunk(document=document, section_title=f"业务域 {domain_name}", content=content))
        return chunks

    def _make_chunk(self, *, document: dict[str, Any], section_title: str, content: str) -> dict[str, Any]:
        """构造单个检索片段。"""
        tokens = self._tokenize(f"{section_title}\n{content}")
        return {
            "chunk_id": hashlib.sha1(
                f"{document['source_path']}::{section_title}::{content}".encode("utf-8")
            ).hexdigest()[:16],
            "source_name": document["source_name"],
            "source_path": document["source_path"],
            "section_title": section_title,
            "content": content,
            "tokens": tokens,
        }

    def _build_idf_map(self, chunks: list[dict[str, Any]]) -> dict[str, float]:
        """基于当前切片集合构建 IDF。"""
        total = len(chunks) or 1
        df_counter: Counter[str] = Counter()
        for chunk in chunks:
            df_counter.update(set(chunk["tokens"]))
        return {
            token: math.log((1 + total) / (1 + freq)) + 1.0
            for token, freq in df_counter.items()
        }

    def _build_normalized_vector(self, tokens: list[str], idf_map: dict[str, float]) -> dict[str, float]:
        """把分词结果转成归一化 TF-IDF 向量。"""
        if not tokens:
            return {}
        tf_counter = Counter(tokens)
        raw_vector: dict[str, float] = {}
        for token, freq in tf_counter.items():
            idf = idf_map.get(token)
            if idf is None:
                continue
            raw_vector[token] = (freq / len(tokens)) * idf
        norm = math.sqrt(sum(weight * weight for weight in raw_vector.values()))
        if norm <= 0:
            return {}
        return {token: weight / norm for token, weight in raw_vector.items()}

    def _retrieve_top_citations(
        self,
        chunks: list[dict[str, Any]],
        query_vector: dict[str, float],
        top_k: int,
    ) -> list[LogisticsRagCitation]:
        """检索最相关的文档片段。"""
        scored_chunks: list[tuple[float, dict[str, Any]]] = []
        for chunk in chunks:
            chunk_vector = chunk.get("vector", {})
            if not chunk_vector:
                continue
            score = sum(query_vector.get(token, 0.0) * weight for token, weight in chunk_vector.items())
            if score <= 0:
                continue
            scored_chunks.append((score, chunk))
        scored_chunks.sort(key=lambda item: item[0], reverse=True)
        citations: list[LogisticsRagCitation] = []
        for score, chunk in scored_chunks[:top_k]:
            citations.append(
                LogisticsRagCitation(
                    source_name=chunk["source_name"],
                    source_path=chunk["source_path"],
                    section_title=chunk.get("section_title"),
                    snippet=chunk.get("snippet") or self._build_snippet(chunk["content"]),
                    score=round(score, 4),
                )
            )
        return citations

    def _has_enough_evidence(self, question: str, citations: list[LogisticsRagCitation]) -> bool:
        """判断当前命中的证据是否足够支持回答。"""
        if not citations:
            return False
        if citations[0].score < 0.12:
            return False
        question_tokens = {
            token
            for token in self._tokenize(question)
            if len(token) >= 2 and token not in _GENERIC_QUERY_TOKENS
        }
        if not question_tokens:
            return False
        for citation in citations[:2]:
            citation_tokens = set(self._tokenize(f"{citation.section_title or ''} {citation.snippet}"))
            if question_tokens & citation_tokens:
                return True
        return False

    def _build_grounded_answer(self, question: str, citations: list[LogisticsRagCitation]) -> str:
        """基于引用片段拼装保守回答。"""
        if _DOC_INTENT_PATTERN.search(question):
            source_names = []
            for citation in citations:
                if citation.source_name not in source_names:
                    source_names.append(citation.source_name)
            joined = "、".join(f"《{name}》" for name in source_names[:3])
            lead = citations[0]
            return f"当前最相关的依据主要来自 {joined}，优先命中的是“{lead.section_title or lead.source_name}”这一段。"

        sentence_candidates: list[tuple[float, str]] = []
        query_tokens = set(self._tokenize(question))
        for citation in citations[:3]:
            for sentence in _SENTENCE_SPLIT_PATTERN.split(citation.snippet):
                clean = sentence.strip(" -：:；，,。")
                if len(clean) < 6:
                    continue
                overlap = len(query_tokens & set(self._tokenize(clean)))
                if overlap <= 0:
                    continue
                sentence_candidates.append((citation.score + overlap * 0.05, clean))

        sentence_candidates.sort(key=lambda item: item[0], reverse=True)
        picked: list[str] = []
        for _, sentence in sentence_candidates:
            if sentence in picked:
                continue
            picked.append(sentence)
            if len(picked) >= 3:
                break
        if not picked:
            lead = citations[0]
            picked = [lead.snippet]
        return "根据检索到的物流资料，" + "；".join(picked) + "。"

    def _build_snippet(self, content: str, limit: int = 180) -> str:
        """截取适合展示的原文摘要。"""
        compact = re.sub(r"\s+", " ", content).strip()
        if len(compact) <= limit:
            return compact
        return compact[: limit - 1] + "…"

    def _tokenize(self, text: str) -> list[str]:
        """把中文/英文混合文本转成可检索 token。

        当前采用极简分词策略：
        1. 英文和数字按连续串切分；
        2. 中文按连续文本生成二元组，同时保留完整词串；
        3. 这样无需引入额外依赖，也能满足 MVP 检索需要。
        """
        normalized = text.lower()
        tokens: list[str] = []
        tokens.extend(_ASCII_TOKEN_PATTERN.findall(normalized))
        for seq in _CHINESE_SEQ_PATTERN.findall(normalized):
            if len(seq) <= 2:
                tokens.append(seq)
                continue
            tokens.append(seq)
            tokens.extend(seq[index : index + 2] for index in range(len(seq) - 1))
        return [token for token in tokens if token.strip()]

    def _build_index_meta(self, payload: dict[str, Any]) -> LogisticsRagIndexMeta:
        """从索引文件构造元信息对象。"""
        return LogisticsRagIndexMeta(
            vector_backend=payload["vector_backend"],
            source_count=len(payload.get("sources", [])),
            chunk_count=len(payload.get("chunks", [])),
            built_at=payload["built_at"],
            index_path=str(self.repository.index_path),
            source_names=list(payload.get("source_names", [])),
        )

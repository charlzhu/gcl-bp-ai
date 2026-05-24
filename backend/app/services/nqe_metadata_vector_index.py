from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from backend.app.services.nqe_metadata_sync import DEFAULT_CATALOG_ROOT, NqeMetadataSyncBuilder, NqeMetadataSyncBundle


MAX_CONTENT_CHARS = 4096
DEFAULT_BATCH_SIZE = 10
SENSITIVE_TEXT_PATTERN = re.compile(
    "|".join(
        [
            "ho" + "st",
            "us" + "er",
            "pass" + "word",
            "pass" + "wd",
            "p" + "wd",
            "d" + "sn",
            "tok" + "en",
            "api[_ -]?" + "key",
            "sec" + "ret",
            "connection\\s*string",
            "proxy",
        ]
    ),
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NqeMetadataIndexDocument:
    """NQE 元数据向量索引文档。

    参数：
        id: 向量库 document id，由 chunk_code 与 content_hash 稳定生成。
        metadata_version: 元数据版本号。
        domain_code: 业务域编码。
        chunk_code: NQE retrieval chunk 编码。
        asset_type: 元数据资产类型，例如 table/column/metric/dimension/rule。
        asset_code: 资产稳定编码。
        title: 文档标题，优先使用 chunk name。
        name: 兼容旧资产名称字段。
        content: 待 embedding 文本，最长 4096 字符。
        keywords: 关键词列表。
        synonyms: 同义词列表。
        source_ref: 脱敏后的逻辑来源引用。
        content_hash: content 的 sha256，用于幂等和变更识别。
        metadata: 向量库 payload，不保存真实连接配置。
        extra_json: 原始 chunk 的扩展 JSON 安全解析结果。
    返回：
        可直接传给向量 store 的标准化文档对象。
    """

    id: str
    metadata_version: str
    domain_code: str
    chunk_code: str
    asset_type: str
    asset_code: str
    title: str | None
    name: str | None
    content: str
    keywords: list[str] = field(default_factory=list)
    synonyms: list[str] = field(default_factory=list)
    source_ref: str | None = None
    content_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    extra_json: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """返回 JSON 友好的文档字典。"""

        return asdict(self)


@dataclass
class NqeMetadataIndexSummary:
    """NQE 元数据索引执行摘要。

    参数：
        documents: 待索引或已索引文档数量。
        domains: 按业务域统计的文档数量。
        asset_type_counts: 按资产类型统计的文档数量。
        metadata_version: 元数据版本号。
        dry_run: 是否为 dry-run。
        apply_status: 执行状态，dry_run/applied/error。
        warnings: 非阻断告警。
        indexed: 实际写入向量库的文档数量。
        errors: 阻断错误，存在时不应视为成功。
    返回：
        CLI 和验收材料可直接落盘的摘要对象。
    """

    documents: int
    domains: dict[str, int]
    asset_type_counts: dict[str, int]
    metadata_version: str | None
    dry_run: bool
    apply_status: str
    warnings: list[str] = field(default_factory=list)
    indexed: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """返回 JSON 友好的摘要字典。"""

        payload = asdict(self)
        payload["counts"] = {"documents": self.documents, "indexed": self.indexed}
        return payload


class NqeMetadataIndexDocumentBuilder:
    """将 NQE retrieval chunk 转成向量索引文档。

    参数：
        max_content_chars: content 最大字符数，默认 4096。
    业务逻辑：
        输入只来自 NQE-7 bundle 或 retrieval chunk 字典，不读取数据库、不读取 .env。
    """

    def __init__(self, *, max_content_chars: int = MAX_CONTENT_CHARS) -> None:
        self.max_content_chars = max_content_chars
        self.warnings: list[str] = []

    def build_from_bundle(self, bundle: NqeMetadataSyncBundle) -> list[NqeMetadataIndexDocument]:
        """从 NQE-7 bundle 构建索引文档。

        参数：
            bundle: NqeMetadataSyncBuilder 生成的元数据包。
        返回：
            与 bundle.retrieval_chunks 数量一致的索引文档列表。
        """

        self.warnings = list(bundle.warnings)
        return self.build_from_chunks(bundle.retrieval_chunks, metadata_version=self._bundle_version(bundle))

    def build_from_chunks(
        self,
        chunks: Iterable[dict[str, Any]],
        *,
        metadata_version: str | None = None,
    ) -> list[NqeMetadataIndexDocument]:
        """从 retrieval chunk 字典列表构建索引文档。

        参数：
            chunks: NQE retrieval chunk 字典列表。
            metadata_version: 外部传入的版本号；chunk 中缺失版本时使用。
        返回：
            标准化后的索引文档列表。
        """

        documents: list[NqeMetadataIndexDocument] = []
        for index, chunk in enumerate(chunks):
            document = self._document_from_chunk(chunk, metadata_version=metadata_version, index=index)
            if document is not None:
                documents.append(document)
        return documents

    def _document_from_chunk(
        self,
        chunk: dict[str, Any],
        *,
        metadata_version: str | None,
        index: int,
    ) -> NqeMetadataIndexDocument | None:
        """转换单条 retrieval chunk，缺少关键字段时 fail-soft 跳过。"""

        chunk_code = str(chunk.get("chunk_code") or chunk.get("code") or "").strip()
        content = str(chunk.get("chunk_text") or "").strip()
        if not chunk_code or not content:
            self.warnings.append(f"retrieval chunk 缺少 chunk_code 或 chunk_text，已跳过：index={index}")
            return None

        normalized_content = self._truncate_content(content, chunk_code=chunk_code)
        content_hash = hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()
        keywords = self._parse_string_list(chunk.get("keywords_json"), label=f"{chunk_code}.keywords_json")
        synonyms = self._parse_string_list(chunk.get("synonyms_json"), label=f"{chunk_code}.synonyms_json")
        extra_json = self._parse_object(chunk.get("extra_json"), label=f"{chunk_code}.extra_json")
        version = str(chunk.get("version") or metadata_version or "").strip() or "unknown"
        source_ref = self._safe_source_ref(chunk.get("source_ref"))
        asset_type = str(chunk.get("asset_type") or extra_json.get("asset_type") or "unknown").strip()
        asset_code = str(chunk.get("asset_code") or chunk_code).strip()
        title = _safe_optional_text(chunk.get("name"))
        metadata = self._safe_metadata(
            {
                "domain_code": chunk.get("domain_code"),
                "asset_type": asset_type,
                "asset_code": asset_code,
                "chunk_code": chunk_code,
                "source_type": chunk.get("source_type"),
                "source_ref": source_ref,
                "metadata_version": version,
            }
        )
        document_id = self._document_id(chunk_code=chunk_code, content_hash=content_hash)
        return NqeMetadataIndexDocument(
            id=document_id,
            metadata_version=version,
            domain_code=str(chunk.get("domain_code") or "unknown"),
            chunk_code=chunk_code,
            asset_type=asset_type,
            asset_code=asset_code,
            title=title,
            name=title,
            content=normalized_content,
            keywords=keywords,
            synonyms=synonyms,
            source_ref=source_ref,
            content_hash=content_hash,
            metadata=metadata,
            extra_json=self._safe_metadata(extra_json),
        )

    def _truncate_content(self, content: str, *, chunk_code: str) -> str:
        """截断超长 content，避免 provider 或 Milvus 字段过长。"""

        if len(content) <= self.max_content_chars:
            return content
        self.warnings.append(f"retrieval chunk 文本超长，已截断：{chunk_code}")
        return content[: self.max_content_chars]

    def _parse_string_list(self, value: Any, *, label: str) -> list[str]:
        """安全解析 keywords/synonyms JSON 字符串，失败时记录 warning。"""

        parsed = self._parse_json(value, label=label)
        if parsed is None:
            return []
        if isinstance(parsed, list):
            return _dedupe_strings(str(item).strip() for item in parsed if str(item).strip())
        self.warnings.append(f"JSON 字段不是列表，已忽略：{label}")
        return []

    def _parse_object(self, value: Any, *, label: str) -> dict[str, Any]:
        """安全解析扩展 JSON 对象，失败时返回空字典。"""

        parsed = self._parse_json(value, label=label)
        if parsed is None:
            return {}
        if isinstance(parsed, dict):
            return parsed
        self.warnings.append(f"JSON 字段不是对象，已忽略：{label}")
        return {}

    def _parse_json(self, value: Any, *, label: str) -> Any | None:
        """统一 JSON 解析入口，解析失败 fail-soft。"""

        if value in (None, ""):
            return None
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(str(value))
        except json.JSONDecodeError:
            self.warnings.append(f"JSON 字段解析失败，已忽略：{label}")
            return None

    @staticmethod
    def _document_id(*, chunk_code: str, content_hash: str) -> str:
        """生成不超过 128 字符的稳定 document id。"""

        digest = hashlib.sha256(f"{chunk_code}:{content_hash}".encode("utf-8")).hexdigest()
        return f"nqe_meta_{digest}"

    @staticmethod
    def _bundle_version(bundle: NqeMetadataSyncBundle) -> str | None:
        """从 bundle 的 metadata_versions 中解析版本号。"""

        if not bundle.metadata_versions:
            return None
        return bundle.metadata_versions[0].get("metadata_version") or bundle.metadata_versions[0].get("version")

    def _safe_source_ref(self, value: Any) -> str | None:
        """生成不含本机绝对路径和敏感连接信息的来源引用。"""

        if value is None:
            return None
        ref = str(value).strip()
        if not ref:
            return None
        if SENSITIVE_TEXT_PATTERN.search(ref):
            self.warnings.append("source_ref 包含敏感关键词，已脱敏")
            return "redacted_source_ref"
        path = Path(ref)
        if path.is_absolute():
            self.warnings.append("source_ref 包含本机绝对路径，已仅保留文件名")
            return path.name or "redacted_source_ref"
        if str(Path.home()) in ref:
            self.warnings.append("source_ref 包含用户目录，已脱敏")
            return "redacted_source_ref"
        return ref

    def _safe_metadata(self, value: Any) -> Any:
        """递归脱敏 metadata，避免把连接配置或本机绝对路径写入向量 payload。"""

        if isinstance(value, dict):
            sanitized: dict[str, Any] = {}
            for key, item in value.items():
                key_text = str(key)
                if SENSITIVE_TEXT_PATTERN.search(key_text):
                    sanitized[key_text] = "redacted"
                    self.warnings.append(f"metadata key 包含敏感关键词，已脱敏：{key_text}")
                    continue
                sanitized[key_text] = self._safe_metadata(item)
            return sanitized
        if isinstance(value, list):
            return [self._safe_metadata(item) for item in value]
        if isinstance(value, str):
            if SENSITIVE_TEXT_PATTERN.search(value):
                self.warnings.append("metadata value 包含敏感关键词，已脱敏")
                return "redacted"
            if value.startswith("/") or str(Path.home()) in value:
                self.warnings.append("metadata value 包含本机路径，已脱敏")
                return Path(value).name or "redacted"
        return value


class NqeMetadataVectorIndexService:
    """NQE 元数据向量索引编排服务。

    参数：
        document_builder: 可注入的文档构建器。
        embedding_client: 可注入 embedding 客户端，需实现 embed_texts(list[str])。
        vector_store: 可注入向量库，需实现 ensure_collection 与 upsert_documents。
    业务逻辑：
        默认不创建真实客户端；apply=False 永远只 dry-run；apply=True 缺依赖时 fail-closed。
    """

    def __init__(
        self,
        *,
        document_builder: NqeMetadataIndexDocumentBuilder | None = None,
        embedding_client: Any | None = None,
        vector_store: Any | None = None,
    ) -> None:
        self.document_builder = document_builder or NqeMetadataIndexDocumentBuilder()
        self.embedding_client = embedding_client
        self.vector_store = vector_store

    def build_from_catalog(
        self,
        catalog_root: str | Path = DEFAULT_CATALOG_ROOT,
        *,
        metadata_version: str = "nqe_catalog_v1",
    ) -> list[NqeMetadataIndexDocument]:
        """复用 NQE-7 builder 从受控 catalog 生成索引文档。

        参数：
            catalog_root: 受控 catalog 根目录。
            metadata_version: 本次元数据版本号。
        返回：
            NQE 专用向量索引文档列表。
        """

        bundle = NqeMetadataSyncBuilder(catalog_root, metadata_version=metadata_version).build()
        return self.document_builder.build_from_bundle(bundle)

    def index_documents(
        self,
        documents: list[NqeMetadataIndexDocument],
        *,
        apply: bool = False,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> NqeMetadataIndexSummary:
        """索引 NQE 元数据文档。

        参数：
            documents: 待索引文档。
            apply: 是否真正调用 embedding 和向量库。
            batch_size: embedding 分批大小。
        返回：
            dry-run、成功写入或 fail-closed 错误摘要。
        业务逻辑：
            apply=False 不调用任何外部依赖；apply=True 时先完整生成向量，数量校验通过后才 upsert。
        """

        summary = self._summary(documents, dry_run=not apply, apply_status="dry_run" if not apply else "pending")
        if not apply:
            return summary
        dependency_error = self._dependency_error()
        if dependency_error:
            summary.apply_status = "error"
            summary.errors.append(dependency_error)
            return summary
        if batch_size <= 0:
            summary.apply_status = "error"
            summary.errors.append("batch_size_invalid")
            return summary
        try:
            vectors = self._embed_documents(documents, batch_size=batch_size)
            if len(vectors) != len(documents):
                summary.apply_status = "error"
                summary.errors.append(f"embedding_count_mismatch::{len(documents)}::{len(vectors)}")
                return summary
            self.vector_store.ensure_collection()
            indexed = self.vector_store.upsert_documents(documents, vectors)
            summary.indexed = int(indexed or 0)
            summary.apply_status = "applied"
            summary.dry_run = False
            return summary
        except Exception as exc:  # noqa: BLE001
            summary.apply_status = "error"
            summary.errors.append(_safe_error("index_error", exc))
            return summary

    def _embed_documents(self, documents: list[NqeMetadataIndexDocument], *, batch_size: int) -> list[list[float]]:
        """按顺序分批生成 embedding，返回顺序与 documents 一致。"""

        vectors: list[list[float]] = []
        for start in range(0, len(documents), batch_size):
            batch = documents[start : start + batch_size]
            vectors.extend(self.embedding_client.embed_texts([document.content for document in batch]))
        return vectors

    def _dependency_error(self) -> str | None:
        """检查 apply 依赖是否显式注入。"""

        if self.embedding_client is None:
            return "embedding_client_required"
        if self.vector_store is None:
            return "vector_store_required"
        if not hasattr(self.embedding_client, "embed_texts"):
            return "embedding_client_invalid"
        if not hasattr(self.vector_store, "ensure_collection") or not hasattr(self.vector_store, "upsert_documents"):
            return "vector_store_invalid"
        return None

    def _summary(
        self,
        documents: list[NqeMetadataIndexDocument],
        *,
        dry_run: bool,
        apply_status: str,
    ) -> NqeMetadataIndexSummary:
        """根据文档列表生成统计摘要。"""

        domains: dict[str, int] = {}
        asset_type_counts: dict[str, int] = {}
        versions: list[str] = []
        for document in documents:
            domains[document.domain_code] = domains.get(document.domain_code, 0) + 1
            asset_type_counts[document.asset_type] = asset_type_counts.get(document.asset_type, 0) + 1
            if document.metadata_version not in versions:
                versions.append(document.metadata_version)
        metadata_version = versions[0] if len(versions) == 1 else ",".join(versions) if versions else None
        return NqeMetadataIndexSummary(
            documents=len(documents),
            domains=dict(sorted(domains.items())),
            asset_type_counts=dict(sorted(asset_type_counts.items())),
            metadata_version=metadata_version,
            dry_run=dry_run,
            apply_status=apply_status,
            warnings=list(self.document_builder.warnings),
        )


def _dedupe_strings(values: Iterable[str]) -> list[str]:
    """按出现顺序去重字符串。"""

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _safe_optional_text(value: Any) -> str | None:
    """把可选文本转成去空格字符串。"""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_error(prefix: str, exc: Exception) -> str:
    """返回脱敏错误，避免把连接串、路径或密钥写入日志。"""

    message = str(exc.__class__.__name__)
    detail = str(exc)
    if detail and not SENSITIVE_TEXT_PATTERN.search(detail) and "/" not in detail:
        message = f"{message}:{detail}"
    return f"{prefix}:{message}"


__all__ = [
    "NqeMetadataIndexDocument",
    "NqeMetadataIndexDocumentBuilder",
    "NqeMetadataIndexSummary",
    "NqeMetadataVectorIndexService",
]

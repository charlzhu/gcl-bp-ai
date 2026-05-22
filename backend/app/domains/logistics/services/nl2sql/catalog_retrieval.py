from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from backend.app.core.config import settings
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import (
    LogisticsCatalogColumn,
    LogisticsCatalogDimension,
    LogisticsCatalogExample,
    LogisticsCatalogJoin,
    LogisticsCatalogMetric,
    LogisticsCatalogRule,
    LogisticsCatalogTable,
    LogisticsSemanticCatalog,
    LogisticsSemanticCatalogLoader,
)

LOGISTICS_NL2SQL_CATALOG_COLLECTION_SUFFIX = "logistics_nl2sql_catalog"
FORBIDDEN_RECALL_IDENTIFIER_TOKENS = (
    "sys_query_log",
    "v_sap",
    "sap_mid",
    "oracle_mid",
    "oracle_",
    "ods_",
)
FORBIDDEN_RECALL_SOURCE_SYSTEMS = {"sap", "sap_mid", "oracle", "oracle_mid", "ods"}
FORBIDDEN_RECALL_SECRET_KEYS = {
    "api_key",
    "apikey",
    "secret",
    "password",
    "passwd",
    "token",
    "access_token",
    "refresh_token",
}


def _build_dashscope_service_url(base_url: str, endpoint_path: str) -> str:
    """构造 DashScope service 类接口 URL。

    参数：
        base_url: 项目配置的大模型基础地址，可能是 OpenAI 兼容模式地址。
        endpoint_path: DashScope service 接口路径，例如 rerank 服务路径。

    返回：
        可用于 httpx 调用的完整 URL。

    业务逻辑：
        主 LLM 与 embedding 使用 OpenAI 兼容模式 `/compatible-mode/v1`；但 rerank
        属于 DashScope service API，需要挂在站点根路径下。这里仅在 service
        endpoint 场景剥离兼容模式后缀，避免把 rerank 错误拼成
        `/compatible-mode/v1/api/v1/services/...` 导致真实 provider 返回 404。
    """

    normalized_base = (base_url or "").rstrip("/")
    normalized_path = (endpoint_path or "").strip("/")
    if normalized_path.startswith("api/v1/services/"):
        normalized_base = re.sub(r"/compatible-mode/v1$", "", normalized_base)
    return normalized_base + "/" + normalized_path


def _configured_provider_proxy_url() -> str | None:
    """读取 provider 调用使用的可选代理地址。

    返回：
        显式配置的代理 URL，或标准环境变量中的代理 URL；均不在日志中输出。
    业务逻辑：
        真实百炼 provider 门禁可能需要本地 SOCKS 代理。优先使用项目专用
        `LLM_ALL_PROXY/LLM_HTTPS_PROXY/LLM_HTTP_PROXY`，未配置时兼容系统标准
        `ALL_PROXY/HTTPS_PROXY/HTTP_PROXY` 与小写形式。
    """

    candidates = [
        getattr(settings, "llm_all_proxy", ""),
        getattr(settings, "llm_https_proxy", ""),
        getattr(settings, "llm_http_proxy", ""),
        os.getenv("ALL_PROXY"),
        os.getenv("HTTPS_PROXY"),
        os.getenv("HTTP_PROXY"),
        os.getenv("all_proxy"),
        os.getenv("https_proxy"),
        os.getenv("http_proxy"),
    ]
    for value in candidates:
        proxy_url = str(value or "").strip()
        if proxy_url:
            return proxy_url
    return None


def _build_provider_httpx_client_kwargs(*, timeout_seconds: float) -> dict[str, Any]:
    """构造 provider HTTP 客户端参数。

    参数：
        timeout_seconds: 单次 provider 调用超时时间。
    返回：
        可传给 `httpx.Client` 的参数字典；显式代理存在时包含 `proxy`。
    业务逻辑：
        embedding、rerank、SQLPlan LLM 和 provider smoke 共用同一套代理策略，
        以保证 SOCKS 配置在所有真实 provider gate 中表现一致。
    """

    kwargs: dict[str, Any] = {"timeout": timeout_seconds, "trust_env": True}
    proxy_url = _configured_provider_proxy_url()
    if proxy_url:
        kwargs["proxy"] = proxy_url
    return kwargs


def _build_provider_openai_client_kwargs(
    *,
    base_url: str | None,
    api_key: str | None,
    timeout_seconds: float,
    max_retries: int = 0,
) -> dict[str, Any]:
    """构造 OpenAI 兼容客户端参数。

    参数：
        base_url: OpenAI 兼容接口基础地址。
        api_key: provider API Key。
        timeout_seconds: 调用超时时间。
        max_retries: OpenAI 客户端重试次数。
    返回：
        可传给 `OpenAI(...)` 的参数；若配置代理则内置 httpx.Client。
    """

    kwargs: dict[str, Any] = {
        "base_url": base_url,
        "api_key": api_key,
        "max_retries": max_retries,
    }
    httpx_kwargs = _build_provider_httpx_client_kwargs(timeout_seconds=timeout_seconds)
    if "proxy" in httpx_kwargs:
        import httpx

        kwargs["http_client"] = httpx.Client(**httpx_kwargs)
    else:
        kwargs["timeout"] = timeout_seconds
    return kwargs


class LogisticsCatalogRecallDocument(BaseModel):

    """可进入 M2 embedding/Milvus/rerank 的受控 Semantic Catalog 文档。

    业务逻辑：
        文档只承载 catalog 元信息和业务语义，不携带可执行 SQL，也不允许 SAP/ODS/日志表等
        非中间库来源进入向量索引。后续 SQLPlan 只能通过 catalog_id 回查白名单 catalog。
    """

    model_config = ConfigDict(extra="forbid")

    catalog_id: str
    catalog_version: str
    doc_type: Literal["table", "column", "metric", "dimension", "rule", "join", "example"]
    title: str
    content: str
    keywords: list[str] = Field(default_factory=list)
    source_table: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_safe_recall_payload(self) -> "LogisticsCatalogRecallDocument":
        """阻断非白名单来源进入召回链路。"""

        for value in _iter_payload_strings(
            {
                "catalog_id": self.catalog_id,
                "title": self.title,
                "content": self.content,
                "keywords": self.keywords,
                "source_table": self.source_table,
                "metadata": self.metadata,
            }
        ):
            forbidden = _find_forbidden_recall_identifier(value)
            if forbidden:
                raise ValueError(f"forbidden_recall_identifier::{forbidden}")
            secret = _find_secret_like_text(value)
            if secret:
                raise ValueError(f"forbidden_recall_secret::{secret}")

        secret_key = _find_secret_key(self.metadata)
        if secret_key:
            raise ValueError(f"forbidden_recall_secret::{secret_key}")

        source_system = str(self.metadata.get("source_system") or "").strip().lower()
        if source_system in FORBIDDEN_RECALL_SOURCE_SYSTEMS:
            raise ValueError(f"forbidden_source_system::{source_system}")
        return self


class LogisticsCatalogRecallHit(BaseModel):
    """Milvus/Rerank 命中的单条受控召回结果。"""

    model_config = ConfigDict(extra="forbid")

    document: LogisticsCatalogRecallDocument
    vector_score: float = 0.0
    rerank_score: float | None = None
    source: str = "milvus"


class LogisticsCatalogRerankScore(BaseModel):
    """Reranker 对 catalog_id 的精排分数。"""

    model_config = ConfigDict(extra="forbid")

    catalog_id: str
    score: float


class LogisticsCatalogRecallResult(BaseModel):
    """M2 index/recall 的受控返回对象。"""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "disabled", "empty", "error"]
    hits: list[LogisticsCatalogRecallHit] = Field(default_factory=list)
    error: str | None = None
    indexed_count: int = 0


class LogisticsCatalogRecallDocumentBuilder:
    """把 M1 Semantic Catalog 转换成 M2 召回文档。"""

    def __init__(self, *, max_content_chars: int = 1200) -> None:
        self.max_content_chars = max_content_chars

    def build(self, catalog: LogisticsSemanticCatalog) -> list[LogisticsCatalogRecallDocument]:
        """生成 table/column/metric/dimension/rule/join 文档。"""

        documents: list[LogisticsCatalogRecallDocument] = []
        for table in catalog.allowed_tables():
            safe_columns = _safe_recall_columns(table)
            documents.append(self._table_document(catalog.catalog_version, table, safe_columns))
            documents.extend(
                self._column_document(catalog.catalog_version, table, column) for column in safe_columns
            )
        documents.extend(self._metric_document(catalog.catalog_version, metric) for metric in catalog.metrics)
        documents.extend(self._dimension_document(catalog.catalog_version, dimension) for dimension in catalog.dimensions)
        documents.extend(self._rule_document(catalog.catalog_version, rule) for rule in catalog.rules)
        documents.extend(self._join_document(catalog.catalog_version, join) for join in catalog.joins)
        documents.extend(self._example_document(catalog.catalog_version, example) for example in catalog.examples)
        return documents

    def _table_document(
        self,
        catalog_version: str,
        table: LogisticsCatalogTable,
        columns: list[LogisticsCatalogColumn],
    ) -> LogisticsCatalogRecallDocument:
        keywords = _dedupe_strings(
            [table.table_name, table.display_name, table.grain or ""]
            + [column.name for column in columns]
            + [column.business_name or "" for column in columns]
        )
        content = self._content(
            "表",
            table.display_name,
            f"表标识 {table.table_name}",
            f"粒度 {table.grain}" if table.grain else "",
            "字段 " + "，".join(
                _format_column_for_content(column) for column in columns[:30]
            ),
        )
        return LogisticsCatalogRecallDocument(
            catalog_id=f"table:{table.table_name}",
            catalog_version=catalog_version,
            doc_type="table",
            title=table.display_name,
            content=content,
            keywords=keywords,
            source_table=table.table_name,
            metadata={
                "table": table.table_name,
                "source_system": table.source_system,
                "domain": table.domain,
                "grain": table.grain,
                "allowed_read": table.allowed_read,
                "columns": [column.name for column in columns],
            },
        )

    def _column_document(
        self,
        catalog_version: str,
        table: LogisticsCatalogTable,
        column: LogisticsCatalogColumn,
    ) -> LogisticsCatalogRecallDocument:
        title = column.business_name or column.name
        # 构造取值示例文本
        examples_text = ""
        if column.field_value_examples:
            examples_text = "取值示例 " + "，".join(column.field_value_examples[:10])
        content = self._content(
            "字段",
            title,
            f"字段标识 {table.table_name}.{column.name}",
            f"类型 {column.data_type}",
            f"语义角色 {column.semantic_role}" if column.semantic_role else "",
            f"所属表 {table.display_name}",
            examples_text,
        )
        return LogisticsCatalogRecallDocument(
            catalog_id=f"column:{table.table_name}.{column.name}",
            catalog_version=catalog_version,
            doc_type="column",
            title=title,
            content=content,
            keywords=_dedupe_strings([column.name, title, column.semantic_role or "", table.table_name, table.display_name]),
            source_table=table.table_name,
            metadata={
                "table": table.table_name,
                "column": column.name,
                "data_type": column.data_type,
                "business_name": column.business_name,
                "semantic_role": column.semantic_role,
                "nullable": column.nullable,
                "source_system": table.source_system,
            },
        )

    def _metric_document(self, catalog_version: str, metric: LogisticsCatalogMetric) -> LogisticsCatalogRecallDocument:
        # 构造取值示例、计算公式、关联列文本
        examples_text = ""
        if metric.field_value_examples:
            examples_text = "取值示例 " + "，".join(metric.field_value_examples[:10])
        formula_text = ""
        if metric.calculation_formula:
            formula_text = "计算公式 " + metric.calculation_formula
        calculation_text = ""
        if metric.calculation_notes:
            calculation_text = "计算说明 " + metric.calculation_notes
        relevant_text = ""
        if metric.relevant_columns:
            relevant_text = "关联字段 " + "，".join(metric.relevant_columns[:20])
        content = self._content(
            "指标",
            metric.display_name,
            f"指标标识 {metric.metric_id}",
            f"同义词 {'，'.join(metric.aliases)}" if metric.aliases else "",
            f"单位 {metric.unit}" if metric.unit else "",
            f"聚合 {metric.aggregation}" if metric.aggregation else "",
            _business_safe_text(metric.business_note or ""),
            examples_text,
            formula_text,
            calculation_text,
            relevant_text,
            "依赖字段 " + "，".join(metric.source_columns) if metric.source_columns else "",
        )
        return LogisticsCatalogRecallDocument(
            catalog_id=f"metric:{metric.metric_id}",
            catalog_version=catalog_version,
            doc_type="metric",
            title=metric.display_name,
            content=content,
            keywords=_dedupe_strings([metric.metric_id, metric.display_name, metric.unit or "", *metric.aliases]),
            source_table=metric.table,
            metadata={
                "metric_id": metric.metric_id,
                "table": metric.table,
                "unit": metric.unit,
                "aggregation": metric.aggregation,
                "source_columns": list(metric.source_columns),
            },
        )

    def _dimension_document(
        self,
        catalog_version: str,
        dimension: LogisticsCatalogDimension,
    ) -> LogisticsCatalogRecallDocument:
        # 构造取值示例文本
        examples_text = ""
        if dimension.field_value_examples:
            examples_text = "取值示例 " + "，".join(dimension.field_value_examples[:10])
        content = self._content(
            "维度",
            dimension.display_name,
            f"维度标识 {dimension.dimension_id}",
            f"同义词 {'，'.join(dimension.aliases)}" if dimension.aliases else "",
            f"字段 {dimension.table}.{dimension.column}" if dimension.table else f"字段 {dimension.column}",
            dimension.business_note or "",
            examples_text,
        )
        return LogisticsCatalogRecallDocument(
            catalog_id=f"dimension:{dimension.dimension_id}",
            catalog_version=catalog_version,
            doc_type="dimension",
            title=dimension.display_name,
            content=content,
            keywords=_dedupe_strings([dimension.dimension_id, dimension.display_name, dimension.column, *dimension.aliases]),
            source_table=dimension.table,
            metadata={
                "dimension_id": dimension.dimension_id,
                "table": dimension.table,
                "column": dimension.column,
            },
        )

    def _rule_document(self, catalog_version: str, rule: LogisticsCatalogRule) -> LogisticsCatalogRecallDocument:
        content = self._content(
            "规则",
            rule.display_name,
            f"规则标识 {rule.rule_id}",
            f"类型 {rule.rule_type}",
            f"同义词 {'，'.join(rule.aliases)}" if rule.aliases else "",
            f"动作 {rule.action}",
            rule.business_message or "",
        )
        return LogisticsCatalogRecallDocument(
            catalog_id=f"rule:{rule.rule_id}",
            catalog_version=catalog_version,
            doc_type="rule",
            title=rule.display_name,
            content=content,
            keywords=_dedupe_strings([rule.rule_id, rule.display_name, rule.rule_type, rule.action, *rule.aliases]),
            source_table=None,
            metadata={
                "rule_id": rule.rule_id,
                "rule_type": rule.rule_type,
                "action": rule.action,
                "relax_filters": rule.relax_filters,
            },
        )

    def _join_document(self, catalog_version: str, join: LogisticsCatalogJoin) -> LogisticsCatalogRecallDocument:
        content = self._content(
            "关联",
            join.join_id,
            f"左表 {join.left_table}",
            f"右表 {join.right_table}",
            f"关联类型 {join.join_type}",
            join.business_note or "",
        )
        return LogisticsCatalogRecallDocument(
            catalog_id=f"join:{join.join_id}",
            catalog_version=catalog_version,
            doc_type="join",
            title=join.join_id,
            content=content,
            keywords=_dedupe_strings([join.join_id, join.left_table, join.right_table, join.join_type]),
            source_table=join.left_table,
            metadata={
                "join_id": join.join_id,
                "left_table": join.left_table,
                "right_table": join.right_table,
                "join_type": join.join_type,
                # 召回 payload 只暴露受控关联语义，不携带 join.on 等 SQL-like 片段；
                # 后续 SQLPlan 必须通过 catalog_id 回查后端白名单规则。
                "join_condition_count": len(join.on),
            },
        )

    def _example_document(self, catalog_version: str, example: LogisticsCatalogExample) -> LogisticsCatalogRecallDocument:
        content = self._content(
            "示例",
            example.display_name,
            f"示例标识 {example.example_id}",
            f"自然语言 {example.question}",
            f"查询类型 {example.query_type}",
            "指标 " + "，".join(example.metrics) if example.metrics else "",
            "维度 " + "，".join(example.dimensions) if example.dimensions else "",
            "分组 " + "，".join(example.group_by) if example.group_by else "",
            "规则 " + "，".join(example.business_rules) if example.business_rules else "",
            example.notes or "",
        )
        return LogisticsCatalogRecallDocument(
            catalog_id=f"example:{example.example_id}",
            catalog_version=catalog_version,
            doc_type="example",
            title=example.display_name,
            content=content,
            keywords=_dedupe_strings(
                [
                    example.example_id,
                    example.display_name,
                    example.question,
                    example.query_type,
                    *example.metrics,
                    *example.dimensions,
                    *example.business_rules,
                ]
            ),
            source_table=None,
            metadata={
                "example_id": example.example_id,
                "domain": example.domain,
                "query_type": example.query_type,
                "metrics": list(example.metrics),
                "dimensions": list(example.dimensions),
                "group_by": list(example.group_by),
                "business_rules": list(example.business_rules),
                "catalog_refs": list(example.catalog_refs),
            },
        )

    def _content(self, *parts: str) -> str:
        text = "；".join(part.strip() for part in parts if str(part).strip())
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= self.max_content_chars:
            return text
        return text[: self.max_content_chars - 1].rstrip() + "…"


class LogisticsBailianEmbeddingClient:
    """百炼 Qwen3-Embedding-4B embedding 客户端。

    测试通过注入 fake client；真实调用使用 OpenAI-compatible embeddings API。
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        client: Any | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.enabled = enabled
        self.base_url = settings.llm_base_url if base_url is None else base_url
        self.api_key = settings.llm_api_key if api_key is None else api_key
        self.model = settings.embedding_model if model is None else model
        self._client = client
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        return bool(self.enabled and (self._client or (self.base_url and self.api_key and self.model)))

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.is_available():
            raise RuntimeError("embedding_unavailable")
        if not texts:
            return []
        if self._client and hasattr(self._client, "embed_texts"):
            return self._client.embed_texts(texts)
        try:
            from openai import OpenAI

            openai_kwargs = _build_provider_openai_client_kwargs(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout_seconds=self.timeout_seconds,
                max_retries=0,
            )
            client = self._client or OpenAI(**openai_kwargs)
            response = client.embeddings.create(model=self.model, input=texts)
            return [list(item.embedding) for item in response.data]
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(_safe_error("embedding_error", exc)) from exc


class LogisticsBailianRerankClient:
    """百炼 Qwen3-Reranker 客户端。

    优先支持测试注入的 `rerank` 方法；真实调用按 DashScope rerank HTTP 形态发送，失败时由上层
    fail-closed，不降级为未精排结果。
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        endpoint_path: str | None = None,
        client: Any | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.enabled = enabled
        self.base_url = settings.llm_base_url if base_url is None else base_url
        self.api_key = settings.llm_api_key if api_key is None else api_key
        self.model = settings.rerank_model if model is None else model
        self.endpoint_path = settings.rerank_endpoint_path if endpoint_path is None else endpoint_path
        self._client = client
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        return bool(self.enabled and (self._client or (self.base_url and self.api_key and self.model)))

    def rerank(
        self,
        *,
        query: str,
        documents: list[LogisticsCatalogRecallHit],
        top_n: int,
    ) -> list[LogisticsCatalogRerankScore]:
        if not self.is_available():
            raise RuntimeError("rerank_unavailable")
        if not documents:
            return []
        if self._client and hasattr(self._client, "rerank"):
            raw = self._client.rerank(query=query, documents=documents, top_n=top_n)
            return _coerce_rerank_scores(raw, documents)
        try:
            import httpx

            url = _build_dashscope_service_url(self.base_url, self.endpoint_path)
            payload = {
                "model": self.model,
                "input": {"query": query, "documents": [hit.document.content for hit in documents]},
                "parameters": {"top_n": top_n, "return_documents": False},
            }
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            httpx_kwargs = _build_provider_httpx_client_kwargs(timeout_seconds=self.timeout_seconds)
            with httpx.Client(**httpx_kwargs) as http_client:
                response = http_client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return _coerce_rerank_scores(response.json(), documents)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(_safe_error("rerank_error", exc)) from exc


class LogisticsMilvusCatalogVectorStore:
    """物流 NL2SQL catalog 的 Milvus 向量索引适配器。"""

    def __init__(
        self,
        *,
        collection_name: str | None = None,
        dimension: int | None = None,
        uri: str | None = None,
        client: Any | None = None,
        metric_type: str = "COSINE",
    ) -> None:
        prefix = settings.milvus_collection_prefix or "gcl_bp_ai"
        self.collection_name = collection_name or f"{prefix}_{LOGISTICS_NL2SQL_CATALOG_COLLECTION_SUFFIX}"
        self.dimension = dimension or settings.embedding_dimension
        self.uri = uri or _milvus_uri(settings.milvus_host, settings.milvus_port)
        self._client = client
        self.metric_type = metric_type

    def is_available(self) -> bool:
        return bool(self._client or (self.uri and self.collection_name and self.dimension > 0))

    def _client_or_create(self) -> Any:
        if self._client is not None:
            return self._client
        from pymilvus import MilvusClient

        token = None
        if settings.milvus_user or settings.milvus_password:
            token = f"{settings.milvus_user}:{settings.milvus_password}"
        self._client = MilvusClient(uri=self.uri, token=token)
        return self._client

    def ensure_collection(self) -> None:
        client = self._client_or_create()
        if hasattr(client, "has_collection") and client.has_collection(self.collection_name):
            return
        if hasattr(client, "create_schema") and hasattr(client, "prepare_index_params"):
            schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
            varchar = _milvus_data_type("VARCHAR")
            float_vector = _milvus_data_type("FLOAT_VECTOR")
            schema.add_field(field_name="id", datatype=varchar, is_primary=True, max_length=64)
            schema.add_field(field_name="catalog_id", datatype=varchar, max_length=256)
            schema.add_field(field_name="catalog_version", datatype=varchar, max_length=128)
            schema.add_field(field_name="doc_type", datatype=varchar, max_length=32)
            schema.add_field(field_name="title", datatype=varchar, max_length=512)
            schema.add_field(field_name="content", datatype=varchar, max_length=4096)
            schema.add_field(field_name="keywords_json", datatype=varchar, max_length=4096)
            schema.add_field(field_name="metadata_json", datatype=varchar, max_length=4096)
            schema.add_field(field_name="source_table", datatype=varchar, max_length=256)
            schema.add_field(field_name="vector", datatype=float_vector, dim=self.dimension)

            index_params = client.prepare_index_params()
            index_params.add_index(
                field_name="vector",
                index_type="AUTOINDEX",
                metric_type=self.metric_type,
            )
            client.create_collection(
                collection_name=self.collection_name,
                schema=schema,
                index_params=index_params,
                consistency_level="Strong",
            )
            return
        client.create_collection(
            collection_name=self.collection_name,
            dimension=self.dimension,
            metric_type=self.metric_type,
            consistency_level="Strong",
        )

    def upsert_documents(self, documents: list[LogisticsCatalogRecallDocument], vectors: list[list[float]]) -> int:
        if len(documents) != len(vectors):
            raise ValueError(f"embedding_count_mismatch::{len(documents)}::{len(vectors)}")
        data = [self._record_for_document(document, vector) for document, vector in zip(documents, vectors, strict=True)]
        client = self._client_or_create()
        if hasattr(client, "upsert"):
            client.upsert(collection_name=self.collection_name, data=data)
        else:
            client.insert(collection_name=self.collection_name, data=data)
        return len(data)

    def search(self, vector: list[float], *, top_k: int) -> list[LogisticsCatalogRecallHit]:
        client = self._client_or_create()
        raw = client.search(
            collection_name=self.collection_name,
            data=[vector],
            anns_field="vector",
            limit=top_k,
            output_fields=[
                "catalog_id",
                "catalog_version",
                "doc_type",
                "title",
                "content",
                "keywords_json",
                "metadata_json",
                "source_table",
            ],
        )
        first_batch = raw[0] if raw else []
        return [_coerce_milvus_hit(item) for item in first_batch]

    def _record_for_document(self, document: LogisticsCatalogRecallDocument, vector: list[float]) -> dict[str, Any]:
        return {
            "id": _stable_doc_id(document),
            "vector": list(vector),
            "catalog_id": document.catalog_id,
            "catalog_version": document.catalog_version,
            "doc_type": document.doc_type,
            "title": document.title,
            "content": document.content,
            "keywords_json": json.dumps(document.keywords, ensure_ascii=False),
            "metadata_json": json.dumps(document.metadata, ensure_ascii=False),
            "source_table": document.source_table or "",
        }


class LogisticsCatalogRecallService:
    """M2 catalog index/recall 编排服务。"""

    def __init__(
        self,
        *,
        catalog_loader: LogisticsSemanticCatalogLoader | None = None,
        document_builder: Any | None = None,
        embedding_client: Any | None = None,
        vector_store: Any | None = None,
        reranker: Any | None = None,
        vector_top_k: int | None = None,
        rerank_top_k: int | None = None,
        rerank_min_score: float | None = None,
        enable_keyword_fallback: bool = False,
    ) -> None:
        self.catalog_loader = catalog_loader or LogisticsSemanticCatalogLoader()
        self.document_builder = document_builder or LogisticsCatalogRecallDocumentBuilder()
        self.embedding_client = embedding_client or LogisticsBailianEmbeddingClient()
        self.vector_store = vector_store or LogisticsMilvusCatalogVectorStore()
        self.reranker = reranker or LogisticsBailianRerankClient()
        self.vector_top_k = vector_top_k or settings.nl2sql_recall_top_k
        self.rerank_top_k = rerank_top_k or settings.nl2sql_rerank_top_k
        self.rerank_min_score = settings.nl2sql_rerank_min_score if rerank_min_score is None else rerank_min_score
        self._allowed_catalog_ids_cache: set[str] | None = None
        self._canonical_documents_cache: dict[str, LogisticsCatalogRecallDocument] | None = None
        self._enable_keyword_fallback = enable_keyword_fallback

    def index_catalog(self, *, catalog: LogisticsSemanticCatalog | Any | None = None) -> LogisticsCatalogRecallResult:
        """把 catalog 文档写入 Milvus；任一依赖不可用时 fail-closed。"""

        availability_error = self._index_availability_error()
        if availability_error:
            return LogisticsCatalogRecallResult(status="disabled", error=availability_error)
        try:
            resolved_catalog = self.catalog_loader.load() if catalog is None else catalog
            documents = self.document_builder.build(resolved_catalog)
            if not documents:
                return LogisticsCatalogRecallResult(status="empty", error="catalog_documents_empty")
            vectors = self._embed_documents_for_index(documents)
            if len(vectors) != len(documents):
                return LogisticsCatalogRecallResult(
                    status="error",
                    error=f"embedding_count_mismatch::{len(documents)}::{len(vectors)}",
                )
            self.vector_store.ensure_collection()
            indexed = self.vector_store.upsert_documents(documents, vectors)
            return LogisticsCatalogRecallResult(status="ok", indexed_count=indexed)
        except Exception as exc:  # noqa: BLE001
            return LogisticsCatalogRecallResult(status="error", error=_safe_error("index_error", exc))

    def _embed_documents_for_index(self, documents: list[LogisticsCatalogRecallDocument]) -> list[list[float]]:
        """分批生成 catalog 文档向量。

        参数：
            documents: 已通过白名单与脱敏校验的 Semantic Catalog 召回文档。

        返回：
            与 documents 顺序一一对应的向量列表。

        业务逻辑：
            百炼 `text-embedding-v4` 单次请求存在批量上限，真实 reindex 不能一次性
            提交全部 catalog 文档。这里固定按 10 条分批，既兼容当前 provider，也保持
            Milvus upsert 前的文档顺序稳定，便于审计和回放。
        """

        vectors: list[list[float]] = []
        batch_size = 10
        for start in range(0, len(documents), batch_size):
            batch = documents[start : start + batch_size]
            vectors.extend(self.embedding_client.embed_texts([document.content for document in batch]))
        return vectors

    def recall(
        self,
        *,
        question: str,
        normalized_question: str | None = None,
        slot_summary: str | None = None,
    ) -> LogisticsCatalogRecallResult:
        """基于问题召回并精排 catalog 文档；不可用或不可信时 fail-closed。"""

        query = self._query_text(question=question, normalized_question=normalized_question, slot_summary=slot_summary)
        if not query:
            return LogisticsCatalogRecallResult(status="empty", error="query_empty")
        availability_error = self._recall_availability_error()
        if availability_error:
            if self._enable_keyword_fallback:
                return self._keyword_fallback_recall(query)
            return LogisticsCatalogRecallResult(status="disabled", error=availability_error)
        try:
            vectors = self.embedding_client.embed_texts([query])
            if not vectors:
                return LogisticsCatalogRecallResult(status="empty", error="embedding_empty")
            raw_hits = self.vector_store.search(vectors[0], top_k=self.vector_top_k)
            hits = [self._coerce_hit(raw_hit) for raw_hit in raw_hits]
            canonical_hits = self._canonicalize_hits(hits)
            unique_hits = self._dedupe_hits(canonical_hits)
            if not unique_hits:
                return LogisticsCatalogRecallResult(status="empty", error="milvus_hits_empty")
            rerank_scores = self.reranker.rerank(
                query=query,
                documents=unique_hits,
                top_n=self.rerank_top_k,
            )
            reranked = self._apply_rerank_scores(unique_hits, rerank_scores)
            if not reranked:
                return LogisticsCatalogRecallResult(status="empty", error="rerank_hits_empty")
            return LogisticsCatalogRecallResult(status="ok", hits=reranked)
        except (ValidationError, ValueError) as exc:
            return LogisticsCatalogRecallResult(status="error", error=_safe_error("recall_validation_error", exc))
        except Exception as exc:  # noqa: BLE001
            return LogisticsCatalogRecallResult(status="error", error=_safe_error("recall_error", exc))

    def _keyword_fallback_recall(self, query: str) -> LogisticsCatalogRecallResult:
        """当向量检索不可用时，通过 keyword 匹配本地 canonical documents 做简易召回。

        参数：
            query: 已构建的查询文本。
        返回：
            与向量 recall 相同结构的召回结果。
        业务逻辑：
            1. 只在 enable_keyword_fallback=True 时被调用。
            2. 对 query 做简单 token 化，匹配 canonical documents 的 keywords/title/content。
            3. 得分>0 才返回，否则返回 empty。
        """
        try:
            documents = self._canonical_documents()
            if not documents:
                return LogisticsCatalogRecallResult(status="empty", error="catalog_documents_empty")
            query_lower = query.lower()
            query_tokens = {t.strip(".,!?\"'()[]{}") for t in query_lower.split() if len(t.strip(".,!?\"'()[]{}")) > 1}
            scored: list[tuple[float, str]] = []
            for doc_id, doc in documents.items():
                score = 0.0
                # keyword 精确匹配
                for kw in doc.keywords:
                    if kw.lower() in query_lower:
                        score += 5.0
                # title 匹配
                title_lower = doc.title.lower()
                for token in query_tokens:
                    if token in title_lower:
                        score += 3.0
                if score > 0:
                    scored.append((score, doc_id))
            if not scored:
                return LogisticsCatalogRecallResult(status="empty", error="keyword_fallback_no_match")
            scored.sort(key=lambda x: x[0], reverse=True)
            top_n = min(self.vector_top_k, len(scored))
            hits: list[LogisticsCatalogRecallHit] = []
            for _, doc_id in scored[:top_n]:
                doc = documents[doc_id]
                hits.append(LogisticsCatalogRecallHit(
                    document=doc,
                    vector_score=0.0,
                    rerank_score=None,
                    source="keyword_fallback",
                ))
            return LogisticsCatalogRecallResult(status="ok", hits=hits)
        except Exception as exc:  # noqa: BLE001
            return LogisticsCatalogRecallResult(status="error", error=_safe_error("keyword_fallback_error", exc))

    def _index_availability_error(self) -> str | None:
        if not self.embedding_client.is_available():
            return "embedding_unavailable"
        if not self.vector_store.is_available():
            return "milvus_unavailable"
        return None

    def _recall_availability_error(self) -> str | None:
        index_error = self._index_availability_error()
        if index_error:
            return index_error
        if not self.reranker.is_available():
            return "rerank_unavailable"
        return None

    def _allowed_catalog_ids(self) -> set[str]:
        if self._allowed_catalog_ids_cache is None:
            self._allowed_catalog_ids_cache = set(self._canonical_documents())
        return self._allowed_catalog_ids_cache

    def _canonical_documents(self) -> dict[str, LogisticsCatalogRecallDocument]:
        """读取当前受控 catalog 文档，用于把 Milvus 命中重建为可信 payload。"""

        if self._canonical_documents_cache is None:
            catalog = self.catalog_loader.load()
            documents = self.document_builder.build(catalog)
            self._canonical_documents_cache = {document.catalog_id: document for document in documents}
        return self._canonical_documents_cache

    def _validate_hits_against_catalog(self, hits: list[LogisticsCatalogRecallHit]) -> None:
        allowed_catalog_ids = self._allowed_catalog_ids()
        for hit in hits:
            if hit.document.catalog_id not in allowed_catalog_ids:
                raise ValueError(f"catalog_hit_not_allowed::{hit.document.catalog_id}")

    def _canonicalize_hits(self, hits: list[LogisticsCatalogRecallHit]) -> list[LogisticsCatalogRecallHit]:
        """按 catalog_id 回查当前 catalog，丢弃 Milvus 中不可信的 title/content/metadata。
        不在 canonical 中的 hit 被跳过而非抛异常，以支持多域 catalog 的混合召回。
        """

        canonical_documents = self._canonical_documents()
        canonical_hits: list[LogisticsCatalogRecallHit] = []
        for hit in hits:
            canonical_document = canonical_documents.get(hit.document.catalog_id)
            if canonical_document is None:
                # 不在当前 canonical 中的 catalog_id 直接跳过（多域混合召回场景）
                continue
            if hit.document.catalog_version != canonical_document.catalog_version:
                continue
            canonical_hits.append(
                LogisticsCatalogRecallHit(
                    document=canonical_document,
                    vector_score=hit.vector_score,
                    rerank_score=hit.rerank_score,
                    source=hit.source,
                )
            )
        return canonical_hits

    @staticmethod
    def _query_text(*, question: str, normalized_question: str | None, slot_summary: str | None) -> str:
        return "\n".join(_dedupe_strings([question, normalized_question or "", slot_summary or ""]))

    @staticmethod
    def _coerce_hit(raw_hit: Any) -> LogisticsCatalogRecallHit:
        if isinstance(raw_hit, LogisticsCatalogRecallHit):
            return raw_hit
        if isinstance(raw_hit, dict):
            if "document" in raw_hit:
                document = LogisticsCatalogRecallDocument.model_validate(raw_hit["document"])
                return LogisticsCatalogRecallHit(
                    document=document,
                    vector_score=float(raw_hit.get("vector_score", raw_hit.get("score", 0.0)) or 0.0),
                    rerank_score=raw_hit.get("rerank_score"),
                    source=str(raw_hit.get("source") or "milvus"),
                )
            return _coerce_milvus_hit(raw_hit)
        raise ValueError(f"recall_hit_type_invalid::{type(raw_hit).__name__}")

    @staticmethod
    def _dedupe_hits(hits: list[LogisticsCatalogRecallHit]) -> list[LogisticsCatalogRecallHit]:
        best_by_id: dict[str, LogisticsCatalogRecallHit] = {}
        order: list[str] = []
        for hit in hits:
            catalog_id = hit.document.catalog_id
            current = best_by_id.get(catalog_id)
            if current is None:
                order.append(catalog_id)
                best_by_id[catalog_id] = hit
            elif hit.vector_score > current.vector_score:
                best_by_id[catalog_id] = hit
        return [best_by_id[catalog_id] for catalog_id in order]

    def _apply_rerank_scores(
        self,
        hits: list[LogisticsCatalogRecallHit],
        scores: list[LogisticsCatalogRerankScore],
    ) -> list[LogisticsCatalogRecallHit]:
        hit_by_id = {hit.document.catalog_id: hit for hit in hits}
        reranked: list[LogisticsCatalogRecallHit] = []
        for score in scores:
            if score.score < self.rerank_min_score:
                continue
            hit = hit_by_id.get(score.catalog_id)
            if not hit:
                continue
            reranked.append(
                LogisticsCatalogRecallHit(
                    document=hit.document,
                    vector_score=hit.vector_score,
                    rerank_score=score.score,
                    source="rerank",
                )
            )
            if len(reranked) >= self.rerank_top_k:
                break
        return reranked


def _format_column_for_content(column: LogisticsCatalogColumn) -> str:
    label = column.business_name or column.name
    role = f"/{column.semantic_role}" if column.semantic_role else ""
    return f"{label}({column.name}{role})"


def _safe_recall_columns(table: LogisticsCatalogTable) -> list[LogisticsCatalogColumn]:
    """过滤不应进入 Milvus payload 的来源系统技术字段。"""

    return [
        column
        for column in table.columns
        if not _contains_forbidden_recall_source_token(column.name)
        and not _contains_forbidden_recall_source_token(column.business_name or "")
    ]


def _contains_forbidden_recall_source_token(value: str) -> bool:
    text = str(value or "")
    return bool(
        re.search(r"(?i)(^|[^a-z0-9])sap([^a-z0-9]|$)|sap_|v_sap|sys_query_log|ods_|oracle_mid", text)
    )


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _business_safe_text(value: str) -> str:
    """把业务说明中的 SQL 片段改写成业务口径文本，避免召回上下文携带可执行表达式。"""

    text = str(value or "")
    replacements = {
        "SUM(total_fee)/SUM(shipment_trip_count)": "总费用合计除以车次合计",
        "SUM(total_fee) / SUM(shipment_trip_count)": "总费用合计除以车次合计",
        "AVG(total_fee)": "明细行总费用平均值",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\b(SUM|AVG|COUNT|MIN|MAX)\s*\([^)]*\)", "受控聚合口径", text, flags=re.IGNORECASE)
    return text


def _iter_payload_strings(value: Any) -> list[str]:
    """递归展开召回 payload 中需要做安全扫描的字符串。"""

    strings: list[str] = []
    if value is None:
        return strings
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            strings.append(key_text)
            # source_system 有专门错误码，避免被通用 sap_mid/oracle_mid token 抢先命中。
            if key_text.strip().lower() == "source_system":
                continue
            strings.extend(_iter_payload_strings(item))
        return strings
    if isinstance(value, (list, tuple, set)):
        for item in value:
            strings.extend(_iter_payload_strings(item))
        return strings
    if isinstance(value, (bool, int, float)):
        return strings
    return [str(value)]


def _find_secret_like_text(value: str) -> str | None:
    """识别字符串中可能泄露的密钥、令牌或密码片段。"""

    text = str(value or "")
    key_match = re.search(
        r"(?i)\b(api[_-]?key|password|passwd|token|access[_-]?token|refresh[_-]?token|secret)\b\s*[:=]",
        text,
    )
    if key_match:
        return _normalize_secret_key(key_match.group(1))
    if re.search(r"(?i)\bauthorization\s*[:=]?\s*bearer\s+\S+", text):
        return "authorization"
    if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b", text):
        return "api_key"
    normalized = _normalize_secret_key(text)
    if normalized in FORBIDDEN_RECALL_SECRET_KEYS:
        return normalized
    return None


def _find_secret_key(value: Any) -> str | None:
    """递归检查 metadata key，防止 password/token 等字段名进入 Milvus payload。"""

    if isinstance(value, dict):
        for key, item in value.items():
            normalized = _normalize_secret_key(str(key))
            if normalized in FORBIDDEN_RECALL_SECRET_KEYS:
                return normalized
            nested = _find_secret_key(item)
            if nested:
                return nested
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            nested = _find_secret_key(item)
            if nested:
                return nested
    return None


def _normalize_secret_key(value: str) -> str:
    return re.sub(r"[\s_-]+", "_", str(value or "").strip().lower())


def _find_forbidden_recall_identifier(value: str) -> str | None:
    raw = str(value or "").strip()
    lowered = raw.lower()
    patterns = (
        r"sys_query_log",
        r"v_sap[\w_]*",
        r"sap_mid[\w_]*",
        r"oracle_mid[\w_]*",
        r"oracle_[\w_]*",
        r"ods[\w_]*",
    )
    for token in FORBIDDEN_RECALL_IDENTIFIER_TOKENS:
        if token not in lowered:
            continue
        if ":" in raw:
            return raw.split(":", 1)[-1] or token
        for pattern in patterns:
            match = re.search(pattern, raw, flags=re.IGNORECASE)
            if match:
                return match.group(0)
        return token
    return None


def _milvus_data_type(name: str) -> Any:
    """兼容真实 pymilvus 与单测 fake client 的 DataType 获取。"""

    try:
        from pymilvus import DataType

        return getattr(DataType, name)
    except Exception:  # noqa: BLE001
        return name


def _milvus_uri(host: str, port: int) -> str:
    if host.startswith("http://") or host.startswith("https://"):
        return host if re.search(r":\d+/?$", host) else f"{host.rstrip('/')}:{port}"
    return f"http://{host}:{port}"


def _stable_doc_id(document: LogisticsCatalogRecallDocument) -> str:
    digest = hashlib.sha1(f"{document.catalog_version}:{document.catalog_id}".encode("utf-8")).hexdigest()
    return digest[:32]


def _coerce_milvus_hit(raw_hit: Any) -> LogisticsCatalogRecallHit:
    if isinstance(raw_hit, LogisticsCatalogRecallHit):
        return raw_hit
    if not isinstance(raw_hit, dict):
        raise ValueError(f"milvus_hit_type_invalid::{type(raw_hit).__name__}")
    raw_entity = raw_hit.get("entity")
    entity: dict[str, Any] = raw_entity if isinstance(raw_entity, dict) else raw_hit
    metadata = _json_loads_if_needed(entity.get("metadata_json"), default={}, field_name="metadata_json")
    keywords = _json_loads_if_needed(entity.get("keywords_json"), default=[], field_name="keywords_json")
    document = LogisticsCatalogRecallDocument.model_validate(
        {
            "catalog_id": str(entity.get("catalog_id") or ""),
            "catalog_version": str(entity.get("catalog_version") or ""),
            "doc_type": str(entity.get("doc_type") or "metric"),
            "title": str(entity.get("title") or ""),
            "content": str(entity.get("content") or ""),
            "keywords": [str(item) for item in keywords] if isinstance(keywords, list) else [],
            "source_table": str(entity.get("source_table") or "") or None,
            "metadata": dict(metadata) if isinstance(metadata, dict) else {},
        }
    )
    return LogisticsCatalogRecallHit(
        document=document,
        vector_score=float(raw_hit.get("distance", raw_hit.get("score", raw_hit.get("vector_score", 0.0))) or 0.0),
        source="milvus",
    )


def _json_loads_if_needed(value: Any, *, default: Any, field_name: str | None = None) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            if field_name:
                raise ValueError(f"invalid_json_payload::{field_name}") from exc
            return default
    return value


def _coerce_rerank_scores(raw: Any, documents: list[LogisticsCatalogRecallHit]) -> list[LogisticsCatalogRerankScore]:
    if isinstance(raw, list):
        scores: list[LogisticsCatalogRerankScore] = []
        for item in raw:
            if isinstance(item, LogisticsCatalogRerankScore):
                scores.append(item)
            elif isinstance(item, dict):
                scores.append(LogisticsCatalogRerankScore.model_validate(item))
        return scores
    if isinstance(raw, dict):
        results = raw.get("results") or raw.get("output", {}).get("results") or []
        scores = []
        for item in results:
            index = item.get("index")
            if index is None or not isinstance(index, int) or index < 0 or index >= len(documents):
                continue
            score = item.get("relevance_score", item.get("score", item.get("rerank_score", 0.0)))
            scores.append(
                LogisticsCatalogRerankScore(
                    catalog_id=documents[index].document.catalog_id,
                    score=float(score or 0.0),
                )
            )
        return scores
    raise ValueError(f"rerank_response_type_invalid::{type(raw).__name__}")


def _safe_error(prefix: str, exc: BaseException) -> str:
    message = str(exc)
    message = re.sub(
        r"(?i)([a-z][a-z0-9+.-]*://[^:/@\s]+):([^@\s]+)@",
        r"\1:[REDACTED]@",
        message,
    )
    message = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "sk-[REDACTED]", message)
    message = re.sub(
        r"(?i)\b(api[_-]?key|password|passwd|token|access[_-]?token|refresh[_-]?token|secret)\s*[:=]\s*['\"]?[^\s,'\"}]+",
        lambda match: f"{match.group(1)}=[REDACTED]",
        message,
    )
    message = re.sub(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,'\"]+", r"\1[REDACTED]", message)
    return f"{prefix}::{message}"


__all__ = [
    "LOGISTICS_NL2SQL_CATALOG_COLLECTION_SUFFIX",
    "LogisticsBailianEmbeddingClient",
    "LogisticsBailianRerankClient",
    "LogisticsCatalogRecallDocument",
    "LogisticsCatalogRecallDocumentBuilder",
    "LogisticsCatalogRecallHit",
    "LogisticsCatalogRecallResult",
    "LogisticsCatalogRecallService",
    "LogisticsCatalogRerankScore",
    "LogisticsMilvusCatalogVectorStore",
]

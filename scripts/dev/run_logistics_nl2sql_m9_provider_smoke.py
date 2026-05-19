#!/usr/bin/env python
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

# 固定脚本入口：M9 真实 provider 门禁冒烟，所有输出只给脱敏结论，不打印 .env、密钥、host、user、password 或 DSN。
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.core.config import settings  # noqa: E402
from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import (  # noqa: E402
    LogisticsBailianEmbeddingClient,
    LogisticsBailianRerankClient,
    LogisticsCatalogRecallDocument,
    LogisticsCatalogRecallHit,
    LogisticsMilvusCatalogVectorStore,
    _build_provider_openai_client_kwargs,
)


def _configured(value: Any) -> bool:
    """判断配置项是否存在；只返回布尔值，避免输出真实配置内容。"""

    return bool(str(value or "").strip())


def _safe_error(exc: BaseException) -> str:
    """脱敏外部 provider 错误，避免密钥、连接串或认证头进入验收日志。"""

    message = str(exc)
    message = re.sub(
        r"(?i)([a-z][a-z0-9+.-]*://[^:/@\s]+):([^@\s]+)@",
        r"\1:[REDACTED]@",
        message,
    )
    message = re.sub(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s,'\")]+", "[REDACTED_URL]", message)
    message = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b", "[REDACTED_HOST]", message)
    message = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "sk-[REDACTED]", message)
    message = re.sub(
        r"(?i)\b(api[_-]?key|password|passwd|token|access[_-]?token|refresh[_-]?token|secret)\s*[:=]\s*['\"]?[^\s,'\"}]+",
        lambda match: f"{match.group(1)}=[REDACTED]",
        message,
    )
    message = re.sub(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,'\"]+", r"\1[REDACTED]", message)
    return message[:600]


def _result(name: str, status: str, *, reason: str | None = None, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """构造统一 provider 冒烟结果。"""

    payload: dict[str, Any] = {"provider": name, "status": status}
    if reason:
        payload["reason"] = reason
    if details:
        payload["details"] = details
    return payload


def smoke_embedding() -> dict[str, Any]:
    """真实调用项目配置的 Embedding provider，验证能返回向量。"""

    required = {
        "llm_base_url": _configured(settings.llm_base_url),
        "llm_api_key": _configured(settings.llm_api_key),
        "embedding_model": _configured(settings.embedding_model),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return _result("embedding", "BLOCKED", reason="missing_config::" + ",".join(missing), details=required)
    started = time.perf_counter()
    try:
        vectors = LogisticsBailianEmbeddingClient(timeout_seconds=15).embed_texts(["物流发运量语义召回 smoke"])
        dimension = len(vectors[0]) if vectors and vectors[0] else 0
        if dimension <= 0:
            return _result("embedding", "FAIL", reason="empty_embedding_vector")
        return _result(
            "embedding",
            "PASS",
            details={"vector_count": len(vectors), "vector_dimension": dimension, "elapsed_ms": int((time.perf_counter() - started) * 1000)},
        )
    except Exception as exc:  # noqa: BLE001
        return _result("embedding", "BLOCKED", reason="provider_error::" + _safe_error(exc))


def smoke_milvus() -> dict[str, Any]:
    """真实连接 Milvus，验证向量库客户端可用；不写入业务数据。"""

    required = {
        "milvus_host": _configured(settings.milvus_host),
        "milvus_port": int(settings.milvus_port or 0) > 0,
        "embedding_dimension": int(settings.embedding_dimension or 0) > 0,
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return _result("milvus", "BLOCKED", reason="missing_config::" + ",".join(missing), details=required)
    started = time.perf_counter()
    try:
        store = LogisticsMilvusCatalogVectorStore()
        client = store._client_or_create()  # noqa: SLF001 - provider smoke 只做连接探测，不输出连接细节。
        collections_count: int | None = None
        if hasattr(client, "list_collections"):
            collections = client.list_collections()
            collections_count = len(collections or [])
        return _result(
            "milvus",
            "PASS",
            details={"collection_name_configured": bool(store.collection_name), "collections_count": collections_count, "elapsed_ms": int((time.perf_counter() - started) * 1000)},
        )
    except Exception as exc:  # noqa: BLE001
        return _result("milvus", "BLOCKED", reason="provider_error::" + _safe_error(exc))


def smoke_rerank() -> dict[str, Any]:
    """真实调用项目配置的 Rerank provider，验证能返回精排分数。"""

    required = {
        "llm_base_url": _configured(settings.llm_base_url),
        "llm_api_key": _configured(settings.llm_api_key),
        "rerank_model": _configured(settings.rerank_model),
        "rerank_endpoint_path": _configured(settings.rerank_endpoint_path),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return _result("rerank", "BLOCKED", reason="missing_config::" + ",".join(missing), details=required)
    started = time.perf_counter()
    try:
        docs = [
            LogisticsCatalogRecallHit(
                document=LogisticsCatalogRecallDocument(
                    catalog_id="metric:shipment_mw",
                    catalog_version="logistics_nl2sql_catalog.v1",
                    doc_type="metric",
                    title="发运量",
                    content="物流发运量，单位 MW，适合回答运输量、发货量、出货量等业务问法。",
                    keywords=["发运量", "MW"],
                    metadata={"metric_id": "shipment_mw"},
                ),
                vector_score=0.8,
            ),
            LogisticsCatalogRecallHit(
                document=LogisticsCatalogRecallDocument(
                    catalog_id="dimension:logistics_company_name",
                    catalog_version="logistics_nl2sql_catalog.v1",
                    doc_type="dimension",
                    title="承运商",
                    content="物流承运商或物流公司维度。",
                    keywords=["承运商", "物流公司"],
                    metadata={"dimension_id": "logistics_company_name"},
                ),
                vector_score=0.7,
            ),
        ]
        scores = LogisticsBailianRerankClient(timeout_seconds=15).rerank(query="哪个物流跑得最多", documents=docs, top_n=1)
        if not scores:
            return _result("rerank", "FAIL", reason="empty_rerank_scores")
        return _result(
            "rerank",
            "PASS",
            details={"score_count": len(scores), "elapsed_ms": int((time.perf_counter() - started) * 1000)},
        )
    except Exception as exc:  # noqa: BLE001
        return _result("rerank", "BLOCKED", reason="provider_error::" + _safe_error(exc))


def smoke_llm() -> dict[str, Any]:
    """真实调用项目主 LLM provider，验证最小 JSON 响应链路可用。"""

    required = {
        "llm_base_url": _configured(settings.llm_base_url),
        "llm_api_key": _configured(settings.llm_api_key),
        "llm_model": _configured(settings.llm_model),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return _result("llm_provider", "BLOCKED", reason="missing_config::" + ",".join(missing), details=required)
    started = time.perf_counter()
    try:
        from openai import OpenAI

        openai_kwargs = _build_provider_openai_client_kwargs(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout_seconds=15,
            max_retries=0,
        )
        client = OpenAI(**openai_kwargs)
        completion = client.chat.completions.create(
            model=settings.llm_model,
            temperature=0,
            messages=[
                {"role": "system", "content": "只返回严格 JSON，不要解释。"},
                {"role": "user", "content": "返回 {\"ok\": true}"},
            ],
        )
        content = (completion.choices[0].message.content or "").strip()
        if not content:
            return _result("llm_provider", "FAIL", reason="empty_llm_response")
        return _result(
            "llm_provider",
            "PASS",
            details={"response_chars": len(content), "elapsed_ms": int((time.perf_counter() - started) * 1000)},
        )
    except Exception as exc:  # noqa: BLE001
        return _result("llm_provider", "BLOCKED", reason="provider_error::" + _safe_error(exc))


def main() -> int:
    """执行所有真实 provider smoke，并以非零退出码提示存在未通过门禁。"""

    results = [smoke_embedding(), smoke_milvus(), smoke_rerank(), smoke_llm()]
    summary = {item["provider"]: item["status"] for item in results}
    payload = {"version": "logistics_nl2sql_m9_provider_smoke.v1", "summary": summary, "results": results}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if all(item["status"] == "PASS" for item in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())

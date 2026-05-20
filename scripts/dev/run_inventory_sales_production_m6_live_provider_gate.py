#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# 固定脚本入口：M6 产销存 live provider gate / reindex / shadow gate，避免使用临时 heredoc 命令。
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.core.config import settings  # noqa: E402
from backend.app.domains.business_analysis.services.inventory_sales_production.m6_live_provider_gate import (  # noqa: E402
    DEFAULT_M6_RECORDS_FILENAME,
    DEFAULT_M6_REPORT_FILENAME,
    M6_ISP_LIVE_PROVIDER_GATE_VERSION,
    InventorySalesProductionM6CatalogRecallDocumentBuilder,
    InventorySalesProductionM6CatalogRecallService,
    InventorySalesProductionM6LiveShadowGateRun,
    InventorySalesProductionM6LiveShadowGateRunner,
    InventorySalesProductionM6LiveShadowSample,
    InventorySalesProductionM6OpenAiSqlPlanProvider,
    InventorySalesProductionM6ProviderSmokeRunner,
    InventorySalesProductionM6ReadonlyMiddleDbShadowExecutor,
    InventorySalesProductionM6SqlPlanGenerator,
    render_safe_m6_provider_smoke_summary_json,
)


def _json_print(payload: dict[str, Any]) -> None:
    """以 UTF-8 JSON 输出脚本结果，避免打印 provider/密钥/连接细节。"""

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _configured(value: Any) -> bool:
    """判断配置是否已填写；只返回布尔，不输出真实配置。"""

    return bool(str(value or "").strip())


def _missing_config(required: dict[str, bool]) -> list[str]:
    """返回缺失配置键名，键名本身可公开，值永不输出。"""

    return [name for name, ok in required.items() if not ok]


def _blocked(reason: str) -> dict[str, str]:
    """构造 BLOCKED probe 返回值。"""

    return {"status": "BLOCKED", "reason": reason}


def _real_provider_smoke_runner() -> InventorySalesProductionM6ProviderSmokeRunner:
    """构造真实 provider smoke runner。

    业务逻辑：provider smoke 必须真实探测配置/外部 provider；配置缺失时返回 BLOCKED，
    不得使用 fake 向量、fake rerank 或 fake LLM 伪装通过。
    """

    return InventorySalesProductionM6ProviderSmokeRunner(
        embedding_probe=_probe_embedding_provider,
        vector_store_probe=_probe_vector_store_provider,
        rerank_probe=_probe_rerank_provider,
        llm_probe=_probe_llm_provider,
    )


def _probe_embedding_provider() -> dict[str, Any]:
    """真实探测 Embedding provider。"""

    missing = _missing_config(
        {
            "llm_base_url": _configured(settings.llm_base_url),
            "llm_api_key": _configured(settings.llm_api_key),
            "embedding_model": _configured(settings.embedding_model),
        }
    )
    if missing:
        return _blocked("missing_config::" + ",".join(missing))
    try:
        from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import LogisticsBailianEmbeddingClient

        vectors = LogisticsBailianEmbeddingClient(timeout_seconds=15).embed_texts(["产销存 provider smoke"])
        return {"status": "PASS"} if vectors and vectors[0] else {"status": "FAIL", "reason": "empty_embedding_vector"}
    except Exception as exc:  # noqa: BLE001 - 外部 provider 错误必须受控脱敏。
        return _blocked("provider_error::" + str(exc))


def _probe_vector_store_provider() -> dict[str, Any]:
    """真实探测向量库连接。"""

    missing = _missing_config(
        {
            "milvus_host": _configured(settings.milvus_host),
            "milvus_port": int(settings.milvus_port or 0) > 0,
            "embedding_dimension": int(settings.embedding_dimension or 0) > 0,
        }
    )
    if missing:
        return _blocked("missing_config::" + ",".join(missing))
    try:
        from pymilvus import MilvusClient

        uri = f"http://{settings.milvus_host}:{settings.milvus_port}"
        client = MilvusClient(uri=uri)
        if hasattr(client, "list_collections"):
            client.list_collections()
        return {"status": "PASS"}
    except Exception as exc:  # noqa: BLE001 - 不输出 host/端口细节。
        return _blocked("provider_error::" + str(exc))


def _probe_rerank_provider() -> dict[str, Any]:
    """真实探测 Rerank provider。"""

    missing = _missing_config(
        {
            "llm_base_url": _configured(settings.llm_base_url),
            "llm_api_key": _configured(settings.llm_api_key),
            "rerank_model": _configured(settings.rerank_model),
            "rerank_endpoint_path": _configured(settings.rerank_endpoint_path),
        }
    )
    if missing:
        return _blocked("missing_config::" + ",".join(missing))
    try:
        from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import (
            LogisticsBailianRerankClient,
            LogisticsCatalogRecallDocument,
            LogisticsCatalogRecallHit,
        )

        docs = [
            LogisticsCatalogRecallHit(
                document=LogisticsCatalogRecallDocument(
                    catalog_id="metric:shipment_volume",
                    catalog_version=M6_ISP_LIVE_PROVIDER_GATE_VERSION,
                    doc_type="metric",
                    title="销量",
                    content="产销存销量默认等同发货量。",
                    keywords=["销量", "发货量"],
                ),
                vector_score=0.9,
            ),
            LogisticsCatalogRecallHit(
                document=LogisticsCatalogRecallDocument(
                    catalog_id="metric:ending_inventory_volume",
                    catalog_version=M6_ISP_LIVE_PROVIDER_GATE_VERSION,
                    doc_type="metric",
                    title="库存",
                    content="产销存库存按期末快照口径。",
                    keywords=["库存", "期末"],
                ),
                vector_score=0.8,
            ),
        ]
        scores = LogisticsBailianRerankClient(timeout_seconds=15).rerank(query="2025年销量", documents=docs, top_n=1)
        return {"status": "PASS"} if scores else {"status": "FAIL", "reason": "empty_rerank_scores"}
    except Exception as exc:  # noqa: BLE001
        return _blocked("provider_error::" + str(exc))


def _probe_llm_provider() -> dict[str, Any]:
    """真实探测主 LLM provider。"""

    missing = _missing_config(
        {
            "llm_base_url": _configured(settings.llm_base_url),
            "llm_api_key": _configured(settings.llm_api_key),
            "llm_model": _configured(settings.llm_model),
        }
    )
    if missing:
        return _blocked("missing_config::" + ",".join(missing))
    try:
        from openai import OpenAI

        from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import _build_provider_openai_client_kwargs

        client = OpenAI(
            **_build_provider_openai_client_kwargs(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                timeout_seconds=15,
                max_retries=0,
            )
        )
        completion = client.chat.completions.create(
            model=settings.llm_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    # OpenAI 兼容接口在 response_format=json_object 时要求消息显式包含 json 字样；
                    # smoke 只验证 provider 可用性，不暴露模型名、密钥或连接信息。
                    "content": "请只返回 JSON 对象：{\"ok\": true}",
                }
            ],
        )
        content = completion.choices[0].message.content or ""
        return {"status": "PASS"} if content.strip() else {"status": "FAIL", "reason": "empty_llm_response"}
    except Exception as exc:  # noqa: BLE001
        return _blocked("provider_error::" + str(exc))


def run_provider_smoke() -> int:
    """执行 M6 provider smoke 并输出公开安全摘要。"""

    result = _real_provider_smoke_runner().run()
    print(render_safe_m6_provider_smoke_summary_json(result))
    return 0 if result.ok else 2


def run_reindex_catalog(*, artifact_dir: Path, dry_run: bool) -> int:
    """执行 catalog reindex dry-run 或写入本地 reindex 文档。

    参数：artifact_dir 为验收材料目录；dry_run 为 True 时只输出数量，不写索引。
    返回：进程退出码。
    """

    documents = InventorySalesProductionM6CatalogRecallDocumentBuilder().build_documents()
    payload = {
        "version": M6_ISP_LIVE_PROVIDER_GATE_VERSION,
        "gate": "catalog_reindex",
        "status": "PASS",
        "dry_run": bool(dry_run),
        "document_count": len(documents),
    }
    if not dry_run:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_dir / "m6-catalog-reindex-documents.json"
        path.write_text(
            json.dumps([document.model_dump(mode="json") for document in documents], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        payload["documents_path"] = str(path)
    _json_print(payload)
    return 0


def _default_live_shadow_samples(sample_count: int) -> list[InventorySalesProductionM6LiveShadowSample]:
    """构造 live shadow gate 默认样例。"""

    return [
        InventorySalesProductionM6LiveShadowSample(
            sample_id=f"m6_live_sales_year_summary_{index + 1}",
            question="2025年销量是多少？",
            expected_status="matched",
        )
        for index in range(max(1, sample_count))
    ]


def _write_provider_blocked_shadow_report(
    *,
    artifact_dir: Path,
    samples: list[InventorySalesProductionM6LiveShadowSample],
) -> InventorySalesProductionM6LiveShadowGateRun:
    """真实 provider 阻塞时写入 fail-closed shadow gate 报告。"""

    artifact_dir.mkdir(parents=True, exist_ok=True)
    records_path = artifact_dir / DEFAULT_M6_RECORDS_FILENAME
    report_path = artifact_dir / DEFAULT_M6_REPORT_FILENAME
    records = [
        {
            "sample_id": sample.sample_id,
            "actual_status": "shadow_error",
            "provider_live_called": False,
            "sqlplan_validation_ok": False,
            "error_codes": ["provider_blocked"],
            "readonly_middle_db_shadow_executed": False,
        }
        for sample in samples
    ]
    report = {
        "version": M6_ISP_LIVE_PROVIDER_GATE_VERSION,
        "status": "BLOCKED",
        "total": len(samples),
        "success_count": 0,
        "provider_live_called": False,
        "sqlplan_validation_pass_count": 0,
        "readonly_middle_db_shadow_executed": False,
        "formal_qa_executed": False,
        "expected_status_mismatch_count": len(samples),
        "blocked_reason": "provider_blocked",
    }
    records_path.write_text("\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in records) + "\n", encoding="utf-8")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return InventorySalesProductionM6LiveShadowGateRun(report=report, records_path=records_path, report_path=report_path)


def run_live_provider_shadow_gate(*, artifact_dir: Path, max_live_samples: int) -> int:
    """执行 M6 live-provider SQLPlan shadow gate。

    业务逻辑：live gate 只允许真实 provider + 只读中间库；若 provider smoke 不全 PASS，
    直接写 BLOCKED 报告并以非零退出，禁止使用 fake generator 伪通过。
    """

    samples = _default_live_shadow_samples(max_live_samples)
    smoke_result = _real_provider_smoke_runner().run()
    if not smoke_result.ok:
        blocked_run = _write_provider_blocked_shadow_report(artifact_dir=artifact_dir, samples=samples)
        _json_print({**blocked_run.report, "records_path": str(blocked_run.records_path), "report_path": str(blocked_run.report_path)})
        return 2

    documents = InventorySalesProductionM6CatalogRecallDocumentBuilder().build_documents()
    recall_service = InventorySalesProductionM6CatalogRecallService.from_documents(documents)
    runner = InventorySalesProductionM6LiveShadowGateRunner(
        sqlplan_generator=InventorySalesProductionM6SqlPlanGenerator(
            recall_service=recall_service,
            llm_provider=InventorySalesProductionM6OpenAiSqlPlanProvider(),
        ),
        readonly_shadow_executor=InventorySalesProductionM6ReadonlyMiddleDbShadowExecutor(),
    )
    run = runner.run(samples=samples, artifact_dir=artifact_dir)
    _json_print({**run.report, "records_path": str(run.records_path), "report_path": str(run.report_path)})
    return 0 if run.report.get("expected_status_mismatch_count") == 0 else 2


def main() -> int:
    """解析 CLI 参数并执行 M6 独立门禁。"""

    parser = argparse.ArgumentParser(description="Run inventory-sales-production M6 live provider gate checks")
    parser.add_argument(
        "--artifact-dir",
        default="ai/outbox/kanban/t_isp_m6_live_provider_gate",
        help="directory for sanitized M6 artifacts",
    )
    parser.add_argument("--provider-smoke", action="store_true", help="run provider smoke gate")
    parser.add_argument("--reindex-catalog", action="store_true", help="run catalog reindex gate")
    parser.add_argument("--reindex-dry-run", action="store_true", help="build catalog documents without writing index artifacts")
    parser.add_argument("--live-provider-shadow-gate", action="store_true", help="run live-provider SQLPlan shadow gate")
    parser.add_argument("--max-live-samples", type=int, default=1, help="maximum live shadow samples, default: 1")
    args = parser.parse_args()

    artifact_dir = Path(args.artifact_dir)
    exit_codes: list[int] = []
    if args.provider_smoke:
        exit_codes.append(run_provider_smoke())
    if args.reindex_catalog or args.reindex_dry_run:
        exit_codes.append(run_reindex_catalog(artifact_dir=artifact_dir, dry_run=bool(args.reindex_dry_run)))
    if args.live_provider_shadow_gate:
        exit_codes.append(run_live_provider_shadow_gate(artifact_dir=artifact_dir, max_live_samples=args.max_live_samples))
    if not exit_codes:
        parser.print_help()
        return 0
    return 0 if all(code == 0 for code in exit_codes) else 2


if __name__ == "__main__":
    raise SystemExit(main())

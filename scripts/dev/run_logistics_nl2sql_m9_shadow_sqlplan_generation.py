from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

# 固定脚本入口：用于本地/验收触发 M9 自然语言→SQLPlan shadow smoke，避免临时 heredoc 命令。
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import (  # noqa: E402
    LogisticsCatalogRecallDocumentBuilder,
    LogisticsCatalogRecallHit,
    LogisticsCatalogRecallResult,
)
from backend.app.domains.logistics.services.nl2sql.m9_sqlplan_generation import (  # noqa: E402
    LogisticsSqlPlanGenerator,
    build_default_logistics_nl2sql_m9_shadow_samples,
    run_logistics_nl2sql_m9_shadow_sqlplan_generation,
)
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader  # noqa: E402
from backend.app.domains.logistics.services.nl2sql.sql_plan import LogisticsSqlPlanValidator  # noqa: E402

CATALOG_VERSION = "logistics_nl2sql_catalog.v1"


class OfflineFixtureRecallService:
    """离线召回服务。

    业务逻辑：
        只从当前 canonical Semantic Catalog 取白名单文档，构造 runner 需要的召回命中；
        不访问 embedding、Milvus 或 rerank 服务，因此不会修改外部索引。
    """

    def __init__(self) -> None:
        catalog = LogisticsSemanticCatalogLoader().load()
        documents = LogisticsCatalogRecallDocumentBuilder().build(catalog)
        self.by_id = {document.catalog_id: document for document in documents}

    def recall(self, **kwargs: Any) -> LogisticsCatalogRecallResult:
        wanted = [
            "table:dws_logistics_detail_union",
            "metric:shipment_mw",
            "metric:row_count",
            "dimension:biz_year",
            "dimension:logistics_company_name",
            "rule:default_time_range",
            "example:m9_example_carrier_mw_ranking",
            "example:m9_example_yearly_mw_breakdown",
        ]
        hits = [
            LogisticsCatalogRecallHit(document=self.by_id[catalog_id], vector_score=0.88, rerank_score=0.96, source="offline_fixture")
            for catalog_id in wanted
            if catalog_id in self.by_id
        ]
        return LogisticsCatalogRecallResult(status="ok", hits=hits)


class OfflineFixtureGenerator:
    """离线 SQLPlan 生成器。

    业务逻辑：
        该生成器只用于 smoke/验收材料，不访问 LLM，不生成 SQL；它产出受控
        SQLPlan candidate 后仍交给正式 validator 校验，验证 runner 与 shadow pipeline
        的后半段闭环。真实 LLM 生成由 LogisticsSqlPlanGenerator 负责。
    """

    def __init__(self) -> None:
        self.validator = LogisticsSqlPlanValidator()

    def generate(self, **kwargs: Any):
        from backend.app.domains.logistics.services.nl2sql.m9_sqlplan_generation import LogisticsSqlPlanGenerationResult

        normalized_question = str(kwargs.get("normalized_question") or "")
        if "每年" in normalized_question or "分别" in normalized_question:
            candidate = yearly_candidate()
        else:
            candidate = carrier_ranking_candidate()
        validation_result = self.validator.validate(candidate)
        return LogisticsSqlPlanGenerationResult(
            status="ok" if validation_result.ok else "validation_failed",
            candidate=candidate if validation_result.ok else None,
            validation_result=validation_result,
            error_codes=validation_result.error_codes,
        )


def carrier_ranking_candidate() -> dict[str, Any]:
    """返回承运商发运量排名的受控 SQLPlan candidate。"""

    return {
        "schema_version": "logistics_sqlplan_candidate.v1",
        "domain": "logistics",
        "strategy": "sql_direct",
        "catalog_version": CATALOG_VERSION,
        "catalog_refs": [
            {"catalog_id": "table:dws_logistics_detail_union", "catalog_version": CATALOG_VERSION},
            {"catalog_id": "metric:shipment_mw", "catalog_version": CATALOG_VERSION},
            {"catalog_id": "metric:row_count", "catalog_version": CATALOG_VERSION},
            {"catalog_id": "dimension:biz_year", "catalog_version": CATALOG_VERSION},
            {"catalog_id": "dimension:logistics_company_name", "catalog_version": CATALOG_VERSION},
            {"catalog_id": "rule:default_time_range", "catalog_version": CATALOG_VERSION},
            {"catalog_id": "example:m9_example_carrier_mw_ranking", "catalog_version": CATALOG_VERSION},
        ],
        "plan": {
            "query_type": "ranking",
            "tables": ["dws_logistics_detail_union"],
            "joins": [],
            "metrics": ["shipment_mw", "row_count"],
            "dimensions": ["logistics_company_name"],
            "filters": [{"dimension": "biz_year", "operator": "in", "values": [2023, 2024, 2025, 2026]}],
            "group_by": ["logistics_company_name"],
            "order_by": [{"metric": "shipment_mw", "direction": "desc"}],
            "business_rules": ["default_time_range"],
            "explicit_year_buckets": [2023, 2024, 2025, 2026],
            "requested_unit": "MW",
            "limit": 20,
        },
        "clarification_questions": [],
        "unsupported_reason": None,
        "confidence": 0.91,
    }


def yearly_candidate() -> dict[str, Any]:
    """返回多年份发运量拆分的受控 SQLPlan candidate。"""

    candidate = deepcopy(carrier_ranking_candidate())
    candidate["catalog_refs"] = [
        {"catalog_id": "table:dws_logistics_detail_union", "catalog_version": CATALOG_VERSION},
        {"catalog_id": "metric:shipment_mw", "catalog_version": CATALOG_VERSION},
        {"catalog_id": "metric:row_count", "catalog_version": CATALOG_VERSION},
        {"catalog_id": "dimension:biz_year", "catalog_version": CATALOG_VERSION},
        {"catalog_id": "example:m9_example_yearly_mw_breakdown", "catalog_version": CATALOG_VERSION},
    ]
    candidate["plan"] = {
        "query_type": "aggregate",
        "tables": ["dws_logistics_detail_union"],
        "joins": [],
        "metrics": ["shipment_mw", "row_count"],
        "dimensions": ["biz_year"],
        "filters": [{"dimension": "biz_year", "operator": "in", "values": [2023, 2024, 2025]}],
        "group_by": ["biz_year"],
        "order_by": [{"dimension": "biz_year", "direction": "asc"}],
        "business_rules": [],
        "explicit_year_buckets": [2023, 2024, 2025],
        "requested_unit": "MW",
        "limit": 20,
    }
    candidate["confidence"] = 0.9
    return candidate


def main() -> int:
    """解析 CLI 参数并执行 M9 shadow smoke。"""

    parser = argparse.ArgumentParser(description="Run logistics NL2SQL M9 shadow SQLPlan generation smoke")
    parser.add_argument(
        "--artifact-dir",
        default="ai/outbox/kanban/t_m9_nl2sql_shadow",
        help="directory for sanitized M9 JSONL/Markdown artifacts",
    )
    parser.add_argument("--sample-limit", type=int, default=3, help="offline fixture sample limit, default: 3")
    parser.add_argument(
        "--live-provider-smoke",
        action="store_true",
        help="use real catalog recall/rerank and project LLM provider instead of offline fixtures; remains shadow-only",
    )
    parser.add_argument(
        "--max-live-samples",
        type=int,
        default=1,
        help="maximum live-provider smoke samples when --live-provider-smoke is set, default: 1",
    )
    parser.add_argument(
        "--live-provider-timeout-seconds",
        type=float,
        default=60.0,
        help="timeout seconds for each live provider LLM request, default: 60",
    )
    args = parser.parse_args()

    # 默认路径继续使用离线 fixture，确保本地/CI smoke 不依赖真实 LLM、Embedding、Milvus 或 Rerank。
    if args.live_provider_smoke:
        sample_limit = max(1, args.max_live_samples)
        samples = build_default_logistics_nl2sql_m9_shadow_samples()
        recall_service = None
        # 业务逻辑：真实 provider gate 走项目 LLM；默认超时放宽到 60 秒，避免正常但偏慢的样例被误判为 generation error。
        generator = LogisticsSqlPlanGenerator(timeout_seconds=max(1.0, args.live_provider_timeout_seconds))
    else:
        sample_limit = max(1, args.sample_limit)
        samples = build_default_logistics_nl2sql_m9_shadow_samples()[:sample_limit]
        recall_service = OfflineFixtureRecallService()
        generator = OfflineFixtureGenerator()

    run = run_logistics_nl2sql_m9_shadow_sqlplan_generation(
        samples=samples,
        artifact_dir=Path(args.artifact_dir),
        recall_service=recall_service,
        generator=generator,
        live_provider_smoke=args.live_provider_smoke,
        max_live_samples=sample_limit if args.live_provider_smoke else None,
    )
    payload = {
        "version": run.version,
        "shadow_only": run.shadow_only,
        "live_provider_smoke": run.live_provider_smoke,
        "records_path": str(run.records_path),
        "report_path": str(run.report_path),
        "total": run.report.total,
        "success_count": run.report.success_count,
        "generated_count": run.report.generated_count,
        "validation_pass_count": run.report.validation_pass_count,
        "expected_status_mismatch_count": run.report.expected_status_mismatch_count,
        "by_status": run.report.by_status,
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if run.report.expected_status_mismatch_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

"""只读复现 M9 live provider yearly_mw_breakdown 样例。

业务用途：
    捕获 rewrite、route、recall、provider candidate 归一后的摘要与 validator 错误码，
    用于 Kanban t_3d0c55ce 根因定位；不输出密钥、不执行生产写入、不生成用户可见 SQL。
"""

import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.domains.logistics.services.nl2sql.m9_sqlplan_generation import (  # noqa: E402
    LogisticsNl2SqlDomainRouter,
    LogisticsNl2SqlQueryRewriteService,
    LogisticsSqlPlanGenerator,
)
from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import LogisticsCatalogRecallService  # noqa: E402
from backend.app.domains.logistics.services.nl2sql.evaluation_log import redact_evaluation_text  # noqa: E402


def _slot_summary(rewrite: Any) -> str:
    """返回召回服务需要的脱敏槽位摘要。"""

    return json.dumps(
        {
            "default_years": rewrite.default_years,
            "normalized_terms": rewrite.normalized_terms,
            "unsupported_flags": rewrite.unsupported_flags,
            "requested_unit": rewrite.requested_unit,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def main() -> int:
    """执行 yearly_mw_breakdown 单样例，只写脱敏 JSON 调查材料。"""

    artifact_dir = REPO_ROOT / "ai/outbox/kanban/t_3d0c55ce"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    out_path = artifact_dir / "provider-output-investigation.json"

    question = "2023年到2025年每年发运量分别是多少？"
    rewrite = LogisticsNl2SqlQueryRewriteService().rewrite(question)
    route = LogisticsNl2SqlDomainRouter().route(rewrite)
    recall = LogisticsCatalogRecallService().recall(
        question=rewrite.original_question,
        normalized_question=rewrite.normalized_question,
        slot_summary=_slot_summary(rewrite),
    )
    generator = LogisticsSqlPlanGenerator(timeout_seconds=60)
    started = time.perf_counter()
    generation = generator.generate(
        original_question=rewrite.original_question,
        normalized_question=rewrite.normalized_question,
        route=route,
        recall_result=recall,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    candidate: dict[str, Any] = generation.candidate if isinstance(generation.candidate, dict) else {}
    raw_plan = candidate.get("plan")
    plan: dict[str, Any] = raw_plan if isinstance(raw_plan, dict) else {}
    payload: dict[str, Any] = {
        "question": question,
        "rewrite": rewrite.model_dump(mode="json"),
        "route": route.model_dump(mode="json"),
        "recall_status": recall.status,
        "recall_error": redact_evaluation_text(str(recall.error)) if recall.error else None,
        "recall_hit_ids": [hit.document.catalog_id for hit in recall.hits],
        "generation_status": generation.status,
        "generation_error_codes": generation.error_codes,
        "generation_error_message": generation.error_message,
        "llm_model_name_present": bool(generation.llm_model_name),
        "validation_ok": bool(generation.validation_result and generation.validation_result.ok),
        "validation_errors": generation.validation_result.error_codes if generation.validation_result else [],
        "candidate_top_keys": sorted(candidate.keys()) if candidate else [],
        "candidate_catalog_ref_ids": [ref.get("catalog_id") for ref in candidate.get("catalog_refs", []) if isinstance(ref, dict)],
        "plan_summary": {
            "query_type": plan.get("query_type"),
            "tables": plan.get("tables"),
            "joins": plan.get("joins"),
            "metrics": plan.get("metrics"),
            "dimensions": plan.get("dimensions"),
            "filters": plan.get("filters"),
            "group_by": plan.get("group_by"),
            "order_by": plan.get("order_by"),
            "business_rules": plan.get("business_rules"),
            "explicit_year_buckets": plan.get("explicit_year_buckets"),
            "requested_unit": plan.get("requested_unit"),
            "limit": plan.get("limit"),
        },
        "elapsed_ms": elapsed_ms,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if generation.status == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.db.session import SessionLocal
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.domains.logistics.services.error_code_registry import LogisticsErrorCodeRegistry
from scripts.logistics_top200_b_factory_round1 import (
    CLUSTER_DEFINITIONS,
    ClusterDefinition,
    NoopQueryLogRepository,
    assign_cluster,
    load_effective_b_items,
)


@dataclass
class Round2Record:
    """Top200 高价值 B 题工厂化 Round2 单题执行结果。"""

    cluster_id: str
    cluster_name: str
    question_id: str
    question: str
    priority: str
    source_group: str
    baseline_classification: str
    actual_status_code: str
    actual_query_key: str | None
    final_classification: str
    closure_result: str
    closure_reason: str
    answer_summary: str


ROUND2_CLUSTER_IDS = (
    "hist_route_pricing_analysis",
    "carrier_cost_ranking",
    "region_mw_summary_breakdown",
    "system_status_quality_ranking",
)

ROUND2_REMAIN_B_REASON_MAP = {
    "RAW025": "当前线路运价题仍缺统计年份和结果口径，需先确认看平均运费、每月均价还是最高/最低价。",
    "RAW011": "“2026年运量综合”仍缺明确时间范围和拆分口径，需先确认当前累计还是按月/采购方式拆分。",
    "Q291": "supplier_price 离群点题仍缺稳定判定标准，需先确认分布口径和高价离群阈值。",
}


def _lookup_cluster_name(cluster_id: str) -> str:
    """根据题族 ID 取题族名称。"""
    for definition in CLUSTER_DEFINITIONS:
        if definition.cluster_id == cluster_id:
            return definition.cluster_name
    raise KeyError(f"未找到题族 {cluster_id}。")


def _resolve_closure_reason(question_id: str, status_code: str, query_key: str | None) -> tuple[str, str, str]:
    """根据当前真实执行结果，生成 Round2 收口归因。"""
    if (
        status_code == LogisticsErrorCodeRegistry.OK
        and query_key
    ):
        return (
            "A",
            "promoted_to_a",
            "当前主链路已能稳定命中正式 query_key，可纳入 Top200 高价值题的 A 类收口对象。",
        )
    if status_code == LogisticsErrorCodeRegistry.CLARIFICATION_REQUIRED:
        return (
            "B",
            "remain_b",
            ROUND2_REMAIN_B_REASON_MAP.get(
                question_id,
                "当前问题仍缺稳定口径或字段映射，继续保留在 B 类业务化澄清。",
            ),
        )
    if status_code == LogisticsErrorCodeRegistry.UNSUPPORTED_QUESTION:
        return (
            "C",
            "moved_to_c",
            "当前问题已确认超出一期结构化问答边界，应转入 C 类不支持。",
        )
    return (
        "B",
        "remain_b",
        "当前结果结构仍不稳定，暂不进入 A 类。",
    )


def evaluate_round2(
    *,
    effective_b_items: list[dict[str, Any]],
    round1_report_path: Path,
) -> dict[str, Any]:
    """执行 Top200 高价值 B 题工厂化 Round2。"""
    selected_items = [
        item
        for item in effective_b_items
        if assign_cluster(item).cluster_id in ROUND2_CLUSTER_IDS
    ]
    records: list[Round2Record] = []

    db = SessionLocal()
    service = LogisticsDataQaService(db=db, query_log_repository=NoopQueryLogRepository())
    try:
        for item in selected_items:
            definition = assign_cluster(item)
            result = service.query(
                LogisticsDataQaQueryRequest(question=item["question"]),
                trace_id="top200-b-factory-round2",
            )
            actual_status_code = result.status.code if result.status else "NO_STATUS"
            final_classification, closure_result, closure_reason = _resolve_closure_reason(
                item["question_id"],
                actual_status_code,
                result.query_plan.query_key,
            )
            records.append(
                Round2Record(
                    cluster_id=definition.cluster_id,
                    cluster_name=definition.cluster_name,
                    question_id=item["question_id"],
                    question=item["question"],
                    priority=item["priority"],
                    source_group=item["source_group"],
                    baseline_classification="B",
                    actual_status_code=actual_status_code,
                    actual_query_key=result.query_plan.query_key,
                    final_classification=final_classification,
                    closure_result=closure_result,
                    closure_reason=closure_reason,
                    answer_summary=result.answer_summary,
                )
            )
    finally:
        db.close()

    promoted = [record for record in records if record.closure_result == "promoted_to_a"]
    remain_b = [record for record in records if record.closure_result == "remain_b"]
    moved_to_c = [record for record in records if record.closure_result == "moved_to_c"]

    cluster_summary: dict[str, dict[str, Any]] = {}
    for cluster_id in ROUND2_CLUSTER_IDS:
        cluster_records = [record for record in records if record.cluster_id == cluster_id]
        if not cluster_records:
            continue
        cluster_summary[cluster_id] = {
            "cluster_name": _lookup_cluster_name(cluster_id),
            "selected_question_count": len(cluster_records),
            "promoted_to_a": len([record for record in cluster_records if record.closure_result == "promoted_to_a"]),
            "remain_b": len([record for record in cluster_records if record.closure_result == "remain_b"]),
            "moved_to_c": len([record for record in cluster_records if record.closure_result == "moved_to_c"]),
            "question_ids": [record.question_id for record in cluster_records],
        }

    round1_report = json.loads(round1_report_path.read_text(encoding="utf-8"))
    before_distribution = round1_report["summary"]["after_top200_distribution"]
    after_distribution = {
        "A": before_distribution["A"] + len(promoted),
        "B": before_distribution["B"] - len(promoted) - len(moved_to_c),
        "C": before_distribution["C"] + len(moved_to_c),
    }

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "selected_cluster_ids": list(ROUND2_CLUSTER_IDS),
        "selected_cluster_names": [_lookup_cluster_name(cluster_id) for cluster_id in ROUND2_CLUSTER_IDS],
        "summary": {
            "selected_questions": len(records),
            "promoted_to_a": len(promoted),
            "remain_b": len(remain_b),
            "moved_to_c": len(moved_to_c),
            "before_top200_distribution": before_distribution,
            "after_top200_distribution": after_distribution,
        },
        "cluster_summary": cluster_summary,
        "promoted_question_ids": [record.question_id for record in promoted],
        "remain_b_question_ids": [record.question_id for record in remain_b],
        "moved_to_c_question_ids": [record.question_id for record in moved_to_c],
        "items": [asdict(record) for record in records],
    }


def main() -> None:
    """生成 Top200 高价值 B 题工厂化 Round2 报告。"""
    parser = argparse.ArgumentParser(description="Top200 高价值 B 题工厂化 round2")
    parser.add_argument(
        "--top200-json",
        default="/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/backend/app/domains/logistics/config/logistics_top200_questions.json",
        help="Top200 正式清单 JSON 路径",
    )
    parser.add_argument(
        "--p1-p2-report",
        default="/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/tmp/logistics_question_bank/logistics_top200_p1_p2_regression_report.json",
        help="P1/P2 第一轮收口报告路径",
    )
    parser.add_argument(
        "--round1-report",
        default="/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/tmp/logistics_question_bank/logistics_top200_b_factory_round1_report.json",
        help="Round1 工厂化报告路径",
    )
    parser.add_argument(
        "--output",
        default="/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/tmp/logistics_question_bank/logistics_top200_b_factory_round2_report.json",
        help="Round2 工厂化报告输出路径",
    )
    args = parser.parse_args()

    effective_b_items = load_effective_b_items(
        top200_path=Path(args.top200_json),
        p1_p2_report_path=Path(args.p1_p2_report),
    )
    payload = evaluate_round2(
        effective_b_items=effective_b_items,
        round1_report_path=Path(args.round1_report),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

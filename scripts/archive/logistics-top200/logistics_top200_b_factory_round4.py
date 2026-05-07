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
    NoopQueryLogRepository,
    assign_cluster,
)
from scripts.logistics_top200_b_factory_round3 import load_effective_b_items_for_round3


@dataclass
class Round4Record:
    """Top200 高价值 B 题工厂化 Round4 单题执行结果。"""

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


ROUND4_CLUSTER_IDS = (
    "sys_monthly_company_total_fee",
    "sys_monthly_unit_fee",
    "customer_project_analysis",
    "region_mw_summary_breakdown",
    "hist_route_pricing_analysis",
    "diagnostic_analysis",
    "system_status_quality_ranking",
)

ROUND4_REMAIN_B_REASON_MAP = {
    "RAW038": "高运费项目地题仍缺采购方式拆分字段和统计口径，当前继续保留在 B 类业务化澄清。",
    "RAW057": "月份单瓦成本简写题虽然公式已明确，但仍缺年份口径，当前继续保留在 B 类澄清。",
    "RAW049": "项目总运量题当前仍缺年份口径，需先确认按单年还是按 2023–2025 历史累计统计。",
    "RAW011": "2026 运量综合题仍缺明确时间范围和拆分口径，当前继续保留在 B 类业务化澄清。",
    "RAW025": "线路运价题仍缺统计年份和目标指标口径，当前继续保留在 B 类业务化澄清。",
    "Q338": "异常费用过高题仍缺异常阈值和统计时间范围，当前继续保留在 B 类业务化澄清。",
}

ROUND4_MOVED_TO_C_REASON_MAP = {
    "Q291": "supplier_price 分布和高价离群点诊断当前超出一期结构化统计边界，应正式转入 C 类不支持。",
}


def _lookup_cluster_name(cluster_id: str) -> str:
    """根据题族 ID 取题族名称。"""
    for definition in CLUSTER_DEFINITIONS:
        if definition.cluster_id == cluster_id:
            return definition.cluster_name
    raise KeyError(f"未找到题族 {cluster_id}。")


def load_effective_b_items_for_round4(
    *,
    top200_path: Path,
    p1_p2_report_path: Path,
    round1_report_path: Path,
    round2_report_path: Path,
    round3_report_path: Path,
) -> list[dict[str, Any]]:
    """读取 Round4 仍然有效的高价值 B 题。

    说明：
        1. 先复用 Round3 的有效 B 集合，扣除 Round3 已推进进 A 和已转入 C 的题；
        2. 这样 Round4 拿到的就是当前真实还留在 B 的对象；
        3. 不重复手工维护一份平行清单。
    """
    effective_b_items = load_effective_b_items_for_round3(
        top200_path=top200_path,
        p1_p2_report_path=p1_p2_report_path,
        round1_report_path=round1_report_path,
        round2_report_path=round2_report_path,
    )
    round3_report = json.loads(round3_report_path.read_text(encoding="utf-8"))
    excluded_ids = set(round3_report["promoted_question_ids"])
    excluded_ids.update(round3_report["moved_to_c_question_ids"])
    return [item for item in effective_b_items if item["question_id"] not in excluded_ids]


def _resolve_round4_result(
    *,
    question_id: str,
    status_code: str,
    query_key: str | None,
) -> tuple[str, str, str]:
    """按 Round4 当前真实结果，映射最终分类和归因。"""
    if status_code == LogisticsErrorCodeRegistry.OK and query_key:
        return (
            "A",
            "promoted_to_a",
            "当前主链路已能稳定命中正式 query_key，可纳入 Top200 高价值题的 A 类收口对象。",
        )
    if status_code == LogisticsErrorCodeRegistry.CLARIFICATION_REQUIRED:
        return (
            "B",
            "remain_b",
            ROUND4_REMAIN_B_REASON_MAP.get(
                question_id,
                "当前问题仍缺稳定年份、阈值或统计口径，继续保留在 B 类业务化澄清。",
            ),
        )
    if status_code == LogisticsErrorCodeRegistry.UNSUPPORTED_QUESTION:
        return (
            "C",
            "moved_to_c",
            ROUND4_MOVED_TO_C_REASON_MAP.get(
                question_id,
                "当前问题已确认超出一期结构化统计边界，应转入 C 类不支持。",
            ),
        )
    return (
        "B",
        "remain_b",
        "当前结果结构仍不稳定，暂不进入 A 类。",
    )


def evaluate_round4(
    *,
    effective_b_items: list[dict[str, Any]],
    round3_report_path: Path,
) -> dict[str, Any]:
    """执行 Top200 高价值 B 题工厂化 Round4。"""
    selected_items = [
        item
        for item in effective_b_items
        if assign_cluster(item).cluster_id in ROUND4_CLUSTER_IDS
    ]
    records: list[Round4Record] = []

    db = SessionLocal()
    service = LogisticsDataQaService(db=db, query_log_repository=NoopQueryLogRepository())
    try:
        for item in selected_items:
            definition = assign_cluster(item)
            result = service.query(
                LogisticsDataQaQueryRequest(question=item["question"]),
                trace_id="top200-b-factory-round4",
            )
            status_code = result.status.code if result.status else "NO_STATUS"
            final_classification, closure_result, closure_reason = _resolve_round4_result(
                question_id=item["question_id"],
                status_code=status_code,
                query_key=result.query_plan.query_key,
            )
            records.append(
                Round4Record(
                    cluster_id=definition.cluster_id,
                    cluster_name=definition.cluster_name,
                    question_id=item["question_id"],
                    question=item["question"],
                    priority=item["priority"],
                    source_group=item["source_group"],
                    baseline_classification="B",
                    actual_status_code=status_code,
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
    for cluster_id in ROUND4_CLUSTER_IDS:
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

    round3_report = json.loads(round3_report_path.read_text(encoding="utf-8"))
    before_distribution = round3_report["summary"]["after_top200_distribution"]
    after_distribution = {
        "A": before_distribution["A"] + len(promoted),
        "B": before_distribution["B"] - len(promoted) - len(moved_to_c),
        "C": before_distribution["C"] + len(moved_to_c),
    }

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "selected_cluster_ids": list(ROUND4_CLUSTER_IDS),
        "selected_cluster_names": [_lookup_cluster_name(cluster_id) for cluster_id in ROUND4_CLUSTER_IDS],
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
    """生成 Top200 高价值 B 题工厂化 Round4 报告。"""
    parser = argparse.ArgumentParser(description="Top200 高价值 B 题工厂化 round4")
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
        "--round2-report",
        default="/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/tmp/logistics_question_bank/logistics_top200_b_factory_round2_report.json",
        help="Round2 工厂化报告路径",
    )
    parser.add_argument(
        "--round3-report",
        default="/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/tmp/logistics_question_bank/logistics_top200_b_factory_round3_report.json",
        help="Round3 工厂化报告路径",
    )
    parser.add_argument(
        "--output",
        default="/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/tmp/logistics_question_bank/logistics_top200_b_factory_round4_report.json",
        help="Round4 工厂化报告输出路径",
    )
    args = parser.parse_args()

    effective_b_items = load_effective_b_items_for_round4(
        top200_path=Path(args.top200_json),
        p1_p2_report_path=Path(args.p1_p2_report),
        round1_report_path=Path(args.round1_report),
        round2_report_path=Path(args.round2_report),
        round3_report_path=Path(args.round3_report),
    )
    report = evaluate_round4(
        effective_b_items=effective_b_items,
        round3_report_path=Path(args.round3_report),
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()

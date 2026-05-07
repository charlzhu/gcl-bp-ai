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
from scripts.logistics_top200_b_factory_round4 import load_effective_b_items_for_round4


@dataclass
class Round5Record:
    """Top200 高价值 B 题工厂化 Round5 单题执行结果。"""

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


ROUND5_CLUSTER_IDS = (
    "sys_monthly_unit_fee",
    "customer_project_analysis",
    "region_mw_summary_breakdown",
    "hist_route_pricing_analysis",
    "diagnostic_analysis",
)

ROUND5_PROMOTED_REASON_MAP = {
    "RAW057": "月份+额外费用+总W 数公式已经明确，当前按 2026 正式系统口径可稳定计算单瓦运输成本。",
    "RAW011": "“2026 运量综合”当前已统一锁定为截至目前累计的 MW + 车次综合结果，可正式进入 A 类。",
    "RAW025": "线路、目的地和车型已明确，当前已统一锁定为 2023–2025 历史累计平均运费，可正式进入 A 类。",
}

ROUND5_MOVED_TO_C_REASON_MAP = {
    "RAW038": "当前历史台账缺少稳定的询比价/招标拆分字段，无法可靠回答高运费项目地的采购方式拆分结果，应正式转入 C 类。",
    "RAW049": "当前 MVP 暂未把项目名称做成稳定可复用统计维度，项目名称口径问题应正式转入 C 类。",
    "Q338": "该题属于系统追问策略设计，不属于正式业务数据问答范围，应正式转入 C 类。",
}


def _lookup_cluster_name(cluster_id: str) -> str:
    """根据题族 ID 取题族名称。"""
    for definition in CLUSTER_DEFINITIONS:
        if definition.cluster_id == cluster_id:
            return definition.cluster_name
    raise KeyError(f"未找到题族 {cluster_id}。")


def load_effective_b_items_for_round5(
    *,
    top200_path: Path,
    p1_p2_report_path: Path,
    round1_report_path: Path,
    round2_report_path: Path,
    round3_report_path: Path,
    round4_report_path: Path,
) -> list[dict[str, Any]]:
    """读取 Round5 仍然有效的高价值 B 题。

    说明：
        1. 先复用 Round4 的有效 B 集合；
        2. 再扣除 Round4 已推进进 A 和已转入 C 的题；
        3. 这样 Round5 拿到的就是当前真实还留在 B 的 6 条题。
    """
    effective_b_items = load_effective_b_items_for_round4(
        top200_path=top200_path,
        p1_p2_report_path=p1_p2_report_path,
        round1_report_path=round1_report_path,
        round2_report_path=round2_report_path,
        round3_report_path=round3_report_path,
    )
    round4_report = json.loads(round4_report_path.read_text(encoding="utf-8"))
    excluded_ids = set(round4_report["promoted_question_ids"])
    excluded_ids.update(round4_report["moved_to_c_question_ids"])
    return [item for item in effective_b_items if item["question_id"] not in excluded_ids]


def _resolve_round5_result(
    *,
    question_id: str,
    status_code: str,
    query_key: str | None,
) -> tuple[str, str, str]:
    """按 Round5 当前真实结果映射最终分类和归因。"""
    if status_code == LogisticsErrorCodeRegistry.OK and query_key:
        return (
            "A",
            "promoted_to_a",
            ROUND5_PROMOTED_REASON_MAP.get(question_id, "当前主链路已能稳定命中正式 query_key，可纳入 A 类。"),
        )
    if status_code == LogisticsErrorCodeRegistry.UNSUPPORTED_QUESTION:
        return (
            "C",
            "moved_to_c",
            ROUND5_MOVED_TO_C_REASON_MAP.get(question_id, "当前问题已确认超出一期结构化统计边界，应转入 C 类。"),
        )
    return (
        "B",
        "remain_b",
        "当前问题仍需继续保留在 B 类业务化澄清，不应直接误落成功态。",
    )


def evaluate_round5(
    *,
    effective_b_items: list[dict[str, Any]],
    round4_report_path: Path,
) -> dict[str, Any]:
    """执行 Top200 高价值 B 题工厂化 Round5。"""
    selected_items = [
        item
        for item in effective_b_items
        if assign_cluster(item).cluster_id in ROUND5_CLUSTER_IDS
    ]
    records: list[Round5Record] = []

    db = SessionLocal()
    service = LogisticsDataQaService(db=db, query_log_repository=NoopQueryLogRepository())
    try:
        for item in selected_items:
            definition = assign_cluster(item)
            result = service.query(
                LogisticsDataQaQueryRequest(question=item["question"]),
                trace_id="top200-b-factory-round5",
            )
            status_code = result.status.code if result.status else "NO_STATUS"
            final_classification, closure_result, closure_reason = _resolve_round5_result(
                question_id=item["question_id"],
                status_code=status_code,
                query_key=result.query_plan.query_key,
            )
            records.append(
                Round5Record(
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
    for cluster_id in ROUND5_CLUSTER_IDS:
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

    round4_report = json.loads(round4_report_path.read_text(encoding="utf-8"))
    before_distribution = round4_report["summary"]["after_top200_distribution"]
    after_distribution = {
        "A": before_distribution["A"] + len(promoted),
        "B": before_distribution["B"] - len(promoted) - len(moved_to_c),
        "C": before_distribution["C"] + len(moved_to_c),
    }

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "selected_cluster_ids": list(ROUND5_CLUSTER_IDS),
        "selected_cluster_names": [_lookup_cluster_name(cluster_id) for cluster_id in ROUND5_CLUSTER_IDS],
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


def render_markdown(report: dict[str, Any]) -> str:
    """渲染 Round5 摘要文档。"""
    summary = report["summary"]
    lines: list[str] = []
    lines.append("# Top200 高价值 B 题工厂化 Round5")
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    lines.append(f"- Round5 共处理 **{summary['selected_questions']}** 条剩余高价值 B 题。")
    lines.append(f"- 本轮推进进 A：**{summary['promoted_to_a']}** 条。")
    lines.append(f"- 本轮继续保留 B：**{summary['remain_b']}** 条。")
    lines.append(f"- 本轮正式转入 C：**{summary['moved_to_c']}** 条。")
    lines.append("")
    lines.append("## Top200 分布变化")
    lines.append("")
    before_distribution = summary["before_top200_distribution"]
    after_distribution = summary["after_top200_distribution"]
    lines.append(
        f"- 收口前：A={before_distribution['A']} / B={before_distribution['B']} / C={before_distribution['C']}"
    )
    lines.append(
        f"- 收口后：A={after_distribution['A']} / B={after_distribution['B']} / C={after_distribution['C']}"
    )
    lines.append("")
    lines.append("## 各题族结果")
    lines.append("")
    for cluster_id in report["selected_cluster_ids"]:
        item = report["cluster_summary"].get(cluster_id)
        if not item:
            continue
        lines.append(f"### {item['cluster_name']}")
        lines.append("")
        lines.append(
            f"- 题数：{item['selected_question_count']}\n- 推进进 A：{item['promoted_to_a']}\n- 保留 B：{item['remain_b']}\n- 转入 C：{item['moved_to_c']}"
        )
        lines.append("")
    lines.append("## 单题结果")
    lines.append("")
    for item in report["items"]:
        lines.append(
            f"- {item['question_id']}：{item['closure_result']}，{item['closure_reason']}"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    """生成 Top200 高价值 B 题工厂化 Round5 报告。"""
    parser = argparse.ArgumentParser(description="Top200 高价值 B 题工厂化 Round5")
    parser.add_argument(
        "--top200-json",
        default=str(PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_top200_questions.json"),
        help="Top200 正式清单 JSON 路径",
    )
    parser.add_argument(
        "--p1-p2-report",
        default=str(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_top200_p1_p2_regression_report.json"),
        help="P1/P2 收口报告路径",
    )
    parser.add_argument(
        "--round1-report",
        default=str(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_top200_b_factory_round1_report.json"),
        help="Round1 工厂化报告路径",
    )
    parser.add_argument(
        "--round2-report",
        default=str(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_top200_b_factory_round2_report.json"),
        help="Round2 工厂化报告路径",
    )
    parser.add_argument(
        "--round3-report",
        default=str(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_top200_b_factory_round3_report.json"),
        help="Round3 工厂化报告路径",
    )
    parser.add_argument(
        "--round4-report",
        default=str(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_top200_b_factory_round4_report.json"),
        help="Round4 工厂化报告路径",
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_top200_b_factory_round5_report.json"),
        help="Round5 JSON 报告输出路径",
    )
    parser.add_argument(
        "--doc-output",
        default=str(PROJECT_ROOT / "docs/LOGISTICS_TOP200_B_FACTORY_ROUND5.md"),
        help="Round5 Markdown 摘要输出路径",
    )
    args = parser.parse_args()

    effective_b_items = load_effective_b_items_for_round5(
        top200_path=Path(args.top200_json),
        p1_p2_report_path=Path(args.p1_p2_report),
        round1_report_path=Path(args.round1_report),
        round2_report_path=Path(args.round2_report),
        round3_report_path=Path(args.round3_report),
        round4_report_path=Path(args.round4_report),
    )
    report = evaluate_round5(
        effective_b_items=effective_b_items,
        round4_report_path=Path(args.round4_report),
    )
    output_path = Path(args.output)
    doc_path = Path(args.doc_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    doc_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

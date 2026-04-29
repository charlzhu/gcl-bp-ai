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


class NoopQueryLogRepository:
    """无副作用查询日志仓储。

    说明：
        1. 工厂化回归需要真实调用当前 data-qa 主链路；
        2. 但本轮不希望把批量回归题写进业务查询历史；
        3. 因此脚本内注入空日志仓储，避免污染正式查询记录。
    """

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        _ = db, payload
        return 0


@dataclass(frozen=True)
class ClusterDefinition:
    """Top200 高价值 B 题族定义。"""

    cluster_id: str
    cluster_name: str
    question_ids: tuple[str, ...]
    representative_ids: tuple[str, ...]
    current_blocker_reason: str
    fit_round1: bool
    fit_round1_reason: str
    time_dimensions: list[str]
    metric_dimensions: list[str]
    business_dimensions: list[str]
    filter_dimensions: list[str]
    source_layers: list[str]
    output_shapes: list[str]
    required_capabilities: list[str]


@dataclass
class FactoryRecord:
    """工厂化 round1 单题执行结果。"""

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


CLUSTER_DEFINITIONS: tuple[ClusterDefinition, ...] = (
    ClusterDefinition(
        cluster_id="hist_province_total_fee",
        cluster_name="历史省份累计总费用类",
        question_ids=("Q008", "Q009", "Q010", "Q011", "Q012", "Q013", "Q014", "Q015"),
        representative_ids=("Q008", "Q010", "Q015"),
        current_blocker_reason="当前主要被“缺时间范围”通用澄清拦住，但业务口径已可统一解释为 2023–2025 历史累计。",
        fit_round1=True,
        fit_round1_reason="业务高频、领导价值高，且只需补一个省份总费用汇总能力点就能成批收口。",
        time_dimensions=["年", "历史累计"],
        metric_dimensions=["总费用", "总发运量"],
        business_dimensions=["省份"],
        filter_dimensions=["目的省份"],
        source_layers=["历史台账"],
        output_shapes=["聚合", "表格输出"],
        required_capabilities=["历史累计时间口径固化", "query_key 新增", "结果结构复用"],
    ),
    ClusterDefinition(
        cluster_id="hist_carrier_annual_kpi",
        cluster_name="历史承运商年度经营KPI类",
        question_ids=("RAW073", "RAW072", "RAW023", "RAW017", "RAW016", "RAW024", "RAW021", "RAW020"),
        representative_ids=("RAW073", "RAW024", "RAW021"),
        current_blocker_reason="当前主要被术语差异卡住，例如“承运量 / 运输量 / 发货量 / 各家物流”没有统一归一到承运商年度 KPI。",
        fit_round1=True,
        fit_round1_reason="一旦补齐术语归一和解析增强，就能批量复用 hist_carrier_kpi_by_year。",
        time_dimensions=["年"],
        metric_dimensions=["发运量", "占比", "总费用"],
        business_dimensions=["承运商"],
        filter_dimensions=["年份"],
        source_layers=["历史台账"],
        output_shapes=["排名", "表格输出"],
        required_capabilities=["术语归一增强", "query_key 参数复用", "结果结构复用"],
    ),
    ClusterDefinition(
        cluster_id="sys_monthly_company_total_fee",
        cluster_name="2026月度承运商总运费类",
        question_ids=("RAW052", "RAW056", "SQ572", "SQ570", "SQ568", "SQ566", "SQ564", "SQ562"),
        representative_ids=("SQ570", "SQ566", "RAW052"),
        current_blocker_reason="当前一部分题只差承运商名称抽取，另一部分包含基地过滤，仍缺稳定映射字段。",
        fit_round1=True,
        fit_round1_reason="先收“月度承运商总运费”主干能力，可以顺带吃掉 2026 月度经营高频题；基地过滤子题则继续留在 B。",
        time_dimensions=["年", "月"],
        metric_dimensions=["总运费"],
        business_dimensions=["承运商", "客户"],
        filter_dimensions=["月份", "承运商", "客户", "基地"],
        source_layers=["2026系统数据"],
        output_shapes=["聚合", "表格输出"],
        required_capabilities=["承运商名称抽取增强", "系统费用 query_key 复用", "基地映射继续澄清"],
    ),
    ClusterDefinition(
        cluster_id="hist_vehicle_trip_count",
        cluster_name="历史车型总车次类",
        question_ids=("RAW067", "RAW039", "RAW003"),
        representative_ids=("RAW067", "RAW039"),
        current_blocker_reason="当前车型问法较口语化，缺少统一车型别名归一和车次识别。",
        fit_round1=True,
        fit_round1_reason="只需补车型别名和历史车次直接放行规则，就能批量从 B 收进 A。",
        time_dimensions=["年"],
        metric_dimensions=["车次"],
        business_dimensions=["车型"],
        filter_dimensions=["年份", "车型"],
        source_layers=["历史台账"],
        output_shapes=["聚合", "表格输出"],
        required_capabilities=["车型归一增强", "车次问法识别增强"],
    ),
    ClusterDefinition(
        cluster_id="hist_route_pricing_analysis",
        cluster_name="历史线路/城市运价分析类",
        question_ids=("RAW029", "RAW025", "RAW047", "RAW053", "RAW063", "RAW061"),
        representative_ids=("RAW029", "RAW047", "RAW053"),
        current_blocker_reason="当前缺少“线路均价 / 最高价 / 最低价 / 月均价对比”的统一 query_key 和结果模板。",
        fit_round1=False,
        fit_round1_reason="题量不小，但需要新增线路均价和最高/最低价能力点，收口成本高于 round1 其他题族。",
        time_dimensions=["年", "月", "年度对比"],
        metric_dimensions=["平均运费", "最高价", "最低价"],
        business_dimensions=["始发地", "目的地", "车型", "城市"],
        filter_dimensions=["年份", "月份", "始发地", "目的地", "车型"],
        source_layers=["历史台账"],
        output_shapes=["聚合", "对比", "表格输出"],
        required_capabilities=["线路运价 query_key 扩展", "时间解析增强", "结果结构复用"],
    ),
    ClusterDefinition(
        cluster_id="sys_monthly_unit_fee",
        cluster_name="2026月度单瓦成本类",
        question_ids=("RAW057", "SQ532", "SQ528"),
        representative_ids=("SQ528", "SQ532", "RAW057"),
        current_blocker_reason="当前系统侧还没有正式单瓦运输成本 query_key，且缺少年份的题仍需保留澄清。",
        fit_round1=True,
        fit_round1_reason="只要补系统单瓦成本正式口径，就能吃掉明确年月题；缺少年份的题继续保留 B。",
        time_dimensions=["年", "月"],
        metric_dimensions=["单瓦成本"],
        business_dimensions=[],
        filter_dimensions=["年份", "月份", "承运商"],
        source_layers=["2026系统数据"],
        output_shapes=["聚合", "表格输出"],
        required_capabilities=["系统单瓦成本 query_key 新增", "结果结构复用", "缺少年份继续澄清"],
    ),
    ClusterDefinition(
        cluster_id="carrier_cost_ranking",
        cluster_name="承运商成本/运费排名类",
        question_ids=("SQ522", "SQ521", "SQ519", "SQ518", "SQ516", "SQ515"),
        representative_ids=("SQ522", "SQ518", "SQ515"),
        current_blocker_reason="当前缺少统一的承运商单瓦成本 / 总运费排名 query_key 和排序输出模板。",
        fit_round1=False,
        fit_round1_reason="业务价值高，但需要新增 2026/历史承运商排名能力，适合作为 round2 题族。",
        time_dimensions=["年", "月区间"],
        metric_dimensions=["单瓦成本", "总运费", "排名"],
        business_dimensions=["承运商"],
        filter_dimensions=["年份", "月份"],
        source_layers=["历史台账", "2026系统数据"],
        output_shapes=["排名", "表格输出"],
        required_capabilities=["承运商排名 query_key 扩展", "排序结构复用"],
    ),
    ClusterDefinition(
        cluster_id="region_mw_summary_breakdown",
        cluster_name="区域/年度运量综合与拆分类",
        question_ids=("RAW036", "RAW011", "RAW009", "RAW027"),
        representative_ids=("RAW027", "RAW009", "RAW036"),
        current_blocker_reason="当前混杂了系统总量、区域总量和采购方式拆分，缺少统一的维度拆分规则。",
        fit_round1=False,
        fit_round1_reason="价值高，但需要先把采购方式和 2026 综合运量口径再整理一轮，适合 round2 之后推进。",
        time_dimensions=["年", "月区间"],
        metric_dimensions=["发运量"],
        business_dimensions=["区域", "采购方式"],
        filter_dimensions=["年份", "区域", "采购方式"],
        source_layers=["历史台账", "2026系统数据"],
        output_shapes=["聚合", "拆分表格"],
        required_capabilities=["拆分维度固化", "query_key 参数化", "澄清模板继续细化"],
    ),
    ClusterDefinition(
        cluster_id="customer_project_analysis",
        cluster_name="客户/项目总运量与项目地分析类",
        question_ids=("RAW038", "RAW049", "RAW050", "Q256"),
        representative_ids=("RAW038", "RAW049", "Q256"),
        current_blocker_reason="当前仍缺采购方式拆分口径、年份范围和客户/项目主体标准字段统一规则。",
        fit_round1=False,
        fit_round1_reason="业务价值高，但仍涉及采购方式、年份和项目/客户映射，收口成本高于 round1 题族。",
        time_dimensions=["年", "历史累计"],
        metric_dimensions=["发运量", "总费用"],
        business_dimensions=["客户", "项目", "收货地址"],
        filter_dimensions=["年份", "客户", "项目", "采购方式"],
        source_layers=["历史台账", "2026系统数据"],
        output_shapes=["聚合", "排名", "明细"],
        required_capabilities=["客户/项目映射增强", "采购方式字段校验", "高运费地址模板继续细化"],
    ),
    ClusterDefinition(
        cluster_id="system_status_quality_ranking",
        cluster_name="2026系统状态/排名/填充率类",
        question_ids=("Q280", "Q269", "Q268", "Q267", "Q291", "Q287", "Q275"),
        representative_ids=("Q280", "Q267", "Q275"),
        current_blocker_reason="当前涉及填充率、解析成功率、项目排名和异常分布，需要新的数据质量/排名 query_key 组合。",
        fit_round1=False,
        fit_round1_reason="这类题适合在 round2/round3 统一做“数据质量与状态排行能力包”，本轮先不展开。",
        time_dimensions=["年"],
        metric_dimensions=["任务量", "填充率", "解析成功率"],
        business_dimensions=["承运商", "省份", "项目", "城市"],
        filter_dimensions=["年份", "状态", "字段可用性"],
        source_layers=["2026系统数据"],
        output_shapes=["排名", "表格输出"],
        required_capabilities=["数据质量 query_key 扩展", "填充率/成功率结果模板", "字段校验增强"],
    ),
    ClusterDefinition(
        cluster_id="city_carrier_avg_price",
        cluster_name="城市承运商单车均价类",
        question_ids=("Q059", "Q058", "Q057", "Q056", "Q055"),
        representative_ids=("Q056", "Q055", "Q059"),
        current_blocker_reason="当前缺年份、缺单价/车口径，同时还需要城市 × 承运商分组均价 query_key。",
        fit_round1=False,
        fit_round1_reason="成组明显，但需要新 query_key；优先级低于 round1 已选高频题族。",
        time_dimensions=["年"],
        metric_dimensions=["平均单价/车"],
        business_dimensions=["城市", "承运商"],
        filter_dimensions=["年份", "城市"],
        source_layers=["历史台账"],
        output_shapes=["分组对比", "表格输出"],
        required_capabilities=["城市承运商均价 query_key 扩展", "年份澄清模板细化"],
    ),
    ClusterDefinition(
        cluster_id="diagnostic_analysis",
        cluster_name="异常/相关性分析类",
        question_ids=("Q338", "Q249"),
        representative_ids=("Q338", "Q249"),
        current_blocker_reason="当前属于诊断分析和显著性判断，超出一期结构化统计主线。",
        fit_round1=False,
        fit_round1_reason="即使高频也不应在本轮硬拉进 A，更适合继续停在 B/C 边界并等待下一阶段能力建设。",
        time_dimensions=["年", "时间范围"],
        metric_dimensions=["异常费用", "相关性"],
        business_dimensions=["城市", "区域"],
        filter_dimensions=["年份", "评价标准", "相关性口径"],
        source_layers=["历史台账"],
        output_shapes=["分析说明", "排名"],
        required_capabilities=["统计分析能力扩展", "异常定义与相关性口径固化"],
    ),
)

ROUND1_CLUSTER_IDS = (
    "hist_province_total_fee",
    "hist_carrier_annual_kpi",
    "sys_monthly_company_total_fee",
    "hist_vehicle_trip_count",
    "sys_monthly_unit_fee",
)


def load_effective_b_items(top200_path: Path, p1_p2_report_path: Path) -> list[dict[str, Any]]:
    """读取当前 Top200 里实际还留在 B 的高价值题。"""
    payload = json.loads(top200_path.read_text(encoding="utf-8"))
    report = json.loads(p1_p2_report_path.read_text(encoding="utf-8"))
    promoted_ids = {
        item["question_id"]
        for item in report["b_closure_progress"]["items"]
        if item["closure_result"] == "promoted_to_a"
    }
    return [
        item
        for item in payload["items"]
        if item["current_classification"] == "B" and item["question_id"] not in promoted_ids
    ]


def assign_cluster(item: dict[str, Any]) -> ClusterDefinition:
    """按题号把高价值 B 题归入唯一题族。

    说明：
        1. 当前 Top200 有明确的固定题号集合，按题号映射最稳定；
        2. 题族定义仍然是按业务意图和结构模式组织，不是按题号罗列；
        3. 如果出现漏分，脚本会直接失败，避免静默漏题。
    """
    question_id = item["question_id"]
    for definition in CLUSTER_DEFINITIONS:
        if question_id in definition.question_ids:
            return definition
    raise KeyError(f"未找到题号 {question_id} 的题族定义。")


def build_cluster_payload(effective_b_items: list[dict[str, Any]]) -> dict[str, Any]:
    """生成题族聚类 JSON。"""
    clusters: list[dict[str, Any]] = []
    for definition in CLUSTER_DEFINITIONS:
        cluster_items = [item for item in effective_b_items if item["question_id"] in definition.question_ids]
        clusters.append(
            {
                "cluster_id": definition.cluster_id,
                "cluster_name": definition.cluster_name,
                "question_count": len(cluster_items),
                "representative_questions": [
                    {
                        "question_id": item["question_id"],
                        "question": item["question"],
                    }
                    for item in cluster_items
                    if item["question_id"] in definition.representative_ids
                ],
                "question_ids": [item["question_id"] for item in cluster_items],
                "current_blocker_reason": definition.current_blocker_reason,
                "fit_round1": definition.fit_round1,
                "fit_round1_reason": definition.fit_round1_reason,
            }
        )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "effective_b_total": len(effective_b_items),
        "cluster_count": len(CLUSTER_DEFINITIONS),
        "clusters": clusters,
    }


def build_capability_matrix_payload(effective_b_items: list[dict[str, Any]]) -> dict[str, Any]:
    """生成题族能力矩阵 JSON。"""
    family_items: list[dict[str, Any]] = []
    for definition in CLUSTER_DEFINITIONS:
        cluster_items = [item for item in effective_b_items if item["question_id"] in definition.question_ids]
        family_items.append(
            {
                "cluster_id": definition.cluster_id,
                "cluster_name": definition.cluster_name,
                "question_count": len(cluster_items),
                "time_dimensions": definition.time_dimensions,
                "metric_dimensions": definition.metric_dimensions,
                "business_dimensions": definition.business_dimensions,
                "filter_dimensions": definition.filter_dimensions,
                "source_layers": definition.source_layers,
                "output_shapes": definition.output_shapes,
                "required_capabilities": definition.required_capabilities,
                "fit_round1": definition.fit_round1,
            }
        )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "effective_b_total": len(effective_b_items),
        "families": family_items,
    }


def evaluate_round1(effective_b_items: list[dict[str, Any]]) -> dict[str, Any]:
    """执行 round1 题族批量收口回归。"""
    round1_ids = {
        item["question_id"]
        for item in effective_b_items
        if assign_cluster(item).cluster_id in ROUND1_CLUSTER_IDS
    }
    selected_items = [item for item in effective_b_items if item["question_id"] in round1_ids]
    records: list[FactoryRecord] = []

    db = SessionLocal()
    service = LogisticsDataQaService(db=db, query_log_repository=NoopQueryLogRepository())
    try:
        for item in selected_items:
            definition = assign_cluster(item)
            result = service.query(
                LogisticsDataQaQueryRequest(question=item["question"]),
                trace_id="top200-b-factory-round1",
            )
            actual_status_code = result.status.code if result.status else "NO_STATUS"
            if (
                actual_status_code == LogisticsErrorCodeRegistry.OK
                and result.supported
                and not result.needs_clarification
                and result.query_plan.query_key
            ):
                final_classification = "A"
                closure_result = "promoted_to_a"
                closure_reason = "当前主链路已能稳定命中正式 query_key，可纳入 A 类回归。"
            elif result.needs_clarification:
                final_classification = "B"
                closure_result = "remain_b"
                closure_reason = "当前仍缺稳定口径或字段映射，继续保留 B 类澄清。"
            elif not result.supported:
                final_classification = "C"
                closure_result = "moved_to_c"
                closure_reason = "当前问题已确认超出一期能力边界，应转入 C 类不支持。"
            else:
                final_classification = "B"
                closure_result = "remain_b"
                closure_reason = "当前结果结构不稳定，暂不进入 A 类。"
            records.append(
                FactoryRecord(
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

    selected_total = len(records)
    promoted = [record for record in records if record.closure_result == "promoted_to_a"]
    remain_b = [record for record in records if record.closure_result == "remain_b"]
    moved_to_c = [record for record in records if record.closure_result == "moved_to_c"]

    cluster_summary: dict[str, dict[str, Any]] = {}
    for definition in CLUSTER_DEFINITIONS:
        if definition.cluster_id not in ROUND1_CLUSTER_IDS:
            continue
        cluster_records = [record for record in records if record.cluster_id == definition.cluster_id]
        if not cluster_records:
            continue
        cluster_summary[definition.cluster_id] = {
            "cluster_name": definition.cluster_name,
            "selected_question_count": len(cluster_records),
            "promoted_to_a": len([record for record in cluster_records if record.closure_result == "promoted_to_a"]),
            "remain_b": len([record for record in cluster_records if record.closure_result == "remain_b"]),
            "moved_to_c": len([record for record in cluster_records if record.closure_result == "moved_to_c"]),
            "question_ids": [record.question_id for record in cluster_records],
        }

    before_top200_distribution = {"A": 111, "B": 64, "C": 25}
    after_top200_distribution = {
        "A": before_top200_distribution["A"] + len(promoted),
        "B": before_top200_distribution["B"] - len(promoted) - len(moved_to_c),
        "C": before_top200_distribution["C"] + len(moved_to_c),
    }

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "selected_cluster_ids": list(ROUND1_CLUSTER_IDS),
        "selected_cluster_names": [
            definition.cluster_name for definition in CLUSTER_DEFINITIONS if definition.cluster_id in ROUND1_CLUSTER_IDS
        ],
        "summary": {
            "selected_questions": selected_total,
            "promoted_to_a": len(promoted),
            "remain_b": len(remain_b),
            "moved_to_c": len(moved_to_c),
            "before_top200_distribution": before_top200_distribution,
            "after_top200_distribution": after_top200_distribution,
        },
        "cluster_summary": cluster_summary,
        "promoted_question_ids": [record.question_id for record in promoted],
        "remain_b_question_ids": [record.question_id for record in remain_b],
        "moved_to_c_question_ids": [record.question_id for record in moved_to_c],
        "items": [asdict(record) for record in records],
    }


def main() -> None:
    """生成 Top200 高价值 B 题题族、能力矩阵和 round1 收口报告。"""
    parser = argparse.ArgumentParser(description="Top200 高价值 B 题工厂化 round1")
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
        "--clusters-output",
        default="/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/tmp/logistics_question_bank/logistics_top200_b_clusters.json",
        help="题族聚类 JSON 输出路径",
    )
    parser.add_argument(
        "--matrix-output",
        default="/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/tmp/logistics_question_bank/logistics_top200_b_capability_matrix.json",
        help="能力矩阵 JSON 输出路径",
    )
    parser.add_argument(
        "--round1-output",
        default="/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/tmp/logistics_question_bank/logistics_top200_b_factory_round1_report.json",
        help="round1 收口报告输出路径",
    )
    args = parser.parse_args()

    top200_path = Path(args.top200_json)
    p1_p2_report_path = Path(args.p1_p2_report)
    effective_b_items = load_effective_b_items(top200_path=top200_path, p1_p2_report_path=p1_p2_report_path)

    clusters_payload = build_cluster_payload(effective_b_items)
    matrix_payload = build_capability_matrix_payload(effective_b_items)
    round1_payload = evaluate_round1(effective_b_items)

    for output_path_str, payload in (
        (args.clusters_output, clusters_payload),
        (args.matrix_output, matrix_payload),
        (args.round1_output, round1_payload),
    ):
        output_path = Path(output_path_str)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(round1_payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

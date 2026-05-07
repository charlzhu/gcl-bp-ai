from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACCEPTED_MIGRATION_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_c_round2_accepted_migration.json"
)
MASTER_LEDGER_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_master_ledger.json"
A_PRECISE_PLAN_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_c_round2_new_a_precise_batches.json"
)
B_REVIEW_PLAN_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_b_candidate_clarification_review_batches.json"
)
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_post_migration_plan_report.json"
A_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_C_ROUND2_NEW_A_PRECISE_PLAN.md"
B_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_B_CANDIDATE_CLARIFICATION_REVIEW_PLAN.md"


A_BATCH_SIZES = [30, 30, 30, 37]
B_BATCH_SIZES = [60, 80, 80, 70]


@dataclass
class NewAPrecisePlanItem:
    """C Round2 新进 A 精确断言补强计划单题。"""

    plan_id: str
    batch_id: str
    batch_name: str
    batch_order: int
    question_id: str
    question: str
    source_group: str
    priority: str
    family: str
    query_key: str
    standard_answer_source: str
    assertion_scope: str
    assertion_fields: list[str]
    failure_classification_rule: str
    selection_reason: str
    row_count: int


@dataclass
class BCandidateReviewPlanItem:
    """C Round2 B_candidate 澄清模板复检计划单题。"""

    review_id: str
    batch_id: str
    batch_name: str
    batch_order: int
    question_id: str
    question: str
    source_group: str
    priority: str
    family: str
    original_clarification_category: str
    review_category: str
    missing_slots_to_check: list[str]
    suggested_clarification_questions: list[str]
    expected_response_status: str
    required_behavior: str
    llm_allowed_role: str
    boundary_owner: str
    review_reason: str


def _load_json(path: Path) -> Any:
    """读取 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8"))


def _contains_any(text: str, keywords: list[str]) -> bool:
    """判断文本是否包含任一关键词。"""

    return any(keyword in text for keyword in keywords)


def _load_accepted_items() -> list[dict[str, Any]]:
    """读取 C Round2 已接受迁移快照。"""

    return _load_json(ACCEPTED_MIGRATION_PATH)["items"]


def _load_ledger_index() -> dict[tuple[str, str], dict[str, Any]]:
    """读取 903 正式总账并按“题号 + 原题”建立索引。"""

    ledger_items = _load_json(MASTER_LEDGER_PATH)["items"]
    return {(item["question_id"], item["question"]): item for item in ledger_items}


def _query_key_rank(query_key: str) -> int:
    """定义新进 A 精确断言优先级。

    说明：
        系统侧 2026 查询和费用类查询优先进入前两批；
        历史区域汇总类数量较大，放到后续批次批量固化。
    """

    ranks = {
        "sys_mw_and_trip_count": 1,
        "sys_total_fee_by_filters": 2,
        "sys_mw_by_procurement_type": 3,
        "hist_customer_mw": 4,
        "hist_carrier_kpi_by_year": 5,
        "hist_mw_by_all_regions": 6,
        "hist_vehicle_type_trip_count": 7,
        "hist_mw_summary": 8,
    }
    return ranks.get(query_key, 99)


def _build_batch_lookup(batch_sizes: list[int], prefix: str, names: list[str]) -> list[tuple[str, str, int, range]]:
    """按批次数量生成批次区间。"""

    start = 0
    batches: list[tuple[str, str, int, range]] = []
    for index, size in enumerate(batch_sizes, start=1):
        end = start + size
        batch_id = f"{prefix}{index}"
        batches.append((batch_id, names[index - 1], index, range(start, end)))
        start = end
    return batches


def _resolve_batch(index: int, batches: list[tuple[str, str, int, range]]) -> tuple[str, str, int]:
    """根据序号匹配批次。"""

    for batch_id, batch_name, batch_order, batch_range in batches:
        if index in batch_range:
            return batch_id, batch_name, batch_order
    batch_id, batch_name, batch_order, _ = batches[-1]
    return batch_id, batch_name, batch_order


def _build_new_a_precise_plan(
    accepted_items: list[dict[str, Any]],
    ledger_index: dict[tuple[str, str], dict[str, Any]],
) -> list[NewAPrecisePlanItem]:
    """生成 127 条新进 A 的分批精确断言补强计划。"""

    a_items = [
        item
        for item in accepted_items
        if item.get("accepted_status") == "A"
        and item.get("migration_type") == "A_candidate"
        and item.get("passed") is True
    ]
    a_items.sort(
        key=lambda item: (
            _query_key_rank(item.get("actual_query_key") or item.get("query_key") or ""),
            item.get("source_group", ""),
            item["question_id"],
            item["question"],
        )
    )
    batches = _build_batch_lookup(
        A_BATCH_SIZES,
        "C2A-P",
        [
            "Round1：系统侧与费用高价值题",
            "Round2：客户/承运商与费用补强题",
            "Round3：区域/车型/承运商历史题",
            "Round4：历史区域总量批量补强题",
        ],
    )

    plan_items: list[NewAPrecisePlanItem] = []
    for zero_index, item in enumerate(a_items):
        ledger_item = ledger_index[(item["question_id"], item["question"])]
        query_key = item.get("actual_query_key") or item.get("query_key") or ""
        batch_id, batch_name, batch_order = _resolve_batch(zero_index, batches)
        plan_items.append(
            NewAPrecisePlanItem(
                plan_id=f"C2A-PREC-{zero_index + 1:03d}",
                batch_id=batch_id,
                batch_name=batch_name,
                batch_order=batch_order,
                question_id=item["question_id"],
                question=item["question"],
                source_group=item["source_group"],
                priority=ledger_item.get("current_priority", item.get("priority", "P3")),
                family=item["family"],
                query_key=query_key,
                standard_answer_source=(
                    "当前 logistics_ai 数据快照；由 data-qa 主链路执行并固化 "
                    "answer_summary、result_table.columns、result_table.rows。"
                ),
                assertion_scope="status.code + query_plan.query_key + answer_summary + result_table.columns + result_table.rows 精确快照断言",
                assertion_fields=[
                    "status.code",
                    "query_plan.query_key",
                    "answer_summary",
                    "result_table.columns",
                    "result_table.rows",
                ],
                failure_classification_rule="query_key/status 异常归为代码问题；answer_summary/rows 快照不一致归为数据基线变化。",
                selection_reason="C Round2 A_candidate 已通过行为回归并迁入正式 A，尚未纳入更严格精确断言。",
                row_count=int(item.get("row_count") or 0),
            )
        )
    return plan_items


def _derive_review_category(item: dict[str, Any]) -> str:
    """将 B_candidate 归入更细的澄清模板复检题型。"""

    question = item["question"]
    original_category = item.get("clarification_category")
    if original_category == "procurement_metric_scope" or "采购方式" in question:
        return "procurement_metric_scope"
    if original_category == "data_consistency_scope" or _contains_any(question, ["一致", "差异", "不一致", "对账"]):
        return "data_consistency_scope"
    if original_category == "vague_status" or _contains_any(question, ["异常", "问题", "风险", "最差", "原因"]):
        return "abnormal_or_reason_scope"
    if _contains_any(question, ["运输方式", "公路", "铁路", "水路", "汽运", "铁运"]):
        return "transport_mode_metric_scope"
    if _contains_any(question, ["签收率", "SIGNEDFOR", "PREASSIGN", "状态", "任务"]):
        return "system_state_scope"
    if _contains_any(question, ["始发", "发往", "线路", "城市", "地址"]):
        return "route_or_address_scope"
    if _contains_any(question, ["车型", "17.5", "13m", "车辆", "车次"]):
        return "vehicle_or_trip_scope"
    if _contains_any(question, ["客户", "项目", "项目地"]):
        return "customer_project_scope"
    if _contains_any(question, ["排名", "前五", "前十", "最高", "最低"]):
        return "ranking_basis_scope"
    return "generic_metric_scope"


def _category_missing_slots(category: str) -> list[str]:
    """返回澄清模板复检时需要检查的缺失槽位。"""

    mapping = {
        "abnormal_or_reason_scope": ["统计时间范围", "异常/高成本定义", "输出形态", "是否需要明细"],
        "transport_mode_metric_scope": ["统计时间范围", "运输方式口径", "指标口径", "单位口径"],
        "procurement_metric_scope": ["统计时间范围", "采购方式口径", "指标口径", "分组维度"],
        "data_consistency_scope": ["统计时间范围", "对账对象", "差异阈值", "比较维度"],
        "system_state_scope": ["统计时间范围", "状态枚举口径", "指标口径", "分组维度"],
        "route_or_address_scope": ["统计时间范围", "始发/目的地范围", "指标口径", "车型/运输方式限制"],
        "vehicle_or_trip_scope": ["统计时间范围", "车次/车辆数口径", "车型口径", "分组维度"],
        "customer_project_scope": ["统计时间范围", "客户/项目名称", "指标口径", "是否需要排名"],
        "ranking_basis_scope": ["统计时间范围", "排名指标", "排名方向", "TopN 数量"],
        "generic_metric_scope": ["统计时间范围", "指标口径", "分组维度", "输出形态"],
    }
    return mapping.get(category, mapping["generic_metric_scope"])


def _category_questions(category: str) -> list[str]:
    """返回业务化追问候选模板。"""

    mapping = {
        "abnormal_or_reason_scope": [
            "请先说明异常或高成本的判断标准，例如超过均值多少、是否按单瓦成本或单车费用判断？",
            "需要我输出异常明细，还是只汇总异常数量和涉及区域/线路？",
            "请补充统计时间范围，例如 2024 年全年、2025 年某个月或最近一个季度。",
        ],
        "transport_mode_metric_scope": [
            "请明确运输方式口径，例如公路、铁路、水路、汽运或铁运是否需要合并同义口径？",
            "请说明要统计的指标，是发运量、运费、车次、件数还是单瓦成本？",
            "请补充时间范围和是否需要按区域/省份/承运商拆分。",
        ],
        "procurement_metric_scope": [
            "请明确采购方式口径，以及要统计发运量、费用、车次还是单瓦成本？",
            "请补充统计时间范围，例如 2026 年 1 月、2026 年全年或指定区间。",
            "是否需要按承运商、区域、省份或客户继续拆分？",
        ],
        "data_consistency_scope": [
            "请说明要对比哪两个对象的一致性，例如客户名称、承运商映射、状态字段或费用字段？",
            "请补充差异判断标准，例如完全不一致、缺失值、金额差异超过阈值等。",
            "请明确统计时间范围和需要输出明细还是汇总。",
        ],
        "system_state_scope": [
            "请明确要看的系统状态口径，例如 SIGNEDFOR、PREASSIGN 或全部状态分布？",
            "请说明统计指标，是任务数、占比、签收率还是异常任务数量？",
            "请补充时间范围和是否需要按承运商/省份/客户拆分。",
        ],
        "route_or_address_scope": [
            "请明确始发地和目的地范围，是单条线路、某省还是某区域？",
            "请说明要看的指标，是发运量、运费、车次、单车均价还是单瓦成本？",
            "请补充时间范围，以及是否限定车型或运输方式。",
        ],
        "vehicle_or_trip_scope": [
            "请明确车次口径，是发运车次、车辆数、车型数量还是系统任务车辆字段？",
            "请补充统计时间范围，以及是否限定区域、线路或承运商。",
            "是否需要按车型，例如 17.5 米车、13 米车等继续拆分？",
        ],
        "customer_project_scope": [
            "请明确客户或项目名称，或说明是否要按客户/项目整体排名。",
            "请说明指标口径，是发运量、费用、车次还是单瓦成本？",
            "请补充统计时间范围，以及是否需要按区域或省份拆分。",
        ],
        "ranking_basis_scope": [
            "请明确排名指标，例如按发运量、费用、车次、单瓦成本还是签收率排名？",
            "请说明排名方向和数量，例如最高前五、最低后十或全部排序。",
            "请补充统计时间范围和分组维度，例如承运商、区域、省份或客户。",
        ],
        "generic_metric_scope": [
            "请补充统计时间范围，例如年份、月份、季度或起止日期。",
            "请明确要统计的指标，是发运量、运费、车次、件数、单瓦成本还是占比？",
            "请说明是否需要按区域、省份、承运商、客户、线路或运输方式拆分。",
        ],
    }
    return mapping.get(category, mapping["generic_metric_scope"])


def _review_category_rank(category: str) -> int:
    """定义 B_candidate 澄清模板复检优先级。"""

    ranks = {
        "abnormal_or_reason_scope": 1,
        "transport_mode_metric_scope": 2,
        "procurement_metric_scope": 3,
        "route_or_address_scope": 4,
        "system_state_scope": 5,
        "data_consistency_scope": 6,
        "vehicle_or_trip_scope": 7,
        "customer_project_scope": 8,
        "ranking_basis_scope": 9,
        "generic_metric_scope": 10,
    }
    return ranks.get(category, 99)


def _build_b_candidate_review_plan(accepted_items: list[dict[str, Any]]) -> list[BCandidateReviewPlanItem]:
    """生成 290 条 B_candidate 的澄清模板复检计划。"""

    b_items = [
        item
        for item in accepted_items
        if item.get("accepted_status") == "B"
        and item.get("migration_type") == "B_candidate"
    ]
    b_items.sort(
        key=lambda item: (
            _review_category_rank(_derive_review_category(item)),
            item.get("source_group", ""),
            item["family"],
            item["question_id"],
            item["question"],
        )
    )
    batches = _build_batch_lookup(
        B_BATCH_SIZES,
        "BCR",
        [
            "Round1：异常/运输方式/采购高频澄清",
            "Round2：线路/系统状态/数据一致性澄清",
            "Round3：车型/客户/排名澄清",
            "Round4：通用指标口径澄清收尾",
        ],
    )

    plan_items: list[BCandidateReviewPlanItem] = []
    for zero_index, item in enumerate(b_items):
        category = _derive_review_category(item)
        batch_id, batch_name, batch_order = _resolve_batch(zero_index, batches)
        original_category = item.get("clarification_category") or "generic_clarification"
        plan_items.append(
            BCandidateReviewPlanItem(
                review_id=f"BCR-{zero_index + 1:03d}",
                batch_id=batch_id,
                batch_name=batch_name,
                batch_order=batch_order,
                question_id=item["question_id"],
                question=item["question"],
                source_group=item["source_group"],
                priority=item.get("priority", "P3"),
                family=item["family"],
                original_clarification_category=original_category,
                review_category=category,
                missing_slots_to_check=_category_missing_slots(category),
                suggested_clarification_questions=_category_questions(category),
                expected_response_status="needs_clarification=true",
                required_behavior="规则层必须保持澄清边界；不得误落 success 或 unsupported。",
                llm_allowed_role="LLM 仅允许做缺口径识别和追问候选生成，不能做最终边界裁决。",
                boundary_owner="question_bank_response_policy / data_qa_planner 规则层",
                review_reason="C Round2 B_candidate 已迁入 B，需进入后续澄清模板复检，提升真实问法下的业务化追问质量。",
            )
        )
    return plan_items


def _counter_by(items: list[Any], field_name: str) -> dict[str, int]:
    """按 dataclass 字段统计数量。"""

    counter: Counter[str] = Counter(getattr(item, field_name) for item in items)
    return dict(counter)


def _batch_summary(items: list[Any]) -> list[dict[str, Any]]:
    """生成批次统计。"""

    grouped: dict[str, list[Any]] = defaultdict(list)
    for item in items:
        grouped[item.batch_id].append(item)
    summaries: list[dict[str, Any]] = []
    for batch_id, batch_items in sorted(grouped.items(), key=lambda pair: pair[1][0].batch_order):
        summaries.append(
            {
                "batch_id": batch_id,
                "batch_name": batch_items[0].batch_name,
                "batch_order": batch_items[0].batch_order,
                "question_count": len(batch_items),
            }
        )
    return summaries


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """写出 JSON 文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _render_a_doc(payload: dict[str, Any]) -> str:
    """渲染新进 A 精确断言分批计划文档。"""

    summary = payload["summary"]
    lines = [
        "# C Round2 新进 A 精确断言补强计划",
        "",
        "## 一、结论",
        "",
        f"C Round2 新迁入 A 共 `{summary['total_questions']}` 条，已全部进入分批精确断言补强计划。",
        "本轮只建立分批计划，不直接刷新 127 条黄金答案基线。",
        "",
        "## 二、批次安排",
        "",
    ]
    for batch in summary["batch_summary"]:
        lines.append(f"- `{batch['batch_id']}`：{batch['batch_name']}，`{batch['question_count']}` 条")
    lines.extend(
        [
            "",
            "## 三、query_key 分布",
            "",
        ]
    )
    for key, value in summary["query_key_breakdown"].items():
        lines.append(f"- `{key}`：`{value}`")
    lines.extend(
        [
            "",
            "## 四、断言口径",
            "",
            "- 标准答案来源：当前 `logistics_ai` 数据快照，由正式 data-qa 主链路执行后固化。",
            "- 断言字段：`status.code`、`query_plan.query_key`、`answer_summary`、`result_table.columns`、`result_table.rows`。",
            "- 失败归因：query_key/status 异常归为代码问题；answer_summary/rows 快照不一致归为数据基线变化。",
            "",
            "## 五、第一批代表题",
            "",
            "| plan_id | 题号 | query_key | 问题 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for item in payload["items"][:10]:
        lines.append(f"| {item['plan_id']} | {item['question_id']} | {item['query_key']} | {item['question']} |")
    lines.extend(
        [
            "",
            "## 六、下一步",
            "",
            "建议优先执行 `C2A-P1`，形成第一批 30 条精确断言基线；通过后再继续推进 P2/P3/P4。",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_b_doc(payload: dict[str, Any]) -> str:
    """渲染 B_candidate 澄清模板复检计划文档。"""

    summary = payload["summary"]
    lines = [
        "# B_candidate 澄清模板复检计划",
        "",
        "## 一、结论",
        "",
        f"C Round2 迁入 B 的 B_candidate 共 `{summary['total_questions']}` 条，已全部纳入后续澄清模板复检。",
        "本轮不把 B_candidate 改成 success，也不让 LLM 改写 B/C 边界。",
        "",
        "## 二、批次安排",
        "",
    ]
    for batch in summary["batch_summary"]:
        lines.append(f"- `{batch['batch_id']}`：{batch['batch_name']}，`{batch['question_count']}` 条")
    lines.extend(["", "## 三、复检题型分布", ""])
    for key, value in summary["review_category_breakdown"].items():
        lines.append(f"- `{key}`：`{value}`")
    lines.extend(
        [
            "",
            "## 四、复检规则",
            "",
            "- 规则层仍然是最终边界裁决者。",
            "- LLM 只允许做缺口径识别和追问候选生成。",
            "- 每题必须稳定返回 `needs_clarification=true`。",
            "- 不允许误落 success，也不允许误落 unsupported。",
            "",
            "## 五、第一批代表题",
            "",
            "| review_id | 题号 | 复检题型 | 需检查缺口径 | 问题 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for item in payload["items"][:10]:
        lines.append(
            f"| {item['review_id']} | {item['question_id']} | {item['review_category']} | "
            f"{'；'.join(item['missing_slots_to_check'])} | {item['question']} |"
        )
    lines.extend(
        [
            "",
            "## 六、下一步",
            "",
            "建议优先执行 `BCR1`，复检 60 条高频澄清题，重点优化异常、运输方式、采购方式等业务化追问模板。",
        ]
    )
    return "\n".join(lines) + "\n"


def build_post_migration_plan() -> dict[str, Any]:
    """构建 903 总账迁移后的 A/B 后续治理计划。"""

    accepted_items = _load_accepted_items()
    ledger_index = _load_ledger_index()
    a_plan_items = _build_new_a_precise_plan(accepted_items, ledger_index)
    b_plan_items = _build_b_candidate_review_plan(accepted_items)
    generated_at = datetime.now().isoformat(timespec="seconds")

    a_payload = {
        "generated_at": generated_at,
        "source": str(ACCEPTED_MIGRATION_PATH),
        "summary": {
            "total_questions": len(a_plan_items),
            "batch_summary": _batch_summary(a_plan_items),
            "query_key_breakdown": _counter_by(a_plan_items, "query_key"),
            "family_breakdown": _counter_by(a_plan_items, "family"),
            "assertion_policy": "分批建立精确快照断言；不在本计划阶段直接刷新黄金答案。",
        },
        "items": [asdict(item) for item in a_plan_items],
    }
    b_payload = {
        "generated_at": generated_at,
        "source": str(ACCEPTED_MIGRATION_PATH),
        "summary": {
            "total_questions": len(b_plan_items),
            "batch_summary": _batch_summary(b_plan_items),
            "review_category_breakdown": _counter_by(b_plan_items, "review_category"),
            "original_clarification_category_breakdown": _counter_by(
                b_plan_items, "original_clarification_category"
            ),
            "review_policy": "规则层锁定澄清边界；LLM 只辅助缺口径识别和追问候选。",
        },
        "items": [asdict(item) for item in b_plan_items],
    }
    report_payload = {
        "generated_at": generated_at,
        "source": str(ACCEPTED_MIGRATION_PATH),
        "summary": {
            "new_a_precise_plan_total": len(a_plan_items),
            "b_candidate_review_plan_total": len(b_plan_items),
            "recommended_next_action": "先执行 C2A-P1 精确断言 Round1，再并行启动 BCR1 澄清模板复检。",
        },
        "a_precise_plan_summary": a_payload["summary"],
        "b_candidate_review_summary": b_payload["summary"],
    }

    _write_json(A_PRECISE_PLAN_PATH, a_payload)
    _write_json(B_REVIEW_PLAN_PATH, b_payload)
    _write_json(REPORT_PATH, report_payload)
    A_DOC_PATH.write_text(_render_a_doc(a_payload), encoding="utf-8")
    B_DOC_PATH.write_text(_render_b_doc(b_payload), encoding="utf-8")
    return report_payload


def main() -> None:
    """生成 903 迁移后的 A 精确断言补强计划和 B 澄清模板复检计划。"""

    report = build_post_migration_plan()
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

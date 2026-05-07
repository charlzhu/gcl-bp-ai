from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

MASTER_LEDGER_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_master_ledger.json"
B2A_CANDIDATES_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b2a_migration_review_candidates.json"
)
B2A_REVIEW_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_migration_gap_review_report.json"
B2A_A_REGRESSION_SET_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b2a_a_regression_questions.json"
)
B2A_PRECISE_PLAN_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b2a_precise_batches.json"
)
GAP_ROADMAP_JSON_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_gap_capability_roadmap.json"
MIGRATION_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b2a_migration_update_report.json"
MIGRATION_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B2A_MIGRATION_UPDATE.md"
GAP_ROADMAP_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_GAP_CAPABILITY_ROADMAP.md"


B2A_PRECISE_BATCHES = [
    ("B2A-P1", "Round1：系统侧与高价值费用题", 25),
    ("B2A-P2", "Round2：历史区域/客户/运输方式费用题", 30),
    ("B2A-P3", "Round3：历史总运费批量收尾题", 30),
]


@dataclass
class B2ARegressionQuestion:
    """B->A 新迁入题行为回归配置。

    参数：
        question_id: 题库题号。
        question: 原始问题。
        source_group: 来源分组。
        family: 所属题族。
        expected_query_key: 行为回归必须命中的 query_key。
        expected_status_code: 行为回归必须返回的状态码。
        migration_basis: 迁移依据说明。

    返回：
        该 dataclass 会被序列化为 JSON，供独立行为回归脚本复用。
    """

    question_id: str
    question: str
    source_group: str
    family: str
    expected_query_key: str
    expected_status_code: str
    migration_basis: str


@dataclass
class B2APrecisePlanItem:
    """B->A 新迁入题精确断言补强计划项。"""

    plan_id: str
    batch_id: str
    batch_name: str
    batch_order: int
    question_id: str
    question: str
    source_group: str
    family: str
    query_key: str
    standard_answer_source: str
    assertion_scope: str
    assertion_fields: list[str]
    failure_classification_rule: str
    selection_reason: str


@dataclass
class GapCapabilityItem:
    """B 类缺口能力建设路线项。"""

    capability_id: str
    gap_type: str
    family: str
    category: str
    priority: str
    question_count: int
    representative_questions: list[str]
    required_capability: str
    build_action: str
    acceptance_rule: str
    owner_type: str
    next_wave: str


def _load_json(path: Path) -> Any:
    """读取 JSON 文件。

    参数：
        path: JSON 文件路径。

    返回：
        反序列化后的 Python 对象。
    """

    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    """写出 JSON 文件。

    参数：
        path: 输出路径。
        payload: 待序列化对象。

    返回：
        无返回值。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _append_remark(original: str, remark: str) -> str:
    """追加总账备注，避免覆盖既有治理痕迹。"""

    if not original:
        return remark
    if remark in original:
        return original
    return f"{original}；{remark}"


def _query_key_rank(query_key: str) -> int:
    """定义精确断言计划排序优先级。"""

    ranks = {
        "sys_mw_and_trip_count": 1,
        "sys_total_fee_by_filters": 2,
        "hist_total_fee_summary": 3,
    }
    return ranks.get(query_key, 99)


def _resolve_precise_batch(index: int) -> tuple[str, str, int]:
    """按序号分配精确断言批次。

    参数：
        index: 从 0 开始的题目序号。

    返回：
        batch_id、batch_name、batch_order。
    """

    cursor = 0
    for order, (batch_id, batch_name, size) in enumerate(B2A_PRECISE_BATCHES, start=1):
        if cursor <= index < cursor + size:
            return batch_id, batch_name, order
        cursor += size
    batch_id, batch_name, _ = B2A_PRECISE_BATCHES[-1]
    return batch_id, batch_name, len(B2A_PRECISE_BATCHES)


def _validate_candidates(
    *,
    candidates: list[dict[str, Any]],
    review_records: list[dict[str, Any]],
    ledger_items: list[dict[str, Any]],
) -> list[str]:
    """校验 85 条候选是否仍满足正式迁移前置条件。

    重要业务逻辑：
        1. 候选必须出现在上一轮真实行为复核报告中；
        2. 候选必须 passed_behavior_review=true；
        3. 候选当前必须仍在正式总账 B 类，或已经由本脚本迁入 A；
        4. 已迁入 A 且 query_key 一致时视为幂等通过；
        5. 如果条件不满足，本脚本拒绝 apply，避免误迁移。
    """

    errors: list[str] = []
    review_index = {
        (item["question_id"], item["question"]): item
        for item in review_records
        if item.get("migration_decision") == "ready_for_a_migration"
    }
    ledger_index = {(item["question_id"], item["question"]): item for item in ledger_items}
    for candidate in candidates:
        key = (candidate["question_id"], candidate["question"])
        review_item = review_index.get(key)
        ledger_item = ledger_index.get(key)
        if not review_item:
            errors.append(f"{candidate['question_id']} 缺少 ready_for_a_migration 复核记录。")
            continue
        if review_item.get("passed_behavior_review") is not True:
            errors.append(f"{candidate['question_id']} 行为复核未通过。")
        if review_item.get("actual_query_key") != candidate.get("query_key"):
            errors.append(
                f"{candidate['question_id']} query_key 不一致：候选={candidate.get('query_key')}，复核={review_item.get('actual_query_key')}。"
            )
        if not ledger_item:
            errors.append(f"{candidate['question_id']} 在 903 总账中未找到原题。")
            continue
        current_status = ledger_item.get("current_status")
        current_query_key = ledger_item.get("current_query_key")
        if current_status == "A" and current_query_key == candidate.get("query_key"):
            continue
        if current_status != "B":
            errors.append(f"{candidate['question_id']} 当前总账状态不是 B/已迁入 A，而是 {current_status}。")
    return errors


def _recompute_ledger_summary(ledger_payload: dict[str, Any]) -> dict[str, Any]:
    """按更新后的 items 重算 903 总账汇总。"""

    items = ledger_payload["items"]
    baseline_distribution: Counter[str] = Counter(item["baseline_status"] for item in items)
    current_distribution: Counter[str] = Counter(item["current_status"] for item in items)
    migration_breakdown: Counter[str] = Counter(
        f"{item['baseline_status']}->{item['current_status']}" for item in items
    )
    pool_breakdown: Counter[str] = Counter(item["governance_pool"] for item in items)
    unique_distribution_members: defaultdict[str, set[str]] = defaultdict(set)
    unique_pool_members: defaultdict[str, set[str]] = defaultdict(set)
    theme_breakdown: Counter[str] = Counter()

    for item in items:
        question_id = item["question_id"]
        unique_distribution_members[item["current_status"]].add(question_id)
        unique_pool_members[item["governance_pool"]].add(question_id)
        for tag in item.get("theme_tags", []):
            theme_breakdown[tag] += 1

    old_summary = ledger_payload.get("summary", {})
    summary = dict(old_summary)
    summary.update(
        {
            "current_distribution": {status: current_distribution.get(status, 0) for status in ("A", "B", "C", "D")},
            "current_unique_distribution": {
                status: len(unique_distribution_members.get(status, set())) for status in ("A", "B", "C", "D")
            },
            "migration_breakdown": dict(migration_breakdown),
            "net_change_vs_baseline": {
                status: current_distribution.get(status, 0) - baseline_distribution.get(status, 0)
                for status in ("A", "B", "C", "D")
            },
            "pool_breakdown": {
                pool: pool_breakdown.get(pool, 0)
                for pool in (
                    "A-稳定增强池",
                    "B-候选收口池",
                    "B-长期澄清池",
                    "C-边界观察池",
                    "D-待业务/数据修订池",
                )
            },
            "pool_unique_breakdown": {
                pool: len(unique_pool_members.get(pool, set()))
                for pool in (
                    "A-稳定增强池",
                    "B-候选收口池",
                    "B-长期澄清池",
                    "C-边界观察池",
                    "D-待业务/数据修订池",
                )
            },
            "theme_breakdown": dict(theme_breakdown),
            "b2a_migration_review_impact": {
                "reviewed_candidates": 86,
                "migrated_to_a": 85,
                "kept_b_due_to_data_baseline": 1,
                "distribution_after_migration": {
                    status: current_distribution.get(status, 0) for status in ("A", "B", "C", "D")
                },
                "policy": "只有上一轮真实 data-qa 行为复核通过、且当前仍处于 B 的候选，才允许正式迁入 A。",
            },
            "recommended_next_pool": "A-稳定增强池 / B-长期澄清池",
            "recommended_next_pool_reason": (
                "B->A 迁移已把 85 条行为复核通过题写入 A；下一步应先跑新增 A 行为回归，"
                "再按 B2A-P1/P2/P3 分批建立精确断言，同时按 441 条 B 缺口路线推进 query_key、数据口径、业务定义能力建设。"
            ),
        }
    )
    return summary


def _apply_b2a_to_ledger(
    *,
    ledger_payload: dict[str, Any],
    candidates: list[dict[str, Any]],
    apply: bool,
) -> dict[str, Any]:
    """把 85 条 B->A 候选迁入总账 A 类。

    参数：
        ledger_payload: 当前 903 总账。
        candidates: 已通过行为复核的迁移候选。
        apply: 是否实际更新 ledger_payload。

    返回：
        迁移统计与逐题记录。
    """

    ledger_index = {(item["question_id"], item["question"]): item for item in ledger_payload["items"]}
    records: list[dict[str, Any]] = []
    for candidate in candidates:
        key = (candidate["question_id"], candidate["question"])
        ledger_item = ledger_index[key]
        before_status = ledger_item["current_status"]
        before_pool = ledger_item["governance_pool"]
        if apply:
            ledger_item["current_status"] = "A"
            ledger_item["current_query_key"] = candidate["query_key"]
            ledger_item["in_behavior_regression"] = True
            ledger_item["in_precise_assertion"] = False
            ledger_item["current_blocker_reason"] = "B->A 迁移复核已通过，当前已进入 A；尚未纳入更严格精确断言。"
            ledger_item["next_action"] = "纳入新增 A 行为回归固定集，并按 B2A-P1/P2/P3 建立更严格精确断言。"
            ledger_item["governance_pool"] = "A-稳定增强池"
            ledger_item["remarks"] = _append_remark(
                ledger_item.get("remarks", ""),
                "B->A 迁移复核通过并正式迁入 A。",
            )
        records.append(
            {
                "question_id": candidate["question_id"],
                "question": candidate["question"],
                "source_group": candidate["source_group"],
                "family": candidate["family"],
                "query_key": candidate["query_key"],
                "before_status": before_status,
                "after_status": "A" if apply else before_status,
                "before_pool": before_pool,
                "after_pool": "A-稳定增强池" if apply else before_pool,
                "applied": apply,
            }
        )
    return {
        "applied": apply,
        "migrated_count": len(records) if apply else 0,
        "candidate_count": len(records),
        "records": records,
    }


def _build_a_regression_set(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """生成 85 条新增 A 行为回归题集。"""

    items = [
        B2ARegressionQuestion(
            question_id=item["question_id"],
            question=item["question"],
            source_group=item["source_group"],
            family=item["family"],
            expected_query_key=item["query_key"],
            expected_status_code="OK",
            migration_basis=item["migration_basis"],
        )
        for item in candidates
    ]
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": str(B2A_CANDIDATES_PATH),
        "regression_rule": "真实调用 data-qa 主链路，要求 query_key 命中预期、状态 OK、supported=true、非澄清、非拒答且结果非空。",
        "summary": {
            "total_questions": len(items),
            "query_key_breakdown": dict(Counter(item.expected_query_key for item in items)),
            "family_breakdown": dict(Counter(item.family for item in items)),
        },
        "items": [asdict(item) for item in items],
    }
    _write_json(B2A_A_REGRESSION_SET_PATH, payload)
    return payload


def _build_precise_plan(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """生成 85 条新增 A 分批精确断言补强计划。"""

    sorted_candidates = sorted(
        candidates,
        key=lambda item: (
            _query_key_rank(item["query_key"]),
            item["family"],
            item["source_group"],
            item["question_id"],
            item["question"],
        ),
    )
    plan_items: list[B2APrecisePlanItem] = []
    for index, item in enumerate(sorted_candidates):
        batch_id, batch_name, batch_order = _resolve_precise_batch(index)
        plan_items.append(
            B2APrecisePlanItem(
                plan_id=f"B2A-PREC-{index + 1:03d}",
                batch_id=batch_id,
                batch_name=batch_name,
                batch_order=batch_order,
                question_id=item["question_id"],
                question=item["question"],
                source_group=item["source_group"],
                family=item["family"],
                query_key=item["query_key"],
                standard_answer_source="当前 logistics_ai 数据快照；由正式 data-qa 主链路执行并固化响应快照。",
                assertion_scope="status.code + query_plan.query_key + answer_summary + result_table.columns + result_table.rows 精确快照断言",
                assertion_fields=[
                    "status.code",
                    "query_plan.query_key",
                    "answer_summary",
                    "result_table.columns",
                    "result_table.rows",
                ],
                failure_classification_rule="query_key/status/columns 变化归为代码问题；answer_summary/rows 变化归为数据基线变化。",
                selection_reason="B->A 迁移复核通过并进入 A，尚未纳入更严格精确断言。",
            )
        )
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": str(B2A_CANDIDATES_PATH),
        "summary": {
            "total_questions": len(plan_items),
            "batch_summary": [
                {
                    "batch_id": batch_id,
                    "batch_name": batch_name,
                    "batch_order": order,
                    "question_count": sum(1 for item in plan_items if item.batch_id == batch_id),
                }
                for order, (batch_id, batch_name, _size) in enumerate(B2A_PRECISE_BATCHES, start=1)
            ],
            "query_key_breakdown": dict(Counter(item.query_key for item in plan_items)),
            "family_breakdown": dict(Counter(item.family for item in plan_items)),
        },
        "items": [asdict(item) for item in plan_items],
    }
    _write_json(B2A_PRECISE_PLAN_PATH, payload)
    return payload


def _gap_capability_definition(gap_type: str, family: str, category: str) -> tuple[str, str, str, str]:
    """把 B 缺口转成能力建设动作。

    返回：
        required_capability、build_action、acceptance_rule、owner_type。
    """

    if gap_type == "query_key_gap":
        return (
            "受控 query_key 参数化 / 复用能力",
            f"围绕 `{family}` 的 `{category}` 建立可复用 query_key 或参数化解析，不写死单题。",
            "对应题族样本在语义回归中不再进入通用澄清，且 A 行为回归 query_key 稳定命中。",
            "data-qa 工程侧",
        )
    if gap_type == "data_scope_gap":
        return (
            "数据字段与统计口径确认能力",
            f"先由数据 owner 确认 `{family}` 的 `{category}` 字段来源、空值处理、过滤范围和数据可用性。",
            "数据 owner 给出口径后，题目要么进入 A 候选收口，要么稳定保留业务化澄清。",
            "数据 owner / 业务 owner",
        )
    return (
        "业务定义与澄清模板能力",
        f"固化 `{family}` 的 `{category}` 业务定义、异常阈值、排名口径或比较标准。",
        "未补定义前稳定返回业务化澄清；补定义后再进入 A 候选复核，不允许直接猜测。",
        "业务 owner / 规则策略侧",
    )


def _roadmap_priority(count: int, gap_type: str, category: str) -> str:
    """按题量和缺口类型生成建设优先级。"""

    if count >= 50:
        return "P1"
    if gap_type == "query_key_gap" and count >= 20:
        return "P1"
    if category in {"mapping_consistency_scope", "data_consistency_scope", "route_or_address_scope"}:
        return "P1"
    if count >= 10:
        return "P2"
    return "P3"


def _next_wave(priority: str, gap_type: str) -> str:
    """生成后续推进波次建议。"""

    if priority == "P1" and gap_type == "query_key_gap":
        return "B-gap Wave1：优先补可参数化 query_key"
    if priority == "P1":
        return "B-gap Wave2：优先补数据/业务口径确认"
    if priority == "P2":
        return "B-gap Wave3：中频题族能力补齐"
    return "B-gap Observe：低频尾项观察"


def _build_gap_capability_roadmap(gap_records: list[dict[str, Any]]) -> dict[str, Any]:
    """把 441 条 B 缺口矩阵转成后续能力建设路线。"""

    grouped: defaultdict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in gap_records:
        grouped[(item["primary_gap_type"], item.get("family") or "未分类", item.get("category") or "未分类")].append(item)

    capability_items: list[GapCapabilityItem] = []
    for index, ((gap_type, family, category), records) in enumerate(
        sorted(grouped.items(), key=lambda pair: (-len(pair[1]), pair[0][0], pair[0][1], pair[0][2])),
        start=1,
    ):
        required_capability, build_action, acceptance_rule, owner_type = _gap_capability_definition(
            gap_type, family, category
        )
        priority = _roadmap_priority(len(records), gap_type, category)
        capability_items.append(
            GapCapabilityItem(
                capability_id=f"B-GAP-{index:03d}",
                gap_type=gap_type,
                family=family,
                category=category,
                priority=priority,
                question_count=len(records),
                representative_questions=[record["question"] for record in records[:5]],
                required_capability=required_capability,
                build_action=build_action,
                acceptance_rule=acceptance_rule,
                owner_type=owner_type,
                next_wave=_next_wave(priority, gap_type),
            )
        )

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": str(B2A_REVIEW_REPORT_PATH),
        "summary": {
            "total_questions": len(gap_records),
            "capability_item_count": len(capability_items),
            "gap_type_breakdown": dict(Counter(item["primary_gap_type"] for item in gap_records)),
            "family_breakdown": dict(Counter(item.get("family") or "未分类" for item in gap_records)),
            "priority_breakdown": dict(Counter(item.priority for item in capability_items)),
            "next_wave_breakdown": dict(Counter(item.next_wave for item in capability_items)),
        },
        "items": [asdict(item) for item in capability_items],
    }
    _write_json(GAP_ROADMAP_JSON_PATH, payload)
    return payload


def _render_migration_doc(
    *,
    report: dict[str, Any],
    regression_set: dict[str, Any],
    precise_plan: dict[str, Any],
) -> str:
    """渲染 B->A 迁移更新说明文档。"""

    summary = report["summary"]
    lines = [
        "# 903 B->A 迁移更新与新增 A 回归计划",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 一、结论",
        "",
        f"- 本轮基于 86 条 B->A 直接候选复核结果，正式迁入 A：`{summary['migrated_to_a']}` 条。",
        f"- 保持 B：`{summary['kept_b_due_to_data_baseline']}` 条，原因是数据基线阻塞。",
        f"- 迁移后 903 总账分布：`{summary['ledger_distribution_after']}`。",
        f"- 新增 A 行为回归题集：`{regression_set['summary']['total_questions']}` 条。",
        f"- 新增 A 精确断言计划：`{precise_plan['summary']['total_questions']}` 条，分 3 批推进。",
        "",
        "## 二、迁移原则",
        "",
        "- 只迁移上一轮真实 data-qa 主链路行为复核通过的题。",
        "- 原题必须当前仍在 B，且 query_key 与复核记录一致。",
        "- 补槽后可答但原题仍缺口径的题不迁入 A。",
        "- 数据基线阻塞题不迁入 A。",
        "",
        "## 三、query_key 分布",
        "",
    ]
    for key, value in summary["migrated_query_key_breakdown"].items():
        lines.append(f"- `{key}`：`{value}`")
    lines.extend(["", "## 四、精确断言批次", ""])
    for batch in precise_plan["summary"]["batch_summary"]:
        lines.append(f"- `{batch['batch_id']}`：{batch['batch_name']}，`{batch['question_count']}` 条")
    lines.extend(["", "## 五、代表迁移题", "", "| 题号 | query_key | 问题 |", "| --- | --- | --- |"])
    for item in report["migration_records"][:15]:
        lines.append(f"| {item['question_id']} | {item['query_key']} | {item['question']} |")
    lines.extend(
        [
            "",
            "## 六、已完成验证与下一步",
            "",
            "- 85 条新增 A 行为回归题集已生成；执行 `scripts/logistics_903_b2a_a_regression.py` 后用于确认迁移固定保护。",
            "- 先执行 `B2A-P1` 精确断言，随后推进 `B2A-P2` / `B2A-P3`。",
            "- 结合 441 条 B 缺口路线图，优先补 P1 query_key_gap 题族。",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_gap_roadmap_doc(payload: dict[str, Any]) -> str:
    """渲染 B 缺口能力建设路线文档。"""

    summary = payload["summary"]
    lines = [
        "# 441 条 B 缺口能力建设路线图",
        "",
        f"生成时间：{payload['generated_at']}",
        "",
        "## 一、结论",
        "",
        f"- 仍需澄清 B 题：`{summary['total_questions']}` 条。",
        f"- 能力建设项：`{summary['capability_item_count']}` 个。",
        f"- 缺口类型分布：`{summary['gap_type_breakdown']}`。",
        f"- 建议波次分布：`{summary['next_wave_breakdown']}`。",
        "",
        "## 二、路线原则",
        "",
        "- `query_key_gap`：优先补受控 query_key 或参数化能力，成熟后再进入 B->A 复核。",
        "- `data_scope_gap`：先补字段来源、数据可用性、过滤范围和空值口径，不用规则硬猜。",
        "- `business_definition_gap`：先补异常、排名、对比、风险等业务定义，未补定义前稳定澄清。",
        "",
        "## 三、P1 能力建设项",
        "",
        "| capability_id | 缺口类型 | 题族 | 类别 | 数量 | 建设动作 |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for item in payload["items"]:
        if item["priority"] != "P1":
            continue
        lines.append(
            f"| {item['capability_id']} | {item['gap_type']} | {item['family']} | {item['category']} | "
            f"{item['question_count']} | {item['build_action']} |"
        )
    lines.extend(["", "## 四、代表样例", ""])
    for item in payload["items"][:12]:
        lines.append(f"### {item['capability_id']}：{item['family']} / {item['category']}")
        lines.append("")
        lines.append(f"- 缺口类型：`{item['gap_type']}`")
        lines.append(f"- 建设动作：{item['build_action']}")
        lines.append(f"- 验收规则：{item['acceptance_rule']}")
        for question in item["representative_questions"][:3]:
            lines.append(f"- 样例：{question}")
        lines.append("")
    lines.extend(
        [
            "## 五、下一步",
            "",
            "- 先推进 `B-gap Wave1` 中 P1 query_key_gap，目标是批量吃掉线路/城市、综合统计、系统状态等可参数化题族。",
            "- 同步把 `data_scope_gap` 和 `business_definition_gap` 交给数据/业务 owner 明确口径，避免误答。",
            "- 每个能力项完成后必须回到 903 语义回归和 B->A 迁移复核，不允许直接手工改 A。",
        ]
    )
    return "\n".join(lines) + "\n"


def build_and_optionally_apply(*, apply: bool) -> dict[str, Any]:
    """构建迁移更新、回归题集、精确计划和缺口路线图。

    参数：
        apply: 是否把 85 条正式写入总账 A。

    返回：
        迁移报告摘要。
    """

    ledger_payload = _load_json(MASTER_LEDGER_PATH)
    candidates_payload = _load_json(B2A_CANDIDATES_PATH)
    review_payload = _load_json(B2A_REVIEW_REPORT_PATH)
    candidates = candidates_payload["items"]
    review_records = review_payload["migration_review_records"]
    validation_errors = _validate_candidates(
        candidates=candidates,
        review_records=review_records,
        ledger_items=ledger_payload["items"],
    )
    if validation_errors:
        raise RuntimeError("B->A 迁移前置校验失败：\n" + "\n".join(validation_errors))

    before_distribution = ledger_payload["summary"]["current_distribution"]
    migration_result = _apply_b2a_to_ledger(ledger_payload=ledger_payload, candidates=candidates, apply=apply)
    if apply:
        ledger_payload["generated_at"] = datetime.now().isoformat(timespec="seconds")
        ledger_payload["summary"] = _recompute_ledger_summary(ledger_payload)
        _write_json(MASTER_LEDGER_PATH, ledger_payload)
    after_distribution = ledger_payload["summary"]["current_distribution"]

    regression_set = _build_a_regression_set(candidates)
    precise_plan = _build_precise_plan(candidates)
    gap_roadmap = _build_gap_capability_roadmap(review_payload["gap_matrix_records"])

    failed_records = [
        item
        for item in review_records
        if item.get("migration_decision") == "keep_b_until_fixed"
    ]
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "applied": apply,
        "sources": {
            "master_ledger": str(MASTER_LEDGER_PATH),
            "b2a_candidates": str(B2A_CANDIDATES_PATH),
            "b2a_review_report": str(B2A_REVIEW_REPORT_PATH),
        },
        "outputs": {
            "a_regression_set": str(B2A_A_REGRESSION_SET_PATH),
            "precise_plan": str(B2A_PRECISE_PLAN_PATH),
            "gap_roadmap_json": str(GAP_ROADMAP_JSON_PATH),
            "migration_doc": str(MIGRATION_DOC_PATH),
            "gap_roadmap_doc": str(GAP_ROADMAP_DOC_PATH),
        },
        "summary": {
            "candidate_count": len(candidates),
            "migrated_to_a": migration_result["migrated_count"],
            "kept_b_due_to_data_baseline": len(failed_records),
            "ledger_distribution_before": before_distribution,
            "ledger_distribution_after": after_distribution,
            "migrated_query_key_breakdown": dict(Counter(item["query_key"] for item in candidates)),
            "migrated_family_breakdown": dict(Counter(item["family"] for item in candidates)),
            "a_regression_set_total": regression_set["summary"]["total_questions"],
            "precise_plan_total": precise_plan["summary"]["total_questions"],
            "gap_roadmap_total_questions": gap_roadmap["summary"]["total_questions"],
            "gap_capability_item_count": gap_roadmap["summary"]["capability_item_count"],
        },
        "migration_records": migration_result["records"],
        "kept_b_records": failed_records,
    }
    _write_json(MIGRATION_REPORT_PATH, report)
    MIGRATION_DOC_PATH.write_text(
        _render_migration_doc(report=report, regression_set=regression_set, precise_plan=precise_plan),
        encoding="utf-8",
    )
    GAP_ROADMAP_DOC_PATH.write_text(_render_gap_roadmap_doc(gap_roadmap), encoding="utf-8")
    return report


def main() -> None:
    """命令行入口。

    默认 dry-run 只生成计划和报告；传入 --apply 才会正式更新 903 总账。
    """

    parser = argparse.ArgumentParser(description="903 B->A 迁移更新、A 回归题集与 B 缺口路线图生成")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="正式把 85 条 B->A 候选写入 903 总账；不传则只做 dry-run 计划生成。",
    )
    args = parser.parse_args()
    report = build_and_optionally_apply(apply=args.apply)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

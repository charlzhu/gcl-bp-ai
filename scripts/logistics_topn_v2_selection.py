from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATION_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_question_bank_classification.json"
TOP200_CONFIG_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_top200_questions.json"
TOP200_P12_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_top200_p1_p2_regression_report.json"
ROUND_REPORT_TEMPLATE = "tmp/logistics_question_bank/logistics_top200_b_factory_round{round_no}_report.json"
POC_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_llm_understanding_poc_report.json"
GUARDRAIL_AUDIT_PATH = PROJECT_ROOT / "data/logs/logistics_llm_guardrail_audit.jsonl"
KEY_A_PRECISE_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/question_bank_a_key_questions.json"
ROUND45_PRECISE_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_round45_new_a_precise_questions.json"
P1P2_PRECISE_BASELINE_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_top200_p1_p2_a_precise_baseline.json"

TOPN_V2_CONFIG_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_topn_v2_questions.json"
TOPN_V2_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_topn_v2_selection_report.json"
TOPN_V2_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_TOPN_V2_SELECTION.md"


@dataclass(frozen=True)
class SelectionPolicy:
    """TopN v2 滚动重选策略。

    说明：
        1. 当前不再继续机械拉 200 条，而是按剩余价值密度给出更小规模的滚动集合；
        2. TopN v2 目标不是再次发起大规模物流域攻坚，而是帮助判断下一阶段应继续留在物流域，
           还是转入下一业务主线准备；
        3. 配额按三类候选池拆开，避免清单被“未入精确断言的 A 题”或“高价值 C 题”单独吞没。
    """

    topn_size: int
    lane_quota: dict[str, int]
    source_weight: dict[str, int]
    lane_weight: dict[str, int]
    exact_match_audit_boost: int
    poc_evidence_boost: int


POLICY = SelectionPolicy(
    topn_size=80,
    lane_quota={
        "A-稳定增强": 40,
        "B-候选收口": 25,
        "C-边界观察": 15,
    },
    source_weight={
        "73": 40,
        "230": 30,
        "600": 20,
    },
    lane_weight={
        "A-稳定增强": 40,
        "B-候选收口": 34,
        "C-边界观察": 18,
    },
    exact_match_audit_boost=3,
    poc_evidence_boost=5,
)


def _contains_any(text: str, keywords: list[str]) -> bool:
    """判断文本中是否包含任一关键词。"""

    return any(keyword in text for keyword in keywords)


def _load_json(path: Path) -> Any:
    """读取 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8"))


def _derive_theme_tags(question: str) -> list[str]:
    """给问题打主题标签，用于统计和路线图解释。"""

    tags: list[str] = []
    if _contains_any(question, ["发运量", "运量", "MW", "总瓦数", "瓦数", "车次", "总车数", "车辆数"]):
        tags.append("运量/车次类")
    if _contains_any(question, ["运费", "费用", "总费用", "总运费", "元/瓦", "元瓦", "单瓦"]):
        tags.append("费用/成本类")
    if _contains_any(question, ["承运商", "物流公司", "物流供应商", "签收率"]):
        tags.append("承运商类")
    if _contains_any(question, ["客户", "项目", "项目地", "收货地址"]):
        tags.append("客户/项目类")
    if _contains_any(question, ["区域", "省", "城市", "基地"]):
        tags.append("区域/省份类")
    if _contains_any(question, ["排名", "前五", "前十", "后十", "最高", "最低"]):
        tags.append("排名类")
    if _contains_any(question, ["2026", "26年", "SIGNEDFOR", "任务", "填充率", "解析成功率"]):
        tags.append("2026系统类")
    if _contains_any(question, ["预测", "预计", "波动区间", "相关性", "离群点", "模型", "治理原则"]):
        tags.append("预测/诊断类")
    return sorted(set(tags)) or ["其他"]


def _derive_family(question: str) -> str:
    """把问题归并成便于后续决策的题族。"""

    if _contains_any(question, ["预测", "预计", "波动区间", "相关性", "离群点", "模型", "治理原则", "到达时间", "ETA", "在途"]):
        return "预测/诊断/开放讨论类"
    if _contains_any(question, ["客户", "项目", "项目地", "收货地址"]):
        return "客户/项目分析类"
    if _contains_any(question, ["承运商", "物流公司", "物流供应商", "签收率"]):
        return "承运商经营与排名类"
    if _contains_any(question, ["始发", "发往", "线路", "城市", "江苏", "广东", "安徽", "17.5", "13m", "运价", "单车均价"]):
        return "线路/城市运价类"
    if _contains_any(question, ["区域", "省", "基地"]) and _contains_any(question, ["发运量", "运量", "MW", "费用", "运费"]):
        return "区域/省份/基地汇总类"
    if _contains_any(question, ["状态", "任务", "填充率", "解析成功率", "mapping", "assign_detail", "supplier_price"]):
        return "2026系统状态与数据质量类"
    if _contains_any(question, ["经营计划", "辅料送样", "刘娟"]):
        return "特殊业务口径类"
    return "综合统计类"


def _derive_business_value_score(question: str) -> tuple[int, list[str]]:
    """计算业务价值分，并返回解释原因。"""

    score = 0
    reasons: list[str] = []
    if _contains_any(question, ["发运量", "运量", "MW", "总瓦数", "瓦数"]):
        score += 10
        reasons.append("涉及发运量/MW等核心经营指标")
    if _contains_any(question, ["运费", "费用", "总费用", "总运费", "元/瓦", "元瓦", "单瓦"]):
        score += 12
        reasons.append("涉及费用/单瓦成本等核心成本指标")
    if _contains_any(question, ["车次", "总车数", "车辆数"]):
        score += 10
        reasons.append("涉及车次/车辆数等高频运输指标")
    if _contains_any(question, ["承运商", "物流公司", "物流供应商", "签收率"]):
        score += 9
        reasons.append("可用于承运商经营评价和签收看数")
    if _contains_any(question, ["区域", "省", "城市", "基地"]):
        score += 8
        reasons.append("支持区域、省份、基地层面的管理看板")
    if _contains_any(question, ["客户", "项目", "项目地", "收货地址"]):
        score += 8
        reasons.append("与客户/项目经营分析直接相关")
    if _contains_any(question, ["排名", "前五", "前十", "后十", "最高", "最低"]):
        score += 8
        reasons.append("适合管理汇报中的排名与对比场景")
    if _contains_any(question, ["每月", "月度", "各月", "月份", "趋势", "对比"]):
        score += 7
        reasons.append("适合月度经营跟踪和趋势对比")
    if _contains_any(question, ["2026", "26年"]):
        score += 6
        reasons.append("覆盖 2026 正式系统经营看数")
    return score, reasons


def _derive_penalty_score(question: str) -> tuple[int, list[str]]:
    """对当前不适合优先投入的问题打惩罚分。"""

    score = 0
    reasons: list[str] = []
    if _contains_any(question, ["预测", "预计", "波动区间"]):
        score -= 10
        reasons.append("预测/趋势类当前不适合继续深挖")
    if _contains_any(question, ["ETA", "到达时间", "在途"]):
        score -= 10
        reasons.append("ETA/复杂时效推理类当前主链路不支持")
    if _contains_any(question, ["模型", "设计一个", "治理原则"]):
        score -= 10
        reasons.append("开放设计/模型类问题当前不适合投入")
    if _contains_any(question, ["相关性", "离群点", "显著"]) and _contains_any(question, ["如何", "为什么", "哪些"]):
        score -= 8
        reasons.append("诊断分析类问题仍需先锁定统计标准")
    return score, reasons


def _derive_blocker_reason(question: str, current_status: str, current_reason: str) -> str:
    """生成更业务化的阻塞说明。"""

    if current_status == "A":
        return "当前已进入 A 类，但尚未全部纳入更严格精确断言回归。"
    if current_status == "B":
        if not _contains_any(question, ["2023", "2024", "2025", "2026", "23年", "24年", "25年", "26年", "本月", "今年"]):
            return "缺少明确统计时间范围，仍需先澄清年份或月份。"
        if _contains_any(question, ["最近", "近期", "最差", "异常", "有没有问题", "哪些有问题"]):
            return "缺少评价标准或异常定义，当前仍需先澄清。"
        if _contains_any(question, ["分别是多少", "各省", "各城市", "各承运商", "各运输方式"]):
            return "缺少拆分维度或结果口径，当前仍需先澄清。"
        return current_reason or "当前仍缺少关键统计口径，暂不宜直接推进。"
    if _contains_any(question, ["预测", "预计", "波动区间"]):
        return "预测/趋势类问题，当前仍明确停在 C 类。"
    if _contains_any(question, ["ETA", "到达时间", "在途"]):
        return "ETA/时效推理类问题，当前仍明确停在 C 类。"
    if _contains_any(question, ["模型", "设计一个", "治理原则"]):
        return "开放讨论/模型设计类问题，当前仍明确停在 C 类。"
    return current_reason or "当前问题超出现有物流结构化查询边界。"


def _derive_next_phase_path(lane: str) -> str:
    """返回候选进入下一阶段后的建议路径。"""

    if lane == "A-稳定增强":
        return "A-继续精确断言增强"
    if lane == "B-候选收口":
        return "B-候选收口"
    return "C-边界保留"


def _load_classification_items() -> dict[str, dict[str, Any]]:
    """读取全量 903 题分层结果。"""

    payload = _load_json(CLASSIFICATION_PATH)
    return {item["question_id"]: item for item in payload["items"]}


def _load_precise_ids() -> set[str]:
    """读取已经进入更严格精确断言的题号。"""

    precise_ids: set[str] = set()
    for path in (KEY_A_PRECISE_PATH, ROUND45_PRECISE_PATH):
        for item in _load_json(path):
            question_id = item.get("question_id") or item.get("question_bank_id")
            if question_id:
                precise_ids.add(question_id)
    for item in _load_json(P1P2_PRECISE_BASELINE_PATH)["items"]:
        question_id = item.get("question_id") or item.get("question_bank_id")
        if question_id:
            precise_ids.add(question_id)
    return precise_ids


def _rebuild_current_top200_state() -> dict[str, dict[str, Any]]:
    """根据原始 Top200、P1/P2 收口和 Round1-5 结果还原当前 Top200 真正状态。"""

    top200_items = {
        item["question_id"]: dict(item)
        for item in _load_json(TOP200_CONFIG_PATH)["items"]
    }
    for item in top200_items.values():
        item["final_classification"] = item["current_classification"]
        item["final_reason"] = item.get("current_blocker_reason") or item.get("current_route") or ""
    p12_items = _load_json(TOP200_P12_REPORT_PATH)["b_closure_progress"]["items"]
    for record in p12_items:
        top200_items[record["question_id"]]["final_classification"] = {
            "promoted_to_a": "A",
            "remain_b": "B",
            "moved_to_c": "C",
        }[record["closure_result"]]
        top200_items[record["question_id"]]["final_reason"] = record["closure_reason"]
        if record.get("actual_query_key"):
            top200_items[record["question_id"]]["query_key"] = record["actual_query_key"]
    for round_no in range(1, 6):
        round_items = _load_json(PROJECT_ROOT / ROUND_REPORT_TEMPLATE.format(round_no=round_no))["items"]
        for record in round_items:
            top200_items[record["question_id"]]["final_classification"] = record["final_classification"]
            top200_items[record["question_id"]]["final_reason"] = record["closure_reason"]
            if record.get("actual_query_key"):
                top200_items[record["question_id"]]["query_key"] = record["actual_query_key"]
    return top200_items


def _load_runtime_evidence(
    classification_items: dict[str, dict[str, Any]],
    top200_items: dict[str, dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """读取 PoC 与审计日志，作为真实业务变体和失败样本证据。"""

    text_to_ids: defaultdict[str, list[str]] = defaultdict(list)
    for question_id, item in classification_items.items():
        text_to_ids[item["question"]].append(question_id)
    for question_id, item in top200_items.items():
        text_to_ids[item["question"]].append(question_id)

    evidence: dict[str, dict[str, int]] = defaultdict(lambda: {"poc_hits": 0, "audit_hits": 0})

    poc_report = _load_json(POC_REPORT_PATH)
    for bucket in ("a_items", "b_items", "c_items"):
        for record in poc_report.get(bucket, []):
            question_id = record.get("question_id") or record.get("acceptance_id")
            if question_id and question_id in classification_items:
                evidence[question_id]["poc_hits"] += 1

    if GUARDRAIL_AUDIT_PATH.exists():
        for line in GUARDRAIL_AUDIT_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            question = payload.get("question")
            if not question:
                continue
            for question_id in text_to_ids.get(question, []):
                evidence[question_id]["audit_hits"] += 1

    return evidence


def _build_candidate(
    question_id: str,
    item: dict[str, Any],
    lane: str,
    pool_source: str,
    runtime_evidence: dict[str, dict[str, int]],
) -> dict[str, Any]:
    """构建 TopN v2 候选记录。"""

    business_value_score, business_reasons = _derive_business_value_score(item["question"])
    penalty_score, penalty_reasons = _derive_penalty_score(item["question"])
    evidence = runtime_evidence.get(question_id, {"poc_hits": 0, "audit_hits": 0})
    source_score = POLICY.source_weight.get(item["source_group"], 15)
    lane_score = POLICY.lane_weight[lane]
    evidence_score = (
        evidence["poc_hits"] * POLICY.poc_evidence_boost
        + evidence["audit_hits"] * POLICY.exact_match_audit_boost
    )
    current_status = item["current_status"]
    calculability_score = {
        "A": 18,
        "B": 10,
        "C": 4,
    }[current_status]
    total_score = source_score + lane_score + business_value_score + calculability_score + evidence_score + penalty_score
    return {
        "question_id": question_id,
        "question": item["question"],
        "source_group": item["source_group"],
        "source_label": item["source_label"],
        "category_label": item["category_label"],
        "difficulty": item["difficulty"],
        "current_status": current_status,
        "recommended_status": current_status,
        "lane": lane,
        "pool_source": pool_source,
        "query_key": item.get("query_key"),
        "theme_tags": _derive_theme_tags(item["question"]),
        "family": _derive_family(item["question"]),
        "business_value_reasons": business_reasons,
        "business_value_score": business_value_score,
        "source_score": source_score,
        "lane_score": lane_score,
        "calculability_score": calculability_score,
        "runtime_evidence": evidence,
        "runtime_evidence_score": evidence_score,
        "penalty_reasons": penalty_reasons,
        "penalty_score": penalty_score,
        "total_score": total_score,
        "current_blocker_reason": _derive_blocker_reason(item["question"], current_status, item.get("current_reason", "")),
        "next_phase_path": _derive_next_phase_path(lane),
        "enter_next_phase": True,
    }


def _build_candidate_pool() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """构建 TopN v2 候选池。"""

    classification_payload = _load_json(CLASSIFICATION_PATH)
    classification_items = {item["question_id"]: item for item in classification_payload["items"]}
    top200_items = _rebuild_current_top200_state()
    precise_ids = _load_precise_ids()
    runtime_evidence = _load_runtime_evidence(classification_items, top200_items)
    raw_question_ids = [item["question_id"] for item in classification_payload["items"]]
    duplicate_counter = Counter(raw_question_ids)
    duplicate_question_ids = sorted(question_id for question_id, count in duplicate_counter.items() if count > 1)

    candidates: list[dict[str, Any]] = []
    for question_id, item in top200_items.items():
        current_status = item["final_classification"]
        merged_item = {
            **classification_items.get(question_id, {}),
            **item,
            "current_status": current_status,
            "current_reason": item.get("final_reason", ""),
        }
        if current_status == "A" and question_id not in precise_ids:
            candidates.append(
                _build_candidate(
                    question_id=question_id,
                    item=merged_item,
                    lane="A-稳定增强",
                    pool_source="current_top200_a_not_precise",
                    runtime_evidence=runtime_evidence,
                )
            )
        elif current_status == "C":
            candidates.append(
                _build_candidate(
                    question_id=question_id,
                    item=merged_item,
                    lane="C-边界观察",
                    pool_source="current_top200_c",
                    runtime_evidence=runtime_evidence,
                )
            )

    for question_id, item in classification_items.items():
        if question_id in top200_items:
            continue
        current_status = item["classification"]
        if current_status not in {"B", "C"}:
            continue
        lane = "B-候选收口" if current_status == "B" else "C-边界观察"
        merged_item = {
            **item,
            "current_status": current_status,
            "current_reason": item.get("reason", ""),
        }
        candidates.append(
            _build_candidate(
                question_id=question_id,
                item=merged_item,
                lane=lane,
                pool_source="remaining_903",
                runtime_evidence=runtime_evidence,
            )
        )

    pool_summary = {
        "raw_question_total": classification_payload["summary"]["total_questions"],
        "unique_question_id_total": len(classification_items),
        "duplicate_question_ids": duplicate_question_ids,
        "candidate_pool_total": len(candidates),
        "pool_source_breakdown": dict(Counter(item["pool_source"] for item in candidates)),
        "status_breakdown": dict(Counter(item["current_status"] for item in candidates)),
        "runtime_evidence_summary": {
            "poc_attached_question_count": sum(1 for item in candidates if item["runtime_evidence"]["poc_hits"] > 0),
            "audit_attached_question_count": sum(1 for item in candidates if item["runtime_evidence"]["audit_hits"] > 0),
            "poc_record_total": sum(item["runtime_evidence"]["poc_hits"] for item in candidates),
            "audit_exact_match_total": sum(item["runtime_evidence"]["audit_hits"] for item in candidates),
        },
        "precise_a_outside_pool_count": 0,
        "top200_current_distribution": dict(Counter(item["final_classification"] for item in top200_items.values())),
    }
    return candidates, pool_summary


def _select_topn_v2(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按配额选出 TopN v2。"""

    lane_ranked: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        lane_ranked[item["lane"]].append(item)
    for lane in lane_ranked:
        lane_ranked[lane].sort(key=lambda item: (-item["total_score"], item["question_id"]))

    selected: list[dict[str, Any]] = []
    for lane, quota in POLICY.lane_quota.items():
        selected.extend(lane_ranked[lane][:quota])

    selected.sort(key=lambda item: (-item["total_score"], item["question_id"]))
    for rank, item in enumerate(selected, start=1):
        item["rank"] = rank
        if rank <= 30:
            item["priority"] = "P1"
        elif rank <= 55:
            item["priority"] = "P2"
        else:
            item["priority"] = "P3"
    return selected


def _derive_recommendation(selected: list[dict[str, Any]], pool_summary: dict[str, Any]) -> dict[str, Any]:
    """基于 TopN v2 结果给出明确的阶段判断。"""

    lane_counter = Counter(item["lane"] for item in selected)
    family_counter = Counter(item["family"] for item in selected)
    b_family_counter = Counter(item["family"] for item in selected if item["lane"] == "B-候选收口")
    candidate_density = {
        "a_stability_count": lane_counter["A-稳定增强"],
        "b_opportunity_count": lane_counter["B-候选收口"],
        "c_watchlist_count": lane_counter["C-边界观察"],
    }
    continue_logistics = lane_counter["B-候选收口"] >= 20
    recommendation_text = (
        "建议把物流域转入“轻量持续维护 + Top80 v2 滚动观察”模式，同时开始准备经营分析域的数据盘点与口径梳理。"
        "原因是 Top200 高价值 B 题已经阶段性清零，当前剩余高价值集合中，A 类稳定性增强与 C 类边界观察占比更高，"
        "继续做下一轮 Top200 规模物流攻坚的价值密度已经明显下降。"
    )
    if continue_logistics:
        recommendation_text = (
            "建议物流域继续保留一个 Top80 v2 轻量收口清单，但不再做 Top200 级别攻坚；"
            "同时开始准备经营分析域的数据盘点与口径梳理。"
        )

    return {
        "recommended_topn_size": POLICY.topn_size,
        "lane_breakdown": candidate_density,
        "priority_breakdown": dict(Counter(item["priority"] for item in selected)),
        "family_breakdown": dict(family_counter),
        "b_lane_family_breakdown": dict(b_family_counter),
        "top_families_to_continue": [
            family
            for family, _ in b_family_counter.most_common(5)
        ],
        "decision": {
            "continue_logistics_domain": continue_logistics,
            "prepare_next_business_domain": True,
            "explicit_recommendation": recommendation_text,
            "why_not_next_top200": [
                "Top200 高价值 B 题已经阶段性清零，继续按 Top200 规模推进会摊薄投入价值。",
                "剩余候选中 A 类稳定性增强占比高，说明后续重点更偏“补稳”而不是“大批量扩能力”。",
                "剩余 C 类仍有明确边界，不适合为了继续留在物流域而强行扩能力。",
            ],
            "next_if_stay_in_logistics": "若继续留在物流域，只建议围绕 Top80 v2 的 P1/P2 做轻量收尾，不建议再发起新一轮 Top200 工程。",
            "next_if_prepare_new_domain": "建议下一阶段进入经营分析域前置准备：先做数据盘点、口径梳理和高价值问题清单，而不是直接写代码。",
        },
        "pool_summary": pool_summary,
    }


def _write_markdown(
    selected: list[dict[str, Any]],
    report: dict[str, Any],
) -> None:
    """写出 TopN v2 路线图文档。"""

    lane_breakdown = report["selection_summary"]["lane_breakdown"]
    priority_breakdown = report["selection_summary"]["priority_breakdown"]
    family_breakdown = report["selection_summary"]["family_breakdown"]
    b_lane_family_breakdown = report["selection_summary"]["b_lane_family_breakdown"]
    recommendation = report["recommendation"]["decision"]

    p1_examples = [item for item in selected if item["priority"] == "P1"][:12]
    p2_examples = [item for item in selected if item["priority"] == "P2"][:12]
    p3_examples = [item for item in selected if item["priority"] == "P3"][:12]

    lines = [
        "# 物流域 TopN v2 滚动重选方案",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 为什么现在做 TopN v2，而不是继续再拉一轮 Top200",
        "",
        "- Top200 高价值 B 题已经阶段性清零，继续按 Top200 规模推进会明显摊薄投入价值。",
        "- 当前剩余高价值集合里，A 类稳定性增强和 C 类边界观察占比更高，说明物流域当前更适合进入“收尾 + 稳定性增强”阶段。",
        "- 因此本轮不再机械拉 200 条，而是重新定义“下一批最值得继续做的问题”，用于判断后续是继续留在物流域，还是准备切下一业务域。",
        "",
        "## 候选池定义",
        "",
        f"- 原始题库总量：{report['candidate_pool']['raw_question_total']} 条",
        f"- 去重后的唯一题号总量：{report['candidate_pool']['unique_question_id_total']} 条",
        f"- 存在重复题号的条目：{report['candidate_pool']['duplicate_question_ids']}",
        f"- 候选池总量：{report['candidate_pool']['candidate_pool_total']}",
        f"- 候选池来源分布：{report['candidate_pool']['pool_source_breakdown']}",
        f"- 候选池当前状态分布：{report['candidate_pool']['status_breakdown']}",
        "- 候选池组成：",
        "  - 未进入当前 Top200 的剩余题",
        "  - 当前 Top200 中仍停在 C 的题",
        "  - 当前 Top200 中已进入 A 但尚未纳入更严格精确断言的题",
        "  - LLM PoC / Guardrail / 查询审计中的真实变体与失败样本证据（作为加权证据，不单独起平行题库）",
        "",
        "## 筛选原则",
        "",
        "- 业务真实频率：优先保留真实业务补充问法、真实失败样本覆盖过的题。",
        "- 管理价值：优先保留发运量、运费、车次、承运商经营、区域/客户/项目分析、排名对比题。",
        "- 数据可算性：优先保留当前口径可锁、可进入 A 或可做更严格精确断言的题。",
        "- 推进成本：避免再次把大量预测、ETA、开放讨论题拉进主攻清单。",
        "- 当前边界归属：把候选明确分成 A-稳定增强、B-候选收口、C-边界观察三条路径。",
        "",
        "## 建议的 TopN v2 规模",
        "",
        f"- 建议规模：Top{report['recommendation']['recommended_topn_size']} v2",
        f"- A/B/C（按下一阶段路径）分布：{lane_breakdown}",
        f"- P1/P2/P3 分布：{priority_breakdown}",
        "",
        "## 最值得继续推进的题族",
        "",
    ]
    for family, count in sorted(b_lane_family_breakdown.items(), key=lambda pair: (-pair[1], pair[0]))[:8]:
        lines.append(f"- {family}：{count} 条")

    lines.extend(
        [
            "",
            "## 方案判断",
            "",
            f"- 是否继续留在物流域：{'是，但仅建议轻量持续维护' if recommendation['continue_logistics_domain'] else '不建议继续做 Top200 级别深挖'}",
            f"- 是否应开始准备下一业务域：{'是' if recommendation['prepare_next_business_domain'] else '否'}",
            f"- 明确建议：{recommendation['explicit_recommendation']}",
            "",
            "### 为什么当前不建议再做一轮 Top200",
        ]
    )
    for reason in recommendation["why_not_next_top200"]:
        lines.append(f"- {reason}")

    lines.extend(
        [
            "",
            "## TopN v2 示例清单",
            "",
            "### P1 示例",
        ]
    )
    for item in p1_examples:
        lines.append(
            f"- {item['question_id']} | {item['lane']} | {item['family']} | {item['question']}"
        )
    lines.extend(["", "### P2 示例"])
    for item in p2_examples:
        lines.append(
            f"- {item['question_id']} | {item['lane']} | {item['family']} | {item['question']}"
        )
    lines.extend(["", "### P3 示例"])
    for item in p3_examples:
        lines.append(
            f"- {item['question_id']} | {item['lane']} | {item['family']} | {item['question']}"
        )

    lines.extend(
        [
            "",
            "## 当前结论",
            "",
            "- 物流域并不是完全没有后续价值，但剩余价值密度已经明显低于 Top200 阶段。",
            "- 更合理的动作是：保留一个 Top80 v2 作为物流域滚动维护与稳定性增强清单，同时开始准备经营分析域的数据盘点与口径梳理。",
        ]
    )

    TOPN_V2_DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """生成 TopN v2 配置、报告和文档。"""

    candidates, pool_summary = _build_candidate_pool()
    selected = _select_topn_v2(candidates)
    recommendation = _derive_recommendation(selected, pool_summary)

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_pool": pool_summary,
        "selection_policy": {
            "topn_size": POLICY.topn_size,
            "lane_quota": POLICY.lane_quota,
            "source_weight": POLICY.source_weight,
            "lane_weight": POLICY.lane_weight,
            "exact_match_audit_boost": POLICY.exact_match_audit_boost,
            "poc_evidence_boost": POLICY.poc_evidence_boost,
        },
        "selection_summary": {
            "selected_total": len(selected),
            "lane_breakdown": dict(Counter(item["lane"] for item in selected)),
            "priority_breakdown": dict(Counter(item["priority"] for item in selected)),
            "family_breakdown": dict(Counter(item["family"] for item in selected)),
            "b_lane_family_breakdown": dict(Counter(item["family"] for item in selected if item["lane"] == "B-候选收口")),
        },
        "recommendation": recommendation,
        "items": selected,
    }

    TOPN_V2_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOPN_V2_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOPN_V2_CONFIG_PATH.write_text(
        json.dumps(
            {
                "generated_at": report["generated_at"],
                "recommended_topn_size": POLICY.topn_size,
                "items": selected,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    TOPN_V2_REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_markdown(selected, report)

    print(
        json.dumps(
            {
                "candidate_pool_total": report["candidate_pool"]["candidate_pool_total"],
                "selected_total": report["selection_summary"]["selected_total"],
                "lane_breakdown": report["selection_summary"]["lane_breakdown"],
                "priority_breakdown": report["selection_summary"]["priority_breakdown"],
                "decision": report["recommendation"]["decision"]["explicit_recommendation"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

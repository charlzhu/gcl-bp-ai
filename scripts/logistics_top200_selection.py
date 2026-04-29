from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATION_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_question_bank_classification.json"
TOP200_CONFIG_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_top200_questions.json"
TOP200_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_top200_selection_report.json"


@dataclass(frozen=True)
class SelectionRule:
    """Top200 筛选规则说明。

    说明：
        1. 这里不只记录打分项，也记录分类配额，保证结果可解释；
        2. 规则优先服务“高频高价值先收口”，不是为了把 903 条平均推进；
        3. 后续若要复盘 Top200 变化，只需要重跑脚本并对比规则和输入分类文件。
    """

    source_weight: dict[str, int]
    classification_weight: dict[str, int]
    closure_weight: dict[str, int]
    class_quota: dict[str, int]


RULE = SelectionRule(
    source_weight={
        "73": 40,
        "230": 30,
        "600": 20,
    },
    classification_weight={
        "A": 34,
        "B": 20,
        "C": 8,
    },
    closure_weight={
        "A": 18,
        "B": 10,
        "C": 2,
    },
    class_quota={
        "A": 75,
        "B": 100,
        "C": 25,
    },
)


def _load_items(path: Path) -> list[dict[str, Any]]:
    """读取题库分层结果。

    参数：
        path: 题库分类 JSON 路径。

    返回：
        list[dict[str, Any]]: 分类后的题目列表。
    """

    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("items", [])


def _contains_any(text: str, keywords: list[str]) -> bool:
    """判断问题中是否包含任一关键词。"""

    return any(keyword in text for keyword in keywords)


def _derive_theme_tags(question: str) -> list[str]:
    """给题目打主题标签，便于后续按批次收口。

    说明：
        1. 标签是多选，不强求互斥；
        2. 当前标签集只服务 Top200 路线图，不改变现有 query_key 或返回结构。
    """

    tags: list[str] = []
    if _contains_any(question, ["发运量", "运量", "MW", "总瓦数", "瓦数", "运费", "费用", "总费用", "总运费", "元/瓦", "元瓦", "单瓦", "车次", "多少车", "总车数", "车辆数"]):
        tags.append("指标类")
    if _contains_any(question, ["排名", "前五", "前十", "后十", "最高", "最低"]):
        tags.append("排名类")
    if _contains_any(question, ["每月", "月度", "各月", "月份", "趋势", "对比"]):
        tags.append("月度趋势类")
    if _contains_any(question, ["承运商", "物流公司", "物流供应商", "签收率"]):
        tags.append("承运商类")
    if _contains_any(question, ["客户", "项目", "项目地", "收货地址"]):
        tags.append("客户类")
    if _contains_any(question, ["运输方式", "公路", "铁路", "水运", "海运"]):
        tags.append("运输方式类")
    if _contains_any(question, ["区域", "省", "城市", "基地"]):
        tags.append("区域/省份类")
    if _contains_any(question, ["2026", "26年", "26月"]):
        tags.append("2026系统类")
    if _contains_any(question, ["经营计划", "辅料送样", "刘娟"]):
        tags.append("特殊业务口径类")
    return sorted(set(tags)) or ["其他"]


def _derive_business_value_score(question: str) -> tuple[int, list[str]]:
    """计算业务价值分，并返回可解释原因。"""

    score = 0
    reasons: list[str] = []
    if _contains_any(question, ["发运量", "运量", "MW", "总瓦数", "瓦数"]):
        score += 10
        reasons.append("涉及发运量/MW等核心经营指标")
    if _contains_any(question, ["运费", "费用", "总费用", "总运费", "元/瓦", "元瓦", "单瓦"]):
        score += 12
        reasons.append("涉及费用/单瓦成本等核心成本指标")
    if _contains_any(question, ["车次", "多少车", "总车数", "车辆数"]):
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
    if _contains_any(question, ["2026", "26年", "26月"]):
        score += 6
        reasons.append("覆盖 2026 正式系统经营看数")
    if _contains_any(question, ["经营计划", "辅料送样", "刘娟"]):
        score += 6
        reasons.append("涉及已锁定的特殊业务口径")
    return score, reasons


def _derive_penalty(question: str) -> tuple[int, list[str]]:
    """给当前难以快速收口的题目加惩罚分。"""

    score = 0
    reasons: list[str] = []
    if _contains_any(question, ["预测", "预计", "波动区间"]):
        score -= 8
        reasons.append("预测/趋势类当前不适合优先收口")
    if _contains_any(question, ["ETA", "到达时间", "在途"]):
        score -= 8
        reasons.append("ETA/时效推理类当前主链路不支持")
    if _contains_any(question, ["模型", "设计一个", "治理原则"]):
        score -= 8
        reasons.append("开放设计/模型类问题不宜优先投入")
    if _contains_any(question, ["原因", "明细", "项目"]) and "额外费用" in question:
        score -= 8
        reasons.append("额外费用原因/明细类当前仍停在不支持")
    return score, reasons


def _derive_blocker_reason(item: dict[str, Any]) -> str:
    """为非 A 类题目生成更清楚的阻塞原因。"""

    question = item["question"]
    if item["classification"] == "A":
        return ""
    if item["classification"] == "B":
        if _contains_any(question, ["最近", "近期", "最差", "异常", "有没有问题", "哪些有问题"]):
            return "缺少时间范围、评价标准或异常定义，当前应先澄清后再执行。"
        if _contains_any(question, ["分别是多少", "各省", "各城市", "各承运商", "各运输方式"]):
            return "缺少拆分维度或结果指标口径，当前应先澄清再执行。"
        if not _contains_any(question, ["2023", "2024", "2025", "2026", "23年", "24年", "25年", "26年", "本月", "今年"]):
            return "缺少明确统计时间范围，当前应先澄清年份或月份。"
        return "当前问题仍缺少关键统计口径，需先进入澄清路径。"
    if _contains_any(question, ["预测", "预计", "波动区间"]):
        return "预测/趋势类问题，当前主链路明确不支持。"
    if _contains_any(question, ["ETA", "到达时间", "在途"]):
        return "ETA/复杂时效推理类问题，当前主链路明确不支持。"
    if _contains_any(question, ["模型", "设计一个", "治理原则"]):
        return "开放讨论/模型设计类问题，当前主链路明确不支持。"
    if "额外费用" in question and _contains_any(question, ["原因", "明细", "项目"]):
        return "额外费用原因/明细类问题，当前主链路明确不支持。"
    return item.get("reason", "当前问题超出物流数据问答一期支持边界。")


def _derive_next_action(item: dict[str, Any], priority: str) -> str:
    """给出题目当前最合理的收口动作。"""

    classification = item["classification"]
    if classification == "A":
        return "保持 A 类稳定支持，并纳入持续回归监控。"
    if classification == "B":
        if priority in {"P1", "P2"}:
            return "优先细化澄清模板，条件成熟时评估是否扩成 A 类 query_key。"
        return "先保持澄清路径，待高频模板和字段口径进一步收口后再推进。"
    return "继续保持 C 类不支持，明确边界即可，不建议本阶段投入扩展。"


def _derive_route_label(item: dict[str, Any]) -> str:
    """生成当前建议路径标签。"""

    classification = item["classification"]
    if classification == "A":
        return "A-稳定支持"
    if classification == "B":
        return "B-先澄清"
    return "C-明确不支持"


def _build_item(item: dict[str, Any], rank: int) -> dict[str, Any]:
    """构建 Top200 单条结果。"""

    business_value_score, business_reasons = _derive_business_value_score(item["question"])
    penalty_score, penalty_reasons = _derive_penalty(item["question"])
    frequency_score = RULE.source_weight[item["source_group"]]
    calculability_score = RULE.classification_weight[item["classification"]] + (6 if item.get("query_key") else 0)
    closure_cost_score = RULE.closure_weight[item["classification"]]
    total_score = frequency_score + business_value_score + calculability_score + closure_cost_score + penalty_score
    priority = "P1" if rank <= 50 else "P2" if rank <= 100 else "P3"
    stable_supported = item["classification"] == "A" and bool(item.get("query_key"))
    recommended_priority_closure = item["classification"] in {"A", "B"} and priority in {"P1", "P2"}

    return {
        "rank": rank,
        "priority": priority,
        "question_id": item["question_id"],
        "question": item["question"],
        "source_group": item["source_group"],
        "source_label": item["source_label"],
        "category_label": item["category_label"],
        "difficulty": item["difficulty"],
        "current_classification": item["classification"],
        "current_route": _derive_route_label(item),
        "query_key": item.get("query_key"),
        "stable_supported": stable_supported,
        "recommended_priority_closure": recommended_priority_closure,
        "suggested_next_action": _derive_next_action(item, priority),
        "business_value_reason": "；".join(business_reasons) if business_reasons else "当前管理价值相对一般。",
        "blocking_reason": _derive_blocker_reason(item),
        "ability_boundary": item.get("ability_boundary", ""),
        "theme_tags": _derive_theme_tags(item["question"]),
        "selection_score": {
            "total": total_score,
            "frequency_score": frequency_score,
            "business_value_score": business_value_score,
            "calculability_score": calculability_score,
            "closure_cost_score": closure_cost_score,
            "penalty_score": penalty_score,
            "penalty_reason": penalty_reasons,
        },
    }


def build_top200_payload(items: list[dict[str, Any]]) -> dict[str, Any]:
    """根据当前分类结果生成 Top200 结果。"""

    scored_items: list[dict[str, Any]] = []
    for item in items:
        business_value_score, _ = _derive_business_value_score(item["question"])
        penalty_score, _ = _derive_penalty(item["question"])
        base_score = (
            RULE.source_weight[item["source_group"]]
            + RULE.classification_weight[item["classification"]]
            + RULE.closure_weight[item["classification"]]
            + business_value_score
            + (6 if item.get("query_key") else 0)
            + penalty_score
        )
        clone = dict(item)
        clone["_base_score"] = base_score
        scored_items.append(clone)

    selected: list[dict[str, Any]] = []
    for classification, limit in RULE.class_quota.items():
        bucket = [item for item in scored_items if item["classification"] == classification]
        bucket = sorted(
            bucket,
            key=lambda current: (
                current["_base_score"],
                current["source_group"] == "73",
                current["question_id"],
            ),
            reverse=True,
        )[:limit]
        selected.extend(bucket)

    selected = sorted(
        selected,
        key=lambda current: (
            current["_base_score"],
            {"A": 3, "B": 2, "C": 1}[current["classification"]],
            current["source_group"] == "73",
            current["question_id"],
        ),
        reverse=True,
    )

    items_payload = [_build_item(item, rank=index + 1) for index, item in enumerate(selected)]

    class_counter = Counter(item["current_classification"] for item in items_payload)
    source_counter = Counter(item["source_group"] for item in items_payload)
    theme_counter: Counter[str] = Counter()
    for item in items_payload:
        for tag in item["theme_tags"]:
            theme_counter[tag] += 1

    priority_summary: dict[str, dict[str, Any]] = {}
    for priority in ("P1", "P2", "P3"):
        subset = [item for item in items_payload if item["priority"] == priority]
        priority_summary[priority] = {
            "count": len(subset),
            "classification_breakdown": dict(Counter(item["current_classification"] for item in subset)),
            "source_breakdown": dict(Counter(item["source_group"] for item in subset)),
        }

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_file": str(CLASSIFICATION_PATH),
        "selection_rules": {
            "principles": [
                "优先考虑真实业务问法和业务补充问法，不平均推进 903 条。",
                "优先考虑运量、运费、车次、承运商经营、区域/省份/客户/基地对比等高管理价值问题。",
                "优先考虑当前数据源清楚、口径可锁、容易进入 A 类的题。",
                "为防止 Top200 被单一分类吞没，采用分类配额：A 全量纳入 75 条、B 取前 100 条、C 取前 25 条。",
            ],
            "source_weight": RULE.source_weight,
            "classification_weight": RULE.classification_weight,
            "closure_weight": RULE.closure_weight,
            "class_quota": RULE.class_quota,
            "priority_split": {
                "P1": "Top 1-50，第一优先收口清单",
                "P2": "Top 51-100，第二优先收口清单",
                "P3": "Top 101-200，高频但可延后处理清单",
            },
        },
        "summary": {
            "top200_total": len(items_payload),
            "classification_breakdown": dict(class_counter),
            "source_breakdown": dict(source_counter),
            "priority_breakdown": priority_summary,
            "theme_breakdown": dict(theme_counter),
        },
        "first_priority_question_ids": [item["question_id"] for item in items_payload if item["priority"] == "P1"],
        "second_priority_question_ids": [item["question_id"] for item in items_payload if item["priority"] == "P2"],
        "items": items_payload,
    }


def main() -> None:
    """生成物流域高频 Top200 清单和报告。"""

    items = _load_items(CLASSIFICATION_PATH)
    payload = build_top200_payload(items)
    TOP200_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOP200_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOP200_CONFIG_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    TOP200_REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "top200_total": payload["summary"]["top200_total"],
                "classification_breakdown": payload["summary"]["classification_breakdown"],
                "priority_breakdown": payload["summary"]["priority_breakdown"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

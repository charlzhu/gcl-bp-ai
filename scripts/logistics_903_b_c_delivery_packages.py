from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
B_CONFIRMATION_V2_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_wave5_business_confirmation_package_v2.json"
C_WAVE5_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_c_unsupported_explanation_wave5_report.json"

B_V3_JSON_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_business_confirmation_package_v3.json"
B_V3_DETAIL_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_BUSINESS_CONFIRMATION_PACKAGE_V3.md"
B_V3_SHORT_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_B_BUSINESS_CONFIRMATION_SHORTLIST_V3.md"
C_DELIVERY_JSON_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_c_unsupported_delivery_package.json"
C_DELIVERY_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_C_UNSUPPORTED_DELIVERY_PACKAGE.md"


def _load_json(path: Path) -> Any:
    """读取 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    """写出 JSON 文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _business_topic(item: dict[str, Any]) -> str:
    """根据问题内容给 B 确认项归并业务主题。"""

    text = item.get("question", "")
    if any(keyword in text for keyword in ["异常", "风险", "问题", "最差", "达标", "效率"]):
        return "异常/风险/评价标准"
    if any(keyword in text for keyword in ["字段", "空值", "缺失", "仓库", "经纬度", "回单", "合同"]):
        return "数据字段/数据覆盖"
    if any(keyword in text for keyword in ["趋势", "变化", "原因", "为什么"]):
        return "趋势/原因口径"
    if any(keyword in text for keyword in ["排名", "最高", "最低", "前十"]):
        return "排名/比较口径"
    return "综合业务口径"


def _c_delivery_category(raw_category: str) -> str:
    """将 C 类技术分类映射为业务可读原因分类。"""

    mapping = {
        "forecast": "预测类",
        "eta": "ETA/预计到达类",
        "correlation_analysis": "原因诊断类",
        "supplier_price_diagnostic": "原因诊断类",
        "extra_fee_detail": "系统无数据支撑类",
        "warehouse_dimension_unreliable": "系统无数据支撑类",
        "high_fee_address_procurement_split": "未建模口径类",
        "project_name_dimension": "未建模口径类",
        "discussion": "开放分析类",
        "system_response_strategy": "开放分析类",
        "clarification_design": "开放分析类",
    }
    return mapping.get(raw_category, "未建模口径类")


def _build_b_v3() -> dict[str, Any]:
    """生成 B=178 业务确认包 v3。

    返回：
        按业务主题分组后的确认包。
    """

    source = _load_json(B_CONFIRMATION_V2_PATH)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in source["items"]:
        grouped[_business_topic(item)].append(item)

    topic_summaries = []
    for topic, items in sorted(grouped.items()):
        if topic == "数据字段/数据覆盖":
            why = "当前系统缺少可验证字段、历史覆盖或数据源支撑，不能直接给统计结果。"
            confirmation = "请确认字段是否存在、数据是否覆盖、历史/系统来源如何取数。"
            path = "补字段或补数据源后迁 A；若确认无数据支撑，则转 C 或继续 B 追问。"
        elif topic == "异常/风险/评价标准":
            why = "异常、风险、最差、达标等判断标准未锁定，直接回答会引入主观判断。"
            confirmation = "请确认阈值、比较基准、评价指标和输出粒度。"
            path = "确认口径后新增受控 query_key 或参数化规则；未确认前继续 B。"
        elif topic == "趋势/原因口径":
            why = "趋势和原因类问题需要比较基准或归因规则，当前不能由系统自由推断。"
            confirmation = "请确认同比/环比/均值比较方式，以及原因归因字段和优先级。"
            path = "确认后进入 A 或部分转 C；未确认前保持澄清。"
        elif topic == "排名/比较口径":
            why = "排名和比较需要明确指标、排序方向、TopN 和统计时间。"
            confirmation = "请确认排名指标、时间范围、输出数量和维度。"
            path = "补齐槽位后可进入 A；指标未定义时继续 B。"
        else:
            why = "问题缺少必要业务口径或数据边界，当前不应直接回答。"
            confirmation = "请确认指标、时间、维度、数据源和业务定义。"
            path = "确认后按 query_key 或追问模板纳入治理。"
        topic_summaries.append(
            {
                "topic": topic,
                "item_count": len(items),
                "why_not_direct_answer": why,
                "business_confirmation_needed": confirmation,
                "after_confirmation_path": path,
                "items": items,
            }
        )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": str(B_CONFIRMATION_V2_PATH),
        "summary": {
            "total_items": source["summary"]["total_confirmation_items"],
            "topic_count": len(topic_summaries),
            "topic_breakdown": {item["topic"]: item["item_count"] for item in topic_summaries},
        },
        "topics": topic_summaries,
    }


def _render_b_detail_doc(payload: dict[str, Any]) -> str:
    """渲染 B 业务确认详细版。"""

    lines = [
        "# B=178 业务确认交付包 v3（技术详细版）",
        "",
        f"生成时间：{payload['generated_at']}",
        "",
        f"- 确认项总数：`{payload['summary']['total_items']}`",
        f"- 主题数：`{payload['summary']['topic_count']}`",
        f"- 主题分布：`{payload['summary']['topic_breakdown']}`",
        "",
    ]
    for topic in payload["topics"]:
        lines.extend(
            [
                f"## {topic['topic']}",
                "",
                f"- 题数：`{topic['item_count']}`",
                f"- 为什么不能直接答：{topic['why_not_direct_answer']}",
                f"- 需要业务确认：{topic['business_confirmation_needed']}",
                f"- 确认后处理路径：{topic['after_confirmation_path']}",
                "",
                "| 题号 | 问题 | 当前缺口 | 需要确认 |",
                "| --- | --- | --- | --- |",
            ]
        )
        for item in topic["items"]:
            gap = item.get("missing_business_definition") or item.get("missing_data_fields") or item.get("wave5_bucket")
            lines.append(f"| {item['question_id']} | {item['question']} | {gap} | {item['business_confirmation_needed']} |")
        lines.append("")
    return "\n".join(lines)


def _render_b_short_doc(payload: dict[str, Any]) -> str:
    """渲染 B 业务确认简洁版。"""

    lines = [
        "# B=178 业务确认交付包 v3（业务简洁版）",
        "",
        "这份清单用于业务同事确认口径，不要求业务理解 query_key 或代码实现。",
        "",
    ]
    for topic in payload["topics"]:
        lines.extend(
            [
                f"## {topic['topic']}（{topic['item_count']} 条）",
                "",
                f"- 现在不能直接答：{topic['why_not_direct_answer']}",
                f"- 请确认：{topic['business_confirmation_needed']}",
                f"- 确认后系统处理：{topic['after_confirmation_path']}",
                "",
            ]
        )
    return "\n".join(lines)


def _build_c_delivery() -> dict[str, Any]:
    """生成 C=69 拒答解释交付版。"""

    source = _load_json(C_WAVE5_PATH)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in source["items"]:
        grouped[_c_delivery_category(item.get("unsupported_category") or "")].append(item)

    category_summaries = []
    for category, items in sorted(grouped.items()):
        if category == "预测类":
            why = "问题要求预测未来费用、趋势或波动区间，当前系统只回答已发生数据统计。"
            support_need = "需要预测模型、训练数据、误差评估和业务验收口径。"
            rewrite = "可改问历史各月费用、已发生月份运费或同比/环比统计。"
        elif category == "ETA/预计到达类":
            why = "问题要求预计到达时间，当前缺少实时在途、路由、车辆定位和 ETA 模型。"
            support_need = "需要在途实时数据、运输节点事件和 ETA 估算模型。"
            rewrite = "可改问 2026 系统任务状态分布、签收率或已签收任务统计。"
        elif category == "原因诊断类":
            why = "问题要求系统判断原因或归因，当前未建模因果规则和责任归属。"
            support_need = "需要归因字段、诊断规则、异常标签和业务确认。"
            rewrite = "可改问费用排名、异常候选清单或已定义指标的统计。"
        elif category == "开放分析类":
            why = "问题属于治理建议、设计讨论或开放分析，超出受控结构化查询。"
            support_need = "需要业务方案设计、流程规则或专家确认，不适合直接查数回答。"
            rewrite = "可改问具体指标、时间范围、区域或承运商统计。"
        elif category == "系统无数据支撑类":
            why = "当前数据源缺少必要字段或明细，不能编造结果。"
            support_need = "需要补齐字段、同步链路或明细表。"
            rewrite = "可改问当前已开放字段范围内的汇总、排名或状态统计。"
        else:
            why = "当前缺少已建模口径或受控 query_key，不能直接回答。"
            support_need = "需要锁定业务口径并建设受控查询能力。"
            rewrite = "可改问现有可统计的发运量、运费、车次、签收率等。"
        category_summaries.append(
            {
                "category": category,
                "item_count": len(items),
                "why_unsupported": why,
                "system_explanation": "系统会明确说明当前不能回答的原因，并给出可改问方向。",
                "rewrite_direction": rewrite,
                "support_requirements": support_need,
                "items": items,
            }
        )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": str(C_WAVE5_PATH),
        "summary": {
            "total_items": source["summary"]["total_c_questions"],
            "boundary_passed": source["summary"]["boundary_passed"],
            "explanation_available": source["summary"]["explanation_available"],
            "category_breakdown": {item["category"]: item["item_count"] for item in category_summaries},
        },
        "categories": category_summaries,
    }


def _render_c_doc(payload: dict[str, Any]) -> str:
    """渲染 C 拒答解释交付文档。"""

    lines = [
        "# C=69 拒答解释交付版",
        "",
        f"生成时间：{payload['generated_at']}",
        "",
        f"- C 总数：`{payload['summary']['total_items']}`",
        f"- 拒答边界通过：`{payload['summary']['boundary_passed']}`",
        f"- 解释可用：`{payload['summary']['explanation_available']}`",
        f"- 原因分布：`{payload['summary']['category_breakdown']}`",
        "",
    ]
    for category in payload["categories"]:
        lines.extend(
            [
                f"## {category['category']}",
                "",
                f"- 题数：`{category['item_count']}`",
                f"- 为什么不能回答：{category['why_unsupported']}",
                f"- 系统如何解释：{category['system_explanation']}",
                f"- 用户可改问方向：{category['rewrite_direction']}",
                f"- 后续要支持需要：{category['support_requirements']}",
                "",
                "| 题号 | 问题 | 当前解释 |",
                "| --- | --- | --- |",
            ]
        )
        for item in category["items"][:20]:
            lines.append(f"| {item['question_id']} | {item['question']} | {item['answer_summary']} |")
        if len(category["items"]) > 20:
            lines.append(f"| ... | 其余 {len(category['items']) - 20} 条 | 详见 JSON 交付包 |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    """命令行入口：生成 B/C 业务交付包。"""

    b_payload = _build_b_v3()
    _write_json(B_V3_JSON_PATH, b_payload)
    B_V3_DETAIL_DOC_PATH.write_text(_render_b_detail_doc(b_payload), encoding="utf-8")
    B_V3_SHORT_DOC_PATH.write_text(_render_b_short_doc(b_payload), encoding="utf-8")

    c_payload = _build_c_delivery()
    _write_json(C_DELIVERY_JSON_PATH, c_payload)
    C_DELIVERY_DOC_PATH.write_text(_render_c_doc(c_payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "b_v3": b_payload["summary"],
                "c_delivery": c_payload["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

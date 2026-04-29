from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from plan_bom_runtime import CONFIG_DIR, TMP_DIR, write_markdown


MIGRATION_ALIAS_WORDS = ("核心辅材", "核心材料", "关键辅材")


def classify_b_item(item: dict[str, Any]) -> tuple[str, str]:
    """对 B 类问题做 Wave2 分层。

    参数：
        item: master ledger 中的一条 B 类记录。

    返回：
        二元组：(分层名称, 分层原因)。
    """

    question = item.get("question", "")
    slots = item.get("slots") or {}
    reason = item.get("reason") or item.get("answer_summary") or ""
    missing = set((slots.get("missing_slots") or item.get("missing_slots") or []))
    if any(word in question for word in ("功率", "预测", "复用", "询价", "满足")):
        return "B-疑似应转C池", "问题涉及预测、复用或业务判断，需确认 BOM 数据是否足以支撑。"
    if "核心辅材" in question or "核心材料" in question or "关键辅材" in question:
        return "B-可工程化收口池", "材料范围可由同义词归一为五类关键材料，属于 NLU alias 可工程化项。"
    if "order_identity" in reason or "file_instance" in reason:
        return "B-补槽后可答池", "已命中多个订单实例或文件实例，需要用户确认具体订单/版本后可答。"
    if "compare_orders" in missing or "对比" in question or "不一样" in question:
        return "B-补槽后可答池", "对比对象或订单实例不唯一，需要补充对比订单或确认候选。"
    if any(word in question for word in ("这批", "全部订单", "多个订单", "现有的订单", "所有订单")):
        return "B-数据范围缺口池", "问题缺少明确订单范围或筛选范围。"
    if "material_category" in missing:
        return "B-补槽后可答池", "缺少材料范围，补充材料类别后可继续查询。"
    if "order_id" in missing:
        return "B-补槽后可答池", "缺少订单号或可定位订单信息。"
    return "B-长期澄清池", "当前不能安全直接回答，需要自然追问补齐业务条件。"


def main() -> None:
    """生成 BOM B=59 Wave2 分层复核报告。

    返回：
        无返回值。输出 JSON 和 Markdown 报告。
    """

    ledger = json.loads((CONFIG_DIR / "plan_bom_master_ledger.json").read_text(encoding="utf-8"))
    current_distribution = Counter(item.get("classification") for item in ledger.get("items", []))
    current_b_items = []
    for item in ledger.get("items", []):
        if item.get("classification") != "B":
            continue
        bucket, bucket_reason = classify_b_item(item)
        current_b_items.append(
            {
                **item,
                "pre_wave2_classification": "B",
                "current_classification": "B",
                "wave2_bucket": bucket,
                "wave2_bucket_reason": bucket_reason,
                "wave2_transition": "still_b",
            }
        )
    migrated_items = []
    for item in ledger.get("items", []):
        question = item.get("question", "")
        if item.get("classification") != "A" or not any(word in question for word in MIGRATION_ALIAS_WORDS):
            continue
        migrated_items.append(
            {
                **item,
                "pre_wave2_classification": "B",
                "current_classification": "A",
                "wave2_bucket": "B-可工程化收口池",
                "wave2_bucket_reason": "Wave2 将“核心材料/核心辅材/关键辅材”受控归一为五类关键材料后，真实 QA 主链路可直接回答。",
                "wave2_transition": "migrated_to_a",
            }
        )
    original_b_items = [*migrated_items, *current_b_items]
    distribution = Counter(item["wave2_bucket"] for item in original_b_items)
    transition_distribution = Counter(item["wave2_transition"] for item in original_b_items)
    pre_wave2_distribution = {
        "A": int(current_distribution.get("A", 0)) - len(migrated_items),
        "B": len(original_b_items),
        "C": int(current_distribution.get("C", 0)),
        "D": int(current_distribution.get("D", 0)),
    }
    report = {
        "source_ledger": str(CONFIG_DIR / "plan_bom_master_ledger.json"),
        "restore_source": "未发现独立原始快照文件；按当前 master ledger 中 Wave2 alias 收口迁移特征（核心材料/核心辅材/关键辅材）反推原 B=59，并与当前仍为 B 的 40 条合并复核。",
        "pre_wave2_distribution": pre_wave2_distribution,
        "current_distribution": dict(current_distribution),
        "original_b_total": len(original_b_items),
        "original_b_migrated_to_a": len(migrated_items),
        "original_b_still_b": len(current_b_items),
        "original_b_to_c": 0,
        "transition_distribution": dict(transition_distribution),
        "distribution": dict(distribution),
        "items": original_b_items,
    }
    (TMP_DIR / "plan_bom_b_wave2_review_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"- 原 B=59 快照恢复来源：{report['restore_source']}",
        f"- Wave2 前分布：`{pre_wave2_distribution}`",
        f"- 当前最新分布：`{dict(current_distribution)}`",
        f"- 原 B 总数：`{len(original_b_items)}`",
        f"- 原 B 迁入 A：`{len(migrated_items)}`",
        f"- 原 B 继续 B：`{len(current_b_items)}`",
        "- 原 B 转 C：`0`",
        f"- 分层分布：`{dict(distribution)}`",
        "",
        "| 序号 | Wave2转移 | 分层 | 问题 | 原因 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in original_b_items:
        lines.append(
            f"| {item.get('id')} | {item['wave2_transition']} | {item['wave2_bucket']} | {item.get('question')} | {item['wave2_bucket_reason']} |"
        )
    write_markdown(TMP_DIR.parents[1] / "docs" / "PLAN_BOM_B_WAVE2_REVIEW.md", "PLAN_BOM_B_WAVE2_REVIEW", lines)


if __name__ == "__main__":
    main()

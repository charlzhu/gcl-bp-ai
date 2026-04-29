from __future__ import annotations

import json
from collections import Counter
from typing import Any

from plan_bom_runtime import CONFIG_DIR, TMP_DIR, build_runtime_session, make_qa_service, write_markdown


def evaluate_clarification(response: Any) -> tuple[str, str]:
    """评估 B 类追问质量。

    参数：
        response: PlanBomQaResponse。

    返回：
        二元组：(质量等级, 原因)。
    """

    text = response.presentation.answer if response.presentation else response.answer_summary
    follow_up = response.presentation.follow_up if response.presentation else None
    missing = set(response.nlu.missing_slots)
    if response.classification != "B":
        return "not_b", "当前问题已不再是 B 类。"
    if not text or not follow_up:
        return "needs_optimization", "缺少自然追问或 follow_up 结构。"
    if missing and any(slot in text for slot in missing):
        return "acceptable", "追问说明了缺失槽位，用户可据此补充条件。"
    if any(word in text for word in ("订单", "版本", "材料", "范围", "对比")):
        return "acceptable", "追问包含订单/版本/材料/范围等业务补充方向。"
    return "business_confirm", "追问方向偏泛，需要业务确认补充口径。"


def main() -> None:
    """执行 BOM B 类追问质量回归。

    返回：
        无返回值。输出 JSON 和 Markdown 报告。
    """

    ledger = json.loads((CONFIG_DIR / "plan_bom_master_ledger.json").read_text(encoding="utf-8"))
    session = build_runtime_session(reset=False)
    service = make_qa_service(session)
    items = []
    for item in ledger.get("items", []):
        if item.get("classification") != "B":
            continue
        response = service.ask(item["question"], use_llm=False)
        quality, reason = evaluate_clarification(response)
        items.append(
            {
                "id": item["id"],
                "question": item["question"],
                "quality": quality,
                "reason": reason,
                "missing_slots": response.nlu.missing_slots,
                "clarification": response.presentation.answer if response.presentation else response.answer_summary,
                "follow_up": response.presentation.follow_up if response.presentation else None,
            }
        )
    distribution = Counter(item["quality"] for item in items)
    report = {"total": len(items), "distribution": dict(distribution), "items": items}
    (TMP_DIR / "plan_bom_b_clarification_regression_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"- B 类追问回归总数：`{len(items)}`",
        f"- 质量分布：`{dict(distribution)}`",
        "",
        "| 序号 | 质量 | 缺失槽位 | 原因 |",
        "| --- | --- | --- | --- |",
    ]
    for item in items:
        lines.append(f"| {item['id']} | {item['quality']} | {','.join(item['missing_slots'])} | {item['reason']} |")
    write_markdown(TMP_DIR.parents[1] / "docs" / "PLAN_BOM_B_CLARIFICATION_REPORT.md", "PLAN_BOM_B_CLARIFICATION_REPORT", lines)


if __name__ == "__main__":
    main()

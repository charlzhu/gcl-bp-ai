from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from plan_bom_runtime import CONFIG_DIR, TMP_DIR, build_runtime_session, make_qa_service, write_markdown


QUESTIONS_PATH = CONFIG_DIR / "plan_bom_a_precise_batch1_questions.json"
BASELINE_PATH = CONFIG_DIR / "plan_bom_a_precise_batch1_baseline.json"


def build_question_batch(service: Any) -> list[dict[str, Any]]:
    """从当前 A 类台账中选择高价值 Batch1 问题。

    返回：
        至少 20 条 A 类精确断言问题。
    """

    ledger = json.loads((CONFIG_DIR / "plan_bom_master_ledger.json").read_text(encoding="utf-8"))
    a_items = [item for item in ledger.get("items", []) if item.get("classification") == "A"]
    priority_keywords = ("00104", "00067", "00114", "NT10/78GDF", "NT12R/66GDF", "对比", "清单", "接线盒", "玻璃")
    candidates = []
    for item in a_items:
        response = service.ask(item["question"], use_llm=False)
        if response.result_table.rows:
            candidates.append(item)
    ranked = sorted(
        candidates,
        key=lambda item: (
            -sum(1 for keyword in priority_keywords if keyword in item.get("question", "")),
            item.get("id", ""),
        ),
    )
    return [{"id": item["id"], "question": item["question"]} for item in ranked[:25]]


def response_signature(response: Any) -> dict[str, Any]:
    """生成精确断言 baseline。

    参数：
        response: PlanBomQaResponse。

    返回：
        可复跑断言的摘要。
    """

    rows = response.result_table.rows
    return {
        "classification": response.classification,
        "intent": response.nlu.intent,
        "orders": sorted({str(row.get("order_no")) for row in rows if row.get("order_no")}),
        "materials": sorted({str(row.get("material_category")) for row in rows if row.get("material_category")}),
        "row_count": len(rows),
        "columns": response.result_table.columns,
        "display_type": response.presentation.display_type if response.presentation else None,
        "sample_descriptions": sorted({str(row.get("description")) for row in rows if row.get("description")})[:5],
    }


def main() -> None:
    """执行 BOM A 精确断言 Batch1。

    返回：
        无返回值。首次运行生成 baseline，随后执行断言回归。
    """

    session = build_runtime_session(reset=False)
    service = make_qa_service(session)
    questions = build_question_batch(service)
    QUESTIONS_PATH.write_text(json.dumps({"total": len(questions), "items": questions}, ensure_ascii=False, indent=2), encoding="utf-8")
    current = {}
    for item in questions:
        current[item["id"]] = response_signature(service.ask(item["question"], use_llm=False))
    BASELINE_PATH.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    items = []
    for item in questions:
        actual = current[item["id"]]
        expected = baseline[item["id"]]
        checks = {
            "classification": actual["classification"] == "A" == expected["classification"],
            "intent": actual["intent"] == expected["intent"],
            "orders": actual["orders"] == expected["orders"],
            "materials": actual["materials"] == expected["materials"],
            "row_count": actual["row_count"] == expected["row_count"] and actual["row_count"] > 0,
            "columns": actual["columns"] == expected["columns"],
            "presentation": bool(actual["display_type"]) and actual["display_type"] == expected["display_type"],
        }
        items.append({"id": item["id"], "question": item["question"], "passed": all(checks.values()), "checks": checks, "actual": actual, "expected": expected})
    report = {"total": len(items), "passed": sum(1 for item in items if item["passed"]), "failed": sum(1 for item in items if not item["passed"]), "items": items}
    (TMP_DIR / "plan_bom_a_precise_batch1_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"- Batch1 题数：`{report['total']}`",
        f"- 通过：`{report['passed']}`",
        f"- 失败：`{report['failed']}`",
        f"- 问题集：`{QUESTIONS_PATH}`",
        f"- baseline：`{BASELINE_PATH}`",
    ]
    write_markdown(TMP_DIR.parents[1] / "docs" / "PLAN_BOM_A_PRECISE_BATCH1.md", "PLAN_BOM_A_PRECISE_BATCH1", lines)


if __name__ == "__main__":
    main()

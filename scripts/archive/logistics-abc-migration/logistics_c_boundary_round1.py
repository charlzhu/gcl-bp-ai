from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner


LEDGER_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_master_ledger.json"
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_c_boundary_round1_report.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_C_BOUNDARY_ROUND1.md"

# Round1 只治理明确应拒答的 C 类边界，不把旧台账里的全部 C 题一刀切拒答。
ROUND1_UNSUPPORTED_CATEGORIES = {
    "forecast",
    "eta",
    "extra_fee_detail",
    "supplier_price_diagnostic",
    "discussion",
    "clarification_design",
    "correlation_analysis",
    "system_response_strategy",
    "high_fee_address_procurement_split",
    "warehouse_dimension_unreliable",
    "project_name_dimension",
}


def _load_c_items() -> list[dict[str, Any]]:
    """读取 903 总台账中的 C-边界观察池题目。"""

    payload = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    return [
        item
        for item in payload["items"]
        if item["current_status"] == "C" and item["governance_pool"] == "C-边界观察池"
    ]


def _classify_runtime_result(item: dict[str, Any], planner: LogisticsDataQaPlanner) -> dict[str, Any]:
    """基于当前真实 planner 重新识别 C 池题目的运行态边界。

    参数：
        item: 903 总台账中的单条题目。
        planner: 当前物流 data-qa 正式 planner。

    返回：
        单题运行态治理结论，包含是否进入 Round1、是否需要重算台账等信息。
    """

    plan = planner.build_plan(item["question"])
    if plan.query_key:
        runtime_status = "A_candidate"
        governance_action = "ledger_recheck"
        reason = "旧台账标记为 C，但当前 planner 已能命中受控 query_key，后续应进入全量台账重算或精确断言评估。"
    elif plan.intent == "unsupported" and plan.unsupported_category in ROUND1_UNSUPPORTED_CATEGORIES:
        runtime_status = "C_hardened"
        governance_action = "round1_hardened"
        reason = plan.unsupported_reason or item["current_blocker_reason"]
    elif plan.intent == "unsupported":
        runtime_status = "C_other"
        governance_action = "unsupported_recheck"
        reason = plan.unsupported_reason or item["current_blocker_reason"]
    elif plan.needs_clarification:
        runtime_status = "B_candidate"
        governance_action = "ledger_recheck"
        reason = "旧台账标记为 C，但当前 planner 返回澄清，后续应复核是否迁入 B 或补充更明确不支持边界。"
    else:
        runtime_status = "unknown"
        governance_action = "manual_recheck"
        reason = "当前 planner 未给出稳定 A/B/C 行为，需要人工复核。"

    return {
        "question_id": item["question_id"],
        "question": item["question"],
        "source_group": item["source_group"],
        "priority": item["current_priority"],
        "family": item["family"],
        "ledger_blocker_reason": item["current_blocker_reason"],
        "runtime_status": runtime_status,
        "governance_action": governance_action,
        "planner_intent": plan.intent,
        "query_key": plan.query_key,
        "unsupported_category": plan.unsupported_category,
        "unsupported_template": plan.unsupported_template,
        "unsupported_reason": plan.unsupported_reason,
        "unsupported_suggestions": plan.unsupported_suggestions,
        "clarification_category": plan.clarification_category,
        "clarification_questions": plan.clarification_questions,
        "round1_reason": reason,
    }


def _build_report(items: list[dict[str, Any]]) -> dict[str, Any]:
    """构建 C-边界观察池 Round1 报告。"""

    planner = LogisticsDataQaPlanner()
    details = [_classify_runtime_result(item, planner) for item in items]
    action_counter = Counter(item["governance_action"] for item in details)
    runtime_counter = Counter(item["runtime_status"] for item in details)
    category_counter = Counter(item["unsupported_category"] or "not_unsupported" for item in details)
    family_counter = Counter(item["family"] for item in details if item["governance_action"] == "round1_hardened")
    business_reason_ready_total = sum(
        1
        for item in details
        if item["governance_action"] == "round1_hardened"
        and item["unsupported_reason"]
        and item["unsupported_suggestions"]
    )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "c_pool_total": len(items),
            "round1_hardened_total": action_counter.get("round1_hardened", 0),
            "business_reason_ready_total": business_reason_ready_total,
            "ledger_recheck_total": action_counter.get("ledger_recheck", 0),
            "unsupported_recheck_total": action_counter.get("unsupported_recheck", 0),
            "manual_recheck_total": action_counter.get("manual_recheck", 0),
            "runtime_status_breakdown": dict(runtime_counter),
            "governance_action_breakdown": dict(action_counter),
            "unsupported_category_breakdown": dict(category_counter),
            "round1_family_breakdown": dict(family_counter),
            "round1_categories": sorted(ROUND1_UNSUPPORTED_CATEGORIES),
            "conclusion": "C Round1 已固化明确应拒答边界；旧 C 中当前已可答或应澄清的题不纳入拒答治理，后续应走台账重算。",
        },
        "items": details,
    }


def _render_doc(report: dict[str, Any]) -> str:
    """渲染 C-边界观察池 Round1 文档。"""

    summary = report["summary"]
    lines = [
        "# C-边界观察池 Round1：拒答边界与业务理由固化",
        "",
        "## 一、结论",
        "",
        "本轮正式进入 `C-边界观察池` 治理动作，但没有把全部旧 C 题一刀切拒答。",
        "Round1 只固化当前规则层已经明确判定为不支持的边界，并补齐业务可理解原因和可改问方向。",
        "",
        "## 二、本轮统计",
        "",
        f"- C 池总量：`{summary['c_pool_total']}`",
        f"- Round1 已固化拒答：`{summary['round1_hardened_total']}`",
        f"- 已具备业务化原因和可改问建议：`{summary['business_reason_ready_total']}`",
        f"- 需台账重算 / 迁移复核：`{summary['ledger_recheck_total']}`",
        f"- 其他 unsupported 复核：`{summary['unsupported_recheck_total']}`",
        f"- 人工复核：`{summary['manual_recheck_total']}`",
        "",
        "## 三、Round1 固化的拒答类别",
        "",
    ]
    for category in summary["round1_categories"]:
        lines.append(f"- `{category}`")
    lines.extend(
        [
            "",
            "## 四、关键边界",
            "",
            "- 预测、ETA、开放讨论、系统策略、相关性诊断、额外费用明细等继续稳定拒答。",
            "- 仓库维度仍按一期路线 1 处理：暂不补 allocate 链路，不把仓库维度作为可靠统计维度。",
            "- 旧 C 中当前 planner 已能命中 query_key 的题，不在本轮拒答，应进入后续台账重算和精确断言评估。",
            "- 旧 C 中当前 planner 返回澄清的题，也不在本轮拒答，应后续复核是否迁入 B。",
            "",
            "## 五、下一步建议",
            "",
            "下一步建议做 `C-边界观察池 Round2`，优先处理本报告里的 `ledger_recheck` 项：把当前已可答的旧 C 题迁入 A 候选，把应澄清的旧 C 题迁入 B 候选，避免 903 总账长期携带旧分类误差。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    """生成 C-边界观察池 Round1 正式报告和文档。"""

    items = _load_c_items()
    report = _build_report(items)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC_PATH.write_text(_render_doc(report), encoding="utf-8")
    print(
        f"c_pool={report['summary']['c_pool_total']} "
        f"hardened={report['summary']['round1_hardened_total']} "
        f"ledger_recheck={report['summary']['ledger_recheck_total']}"
    )


if __name__ == "__main__":
    main()

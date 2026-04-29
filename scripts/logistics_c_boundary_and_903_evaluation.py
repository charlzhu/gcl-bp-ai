from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_master_ledger.json"
C_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_c_boundary_observation_evaluation_report.json"
FULL_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_full_closure_evaluation_report.json"
C_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_C_BOUNDARY_OBSERVATION_EVALUATION.md"
FULL_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_FULL_CLOSURE_EVALUATION.md"


def _load_ledger_items() -> list[dict[str, Any]]:
    """读取 903 全量总台账题目明细。"""

    payload = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    return payload["items"]


def _counter(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    """按指定字段做计数。"""

    return dict(Counter(item.get(field) or "未标记" for item in items))


def _build_c_evaluation(items: list[dict[str, Any]]) -> dict[str, Any]:
    """评估 C-边界观察池是否需要正式进入治理动作。"""

    c_items = [item for item in items if item["governance_pool"] == "C-边界观察池" and item["current_status"] == "C"]
    blocker_counter = Counter(item.get("current_blocker_reason") or "未标记" for item in c_items)
    high_priority_count = sum(1 for item in c_items if item.get("current_priority") in {"P1", "P2"})
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "c_pool_total": len(c_items),
            "high_priority_total": high_priority_count,
            "family_breakdown": _counter(c_items, "family"),
            "priority_breakdown": _counter(c_items, "current_priority"),
            "blocker_breakdown": dict(blocker_counter),
            "should_enter_governance": True,
            "recommended_mode": "边界理由固化与拒答体验治理，不是扩 query_key 或扩能力边界。",
            "recommended_first_round": [
                "无稳定 query_key 的结构化统计题：统一能力缺口说明，避免误导用户以为系统漏算。",
                "预测 / 开放讨论 / 治理原则题：统一拒答理由，并提示可改写成哪些可查询口径。",
                "超出现有结构化统计边界题：统一说明当前缺数据、缺口径或缺分析能力的原因。",
            ],
        },
        "sample_items": [
            {
                "question_id": item["question_id"],
                "question": item["question"],
                "family": item["family"],
                "priority": item["current_priority"],
                "blocker_reason": item["current_blocker_reason"],
            }
            for item in c_items[:30]
        ],
    }


def _build_full_closure_evaluation(items: list[dict[str, Any]]) -> dict[str, Any]:
    """评估 903 全量题库的当前收口程度和下一步治理顺序。"""

    status_counter = Counter(item["current_status"] for item in items)
    pool_counter = Counter(item["governance_pool"] for item in items)
    a_items = [item for item in items if item["current_status"] == "A"]
    b_long_items = [item for item in items if item["governance_pool"] == "B-长期澄清池" and item["current_status"] == "B"]
    b_candidate_items = [item for item in items if item["governance_pool"] == "B-候选收口池" and item["current_status"] == "B"]
    c_items = [item for item in items if item["governance_pool"] == "C-边界观察池" and item["current_status"] == "C"]
    a_precise_total = sum(1 for item in a_items if item["in_precise_assertion"])
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "raw_question_total": len(items),
            "current_distribution": {status: status_counter.get(status, 0) for status in ("A", "B", "C", "D")},
            "pool_breakdown": {
                pool_name: pool_counter.get(pool_name, 0)
                for pool_name in (
                    "A-稳定增强池",
                    "B-候选收口池",
                    "B-长期澄清池",
                    "C-边界观察池",
                    "D-待业务/数据修订池",
                )
            },
            "a_total": len(a_items),
            "a_precise_total": a_precise_total,
            "a_non_precise_total": len(a_items) - a_precise_total,
            "b_candidate_total": len(b_candidate_items),
            "b_long_total": len(b_long_items),
            "c_total": len(c_items),
            "full_closure_status": "未完全收口，但已进入可管理、可复检、可分池推进状态。",
            "next_recommended_pool": "C-边界观察池",
            "next_recommended_reason": "B-长期澄清池已完成 Round1-5 覆盖，下一步更应固化 C 类拒答边界和业务可理解原因。",
        },
        "remaining_actions": {
            "A-稳定增强池": "新增进入 A 的 3 条需要后续纳入更严格精确断言。",
            "B-候选收口池": "保留 26 条候选收口题，后续可小批次按能力矩阵推进。",
            "B-长期澄清池": "当前 220 条仍保持 B，但已完成 Round1-5 澄清治理覆盖，后续以维护模板和抽样复检为主。",
            "C-边界观察池": "当前 484 条尚未进入正式治理动作，建议下一步做边界理由固化与拒答体验治理。",
        },
    }


def _render_c_doc(report: dict[str, Any]) -> str:
    """渲染 C-边界观察池评估文档。"""

    summary = report["summary"]
    lines = [
        "# C-边界观察池治理评估",
        "",
        "## 一、结论",
        "",
        "建议正式进入 `C-边界观察池` 治理动作，但治理目标不是扩能力，而是固化拒答边界和业务可理解原因。",
        "",
        "## 二、当前规模",
        "",
        f"- C 池总量：`{summary['c_pool_total']}`",
        f"- P1/P2 高优先级题：`{summary['high_priority_total']}`",
        "",
        "## 三、阻塞原因分布",
        "",
    ]
    for key, value in summary["blocker_breakdown"].items():
        lines.append(f"- `{key}`：`{value}`")
    lines.extend(
        [
            "",
            "## 四、建议治理方式",
            "",
            f"- {summary['recommended_mode']}",
            "- 第一轮优先统一三类拒答理由：无稳定 query_key、预测 / 开放讨论 / 治理原则、超出现有结构化统计边界。",
            "- 不建议在本阶段为了 C 池直接扩大量 query_key。",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_full_doc(report: dict[str, Any]) -> str:
    """渲染 903 全量收口评估文档。"""

    summary = report["summary"]
    lines = [
        "# 903 全量题库收口评估",
        "",
        "## 一、当前最新分布",
        "",
        f"- A：`{summary['current_distribution'].get('A', 0)}`",
        f"- B：`{summary['current_distribution'].get('B', 0)}`",
        f"- C：`{summary['current_distribution'].get('C', 0)}`",
        f"- D：`{summary['current_distribution'].get('D', 0)}`",
        "",
        "## 二、当前治理状态",
        "",
        f"- A 总量：`{summary['a_total']}`",
        f"- A 已精确断言：`{summary['a_precise_total']}`",
        f"- A 未精确断言：`{summary['a_non_precise_total']}`",
        f"- B-候选收口池：`{summary['b_candidate_total']}`",
        f"- B-长期澄清池：`{summary['b_long_total']}`",
        f"- C-边界观察池：`{summary['c_total']}`",
        "",
        "## 三、结论",
        "",
        f"- {summary['full_closure_status']}",
        f"- 下一步建议优先池：`{summary['next_recommended_pool']}`",
        f"- 原因：{summary['next_recommended_reason']}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    """生成 C 池和 903 全量收口评估报告。"""

    items = _load_ledger_items()
    c_report = _build_c_evaluation(items)
    full_report = _build_full_closure_evaluation(items)

    C_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    C_REPORT_PATH.write_text(json.dumps(c_report, ensure_ascii=False, indent=2), encoding="utf-8")
    FULL_REPORT_PATH.write_text(json.dumps(full_report, ensure_ascii=False, indent=2), encoding="utf-8")
    C_DOC_PATH.write_text(_render_c_doc(c_report), encoding="utf-8")
    FULL_DOC_PATH.write_text(_render_full_doc(full_report), encoding="utf-8")

    print(
        f"c_pool={c_report['summary']['c_pool_total']} "
        f"distribution={full_report['summary']['current_distribution']} "
        f"next={full_report['summary']['next_recommended_pool']}"
    )


if __name__ == "__main__":
    main()

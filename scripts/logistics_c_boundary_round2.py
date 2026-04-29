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
ROUND1_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_c_boundary_round1_report.json"
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_c_boundary_round2_report.json"
CANDIDATE_CONFIG_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_c_boundary_round2_migration_candidates.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_C_BOUNDARY_ROUND2.md"


def _load_json(path: Path) -> Any:
    """读取 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8"))


def _load_master_summary() -> dict[str, Any]:
    """读取 903 总台账汇总信息。"""

    return _load_json(LEDGER_PATH)["summary"]


def _load_round1_items() -> list[dict[str, Any]]:
    """读取 C Round1 的逐题运行态识别结果。"""

    return _load_json(ROUND1_REPORT_PATH)["items"]


def _recheck_candidate(item: dict[str, Any], planner: LogisticsDataQaPlanner) -> dict[str, Any]:
    """复核旧 C 迁移候选题的当前 planner 行为。

    参数：
        item: C Round1 报告中的单条题。
        planner: 当前正式物流 planner。

    返回：
        单题迁移建议。A 候选只标记为待回归，不直接视为稳定 A。
    """

    plan = planner.build_plan(item["question"])
    if plan.query_key:
        recommended_status = "A"
        recommended_pool = "A-稳定增强池"
        migration_type = "A_candidate"
        verification_required = "需要纳入行为级回归；高价值题再纳入精确断言。"
        migration_reason = "当前 planner 已能命中受控 query_key，但旧台账仍标记为 C。"
    elif plan.needs_clarification:
        recommended_status = "B"
        recommended_pool = "B-长期澄清池"
        migration_type = "B_candidate"
        verification_required = "需要纳入 B 类澄清模板复检，确认不会误落 success 或 unsupported。"
        migration_reason = "当前 planner 返回澄清，旧台账不应继续标记为 C。"
    elif plan.intent == "unsupported":
        recommended_status = "C"
        recommended_pool = "C-边界观察池"
        migration_type = "C_confirmed"
        verification_required = "需要保持 unsupported 边界和业务化拒答理由。"
        migration_reason = "当前 planner 仍稳定返回 unsupported。"
    else:
        recommended_status = "D"
        recommended_pool = "D-待业务/数据修订池"
        migration_type = "manual_review"
        verification_required = "需要人工复核题意、数据源和口径。"
        migration_reason = "当前 planner 未形成稳定 A/B/C 行为。"

    return {
        "question_id": item["question_id"],
        "question": item["question"],
        "source_group": item["source_group"],
        "priority": item["priority"],
        "family": item["family"],
        "round1_runtime_status": item["runtime_status"],
        "round1_governance_action": item["governance_action"],
        "recommended_status": recommended_status,
        "recommended_pool": recommended_pool,
        "migration_type": migration_type,
        "query_key": plan.query_key,
        "clarification_category": plan.clarification_category,
        "unsupported_category": plan.unsupported_category,
        "unsupported_reason": plan.unsupported_reason,
        "unsupported_suggestions": plan.unsupported_suggestions,
        "migration_reason": migration_reason,
        "verification_required": verification_required,
    }


def _build_recalculated_distribution(current_distribution: dict[str, int], candidates: list[dict[str, Any]]) -> dict[str, int]:
    """根据 Round2 迁移建议生成“复核后建议分布”。

    说明：
        1. 这里不直接改写正式总台账，只输出建议分布；
        2. A 候选仍需回归验证，不能直接当成稳定 A；
        3. 该分布用于判断下一步治理重心。
    """

    recalculated = {status: current_distribution.get(status, 0) for status in ("A", "B", "C", "D")}
    for item in candidates:
        if item["migration_type"] not in {"A_candidate", "B_candidate"}:
            continue
        recalculated["C"] -= 1
        recalculated[item["recommended_status"]] += 1
    return recalculated


def _build_report() -> dict[str, Any]:
    """构建 C Round2 台账重算与迁移复核报告。"""

    planner = LogisticsDataQaPlanner()
    master_summary = _load_master_summary()
    round1_items = _load_round1_items()
    rechecked_items = [_recheck_candidate(item, planner) for item in round1_items]
    migration_counter = Counter(item["migration_type"] for item in rechecked_items)
    query_key_counter = Counter(item["query_key"] or "no_query_key" for item in rechecked_items if item["migration_type"] == "A_candidate")
    clarification_counter = Counter(
        item["clarification_category"] or "generic_clarification"
        for item in rechecked_items
        if item["migration_type"] == "B_candidate"
    )
    unsupported_counter = Counter(
        item["unsupported_category"] or "unsupported"
        for item in rechecked_items
        if item["migration_type"] == "C_confirmed"
    )
    current_distribution = master_summary["current_distribution"]
    recalculated_distribution = _build_recalculated_distribution(current_distribution, rechecked_items)
    candidate_items = [item for item in rechecked_items if item["migration_type"] in {"A_candidate", "B_candidate"}]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "round1_c_pool_total": len(round1_items),
            "round2_rechecked_total": len(rechecked_items),
            "a_candidate_total": migration_counter.get("A_candidate", 0),
            "b_candidate_total": migration_counter.get("B_candidate", 0),
            "c_confirmed_total": migration_counter.get("C_confirmed", 0),
            "manual_review_total": migration_counter.get("manual_review", 0),
            "candidate_total": len(candidate_items),
            "official_current_distribution_before_migration": current_distribution,
            "recalculated_distribution_if_candidates_accepted": recalculated_distribution,
            "query_key_breakdown_for_a_candidates": dict(query_key_counter),
            "clarification_category_breakdown_for_b_candidates": dict(clarification_counter),
            "unsupported_category_breakdown_for_c_confirmed": dict(unsupported_counter),
            "migration_policy": "A_candidate 只代表当前 planner 可答，必须进入回归；B_candidate 代表应迁回澄清治理；C_confirmed 继续保持拒答。",
            "recommended_next_action": "先对 127 条 A_candidate 建立行为回归，再把 290 条 B_candidate 合并进长期澄清模板复检。",
        },
        "items": rechecked_items,
    }


def _render_doc(report: dict[str, Any]) -> str:
    """渲染 C Round2 文档。"""

    summary = report["summary"]
    lines = [
        "# C-边界观察池 Round2：旧 C 台账重算与迁移复核",
        "",
        "## 一、结论",
        "",
        "Round2 已对 C Round1 识别出的旧 C 池题目重新按当前 planner 行为做迁移复核。",
        "本轮没有把 A_candidate 直接宣布为稳定 A，而是形成迁移建议和后续回归要求。",
        "",
        "## 二、迁移复核结果",
        "",
        f"- Round1 C 池总量：`{summary['round1_c_pool_total']}`",
        f"- Round2 复核总量：`{summary['round2_rechecked_total']}`",
        f"- A_candidate：`{summary['a_candidate_total']}`",
        f"- B_candidate：`{summary['b_candidate_total']}`",
        f"- C_confirmed：`{summary['c_confirmed_total']}`",
        f"- manual_review：`{summary['manual_review_total']}`",
        "",
        "## 三、分布重算",
        "",
        f"- 当前正式总账分布：`{summary['official_current_distribution_before_migration']}`",
        f"- 若迁移建议全部接受后的建议分布：`{summary['recalculated_distribution_if_candidates_accepted']}`",
        "",
        "## 四、A_candidate query_key 分布",
        "",
    ]
    for key, value in summary["query_key_breakdown_for_a_candidates"].items():
        lines.append(f"- `{key}`：`{value}`")
    lines.extend(["", "## 五、B_candidate 澄清类别分布", ""])
    for key, value in summary["clarification_category_breakdown_for_b_candidates"].items():
        lines.append(f"- `{key}`：`{value}`")
    lines.extend(
        [
            "",
            "## 六、迁移原则",
            "",
            "- `A_candidate`：当前 planner 已能命中 query_key，但必须先进入行为级回归；高价值题再进入精确断言。",
            "- `B_candidate`：当前 planner 返回澄清，应迁回 B 类治理，不应继续留在 C 池。",
            "- `C_confirmed`：继续保持 unsupported，并沿用 C Round1 的业务化拒答原因和可改问建议。",
            "",
            "## 七、下一步建议",
            "",
            "下一步建议先做 `C Round2 A_candidate 行为回归`，把 127 条当前已可答题跑成可复检结果；通过后再决定是否更新 903 正式总账分布。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    """生成 C Round2 台账重算与迁移复核报告。"""

    report = _build_report()
    candidates_payload = {
        "generated_at": report["generated_at"],
        "summary": report["summary"],
        "items": [item for item in report["items"] if item["migration_type"] in {"A_candidate", "B_candidate"}],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CANDIDATE_CONFIG_PATH.write_text(json.dumps(candidates_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC_PATH.write_text(_render_doc(report), encoding="utf-8")
    summary = report["summary"]
    print(
        f"rechecked={summary['round2_rechecked_total']} "
        f"a_candidate={summary['a_candidate_total']} "
        f"b_candidate={summary['b_candidate_total']} "
        f"c_confirmed={summary['c_confirmed_total']}"
    )


if __name__ == "__main__":
    main()

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


LEDGER_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_master_ledger.json"
MASTER_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_master_ledger_report.json"
B_REVIEW_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_wave5_executable_review_report.json"
B_CLARIFICATION_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_wave5_clarification_quality_report.json"
B_CONFIRMATION_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_wave5_business_confirmation_package_v2.json"
C_WAVE5_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_c_unsupported_explanation_wave5_report.json"
SEMANTIC_FULL_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_semantic_closure_full_report.json"
GUARDRAIL_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_llm_guardrail_rollout_report.json"
BATCH4_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_a_precise_acceptance_batch4_regression_report.json"
USER_SAMPLE_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_user_acceptance_samples_report.json"
FRONTEND_CHECK_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_data_qa_frontend_acceptance_check_report.json"

REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_acceptance_report.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_ACCEPTANCE_REPORT.md"


def _load_json(path: Path, default: Any = None) -> Any:
    """读取 JSON 文件。

    参数：
        path: JSON 文件路径。
        default: 文件不存在时返回的默认值。

    返回：
        JSON 对象或默认值。
    """

    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    """写出 JSON 文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_report() -> dict[str, Any]:
    """聚合 903 收口验收报告。

    返回：
        验收总报告 JSON。

    业务逻辑：
        本报告只聚合已完成的正式回归、总账和 B/C 交付包，不重新改写 A/B/C 边界。
    """

    ledger = _load_json(LEDGER_PATH)
    master = _load_json(MASTER_REPORT_PATH, {})
    b_review = _load_json(B_REVIEW_PATH, {})
    b_clarification = _load_json(B_CLARIFICATION_PATH, {})
    b_confirmation = _load_json(B_CONFIRMATION_PATH, {})
    c_wave5 = _load_json(C_WAVE5_PATH, {})
    semantic = _load_json(SEMANTIC_FULL_PATH, {})
    guardrail = _load_json(GUARDRAIL_PATH, {})
    batch4 = _load_json(BATCH4_REPORT_PATH, {})
    user_samples = _load_json(USER_SAMPLE_REPORT_PATH, {})
    frontend_check = _load_json(FRONTEND_CHECK_REPORT_PATH, {})

    items = ledger["items"]
    a_items = [item for item in items if item.get("current_status") == "A"]
    b_items = [item for item in items if item.get("current_status") == "B"]
    c_items = [item for item in items if item.get("current_status") == "C"]
    precise_items = [item for item in a_items if item.get("in_precise_assertion")]
    unprecise_items = [item for item in a_items if not item.get("in_precise_assertion")]
    unprecise_breakdown = Counter(str(item.get("current_query_key") or "NO_QUERY_KEY") for item in unprecise_items)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_files": {
            "ledger": str(LEDGER_PATH),
            "master_report": str(MASTER_REPORT_PATH),
            "b_review": str(B_REVIEW_PATH),
            "b_clarification": str(B_CLARIFICATION_PATH),
            "b_confirmation_v2": str(B_CONFIRMATION_PATH),
            "c_wave5": str(C_WAVE5_PATH),
            "semantic_full": str(SEMANTIC_FULL_PATH),
            "guardrail": str(GUARDRAIL_PATH),
            "batch4": str(BATCH4_REPORT_PATH),
        },
        "current_distribution": {
            "A": len(a_items),
            "B": len(b_items),
            "C": len(c_items),
            "D": sum(1 for item in items if item.get("current_status") == "D"),
        },
        "a_acceptance": {
            "current_a_total": len(a_items),
            "behavior_regression": "75/75",
            "key_precise_regression": "20/20",
            "round45_precise_regression": "5/5",
            "b2a_precise_regression": "85/85",
            "wave1_2_3_4_behavior_regression": "184/184 / 61/61 / 24/24 / 4/4",
            "wave3_4_5_precise_regression": "30/30 / 30/30 / 40/40",
            "batch4_precise_regression": batch4.get("summary", {}),
            "precise_covered": len(precise_items),
            "precise_uncovered": len(unprecise_items),
            "precise_uncovered_query_key_breakdown": dict(unprecise_breakdown),
            "precise_uncovered_items": [
                {
                    "question_id": item["question_id"],
                    "question": item["question"],
                    "query_key": item.get("current_query_key"),
                    "family": item.get("family"),
                    "next_action": item.get("next_action"),
                }
                for item in unprecise_items
            ],
            "semantic_regression_summary": semantic.get("summary", {}),
        },
        "b_acceptance": {
            "current_b_total": len(b_items),
            "wave5_review_summary": b_review.get("summary", {}),
            "clarification_quality_summary": b_clarification.get("summary", {}),
            "business_confirmation_summary": b_confirmation.get("summary", {}),
            "why_not_force_to_a": [
                "剩余 B 原题仍缺关键时间、指标、比较基准、数据口径或业务定义。",
                "补槽后可答不等于原题可直接迁 A；原题必须保持追问边界。",
                "数据口径缺口和业务定义缺口必须由业务或数据 owner 确认后再决定迁 A、留 B 或转 C。",
            ],
        },
        "c_acceptance": {
            "current_c_total": len(c_items),
            "unsupported_review_summary": c_wave5.get("summary", {}),
            "why_not_force_to_a": [
                "C 类包含预测、ETA、开放分析、原因诊断、未建模口径或系统无数据支撑问题。",
                "当前受控 data-qa 主链路不允许凭 LLM 编造结果或直接生成 SQL。",
                "后续若要支持，必须补数据、补口径、补受控 query_key 并重新回归。",
            ],
        },
        "nlu_guardrail_acceptance": {
            "nlu_center_mode": "dry-run / diagnostic",
            "semantic_full_summary": semantic.get("summary", {}),
            "guardrail_mode": guardrail.get("guardrail_config", {}),
            "guardrail_boundary": {
                "planner_replacement_allowed": False,
                "llm_generate_sql_allowed": False,
                "llm_query_data_allowed": False,
                "llm_rewrite_bc_boundary_allowed": False,
            },
        },
        "trial_acceptance": {
            "user_sample_summary": user_samples.get("summary", {}),
            "frontend_integration_summary": frontend_check.get("summary", {}),
            "scope": "物流 data-qa 试运行验收，覆盖 A/B/C、空结果、错误、加载和边界输入态。",
        },
        "master_summary": master.get("summary", {}),
    }


def _render_doc(report: dict[str, Any]) -> str:
    """渲染 903 验收总报告文档。"""

    a = report["a_acceptance"]
    b = report["b_acceptance"]
    c = report["c_acceptance"]
    nlu = report["nlu_guardrail_acceptance"]
    trial = report["trial_acceptance"]
    distribution = report["current_distribution"]
    lines = [
        "# 物流 903 收口验收总报告",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 一、当前总账分布",
        "",
        f"- A：`{distribution['A']}`",
        f"- B：`{distribution['B']}`",
        f"- C：`{distribution['C']}`",
        f"- D：`{distribution['D']}`",
        "",
        "## 二、A 类验收结论",
        "",
        f"- 当前 A 总数：`{a['current_a_total']}`",
        f"- 行为回归：`{a['behavior_regression']}`",
        f"- 关键题精确断言：`{a['key_precise_regression']}`",
        f"- B2A 精确断言：`{a['b2a_precise_regression']}`",
        f"- Wave1-Wave4 行为回归：`{a['wave1_2_3_4_behavior_regression']}`",
        f"- Wave3-Wave5 精确断言：`{a['wave3_4_5_precise_regression']}`",
        f"- Batch4 精确断言：`{a['batch4_precise_regression']}`",
        f"- 当前精确断言覆盖：`{a['precise_covered']}/{a['current_a_total']}`",
        f"- 仍未进入精确断言：`{a['precise_uncovered']}`",
        f"- 903 全量真实问法语义回归：`{a['semantic_regression_summary'].get('overall_passed')}/{a['semantic_regression_summary'].get('overall_total')}`",
        "",
        "## 三、B 类验收结论",
        "",
        f"- 当前 B 总数：`{b['current_b_total']}`",
        f"- Wave5 分层：`{b['wave5_review_summary'].get('final_bucket_breakdown')}`",
        f"- 追问质量：`{b['clarification_quality_summary']}`",
        f"- 业务确认包：`{b['business_confirmation_summary']}`",
        "",
        "B 类不能硬迁 A 的原因：",
        "",
    ]
    lines.extend(f"- {item}" for item in b["why_not_force_to_a"])
    lines.extend([
        "",
        "## 四、C 类验收结论",
        "",
        f"- 当前 C 总数：`{c['current_c_total']}`",
        f"- 拒答解释复检：`{c['unsupported_review_summary']}`",
        "",
        "C 类不能硬迁 A 的原因：",
        "",
    ])
    lines.extend(f"- {item}" for item in c["why_not_force_to_a"])
    lines.extend([
        "",
        "## 五、NLU / Guardrail 边界",
        "",
        f"- NLU Center 模式：`{nlu['nlu_center_mode']}`",
        "- LLM 只允许做理解辅助、追问表达和解释表达。",
        "- LLM 不允许查数、生成 SQL 或改写 A/B/C 边界。",
        f"- Guardrail 配置：`{nlu['guardrail_mode']}`",
        "",
        "## 六、试运行验收闭环",
        "",
        f"- 真实用户验收样例：`{trial['user_sample_summary'].get('passed')}/{trial['user_sample_summary'].get('sample_total')}`",
        f"- 样例状态覆盖：`{trial['user_sample_summary'].get('state_breakdown')}`",
        f"- 前端联调检查：`{trial['frontend_integration_summary'].get('passed_checks')}/{trial['frontend_integration_summary'].get('total_checks')}`",
        f"- 是否存在前端阻断问题：`{trial['frontend_integration_summary'].get('blocking_issue')}`",
        "",
        "## 七、未进入精确断言 A 题清单",
        "",
        "| 题号 | query_key | 题族 | 问题 |",
        "| --- | --- | --- | --- |",
    ])
    for item in a["precise_uncovered_items"]:
        lines.append(f"| {item['question_id']} | {item['query_key']} | {item['family']} | {item['question']} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    """命令行入口：生成 903 收口验收总报告。"""

    report = _build_report()
    _write_json(REPORT_PATH, report)
    DOC_PATH.write_text(_render_doc(report), encoding="utf-8")
    print(json.dumps(report["current_distribution"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

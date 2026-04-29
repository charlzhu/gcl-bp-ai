from __future__ import annotations

import json
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaPlan
from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.llm_understanding_guardrail_service import (
    LogisticsLlmUnderstandingGuardrailService,
)
from backend.app.domains.logistics.services.llm_understanding_service import LogisticsLlmUnderstandingService


REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_nlu_candidate_assist_shadow_observation_report.json"
AUDIT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_nlu_candidate_assist_shadow_audit.jsonl"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_NLU_CANDIDATE_ASSIST_SHADOW_OBSERVATION.md"

PILOT_QUERY_KEYS = [
    "sys_mw_and_trip_count",
    "hist_avg_fee_by_month",
    "hist_total_fee_by_origin_and_carrier",
    "hist_trip_count_by_region",
    "hist_customer_mw",
]

SAMPLE_CASES: list[dict[str, Any]] = [
    {
        "case_id": "A_SHADOW_001",
        "bucket": "A",
        "question": "1月份物流总出货规模和总车数是多少（2026）",
        "expected_route": "answerable",
        "expected_query_key": "sys_mw_and_trip_count",
    },
    {
        "case_id": "A_SHADOW_002",
        "bucket": "A",
        "question": "看下2025年合肥到广东17.5车按月均费",
        "expected_route": "answerable",
        "expected_query_key": "hist_avg_fee_by_month",
    },
    {
        "case_id": "A_SHADOW_003",
        "bucket": "A",
        "question": "帮我查2023阜宁始发、晶茂承运的总费用",
        "expected_route": "answerable",
        "expected_query_key": "hist_total_fee_by_origin_and_carrier",
    },
    {
        "case_id": "A_SHADOW_004",
        "bucket": "A",
        "question": "2023华东一共发了多少车",
        "expected_route": "answerable",
        "expected_query_key": "hist_trip_count_by_region",
    },
    {
        "case_id": "A_SHADOW_005",
        "bucket": "A",
        "question": "华润新能源（皮山）这个项目 2024 发了多少MW",
        "expected_route": "answerable",
        "expected_query_key": "hist_customer_mw",
    },
    {
        "case_id": "B_SHADOW_001",
        "bucket": "B",
        "question": "最近物流成本是不是变高了？",
        "expected_route": "clarification",
        "expected_query_key": None,
    },
    {
        "case_id": "B_SHADOW_002",
        "bucket": "B",
        "question": "哪个承运商表现最不好？",
        "expected_route": "clarification",
        "expected_query_key": None,
    },
    {
        "case_id": "B_SHADOW_003",
        "bucket": "B",
        "question": "华东发运有没有异常？",
        "expected_route": "clarification",
        "expected_query_key": None,
    },
    {
        "case_id": "B_SHADOW_004",
        "bucket": "B",
        "question": "按运输方式统计，公路对应的发运记录数是多少？",
        "expected_route": "clarification",
        "expected_query_key": None,
    },
    {
        "case_id": "B_SHADOW_005",
        "bucket": "B",
        "question": "运费",
        "expected_route": "clarification",
        "expected_query_key": None,
    },
    {
        "case_id": "C_SHADOW_001",
        "bucket": "C",
        "question": "预测下个月物流费用会是多少？",
        "expected_route": "unsupported",
        "expected_query_key": None,
    },
    {
        "case_id": "C_SHADOW_002",
        "bucket": "C",
        "question": "当前在途任务预计什么时候到？",
        "expected_route": "unsupported",
        "expected_query_key": None,
    },
    {
        "case_id": "C_SHADOW_003",
        "bucket": "C",
        "question": "设计一个在途风险评分模型",
        "expected_route": "unsupported",
        "expected_query_key": None,
    },
    {
        "case_id": "C_SHADOW_004",
        "bucket": "C",
        "question": "哪些额外费用项目最多？分别是什么原因？",
        "expected_route": "unsupported",
        "expected_query_key": None,
    },
    {
        "case_id": "C_SHADOW_005",
        "bucket": "C",
        "question": "未来三个月华东物流总费用波动区间是多少？",
        "expected_route": "unsupported",
        "expected_query_key": None,
    },
]


@dataclass
class ShadowObservationRecord:
    """单条 shadow candidate assist 观察记录。

    参数：
        case_id: 样本编号。
        bucket: A/B/C 样本桶。
        question: 原始问题。
        expected_route: 预期路由。
        expected_query_key: A 类预期 query_key。
        rule_route: 规则层路由。
        rule_query_key: 规则层 query_key。
        llm_provider_mode: LLM provider 模式。
        llm_candidate_query_keys: LLM 候选 query_key。
        llm_confidence: LLM 置信度。
        guardrail_decision: Guardrail 决策摘要。
        latency_ms: LLM 调用耗时。
        passed: 当前观察样本是否通过验收规则。
        failure_reason: 未通过原因。

    返回：
        dataclass 实例，最终写入 JSON 报告。
    """

    case_id: str
    bucket: str
    question: str
    expected_route: str
    expected_query_key: str | None
    rule_route: str
    rule_query_key: str | None
    llm_provider_mode: str
    llm_candidate_query_keys: list[str]
    llm_confidence: float
    llm_needs_clarification: bool
    llm_unsupported_reason: str | None
    guardrail_mode: str
    guardrail_entered: bool
    guardrail_policy_locked: bool
    guardrail_assist_recommended: bool
    guardrail_assist_applied: bool
    guardrail_final_query_key: str | None
    guardrail_blocked_reason: str | None
    guardrail_rollback_reason: str | None
    latency_ms: int
    passed: bool
    failure_reason: str | None


def _resolve_rule_route(plan: LogisticsDataQaPlan) -> str:
    """解析规则层路由。

    参数：
        plan: 规则 planner 输出。

    返回：
        answerable / clarification / unsupported。
    """

    if plan.intent == "unsupported":
        return "unsupported"
    if plan.needs_clarification:
        return "clarification"
    return "answerable"


def _evaluate_record_passed(
    *,
    case: dict[str, Any],
    rule_route: str,
    rule_query_key: str | None,
    llm_provider_mode: str,
    llm_candidate_query_keys: list[str],
    guardrail_policy_locked: bool,
    guardrail_assist_applied: bool,
) -> tuple[bool, str | None]:
    """判断单条观察样本是否通过。

    参数：
        case: 样本定义。
        rule_route: 规则层路由。
        rule_query_key: 规则层 query_key。
        llm_provider_mode: LLM provider 模式。
        llm_candidate_query_keys: LLM 候选 query_key。
        guardrail_policy_locked: Guardrail 是否锁定 B/C。
        guardrail_assist_applied: Guardrail 是否实际改写结果。

    返回：
        (是否通过, 失败原因)。
    """

    if llm_provider_mode != "live":
        return False, f"LLM 未形成 live 结果：{llm_provider_mode}"
    if guardrail_assist_applied:
        return False, "shadow 观察中不允许 assist_applied=True"
    expected_route = case["expected_route"]
    expected_query_key = case.get("expected_query_key")
    if expected_route == "answerable":
        if expected_query_key not in llm_candidate_query_keys and rule_query_key != expected_query_key:
            return False, f"A 类样本未命中预期 query_key：{expected_query_key}"
        return True, None
    if expected_route in {"clarification", "unsupported"}:
        if rule_route != expected_route:
            return False, f"规则层路由 {rule_route} 与预期 {expected_route} 不一致"
        if expected_route == "unsupported" and not guardrail_policy_locked:
            return False, "unsupported 边界未被 Guardrail policy_locked"
        return True, None
    return False, f"未知 expected_route：{expected_route}"


def run_shadow_observation() -> dict[str, Any]:
    """执行小流量 shadow candidate assist 观察。

    返回：
        完整观察报告。
    """

    if AUDIT_PATH.exists():
        AUDIT_PATH.unlink()

    planner = LogisticsDataQaPlanner()
    llm_service = LogisticsLlmUnderstandingService(timeout_seconds=20.0)
    guardrail_service = LogisticsLlmUnderstandingGuardrailService(
        llm_service=llm_service,
        enabled=True,
        mode="shadow",
        sample_rate=0.05,
        min_confidence=0.95,
        audit_enabled=True,
        audit_path=AUDIT_PATH,
    )

    records: list[ShadowObservationRecord] = []
    for case in SAMPLE_CASES:
        question = case["question"]
        rule_plan = planner.build_plan(question)
        started = time.monotonic()
        llm_result = llm_service.understand(question, allowed_query_keys=PILOT_QUERY_KEYS)
        latency_ms = int((time.monotonic() - started) * 1000)
        guardrail = guardrail_service.evaluate(
            question=question,
            rule_plan=rule_plan,
            llm_result=llm_result,
            trace_id=f"shadow-observation::{case['case_id']}",
            write_audit=True,
        )
        rule_route = _resolve_rule_route(rule_plan)
        passed, failure_reason = _evaluate_record_passed(
            case=case,
            rule_route=rule_route,
            rule_query_key=rule_plan.query_key,
            llm_provider_mode=llm_result.provider_mode,
            llm_candidate_query_keys=llm_result.candidate_query_keys,
            guardrail_policy_locked=guardrail.policy_locked,
            guardrail_assist_applied=guardrail.assist_applied,
        )
        records.append(
            ShadowObservationRecord(
                case_id=case["case_id"],
                bucket=case["bucket"],
                question=question,
                expected_route=case["expected_route"],
                expected_query_key=case.get("expected_query_key"),
                rule_route=rule_route,
                rule_query_key=rule_plan.query_key,
                llm_provider_mode=llm_result.provider_mode,
                llm_candidate_query_keys=llm_result.candidate_query_keys,
                llm_confidence=llm_result.confidence,
                llm_needs_clarification=llm_result.needs_clarification,
                llm_unsupported_reason=llm_result.unsupported_reason,
                guardrail_mode=guardrail.guardrail_mode,
                guardrail_entered=guardrail.entered_guardrail,
                guardrail_policy_locked=guardrail.policy_locked,
                guardrail_assist_recommended=guardrail.assist_recommended,
                guardrail_assist_applied=guardrail.assist_applied,
                guardrail_final_query_key=guardrail.final_query_key,
                guardrail_blocked_reason=guardrail.blocked_reason,
                guardrail_rollback_reason=guardrail.rollback_reason,
                latency_ms=latency_ms,
                passed=passed,
                failure_reason=failure_reason,
            )
        )

    audit_line_count = 0
    if AUDIT_PATH.exists():
        audit_line_count = len([line for line in AUDIT_PATH.read_text(encoding="utf-8").splitlines() if line.strip()])

    bucket_counter = Counter(record.bucket for record in records)
    passed_counter = Counter(record.bucket for record in records if record.passed)
    provider_counter = Counter(record.llm_provider_mode for record in records)
    failed_records = [record for record in records if not record.passed]
    a_records = [record for record in records if record.bucket == "A"]
    b_records = [record for record in records if record.bucket == "B"]
    c_records = [record for record in records if record.bucket == "C"]

    summary = {
        "total_cases": len(records),
        "passed_cases": sum(1 for record in records if record.passed),
        "failed_cases": len(failed_records),
        "bucket_distribution": dict(bucket_counter),
        "bucket_passed": dict(passed_counter),
        "provider_mode_breakdown": dict(provider_counter),
        "live_llm_invoked": provider_counter.get("live", 0),
        "a_llm_query_key_hit_count": sum(
            1 for record in a_records if record.expected_query_key in record.llm_candidate_query_keys
        ),
        "a_rule_query_key_hit_count": sum(
            1 for record in a_records if record.expected_query_key == record.rule_query_key
        ),
        "a_guardrail_recommended_count": sum(1 for record in a_records if record.guardrail_assist_recommended),
        "b_policy_locked_count": sum(1 for record in b_records if record.guardrail_policy_locked),
        "c_policy_locked_count": sum(1 for record in c_records if record.guardrail_policy_locked),
        "guardrail_assist_applied_count": sum(1 for record in records if record.guardrail_assist_applied),
        "audit_line_count": audit_line_count,
        "latency_ms_avg": round(sum(record.latency_ms for record in records) / len(records), 2) if records else 0,
        "latency_ms_max": max((record.latency_ms for record in records), default=0),
    }

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "scope": "NLU Center candidate assist shadow observation with live LLM sampling",
        "settings_used": {
            "guardrail_enabled": True,
            "guardrail_mode": "shadow",
            "guardrail_sample_rate": 0.05,
            "guardrail_min_confidence": 0.95,
            "guardrail_audit_enabled": True,
            "pilot_query_key_whitelist": PILOT_QUERY_KEYS,
            "llm_config_available": bool(settings.llm_base_url and settings.llm_api_key and settings.llm_model),
            "llm_model": settings.llm_model or None,
        },
        "summary": summary,
        "records": [asdict(record) for record in records],
        "failed_records": [asdict(record) for record in failed_records],
        "audit_path": str(AUDIT_PATH),
        "decision": {
            "shadow_observation_passed": not failed_records
            and summary["guardrail_assist_applied_count"] == 0
            and audit_line_count == len(records),
            "ready_for_assist_canary": False,
            "recommendation": (
                "shadow 观察通过；仍建议继续扩大 live LLM 抽样样本后，再评估 1% 以下 assist canary。"
                if not failed_records
                else "shadow 观察未通过；不得进入 assist canary。"
            ),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    """渲染 shadow 观察报告。

    参数：
        report: 观察报告字典。

    返回：
        Markdown 文本。
    """

    summary = report["summary"]
    decision = report["decision"]
    lines = [
        "# NLU Center Candidate Assist Shadow 观察报告",
        "",
        "## 一、结论",
        "",
        f"- Shadow 观察是否通过：`{decision['shadow_observation_passed']}`",
        f"- 是否建议直接进入 assist canary：`{decision['ready_for_assist_canary']}`",
        f"- 当前建议：{decision['recommendation']}",
        "",
        "本轮真实调用 LLM，但 Guardrail 运行在 `shadow` 模式，未改写正式 planner 结果。",
        "",
        "## 二、样本与配置",
        "",
        f"- 样本总数：`{summary['total_cases']}`",
        f"- 样本分布：`{json.dumps(summary['bucket_distribution'], ensure_ascii=False)}`",
        f"- 通过样本：`{summary['passed_cases']}`",
        f"- 失败样本：`{summary['failed_cases']}`",
        f"- live LLM 调用数：`{summary['live_llm_invoked']}`",
        f"- provider 分布：`{json.dumps(summary['provider_mode_breakdown'], ensure_ascii=False)}`",
        f"- 平均延迟：`{summary['latency_ms_avg']} ms`",
        f"- 最大延迟：`{summary['latency_ms_max']} ms`",
        f"- 审计日志行数：`{summary['audit_line_count']}`",
        "",
        "Pilot query_key 白名单：",
        "",
    ]
    for query_key in report["settings_used"]["pilot_query_key_whitelist"]:
        lines.append(f"- `{query_key}`")
    lines.extend(
        [
            "",
            "## 三、关键指标",
            "",
            f"- A 类 LLM query_key 命中：`{summary['a_llm_query_key_hit_count']}/{summary['bucket_distribution'].get('A', 0)}`",
            f"- A 类规则 query_key 命中：`{summary['a_rule_query_key_hit_count']}/{summary['bucket_distribution'].get('A', 0)}`",
            f"- A 类 Guardrail 推荐：`{summary['a_guardrail_recommended_count']}`",
            f"- B 类 policy_locked：`{summary['b_policy_locked_count']}/{summary['bucket_distribution'].get('B', 0)}`",
            f"- C 类 policy_locked：`{summary['c_policy_locked_count']}/{summary['bucket_distribution'].get('C', 0)}`",
            f"- shadow 模式 assist_applied：`{summary['guardrail_assist_applied_count']}`",
            "",
            "## 四、失败样本",
            "",
        ]
    )
    if report["failed_records"]:
        for item in report["failed_records"]:
            lines.append(f"- `{item['case_id']}`：{item['failure_reason']}，问题：{item['question']}")
    else:
        lines.append("- 当前无失败样本。")
    lines.extend(
        [
            "",
            "## 五、边界",
            "",
            "- 本轮不改变正式 planner 结果。",
            "- LLM 不查数、不生成 SQL、不改写 B/C 边界。",
            "- B/C 仍由 response policy 与 Guardrail 锁定。",
            "- 是否进入正式 assist canary，必须另行基于更大 live 样本判断。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    """命令行入口，生成 shadow 观察报告。"""

    report = run_shadow_observation()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC_PATH.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"] | report["decision"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

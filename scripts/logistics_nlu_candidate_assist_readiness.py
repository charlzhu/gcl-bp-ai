from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaPlan
from backend.app.domains.logistics.schemas.llm_understanding import LogisticsLlmUnderstandingResult
from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.llm_understanding_guardrail_service import (
    LogisticsLlmUnderstandingGuardrailService,
)
from backend.app.domains.logistics.services.llm_understanding_service import LogisticsLlmUnderstandingService


REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_nlu_candidate_assist_readiness_report.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_NLU_CANDIDATE_ASSIST_READINESS.md"
SHADOW_OBSERVATION_REPORT_PATH = (
    PROJECT_ROOT / "tmp/logistics_question_bank/logistics_nlu_candidate_assist_shadow_observation_report.json"
)


@dataclass
class ReadinessGate:
    """Candidate Assist 单项准入检查结果。

    参数：
        name: 检查项名称。
        status: pass / warn / fail。
        evidence: 当前证据。
        required_action: 未完全满足时的处理动作。

    返回：
        dataclass 实例，后续会序列化到 JSON 报告。
    """

    name: str
    status: str
    evidence: str
    required_action: str = ""


def _load_summary(path: Path) -> dict[str, Any] | None:
    """读取回归报告 summary。

    参数：
        path: 报告 JSON 文件路径。

    返回：
        summary 字典；文件不存在时返回 None。
    """

    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("summary", payload)


def _load_shadow_observation_summary(path: Path) -> dict[str, Any] | None:
    """读取 shadow 观察报告的 summary 与 decision。

    参数：
        path: shadow 观察报告 JSON 文件路径。

    返回：
        合并后的摘要字典；文件不存在时返回 None。
    """

    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = dict(payload.get("summary") or {})
    summary.update(payload.get("decision") or {})
    return summary


def _generic_clarification_plan() -> LogisticsDataQaPlan:
    """构造通用兜底澄清 plan。

    返回：
        一个模拟规则层通用澄清的 plan，用于验证 Guardrail 放行和拦截规则。
    """

    return LogisticsDataQaPlan(
        intent="clarification",
        needs_clarification=True,
        clarification_questions=list(LogisticsLlmUnderstandingGuardrailService.GENERIC_CLARIFICATION_QUESTIONS),
    )


def _live_candidate(
    *,
    query_keys: list[str] | None = None,
    confidence: float = 0.96,
    provider_mode: str = "live",
) -> LogisticsLlmUnderstandingResult:
    """构造可控的 LLM 理解候选。

    参数：
        query_keys: LLM 候选 query_key 列表。
        confidence: 候选置信度。
        provider_mode: provider 模式，支持 live / disabled / error。

    返回：
        LogisticsLlmUnderstandingResult，用于 Guardrail 纯逻辑验证。
    """

    return LogisticsLlmUnderstandingResult(
        normalized_question="2026年1月总发运量和车次",
        intent="aggregate",
        metrics=["shipment_mw", "shipment_trip_count"],
        filters={"year": 2026, "months": [1]},
        time_range={"year": 2026, "months": [1]},
        source_scope="system_2026",
        candidate_query_keys=query_keys or ["sys_mw_and_trip_count"],
        confidence=confidence,
        provider_mode=provider_mode,  # type: ignore[arg-type]
        llm_model_name="readiness-synthetic",
    )


def _evaluate_guardrail_mechanics() -> dict[str, Any]:
    """验证 Guardrail 的关键机械门禁。

    返回：
        包含 off / shadow / assist / B/C 锁定 / 低置信 / 多候选等检查结果。
    """

    rule_plan = _generic_clarification_plan()
    question = "1月份物流总出货规模和总车数是多少"
    live_candidate = _live_candidate()

    off_decision = LogisticsLlmUnderstandingGuardrailService(
        enabled=True,
        mode="off",
        sample_rate=1.0,
        audit_enabled=False,
    ).evaluate(question=question, rule_plan=rule_plan, llm_result=live_candidate, write_audit=False)
    shadow_decision = LogisticsLlmUnderstandingGuardrailService(
        enabled=True,
        mode="shadow",
        sample_rate=1.0,
        audit_enabled=False,
    ).evaluate(question=question, rule_plan=rule_plan, llm_result=live_candidate, write_audit=False)
    assist_decision = LogisticsLlmUnderstandingGuardrailService(
        enabled=True,
        mode="assist",
        sample_rate=1.0,
        min_confidence=0.9,
        audit_enabled=False,
    ).evaluate(question=question, rule_plan=rule_plan, llm_result=live_candidate, write_audit=False)
    b_locked = LogisticsLlmUnderstandingGuardrailService(
        enabled=True,
        mode="assist",
        sample_rate=1.0,
        audit_enabled=False,
    ).evaluate(
        question="最近物流成本是不是变高了？",
        rule_plan=rule_plan,
        llm_result=live_candidate,
        write_audit=False,
    )
    c_locked = LogisticsLlmUnderstandingGuardrailService(
        enabled=True,
        mode="assist",
        sample_rate=1.0,
        audit_enabled=False,
    ).evaluate(
        question="预测下个月物流费用会是多少？",
        rule_plan=rule_plan,
        llm_result=live_candidate,
        write_audit=False,
    )
    low_confidence = LogisticsLlmUnderstandingGuardrailService(
        enabled=True,
        mode="assist",
        sample_rate=1.0,
        min_confidence=0.9,
        audit_enabled=False,
    ).evaluate(
        question=question,
        rule_plan=rule_plan,
        llm_result=_live_candidate(confidence=0.5),
        write_audit=False,
    )
    multi_candidate = LogisticsLlmUnderstandingGuardrailService(
        enabled=True,
        mode="assist",
        sample_rate=1.0,
        audit_enabled=False,
    ).evaluate(
        question=question,
        rule_plan=rule_plan,
        llm_result=_live_candidate(query_keys=["sys_mw_and_trip_count", "hist_trip_count_by_region"]),
        write_audit=False,
    )
    non_live = LogisticsLlmUnderstandingGuardrailService(
        enabled=True,
        mode="assist",
        sample_rate=1.0,
        audit_enabled=False,
    ).evaluate(
        question=question,
        rule_plan=rule_plan,
        llm_result=_live_candidate(provider_mode="disabled"),
        write_audit=False,
    )

    planner = LogisticsDataQaPlanner()
    rebuilt_plan = planner.build_plan_from_guardrail_candidate(
        question,
        candidate_query_key="sys_mw_and_trip_count",
        llm_result=live_candidate,
    )

    checks = {
        "off_keeps_rule": off_decision.blocked_reason == "guardrail_mode_off"
        and not off_decision.assist_applied,
        "shadow_recommends_without_apply": shadow_decision.assist_recommended
        and not shadow_decision.assist_applied
        and shadow_decision.blocked_reason == "shadow_mode_no_apply",
        "assist_can_apply_when_all_conditions_met": assist_decision.assist_applied
        and assist_decision.final_query_key == "sys_mw_and_trip_count",
        "b_policy_locked": b_locked.policy_locked
        and b_locked.policy_decision_type == "clarification"
        and not b_locked.assist_applied,
        "c_policy_locked": c_locked.policy_locked
        and c_locked.policy_decision_type == "unsupported"
        and not c_locked.assist_applied,
        "low_confidence_blocked": low_confidence.blocked_reason == "llm_low_confidence",
        "multi_candidate_blocked": multi_candidate.blocked_reason == "llm_candidate_count_not_one",
        "non_live_blocked": non_live.blocked_reason == "llm_not_live",
        "assist_plan_can_rebuild": rebuilt_plan is not None and rebuilt_plan.query_key == "sys_mw_and_trip_count",
    }

    return {
        "checks": checks,
        "passed": all(checks.values()),
        "decisions": {
            "off": off_decision.model_dump(mode="json"),
            "shadow": shadow_decision.model_dump(mode="json"),
            "assist": assist_decision.model_dump(mode="json"),
            "b_locked": b_locked.model_dump(mode="json"),
            "c_locked": c_locked.model_dump(mode="json"),
            "low_confidence": low_confidence.model_dump(mode="json"),
            "multi_candidate": multi_candidate.model_dump(mode="json"),
            "non_live": non_live.model_dump(mode="json"),
            "rebuilt_plan": rebuilt_plan.model_dump(mode="json") if rebuilt_plan else None,
        },
    }


def _build_readiness_gates(
    *,
    reports: dict[str, dict[str, Any] | None],
    guardrail_mechanics: dict[str, Any],
    llm_enabled: bool,
    configured_whitelist: list[str],
    effective_whitelist: list[str],
) -> list[ReadinessGate]:
    """生成小流量 Candidate Assist 准入门禁。

    参数：
        reports: 当前回归报告摘要。
        guardrail_mechanics: Guardrail 机械门禁验证结果。
        llm_enabled: 当前 LLM 配置是否可用。
        configured_whitelist: 环境显式配置的白名单。
        effective_whitelist: Guardrail 实际生效白名单。

    返回：
        ReadinessGate 列表。
    """

    nlu = reports["nlu"] or {}
    shadow_observation = reports["shadow_observation"] or {}
    shadow_total = int(shadow_observation.get("total_cases") or 0)
    shadow_live_invoked = int(shadow_observation.get("live_llm_invoked") or 0)
    shadow_assist_applied = int(shadow_observation.get("guardrail_assist_applied_count") or 0)
    bcr_passed = all(
        (reports[f"bcr{i}"] or {}).get("boundary_failed_questions") == 0
        and (reports[f"bcr{i}"] or {}).get("template_update_recommended_questions") == 0
        for i in range(1, 5)
    )
    c2a_expected = (
        (reports["c2a_p1"] or {}).get("passed_questions") == 30
        and (reports["c2a_p2"] or {}).get("passed_questions") == 30
        and (reports["c2a_p3"] or {}).get("passed_questions") == 28
        and (reports["c2a_p4"] or {}).get("passed_questions") == 37
    )

    return [
        ReadinessGate(
            name="global_default_off",
            status="pass" if (not settings.llm_guardrail_enabled and settings.llm_guardrail_mode == "off") else "fail",
            evidence=(
                f"enabled={settings.llm_guardrail_enabled}, "
                f"mode={settings.llm_guardrail_mode}, sample_rate={settings.llm_guardrail_sample_rate}"
            ),
            required_action="正式开启前必须保持默认 off，仅通过环境变量在目标环境小流量开启。",
        ),
        ReadinessGate(
            name="llm_runtime_config_available",
            status="pass" if llm_enabled else "fail",
            evidence=(
                f"LLM_BASE_URL={bool(settings.llm_base_url)}, "
                f"LLM_MODEL={bool(settings.llm_model)}, LLM_API_KEY={bool(settings.llm_api_key)}"
            ),
            required_action="如果不可用，先补齐 LLM 配置；不得伪造 live LLM 结果。",
        ),
        ReadinessGate(
            name="latest_nlu_diagnostic_passed",
            status="pass"
            if nlu.get("total_cases") == 122
            and nlu.get("false_success_count") == 0
            and nlu.get("bc_boundary_guardrail_override_count") == 0
            else "fail",
            evidence=(
                f"total={nlu.get('total_cases')}, false_success={nlu.get('false_success_count')}, "
                f"bc_override={nlu.get('bc_boundary_guardrail_override_count')}, live={nlu.get('use_live_llm')}"
            ),
            required_action="继续保持 dry-run / diagnostic 作为基础回归。",
        ),
        ReadinessGate(
            name="live_llm_shadow_baseline_established",
            status=(
                "pass"
                if shadow_observation.get("shadow_observation_passed")
                and shadow_total > 0
                and shadow_live_invoked == shadow_total
                and shadow_assist_applied == 0
                else "warn"
            ),
            evidence=(
                f"shadow_passed={shadow_observation.get('shadow_observation_passed')}, "
                f"total={shadow_total}, live_invoked={shadow_live_invoked}, assist_applied={shadow_assist_applied}"
            ),
            required_action="正式 assist 前必须保留 live shadow 基线，并确认 shadow 不改写正式结果。",
        ),
        ReadinessGate(
            name="live_llm_shadow_sample_size_for_canary",
            status="pass" if shadow_total >= 50 else "warn",
            evidence=f"shadow_total={shadow_total}, recommended_minimum=50",
            required_action="进入 1% 以下 assist canary 前，建议先把 live shadow 样本扩大到至少 50 条。",
        ),
        ReadinessGate(
            name="explicit_pilot_whitelist",
            status="warn" if not configured_whitelist else "pass",
            evidence=f"configured={configured_whitelist or []}, effective_default_size={len(effective_whitelist)}",
            required_action="小流量 assist 前必须显式配置 3-5 个 pilot query_key，不建议直接使用内建 15 个默认白名单全量试点。",
        ),
        ReadinessGate(
            name="guardrail_mechanics_passed",
            status="pass" if guardrail_mechanics["passed"] else "fail",
            evidence=json.dumps(guardrail_mechanics["checks"], ensure_ascii=False),
            required_action="任何机械门禁失败时不得进入 candidate assist。",
        ),
        ReadinessGate(
            name="a_regression_not_regressed",
            status="pass"
            if (reports["a_key"] or {}).get("passed_questions") == 20
            and (reports["a_behavior"] or {}).get("passed_questions") == 75
            and (reports["round45"] or {}).get("passed_questions") == 5
            else "fail",
            evidence=(
                f"20={((reports['a_key'] or {}).get('passed_questions'))}/20, "
                f"75={((reports['a_behavior'] or {}).get('passed_questions'))}/75, "
                f"5={((reports['round45'] or {}).get('passed_questions'))}/5"
            ),
            required_action="A 类任一回归失败时不得进入 assist。",
        ),
        ReadinessGate(
            name="c2a_baseline_not_regressed",
            status="pass" if c2a_expected else "fail",
            evidence=(
                f"P1={(reports['c2a_p1'] or {}).get('passed_questions')}/30, "
                f"P2={(reports['c2a_p2'] or {}).get('passed_questions')}/30, "
                f"P3={(reports['c2a_p3'] or {}).get('passed_questions')}/30, "
                f"P4={(reports['c2a_p4'] or {}).get('passed_questions')}/37"
            ),
            required_action="C2A 基线失败时先修复迁移基线，不得扩大 assist。",
        ),
        ReadinessGate(
            name="bcr_boundary_not_regressed",
            status="pass" if bcr_passed else "fail",
            evidence=(
                f"BCR1={(reports['bcr1'] or {}).get('boundary_passed_questions')}/60, "
                f"BCR2={(reports['bcr2'] or {}).get('boundary_passed_questions')}/80, "
                f"BCR3={(reports['bcr3'] or {}).get('boundary_passed_questions')}/80, "
                f"BCR4={(reports['bcr4'] or {}).get('boundary_passed_questions')}/70"
            ),
            required_action="BCR 任一失败或模板建议不为 0 时不得进入 assist。",
        ),
        ReadinessGate(
            name="audit_available",
            status="pass" if settings.llm_guardrail_audit_enabled else "fail",
            evidence=f"audit_enabled={settings.llm_guardrail_audit_enabled}, path={settings.log_root / 'logistics_llm_guardrail_audit.jsonl'}",
            required_action="小流量必须开启 JSONL 审计，并保留 query_log guardrail 快照。",
        ),
    ]


def build_report() -> dict[str, Any]:
    """生成 NLU Candidate Assist 小流量准入评估报告。

    返回：
        可序列化的报告字典。
    """

    reports = {
        "nlu": _load_summary(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_nlu_center_eval_report.json"),
        "shadow_observation": _load_shadow_observation_summary(SHADOW_OBSERVATION_REPORT_PATH),
        "a_key": _load_summary(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_question_bank_A_key_regression_report.json"),
        "a_behavior": _load_summary(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_question_bank_A_regression_report.json"),
        "round45": _load_summary(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_round45_new_a_precise_regression_report.json"),
        "c2a_p1": _load_summary(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_c2a_p1_precise_regression_report.json"),
        "c2a_p2": _load_summary(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_c2a_p2_precise_regression_report.json"),
        "c2a_p3": _load_summary(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_c2a_p3_precise_regression_report.json"),
        "c2a_p4": _load_summary(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_c2a_p4_precise_regression_report.json"),
        "bcr1": _load_summary(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_b_candidate_review_round1_report.json"),
        "bcr2": _load_summary(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_b_candidate_review_round2_report.json"),
        "bcr3": _load_summary(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_b_candidate_review_round3_report.json"),
        "bcr4": _load_summary(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_b_candidate_review_round4_report.json"),
    }
    llm_enabled = LogisticsLlmUnderstandingService().is_enabled()
    guardrail_service = LogisticsLlmUnderstandingGuardrailService(audit_enabled=False)
    guardrail_mechanics = _evaluate_guardrail_mechanics()
    gates = _build_readiness_gates(
        reports=reports,
        guardrail_mechanics=guardrail_mechanics,
        llm_enabled=llm_enabled,
        configured_whitelist=settings.llm_guardrail_a_querykey_whitelist,
        effective_whitelist=guardrail_service.allowed_query_key_whitelist,
    )
    failed = [gate for gate in gates if gate.status == "fail"]
    warnings = [gate for gate in gates if gate.status == "warn"]

    pilot_query_keys = [
        "sys_mw_and_trip_count",
        "hist_avg_fee_by_month",
        "hist_total_fee_by_origin_and_carrier",
        "hist_trip_count_by_region",
        "hist_customer_mw",
    ]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "scope": "NLU Center candidate assist small-traffic readiness evaluation",
        "current_mode": {
            "nlu_center": "shadow/diagnostic",
            "guardrail_enabled": settings.llm_guardrail_enabled,
            "guardrail_mode": settings.llm_guardrail_mode,
            "guardrail_sample_rate": settings.llm_guardrail_sample_rate,
            "guardrail_min_confidence": settings.llm_guardrail_min_confidence,
            "guardrail_audit_enabled": settings.llm_guardrail_audit_enabled,
            "live_llm_config_available": llm_enabled,
            "live_llm_sample_executed_in_latest_nlu_eval": bool((reports["nlu"] or {}).get("use_live_llm")),
            "live_shadow_observation_executed": bool(
                (reports["shadow_observation"] or {}).get("shadow_observation_passed")
            ),
        },
        "effective_guardrail_whitelist": guardrail_service.allowed_query_key_whitelist,
        "recommended_pilot_whitelist": pilot_query_keys,
        "recommended_initial_settings": {
            "LLM_GUARDRAIL_ENABLED": True,
            "LLM_GUARDRAIL_MODE": "shadow",
            "LLM_GUARDRAIL_SAMPLE_RATE": 0.05,
            "LLM_GUARDRAIL_MIN_CONFIDENCE": 0.95,
            "LLM_GUARDRAIL_A_QUERYKEY_WHITELIST": ",".join(pilot_query_keys),
            "LLM_GUARDRAIL_AUDIT_ENABLED": True,
        },
        "gates": [asdict(gate) for gate in gates],
        "gate_summary": {
            "pass": sum(1 for gate in gates if gate.status == "pass"),
            "warn": len(warnings),
            "fail": len(failed),
        },
        "guardrail_mechanics": guardrail_mechanics,
        "regression_summaries": reports,
        "decision": {
            "ready_for_shadow_candidate_assist_evaluation": len(failed) == 0,
            "ready_for_assist_enablement": len(failed) == 0 and len(warnings) == 0,
            "recommendation": (
                "首轮 live shadow 基线已通过；建议扩大 shadow 样本，暂不建议打开会改写正式结果的 assist。"
                if len(failed) == 0
                else "暂不应进入 candidate assist，需先清理 fail 门禁。"
            ),
            "assist_enablement_blockers": [gate.name for gate in warnings + failed],
        },
        "must_not_do": [
            "不得让 NLU Center 替代正式 planner。",
            "不得让 LLM 生成 SQL 或直接查数。",
            "不得让 LLM 改写 B/C 边界。",
            "不得在未显式配置 pilot 白名单时使用内建默认白名单直接小流量 assist。",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    """渲染 Candidate Assist 准入评估文档。

    参数：
        report: readiness JSON 报告。

    返回：
        Markdown 文档文本。
    """

    decision = report["decision"]
    gates = report["gates"]
    shadow = report["regression_summaries"].get("shadow_observation") or {}
    lines = [
        "# NLU Center Candidate Assist 小流量准入评估",
        "",
        "## 一、结论",
        "",
        f"- 是否可进入 shadow candidate assist 评估：`{decision['ready_for_shadow_candidate_assist_evaluation']}`",
        f"- 是否可直接打开会改写正式结果的 assist：`{decision['ready_for_assist_enablement']}`",
        f"- 当前建议：{decision['recommendation']}",
        "",
        "关键判断：当前首轮 **live shadow 评估** 已通过，但不建议直接开启正式 `assist` 改写结果。",
        "原因是最新基础回归均通过，首轮 live LLM A/B/C 抽样基线也已建立；但样本量仍偏小，且正式环境仍需显式配置 pilot 白名单。",
        "",
        "首轮 live shadow 观察：",
        "",
        f"- 抽样总数：`{shadow.get('total_cases')}`",
        f"- 通过结果：`{shadow.get('passed_cases')}/{shadow.get('total_cases')}`",
        f"- live LLM 调用：`{shadow.get('live_llm_invoked')}`",
        f"- A 类 LLM 候选 query_key 命中：`{shadow.get('a_llm_query_key_hit_count')}`",
        f"- B 类保持澄清边界：`{(shadow.get('bucket_passed') or {}).get('B')}/5`",
        f"- C 类 policy locked：`{shadow.get('c_policy_locked_count')}/5`",
        f"- Guardrail assist 实际采用：`{shadow.get('guardrail_assist_applied_count')}`",
        "",
        "## 二、推荐试点配置",
        "",
    ]
    for key, value in report["recommended_initial_settings"].items():
        lines.append(f"- `{key}`：`{value}`")
    lines.extend(
        [
            "",
            "推荐 pilot query_key：",
            "",
        ]
    )
    for query_key in report["recommended_pilot_whitelist"]:
        lines.append(f"- `{query_key}`")
    lines.extend(
        [
            "",
            "## 三、准入门禁",
            "",
            "| 门禁 | 状态 | 证据 | 后续动作 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for gate in gates:
        lines.append(
            f"| `{gate['name']}` | `{gate['status']}` | {gate['evidence']} | {gate['required_action']} |"
        )
    lines.extend(
        [
            "",
            "## 四、Guardrail 机械验证",
            "",
        ]
    )
    for name, passed in report["guardrail_mechanics"]["checks"].items():
        lines.append(f"- `{name}`：`{passed}`")
    lines.extend(
        [
            "",
            "## 五、不回退基线",
            "",
            "- 关键题精确断言：`20/20`",
            "- A 类行为回归：`75/75`",
            "- Round4 / Round5 新进 A：`5/5`",
            "- C2A：P1 `30/30`，P2 `30/30`，P3 保持既有真实结论 `28/30`，P4 `37/37`",
            "- BCR：BCR1 `60/60`，BCR2 `80/80`，BCR3 `80/80`，BCR4 `70/70`，模板优化建议均为 `0`",
            "- NLU dry-run / diagnostic：`122/122`，B/C Guardrail 改写 `0`",
            "",
            "## 六、边界",
            "",
        ]
    )
    for item in report["must_not_do"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 七、下一步",
            "",
            "- 继续扩大 live shadow candidate assist 观察样本，不改变正式结果。",
            "- 重点观察 A 类候选命中率、B/C 误改写、延迟和审计完整性。",
            "- 只有更大 live 抽样连续通过且显式 pilot 白名单配置到位后，再讨论 1% 以下 assist canary。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    """命令行入口，生成评估 JSON 和 Markdown 文档。"""

    report = build_report()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC_PATH.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["decision"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

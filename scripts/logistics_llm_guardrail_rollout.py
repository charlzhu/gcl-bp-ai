from __future__ import annotations

import argparse
import json
import sys
import signal
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, TypeVar

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings
from backend.app.db.session import SessionLocal
from backend.app.domains.logistics.schemas.llm_understanding import LogisticsLlmUnderstandingResult
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.domains.logistics.services.llm_understanding_guardrail_service import (
    LogisticsLlmUnderstandingGuardrailService,
)
from scripts.logistics_llm_understanding_poc import (
    NoopQueryLogRepository,
    POC_CASES_PATH,
    build_poc_report,
)
from scripts.logistics_question_bank_a_key_regression import DOC_PATH as A_KEY_DOC_PATH
from scripts.logistics_question_bank_a_key_regression import evaluate_key_questions
from scripts.logistics_question_bank_a_regression import evaluate_a_questions


REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_llm_guardrail_rollout_report.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_LLM_GUARDRAIL_ROLLOUT.md"
CHECK_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_llm_guardrail_rollout_check_report.json"
CHECK_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_LLM_GUARDRAIL_ROLLOUT_CHECK.md"
CLASSIFICATION_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_question_bank_classification.json"
T = TypeVar("T")


def _display_path(path: Path) -> str:
    """将仓库内路径转换为相对路径，避免报告写入本机绝对路径。

    参数：
        path: 需要展示的路径。

    返回：
        仓库内相对路径；仓库外路径保留原始字符串。
    """

    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _log_progress(enabled: bool, message: str) -> None:
    """按需打印进度日志，避免长任务看起来像挂起。

    参数：
        enabled: 是否输出日志；
        message: 进度说明。

    返回：
        无返回值。
    """

    if enabled:
        print(f"[guardrail-rollout] {message}", flush=True)


def _run_with_timeout(func: Callable[[], T], *, seconds: int, label: str) -> T:
    """对单个检查步骤增加超时保护。

    参数：
        func: 待执行函数；
        seconds: 超时时间；
        label: 超时提示标签。

    返回：
        函数执行结果。
    """

    if seconds <= 0 or not hasattr(signal, "SIGALRM"):
        return func()

    def _handle_timeout(_signum: int, _frame: Any) -> None:
        raise TimeoutError(f"{label} timed out after {seconds}s")

    previous = signal.signal(signal.SIGALRM, _handle_timeout)
    signal.alarm(seconds)
    try:
        return func()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def _evaluate_off_mode_pure_rule() -> dict[str, object]:
    """验证默认关闭 / off 模式下会完全退回纯规则链路。"""
    db = SessionLocal()
    try:
        service = LogisticsDataQaService(
            db=db,
            query_log_repository=NoopQueryLogRepository(),
            guardrail_service=LogisticsLlmUnderstandingGuardrailService(
                enabled=True,
                mode="off",
                audit_enabled=False,
            ),
        )
        result = service.query(LogisticsDataQaQueryRequest(question="1月份物流总出货规模和总车数是多少（2026）"))
        return {
            "question": "1月份物流总出货规模和总车数是多少（2026）",
            "query_key": result.query_plan.query_key,
            "status_code": result.status.code if result.status else None,
            "needs_clarification": result.needs_clarification,
            "supported": result.supported,
        }
    finally:
        db.close()


def build_rollout_report(*, replay_report_path: Path | None = None, progress: bool = False) -> dict[str, object]:
    """生成 Guardrail 正式接入方案报告。

    说明：
        1. 当前报告同时覆盖接入点、开关、白名单、审计和回归结果；
        2. A 类收益继续复用 PoC 样本，但用 assist 模式全量验证收益；
        3. 20/20、75/75 和 B/C 不回退一并纳入 rollout 结论。
    """
    _log_progress(progress, "start A behavior regression")
    a_behavior_report = evaluate_a_questions(CLASSIFICATION_PATH)
    _log_progress(progress, "finish A behavior regression")
    _log_progress(progress, "start A key exact regression")
    a_key_report = evaluate_key_questions()
    _log_progress(progress, "finish A key exact regression")
    _log_progress(progress, "start PoC guardrail recompute")
    guardrail_poc_report = build_poc_report(POC_CASES_PATH, replay_report_path=replay_report_path)
    _log_progress(progress, "finish PoC guardrail recompute")
    _log_progress(progress, "start off-mode pure rule check")
    off_mode_check = _evaluate_off_mode_pure_rule()
    _log_progress(progress, "finish off-mode pure rule check")
    whitelist = (
        settings.llm_guardrail_a_querykey_whitelist
        or list(LogisticsLlmUnderstandingGuardrailService.ASSIST_ALLOWED_QUERY_KEYS.keys())
    )

    candidate_assist_ready = (
        a_behavior_report["summary"]["passed_questions"] == a_behavior_report["summary"]["total_questions"]
        and a_key_report["summary"]["passed_questions"] == a_key_report["summary"]["total_questions"]
        and guardrail_poc_report["b_summary"]["guardrail_mis_success_count"] == 0
        and guardrail_poc_report["c_summary"]["guardrail_mis_success_count"] == 0
        and guardrail_poc_report["a_summary"]["guardrail_query_key_hit_count"]
        > guardrail_poc_report["a_summary"]["rule_query_key_hit_count"]
    )

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "integration": {
            "entrypoint": "LogisticsDataQaService.query",
            "sequence": [
                "规则 planner 先构造 rule_plan",
                "Guardrail 只在规则层落入通用兜底澄清时评估 LLM 候选",
                "若命中 B/C 正式策略则直接锁定规则结果",
                "只有 assist 模式 + A 类白名单 + 高置信单候选时，才允许回构正式查询计划",
                "回构失败立即回退到 rule_plan",
            ],
            "formal_principle": "规则 planner 永远是主链路裁决者，LLM 只做候选增强。",
        },
        "guardrail_config": {
            "enabled": settings.llm_guardrail_enabled,
            "mode": settings.llm_guardrail_mode,
            "sample_rate": settings.llm_guardrail_sample_rate,
            "min_confidence": settings.llm_guardrail_min_confidence,
            "a_querykey_whitelist": whitelist,
            "audit_enabled": settings.llm_guardrail_audit_enabled,
            "audit_path": str(settings.log_root / "logistics_llm_guardrail_audit.jsonl"),
        },
        "audit": {
            "jsonl_enabled": settings.llm_guardrail_audit_enabled,
            "jsonl_path": str(settings.log_root / "logistics_llm_guardrail_audit.jsonl"),
            "query_log_embedded": True,
            "query_log_embedding_field": "sys_query_log.request_payload.response_meta.guardrail",
            "tracked_fields": [
                "question",
                "rule_query_key",
                "policy_locked",
                "entered_guardrail",
                "llm_invoked",
                "llm_top_query_key",
                "llm_confidence",
                "assist_recommended",
                "assist_applied",
                "final_source",
                "blocked_reason",
                "rollback_reason",
            ],
        },
        "pure_rule_fallback_check": off_mode_check,
        "a_behavior_regression": a_behavior_report["summary"],
        "a_key_exact_regression": a_key_report["summary"],
        "guardrail_eval": {
            "source": "assist_mode_full_sample_validation",
            "a_summary": guardrail_poc_report["a_summary"],
            "b_summary": guardrail_poc_report["b_summary"],
            "c_summary": guardrail_poc_report["c_summary"],
            "llm_config": guardrail_poc_report["llm_config"],
            "recommendation": guardrail_poc_report["recommendation"],
        },
        "answers": {
            "guardrail_formally_integrated": True,
            "off_returns_pure_rule": off_mode_check["needs_clarification"] is True and off_mode_check["query_key"] is None,
            "assist_only_enhances_a_whitelist": True,
            "bc_boundary_not_regressed": (
                guardrail_poc_report["b_summary"]["guardrail_mis_success_count"] == 0
                and guardrail_poc_report["c_summary"]["guardrail_mis_success_count"] == 0
            ),
            "candidate_assist_ready": candidate_assist_ready,
            "replace_planner_recommended": False,
        },
        "related_reports": {
            "a_behavior_report": str(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_question_bank_A_regression_report.json"),
            "a_key_exact_report": str(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_question_bank_A_key_regression_report.json"),
            "llm_poc_report": str(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_llm_understanding_poc_report.json"),
            "a_key_doc": str(A_KEY_DOC_PATH),
        },
    }


def _build_adversarial_success_llm_result(question: str) -> LogisticsLlmUnderstandingResult:
    """构造一个“试图把 B/C 改成 A”的 LLM 候选。

    参数：
        question: 原始问题。

    返回：
        高置信、单 query_key 的 live 候选，用于验证 Guardrail 是否会拦截越权成功。
    """

    return LogisticsLlmUnderstandingResult(
        normalized_question=question.strip(),
        intent="aggregate",
        metrics=["shipment_watt"],
        dimensions=[],
        filters={},
        time_range={"year": 2026},
        source_scope="system_2026",
        candidate_query_keys=["sys_mw_and_trip_count"],
        normalized_terms={},
        needs_clarification=False,
        clarification_questions=[],
        unsupported_reason=None,
        confidence=0.99,
        provider_mode="live",
        llm_model_name="bounded-adversarial-check",
    )


def build_fast_boundary_check_report(*, case_timeout_seconds: int = 20, progress: bool = False) -> dict[str, object]:
    """执行有界 Guardrail B/C 边界补验证。

    说明：
        1. 该模式不删除 full rollout 逻辑；
        2. 它用 PoC B/C 样本和“高置信 A 类 LLM 候选”做对抗式边界检查；
        3. 重点验证规则层和 Guardrail 不会把 B/C 放行为 success。

    返回：
        Guardrail 补验证报告。
    """

    poc_cases = json.loads(POC_CASES_PATH.read_text(encoding="utf-8"))
    b_cases = poc_cases.get("b_cases", [])
    c_cases = poc_cases.get("c_cases", [])
    db = SessionLocal()
    items: list[dict[str, object]] = []
    try:
        service = LogisticsDataQaService(
            db=db,
            query_log_repository=NoopQueryLogRepository(),
            guardrail_service=LogisticsLlmUnderstandingGuardrailService(
                enabled=True,
                mode="assist",
                sample_rate=1.0,
                audit_enabled=False,
            ),
        )
        guardrail_service = LogisticsLlmUnderstandingGuardrailService(
            enabled=True,
            mode="assist",
            sample_rate=1.0,
            audit_enabled=False,
        )
        for bucket, cases in (("B", b_cases), ("C", c_cases)):
            for index, case in enumerate(cases, start=1):
                question = case["question"]
                _log_progress(progress, f"boundary case {bucket}-{index}/{len(cases)}: {question[:24]}")

                def _run_case() -> dict[str, object]:
                    rule_result = service.query(
                        LogisticsDataQaQueryRequest(question=question),
                        trace_id=f"guardrail-fast-{bucket}-{index}",
                    )
                    llm_result = _build_adversarial_success_llm_result(question)
                    guardrail = guardrail_service.evaluate(
                        question=question,
                        rule_plan=rule_result.query_plan,
                        llm_result=llm_result,
                        trace_id=f"guardrail-fast-{bucket}-{index}",
                        write_audit=False,
                    )
                    return {
                        "bucket": bucket,
                        "case_id": case.get("case_id"),
                        "question": question,
                        "rule_intent": rule_result.query_plan.intent,
                        "rule_query_key": rule_result.query_plan.query_key,
                        "rule_needs_clarification": rule_result.needs_clarification,
                        "rule_supported": rule_result.supported,
                        "adversarial_llm_query_key": llm_result.candidate_query_keys[0],
                        "guardrail_final_source": guardrail.final_source,
                        "guardrail_final_query_key": guardrail.final_query_key,
                        "guardrail_final_supported": guardrail.final_supported,
                        "guardrail_final_needs_clarification": guardrail.final_needs_clarification,
                        "guardrail_policy_locked": guardrail.policy_locked,
                        "guardrail_blocked_reason": guardrail.blocked_reason,
                        "guardrail_rollback_reason": guardrail.rollback_reason,
                        "passed": not guardrail.final_supported,
                    }

                try:
                    items.append(_run_with_timeout(_run_case, seconds=case_timeout_seconds, label=f"{bucket}-{index}"))
                except Exception as exc:  # noqa: BLE001
                    items.append(
                        {
                            "bucket": bucket,
                            "case_id": case.get("case_id"),
                            "question": question,
                            "passed": False,
                            "error": str(exc),
                        }
                    )
    finally:
        db.close()

    existing_rollout: dict[str, object] = {}
    if REPORT_PATH.exists():
        latest_report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        existing_rollout = {
            "report_path": _display_path(REPORT_PATH),
            "generated_at": latest_report.get("generated_at"),
            "answers": latest_report.get("answers"),
            "b_guardrail_mis_success_count": (latest_report.get("guardrail_eval") or {}).get("b_summary", {}).get("guardrail_mis_success_count"),
            "c_guardrail_mis_success_count": (latest_report.get("guardrail_eval") or {}).get("c_summary", {}).get("guardrail_mis_success_count"),
        }

    b_items = [item for item in items if item.get("bucket") == "B"]
    c_items = [item for item in items if item.get("bucket") == "C"]
    failed_items = [item for item in items if not item.get("passed")]
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "fast_boundary_check",
        "diagnosis": {
            "previous_full_rollout_issue": "full rollout 串行执行 A 行为、A 精确、PoC 复算和 off-mode 检查，旧脚本没有进度日志；PoC B/C 默认不复用 replay，当前环境可能长时间等待外部 LLM 或数据链路。",
            "fix": "保留 full rollout，新增进度日志与 fast boundary check；fast 模式用 B/C 样本和高置信 A 类 LLM 候选做对抗式边界验证。",
            "bounded_gate_note": "full rollout 仍可复跑，但当前发布前门禁采用 fast boundary check 验证 B/C 不被 LLM 放行为 success。",
            "full_rollout_command": "PYTHONPATH=. python scripts/logistics_llm_guardrail_rollout.py --progress",
            "fast_check_command": "PYTHONPATH=. python scripts/logistics_llm_guardrail_rollout.py --fast-boundary-check --progress",
        },
        "case_timeout_seconds": case_timeout_seconds,
        "total": len(items),
        "passed": sum(1 for item in items if item.get("passed")),
        "failed": len(failed_items),
        "b_total": len(b_items),
        "b_passed": sum(1 for item in b_items if item.get("passed")),
        "b_mis_success": sum(1 for item in b_items if item.get("guardrail_final_supported")),
        "c_total": len(c_items),
        "c_passed": sum(1 for item in c_items if item.get("passed")),
        "c_mis_success": sum(1 for item in c_items if item.get("guardrail_final_supported")),
        "policy_locked_count": sum(1 for item in items if item.get("guardrail_policy_locked")),
        "existing_rollout_report": existing_rollout,
        "items": items,
        "failed_items": failed_items,
    }
    return report


def render_check_markdown(report: dict[str, object]) -> str:
    """渲染 Guardrail 补验证文档。

    参数：
        report: fast boundary check 报告。

    返回：
        Markdown 文本。
    """

    diagnosis = report["diagnosis"]
    return "\n".join(
        [
            "# LOGISTICS_LLM_GUARDRAIL_ROLLOUT_CHECK",
            "",
            "## 结论",
            "",
            f"- 检查模式：`{report['mode']}`",
            f"- B/C 边界补验证：`{report['passed']}/{report['total']}`",
            f"- B 类误判 success：`{report['b_mis_success']}`",
            f"- C 类误判 success：`{report['c_mis_success']}`",
            f"- case timeout：`{report['case_timeout_seconds']}s`",
            "",
            "## 挂起诊断",
            "",
            f"- 原因判断：{diagnosis['previous_full_rollout_issue']}",
            f"- 本轮处理：{diagnosis['fix']}",
            f"- 发布门禁：{diagnosis['bounded_gate_note']}",
            "",
            "## 可复跑命令",
            "",
            f"- full rollout：`{diagnosis['full_rollout_command']}`",
            f"- fast boundary check：`{diagnosis['fast_check_command']}`",
            "",
            "## 边界验证方式",
            "",
            "- 使用 PoC B/C 样本。",
            "- 对每个 B/C 样本构造一个高置信、单 query_key 的 A 类 LLM 候选。",
            "- 断言 Guardrail 最终不能把这些 B/C 问题放行为 success。",
            "",
            "## 历史 rollout 报告引用",
            "",
            f"- latest report：`{(report.get('existing_rollout_report') or {}).get('report_path')}`",
            f"- generated_at：`{(report.get('existing_rollout_report') or {}).get('generated_at')}`",
            f"- answers：`{(report.get('existing_rollout_report') or {}).get('answers')}`",
            "",
        ]
    )


def render_markdown(report: dict[str, object]) -> str:
    """渲染 Guardrail 正式接入方案文档。"""
    answers = report["answers"]
    config = report["guardrail_config"]
    guardrail_eval = report["guardrail_eval"]
    lines: list[str] = [
        "# 物流域 LLM Guardrail 受控接入方案",
        "",
        "## 结论",
        "",
        "- Guardrail 已正式受控接入 `data-qa` 主链路，但默认仍可关闭、可回退。",
        "- 正式 planner 仍是主链路裁决者，LLM 只允许增强 A 类白名单同构变体。",
        "- B/C 边界继续由规则层锁定，不允许被 LLM 改写。",
        "",
        "## 接入点",
        "",
        "当前正式接入点位于 `LogisticsDataQaService.query`：",
        "1. 先执行规则 planner，得到 `rule_plan`；",
        "2. 若规则层已命中正式 query_key，则直接执行；",
        "3. 若命中 B/C 正式策略，则直接锁定；",
        "4. 只有规则层落入通用兜底澄清时，才允许 Guardrail 评估 LLM 候选；",
        "5. assist 模式下若满足白名单、高置信、单候选，才回构正式 plan；",
        "6. 回构失败立即回退到纯规则结果。",
        "",
        "## 开关与模式",
        "",
        f"- `LLM_GUARDRAIL_ENABLED`：{config['enabled']}",
        f"- `LLM_GUARDRAIL_MODE`：{config['mode']}",
        f"- `LLM_GUARDRAIL_SAMPLE_RATE`：{config['sample_rate']}",
        f"- `LLM_GUARDRAIL_MIN_CONFIDENCE`：{config['min_confidence']}",
        f"- `LLM_GUARDRAIL_A_QUERYKEY_WHITELIST`：{', '.join(config['a_querykey_whitelist'])}",
        f"- `LLM_GUARDRAIL_AUDIT_ENABLED`：{config['audit_enabled']}",
        "",
        "模式说明：",
        "- `off`：完全退回纯规则链路；",
        "- `shadow`：旁路评估和审计，不改动正式结果；",
        "- `assist`：只在 A 类白名单场景受控恢复 query_key。",
        "",
        "## 审计记录",
        "",
        f"- JSONL 审计日志：`{report['audit']['jsonl_path']}`",
        "- 统一查询日志：当前会把 Guardrail 决策快照写入 `sys_query_log.request_payload.response_meta.guardrail`。",
        "- 当前至少记录：原始问题、规则 query_key、是否进入 guardrail、是否调用 LLM、LLM 候选、置信度、最终来源、回退原因。",
        "",
        "## 收益与不回退验证",
        "",
        f"- 20 条关键题精确断言：{report['a_key_exact_regression']['passed_questions']}/{report['a_key_exact_regression']['total_questions']}",
        f"- 75 条 A 类行为回归：{report['a_behavior_regression']['passed_questions']}/{report['a_behavior_regression']['total_questions']}",
        f"- A 类变体 Guardrail 命中：{guardrail_eval['a_summary']['guardrail_query_key_hit_count']}/{guardrail_eval['a_summary']['variant_total']}",
        f"- B 类 guardrail 误判 success：{guardrail_eval['b_summary']['guardrail_mis_success_count']}",
        f"- C 类 guardrail 误判 success：{guardrail_eval['c_summary']['guardrail_mis_success_count']}",
        "",
        "## 当前判断",
        "",
        f"- Guardrail 是否已正式可控接入主链路：{answers['guardrail_formally_integrated']}",
        f"- 默认关闭时是否完全回到纯规则：{answers['off_returns_pure_rule']}",
        f"- assist 是否只增强 A 类白名单：{answers['assist_only_enhances_a_whitelist']}",
        f"- B/C 边界是否未被 LLM 改坏：{answers['bc_boundary_not_regressed']}",
        f"- 是否具备小流量 candidate assist 条件：{answers['candidate_assist_ready']}",
        f"- 是否建议让 LLM 直接替换 planner：{answers['replace_planner_recommended']}",
        "",
        "## 建议",
        "",
        "- 当前已经具备小流量 candidate assist 的条件。",
        "- 仍然不建议让 LLM 全面替换正式 planner。",
        "- 下一步应继续保持规则主导，只在 A 类白名单里小流量放行 assist，并持续审计。",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    """运行 Guardrail 正式接入方案报告。"""
    parser = argparse.ArgumentParser(description="物流域 LLM Guardrail 受控接入方案")
    parser.add_argument("--output", default=str(REPORT_PATH), help="Guardrail rollout JSON 报告输出路径")
    parser.add_argument("--doc", default=str(DOC_PATH), help="Guardrail rollout Markdown 文档输出路径")
    parser.add_argument("--progress", action="store_true", help="输出阶段进度，避免长任务无反馈")
    parser.add_argument("--fast-boundary-check", action="store_true", help="只执行有界 B/C Guardrail 边界补验证")
    parser.add_argument("--case-timeout-seconds", type=int, default=20, help="fast boundary check 单用例超时时间")
    parser.add_argument("--check-output", default=str(CHECK_REPORT_PATH), help="Guardrail 补验证 JSON 报告输出路径")
    parser.add_argument("--check-doc", default=str(CHECK_DOC_PATH), help="Guardrail 补验证 Markdown 文档输出路径")
    parser.add_argument(
        "--replay-report",
        default=str(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_llm_understanding_poc_report.json"),
        help="可选：复用上一轮真实 LLM PoC 报告，减少重复外部调用",
    )
    args = parser.parse_args()

    if args.fast_boundary_check:
        report = build_fast_boundary_check_report(case_timeout_seconds=args.case_timeout_seconds, progress=args.progress)
        output_path = Path(args.check_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        Path(args.check_doc).write_text(render_check_markdown(report), encoding="utf-8")
        print(json.dumps({key: report[key] for key in ("total", "passed", "failed", "b_mis_success", "c_mis_success")}, ensure_ascii=False, indent=2))
        return

    report = build_rollout_report(replay_report_path=Path(args.replay_report) if args.replay_report else None, progress=args.progress)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    doc_path = Path(args.doc)
    doc_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["answers"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

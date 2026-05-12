from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from backend.app.core.config import settings
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaPlan
from backend.app.domains.logistics.schemas.llm_understanding import (
    LogisticsLlmGuardrailAuditRecord,
    LogisticsLlmGuardrailDecision,
    LogisticsLlmUnderstandingResult,
)
from backend.app.domains.logistics.services.llm_understanding_service import LogisticsLlmUnderstandingService
from backend.app.domains.logistics.services.question_bank_response_policy import LogisticsQuestionBankResponsePolicy


class LogisticsLlmUnderstandingGuardrailService:
    """物流域 LLM Guardrail 辅助服务。

    设计目标：
        1. 正式 planner 仍由规则层主导，当前服务不替换正式裁决；
        2. 只允许 LLM 在 A 类稳定 query_key 的同构变体问法上做候选增强；
        3. B/C 类边界继续由规则策略锁定，LLM 不得改写澄清或不支持结论。
    """

    # 当前只允许 LLM 增强已经稳定支持的 query_key，避免扩大能力边界。
    # composite_decomposed 只作为顶层拆分候选，最终还需 planner 回构为受控子计划。
    ASSIST_ALLOWED_QUERY_KEYS: dict[str, str] = {
        "hist_total_fee_city_rank": "ranking",
        "hist_avg_fee_by_month": "aggregate",
        "hist_avg_fee_per_watt_by_transport": "ranking",
        "hist_extra_fee_ratio_peak_month": "ranking",
        "hist_total_fee_by_origin_and_carrier": "aggregate",
        "sys_mw_and_trip_count": "aggregate",
        "hist_trip_count_by_region": "aggregate",
        "hist_quantity_by_region": "aggregate",
        "hist_customer_mw": "aggregate",
        "hist_vehicle_type_trip_count": "aggregate",
        "sys_signedfor_rate_by_carrier": "ranking",
        "hist_multi_origin_customers": "detail_list",
        "sys_companies_without_tasks": "detail_list",
        "hist_plan_actual_deviation": "compare",
        "sys_special_total_fee": "aggregate",
        "composite_decomposed": "composite",
    }
    COMPOSITE_POLICY_ASSIST_CATEGORIES = {"high_fee_address_procurement_split"}
    GENERIC_CLARIFICATION_QUESTIONS = (
        "当前 MVP 只支持时间聚合、区域筛选、承运商排名、费用/运量统计等结构化数据问题。",
        "请补充明确的时间、指标和维度，例如“2025年华东区域总运费”或“2026年1月总发运量”。",
    )
    ASSIST_ALLOWED_INTENTS = {"aggregate", "ranking", "comparison", "detail", "composite", "unknown"}

    def __init__(
        self,
        *,
        llm_service: LogisticsLlmUnderstandingService | None = None,
        response_policy: LogisticsQuestionBankResponsePolicy | None = None,
        enabled: bool | None = None,
        mode: str | None = None,
        sample_rate: float | None = None,
        min_confidence: float | None = None,
        audit_enabled: bool | None = None,
        audit_path: Path | None = None,
    ) -> None:
        """初始化 Guardrail 服务。

        参数：
            llm_service: 可注入的 LLM 理解层服务，便于测试和 PoC 脚本复用。
            response_policy: 可注入的题库响应策略，保证 B/C 边界始终一致。
            enabled: Guardrail 是否启用，默认读取 settings。
            mode: Guardrail 当前运行模式，默认读取 settings。
            sample_rate: 未来小流量 candidate assist 的抽样比例。
            min_confidence: 允许 LLM 候选进入 A 类增强的最低置信度。
            audit_enabled: 是否写 Guardrail 审计日志。
            audit_path: Guardrail 审计日志文件路径。
        """

        self.llm_service = llm_service or LogisticsLlmUnderstandingService()
        self.response_policy = response_policy or LogisticsQuestionBankResponsePolicy()
        self.enabled = settings.llm_guardrail_enabled if enabled is None else enabled
        self.mode = settings.llm_guardrail_mode if mode is None else mode
        self.sample_rate = settings.llm_guardrail_sample_rate if sample_rate is None else sample_rate
        self.min_confidence = settings.llm_guardrail_min_confidence if min_confidence is None else min_confidence
        self.audit_enabled = settings.llm_guardrail_audit_enabled if audit_enabled is None else audit_enabled
        self.audit_path = audit_path or (settings.log_root / "logistics_llm_guardrail_audit.jsonl")
        self.allowed_query_key_whitelist = self._resolve_allowed_query_key_whitelist()

    def evaluate(
        self,
        *,
        question: str,
        rule_plan: LogisticsDataQaPlan,
        llm_result: LogisticsLlmUnderstandingResult | None = None,
        trace_id: str | None = None,
        write_audit: bool = True,
    ) -> LogisticsLlmGuardrailDecision:
        """评估当前问题是否允许进入 LLM 候选增强。

        说明：
            1. 先看规则层是否已明确命中支持 / 澄清 / 不支持；
            2. 只有“未命中正式 query_key、且只是通用兜底澄清”的问题才进入候选增强；
            3. 进入增强后仍要求：单候选、高置信、白名单 query_key、非 B/C 语义。
        """

        sampled_in = self._is_sampled_in(question)
        policy_decision = self.response_policy.match(question)
        composite_policy_assist_allowed = (
            policy_decision is not None
            and policy_decision.decision_type == "unsupported"
            and policy_decision.category in self.COMPOSITE_POLICY_ASSIST_CATEGORIES
        )
        decision = LogisticsLlmGuardrailDecision(
            question=question,
            guardrail_enabled=self.enabled,
            guardrail_mode=self._normalize_mode(self.mode),
            sampled_in=sampled_in,
            rule_intent=rule_plan.intent,
            rule_query_key=rule_plan.query_key,
            rule_needs_clarification=rule_plan.needs_clarification,
            rule_supported=rule_plan.intent not in {"clarification", "unsupported"},
            final_intent=rule_plan.intent,
            final_query_key=rule_plan.query_key,
            final_needs_clarification=rule_plan.needs_clarification,
            final_supported=rule_plan.intent not in {"clarification", "unsupported"},
            allowed_query_key_whitelist=self.allowed_query_key_whitelist,
        )

        # Guardrail 未启用或当前不在抽样流量内时，直接保持规则裁决。
        if not self.enabled:
            decision.blocked_reason = "guardrail_disabled"
            decision.rollback_reason = "global_switch_off"
            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
            return decision
        if decision.guardrail_mode == "off":
            decision.blocked_reason = "guardrail_mode_off"
            decision.rollback_reason = "mode_off"
            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
            return decision
        if not sampled_in:
            decision.blocked_reason = "guardrail_not_sampled_in"
            decision.rollback_reason = "sample_not_hit"
            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
            return decision
        decision.entered_guardrail = True

        # B/C 边界一旦被正式策略命中，默认完全锁定，不允许 LLM 继续改写。
        # 例外：高运费地址 + 采购方式这类“可能是两个独立子问”的旧拒答策略，
        # 允许 LLM 先给出顶层复合拆分候选，再由 planner 做字段能力和回指安全校验。
        if policy_decision is not None:
            decision.policy_decision_type = policy_decision.decision_type
            decision.policy_category = policy_decision.category
        if policy_decision is not None and not composite_policy_assist_allowed:
            decision.policy_locked = True
            decision.blocked_reason = f"policy_locked::{policy_decision.decision_type}::{policy_decision.category}"
            decision.rollback_reason = "rule_policy_locked"
            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
            return decision

        # 规则已经稳定命中 query_key 时，不需要任何 LLM 增强。
        if rule_plan.query_key:
            decision.blocked_reason = "rule_already_hit_query_key"
            decision.rollback_reason = "rule_already_supported"
            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
            return decision

        # 规则若已经明确不支持，也不允许 LLM 反向放行；复合拆分例外仍需后续 planner 校验。
        if rule_plan.intent == "unsupported" and not composite_policy_assist_allowed:
            decision.blocked_reason = "rule_declared_unsupported"
            decision.rollback_reason = "rule_declared_unsupported"
            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
            return decision

        # 只允许“通用兜底澄清”进入 A 类候选增强，专属澄清模板不允许被绕过；
        # 复合拆分例外可以从旧拒答策略进入 LLM 候选，但最终必须回构成受控子查询。
        if not rule_plan.needs_clarification and not composite_policy_assist_allowed:
            decision.blocked_reason = "rule_not_in_generic_clarification"
            decision.rollback_reason = "rule_not_generic_clarification"
            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
            return decision
        if rule_plan.needs_clarification and not self._is_generic_clarification(rule_plan) and not composite_policy_assist_allowed:
            decision.blocked_reason = "rule_specific_clarification_locked"
            decision.rollback_reason = "rule_specific_clarification_locked"
            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
            return decision

        decision.eligible_for_assist = True
        decision.llm_invoked = llm_result is None
        llm_output = llm_result or self.llm_service.understand(
            question,
            allowed_query_keys=self.allowed_query_key_whitelist,
        )
        decision.llm_intent = llm_output.intent
        decision.llm_candidate_query_keys = llm_output.candidate_query_keys
        decision.llm_top_query_key = llm_output.candidate_query_keys[0] if llm_output.candidate_query_keys else None
        decision.llm_filters = llm_output.filters
        decision.llm_time_range = llm_output.time_range
        decision.llm_normalized_terms = llm_output.normalized_terms
        decision.llm_confidence = llm_output.confidence
        decision.llm_provider_mode = llm_output.provider_mode

        # 只接受真实 live 结果，配置缺失或外部错误都不能放大为正式能力。
        if llm_output.provider_mode != "live":
            decision.blocked_reason = "llm_not_live"
            decision.rollback_reason = "llm_not_live"
            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
            return decision

        # 如果 LLM 自己判断成 B/C，也不允许它改写规则层，只能继续保持规则结论。
        if llm_output.needs_clarification or llm_output.unsupported_reason:
            decision.blocked_reason = "llm_requested_bc_boundary"
            decision.rollback_reason = "llm_hit_bc_boundary"
            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
            return decision

        if llm_output.intent not in self.ASSIST_ALLOWED_INTENTS:
            decision.blocked_reason = "llm_intent_not_allowed"
            decision.rollback_reason = "llm_intent_not_allowed"
            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
            return decision

        if llm_output.confidence < self.min_confidence:
            decision.blocked_reason = "llm_low_confidence"
            decision.rollback_reason = "llm_low_confidence"
            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
            return decision

        if len(llm_output.candidate_query_keys) != 1:
            decision.blocked_reason = "llm_candidate_count_not_one"
            decision.rollback_reason = "llm_candidate_count_not_one"
            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
            return decision

        candidate_query_key = llm_output.candidate_query_keys[0]
        if composite_policy_assist_allowed and candidate_query_key != "composite_decomposed":
            # 复合策略例外只允许 LLM 回答“可拆为受控复合问题”，不能借 unsupported 边界改写成其它 A 类能力。
            decision.blocked_reason = "composite_policy_requires_composite_candidate"
            decision.rollback_reason = "composite_policy_requires_composite_candidate"
            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
            return decision
        if candidate_query_key not in self.allowed_query_key_whitelist:
            decision.blocked_reason = "llm_query_key_not_allowlisted"
            decision.rollback_reason = "candidate_not_allowlisted"
            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
            return decision

        decision.assist_recommended = True

        # shadow 只记录可放行候选，不允许改动正式结果。
        if decision.guardrail_mode == "shadow":
            decision.blocked_reason = "shadow_mode_no_apply"
            decision.rollback_reason = "shadow_mode_only_audit"
            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
            return decision

        # 满足所有 guardrail 且处于 assist 模式时，才视为“正式受控候选增强”。
        decision.assist_applied = True
        decision.final_source = "llm_assist"
        decision.final_query_key = candidate_query_key
        decision.final_intent = self.ASSIST_ALLOWED_QUERY_KEYS[candidate_query_key]
        decision.final_needs_clarification = False
        decision.final_supported = True
        decision.blocked_reason = None
        decision.rollback_reason = None
        self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
        return decision

    def write_audit_log(self, *, trace_id: str | None, decision: LogisticsLlmGuardrailDecision) -> None:
        """对外暴露正式审计写入入口，便于主链路在最终定案后补写日志。"""
        self._write_audit_log(trace_id=trace_id, decision=decision)

    def _resolve_allowed_query_key_whitelist(self) -> list[str]:
        """解析当前 Guardrail 可增强的 A 类 query_key 白名单。

        说明：
            1. 如果配置未显式给白名单，则退回到服务内建稳定白名单；
            2. 如果配置里包含未知 query_key，会自动过滤，避免越界放行；
            3. 最终始终返回有序列表，便于审计和报告。
        """
        configured = settings.llm_guardrail_a_querykey_whitelist or []
        allowlist = configured or list(self.ASSIST_ALLOWED_QUERY_KEYS.keys())
        return [item for item in allowlist if item in self.ASSIST_ALLOWED_QUERY_KEYS]

    @staticmethod
    def _normalize_mode(mode: str | None) -> str:
        """统一 guardrail 模式口径，兼容旧版 disabled 配置。"""
        if mode in {"shadow", "assist"}:
            return mode
        return "off"

    def _is_generic_clarification(self, rule_plan: LogisticsDataQaPlan) -> bool:
        """判断规则层当前是否只是命中了通用兜底澄清。"""
        return tuple(rule_plan.clarification_questions) == self.GENERIC_CLARIFICATION_QUESTIONS

    def _is_sampled_in(self, question: str) -> bool:
        """判断当前问题是否命中 Guardrail 抽样。

        说明：
            1. shadow 模式默认全量采样，便于完整对比；
            2. assist 模式支持按 sample_rate 做稳定抽样；
            3. 抽样基于问题哈希，便于跨进程复现。
        """

        normalized_mode = self._normalize_mode(self.mode)
        if normalized_mode == "shadow":
            return True
        if normalized_mode != "assist":
            return False
        if self.sample_rate <= 0:
            return False
        if self.sample_rate >= 1:
            return True
        digest = hashlib.md5(question.encode("utf-8")).hexdigest()  # noqa: S324
        ratio = int(digest[:8], 16) / 0xFFFFFFFF
        return ratio < self.sample_rate

    def _write_audit_log(self, *, trace_id: str | None, decision: LogisticsLlmGuardrailDecision) -> None:
        """写 Guardrail JSONL 审计日志。"""

        if not self.audit_enabled:
            return
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        record = LogisticsLlmGuardrailAuditRecord(
            created_at=datetime.now().isoformat(timespec="seconds"),
            trace_id=trace_id,
            question=decision.question,
            guardrail_enabled=decision.guardrail_enabled,
            guardrail_mode=decision.guardrail_mode,
            sampled_in=decision.sampled_in,
            entered_guardrail=decision.entered_guardrail,
            llm_invoked=decision.llm_invoked,
            policy_locked=decision.policy_locked,
            policy_decision_type=decision.policy_decision_type,
            policy_category=decision.policy_category,
            rule_intent=decision.rule_intent,
            rule_query_key=decision.rule_query_key,
            rule_needs_clarification=decision.rule_needs_clarification,
            rule_supported=decision.rule_supported,
            llm_provider_mode=decision.llm_provider_mode,
            llm_top_query_key=decision.llm_top_query_key,
            llm_confidence=decision.llm_confidence,
            assist_recommended=decision.assist_recommended,
            assist_applied=decision.assist_applied,
            final_source=decision.final_source,
            final_intent=decision.final_intent,
            final_query_key=decision.final_query_key,
            final_needs_clarification=decision.final_needs_clarification,
            final_supported=decision.final_supported,
            allowed_query_key_whitelist=decision.allowed_query_key_whitelist,
            blocked_reason=decision.blocked_reason,
            rollback_reason=decision.rollback_reason,
        )
        with self.audit_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=False) + "\n")

    def _maybe_write_audit_log(
        self,
        *,
        trace_id: str | None,
        decision: LogisticsLlmGuardrailDecision,
        write_audit: bool,
    ) -> None:
        """按调用方要求决定是否立即写审计。"""
        if write_audit:
            self._write_audit_log(trace_id=trace_id, decision=decision)

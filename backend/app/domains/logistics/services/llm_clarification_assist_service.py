from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI

from backend.app.core.config import settings
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaPlan
from backend.app.domains.logistics.schemas.llm_understanding import (
    LogisticsLlmClarificationAssistAuditRecord,
    LogisticsLlmClarificationAssistResult,
)


class LogisticsLlmClarificationAssistService:
    """物流域澄清辅助服务。

    说明：
        1. 当前服务只在规则层已经明确判定“必须澄清”后才会介入；
        2. LLM 只负责识别缺口径和生成更业务化的追问候选，不允许改判成 success / unsupported；
        3. 若 LLM 配置缺失、置信度不足或类别不在白名单内，统一回退到规则模板。
    """

    DEFAULT_ALLOWED_CATEGORIES = [
        "vague_status",
        "transport_record_scope",
        "quarter_trip_metric_scope",
        "route_loading_scope",
        "rate_distribution_scope",
        "system_status_ratio_scope",
        "parse_status_scope",
        "status_risk_scope",
        "route_price_metric_scope",
        "procurement_metric_scope",
        "data_quality_scope",
        "high_fee_address_scope",
        "state_breakdown_scope",
        "comparison_basis_scope",
        "mapping_consistency_scope",
        "route_metric_scope",
        "data_consistency_scope",
        "quarter_area_metric_scope",
        "transport_unit_fee_scope",
        "state_ranking_scope",
        "task_split_scope",
        "field_alias_comparison_scope",
        "cause_distribution_scope",
        "contract_carrier_scope",
        "driver_identity_consistency_scope",
        "transport_distance_scope",
        "parse_fail_ranking_scope",
        "short_context_scope",
        "shipment_quantity_scope",
        "carrier_unit_fee_scope",
        "abnormal_or_reason_scope",
        "transport_mode_metric_scope",
        "route_or_address_scope",
        "system_state_scope",
        "vehicle_or_trip_scope",
        "customer_project_scope",
        "ranking_basis_scope",
    ]
    # 不同澄清题型的业务提示词，用于提醒 LLM 优先识别什么缺口径。
    CATEGORY_HINTS = {
        "vague_status": "优先识别时间范围和评价指标，避免只追问泛泛的“请补充更多信息”。",
        "transport_record_scope": "优先区分发运明细行、物流任务数和车次，避免把“记录数”直接等同为车次。",
        "quarter_trip_metric_scope": "优先区分车次和唯一车辆数，并确认是否只看历史台账口径。",
        "route_loading_scope": "优先确认平均口径是按车次、按任务还是按装载记录，以及空值如何处理。",
        "rate_distribution_scope": "优先确认达标率定义，以及均值/中位数的聚合基础。",
        "system_status_ratio_scope": "优先确认占比分母和是否只看 2026 正式有效任务。",
        "parse_status_scope": "优先确认状态码业务含义，以及统计对象是否只看正式系统派车任务。",
        "status_risk_scope": "优先识别风险判定标准和统计范围，避免把“风险”直接理解成固定单一指标。",
        "route_price_metric_scope": "优先确认“运价/报价”指平均单车运费、平均运费还是单瓦价，并确认历史口径是否统一。",
        "procurement_metric_scope": "优先确认采购方式对比看的是什么指标，以及是否只统计已打标的正式任务。",
        "data_quality_scope": "优先确认是看问题数量、问题率还是明细清单，以及是否需要继续按承运商、状态或采购方式拆分。",
        "high_fee_address_scope": "优先确认高运费地址的阈值口径是单笔记录还是全年累计，并确认后续展示指标。",
        "state_breakdown_scope": "优先确认统计对象是哪张任务表，以及是否保留全部状态还是只看核心状态。",
        "comparison_basis_scope": "优先识别比较的核心指标和判断标准，避免把“变化最大”“更划算”“最忙”直接理解成单一口径。",
        "mapping_consistency_scope": "优先确认统一后的主口径和展示目标，避免把字段映射问题直接当成单一结果查询。",
        "route_metric_scope": "优先确认线路问题要看的到底是平均单车运费、单瓦价还是平均路程，以及平均基础是什么。",
        "data_consistency_scope": "优先确认是看异常数量、问题率还是异常清单，并确认是否需要继续按承运商、仓库或状态拆分。",
        "quarter_area_metric_scope": "优先确认季度统计是否只看历史台账，以及排序展示按指标排序还是按固定区域顺序。",
        "transport_unit_fee_scope": "优先确认平均单瓦成本的计算基础和费用口径，避免把总运费除总瓦数与逐条记录平均混算。",
        "state_ranking_scope": "优先确认“最多”按任务数量还是按占比排序，以及统计对象是否只看 2026 正式系统当前状态任务。",
        "task_split_scope": "优先确认“拆分最多”按派车任务数、车牌数还是承运商数统计，并确认是否只看 2026 正式系统数据。",
        "field_alias_comparison_scope": "优先确认车次、车辆数和效率指标的统一口径，避免跨年字段名称差异导致误算。",
        "cause_distribution_scope": "优先确认产生原因字段是否需要归并，以及区域差异按数量、占比还是排名展示。",
        "contract_carrier_scope": "优先确认看合同数量还是合同明细，并确认系统数据与历史台账是否混用。",
        "driver_identity_consistency_scope": "优先确认看异常数量、异常明细还是按承运商拆分，并确认是否只看 2026 正式系统。",
        "transport_distance_scope": "优先确认送达距离字段来源、空值处理和平均基础。",
        "parse_fail_ranking_scope": "优先确认解析失败状态口径和排名指标，避免把失败数和失败率混算。",
        "short_context_scope": "优先补齐上下文、统计维度、结果指标和时间范围。",
        "shipment_quantity_scope": "优先确认“量”是否按默认瓦数 / MW 展示，以及统计主体是全量、客户还是承运商。",
        "carrier_unit_fee_scope": "优先确认公司名称按承运商还是客户理解，并确认单瓦成本费用分子是否包含额外费用。",
        "abnormal_or_reason_scope": "优先确认异常或高成本判定标准、统计时间范围，以及结果要明细还是汇总。",
        "transport_mode_metric_scope": "优先确认运输方式同义口径、统计指标、单位和时间范围，避免把公路/汽运或铁路/铁运拆错。",
        "route_or_address_scope": "优先确认始发地、目的地、指标、单位和车型/运输方式限制，避免线路条件看似明确但口径不完整。",
        "system_state_scope": "优先确认系统状态枚举、统计指标、时间范围和分组维度，避免把缺失字段直接当成可估算结论。",
        "vehicle_or_trip_scope": "优先确认车次/车辆数口径、车型口径和分组维度，避免把总车次、车辆数、车型数量混算。",
        "customer_project_scope": "优先确认客户/项目名称归并口径、指标口径和是否需要排名，避免把客户简称、项目名称和标准客户名混算。",
        "ranking_basis_scope": "优先确认排名指标、排名方向和 TopN 数量，避免把排名、前十、最高等问法直接落到单一排序口径。",
    }
    SLOT_WHITELIST = {
        "time_range",
        "metric_definition",
        "dimension_split",
        "record_scope",
        "source_scope",
        "evaluation_metric",
        "special_definition",
        "threshold_scope",
        "procurement_scope",
        "base_scope",
        "mapping_field",
        "price_metric",
        "fee_scope",
        "analysis_scope",
        "exception_threshold",
        "table_scope",
        "status_scope",
        "result_metric",
        "statistic_scope",
        "denominator_scope",
        "status_code_meaning",
        "aggregation_basis",
        "null_handling",
        "sort_order",
    }

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        client: Any | None = None,
        enabled: bool | None = None,
        mode: str | None = None,
        sample_rate: float | None = None,
        min_confidence: float | None = None,
        audit_enabled: bool | None = None,
        audit_path: Path | None = None,
        allowed_categories: list[str] | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        """初始化澄清辅助服务。"""

        self.base_url = base_url if base_url is not None else settings.llm_base_url
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self.model = model if model is not None else settings.llm_model
        self._client = client
        self.enabled = settings.llm_clarification_assist_enabled if enabled is None else enabled
        self.mode = settings.llm_clarification_assist_mode if mode is None else mode
        self.sample_rate = settings.llm_clarification_assist_sample_rate if sample_rate is None else sample_rate
        self.min_confidence = settings.llm_clarification_assist_min_confidence if min_confidence is None else min_confidence
        self.audit_enabled = settings.llm_clarification_assist_audit_enabled if audit_enabled is None else audit_enabled
        self.audit_path = audit_path or (settings.log_root / "logistics_llm_clarification_assist.jsonl")
        self.allowed_categories = self._resolve_allowed_categories(allowed_categories)
        self.timeout_seconds = timeout_seconds

    def is_enabled(self) -> bool:
        """判断当前环境是否具备真实 LLM 调用配置。"""
        return bool(self.base_url and self.api_key and self.model)

    def apply(
        self,
        *,
        question: str,
        plan: LogisticsDataQaPlan,
        trace_id: str | None = None,
    ) -> tuple[LogisticsDataQaPlan, str]:
        """在规则已判定澄清后，尝试生成更业务化的追问候选。

        返回：
            1. 可能被增强过的 plan；
            2. 当前用于对外展示的澄清摘要。
        """

        normalized_mode = self._normalize_mode(self.mode)
        summary = plan.clarification_reason or "当前问题还不够明确，需先补充口径。"
        sampled_in = self._is_sampled_in(question, normalized_mode=normalized_mode)
        result = LogisticsLlmClarificationAssistResult(
            normalized_question=question.strip(),
            clarification_category=plan.clarification_category,
            missing_slots=list(plan.clarification_missing_slots),
            suggested_questions=list(plan.clarification_questions),
            business_summary=summary,
            provider_mode="disabled",
            llm_model_name=self.model or None,
        )
        applied = False
        blocked_reason: str | None = None

        if not self.enabled or normalized_mode == "off":
            blocked_reason = "clarification_assist_off"
            self._write_audit(
                trace_id=trace_id,
                plan=plan,
                result=result,
                sampled_in=sampled_in,
                applied=applied,
                blocked_reason=blocked_reason,
                normalized_mode=normalized_mode,
            )
            return plan, summary

        if not sampled_in:
            blocked_reason = "clarification_assist_not_sampled"
            self._write_audit(
                trace_id=trace_id,
                plan=plan,
                result=result,
                sampled_in=sampled_in,
                applied=applied,
                blocked_reason=blocked_reason,
                normalized_mode=normalized_mode,
            )
            return plan, summary

        if not plan.clarification_category or plan.clarification_category not in self.allowed_categories:
            blocked_reason = "clarification_category_not_allowlisted"
            self._write_audit(
                trace_id=trace_id,
                plan=plan,
                result=result,
                sampled_in=sampled_in,
                applied=applied,
                blocked_reason=blocked_reason,
                normalized_mode=normalized_mode,
            )
            return plan, summary

        if not self.is_enabled():
            blocked_reason = "llm_not_configured"
            self._write_audit(
                trace_id=trace_id,
                plan=plan,
                result=result,
                sampled_in=sampled_in,
                applied=applied,
                blocked_reason=blocked_reason,
                normalized_mode=normalized_mode,
            )
            return plan, summary

        result = self._request_clarification_assist(question=question, plan=plan)
        if result.provider_mode != "live":
            blocked_reason = "llm_not_live"
            self._write_audit(
                trace_id=trace_id,
                plan=plan,
                result=result,
                sampled_in=sampled_in,
                applied=applied,
                blocked_reason=blocked_reason,
                normalized_mode=normalized_mode,
            )
            return plan, summary

        if normalized_mode == "shadow":
            blocked_reason = "shadow_mode_only_audit"
            self._write_audit(
                trace_id=trace_id,
                plan=plan,
                result=result,
                sampled_in=sampled_in,
                applied=applied,
                blocked_reason=blocked_reason,
                normalized_mode=normalized_mode,
            )
            return plan, summary

        if result.confidence < self.min_confidence:
            blocked_reason = "llm_low_confidence"
            self._write_audit(
                trace_id=trace_id,
                plan=plan,
                result=result,
                sampled_in=sampled_in,
                applied=applied,
                blocked_reason=blocked_reason,
                normalized_mode=normalized_mode,
            )
            return plan, summary

        if not result.suggested_questions:
            blocked_reason = "llm_no_questions"
            self._write_audit(
                trace_id=trace_id,
                plan=plan,
                result=result,
                sampled_in=sampled_in,
                applied=applied,
                blocked_reason=blocked_reason,
                normalized_mode=normalized_mode,
            )
            return plan, summary

        plan.clarification_questions = result.suggested_questions
        if result.missing_slots:
            plan.clarification_missing_slots = result.missing_slots
        plan.clarification_assist_used = True
        plan.clarification_assist_provider_mode = result.provider_mode
        applied = True
        summary = result.business_summary or summary

        self._write_audit(
            trace_id=trace_id,
            plan=plan,
            result=result,
            sampled_in=sampled_in,
            applied=applied,
            blocked_reason=blocked_reason,
            normalized_mode=normalized_mode,
        )
        return plan, summary

    def _request_clarification_assist(
        self,
        *,
        question: str,
        plan: LogisticsDataQaPlan,
    ) -> LogisticsLlmClarificationAssistResult:
        """调用外部 LLM 生成澄清候选。"""

        try:
            client = self._client or OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout_seconds,
                max_retries=0,
            )
            completion = client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    {
                        "role": "user",
                        "content": self._build_user_prompt(question=question, plan=plan),
                    },
                ],
            )
            content = completion.choices[0].message.content or "{}"
            payload = self._extract_json(content)
            return self._normalize_payload(question=question, plan=plan, payload=payload)
        except Exception as exc:  # noqa: BLE001
            return LogisticsLlmClarificationAssistResult(
                normalized_question=question.strip(),
                clarification_category=plan.clarification_category,
                missing_slots=list(plan.clarification_missing_slots),
                suggested_questions=list(plan.clarification_questions),
                business_summary=plan.clarification_reason,
                provider_mode="error",
                provider_error=str(exc),
                llm_model_name=self.model or None,
            )

    def _build_system_prompt(self) -> str:
        """构建澄清辅助系统提示词。"""

        return (
            "你是物流数据问答系统的“澄清辅助层”。\n"
            "规则层已经明确判定这个问题必须先澄清，你不能把它改判成 success，也不能改判成 unsupported。\n"
            "你的任务只有两个：\n"
            "1. 识别当前问题缺少哪些关键口径；\n"
            "2. 生成更业务化、更易懂的追问候选。\n"
            "你不能查询数据库，不能输出 SQL，不能编造任何业务结果。\n"
            "输出必须是单个 JSON 对象，字段如下：\n"
            "{\n"
            '  "missing_slots": ["time_range", "metric_definition"],\n'
            '  "slot_reasons": {"time_range":"...", "metric_definition":"..."},\n'
            '  "suggested_questions": ["...", "..."],\n'
            '  "business_summary": "...",\n'
            '  "confidence": 0.0\n'
            "}\n"
            "missing_slots 只能从这组固定枚举里选：\n"
            "time_range, metric_definition, dimension_split, record_scope, source_scope, evaluation_metric, special_definition, threshold_scope, procurement_scope, base_scope, mapping_field, price_metric, fee_scope, analysis_scope, exception_threshold, table_scope, status_scope, result_metric, statistic_scope, denominator_scope, status_code_meaning, aggregation_basis, null_handling。\n"
            "追问要求：\n"
            "1. 用业务人员能看懂的话，不要写成技术文档；\n"
            "2. 优先追问真正缺失的 2 个关键点，不要问太多；\n"
            "3. 如果规则层已经给出较好的追问，不要改得更差；\n"
            "4. 不要输出 markdown，不要输出解释段落。"
            "5. confidence 不要默认写 0；当缺口径识别与规则模板一致、追问清楚且业务表达自然时，confidence 应不低于 0.8。"
        )

    def _build_user_prompt(self, *, question: str, plan: LogisticsDataQaPlan) -> str:
        """构建澄清辅助用户提示词。"""

        category_hint = self.CATEGORY_HINTS.get(plan.clarification_category or "", "优先识别真正缺失的关键口径。")
        return (
            f"原始问题：{question}\n"
            f"规则澄清类别：{plan.clarification_category}\n"
            f"题型提示：{category_hint}\n"
            f"规则澄清原因：{plan.clarification_reason}\n"
            f"规则识别的缺口径：{json.dumps(plan.clarification_missing_slots, ensure_ascii=False)}\n"
            f"规则追问模板：{json.dumps(plan.clarification_questions, ensure_ascii=False)}\n"
            "请只输出 JSON。"
        )

    def _extract_json(self, content: str) -> dict[str, Any]:
        """从模型文本中提取 JSON。"""

        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
            stripped = re.sub(r"\s*```$", "", stripped)
        match = re.search(r"\{.*\}", stripped, flags=re.S)
        json_text = match.group(0) if match else stripped
        parsed = json.loads(json_text)
        return parsed if isinstance(parsed, dict) else {}

    def _normalize_payload(
        self,
        *,
        question: str,
        plan: LogisticsDataQaPlan,
        payload: dict[str, Any],
    ) -> LogisticsLlmClarificationAssistResult:
        """清洗模型输出。"""

        llm_missing_slots = [
            item
            for item in payload.get("missing_slots", [])
            if isinstance(item, str) and item in self.SLOT_WHITELIST
        ]
        # 规则层已经给出的缺口径是下限，LLM 只能补充，不能把已有口径抹掉。
        missing_slots = self._merge_slots(
            base_slots=list(plan.clarification_missing_slots),
            llm_slots=llm_missing_slots,
        )
        slot_reasons_raw = payload.get("slot_reasons", {})
        slot_reasons = {}
        if isinstance(slot_reasons_raw, dict):
            for key, value in slot_reasons_raw.items():
                if key in self.SLOT_WHITELIST and isinstance(value, str) and value.strip():
                    slot_reasons[key] = value.strip()

        llm_questions = [
            item.strip()
            for item in payload.get("suggested_questions", [])
            if isinstance(item, str) and item.strip()
        ][:3]
        # 模型追问如果不够完整，自动补回规则模板，避免增强后反而问得更少、更差。
        suggested_questions = self._merge_questions(
            llm_questions=llm_questions,
            rule_questions=list(plan.clarification_questions),
        )
        business_summary = payload.get("business_summary")
        if not isinstance(business_summary, str) or not business_summary.strip():
            business_summary = plan.clarification_reason

        confidence = payload.get("confidence", 0.0)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except Exception:  # noqa: BLE001
            confidence = 0.0
        # 部分模型即使给出了完整、可用的追问，也会把 confidence 固定写成 0。
        # 当前在不改变 B/C 边界的前提下，用结构质量派生一个保守置信度，避免好追问被白白丢掉。
        confidence = max(
            confidence,
            self._derive_confidence(
                rule_missing_slots=list(plan.clarification_missing_slots),
                llm_missing_slots=missing_slots,
                suggested_questions=suggested_questions,
                business_summary=business_summary,
            ),
        )

        return LogisticsLlmClarificationAssistResult(
            normalized_question=question.strip(),
            clarification_category=plan.clarification_category,
            missing_slots=missing_slots,
            slot_reasons=slot_reasons,
            suggested_questions=suggested_questions,
            business_summary=business_summary,
            confidence=confidence,
            provider_mode="live",
            llm_model_name=self.model or None,
        )

    def _merge_slots(self, *, base_slots: list[str], llm_slots: list[str]) -> list[str]:
        """合并规则层和 LLM 的缺口径识别结果。

        说明：
            1. 规则层识别出的缺口径是稳定下限，不能被 LLM 覆盖掉；
            2. LLM 只允许补充更多缺口径，不允许删除规则层已有项；
            3. 结果按“规则在前、LLM 新增在后”的顺序输出，便于后续审计。
        """

        merged: list[str] = []
        for item in [*base_slots, *llm_slots]:
            if item and item not in merged:
                merged.append(item)
        return merged

    def _merge_questions(self, *, llm_questions: list[str], rule_questions: list[str]) -> list[str]:
        """合并模型追问和规则模板。

        说明：
            1. 优先保留模型生成的更业务化问法；
            2. 如果模型问得不够完整，就补回规则模板；
            3. 最多保留 5 个问题，避免 LLM 追问覆盖了业务表达却漏掉规则层必须确认的口径。
        """

        merged: list[str] = []
        for item in [*llm_questions, *rule_questions]:
            normalized = item.strip()
            if normalized and normalized not in merged:
                merged.append(normalized)
            if len(merged) >= 5:
                break
        return merged or list(rule_questions)

    def _derive_confidence(
        self,
        *,
        rule_missing_slots: list[str],
        llm_missing_slots: list[str],
        suggested_questions: list[str],
        business_summary: str,
    ) -> float:
        """按输出结构质量派生保守置信度。

        说明：
            1. 当前派生置信度只用于“追问内容是否值得采用”，不影响最终边界仍是 clarification；
            2. 重点看三件事：缺口径是否对齐、追问是否完整、业务摘要是否可读；
            3. 派生值上限控制在 0.95，避免把结构完整误当成绝对正确。
        """

        if not suggested_questions:
            return 0.0

        overlap_score = 0.0
        if rule_missing_slots:
            overlap_count = len(set(rule_missing_slots) & set(llm_missing_slots))
            overlap_score = overlap_count / max(len(set(rule_missing_slots)), 1)
        elif llm_missing_slots:
            overlap_score = 1.0

        question_score = 0.0
        if len(suggested_questions) >= 2:
            question_score = 1.0
        elif len(suggested_questions) == 1:
            question_score = 0.6

        summary_score = 0.0
        if business_summary and len(business_summary.strip()) >= 16:
            summary_score = 1.0
        elif business_summary and len(business_summary.strip()) >= 8:
            summary_score = 0.5

        derived = (overlap_score * 0.45) + (question_score * 0.35) + (summary_score * 0.20)
        return round(min(0.95, derived), 2)

    def _resolve_allowed_categories(self, configured: list[str] | None) -> list[str]:
        """解析允许增强的澄清类别白名单。"""

        raw = configured if configured is not None else settings.llm_clarification_assist_category_whitelist
        allowlist = raw or self.DEFAULT_ALLOWED_CATEGORIES
        return [item for item in allowlist if item in self.DEFAULT_ALLOWED_CATEGORIES]

    @staticmethod
    def _normalize_mode(mode: str | None) -> str:
        """统一澄清辅助模式。"""
        if mode in {"shadow", "assist"}:
            return mode
        return "off"

    def _is_sampled_in(self, question: str, *, normalized_mode: str) -> bool:
        """判断当前问题是否命中澄清辅助抽样。"""

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

    def _write_audit(
        self,
        *,
        trace_id: str | None,
        plan: LogisticsDataQaPlan,
        result: LogisticsLlmClarificationAssistResult,
        sampled_in: bool,
        applied: bool,
        blocked_reason: str | None,
        normalized_mode: str,
    ) -> None:
        """写澄清辅助 JSONL 审计日志。"""

        if not self.audit_enabled:
            return
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        record = LogisticsLlmClarificationAssistAuditRecord(
            created_at=datetime.now().isoformat(timespec="seconds"),
            trace_id=trace_id,
            question=result.normalized_question,
            clarification_category=plan.clarification_category,
            clarification_reason=plan.clarification_reason,
            rule_missing_slots=list(plan.clarification_missing_slots),
            rule_questions=list(plan.clarification_questions),
            assist_enabled=self.enabled,
            assist_mode=normalized_mode,
            sampled_in=sampled_in,
            llm_invoked=result.provider_mode in {"live", "error"},
            llm_provider_mode=result.provider_mode,
            llm_missing_slots=list(result.missing_slots),
            llm_confidence=result.confidence,
            applied=applied,
            final_missing_slots=list(plan.clarification_missing_slots),
            final_questions=list(plan.clarification_questions),
            blocked_reason=blocked_reason,
        )
        with self.audit_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=False) + "\n")

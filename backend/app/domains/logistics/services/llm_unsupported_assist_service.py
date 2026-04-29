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
    LogisticsLlmUnsupportedAssistAuditRecord,
    LogisticsLlmUnsupportedAssistResult,
)


class LogisticsLlmUnsupportedAssistService:
    """物流域 C 类拒答解释辅助服务。

    说明：
        1. 该服务只在规则层已经判定 unsupported 后介入；
        2. LLM 只负责生成业务可理解原因和可改问方向，不能改变最终 C 类裁决；
        3. LLM 不允许查数、生成 SQL、输出最终统计结果或把问题改判成可回答。
    """

    DEFAULT_ALLOWED_CATEGORIES = [
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
    ]

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
        """初始化拒答解释辅助服务。

        参数：
            base_url: LLM 服务地址，默认读取 settings。
            api_key: LLM 密钥，默认读取 settings。
            model: LLM 模型名，默认读取 settings。
            client: 测试用 OpenAI 兼容客户端。
            enabled: 是否启用辅助。
            mode: off / shadow / assist；shadow 只审计不采用。
            sample_rate: 采样比例。
            min_confidence: 采用 LLM 输出的最低置信度。
            audit_enabled: 是否写审计日志。
            audit_path: 审计 JSONL 路径。
            allowed_categories: 允许 LLM 辅助解释的 unsupported 类别。
            timeout_seconds: 单次 LLM 调用超时时间。

        返回：
            无返回值。
        """

        self.base_url = base_url if base_url is not None else settings.llm_base_url
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self.model = model if model is not None else settings.llm_model
        self._client = client
        self.enabled = settings.llm_unsupported_assist_enabled if enabled is None else enabled
        self.mode = settings.llm_unsupported_assist_mode if mode is None else mode
        self.sample_rate = settings.llm_unsupported_assist_sample_rate if sample_rate is None else sample_rate
        self.min_confidence = settings.llm_unsupported_assist_min_confidence if min_confidence is None else min_confidence
        self.audit_enabled = settings.llm_unsupported_assist_audit_enabled if audit_enabled is None else audit_enabled
        self.audit_path = audit_path or (settings.log_root / "logistics_llm_unsupported_assist.jsonl")
        self.allowed_categories = self._resolve_allowed_categories(allowed_categories)
        self.timeout_seconds = timeout_seconds

    def is_enabled(self) -> bool:
        """判断当前环境是否具备真实 LLM 调用配置。

        返回：
            True 表示 base_url / api_key / model 均已配置。
        """

        return bool(self.base_url and self.api_key and self.model)

    def apply(
        self,
        *,
        question: str,
        plan: LogisticsDataQaPlan,
        trace_id: str | None = None,
    ) -> LogisticsDataQaPlan:
        """在规则已判定 unsupported 后，尝试生成更业务化拒答解释。

        参数：
            question: 用户原始问题。
            plan: 规则层已生成的 unsupported 计划。
            trace_id: 请求追踪 ID。

        返回：
            可能被增强过解释文本的 plan；intent 与 unsupported 类别不会被 LLM 改写。
        """

        normalized_mode = self._normalize_mode(self.mode)
        result = LogisticsLlmUnsupportedAssistResult(
            normalized_question=question.strip(),
            unsupported_category=plan.unsupported_category,
            business_reason=plan.unsupported_reason or "当前问题暂不支持。",
            suggestions=list(plan.unsupported_suggestions),
            provider_mode="disabled",
            llm_model_name=self.model or None,
        )
        sampled_in = self._is_sampled_in(question, normalized_mode=normalized_mode)
        applied = False
        blocked_reason: str | None = None

        if plan.intent != "unsupported":
            blocked_reason = "plan_not_unsupported"
            self._write_audit(
                trace_id=trace_id,
                question=question,
                plan=plan,
                result=result,
                sampled_in=sampled_in,
                applied=applied,
                blocked_reason=blocked_reason,
                normalized_mode=normalized_mode,
            )
            return plan

        if not self.enabled or normalized_mode == "off":
            blocked_reason = "unsupported_assist_off"
            self._write_audit(
                trace_id=trace_id,
                question=question,
                plan=plan,
                result=result,
                sampled_in=sampled_in,
                applied=applied,
                blocked_reason=blocked_reason,
                normalized_mode=normalized_mode,
            )
            return plan

        if not sampled_in:
            blocked_reason = "unsupported_assist_not_sampled"
            self._write_audit(
                trace_id=trace_id,
                question=question,
                plan=plan,
                result=result,
                sampled_in=sampled_in,
                applied=applied,
                blocked_reason=blocked_reason,
                normalized_mode=normalized_mode,
            )
            return plan

        if not plan.unsupported_category or plan.unsupported_category not in self.allowed_categories:
            blocked_reason = "unsupported_category_not_allowlisted"
            self._write_audit(
                trace_id=trace_id,
                question=question,
                plan=plan,
                result=result,
                sampled_in=sampled_in,
                applied=applied,
                blocked_reason=blocked_reason,
                normalized_mode=normalized_mode,
            )
            return plan

        if not self.is_enabled():
            blocked_reason = "llm_not_configured"
            self._write_audit(
                trace_id=trace_id,
                question=question,
                plan=plan,
                result=result,
                sampled_in=sampled_in,
                applied=applied,
                blocked_reason=blocked_reason,
                normalized_mode=normalized_mode,
            )
            return plan

        result = self._request_unsupported_assist(question=question, plan=plan)
        if result.provider_mode != "live":
            blocked_reason = "llm_not_live"
            self._write_audit(
                trace_id=trace_id,
                question=question,
                plan=plan,
                result=result,
                sampled_in=sampled_in,
                applied=applied,
                blocked_reason=blocked_reason,
                normalized_mode=normalized_mode,
            )
            return plan

        if normalized_mode == "shadow":
            blocked_reason = "shadow_mode_only_audit"
            self._write_audit(
                trace_id=trace_id,
                question=question,
                plan=plan,
                result=result,
                sampled_in=sampled_in,
                applied=applied,
                blocked_reason=blocked_reason,
                normalized_mode=normalized_mode,
            )
            return plan

        if result.confidence < self.min_confidence:
            blocked_reason = "llm_low_confidence"
            self._write_audit(
                trace_id=trace_id,
                question=question,
                plan=plan,
                result=result,
                sampled_in=sampled_in,
                applied=applied,
                blocked_reason=blocked_reason,
                normalized_mode=normalized_mode,
            )
            return plan

        if result.business_reason.strip():
            plan.unsupported_reason = result.business_reason.strip()
        if result.suggestions:
            plan.unsupported_suggestions = result.suggestions
        plan.unsupported_assist_used = True
        plan.unsupported_assist_provider_mode = result.provider_mode
        applied = True

        self._write_audit(
            trace_id=trace_id,
            question=question,
            plan=plan,
            result=result,
            sampled_in=sampled_in,
            applied=applied,
            blocked_reason=blocked_reason,
            normalized_mode=normalized_mode,
        )
        return plan

    def _request_unsupported_assist(
        self,
        *,
        question: str,
        plan: LogisticsDataQaPlan,
    ) -> LogisticsLlmUnsupportedAssistResult:
        """调用外部 LLM 生成拒答解释候选。

        参数：
            question: 用户原始问题。
            plan: 规则层 unsupported 计划。

        返回：
            清洗后的 LLM 拒答解释候选。
        """

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
                    {"role": "user", "content": self._build_user_prompt(question=question, plan=plan)},
                ],
            )
            content = completion.choices[0].message.content or "{}"
            payload = self._extract_json(content)
            return self._normalize_payload(question=question, plan=plan, payload=payload)
        except Exception as exc:  # noqa: BLE001
            return LogisticsLlmUnsupportedAssistResult(
                normalized_question=question.strip(),
                unsupported_category=plan.unsupported_category,
                business_reason=plan.unsupported_reason or "当前问题暂不支持。",
                suggestions=list(plan.unsupported_suggestions),
                provider_mode="error",
                provider_error=str(exc),
                llm_model_name=self.model or None,
            )

    def _build_system_prompt(self) -> str:
        """构建拒答解释辅助系统提示词。

        返回：
            约束 LLM 只做解释与可改问建议的系统提示词。
        """

        return (
            "你是物流数据问答系统的“拒答解释辅助层”。\n"
            "规则层已经明确判定当前问题暂不支持，你不能把它改判成可回答，不能改成澄清，不能生成 SQL，不能查数，不能编造结果。\n"
            "你的任务只有两个：\n"
            "1. 用业务人员能理解的话解释为什么当前不能回答；\n"
            "2. 给出 1-3 条可改问方向，让用户知道如何改成当前系统能处理的结构化统计问题。\n"
            "输出必须是单个 JSON 对象，不要输出 markdown，不要输出解释段落。\n"
            "JSON 字段：business_reason, suggestions, confidence。\n"
            "要求：\n"
            "- business_reason 不要使用技术错误栈或模型术语；\n"
            "- suggestions 不能承诺系统不具备的预测、ETA、风险评分、原因归因、明细诊断能力；\n"
            "- 如果规则原因已经足够清楚，可以保守复述并优化表达；\n"
            "- confidence 不要默认写 0；当解释和规则类别一致且建议可执行时，confidence 应不低于 0.8。"
        )

    def _build_user_prompt(self, *, question: str, plan: LogisticsDataQaPlan) -> str:
        """构建拒答解释辅助用户提示词。

        参数：
            question: 用户原始问题。
            plan: 规则层 unsupported 计划。

        返回：
            用户提示词文本。
        """

        return (
            f"原始问题：{question}\n"
            f"规则拒答类别：{plan.unsupported_category}\n"
            f"规则拒答原因：{plan.unsupported_reason}\n"
            f"规则可改问建议：{json.dumps(plan.unsupported_suggestions, ensure_ascii=False)}\n"
            "请只输出 JSON。"
        )

    def _extract_json(self, content: str) -> dict[str, Any]:
        """从模型文本中提取 JSON。

        参数：
            content: LLM 返回文本。

        返回：
            JSON 对象；解析失败由调用方捕获。
        """

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
    ) -> LogisticsLlmUnsupportedAssistResult:
        """清洗 LLM 拒答解释输出。

        参数：
            question: 用户原始问题。
            plan: 规则层 unsupported 计划。
            payload: LLM 原始 JSON。

        返回：
            受控的拒答解释结果。
        """

        business_reason = payload.get("business_reason")
        if not isinstance(business_reason, str) or not business_reason.strip():
            business_reason = plan.unsupported_reason or "当前问题暂不支持。"

        suggestions = [
            item.strip()
            for item in payload.get("suggestions", [])
            if isinstance(item, str) and item.strip()
        ][:3]
        if not suggestions:
            suggestions = list(plan.unsupported_suggestions)

        confidence = payload.get("confidence", 0.0)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except Exception:  # noqa: BLE001
            confidence = 0.0
        if business_reason and suggestions:
            confidence = max(confidence, 0.8)

        return LogisticsLlmUnsupportedAssistResult(
            normalized_question=question.strip(),
            unsupported_category=plan.unsupported_category,
            business_reason=business_reason.strip(),
            suggestions=suggestions,
            confidence=confidence,
            provider_mode="live",
            llm_model_name=self.model or None,
        )

    @staticmethod
    def _normalize_mode(mode: str | None) -> str:
        """规范化模式值。

        参数：
            mode: 配置中的模式。

        返回：
            off / shadow / assist 之一。
        """

        normalized = (mode or "off").strip().lower()
        return normalized if normalized in {"off", "shadow", "assist"} else "off"

    def _is_sampled_in(self, question: str, *, normalized_mode: str) -> bool:
        """稳定采样判断。

        参数：
            question: 用户原始问题。
            normalized_mode: 已规范化模式。

        返回：
            True 表示本次请求进入 LLM 拒答解释辅助。
        """

        if normalized_mode == "off":
            return False
        if self.sample_rate >= 1:
            return True
        if self.sample_rate <= 0:
            return False
        digest = hashlib.sha256(question.strip().encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) / 0xFFFFFFFF
        return bucket <= self.sample_rate

    def _resolve_allowed_categories(self, configured: list[str] | None) -> list[str]:
        """解析允许 LLM 辅助解释的 C 类类别。

        参数：
            configured: 外部传入白名单；为空时读取 settings。

        返回：
            最终类别白名单。
        """

        raw = configured if configured is not None else settings.llm_unsupported_assist_category_whitelist
        if not raw:
            return list(self.DEFAULT_ALLOWED_CATEGORIES)
        return [item for item in raw if item in self.DEFAULT_ALLOWED_CATEGORIES]

    def _write_audit(
        self,
        *,
        trace_id: str | None,
        question: str,
        plan: LogisticsDataQaPlan,
        result: LogisticsLlmUnsupportedAssistResult,
        sampled_in: bool,
        applied: bool,
        blocked_reason: str | None,
        normalized_mode: str,
    ) -> None:
        """写入拒答解释辅助审计日志。

        参数：
            trace_id: 请求追踪 ID。
            question: 用户原始问题。
            plan: 最终 plan。
            result: LLM 拒答解释结果。
            sampled_in: 是否进入采样。
            applied: 是否采用 LLM 输出。
            blocked_reason: 未采用原因。
            normalized_mode: off / shadow / assist。

        返回：
            无返回值；审计失败不影响主链路。
        """

        if not self.audit_enabled:
            return
        record = LogisticsLlmUnsupportedAssistAuditRecord(
            created_at=datetime.now().isoformat(timespec="seconds"),
            trace_id=trace_id,
            question=question,
            unsupported_category=plan.unsupported_category,
            rule_reason=plan.unsupported_reason,
            rule_suggestions=list(plan.unsupported_suggestions),
            assist_enabled=self.enabled,
            assist_mode=normalized_mode,  # type: ignore[arg-type]
            sampled_in=sampled_in,
            llm_invoked=result.provider_mode == "live",
            llm_provider_mode=result.provider_mode,
            llm_business_reason=result.business_reason,
            llm_confidence=result.confidence,
            applied=applied,
            final_reason=plan.unsupported_reason,
            final_suggestions=list(plan.unsupported_suggestions),
            blocked_reason=blocked_reason,
        )
        try:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self.audit_path.open("a", encoding="utf-8") as file:
                file.write(record.model_dump_json() + "\n")
        except Exception:  # noqa: BLE001
            return

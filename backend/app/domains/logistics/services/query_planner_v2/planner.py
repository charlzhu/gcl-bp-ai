from __future__ import annotations

from backend.app.core.config import settings
from backend.app.domains.logistics.services.query_planner_v2.capability_registry import (
    LogisticsQueryPlannerV2CapabilityRegistry,
)
from backend.app.domains.logistics.services.query_planner_v2.fallback import LogisticsQueryPlannerV2Fallback
from backend.app.domains.logistics.services.query_planner_v2.legacy_adapter import LogisticsQueryPlannerV2LegacyAdapter
from backend.app.domains.logistics.services.query_planner_v2.llm_parser import LogisticsQueryPlannerV2LlmParser
from backend.app.domains.logistics.services.query_planner_v2.normalizer import LogisticsQueryPlannerV2Normalizer
from backend.app.domains.logistics.services.query_planner_v2.prompt_builder import LogisticsQueryPlannerV2PromptBuilder
from backend.app.domains.logistics.services.query_planner_v2.validator import LogisticsQueryPlannerV2Validator
from backend.app.domains.query_planning.schemas.query_plan_v2 import QueryPlanningV2Plan


class LogisticsQueryPlannerV2:
    """物流领域 Query Planner V2 编排器。

    业务逻辑：
        1. 自然语言问题先交给 LLM 生成 QueryPlan 候选；
        2. 后端归一化和 Validator 做白名单/字段/时间/B/C 边界校验；
        3. 校验通过只生成 shadow QueryPlanningV2Plan，不替换正式物流 QA；
        4. 任何不可用或校验失败都回退旧 planner。
    """

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        mode: str | None = None,
        min_confidence: float | None = None,
        allowed_query_keys: list[str] | None = None,
        registry: LogisticsQueryPlannerV2CapabilityRegistry | None = None,
        prompt_builder: LogisticsQueryPlannerV2PromptBuilder | None = None,
        llm_parser: LogisticsQueryPlannerV2LlmParser | object | None = None,
        normalizer: LogisticsQueryPlannerV2Normalizer | None = None,
        validator: LogisticsQueryPlannerV2Validator | None = None,
        legacy_adapter: LogisticsQueryPlannerV2LegacyAdapter | None = None,
        fallback: LogisticsQueryPlannerV2Fallback | None = None,
    ) -> None:
        """初始化 Query Planner V2 编排器。

        参数：
            enabled/mode/min_confidence/allowed_query_keys: 灰度配置；默认读取 settings。
            registry/prompt_builder/llm_parser/normalizer/validator: 可注入组件，便于 TDD。
            legacy_adapter/fallback: 与旧 planner 的适配和回退组件。
        返回：无。
        """

        self.enabled = settings.logistics_query_planner_v2_enabled if enabled is None else enabled
        self.mode = self._normalize_mode(mode if mode is not None else settings.logistics_query_planner_v2_mode)
        self.registry = registry or LogisticsQueryPlannerV2CapabilityRegistry()
        configured_allowed = allowed_query_keys if allowed_query_keys is not None else settings.logistics_query_planner_v2_allowed_query_keys
        registry_keys = sorted(self.registry.allowed_query_keys())
        self.config_errors: list[str] = []
        if configured_allowed:
            self.allowed_query_keys = [key for key in configured_allowed if key in self.registry.allowed_query_keys()]
            if not self.allowed_query_keys:
                self.config_errors.append("allowed_query_keys_no_valid_entries")
        else:
            self.allowed_query_keys = registry_keys
        self.min_confidence = (
            settings.logistics_query_planner_v2_min_confidence if min_confidence is None else min_confidence
        )
        self.prompt_builder = prompt_builder or LogisticsQueryPlannerV2PromptBuilder()
        self.llm_parser = llm_parser or LogisticsQueryPlannerV2LlmParser(enabled=self.enabled)
        self.normalizer = normalizer or LogisticsQueryPlannerV2Normalizer()
        self.validator = validator or LogisticsQueryPlannerV2Validator(
            registry=self.registry,
            min_confidence=self.min_confidence,
            allowed_query_keys=set(self.allowed_query_keys),
        )
        self.legacy_adapter = legacy_adapter or LogisticsQueryPlannerV2LegacyAdapter()
        self.fallback = fallback or LogisticsQueryPlannerV2Fallback()

    def should_use(self) -> bool:
        """判断是否进入 V2 LLM 候选流程。"""

        return bool(self.enabled and self.mode in {"shadow", "assist"} and not self.config_errors)

    def build_shadow_plan(self, question: str, *, trace_id: str | None = None) -> QueryPlanningV2Plan:
        """构建物流 Query Planner V2 shadow 计划。

        参数：
            question: 用户原始问题。
            trace_id: 请求追踪号。
        返回：
            QueryPlanningV2Plan；校验失败时为旧 planner fallback 快照。
        """

        if not self.enabled or self.mode not in {"shadow", "assist"}:
            return self.fallback.to_query_plan(question=question, trace_id=trace_id, reason="llm_disabled")
        if self.config_errors:
            return self.fallback.to_query_plan(
                question=question,
                trace_id=trace_id,
                reason="config_invalid::" + ";".join(self.config_errors),
            )

        system_prompt = self.prompt_builder.build_system_prompt(self.registry, allowed_query_keys=self.allowed_query_keys)
        user_prompt = self.prompt_builder.build_user_prompt(question)
        candidate = self.llm_parser.parse(
            question=question,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            allowed_query_keys=list(self.allowed_query_keys),
        )
        if candidate.provider_mode != "live":
            reason = candidate.provider_error or f"llm_not_live::{candidate.provider_mode}"
            return self.fallback.to_query_plan(question=question, trace_id=trace_id, reason=reason)

        normalized_candidate = self.normalizer.normalize(candidate, question=question)
        validation = self.validator.validate(normalized_candidate, original_question=question)
        if not validation.accepted:
            return self.fallback.to_query_plan(
                question=question,
                trace_id=trace_id,
                reason="validation_failed::" + ";".join(validation.errors),
            )

        legacy_rule_plan = self.fallback.build_legacy_plan(question)
        return self.legacy_adapter.to_query_plan(
            candidate=normalized_candidate,
            validation=validation,
            original_question=question,
            trace_id=trace_id,
            legacy_rule_plan=legacy_rule_plan,
            mode=self.mode,
        )

    @staticmethod
    def _normalize_mode(value: str | None) -> str:
        """归一化模式配置。"""

        normalized = (value or "off").strip().lower()
        return normalized if normalized in {"off", "shadow", "assist"} else "off"


__all__ = ["LogisticsQueryPlannerV2"]

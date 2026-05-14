from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from backend.app.domains.logistics.services.query_planner_v2.capability_registry import (
    LogisticsQueryPlannerV2CapabilityRegistry,
)
from backend.app.domains.logistics.services.query_planner_v2.llm_parser import (
    LogisticsQueryPlannerV2Candidate,
    LogisticsQueryPlannerV2LlmParser,
)


@dataclass
class LogisticsQueryPlannerV2ValidationResult:
    """物流 Query Planner V2 校验结果。

    参数：
        accepted: 是否允许进入 shadow deterministic plan。
        candidate: 归一后的候选。
        errors: 阻断原因列表。
        warnings: 非阻断提示。
    返回：
        Validator 对 LLM 候选的完整裁决。
    """

    accepted: bool
    candidate: LogisticsQueryPlannerV2Candidate
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class LogisticsQueryPlannerV2Validator:
    """物流 Query Planner V2 后端确定性校验器。

    业务逻辑：
        1. 以 Capability Registry 为唯一白名单；
        2. 校验字段、指标、维度、聚合、时间范围和实体归一化；
        3. B/C 类边界和危险字段一律 fail closed，不允许 LLM 反向放行。
    """

    ALLOWED_ORIGINS = {"合肥", "阜宁"}
    # 目的城市不要求穷举全业务城市，但当前 MVP 测试线路必须可识别马鞍山。
    KNOWN_ROUTE_CITIES = {"马鞍山", "南京", "广州"}
    ALLOWED_VEHICLE_TYPES = {"17.5", "13", "9.6", "4.2"}

    def __init__(
        self,
        *,
        registry: LogisticsQueryPlannerV2CapabilityRegistry | None = None,
        min_confidence: float = 0.9,
        allowed_query_keys: set[str] | list[str] | None = None,
    ) -> None:
        """初始化校验器。

        参数：
            registry: query_key 能力注册表。
            min_confidence: 允许放行的最低 LLM 置信度。
            allowed_query_keys: 可选配置层 query_key 白名单。
        返回：无。
        """

        self.registry = registry or LogisticsQueryPlannerV2CapabilityRegistry()
        self.min_confidence = min_confidence
        self.allowed_query_keys = set(allowed_query_keys or [])

    def validate(self, candidate: LogisticsQueryPlannerV2Candidate, *, original_question: str) -> LogisticsQueryPlannerV2ValidationResult:
        """校验 LLM QueryPlan 候选。

        参数：
            candidate: 归一后的 QueryPlan 候选。
            original_question: 用户原始问题，用于 B/C 边界和多段路径识别。
        返回：
            accepted=false 时必须走 fallback 或澄清，不能执行。
        """

        errors: list[str] = []
        warnings: list[str] = []

        if candidate.provider_mode != "live":
            errors.append(f"llm_not_live::{candidate.provider_mode}")
        forbidden = LogisticsQueryPlannerV2LlmParser._find_forbidden_fields(candidate.raw_payload)
        for field_name in sorted(forbidden):
            errors.append(f"forbidden_field::{field_name}")
        if candidate.unsupported_reason:
            errors.append("llm_requested_unsupported")
        if candidate.clarification_questions:
            errors.append("llm_requested_clarification")
        if not 0.0 <= self.min_confidence <= 1.0:
            errors.append(f"config_invalid::min_confidence_range::{self.min_confidence:.3f}")
        if not 0.0 <= candidate.confidence <= 1.0:
            errors.append(f"invalid_confidence_range::{candidate.confidence:.3f}")
        elif candidate.confidence < self.min_confidence:
            errors.append(f"low_confidence::{candidate.confidence:.3f}<{self.min_confidence:.3f}")
        if self._is_policy_locked_question(original_question) or self._is_policy_locked_question(candidate.normalized_question):
            errors.append("policy_locked::bc_boundary")

        capability = self.registry.get(candidate.query_key)
        if capability is None:
            errors.append(f"unknown_query_key::{candidate.query_key}")
        elif self.allowed_query_keys and candidate.query_key not in self.allowed_query_keys:
            errors.append(f"query_key_not_allowed_by_config::{candidate.query_key}")

        if capability is not None:
            self._validate_filters(candidate, capability, errors)
            self._validate_collection("metric", candidate.metrics, capability.allowed_metrics, errors)
            self._validate_collection("dimension", candidate.dimensions, capability.allowed_dimensions, errors)
            self._validate_collection("group_by", candidate.group_by, capability.allowed_group_by, errors)
            self._validate_collection("aggregation", candidate.aggregations, capability.allowed_aggregations, errors)
            if candidate.compare_mode and candidate.compare_mode not in capability.allowed_compare_modes:
                errors.append(f"compare_mode_not_allowed::{candidate.compare_mode}")
            self._validate_question_years(candidate, capability.time_scope, original_question, errors)
            self._validate_time_scope(candidate, capability.time_scope, errors)
            self._validate_normalized_entities(candidate, errors)

        if self._has_multi_hop_route(original_question):
            errors.append("multi_hop_route_requires_clarification")

        return LogisticsQueryPlannerV2ValidationResult(
            accepted=not errors,
            candidate=candidate,
            errors=self._dedupe(errors),
            warnings=warnings,
        )

    def _validate_filters(self, candidate: LogisticsQueryPlannerV2Candidate, capability: Any, errors: list[str]) -> None:
        """校验过滤字段白名单和必填槽位。"""

        for key in candidate.filters:
            if key not in capability.allowed_filters:
                errors.append(f"filter_not_allowed::{key}")
        for key in sorted(capability.required_filters):
            if candidate.filters.get(key) in (None, "", []):
                errors.append(f"missing_required_filter::{key}")
        for group in capability.required_any_filters:
            if not any(candidate.filters.get(key) not in (None, "", []) for key in group):
                joined = "|".join(sorted(group))
                errors.append(f"missing_required_any_filter::{joined}")

    @staticmethod
    def _validate_collection(label: str, values: list[str], allowed: set[str], errors: list[str]) -> None:
        """校验指标/维度/分组/聚合是否在白名单内。"""

        for value in values:
            if value not in allowed:
                errors.append(f"{label}_not_allowed::{value}")

    @classmethod
    def _validate_question_years(
        cls,
        candidate: LogisticsQueryPlannerV2Candidate,
        time_scope: str,
        original_question: str,
        errors: list[str],
    ) -> None:
        """用原始问题中的显式年份反校验 LLM 候选，防止年份被候选改写绕过。"""

        question_years = cls._extract_years_from_text(original_question)
        if not question_years:
            return
        candidate_years = cls._extract_candidate_years(candidate)
        if set(candidate_years) != set(question_years):
            errors.append("question_candidate_years_conflict")
        if time_scope == "historical_2023_2025" and any(year < 2023 or year > 2025 for year in question_years):
            errors.append("time_scope_mismatch::question_historical_2023_2025")
        if 2026 in question_years and any(year <= 2025 for year in question_years):
            errors.append("time_scope_mismatch::question_historical_system_mixed")

    @classmethod
    def _extract_candidate_years(cls, candidate: LogisticsQueryPlannerV2Candidate) -> list[int]:
        """从候选 filters/time_range 中抽取年份，用于和原始问题做一致性比对。"""

        raw_years = candidate.filters.get("years") or candidate.time_range.get("years") or []
        if not isinstance(raw_years, list):
            raw_years = [raw_years]
        years: list[int] = []
        for item in raw_years:
            try:
                years.append(int(item))
            except (TypeError, ValueError):
                years.extend(cls._extract_years_from_text(str(item)))
        return cls._dedupe_ints(years)

    @staticmethod
    def _extract_years_from_text(text: str) -> list[int]:
        """从用户问题或 LLM 字符串槽位中抽取四位/两位年份。"""

        years: list[int] = []
        for match in re.findall(r"20\d{2}", text or ""):
            years.append(int(match))
        for match in re.findall(r"(?<!\d)(2\d)\s*年", text or ""):
            years.append(2000 + int(match))
        return LogisticsQueryPlannerV2Validator._dedupe_ints(years)

    @staticmethod
    def _dedupe_ints(values: list[int]) -> list[int]:
        """保持顺序去重年份。"""

        result: list[int] = []
        seen: set[int] = set()
        for value in values:
            if value not in seen:
                seen.add(value)
                result.append(value)
        return result

    @staticmethod
    def _validate_time_scope(candidate: LogisticsQueryPlannerV2Candidate, time_scope: str, errors: list[str]) -> None:
        """校验历史台账和 2026 系统数据不能误混。"""

        allowed_time_range_keys = {"years", "months", "source_scope", "time_scope"}
        for key in candidate.time_range:
            if key not in allowed_time_range_keys:
                errors.append(f"time_range_key_not_allowed::{key}")
        for scope_key in ("source_scope", "time_scope"):
            declared_scope = candidate.time_range.get(scope_key)
            if declared_scope and str(declared_scope).strip() != time_scope:
                errors.append(f"time_scope_mismatch::{scope_key}::{declared_scope}")

        years = candidate.filters.get("years") or candidate.time_range.get("years") or []
        if not isinstance(years, list):
            years = [years]
        normalized_years: list[int] = []
        for item in years:
            try:
                normalized_years.append(int(item))
            except (TypeError, ValueError):
                errors.append(f"invalid_year::{item}")
        if time_scope == "historical_2023_2025" and any(year < 2023 or year > 2025 for year in normalized_years):
            errors.append("time_scope_mismatch::historical_2023_2025")
        if 2026 in normalized_years and any(year <= 2025 for year in normalized_years):
            errors.append("time_scope_mismatch::historical_system_mixed")

    def _validate_normalized_entities(self, candidate: LogisticsQueryPlannerV2Candidate, errors: list[str]) -> None:
        """校验始发地、目的地、车型是否已经归一到受控表达。"""

        origin = candidate.filters.get("origin_place")
        if origin and origin not in self.ALLOWED_ORIGINS:
            errors.append(f"origin_not_normalized::{origin}")
        city = candidate.filters.get("city")
        if city and (not isinstance(city, str) or "到" in city or "至" in city or city not in self.KNOWN_ROUTE_CITIES):
            errors.append(f"city_not_normalized::{city}")
        vehicle_type = candidate.filters.get("vehicle_type")
        if vehicle_type and vehicle_type not in self.ALLOWED_VEHICLE_TYPES:
            errors.append(f"vehicle_type_not_normalized::{vehicle_type}")

    @staticmethod
    def _is_policy_locked_question(question: str) -> bool:
        """识别不能被 LLM 反向放行的 B/C 边界问题。"""

        compact = "".join(question.split())
        locked_keywords = (
            "预测未来",
            "未来三个月",
            "未来一个月",
            "到货时间",
            "ETA",
            "原因是什么",
            "什么原因",
            "方案设计",
            "评分模型",
        )
        return any(keyword in compact for keyword in locked_keywords)

    @staticmethod
    def _has_multi_hop_route(question: str) -> bool:
        """识别多段路径；当前 MVP 只支持单始发地到单目的地。"""

        compact = "".join(question.split())
        route_part = re.sub(r"^.*?年", "", compact)
        connector_count = len(re.findall(r"(至|到|->|→)", route_part))
        return connector_count >= 2

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        """保持顺序去重。"""

        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value not in seen:
                seen.add(value)
                result.append(value)
        return result


__all__ = ["LogisticsQueryPlannerV2ValidationResult", "LogisticsQueryPlannerV2Validator"]

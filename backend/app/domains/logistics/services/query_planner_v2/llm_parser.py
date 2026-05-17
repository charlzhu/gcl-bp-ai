from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.config import settings


class LogisticsQueryPlannerV2Candidate(BaseModel):
    """物流 Query Planner V2 的 LLM QueryPlan 候选。

    参数：
        normalized_question: LLM 或后端归一后的问题文本。
        intent: 受控意图。
        query_key: 白名单 query_key 候选。
        filters: 受控过滤槽位。
        metrics/dimensions/group_by/aggregations: 指标、维度、分组和聚合槽位。
        compare_mode: 对比或趋势模式。
        time_range: LLM 提供的时间范围快照。
        confidence: LLM 对候选的置信度。
        clarification_questions: 缺槽时的澄清问题。
        unsupported_reason: 不支持原因。
        provider_mode/provider_error: LLM 调用或解析状态。
        raw_payload: 原始 JSON，用于 Validator 递归安全检查。
    返回：
        只描述候选计划、不执行查询的数据对象。
    """

    model_config = ConfigDict(extra="forbid")

    normalized_question: str = ""
    intent: str = "unknown"
    query_key: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    aggregations: list[str] = Field(default_factory=list)
    compare_mode: str | None = None
    time_range: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    clarification_questions: list[str] = Field(default_factory=list)
    unsupported_reason: str | None = None
    provider_mode: str = "live"
    provider_error: str | None = None
    llm_model_name: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class LogisticsQueryPlannerV2LlmParser:
    """物流 Query Planner V2 的 LLM 调用和 JSON 解析器。

    业务逻辑：
        1. 只允许 OpenAI 兼容模型返回 JSON 候选；
        2. 解析器不执行 SQL、不查库、不计算业务数值；
        3. 一旦发现危险字段，立即 fail closed 到 error 候选。
    """

    FORBIDDEN_FIELDS = {
        "sql",
        "where",
        "where_clause",
        "database",
        "table_name",
        "answer",
        "computed_value",
        "python_code",
        "tool_call",
    }
    ALLOWED_TOP_LEVEL_FIELDS = {
        "intent",
        "query_key",
        "candidate_query_keys",
        "filters",
        "metrics",
        "dimensions",
        "group_by",
        "aggregations",
        "compare_mode",
        "time_range",
        "confidence",
        "clarification_questions",
        "unsupported_reason",
        "normalized_question",
    }

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        client: Any | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        """初始化解析器。

        参数：
            enabled: 是否允许真实 LLM 调用；默认读取 Query Planner V2 配置。
            base_url/api_key/model: OpenAI 兼容配置。
            client: 测试注入客户端。
            timeout_seconds: 外部调用超时。
        返回：无。
        """

        self.enabled = settings.logistics_query_planner_v2_enabled if enabled is None else enabled
        self.base_url = base_url if base_url is not None else settings.llm_base_url
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self.model = model if model is not None else settings.llm_model
        self._client = client
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        """判断当前是否具备真实 LLM 调用条件。"""

        return bool(self.enabled and (self._client or (self.base_url and self.api_key and self.model)))

    def parse(
        self,
        *,
        question: str,
        system_prompt: str,
        user_prompt: str,
        allowed_query_keys: list[str],
    ) -> LogisticsQueryPlannerV2Candidate:
        """调用 LLM 并解析 QueryPlan JSON。

        参数：
            question: 原始问题。
            system_prompt: 系统提示词。
            user_prompt: 用户提示词。
            allowed_query_keys: 白名单 query_key，供审计记录使用。
        返回：
            解析后的候选；不可用或失败时返回 provider_mode=disabled/error。
        """

        if not self.is_available():
            return LogisticsQueryPlannerV2Candidate(
                normalized_question=question.strip(),
                provider_mode="disabled",
                provider_error="当前环境未启用或未配置物流 Query Planner V2 LLM。",
                raw_payload={"allowed_query_keys": allowed_query_keys},
            )
        try:
            from openai import OpenAI

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
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = completion.choices[0].message.content or "{}"
            candidate = self.parse_text(content, question=question)
            candidate.llm_model_name = self.model or None
            return candidate
        except Exception as exc:  # noqa: BLE001
            return LogisticsQueryPlannerV2Candidate(
                normalized_question=question.strip(),
                provider_mode="error",
                provider_error=str(exc),
                llm_model_name=self.model or None,
            )

    def parse_text(self, content: str, *, question: str) -> LogisticsQueryPlannerV2Candidate:
        """解析 LLM 文本响应中的严格 JSON。

        参数：
            content: 模型返回文本。
            question: 原始问题。
        返回：
            provider_mode=live 的候选，或 provider_mode=error 的 fail-closed 候选。
        """

        try:
            payload = self._extract_json(content)
            forbidden = self._find_forbidden_fields(payload)
            if forbidden:
                first = sorted(forbidden)[0]
                return self._error_candidate(question, f"forbidden_field::{first}", raw_payload=payload)
            unexpected = sorted(set(payload) - self.ALLOWED_TOP_LEVEL_FIELDS)
            if unexpected:
                return self._error_candidate(question, f"unexpected_field::{unexpected[0]}", raw_payload=payload)
            return self._candidate_from_payload(payload, question=question)
        except Exception as exc:  # noqa: BLE001
            return self._error_candidate(question, f"json_parse_error::{exc}")

    def _candidate_from_payload(self, payload: dict[str, Any], *, question: str) -> LogisticsQueryPlannerV2Candidate:
        """把 JSON dict 转成候选对象。"""

        query_key = payload.get("query_key")
        if not query_key and isinstance(payload.get("candidate_query_keys"), list) and payload["candidate_query_keys"]:
            query_key = payload["candidate_query_keys"][0]
        raw_filters = payload.get("filters")
        filters: dict[str, Any] = dict(raw_filters) if isinstance(raw_filters, dict) else {}
        raw_time_range = payload.get("time_range")
        time_range: dict[str, Any] = dict(raw_time_range) if isinstance(raw_time_range, dict) else {}
        return LogisticsQueryPlannerV2Candidate(
            normalized_question=str(payload.get("normalized_question") or question).strip(),
            intent=str(payload.get("intent") or "unknown"),
            query_key=str(query_key).strip() if query_key else None,
            filters=dict(filters),
            metrics=self._as_str_list(payload.get("metrics")),
            dimensions=self._as_str_list(payload.get("dimensions")),
            group_by=self._as_str_list(payload.get("group_by")),
            aggregations=self._as_str_list(payload.get("aggregations")),
            compare_mode=str(payload.get("compare_mode")).strip() if payload.get("compare_mode") else None,
            time_range=dict(time_range),
            confidence=self._as_float(payload.get("confidence")),
            clarification_questions=self._as_str_list(payload.get("clarification_questions")),
            unsupported_reason=str(payload.get("unsupported_reason")).strip() if payload.get("unsupported_reason") else None,
            provider_mode="live",
            raw_payload=dict(payload),
        )

    @classmethod
    def _extract_json(cls, content: str) -> dict[str, Any]:
        """解析严格 JSON 对象，拒绝 markdown 或解释性前后缀。"""

        stripped = content.strip()
        if not stripped.startswith("{") or not stripped.endswith("}"):
            raise ValueError("LLM 输出必须是严格 JSON object，不能包含 markdown 或额外文本")
        try:
            def _reject_non_standard_constant(value: str) -> None:
                """拒绝 NaN/Infinity 等 Python json 默认会放行的非标准 JSON 常量。"""
                raise ValueError(f"LLM 输出包含非标准 JSON 常量：{value}")

            parsed = json.loads(stripped, parse_constant=_reject_non_standard_constant)
        except json.JSONDecodeError as exc:
            raise ValueError(str(exc)) from exc
        if not isinstance(parsed, dict):
            raise ValueError("LLM 输出不是 JSON object")
        return parsed

    @classmethod
    def _find_forbidden_fields(cls, value: Any) -> set[str]:
        """递归扫描危险字段名。"""

        found: set[str] = set()
        if isinstance(value, dict):
            for key, item in value.items():
                normalized_key = str(key).strip().lower()
                if normalized_key in cls.FORBIDDEN_FIELDS:
                    found.add(normalized_key)
                found.update(cls._find_forbidden_fields(item))
        elif isinstance(value, list):
            for item in value:
                found.update(cls._find_forbidden_fields(item))
        return found

    @staticmethod
    def _as_str_list(value: Any) -> list[str]:
        """把 LLM 输出归一成字符串列表。"""

        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value).strip()
        return [text] if text else []

    @staticmethod
    def _as_float(value: Any) -> float:
        """把置信度安全转换为 float。"""

        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _error_candidate(
        question: str,
        reason: str,
        *,
        raw_payload: dict[str, Any] | None = None,
    ) -> LogisticsQueryPlannerV2Candidate:
        """构造 fail-closed 候选。"""

        return LogisticsQueryPlannerV2Candidate(
            normalized_question=question.strip(),
            provider_mode="error",
            provider_error=reason,
            raw_payload=raw_payload or {},
        )


__all__ = ["LogisticsQueryPlannerV2Candidate", "LogisticsQueryPlannerV2LlmParser"]

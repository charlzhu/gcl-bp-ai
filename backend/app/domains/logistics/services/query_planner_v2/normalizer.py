from __future__ import annotations

import re
from typing import Any

from backend.app.domains.logistics.services.query_planner_v2.llm_parser import LogisticsQueryPlannerV2Candidate


class LogisticsQueryPlannerV2Normalizer:
    """物流 Query Planner V2 槽位归一化器。

    业务逻辑：
        1. LLM 只负责语义理解，输出可能包含口语化槽位；
        2. 后端归一化器把年份、车型、始发地、目的地、指标口径收敛到受控值；
        3. 未识别实体不静默改写，保留原值交给 Validator fail closed。
    """

    ROUTE_DEFAULT_QUERY_KEYS = {"hist_route_pricing_analysis", "hist_avg_fee_by_month"}

    ORIGIN_ALIASES = {
        "合肥": "合肥",
        "安徽合肥": "合肥",
        "阜宁": "阜宁",
        "安徽阜宁": "阜宁",
    }
    CITY_ALIASES = {
        "马鞍山": "马鞍山",
        "马鞍山市": "马鞍山",
        "南京": "南京",
        "南京市": "南京",
        "广州": "广州",
        "广州市": "广州",
    }
    VEHICLE_ALIASES = {
        "17.5": "17.5",
        "17.5米": "17.5",
        "17.5米车": "17.5",
        "17.5车": "17.5",
        "17米五": "17.5",
        "17米五车": "17.5",
        "十七米五": "17.5",
        "十七米五车": "17.5",
    }
    METRIC_ALIASES = {
        "平均运费": "avg_fee",
        "均费": "avg_fee",
        "平均每车多少钱": "avg_fee",
        "avg_fee": "avg_fee",
        "总运费": "total_fee",
        "总费用": "total_fee",
        "total_fee": "total_fee",
        "车次数": "row_count",
        "记录数": "row_count",
        "row_count": "row_count",
    }

    def normalize(self, candidate_or_payload: LogisticsQueryPlannerV2Candidate | dict[str, Any], *, question: str) -> LogisticsQueryPlannerV2Candidate:
        """归一化 LLM QueryPlan 候选。

        参数：
            candidate_or_payload: Parser 输出候选或测试/上游传入的 dict。
            question: 原始问题，用于补充年份和趋势/对比语义。
        返回：
            归一后的候选，仍不代表可执行，必须继续 Validator 校验。
        """

        candidate = self._ensure_candidate(candidate_or_payload, question=question)
        filters = self._normalize_filters(
            candidate.filters,
            candidate.time_range,
            question=question,
            query_key=candidate.query_key,
        )
        metrics = self._normalize_metrics(candidate.metrics, question=question)
        aggregations = self._normalize_aggregations(candidate.aggregations, metrics=metrics, question=question)
        compare_mode = self._normalize_compare_mode(candidate.compare_mode, question=question)
        group_by = self._normalize_str_list(candidate.group_by)
        dimensions = self._normalize_str_list(candidate.dimensions)
        if compare_mode == "monthly_trend" and "month" not in group_by:
            group_by.append("month")
        if compare_mode == "year_compare" and "year" not in group_by:
            group_by.append("year")

        return candidate.model_copy(
            update={
                "normalized_question": candidate.normalized_question or question.strip(),
                "query_key": self._normalize_query_key(candidate.query_key),
                "filters": filters,
                "metrics": metrics,
                "dimensions": dimensions,
                "group_by": group_by,
                "aggregations": aggregations,
                "compare_mode": compare_mode,
                "time_range": self._normalize_time_range(candidate.time_range, filters),
            },
            deep=True,
        )

    def _ensure_candidate(self, value: LogisticsQueryPlannerV2Candidate | dict[str, Any], *, question: str) -> LogisticsQueryPlannerV2Candidate:
        """把 dict 或候选对象统一成 Candidate。"""

        if isinstance(value, LogisticsQueryPlannerV2Candidate):
            return value
        query_key = value.get("query_key")
        if not query_key and isinstance(value.get("candidate_query_keys"), list) and value["candidate_query_keys"]:
            query_key = value["candidate_query_keys"][0]
        filters = value.get("filters") if isinstance(value.get("filters"), dict) else {}
        time_range = value.get("time_range") if isinstance(value.get("time_range"), dict) else {}
        return LogisticsQueryPlannerV2Candidate(
            normalized_question=str(value.get("normalized_question") or question).strip(),
            intent=str(value.get("intent") or "unknown"),
            query_key=str(query_key).strip() if query_key else None,
            filters=dict(filters),
            metrics=self._normalize_str_list(value.get("metrics")),
            dimensions=self._normalize_str_list(value.get("dimensions")),
            group_by=self._normalize_str_list(value.get("group_by")),
            aggregations=self._normalize_str_list(value.get("aggregations")),
            compare_mode=str(value.get("compare_mode")).strip() if value.get("compare_mode") else None,
            time_range=dict(time_range),
            confidence=self._as_float(value.get("confidence"), default=0.0),
            clarification_questions=self._normalize_str_list(value.get("clarification_questions")),
            unsupported_reason=str(value.get("unsupported_reason")).strip() if value.get("unsupported_reason") else None,
            provider_mode=str(value.get("provider_mode") or "live"),
            provider_error=str(value.get("provider_error")).strip() if value.get("provider_error") else None,
            raw_payload=dict(value),
        )

    def _normalize_filters(
        self,
        filters: dict[str, Any],
        time_range: dict[str, Any],
        *,
        question: str,
        query_key: str | None,
    ) -> dict[str, Any]:
        """归一化过滤槽位。"""

        normalized = dict(filters)
        years = self._normalize_years(normalized.get("years") or normalized.get("year") or time_range.get("years"), question=question)
        if years:
            normalized["years"] = years
            normalized.pop("year", None)
        if "origin_place" in normalized:
            normalized["origin_place"] = self._normalize_origin(normalized["origin_place"])
        if "city" in normalized:
            normalized["city"] = self._normalize_city(normalized["city"])
        if "province" in normalized:
            normalized["province"] = self._normalize_province(normalized["province"])
        if "vehicle_type" in normalized:
            normalized["vehicle_type"] = self._normalize_vehicle_type(normalized["vehicle_type"])
        if query_key in self.ROUTE_DEFAULT_QUERY_KEYS:
            normalized["view_mode"] = self._normalize_view_mode(normalized.get("view_mode"), question=question)
            normalized["price_metric"] = self._normalize_price_metric(normalized.get("price_metric"), question=question)
        return {key: value for key, value in normalized.items() if value not in (None, "", [])}

    def _normalize_time_range(self, time_range: dict[str, Any], filters: dict[str, Any]) -> dict[str, Any]:
        """把 filters 中的年份同步到 time_range，方便审计。"""

        normalized = dict(time_range)
        if filters.get("years"):
            normalized["years"] = list(filters["years"])
        return normalized

    @classmethod
    def _normalize_years(cls, value: Any, *, question: str) -> list[int]:
        """归一化年份列表；问题中显式多个年份时优先保留全部年份。"""

        extracted_from_question = cls._extract_years_from_text(question)
        raw_values: list[Any] = []
        if isinstance(value, list):
            raw_values.extend(value)
        elif value is not None:
            raw_values.append(value)
        years: list[int] = []
        for item in raw_values:
            if isinstance(item, int):
                years.append(item)
                continue
            years.extend(cls._extract_years_from_text(str(item)))
        if len(extracted_from_question) > len(set(years)):
            years = extracted_from_question
        elif not years:
            years = extracted_from_question
        return cls._dedupe_ints(years)

    @staticmethod
    def _extract_years_from_text(text: str) -> list[int]:
        """从中文问题中抽取 2023-2026 或 23/24/25/26 年。"""

        years: list[int] = []
        for match in re.findall(r"20(?:2[3-6])", text):
            years.append(int(match))
        for match in re.findall(r"(?<!\d)(2[3-6])\s*年", text):
            years.append(2000 + int(match))
        return LogisticsQueryPlannerV2Normalizer._dedupe_ints(years)

    @staticmethod
    def _dedupe_ints(values: list[int]) -> list[int]:
        """保持顺序去重整数列表。"""

        result: list[int] = []
        seen: set[int] = set()
        for value in values:
            if value not in seen:
                seen.add(value)
                result.append(value)
        return result

    @classmethod
    def _normalize_origin(cls, value: Any) -> str:
        """归一化受控始发地；未知值原样返回给 Validator。"""

        text = str(value).strip().replace(" ", "")
        return cls.ORIGIN_ALIASES.get(text, text)

    @classmethod
    def _normalize_city(cls, value: Any) -> str:
        """归一化目的城市；未知城市只去掉末尾“市”，再交给 Validator。"""

        text = str(value).strip().replace(" ", "")
        if text in cls.CITY_ALIASES:
            return cls.CITY_ALIASES[text]
        return text[:-1] if text.endswith("市") else text

    @staticmethod
    def _normalize_province(value: Any) -> str:
        """归一化省份名称。"""

        text = str(value).strip().replace(" ", "")
        return text[:-1] if text.endswith("省") else text

    @classmethod
    def _normalize_vehicle_type(cls, value: Any) -> str:
        """归一化车型表达。"""

        text = str(value).strip().replace(" ", "")
        if text in cls.VEHICLE_ALIASES:
            return cls.VEHICLE_ALIASES[text]
        if re.search(r"17(?:\.5|米五|米5|\.5米|\.5米车|\.5车)", text):
            return "17.5"
        return text

    @classmethod
    def _normalize_metrics(cls, values: list[str], *, question: str) -> list[str]:
        """归一化指标槽位。"""

        normalized = [cls.METRIC_ALIASES.get(str(item).strip(), str(item).strip()) for item in values if str(item).strip()]
        if not normalized:
            compact = "".join(question.split())
            if any(keyword in compact for keyword in ("平均运费", "均费", "平均多少钱", "平均每车")):
                normalized.append("avg_fee")
            if any(keyword in compact for keyword in ("总运费", "总费用")):
                normalized.append("total_fee")
        if "avg_fee" in normalized and "row_count" not in normalized:
            normalized.append("row_count")
        return cls._dedupe_strs(normalized)

    @staticmethod
    def _normalize_aggregations(values: list[str], *, metrics: list[str], question: str) -> list[str]:
        """归一化聚合算子。"""

        mapping = {"average": "avg", "mean": "avg", "avg": "avg", "sum": "sum", "count": "count"}
        normalized = [mapping.get(str(item).strip().lower(), str(item).strip().lower()) for item in values if str(item).strip()]
        compact = "".join(question.split())
        if not normalized and ("avg_fee" in metrics or any(keyword in compact for keyword in ("平均", "均费"))):
            normalized.append("avg")
        return LogisticsQueryPlannerV2Normalizer._dedupe_strs(normalized)

    @staticmethod
    def _normalize_compare_mode(value: str | None, *, question: str) -> str | None:
        """归一化对比/趋势模式。"""

        compact = "".join(question.split())
        if value:
            raw = value.strip().lower()
            mapping = {
                "yearly_compare": "year_compare",
                "year_compare": "year_compare",
                "month_trend": "monthly_trend",
                "monthly_trend": "monthly_trend",
                "month_over_month": "month_over_month",
                "year_over_year": "year_over_year",
                "none": "none",
            }
            return mapping.get(raw, raw)
        if "月度趋势" in compact or "按月" in compact:
            return "monthly_trend"
        if "对比" in compact and len(LogisticsQueryPlannerV2Normalizer._extract_years_from_text(compact)) >= 2:
            return "year_compare"
        return None

    @staticmethod
    def _normalize_view_mode(value: Any, *, question: str) -> str:
        """归一化运价视图模式。"""

        text = str(value).strip() if value is not None else ""
        compact = "".join(question.split())
        if text in {"avg_fee", "average_fee", "均费", "平均运费"}:
            return "avg_fee"
        if text in {"monthly_trend", "month_trend", "月度趋势"} or "月度趋势" in compact or "按月" in compact:
            return "monthly_trend"
        if any(keyword in compact for keyword in ("平均", "均费", "平均多少钱")):
            return "avg_fee"
        return text or "avg_fee"

    @staticmethod
    def _normalize_price_metric(value: Any, *, question: str) -> str:
        """归一化价格口径。

        业务口径：
            1. “报价 / 单价 / 运价”指源表 `unit_price_per_vehicle`，不等同于均价；
            2. “均价 / 平均运费”才走总费用除以车次的后续计算口径；
            3. 仅用户明确说“总费用/总运费/运费”时按 `total_fee` 处理。
        """

        text = str(value).strip() if value is not None else ""
        compact_question = "".join(question.split())
        if text in {"unit_price_per_vehicle", "单价/车", "报价", "单价", "运价"}:
            return "unit_price_per_vehicle"
        if any(keyword in compact_question for keyword in ("报价", "单价", "运价")):
            return "unit_price_per_vehicle"
        if text in {"total_fee", "总费用", "总运费", "运费", "avg_fee_per_trip", "avg_fee", "均价", "平均运费", "平均每车费用", "单车均费"}:
            return "total_fee"
        return text or "total_fee"

    @staticmethod
    def _normalize_query_key(value: str | None) -> str | None:
        """清理 query_key 空白。"""

        return value.strip() if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _normalize_str_list(value: Any) -> list[str]:
        """把任意值转成字符串列表。"""

        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value).strip()
        return [text] if text else []

    @staticmethod
    def _dedupe_strs(values: list[str]) -> list[str]:
        """保持顺序去重字符串。"""

        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value and value not in seen:
                seen.add(value)
                result.append(value)
        return result

    @staticmethod
    def _as_float(value: Any, *, default: float) -> float:
        """安全转换 float。"""

        try:
            return float(value)
        except (TypeError, ValueError):
            return default


__all__ = ["LogisticsQueryPlannerV2Normalizer"]

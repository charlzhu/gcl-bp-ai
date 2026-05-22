"""M15：灰度门禁。

业务逻辑：
    1. 根据 query_key 将问题分类为 SIMPLE_AGGREGATE / DIMENSION_SPLIT / MULTI_METRIC_SUMMARY。
    2. 每类问题 + 每域独立灰度开关。
    3. 灰度关闭时回退到正式 QA 链路。
    4. 支持 JSON 格式环境变量：NL2SQL_GRAYSCALE_CONFIG
"""

from __future__ import annotations

import enum
import json
import os
from typing import Any

from pydantic import BaseModel, Field

from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaResult

from backend.app.domains.logistics.services.nl2sql.m15_grayscale_decision_result import (
    DEFAULT_GRAYSCALE_DOMAIN,
    GRAYSCALE_CONFIG_ENV_FLAG,
    GRAYSCALE_TYPES_ENV_FLAG,
)

# query_key 到 GrayscaleQuestionType 的映射白名单
_QUERY_KEY_TO_TYPE: dict[str, str] = {
    # 简单 aggregate
    "total_fee": "simple_aggregate",
    "hist_total_fee_city_rank": "simple_aggregate",
    "hist_total_fee_province_rank": "simple_aggregate",
    "hist_total_fee_summary": "simple_aggregate",
    "hist_carrier_fee_rank": "simple_aggregate",
    "hist_mw_fee_summary": "simple_aggregate",
    "hist_total_tons_summary": "simple_aggregate",
    "hist_shipment_count": "simple_aggregate",
    # 按维度拆分
    "composite_decomposed": "dimension_split",
    "yearly_mw_breakdown": "dimension_split",
    "monthly_trend": "dimension_split",
    "carrier_split": "dimension_split",
    "province_breakdown": "dimension_split",
    "city_breakdown": "dimension_split",
    # 多指标汇总
    "multi_metric_comparison": "multi_metric_summary",
    "comprehensive_summary": "multi_metric_summary",
}

# 自动匹配 hist_ 前缀
_HIST_PREFIX = "hist_"


class GrayscaleQuestionType(str, enum.Enum):
    """灰度问题类型。

    参数：
        SIMPLE_AGGREGATE: 简单 aggregate。
        DIMENSION_SPLIT: 按维度拆分。
        MULTI_METRIC_SUMMARY: 多指标汇总。
    """

    SIMPLE_AGGREGATE = "simple_aggregate"
    DIMENSION_SPLIT = "dimension_split"
    MULTI_METRIC_SUMMARY = "multi_metric_summary"


class LogisticsNl2SqlGrayscaleConfig(BaseModel):
    """灰度配置。

    参数：
        enabled_types: 已启用的灰度问题类型集合；默认空集（全部关闭）。
        enabled_domains: 已启用的灰度域集合；默认空集（全部关闭）。
        domain_types: 域粒度的类型开关，key=domain，value=已启用的类型集合。
    """

    enabled_types: set[str] = Field(default_factory=set)
    enabled_domains: set[str] = Field(default_factory=set)
    domain_types: dict[str, set[str]] = Field(default_factory=dict)

    def is_enabled(self, question_type: GrayscaleQuestionType, domain: str = DEFAULT_GRAYSCALE_DOMAIN) -> bool:
        """指定问题类型 + 域的灰度是否已启用。

        参数：
            question_type: 问题类型。
            domain: 业务域名称，默认 logistics。
        返回：
            是否启用灰度。
        """
        # 先检查域是否启用
        if self.enabled_domains:
            if domain not in self.enabled_domains:
                return False

        # 域粒度类型开关优先
        if domain in self.domain_types and question_type.value in self.domain_types[domain]:
            return True

        # 全局类型开关作为兜底
        if question_type.value in self.enabled_types:
            return True

        return False

    def enable(self, question_type: GrayscaleQuestionType, domain: str = DEFAULT_GRAYSCALE_DOMAIN) -> None:
        """启用指定域+类型的灰度。"""
        if domain not in self.domain_types:
            self.domain_types[domain] = set()
        self.domain_types[domain].add(question_type.value)
        # 也加入全局
        self.enabled_types.add(question_type.value)
        self.enabled_domains.add(domain)

    def disable(self, question_type: GrayscaleQuestionType, domain: str = DEFAULT_GRAYSCALE_DOMAIN) -> None:
        """关闭指定域+类型的灰度。"""
        if domain in self.domain_types:
            self.domain_types[domain].discard(question_type.value)
        self.enabled_types.discard(question_type.value)

    @classmethod
    def from_env(
        cls,
        env_flag: str = GRAYSCALE_TYPES_ENV_FLAG,
        config_flag: str = GRAYSCALE_CONFIG_ENV_FLAG,
    ) -> LogisticsNl2SqlGrayscaleConfig:
        """从环境变量构造灰度配置。

        优先解析 NL2SQL_GRAYSCALE_CONFIG（JSON格式），
        降级到 LOGISTICS_NL2SQL_GRAYSCALE_TYPES（旧格式）。

        旧格式示例：LOGISTICS_NL2SQL_GRAYSCALE_TYPES="simple_aggregate,dimension_split"
        新格式示例：NL2SQL_GRAYSCALE_CONFIG='{"logistics": ["simple_aggregate"]}'
        """
        config_json = os.environ.get(config_flag, "")
        if config_json:
            try:
                parsed = json.loads(config_json)
                if isinstance(parsed, dict):
                    enabled_types: set[str] = set()
                    enabled_domains: set[str] = set()
                    domain_types: dict[str, set[str]] = {}
                    for domain, types in parsed.items():
                        if isinstance(types, list):
                            enabled_domains.add(domain)
                            domain_types[domain] = set(types)
                            enabled_types.update(types)
                    return cls(
                        enabled_types=enabled_types,
                        enabled_domains=enabled_domains,
                        domain_types=domain_types,
                    )
            except (json.JSONDecodeError, TypeError):
                pass

        # 旧格式兼容
        legacy = os.environ.get(env_flag, "")
        if legacy:
            types = {t.strip() for t in legacy.split(",") if t.strip()}
            return cls(
                enabled_types=types,
                enabled_domains={DEFAULT_GRAYSCALE_DOMAIN},
                domain_types={DEFAULT_GRAYSCALE_DOMAIN: types},
            )

        return cls()


class LogisticsNl2SqlGrayscaleDecision(BaseModel):
    """灰度决策结果。

    参数：
        should_grayscale: 是否应灰度切换（使用 NL2SQL shadow 结果作为正式回答）。
        question_type: 分类后的问题类型；None 表示未知类型（不灰度）。
        domain: 灰度决策所属的业务域。
        fallback_reason: 灰度不启动的原因；None 表示正常灰度。
    """

    should_grayscale: bool = False
    question_type: GrayscaleQuestionType | None = None
    domain: str = DEFAULT_GRAYSCALE_DOMAIN
    fallback_reason: str | None = None


class LogisticsNl2SqlGrayscaleGate:
    """灰度门禁：根据配置和问题类型 + 域决定是否灰度切换。

    参数：
        config: 灰度配置；默认全部关闭。
    """

    def __init__(
        self,
        config: LogisticsNl2SqlGrayscaleConfig | None = None,
    ) -> None:
        """初始化灰度门禁。

        参数：
            config: 灰度配置，缺省全部关闭。
        """
        self.config = config or LogisticsNl2SqlGrayscaleConfig()

    @staticmethod
    def classify_query_key(query_key: str | None) -> GrayscaleQuestionType | None:
        """根据 query_key 分类问题类型。

        参数：
            query_key: formal QA 的 query_key。
        返回：
            已知 query_key 对应的问题类型；无映射返回 None。
        """
        if query_key is None:
            return None

        # 精确匹配
        mapped = _QUERY_KEY_TO_TYPE.get(query_key)
        if mapped is not None:
            return GrayscaleQuestionType(mapped)

        # 前缀匹配：hist_ 前缀映射到 simple_aggregate
        if query_key.startswith(_HIST_PREFIX) and len(query_key) > len(_HIST_PREFIX):
            return GrayscaleQuestionType.SIMPLE_AGGREGATE

        return None

    def decide(
        self,
        *,
        formal: LogisticsDataQaResult,
        domain: str = DEFAULT_GRAYSCALE_DOMAIN,
    ) -> LogisticsNl2SqlGrayscaleDecision:
        """基于正式 QA 结果 + 域决定是否灰度切换。

        参数：
            formal: 正式 QA 结果。
            domain: 业务域名称；默认 logistics。
        返回：
            LogisticsNl2SqlGrayscaleDecision 灰度决策。
        """
        query_key = formal.query_plan.query_key
        question_type = self.classify_query_key(query_key)

        # 如果域已完全启用灰度（domain_types 中有该域的全部类型），直接灰度
        if self.config.enabled_domains and domain in self.config.enabled_domains:
            return LogisticsNl2SqlGrayscaleDecision(
                should_grayscale=True,
                question_type=question_type,
                domain=domain,
                fallback_reason=None,
            )

        if question_type is None:
            return LogisticsNl2SqlGrayscaleDecision(
                should_grayscale=False,
                question_type=None,
                domain=domain,
                fallback_reason="unknown_question_type",
            )

        if not self.config.is_enabled(question_type, domain=domain):
            return LogisticsNl2SqlGrayscaleDecision(
                should_grayscale=False,
                question_type=question_type,
                domain=domain,
                fallback_reason="grayscale_disabled",
            )

        return LogisticsNl2SqlGrayscaleDecision(
            should_grayscale=True,
            question_type=question_type,
            domain=domain,
            fallback_reason=None,
        )


__all__ = [
    "GrayscaleQuestionType",
    "LogisticsNl2SqlGrayscaleConfig",
    "LogisticsNl2SqlGrayscaleDecision",
    "LogisticsNl2SqlGrayscaleGate",
]

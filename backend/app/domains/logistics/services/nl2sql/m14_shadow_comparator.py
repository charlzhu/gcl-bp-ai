"""M14：Shadow 结果对比器。

业务逻辑：
    1. 对比 formal QA 结果与 NL2SQL shadow 摘要在状态、行数、错误码上的差异。
    2. LENIENT 模式（默认）：行数差异 abs(diff) <= threshold 认为是匹配。
    3. STRICT 模式：使用更严格的阈值。
    4. disabled shadow 不计入差异统计。
"""

from __future__ import annotations

import enum
from typing import Any

from pydantic import BaseModel, Field

from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaResult
from backend.app.domains.logistics.services.nl2sql.live_shadow_adapter import (
    LogisticsNl2SqlLiveShadowSummary,
)

_DISABLED_STATUS_CODES: frozenset[str] = frozenset({"disabled"})
_NON_ERROR_DISABLE_CODES: frozenset[str] = frozenset({"m10c_live_shadow_disabled"})


class ShadowCompareMode(str, enum.Enum):
    """对比模式。

    参数：
        LENIENT: 宽容模式，行数差异<=threshold视为匹配。
        STRICT: 严格模式，更小的阈值。
    """

    LENIENT = "lenient"
    STRICT = "strict"


class LogisticsNl2SqlShadowComparatorConfig(BaseModel):
    """对比器配置。

    参数：
        compare_mode: 对比模式，默认 LENIENT。
        row_count_diff_threshold: 行数差异绝对值阈值（LENIENT 默认5，STRICT 默认2）。
        row_count_diff_ratio: 行数差异比例阈值（LENIENT 默认0.1=10%）。
    """

    compare_mode: ShadowCompareMode = ShadowCompareMode.LENIENT
    row_count_diff_threshold: int = 5
    row_count_diff_ratio: float = 0.1

    def resolve_threshold(self) -> int:
        """根据模式返回实际阈值。"""
        if self.compare_mode == ShadowCompareMode.LENIENT:
            return self.row_count_diff_threshold
        return min(self.row_count_diff_threshold, 2)  # STRICT 模式强制更严


class LogisticsNl2SqlShadowComparison(BaseModel):
    """formal vs shadow 对比结果。

    参数：
        formal_status: formal QA 状态码。
        shadow_status: shadow 状态。
        formal_row_count: formal 结果行数。
        shadow_row_count: shadow 结果行数。
        formal_status_match: 状态是否一致。
        row_count_match: 行数是否匹配（考虑阈值）。
        error_code_match: 错误码是否匹配。
        mismatch_flags: 不匹配标记列表。
        overall_match: 总体是否匹配（所有 mismatch_flags 为空）。
    """

    formal_status: str
    shadow_status: str
    formal_row_count: int
    shadow_row_count: int
    formal_status_match: bool
    row_count_match: bool
    error_code_match: bool
    mismatch_flags: list[str] = Field(default_factory=list)

    @property
    def overall_match(self) -> bool:
        """所有字段均匹配时返回 True。"""
        return len(self.mismatch_flags) == 0

    def has_mismatch(self, flag: str) -> bool:
        """检查是否存在指定 mismatch flag。"""
        return flag in self.mismatch_flags


class LogisticsNl2SqlShadowComparator:
    """对比 formal QA 结果与 NL2SQL shadow 摘要的结构化差异。

    参数：
        config: 对比器配置；默认 LENIENT 模式。
    """

    def __init__(
        self,
        config: LogisticsNl2SqlShadowComparatorConfig | None = None,
    ) -> None:
        """初始化对比器。

        参数：
            config: 对比配置，缺省使用默认 LENIENT 模式。
        """
        self.config = config or LogisticsNl2SqlShadowComparatorConfig()

    def compare(
        self,
        *,
        formal: LogisticsDataQaResult,
        shadow: LogisticsNl2SqlLiveShadowSummary,
    ) -> LogisticsNl2SqlShadowComparison:
        """执行一次 formal vs shadow 对比。

        参数：
            formal: 正式 QA 结果。
            shadow: NL2SQL shadow 摘要。

        返回：
            LogisticsNl2SqlShadowComparison 对比结果。
        """
        # shadow disabled 时不计入差异
        if shadow.enabled is False or shadow.status in _DISABLED_STATUS_CODES:
            return self._disabled_comparison(formal=formal, shadow=shadow)

        mismatch_flags: list[str] = []

        # 1. 状态对比
        formal_status = self._get_formal_status(formal)
        formal_status_match = self._compare_formal_status(formal_status, shadow)
        if not formal_status_match:
            mismatch_flags.append("shadow_status_mismatch")

        # 2. 行数对比
        formal_row_count = len(formal.result_table.rows)
        shadow_row_count = shadow.row_count
        row_count_match = self._compare_row_count(formal_row_count, shadow_row_count)
        if not row_count_match:
            mismatch_flags.append("row_count_mismatch")

        # 3. 错误码对比
        error_code_match = self._compare_error_codes(shadow)
        if not error_code_match:
            mismatch_flags.append("error_code_mismatch")

        return LogisticsNl2SqlShadowComparison(
            formal_status=formal_status,
            shadow_status=shadow.status,
            formal_row_count=formal_row_count,
            shadow_row_count=shadow_row_count,
            formal_status_match=formal_status_match,
            row_count_match=row_count_match,
            error_code_match=error_code_match,
            mismatch_flags=mismatch_flags,
        )

    @staticmethod
    def _get_formal_status(result: LogisticsDataQaResult) -> str:
        """从 formal QA 结果提取状态码。"""
        if result.status is not None:
            return result.status.code
        return "UNKNOWN"

    @staticmethod
    def _compare_formal_status(
        formal_status: str,
        shadow: LogisticsNl2SqlLiveShadowSummary,
    ) -> bool:
        """对比 formal 状态与 shadow 状态是否一致。

        shadow disabled/skipped 状态下不做严格匹配。
        """
        if shadow.status in _DISABLED_STATUS_CODES:
            return True
        # formal SUCCESS 对应 shadow success
        if formal_status == "SUCCESS":
            return shadow.status == "success"
        if formal_status == "EMPTY_RESULT":
            return shadow.status in ("success", "skipped")
        if formal_status == "ERROR":
            return shadow.status in ("error", "validation_failed")
        if formal_status == "CLARIFICATION":
            return shadow.status in ("skipped", "disabled")
        if formal_status == "UNSUPPORTED":
            return shadow.status in ("skipped", "disabled")
        return True

    def _compare_row_count(
        self,
        formal_row_count: int,
        shadow_row_count: int,
    ) -> bool:
        """比较 formal 与 shadow 的行数差异是否在允许范围内。

        参数：
            formal_row_count: 正式结果行数。
            shadow_row_count: shadow 结果行数。
        返回：
            行数差异在阈值内返回 True。
        """
        diff = abs(formal_row_count - shadow_row_count)
        threshold = self.config.resolve_threshold()
        # 绝对差异 <= 阈值
        if diff <= threshold:
            return True
        # 比例差异 <= 比例阈值
        max_count = max(formal_row_count, shadow_row_count)
        if max_count > 0 and (diff / max_count) <= self.config.row_count_diff_ratio:
            return True
        return False

    @staticmethod
    def _compare_error_codes(shadow: LogisticsNl2SqlLiveShadowSummary) -> bool:
        """检查 shadow 错误码是否异常。

        disabled 相关错误码不计为不匹配。
        """
        if not shadow.error_codes:
            return True
        # 如果所有错误码都是非致命 disable 码
        non_disabled = [c for c in shadow.error_codes if c not in _NON_ERROR_DISABLE_CODES]
        return len(non_disabled) == 0

    @staticmethod
    def _disabled_comparison(
        *,
        formal: LogisticsDataQaResult,
        shadow: LogisticsNl2SqlLiveShadowSummary,
    ) -> LogisticsNl2SqlShadowComparison:
        """shadow disabled 时返回中性对比结果（全部标记为匹配）。"""
        return LogisticsNl2SqlShadowComparison(
            formal_status=LogisticsNl2SqlShadowComparator._get_formal_status(formal),
            shadow_status=shadow.status,
            formal_row_count=len(formal.result_table.rows),
            shadow_row_count=shadow.row_count,
            formal_status_match=True,
            row_count_match=True,
            error_code_match=True,
            mismatch_flags=[],
        )


__all__ = [
    "LogisticsNl2SqlShadowComparison",
    "LogisticsNl2SqlShadowComparator",
    "LogisticsNl2SqlShadowComparatorConfig",
    "ShadowCompareMode",
]

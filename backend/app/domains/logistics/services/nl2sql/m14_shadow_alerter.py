"""M14：Shadow 告警器。

业务逻辑：
    1. 根据对比器结果输出结构化告警。
    2. 支持累计差异率统计。
    3. 可禁用告警输出（仅统计）。
    4. 统计窗口限制内存中保留的记录数。
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Any

from pydantic import BaseModel, Field, field_validator

from backend.app.domains.logistics.services.nl2sql.m14_shadow_comparator import (
    LogisticsNl2SqlShadowComparison,
)

logger = logging.getLogger(__name__)


class LogisticsNl2SqlShadowAlerterConfig(BaseModel):
    """告警器配置。

    参数：
        warn_on_mismatch: 是否输出 logger.warning 告警；默认 True。
        stats_window: 统计窗口内保留的记录数，默认 1000。
    """

    warn_on_mismatch: bool = True
    stats_window: int = 1000


class LogisticsNl2SqlShadowAlertRecord(BaseModel):
    """单次告警记录。

    参数：
        alert_fired: 是否触发了告警。
        trace_id: 关联 trace_id。
        question: 用户问题（截断到前200字符）。
        mismatch_flags: 不匹配标记列表。
        formal_status: formal QA 状态码。
        shadow_status: shadow 状态。
        formal_row_count: formal 行数。
        shadow_row_count: shadow 行数。
    """

    alert_fired: bool
    trace_id: str | None = None
    question: str = ""
    mismatch_flags: list[str] = Field(default_factory=list)
    formal_status: str = ""
    shadow_status: str = ""
    formal_row_count: int = 0
    shadow_row_count: int = 0

    @field_validator("question", mode="before")
    @classmethod
    def _truncate_question(cls, value: Any) -> str:
        """截断超长问题到前 200 字符。"""
        text = str(value or "")
        return text[:200]


class LogisticsNl2SqlShadowAlertStats(BaseModel):
    """累计告警统计。

    参数：
        total_shadow: 总 shadow 次数。
        diff_count: 差异次数。
        diff_ratio: 差异比例（diff_count / total_shadow）。
    """

    total_shadow: int = 0
    diff_count: int = 0
    diff_ratio: float = 0.0


class LogisticsNl2SqlShadowAlerter:
    """根据对比结果输出结构化告警并累计统计。

    参数：
        config: 告警器配置；默认启用告警，窗口 1000。
    用法：
        alerter = LogisticsNl2SqlShadowAlerter()
        record = alerter.evaluate(comparison=..., trace_id="t1", question="q1")
        stats = alerter.get_stats()
    """

    def __init__(
        self,
        config: LogisticsNl2SqlShadowAlerterConfig | None = None,
    ) -> None:
        """初始化告警器。

        参数：
            config: 告警配置，缺省使用默认配置。
        """
        self.config = config or LogisticsNl2SqlShadowAlerterConfig()
        self._records: deque[LogisticsNl2SqlShadowAlertRecord] = deque(maxlen=self.config.stats_window)

    def evaluate(
        self,
        *,
        comparison: LogisticsNl2SqlShadowComparison,
        trace_id: str | None = None,
        question: str = "",
    ) -> LogisticsNl2SqlShadowAlertRecord:
        """评估一次对比结果，返回告警记录。

        参数：
            comparison: 对比器输出的对比结果。
            trace_id: 关联 trace_id。
            question: 用户问题。

        返回：
            LogisticsNl2SqlShadowAlertRecord 告警记录。
        """
        alert_fired = (
            len(comparison.mismatch_flags) > 0
            and self.config.warn_on_mismatch
            and comparison.shadow_status != "disabled"
        )

        record = LogisticsNl2SqlShadowAlertRecord(
            alert_fired=alert_fired,
            trace_id=trace_id,
            question=question,
            mismatch_flags=comparison.mismatch_flags,
            formal_status=comparison.formal_status,
            shadow_status=comparison.shadow_status,
            formal_row_count=comparison.formal_row_count,
            shadow_row_count=comparison.shadow_row_count,
        )

        self._records.append(record)

        if alert_fired:
            logger.warning(
                "NL2SQL shadow mismatch: trace_id=%s flags=%s formal=%s shadow=%s "
                "formal_rows=%d shadow_rows=%d question=%.80s",
                trace_id,
                ",".join(comparison.mismatch_flags),
                comparison.formal_status,
                comparison.shadow_status,
                comparison.formal_row_count,
                comparison.shadow_row_count,
                question,
            )

        return record

    def get_stats(self) -> LogisticsNl2SqlShadowAlertStats:
        """获取当前统计报表。

        返回：
            LogisticsNl2SqlShadowAlertStats 统计结果。
        """
        total = len(self._records)
        if total == 0:
            return LogisticsNl2SqlShadowAlertStats()
        diff_count = sum(1 for r in self._records if r.alert_fired)
        return LogisticsNl2SqlShadowAlertStats(
            total_shadow=total,
            diff_count=diff_count,
            diff_ratio=diff_count / total,
        )

    def reset_stats(self) -> None:
        """重置统计。"""
        self._records.clear()


__all__ = [
    "LogisticsNl2SqlShadowAlerter",
    "LogisticsNl2SqlShadowAlerterConfig",
    "LogisticsNl2SqlShadowAlertRecord",
    "LogisticsNl2SqlShadowAlertStats",
]

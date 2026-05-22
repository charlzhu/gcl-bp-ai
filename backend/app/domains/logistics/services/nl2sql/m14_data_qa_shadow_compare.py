"""M14：data_qa_service 中串联 Shadow 对比与告警的轻量工具函数。

业务逻辑：
    1. 从 _build_nl2sql_live_shadow_audit 返回的 dict 重建 LogisticsNl2SqlLiveShadowSummary。
    2. 调用 LogisticsNl2SqlShadowComparator 做 structured 对比。
    3. 调用 LogisticsNl2SqlShadowAlerter 输出告警并累计统计。
    4. 将 comparison 摘要附加到 response_meta["nl2sql_live_shadow_comparison"]。
    5. 异常不传递，旁路失败不影响正式 QA。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaResult
from backend.app.domains.logistics.services.nl2sql.live_shadow_adapter import (
    LogisticsNl2SqlLiveShadowSummary,
)
from backend.app.domains.logistics.services.nl2sql.m14_shadow_alerter import (
    LogisticsNl2SqlShadowAlerter,
)
from backend.app.domains.logistics.services.nl2sql.m14_shadow_comparator import (
    LogisticsNl2SqlShadowComparator,
    LogisticsNl2SqlShadowComparison,
)

logger = logging.getLogger(__name__)

# 默认日志路径，可通过环境变量覆盖
_DEFAULT_NL2SQL_ALERT_LOG_PATH = "ai/outbox/nl2sql-shadow-compare-alerts.jsonl"

# 全局共享的 alerter 实例（进程级别，data_qa_service 也是进程级别）
_global_shadow_alerter: LogisticsNl2SqlShadowAlerter | None = None


def get_global_shadow_alerter() -> LogisticsNl2SqlShadowAlerter:
    """获取全局共享的告警器实例。"""
    global _global_shadow_alerter
    if _global_shadow_alerter is None:
        _global_shadow_alerter = LogisticsNl2SqlShadowAlerter()
    return _global_shadow_alerter


def compare_nl2sql_shadow_and_attach(
    *,
    result: LogisticsDataQaResult,
    nl2sql_shadow_summary_dict: dict[str, Any] | None,
    trace_id: str | None,
    question: str,
    response_meta: dict[str, Any],
    comparator: LogisticsNl2SqlShadowComparator | None = None,
    alerter: LogisticsNl2SqlShadowAlerter | None = None,
) -> None:
    """对比 formal QA 结果与 NL2SQL shadow 摘要，并把 comparison + alert 附加到 response_meta。

    参数：
        result: 已完成的形式 QA 结果（LogisticsDataQaResult）。
        nl2sql_shadow_summary_dict: _build_nl2sql_live_shadow_audit 返回的 dict（可为 None）。
        trace_id: 当前请求 trace_id。
        question: 用户原始问题。
        response_meta: 当前 response_meta 字典（会被原地修改）。
        comparator: 对比器；缺省默认配置。
        alerter: 告警器；缺省全局实例。

    返回：
        无返回值。response_meta 被原地修改，附加 "nl2sql_live_shadow_comparison" 键。
        所有异常在内部捕获并记录 warning，不向外传递。

    业务逻辑：
        - shadow disabled 时不做对比，不附加 comparison 字段。
        - 对比和告警异常不中断调用方逻辑。
    """
    if nl2sql_shadow_summary_dict is None:
        return

    try:
        # 从 dict 重建 Pydantic 对象
        shadow_summary = LogisticsNl2SqlLiveShadowSummary.model_validate(nl2sql_shadow_summary_dict)
    except Exception as exc:  # noqa: BLE001
        logger.warning("nl2sql shadow comparison: rebuild summary failed: %s", exc)
        return

    # shadow disabled 时不做对比
    if not shadow_summary.enabled or shadow_summary.status == "disabled":
        return

    resolved_comparator = comparator or LogisticsNl2SqlShadowComparator()
    resolved_alerter = alerter or get_global_shadow_alerter()

    try:
        comparison: LogisticsNl2SqlShadowComparison = resolved_comparator.compare(
            formal=result,
            shadow=shadow_summary,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("nl2sql shadow comparison: compare failed: %s", exc)
        return

    try:
        resolved_alerter.evaluate(
            comparison=comparison,
            trace_id=trace_id,
            question=question,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("nl2sql shadow comparison: alerter evaluate failed: %s", exc)
        return

    # 附加 comparison 摘要（只附加敏感字段，不包含原始 SQL 或表名）
    try:
        comparison_json = comparison.model_dump(mode="json")
        response_meta["nl2sql_live_shadow_comparison"] = comparison_json
    except Exception as exc:  # noqa: BLE001
        logger.warning("nl2sql shadow comparison: attach to meta failed: %s", exc)

    # 持久化告警到 JSONL 文件（用于 cron 定时扫描生成差异率日报）
    if not comparison.overall_match:
        try:
            alert_log_path = os.getenv("NL2SQL_SHADOW_ALERT_LOG_PATH", _DEFAULT_NL2SQL_ALERT_LOG_PATH)
            alert_record = {
                "trace_id": trace_id,
                "question": question[:100],
                "domain": shadow_summary.domain if hasattr(shadow_summary, "domain") else "logistics",
                "formal_status": comparison.formal_status,
                "shadow_status": comparison.shadow_status,
                "formal_row_count": comparison.formal_row_count,
                "shadow_row_count": comparison.shadow_row_count,
                "mismatch_flags": comparison.mismatch_flags,
                "ts": __import__("datetime").datetime.now().isoformat(),
            }
            log_dir = os.path.dirname(alert_log_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            with open(alert_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(alert_record, ensure_ascii=False) + "\n")
        except Exception as exc:  # noqa: BLE001
            logger.warning("nl2sql shadow comparison: write alert log failed: %s", exc)


__all__ = [
    "compare_nl2sql_shadow_and_attach",
    "get_global_shadow_alerter",
]

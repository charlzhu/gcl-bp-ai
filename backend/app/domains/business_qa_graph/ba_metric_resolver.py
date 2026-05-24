"""产销存指标别名确定性解析器。

在 LLM SQL 生成前，将用户自然语言中的指标词映射为标准 metric_code。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResolvedMetric:
    metric_id: str = ""
    display_name: str = ""
    metric_code: str = ""
    confidence: float = 0.0
    fallback_reason: str = ""
    # 确定的 SQL WHERE 片段
    sql_filter: str = ""


def resolve_business_analysis_metric(
    question: str,
    metrics: list[dict[str, Any]],
) -> ResolvedMetric:
    """将用户问题中的指标词映射为标准 metric_id。

    参数:
        question: 用户自然语言问题。
        metrics: context 中的 metric_infos 列表（含 metric_id/display_name/aliases）。
    返回:
        ResolvedMetric，包含 sql_filter 供 LLM 直接使用。
    """
    if not metrics:
        return ResolvedMetric(fallback_reason="no_metrics_in_context")

    question_lower = question.lower()
    best_match: dict[str, Any] | None = None
    best_score = 0

    for m in metrics:
        metric_id = m.get("metric_id", "")
        display_name = m.get("display_name", "")
        aliases = list(m.get("aliases", []))

        keywords = [metric_id, display_name] + aliases
        score = 0
        for kw in keywords:
            if kw.lower() in question_lower:
                # 完整匹配得分更高
                score = max(score, len(kw) * 2 if kw.lower() in question_lower else 0)

        if score > best_score:
            best_score = score
            best_match = m

    if not best_match:
        # 无显式匹配：使用默认产量指标
        for m in metrics:
            if m.get("metric_id") == "production_actual_including_oem":
                return ResolvedMetric(
                    metric_id=m.get("metric_id", ""),
                    display_name=m.get("display_name", ""),
                    metric_code=m.get("metric_id", ""),
                    confidence=0.5,
                    sql_filter=f"metric_code = '{m.get('metric_id', '')}'",
                )
        return ResolvedMetric(fallback_reason="no_matching_metric")

    metric_id = best_match.get("metric_id", "")
    return ResolvedMetric(
        metric_id=metric_id,
        display_name=best_match.get("display_name", ""),
        metric_code=metric_id,
        confidence=min(best_score / 20.0, 1.0),
        sql_filter=f"metric_code = '{metric_id}'",
    )

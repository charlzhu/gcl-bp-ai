from __future__ import annotations

from typing import Any


class LogisticsMetricResolver:
    """物流域指标解析器。"""

    def resolve(self, question: str, metric_dictionary: dict[str, Any], fallback_metric: str) -> tuple[str, str | None]:
        metrics = metric_dictionary.get("metrics") or {}
        lowered = question.lower()
        for metric_code, item in metrics.items():
            aliases = item.get("aliases", []) if isinstance(item, dict) else []
            for alias in aliases:
                if alias.lower() in lowered:
                    return str(metric_code), item.get("display_name") if isinstance(item, dict) else None
        return fallback_metric, None

from __future__ import annotations

from typing import Any


class LogisticsEnumMapper:
    """物流域枚举映射器。"""

    def map_value(self, enum_type: str, question: str, enum_config: dict[str, Any]) -> tuple[str | None, dict[str, str]]:
        enums = (enum_config.get("enums") or {}).get(enum_type) or {}
        hits: dict[str, str] = {}
        for canonical, aliases in enums.items():
            for alias in aliases:
                if alias in question:
                    hits[alias] = str(canonical)
                    return str(canonical), hits
        return None, hits

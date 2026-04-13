from __future__ import annotations

import re
from typing import Any


class LogisticsTextNormalizer:
    """物流域文本归一器。"""

    def normalize(self, question: str, synonyms_config: dict[str, Any]) -> tuple[str, dict[str, str]]:
        """对用户问题做轻量归一，并返回命中的同义词映射。"""
        normalized = self._basic_normalize(question)
        hit_synonyms: dict[str, str] = {}

        for canonical, item in (synonyms_config.get("terms") or {}).items():
            aliases = item.get("aliases", []) if isinstance(item, dict) else []
            for alias in aliases:
                if not alias:
                    continue
                pattern = re.compile(re.escape(alias), re.IGNORECASE)
                if pattern.search(normalized):
                    normalized = pattern.sub(str(canonical), normalized)
                    hit_synonyms[alias] = str(canonical)
        return normalized, hit_synonyms

    @staticmethod
    def _basic_normalize(text: str) -> str:
        value = text.strip()
        value = value.replace("（", "(").replace("）", ")")
        value = value.replace("：", ":").replace("，", ",")
        value = value.replace("　", " ")
        return re.sub(r"\s+", " ", value)

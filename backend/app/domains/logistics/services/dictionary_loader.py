from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


class LogisticsDictionaryLoader:
    """物流域字典配置加载器。"""

    def __init__(self, base_dir: str | None = None) -> None:
        default_dir = Path(__file__).resolve().parent.parent / "config"
        self.base_dir = Path(base_dir) if base_dir else default_dir

    def load_yaml(self, filename: str) -> dict[str, Any]:
        path = self.base_dir / filename
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def load_synonyms(self) -> dict[str, Any]:
        return self.load_yaml("synonyms.yaml")

    def load_metric_dictionary(self) -> dict[str, Any]:
        return self.load_yaml("metric_dictionary.yaml")

    def load_enum_mappings(self) -> dict[str, Any]:
        return self.load_yaml("enum_mappings.yaml")


@lru_cache(maxsize=4)
def get_default_dictionary_loader(base_dir: str | None = None) -> LogisticsDictionaryLoader:
    """获取默认字典加载器。"""
    return LogisticsDictionaryLoader(base_dir=base_dir)

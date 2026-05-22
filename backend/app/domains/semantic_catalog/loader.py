"""
YAML 文件加载器：从 YAML/JSON 文件加载统一语义资产注册表。

业务逻辑：
    1. 只读取仓库内人工审计的 YAML 文件。
    2. 不连接生产库、不生成 SQL、不触及现有领域 catalog 内部。
    3. 返回强 schema 的 BusinessSemanticCatalog 对象。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from backend.app.domains.semantic_catalog.schema import (
    SemanticMetric,
    SemanticDimension,
    SemanticEntity,
    SemanticCapability,
)
from backend.app.domains.semantic_catalog.catalog import BusinessSemanticCatalog

# 默认 catalog 目录：统一语义资产注册文件存放位置
DEFAULT_UNIFIED_CATALOG_DIR = Path(__file__).resolve().parents[2] / "config" / "unified_catalog"


class SemanticCatalogYamlLoader:
    """统一语义资产 YAML 加载器。

    参数：
        catalog_dir: 可选 catalog 目录；测试可传临时目录。

    返回：
        加载器实例。
    """

    def __init__(self, catalog_dir: str | Path | None = None) -> None:
        """初始化加载器。

        参数：
            catalog_dir: catalog 文件目录，默认使用 config/unified_catalog。
        """
        self.catalog_dir = Path(catalog_dir) if catalog_dir else DEFAULT_UNIFIED_CATALOG_DIR

    def load(self) -> BusinessSemanticCatalog:
        """加载全部 YAML 文件并合并到统一注册表。

        返回：
            填充完成的 BusinessSemanticCatalog 实例。

        业务逻辑：
            按 metrics.yaml → dimensions.yaml → entities.yaml 顺序读取。
            缺失文件按空列表处理（不报错），方便分阶段交付。
        """
        catalog = BusinessSemanticCatalog()

        metrics_data = self._read_yaml("metrics.yaml")
        for item in metrics_data.get("metrics", []):
            metric = SemanticMetric.model_validate(item)
            catalog.register_metric(metric)

        dimensions_data = self._read_yaml("dimensions.yaml")
        for item in dimensions_data.get("dimensions", []):
            dim = SemanticDimension.model_validate(item)
            catalog.register_dimension(dim)

        entities_data = self._read_yaml("entities.yaml")
        for item in entities_data.get("entities", []):
            entity = SemanticEntity.model_validate(item)
            catalog.register_entity(entity)

        capabilities_data = self._read_yaml("capabilities.yaml")
        for item in capabilities_data.get("capabilities", []):
            cap = SemanticCapability.model_validate(item)
            catalog.register_capability(cap)

        return catalog

    def _read_yaml(self, file_name: str) -> dict[str, Any]:
        """读取单个 YAML 文件。

        参数：
            file_name: YAML 文件名。

        返回：
            解析后的字典；缺失文件返回空 dict。

        业务逻辑：
            缺失文件不抛错——支持分阶段交付 YAML 配置。
        """
        path = self.catalog_dir / file_name
        if not path.exists():
            return {}
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"catalog_yaml_must_be_mapping::{path}")
        return data


__all__ = [
    "DEFAULT_UNIFIED_CATALOG_DIR",
    "SemanticCatalogYamlLoader",
]

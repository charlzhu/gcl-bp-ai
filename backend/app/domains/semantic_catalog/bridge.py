"""
统一语义资产桥接层：将现有领域 catalog 只读适配到统一注册表。

业务逻辑：
    1. 不做内改——只从现有 LogisticsSemanticCatalog（及其他领域 catalog）读取数据。
    2. 桥接是单向的：现有 catalog → 统一注册表。
    3. 新增的指标/维度/实体可以直接注册到统一 catalog 中。
    4. 统一 catalog 不替代现有领域 catalog 的 SQLPlan 校验、表白名单等核心链路。
"""

from __future__ import annotations

from backend.app.domains.semantic_catalog.schema import (
    SemanticMetric,
    SemanticDimension,
    SemanticEntity,
)
from backend.app.domains.semantic_catalog.catalog import BusinessSemanticCatalog


def bridge_logistics_catalog_to_unified(
    logistics_catalog: object,
    unified: BusinessSemanticCatalog,
) -> None:
    """将现有 LogisticsSemanticCatalog 桥接到统一注册表。

    参数：
        logistics_catalog: LogisticsSemanticCatalog 实例（不改动）。
        unified: 目标 BusinessSemanticCatalog 实例。

    业务逻辑：
        1. 只做读取式适配——不修改 logistics_catalog 内部状态。
        2. 从物流 catalog 中提取 metrics、dimensions、entities 注册到统一表。
        3. 字段映射：
           - LogisticsCatalogMetric → SemanticMetric（只取业务语义字段）
           - LogisticsCatalogDimension → SemanticDimension（只取业务语义字段）

    说明：
        此函数依赖 LogisticsSemanticCatalog 的公开数据属性（metrics、dimensions），
        而不依赖其内部实现细节。物流 catalog 的 SQL 表达式、表白名单、
        Join 规则等 NL2SQL 专用字段不会被复制到统一注册表中——
        统一注册表只保存"业务层面有哪些指标/维度/实体可用"的信息。
    """
    domain = "logistics"

    # 桥接指标：LogisticsCatalogMetric → SemanticMetric
    for metric in getattr(logistics_catalog, "metrics", []):
        unified_metric = SemanticMetric(
            metric_id=getattr(metric, "metric_id", ""),
            display_name=getattr(metric, "display_name", ""),
            domain=domain,
            aliases=list(getattr(metric, "aliases", [])),
            unit=getattr(metric, "unit", None),
            description=getattr(metric, "business_note", None),
        )
        unified.register_metric(unified_metric)

    # 桥接维度：LogisticsCatalogDimension → SemanticDimension
    for dim in getattr(logistics_catalog, "dimensions", []):
        unified_dim = SemanticDimension(
            dimension_id=getattr(dim, "dimension_id", ""),
            display_name=getattr(dim, "display_name", ""),
            domain=domain,
            aliases=list(getattr(dim, "aliases", [])),
            description=getattr(dim, "business_note", None),
        )
        unified.register_dimension(unified_dim)

    # 桥接实体：从 dimensions 中提取 entity-type 维度作为实体
    # 物流域中承运商(carrier)、委托人(entity) 可作为业务实体
    entity_dimension_ids = {"carrier", "entity", "region"}
    for dim in getattr(logistics_catalog, "dimensions", []):
        dim_id = getattr(dim, "dimension_id", "")
        if dim_id in entity_dimension_ids:
            entity = SemanticEntity(
                entity_id=dim_id,
                display_name=getattr(dim, "display_name", ""),
                domain=domain,
                entity_type=dim_id,
                aliases=list(getattr(dim, "aliases", [])),
                description=getattr(dim, "business_note", None),
            )
            unified.register_entity(entity)


__all__ = ["bridge_logistics_catalog_to_unified"]

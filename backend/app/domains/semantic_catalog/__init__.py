"""
统一语义资产 Catalog（Unified Semantic Catalog）。

业务定位：
    本模块提供跨业务域（物流、计划 BOM、经营分析、物管）的统一语义资产定义。
    它是 NL2SQL / QueryPlanningV2 的辅助能力层——描述"有哪些指标/维度/实体可用"，
    但不替代现有领域 catalog 的 SQLPlan 校验、表白名单等核心能力。

模块组成：
    - schema: 核心数据结构（SemanticMetric、SemanticDimension、SemanticEntity）
    - catalog: 统一注册表（BusinessSemanticCatalog）
    - loader: YAML 文件加载器（SemanticCatalogYamlLoader）
    - bridge: 现有领域 catalog 桥接适配层

约束：
    - 不做物管/SAP MID M2。
    - 不引入 ES。
    - 不替代 NL2SQL。
    - 保留旧接口和回退。
    - LLM 只读，不自由 SQL/查数/改事实。
"""

from backend.app.domains.semantic_catalog.schema import (
    SemanticMetric,
    SemanticDimension,
    SemanticEntity,
    SemanticCapability,
    BusinessValueResolverProtocol,
)
from backend.app.domains.semantic_catalog.catalog import BusinessSemanticCatalog
from backend.app.domains.semantic_catalog.loader import (
    SemanticCatalogYamlLoader,
    DEFAULT_UNIFIED_CATALOG_DIR,
)
from backend.app.domains.semantic_catalog.bridge import (
    bridge_logistics_catalog_to_unified,
)
from backend.app.domains.semantic_catalog.value_resolver.base import (
    BusinessValueResolver,
)
from backend.app.domains.semantic_catalog.value_resolver.logistics_resolver import (
    LogisticsValueResolver,
)
from backend.app.domains.semantic_catalog.value_resolver.plan_bom_resolver import (
    PlanBomValueResolver,
)

# 多候选消歧统一交互模块
from backend.app.domains.semantic_catalog.disambiguation import (
    DisambiguationCandidate,
    DisambiguationRequest,
    DisambiguationResponse,
    DisambiguationResolveRequest,
    DisambiguationResolveResponse,
    DisambiguationService,
    DisambiguationError,
)

__all__ = [
    "SemanticMetric",
    "SemanticDimension",
    "SemanticEntity",
    "SemanticCapability",
    "BusinessValueResolverProtocol",
    "BusinessSemanticCatalog",
    "SemanticCatalogYamlLoader",
    "DEFAULT_UNIFIED_CATALOG_DIR",
    "bridge_logistics_catalog_to_unified",
    "BusinessValueResolver",
    "LogisticsValueResolver",
    "PlanBomValueResolver",
    # 多候选消歧模块
    "DisambiguationCandidate",
    "DisambiguationRequest",
    "DisambiguationResponse",
    "DisambiguationResolveRequest",
    "DisambiguationResolveResponse",
    "DisambiguationService",
    "DisambiguationError",
]

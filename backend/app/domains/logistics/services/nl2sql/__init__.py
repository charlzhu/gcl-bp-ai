"""物流 NL2SQL 子能力入口。

本包只承载 NL2SQL shadow 架构所需的 catalog、规则和后续 SQLPlan 辅助能力，
当前 M1 不接管既有物流 Data QA 正式查询链路。
"""

from backend.app.domains.logistics.services.nl2sql.business_rules import LogisticsNl2SqlBusinessRules
from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import (
    LogisticsCatalogRecallDocumentBuilder,
    LogisticsCatalogRecallService,
)
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader
from backend.app.domains.logistics.services.nl2sql.sql_plan import (
    LogisticsSqlPlan,
    LogisticsSqlPlanCandidate,
    LogisticsSqlPlanValidationResult,
    LogisticsSqlPlanValidator,
    validate_logistics_sql_plan_candidate,
)

__all__ = [
    "LogisticsCatalogRecallDocumentBuilder",
    "LogisticsCatalogRecallService",
    "LogisticsNl2SqlBusinessRules",
    "LogisticsSemanticCatalogLoader",
    "LogisticsSqlPlan",
    "LogisticsSqlPlanCandidate",
    "LogisticsSqlPlanValidationResult",
    "LogisticsSqlPlanValidator",
    "validate_logistics_sql_plan_candidate",
]

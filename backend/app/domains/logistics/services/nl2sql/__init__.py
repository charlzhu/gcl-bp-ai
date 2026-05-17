"""物流 NL2SQL 子能力入口。

本包承载 NL2SQL shadow 架构所需的 catalog、规则、SQLPlan、SQL 安全执行与评估能力。
当前 M5 shadow pipeline 仅用于内部评估，不接管既有物流 Data QA 正式查询链路。
"""

from backend.app.domains.logistics.services.nl2sql.business_rules import LogisticsNl2SqlBusinessRules
from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import (
    LogisticsCatalogRecallDocumentBuilder,
    LogisticsCatalogRecallService,
)
from backend.app.domains.logistics.services.nl2sql.evaluation_log import (
    InMemoryLogisticsNl2SqlEvaluationLogSink,
    JsonlLogisticsNl2SqlEvaluationLogSink,
    LogisticsNl2SqlEvaluationLogRecord,
    LogisticsNl2SqlEvaluationLogSummary,
    redact_evaluation_text,
    summarize_evaluation_logs,
)
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader
from backend.app.domains.logistics.services.nl2sql.shadow_pipeline import (
    LogisticsNl2SqlShadowPipeline,
    LogisticsNl2SqlShadowPipelineRequest,
    LogisticsNl2SqlShadowPipelineResult,
)
from backend.app.domains.logistics.services.nl2sql.sql_execution import (
    FakeLogisticsSqlExecutor,
    LogisticsSqlExecutionResult,
    LogisticsSqlExecutionService,
)
from backend.app.domains.logistics.services.nl2sql.sql_plan import (
    LogisticsSqlPlan,
    LogisticsSqlPlanCandidate,
    LogisticsSqlPlanValidationResult,
    LogisticsSqlPlanValidator,
    validate_logistics_sql_plan_candidate,
)
from backend.app.domains.logistics.services.nl2sql.sql_renderer import (
    LogisticsRenderedSql,
    LogisticsSqlRenderer,
    render_logistics_sql,
)
from backend.app.domains.logistics.services.nl2sql.sql_safety import (
    LogisticsSqlSafetyChecker,
    LogisticsSqlSafetyResult,
    check_logistics_sql_safety,
)

__all__ = [
    "FakeLogisticsSqlExecutor",
    "InMemoryLogisticsNl2SqlEvaluationLogSink",
    "JsonlLogisticsNl2SqlEvaluationLogSink",
    "LogisticsCatalogRecallDocumentBuilder",
    "LogisticsCatalogRecallService",
    "LogisticsNl2SqlEvaluationLogRecord",
    "LogisticsNl2SqlEvaluationLogSummary",
    "LogisticsNl2SqlBusinessRules",
    "LogisticsNl2SqlShadowPipeline",
    "LogisticsNl2SqlShadowPipelineRequest",
    "LogisticsNl2SqlShadowPipelineResult",
    "LogisticsRenderedSql",
    "LogisticsSemanticCatalogLoader",
    "LogisticsSqlExecutionResult",
    "LogisticsSqlExecutionService",
    "LogisticsSqlPlan",
    "LogisticsSqlPlanCandidate",
    "LogisticsSqlPlanValidationResult",
    "LogisticsSqlPlanValidator",
    "LogisticsSqlRenderer",
    "LogisticsSqlSafetyChecker",
    "LogisticsSqlSafetyResult",
    "check_logistics_sql_safety",
    "redact_evaluation_text",
    "render_logistics_sql",
    "summarize_evaluation_logs",
    "validate_logistics_sql_plan_candidate",
]

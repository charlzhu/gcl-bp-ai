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
from backend.app.domains.logistics.services.nl2sql.evaluation_report import (
    LogisticsNl2SqlEvaluationReport,
    LogisticsNl2SqlEvaluationReportSampleOutcome,
    LogisticsNl2SqlEvaluationReportTopError,
    build_logistics_nl2sql_evaluation_report,
    render_logistics_nl2sql_evaluation_report_markdown,
)
from backend.app.domains.logistics.services.nl2sql.m7_readonly_smoke import (
    M7_READONLY_SMOKE_VERSION,
    LogisticsNl2SqlM7ReadonlySmokeOutcome,
    LogisticsNl2SqlM7ReadonlySmokeRunResult,
    LogisticsNl2SqlM7ReadonlySmokeSample,
    build_default_logistics_nl2sql_m7_readonly_smoke_samples,
    run_logistics_nl2sql_m7_readonly_smoke,
)
from backend.app.domains.logistics.services.nl2sql.m8_shadow_eval import (
    DEFAULT_M8_ARTIFACT_DIR,
    DEFAULT_M8_RECORDS_FILENAME,
    DEFAULT_M8_REPORT_FILENAME,
    DEFAULT_M8_SAMPLE_IDS,
    M8_SHADOW_EVAL_VERSION,
    LogisticsNl2SqlM8ShadowEvalOutcome,
    LogisticsNl2SqlM8ShadowEvalRunResult,
    LogisticsNl2SqlM8ShadowEvalSample,
    build_default_logistics_nl2sql_m8_shadow_eval_samples,
    render_safe_m8_summary_json,
    run_logistics_nl2sql_m8_shadow_eval,
)
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader
from backend.app.domains.logistics.services.nl2sql.shadow_pipeline import (
    LogisticsNl2SqlShadowPipeline,
    LogisticsNl2SqlShadowPipelineRequest,
    LogisticsNl2SqlShadowPipelineResult,
)
from backend.app.domains.logistics.services.nl2sql.shadow_smoke import (
    DEFAULT_LOGISTICS_NL2SQL_SHADOW_SMOKE_SAMPLE_IDS,
    LogisticsNl2SqlShadowSmokeOutcome,
    LogisticsNl2SqlShadowSmokeRunResult,
    LogisticsNl2SqlShadowSmokeSample,
    build_default_logistics_nl2sql_shadow_smoke_samples,
    run_logistics_nl2sql_shadow_smoke,
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
    "DEFAULT_LOGISTICS_NL2SQL_SHADOW_SMOKE_SAMPLE_IDS",
    "LogisticsCatalogRecallDocumentBuilder",
    "LogisticsCatalogRecallService",
    "LogisticsNl2SqlEvaluationLogRecord",
    "LogisticsNl2SqlEvaluationLogSummary",
    "LogisticsNl2SqlEvaluationReport",
    "LogisticsNl2SqlEvaluationReportSampleOutcome",
    "LogisticsNl2SqlEvaluationReportTopError",
    "LogisticsNl2SqlBusinessRules",
    "M7_READONLY_SMOKE_VERSION",
    "LogisticsNl2SqlM7ReadonlySmokeOutcome",
    "LogisticsNl2SqlM7ReadonlySmokeRunResult",
    "LogisticsNl2SqlM7ReadonlySmokeSample",
    "DEFAULT_M8_ARTIFACT_DIR",
    "DEFAULT_M8_RECORDS_FILENAME",
    "DEFAULT_M8_REPORT_FILENAME",
    "DEFAULT_M8_SAMPLE_IDS",
    "M8_SHADOW_EVAL_VERSION",
    "LogisticsNl2SqlM8ShadowEvalOutcome",
    "LogisticsNl2SqlM8ShadowEvalRunResult",
    "LogisticsNl2SqlM8ShadowEvalSample",
    "LogisticsNl2SqlShadowPipeline",
    "LogisticsNl2SqlShadowPipelineRequest",
    "LogisticsNl2SqlShadowPipelineResult",
    "LogisticsNl2SqlShadowSmokeOutcome",
    "LogisticsNl2SqlShadowSmokeRunResult",
    "LogisticsNl2SqlShadowSmokeSample",
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
    "build_default_logistics_nl2sql_m7_readonly_smoke_samples",
    "build_default_logistics_nl2sql_m8_shadow_eval_samples",
    "build_default_logistics_nl2sql_shadow_smoke_samples",
    "build_logistics_nl2sql_evaluation_report",
    "redact_evaluation_text",
    "render_safe_m8_summary_json",
    "render_logistics_sql",
    "render_logistics_nl2sql_evaluation_report_markdown",
    "run_logistics_nl2sql_m7_readonly_smoke",
    "run_logistics_nl2sql_m8_shadow_eval",
    "run_logistics_nl2sql_shadow_smoke",
    "summarize_evaluation_logs",
    "validate_logistics_sql_plan_candidate",
]

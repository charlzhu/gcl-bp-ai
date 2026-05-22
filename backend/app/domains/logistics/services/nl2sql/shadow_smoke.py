from __future__ import annotations

import time
from copy import deepcopy
from typing import Any, Callable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domains.logistics.services.nl2sql.evaluation_log import (
    LogisticsNl2SqlEvaluationLogRecord,
    LogisticsNl2SqlEvaluationLogSink,
    redact_evaluation_text,
)
from backend.app.domains.logistics.services.nl2sql.evaluation_report import (
    LogisticsNl2SqlEvaluationReport,
    build_logistics_nl2sql_evaluation_report,
    render_logistics_nl2sql_evaluation_report_markdown,
)
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalog, LogisticsSemanticCatalogLoader
from backend.app.domains.logistics.services.nl2sql.shadow_pipeline import (
    SHADOW_PIPELINE_VERSION,
    LogisticsNl2SqlShadowPipeline,
    LogisticsNl2SqlShadowPipelineRequest,
    LogisticsNl2SqlShadowPipelineResult,
)
from backend.app.domains.logistics.services.nl2sql.sql_execution import (
    LogisticsSqlExecutionService,
    LogisticsSqlExecutor,
)
from backend.app.domains.logistics.services.nl2sql.sql_plan import LogisticsSqlPlanValidationResult
from backend.app.domains.logistics.services.nl2sql.sql_renderer import LogisticsRenderedSql, LogisticsSqlRenderer
from backend.app.domains.logistics.services.nl2sql.sql_safety import LogisticsSqlSafetyChecker

SHADOW_SMOKE_VERSION = "logistics_nl2sql_shadow_smoke.v1"
DEFAULT_LOGISTICS_NL2SQL_SHADOW_SMOKE_SAMPLE_IDS: tuple[str, ...] = (
    "success_valid_plan",
    "skipped_missing_candidate",
    "unsupported_non_sql_direct_strategy",
    "skipped_non_logistics_domain",
    "skipped_non_middle_db_source",
    "validation_failed_unknown_metric",
    "safety_failed_select_star",
    "explain_failed_fake_executor",
    "trial_failed_fake_executor",
    "redaction_failure_sanitized",
)
SmokeExecutorMode = Literal["success", "explain_failed", "trial_failed"]
SmokeRendererMode = Literal["default", "unsafe_select_star", "secret_warning"]
SmokeExecutorFactory = Callable[["LogisticsNl2SqlShadowSmokeSample"], LogisticsSqlExecutor | None]


class _SmokeRendererProtocol(Protocol):
    """smoke runner 可注入 renderer 的最小协议。"""

    def render(self, validation_result: LogisticsSqlPlanValidationResult) -> LogisticsRenderedSql:
        """把校验通过的 SQLPlan 渲染为受控 SQL。"""


class LogisticsNl2SqlShadowSmokeSample(BaseModel):
    """M6 离线 shadow smoke 样例定义。

    业务逻辑：
        样例只保存通用业务模板和 SQLPlan candidate，不读取 `.env`，不携带真实客户数据，也不会连接真实
        MySQL/Oracle/SAP/Milvus。renderer/executor mode 仅用于离线 fake 场景覆盖。
    """

    model_config = ConfigDict(extra="forbid")

    sample_id: str
    description: str
    request: LogisticsNl2SqlShadowPipelineRequest
    executor_mode: SmokeExecutorMode = "success"
    renderer_mode: SmokeRendererMode = "default"
    offline_only: bool = True


class LogisticsNl2SqlShadowSmokeOutcome(BaseModel):
    """单条 M6 smoke 样例执行结果。"""

    model_config = ConfigDict(extra="forbid")

    sample: LogisticsNl2SqlShadowSmokeSample
    result: LogisticsNl2SqlShadowPipelineResult
    evaluation_log_record: LogisticsNl2SqlEvaluationLogRecord


class LogisticsNl2SqlShadowSmokeRunResult(BaseModel):
    """M6 smoke runner 总返回。"""

    model_config = ConfigDict(extra="forbid")

    outcomes: list[LogisticsNl2SqlShadowSmokeOutcome] = Field(default_factory=list)
    evaluation_log_records: list[LogisticsNl2SqlEvaluationLogRecord] = Field(default_factory=list)
    report: LogisticsNl2SqlEvaluationReport

    def render_markdown(self) -> str:
        """把本次 run 的安全评估报表渲染为 Markdown。"""

        return render_logistics_nl2sql_evaluation_report_markdown(self.report)


def build_default_logistics_nl2sql_shadow_smoke_samples() -> list[LogisticsNl2SqlShadowSmokeSample]:
    """构造 M6 默认离线 smoke 样例集。

    返回：
        覆盖 success、skipped、unsupported、validation、safety、explain、trial 与脱敏场景的通用样例列表。
    """

    password_key = "pass" + "word"
    token_key = "tok" + "en"
    bearer_value = "bearer-secret-value"
    dsn = "mysql://demo:" + "pass" + "123" + "@db.local/prod"
    return [
        LogisticsNl2SqlShadowSmokeSample(
            sample_id="success_valid_plan",
            description="合法 SQLPlan + fake executor explain/trial 成功",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="2025年按承运商统计发运量排名",
                rewritten_question="按承运商汇总发运量并降序排序",
                request_id="m6-success",
                candidate=_valid_candidate(),
            ),
        ),
        LogisticsNl2SqlShadowSmokeSample(
            sample_id="skipped_missing_candidate",
            description="缺少 SQLPlan candidate，应跳过 SQL 阶段",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="2025年物流发运量是多少",
                request_id="m6-missing-candidate",
                candidate=None,
            ),
        ),
        LogisticsNl2SqlShadowSmokeSample(
            sample_id="unsupported_non_sql_direct_strategy",
            description="非 sql_direct strategy，应停在 candidate 边界",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="请解释物流整体情况",
                request_id="m6-non-sql-strategy",
                candidate=_valid_candidate(strategy="clarify"),
            ),
        ),
        LogisticsNl2SqlShadowSmokeSample(
            sample_id="skipped_non_logistics_domain",
            description="非 logistics domain，应跳过 shadow SQL 链路",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="物管库存和出入库",
                domain="material_management",
                request_id="m6-non-logistics",
                candidate=_valid_candidate(),
            ),
        ),
        LogisticsNl2SqlShadowSmokeSample(
            sample_id="skipped_non_middle_db_source",
            description="非 middle_db source，应跳过 shadow SQL 链路",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="从 SAP 查物流发运量",
                source_system="sap_mid",
                request_id="m6-non-middle-db",
                candidate=_valid_candidate(),
            ),
        ),
        LogisticsNl2SqlShadowSmokeSample(
            sample_id="validation_failed_unknown_metric",
            description="未知指标应被 SQLPlan validator fail-closed",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="2025年未知费用指标是多少",
                request_id="m6-validation-failed",
                candidate=_valid_candidate(plan={"metrics": ["unknown_fee_metric"]}),
            ),
        ),
        LogisticsNl2SqlShadowSmokeSample(
            sample_id="safety_failed_select_star",
            description="renderer fixture 产生 SELECT star，必须被 M4 safety 拒绝",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="2025年物流明细试运行",
                request_id="m6-safety-failed",
                candidate=_valid_candidate(),
            ),
            renderer_mode="unsafe_select_star",
        ),
        LogisticsNl2SqlShadowSmokeSample(
            sample_id="explain_failed_fake_executor",
            description="fake executor EXPLAIN 失败，应记录 explain_failed",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="2025年发运量汇总",
                request_id="m6-explain-failed",
                candidate=_valid_candidate(plan={"query_type": "aggregate", "dimensions": [], "group_by": [], "order_by": [], "limit": None}),
            ),
            executor_mode="explain_failed",
        ),
        LogisticsNl2SqlShadowSmokeSample(
            sample_id="trial_failed_fake_executor",
            description="fake executor trial 失败，应记录 trial_failed",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="2025年发运量汇总试执行",
                request_id="m6-trial-failed",
                candidate=_valid_candidate(plan={"query_type": "aggregate", "dimensions": [], "group_by": [], "order_by": [], "limit": None}),
            ),
            executor_mode="trial_failed",
        ),
        LogisticsNl2SqlShadowSmokeSample(
            sample_id="redaction_failure_sanitized",
            description="日志脱敏样例：question/error/warning 含敏感文本但报表不得泄露",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question=(
                    f"2025年发运量 {password_key}=unit-password {token_key}=tok_unitsecret "
                    f"Bearer {bearer_value} {dsn} SELECT * FROM dws_logistics_detail_union"
                ),
                request_id="m6-redaction",
                candidate=_valid_candidate(plan={"query_type": "aggregate", "dimensions": [], "group_by": [], "order_by": [], "limit": None}),
            ),
            executor_mode="explain_failed",
            renderer_mode="secret_warning",
        ),
    ]


def run_logistics_nl2sql_shadow_smoke(
    *,
    samples: list[LogisticsNl2SqlShadowSmokeSample] | None = None,
    executor_factory: SmokeExecutorFactory | None = None,
    log_sink: LogisticsNl2SqlEvaluationLogSink | None = None,
) -> LogisticsNl2SqlShadowSmokeRunResult:
    """顺序执行 M6 离线 shadow smoke 样例。

    参数：
        samples: 可选样例集；未传入时使用默认离线样例。
        executor_factory: 可选 fake executor 工厂，用于单测注入异常；返回 None 时使用样例默认 fake executor。
        log_sink: 可选 evaluation log sink；runner 同时从每条 result 中收集日志记录。
    返回：
        每条样例结果、日志记录和安全评估报表。
    """

    catalog = LogisticsSemanticCatalogLoader().load()
    safety_checker = LogisticsSqlSafetyChecker(catalog=catalog)
    resolved_samples = samples or build_default_logistics_nl2sql_shadow_smoke_samples()
    outcomes: list[LogisticsNl2SqlShadowSmokeOutcome] = []
    sample_ids_by_trace: dict[str, str] = {}
    descriptions_by_trace: dict[str, str] = {}
    for sample in resolved_samples:
        try:
            executor = executor_factory(sample) if executor_factory else None
            if executor is None:
                executor = _OfflineSmokeExecutor(mode=sample.executor_mode)
            renderer = _build_renderer(sample.renderer_mode, catalog)
            pipeline = LogisticsNl2SqlShadowPipeline(
                catalog=catalog,
                renderer=renderer,
                safety_checker=safety_checker,
                execution_service=LogisticsSqlExecutionService(executor=executor, safety_checker=safety_checker),
                log_sink=log_sink,
                pipeline_version=SHADOW_PIPELINE_VERSION,
            )
            result = pipeline.run(sample.request)
            record = result.evaluation_log_record
        except Exception as exc:  # noqa: BLE001 - smoke runner 必须单条 fail-closed 后继续后续样例
            result, record = _build_runner_failure(sample, exc)
            _write_optional_log_sink(log_sink, record)
        sample_ids_by_trace[record.trace_id] = sample.sample_id
        descriptions_by_trace[record.trace_id] = sample.description
        outcomes.append(LogisticsNl2SqlShadowSmokeOutcome(sample=sample, result=result, evaluation_log_record=record))

    records = [outcome.evaluation_log_record for outcome in outcomes]
    report = build_logistics_nl2sql_evaluation_report(
        records,
        sample_ids=sample_ids_by_trace,
        sample_descriptions=descriptions_by_trace,
        warnings=[f"{SHADOW_SMOKE_VERSION} offline shadow-only; M7 才允许只读中间库 smoke"],
    )
    return LogisticsNl2SqlShadowSmokeRunResult(outcomes=outcomes, evaluation_log_records=records, report=report)


class _OfflineSmokeExecutor:
    """M6 默认离线 fake executor，不连接任何真实数据库。"""

    def __init__(self, *, mode: SmokeExecutorMode = "success") -> None:
        """初始化 fake 执行模式。"""

        self.mode = mode
        self.calls: list[str] = []

    def explain(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """模拟 EXPLAIN；explain_failed 模式抛出脱敏测试错误。"""

        self.calls.append("explain")
        if self.mode == "explain_failed":
            password_key = "pass" + "word"
            token_key = "tok" + "en"
            dsn = "mysql://demo:" + "pass" + "123" + "@db.local/prod"
            raise RuntimeError(f"offline explain failed {password_key}=unit-password {token_key}=tok_unitsecret {dsn}")
        return [{"select_type": "SIMPLE", "offline": True}]

    def trial(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """模拟 trial；trial_failed 模式抛出脱敏测试错误。"""

        self.calls.append("trial")
        if self.mode == "trial_failed":
            token_key = "tok" + "en"
            raise RuntimeError(f"offline trial failed {token_key}=tok_unitsecret raw_param_value")
        return [{"sample_metric": 1, "offline": True}]


class _UnsafeSelectStarRenderer:
    """测试用 renderer：产出 SELECT star，仍交给 production safety 边界拒绝。"""

    def render(self, validation_result: LogisticsSqlPlanValidationResult) -> LogisticsRenderedSql:
        """返回不安全但参数化的 SQL，验证 safety fail-closed。"""

        return LogisticsRenderedSql(
            sql="SELECT * FROM dws_logistics_detail_union WHERE dws_logistics_detail_union.biz_year = :p0",
            params={"p0": 2025},
            referenced_tables=["dws_logistics_detail_union"],
            referenced_columns=[("dws_logistics_detail_union", "biz_year")],
        )


class _SecretWarningRenderer:
    """测试用 renderer：复用生产 renderer 后追加需要脱敏的 warning。"""

    def __init__(self, catalog: LogisticsSemanticCatalog) -> None:
        """初始化内部生产 renderer。"""

        self.renderer = LogisticsSqlRenderer(catalog=catalog)

    def render(self, validation_result: LogisticsSqlPlanValidationResult) -> LogisticsRenderedSql:
        """渲染合法 SQL，并附加含密钥和 SQL-like 文本的 warning。"""

        rendered = self.renderer.render(validation_result)
        password_key = "pass" + "word"
        token_key = "tok" + "en"
        warnings = [
            *rendered.warnings,
            f"warning {password_key}=unit-password {token_key}=tok_unitsecret SELECT * FROM dws_logistics_detail_union",
        ]
        return rendered.model_copy(update={"warnings": warnings})


def _build_renderer(mode: SmokeRendererMode, catalog: LogisticsSemanticCatalog) -> _SmokeRendererProtocol | None:
    """按样例 renderer_mode 构造 renderer；默认返回 None 使用 M5 production renderer。"""

    if mode == "unsafe_select_star":
        return _UnsafeSelectStarRenderer()
    if mode == "secret_warning":
        return _SecretWarningRenderer(catalog)
    return None


def _build_runner_failure(
    sample: LogisticsNl2SqlShadowSmokeSample,
    exc: Exception,
) -> tuple[LogisticsNl2SqlShadowPipelineResult, LogisticsNl2SqlEvaluationLogRecord]:
    """把 runner 边界异常收敛为单条受控失败结果。"""

    started = time.perf_counter()
    trace_id = f"shadow-smoke-{sample.sample_id}"
    error_message = redact_evaluation_text(str(exc))
    duration_ms = int((time.perf_counter() - started) * 1000)
    record = LogisticsNl2SqlEvaluationLogRecord.from_pipeline(
        trace_id=trace_id,
        request_id=sample.request.request_id,
        question=sample.request.question,
        rewritten_question=sample.request.rewritten_question,
        domain=sample.request.domain,
        source_system=sample.request.source_system,
        status="render_failed",
        stage="runner",
        error_codes=["shadow_smoke_sample_failed"],
        error_message=error_message,
        catalog_ids=[],
        catalog_versions=[],
        sql_hash=None,
        sql_param_keys=[],
        validation_errors=[],
        safety_errors=[],
        explain_ok=False,
        trial_ok=False,
        row_count=0,
        sample_row_count=0,
        duration_ms=duration_ms,
        pipeline_version=SHADOW_SMOKE_VERSION,
        warnings=["single sample failed; runner continued"],
    )
    result = LogisticsNl2SqlShadowPipelineResult(
        status="render_failed",
        stage="runner",
        error_codes=list(record.error_codes),
        error_message=record.error_message,
        trace_id=trace_id,
        sql_hash=None,
        sql_param_keys=[],
        row_count=0,
        sample_row_count=0,
        explain_ok=False,
        trial_ok=False,
        evaluation_log_record=record,
        log_error=None,
    )
    return result, record


def _write_optional_log_sink(log_sink: LogisticsNl2SqlEvaluationLogSink | None, record: LogisticsNl2SqlEvaluationLogRecord) -> None:
    """runner 合成失败日志时也尝试写入外部 sink，但 sink 失败不能影响 smoke。"""

    if log_sink is None:
        return
    try:
        log_sink.write(record)
    except Exception:  # noqa: BLE001 - sink 是评估副作用，不能阻断 runner
        return


def _filter(dimension: str, operator: str, values: list[Any]) -> dict[str, Any]:
    """生成默认 SQLPlan 过滤条件。"""

    return {"dimension": dimension, "operator": operator, "values": values}


def _valid_candidate(**overrides: Any) -> dict[str, Any]:
    """生成通用物流 SQLPlan candidate，不包含真实客户/历史问答数据。"""

    candidate: dict[str, Any] = {
        "schema_version": "logistics_sqlplan_candidate.v1",
        "domain": "logistics",
        "strategy": "sql_direct",
        "catalog_version": "logistics_nl2sql_catalog.v1",
        "catalog_refs": [
            {"catalog_id": "table:dws_logistics_detail_union", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "metric:shipment_mw", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "metric:row_count", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "dimension:biz_year", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "dimension:logistics_company_name", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "rule:default_time_range", "catalog_version": "logistics_nl2sql_catalog.v1"},
        ],
        "plan": {
            "query_type": "ranking",
            "tables": ["dws_logistics_detail_union"],
            "joins": [],
            "metrics": ["shipment_mw", "row_count"],
            "dimensions": ["logistics_company_name"],
            "filters": [_filter("biz_year", "in", [2023, 2024, 2025, 2026])],
            "group_by": ["logistics_company_name"],
            "order_by": [{"metric": "shipment_mw", "direction": "desc"}],
            "business_rules": ["default_time_range"],
            "explicit_year_buckets": [2023, 2024, 2025, 2026],
            "requested_unit": "MW",
            "limit": 20,
        },
        "clarification_questions": [],
        "unsupported_reason": None,
        "confidence": 0.91,
    }
    return _deep_merge(candidate, overrides)


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """递归合并样例覆盖字段。"""

    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        elif isinstance(value, list) and key == "catalog_refs":
            merged[key] = [*merged[key], *value]
        else:
            merged[key] = value
    return merged


__all__ = [
    "DEFAULT_LOGISTICS_NL2SQL_SHADOW_SMOKE_SAMPLE_IDS",
    "SHADOW_SMOKE_VERSION",
    "LogisticsNl2SqlShadowSmokeOutcome",
    "LogisticsNl2SqlShadowSmokeRunResult",
    "LogisticsNl2SqlShadowSmokeSample",
    "build_default_logistics_nl2sql_shadow_smoke_samples",
    "run_logistics_nl2sql_shadow_smoke",
]

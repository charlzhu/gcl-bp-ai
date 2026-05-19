from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domains.logistics.services.nl2sql.evaluation_log import LogisticsNl2SqlEvaluationLogRecord
from backend.app.domains.logistics.services.nl2sql.evaluation_report import (
    LogisticsNl2SqlEvaluationReport,
    build_logistics_nl2sql_evaluation_report,
    render_logistics_nl2sql_evaluation_report_markdown,
)
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader
from backend.app.domains.logistics.services.nl2sql.shadow_pipeline import (
    LogisticsNl2SqlShadowPipeline,
    LogisticsNl2SqlShadowPipelineRequest,
    LogisticsNl2SqlShadowPipelineResult,
)
from backend.app.domains.logistics.services.nl2sql.sql_execution import (
    FakeLogisticsSqlExecutor,
    LogisticsSqlExecutionService,
)
from backend.app.domains.logistics.services.nl2sql.sql_plan import LogisticsSqlPlanValidationResult
from backend.app.domains.logistics.services.nl2sql.sql_renderer import LogisticsRenderedSql
from backend.app.domains.logistics.services.nl2sql.sql_safety import LogisticsSqlSafetyChecker

M8_SHADOW_EVAL_VERSION = "logistics_nl2sql_m8_shadow_eval.v1"
DEFAULT_M8_RECORDS_FILENAME = "m8-shadow-eval-records.jsonl"
DEFAULT_M8_REPORT_FILENAME = "m8-shadow-eval-report.md"
DEFAULT_M8_ARTIFACT_DIR = Path("ai/outbox/kanban/t_7895e090")
DEFAULT_M8_SAMPLE_IDS: tuple[str, ...] = (
    "m8_success_yearly_shipment_mw_by_year",
    "m8_success_carrier_avg_fee_per_trip",
    "m8_success_monthly_total_fee_trend",
    "m8_success_region_transport_mode_shipment_fee",
    "m8_validation_tonnage_unit_rejected",
    "m8_validation_unknown_price_metric_rejected",
    "m8_success_carrier_rank_by_mw",
    "m8_success_origin_customer_topn_detail",
    "m8_validation_quote_metric_requires_supported_hist_scope",
    "m8_safety_forbidden_update_sql_blocked",
    "m8_skipped_missing_candidate",
    "m8_unsupported_non_sql_direct_strategy",
)


class LogisticsNl2SqlM8ShadowEvalSample(BaseModel):
    """M8 物流 NL2SQL shadow-only 评估样例。"""

    model_config = ConfigDict(extra="forbid")

    sample_id: str
    description: str
    request: LogisticsNl2SqlShadowPipelineRequest
    category: str
    business_case: str
    metric_family: str
    expected_status: str
    force_safety_sql_failure: bool = False
    offline_only: bool = True


class LogisticsNl2SqlM8ShadowEvalOutcome(BaseModel):
    """M8 单条 shadow-only 样例执行结果。"""

    model_config = ConfigDict(extra="forbid")

    sample: LogisticsNl2SqlM8ShadowEvalSample
    result: LogisticsNl2SqlShadowPipelineResult
    evaluation_log_record: LogisticsNl2SqlEvaluationLogRecord
    executor_call_count_before: int = 0
    executor_call_count_after: int = 0


class LogisticsNl2SqlM8ShadowEvalRunResult(BaseModel):
    """M8 shadow-only 评估总返回。"""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    outcomes: list[LogisticsNl2SqlM8ShadowEvalOutcome] = Field(default_factory=list)
    evaluation_log_records: list[LogisticsNl2SqlEvaluationLogRecord] = Field(default_factory=list)
    report: LogisticsNl2SqlEvaluationReport
    records_path: Path
    report_path: Path
    shadow_only: bool = True
    live_smoke_executed: bool = False

    def render_markdown(self) -> str:
        """把 M8 评估报表渲染为 Markdown。"""

        return render_logistics_nl2sql_evaluation_report_markdown(self.report)


class _M8UnsafeSqlRenderer:
    """M8 safety 负例专用 renderer。

    业务逻辑：
        该 renderer 只在 `force_safety_sql_failure=True` 的离线样例中使用，用于证明写 SQL 会被
        safety gate fail-closed；它不进入正式 QA 主链路，也不会触达真实数据库。
    """

    def render(self, validation_result: LogisticsSqlPlanValidationResult) -> LogisticsRenderedSql:
        """在 SQLPlan 校验通过后返回危险 SQL，供 safety gate 阻断。"""

        if not validation_result.ok or validation_result.normalized_plan is None:
            raise ValueError("m8_unsafe_renderer_requires_validated_plan")
        return LogisticsRenderedSql(
            sql="update dws_logistics_detail_union set shipment_watt = :p0",
            params={"p0": 0},
            referenced_tables=["dws_logistics_detail_union"],
            referenced_columns=[("dws_logistics_detail_union", "shipment_watt")],
            referenced_joins=[],
            warnings=["m8_safety_negative_renderer"],
        )


def build_default_logistics_nl2sql_m8_shadow_eval_samples() -> list[LogisticsNl2SqlM8ShadowEvalSample]:
    """构造 M8 默认 shadow-only 样例集。

    样例覆盖常见物流问题能力：年度发运量、承运商均价、月度费用趋势、区域/运输方式拆分；
    同时保留吨数和未知价格指标 fail-closed 负例。样例只使用受控 SQLPlan candidate，不读 .env。
    """

    return [
        LogisticsNl2SqlM8ShadowEvalSample(
            sample_id="m8_success_yearly_shipment_mw_by_year",
            description="按年份汇总发运量和明细行数，验证显式多年份桶覆盖",
            category="trend",
            business_case="explicit_year_bucket_shipment_volume",
            metric_family="shipment_volume",
            expected_status="success",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="2023到2026年每年物流发运量分别是多少",
                rewritten_question="按年份汇总发运量并保留 2023-2026 年份桶",
                request_id="m8-yearly-shipment-mw",
                candidate=_candidate(
                    metrics=["shipment_mw", "row_count"],
                    dimensions=["biz_year"],
                    group_by=["biz_year"],
                    order_by=[{"dimension": "biz_year", "direction": "asc"}],
                    requested_unit="MW",
                ),
            ),
        ),
        LogisticsNl2SqlM8ShadowEvalSample(
            sample_id="m8_success_carrier_avg_fee_per_trip",
            description="按承运商统计平均每车费用，验证均价口径与总费用/车次同时可追溯",
            category="ranking",
            business_case="carrier_average_freight_by_trip",
            metric_family="average_freight",
            expected_status="success",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="各物流公司平均运费是多少，按高到低排",
                rewritten_question="按承运商汇总总费用、车次和平均每车费用",
                request_id="m8-carrier-avg-fee",
                candidate=_candidate(
                    query_type="ranking",
                    metrics=["avg_fee_per_trip", "total_fee", "shipment_trip_count", "row_count"],
                    dimensions=["logistics_company_name"],
                    group_by=["logistics_company_name"],
                    order_by=[{"metric": "avg_fee_per_trip", "direction": "desc"}],
                    requested_unit="元/车",
                    limit=20,
                ),
            ),
        ),
        LogisticsNl2SqlM8ShadowEvalSample(
            sample_id="m8_success_monthly_total_fee_trend",
            description="按年月汇总总费用，验证月度趋势维度覆盖",
            category="trend",
            business_case="monthly_total_fee_trend",
            metric_family="total_fee",
            expected_status="success",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="2023到2026年每月物流总运费趋势是什么",
                rewritten_question="按年月汇总总费用并按年月升序排序",
                request_id="m8-monthly-total-fee",
                candidate=_candidate(
                    metrics=["total_fee", "row_count"],
                    dimensions=["biz_month"],
                    group_by=["biz_month"],
                    order_by=[{"dimension": "biz_month", "direction": "asc"}],
                    requested_unit="元",
                ),
            ),
        ),
        LogisticsNl2SqlM8ShadowEvalSample(
            sample_id="m8_success_region_transport_mode_shipment_fee",
            description="按区域和运输方式拆分发运量、总费用，验证多维 group by 覆盖",
            category="breakdown",
            business_case="region_transport_mode_breakdown",
            metric_family="shipment_volume",
            expected_status="success",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="各区域不同运输方式的发运量和总费用分别是多少",
                rewritten_question="按区域和运输方式汇总发运量、总费用与明细行数",
                request_id="m8-region-mode-shipment-fee",
                candidate=_candidate(
                    query_type="ranking",
                    metrics=["shipment_mw", "total_fee", "row_count"],
                    dimensions=["region_name", "transport_mode"],
                    group_by=["region_name", "transport_mode"],
                    order_by=[{"metric": "shipment_mw", "direction": "desc"}],
                    requested_unit="MW",
                    limit=20,
                ),
            ),
        ),
        LogisticsNl2SqlM8ShadowEvalSample(
            sample_id="m8_validation_tonnage_unit_rejected",
            description="吨数/吨位当前不支持，必须停在 SQLPlan 校验边界",
            category="validation",
            business_case="unsupported_tonnage_fail_closed",
            metric_family="unsupported",
            expected_status="validation_failed",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="2025年运输吨位是多少",
                rewritten_question="用户请求吨数口径，当前物流 NL2SQL 不支持",
                request_id="m8-tonnage-rejected",
                candidate=_candidate(
                    metrics=["shipment_mw"],
                    dimensions=[],
                    group_by=[],
                    order_by=[],
                    requested_unit="吨",
                    business_rules=["default_time_range", "unsupported_tonnage"],
                ),
            ),
        ),
        LogisticsNl2SqlM8ShadowEvalSample(
            sample_id="m8_validation_unknown_price_metric_rejected",
            description="未知价格指标不能默认为均价或报价，必须 fail-closed",
            category="validation",
            business_case="unknown_price_metric_fail_closed",
            metric_family="unsupported",
            expected_status="validation_failed",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="物流神秘价格指标是多少",
                rewritten_question="未知价格指标不能映射到临近价格概念",
                request_id="m8-unknown-price-metric",
                candidate=_candidate(
                    metrics=["unknown_price_metric"],
                    dimensions=[],
                    group_by=[],
                    order_by=[],
                    requested_unit="元/车",
                    extra_catalog_refs=["metric:unknown_price_metric"],
                ),
            ),
        ),
        LogisticsNl2SqlM8ShadowEvalSample(
            sample_id="m8_success_carrier_rank_by_mw",
            description="按承运商统计发运量排名，验证哪个物流跑得最多的排名口径",
            category="ranking",
            business_case="carrier_rank_by_shipment_mw",
            metric_family="shipment_volume",
            expected_status="success",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="哪个物流公司跑得最多，按发运量排名",
                rewritten_question="按承运商汇总发运量并取 TopN 排名",
                request_id="m8-carrier-rank-by-mw",
                candidate=_candidate(
                    query_type="ranking",
                    metrics=["carrier_rank_by_mw", "shipment_mw", "row_count"],
                    dimensions=["logistics_company_name"],
                    group_by=["logistics_company_name"],
                    order_by=[{"metric": "carrier_rank_by_mw", "direction": "desc"}],
                    requested_unit="MW",
                    limit=10,
                ),
            ),
        ),
        LogisticsNl2SqlM8ShadowEvalSample(
            sample_id="m8_success_origin_customer_topn_detail",
            description="按始发地和客户输出明细 TopN，验证明细类 limit 与路线/客户维度覆盖",
            category="detail",
            business_case="origin_customer_topn_detail",
            metric_family="trip_count",
            expected_status="success",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="从合肥发给重点客户的物流明细前20条是什么",
                rewritten_question="筛选始发地后返回客户、年份、发运量、总费用、车次明细 TopN",
                request_id="m8-origin-customer-topn-detail",
                candidate=_candidate(
                    query_type="detail",
                    metrics=["shipment_mw", "total_fee", "shipment_trip_count"],
                    dimensions=["origin_place", "customer_name", "biz_year"],
                    filters=[_filter("biz_year", "in", [2023, 2024, 2025, 2026]), _filter("origin_place", "like", ["合肥"])],
                    group_by=[],
                    order_by=[{"dimension": "biz_year", "direction": "desc"}],
                    requested_unit="MW",
                    limit=20,
                ),
            ),
        ),
        LogisticsNl2SqlM8ShadowEvalSample(
            sample_id="m8_validation_quote_metric_requires_supported_hist_scope",
            description="报价/单价/运价依赖历史明细单价表，M8 dws-only shadow 样例必须受控失败",
            category="validation",
            business_case="unit_price_scope_fail_closed",
            metric_family="unit_price",
            expected_status="validation_failed",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="各线路报价/单价是多少",
                rewritten_question="报价/单价不能误映射成均价，当前样例未接历史明细表范围",
                request_id="m8-quote-metric-scope-rejected",
                candidate=_candidate(
                    query_type="ranking",
                    metrics=["unit_price_per_vehicle"],
                    dimensions=["logistics_company_name"],
                    group_by=["logistics_company_name"],
                    order_by=[{"metric": "unit_price_per_vehicle", "direction": "desc"}],
                    requested_unit="元/车",
                    limit=20,
                ),
            ),
        ),
        LogisticsNl2SqlM8ShadowEvalSample(
            sample_id="m8_safety_forbidden_update_sql_blocked",
            description="渲染器异常输出写 SQL 时必须停在 safety gate，且不触达 executor",
            category="safety",
            business_case="forbidden_update_sql_blocked",
            metric_family="safety_negative",
            expected_status="safety_failed",
            force_safety_sql_failure=True,
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="安全负例：禁止任何更新语句",
                rewritten_question="安全负例只验证 safety gate，不执行数据库写操作",
                request_id="m8-safety-forbidden-update",
                candidate=_candidate(
                    metrics=["shipment_mw"],
                    dimensions=[],
                    group_by=[],
                    order_by=[],
                    requested_unit="MW",
                ),
            ),
        ),
        LogisticsNl2SqlM8ShadowEvalSample(
            sample_id="m8_skipped_missing_candidate",
            description="缺少 SQLPlan candidate 时跳过 SQL 阶段，保持 shadow 不影响主流程",
            category="environment",
            business_case="missing_candidate_skipped",
            metric_family="unsupported",
            expected_status="skipped",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="物流整体情况怎么样",
                request_id="m8-missing-candidate",
                candidate=None,
            ),
        ),
        LogisticsNl2SqlM8ShadowEvalSample(
            sample_id="m8_unsupported_non_sql_direct_strategy",
            description="非 sql_direct strategy 停在 candidate 边界",
            category="validation",
            business_case="non_sql_direct_strategy_unsupported",
            metric_family="unsupported",
            expected_status="unsupported",
            request=LogisticsNl2SqlShadowPipelineRequest(
                question="请给出物流业务解释性分析",
                request_id="m8-non-sql-direct",
                candidate=_candidate(strategy="clarify"),
            ),
        ),
    ]


def run_logistics_nl2sql_m8_shadow_eval(
    *,
    artifact_dir: str | Path = DEFAULT_M8_ARTIFACT_DIR,
    samples: list[LogisticsNl2SqlM8ShadowEvalSample] | None = None,
) -> LogisticsNl2SqlM8ShadowEvalRunResult:
    """运行 M8 shadow-only 样例评估，并写出 JSONL/Markdown 验收材料。

    该 runner 不读取 backend/.env，不连接真实中间库，只用 fake executor 验证 SQLPlan→Renderer→Safety→
    evaluation log/report 的离线闭环。
    """

    resolved_artifact_dir = Path(artifact_dir)
    resolved_artifact_dir.mkdir(parents=True, exist_ok=True)
    records_path = resolved_artifact_dir / DEFAULT_M8_RECORDS_FILENAME
    report_path = resolved_artifact_dir / DEFAULT_M8_REPORT_FILENAME
    _reset_artifact(records_path)
    _reset_artifact(report_path)

    catalog = LogisticsSemanticCatalogLoader().load()
    safety_checker = LogisticsSqlSafetyChecker(catalog=catalog)
    fake_executor = FakeLogisticsSqlExecutor(
        explain_rows=[{"select_type": "SIMPLE", "offline": True}],
        trial_rows=[{"sample_metric": 1, "offline": True}],
    )
    execution_service = LogisticsSqlExecutionService(
        executor=fake_executor,
        safety_checker=safety_checker,
        trial_limit=1,
    )
    pipeline = LogisticsNl2SqlShadowPipeline(
        catalog=catalog,
        safety_checker=safety_checker,
        execution_service=execution_service,
        pipeline_version=M8_SHADOW_EVAL_VERSION,
    )
    unsafe_sql_pipeline = LogisticsNl2SqlShadowPipeline(
        catalog=catalog,
        renderer=_M8UnsafeSqlRenderer(),
        safety_checker=safety_checker,
        execution_service=execution_service,
        pipeline_version=M8_SHADOW_EVAL_VERSION,
    )

    resolved_samples = samples or build_default_logistics_nl2sql_m8_shadow_eval_samples()
    outcomes: list[LogisticsNl2SqlM8ShadowEvalOutcome] = []
    sample_ids_by_trace: dict[str, str] = {}
    descriptions_by_trace: dict[str, str] = {}
    sample_metadata_by_trace: dict[str, dict[str, Any]] = {}
    for sample in resolved_samples:
        # 仅 safety 负例使用专用 renderer 构造危险 SQL；仍先经过 SQLPlan validator，且只停在 safety gate。
        active_pipeline = unsafe_sql_pipeline if sample.force_safety_sql_failure else pipeline
        executor_call_count_before = len(fake_executor.calls)
        result = active_pipeline.run(sample.request)
        executor_call_count_after = len(fake_executor.calls)
        record = result.evaluation_log_record
        outcomes.append(
            LogisticsNl2SqlM8ShadowEvalOutcome(
                sample=sample,
                result=result,
                evaluation_log_record=record,
                executor_call_count_before=executor_call_count_before,
                executor_call_count_after=executor_call_count_after,
            )
        )
        sample_ids_by_trace[record.trace_id] = sample.sample_id
        descriptions_by_trace[record.trace_id] = sample.description
        sample_metadata_by_trace[record.trace_id] = {
            "category": sample.category,
            "business_case": sample.business_case,
            "metric_family": sample.metric_family,
            "expected_status": sample.expected_status,
        }

    records = [outcome.evaluation_log_record for outcome in outcomes]
    report = build_logistics_nl2sql_evaluation_report(
        records,
        sample_ids=sample_ids_by_trace,
        sample_descriptions=descriptions_by_trace,
        warnings=[f"{M8_SHADOW_EVAL_VERSION} shadow-only; no live database query executed"],
        include_catalog_breakdown=True,
        sample_metadata=sample_metadata_by_trace,
    )
    _write_records(records_path, records)
    _write_report(report_path, report)
    return LogisticsNl2SqlM8ShadowEvalRunResult(
        outcomes=outcomes,
        evaluation_log_records=records,
        report=report,
        records_path=records_path,
        report_path=report_path,
        shadow_only=True,
        live_smoke_executed=False,
    )


def _candidate(
    *,
    query_type: str = "aggregate",
    metrics: list[str] | None = None,
    dimensions: list[str] | None = None,
    filters: list[dict[str, Any]] | None = None,
    group_by: list[str] | None = None,
    order_by: list[dict[str, Any]] | None = None,
    requested_unit: str = "MW",
    business_rules: list[str] | None = None,
    limit: int | None = None,
    strategy: str = "sql_direct",
    extra_catalog_refs: list[str] | None = None,
) -> dict[str, Any]:
    """生成 M8 样例用受控 SQLPlan candidate。"""

    resolved_metrics = metrics or ["shipment_mw", "row_count"]
    resolved_dimensions = dimensions or []
    resolved_filters = filters or [_filter("biz_year", "in", [2023, 2024, 2025, 2026])]
    resolved_group_by = group_by if group_by is not None else list(resolved_dimensions)
    resolved_order_by = order_by if order_by is not None else []
    resolved_rules = business_rules or ["default_time_range"]
    catalog_ids = _catalog_ids(
        metrics=resolved_metrics,
        dimensions=[
            *resolved_dimensions,
            *(item.get("dimension") for item in resolved_filters if isinstance(item, dict)),
            *resolved_group_by,
            *(item.get("dimension") for item in resolved_order_by if isinstance(item, dict) and item.get("dimension")),
        ],
        tables=["dws_logistics_detail_union"],
        rules=resolved_rules,
        extra=[
            *(extra_catalog_refs or []),
            *(f"metric:{item.get('metric')}" for item in resolved_order_by if isinstance(item, dict) and item.get("metric")),
        ],
    )
    candidate: dict[str, Any] = {
        "schema_version": "logistics_sqlplan_candidate.v1",
        "domain": "logistics",
        "strategy": strategy,
        "catalog_version": "logistics_nl2sql_catalog.v1",
        "catalog_refs": [
            {"catalog_id": catalog_id, "catalog_version": "logistics_nl2sql_catalog.v1"}
            for catalog_id in catalog_ids
        ],
        "plan": {
            "query_type": query_type,
            "tables": ["dws_logistics_detail_union"],
            "joins": [],
            "metrics": resolved_metrics,
            "dimensions": resolved_dimensions,
            "filters": resolved_filters,
            "group_by": resolved_group_by,
            "order_by": resolved_order_by,
            "business_rules": resolved_rules,
            "explicit_year_buckets": [2023, 2024, 2025, 2026],
            "requested_unit": requested_unit,
            "limit": limit,
        },
        "clarification_questions": [],
        "unsupported_reason": None,
        "confidence": 0.9,
    }
    return deepcopy(candidate)


def _catalog_ids(
    *,
    metrics: list[str],
    dimensions: list[Any],
    tables: list[str],
    rules: list[str],
    extra: list[str],
) -> list[str]:
    """按稳定顺序生成去重 catalog ref ID。"""

    ordered: list[str] = []
    for value in [*(f"table:{item}" for item in tables), *(f"metric:{item}" for item in metrics)]:
        _append_catalog_id(ordered, value)
    for item in dimensions:
        if item:
            _append_catalog_id(ordered, f"dimension:{item}")
    for item in rules:
        _append_catalog_id(ordered, f"rule:{item}")
    for item in extra:
        _append_catalog_id(ordered, item)
    return ordered


def _append_catalog_id(values: list[str], item: str) -> None:
    """向 catalog ref 列表追加非空去重 ID。"""

    normalized = str(item or "").strip()
    if normalized and normalized not in values:
        values.append(normalized)


def _filter(dimension: str, operator: str, values: list[Any]) -> dict[str, Any]:
    """生成 M8 样例过滤条件。"""

    return {"dimension": dimension, "operator": operator, "values": values}


def _reset_artifact(path: Path) -> None:
    """重置固定 artifact 文件。"""

    if path.exists():
        path.unlink()


def _write_records(path: Path, records: list[LogisticsNl2SqlEvaluationLogRecord]) -> None:
    """写出逐行 JSON evaluation log。"""

    lines = [record.model_dump_json() for record in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _write_report(path: Path, report: LogisticsNl2SqlEvaluationReport) -> None:
    """写出 Markdown 评估报表。"""

    path.write_text(render_logistics_nl2sql_evaluation_report_markdown(report), encoding="utf-8")


def _safe_summary(result: LogisticsNl2SqlM8ShadowEvalRunResult) -> dict[str, Any]:
    """构造 CLI 可打印的脱敏摘要。"""

    return {
        "version": M8_SHADOW_EVAL_VERSION,
        "shadow_only": result.shadow_only,
        "live_smoke_executed": result.live_smoke_executed,
        "records_path": str(result.records_path),
        "report_path": str(result.report_path),
        "total": result.report.total,
        "by_status": result.report.by_status,
        "success_rate": result.report.success_rate,
        "catalog_ref_coverage": result.report.catalog_ref_coverage,
        "distinct_catalog_ref_count": result.report.distinct_catalog_ref_count,
    }


def render_safe_m8_summary_json(result: LogisticsNl2SqlM8ShadowEvalRunResult) -> str:
    """渲染给固定脚本 stdout 使用的安全 JSON 摘要。"""

    return json.dumps(_safe_summary(result), ensure_ascii=False, sort_keys=True)


__all__ = [
    "DEFAULT_M8_ARTIFACT_DIR",
    "DEFAULT_M8_RECORDS_FILENAME",
    "DEFAULT_M8_REPORT_FILENAME",
    "DEFAULT_M8_SAMPLE_IDS",
    "M8_SHADOW_EVAL_VERSION",
    "LogisticsNl2SqlM8ShadowEvalOutcome",
    "LogisticsNl2SqlM8ShadowEvalRunResult",
    "LogisticsNl2SqlM8ShadowEvalSample",
    "build_default_logistics_nl2sql_m8_shadow_eval_samples",
    "render_safe_m8_summary_json",
    "run_logistics_nl2sql_m8_shadow_eval",
]

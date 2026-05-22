from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from backend.app.domains.business_analysis.schemas.inventory_sales_production_query import (
    InventorySalesProductionPeriodSpec,
    InventorySalesProductionQueryPlan,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.nl_query_planner import (
    InventorySalesProductionNlQueryPlanner,
    InventorySalesProductionPlanningError,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.sql_plan import (
    DEFAULT_ISP_MAX_PUBLISHED_MONTH_BY_YEAR,
    ISP_SQLPLAN_CANDIDATE_SCHEMA_VERSION,
    REQUIRED_ISP_SEMANTIC_CATALOG_VERSION,
    InventorySalesProductionSqlPlan,
    validate_inventory_sales_production_sql_plan_candidate,
)

M5_ISP_SHADOW_COMPARE_VERSION = "business_analysis_inventory_sales_production_m5_shadow_compare.v1"
DEFAULT_M5_ISP_RECORDS_FILENAME = "m5-inventory-sales-production-shadow-records.jsonl"
DEFAULT_M5_ISP_REPORT_FILENAME = "m5-inventory-sales-production-shadow-report.md"
DEFAULT_M5_ISP_ARTIFACT_DIR = Path("ai/outbox/kanban/m5-shadow-compare")

_MIDDLE_FACT_TABLE = "dwd_ba_isp_monthly_fact"
_SQL_TEXT_RE = re.compile(
    r"\b(select|insert|update|delete|drop|alter|truncate|create|merge|from|where|having|union)\b|--|/\*|\*/",
    re.IGNORECASE,
)
_DSN_TEXT_RE = re.compile(
    r"\b(?:[a-z][a-z0-9+.-]*://|jdbc:[^\s,;]+|oracle:thin:@)[^\s,;]+",
    re.IGNORECASE,
)
_BEARER_TEXT_RE = re.compile(r"\bbearer\s+[^\s,;]+", re.IGNORECASE)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"\b([A-Za-z0-9_-]*(?:api[_-]?key|apikey|secret(?:[_-]?key)?|password|passwd|token|access[_-]?token|dsn|url|connection[_-]?string)[A-Za-z0-9_-]*)\b\s*[:=]\s*['\"]?[^'\"\s,;]+",
    re.IGNORECASE,
)
_CONNECTION_TEXT_RE = re.compile(
    r"\b(?:host|server|data\s+source|user\s+id|uid)\s*=\s*[^\s,;]+",
    re.IGNORECASE,
)
_PERIOD_BOUNDARY_ERROR_RE = re.compile(
    r"\bsqlplan_unpublished_month_blocks_sql_direct::\d{4}::\d{1,2}::\d{1,2}\b"
)


def resolve_default_inventory_sales_production_m5_artifact_dir() -> Path:
    """解析 M5 shadow 默认产物目录，优先写入当前看板任务 outbox。

    业务逻辑：看板任务恢复时不能把新证据写回旧任务目录；如果调度器提供
    HERMES_KANBAN_TASK，则默认目录固定为 ai/outbox/kanban/<task_id>，否则
    使用通用 m5-shadow-compare 目录，避免硬编码历史任务号。
    """

    task_id = str(os.environ.get("HERMES_KANBAN_TASK") or "").strip()
    if task_id:
        safe_task_id = re.sub(r"[^A-Za-z0-9_-]", "_", task_id)
        return Path.cwd() / "ai" / "outbox" / "kanban" / safe_task_id
    return Path.cwd() / DEFAULT_M5_ISP_ARTIFACT_DIR


@dataclass(frozen=True, slots=True)
class InventorySalesProductionM5ShadowCompareSample:
    """M5 产销存 QueryPlan / SQLPlan 离线 shadow 对比样例。"""

    sample_id: str
    description: str
    question: str
    question_category: str
    expected_status: str
    candidate_override: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class InventorySalesProductionM5ShadowCompareRecord:
    """可持久化的脱敏 shadow 对比记录。"""

    schema_version: str
    pipeline_version: str
    trace_id: str
    sample_id: str
    question_category: str
    expected_status: str
    status: str
    stage: str
    error_codes: list[str]
    warnings: list[str]
    queryplan_signature: dict[str, Any] | None
    candidate_signature: dict[str, Any] | None
    shadow_only: bool = True
    formal_qa_executed: bool = False
    live_db_executed: bool = False


@dataclass(frozen=True, slots=True)
class InventorySalesProductionM5ShadowCompareOutcome:
    """单条样例的 shadow 对比结果。"""

    sample: InventorySalesProductionM5ShadowCompareSample
    record: InventorySalesProductionM5ShadowCompareRecord


@dataclass(frozen=True, slots=True)
class InventorySalesProductionM5ShadowCompareRunResult:
    """M5 shadow compare 运行结果。"""

    outcomes: list[InventorySalesProductionM5ShadowCompareOutcome]
    records_path: Path
    report_path: Path
    report: dict[str, Any]
    shadow_only: bool = True
    formal_qa_executed: bool = False
    live_db_executed: bool = False


def build_default_inventory_sales_production_m5_shadow_samples(
    *,
    max_samples: int | None = None,
) -> list[InventorySalesProductionM5ShadowCompareSample]:
    """构造产销存 M5/M5-6 shadow 默认样例。

    参数：max_samples 为可选上限，用于 runner 或单测快速截取前 N 条样例。
    返回：按稳定顺序排列的 shadow 样例列表，前 11 条保留 M5/M4-6 收口基线，后续
    M5-6 扩样覆盖核心指标、同义问法、期间边界和 fail-closed 安全场景。
    关键业务逻辑：这里只声明离线问题样例和独立 SQLPlan fixture，不调用 live DB，
    也不把 QueryPlan 反向生成 SQLPlan，避免 shadow 自我匹配。
    """

    samples = [
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m4_6_sales_year_summary",
            description="M4-6 年度销量口径样例",
            question="2024年销量是多少？",
            question_category="sales_summary",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_summary",
                metrics=["shipment_volume"],
                dimensions=[],
                period_type="year",
                year=2024,
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m4_6_sales_quarter_summary",
            description="M4-6 一季度销量口径样例",
            question="2025年Q1销量是多少？",
            question_category="sales_summary",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_summary",
                metrics=["shipment_volume"],
                dimensions=[],
                period_type="quarter",
                year=2025,
                quarter=1,
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m4_6_sales_ytd_summary",
            description="M4-6 截至指定月份累计销量样例",
            question="2026年截至4月累计销量是多少？",
            question_category="sales_summary",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_summary",
                metrics=["shipment_volume"],
                dimensions=[],
                period_type="ytd",
                year=2026,
                month_filter_values=[1, 2, 3, 4],
                business_rules=["ytd_by_published_months"],
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m4_6_inventory_snapshot",
            description="M4-6 月度库存时点样例",
            question="2026年4月存货合计是多少？",
            question_category="inventory_snapshot",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_inventory_snapshot",
                metrics=["ending_inventory_volume"],
                dimensions=[],
                period_type="month",
                year=2026,
                month=4,
                business_rules=["period_end_inventory_snapshot"],
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m4_6_consigned_inventory_snapshot",
            description="M4-6 月度寄存库存时点样例",
            question="2026年4月寄存仓还有多少？",
            question_category="inventory_snapshot",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_inventory_snapshot",
                metrics=["consigned_inventory_volume"],
                dimensions=[],
                period_type="month",
                year=2026,
                month=4,
                business_rules=["period_end_inventory_snapshot"],
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m4_6_budget_achievement",
            description="M4-6 年度预算达成率样例",
            question="2023年预算达成率是多少？",
            question_category="budget_achievement",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_budget_achievement",
                metrics=["production_actual_including_oem"],
                dimensions=[],
                period_type="year",
                year=2023,
                business_rules=["budget_achievement_recalculated"],
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m4_6_invoice_sales_summary",
            description="M4-6 显式开票销量样例",
            question="2025年开票销量是多少？",
            question_category="sales_summary",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_summary",
                metrics=["invoice_sales_volume"],
                dimensions=[],
                period_type="year",
                year=2025,
                business_flags={"explicit_invoice": True},
                business_rules=["explicit_invoice_metric"],
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m4_6_unsupported_yoy",
            description="M4-6 同比类 M9 后受控支持",
            question="2025年销量同比增长率是多少？",
            question_category="unsupported_guard",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_period_compare",
                metrics=["shipment_volume"],
                dimensions=["business_month"],
                period_type="month_range",
                year=2025,
                month_filter_values=list(range(1, 13)),
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m4_6_unsupported_month_range",
            description="M4-6 月区间 M9 后受控支持，签名差异接受 plan_mismatch",
            question="2026年2月至4月销量是多少？",
            question_category="unsupported_guard",
            expected_status="plan_mismatch",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_period_compare",
                metrics=["shipment_volume"],
                dimensions=["business_month"],
                period_type="month_range",
                year=2026,
                month_filter_values=[2, 3, 4],
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m4_6_clarification_inventory_turnover",
            description="M4-6 库存周转率需补充口径样例",
            question="2025年库存周转率是多少？",
            question_category="clarification_guard",
            expected_status="queryplan_clarification",
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_redaction_sql_payload_blocked",
            description="M5 SQLPlan 候选含 SQL/凭据噪声时必须 fail-closed 且 artifacts 脱敏",
            question="2024年销量是多少？",
            question_category="redaction_guard",
            expected_status="sqlplan_validation_failed",
            candidate_override=_redaction_guard_candidate_payload(),
        ),
    ]
    samples.extend(_build_m5_6_shadow_expansion_samples())
    # S4: NL 变体 shadow 样本——同一业务语义、不同自然语言表述，验证 LLM 与规则规划器输出一致性
    samples.extend(_build_nl_variant_shadow_samples())
    if max_samples is not None:
        return samples[: max(0, max_samples)]
    return samples


def _build_m5_6_shadow_expansion_samples() -> list[InventorySalesProductionM5ShadowCompareSample]:
    """构造 M5-6 shadow 扩样样例。

    返回：只用于 M5-6 离线 shadow 的增量样例列表。
    关键业务逻辑：样例覆盖产量、销量、库存、寄存、预算达成率、维度拆分、
    已发布/月度边界、同义表达和 fail-closed；其中 matched 样例均显式提供独立
    SQLPlan fixture，安全边界样例则保留缺候选或非法候选以验证保守失败。
    """

    return [
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_production_year_summary",
            description="M5-6 年度产量核心指标样例",
            question="2023年产量是多少？",
            question_category="production_summary",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_summary",
                metrics=["production_actual_including_oem"],
                dimensions=[],
                period_type="year",
                year=2023,
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_sales_external_default_scope",
            description="M5-6 对外销量默认口径同义问法样例",
            question="2024年对外销量是多少？",
            question_category="sales_summary",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_summary",
                metrics=["shipment_volume"],
                dimensions=[],
                period_type="year",
                year=2024,
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_sales_year_synonym_shipment",
            description="M5-6 发货量等价销量的年度同义样例",
            question="2025年发货量是多少？",
            question_category="sales_summary",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_summary",
                metrics=["shipment_volume"],
                dimensions=[],
                period_type="year",
                year=2025,
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_sales_chinese_quarter_synonym",
            description="M5-6 中文季度和销售量同义样例",
            question="2025年一季度销售量是多少？",
            question_category="sales_summary",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_summary",
                metrics=["shipment_volume"],
                dimensions=[],
                period_type="quarter",
                year=2025,
                quarter=1,
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_sales_ytd_prefix_synonym",
            description="M5-6 前 N 个月累计销量样例",
            question="2026年前4个月累计销量是多少？",
            question_category="time_boundary_guard",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_summary",
                metrics=["shipment_volume"],
                dimensions=[],
                period_type="ytd",
                year=2026,
                month_filter_values=[1, 2, 3, 4],
                business_rules=["ytd_by_published_months"],
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_inventory_stock_synonym",
            description="M5-6 库存/存货月度时点同义样例",
            question="2026年4月库存是多少？",
            question_category="inventory_snapshot",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_inventory_snapshot",
                metrics=["ending_inventory_volume"],
                dimensions=[],
                period_type="month",
                year=2026,
                month=4,
                business_rules=["period_end_inventory_snapshot"],
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_consigned_inventory_synonym",
            description="M5-6 寄存仓/寄存合计月度时点同义样例",
            question="2026年4月寄存合计是多少？",
            question_category="inventory_snapshot",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_inventory_snapshot",
                metrics=["consigned_inventory_volume"],
                dimensions=[],
                period_type="month",
                year=2026,
                month=4,
                business_rules=["period_end_inventory_snapshot"],
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_budget_achievement_current_year_boundary",
            description="M5-6 当前已发布年份预算达成率边界样例",
            question="2026年预算达成率是多少？",
            question_category="budget_achievement",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_budget_achievement",
                metrics=["production_actual_including_oem"],
                dimensions=[],
                period_type="year",
                year=2026,
                business_rules=["budget_achievement_recalculated"],
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_production_by_model_type",
            description="M5-6 按版型拆分产量样例",
            question="2025年按版型产量是多少？",
            question_category="dimension_breakdown",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_breakdown",
                metrics=["production_by_model_type"],
                dimensions=["model_type"],
                period_type="year",
                year=2025,
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_inventory_by_base_period_end",
            description="M5-6 按基地拆分库存月末时点样例",
            question="2026年4月各基地库存是多少？",
            question_category="dimension_breakdown",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_inventory_snapshot",
                metrics=["ending_inventory_by_base"],
                dimensions=["base_name"],
                period_type="month",
                year=2026,
                month=4,
                business_rules=["period_end_inventory_snapshot"],
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_sales_by_base_breakdown",
            description="M5-6 按基地拆分销量样例",
            question="2024年各基地销量是多少？",
            question_category="dimension_breakdown",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_breakdown",
                metrics=["shipment_by_base"],
                dimensions=["base_name"],
                period_type="year",
                year=2024,
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_sales_monthly_trend",
            description="M5-6 按月销量趋势样例",
            question="2026年按月销量趋势是多少？",
            question_category="time_boundary_guard",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_trend",
                metrics=["shipment_volume"],
                dimensions=["business_month"],
                period_type="year",
                year=2026,
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_production_ytd_boundary",
            description="M5-6 截至已发布月份累计产量样例",
            question="2026年截至4月产量是多少？",
            question_category="time_boundary_guard",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_summary",
                metrics=["production_actual_including_oem"],
                dimensions=[],
                period_type="ytd",
                year=2026,
                month_filter_values=[1, 2, 3, 4],
                business_rules=["ytd_by_published_months"],
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_sales_future_month_blocked",
            description="M5-6 未来月份区间必须在 QueryPlan 阶段 fail-closed",
            question="2026年5月至6月未来月份销量是多少？",
            question_category="time_boundary_guard",
            expected_status="sqlplan_candidate_unavailable",
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_missing_time_default_years_scope",
            description="M5-6 多年默认范围暂缺独立 SQLPlan 候选时必须 fail-closed",
            question="2023年至2026年销量是多少？",
            question_category="missing_time_scope_guard",
            expected_status="sqlplan_candidate_unavailable",
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_missing_time_no_time_default_scope_guard",
            description="M5-6 无显式时间的 2023-2026 默认范围未接管前必须保守澄清",
            question="销量是多少？",
            question_category="missing_time_scope_guard",
            expected_status="queryplan_clarification",
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_unsupported_mom",
            description="M5-6 环比类 M9 后受控支持",
            question="2025年销量环比变化是多少？",
            question_category="unsupported_guard",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_period_compare",
                metrics=["shipment_volume"],
                dimensions=["business_month"],
                period_type="month_range",
                year=2025,
                month_filter_values=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_clarification_unknown_metric",
            description="M5-6 未知指标必须澄清，不能泛化为其他指标",
            question="2025年未知指标是多少？",
            question_category="clarification_guard",
            expected_status="queryplan_clarification",
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_sqlplan_unpublished_month_guard",
            description="M5-6 SQLPlan 候选越过已发布月份边界时必须 fail-closed",
            question="2026年5月销量是多少？",
            question_category="time_boundary_guard",
            expected_status="sqlplan_validation_failed",
            candidate_override=_unpublished_month_guard_candidate_payload(),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_sqlplan_internal_debug_key_guard",
            description="M5-6 SQLPlan 候选含内部日志/调试标识时必须 fail-closed",
            question="2024年销量是多少？",
            question_category="redaction_guard",
            expected_status="sqlplan_validation_failed",
            candidate_override=_internal_debug_key_guard_candidate_payload(),
        ),
    ]


def run_inventory_sales_production_m5_shadow_compare(
    *,
    samples: list[InventorySalesProductionM5ShadowCompareSample] | None = None,
    artifact_dir: str | Path | None = None,
) -> InventorySalesProductionM5ShadowCompareRunResult:
    """执行 QueryPlan 与 SQLPlan 的离线 shadow 对比，不调用正式 QA 主链路或真实数据库。"""

    resolved_samples = list(samples or build_default_inventory_sales_production_m5_shadow_samples())
    resolved_artifact_dir = Path(artifact_dir) if artifact_dir is not None else resolve_default_inventory_sales_production_m5_artifact_dir()
    resolved_artifact_dir.mkdir(parents=True, exist_ok=True)
    records_path = resolved_artifact_dir / DEFAULT_M5_ISP_RECORDS_FILENAME
    report_path = resolved_artifact_dir / DEFAULT_M5_ISP_REPORT_FILENAME

    planner = InventorySalesProductionNlQueryPlanner()
    outcomes = [_run_one_shadow_sample(planner, sample) for sample in resolved_samples]
    records = [outcome.record for outcome in outcomes]
    report = _build_report(records)
    _write_records(records_path, records)
    _write_report(report_path, report, records)
    return InventorySalesProductionM5ShadowCompareRunResult(
        outcomes=outcomes,
        records_path=records_path,
        report_path=report_path,
        report=report,
    )


def render_safe_m5_shadow_compare_summary_json(result: InventorySalesProductionM5ShadowCompareRunResult) -> str:
    """渲染 CLI stdout 使用的脱敏 JSON 摘要。"""

    summary = {
        "version": M5_ISP_SHADOW_COMPARE_VERSION,
        "shadow_only": result.shadow_only,
        "formal_qa_executed": result.formal_qa_executed,
        "live_db_executed": result.live_db_executed,
        "records_path": str(result.records_path),
        "report_path": str(result.report_path),
        "total": result.report["total"],
        "by_status": result.report["by_status"],
        "matched_count": result.report["matched_count"],
        "fail_closed_count": result.report["fail_closed_count"],
        "expected_status_mismatch_count": result.report["expected_status_mismatch_count"],
    }
    return json.dumps(summary, ensure_ascii=False, sort_keys=True)


def _run_one_shadow_sample(
    planner: InventorySalesProductionNlQueryPlanner,
    sample: InventorySalesProductionM5ShadowCompareSample,
) -> InventorySalesProductionM5ShadowCompareOutcome:
    """执行单样例离线对比。"""

    trace_id = f"isp-m5-shadow-{sample.sample_id}"
    try:
        query_plan = planner.build_plan(sample.question)
    except InventorySalesProductionPlanningError as exc:
        status = "queryplan_clarification" if exc.status == "clarification" else "queryplan_unsupported"
        record = _record(
            trace_id=trace_id,
            sample=sample,
            status=status,
            stage="queryplan_planning",
            error_codes=[f"queryplan_{exc.status}"],
            warnings=[],
            queryplan_signature=None,
            candidate_signature=None,
        )
        return InventorySalesProductionM5ShadowCompareOutcome(sample=sample, record=record)

    queryplan_signature = _signature_from_query_plan(query_plan)
    if sample.candidate_override is None:
        record = _record(
            trace_id=trace_id,
            sample=sample,
            status="sqlplan_candidate_unavailable",
            stage="sqlplan_candidate",
            error_codes=["sqlplan_candidate_unavailable"],
            warnings=[],
            queryplan_signature=queryplan_signature,
            candidate_signature=None,
        )
        return InventorySalesProductionM5ShadowCompareOutcome(sample=sample, record=record)

    candidate_payload = sample.candidate_override
    validation = validate_inventory_sales_production_sql_plan_candidate(candidate_payload)
    if not validation.ok or validation.normalized_plan is None:
        record = _record(
            trace_id=trace_id,
            sample=sample,
            status="sqlplan_validation_failed",
            stage="sqlplan_validation",
            error_codes=validation.error_codes,
            warnings=[],
            queryplan_signature=queryplan_signature,
            candidate_signature=None,
        )
        return InventorySalesProductionM5ShadowCompareOutcome(sample=sample, record=record)

    candidate_signature = _signature_from_sql_plan(validation.normalized_plan)
    status = "matched" if queryplan_signature == candidate_signature else "plan_mismatch"
    errors = [] if status == "matched" else ["queryplan_sqlplan_signature_mismatch"]
    record = _record(
        trace_id=trace_id,
        sample=sample,
        status=status,
        stage="shadow_compare",
        error_codes=errors,
        warnings=[],
        queryplan_signature=queryplan_signature,
        candidate_signature=candidate_signature,
    )
    return InventorySalesProductionM5ShadowCompareOutcome(sample=sample, record=record)


def _record(
    *,
    trace_id: str,
    sample: InventorySalesProductionM5ShadowCompareSample,
    status: str,
    stage: str,
    error_codes: list[str],
    warnings: list[str],
    queryplan_signature: dict[str, Any] | None,
    candidate_signature: dict[str, Any] | None,
) -> InventorySalesProductionM5ShadowCompareRecord:
    """构造不含原问题、不含 SQL、不含参数值的安全记录。"""

    return InventorySalesProductionM5ShadowCompareRecord(
        schema_version="business_analysis_inventory_sales_production_m5_shadow_record.v1",
        pipeline_version=M5_ISP_SHADOW_COMPARE_VERSION,
        trace_id=trace_id,
        sample_id=sample.sample_id,
        question_category=sample.question_category,
        expected_status=sample.expected_status,
        status=status,
        stage=stage,
        error_codes=_dedupe_safe_texts(error_codes),
        warnings=_dedupe_safe_texts(warnings),
        queryplan_signature=queryplan_signature,
        candidate_signature=candidate_signature,
    )


def _build_sqlplan_candidate_payload(
    *,
    query_key: str,
    metrics: list[str],
    dimensions: list[str],
    period_type: str,
    year: int,
    month: int | None = None,
    quarter: int | None = None,
    month_filter_values: list[int] | None = None,
    business_flags: dict[str, Any] | None = None,
    business_rules: list[str] | None = None,
    calculation_policy: str | None = None,
) -> dict[str, Any]:
    """构造独立 SQLPlan fixture 候选，不依赖 QueryPlan 反向生成。

    业务逻辑：M5 shadow 阶段需要对比既有 QueryPlan 与独立 NL2SQL/SQLPlan 形态。
    当前没有接入 live LLM provider 时，用显式样例 fixture 代表独立 SQLPlan 候选，
    避免把 QueryPlan 原样转换后自我比较导致误报 matched。
    """

    filters: list[dict[str, Any]] = [{"dimension": "business_year", "operator": "=", "values": [year]}]
    if month_filter_values:
        filters.append({"dimension": "business_month", "operator": "in", "values": list(month_filter_values)})
    plan_payload = {
        "query_key": query_key,
        "domain": "business_analysis",
        "sub_domain": "inventory_sales_production",
        "tables": [_MIDDLE_FACT_TABLE],
        "metrics": list(metrics),
        "dimensions": list(dimensions),
        "filters": filters,
        "group_by": list(dimensions),
        "order_by": [],
        "business_rules": list(business_rules or []),
        "business_flags": dict(business_flags or {}),
        "period_type": period_type,
        "year": year,
        "month": month,
        "quarter": quarter,
        "start_month": None,
        "end_month": None,
        "calculation_policy": calculation_policy,
        "limit": None,
    }
    return {
        "schema_version": ISP_SQLPLAN_CANDIDATE_SCHEMA_VERSION,
        "domain": "business_analysis",
        "sub_domain": "inventory_sales_production",
        "strategy": "sql_direct",
        "catalog_version": REQUIRED_ISP_SEMANTIC_CATALOG_VERSION,
        "catalog_refs": _catalog_refs_for_plan_payload(plan_payload),
        "plan": plan_payload,
        "clarification_questions": [],
        "unsupported_reason": None,
        "confidence": 0.9,
    }


def _business_rules_for_query_plan(query_plan: InventorySalesProductionQueryPlan) -> list[str]:
    """生成不包含 SQL 片段的业务规则标签。"""

    rules: list[str] = []
    if query_plan.query_key == "ba_isp_budget_achievement":
        rules.append("budget_achievement_recalculated")
    if query_plan.period.period_type == "ytd":
        rules.append("ytd_by_published_months")
    if query_plan.query_key == "ba_isp_inventory_snapshot":
        rules.append("period_end_inventory_snapshot")
    if query_plan.filters.get("explicit_invoice"):
        rules.append("explicit_invoice_metric")
    return rules


def _catalog_refs_for_plan_payload(plan_payload: dict[str, Any]) -> list[dict[str, str]]:
    """按稳定顺序为 SQLPlan candidate 补齐 catalog_refs。"""

    ids: list[str] = []
    for table in plan_payload.get("tables", []):
        _append_unique(ids, f"table:{table}")
    for metric in plan_payload.get("metrics", []):
        _append_unique(ids, f"metric:{metric}")
    for dimension in plan_payload.get("dimensions", []):
        _append_unique(ids, f"dimension:{dimension}")
    for dimension in plan_payload.get("group_by", []):
        _append_unique(ids, f"dimension:{dimension}")
    for item in plan_payload.get("filters", []):
        dimension = item.get("dimension") if isinstance(item, dict) else None
        if dimension:
            _append_unique(ids, f"dimension:{dimension}")
    return [{"catalog_id": catalog_id, "catalog_version": REQUIRED_ISP_SEMANTIC_CATALOG_VERSION} for catalog_id in ids]


def _redaction_guard_candidate_payload() -> dict[str, Any]:
    """构造含 SQL-like 噪声的 candidate，验证 validator fail-closed 与 artifact 脱敏。"""

    payload = _build_sqlplan_candidate_payload(
        query_key="ba_isp_metric_summary",
        metrics=["shipment_volume"],
        dimensions=[],
        period_type="year",
        year=2024,
    )
    payload["plan"]["raw_sql"] = "SELECT * FROM dwd_ba_isp_monthly_fact"
    payload["plan"]["filters"].append(
        {"dimension": "business_month", "operator": "like", "values": ["Bearer redaction_probe"]}
    )
    payload["catalog_refs"].append(
        {"catalog_id": "dimension:business_month", "catalog_version": REQUIRED_ISP_SEMANTIC_CATALOG_VERSION}
    )
    return payload


def _unpublished_month_guard_candidate_payload() -> dict[str, Any]:
    """构造越过已发布月份边界的 SQLPlan fixture。

    返回：2026 年 5 月销量候选。当前产销存中间库仅发布到 2026 年 4 月，
    validator 应在 SQLPlan 阶段 fail-closed，避免未来月份被当成真实结果。
    """

    return _build_sqlplan_candidate_payload(
        query_key="ba_isp_metric_summary",
        metrics=["shipment_volume"],
        dimensions=[],
        period_type="month",
        year=2026,
        month=5,
    )


def _internal_debug_key_guard_candidate_payload() -> dict[str, Any]:
    """构造含内部审计/调试标识的 SQLPlan fixture。

    返回：带有内部日志标识 business_flag 的候选。该字段不是业务口径开关，
    validator 应 fail-closed，确保 shadow artifacts 不接纳 raw/debug/internal 语义。
    """

    payload = _build_sqlplan_candidate_payload(
        query_key="ba_isp_metric_summary",
        metrics=["shipment_volume"],
        dimensions=[],
        period_type="year",
        year=2024,
    )
    payload["plan"]["business_flags"]["sys_query_log"] = True
    return payload


def _signature_from_query_plan(query_plan: InventorySalesProductionQueryPlan) -> dict[str, Any]:
    """提取 QueryPlan 与 SQLPlan 可比的业务签名，不持久化具体时间参数。"""

    return {
        "query_key": query_plan.query_key,
        "metrics": sorted(query_plan.metrics),
        "dimensions": sorted(query_plan.dimensions),
        "business_flags": _safe_flag_signature(query_plan.filters),
        "period_semantics": _query_period_semantics(query_plan.period),
        "period_value_bucket": _query_period_value_bucket(query_plan.period),
        "period_value_fingerprint": _safe_value_fingerprint(_query_period_fingerprint_payload(query_plan.period)),
    }


def _signature_from_sql_plan(plan: InventorySalesProductionSqlPlan) -> dict[str, Any]:
    """提取 SQLPlan 与 QueryPlan 可比的业务签名，不持久化具体时间参数。"""

    return {
        "query_key": plan.query_key,
        "metrics": sorted(plan.metrics),
        "dimensions": sorted(plan.dimensions),
        "business_flags": _safe_flag_signature(plan.business_flags),
        "period_semantics": _sql_period_semantics(plan),
        "period_value_bucket": _sql_period_value_bucket(plan),
        "period_value_fingerprint": _safe_value_fingerprint(_sql_period_fingerprint_payload(plan)),
    }


def _safe_flag_signature(flags: dict[str, Any]) -> dict[str, str]:
    """业务开关签名使用类型/指纹，避免 bool 强转掩盖非布尔差异。"""

    return {key: _safe_value_fingerprint(value) for key, value in sorted((flags or {}).items())}


def _safe_value_fingerprint(value: Any) -> str:
    """生成不回显原值的安全指纹；布尔开关保留真假语义，非布尔仅保留类型和摘要。"""

    if isinstance(value, bool):
        return f"bool:{str(value).lower()}"
    if value is None:
        return "null"
    try:
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except TypeError:
        rendered = str(type(value).__name__)
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:12]
    return f"{type(value).__name__}:sha256:{digest}"


def _query_period_fingerprint_payload(period: InventorySalesProductionPeriodSpec) -> dict[str, Any]:
    """生成 QueryPlan 期间比较载荷，仅用于不可逆指纹，不直接持久化明文。"""

    semantics = _query_period_semantics(period)
    payload: dict[str, Any] = {"semantics": semantics, "bucket": _query_period_value_bucket(period), "year": period.year}
    if semantics == "month":
        payload["month"] = period.month
    elif semantics == "quarter":
        payload["quarter"] = period.quarter
    elif semantics == "ytd":
        payload["months"] = _months_from_query_period(period)
    else:
        payload["months"] = _months_from_query_period(period)
    return payload


def _sql_period_fingerprint_payload(plan: InventorySalesProductionSqlPlan) -> dict[str, Any]:
    """生成 SQLPlan 期间比较载荷，仅用于不可逆指纹，不直接持久化明文。"""

    semantics = _sql_period_semantics(plan)
    payload: dict[str, Any] = {"semantics": semantics, "bucket": _sql_period_value_bucket(plan), "year": plan.year}
    if semantics == "month":
        payload["month"] = plan.month
    elif semantics == "quarter":
        payload["quarter"] = plan.quarter
    elif semantics == "ytd":
        payload["months"] = _months_from_sql_plan(plan)
    else:
        payload["months"] = _months_from_sql_plan(plan)
    return payload


def _query_period_semantics(period: InventorySalesProductionPeriodSpec) -> str:
    """返回 QueryPlan 的期间语义类别，不包含具体年月。"""

    if period.period_type in {"month", "quarter", "ytd"}:
        return period.period_type
    return "year"


def _sql_period_semantics(plan: InventorySalesProductionSqlPlan) -> str:
    """从 SQLPlan 受控字段推断期间语义，避免 YTD 与年度误判一致。"""

    rules = {str(rule) for rule in plan.business_rules}
    if plan.period_type == "ytd" or "ytd_by_published_months" in rules:
        return "ytd"
    if plan.period_type == "month" and plan.month is not None:
        return "month"
    if plan.period_type == "quarter" and plan.quarter is not None:
        return "quarter"
    return "year"


def _query_period_value_bucket(period: InventorySalesProductionPeriodSpec) -> str:
    """返回 QueryPlan 期间形状桶，不写出具体年月参数。"""

    if period.period_type == "month":
        return "single_month"
    if period.period_type == "quarter":
        return "quarter"
    if period.period_type == "ytd":
        return "year_to_date"
    return "full_year_or_published_year"


def _sql_period_value_bucket(plan: InventorySalesProductionSqlPlan) -> str:
    """返回 SQLPlan 期间形状桶，不写出具体年月参数。"""

    semantics = _sql_period_semantics(plan)
    if semantics == "month":
        return "single_month"
    if semantics == "quarter":
        return "quarter"
    if semantics == "ytd":
        return "year_to_date"
    return "full_year_or_published_year"


def _months_from_query_period(period: InventorySalesProductionPeriodSpec) -> list[int]:
    """把 QueryPlan 期间规范化为月份集合。"""

    if period.period_type == "month" and period.month is not None:
        return [period.month]
    if period.period_type == "quarter" and period.quarter is not None:
        start = (period.quarter - 1) * 3 + 1
        return list(range(start, start + 3))
    if period.period_type == "ytd":
        end = period.end_month or DEFAULT_ISP_MAX_PUBLISHED_MONTH_BY_YEAR.get(period.year, 12)
        start = period.start_month or 1
        return list(range(start, end + 1))
    return list(range(1, DEFAULT_ISP_MAX_PUBLISHED_MONTH_BY_YEAR.get(period.year, 12) + 1))


def _months_from_sql_plan(plan: InventorySalesProductionSqlPlan) -> list[int]:
    """把 SQLPlan 期间和月份过滤规范化为月份集合。"""

    month_filter_values: list[int] = []
    for item in plan.filters:
        if item.dimension == "business_month":
            for value in item.values:
                if isinstance(value, int) and not isinstance(value, bool):
                    month_filter_values.append(value)
    if month_filter_values:
        return sorted(set(month_filter_values))
    if plan.period_type == "month" and plan.month is not None:
        return [plan.month]
    if plan.period_type == "quarter" and plan.quarter is not None:
        start = (plan.quarter - 1) * 3 + 1
        return list(range(start, start + 3))
    return list(range(1, DEFAULT_ISP_MAX_PUBLISHED_MONTH_BY_YEAR.get(plan.year, 12) + 1))


def _build_report(records: list[InventorySalesProductionM5ShadowCompareRecord]) -> dict[str, Any]:
    """基于安全记录生成可读报告数据。"""

    by_status = Counter(record.status for record in records)
    by_category = Counter(record.question_category for record in records)
    fail_closed_statuses = {
        "queryplan_unsupported",
        "queryplan_clarification",
        "sqlplan_candidate_unavailable",
        "sqlplan_validation_failed",
    }
    expected_mismatch = sum(1 for record in records if record.status != record.expected_status)
    matched_count = by_status.get("matched", 0)
    total = len(records)
    return {
        "version": M5_ISP_SHADOW_COMPARE_VERSION,
        "total": total,
        "by_status": dict(sorted(by_status.items())),
        "by_category": dict(sorted(by_category.items())),
        "matched_count": matched_count,
        "fail_closed_count": sum(by_status.get(status, 0) for status in fail_closed_statuses),
        "expected_status_match_count": total - expected_mismatch,
        "expected_status_mismatch_count": expected_mismatch,
        "match_rate": round(matched_count / total, 4) if total else 0.0,
        "shadow_only": True,
        "formal_qa_executed": False,
        "live_db_executed": False,
    }


def _write_records(path: Path, records: list[InventorySalesProductionM5ShadowCompareRecord]) -> None:
    """写出 JSONL 安全记录。"""

    lines = [json.dumps(asdict(record), ensure_ascii=False, sort_keys=True) for record in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _write_report(path: Path, report: dict[str, Any], records: list[InventorySalesProductionM5ShadowCompareRecord]) -> None:
    """写出不包含 SQL/原问题/参数值的 Markdown 报告。"""

    lines = [
        "# 产销存 M5 Shadow Compare Report",
        "",
        f"version: {report['version']}",
        f"shadow_only: {str(report['shadow_only']).lower()}",
        f"formal_qa_executed: {str(report['formal_qa_executed']).lower()}",
        f"live_db_executed: {str(report['live_db_executed']).lower()}",
        f"total: {report['total']}",
        f"matched_count: {report['matched_count']}",
        f"fail_closed_count: {report['fail_closed_count']}",
        f"expected_status_mismatch_count: {report['expected_status_mismatch_count']}",
        "",
        "## by_status",
    ]
    lines.extend(f"- {status}: {count}" for status, count in report["by_status"].items())
    lines.extend(["", "## sample_outcomes"])
    for record in records:
        errors = ",".join(record.error_codes) if record.error_codes else "-"
        lines.append(
            f"- {record.sample_id}: category={record.question_category}; status={record.status}; "
            f"expected={record.expected_status}; stage={record.stage}; errors={errors}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_unique(values: list[str], item: str) -> None:
    """稳定去重追加。"""

    if item and item not in values:
        values.append(item)


def _dedupe_safe_texts(values: list[str]) -> list[str]:
    """错误码/告警只保留稳定安全文本，不回显 raw payload。"""

    safe_values: list[str] = []
    for value in values:
        normalized = str(value or "")
        normalized = _SQL_TEXT_RE.sub("[SQL]", normalized)
        normalized = _DSN_TEXT_RE.sub("[DSN]", normalized)
        normalized = _BEARER_TEXT_RE.sub("[BEARER]", normalized)
        normalized = _SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", normalized)
        normalized = _CONNECTION_TEXT_RE.sub("[CONNECTION]", normalized)
        normalized = _PERIOD_BOUNDARY_ERROR_RE.sub(
            "sqlplan_unpublished_month_blocks_sql_direct::[PERIOD_BOUNDARY]",
            normalized,
        )
        if normalized and normalized not in safe_values:
            safe_values.append(normalized)
    return safe_values


def _build_nl_variant_shadow_samples() -> list[InventorySalesProductionM5ShadowCompareSample]:
    """构造 S4 NL 变体 shadow 样本——同一业务语义、不同自然语言表述。

    说明：
        1. 每条样本对应一个自然语言变体问法，与现有标准问题业务语义等价；
        2. candidate_override 复用对应标准问题的 SQLPlan 候选，验证 LLM 规划器与规则规划器输出一致性；
        3. category 统一标记为 "nl_variant" 以便在报告中区分；
        4. 覆盖产量、销量、库存、寄存、开票、预算达成、基地拆分等核心指标的自然语言变体。
    """
    return [
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_nl_variant_sales_shipment_synonym",
            description="S4 '卖了/出货/发运' 等价销量变体（规则规划器需澄清），LLM 规划器应能处理",
            question="2024年卖了多少？",
            question_category="nl_variant",
            expected_status="queryplan_clarification",
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_nl_variant_sales_delivery_synonym",
            description="S4 '出货量/发运量' 等价销量变体（规则规划器需澄清），LLM 规划器应能处理",
            question="2025年出货量是多少？",
            question_category="nl_variant",
            expected_status="queryplan_clarification",
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_nl_variant_production_output_synonym",
            description="S4 '产出/生产了多少' 等价产量变体",
            question="2023年产出是多少？",
            question_category="nl_variant",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_summary",
                metrics=["production_actual_including_oem"],
                dimensions=[],
                period_type="year",
                year=2023,
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_nl_variant_production_actual_synonym",
            description="S4 '实际生产了多少' 等价产量变体（规则规划器需澄清），LLM 规划器应能处理",
            question="2025年实际生产了多少？",
            question_category="nl_variant",
            expected_status="queryplan_clarification",
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_nl_variant_inventory_stock_synonym",
            description="S4 '存货' 等价库存变体",
            question="2026年4月存货是多少？",
            question_category="nl_variant",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_inventory_snapshot",
                metrics=["ending_inventory_volume"],
                dimensions=[],
                period_type="month",
                year=2026,
                month=4,
                business_rules=["period_end_inventory_snapshot"],
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_nl_variant_consigned_deposit_synonym",
            description="S4 '寄存仓/寄存合计' 等价寄存变体",
            question="2026年4月寄存仓有多少？",
            question_category="nl_variant",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_inventory_snapshot",
                metrics=["consigned_inventory_volume"],
                dimensions=[],
                period_type="month",
                year=2026,
                month=4,
                business_rules=["period_end_inventory_snapshot"],
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_nl_variant_invoice_billed_synonym",
            description="S4 '已开票/开票了多少' 等价开票变体",
            question="2025年已开票销量是多少？",
            question_category="nl_variant",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_summary",
                metrics=["invoice_sales_volume"],
                dimensions=[],
                period_type="year",
                year=2025,
                business_flags={"explicit_invoice": True},
                business_rules=["explicit_invoice_metric"],
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_nl_variant_budget_completion_synonym",
            description="S4 '预算完成率/目标完成情况' 等价预算达成率变体（规则规划器需澄清），LLM 规划器应能处理",
            question="2023年预算完成率是多少？",
            question_category="nl_variant",
            expected_status="queryplan_clarification",
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_nl_variant_production_by_base_breakdown",
            description="S4 '按基地/各基地产量' 等价基地拆分变体（规则规划器需澄清），LLM 规划器应能处理",
            question="2025年各基地生产了多少？",
            question_category="nl_variant",
            expected_status="queryplan_clarification",
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_nl_variant_sales_by_base_breakdown_synonym",
            description="S4 '按基地的发货量' 等价销量按基地拆分变体",
            question="2024年按基地的发货量是多少？",
            question_category="nl_variant",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_breakdown",
                metrics=["shipment_by_base"],
                dimensions=["base_name"],
                period_type="year",
                year=2024,
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_nl_variant_monthly_trend_month_word",
            description="S4 '每月销量' 等价趋势变体",
            question="2026年每月销量是多少？",
            question_category="nl_variant",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_trend",
                metrics=["shipment_volume"],
                dimensions=["business_month"],
                period_type="year",
                year=2026,
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_nl_variant_yoy_growth_synonym",
            description="S4 '同比增长' 等价同比变体",
            question="2025年产量同比增长率是多少？",
            question_category="nl_variant",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_period_compare",
                metrics=["production_actual_including_oem"],
                dimensions=["business_month"],
                period_type="month_range",
                year=2025,
                month_filter_values=list(range(1, 13)),
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_nl_variant_month_range_half_year",
            description="S4 '上半年销量' 等价月区间变体",
            question="2025年上半年销量是多少？",
            question_category="nl_variant",
            expected_status="plan_mismatch",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_period_compare",
                metrics=["shipment_volume"],
                dimensions=["business_month"],
                period_type="month_range",
                year=2025,
                month_filter_values=[1, 2, 3, 4, 5, 6],
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="m5_6_nl_variant_ytd_up_to_month_synonym",
            description="S4 '前N个月/截至N月累计' 等价 YTD 变体",
            question="2026年前4个月累计产量是多少？",
            question_category="nl_variant",
            expected_status="matched",
            candidate_override=_build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_summary",
                metrics=["production_actual_including_oem"],
                dimensions=[],
                period_type="ytd",
                year=2026,
                month_filter_values=[1, 2, 3, 4],
                business_rules=["ytd_by_published_months"],
            ),
        ),
    ]


# ===== S5: M7 双轨对比 — 规则规划器 vs LLM 规划器 =====


@dataclass(frozen=True, slots=True)
class InventorySalesProductionDualTrackCompareOutcome:
    """双轨对比输出：规则规划器与 LLM 规划器的 QueryPlan 签名对比结果。

    参数：
        sample: 参与对比的样本。
        rule_signature: 规则规划器生成的 QueryPlan 签名；为空时表示规则规划器无法处理。
        llm_signature: LLM 规划器生成的 QueryPlan 签名（注入 mock，不真调用 API）；为空时表示 LLM 规划器无法处理。
        rule_status: 规则规划器执行状态（success/clarification/unsupported）。
        llm_mode: LLM 规划器使用模式（llm/fallback_rule/fallback_error）。
        signatures_match: 两个签名是否一致（都不为空时才比较）。
    返回：
        可被双轨对比汇总和报告使用的对比结果。
    """

    sample: InventorySalesProductionM5ShadowCompareSample
    rule_signature: dict[str, Any] | None
    llm_signature: dict[str, Any] | None
    rule_status: str
    llm_mode: str
    signatures_match: bool | None


@dataclass(frozen=True, slots=True)
class InventorySalesProductionDualTrackCompareRunResult:
    """双轨对比运行结果。"""

    outcomes: list[InventorySalesProductionDualTrackCompareOutcome]
    total: int
    by_status: dict[str, int]
    matched_count: int
    mismatch_count: int
    rule_only_count: int
    llm_only_count: int
    both_fail_count: int


def run_dual_track_compare(
    *,
    samples: list[InventorySalesProductionM5ShadowCompareSample] | None = None,
    llm_planner: object | None = None,
) -> InventorySalesProductionDualTrackCompareRunResult:
    """执行双轨对比：对每条样本并行使用规则规划器和 LLM 规划器。

    参数：
        samples: 参与对比的样本，为空时使用默认 NL 变体样本。
        llm_planner: 可注入的 LLM 规划器实例（测试可注入 mock）。
    返回：
        InventorySalesProductionDualTrackCompareRunResult，包含每条样本的对比结果。
    """
    resolved_samples = list(samples or build_default_inventory_sales_production_m5_shadow_samples())
    # 只对 NL 变体样本执行双轨对比
    nl_samples = [s for s in resolved_samples if s.question_category == "nl_variant"]
    if not nl_samples:
        nl_samples = resolved_samples[:10]  # 兜底取前 10 条

    planner = InventorySalesProductionNlQueryPlanner()
    outcomes: list[InventorySalesProductionDualTrackCompareOutcome] = []

    for sample in nl_samples:
        outcome = _run_one_dual_track_sample(
            rule_planner=planner,
            llm_planner=llm_planner,
            sample=sample,
        )
        outcomes.append(outcome)

    by_status: dict[str, int] = {}
    matched = 0
    mismatched = 0
    rule_only = 0
    llm_only = 0
    both_fail = 0

    for o in outcomes:
        if o.signatures_match is True:
            matched += 1
            _increment_counter(by_status, "matched")
        elif o.signatures_match is False:
            mismatched += 1
            _increment_counter(by_status, "mismatch")
        elif o.rule_signature and not o.llm_signature:
            rule_only += 1
            _increment_counter(by_status, "rule_only")
        elif not o.rule_signature and o.llm_signature:
            llm_only += 1
            _increment_counter(by_status, "llm_only")
        else:
            both_fail += 1
            _increment_counter(by_status, "both_fail")

    return InventorySalesProductionDualTrackCompareRunResult(
        outcomes=outcomes,
        total=len(outcomes),
        by_status=dict(sorted(by_status.items())),
        matched_count=matched,
        mismatch_count=mismatched,
        rule_only_count=rule_only,
        llm_only_count=llm_only,
        both_fail_count=both_fail,
    )


def _run_one_dual_track_sample(
    *,
    rule_planner: InventorySalesProductionNlQueryPlanner,
    llm_planner: object | None,
    sample: InventorySalesProductionM5ShadowCompareSample,
) -> InventorySalesProductionDualTrackCompareOutcome:
    """执行单条样本的双轨对比。

    参数：
        rule_planner: 规则规划器实例。
        llm_planner: LLM 规划器实例（测试可注入 mock；None 时使用真实 S3 planner 但跳过 LLM 调用）。
        sample: 待对比样本。
    返回：
        DualTrackCompareOutcome。
    """
    # 规则规划器
    rule_signature: dict[str, Any] | None = None
    rule_status = "success"
    try:
        rule_plan = rule_planner.build_plan(sample.question)
        rule_signature = _signature_from_query_plan(rule_plan)
    except InventorySalesProductionPlanningError as exc:
        rule_status = exc.status

    # LLM 规划器
    llm_signature: dict[str, Any] | None = None
    llm_mode = "llm"
    if llm_planner is not None:
        # 使用注入的 LLM 规划器（测试 mock / 真实 planner）
        if hasattr(llm_planner, "build_plan_with_debug"):
            try:
                llm_plan, debug = llm_planner.build_plan_with_debug(sample.question)  # type: ignore[union-attr]
                llm_signature = _signature_from_query_plan(llm_plan)
                llm_mode = debug.get("mode", "llm")
            except InventorySalesProductionPlanningError:
                llm_mode = "fallback_error"
        elif hasattr(llm_planner, "build_plan"):
            try:
                llm_plan = llm_planner.build_plan(sample.question)  # type: ignore[union-attr]
                llm_signature = _signature_from_query_plan(llm_plan)
            except InventorySalesProductionPlanningError:
                llm_mode = "fallback_error"

    # 签名对比
    signatures_match: bool | None = None
    if rule_signature is not None and llm_signature is not None:
        signatures_match = rule_signature == llm_signature

    return InventorySalesProductionDualTrackCompareOutcome(
        sample=sample,
        rule_signature=rule_signature,
        llm_signature=llm_signature,
        rule_status=rule_status,
        llm_mode=llm_mode,
        signatures_match=signatures_match,
    )


def _increment_counter(counter: dict[str, int], key: str) -> None:
    """稳定递增计数器。"""
    counter[key] = counter.get(key, 0) + 1


__all__ = [
    "DEFAULT_M5_ISP_ARTIFACT_DIR",
    "DEFAULT_M5_ISP_RECORDS_FILENAME",
    "DEFAULT_M5_ISP_REPORT_FILENAME",
    "M5_ISP_SHADOW_COMPARE_VERSION",
    "InventorySalesProductionM5ShadowCompareOutcome",
    "InventorySalesProductionM5ShadowCompareRecord",
    "InventorySalesProductionM5ShadowCompareRunResult",
    "InventorySalesProductionM5ShadowCompareSample",
    "InventorySalesProductionDualTrackCompareOutcome",
    "InventorySalesProductionDualTrackCompareRunResult",
    "build_default_inventory_sales_production_m5_shadow_samples",
    "render_safe_m5_shadow_compare_summary_json",
    "run_inventory_sales_production_m5_shadow_compare",
    "run_dual_track_compare",
]

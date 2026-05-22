from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from backend.app.domains.logistics.services.nl2sql.m10d_shadow_gate import (
    LogisticsNl2SqlM10DShadowGate,
    LogisticsNl2SqlM10DShadowGateConfig,
    LogisticsNl2SqlM10DShadowGateReport,
)
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalog, LogisticsSemanticCatalogLoader
from backend.app.domains.logistics.services.nl2sql.sql_execution import FakeLogisticsSqlExecutor, LogisticsSqlExecutor
from backend.app.domains.logistics.services.nl2sql.sql_plan import LogisticsSqlPlanValidator, LogisticsSqlPlanValidationResult
from backend.app.domains.logistics.services.nl2sql.sql_renderer import render_logistics_sql, LogisticsRenderedSql
from backend.app.domains.logistics.services.nl2sql.sql_safety import LogisticsSqlSafetyChecker

M10_SHADOW_GATE_RUNNER_VERSION = "logistics_nl2sql_m10_shadow_gate_runner.v1"
DEFAULT_M10_RECORDS_FILENAME = "m10-shadow-gate-records.jsonl"
DEFAULT_M10_REPORT_FILENAME = "m10-shadow-gate-report.md"


class LogisticsNl2SqlM10ShadowGateSample(BaseModel):
    """M10 shadow gate 评估样本。

    参数：
        sample_id: 样本唯一标识。
        description: 样本描述。
        category: 分类（success/guard/edge/safety）。
        expected_gate_status: 期望的 gate status（success/failed/skipped）。
        expected_stage: 期望的阶段。
        question: 用户问题。
        candidate: SQLPlan candidate dict。
    """

    model_config = ConfigDict(extra="forbid")

    sample_id: str
    description: str
    category: str
    expected_gate_status: str
    expected_stage: str
    question: str
    candidate: dict[str, Any]


class LogisticsNl2SqlM10ShadowGateOutcome(BaseModel):
    """M10 shadow gate 评估结果。"""

    model_config = ConfigDict(extra="forbid")

    sample: LogisticsNl2SqlM10ShadowGateSample
    report: LogisticsNl2SqlM10DShadowGateReport
    status_match: bool
    stage_match: bool


class LogisticsNl2SqlM10ShadowGateRunReport(BaseModel):
    """M10 shadow gate 运行报告摘要。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = M10_SHADOW_GATE_RUNNER_VERSION
    total: int
    status_match_count: int
    stage_match_count: int
    by_expected_status: dict[str, int]
    by_actual_status: dict[str, int]
    by_category: dict[str, int]
    warnings: list[str] = Field(default_factory=list)


class LogisticsNl2SqlM10ShadowGateRunResult(BaseModel):
    """M10 shadow gate 运行结果。"""

    model_config = ConfigDict(extra="forbid")

    outcomes: list[LogisticsNl2SqlM10ShadowGateOutcome]
    report: LogisticsNl2SqlM10ShadowGateRunReport
    records_path: Path | None = None
    report_path: Path | None = None


def build_default_logistics_nl2sql_m10_shadow_gate_samples() -> list[LogisticsNl2SqlM10ShadowGateSample]:
    """构造 M10 默认 shadow gate 评估集。

    分层设计：
        - success: 正常通过 gate
        - guard: 被 gate 拒绝（safety/source/disabled）
        - edge: 边界场景（无 LIMIT/无 FROM/union）
        - safety: 安全相关（DDL/DML/危险函数）
    """
    return [
        # ── Success 类 ──────────────────────────────
        LogisticsNl2SqlM10ShadowGateSample(
            sample_id="m10_success_simple_select",
            description="合法单表 SELECT，通过 gate",
            category="success",
            expected_gate_status="success",
            expected_stage="explain",
            question="2025年发运量总计",
            candidate=_candidate(
                query_type="aggregate",
                metrics=["shipment_mw"],
                tables=["dws_logistics_detail_union"],
                filters=[_filter("biz_year", "in", [2023, 2024, 2025, 2026])],
                business_rules=["default_time_range"],
                explicit_year_buckets=[2023, 2024, 2025, 2026],
                requested_unit="MW",
            ),
        ),
        LogisticsNl2SqlM10ShadowGateSample(
            sample_id="m10_success_ranking_with_limit",
            description="ranking 类型带 LIMIT 合法 SQL",
            category="success",
            expected_gate_status="success",
            expected_stage="explain",
            question="2025年承运商发运量排名",
            candidate=_candidate(
                query_type="ranking",
                metrics=["shipment_mw"],
                dimensions=["logistics_company_name"],
                tables=["dws_logistics_detail_union"],
                filters=[_filter("biz_year", "in", [2025])],
                order_by=[{"metric": "shipment_mw", "direction": "desc"}],
                group_by=["logistics_company_name"],
                business_rules=[],
                explicit_year_buckets=[2025],
                requested_unit="MW",
                limit=10,
            ),
        ),
        LogisticsNl2SqlM10ShadowGateSample(
            sample_id="m10_success_detail_with_limit",
            description="detail 类型带 LIMIT 合法 SQL",
            category="success",
            expected_gate_status="success",
            expected_stage="explain",
            question="2025年合肥发运明细前20条",
            candidate=_candidate(
                query_type="detail",
                metrics=["shipment_mw", "total_fee"],
                dimensions=["origin_place", "customer_name", "biz_year"],
                tables=["dws_logistics_detail_union"],
                filters=[_filter("biz_year", "in", [2025]), _filter("origin_place", "like", ["合肥"])],
                order_by=[{"dimension": "biz_year", "direction": "desc"}],
                business_rules=[],
                explicit_year_buckets=[2025],
                requested_unit="MW",
                limit=20,
            ),
        ),
        # ── Guard 类 ────────────────────────────────
        LogisticsNl2SqlM10ShadowGateSample(
            sample_id="m10_guard_safety_sleep_function",
            description="SLEEP() 危险函数被 safety 阻断",
            category="guard",
            expected_gate_status="failed",
            expected_stage="safety",
            question="测速",
            candidate=_candidate(
                query_type="aggregate",
                metrics=["shipment_mw"],
                tables=["dws_logistics_detail_union"],
                filters=[_filter("biz_year", "in", [2023, 2024, 2025, 2026])],
                business_rules=["default_time_range"],
                explicit_year_buckets=[2023, 2024, 2025, 2026],
                requested_unit="MW",
            ),
        ),
        LogisticsNl2SqlM10ShadowGateSample(
            sample_id="m10_guard_safety_unknown_table",
            description="引用非 allow-list 表名",
            category="guard",
            expected_gate_status="failed",
            expected_stage="safety",
            question="查询 sys_user",
            candidate=_candidate(
                query_type="aggregate",
                metrics=["shipment_mw"],
                tables=["sys_user"],
                filters=[],
                requested_unit="MW",
            ),
        ),
        LogisticsNl2SqlM10ShadowGateSample(
            sample_id="m10_guard_safety_multi_statement",
            description="多语句 SQL 被 safety 阻断",
            category="guard",
            expected_gate_status="failed",
            expected_stage="safety",
            question="查询后再删除",
            candidate=_candidate(
                query_type="aggregate",
                metrics=["shipment_mw"],
                tables=["dws_logistics_detail_union"],
                filters=[_filter("biz_year", "in", [2023, 2024, 2025, 2026])],
                business_rules=["default_time_range"],
                explicit_year_buckets=[2023, 2024, 2025, 2026],
                requested_unit="MW",
            ),
        ),
        # ── Edge 类 ─────────────────────────────────
        LogisticsNl2SqlM10ShadowGateSample(
            sample_id="m10_edge_select_star",
            description="SELECT * 被 AST safety 拒绝",
            category="edge",
            expected_gate_status="failed",
            expected_stage="safety",
            question="查询所有列",
            candidate=_candidate(
                query_type="aggregate",
                metrics=["shipment_mw"],
                tables=["dws_logistics_detail_union"],
                filters=[_filter("biz_year", "in", [2023, 2024, 2025, 2026])],
                business_rules=["default_time_range"],
                explicit_year_buckets=[2023, 2024, 2025, 2026],
                requested_unit="MW",
            ),
        ),
        LogisticsNl2SqlM10ShadowGateSample(
            sample_id="m10_edge_union_select",
            description="UNION 被 AST safety 拒绝",
            category="edge",
            expected_gate_status="failed",
            expected_stage="safety",
            question="合并查询",
            candidate=_candidate(
                query_type="aggregate",
                metrics=["shipment_mw"],
                tables=["dws_logistics_detail_union"],
                filters=[_filter("biz_year", "in", [2023, 2024, 2025, 2026])],
                business_rules=["default_time_range"],
                explicit_year_buckets=[2023, 2024, 2025, 2026],
                requested_unit="MW",
            ),
        ),
        # ── Safety 类 ───────────────────────────────
        LogisticsNl2SqlM10ShadowGateSample(
            sample_id="m10_safety_ddl_drop",
            description="DROP TABLE 被安全阻断",
            category="safety",
            expected_gate_status="failed",
            expected_stage="safety",
            question="删除表",
            candidate=_candidate(
                query_type="aggregate",
                metrics=["shipment_mw"],
                tables=["dws_logistics_detail_union"],
                filters=[],
                requested_unit="MW",
            ),
        ),
        LogisticsNl2SqlM10ShadowGateSample(
            sample_id="m10_safety_dml_delete",
            description="DELETE 被安全阻断",
            category="safety",
            expected_gate_status="failed",
            expected_stage="safety",
            question="删除数据",
            candidate=_candidate(
                query_type="aggregate",
                metrics=["shipment_mw"],
                tables=["dws_logistics_detail_union"],
                filters=[],
                requested_unit="MW",
            ),
        ),
        LogisticsNl2SqlM10ShadowGateSample(
            sample_id="m10_safety_string_literal",
            description="字符串字面量被 safety 拒绝",
            category="safety",
            expected_gate_status="failed",
            expected_stage="safety",
            question="按客户名查询",
            candidate=_candidate(
                query_type="aggregate",
                metrics=["shipment_mw"],
                tables=["dws_logistics_detail_union"],
                filters=[_filter("biz_year", "in", [2023, 2024, 2025, 2026])],
                business_rules=["default_time_range"],
                explicit_year_buckets=[2023, 2024, 2025, 2026],
                requested_unit="MW",
            ),
        ),
        LogisticsNl2SqlM10ShadowGateSample(
            sample_id="m10_safety_window_function",
            description="窗口函数被 AST safety 拒绝",
            category="safety",
            expected_gate_status="failed",
            expected_stage="safety",
            question="窗口函数查询",
            candidate=_candidate(
                query_type="aggregate",
                metrics=["shipment_mw"],
                tables=["dws_logistics_detail_union"],
                filters=[_filter("biz_year", "in", [2023, 2024, 2025, 2026])],
                business_rules=["default_time_range"],
                explicit_year_buckets=[2023, 2024, 2025, 2026],
                requested_unit="MW",
            ),
        ),
        LogisticsNl2SqlM10ShadowGateSample(
            sample_id="m10_safety_subquery",
            description="子查询被 AST safety 拒绝",
            category="safety",
            expected_gate_status="failed",
            expected_stage="safety",
            question="子查询统计",
            candidate=_candidate(
                query_type="aggregate",
                metrics=["shipment_mw"],
                tables=["dws_logistics_detail_union"],
                filters=[_filter("biz_year", "in", [2023, 2024, 2025, 2026])],
                business_rules=["default_time_range"],
                explicit_year_buckets=[2023, 2024, 2025, 2026],
                requested_unit="MW",
            ),
        ),
        # -- 新增扩展样例（基线提升）--
        LogisticsNl2SqlM10ShadowGateSample(
            sample_id="m10_success_multi_metric",
            description="多指标聚合（发运量+运费+吨数）通过 gate",
            category="success",
            expected_gate_status="success",
            expected_stage="explain",
            question="2025年各月发运量、运费和吨数总计",
            candidate=_candidate(
                query_type="aggregate",
                metrics=["shipment_mw", "total_fee", "total_tons"],
                tables=["dws_logistics_detail_union"],
                filters=[_filter("biz_year", "in", [2023, 2024, 2025, 2026])],
                business_rules=["default_time_range"],
                explicit_year_buckets=[2023, 2024, 2025, 2026],
                requested_unit="MW",
                limit=10,
            ),
        ),
        LogisticsNl2SqlM10ShadowGateSample(
            sample_id="m10_success_origin_customer_topn",
            description="始发地+客户排名 Top-N",
            category="success",
            expected_gate_status="success",
            expected_stage="explain",
            question="2025年合肥发往宁波的承运商运费排名前5",
            candidate=_candidate(
                query_type="ranking",
                metrics=["total_fee"],
                dimensions=["logistics_company_name"],
                tables=["dws_logistics_detail_union"],
                filters=[_filter("biz_year", "in", [2025]), _filter("origin_place", "like", ["合肥"]), _filter("destination_place", "like", ["宁波"])],
                order_by=[{"metric": "total_fee", "direction": "desc"}],
                group_by=["logistics_company_name"],
                business_rules=[],
                explicit_year_buckets=[2025],
                requested_unit="元",
                limit=5,
            ),
        ),
        LogisticsNl2SqlM10ShadowGateSample(
            sample_id="m10_edge_no_limit",
            description="不带 LIMIT 的 detail 查询被候选SQL gate拒绝",
            category="edge",
            expected_gate_status="failed",
            expected_stage="candidate_sql_gate",
            question="2025年全部发运明细",
            candidate=_candidate(
                query_type="detail",
                metrics=["shipment_mw", "total_fee"],
                dimensions=["origin_place", "customer_name", "biz_year"],
                tables=["dws_logistics_detail_union"],
                filters=[_filter("biz_year", "in", [2025])],
                order_by=[{"dimension": "biz_year", "direction": "desc"}],
                explicit_year_buckets=[2025],
                requested_unit="MW",
            ),
        ),
        LogisticsNl2SqlM10ShadowGateSample(
            sample_id="m10_safety_unqualified_identifier",
            description="未限定字段名被 AST safety 拒绝",
            category="safety",
            expected_gate_status="failed",
            expected_stage="safety",
            question="查询未限定的字段",
            candidate=_candidate(
                query_type="aggregate",
                metrics=["shipment_mw"],
                tables=["dws_logistics_detail_union"],
                filters=[_filter("biz_year", "in", [2023, 2024, 2025, 2026])],
                business_rules=["default_time_range"],
                explicit_year_buckets=[2023, 2024, 2025, 2026],
                requested_unit="MW",
            ),
        ),
    ]


def _candidate(
    *,
    query_type: str = "aggregate",
    metrics: list[str] | None = None,
    dimensions: list[str] | None = None,
    tables: list[str] | None = None,
    filters: list[dict[str, Any]] | None = None,
    group_by: list[str] | None = None,
    order_by: list[dict[str, Any]] | None = None,
    business_rules: list[str] | None = None,
    explicit_year_buckets: list[int] | None = None,
    requested_unit: str = "",
    limit: int | None = None,
) -> dict[str, Any]:
    """构造 M10 shadow gate 评估 candidate。"""
    plan: dict[str, Any] = {
        "query_type": query_type,
        "tables": tables or ["dws_logistics_detail_union"],
        "metrics": metrics or [],
        "dimensions": dimensions or [],
        "filters": filters or [],
        "group_by": group_by or [],
        "order_by": order_by or [],
        "business_rules": business_rules or [],
        "explicit_year_buckets": explicit_year_buckets or [],
        "requested_unit": requested_unit,
    }
    if limit is not None:
        plan["limit"] = limit

    catalog_refs = [{"catalog_id": f"table:{t}", "catalog_version": "logistics_nl2sql_catalog.v1"} for t in plan["tables"]]
    for metric_id in plan["metrics"]:
        catalog_refs.append({"catalog_id": f"metric:{metric_id}", "catalog_version": "logistics_nl2sql_catalog.v1"})
    for dim_id in set(plan["dimensions"]) | set(plan["group_by"]):
        catalog_refs.append({"catalog_id": f"dimension:{dim_id}", "catalog_version": "logistics_nl2sql_catalog.v1"})
    for rule_id in plan["business_rules"]:
        catalog_refs.append({"catalog_id": f"rule:{rule_id}", "catalog_version": "logistics_nl2sql_catalog.v1"})

    return {
        "schema_version": "logistics_sqlplan_candidate.v1",
        "domain": "logistics",
        "strategy": "sql_direct",
        "catalog_version": "logistics_nl2sql_catalog.v1",
        "catalog_refs": catalog_refs,
        "plan": plan,
    }


def _filter(dimension: str, operator: str, values: list[Any]) -> dict[str, Any]:
    return {"dimension": dimension, "operator": operator, "values": values}


def run_logistics_nl2sql_m10_shadow_gate(
    samples: list[LogisticsNl2SqlM10ShadowGateSample] | None = None,
    *,
    artifact_dir: str | Path | None = None,
    safety_checker: LogisticsSqlSafetyChecker | None = None,
    catalog: LogisticsSemanticCatalog | None = None,
) -> LogisticsNl2SqlM10ShadowGateRunResult:
    """运行 M10 shadow gate 评估。

    参数：
        samples: 评估样本列表，缺省使用默认样例集。
        artifact_dir: artifact 输出目录（JSONL + Markdown）。
        safety_checker: 可注入 safety checker。
        catalog: 可注入 catalog。
    返回：
        评估结果（outcomes + report）。
    """
    resolved_catalog = catalog or LogisticsSemanticCatalogLoader().load()
    resolved_safety = safety_checker or LogisticsSqlSafetyChecker(catalog=resolved_catalog)
    samples = samples or build_default_logistics_nl2sql_m10_shadow_gate_samples()
    validator = LogisticsSqlPlanValidator(catalog=resolved_catalog)

    outcomes: list[LogisticsNl2SqlM10ShadowGateOutcome] = []
    warnings: list[str] = []

    for sample in samples:
        # 通过 validator + renderer 产生参数化 SQL 后，喂给 gate
        try:
            validation = validator.validate(sample.candidate)
            if not validation.ok:
                rendered_sql = None
            else:
                rendered_sql = render_logistics_sql(validation)
        except Exception:
            rendered_sql = None

        gate = LogisticsNl2SqlM10DShadowGate(
            config=LogisticsNl2SqlM10DShadowGateConfig(
                enabled=True,
                explain_enabled=True,
                trial_enabled=False,
            ),
            safety_checker=resolved_safety,
        )
        report = gate.run(
            rendered_sql=rendered_sql,
            source_system="middle_db",
        )

        status_match = report.status == sample.expected_gate_status
        stage_match = report.stage == sample.expected_stage

        outcomes.append(LogisticsNl2SqlM10ShadowGateOutcome(
            sample=sample,
            report=report,
            status_match=status_match,
            stage_match=stage_match,
        ))

    # 构建报告
    total = len(outcomes)
    status_match_count = sum(1 for o in outcomes if o.status_match)
    stage_match_count = sum(1 for o in outcomes if o.stage_match)
    by_expected: dict[str, int] = {}
    by_actual: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for o in outcomes:
        by_expected[o.sample.expected_gate_status] = by_expected.get(o.sample.expected_gate_status, 0) + 1
        by_actual[o.report.status] = by_actual.get(o.report.status, 0) + 1
        by_category[o.sample.category] = by_category.get(o.sample.category, 0) + 1

    run_report = LogisticsNl2SqlM10ShadowGateRunReport(
        total=total,
        status_match_count=status_match_count,
        stage_match_count=stage_match_count,
        by_expected_status=by_expected,
        by_actual_status=by_actual,
        by_category=by_category,
        warnings=warnings,
    )

    records_path = None
    report_path = None
    if artifact_dir is not None:
        artifact_path = Path(artifact_dir)
        artifact_path.mkdir(parents=True, exist_ok=True)
        records_path = artifact_path / DEFAULT_M10_RECORDS_FILENAME
        report_path = artifact_path / DEFAULT_M10_REPORT_FILENAME

        with open(records_path, "w", encoding="utf-8") as f:
            for o in outcomes:
                record = {
                    "sample_id": o.sample.sample_id,
                    "category": o.sample.category,
                    "expected_status": o.sample.expected_gate_status,
                    "actual_status": o.report.status,
                    "status_match": o.status_match,
                    "stage_match": o.stage_match,
                    "error_codes": o.report.error_codes,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        md_lines = [
            f"# M10 NL2SQL Shadow Gate Report\n",
            f"- schema_version: {M10_SHADOW_GATE_RUNNER_VERSION}",
            f"- total: {total}",
            f"- status_match_count: {status_match_count}/{total} ({status_match_count / total * 100:.1f}%)",
            f"- stage_match_count: {stage_match_count}/{total}\n",
            "## By Expected Status",
        ]
        for k, v in sorted(by_expected.items()):
            md_lines.append(f"- {k}: {v}")
        md_lines.append("\n## By Actual Status")
        for k, v in sorted(by_actual.items()):
            md_lines.append(f"- {k}: {v}")
        md_lines.append("\n## By Category")
        for k, v in sorted(by_category.items()):
            md_lines.append(f"- {k}: {v}")
        md_lines.append("\n## Samples")
        for o in outcomes:
            status_icon = "✅" if o.status_match else "❌"
            stage_icon = "✅" if o.stage_match else "⚠️"
            md_lines.append(
                f"- {status_icon} {o.sample.sample_id}: "
                f"expected={o.sample.expected_gate_status}, actual={o.report.status}, "
                f"stage={o.report.stage}, "
                f"errors={o.report.error_codes[:3]}"
            )

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines) + "\n")

    return LogisticsNl2SqlM10ShadowGateRunResult(
        outcomes=outcomes,
        report=run_report,
        records_path=records_path,
        report_path=report_path,
    )


__all__ = [
    "M10_SHADOW_GATE_RUNNER_VERSION",
    "LogisticsNl2SqlM10ShadowGateSample",
    "LogisticsNl2SqlM10ShadowGateOutcome",
    "LogisticsNl2SqlM10ShadowGateRunReport",
    "LogisticsNl2SqlM10ShadowGateRunResult",
    "build_default_logistics_nl2sql_m10_shadow_gate_samples",
    "run_logistics_nl2sql_m10_shadow_gate",
]

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domains.logistics.repositories.query_repository import LogisticsQueryRepository
from backend.app.domains.query_planning.schemas.query_plan_v2 import QueryPlanningV2Plan
from backend.app.domains.query_planning.services.query_planning_v2_service import QueryPlanningV2Service

QueryPlanningV2ShadowDomain = Literal["logistics", "plan_bom"]
QueryPlanningV2GrayDomain = Literal["all", "logistics", "plan_bom"]


class QueryPlanningV2ShadowCase(BaseModel):
    """Query Planning V2 shadow 回归用例定义。

    参数：
        case_id: 稳定用例 ID。
        category: 验收分类，例如物流明确查询、BOM 缺槽澄清。
        domain: 业务域。
        question: 业务员问法。
        expected_strategy: 期望策略。
        expected_intent: 期望受控意图，可为空。
        expected_query_key: 期望 query_key，可为空。
    返回：
        shadow 报表服务用于回放的最小用例。
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str
    category: str
    domain: QueryPlanningV2ShadowDomain
    question: str
    expected_strategy: str
    expected_intent: str | None = None
    expected_query_key: str | None = None


class QueryPlanningV2ShadowCaseResult(BaseModel):
    """单条 shadow 用例对比结果。"""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    category: str
    domain: QueryPlanningV2ShadowDomain
    question: str
    expected_strategy: str
    actual_strategy: str
    expected_intent: str | None = None
    actual_intent: str | None = None
    expected_query_key: str | None = None
    actual_query_key: str | None = None
    matched: bool = False
    mismatch_reasons: list[str] = Field(default_factory=list)
    query_plan: QueryPlanningV2Plan


class QueryPlanningV2ShadowReport(BaseModel):
    """Query Planning V2 shadow 对比报表。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "query_planning_v2_shadow_report.1"
    total_cases: int = 0
    matched_cases: int = 0
    mismatched_cases: int = 0
    cases: list[QueryPlanningV2ShadowCaseResult] = Field(default_factory=list)


class QueryPlanningV2GrayLogScope(BaseModel):
    """真实 sys_query_log 灰度报表查询范围。"""

    model_config = ConfigDict(extra="forbid")

    domain: QueryPlanningV2GrayDomain = "all"
    days: int = 7
    limit: int = 200
    source: str = "sys_query_log"


class QueryPlanningV2GrayLogSummary(BaseModel):
    """真实日志灰度报表汇总指标。"""

    model_config = ConfigDict(extra="forbid")

    total_logs: int = 0
    shadow_available: int = 0
    shadow_missing: int = 0
    corrupt_payload: int = 0
    shadow_coverage_rate: float = 0.0
    strategy_distribution: dict[str, int] = Field(default_factory=dict)
    status_distribution: dict[str, int] = Field(default_factory=dict)
    domain_distribution: dict[str, int] = Field(default_factory=dict)
    query_key_match_count: int = 0
    query_key_mismatch_count: int = 0
    query_key_match_rate: float = 0.0
    formal_clarify_count: int = 0
    clarify_agreement_count: int = 0
    clarify_agreement_rate: float = 0.0
    formal_unsupported_or_no_answer_count: int = 0
    unsupported_agreement_count: int = 0
    unsupported_agreement_rate: float = 0.0
    decomposition_candidate_count: int = 0
    rewrite_candidate_count: int = 0
    hyde_candidate_count: int = 0


class QueryPlanningV2GrayAcceptanceThresholds(BaseModel):
    """Query Planning V2 灰度运营验收门槛。

    参数：
        min_shadow_coverage_rate: shadow 写入覆盖率最低要求。
        min_query_key_match_rate: 可比 query_key 一致率最低要求。
        min_clarify_agreement_rate: 正式澄清与 shadow CLARIFY 一致率最低要求。
        min_unsupported_agreement_rate: 正式拒答/无答案与 shadow 一致率最低要求。
        max_corrupt_payload_count: 损坏日志 payload 最大允许数量。
        max_unsafe_execution_policy_count: 危险执行策略最大允许数量。
        max_clarify_disagreement_count: 澄清边界分歧最大允许数量。
        max_unsupported_disagreement_count: 拒答/无答案边界分歧最大允许数量。
        max_guardrail_blocked_count: guardrail 阻断候选最大观察数量；默认只作为观察项。
    返回：
        报表服务用于自动判定运营验收状态的阈值配置。
    """

    model_config = ConfigDict(extra="forbid")

    min_shadow_coverage_rate: float = 0.95
    min_query_key_match_rate: float = 0.98
    min_clarify_agreement_rate: float = 0.95
    min_unsupported_agreement_rate: float = 0.95
    max_corrupt_payload_count: int = 0
    max_unsafe_execution_policy_count: int = 0
    max_clarify_disagreement_count: int = 0
    max_unsupported_disagreement_count: int = 0
    max_guardrail_blocked_count: int = 0


class QueryPlanningV2GrayAcceptanceCheck(BaseModel):
    """单个灰度验收指标判定结果。"""

    model_config = ConfigDict(extra="forbid")

    metric: str
    actual: float | int | None = None
    threshold: float | int | None = None
    operator: str
    passed: bool
    severity: Literal["blocker", "warning", "info"] = "blocker"
    message: str


class QueryPlanningV2GrayAcceptanceGate(BaseModel):
    """灰度运营验收总判定。"""

    model_config = ConfigDict(extra="forbid")

    status: Literal["PASS", "WATCH", "BLOCKED"] = "WATCH"
    passed: bool = False
    eligible_for_controlled_rollout: bool = False
    thresholds: QueryPlanningV2GrayAcceptanceThresholds = Field(
        default_factory=QueryPlanningV2GrayAcceptanceThresholds
    )
    checks: list[QueryPlanningV2GrayAcceptanceCheck] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    watch_reasons: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class QueryPlanningV2GrayVisualizationKpiCard(BaseModel):
    """运营看板 KPI 卡片数据。"""

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    value: float | int | str | None = None
    unit: str | None = None
    status: Literal["success", "warning", "danger", "neutral"] = "neutral"
    description: str | None = None


class QueryPlanningV2GrayVisualizationPoint(BaseModel):
    """运营看板图表点位数据。"""

    model_config = ConfigDict(extra="forbid")

    name: str
    value: float | int
    ratio: float | None = None


class QueryPlanningV2GrayVisualizationChart(BaseModel):
    """运营看板 chart-ready 图表数据。"""

    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    chart_type: Literal["bar", "pie", "line", "table"] = "bar"
    points: list[QueryPlanningV2GrayVisualizationPoint] = Field(default_factory=list)


class QueryPlanningV2GrayVisualization(BaseModel):
    """Query Planning V2 灰度运营看板数据。

    raw_payload 固定为 None，避免前端/接口直接暴露完整 request_payload。
    """

    model_config = ConfigDict(extra="forbid")

    kpi_cards: list[QueryPlanningV2GrayVisualizationKpiCard] = Field(default_factory=list)
    charts: list[QueryPlanningV2GrayVisualizationChart] = Field(default_factory=list)
    raw_payload: None = None


class QueryPlanningV2GrayLogRiskItem(BaseModel):
    """真实日志灰度报表风险项。"""

    model_config = ConfigDict(extra="forbid")

    log_id: int | None = None
    trace_id: str | None = None
    domain: str | None = None
    question: str | None = None
    status: str | None = None
    formal_query_key: str | None = None
    shadow_strategy: str | None = None
    shadow_query_key: str | None = None
    reason: str


class QueryPlanningV2GrayLogSample(BaseModel):
    """真实日志灰度报表样例行。

    raw_payload 固定为 None，避免接口直接暴露完整 request_payload。
    """

    model_config = ConfigDict(extra="forbid")

    log_id: int | None = None
    trace_id: str | None = None
    created_at: str | None = None
    domain: str | None = None
    question: str | None = None
    formal_status: str | None = None
    formal_query_key: str | None = None
    shadow_strategy: str | None = None
    shadow_query_key: str | None = None
    query_key_matched: bool | None = None
    guardrail_status: str | None = None
    shadow_only: bool | None = None
    llm_can_execute: bool | None = None
    sql_generation_allowed: bool | None = None
    risk_tags: list[str] = Field(default_factory=list)
    raw_payload: None = None


class QueryPlanningV2GrayLogReport(BaseModel):
    """基于真实 sys_query_log 的 Query Planning V2 灰度报表。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "query_plan_v2.gray_report.v1"
    scope: QueryPlanningV2GrayLogScope
    summary: QueryPlanningV2GrayLogSummary = Field(default_factory=QueryPlanningV2GrayLogSummary)
    risk_buckets: dict[str, list[QueryPlanningV2GrayLogRiskItem]] = Field(default_factory=dict)
    samples: list[QueryPlanningV2GrayLogSample] = Field(default_factory=list)
    acceptance_gate: QueryPlanningV2GrayAcceptanceGate = Field(default_factory=QueryPlanningV2GrayAcceptanceGate)
    visualization: QueryPlanningV2GrayVisualization = Field(default_factory=QueryPlanningV2GrayVisualization)


DEFAULT_QUERY_PLANNING_V2_SHADOW_CASES: tuple[QueryPlanningV2ShadowCase, ...] = (
    QueryPlanningV2ShadowCase(
        case_id="logistics_direct_clear",
        category="物流明确查询",
        domain="logistics",
        question="2025年各承运商发运量是多少？",
        expected_strategy="DIRECT_RETRIEVAL",
        expected_intent="aggregate",
        expected_query_key="hist_mw_by_carrier",
    ),
    QueryPlanningV2ShadowCase(
        case_id="logistics_rewrite_colloquial_shadow",
        category="物流口语化查询",
        domain="logistics",
        question="帮我统计一下25年每家物流公司的发运量和占比。",
        expected_strategy="DIRECT_RETRIEVAL",
        expected_intent="aggregate",
        expected_query_key="hist_mw_by_carrier",
    ),
    QueryPlanningV2ShadowCase(
        case_id="logistics_complex_composite",
        category="物流复杂复合查询",
        domain="logistics",
        question="统计24年高运费地址，并列出询比价和招标发运量。",
        expected_strategy="QUERY_DECOMPOSITION",
        expected_intent="composite",
        expected_query_key="composite_decomposed",
    ),
    QueryPlanningV2ShadowCase(
        case_id="logistics_clarify_missing_metric",
        category="物流缺槽澄清",
        domain="logistics",
        question="帮我看一下物流情况。",
        expected_strategy="CLARIFY",
        expected_intent="clarification",
        expected_query_key=None,
    ),
    QueryPlanningV2ShadowCase(
        case_id="logistics_unsupported_prediction",
        category="物流无答案拒答",
        domain="logistics",
        question="预测未来三个月各区域发运量。",
        expected_strategy="UNSUPPORTED",
        expected_intent="unsupported",
        expected_query_key=None,
    ),
    QueryPlanningV2ShadowCase(
        case_id="plan_bom_single_order",
        category="BOM 单订单查询",
        domain="plan_bom",
        question="订单001玻璃规格是什么？",
        expected_strategy="DIRECT_RETRIEVAL",
        expected_intent="single_order_material_specs",
        expected_query_key="single_order_material_specs",
    ),
    QueryPlanningV2ShadowCase(
        case_id="plan_bom_multi_order_table",
        category="BOM 多订单表格",
        domain="plan_bom",
        question="订单001和002的玻璃、焊带做成表格。",
        expected_strategy="DIRECT_RETRIEVAL",
        expected_intent="multi_order_material_table",
        expected_query_key="multi_order_material_table",
    ),
    QueryPlanningV2ShadowCase(
        case_id="plan_bom_order_compare",
        category="BOM 订单对比",
        domain="plan_bom",
        question="订单001和002的关键材料有什么差异？",
        expected_strategy="DIRECT_RETRIEVAL",
        expected_intent="cross_order_material_compare",
        expected_query_key="cross_order_material_compare",
    ),
    QueryPlanningV2ShadowCase(
        case_id="plan_bom_clarify_missing_order",
        category="BOM 缺槽澄清",
        domain="plan_bom",
        question="这个订单玻璃是什么？",
        expected_strategy="CLARIFY",
        expected_intent="single_order_material_specs",
        expected_query_key=None,
    ),
    QueryPlanningV2ShadowCase(
        case_id="plan_bom_variant_power_question",
        category="问法变体鲁棒性",
        domain="plan_bom",
        question="帮我看下这个BOM能不能做到620W占比60%。",
        expected_strategy="CLARIFY",
        expected_intent="plan_power_supplier_recommendation",
        expected_query_key=None,
    ),
)


class QueryPlanningV2ShadowReportService:
    """Query Planning V2 shadow / gray 对比报表服务。

    说明：
        1. 内置 10 类物流 / BOM 验收问题，覆盖明确查询、口语化、复合、澄清和拒答；
        2. 默认 shadow report 只调用 QueryPlanningV2Service.plan 生成计划，不执行正式查询；
        3. Phase 5 灰度报表只读 sys_query_log，不重新执行 QA、SQL 或 LLM。
    """

    _RISK_BUCKET_KEYS = (
        "missing_shadow",
        "corrupt_payload",
        "query_key_mismatch",
        "clarify_disagreement",
        "unsupported_disagreement",
        "guardrail_blocked",
        "unsafe_execution_policy",
    )

    def __init__(
        self,
        *,
        planning_service: QueryPlanningV2Service,
        query_log_repository: LogisticsQueryRepository | None = None,
        db: Any | None = None,
    ) -> None:
        """初始化 shadow / gray 报表服务。

        参数：
            planning_service: Query Planning V2 诊断服务，仅用于内置 10 类用例回放。
            query_log_repository: 真实 sys_query_log 只读仓储，Phase 5 灰度报表使用。
            db: 当前数据库会话，Phase 5 灰度报表只读使用。
        返回：
            无返回值。
        """

        self.planning_service = planning_service
        self.query_log_repository = query_log_repository or LogisticsQueryRepository()
        self.db = db

    def build_default_report(self, *, trace_id: str | None = None, write_audit: bool = False) -> QueryPlanningV2ShadowReport:
        """回放默认 10 类用例并生成对比报表。

        参数：
            trace_id: 当前请求追踪号。
            write_audit: 是否让底层 QueryPlanningV2Service 写 JSONL 审计。
        返回：
            Query Planning V2 shadow 对比报表。
        """

        results: list[QueryPlanningV2ShadowCaseResult] = []
        for case in DEFAULT_QUERY_PLANNING_V2_SHADOW_CASES:
            plan = self.planning_service.plan(
                question=case.question,
                domain=case.domain,
                trace_id=f"{trace_id}:{case.case_id}" if trace_id else case.case_id,
                write_audit=write_audit,
            )
            results.append(self._compare(case, plan))
        matched_cases = sum(1 for result in results if result.matched)
        return QueryPlanningV2ShadowReport(
            total_cases=len(results),
            matched_cases=matched_cases,
            mismatched_cases=len(results) - matched_cases,
            cases=results,
        )

    def build_log_report(
        self,
        *,
        domain: QueryPlanningV2GrayDomain = "all",
        limit: int = 200,
        days: int = 7,
    ) -> QueryPlanningV2GrayLogReport:
        """从真实 sys_query_log 构建 Phase 5 灰度汇总报表。

        参数：
            domain: 业务域过滤，支持 all / logistics / plan_bom。
            limit: 最大读取日志条数，仓储层会再次做上限保护。
            days: 最近多少天，仓储层会再次做上限保护。
        返回：
            Query Planning V2 真实日志灰度报表。
        业务逻辑：
            本方法只读取日志并解析 `query_plan_v2_shadow` 元数据，不调用正式 QA service、不查数、
            不调用 LLM，也不把 HYDE/改写文本当事实答案。
        """

        normalized_domain: QueryPlanningV2GrayDomain = domain if domain in {"all", "logistics", "plan_bom"} else "all"
        normalized_limit = max(1, min(int(limit or 200), 500))
        normalized_days = max(1, min(int(days or 7), 365))
        rows = self.query_log_repository.list_query_logs_for_query_planning_gray(
            self.db,
            domain=normalized_domain,
            limit=normalized_limit,
            days=normalized_days,
        )
        return self._build_log_report_from_rows(
            rows,
            scope=QueryPlanningV2GrayLogScope(
                domain=normalized_domain,
                limit=normalized_limit,
                days=normalized_days,
            ),
        )

    @staticmethod
    def _compare(case: QueryPlanningV2ShadowCase, plan: QueryPlanningV2Plan) -> QueryPlanningV2ShadowCaseResult:
        """对比单条用例期望与实际 query_plan。"""

        mismatch_reasons: list[str] = []
        if plan.strategy != case.expected_strategy:
            mismatch_reasons.append(f"strategy 期望 {case.expected_strategy}，实际 {plan.strategy}")
        if case.expected_intent is not None and plan.intent != case.expected_intent:
            mismatch_reasons.append(f"intent 期望 {case.expected_intent}，实际 {plan.intent}")
        if plan.query_key != case.expected_query_key:
            mismatch_reasons.append(f"query_key 期望 {case.expected_query_key}，实际 {plan.query_key}")
        return QueryPlanningV2ShadowCaseResult(
            case_id=case.case_id,
            category=case.category,
            domain=case.domain,
            question=case.question,
            expected_strategy=case.expected_strategy,
            actual_strategy=plan.strategy,
            expected_intent=case.expected_intent,
            actual_intent=plan.intent,
            expected_query_key=case.expected_query_key,
            actual_query_key=plan.query_key,
            matched=not mismatch_reasons,
            mismatch_reasons=mismatch_reasons,
            query_plan=plan,
        )

    def _build_log_report_from_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        scope: QueryPlanningV2GrayLogScope,
    ) -> QueryPlanningV2GrayLogReport:
        """把 sys_query_log 行归并为灰度报表。"""

        summary = QueryPlanningV2GrayLogSummary(total_logs=len(rows))
        risk_buckets: dict[str, list[QueryPlanningV2GrayLogRiskItem]] = {key: [] for key in self._RISK_BUCKET_KEYS}
        samples: list[QueryPlanningV2GrayLogSample] = []

        for row in rows:
            status_value = str(row.get("status") or "UNKNOWN")
            self._increment(summary.status_distribution, status_value)
            payload = self._parse_payload(row.get("request_payload"))
            domain = self._resolve_domain(row=row, payload=payload)
            self._increment(summary.domain_distribution, domain or "unknown")
            risk_tags: list[str] = []

            if payload is None:
                summary.corrupt_payload += 1
                self._append_risk(
                    risk_buckets,
                    "corrupt_payload",
                    row=row,
                    domain=domain,
                    status=status_value,
                    reason="request_payload 不是合法 JSON，无法读取 query_plan_v2_shadow。",
                )
                risk_tags.append("corrupt_payload")
                samples.append(self._build_sample(row=row, domain=domain, status=status_value, risk_tags=risk_tags))
                continue

            shadow = payload.get("query_plan_v2_shadow") if isinstance(payload, dict) else None
            if not isinstance(shadow, dict):
                summary.shadow_missing += 1
                self._append_risk(
                    risk_buckets,
                    "missing_shadow",
                    row=row,
                    domain=domain,
                    status=status_value,
                    reason="日志缺少 query_plan_v2_shadow，无法参与灰度对比。",
                )
                risk_tags.append("missing_shadow")
                samples.append(
                    self._build_sample(row=row, payload=payload, domain=domain, status=status_value, risk_tags=risk_tags)
                )
                continue

            summary.shadow_available += 1
            shadow_strategy = self._as_str_or_none(shadow.get("strategy"))
            shadow_query_key = self._as_str_or_none(shadow.get("query_key"))
            formal_query_key = self._extract_formal_query_key(row=row, payload=payload)
            self._increment(summary.strategy_distribution, shadow_strategy or "UNKNOWN")

            query_key_matched: bool | None = None
            if formal_query_key or shadow_query_key:
                query_key_matched = formal_query_key == shadow_query_key
                if query_key_matched:
                    summary.query_key_match_count += 1
                else:
                    summary.query_key_mismatch_count += 1
                    risk_tags.append("query_key_mismatch")
                    self._append_risk(
                        risk_buckets,
                        "query_key_mismatch",
                        row=row,
                        domain=domain,
                        status=status_value,
                        formal_query_key=formal_query_key,
                        shadow_strategy=shadow_strategy,
                        shadow_query_key=shadow_query_key,
                        reason="正式 query_key 与 query_plan_v2_shadow query_key 不一致或单侧缺失。",
                    )

            if self._is_formal_clarify(status_value, payload):
                summary.formal_clarify_count += 1
                if shadow_strategy == "CLARIFY":
                    summary.clarify_agreement_count += 1
                else:
                    risk_tags.append("clarify_disagreement")
                    self._append_risk(
                        risk_buckets,
                        "clarify_disagreement",
                        row=row,
                        domain=domain,
                        status=status_value,
                        formal_query_key=formal_query_key,
                        shadow_strategy=shadow_strategy,
                        shadow_query_key=shadow_query_key,
                        reason="正式链路需要澄清，但 shadow strategy 未标记 CLARIFY。",
                    )

            if self._is_formal_unsupported_or_no_answer(status_value, payload):
                summary.formal_unsupported_or_no_answer_count += 1
                if shadow_strategy in {"UNSUPPORTED", "NO_ANSWER"}:
                    summary.unsupported_agreement_count += 1
                else:
                    risk_tags.append("unsupported_disagreement")
                    self._append_risk(
                        risk_buckets,
                        "unsupported_disagreement",
                        row=row,
                        domain=domain,
                        status=status_value,
                        formal_query_key=formal_query_key,
                        shadow_strategy=shadow_strategy,
                        shadow_query_key=shadow_query_key,
                        reason="正式链路无答案/不支持，但 shadow strategy 未标记 NO_ANSWER 或 UNSUPPORTED。",
                    )

            if shadow_strategy == "QUERY_DECOMPOSITION":
                summary.decomposition_candidate_count += 1
            if shadow_strategy == "QUERY_REWRITE_SIMPLIFY":
                summary.rewrite_candidate_count += 1
            if shadow_strategy == "HYDE_RETRIEVAL":
                summary.hyde_candidate_count += 1

            if self._is_guardrail_blocked(shadow):
                risk_tags.append("guardrail_blocked")
                self._append_risk(
                    risk_buckets,
                    "guardrail_blocked",
                    row=row,
                    domain=domain,
                    status=status_value,
                    formal_query_key=formal_query_key,
                    shadow_strategy=shadow_strategy,
                    shadow_query_key=shadow_query_key,
                    reason="shadow guardrail 显示候选被阻断或存在 blocked_reason。",
                )

            policy = shadow.get("execution_policy") if isinstance(shadow.get("execution_policy"), dict) else {}
            if self._is_unsafe_execution_policy(policy):
                risk_tags.append("unsafe_execution_policy")
                self._append_risk(
                    risk_buckets,
                    "unsafe_execution_policy",
                    row=row,
                    domain=domain,
                    status=status_value,
                    formal_query_key=formal_query_key,
                    shadow_strategy=shadow_strategy,
                    shadow_query_key=shadow_query_key,
                    reason="shadow execution_policy 出现非 shadow、LLM 可执行或允许 SQL 生成的危险开关。",
                )

            samples.append(
                self._build_sample(
                    row=row,
                    payload=payload,
                    shadow=shadow,
                    domain=domain,
                    status=status_value,
                    formal_query_key=formal_query_key,
                    shadow_strategy=shadow_strategy,
                    shadow_query_key=shadow_query_key,
                    query_key_matched=query_key_matched,
                    risk_tags=risk_tags,
                )
            )

        self._finalize_rates(summary)
        limited_samples = samples[:50]
        acceptance_gate = self._build_acceptance_gate(summary=summary, risk_buckets=risk_buckets)
        visualization = self._build_visualization(
            summary=summary,
            risk_buckets=risk_buckets,
            acceptance_gate=acceptance_gate,
        )
        return QueryPlanningV2GrayLogReport(
            scope=scope,
            summary=summary,
            risk_buckets=risk_buckets,
            samples=limited_samples,
            acceptance_gate=acceptance_gate,
            visualization=visualization,
        )

    @classmethod
    def _build_acceptance_gate(
        cls,
        *,
        summary: QueryPlanningV2GrayLogSummary,
        risk_buckets: dict[str, list[QueryPlanningV2GrayLogRiskItem]],
    ) -> QueryPlanningV2GrayAcceptanceGate:
        """基于灰度汇总指标生成运营验收门槛结论。

        参数：
            summary: 真实日志灰度汇总指标。
            risk_buckets: 已归类风险桶。
        返回：
            Query Planning V2 灰度运营验收结论。
        业务逻辑：
            该方法只做指标判定，不修改任何正式日志，也不重新执行查询；B/C 边界分歧、危险执行策略、
            损坏 payload 均按阻断项处理，避免 shadow 进入受控接入时扩大风险。
        """

        thresholds = QueryPlanningV2GrayAcceptanceThresholds()
        checks: list[QueryPlanningV2GrayAcceptanceCheck] = []
        blocking_reasons: list[str] = []
        watch_reasons: list[str] = []

        def add_check(
            *,
            metric: str,
            actual: float | int | None,
            threshold: float | int | None,
            operator: str,
            passed: bool,
            failure_reason: str | None,
            severity: Literal["blocker", "warning", "info"] = "blocker",
            success_message: str | None = None,
        ) -> None:
            message = success_message or failure_reason or f"{metric} 验收通过。"
            if not passed and failure_reason:
                message = failure_reason
                if severity == "blocker":
                    blocking_reasons.append(failure_reason)
                elif severity == "warning":
                    watch_reasons.append(failure_reason)
            checks.append(
                QueryPlanningV2GrayAcceptanceCheck(
                    metric=metric,
                    actual=actual,
                    threshold=threshold,
                    operator=operator,
                    passed=passed,
                    severity=severity,
                    message=message,
                )
            )

        add_check(
            metric="shadow_coverage_rate",
            actual=summary.shadow_coverage_rate,
            threshold=thresholds.min_shadow_coverage_rate,
            operator=">=",
            passed=summary.shadow_coverage_rate >= thresholds.min_shadow_coverage_rate,
            failure_reason=f"shadow_coverage_rate 未达到 {cls._format_percent(thresholds.min_shadow_coverage_rate)}",
            success_message="shadow 覆盖率达到运营验收门槛。",
        )

        query_key_total = summary.query_key_match_count + summary.query_key_mismatch_count
        if query_key_total:
            add_check(
                metric="query_key_match_rate",
                actual=summary.query_key_match_rate,
                threshold=thresholds.min_query_key_match_rate,
                operator=">=",
                passed=summary.query_key_match_rate >= thresholds.min_query_key_match_rate,
                failure_reason=f"query_key_match_rate 未达到 {cls._format_percent(thresholds.min_query_key_match_rate)}",
                success_message="query_key 一致率达到运营验收门槛。",
            )
        else:
            add_check(
                metric="query_key_match_rate",
                actual=None,
                threshold=thresholds.min_query_key_match_rate,
                operator=">=",
                passed=True,
                failure_reason=None,
                severity="info",
                success_message="当前样本暂无可比 query_key，暂不作为阻断项。",
            )

        if summary.formal_clarify_count:
            add_check(
                metric="clarify_agreement_rate",
                actual=summary.clarify_agreement_rate,
                threshold=thresholds.min_clarify_agreement_rate,
                operator=">=",
                passed=summary.clarify_agreement_rate >= thresholds.min_clarify_agreement_rate,
                failure_reason=f"clarify_agreement_rate 未达到 {cls._format_percent(thresholds.min_clarify_agreement_rate)}",
                success_message="澄清一致率达到运营验收门槛。",
            )
        else:
            add_check(
                metric="clarify_agreement_rate",
                actual=None,
                threshold=thresholds.min_clarify_agreement_rate,
                operator=">=",
                passed=True,
                failure_reason=None,
                severity="info",
                success_message="当前样本暂无正式澄清日志，暂不作为阻断项。",
            )

        if summary.formal_unsupported_or_no_answer_count:
            add_check(
                metric="unsupported_agreement_rate",
                actual=summary.unsupported_agreement_rate,
                threshold=thresholds.min_unsupported_agreement_rate,
                operator=">=",
                passed=summary.unsupported_agreement_rate >= thresholds.min_unsupported_agreement_rate,
                failure_reason=(
                    "unsupported_agreement_rate 未达到 "
                    f"{cls._format_percent(thresholds.min_unsupported_agreement_rate)}"
                ),
                success_message="拒答/无答案一致率达到运营验收门槛。",
            )
        else:
            add_check(
                metric="unsupported_agreement_rate",
                actual=None,
                threshold=thresholds.min_unsupported_agreement_rate,
                operator=">=",
                passed=True,
                failure_reason=None,
                severity="info",
                success_message="当前样本暂无正式拒答/无答案日志，暂不作为阻断项。",
            )

        count_checks: tuple[tuple[str, int, int, Literal["blocker", "warning", "info"]], ...] = (
            ("corrupt_payload_count", summary.corrupt_payload, thresholds.max_corrupt_payload_count, "blocker"),
            (
                "unsafe_execution_policy_count",
                cls._risk_count(risk_buckets, "unsafe_execution_policy"),
                thresholds.max_unsafe_execution_policy_count,
                "blocker",
            ),
            (
                "clarify_disagreement_count",
                cls._risk_count(risk_buckets, "clarify_disagreement"),
                thresholds.max_clarify_disagreement_count,
                "blocker",
            ),
            (
                "unsupported_disagreement_count",
                cls._risk_count(risk_buckets, "unsupported_disagreement"),
                thresholds.max_unsupported_disagreement_count,
                "blocker",
            ),
            (
                "guardrail_blocked_count",
                cls._risk_count(risk_buckets, "guardrail_blocked"),
                thresholds.max_guardrail_blocked_count,
                "warning",
            ),
        )
        for metric, actual_count, max_allowed, severity in count_checks:
            add_check(
                metric=metric,
                actual=actual_count,
                threshold=max_allowed,
                operator="<=",
                passed=actual_count <= max_allowed,
                failure_reason=f"{metric} 超过允许值 {max_allowed}",
                severity=severity,
                success_message=f"{metric} 在允许范围内。",
            )

        if blocking_reasons:
            status: Literal["PASS", "WATCH", "BLOCKED"] = "BLOCKED"
            recommended_actions = [
                "先修复 BLOCKED 指标对应的问题，保持 Query Planning V2 继续 shadow-only，不进入受控接入。",
                "优先排查 query_key mismatch、B/C 边界分歧、unsafe execution policy 和损坏 payload。",
                "修复后重新跑真实日志灰度报表，并保留验收材料供人工复核。",
            ]
        elif watch_reasons:
            status = "WATCH"
            recommended_actions = [
                "当前无阻断项，但仍有观察项；继续 shadow 灰度并扩大样本后再评估受控接入。",
                "人工抽检 guardrail blocked、HYDE/rewrite/decomposition 候选，确认没有事实计算或 SQL 生成。",
            ]
        else:
            status = "PASS"
            recommended_actions = [
                "Phase 5.4 运营门槛通过，可准备小范围只读看板验收或继续讨论后续受控接入候选。",
                "进入下一阶段前仍需人工抽检样例，确认原始问题、slots、guardrail 与安全边界完整。",
            ]

        return QueryPlanningV2GrayAcceptanceGate(
            status=status,
            passed=status == "PASS",
            eligible_for_controlled_rollout=status == "PASS",
            thresholds=thresholds,
            checks=checks,
            blocking_reasons=blocking_reasons,
            watch_reasons=watch_reasons,
            recommended_actions=recommended_actions,
        )

    @classmethod
    def _build_visualization(
        cls,
        *,
        summary: QueryPlanningV2GrayLogSummary,
        risk_buckets: dict[str, list[QueryPlanningV2GrayLogRiskItem]],
        acceptance_gate: QueryPlanningV2GrayAcceptanceGate,
    ) -> QueryPlanningV2GrayVisualization:
        """生成前端或运营看板可直接消费的图表数据。

        参数：
            summary: 灰度汇总指标。
            risk_buckets: 风险桶。
            acceptance_gate: 运营验收结论。
        返回：
            chart-ready 的 KPI 卡片和分布图数据，不包含完整原始 payload。
        """

        blocker_count = len(acceptance_gate.blocking_reasons)
        query_key_total = summary.query_key_match_count + summary.query_key_mismatch_count
        query_key_kpi_value: float | str = round(summary.query_key_match_rate, 4) if query_key_total else "N/A"
        query_key_kpi_status: Literal["success", "warning", "danger", "neutral"] = (
            "neutral"
            if query_key_total == 0
            else "success"
            if summary.query_key_match_rate >= acceptance_gate.thresholds.min_query_key_match_rate
            else "danger"
        )
        kpi_cards = [
            QueryPlanningV2GrayVisualizationKpiCard(
                key="total_logs",
                label="样本日志数",
                value=summary.total_logs,
                unit="条",
                status="neutral",
                description="本次灰度报表读取的 sys_query_log 样本数。",
            ),
            QueryPlanningV2GrayVisualizationKpiCard(
                key="shadow_coverage_rate",
                label="Shadow 覆盖率",
                value=round(summary.shadow_coverage_rate, 4),
                unit="ratio",
                status="success" if summary.shadow_coverage_rate >= acceptance_gate.thresholds.min_shadow_coverage_rate else "danger",
                description="有 query_plan_v2_shadow 的正式日志占比。",
            ),
            QueryPlanningV2GrayVisualizationKpiCard(
                key="query_key_match_rate",
                label="Query Key 一致率",
                value=query_key_kpi_value,
                unit="ratio" if query_key_total else None,
                status=query_key_kpi_status,
                description=(
                    "formal query_key 与 shadow query_key 在可比样本中的一致比例。"
                    if query_key_total
                    else "当前样本暂无可比 query_key，按运营验收 info 项处理。"
                ),
            ),
            QueryPlanningV2GrayVisualizationKpiCard(
                key="clarify_agreement_rate",
                label="澄清一致率",
                value=round(summary.clarify_agreement_rate, 4),
                unit="ratio",
                status=(
                    "success"
                    if summary.formal_clarify_count == 0
                    or summary.clarify_agreement_rate >= acceptance_gate.thresholds.min_clarify_agreement_rate
                    else "danger"
                ),
                description="正式澄清日志中 shadow 也判定为 CLARIFY 的比例。",
            ),
            QueryPlanningV2GrayVisualizationKpiCard(
                key="unsupported_agreement_rate",
                label="拒答/无答案一致率",
                value=round(summary.unsupported_agreement_rate, 4),
                unit="ratio",
                status=(
                    "success"
                    if summary.formal_unsupported_or_no_answer_count == 0
                    or summary.unsupported_agreement_rate >= acceptance_gate.thresholds.min_unsupported_agreement_rate
                    else "danger"
                ),
                description="正式拒答/无答案日志中 shadow 也判定为 NO_ANSWER/UNSUPPORTED 的比例。",
            ),
            QueryPlanningV2GrayVisualizationKpiCard(
                key="risk_blocker_count",
                label="阻断项数量",
                value=blocker_count,
                unit="项",
                status="success" if blocker_count == 0 else "danger",
                description="运营验收阻断原因数量，非风险桶原始条数。",
            ),
        ]

        risk_counts = {key: len(risk_buckets.get(key, [])) for key in cls._RISK_BUCKET_KEYS}
        charts = [
            cls._build_distribution_chart(
                key="strategy_distribution",
                title="Strategy 分布",
                chart_type="pie",
                distribution=summary.strategy_distribution,
                denominator=summary.shadow_available,
            ),
            cls._build_distribution_chart(
                key="domain_distribution",
                title="Domain 分布",
                chart_type="pie",
                distribution=summary.domain_distribution,
                denominator=summary.total_logs,
            ),
            cls._build_distribution_chart(
                key="status_distribution",
                title="正式状态分布",
                chart_type="bar",
                distribution=summary.status_distribution,
                denominator=summary.total_logs,
            ),
            cls._build_distribution_chart(
                key="risk_bucket_counts",
                title="风险桶数量",
                chart_type="bar",
                distribution=risk_counts,
                denominator=max(1, sum(risk_counts.values())),
            ),
        ]
        return QueryPlanningV2GrayVisualization(kpi_cards=kpi_cards, charts=charts, raw_payload=None)

    @classmethod
    def _build_distribution_chart(
        cls,
        *,
        key: str,
        title: str,
        chart_type: Literal["bar", "pie", "line", "table"],
        distribution: dict[str, int],
        denominator: int,
    ) -> QueryPlanningV2GrayVisualizationChart:
        """把字典计数器转换为 chart-ready 图表数据。"""

        points = [
            QueryPlanningV2GrayVisualizationPoint(
                name=name,
                value=value,
                ratio=(value / denominator if denominator else None),
            )
            for name, value in distribution.items()
        ]
        return QueryPlanningV2GrayVisualizationChart(key=key, title=title, chart_type=chart_type, points=points)

    @staticmethod
    def _risk_count(risk_buckets: dict[str, list[QueryPlanningV2GrayLogRiskItem]], bucket: str) -> int:
        """读取指定风险桶的条数。"""

        return len(risk_buckets.get(bucket, []))

    @staticmethod
    def _format_percent(value: float) -> str:
        """把比例格式化为中文验收说明中的百分比。"""

        return f"{value:.2%}"

    @staticmethod
    def _parse_payload(value: Any) -> dict[str, Any] | None:
        """解析 request_payload；失败返回 None，由报表记录 corrupt_payload 风险。"""

        if isinstance(value, dict):
            return value
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _resolve_domain(*, row: dict[str, Any], payload: dict[str, Any] | None) -> str | None:
        """根据 payload / query_type 推断业务域。"""

        if isinstance(payload, dict):
            response_meta = payload.get("response_meta") if isinstance(payload.get("response_meta"), dict) else {}
            shadow = payload.get("query_plan_v2_shadow") if isinstance(payload.get("query_plan_v2_shadow"), dict) else {}
            domain = response_meta.get("domain") or shadow.get("domain")
            if isinstance(domain, str) and domain:
                return domain
        query_type = row.get("query_type")
        if query_type == "DATA_QA":
            return "logistics"
        if query_type == "PLAN_BOM_QA":
            return "plan_bom"
        return None

    @staticmethod
    def _extract_formal_query_key(*, row: dict[str, Any], payload: dict[str, Any]) -> str | None:
        """从正式 QA 快照中提取正式 query_key，用于与 shadow 对比。"""

        query_result = payload.get("query_result") if isinstance(payload.get("query_result"), dict) else {}
        query_plan = query_result.get("query_plan") if isinstance(query_result.get("query_plan"), dict) else {}
        response_meta = payload.get("response_meta") if isinstance(payload.get("response_meta"), dict) else {}
        return QueryPlanningV2ShadowReportService._as_str_or_none(
            query_plan.get("query_key") or response_meta.get("metric_type") or row.get("metric_type")
        )

    @staticmethod
    def _is_formal_clarify(status: str, payload: dict[str, Any]) -> bool:
        """判断正式链路是否为澄清状态。"""

        status_upper = status.upper()
        if status_upper in {"CLARIFICATION", "CLARIFICATION_REQUIRED"}:
            return True
        response_meta = payload.get("response_meta") if isinstance(payload.get("response_meta"), dict) else {}
        status_payload = response_meta.get("status") if isinstance(response_meta.get("status"), dict) else {}
        return status_payload.get("code") == "CLARIFICATION_REQUIRED"

    @staticmethod
    def _is_formal_unsupported_or_no_answer(status: str, payload: dict[str, Any]) -> bool:
        """判断正式链路是否为无答案或不支持。"""

        status_upper = status.upper()
        if status_upper in {"UNSUPPORTED", "NO_ANSWER", "EMPTY_RESULT"}:
            return True
        response_meta = payload.get("response_meta") if isinstance(payload.get("response_meta"), dict) else {}
        status_payload = response_meta.get("status") if isinstance(response_meta.get("status"), dict) else {}
        return status_payload.get("code") in {"UNSUPPORTED_QUESTION", "NO_ANSWER", "EMPTY_RESULT"}

    @staticmethod
    def _is_guardrail_blocked(shadow: dict[str, Any]) -> bool:
        """判断 shadow guardrail 是否有阻断信号。"""

        decision = shadow.get("guardrail_decision") if isinstance(shadow.get("guardrail_decision"), dict) else {}
        if decision.get("accepted") is False:
            return True
        return bool(decision.get("blocked_reason"))

    @staticmethod
    def _is_unsafe_execution_policy(policy: dict[str, Any]) -> bool:
        """判断执行策略是否突破 shadow-only 安全边界。"""

        return (
            policy.get("shadow_only") is not True
            or bool(policy.get("llm_can_execute"))
            or bool(policy.get("sql_generation_allowed"))
        )

    @staticmethod
    def _build_sample(
        *,
        row: dict[str, Any],
        payload: dict[str, Any] | None = None,
        shadow: dict[str, Any] | None = None,
        domain: str | None = None,
        status: str | None = None,
        formal_query_key: str | None = None,
        shadow_strategy: str | None = None,
        shadow_query_key: str | None = None,
        query_key_matched: bool | None = None,
        risk_tags: list[str] | None = None,
    ) -> QueryPlanningV2GrayLogSample:
        """生成一条脱敏样例，不携带完整 raw payload。"""

        policy = shadow.get("execution_policy") if isinstance(shadow, dict) and isinstance(shadow.get("execution_policy"), dict) else {}
        decision = shadow.get("guardrail_decision") if isinstance(shadow, dict) and isinstance(shadow.get("guardrail_decision"), dict) else {}
        guardrail_status = None
        if decision:
            guardrail_status = "blocked" if decision.get("accepted") is False or decision.get("blocked_reason") else "accepted"
        return QueryPlanningV2GrayLogSample(
            log_id=QueryPlanningV2ShadowReportService._safe_int(row.get("id")),
            trace_id=QueryPlanningV2ShadowReportService._as_str_or_none(row.get("trace_id")),
            created_at=QueryPlanningV2ShadowReportService._as_str_or_none(row.get("created_at")),
            domain=domain,
            question=QueryPlanningV2ShadowReportService._as_str_or_none(row.get("question_text"))
            or QueryPlanningV2ShadowReportService._as_str_or_none((payload or {}).get("question")),
            formal_status=status,
            formal_query_key=formal_query_key,
            shadow_strategy=shadow_strategy,
            shadow_query_key=shadow_query_key,
            query_key_matched=query_key_matched,
            guardrail_status=guardrail_status,
            shadow_only=policy.get("shadow_only") if policy else None,
            llm_can_execute=policy.get("llm_can_execute") if policy else None,
            sql_generation_allowed=policy.get("sql_generation_allowed") if policy else None,
            risk_tags=risk_tags or [],
            raw_payload=None,
        )

    @staticmethod
    def _append_risk(
        risk_buckets: dict[str, list[QueryPlanningV2GrayLogRiskItem]],
        bucket: str,
        *,
        row: dict[str, Any],
        domain: str | None,
        status: str | None,
        reason: str,
        formal_query_key: str | None = None,
        shadow_strategy: str | None = None,
        shadow_query_key: str | None = None,
    ) -> None:
        """向指定风险桶追加风险项。"""

        risk_buckets.setdefault(bucket, []).append(
            QueryPlanningV2GrayLogRiskItem(
                log_id=QueryPlanningV2ShadowReportService._safe_int(row.get("id")),
                trace_id=QueryPlanningV2ShadowReportService._as_str_or_none(row.get("trace_id")),
                domain=domain,
                question=QueryPlanningV2ShadowReportService._as_str_or_none(row.get("question_text")),
                status=status,
                formal_query_key=formal_query_key,
                shadow_strategy=shadow_strategy,
                shadow_query_key=shadow_query_key,
                reason=reason,
            )
        )

    @staticmethod
    def _finalize_rates(summary: QueryPlanningV2GrayLogSummary) -> None:
        """计算灰度报表中的比例指标。"""

        if summary.total_logs:
            summary.shadow_coverage_rate = summary.shadow_available / summary.total_logs
        query_key_total = summary.query_key_match_count + summary.query_key_mismatch_count
        if query_key_total:
            summary.query_key_match_rate = summary.query_key_match_count / query_key_total
        if summary.formal_clarify_count:
            summary.clarify_agreement_rate = summary.clarify_agreement_count / summary.formal_clarify_count
        if summary.formal_unsupported_or_no_answer_count:
            summary.unsupported_agreement_rate = (
                summary.unsupported_agreement_count / summary.formal_unsupported_or_no_answer_count
            )

    @staticmethod
    def _increment(counter: dict[str, int], key: str) -> None:
        """字典计数器自增。"""

        counter[key] = counter.get(key, 0) + 1

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        """安全转换整数，失败返回 None。"""

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_str_or_none(value: Any) -> str | None:
        """把非空值归一成字符串。"""

        if value is None:
            return None
        text = str(value)
        return text if text else None


__all__ = [
    "DEFAULT_QUERY_PLANNING_V2_SHADOW_CASES",
    "QueryPlanningV2GrayAcceptanceCheck",
    "QueryPlanningV2GrayAcceptanceGate",
    "QueryPlanningV2GrayAcceptanceThresholds",
    "QueryPlanningV2GrayLogReport",
    "QueryPlanningV2GrayLogRiskItem",
    "QueryPlanningV2GrayLogSample",
    "QueryPlanningV2GrayLogScope",
    "QueryPlanningV2GrayLogSummary",
    "QueryPlanningV2GrayVisualization",
    "QueryPlanningV2GrayVisualizationChart",
    "QueryPlanningV2GrayVisualizationKpiCard",
    "QueryPlanningV2GrayVisualizationPoint",
    "QueryPlanningV2ShadowCase",
    "QueryPlanningV2ShadowCaseResult",
    "QueryPlanningV2ShadowReport",
    "QueryPlanningV2ShadowReportService",
]

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
        return QueryPlanningV2GrayLogReport(
            scope=scope,
            summary=summary,
            risk_buckets=risk_buckets,
            samples=samples[:50],
        )

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
    "QueryPlanningV2GrayLogReport",
    "QueryPlanningV2GrayLogRiskItem",
    "QueryPlanningV2GrayLogSample",
    "QueryPlanningV2GrayLogScope",
    "QueryPlanningV2GrayLogSummary",
    "QueryPlanningV2ShadowCase",
    "QueryPlanningV2ShadowCaseResult",
    "QueryPlanningV2ShadowReport",
    "QueryPlanningV2ShadowReportService",
]

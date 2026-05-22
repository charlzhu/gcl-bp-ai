from __future__ import annotations

import json
import re
import time
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal, TypeGuard
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.config import settings
from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import (
    LogisticsCatalogRecallResult,
    LogisticsCatalogRecallService,
    _build_provider_openai_client_kwargs,
)
from backend.app.domains.logistics.services.nl2sql.evaluation_log import redact_evaluation_text
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalog, LogisticsSemanticCatalogLoader
from backend.app.domains.logistics.services.nl2sql.shadow_pipeline import (
    LogisticsNl2SqlShadowPipeline,
    LogisticsNl2SqlShadowPipelineRequest,
)
from backend.app.domains.logistics.services.nl2sql.sql_plan import (
    DEFAULT_LOGISTICS_YEARS,
    LogisticsSqlPlanCandidate,
    LogisticsSqlPlanValidationResult,
    LogisticsSqlPlanValidator,
)

M9_SHADOW_SQLPLAN_GENERATION_VERSION = "logistics_nl2sql_m9_shadow_sqlplan_generation.v1"
DEFAULT_M9_RECORDS_FILENAME = "m9-shadow-sqlplan-generation-records.jsonl"
DEFAULT_M9_REPORT_FILENAME = "m9-shadow-sqlplan-generation-report.md"

_SQLPLAN_FORBIDDEN_LLM_FIELDS = {
    "sql",
    "raw_sql",
    "where",
    "where_clause",
    "having",
    "free_sql",
    "answer",
    "computed_value",
    "python_code",
    "tool_call",
    "database",
    "table_name",
}
SQLPLAN_CANDIDATE_ALLOWED_TOP_LEVEL_KEYS = [
    "schema_version",
    "domain",
    "strategy",
    "catalog_version",
    "catalog_refs",
    "plan",
    "clarification_questions",
    "unsupported_reason",
    "confidence",
]
SQLPLAN_PLAN_ALLOWED_KEYS = [
    "query_type",
    "domain",
    "tables",
    "joins",
    "metrics",
    "dimensions",
    "filters",
    "group_by",
    "order_by",
    "business_rules",
    "explicit_year_buckets",
    "requested_unit",
    "limit",
]
SQLPLAN_FILTER_ALLOWED_KEYS = ["dimension", "operator", "values", "source"]
SQLPLAN_ORDER_BY_ALLOWED_KEYS = ["metric", "dimension", "direction"]
SQLPLAN_FORBIDDEN_MISPLACED_KEYS = [
    "plan_filters",
    "plan.confidence",
    "_business_rules",
    "_explicit_year_buckets",
    "_requested_unit",
    "_limit",
    "_plan_filters",
    "sql_plan",
    "query_plan",
    "candidate",
]
SQLPLAN_SAFE_TOP_LEVEL_KEY_ALIASES = {
    "catalog refs": "catalog_refs",
    "catalogRefs": "catalog_refs",
    "catalog references": "catalog_refs",
    "unsupportedReason": "unsupported_reason",
    "unsupported reason": "unsupported_reason",
    "unsupported_reasonalityReason": "unsupported_reason",
}
_TONNAGE_RE = re.compile(r"吨数|运输吨位|吨位|(?<!千)吨(?!位)")
_YEAR_RE = re.compile(r"(?:20)?2[0-9]{3}|\b2[3-6]\s*年")


class LogisticsNl2SqlQueryRewriteResult(BaseModel):
    """M9 Query Rewrite 的受控输出。"""

    model_config = ConfigDict(extra="forbid")

    original_question: str
    normalized_question: str
    default_years: list[int] = Field(default_factory=list)
    normalized_terms: dict[str, str] = Field(default_factory=dict)
    removed_constraints: list[str] = Field(default_factory=list)
    unsupported_flags: list[str] = Field(default_factory=list)
    requested_unit: str | None = None


class LogisticsNl2SqlQueryRewriteService:
    """物流 NL2SQL M9 查询改写：只做轻量归一，不删除用户约束。"""

    TERM_MAP = {
        "发货量": "发运量",
        "运输量": "发运量",
        "物流量": "发运量",
        "出货量": "发运量",
        "物流公司": "承运商",
        "物流供应商": "承运商",
    }

    def rewrite(self, question: str) -> LogisticsNl2SqlQueryRewriteResult:
        original = str(question or "").strip()
        normalized = original
        normalized_terms: dict[str, str] = {}
        for source, target in self.TERM_MAP.items():
            if source in normalized:
                normalized = normalized.replace(source, target)
                normalized_terms[source] = target

        default_years = [] if _has_explicit_year(normalized) else list(DEFAULT_LOGISTICS_YEARS)
        unsupported_flags: list[str] = []
        requested_unit = "MW" if any(token in normalized for token in ("发运量", "MW", "mw", "瓦数", "件数")) else None
        if _TONNAGE_RE.search(original):
            unsupported_flags.append("unsupported_tonnage")
            requested_unit = "吨"

        return LogisticsNl2SqlQueryRewriteResult(
            original_question=original,
            normalized_question=normalized,
            default_years=default_years,
            normalized_terms=normalized_terms,
            removed_constraints=[],
            unsupported_flags=unsupported_flags,
            requested_unit=requested_unit,
        )


from backend.app.domains.logistics.services.nl2sql.domain_router import (
    Nl2SqlDomainRoute,
    Nl2SqlDomainRouter,
)


class LogisticsNl2SqlDomainRoute(Nl2SqlDomainRoute):
    """M9 domain router 结果（别名兼容，继承自 Nl2SqlDomainRoute）。"""



class LogisticsNl2SqlDomainRouter(Nl2SqlDomainRouter):
    """M9 领域路由：只允许物流中间库 shadow。

    继承自 Nl2SqlDomainRouter，保留现有关键词和路由判断逻辑不变。
    当 registry 注册了新域（如 business_analysis / plan_bom）后，
    将逐步放开 should_process=False 的限制。
    """

    # 物管/物控域关键词：M9 第一阶段只做物流，遇到库存/出入库等物管问题必须 fail-closed，不能误送物流 NL2SQL。
    MATERIAL_MANAGEMENT_TOKENS = ("物管", "物控", "物料", "库存", "出入库", "入库", "出库", "仓库", "库龄")
    # 经营分析域关键词：避免收入/利润/预算达成率等经营分析问题被物流 shadow 误处理。
    BUSINESS_ANALYSIS_TOKENS = ("经营分析", "收入", "利润", "毛利", "预算达成率", "产销存", "销售量", "销量")

    def route(self, question: str | LogisticsNl2SqlQueryRewriteResult) -> LogisticsNl2SqlDomainRoute:
        text = question.normalized_question if isinstance(question, LogisticsNl2SqlQueryRewriteResult) else str(question or "")
        lowered = text.lower()
        if any(token in lowered for token in ("sap", "oracle", "mid")) or any(token in text for token in ("源表", "直查")):
            return LogisticsNl2SqlDomainRoute(
                should_process=False,
                domain="logistics",
                source_system="sap_oracle_mid",
                reason_code="m9_source_not_allowed::sap_oracle_mid",
            )
        if any(token in text for token in self.MATERIAL_MANAGEMENT_TOKENS):
            return LogisticsNl2SqlDomainRoute(
                should_process=False,
                domain="material_management",
                source_system="middle_db",
                reason_code="m9_domain_not_supported::material_management",
            )
        if any(token in text for token in self.BUSINESS_ANALYSIS_TOKENS):
            return LogisticsNl2SqlDomainRoute(
                should_process=True,
                domain="business_analysis",
                source_system="middle_db",
                mode="shadow",
                reason_code=None,
            )
        # 先检查 registry 中的已注册域（Nl2SqlDomainRouter 基类逻辑）
        # plan_bom / business_analysis 已注册到 registry，由基类自动识别
        registry_result = super().route(text)
        if registry_result.should_process:
            # registry 识别出域（物流/产销存/计划BOM）时，传递域但不保留 reason_code，
            # 保持 LogisticsNl2SqlDomainRouter 原有的 reason_code=None 语义
            return LogisticsNl2SqlDomainRoute(
                should_process=True,
                domain=registry_result.domain,
                source_system="middle_db",
                mode="shadow",
                reason_code=None,
            )
        return LogisticsNl2SqlDomainRoute(should_process=True, domain="logistics", source_system="middle_db", mode="shadow")


class LogisticsSqlPlanGenerationResult(BaseModel):
    """M9 LLM SQLPlan Generator 的受控结果。"""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    status: Literal["ok", "disabled", "route_skipped", "recall_failed", "validation_failed", "error"]
    candidate: dict[str, Any] | None = None
    validation_result: LogisticsSqlPlanValidationResult | None = None
    error_codes: list[str] = Field(default_factory=list)
    error_message: str | None = None
    llm_model_name: str | None = None


class LogisticsSqlPlanGenerator:
    """使用当前项目主 LLM 生成受控 SQLPlan candidate，并立即走 SQLPlan validator。"""

    def __init__(
        self,
        *,
        enabled: bool = True,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        client: Any | None = None,
        catalog: LogisticsSemanticCatalog | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.enabled = enabled
        self.base_url = settings.llm_base_url if base_url is None else base_url
        self.api_key = settings.llm_api_key if api_key is None else api_key
        self.model = settings.llm_model if model is None else model
        self._client = client
        self.catalog = catalog or LogisticsSemanticCatalogLoader().load()
        self.validator = LogisticsSqlPlanValidator(catalog=self.catalog)
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        return bool(self.enabled and (self._client or (self.base_url and self.api_key and self.model)))

    def generate(
        self,
        *,
        original_question: str,
        normalized_question: str,
        route: LogisticsNl2SqlDomainRoute,
        recall_result: LogisticsCatalogRecallResult,
    ) -> LogisticsSqlPlanGenerationResult:
        """生成 SQLPlan candidate；任一前置条件不满足都 fail-closed。"""

        if not route.should_process:
            return LogisticsSqlPlanGenerationResult(status="route_skipped", error_codes=[route.reason_code or "m9_route_skipped"])
        if recall_result.status != "ok" or not recall_result.hits:
            return LogisticsSqlPlanGenerationResult(
                status="recall_failed",
                error_codes=[f"m9_recall_not_ok::{recall_result.status}", *( [recall_result.error] if recall_result.error else [] )],
            )
        if not self.is_available():
            return LogisticsSqlPlanGenerationResult(status="disabled", error_codes=["m9_llm_not_configured"])

        try:
            client = self._client or self._build_openai_client()
            messages = self._build_messages(
                original_question=original_question,
                normalized_question=normalized_question,
                route=route,
                recall_result=recall_result,
            )
            completion = client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=messages,
                response_format={"type": "json_object"},
            )
            content = completion.choices[0].message.content or "{}"
            candidate = self._parse_candidate_text(content)
            if isinstance(candidate, LogisticsSqlPlanGenerationResult):
                return candidate
            candidate = self._normalize_candidate_for_validation(
                candidate,
                original_question=original_question,
                normalized_question=normalized_question,
                recall_result=recall_result,
            )
            validation_result = self.validator.validate(candidate)
            if not validation_result.ok:
                return LogisticsSqlPlanGenerationResult(
                    status="validation_failed",
                    candidate=None,
                    validation_result=validation_result,
                    error_codes=validation_result.error_codes,
                    llm_model_name=self.model or None,
                )
            return LogisticsSqlPlanGenerationResult(
                status="ok",
                candidate=candidate,
                validation_result=validation_result,
                error_codes=[],
                llm_model_name=self.model or None,
            )
        except Exception as exc:  # noqa: BLE001 - LLM 边界错误必须转为受控状态
            return LogisticsSqlPlanGenerationResult(
                status="error",
                error_codes=["m9_llm_generation_error"],
                error_message=redact_evaluation_text(str(exc)),
                llm_model_name=self.model or None,
            )

    def _normalize_candidate_for_validation(
        self,
        candidate: dict[str, Any],
        *,
        original_question: str,
        normalized_question: str,
        recall_result: LogisticsCatalogRecallResult,
    ) -> dict[str, Any]:
        """在 validator 前做安全、可审计的 provider 输出规范化。

        参数：
            candidate: LLM 返回且已通过严格 JSON/禁用字段扫描的候选对象。
            original_question: 用户原始问题，用于判断是否可补默认时间规则。
            normalized_question: Query Rewrite 后问题，用于判断显式年份。
            recall_result: 本次召回命中；所有补全 catalog_ref 必须来自召回命中或其 canonical 依赖。
        返回：
            规范化后的 candidate。未知 catalog_id、未召回且未声明依赖的指标、任意 raw SQL 仍由 validator fail-closed。
        """

        normalized = deepcopy(candidate)
        if not isinstance(normalized, dict):
            return candidate

        normalized = _normalize_safe_provider_top_level_aliases(normalized)
        catalog_version = self.catalog.catalog_version
        normalized["catalog_version"] = catalog_version
        plan = normalized.get("plan")
        if not isinstance(plan, dict):
            return normalized

        recalled_ids = {hit.document.catalog_id for hit in recall_result.hits}
        available_catalog_ids = self._expand_recalled_catalog_dependencies(recalled_ids)

        # 业务逻辑：LLM 常把空业务规则解释成字符串（如 businesses: []）。仅清理这种空占位；真实未知规则保留给 validator 拦截。
        cleaned_rules: list[Any] = []
        for rule in plan.get("business_rules") or []:
            if not isinstance(rule, str):
                cleaned_rules.append(rule)
                continue
            rule_text = rule.strip()
            if _is_empty_rule_placeholder(rule_text):
                continue
            if rule_text == "default_time_range" and _should_drop_default_time_rule_for_explicit_years(
                original_question=original_question,
                normalized_question=normalized_question,
                plan=plan,
            ):
                # 业务逻辑：用户已显式给出 2023-2025 等年份时，provider 可能从默认时间示例误抄 default_time_range。
                # 只有在年份过滤与 explicit_year_buckets 完全一致、且不是默认 2023-2026 时才移除，避免把真实默认时间查询改错。
                continue
            cleaned_rules.append(rule_text)

        if self._should_apply_default_time_rule(
            original_question=original_question,
            normalized_question=normalized_question,
            plan=plan,
            recalled_ids=available_catalog_ids,
        ):
            if "default_time_range" not in cleaned_rules:
                cleaned_rules.append("default_time_range")
            if not plan.get("explicit_year_buckets"):
                plan["explicit_year_buckets"] = list(DEFAULT_LOGISTICS_YEARS)
        _normalize_explicit_year_buckets_from_filters(plan)
        plan["business_rules"] = cleaned_rules
        self._normalize_single_table_plan_tables(plan)

        refs_by_id: dict[str, dict[str, str]] = {}
        for catalog_id in sorted(recalled_ids):
            if catalog_id in available_catalog_ids:
                refs_by_id[catalog_id] = {"catalog_id": catalog_id, "catalog_version": catalog_version}
        for ref in normalized.get("catalog_refs") or []:
            if not isinstance(ref, dict):
                continue
            catalog_id = str(ref.get("catalog_id") or "").strip()
            if catalog_id in available_catalog_ids:
                refs_by_id[catalog_id] = {"catalog_id": catalog_id, "catalog_version": catalog_version}

        for catalog_id in self._collect_required_catalog_refs_from_plan(plan):
            if catalog_id in available_catalog_ids:
                refs_by_id[catalog_id] = {"catalog_id": catalog_id, "catalog_version": catalog_version}
        normalized["catalog_refs"] = [refs_by_id[catalog_id] for catalog_id in sorted(refs_by_id)]
        return normalized

    def _collect_required_catalog_refs_from_plan(self, plan: dict[str, Any]) -> set[str]:
        """从 plan 中提取 validator 后续一定会要求的 catalog_ref。"""

        refs: set[str] = set()
        for table_name in _string_items(plan.get("tables")):
            refs.add(f"table:{table_name}")
        for metric_id in _string_items(plan.get("metrics")):
            refs.add(f"metric:{metric_id}")
        for dimension_id in _string_items(plan.get("dimensions")):
            refs.add(f"dimension:{dimension_id}")
        for dimension_id in _string_items(plan.get("group_by")):
            refs.add(f"dimension:{dimension_id}")
        for rule_id in _string_items(plan.get("business_rules")):
            refs.add(f"rule:{rule_id}")
        for item in plan.get("filters") or []:
            if isinstance(item, dict) and isinstance(item.get("dimension"), str):
                refs.add(f"dimension:{item['dimension']}")
        for item in plan.get("order_by") or []:
            if not isinstance(item, dict):
                continue
            metric_id = item.get("metric")
            dimension_id = item.get("dimension")
            if isinstance(metric_id, str) and metric_id.strip():
                refs.add(f"metric:{metric_id.strip()}")
            if isinstance(dimension_id, str) and dimension_id.strip():
                refs.add(f"dimension:{dimension_id.strip()}")
        return refs

    def _normalize_single_table_plan_tables(self, plan: dict[str, Any]) -> None:
        """在无 join 的单服务表计划中移除 provider 误混入的未引用表。

        参数：
            plan: provider 输出的 plan dict，会被原地安全归一。
        返回：
            无返回值；仅当所有指标/维度引用都能证明落在同一张表时修改 plan.tables。
        业务逻辑：
            live provider 可能因为召回到原始历史明细表，就把它和统一服务表一起写入 tables。
            如果当前 plan 没有 join，且 metrics/dimensions/group_by/filter/order_by 引用的 catalog
            全部指向同一张服务表，则多余表只是召回噪声，可以收敛成单表；否则保持原样交给 validator fail-closed。
        """

        raw_tables = plan.get("tables")
        if not _is_non_empty_string_list(raw_tables):
            # 业务逻辑：tables 形态不标准时不得在 generator 层“修好”，必须保留给 schema/validator fail-closed。
            return
        tables = _dedupe_string_items(raw_tables)
        if len(tables) <= 1:
            return
        if not _is_empty_list_or_none(plan.get("joins")):
            # 业务逻辑：任何非空或非 list 的 joins 都不是“无 join”；不允许在有 join 语义时裁剪表。
            return
        referenced_tables = self._collect_plan_referenced_tables(plan)
        if referenced_tables is None or len(referenced_tables) != 1:
            return
        primary_table = next(iter(referenced_tables))
        if primary_table in set(tables):
            plan["tables"] = [primary_table]

    def _collect_plan_referenced_tables(self, plan: dict[str, Any]) -> set[str] | None:
        """收集 plan 中指标和维度通过 canonical catalog 指向的表。

        参数：
            plan: provider 输出的 plan dict。
        返回：
            表名集合；若存在未知指标/维度则返回 None，表示不能安全裁剪 tables。
        """

        referenced_tables: set[str] = set()
        if not _is_optional_string_list(plan.get("metrics")):
            return None
        if not _is_optional_string_list(plan.get("dimensions")):
            return None
        if not _is_optional_string_list(plan.get("group_by")):
            return None
        metric_ids = _dedupe_string_items(plan.get("metrics"))
        dimension_ids = _dedupe_string_items(plan.get("dimensions")) + _dedupe_string_items(plan.get("group_by"))

        raw_filters = plan.get("filters")
        if raw_filters is None:
            raw_filters = []
        elif not isinstance(raw_filters, list):
            return None
        for item in raw_filters:
            if not isinstance(item, dict):
                return None
            dimension_id = item.get("dimension")
            if not _is_non_empty_string(dimension_id):
                return None
            dimension_ids.append(dimension_id.strip())

        raw_order_by = plan.get("order_by")
        if raw_order_by is None:
            raw_order_by = []
        elif not isinstance(raw_order_by, list):
            return None
        for item in raw_order_by:
            if not isinstance(item, dict):
                return None
            metric_id = item.get("metric")
            dimension_id = item.get("dimension")
            if metric_id is not None and not _is_non_empty_string(metric_id):
                return None
            if dimension_id is not None and not _is_non_empty_string(dimension_id):
                return None
            has_metric = _is_non_empty_string(metric_id)
            has_dimension = _is_non_empty_string(dimension_id)
            if has_metric == has_dimension:
                return None
            if has_metric:
                metric_ids.append(metric_id.strip())
            if has_dimension:
                dimension_ids.append(dimension_id.strip())

        for metric_id in _dedupe_string_items(metric_ids):
            table_name = self._lookup_metric_table(metric_id)
            if not table_name:
                return None
            referenced_tables.add(table_name)
        for dimension_id in _dedupe_string_items(dimension_ids):
            table_name = self._lookup_dimension_table(dimension_id)
            if not table_name:
                return None
            referenced_tables.add(table_name)
        return referenced_tables

    def _lookup_metric_table(self, metric_id: str) -> str | None:
        """按 metric_id 查询 canonical 指标所属表；未知指标返回 None。"""

        for metric in self.catalog.metrics:
            if metric.metric_id == metric_id and metric.table:
                return metric.table
        return None

    def _lookup_dimension_table(self, dimension_id: str) -> str | None:
        """按 dimension_id 查询 canonical 维度所属表；未知维度返回 None。"""

        for dimension in self.catalog.dimensions:
            if dimension.dimension_id == dimension_id and dimension.table:
                return dimension.table
        return None

    def _expand_recalled_catalog_dependencies(self, recalled_ids: set[str]) -> set[str]:
        """展开本次召回命中在 canonical catalog 中声明的安全依赖。

        参数：
            recalled_ids: 本次 recall/rerank 实际返回的 catalog_id 集合。
        返回：
            可供 candidate.catalog_refs 自动补全的 catalog_id 集合。
        业务逻辑：
            live provider gate 可能只召回到 example 文档，而该 example 在本地 Semantic Catalog
            中已经人工声明了所需 table/metric/dimension/rule。这里只从本地 canonical catalog
            展开这些依赖，且必须落在当前 validator 允许的 catalog_id 白名单内；不会信任 LLM
            自行声明的依赖，也不会放开未召回、未声明的指标或表。
        """

        allowed_ids = self._build_allowed_catalog_ref_ids()
        expanded = {catalog_id for catalog_id in recalled_ids if catalog_id in allowed_ids}
        pending = list(expanded)
        while pending:
            catalog_id = pending.pop()
            for dependency_id in self._catalog_ref_dependencies(catalog_id):
                if dependency_id not in allowed_ids or dependency_id in expanded:
                    continue
                expanded.add(dependency_id)
                pending.append(dependency_id)
        return expanded

    def _catalog_ref_dependencies(self, catalog_id: str) -> set[str]:
        """返回单个 canonical catalog_id 的受控依赖。"""

        if catalog_id.startswith("example:"):
            example_id = catalog_id.split(":", 1)[1]
            for example in self.catalog.examples:
                if example.example_id == example_id:
                    return set(example.catalog_refs)
            return set()
        if catalog_id.startswith("metric:"):
            metric_id = catalog_id.split(":", 1)[1]
            for metric in self.catalog.metrics:
                if metric.metric_id == metric_id and metric.table:
                    return {f"table:{metric.table}"}
            return set()
        if catalog_id.startswith("dimension:"):
            dimension_id = catalog_id.split(":", 1)[1]
            for dimension in self.catalog.dimensions:
                if dimension.dimension_id == dimension_id and dimension.table:
                    return {f"table:{dimension.table}"}
            return set()
        if catalog_id.startswith("join:"):
            join_id = catalog_id.split(":", 1)[1]
            for join in self.catalog.joins:
                if join.join_id == join_id:
                    return {f"table:{join.left_table}", f"table:{join.right_table}"}
            return set()
        return set()

    def _build_allowed_catalog_ref_ids(self) -> set[str]:
        """从当前 canonical catalog 构造 normalization 可使用的 catalog_id 白名单。"""

        ids: set[str] = set()
        ids.update(f"table:{table.table_name}" for table in self.catalog.allowed_tables())
        ids.update(f"metric:{metric.metric_id}" for metric in self.catalog.metrics)
        ids.update(f"dimension:{dimension.dimension_id}" for dimension in self.catalog.dimensions)
        ids.update(f"join:{join.join_id}" for join in self.catalog.joins)
        ids.update(f"rule:{rule.rule_id}" for rule in self.catalog.rules)
        ids.update(f"example:{example.example_id}" for example in self.catalog.examples)
        return ids

    def _should_apply_default_time_rule(
        self,
        *,
        original_question: str,
        normalized_question: str,
        plan: dict[str, Any],
        recalled_ids: set[str],
    ) -> bool:
        """判断是否可安全补默认时间业务规则。"""

        if "rule:default_time_range" not in recalled_ids:
            return False
        if _has_explicit_year(original_question) or _has_explicit_year(normalized_question):
            return False
        return _plan_has_default_year_filter(plan)

    def _build_openai_client(self) -> Any:
        from openai import OpenAI

        openai_kwargs = _build_provider_openai_client_kwargs(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout_seconds=self.timeout_seconds,
            max_retries=0,
        )
        return OpenAI(**openai_kwargs)

    def _build_messages(
        self,
        *,
        original_question: str,
        normalized_question: str,
        route: LogisticsNl2SqlDomainRoute,
        recall_result: LogisticsCatalogRecallResult,
    ) -> list[dict[str, str]]:
        """构造主 LLM 消息。

        参数：
            original_question: 用户原始问题。
            normalized_question: Query Rewrite 后的问题文本。
            route: 领域路由结果，必须已通过物流中间库 shadow 路由。
            recall_result: catalog 召回与 rerank 结果。
        返回：
            OpenAI Chat Completions 消息列表；其中 user 消息包含严格 schema contract，避免 LLM 输出错层字段。
        """

        hit_payload = [
            {
                "catalog_id": hit.document.catalog_id,
                "catalog_version": hit.document.catalog_version,
                "doc_type": hit.document.doc_type,
                "title": hit.document.title,
                "content": hit.document.content,
                "metadata": hit.document.metadata,
                "rerank_score": hit.rerank_score,
            }
            for hit in recall_result.hits
        ]
        recalled_ids = {hit.document.catalog_id for hit in recall_result.hits}
        allowed_catalog_ids = sorted(self._expand_recalled_catalog_dependencies(recalled_ids))
        system_prompt = (
            "你是物流 NL2SQL 的 SQLPlan Generator。\n"
            "只允许返回严格 JSON object，不能输出 markdown、解释性文字或多段内容。\n"
            "最终输出必须就是 logistics_sqlplan_candidate.v1 对象本身，不能再包一层 candidate/query_plan/sql_plan。\n"
            "不能输出 SQL、raw_sql、where、having、表字段猜测、数据库连接、最终答案或计算值。\n"
            "只能生成 schema_contract 允许的键；任何额外键、错层键或非标数组元素都会被后端拒绝。\n"
            "filters、business_rules、explicit_year_buckets、requested_unit、limit 只能放在 plan 内。\n"
            "confidence 只能放在顶层，绝不能放在 plan.confidence。\n"
            "plan.dimensions、plan.metrics、plan.group_by、plan.business_rules 必须是字符串数组，不能放对象。\n"
            "所有表、指标、维度、规则和示例必须来自召回 catalog_id，或召回示例在 metadata.catalog_refs 中声明的 canonical 依赖。\n"
            "如果问题需要澄清或不支持，仍然返回同一顶层结构并设置 strategy=clarify/unsupported，不要伪造 sql_direct。"
        )
        user_prompt = json.dumps(
            {
                "original_question": original_question,
                "normalized_question": normalized_question,
                "route": route.model_dump(mode="json"),
                "catalog_version": self.catalog.catalog_version,
                "recall_hits": hit_payload,
                "allowed_catalog_ids": allowed_catalog_ids,
                "schema_contract": self._build_schema_contract(),
                "json_schema_contract": self._build_json_schema_contract(),
                "required_candidate_schema": self._build_required_candidate_schema(),
                "valid_sql_direct_example": self._build_valid_sql_direct_example(allowed_catalog_ids),
                "output_instruction": (
                    "Return exactly one JSON object that matches json_schema_contract and schema_contract. "
                    "Do not include any key listed in forbidden_misplaced_keys. Do not wrap the object."
                ),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

    def _build_schema_contract(self) -> dict[str, Any]:
        """返回给 LLM 的紧凑字段归属契约。

        返回：
            JSON 可序列化契约，明确顶层、plan、filter、order_by 的允许字段和常见错层字段。
        """

        return {
            "strict_additional_properties": False,
            "allowed_top_level_keys": SQLPLAN_CANDIDATE_ALLOWED_TOP_LEVEL_KEYS,
            "allowed_plan_keys": SQLPLAN_PLAN_ALLOWED_KEYS,
            "allowed_filter_keys": SQLPLAN_FILTER_ALLOWED_KEYS,
            "allowed_order_by_keys": SQLPLAN_ORDER_BY_ALLOWED_KEYS,
            "forbidden_misplaced_keys": SQLPLAN_FORBIDDEN_MISPLACED_KEYS,
            "field_placement": {
                "filters": "plan.filters",
                "business_rules": "plan.business_rules",
                "explicit_year_buckets": "plan.explicit_year_buckets",
                "requested_unit": "plan.requested_unit",
                "limit": "plan.limit",
                "confidence": "top-level confidence only",
            },
            "array_item_rules": {
                "catalog_refs": "array<object{catalog_id:string,catalog_version:string}>",
                "plan.metrics": "array<string>",
                "plan.dimensions": "array<string>",
                "plan.group_by": "array<string>",
                "plan.business_rules": "array<string>",
                "plan.filters": "array<object{dimension:string,operator:string,values:array<scalar>,source?:string}>",
                "plan.order_by": "array<object{metric?:string,dimension?:string,direction:asc|desc}>",
            },
            "default_time_rule": {
                "dimension": "biz_year",
                "operator": "in",
                "values": DEFAULT_LOGISTICS_YEARS,
                "business_rule": "default_time_range",
                "explicit_year_buckets": DEFAULT_LOGISTICS_YEARS,
            },
        }

    def _build_json_schema_contract(self) -> dict[str, Any]:
        """返回 Pydantic 导出的 JSON Schema，用于约束 provider 的结构化输出。"""

        schema = LogisticsSqlPlanCandidate.model_json_schema()
        # 业务逻辑：显式补强 additionalProperties=false，防止不同 Pydantic 版本导出的 schema 被模型误读。
        schema["additionalProperties"] = False
        return schema

    def _build_required_candidate_schema(self) -> dict[str, Any]:
        """返回人类可读的 candidate 骨架，帮助 LLM 理解字段层级。"""

        catalog_version = self.catalog.catalog_version
        return {
            "schema_version": "logistics_sqlplan_candidate.v1",
            "domain": "logistics",
            "strategy": "sql_direct|clarify|unsupported",
            "catalog_version": catalog_version,
            "catalog_refs": [{"catalog_id": "catalog id from recall_hits", "catalog_version": catalog_version}],
            "plan": {
                "query_type": "aggregate|ranking|detail",
                "domain": "logistics",
                "tables": [],
                "joins": [],
                "metrics": [],
                "dimensions": [],
                "filters": [],
                "group_by": [],
                "order_by": [],
                "business_rules": [],
                "explicit_year_buckets": [],
                "requested_unit": "MW",
                "limit": 20,
            },
            "clarification_questions": [],
            "unsupported_reason": None,
            "confidence": 0.0,
        }

    def _build_valid_sql_direct_example(self, allowed_catalog_ids: list[str]) -> dict[str, Any]:
        """返回一个合法 SQLPlan candidate 示例，只用于提示字段形状，不作为执行结果。

        参数：
            allowed_catalog_ids: 本次召回命中的 catalog_id 列表。
        返回：
            尽量只使用本次召回命中的 catalog_id；字段层级与 validator 接受的结构保持一致。
        """

        catalog_version = self.catalog.catalog_version
        example_ref_ids = [
            "table:dws_logistics_detail_union",
            "metric:shipment_mw",
            "metric:row_count",
            "dimension:biz_year",
            "dimension:logistics_company_name",
            "rule:default_time_range",
            "example:m9_example_carrier_mw_ranking",
        ]
        allowed = set(allowed_catalog_ids)
        refs = [
            {"catalog_id": catalog_id, "catalog_version": catalog_version}
            for catalog_id in example_ref_ids
            if catalog_id in allowed
        ]
        return {
            "schema_version": "logistics_sqlplan_candidate.v1",
            "domain": "logistics",
            "strategy": "sql_direct",
            "catalog_version": catalog_version,
            "catalog_refs": refs,
            "plan": {
                "query_type": "ranking",
                "domain": "logistics",
                "tables": ["dws_logistics_detail_union"],
                "joins": [],
                "metrics": ["shipment_mw", "row_count"],
                "dimensions": ["logistics_company_name"],
                "filters": [
                    {"dimension": "biz_year", "operator": "in", "values": DEFAULT_LOGISTICS_YEARS, "source": "default_time_range"}
                ],
                "group_by": ["logistics_company_name"],
                "order_by": [{"metric": "shipment_mw", "direction": "desc"}],
                "business_rules": ["default_time_range"],
                "explicit_year_buckets": DEFAULT_LOGISTICS_YEARS,
                "requested_unit": "MW",
                "limit": 20,
            },
            "clarification_questions": [],
            "unsupported_reason": None,
            "confidence": 0.9,
        }

    def _parse_candidate_text(self, content: str) -> dict[str, Any] | LogisticsSqlPlanGenerationResult:
        stripped = str(content or "").strip()
        if not stripped.startswith("{") or not stripped.endswith("}"):
            return LogisticsSqlPlanGenerationResult(status="validation_failed", error_codes=["m9_llm_output_not_strict_json"])
        try:
            payload = json.loads(stripped, parse_constant=_reject_json_constant)
        except Exception:
            return LogisticsSqlPlanGenerationResult(status="validation_failed", error_codes=["m9_llm_output_json_parse_error"])
        if not isinstance(payload, dict):
            return LogisticsSqlPlanGenerationResult(status="validation_failed", error_codes=["m9_llm_output_not_json_object"])
        forbidden = sorted(_find_forbidden_llm_fields(payload))
        if forbidden:
            return LogisticsSqlPlanGenerationResult(
                status="validation_failed",
                error_codes=[f"m9_forbidden_llm_field::{forbidden[0]}"],
            )
        return payload


class LogisticsNl2SqlM9ShadowSample(BaseModel):
    """M9 自然语言→SQLPlan shadow 样例。

    参数：
        raw_candidate_sql: 可选的上游原始 SQL 文本，只在运行时传给 M10-B gate；字段设置为
            `exclude=True`，写 records/report 时不会落盘 SQL 原文。
    """

    model_config = ConfigDict(extra="forbid")

    sample_id: str
    question: str
    expected_status: str = "success"
    category: str = "general"
    business_case: str = "general"
    offline_only: bool = True
    raw_candidate_sql: str | None = Field(default=None, exclude=True)


class LogisticsNl2SqlM9ShadowOutcome(BaseModel):
    """单条 M9 shadow 样例结果。"""

    model_config = ConfigDict(extra="forbid")

    sample: LogisticsNl2SqlM9ShadowSample
    status: str
    stage: str
    error_codes: list[str] = Field(default_factory=list)
    generated: bool = False
    validation_ok: bool = False
    shadow_status: str | None = None
    sql_hash: str | None = None
    row_count: int = 0
    candidate_sql_gate_allowed: bool | None = None
    candidate_sql_gate_rejected: bool | None = None
    candidate_sql_gate_reason_code: str | None = None
    elapsed_ms: int = 0


class LogisticsNl2SqlM9ShadowReport(BaseModel):
    """M9 shadow 汇总报表。"""

    model_config = ConfigDict(extra="forbid")

    total: int = 0
    success_count: int = 0
    recall_failed_count: int = 0
    generated_count: int = 0
    validation_pass_count: int = 0
    validation_failed_count: int = 0
    candidate_sql_gate_allowed_count: int = 0
    candidate_sql_gate_rejected_count: int = 0
    by_candidate_sql_gate_reason: dict[str, int] = Field(default_factory=dict)
    expected_status_match_count: int = 0
    expected_status_mismatch_count: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_business_case: dict[str, int] = Field(default_factory=dict)


class LogisticsNl2SqlM9ShadowRun(BaseModel):
    """M9 shadow runner 返回。"""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    version: str = M9_SHADOW_SQLPLAN_GENERATION_VERSION
    shadow_only: bool = True
    live_provider_smoke: bool = False
    outcomes: list[LogisticsNl2SqlM9ShadowOutcome] = Field(default_factory=list)
    report: LogisticsNl2SqlM9ShadowReport
    records_path: Path
    report_path: Path

    def render_markdown(self) -> str:
        lines = [
            "# M9 NL2SQL Shadow SQLPlan Generation Report",
            "",
            f"- version: {self.version}",
            f"- shadow_only: {self.shadow_only}",
            f"- total: {self.report.total}",
            f"- success_count: {self.report.success_count}",
            f"- generated_count: {self.report.generated_count}",
            f"- validation_pass_count: {self.report.validation_pass_count}",
            f"- recall_failed_count: {self.report.recall_failed_count}",
            f"- candidate_sql_gate_allowed_count: {self.report.candidate_sql_gate_allowed_count}",
            f"- candidate_sql_gate_rejected_count: {self.report.candidate_sql_gate_rejected_count}",
            f"- expected_status_mismatch_count: {self.report.expected_status_mismatch_count}",
            "",
            "## By Status",
        ]
        lines.extend(f"- {key}: {value}" for key, value in sorted(self.report.by_status.items()))
        if self.report.by_candidate_sql_gate_reason:
            lines.append("")
            lines.append("## Candidate SQL Gate Reasons")
            lines.extend(
                f"- {key}: {value}" for key, value in sorted(self.report.by_candidate_sql_gate_reason.items())
            )
        lines.append("")
        lines.append("## Samples")
        for outcome in self.outcomes:
            lines.append(
                f"- {outcome.sample.sample_id}: status={outcome.status}, stage={outcome.stage}, generated={outcome.generated}"
            )
        return "\n".join(lines) + "\n"


def build_default_logistics_nl2sql_m9_shadow_samples() -> list[LogisticsNl2SqlM9ShadowSample]:
    """构造 M9 默认自然语言样例集；只用于 shadow/offline 评估。"""

    return [
        LogisticsNl2SqlM9ShadowSample(
            sample_id="m9_success_carrier_mw_ranking_default_years",
            question="哪个物流跑得最多？",
            expected_status="success",
            category="ranking",
            business_case="carrier_mw_ranking",
        ),
        LogisticsNl2SqlM9ShadowSample(
            sample_id="m9_success_yearly_mw_breakdown",
            question="2023年到2025年每年发运量分别是多少？",
            expected_status="success",
            category="breakdown",
            business_case="yearly_mw_breakdown",
        ),
        LogisticsNl2SqlM9ShadowSample(
            sample_id="m9_guard_tonnage_fail_closed",
            question="2025年各承运商运输吨位排名",
            expected_status="validation_failed",
            category="validation",
            business_case="unsupported_tonnage",
        ),

        # -- 新增 M9 扩展样例（P2：基线提升）--
        LogisticsNl2SqlM9ShadowSample(
            sample_id="m9_success_total_fee_summary",
            question="华东区域总费用是多少",
            expected_status="success",
            category="aggregate",
            business_case="total_fee_summary",
        ),
        LogisticsNl2SqlM9ShadowSample(
            sample_id="m9_success_mw_summary",
            question="2023年一年总共的运量是多少MW",
            expected_status="success",
            category="aggregate",
            business_case="mw_summary",
        ),
        LogisticsNl2SqlM9ShadowSample(
            sample_id="m9_success_carrier_mw_by_year",
            question="2023年英赋嘉发运多少量?",
            expected_status="success",
            category="ranking",
            business_case="carrier_mw_by_year",
        ),
        LogisticsNl2SqlM9ShadowSample(
            sample_id="m9_success_origin_customer_topn",
            question="2025年合肥发往宁波的承运商运费排名前5",
            expected_status="success",
            category="ranking",
            business_case="origin_customer_topn",
        ),
        LogisticsNl2SqlM9ShadowSample(
            sample_id="m9_success_route_pricing",
            question="2025年合肥至马鞍山17.5米车的平均运费",
            expected_status="success",
            category="detail",
            business_case="route_pricing",
        ),
        LogisticsNl2SqlM9ShadowSample(
            sample_id="m9_success_multi_year_fee_compare",
            question="23年、24年、25年合肥发广州17.5车运价分别是多少？",
            expected_status="success",
            category="breakdown",
            business_case="multi_year_fee_compare",
        ),
        LogisticsNl2SqlM9ShadowSample(
            sample_id="m9_success_region_monthly_mw",
            question="请按月份汇总发往贵州的发运量和总费用，并区分2023、2024、2025三个年度？",
            expected_status="success",
            category="breakdown",
            business_case="region_monthly_mw",
        ),
        LogisticsNl2SqlM9ShadowSample(
            sample_id="m9_success_multi_metric_aggregate",
            question="2025年各月发运量、运费和吨数总计",
            expected_status="success",
            category="aggregate",
            business_case="multi_metric_aggregate",
        ),
        LogisticsNl2SqlM9ShadowSample(
            sample_id="m9_success_vehicle_type_summary",
            question="请统计合肥始发各车型的车次、发运件数、总费用、平均每车装载托数，并用车型汇总表展示？",
            expected_status="success",
            category="detail",
            business_case="vehicle_type_summary",
        ),
        LogisticsNl2SqlM9ShadowSample(
            sample_id="m9_success_extra_fee_by_month",
            question="2026年1月份额外费用产生多少钱，分别是什么项目？什么原因产生的？",
            expected_status="success",
            category="detail",
            business_case="extra_fee_by_month",
        ),
        LogisticsNl2SqlM9ShadowSample(
            sample_id="m9_guard_tonnage_fail_closed",
            question="2025年各承运商运输吨位排名",
            expected_status="validation_failed",
            category="validation",
            business_case="unsupported_tonnage",
        ),
        LogisticsNl2SqlM9ShadowSample(
            sample_id="m9_success_avg_fee_per_watt",
            question="请把华东各运输方式平均元每瓦按从低到高列出来",
            expected_status="success",
            category="ranking",
            business_case="avg_fee_per_watt",
        ),
        LogisticsNl2SqlM9ShadowSample(
            sample_id="m9_success_extra_fee_ratio",
            question="请统计2023年备注中包含倒运、中转、换车、压车、放空的记录数量和费用金额？",
            expected_status="success",
            category="detail",
            business_case="extra_fee_ratio",
        ),
        LogisticsNl2SqlM9ShadowSample(
            sample_id="m9_success_customer_mw_by_year",
            question="华润新能源（皮山）有限公司 项目 24年发运量是多少",
            expected_status="success",
            category="aggregate",
            business_case="customer_mw_by_year",
        ),
    ]


def run_logistics_nl2sql_m9_shadow_sqlplan_generation(
    *,
    samples: list[LogisticsNl2SqlM9ShadowSample] | None = None,
    artifact_dir: str | Path | None = None,
    recall_service: Any | None = None,
    generator: Any | None = None,
    pipeline: LogisticsNl2SqlShadowPipeline | None = None,
    live_provider_smoke: bool = False,
    max_live_samples: int | None = None,
) -> LogisticsNl2SqlM9ShadowRun:
    """执行 M9 自然语言→SQLPlan→shadow pipeline 评估。"""

    resolved_samples = samples or build_default_logistics_nl2sql_m9_shadow_samples()
    if live_provider_smoke and max_live_samples is not None:
        resolved_samples = resolved_samples[:max_live_samples]
    artifact_path = Path(artifact_dir or "ai/outbox/kanban/t_m9_nl2sql_shadow")
    artifact_path.mkdir(parents=True, exist_ok=True)
    records_path = artifact_path / DEFAULT_M9_RECORDS_FILENAME
    report_path = artifact_path / DEFAULT_M9_REPORT_FILENAME

    rewrite_service = LogisticsNl2SqlQueryRewriteService()
    router = LogisticsNl2SqlDomainRouter()
    # 后续依赖按需懒加载：rewrite/route fail-closed 的样例不应构造召回、LLM 或 shadow pipeline 适配器。
    resolved_recall_service = recall_service
    resolved_generator = generator
    resolved_pipeline = pipeline

    outcomes: list[LogisticsNl2SqlM9ShadowOutcome] = []
    for sample in resolved_samples:
        started = time.perf_counter()
        rewrite = rewrite_service.rewrite(sample.question)
        unsupported_error_codes = _rewrite_unsupported_error_codes(rewrite)
        if unsupported_error_codes:
            # 不支持的业务单位是确定性停止信号：必须在召回、LLM 生成和 shadow 执行前 fail-closed，避免被离线/真实生成器改写成 MW。
            outcomes.append(
                _outcome(
                    sample=sample,
                    status="validation_failed",
                    stage="rewrite",
                    started=started,
                    error_codes=unsupported_error_codes,
                    generated=False,
                    validation_ok=False,
                )
            )
            continue
        route = router.route(rewrite)
        if not route.should_process:
            outcomes.append(
                _outcome(
                    sample=sample,
                    status="route_skipped",
                    stage="route",
                    started=started,
                    error_codes=[route.reason_code or "m9_route_skipped"],
                )
            )
            continue

        if resolved_recall_service is None:
            # 首次进入召回阶段时才构造真实召回服务；rewrite/route 阶段被阻断的样例无需依赖外部 provider。
            # 当 live_provider_smoke=False（离线模式）时，启用 keyword fallback
            # 避免向量检索不可用时所有成功的 NL 样例都 recall_failed。
            resolved_recall_service = LogisticsCatalogRecallService(
                enable_keyword_fallback=not live_provider_smoke,
            )
        recall_result = resolved_recall_service.recall(
            question=rewrite.original_question,
            normalized_question=rewrite.normalized_question,
            slot_summary=_slot_summary(rewrite),
        )
        if recall_result.status != "ok" or not recall_result.hits:
            outcomes.append(
                _outcome(
                    sample=sample,
                    status="recall_failed",
                    stage="recall",
                    started=started,
                    error_codes=[f"m9_recall_not_ok::{recall_result.status}", *( [recall_result.error] if recall_result.error else [] )],
                )
            )
            continue

        if resolved_generator is None:
            # 召回成功后才构造 LLM generator，避免前置 fail-closed 样例触发无意义的 LLM 配置读取。
            resolved_generator = LogisticsSqlPlanGenerator()
        generation = resolved_generator.generate(
            original_question=rewrite.original_question,
            normalized_question=rewrite.normalized_question,
            route=route,
            recall_result=recall_result,
        )
        if generation.status != "ok" or not generation.candidate:
            outcomes.append(
                _outcome(
                    sample=sample,
                    status="validation_failed" if generation.status == "validation_failed" else generation.status,
                    stage="generation",
                    started=started,
                    error_codes=generation.error_codes,
                    generated=False,
                    validation_ok=False,
                )
            )
            continue

        if resolved_pipeline is None:
            # SQLPlan 已验证通过后才构造 shadow pipeline；不支持/召回/生成失败都不进入执行链路。
            resolved_pipeline = LogisticsNl2SqlShadowPipeline()
        shadow_result = resolved_pipeline.run(
            LogisticsNl2SqlShadowPipelineRequest(
                question=rewrite.original_question,
                rewritten_question=rewrite.normalized_question,
                domain=route.domain,
                source_system=route.source_system,
                candidate=generation.candidate,
                raw_candidate_sql=sample.raw_candidate_sql,
                request_id=uuid4().hex,
                dry_run=True,
            )
        )
        outcomes.append(
            _outcome(
                sample=sample,
                status=shadow_result.status,
                stage=shadow_result.stage,
                started=started,
                error_codes=shadow_result.error_codes,
                generated=True,
                validation_ok=bool(generation.validation_result and generation.validation_result.ok),
                shadow_status=shadow_result.status,
                sql_hash=shadow_result.sql_hash,
                row_count=shadow_result.row_count,
                candidate_sql_gate_allowed=shadow_result.candidate_sql_gate_allowed,
                candidate_sql_gate_rejected=shadow_result.candidate_sql_gate_rejected,
                candidate_sql_gate_reason_code=shadow_result.candidate_sql_gate_reason_code,
            )
        )

    report = _build_report(outcomes)
    run = LogisticsNl2SqlM9ShadowRun(
        outcomes=outcomes,
        report=report,
        records_path=records_path,
        report_path=report_path,
        live_provider_smoke=live_provider_smoke,
    )
    _write_records(records_path, outcomes)
    report_path.write_text(run.render_markdown(), encoding="utf-8")
    return run


def _outcome(
    *,
    sample: LogisticsNl2SqlM9ShadowSample,
    status: str,
    stage: str,
    started: float,
    error_codes: list[str] | None = None,
    generated: bool = False,
    validation_ok: bool = False,
    shadow_status: str | None = None,
    sql_hash: str | None = None,
    row_count: int = 0,
    candidate_sql_gate_allowed: bool | None = None,
    candidate_sql_gate_rejected: bool | None = None,
    candidate_sql_gate_reason_code: str | None = None,
) -> LogisticsNl2SqlM9ShadowOutcome:
    return LogisticsNl2SqlM9ShadowOutcome(
        sample=sample,
        status=status,
        stage=stage,
        error_codes=[redact_evaluation_text(str(error)) for error in (error_codes or []) if error],
        generated=generated,
        validation_ok=validation_ok,
        shadow_status=shadow_status,
        sql_hash=sql_hash,
        row_count=row_count,
        candidate_sql_gate_allowed=candidate_sql_gate_allowed,
        candidate_sql_gate_rejected=candidate_sql_gate_rejected,
        candidate_sql_gate_reason_code=redact_evaluation_text(str(candidate_sql_gate_reason_code)) if candidate_sql_gate_reason_code else None,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )


def _build_report(outcomes: list[LogisticsNl2SqlM9ShadowOutcome]) -> LogisticsNl2SqlM9ShadowReport:
    total = len(outcomes)
    by_status = Counter(outcome.status for outcome in outcomes)
    by_category = Counter(outcome.sample.category for outcome in outcomes)
    by_business_case = Counter(outcome.sample.business_case for outcome in outcomes)
    by_candidate_sql_gate_reason = Counter(
        outcome.candidate_sql_gate_reason_code for outcome in outcomes if outcome.candidate_sql_gate_reason_code
    )
    expected_status_match_count = sum(1 for outcome in outcomes if outcome.status == outcome.sample.expected_status)
    return LogisticsNl2SqlM9ShadowReport(
        total=total,
        success_count=by_status.get("success", 0),
        recall_failed_count=by_status.get("recall_failed", 0),
        generated_count=sum(1 for outcome in outcomes if outcome.generated),
        validation_pass_count=sum(1 for outcome in outcomes if outcome.validation_ok),
        validation_failed_count=by_status.get("validation_failed", 0),
        candidate_sql_gate_allowed_count=sum(1 for outcome in outcomes if outcome.candidate_sql_gate_allowed is True),
        candidate_sql_gate_rejected_count=sum(1 for outcome in outcomes if outcome.candidate_sql_gate_rejected is True),
        by_candidate_sql_gate_reason=dict(by_candidate_sql_gate_reason),
        expected_status_match_count=expected_status_match_count,
        expected_status_mismatch_count=total - expected_status_match_count,
        by_status=dict(by_status),
        by_category=dict(by_category),
        by_business_case=dict(by_business_case),
    )


def _write_records(path: Path, outcomes: list[LogisticsNl2SqlM9ShadowOutcome]) -> None:
    lines = [json.dumps(outcome.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) for outcome in outcomes]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _normalize_safe_provider_top_level_aliases(payload: dict[str, Any]) -> dict[str, Any]:
    """归一真实 provider 偶发的安全顶层别名键。

    参数：
        payload: LLM 已返回且已通过禁用字段扫描的 JSON object。
    返回：
        只对白名单别名做复制/删除后的 payload；未知额外键继续保留给 validator fail-closed。
    业务逻辑：
        catalog_refs 后续仍会按本次 recall 命中和 canonical 依赖重建，不信任 LLM 自行扩大引用；
        unsupported_reason 若出现非空冲突会保留别名键，让严格 schema 拦截，避免把不支持结论误改成成功。
    """

    normalized = dict(payload)
    for alias, canonical_key in SQLPLAN_SAFE_TOP_LEVEL_KEY_ALIASES.items():
        if alias not in normalized:
            continue
        alias_value = normalized.pop(alias)
        if canonical_key not in normalized:
            normalized[canonical_key] = alias_value
            continue
        canonical_value = normalized.get(canonical_key)
        if canonical_key == "catalog_refs" or _is_empty_provider_alias_value(alias_value) or alias_value == canonical_value:
            continue
        if _is_empty_provider_alias_value(canonical_value):
            normalized[canonical_key] = alias_value
            continue
        # 业务逻辑：别名与 canonical 同时给出且含义冲突时不能猜测，恢复别名交给 strict schema fail-closed。
        normalized[alias] = alias_value
    return normalized


def _is_empty_provider_alias_value(value: Any) -> bool:
    """判断 provider 别名值是否只是空占位；用于安全忽略重复别名。"""

    if value is None:
        return True
    if value == [] or value == {}:
        return True
    if isinstance(value, str) and value.strip().lower() in {"", "null", "none", "[]", "{}"}:
        return True
    return False


def _slot_summary(rewrite: LogisticsNl2SqlQueryRewriteResult) -> str:
    return json.dumps(
        {
            "default_years": rewrite.default_years,
            "normalized_terms": rewrite.normalized_terms,
            "unsupported_flags": rewrite.unsupported_flags,
            "requested_unit": rewrite.requested_unit,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _rewrite_unsupported_error_codes(rewrite: LogisticsNl2SqlQueryRewriteResult) -> list[str]:
    """把 Query Rewrite 的不支持标记转换成 M9 runner 可审计的 fail-closed 错误码。

    参数：
        rewrite: 当前样例的查询改写结果，包含 unsupported_flags 等确定性口径标记。
    返回：
        错误码列表；为空表示可以继续进入领域路由和召回阶段。
    """

    # 业务逻辑：吨位等 unsupported flag 不能交给召回或 LLM 自行解释，否则容易被改写成相近的 MW 指标。
    return [f"m9_rewrite_unsupported::{flag}" for flag in rewrite.unsupported_flags if flag]


def _has_explicit_year(text: str) -> bool:
    return bool(_YEAR_RE.search(text))


def _string_items(value: Any) -> list[str]:
    """提取字符串数组中的有效字符串，非字符串项保留给 Pydantic/validator 失败。"""

    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _is_non_empty_string(value: Any) -> TypeGuard[str]:
    """判断 provider 输出值是否为非空字符串。

    参数：
        value: 任意 provider 输出字段值。
    返回：
        True 表示该值是去空白后仍非空的字符串；False 表示该值不能作为 catalog 引用。
    """

    return isinstance(value, str) and bool(value.strip())


def _is_non_empty_string_list(value: Any) -> bool:
    """判断值是否为非空字符串列表。

    参数：
        value: provider 输出的任意字段。
    返回：
        True 表示是 `list[str]` 且每项去空白后非空；False 表示必须保持原样交由 validator 拦截。
    """

    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)


def _is_optional_string_list(value: Any) -> bool:
    """判断可选字段是否为字符串列表或未提供。

    参数：
        value: provider 输出的任意字段。
    返回：
        True 表示字段缺省/None 或为有效 `list[str]`；False 表示字段形态异常，不能用于归一化判断。
    """

    return value is None or _is_non_empty_string_list(value) or value == []


def _is_empty_list_or_none(value: Any) -> bool:
    """判断字段是否明确表示空列表或未提供。

    参数：
        value: provider 输出的任意字段。
    返回：
        True 表示 None 或空 list；False 表示存在 join/异常形态，应 fail-closed 不做归一化。
    """

    return value is None or value == []


def _dedupe_string_items(value: Any) -> list[str]:
    """按出现顺序去重字符串数组，用于安全归一 provider 重复项。

    参数：
        value: 任意 provider 输出值，通常是 list[str]。
    返回：
        去重后的非空字符串列表；非字符串项不在这里修复，继续由后续 schema/validator 拦截。
    """

    seen: set[str] = set()
    items: list[str] = []
    for item in _string_items(value):
        if item in seen:
            continue
        seen.add(item)
        items.append(item)
    return items


def _should_drop_default_time_rule_for_explicit_years(
    *,
    original_question: str,
    normalized_question: str,
    plan: dict[str, Any],
) -> bool:
    """判断显式年份问题中误带的 default_time_range 是否可以安全移除。

    参数：
        original_question: 用户原始问题。
        normalized_question: Query Rewrite 后的问题。
        plan: provider 输出的 plan dict。
    返回：
        True 表示可移除 default_time_range；False 表示保持原样交给 validator。
    业务逻辑：
        default_time_range 仅代表无显式时间时默认 2023-2026。若用户已明确问 2023-2025，且
        plan.filters 与 explicit_year_buckets 完全一致、并且不是默认全集，说明该规则是从召回示例误抄，
        可以移除；否则不做推断，保持 fail-closed。
    """

    if not (_has_explicit_year(original_question) or _has_explicit_year(normalized_question)):
        return False
    filter_years = _extract_plan_biz_years(plan)
    if not filter_years or filter_years == DEFAULT_LOGISTICS_YEARS:
        return False
    buckets = plan.get("explicit_year_buckets")
    if not isinstance(buckets, list) or not buckets:
        return False
    bucket_years: list[int] = []
    for value in buckets:
        year = _coerce_year_value(value)
        if year is None:
            return False
        bucket_years.append(year)
    return sorted(set(bucket_years)) == filter_years


def _is_empty_rule_placeholder(value: str) -> bool:
    """识别 LLM 对空业务规则数组的常见字符串化占位。"""

    compact = re.sub(r"\s+", "", str(value or "").strip().lower())
    return compact in {"", "[]", "null", "none", "businesses:[]", "business_rules:[]", "rules:[]"}


def _plan_has_default_year_filter(plan: dict[str, Any]) -> bool:
    """判断 plan 是否已经携带 2023-2026 默认年份过滤。"""

    for item in plan.get("filters") or []:
        if not isinstance(item, dict) or item.get("dimension") != "biz_year":
            continue
        years = [_coerce_year_value(value) for value in item.get("values") or []]
        parsed_years = sorted(year for year in years if year is not None)
        operator = str(item.get("operator") or "").strip().lower()
        if operator == "in" and parsed_years == DEFAULT_LOGISTICS_YEARS:
            return True
        if operator == "between" and len(parsed_years) == 2:
            start, end = parsed_years[0], parsed_years[-1]
            if start == DEFAULT_LOGISTICS_YEARS[0] and end == DEFAULT_LOGISTICS_YEARS[-1]:
                return True
    return False


def _normalize_explicit_year_buckets_from_filters(plan: dict[str, Any]) -> None:
    """仅当 explicit_year_buckets 去重后与年份过滤完全一致时，安全归一重复年份。"""

    buckets = plan.get("explicit_year_buckets")
    if not isinstance(buckets, list) or not buckets:
        return

    filter_years = _extract_plan_biz_years(plan)
    if not filter_years:
        return

    bucket_years: list[int] = []
    for value in buckets:
        year = _coerce_year_value(value)
        if year is None:
            return
        bucket_years.append(year)

    normalized_buckets = sorted(set(bucket_years))
    if normalized_buckets == filter_years:
        plan["explicit_year_buckets"] = normalized_buckets


def _extract_plan_biz_years(plan: dict[str, Any]) -> list[int]:
    """从 provider 原始 plan.filters 中安全提取 biz_year 年份集合。"""

    years: set[int] = set()
    for item in plan.get("filters") or []:
        if not isinstance(item, dict) or item.get("dimension") != "biz_year":
            continue
        raw_values = item.get("values") or []
        if not isinstance(raw_values, list):
            return []
        parsed_years: list[int] = []
        for value in raw_values:
            year = _coerce_year_value(value)
            if year is None:
                return []
            parsed_years.append(year)

        operator = str(item.get("operator") or "").strip().lower()
        if operator == "between" and len(parsed_years) == 2:
            start, end = sorted(parsed_years)
            if start < DEFAULT_LOGISTICS_YEARS[0] or end > DEFAULT_LOGISTICS_YEARS[-1]:
                return []
            years.update(range(start, end + 1))
        elif operator in {"=", "in"}:
            years.update(parsed_years)
        else:
            return []
    return sorted(years)


def _coerce_year_value(value: Any) -> int | None:
    """把 LLM 可能输出的年份标量转为四位年份；失败返回 None。"""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        if value in DEFAULT_LOGISTICS_YEARS:
            return value
        if 23 <= value <= 26:
            return 2000 + value
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return _coerce_year_value(int(stripped))
        match = re.search(r"20(2[3-6])", stripped)
        if match:
            return int(f"20{match.group(1)}")
        short_match = re.search(r"(?<!\d)(2[3-6])\s*年", stripped)
        if short_match:
            return int(f"20{short_match.group(1)}")
    return None


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non_standard_json_constant::{value}")


def _find_forbidden_llm_fields(value: Any, *, path: str = "") -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in _SQLPLAN_FORBIDDEN_LLM_FIELDS:
                found.add(key_text.lower())
            found.update(_find_forbidden_llm_fields(item, path=f"{path}.{key_text}" if path else key_text))
    elif isinstance(value, list):
        for item in value:
            found.update(_find_forbidden_llm_fields(item, path=path))
    return found


__all__ = [
    "DEFAULT_M9_RECORDS_FILENAME",
    "DEFAULT_M9_REPORT_FILENAME",
    "M9_SHADOW_SQLPLAN_GENERATION_VERSION",
    "LogisticsNl2SqlDomainRoute",
    "LogisticsNl2SqlDomainRouter",
    "LogisticsNl2SqlM9ShadowOutcome",
    "LogisticsNl2SqlM9ShadowReport",
    "LogisticsNl2SqlM9ShadowRun",
    "LogisticsNl2SqlM9ShadowSample",
    "LogisticsNl2SqlQueryRewriteResult",
    "LogisticsNl2SqlQueryRewriteService",
    "LogisticsSqlPlanGenerationResult",
    "LogisticsSqlPlanGenerator",
    "build_default_logistics_nl2sql_m9_shadow_samples",
    "run_logistics_nl2sql_m9_shadow_sqlplan_generation",
]

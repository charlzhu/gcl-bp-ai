from __future__ import annotations

import json
import logging
from typing import Any

from backend.app.domains.business_analysis.schemas.inventory_sales_production_query import (
    InventorySalesProductionPeriodSpec,
    InventorySalesProductionQueryPlan,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.nl_query_planner import (
    InventorySalesProductionNlQueryPlanner,
    InventorySalesProductionPlanningError,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.semantic_catalog import (
    InventorySalesProductionSemanticCatalog,
    InventorySalesProductionSemanticCatalogLoader,
    ISP_SUPPORTED_QUERY_KEYS,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.sql_plan import (
    InventorySalesProductionSqlPlanCandidate,
    InventorySalesProductionSqlPlanFilter,
    InventorySalesProductionSqlPlanOrderBy,
    InventorySalesProductionSqlPlan,
    InventorySalesProductionSqlPlanValidator,
)

logger = logging.getLogger(__name__)

# S7: LLM 完整 SQLPlan 规划器
# LLM 输出完整的 InventorySalesProductionSqlPlanCandidate（含过滤、排序、业务规则），
# 经 SqlPlanValidator 校验后转换为 QueryPlan 由现有 executor 执行。


def _build_sqlplan_system_prompt(
    catalog: InventorySalesProductionSemanticCatalog,
) -> str:
    """构建 LLM 完整 SQLPlan 生成的 System Prompt。

    参数：
        catalog: 已加载的 Semantic Catalog。
    返回：
        格式化后的 System Prompt 字符串。
    """
    # 构建指标描述列表
    metrics_lines = []
    for metric in catalog.metrics:
        nl_desc = metric.nl_description or metric.business_note or ""
        examples = ""
        if metric.example_questions:
            examples = " 示例问法: " + "、".join(metric.example_questions[:3])
        metrics_lines.append(
            f"  {metric.metric_id} - {metric.display_name}: {nl_desc}{examples}"
        )
    metrics_desc = "\n".join(metrics_lines)

    # 构建维度描述列表
    dims_lines = []
    for dim in catalog.dimensions:
        nl_desc = dim.nl_description or ""
        values = ""
        if dim.example_values:
            values = " 取值示例: " + ", ".join(dim.example_values[:6])
        dims_lines.append(
            f"  {dim.dimension_id} - {dim.display_name}: {nl_desc}{values}"
        )
    dimensions_desc = "\n".join(dims_lines)

    # 构建 query_key 规则描述
    query_key_lines = []
    for qk in ISP_SUPPORTED_QUERY_KEYS:
        desc = _QUERY_KEY_DESCRIPTIONS.get(qk, "")
        query_key_lines.append(f"  - {qk}: {desc}")
    query_key_rules = "\n".join(query_key_lines)

    # 构建 filter 维度描述（可做过滤条件的维度）
    filter_dim_lines = []
    for dim in catalog.dimensions:
        dim_desc = dim.nl_description or ""
        values = ""
        if dim.example_values:
            values = " 示例值: " + ", ".join(dim.example_values[:6])
        filter_dim_lines.append(
            f"  {dim.dimension_id} - {dim.display_name}: {dim_desc} {values}"
        )
    filter_dimensions_desc = "\n".join(filter_dim_lines)

    return _SQLPLAN_GENERATION_SYSTEM_PROMPT.format(
        query_key_rules=query_key_rules,
        metrics_desc=metrics_desc,
        dimensions_desc=dimensions_desc,
        filter_dimensions_desc=filter_dimensions_desc,
    )


_SQLPLAN_GENERATION_SYSTEM_PROMPT = """你是一个产销存经营分析智能助手的 SQLPlan 规划器。
你的任务是将用户的自然语言问题解析为受控的 SQLPlan，不能生成 SQL 或 SQL 片段。

业务域：产销存经营分析（business_analysis / inventory_sales_production）
支持的期间类型：year（全年）、quarter（季度）、month（单月）、ytd（年初至某月累计）、month_range（月份区间）

支持的查询能力（query_key）及规则：
{query_key_rules}

可查询的指标列表（metric_code - 指标名称 - 业务说明）：
{metrics_desc}

可查询的维度列表（dimension_id - 维度名称 - 说明/示例）：
{dimensions_desc}

可过滤的维度及取值示例（filter 中 dimension 只能使用以下维度）：
{filter_dimensions_desc}

输出 JSON 格式（严格按此结构）：
{{
  "strategy": "sql_direct",
  "catalog_version": "business_analysis_inventory_sales_production_catalog.v1",
  "catalog_refs": [],
  "plan": {{
    "query_key": "ba_isp_metric_summary",
    "tables": ["v_hf_sap_inout_daily"],
    "metrics": ["shipment_volume"],
    "dimensions": [],
    "filters": [
      {{"dimension": "business_year", "operator": "=", "values": [2025]}}
    ],
    "group_by": [],
    "order_by": [],
    "business_rules": [],
    "business_flags": {{}},
    "period_type": "year",
    "year": 2025,
    "month": null,
    "quarter": null,
    "start_month": null,
    "end_month": null,
    "calculation_policy": null,
    "limit": null
  }},
  "clarification_questions": [],
  "unsupported_reason": null,
  "confidence": null
}}

关键规则：
- 无法确定查询意图时设置 strategy="clarify" 并填写 clarification_questions
- 明确不支持的查询 strategy="unsupported" 并填写 unsupported_reason
- 不要编造不存在的 metric_code、dimension_id 或 query_key
- filters 中只使用维度列表中的 dimension_id（如 business_year、base_name、model_type）
- filters 中的 operator 只使用 =、in、between
- business_year operator="in" 时可传多个年份，如 [2023, 2024, 2025]
- group_by 只使用维度列表中的 dimension_id
- order_by 中 metric 或 dimension 只使用 catalog 中的 metric_code 或 dimension_id
- 用户没说具体年份时设 year 为 2026（当前最新年份）
- query_key ba_isp_period_compare 用于同比、环比、月份区间查询
- query_key ba_isp_metric_trend 用于趋势查询（按月展开）
- query_key ba_isp_metric_breakdown 用于按维度拆分的查询（按基地、按版型）
- catalog_refs 保持空数组即可
"""

_QUERY_KEY_DESCRIPTIONS: dict[str, str] = {
    "ba_isp_metric_summary": "单指标汇总，适用于年度/季度/月度等单期间汇总查询。无维度拆分。",
    "ba_isp_metric_breakdown": "单指标按维度拆分，用户说按基地、各基地、按版型时使用。",
    "ba_isp_metric_trend": "趋势查询，用户说趋势、按月、每月时使用，按月份展开。",
    "ba_isp_budget_achievement": "预算达成率计算，需要产量和预算两个指标。",
    "ba_isp_inventory_snapshot": "库存/寄存等时点指标快照，取期末值。",
    "ba_isp_period_compare": "期间对比，用于同比、环比、月份区间查询，按月份展开。",
}

# 允许直接转换为 QueryPlan 的 strategy 类型
_DIRECT_EXECUTE_STRATEGIES = frozenset({"sql_direct"})


class InventorySalesProductionNl2SqlSqlPlanPlanner:
    """产销存 LLM 完整 SQLPlan 规划器（S7）。

    业务定位：
        1. 实现与 InventorySalesProductionNlQueryPlanner 相同的 build_plan(question) 接口；
        2. 内部使用 LLM 生成完整的 InventorySalesProductionSqlPlanCandidate；
        3. 经 InventorySalesProductionSqlPlanValidator 做 fail-closed 校验；
        4. 校验通过后转换为 InventorySalesProductionQueryPlan 由现有 executor 执行；
        5. LLM 失败、返回 clarification/unsupported、或校验失败时，
           自动 fallback 到规则规划器；
        6. 下游执行器、聚合策略、安全校验不变。

    参数：
        catalog: 可选注入的 Semantic Catalog，为空时使用默认目录。
        llm_model: LLM 模型名称，为空时使用 settings.llm_model。
        llm_base_url: LLM API base URL。
        llm_api_key: LLM API Key。
        timeout: LLM 调用超时秒数。
        fallback_on_error: LLM 失败时是否 fallback 到规则规划器（默认 True）。
    返回：
        执行 build_plan(question) 返回 InventorySalesProductionQueryPlan。
    """

    def __init__(
        self,
        *,
        catalog: object | None = None,
        llm_model: str | None = None,
        llm_base_url: str | None = None,
        llm_api_key: str | None = None,
        timeout: float = 15.0,
        fallback_on_error: bool = True,
    ) -> None:
        self._catalog = catalog
        self._catalog_loaded = False
        self.llm_model = llm_model
        self.llm_base_url = llm_base_url
        self.llm_api_key = llm_api_key
        self.timeout = timeout
        self.fallback_on_error = fallback_on_error
        # 规则规划器作为兜底
        self._rule_planner = InventorySalesProductionNlQueryPlanner()

    @property
    def catalog(self) -> InventorySalesProductionSemanticCatalog:
        """延迟加载 Semantic Catalog，避免构造函数中的循环导入。"""
        if not self._catalog_loaded:
            if self._catalog is None:
                self._catalog = InventorySalesProductionSemanticCatalogLoader().load()
            self._catalog_loaded = True
        return self._catalog  # type: ignore[return-value]

    def build_plan(self, question: str) -> InventorySalesProductionQueryPlan:
        """将用户自然语言问题转换为产销存受控 QueryPlan。

        路径：LLM 生成完整 SqlPlanCandidate → SqlPlanValidator 校验 →
        转换为 QueryPlan → 返回。

        参数：
            question: 用户自然语言问题。
        返回：
            InventorySalesProductionQueryPlan。
        异常：
            InventorySalesProductionPlanningError: LLM 和规则规划器都失败时抛出。
        """
        text = (question or "").strip()
        if not text:
            raise InventorySalesProductionPlanningError(
                "clarification", "请补充要查询的产销存问题。"
            )

        # 第一步：尝试 LLM 完整 SQLPlan 生成
        llm_plan = self._try_llm_sqlplan(text)
        if llm_plan is not None:
            logger.info(
                "nl2sql_sqlplan_planner_llm_mode question=%s", text[:50]
            )
            return llm_plan

        # 第二步：若 LLM 失败且有 fallback 标志，fallback 到规则规划器
        if self.fallback_on_error:
            logger.info(
                "nl2sql_sqlplan_planner_fallback_to_rule question=%s", text[:50]
            )
            try:
                return self._rule_planner.build_plan(text)
            except InventorySalesProductionPlanningError:
                raise
            except Exception:
                raise InventorySalesProductionPlanningError(
                    "unsupported",
                    "当前规划器暂时不可用，请稍后重试。",
                )

        # 无 fallback 时，LLM 失败直接向上传播
        raise InventorySalesProductionPlanningError(
            "unsupported",
            "LLM 完整 SQLPlan 规划器当前不可用，请稍后重试或联系管理员。",
        )

    def build_plan_with_debug(
        self,
        question: str,
    ) -> tuple[InventorySalesProductionQueryPlan, dict[str, Any]]:
        """同 build_plan()，额外返回调试信息（用于 shadow 对比和测试）。

        参数：
            question: 用户自然语言问题。
        返回：
            (InventorySalesProductionQueryPlan, debug_info) 元组。
            debug_info 包含：
                - mode: "llm_sqlplan" | "fallback_rule" | "fallback_error"
                - sqlplan_candidate: LLM 原始 SqlPlanCandidate（仅 llm_sqlplan 模式）
                - validation_result: 校验结果（仅 llm_sqlplan 模式）
                - rule_plan: 规则规划器结果（仅 fallback 模式）
        """
        text = (question or "").strip()
        if not text:
            raise InventorySalesProductionPlanningError(
                "clarification", "请补充要查询的产销存问题。"
            )

        # LLM 路径
        api_key = self.llm_api_key
        if not api_key:
            # 从 settings 获取
            from backend.app.core.config import get_settings
            settings = get_settings()
            api_key = settings.llm_api_key

        if api_key:
            try:
                from openai import OpenAI

                client = OpenAI(
                    api_key=api_key,
                    base_url=self.llm_base_url or "",
                )
                prompt = _build_sqlplan_system_prompt(self.catalog)
                response = client.chat.completions.create(
                    model=self.llm_model or "qwen-max",
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": text},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=2048,
                    timeout=self.timeout,
                )
                content = response.choices[0].message.content or ""
                result_dict = json.loads(content)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "nl2sql_sqlplan_llm_failed question=%s", text[:50],
                    exc_info=True,
                )
                result_dict = {"strategy": "unsupported"}

            # 解析并校验
            candidate, validation = self._validate_sqlplan(result_dict)
            if candidate is not None and validation is not None and validation.ok:
                qp = self._sqlplan_to_query_plan(candidate, text)
                if qp is not None:
                    return qp, {
                        "mode": "llm_sqlplan",
                        "sqlplan_candidate": candidate.model_dump(mode="json"),
                        "validation_result": validation.model_dump(mode="json"),
                    }

            # LLM 成功但校验失败，也做记录
            if validation is not None and not validation.ok:
                logger.info(
                    "nl2sql_sqlplan_validation_failed errors=%s",
                    validation.errors[:5],
                )

        # fallback 路径
        if self.fallback_on_error:
            try:
                rule_plan = self._rule_planner.build_plan(text)
                return rule_plan, {
                    "mode": "fallback_rule",
                }
            except InventorySalesProductionPlanningError:
                raise
            except Exception:
                raise InventorySalesProductionPlanningError(
                    "unsupported",
                    "当前规划器暂时不可用，请稍后重试。",
                )

        raise InventorySalesProductionPlanningError(
            "unsupported",
            "LLM 完整 SQLPlan 规划器当前不可用，请稍后重试或联系管理员。",
        )

    def _try_llm_sqlplan(
        self, question: str
    ) -> InventorySalesProductionQueryPlan | None:
        """尝试使用 LLM 生成完整 SQLPlan 并校验后转换为 QueryPlan。

        参数：
            question: 用户问题。
        返回：
            QueryPlan（成功）或 None（需要澄清/不支持/异常/校验失败）。
        """
        api_key = self.llm_api_key
        if not api_key:
            # 从 settings 获取
            from backend.app.core.config import get_settings

            settings = get_settings()
            api_key = settings.llm_api_key

        if not api_key:
            logger.warning("nl2sql_sqlplan_no_api_key return_fallback")
            return None

        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=api_key,
                base_url=self.llm_base_url or "",
            )
            prompt = _build_sqlplan_system_prompt(self.catalog)
            response = client.chat.completions.create(
                model=self.llm_model or "qwen-max",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": question},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=2048,
                timeout=self.timeout,
            )
            content = response.choices[0].message.content or ""
            result_dict = json.loads(content)
        except Exception:  # noqa: BLE001
            logger.warning(
                "nl2sql_sqlplan_llm_failed question=%s", question[:50],
                exc_info=True,
            )
            return None

        # 检查 LLM 自身的策略决定（clarify/unsupported）
        if (
            result_dict.get("strategy") == "clarify"
            or result_dict.get("clarification_questions")
        ):
            logger.info(
                "nl2sql_sqlplan_clarify question=%s", question[:50],
            )
            return None

        if (
            result_dict.get("strategy") == "unsupported"
            or result_dict.get("unsupported_reason")
        ):
            logger.info(
                "nl2sql_sqlplan_unsupported question=%s reason=%s",
                question[:50],
                result_dict.get("unsupported_reason", "unknown"),
            )
            return None

        # 校验 SQLPlan candidate
        candidate, validation = self._validate_sqlplan(result_dict)
        if candidate is None or validation is None or not validation.ok:
            logger.info(
                "nl2sql_sqlplan_validation_failed question=%s errors=%s",
                question[:50],
                validation.errors[:5] if validation else "parse_failed",
            )
            return None

        # 转换为 QueryPlan
        qp = self._sqlplan_to_query_plan(candidate, question)
        if qp is None:
            return None

        return qp

    def _validate_sqlplan(
        self, result_dict: dict[str, Any]
    ) -> tuple[InventorySalesProductionSqlPlanCandidate | None, Any] | tuple[
        None, None
    ]:
        """解析 LLM 输出的字典并用 SqlPlanValidator 校验。

        参数：
            result_dict: LLM 输出的 JSON 字典。
        返回：
            (InventorySalesProductionSqlPlanCandidate, ValidationResult) 或 (None, None)。
        """
        try:
            candidate = InventorySalesProductionSqlPlanCandidate.model_validate(
                result_dict
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "nl2sql_sqlplan_parse_failed payload_keys=%s",
                list(result_dict.keys()),
            )
            return None, None

        # 校验
        validator = InventorySalesProductionSqlPlanValidator(
            catalog=self.catalog,
        )
        validation = validator.validate(candidate)
        return candidate, validation

    @staticmethod
    def _sqlplan_to_query_plan(
        candidate: InventorySalesProductionSqlPlanCandidate,
        question: str,
    ) -> InventorySalesProductionQueryPlan | None:
        """将校验通过的 SqlPlanCandidate 转换为 InventorySalesProductionQueryPlan。

        参数：
            candidate: 校验通过的 SQLPlan Candidate。
            question: 原始用户问题（仅用于日志）。
        返回：
            InventorySalesProductionQueryPlan，或转换失败返回 None。
        """
        plan = candidate.plan

        # 过滤条件转换：从 SqlPlanFilter 列表转换为 filters dict
        filters_dict: dict[str, list[Any]] = {}
        for f in plan.filters:
            if f.dimension not in filters_dict:
                filters_dict[f.dimension] = []
            filters_dict[f.dimension].extend(f.values)

        # 确定 intent
        intent = _resolve_intent(plan.query_key)

        # 构建 PeriodSpec
        period = InventorySalesProductionPeriodSpec(
            period_type=plan.period_type,
            year=plan.year,
            month=plan.month,
            quarter=plan.quarter,
            start_month=plan.start_month,
            end_month=plan.end_month,
        )

        # 确定 calculation_policy
        calc_policy = plan.calculation_policy

        return InventorySalesProductionQueryPlan(
            query_key=plan.query_key,
            intent=intent,
            metrics=list(plan.metrics),
            dimensions=list(plan.dimensions),
            filters=filters_dict,
            period=period,
            calculation_policy=calc_policy,
            display_preference="business_chat",
        )


def _resolve_intent(query_key: str) -> str:
    """将 query_key 映射为 intent 字符串。

    参数：
        query_key: 查询 key。
    返回：
        intent 字符串。
    """
    intent_map = {
        "ba_isp_metric_summary": "metric_summary",
        "ba_isp_metric_breakdown": "metric_breakdown",
        "ba_isp_metric_trend": "metric_trend",
        "ba_isp_budget_achievement": "budget_achievement",
        "ba_isp_inventory_snapshot": "inventory_snapshot",
        "ba_isp_period_compare": "period_compare",
    }
    return intent_map.get(query_key, "metric_query")


__all__ = [
    "InventorySalesProductionNl2SqlSqlPlanPlanner",
]

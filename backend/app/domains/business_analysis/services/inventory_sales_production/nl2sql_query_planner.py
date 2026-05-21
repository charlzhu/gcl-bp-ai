from __future__ import annotations

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

logger = logging.getLogger(__name__)


class InventorySalesProductionNl2SqlQueryPlanner:
    """产销存 NL2SQL QueryPlan 规划器（S3：LLM Metric Resolution 规划器）。

    业务定位：
        1. 实现与 InventorySalesProductionNlQueryPlanner 相同的 build_plan(question) 接口；
        2. 内部使用 S2 LLM Catalog Recall 服务进行指标/维度/期间解析；
        3. LLM 只输出结构化 CatalogRecallResult（指标、维度、query_key、期间），不输出 SQL；
        4. 通过 recall_to_query_plan 转换为现有 InventorySalesProductionQueryPlan；
        5. LLM 失败或返回 clarification/unsupported 时，自动 fallback 到规则规划器；
        6. 下游执行器、聚合策略、安全校验不变——NL2SQL 只替换规划层。

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
    def catalog(self) -> object:
        """延迟加载 Semantic Catalog，避免构造函数中的循环导入。"""
        if not self._catalog_loaded:
            if self._catalog is None:
                from backend.app.domains.business_analysis.services.inventory_sales_production.semantic_catalog import (
                    InventorySalesProductionSemanticCatalogLoader,
                )
                self._catalog = InventorySalesProductionSemanticCatalogLoader().load()
            self._catalog_loaded = True
        return self._catalog

    def build_plan(self, question: str) -> InventorySalesProductionQueryPlan:
        """将用户自然语言问题转换为产销存受控 QueryPlan。

        参数：
            question: 用户自然语言问题。
        返回：
            InventorySalesProductionQueryPlan。
        异常：
            InventorySalesProductionPlanningError: LLM 和规则规划器都失败时抛出。
        """
        text = (question or "").strip()
        if not text:
            raise InventorySalesProductionPlanningError("clarification", "请补充要查询的产销存问题。")

        # 第一步：尝试 LLM Catalog Recall
        llm_plan = self._try_llm_plan(text)
        if llm_plan is not None:
            logger.info("nl2sql_planner_llm_mode question=%s", text[:50])
            return llm_plan

        # 第二步：若 LLM 失败且有 fallback_on_error 标志，fallback 到规则规划器
        if self.fallback_on_error:
            logger.info("nl2sql_planner_fallback_to_rule question=%s", text[:50])
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
            "LLM 规划器当前不可用，请稍后重试或联系管理员。",
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
                - mode: "llm" | "fallback_rule" | "fallback_error"
                - recall_result: LLM 原始结果（仅 llm 模式）
                - rule_plan: 规则规划器结果（仅 fallback 模式）
        """
        text = (question or "").strip()
        if not text:
            raise InventorySalesProductionPlanningError("clarification", "请补充要查询的产销存问题。")

        # LLM 路径
        recall_svc = self._build_recall_service()
        recall_result = recall_svc.recall(text)

        if (
            recall_result is not None
            and not recall_result.clarification_needed
            and not recall_result.unsupported_reason
            and recall_result.metric_code
            and recall_result.query_key
            and recall_result.year
        ):
            qp = self._recall_result_to_plan(recall_result, text)
            if qp is not None:
                return qp, {
                    "mode": "llm",
                    "recall_result": recall_result.model_dump(mode="json"),
                }

        # fallback 路径
        if self.fallback_on_error:
            try:
                rule_plan = self._rule_planner.build_plan(text)
                return rule_plan, {
                    "mode": "fallback_rule",
                    "recall_result": recall_result.model_dump(mode="json") if recall_result else None,
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
            "LLM 规划器当前不可用，请稍后重试或联系管理员。",
        )

    def _try_llm_plan(self, question: str) -> InventorySalesProductionQueryPlan | None:
        """尝试使用 LLM Catalog Recall 生成 QueryPlan。

        参数：
            question: 用户问题。
        返回：
            QueryPlan（成功）或 None（需要澄清/不支持/异常）。
        """
        try:
            recall_svc = self._build_recall_service()
            result = recall_svc.recall(question)
            if result is None:
                return None
            # 使用本类方法来转换，确保 period_compare 等逻辑正确处理
            return self._recall_result_to_plan(result, question)
        except Exception:  # noqa: BLE001
            logger.warning("nl2sql_planner_llm_failed question=%s", question[:50], exc_info=True)
            return None

    def _build_recall_service(self) -> object:
        """构建 Catalog Recall 服务实例（延迟导入避免循环依赖）。"""
        from backend.app.domains.business_analysis.services.inventory_sales_production.nl2sql_catalog_recall_service import (
            InventorySalesProductionCatalogRecallService,
        )

        return InventorySalesProductionCatalogRecallService(
            catalog=self._catalog,  # type: ignore[arg-type]
            model=self.llm_model,
            base_url=self.llm_base_url,
            api_key=self.llm_api_key,
            timeout=self.timeout,
        )

    @staticmethod
    def _recall_result_to_plan(
        result: object,
        question: str,
    ) -> InventorySalesProductionQueryPlan | None:
        """将 recall 结果转换为 QueryPlan。

        参数：
            result: LLM Catalog Recall 结构化结果（InventorySalesProductionCatalogRecallResult）。
            question: 原始用户问题（用于消歧）。
        返回：
            QueryPlan 或 None。
        """
        # 延迟导入避免循环依赖
        from backend.app.domains.business_analysis.services.inventory_sales_production.nl2sql_catalog_recall_service import (
            InventorySalesProductionCatalogRecallResult,
        )

        if not isinstance(result, InventorySalesProductionCatalogRecallResult):
            return None
        if result.clarification_needed or result.unsupported_reason:
            return None
        if not result.metric_code or not result.query_key or not result.year:
            return None

        period = InventorySalesProductionPeriodSpec(
            period_type=(result.period_type or "year"),  # type: ignore[arg-type]
            year=result.year,
            month=result.month,
            quarter=result.quarter,
            start_month=result.start_month,
            end_month=result.end_month,
        )

        # 处理同比/环比/月区间：确保维度包含 business_month
        dimensions = list(result.dimensions)
        if result.query_key == "ba_isp_period_compare" and "business_month" not in dimensions:
            dimensions.append("business_month")

        return InventorySalesProductionQueryPlan(
            query_key=result.query_key,  # type: ignore[arg-type]
            intent="nl2sql_recall",
            metrics=[result.metric_code],
            dimensions=dimensions,
            filters={},
            period=period,
            calculation_policy=None,
            display_preference="business_chat",
        )


__all__ = ["InventorySalesProductionNl2SqlQueryPlanner"]

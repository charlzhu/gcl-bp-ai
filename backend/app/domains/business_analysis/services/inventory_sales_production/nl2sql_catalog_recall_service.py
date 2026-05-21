from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.config import get_settings
from backend.app.domains.business_analysis.schemas.inventory_sales_production_query import (
    InventorySalesProductionPeriodSpec,
    InventorySalesProductionQueryPlan,
    InventorySalesProductionPeriodType,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.semantic_catalog import (
    InventorySalesProductionSemanticCatalog,
    InventorySalesProductionSemanticCatalogLoader,
    ISP_SUPPORTED_QUERY_KEYS,
)

logger = logging.getLogger(__name__)

# S2: LLM Semantic Catalog Recall —— 结构化输出模型
# LLM 只输出指标、维度、query_key、期间，不输出 SQL


class InventorySalesProductionCatalogRecallResult(BaseModel):
    """LLM Catalog Recall 的结构化输出。"""

    model_config = ConfigDict(extra="forbid")

    metric_code: str | None = None
    query_key: str | None = None
    dimensions: list[str] = Field(default_factory=list)
    year: int | None = None
    period_type: str | None = None
    month: int | None = None
    quarter: int | None = None
    start_month: int | None = None
    end_month: int | None = None
    clarification_needed: str | None = None
    unsupported_reason: str | None = None


# Prompt 模板：将 S1 增强后的 Catalog 描述注入给 LLM
_CATALOG_RECALL_SYSTEM_PROMPT = """你是一个产销存经营分析智能助手的数据查询规划器。
你的任务是将用户的自然语言问题解析为受控的查询计划，不能生成 SQL。

业务域：产销存经营分析（business_analysis / inventory_sales_production）
支持的期间类型：year（全年）、quarter（季度）、month（单月）、ytd（年初至某月累计）、month_range（月份区间）

支持的查询能力（query_key）及规则：
{query_key_rules}

可查询的指标列表（metric_code - 指标名称 - 业务说明）：
{metrics_desc}

可查询的维度列表（dimension_id - 维度名称 - 说明/示例）：
{dimensions_desc}

业务规则：
- 用户说"销量"、"销售量"、"发货量"、"卖了多少"、"出货量" 都映射到 shipment_volume
- 用户说"库存"、"存货" 都映射到 ending_inventory_volume
- 用户说"寄存" 映射到 consigned_inventory_volume
- 用户说"开票" 映射到 invoice_sales_volume（需要开票说明）
- 2024年销量默认采用 shipment_external_excluding_internal（剔除内部交易）
- 开票销量必须用户明确说"开票"才使用
- 库存周转率/周转率/平均库存当前不支持，设为 unsupported

输出 JSON 格式（严格按此结构）：
{{
  "metric_code": "shipment_volume",
  "query_key": "ba_isp_metric_summary",
  "dimensions": [],
  "year": 2025,
  "period_type": "year",
  "month": null,
  "quarter": null,
  "start_month": null,
  "end_month": null,
  "clarification_needed": null,
  "unsupported_reason": null
}}

关键规则：
- 无法确定指标时设置 clarification_needed
- 明确不支持的设置 unsupported_reason
- 不要编造不存在的 metric_code 或 query_key
- 用户没写明具体年份时，clarification_needed 提示补充年份
"""


def _build_query_key_rules_text() -> str:
    """从 SUPPORTED_QUERY_KEYS 构建 query_key 说明文本。"""
    lines = []
    for qk in ISP_SUPPORTED_QUERY_KEYS:
        desc = _QUERY_KEY_DESCRIPTIONS.get(qk, "")
        lines.append(f"  - {qk}: {desc}")
    return "\n".join(lines)


_QUERY_KEY_DESCRIPTIONS: dict[str, str] = {
    "ba_isp_metric_summary": "单指标汇总，适用于年度/季度/月度等单期间汇总查询。无维度拆分。",
    "ba_isp_metric_breakdown": "单指标按维度拆分，用户说按基地、各基地、按版型时使用。",
    "ba_isp_metric_trend": "趋势查询，用户说趋势、按月、每月时使用，按月份展开。",
    "ba_isp_budget_achievement": "预算达成率计算，需要产量和预算两个指标。",
    "ba_isp_inventory_snapshot": "库存/寄存等时点指标快照，取期末值。",
    "ba_isp_period_compare": "期间对比，用于同比、环比、月份区间查询，按月份展开。",
}


class InventorySalesProductionCatalogRecallService:
    """LLM Semantic Catalog Recall 服务。

    说明：
        1. 接收用户自然语言问题，通过 LLM 召回 Catalog 中的指标和维度；
        2. 输出 InventorySalesProductionCatalogRecallResult，不生成 SQL；
        3. 与现有 nl_query_planner.py 同接口，可互换。
    """

    def __init__(
        self,
        *,
        catalog: InventorySalesProductionSemanticCatalog | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        settings = get_settings()
        self.catalog = catalog or InventorySalesProductionSemanticCatalogLoader().load()
        self.model = model or settings.llm_model or "qwen-max"
        self.base_url = base_url or settings.llm_base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.api_key = api_key or settings.llm_api_key
        self.timeout = timeout

    def recall(self, question: str) -> InventorySalesProductionCatalogRecallResult:
        """执行 LLM Catalog Recall。

        参数：
            question: 用户自然语言问题。
        返回：
            InventorySalesProductionCatalogRecallResult；LLM 异常或 timeout 时返回 fallback 空结果。
        """

        if not self.api_key:
            logger.warning("isp_catalog_recall_no_api_key return_fallback")
            return InventorySalesProductionCatalogRecallResult(
                clarification_needed="LLM 服务未配置，请补充API Key。"
            )

        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            system_prompt = self._build_prompt()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=1024,
                timeout=self.timeout,
            )
            content = response.choices[0].message.content or ""
            result_dict = json.loads(content)
            return InventorySalesProductionCatalogRecallResult.model_validate(result_dict)
        except Exception as exc:  # noqa: BLE001
            logger.warning("isp_catalog_recall_failed reason=%s", exc)
            return InventorySalesProductionCatalogRecallResult(
                clarification_needed="LLM 召回服务暂时不可用，请稍后重试。",
            )

    def recall_to_query_plan(self, question: str) -> InventorySalesProductionQueryPlan | None:
        """将 LLM Catalog Recall 结果转换为受控 QueryPlan。

        参数：
            question: 用户自然语言问题。
        返回：
            成功后返回 InventorySalesProductionQueryPlan，失败时返回 None（调用方应 fallback）。
        """

        result = self.recall(question)
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
        return InventorySalesProductionQueryPlan(
            query_key=result.query_key,  # type: ignore[arg-type]
            intent=self._resolve_intent(result.query_key),
            metrics=[result.metric_code],
            dimensions=list(result.dimensions),
            filters={},
            period=period,
            calculation_policy=None,
            display_preference="business_chat",
        )

    def _build_prompt(self) -> str:
        """构建包含 S1 Catalog NL 描述的 System Prompt。"""

        metrics_lines = []
        for metric in self.catalog.metrics:
            nl_desc = metric.nl_description or metric.business_note or ""
            examples = ""
            if metric.example_questions:
                examples = " 示例问法: " + "、".join(metric.example_questions[:3])
            metrics_lines.append(f"  {metric.metric_id} - {metric.display_name}: {nl_desc}{examples}")

        dims_lines = []
        for dim in self.catalog.dimensions:
            nl_desc = dim.nl_description or ""
            values = ""
            if dim.example_values:
                values = " 取值示例: " + ", ".join(dim.example_values[:6])
            dims_lines.append(f"  {dim.dimension_id} - {dim.display_name}: {nl_desc}{values}")

        return _CATALOG_RECALL_SYSTEM_PROMPT.format(
            query_key_rules=_build_query_key_rules_text(),
            metrics_desc="\n".join(metrics_lines),
            dimensions_desc="\n".join(dims_lines),
        )

    @staticmethod
    def _resolve_intent(query_key: str) -> str:
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
    "InventorySalesProductionCatalogRecallResult",
    "InventorySalesProductionCatalogRecallService",
]

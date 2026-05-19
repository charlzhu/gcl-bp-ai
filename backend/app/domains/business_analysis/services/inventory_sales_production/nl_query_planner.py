from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from backend.app.domains.business_analysis.schemas.inventory_sales_production_query import (
    InventorySalesProductionPeriodSpec,
    InventorySalesProductionQueryPlan,
)


@dataclass(slots=True)
class InventorySalesProductionPlanningError(Exception):
    """产销存自然语言规划错误。

    参数：
        status: clarification 或 unsupported，用于 QA 服务转换为业务状态。
        message: 用户可见的业务化说明。
    返回：
        作为异常抛出，表示不能安全生成受控 QueryPlan。
    """

    status: str
    message: str


class InventorySalesProductionNlQueryPlanner:
    """产销存自然语言到受控 QueryPlan 的临时生成器。

    业务定位：
        1. M4 紧急接入阶段只做最小意图、期间和指标归一；
        2. 输出必须是 InventorySalesProductionQueryPlan，不输出 SQL；
        3. 后续统一 NL2SQL 成熟后，可用模型规划器替换本类，但下游 M3 Executor 合同不变；
        4. 不支持或数据口径缺失的问题必须 fail closed，不能编造业务结果。
    """

    _YEAR_PATTERN = re.compile(r"(?<!\d)(20\d{2}|2[3-9])\s*年?")
    _MONTH_PATTERN = re.compile(r"(?<!\d)(1[0-2]|[1-9])\s*月")
    _QUARTER_PATTERN = re.compile(r"(?:Q|q|第)\s*([1-4])\s*(?:季度|季)?")

    def build_plan(self, question: str) -> InventorySalesProductionQueryPlan:
        """将用户问题转换为产销存受控 QueryPlan。

        参数：question 用户自然语言问题。
        返回：InventorySalesProductionQueryPlan，可交给 M3 执行器校验和执行。
        """

        text = (question or "").strip()
        if not text:
            raise InventorySalesProductionPlanningError("clarification", "请补充要查询的产销存问题。")
        normalized = self._normalize_text(text)
        self._reject_known_unsupported(normalized)

        year = self._extract_year(normalized)
        period = self._extract_period(normalized, year)
        metric_code, query_key, filters = self._resolve_metric_and_query_key(normalized)
        dimensions = self._resolve_dimensions(normalized)
        metric_code = self._adapt_metric_for_dimensions(metric_code, dimensions)
        if dimensions and query_key == "ba_isp_metric_summary":
            query_key = "ba_isp_metric_breakdown"
        if "趋势" in normalized or "按月" in normalized or "每月" in normalized:
            query_key = "ba_isp_metric_trend"
            if "business_month" not in dimensions:
                dimensions.append("business_month")

        return InventorySalesProductionQueryPlan(
            query_key=query_key,  # type: ignore[arg-type]
            intent=self._resolve_intent(query_key),
            metrics=[metric_code],
            dimensions=dimensions,
            filters=filters,
            period=period,
            calculation_policy=None,
            display_preference="business_chat",
        )

    @staticmethod
    def _normalize_text(question: str) -> str:
        """归一化问题文本，保留中文业务词。"""

        return question.strip().replace("２", "2").replace("４", "4").replace("０", "0").lower()

    def _extract_year(self, text: str) -> int:
        """提取业务年份；未给年份时要求用户补充，避免经营分析跨年口径误用。"""

        if "今年" in text or "当前" in text or "本年" in text:
            return date.today().year
        match = self._YEAR_PATTERN.search(text)
        if not match:
            raise InventorySalesProductionPlanningError("clarification", "请补充要查询的业务年份，例如 2024 年或 2026 年 4 月。")
        raw_year = match.group(1)
        if len(raw_year) == 2:
            return 2000 + int(raw_year)
        return int(raw_year)

    def _extract_period(self, text: str, year: int) -> InventorySalesProductionPeriodSpec:
        """提取月度、季度、年度或当前累计期间。"""

        month_match = self._MONTH_PATTERN.search(text)
        if month_match:
            return InventorySalesProductionPeriodSpec(period_type="month", year=year, month=int(month_match.group(1)))
        quarter_match = self._QUARTER_PATTERN.search(text)
        if quarter_match:
            return InventorySalesProductionPeriodSpec(period_type="quarter", year=year, quarter=int(quarter_match.group(1)))
        if "累计" in text or "截至" in text or "到现在" in text:
            return InventorySalesProductionPeriodSpec(period_type="ytd", year=year)
        return InventorySalesProductionPeriodSpec(period_type="year", year=year)

    def _resolve_metric_and_query_key(self, text: str) -> tuple[str, str, dict[str, object]]:
        """识别主指标和查询能力。"""

        filters: dict[str, object] = {}
        if "预算达成" in text or "达成率" in text:
            return "production_actual_including_oem", "ba_isp_budget_achievement", filters
        if "寄存" in text:
            return "consigned_inventory_volume", "ba_isp_inventory_snapshot", filters
        if "库存" in text or "存货" in text:
            return "ending_inventory_volume", "ba_isp_inventory_snapshot", filters
        if "开票" in text:
            filters["explicit_invoice"] = True
            return "invoice_sales_volume", "ba_isp_metric_summary", filters
        if "销量" in text or "销售量" in text or "发货量" in text or "发货" in text:
            return "shipment_volume", "ba_isp_metric_summary", filters
        if "产量" in text or "产出" in text:
            return "production_actual_including_oem", "ba_isp_metric_summary", filters
        raise InventorySalesProductionPlanningError(
            "clarification",
            "请说明要查询的产销存指标，例如产量、销量、库存、寄存或预算达成率。",
        )

    @staticmethod
    def _resolve_dimensions(text: str) -> list[str]:
        """识别白名单拆分维度。"""

        dimensions: list[str] = []
        if "各基地" in text or "按基地" in text or "分基地" in text:
            dimensions.append("base_name")
        if "按版型" in text or "各版型" in text:
            dimensions.append("model_type")
        return dimensions

    @staticmethod
    def _adapt_metric_for_dimensions(metric_code: str, dimensions: list[str]) -> str:
        """根据拆分维度切换到已有拆分指标。

        说明：M2/M3 指标目录里部分拆分指标是独立编码；这里仅做指标白名单内的编码切换，
        不拼接字段名、不生成 SQL。
        """

        if "base_name" not in dimensions:
            return metric_code
        mapping = {
            "shipment_volume": "shipment_by_base",
            "production_actual_including_oem": "production_by_base",
            "ending_inventory_volume": "ending_inventory_by_base",
            "consigned_inventory_volume": "consigned_inventory_by_base",
        }
        return mapping.get(metric_code, metric_code)

    @staticmethod
    def _resolve_intent(query_key: str) -> str:
        """生成仅供审计的意图标签。"""

        intent_by_key = {
            "ba_isp_metric_summary": "metric_summary",
            "ba_isp_metric_breakdown": "metric_breakdown",
            "ba_isp_metric_trend": "metric_trend",
            "ba_isp_budget_achievement": "budget_achievement",
            "ba_isp_inventory_snapshot": "inventory_snapshot",
        }
        return intent_by_key.get(query_key, "metric_query")

    @staticmethod
    def _reject_known_unsupported(text: str) -> None:
        """阻断当前 Excel 数据不足的问题，避免系统编造公式结果。"""

        if "库存周转" in text or "周转率" in text or "平均库存" in text:
            raise InventorySalesProductionPlanningError(
                "clarification",
                "库存周转率需要平均库存、销货成本或业务确认的周转公式；当前产销存文件数据不足，请补充口径后再查询。",
            )


__all__ = ["InventorySalesProductionNlQueryPlanner", "InventorySalesProductionPlanningError"]

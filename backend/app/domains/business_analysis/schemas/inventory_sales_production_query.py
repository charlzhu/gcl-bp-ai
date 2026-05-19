from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

InventorySalesProductionQueryKey = Literal[
    "ba_isp_metric_summary",
    "ba_isp_metric_breakdown",
    "ba_isp_metric_trend",
    "ba_isp_budget_achievement",
    "ba_isp_inventory_snapshot",
    "ba_isp_period_compare",
]
InventorySalesProductionPeriodType = Literal["month", "quarter", "year", "ytd"]
InventorySalesProductionResultStatus = Literal["success", "empty_result", "clarification", "unsupported", "error"]


class InventorySalesProductionPeriodSpec(BaseModel):
    """产销存 QueryPlan 期间规格。

    参数：
        period_type: 期间类型，支持月、季度、全年、年初至今。
        year: 业务年份。
        month: period_type=month 时的月份。
        quarter: period_type=quarter 时的季度。
        start_month/end_month: ytd 或自定义期间的起止月份，MVP 主要使用 end_month。
    返回：
        可被执行器确定性展开为已发布月份列表的期间对象。
    """

    model_config = ConfigDict(extra="forbid")

    period_type: InventorySalesProductionPeriodType
    year: int
    month: int | None = None
    quarter: int | None = None
    start_month: int | None = None
    end_month: int | None = None

    @model_validator(mode="after")
    def validate_period_shape(self) -> "InventorySalesProductionPeriodSpec":
        """校验期间基础形状。

        业务逻辑：这里只做结构合法性；是否已发布、是否有数据由执行器结合中间库判断。
        """

        if self.year < 2020 or self.year > 2100:
            raise ValueError("业务年份超出合理范围")
        month_values = [self.month, self.start_month, self.end_month]
        for value in month_values:
            if value is not None and (value < 1 or value > 12):
                raise ValueError("月份必须在 1-12 之间")
        if self.quarter is not None and self.quarter not in {1, 2, 3, 4}:
            raise ValueError("季度必须在 1-4 之间")
        if self.period_type == "month" and self.month is None:
            raise ValueError("月度查询必须提供 month")
        if self.period_type == "quarter" and self.quarter is None:
            raise ValueError("季度查询必须提供 quarter")
        if self.start_month is not None and self.end_month is not None and self.start_month > self.end_month:
            raise ValueError("起始月份不能晚于结束月份")
        return self


class InventorySalesProductionQueryPlan(BaseModel):
    """产销存受控 QueryPlan。

    参数：
        domain/sub_domain: 固定经营分析产销存域，避免误接入物流/计划 BOM。
        query_key: 受控查询能力，不允许自由 SQL。
        intent: 上游语义意图快照，仅用于审计。
        metrics: 标准指标编码，MVP 每次只执行一个主指标。
        dimensions: 白名单拆分维度。
        filters: 受控过滤条件，不承载 SQL 片段。
        period: 查询期间。
        calculation_policy: 上游建议聚合策略；执行器仍以指标维表和后端策略为准。
        display_preference: 展示偏好，M3 不驱动前端。
    返回：
        可被 M3 执行器校验并执行的 QueryPlan。
    """

    model_config = ConfigDict(extra="forbid")

    domain: str = "business_analysis"
    sub_domain: str = "inventory_sales_production"
    query_key: InventorySalesProductionQueryKey
    intent: str | None = None
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    period: InventorySalesProductionPeriodSpec
    calculation_policy: str | None = None
    display_preference: str | None = None

    @model_validator(mode="after")
    def validate_minimal_contract(self) -> "InventorySalesProductionQueryPlan":
        """校验 QueryPlan 最小合同。

        业务逻辑：LLM/上游只能提交结构化计划；计划必须保留领域边界且至少包含一个指标。
        """

        if self.domain != "business_analysis":
            raise ValueError("产销存 QueryPlan domain 必须是 business_analysis")
        if self.sub_domain != "inventory_sales_production":
            raise ValueError("产销存 QueryPlan sub_domain 必须是 inventory_sales_production")
        if not self.metrics:
            raise ValueError("产销存 QueryPlan 必须包含 metrics")
        return self


class InventorySalesProductionQueryRow(BaseModel):
    """产销存查询结果行。

    参数：
        dimensions: 维度值，如基地/版型/月度。
        metric_code/metric_name: 实际执行的指标。
        value_decimal: 后端确定性计算结果。
        unit_standard: 标准单位。
        aggregation_type: 本行采用的聚合策略。
        months_covered: 实际覆盖的已发布月份。
        row_count: 参与聚合的事实行数。
        extra: 预算达成率等衍生指标的可审计补充事实。
    返回：
        用户回答和后续 NL2SQL shadow 对比可复用的结构化事实行。
    """

    model_config = ConfigDict(extra="forbid")

    dimensions: dict[str, Any] = Field(default_factory=dict)
    metric_code: str
    metric_name: str
    value_decimal: Decimal | None
    unit_standard: str
    aggregation_type: str
    months_covered: list[int] = Field(default_factory=list)
    row_count: int = 0
    extra: dict[str, Any] = Field(default_factory=dict)


class InventorySalesProductionQueryResult(BaseModel):
    """产销存 QueryPlan 执行结果。

    参数：
        status: 成功、空结果、澄清或不支持状态。
        answer_summary: 业务化摘要，不暴露表名、SQL、planner 等技术实现。
        rows: 结构化事实行。
        warnings: 业务口径提醒。
        calculation_policy: 实际采用的聚合策略。
        period_label: 期间标签。
        query_key: 执行的受控能力。
    返回：
        M3 后端确定性结果，可在 M4 接入问答展示。
    """

    model_config = ConfigDict(extra="forbid")

    status: InventorySalesProductionResultStatus
    answer_summary: str
    rows: list[InventorySalesProductionQueryRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    calculation_policy: str | None = None
    period_label: str | None = None
    query_key: str | None = None
    domain: str = "business_analysis"
    sub_domain: str = "inventory_sales_production"


__all__ = [
    "InventorySalesProductionPeriodSpec",
    "InventorySalesProductionQueryPlan",
    "InventorySalesProductionQueryResult",
    "InventorySalesProductionQueryRow",
]

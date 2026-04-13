from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# 与数据库/前端约定保持一致的查询来源枚举。
SourceScope = Literal["hist", "sys", "all"]
# 这里同时覆盖统计查询、明细查询和对比查询会用到的业务指标。
MetricType = Literal["shipment_watt", "shipment_count", "shipment_trip_count", "total_fee", "extra_fee"]
SortDirection = Literal["asc", "desc"]

_MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_MONTH_COMPACT_PATTERN = re.compile(r"^\d{6}$")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _normalize_month_token(value: str) -> str:
    """统一把月份输入收敛为 YYYY-MM，便于后续直接参与 SQL 条件拼装。"""
    raw = value.strip()
    if _MONTH_PATTERN.match(raw):
        return raw
    if _MONTH_COMPACT_PATTERN.match(raw):
        return f"{raw[:4]}-{raw[4:6]}"
    if _DATE_PATTERN.match(raw):
        return raw[:7]
    raise ValueError("月份格式必须为 YYYY-MM、YYYYMM 或 YYYY-MM-DD")


class LogisticsBaseFilter(BaseModel):
    """物流查询的公共过滤条件。

    这层模型被 aggregate/detail/compare 共同复用，目的是保证：
    1. 前端传参结构统一；
    2. repository 构造 SQL 时不需要再处理多套字段名；
    3. fallback 模式和数据库模式使用同一份业务过滤条件。
    """

    start_date: str | None = Field(default=None, description="YYYY-MM-DD")
    end_date: str | None = Field(default=None, description="YYYY-MM-DD")
    year_month_list: list[str] = Field(default_factory=list, description="如 ['2025-03', '2026-03']")

    customer_name: str | None = None
    logistics_company_name: str | None = None
    region_name: str | None = None
    warehouse_name: str | None = None
    transport_mode: str | None = None
    origin_place: str | None = None

    contract_no: str | None = None
    inquiry_no: str | None = None
    ship_instruction_no: str | None = None
    sap_order_no: str | None = None
    vehicle_no: str | None = None
    task_id: str | None = None
    product_spec: str | None = None

    metric_type: MetricType = Field(default="shipment_watt", description="默认运量口径按瓦数")
    source_scope: SourceScope = Field(default="all", description="hist/sys/all")

    @field_validator("year_month_list")
    @classmethod
    def normalize_year_month_list(cls, value: list[str]) -> list[str]:
        # 月份列表允许前端混传 YYYYMM / YYYY-MM / YYYY-MM-DD，统一转换后再入库查询。
        return [_normalize_month_token(item) for item in value if item and item.strip()]

    @field_validator("start_date", "end_date")
    @classmethod
    def normalize_dates(cls, value: str | None) -> str | None:
        if value is None:
            return value
        raw = value.strip()
        if _DATE_PATTERN.match(raw):
            return raw
        if _MONTH_PATTERN.match(raw):
            # 起止日期在只给到月份时，默认补成当月 1 号，由 repository 负责按日范围查询。
            return f"{raw}-01"
        raise ValueError("日期格式必须为 YYYY-MM-DD 或 YYYY-MM")


class LogisticsAggregateQuery(LogisticsBaseFilter):
    """统计查询模型。

    group_by/order_by 使用字符串是为了兼容前端配置化传参，
    真正进入 SQL 前会在 repository 中做白名单映射。
    """

    group_by: list[str] = Field(
        default_factory=lambda: ["biz_month"],
        description="可选: biz_year,biz_month,logistics_company_name,region_name,warehouse_name,transport_mode,origin_place,customer_name,source_type",
    )
    order_by: str | None = Field(default=None, description="同 group_by 或指标字段")
    order_direction: SortDirection = "desc"
    limit: int = Field(default=100, ge=1, le=1000)


class LogisticsDetailQuery(LogisticsBaseFilter):
    """明细查询模型。"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=500)
    order_by: str = Field(default="biz_date")
    order_direction: SortDirection = "desc"


class LogisticsCompareSide(BaseModel):
    """对比查询单侧的时间窗口定义。

    例如“2025Q1 vs 2026Q1”会拆成 left/right 两个 side。
    """

    label: str
    start_date: str | None = None
    end_date: str | None = None
    year_month_list: list[str] = Field(default_factory=list)

    @field_validator("year_month_list")
    @classmethod
    def normalize_year_month_list(cls, value: list[str]) -> list[str]:
        return [_normalize_month_token(item) for item in value if item and item.strip()]

    @field_validator("start_date", "end_date")
    @classmethod
    def normalize_dates(cls, value: str | None) -> str | None:
        if value is None:
            return value
        raw = value.strip()
        if _DATE_PATTERN.match(raw):
            return raw
        if _MONTH_PATTERN.match(raw):
            return f"{raw}-01"
        raise ValueError("日期格式必须为 YYYY-MM-DD 或 YYYY-MM")


class LogisticsCompareQuery(LogisticsBaseFilter):
    """跨时间窗/跨来源对比查询模型。"""

    left: LogisticsCompareSide
    right: LogisticsCompareSide
    compare_dim: str | None = Field(default=None, description="对比维度，可为空表示总量对比")


class LogisticsNLQuery(BaseModel):
    """规则版自然语言入口，只保留原始问题文本。"""

    question: str

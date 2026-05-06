from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping


# 历史物流 Excel 字段映射表：计算器只消费标准字段，避免在指标计算逻辑中写死原始中文列名。
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "biz_date": ("发货日期", "日期", "业务日期"),
    "biz_year": ("年份", "年度", "业务年份", "biz_year"),
    "biz_month": ("月度", "月份", "年月", "业务月份", "biz_month"),
    "shipment_watt": ("日实际发运瓦数", "实际发运瓦数", "发运瓦数", "运量", "瓦数", "shipment_watt"),
    "total_fee": ("总费用(元)", "总费用（元）", "总费用", "运费", "运输费用", "total_fee"),
    "shipment_trip_count": ("车辆数", "车次", "派车数", "shipment_trip_count"),
}

DECIMAL_FIELDS = {"shipment_watt", "total_fee", "shipment_trip_count"}


@dataclass(frozen=True)
class LogisticsExcelRow:
    """物流 Excel 标准行。

    参数：
        source_year：Excel 文件对应的业务年份。
        source_file：来源文件路径。
        row_no：Excel 中的数据行号。
        biz_year：业务年份。
        biz_month：业务月份，格式为 YYYY-MM。
        shipment_watt：运量，按瓦数口径。
        total_fee：总运费，单位元。
        shipment_trip_count：车次。
    返回值：无。
    """

    source_year: int
    source_file: str
    row_no: int
    biz_year: int | None
    biz_month: str | None
    shipment_watt: Decimal | None
    total_fee: Decimal | None
    shipment_trip_count: Decimal | None


def normalize_header(header: Any) -> str:
    """归一 Excel 表头。

    参数：
        header：原始表头值。
    返回值：
        去除空白后的表头文本。
    """

    if header is None:
        return ""
    text = str(header).replace("\r", "").replace("\n", "")
    return re.sub(r"\s+", "", text)


def build_alias_lookup() -> dict[str, str]:
    """构建原始表头到标准字段的映射。

    参数：无。
    返回值：
        归一后的原始表头 -> 标准字段。
    """

    lookup: dict[str, str] = {}
    for canonical, aliases in FIELD_ALIASES.items():
        lookup[normalize_header(canonical)] = canonical
        for alias in aliases:
            lookup[normalize_header(alias)] = canonical
    return lookup


def resolve_header_map(headers: list[Any]) -> dict[str, str]:
    """解析一个 Excel sheet 的表头映射。

    参数：
        headers：Excel 第一行表头列表。
    返回值：
        原始表头文本 -> 标准字段。
    """

    alias_lookup = build_alias_lookup()
    resolved: dict[str, str] = {}
    for header in headers:
        normalized = normalize_header(header)
        canonical = alias_lookup.get(normalized)
        if canonical:
            resolved[str(header)] = canonical
    return resolved


def clean_decimal(value: Any) -> Decimal | None:
    """清洗数值字段。

    参数：
        value：Excel 单元格值。
    返回值：
        Decimal 数值；无法解析时返回 None。
    """

    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    text = re.sub(r"(?i)(w|mw|元|车次|辆|%)", "", text).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def clean_date(value: Any) -> date | None:
    """清洗 Excel 日期。

    参数：
        value：Excel 日期单元格，可能是 datetime/date/序列号/字符串。
    返回值：
        date；无法解析时返回 None。

    业务逻辑：
        历史 Excel 常混用日期序列号和字符串日期，基础版只做常见格式兼容。
    """

    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and math.isnan(value):
            return None
        if 1 <= float(value) <= 60000:
            return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m", "%Y/%m"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def derive_year_month(mapped: Mapping[str, Any], *, source_year: int) -> tuple[int | None, str | None]:
    """推导业务年份和月份。

    参数：
        mapped：已映射到标准字段的行数据。
        source_year：当前 Excel 文件配置年份。
    返回值：
        (biz_year, biz_month)。
    """

    biz_date = clean_date(mapped.get("biz_date"))
    if biz_date:
        return biz_date.year, biz_date.strftime("%Y-%m")

    year_value = mapped.get("biz_year")
    month_value = mapped.get("biz_month")
    year = int(clean_decimal(year_value) or source_year)
    text = str(month_value or "").strip()
    if not text:
        return year, None

    full_match = re.search(r"(20\d{2})[-/年]?\s*(\d{1,2})", text)
    if full_match:
        parsed_year = int(full_match.group(1))
        parsed_month = int(full_match.group(2))
        return parsed_year, f"{parsed_year:04d}-{parsed_month:02d}"

    month_match = re.search(r"(\d{1,2})", text)
    if month_match:
        month = int(month_match.group(1))
        if 1 <= month <= 12:
            return year, f"{year:04d}-{month:02d}"
    return year, None


class LogisticsExcelFieldMapper:
    """物流 Excel 字段映射器。

    参数：无。
    返回值：无。

    业务逻辑：
        把不同年份 Excel 的中文表头统一映射为标准字段，后续计算器只依赖标准字段。
    """

    def map_row(
        self,
        raw_row: Mapping[str, Any],
        *,
        source_year: int,
        source_file: Path,
        row_no: int,
    ) -> LogisticsExcelRow:
        """映射单行 Excel 数据。

        参数：
            raw_row：原始 Excel 行。
            source_year：当前 Excel 文件配置年份。
            source_file：来源文件路径。
            row_no：Excel 行号。
        返回值：
            LogisticsExcelRow 标准行。
        """

        alias_lookup = build_alias_lookup()
        mapped: dict[str, Any] = {}
        for raw_key, raw_value in raw_row.items():
            canonical = alias_lookup.get(normalize_header(raw_key))
            if not canonical:
                continue
            mapped[canonical] = clean_decimal(raw_value) if canonical in DECIMAL_FIELDS else raw_value

        biz_year, biz_month = derive_year_month(mapped, source_year=source_year)
        return LogisticsExcelRow(
            source_year=source_year,
            source_file=str(source_file),
            row_no=row_no,
            biz_year=biz_year,
            biz_month=biz_month,
            shipment_watt=mapped.get("shipment_watt"),
            total_fee=mapped.get("total_fee"),
            shipment_trip_count=mapped.get("shipment_trip_count"),
        )

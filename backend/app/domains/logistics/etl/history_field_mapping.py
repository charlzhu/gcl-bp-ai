from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

# 历史 ETL 功能：表头归一到统一 DWD 字段，兼容不同 Excel 模板中的中文列名变体。
HEADER_ALIASES = {
    "发货日期": "biz_date",
    "客户名称（标准名称；最终客户）": "customer_name",
    "客户名称（标准名称；\\n最终客户）": "customer_name",
    "合同编号": "contract_no",
    "询比价编号": "inquiry_no",
    "发货指令": "ship_instruction_no",
    "SAP系统单号": "sap_order_no",
    "地址": "address",
    "省份": "province",
    "城市": "city",
    "路程/KM": "distance_km",
    "路程/km": "distance_km",
    "规格": "product_spec",
    "功率": "product_power",
    "日计划发运件数": "plan_qty",
    "日实际发运件数": "actual_qty",
    "日实际发运瓦数": "actual_watt",
    "发运达标率": "shipment_achieve_rate",
    "要求中标车辆型号": "required_vehicle_type",
    "每车装在托数": "pallet_per_vehicle",
    "车辆数": "shipment_trip_count",
    "车次": "shipment_trip_count",
    "车号": "vehicle_no",
    "物流公司": "logistics_company_name",
    "单价/车": "unit_price_per_vehicle",
    "总费用(元)": "total_fee",
    "总费用（元）": "total_fee",
    "元/瓦": "fee_per_watt",
    "异常费": "extra_fee",
    "额外费用": "extra_fee",
    "产生原因": "extra_fee_reason",
    "配件": "accessory_desc",
    "备注（倒运，中转等特殊情况）": "remark",
    "备注": "remark",
    "运输方式": "transport_mode",
    "区域": "region_name",
    "月度": "biz_month",
    "始发地": "origin_place",
}

RAW_FIELD_TRACK = {
    "车辆数": "raw_vehicle_field_name",
    "车次": "raw_vehicle_field_name",
    "异常费": "raw_extra_fee_field_name",
    "额外费用": "raw_extra_fee_field_name",
}

TEXT_FIELDS = {
    "customer_name",
    "contract_no",
    "inquiry_no",
    "ship_instruction_no",
    "sap_order_no",
    "address",
    "province",
    "city",
    "region_name",
    "origin_place",
    "transport_mode",
    "product_spec",
    "required_vehicle_type",
    "vehicle_no",
    "logistics_company_name",
    "extra_fee_reason",
    "accessory_desc",
    "remark",
    "raw_vehicle_field_name",
    "raw_extra_fee_field_name",
}

DECIMAL_FIELDS = {
    "distance_km",
    "product_power",
    "plan_qty",
    "actual_qty",
    "actual_watt",
    "shipment_achieve_rate",
    "pallet_per_vehicle",
    "shipment_trip_count",
    "unit_price_per_vehicle",
    "total_fee",
    "fee_per_watt",
    "extra_fee",
}


def normalize_header(header: Any) -> str:
    if header is None:
        return ""
    text = str(header)
    text = text.replace("\r", "").replace("\n", "\\n")
    return re.sub(r"\s+", "", text)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def clean_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    text = re.sub(r"(?i)(km|公里|元|mw|w|%)", "", text).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def clean_date(value: Any) -> date | None:
    """清洗日期。

    风险说明：
    1. 历史 Excel 可能混用字符串日期和 Excel serial；
    2. 如果日期格式完全不可识别，返回 `None` 由 service 决定是否跳过该行。
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
        # Excel serial date，常见于旧版 xls/xlsx。
        if 1 <= float(value) <= 60000:
            return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()
    text = clean_text(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m", "%Y/%m"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def derive_year_month(
    biz_date: date | None,
    month_value: Any,
    source_year: int,
) -> tuple[int | None, str | None]:
    if biz_date:
        return biz_date.year, biz_date.strftime("%Y-%m")
    text = clean_text(month_value)
    if not text:
        return source_year, None
    match = re.search(r"(20\d{2})[-/年]?(\d{1,2})", text)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        return year, f"{year:04d}-{month:02d}"
    month_match = re.search(r"(\d{1,2})", text)
    if month_match:
        month = int(month_match.group(1))
        return source_year, f"{source_year:04d}-{month:02d}"
    return source_year, None


def map_hist_row(raw_row: dict[str, Any], *, source_year: int) -> dict[str, Any]:
    """历史 ETL 功能：映射 Excel 字段至 DWD 标准字段。"""
    result: dict[str, Any] = {}
    for raw_key, raw_value in raw_row.items():
        key = normalize_header(raw_key)
        canonical = HEADER_ALIASES.get(key)
        if not canonical:
            continue
        if canonical in TEXT_FIELDS:
            result[canonical] = clean_text(raw_value)
        elif canonical in DECIMAL_FIELDS:
            result[canonical] = clean_decimal(raw_value)
        elif canonical == "biz_date":
            result[canonical] = clean_date(raw_value)
        else:
            result[canonical] = raw_value
        if key in RAW_FIELD_TRACK:
            result[RAW_FIELD_TRACK[key]] = key

    biz_year, biz_month = derive_year_month(result.get("biz_date"), raw_row.get("月度"), source_year)
    result["biz_year"] = biz_year
    result["biz_month"] = biz_month
    result["source_year"] = source_year
    return result

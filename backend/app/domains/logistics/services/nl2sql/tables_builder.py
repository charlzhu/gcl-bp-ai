from __future__ import annotations

from collections import OrderedDict
from typing import Any

from backend.app.domains.logistics.services.nl2sql.semantic_catalog import (
    LOGISTICS_NL2SQL_ALLOWED_READ_TABLES,
    LogisticsCatalogColumn,
    LogisticsCatalogTable,
)


LOGISTICS_NL2SQL_ALLOWED_TABLES = list(LOGISTICS_NL2SQL_ALLOWED_READ_TABLES)


TABLE_DISPLAY_NAMES = {
    "dws_logistics_detail_union": "物流明细统一服务表",
    "dws_logistics_monthly_metric": "物流月度指标服务表",
    "dwd_logistics_hist_shipment_detail": "历史物流发运明细表",
    "dwd_logistics_ship_task": "系统物流发运任务表",
    "dwd_logistics_ship_product": "系统物流发运产品表",
    "dwd_logistics_assign_task": "系统物流委派任务表",
    "dwd_logistics_assign_detail": "系统物流委派明细表",
    "dm_logistics_company_month_rank": "物流公司月度排行表",
}


def build_static_logistics_tables_catalog(rows: list[dict[str, Any]]) -> list[LogisticsCatalogTable]:
    """从库表探查行构造物流 NL2SQL 表 catalog。

    参数：
        rows: INFORMATION_SCHEMA.COLUMNS 风格的行列表，字段可为大小写混合。
    返回：
        仅包含智能助手中间库物流白名单表的 catalog 表声明。
    业务逻辑：
        M1 只允许查询中间库物流表；SAP MID、ODS 源表、未知表一律不进入 catalog。
    """

    allowed = set(LOGISTICS_NL2SQL_ALLOWED_TABLES)
    grouped: OrderedDict[str, list[LogisticsCatalogColumn]] = OrderedDict()
    for row in rows:
        table_name = str(_row_value(row, "table_name") or "")
        column_name = str(_row_value(row, "column_name") or "")
        if table_name not in allowed or not column_name:
            continue
        if table_name not in grouped:
            grouped[table_name] = []
        grouped[table_name].append(
            LogisticsCatalogColumn(
                name=column_name,
                data_type=str(_row_value(row, "data_type") or "unknown"),
                nullable=str(_row_value(row, "is_nullable") or "YES").upper() != "NO",
            )
        )

    result: list[LogisticsCatalogTable] = []
    for table_name in LOGISTICS_NL2SQL_ALLOWED_TABLES:
        columns = grouped.get(table_name)
        if not columns:
            continue
        result.append(
            LogisticsCatalogTable(
                table_name=table_name,
                display_name=TABLE_DISPLAY_NAMES.get(table_name, table_name),
                domain="logistics",
                source_system="middle_db",
                allowed_read=True,
                columns=columns,
            )
        )
    return result


def _row_value(row: dict[str, Any], key: str) -> Any | None:
    """兼容 INFORMATION_SCHEMA 大小写字段名。"""

    return row.get(key) or row.get(key.upper()) or row.get(key.lower())


__all__ = ["LOGISTICS_NL2SQL_ALLOWED_TABLES", "build_static_logistics_tables_catalog"]

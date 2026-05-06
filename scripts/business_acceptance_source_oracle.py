#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from backend.app.db.session import SessionLocal, SourceSessionLocal
from backend.app.domains.logistics.etl.history_field_mapping import map_hist_row
from scripts.business_acceptance_importer import write_json, write_markdown
from scripts.plan_bom_runtime import build_runtime_session, build_standardized_outputs, import_source_zip
from trial_sample_eval_common import extract_months, extract_years, now_iso, read_json
from trial_sample_expected_answer_builder import (
    _build_bom_expected,
    _build_hist_expected,
    _build_sys_expected,
    _clarification_expected,
    _is_2026_special_scope_mw_without_months,
    _is_complex_report_question,
    _should_default_to_history_years,
    _unsupported_expected,
)


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "tmp" / "business_acceptance_full"
DEFAULT_QUESTION_FILE = Path("/Users/zhuchangchao/Downloads/物流和 bom样例题.docx")
DEFAULT_LEDGER = PROJECT_ROOT / "tmp" / "trial_sample_eval" / "sample_question_ledger.json"
DEFAULT_HIST_ZIP = Path("/Users/zhuchangchao/Desktop/01_工作业务/计划经营部/业务计划/物流/23 年至 25 年物流源数据.zip")
DEFAULT_BOM_ZIP = Path("/Users/zhuchangchao/Desktop/01_工作业务/计划经营部/业务计划/计划/电池/BOM 源数据.zip")

HIST_COLUMNS_SQL = """
    import_batch_no VARCHAR(64) NULL,
    source_year INT NULL,
    source_factory VARCHAR(64) NULL,
    source_file_name VARCHAR(255) NULL,
    source_sheet_name VARCHAR(128) NULL,
    source_row_no INT NULL,
    biz_date DATE NULL,
    biz_year INT NULL,
    biz_month INT NULL,
    customer_name TEXT NULL,
    contract_no TEXT NULL,
    inquiry_no TEXT NULL,
    ship_instruction_no TEXT NULL,
    sap_order_no TEXT NULL,
    address TEXT NULL,
    province VARCHAR(128) NULL,
    city VARCHAR(128) NULL,
    region_name VARCHAR(128) NULL,
    origin_place VARCHAR(128) NULL,
    transport_mode VARCHAR(128) NULL,
    distance_km DECIMAL(18,4) NULL,
    product_spec TEXT NULL,
    product_power DECIMAL(18,4) NULL,
    plan_qty DECIMAL(18,4) NULL,
    actual_qty DECIMAL(18,4) NULL,
    actual_watt DECIMAL(24,4) NULL,
    shipment_achieve_rate DECIMAL(18,8) NULL,
    required_vehicle_type VARCHAR(255) NULL,
    pallet_per_vehicle DECIMAL(18,4) NULL,
    shipment_trip_count DECIMAL(18,4) NULL,
    vehicle_no TEXT NULL,
    logistics_company_name VARCHAR(255) NULL,
    unit_price_per_vehicle DECIMAL(18,4) NULL,
    total_fee DECIMAL(24,4) NULL,
    fee_per_watt DECIMAL(18,8) NULL,
    extra_fee DECIMAL(18,4) NULL,
    extra_fee_reason TEXT NULL,
    accessory_desc TEXT NULL,
    remark TEXT NULL,
    raw_vehicle_field_name VARCHAR(64) NULL,
    raw_extra_fee_field_name VARCHAR(64) NULL,
    raw_row_json JSON NULL
"""

HIST_INSERT_FIELDS = [
    "import_batch_no",
    "source_year",
    "source_factory",
    "source_file_name",
    "source_sheet_name",
    "source_row_no",
    "biz_date",
    "biz_year",
    "biz_month",
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
    "distance_km",
    "product_spec",
    "product_power",
    "plan_qty",
    "actual_qty",
    "actual_watt",
    "shipment_achieve_rate",
    "required_vehicle_type",
    "pallet_per_vehicle",
    "shipment_trip_count",
    "vehicle_no",
    "logistics_company_name",
    "unit_price_per_vehicle",
    "total_fee",
    "fee_per_watt",
    "extra_fee",
    "extra_fee_reason",
    "accessory_desc",
    "remark",
    "raw_vehicle_field_name",
    "raw_extra_fee_field_name",
    "raw_row_json",
]


def _source_year(path: Path) -> int:
    """从历史物流 Excel 文件名中识别年份。

    参数：
        path: 源 Excel 文件路径。
    返回值：
        文件归属年份。
    """

    matched = re.search(r"(20\d{2})", path.name)
    if not matched:
        raise ValueError(f"无法从文件名识别年份：{path}")
    return int(matched.group(1))


def _source_factory(path: Path) -> str | None:
    """从历史物流 Excel 文件名中识别始发地。

    参数：
        path: 源 Excel 文件路径。
    返回值：
        当前一期可识别的始发地；无法识别时返回 None。
    """

    if "阜宁" in path.name:
        return "阜宁"
    if "合肥" in path.name:
        return "合肥"
    return None


def _extract_zip(source_zip: Path, target_dir: Path) -> list[Path]:
    """解压源数据 zip 并返回 Excel 文件列表。

    参数：
        source_zip: zip 源文件。
        target_dir: 解压目标目录。
    返回值：
        按文件名排序的 Excel 文件路径。
    """

    if not source_zip.exists():
        raise FileNotFoundError(f"源数据缺失：{source_zip}")
    if target_dir.exists():
        for child in target_dir.rglob("*"):
            if child.is_file():
                child.unlink()
        for child in sorted(target_dir.rglob("*"), reverse=True):
            if child.is_dir():
                child.rmdir()
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source_zip) as archive:
        for info in archive.infolist():
            name = info.filename
            if "__MACOSX" in name or Path(name).name.startswith("._") or name.endswith("/"):
                continue
            suffix = Path(name).suffix.lower()
            if suffix not in {".xlsx", ".xls", ".xlsm"}:
                continue
            archive.extract(info, target_dir)
    files = sorted(path for path in target_dir.rglob("*") if path.suffix.lower() in {".xlsx", ".xls", ".xlsm"})
    if not files:
        raise RuntimeError(f"zip 中没有可核算 Excel：{source_zip}")
    return files


def _json_safe(value: Any) -> Any:
    """把 pandas/openpyxl 值转换为可写 JSON 的类型。

    参数：
        value: 原始单元格值。
    返回值：
        可 JSON 序列化的值。
    """

    if pd.isna(value):
        return None
    if isinstance(value, (date, pd.Timestamp)):
        return str(value.date() if isinstance(value, pd.Timestamp) else value)
    return value


def _month_number(value: Any) -> int | None:
    """把 ETL 映射后的月份转成 1-12。

    参数：
        value: 可能为 `2025-03`、`3` 或日期对象的月份值。
    返回值：
        月份数字；无法识别时返回 None。
    """

    if value is None:
        return None
    if isinstance(value, (int, float)) and not pd.isna(value):
        month = int(value)
        return month if 1 <= month <= 12 else None
    text_value = str(value)
    matched = re.search(r"(?:20\d{2}[-/年])?(\d{1,2})", text_value)
    if not matched:
        return None
    month = int(matched.group(1))
    return month if 1 <= month <= 12 else None


def _normalize_source_text(value: Any) -> Any:
    """清理源 Excel 中不影响业务语义的隐藏字符。

    参数：
        value: Excel 单元格原值。
    返回值：
        清理后的文本；非文本原样返回。
    """

    if not isinstance(value, str):
        return value
    return value.replace("\u200b", "").replace("\ufeff", "").replace("\xa0", "").strip()


def _load_history_rows(hist_zip: Path, extract_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """从附件历史物流 Excel 独立读取 DWD 口径行。

    参数：
        hist_zip: 2023-2025 物流源数据 zip。
        extract_dir: 解压目录。
    返回值：
        `(行列表, 源文件审计信息)`。
    """

    files = _extract_zip(hist_zip, extract_dir)
    rows: list[dict[str, Any]] = []
    sheet_audit: list[dict[str, Any]] = []
    for path in files:
        year = _source_year(path)
        factory = _source_factory(path)
        workbook = pd.ExcelFile(path)
        for sheet_name in workbook.sheet_names:
            frame = pd.read_excel(workbook, sheet_name=sheet_name, dtype=object)
            frame = frame.dropna(how="all")
            sheet_audit.append(
                {
                    "file": str(path),
                    "sheet": sheet_name,
                    "raw_rows": int(len(frame)),
                    "columns": [str(column) for column in frame.columns],
                }
            )
            for row_index, row in frame.where(pd.notnull(frame), None).iterrows():
                raw = {str(key): _json_safe(value) for key, value in row.to_dict().items()}
                mapped = map_hist_row(raw, source_year=year)
                if not mapped.get("biz_date") and not mapped.get("customer_name") and not mapped.get("logistics_company_name"):
                    continue
                mapped["biz_month"] = _month_number(mapped.get("biz_month"))
                mapped["product_spec"] = _normalize_source_text(mapped.get("product_spec"))
                # 业务口径说明：历史台账里“汽运”与“公路”表达同一运输方式，
                # 标准答案核算层先归一，避免把同义记录拆成两个口径。
                if mapped.get("transport_mode") == "汽运":
                    mapped["transport_mode"] = "公路"
                elif mapped.get("transport_mode") == "铁运":
                    mapped["transport_mode"] = "铁路"
                payload = {
                    "import_batch_no": "source-oracle-temp",
                    "source_year": year,
                    "source_factory": factory,
                    "source_file_name": path.name,
                    "source_sheet_name": sheet_name,
                    "source_row_no": int(row_index) + 2,
                    **mapped,
                    "raw_row_json": json.dumps(raw, ensure_ascii=False, default=str),
                }
                rows.append({field: payload.get(field) for field in HIST_INSERT_FIELDS})
    return rows, {"file_count": len(files), "row_count": len(rows), "sheets": sheet_audit}


def _prepare_history_temp_table(db, hist_rows: list[dict[str, Any]]) -> None:
    """把历史附件行写入当前连接的临时核算表。

    参数：
        db: SQLAlchemy Session。
        hist_rows: 已从附件独立解析出的历史明细行。
    返回值：
        无。
    """

    db.execute(text("DROP TEMPORARY TABLE IF EXISTS dwd_logistics_hist_shipment_detail"))
    db.execute(text(f"CREATE TEMPORARY TABLE dwd_logistics_hist_shipment_detail ({HIST_COLUMNS_SQL})"))
    if not hist_rows:
        return
    placeholders = ", ".join(f":{field}" for field in HIST_INSERT_FIELDS)
    fields_sql = ", ".join(HIST_INSERT_FIELDS)
    insert_sql = text(f"INSERT INTO dwd_logistics_hist_shipment_detail ({fields_sql}) VALUES ({placeholders})")
    for start in range(0, len(hist_rows), 500):
        db.execute(insert_sql, hist_rows[start : start + 500])
    db.commit()


def _create_local_system_temp_tables(db) -> None:
    """在本地连接创建 2026 源库核算临时表。

    参数：
        db: 本地 SQLAlchemy Session。
    返回值：
        无。
    """

    for table_name in (
        "ods_logistic_ship_task",
        "dwd_logistics_company",
        "dwd_logistics_ship_task",
        "dwd_logistics_ship_product",
        "dwd_logistics_assign_task",
        "dwd_logistics_assign_detail",
    ):
        db.execute(text(f"DROP TEMPORARY TABLE IF EXISTS {table_name}"))

    db.execute(
        text(
            """
            CREATE TEMPORARY TABLE dwd_logistics_company (
                source_id VARCHAR(64) NULL,
                company_code VARCHAR(128) NULL,
                company_name VARCHAR(255) NULL
            )
            """
        )
    )
    db.execute(
        text(
            """
            CREATE TEMPORARY TABLE ods_logistic_ship_task (
                source_id VARCHAR(64) NULL,
                task_id VARCHAR(64) NULL,
                raw_json JSON NULL
            )
            """
        )
    )
    db.execute(
        text(
            """
            CREATE TEMPORARY TABLE dwd_logistics_ship_task (
                source_id VARCHAR(64) NULL,
                task_id VARCHAR(64) NULL,
                company_id VARCHAR(64) NULL,
                company_name VARCHAR(255) NULL,
                warehouse_id VARCHAR(64) NULL,
                warehouse_name VARCHAR(255) NULL,
                status VARCHAR(64) NULL,
                ship_type VARCHAR(64) NULL,
                project_name TEXT NULL,
                pickup_date DATE NULL,
                expand_dept VARCHAR(128) NULL,
                entrusted_person VARCHAR(128) NULL,
                transport_mode VARCHAR(128) NULL,
                contract_no VARCHAR(255) NULL,
                inquiry_no VARCHAR(255) NULL,
                bidding_no VARCHAR(255) NULL,
                ship_instruction_no VARCHAR(255) NULL,
                rd_no VARCHAR(255) NULL,
                procurement_type VARCHAR(128) NULL,
                car_model VARCHAR(255) NULL,
                loading_trucks DECIMAL(18,4) NULL,
                delivery_province VARCHAR(128) NULL,
                delivery_city VARCHAR(128) NULL,
                delivery_area VARCHAR(128) NULL,
                normalized_region_name VARCHAR(64) NULL,
                region_resolve_source VARCHAR(64) NULL,
                delivery_distance DECIMAL(18,4) NULL,
                reconciliation_status VARCHAR(64) NULL,
                extra_cost_audited VARCHAR(64) NULL,
                base_code VARCHAR(64) NULL,
                del_flag VARCHAR(16) NULL,
                biz_date DATE NULL,
                biz_year INT NULL,
                biz_month VARCHAR(16) NULL,
                is_formal_data INT NULL,
                created_at DATETIME NULL,
                updated_at DATETIME NULL
            )
            """
        )
    )
    db.execute(
        text(
            """
            CREATE TEMPORARY TABLE dwd_logistics_ship_product (
                source_id VARCHAR(64) NULL,
                task_id VARCHAR(64) NULL,
                product_code VARCHAR(255) NULL,
                product_spec TEXT NULL,
                power DECIMAL(18,4) NULL,
                quantity DECIMAL(18,4) NULL,
                price DECIMAL(18,4) NULL,
                unit VARCHAR(64) NULL,
                extra_cost DECIMAL(18,4) NULL,
                created_at DATETIME NULL,
                updated_at DATETIME NULL
            )
            """
        )
    )
    db.execute(
        text(
            """
            CREATE TEMPORARY TABLE dwd_logistics_assign_task (
                source_id VARCHAR(64) NULL,
                task_id VARCHAR(64) NULL,
                ship_task_id VARCHAR(64) NULL,
                company_id VARCHAR(64) NULL,
                company_name VARCHAR(255) NULL,
                warehouse_id VARCHAR(64) NULL,
                warehouse_name VARCHAR(255) NULL,
                status VARCHAR(64) NULL,
                plate_number VARCHAR(128) NULL,
                driver_name VARCHAR(128) NULL,
                driver_phone VARCHAR(128) NULL,
                driver_id_number VARCHAR(128) NULL,
                enter_time DATETIME NULL,
                delivery_note_parse_status VARCHAR(64) NULL,
                created_at DATETIME NULL,
                updated_at DATETIME NULL
            )
            """
        )
    )
    db.execute(
        text(
            """
            CREATE TEMPORARY TABLE dwd_logistics_assign_detail (
                id VARCHAR(64) NULL,
                source_id VARCHAR(64) NULL,
                assign_task_id VARCHAR(64) NULL,
                ship_task_id VARCHAR(64) NULL,
                product_source_id VARCHAR(64) NULL,
                quantity DECIMAL(18,4) NULL,
                supplier_price DECIMAL(18,4) NULL,
                extra_cost DECIMAL(18,4) NULL,
                cost_proof_url TEXT NULL,
                created_at DATETIME NULL,
                updated_at DATETIME NULL
            )
            """
        )
    )


def _fetch_source_system_rows(source_db) -> dict[str, list[dict[str, Any]]]:
    """只读抽取 2026 源 MySQL 数据。

    参数：
        source_db: 源库 SQLAlchemy Session。
    返回值：
        源库表映射后的行字典。
    """

    rows: dict[str, list[dict[str, Any]]] = {}
    rows["dwd_logistics_company"] = [
        dict(row)
        for row in source_db.execute(
            text(
                """
                SELECT company_id AS source_id, base_code AS company_code, company_name
                FROM logistic_logistic_company
                """
            )
        ).mappings()
    ]
    ods_rows = [
        dict(row)
        for row in source_db.execute(
            text(
                """
                SELECT
                    task_id AS source_id,
                    task_id,
                    pickup_date,
                    create_time
                FROM logistic_ship_task
                WHERE DATE(create_time) >= '2026-01-01'
                """
            )
        ).mappings()
    ]
    rows["ods_logistic_ship_task"] = [
        {
            "source_id": row.get("source_id"),
            "task_id": row.get("task_id"),
            "raw_json": json.dumps(
                {"pickup_date": row.get("pickup_date"), "create_time": row.get("create_time")},
                ensure_ascii=False,
                default=str,
            ),
        }
        for row in ods_rows
    ]
    rows["dwd_logistics_ship_task"] = [
        dict(row)
        for row in source_db.execute(
            text(
                """
                SELECT
                    st.task_id AS source_id,
                    st.task_id,
                    st.company_id,
                    c.company_name,
                    NULL AS warehouse_id,
                    NULL AS warehouse_name,
                    st.status,
                    st.ship_type,
                    st.project_name,
                    st.pickup_date,
                    st.expand_dept,
                    st.entrusted_person,
                    st.transport AS transport_mode,
                    st.contract_number AS contract_no,
                    st.inquiry_number AS inquiry_no,
                    st.bidding_number AS bidding_no,
                    st.shipping_instruction AS ship_instruction_no,
                    st.rd_number AS rd_no,
                    st.procurement_type,
                    st.car_model,
                    CASE
                        WHEN st.loading_trucks REGEXP '^[0-9]+(\\.[0-9]+)?$' THEN CAST(st.loading_trucks AS DECIMAL(18,4))
                        ELSE NULL
                    END AS loading_trucks,
                    st.delivery_province,
                    st.delivery_city,
                    st.delivery_area,
                    CASE
                        WHEN NULLIF(TRIM(st.delivery_area), '') IS NOT NULL THEN TRIM(st.delivery_area)
                        WHEN st.delivery_province IN ('上海市', '江苏省', '浙江省', '安徽省', '福建省', '江西省', '山东省') THEN '华东'
                        WHEN st.delivery_province IN ('广东省', '广西壮族自治区', '海南省') THEN '华南'
                        WHEN st.delivery_province IN ('河南省', '湖北省', '湖南省') THEN '华中'
                        WHEN st.delivery_province IN ('北京市', '天津市', '河北省', '山西省', '内蒙古自治区') THEN '华北'
                        WHEN st.delivery_province IN ('重庆市', '四川省', '贵州省', '云南省', '西藏自治区') THEN '西南'
                        WHEN st.delivery_province IN ('陕西省', '甘肃省', '青海省', '宁夏回族自治区', '新疆维吾尔自治区') THEN '西北'
                        WHEN st.delivery_province IN ('辽宁省', '吉林省', '黑龙江省') THEN '东北'
                        ELSE '其他'
                    END AS normalized_region_name,
                    CASE
                        WHEN NULLIF(TRIM(st.delivery_area), '') IS NOT NULL THEN 'delivery_area'
                        WHEN st.delivery_province IS NOT NULL AND st.delivery_province <> '' THEN 'delivery_province'
                        ELSE 'other'
                    END AS region_resolve_source,
                    CASE
                        WHEN st.delivery_distance REGEXP '^[0-9]+(\\.[0-9]+)?$' THEN CAST(st.delivery_distance AS DECIMAL(18,4))
                        ELSE NULL
                    END AS delivery_distance,
                    st.reconciliation_status,
                    st.extra_cost_audited,
                    st.base_code,
                    st.del_flag,
                    DATE(st.create_time) AS biz_date,
                    YEAR(DATE(st.create_time)) AS biz_year,
                    DATE_FORMAT(DATE(st.create_time), '%Y-%m') AS biz_month,
                    1 AS is_formal_data,
                    st.create_time AS created_at,
                    st.update_time AS updated_at
                FROM logistic_ship_task st
                LEFT JOIN logistic_logistic_company c ON c.company_id = st.company_id
                WHERE DATE(st.create_time) >= '2026-01-01'
                  AND COALESCE(st.del_flag, '0') = '0'
                """
            )
        ).mappings()
    ]
    rows["dwd_logistics_ship_product"] = [
        dict(row)
        for row in source_db.execute(
            text(
                """
                SELECT
                    product_id AS source_id,
                    task_id,
                    product_name AS product_code,
                    specification AS product_spec,
                    CASE
                        WHEN power REGEXP '^[0-9]+(\\.[0-9]+)?$' THEN CAST(power AS DECIMAL(18,4))
                        ELSE NULL
                    END AS power,
                    CASE
                        WHEN quantity REGEXP '^[0-9]+(\\.[0-9]+)?$' THEN CAST(quantity AS DECIMAL(18,4))
                        ELSE NULL
                    END AS quantity,
                    CASE
                        WHEN price REGEXP '^[0-9]+(\\.[0-9]+)?$' THEN CAST(price AS DECIMAL(18,4))
                        ELSE NULL
                    END AS price,
                    unit,
                    CASE
                        WHEN extra_cost REGEXP '^[0-9]+(\\.[0-9]+)?$' THEN CAST(extra_cost AS DECIMAL(18,4))
                        ELSE NULL
                    END AS extra_cost,
                    create_time AS created_at,
                    update_time AS updated_at
                FROM logistic_ship_product
                WHERE COALESCE(del_flag, '0') = '0'
                  AND task_id IN (
                      SELECT task_id
                      FROM logistic_ship_task
                      WHERE DATE(create_time) >= '2026-01-01'
                        AND COALESCE(del_flag, '0') = '0'
                  )
                """
            )
        ).mappings()
    ]
    rows["dwd_logistics_assign_task"] = [
        dict(row)
        for row in source_db.execute(
            text(
                """
                SELECT
                    at.task_id AS source_id,
                    at.task_id,
                    at.ship_task_id,
                    st.company_id,
                    c.company_name,
                    NULL AS warehouse_id,
                    NULL AS warehouse_name,
                    at.status,
                    at.plate_number,
                    at.driver_name,
                    at.phone AS driver_phone,
                    at.id_number AS driver_id_number,
                    at.enter_time,
                    at.delivery_note_parse_status,
                    at.create_time AS created_at,
                    at.update_time AS updated_at
                FROM logistic_assign_task at
                LEFT JOIN logistic_ship_task st ON st.task_id = at.ship_task_id
                LEFT JOIN logistic_logistic_company c ON c.company_id = st.company_id
                WHERE COALESCE(at.del_flag, '0') = '0'
                  AND at.ship_task_id IN (
                      SELECT task_id
                      FROM logistic_ship_task
                      WHERE DATE(create_time) >= '2026-01-01'
                        AND COALESCE(del_flag, '0') = '0'
                  )
                """
            )
        ).mappings()
    ]
    rows["dwd_logistics_assign_detail"] = [
        dict(row)
        for row in source_db.execute(
            text(
                """
                SELECT
                    d.detail_id AS id,
                    d.detail_id AS source_id,
                    d.assign_task_id,
                    at.ship_task_id,
                    d.ship_product_id AS product_source_id,
                    CASE
                        WHEN d.quantity REGEXP '^[0-9]+(\\.[0-9]+)?$' THEN CAST(d.quantity AS DECIMAL(18,4))
                        ELSE NULL
                    END AS quantity,
                    CASE
                        WHEN d.supplier_price REGEXP '^[0-9]+(\\.[0-9]+)?$' THEN CAST(d.supplier_price AS DECIMAL(18,4))
                        ELSE NULL
                    END AS supplier_price,
                    CASE
                        WHEN d.extra_cost REGEXP '^[0-9]+(\\.[0-9]+)?$' THEN CAST(d.extra_cost AS DECIMAL(18,4))
                        ELSE NULL
                    END AS extra_cost,
                    d.cost_proof_url,
                    d.create_time AS created_at,
                    d.update_time AS updated_at
                FROM logistic_assign_detail d
                LEFT JOIN logistic_assign_task at ON at.task_id = d.assign_task_id
                WHERE COALESCE(d.del_flag, '0') = '0'
                  AND d.assign_task_id IN (
                      SELECT at2.task_id
                      FROM logistic_assign_task at2
                      JOIN logistic_ship_task st2 ON st2.task_id = at2.ship_task_id
                      WHERE DATE(st2.create_time) >= '2026-01-01'
                        AND COALESCE(st2.del_flag, '0') = '0'
                        AND COALESCE(at2.del_flag, '0') = '0'
                  )
                """
            )
        ).mappings()
    ]
    return rows


def _insert_local_rows(db, table_name: str, rows: list[dict[str, Any]]) -> None:
    """批量写入本地临时表。

    参数：
        db: 本地 SQLAlchemy Session。
        table_name: 临时表名。
        rows: 待写入行。
    返回值：
        无。
    """

    if not rows:
        return
    fields = list(rows[0].keys())
    insert_sql = text(
        f"INSERT INTO {table_name} ({', '.join(fields)}) VALUES ({', '.join(':' + field for field in fields)})"
    )
    for start in range(0, len(rows), 500):
        db.execute(insert_sql, rows[start : start + 500])


def _prepare_source_system_temp_tables(db, source_db) -> dict[str, Any]:
    """从源 MySQL 只读抽取并写入本地临时核算表。

    参数：
        db: 本地 SQLAlchemy Session。
        source_db: 源库 SQLAlchemy Session。
    返回值：
        表行数审计信息。
    """

    _create_local_system_temp_tables(db)
    source_rows = _fetch_source_system_rows(source_db)
    for table_name, rows in source_rows.items():
        _insert_local_rows(db, table_name, rows)
    db.commit()
    audit: dict[str, Any] = {f"{table}_source_rows": len(rows) for table, rows in source_rows.items()}
    for table_name in source_rows:
        audit[table_name] = int(db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0)
    return audit


def _unused_prepare_source_system_temp_tables_in_source_db(db) -> dict[str, Any]:
    """保留源库建临时表实现的旧入口，避免误用。

    参数：
        db: 源库 SQLAlchemy Session。
    返回值：
        表行数审计信息。
    """

    db.execute(
        text(
            """
            CREATE TEMPORARY TABLE dwd_logistics_company AS
            SELECT company_id AS source_id, base_code AS company_code, company_name
            FROM logistic_logistic_company
            """
        )
    )
    db.execute(
        text(
            """
            CREATE TEMPORARY TABLE ods_logistic_ship_task AS
            SELECT
                task_id AS source_id,
                task_id,
                JSON_OBJECT('pickup_date', pickup_date, 'create_time', create_time) AS raw_json
            FROM logistic_ship_task
            WHERE DATE(create_time) >= '2026-01-01'
            """
        )
    )
    db.execute(
        text(
            """
            CREATE TEMPORARY TABLE dwd_logistics_ship_task AS
            SELECT
                st.task_id AS source_id,
                st.task_id,
                st.company_id,
                c.company_name,
                NULL AS warehouse_id,
                NULL AS warehouse_name,
                st.status,
                st.ship_type,
                st.project_name,
                st.pickup_date,
                st.expand_dept,
                st.entrusted_person,
                st.transport AS transport_mode,
                st.contract_number AS contract_no,
                st.inquiry_number AS inquiry_no,
                st.bidding_number AS bidding_no,
                st.shipping_instruction AS ship_instruction_no,
                st.rd_number AS rd_no,
                st.procurement_type,
                st.car_model,
                st.loading_trucks,
                st.delivery_province,
                st.delivery_city,
                st.delivery_area,
                CASE
                    WHEN NULLIF(TRIM(st.delivery_area), '') IS NOT NULL THEN TRIM(st.delivery_area)
                    WHEN st.delivery_province IN ('上海市', '江苏省', '浙江省', '安徽省', '福建省', '江西省', '山东省') THEN '华东'
                    WHEN st.delivery_province IN ('广东省', '广西壮族自治区', '海南省') THEN '华南'
                    WHEN st.delivery_province IN ('河南省', '湖北省', '湖南省') THEN '华中'
                    WHEN st.delivery_province IN ('北京市', '天津市', '河北省', '山西省', '内蒙古自治区') THEN '华北'
                    WHEN st.delivery_province IN ('重庆市', '四川省', '贵州省', '云南省', '西藏自治区') THEN '西南'
                    WHEN st.delivery_province IN ('陕西省', '甘肃省', '青海省', '宁夏回族自治区', '新疆维吾尔自治区') THEN '西北'
                    WHEN st.delivery_province IN ('辽宁省', '吉林省', '黑龙江省') THEN '东北'
                    ELSE '其他'
                END AS normalized_region_name,
                CASE
                    WHEN NULLIF(TRIM(st.delivery_area), '') IS NOT NULL THEN 'delivery_area'
                    WHEN st.delivery_province IS NOT NULL AND st.delivery_province <> '' THEN 'delivery_province'
                    ELSE 'other'
                END AS region_resolve_source,
                st.delivery_distance,
                st.reconciliation_status,
                st.extra_cost_audited,
                st.base_code,
                st.del_flag,
                DATE(st.create_time) AS biz_date,
                YEAR(DATE(st.create_time)) AS biz_year,
                DATE_FORMAT(DATE(st.create_time), '%Y-%m') AS biz_month,
                1 AS is_formal_data,
                st.create_time AS created_at,
                st.update_time AS updated_at
            FROM logistic_ship_task st
            LEFT JOIN logistic_logistic_company c ON c.company_id = st.company_id
            WHERE DATE(st.create_time) >= '2026-01-01'
              AND COALESCE(st.del_flag, '0') = '0'
            """
        )
    )
    db.execute(
        text(
            """
            CREATE TEMPORARY TABLE dwd_logistics_ship_product AS
            SELECT
                product_id AS source_id,
                task_id,
                product_name AS product_code,
                specification AS product_spec,
                CASE
                    WHEN power REGEXP '^[0-9]+(\\.[0-9]+)?$' THEN CAST(power AS DECIMAL(18,4))
                    ELSE NULL
                END AS power,
                CASE
                    WHEN quantity REGEXP '^[0-9]+(\\.[0-9]+)?$' THEN CAST(quantity AS DECIMAL(18,4))
                    ELSE NULL
                END AS quantity,
                CASE
                    WHEN price REGEXP '^[0-9]+(\\.[0-9]+)?$' THEN CAST(price AS DECIMAL(18,4))
                    ELSE NULL
                END AS price,
                unit,
                CASE
                    WHEN extra_cost REGEXP '^[0-9]+(\\.[0-9]+)?$' THEN CAST(extra_cost AS DECIMAL(18,4))
                    ELSE NULL
                END AS extra_cost,
                create_time AS created_at,
                update_time AS updated_at
            FROM logistic_ship_product
            WHERE COALESCE(del_flag, '0') = '0'
              AND task_id IN (SELECT task_id FROM dwd_logistics_ship_task)
            """
        )
    )
    db.execute(
        text(
            """
            CREATE TEMPORARY TABLE dwd_logistics_assign_task AS
            SELECT
                at.task_id AS source_id,
                at.task_id,
                at.ship_task_id,
                st.company_id,
                c.company_name,
                NULL AS warehouse_id,
                NULL AS warehouse_name,
                at.status,
                at.plate_number,
                at.driver_name,
                at.phone AS driver_phone,
                at.id_number AS driver_id_number,
                at.enter_time,
                at.delivery_note_parse_status,
                at.create_time AS created_at,
                at.update_time AS updated_at
            FROM logistic_assign_task at
            LEFT JOIN logistic_ship_task st ON st.task_id = at.ship_task_id
            LEFT JOIN logistic_logistic_company c ON c.company_id = st.company_id
            WHERE COALESCE(at.del_flag, '0') = '0'
              AND at.ship_task_id IN (SELECT task_id FROM dwd_logistics_ship_task)
            """
        )
    )
    db.execute(
        text(
            """
            CREATE TEMPORARY TABLE dwd_logistics_assign_detail AS
            SELECT
                detail_id AS id,
                detail_id AS source_id,
                assign_task_id,
                at.ship_task_id,
                ship_product_id AS product_source_id,
                CASE
                    WHEN d.quantity REGEXP '^[0-9]+(\\.[0-9]+)?$' THEN CAST(d.quantity AS DECIMAL(18,4))
                    ELSE NULL
                END AS quantity,
                CASE
                    WHEN d.supplier_price REGEXP '^[0-9]+(\\.[0-9]+)?$' THEN CAST(d.supplier_price AS DECIMAL(18,4))
                    ELSE NULL
                END AS supplier_price,
                CASE
                    WHEN d.extra_cost REGEXP '^[0-9]+(\\.[0-9]+)?$' THEN CAST(d.extra_cost AS DECIMAL(18,4))
                    ELSE NULL
                END AS extra_cost,
                d.cost_proof_url,
                d.create_time AS created_at,
                d.update_time AS updated_at
            FROM logistic_assign_detail d
            LEFT JOIN logistic_assign_task at ON at.task_id = d.assign_task_id
            WHERE COALESCE(d.del_flag, '0') = '0'
              AND d.assign_task_id IN (SELECT task_id FROM dwd_logistics_assign_task)
            """
        )
    )
    db.commit()
    audit: dict[str, Any] = {}
    for table_name in (
        "dwd_logistics_company",
        "dwd_logistics_ship_task",
        "dwd_logistics_ship_product",
        "dwd_logistics_assign_task",
        "dwd_logistics_assign_detail",
    ):
        audit[table_name] = int(db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0)
    return audit


def _requested_visual(question: str) -> str | None:
    """识别用户明确要求的展示形态。

    参数：
        question: 原始问题文本。
    返回值：
        展示类型；未明确要求时返回 None。
    """

    visual_words = [
        ("pie", ("饼图", "占比图")),
        ("bar", ("柱状图", "柱形图", "排名图")),
        ("line", ("折线图", "趋势图", "趋势")),
        ("table", ("表格", "明细表", "列表", "清单")),
    ]
    for visual_type, aliases in visual_words:
        if any(alias in question for alias in aliases):
            return visual_type
    return None


def _classify_source(expected: dict[str, Any], *, question: str, years: list[int], domain: str) -> str:
    """生成人工可读的数据源说明。

    参数：
        expected: 标准答案结构。
        question: 原始问题文本。
        years: 识别出的年份列表。
        domain: 业务域。
    返回值：
        源数据说明。
    """

    if domain == "plan_bom":
        return "BOM 源数据.zip -> tmp/plan_bom/plan_bom_standardized_materials.json"
    if max(years or [0]) >= 2026:
        return "源 MySQL: logistic_ship_task/logistic_ship_product/logistic_assign_task/logistic_assign_detail"
    if expected.get("expected_status") == "needs_clarification" and not years:
        return "未确认时间范围"
    if domain == "logistics":
        return "23 年至 25 年物流源数据.zip -> 历史 Excel 临时核算表"
    return "未识别业务域"


def _apply_common_decision(item: dict[str, Any], years: list[int], months: list[int]) -> dict[str, Any] | None:
    """复用样例题验收里的通用 B/C 类判定。

    参数：
        item: 台账项。
        years: 已识别年份。
        months: 已识别月份。
    返回值：
        可提前确定的标准答案；需要继续核算时返回 None。
    """

    question = item.get("question", "")
    compact = re.sub(r"\s+", "", question)
    if "车次或车辆数" in compact or "车次/车辆数" in compact:
        return _clarification_expected(
            "“车次”和“车辆数”是两个不同统计口径，题面用“或”表达时不能替业务选择其中一个。",
            ["车次或车辆数口径"],
        )
    if "为什么可能不一致" in question and any(word in question for word in ("客户名", "项目")):
        return _clarification_expected(
            "这是字段口径解释题，需要先确认按客户名称、项目名称，还是归一后的客户口径查询；系统不能把两个不同字段表达直接混为同一个统计条件。",
            ["客户字段口径", "项目字段口径", "客户归一规则"],
        )
    if "产生原因包含" in question and any(word in question for word in ("额外费用", "异常费", "异常费用")):
        return _unsupported_expected("当前系统尚未固化产生原因、额外费用金额、承运商和客户之间的可追溯归因口径，不能直接按原因拆分费用明细。")
    if _is_complex_report_question(question):
        return _clarification_expected(
            "该问题属于宽表、透视表、同比变化或多指标经营汇总类报表，需要先确认报表模板、维度范围和指标口径。",
            ["报表模板", "多指标口径", "维度范围"],
        )
    if _is_2026_special_scope_mw_without_months(question, years, months):
        return _clarification_expected(
            "2026 系统侧特殊业务范围的发运量需要先确认具体月份或明确是否按截至目前累计口径统计。",
            ["2026统计月份", "累计口径"],
        )
    if max(years or [0]) >= 2026 and "任务状态" in question:
        return _clarification_expected(
            "任务状态分布需要先确认状态字段来源和状态口径，例如派车状态、送货单解析状态还是主任务业务状态。",
            ["任务状态字段", "状态口径"],
        )
    if not years and "项目名称" in question and any(word in question for word in ("总运量", "运量", "发运量")):
        return _unsupported_expected("项目名称尚未作为标准化、可复用统计维度管理，不能直接按项目名称可靠汇总运量。")
    return None


def _project_total_trucks(project_name: Any) -> float | None:
    """从 2026 项目名称中解析项目总车数。

    参数：
        project_name: 源系统项目名称。
    返回值：
        可解析时返回车数；否则返回 None。
    """

    if not project_name:
        return None
    parts = str(project_name).split("-")
    if len(parts) < 3:
        return None
    value = parts[2].strip()
    if not re.fullmatch(r"\d+(?:\.\d+)?", value):
        return None
    return float(value)


def _to_float(value: Any) -> float | None:
    """把 Decimal/数字文本转为 float。

    参数：
        value: 待转换值。
    返回值：
        数字值；无法转换时返回 None。
    """

    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return None


def _source_temp_workaround_expected(db, item: dict[str, Any], years: list[int], months: list[int]) -> dict[str, Any] | None:
    """处理 MySQL 临时表不能重复打开的少数核算题。

    参数：
        db: 本地临时核算库。
        item: 台账项。
        years: 识别出的年份。
        months: 识别出的月份。
    返回值：
        能独立核算时返回标准答案；否则返回 None。
    """

    question = item.get("question", "")
    if max(years or [0]) < 2026 and "额外费用占总费用比重最高" in question:
        year_clause = ", ".join(str(int(year)) for year in years)
        rows = [
            dict(row)
            for row in db.execute(
                text(
                    f"""
                    SELECT
                        CONCAT(biz_year, '-', LPAD(biz_month, 2, '0')) AS `月份`,
                        ROUND(SUM(COALESCE(extra_fee, 0)), 0) AS `额外费用`,
                        ROUND(SUM(COALESCE(total_fee, 0)), 0) AS `总费用`,
                        ROUND(100 * SUM(COALESCE(extra_fee, 0)) / NULLIF(SUM(COALESCE(total_fee, 0)), 0), 1) AS `额外费用占比`
                    FROM dwd_logistics_hist_shipment_detail
                    WHERE biz_year IN ({year_clause})
                    GROUP BY biz_year, biz_month
                    ORDER BY `额外费用占比` DESC
                    LIMIT 1
                    """
                )
            ).mappings()
        ]
        table_rows = [
            {
                "月份": row.get("月份"),
                "额外费用": int(row.get("额外费用") or 0),
                "总费用": int(row.get("总费用") or 0),
                "额外费用占比": float(row.get("额外费用占比") or 0),
            }
            for row in rows
        ]
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": "extra_fee_share",
            "table": {"columns": ["月份", "额外费用", "总费用", "额外费用占比"], "rows": table_rows},
            "summary_values": [
                value
                for row in table_rows
                for value in (row.get("月份"), row.get("额外费用"), row.get("额外费用占比"))
                if value is not None
            ],
        }

    if "水路记录" in question:
        waterway_count = int(
            db.execute(
                text("SELECT COUNT(*) FROM dwd_logistics_hist_shipment_detail WHERE transport_mode = '水路'")
            ).scalar()
            or 0
        )
        total_count = int(db.execute(text("SELECT COUNT(*) FROM dwd_logistics_hist_shipment_detail")).scalar() or 0)
        province_rows = [
            dict(row)
            for row in db.execute(
                text(
                    """
                    SELECT province AS `省份`, COUNT(*) AS `记录数`
                    FROM dwd_logistics_hist_shipment_detail
                    WHERE transport_mode = '水路'
                      AND province IS NOT NULL
                    GROUP BY province
                    ORDER BY `记录数` DESC, province ASC
                    LIMIT 10
                    """
                )
            ).mappings()
        ]
        month_rows = [
            dict(row)
            for row in db.execute(
                text(
                    """
                    SELECT biz_month AS `月份`, COUNT(*) AS `记录数`
                    FROM dwd_logistics_hist_shipment_detail
                    WHERE transport_mode = '水路'
                      AND biz_month IS NOT NULL
                    GROUP BY biz_month
                    ORDER BY `记录数` DESC, biz_month ASC
                    LIMIT 10
                    """
                )
            ).mappings()
        ]
        ratio = round(waterway_count / total_count * 100, 2) if total_count else 0
        table_rows = [{"类别": "总体", "项目": "水路记录", "记录数": waterway_count, "占比": ratio}]
        table_rows.extend({"类别": "省份", "项目": row.get("省份"), "记录数": row.get("记录数"), "占比": None} for row in province_rows)
        table_rows.extend({"类别": "月份", "项目": row.get("月份"), "记录数": row.get("记录数"), "占比": None} for row in month_rows)
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": "waterway_record_distribution",
            "table": {"columns": ["类别", "项目", "记录数", "占比"], "rows": table_rows},
            "summary_values": [waterway_count, ratio]
            + [row.get("省份") for row in province_rows[:3] if row.get("省份")]
            + [row.get("月份") for row in month_rows[:3] if row.get("月份") is not None],
        }

    if max(years or [0]) >= 2026 and "单瓦成本" in question and any(word in question for word in ("承运商", "物流公司")):
        filters = ["st.biz_year IN (" + ", ".join(str(int(year)) for year in years) + ")"]
        if months:
            filters.append("MONTH(COALESCE(st.pickup_date, st.biz_date)) IN (" + ", ".join(str(int(month)) for month in months) + ")")
        rows = [
            dict(row)
            for row in db.execute(
                text(
                    f"""
                    SELECT
                        st.task_id,
                        st.company_name,
                        st.project_name,
                        sp.price,
                        sp.power,
                        sp.quantity
                    FROM dwd_logistics_ship_task st
                    LEFT JOIN dwd_logistics_ship_product sp ON sp.task_id = st.task_id
                    WHERE {' AND '.join(filters)}
                      AND st.company_name IS NOT NULL
                      AND TRIM(st.company_name) <> ''
                    """
                )
            ).mappings()
        ]
        by_task: dict[str, dict[str, Any]] = {}
        by_company: defaultdict[str, dict[str, float]] = defaultdict(lambda: {"total_fee": 0.0, "shipment_watt": 0.0, "task_count": 0.0})
        for row in rows:
            task_id = str(row.get("task_id") or "")
            if not task_id:
                continue
            task = by_task.setdefault(
                task_id,
                {
                    "company_name": row.get("company_name"),
                    "project_name": row.get("project_name"),
                    "max_price": None,
                    "shipment_watt": 0.0,
                },
            )
            price = _to_float(row.get("price"))
            if price is not None:
                task["max_price"] = max(float(task["max_price"] or 0), price)
            power = _to_float(row.get("power"))
            quantity = _to_float(row.get("quantity"))
            if power is not None and quantity is not None:
                task["shipment_watt"] += power * quantity
        for task in by_task.values():
            company_name = str(task.get("company_name") or "")
            truck_count = _project_total_trucks(task.get("project_name"))
            max_price = _to_float(task.get("max_price"))
            if truck_count is not None and max_price is not None:
                by_company[company_name]["total_fee"] += truck_count * max_price
            by_company[company_name]["shipment_watt"] += float(task.get("shipment_watt") or 0)
            by_company[company_name]["task_count"] += 1
        top_n = 10
        matched = re.search(r"(?:top|前)\s*(\d+)", question, flags=re.I)
        if matched:
            top_n = int(matched.group(1))
        table_rows = []
        for company_name, values in by_company.items():
            shipment_watt = values["shipment_watt"]
            unit_fee = round(values["total_fee"] / shipment_watt, 8) if shipment_watt else None
            table_rows.append(
                {
                    "承运商": company_name,
                    "平均元/瓦": unit_fee,
                    "总运费": round(values["total_fee"], 2),
                    "发运量": round(shipment_watt / 1000000, 3),
                    "任务数": int(values["task_count"]),
                }
            )
        table_rows = sorted(
            table_rows,
            key=lambda row: (float(row.get("平均元/瓦") or -1), float(row.get("总运费") or 0), str(row.get("承运商") or "")),
            reverse=True,
        )[:top_n]
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": "unit_fee_per_watt",
            "metric_label": "平均元/瓦",
            "unit": "元/瓦",
            "filters": {"years": years, "months": months},
            "dimensions": ["承运商"],
            "top_n": top_n,
            "table": {"columns": ["承运商", "平均元/瓦", "总运费", "发运量", "任务数"], "rows": table_rows},
            "summary_values": [
                value
                for row in table_rows
                for value in (row.get("承运商"), row.get("平均元/瓦"), row.get("总运费"), row.get("发运量"), row.get("任务数"))
                if value is not None
            ],
        }
    return None


def _build_expected_for_item(
    item: dict[str, Any],
    *,
    hist_db,
    source_db,
    bom_materials: list[dict[str, Any]],
) -> dict[str, Any]:
    """按单个问题构建独立标准答案。

    参数：
        item: 样例题台账项。
        hist_db: 已加载附件历史 Excel 的临时核算连接。
        source_db: 已加载源 MySQL 临时视图的核算连接。
        bom_materials: BOM 标准化材料行。
    返回值：
        标准答案结构。
    """

    domain = item.get("domain")
    question = item.get("question", "")
    if domain == "plan_bom":
        return _build_bom_expected(item, bom_materials)
    if domain != "logistics":
        return _clarification_expected("题目业务域未识别，需要先确认是物流还是计划 BOM。", ["业务域"])

    explicit_years = extract_years(question)
    compact = re.sub(r"\s+", "", question)
    if not explicit_years and any(keyword in compact for keyword in ("按月份拆分", "月度汇总表", "功率产品按区域拆分", "分层汇总表")):
        return _clarification_expected(
            "该问题需要先确认统计年份或历史累计范围，不能在标准答案层替业务默认跨年口径。",
            ["统计年份", "历史累计范围"],
        )
    years = list(explicit_years)
    months = extract_months(question)
    if not years and _should_default_to_history_years(question):
        years = [2023, 2024, 2025]
    common_expected = _apply_common_decision(item, years, months)
    if common_expected:
        return common_expected
    if not years:
        return _clarification_expected("缺少年份，无法按正式数据范围计算。", ["年份"])
    workaround_expected = _source_temp_workaround_expected(hist_db if max(years) < 2026 else source_db, item, years, months)
    if workaround_expected:
        return workaround_expected
    if max(years) >= 2026:
        return _build_sys_expected(source_db, item, years, months)
    return _build_hist_expected(hist_db, item, years, months)


def build_source_oracle(
    *,
    ledger_path: Path,
    hist_zip: Path,
    bom_zip: Path,
    output_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """构建全量业务问题标准答案。

    参数：
        ledger_path: 已导入的问题台账。
        hist_zip: 2023-2025 物流源数据 zip。
        bom_zip: BOM 源数据 zip。
        output_dir: 输出目录。
    返回值：
        `(标准答案 payload, 构建报告)`。
    """

    ledger = read_json(ledger_path)
    if not ledger:
        raise FileNotFoundError(f"缺少问题台账：{ledger_path}")

    bom_import = import_source_zip(source_zip=bom_zip, reset=True)
    bom_session = build_runtime_session(reset=False)
    try:
        bom_outputs = build_standardized_outputs(bom_session)
    finally:
        bom_session.close()
    bom_materials = read_json(Path(bom_outputs["standardized_data_path"]), default=[])

    hist_rows, hist_audit = _load_history_rows(hist_zip, output_dir / "source_extract" / "history")
    hist_db = SessionLocal()
    source_db = SourceSessionLocal()
    try:
        _prepare_history_temp_table(hist_db, hist_rows)
        source_audit = _prepare_source_system_temp_tables(hist_db, source_db)
        answers: list[dict[str, Any]] = []
        status_counter: Counter[str] = Counter()
        error_counter: Counter[str] = Counter()
        for item in ledger.get("items", []):
            question = item.get("question", "")
            years = extract_years(question)
            try:
                expected = _build_expected_for_item(
                    item,
                    hist_db=hist_db,
                    source_db=hist_db,
                    bom_materials=bom_materials,
                )
            except Exception as exc:  # noqa: BLE001
                error_key = f"{type(exc).__name__}: {str(exc)[:120]}"
                error_counter[error_key] += 1
                expected = {
                    "expected_status": "not_evaluable",
                    "answer_type": "oracle_error",
                    "reason": f"源数据核算脚本执行失败：{type(exc).__name__}: {exc}",
                }
            status_counter[str(expected.get("expected_status") or "unknown")] += 1
            answers.append(
                {
                    "id": item.get("id"),
                    "original_number": item.get("original_number"),
                    "question": question,
                    "domain": item.get("domain"),
                    "question_type": item.get("question_type"),
                    "requested_visual": _requested_visual(question),
                    "source_location": _classify_source(expected, question=question, years=years, domain=str(item.get("domain") or "")),
                    "expected": expected,
                }
            )
    finally:
        source_db.close()
        hist_db.close()

    payload = {
        "generated_at": now_iso(),
        "ledger_path": str(ledger_path),
        "total_cases": len(answers),
        "status_distribution": dict(status_counter),
        "source_audit": {
            "history_zip": str(hist_zip),
            "history_excel": hist_audit,
            "system_2026_source_mysql_temp_tables": source_audit,
            "bom_zip": str(bom_zip),
            "bom_import": {
                "file_count": bom_import["file_count"],
                "success_count": bom_import["success_count"],
                "failed_count": bom_import["failed_count"],
                "parsed_orders_count": bom_import["parsed_orders_count"],
                "parsed_materials_count": bom_import["parsed_materials_count"],
            },
            "source_rule": "历史物流只读取附件 Excel；2026 物流只读取源 MySQL 临时视图；BOM 只读取附件导入的标准化材料行；不读取智能助手返回结果。",
        },
        "oracle_error_distribution": dict(error_counter),
        "answers": answers,
    }
    report = {
        "generated_at": payload["generated_at"],
        "total_cases": len(answers),
        "status_distribution": dict(status_counter),
        "domain_distribution": dict(Counter(item.get("domain") for item in answers)),
        "requested_visual_distribution": dict(Counter(str(item.get("requested_visual") or "none") for item in answers)),
        "oracle_error_distribution": dict(error_counter),
        "source_audit": payload["source_audit"],
    }
    return payload, report


def write_source_oracle_doc(report: dict[str, Any], output_dir: Path) -> None:
    """写入标准答案核算报告。

    参数：
        report: 构建报告。
        output_dir: 输出目录。
    返回值：
        无。
    """

    audit = report.get("source_audit") or {}
    history = (audit.get("history_excel") or {})
    bom = (audit.get("bom_import") or {})
    system_tables = audit.get("system_2026_source_mysql_temp_tables") or {}
    lines = [
        "## 测试概况",
        f"- 样例题总数：{report.get('total_cases')}",
        f"- 标准答案状态分布：`{report.get('status_distribution')}`",
        f"- 业务域分布：`{report.get('domain_distribution')}`",
        f"- 明确展示要求分布：`{report.get('requested_visual_distribution')}`",
        "",
        "## 源数据核算范围",
        f"- 历史物流 zip：`{audit.get('history_zip')}`",
        f"- 历史物流独立解析行数：{history.get('row_count')}，文件数：{history.get('file_count')}",
        f"- 2026 源 MySQL 临时核算表行数：`{system_tables}`",
        f"- BOM zip：`{audit.get('bom_zip')}`",
        f"- BOM 导入：文件 {bom.get('file_count')}，成功 {bom.get('success_count')}，订单 {bom.get('parsed_orders_count')}，材料行 {bom.get('parsed_materials_count')}",
        "",
        "## 核算原则",
        f"- {audit.get('source_rule')}",
        "- `answerable` 表示已从源数据算出标准答案；`needs_clarification` 表示源数据或业务口径不足；`unsupported` 表示当前系统能力边界内应拒答；`not_evaluable` 表示标准答案脚本仍需补齐核算器。",
        "",
        "## 核算异常分布",
    ]
    errors = report.get("oracle_error_distribution") or {}
    if errors:
        for reason, count in errors.items():
            lines.append(f"- {reason}: {count}")
    else:
        lines.append("- 无")
    write_markdown(output_dir / "source_oracle_report.md", "业务问题标准答案源数据核算报告", lines)


def main() -> int:
    """命令行入口。"""

    parser = argparse.ArgumentParser(description="基于附件和源 MySQL 构建业务问题标准答案")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--hist-zip", type=Path, default=DEFAULT_HIST_ZIP)
    parser.add_argument("--bom-zip", type=Path, default=DEFAULT_BOM_ZIP)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    payload, report = build_source_oracle(
        ledger_path=args.ledger,
        hist_zip=args.hist_zip,
        bom_zip=args.bom_zip,
        output_dir=args.output_dir,
    )
    write_json(args.output_dir / "source_expected_answers.json", payload)
    write_json(args.output_dir / "source_oracle_build_report.json", report)
    write_source_oracle_doc(report, args.output_dir)
    print(f"source expected answers written: {args.output_dir / 'source_expected_answers.json'}")
    print(f"total_cases={payload['total_cases']} status_distribution={payload['status_distribution']}")
    if payload.get("oracle_error_distribution"):
        print(f"oracle_error_distribution={payload['oracle_error_distribution']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

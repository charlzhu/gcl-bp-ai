from __future__ import annotations

import json
import logging
import re
from hashlib import md5
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class LogisticsHistoryImportRepository:
    """历史 Excel 导入仓储。

    风险说明：
    1. 直接依赖 `ods_hist_excel_file`、`ods_hist_excel_row`、`dwd_logistics_hist_shipment_detail`；
    2. `sys_task_error_log` 默认需要同时兼容系统同步和历史导入两套字段；
    3. 所有写入均基于原生 SQL，发布前要核对线上表结构。
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    _DWD_ROW_FIELDS: tuple[str, ...] = (
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
    )
    _VARCHAR_LIMITS: dict[str, int] = {
        "import_batch_no": 64,
        "source_factory": 64,
        "source_file_name": 255,
        "source_sheet_name": 128,
        "biz_month": 16,
        "customer_name": 255,
        "contract_no": 128,
        "inquiry_no": 128,
        "ship_instruction_no": 128,
        "sap_order_no": 128,
        "address": 500,
        "province": 64,
        "city": 64,
        "region_name": 64,
        "origin_place": 128,
        "transport_mode": 64,
        "product_spec": 128,
        "required_vehicle_type": 128,
        "logistics_company_name": 255,
        "extra_fee_reason": 500,
        "raw_vehicle_field_name": 64,
        "raw_extra_fee_field_name": 64,
    }

    def create_task_log(self, *, task_id: str, task_name: str, source_code: str) -> None:
        self.db.execute(
            text(
                """
                INSERT INTO sys_task_log (
                    task_id, task_type, task_name, biz_domain, status, source_code, started_at, created_at, updated_at
                ) VALUES (
                    :task_id, 'HIST_IMPORT', :task_name, 'logistics', 'RUNNING', :source_code, NOW(), NOW(), NOW()
                )
                """
            ),
            {"task_id": task_id, "task_name": task_name, "source_code": source_code},
        )
        self.db.commit()

    def finish_task_log(
        self,
        *,
        task_id: str,
        status: str,
        total_count: int,
        success_count: int,
        fail_count: int,
        message: str,
    ) -> None:
        self.db.execute(
            text(
                """
                UPDATE sys_task_log
                   SET status=:status,
                       total_count=:total_count,
                       success_count=:success_count,
                       fail_count=:fail_count,
                       message=:message,
                       finished_at=NOW(),
                       updated_at=NOW()
                 WHERE task_id=:task_id
                """
            ),
            {
                "task_id": task_id,
                "status": status,
                "total_count": total_count,
                "success_count": success_count,
                "fail_count": fail_count,
                "message": message[:2000],
            },
        )
        self.db.commit()

    def create_error_log(
        self,
        *,
        task_id: str,
        error_stage: str,
        error_message: str,
        source_file_name: str | None = None,
        source_sheet_name: str | None = None,
        row_no: int | None = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> None:
        self.db.execute(
            text(
                """
                INSERT INTO sys_task_error_log (
                    task_id, error_stage, source_file_name, source_sheet_name, row_no, error_message, raw_payload, created_at
                ) VALUES (
                    :task_id, :error_stage, :source_file_name, :source_sheet_name, :row_no, :error_message, :raw_payload, NOW()
                )
                """
            ),
            {
                "task_id": task_id,
                "error_stage": error_stage,
                "source_file_name": source_file_name,
                "source_sheet_name": source_sheet_name,
                "row_no": row_no,
                "error_message": error_message[:2000],
                "raw_payload": json.dumps(raw_payload, ensure_ascii=False, default=str) if raw_payload else None,
            },
        )
        self.db.commit()

    def file_md5(self, file_path: str) -> str:
        digest = md5()
        with open(file_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def create_excel_file_record(
        self,
        *,
        import_batch_no: str,
        source_year: int,
        source_factory: str | None,
        file_path: str,
        sheet_name: str,
        row_count: int,
        file_md5_value: str | None = None,
    ) -> int:
        file_name = Path(file_path).name
        result = self.db.execute(
            text(
                """
                INSERT INTO ods_hist_excel_file (
                    import_batch_no, source_year, source_factory, file_name, file_path, sheet_name, file_md5, row_count, import_status,
                    created_at, updated_at
                ) VALUES (
                    :import_batch_no, :source_year, :source_factory, :file_name, :file_path, :sheet_name, :file_md5, :row_count,
                    'IMPORTED', NOW(), NOW()
                )
                """
            ),
            {
                "import_batch_no": import_batch_no,
                "source_year": source_year,
                "source_factory": source_factory,
                "file_name": file_name,
                "file_path": file_path,
                "sheet_name": sheet_name,
                "file_md5": file_md5_value or self.file_md5(file_path),
                "row_count": row_count,
            },
        )
        self.db.commit()
        return int(result.lastrowid)

    def delete_batch(self, import_batch_no: str) -> None:
        self.db.execute(
            text("DELETE FROM dwd_logistics_hist_shipment_detail WHERE import_batch_no=:batch_no"),
            {"batch_no": import_batch_no},
        )
        self.db.execute(
            text("DELETE FROM ods_hist_excel_row WHERE import_batch_no=:batch_no"),
            {"batch_no": import_batch_no},
        )
        self.db.execute(
            text("DELETE FROM ods_hist_excel_file WHERE import_batch_no=:batch_no"),
            {"batch_no": import_batch_no},
        )
        self.db.commit()

    def batch_insert_ods_rows(self, rows: Iterable[dict[str, Any]]) -> int:
        payload = list(rows)
        if not payload:
            return 0
        # logger.info("batch_insert_ods_rows start rows=%s", len(payload))
        self.db.execute(
            text(
                """
                INSERT INTO ods_hist_excel_row (
                    import_batch_no, file_id, source_year, source_factory, file_name, sheet_name, row_no, raw_row_json, created_at
                ) VALUES (
                    :import_batch_no, :file_id, :source_year, :source_factory, :file_name, :sheet_name, :row_no, :raw_row_json, NOW()
                )
                """
            ),
            payload,
        )
        # logger.info("batch_insert_ods_rows execute done rows=%s", len(payload))
        self.db.commit()
        # logger.info("batch_insert_ods_rows committed rows=%s", len(payload))
        return len(payload)

    def batch_insert_dwd_rows(self, rows: Iterable[dict[str, Any]]) -> int:
        payload = list(rows)
        if not payload:
            return 0
        payload = [self._normalize_dwd_row(row) for row in payload]
        # logger.info("batch_insert_dwd_rows start rows=%s", len(payload))
        sql = text(
            """
            INSERT INTO dwd_logistics_hist_shipment_detail (
                import_batch_no, source_year, source_factory, source_file_name, source_sheet_name, source_row_no,
                biz_date, biz_year, biz_month,
                customer_name, contract_no, inquiry_no, ship_instruction_no, sap_order_no,
                address, province, city, region_name, origin_place, transport_mode, distance_km,
                product_spec, product_power, plan_qty, actual_qty, actual_watt, shipment_achieve_rate,
                required_vehicle_type, pallet_per_vehicle, shipment_trip_count, vehicle_no,
                logistics_company_name, unit_price_per_vehicle, total_fee, fee_per_watt, extra_fee, extra_fee_reason,
                accessory_desc, remark,
                raw_vehicle_field_name, raw_extra_fee_field_name, raw_row_json,
                created_at
            ) VALUES (
                :import_batch_no, :source_year, :source_factory, :source_file_name, :source_sheet_name, :source_row_no,
                :biz_date, :biz_year, :biz_month,
                :customer_name, :contract_no, :inquiry_no, :ship_instruction_no, :sap_order_no,
                :address, :province, :city, :region_name, :origin_place, :transport_mode, :distance_km,
                :product_spec, :product_power, :plan_qty, :actual_qty, :actual_watt, :shipment_achieve_rate,
                :required_vehicle_type, :pallet_per_vehicle, :shipment_trip_count, :vehicle_no,
                :logistics_company_name, :unit_price_per_vehicle, :total_fee, :fee_per_watt, :extra_fee, :extra_fee_reason,
                :accessory_desc, :remark,
                :raw_vehicle_field_name, :raw_extra_fee_field_name, :raw_row_json,
                NOW()
            )
            """
        )
        # 风险说明：
        # 这里不再使用 executemany。当前环境下 `Session.execute(text_sql, list[dict])`
        # 在这张 DWD 表上会卡在 Python 侧的批量参数展开阶段，MySQL 线程表现为 Sleep，
        # 导致看起来像“写入卡死但库里没有数据”。
        # 改为逐行 execute、最后统一 commit，吞吐稍低，但对 2023-2025 历史台账规模更稳定。
        for row in payload:
            self.db.execute(sql, row)
        # logger.info("batch_insert_dwd_rows execute done rows=%s", len(payload))
        self.db.commit()
        # logger.info("batch_insert_dwd_rows committed rows=%s", len(payload))
        return len(payload)

    def _normalize_dwd_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """补全历史 DWD 明细所需的全部绑定字段。

        历史 Excel 有些列不是每个工作簿都存在，直接 executemany 会因为缺失绑定参数失败。
        这里统一补成 `None`，让数据库按空值落库。
        """
        normalized = {field: row.get(field) for field in self._DWD_ROW_FIELDS}
        self._normalize_product_spec_and_accessory(normalized)
        self._truncate_varchar_fields(normalized)
        return normalized

    def _normalize_product_spec_and_accessory(self, row: dict[str, Any]) -> None:
        """把规格列中混入的赠品/配件描述拆到 `accessory_desc`。

        历史 Excel 经常把“规格 + 赠品清单”放在同一个单元格里，例如：
        `GCL-NT10/72GDF-585W 赠品：连接线...`
        而 DWD 的 `product_spec` 只有 128 字符，超长时会直接导致整批导入失败。
        """

        product_spec = row.get("product_spec")
        if not isinstance(product_spec, str):
            return

        cleaned = self._clean_text(product_spec)
        if not cleaned:
            row["product_spec"] = None
            return

        accessory_desc = self._clean_text(row.get("accessory_desc"))
        split_patterns = [
            r"\s+(赠品[:：])",
            r"\s+(配件[:：])",
            r"\s+(附件[:：])",
        ]
        for pattern in split_patterns:
            match = re.search(pattern, cleaned)
            if match:
                split_index = match.start(1)
                spec_part = cleaned[:split_index].strip()
                overflow_part = cleaned[split_index:].strip()
                row["product_spec"] = spec_part or cleaned
                if overflow_part:
                    row["accessory_desc"] = self._merge_text(accessory_desc, overflow_part)
                return

        row["product_spec"] = cleaned

    def _truncate_varchar_fields(self, row: dict[str, Any]) -> None:
        for field, limit in self._VARCHAR_LIMITS.items():
            value = row.get(field)
            if value is None:
                continue
            text_value = self._clean_text(value)
            if text_value is None:
                row[field] = None
                continue
            if len(text_value) <= limit:
                row[field] = text_value
                continue

            overflow = text_value[limit:].strip()
            row[field] = text_value[:limit].strip()
            self._log_truncation(row=row, field=field, original_length=len(text_value), limit=limit)

            if field == "product_spec" and overflow:
                accessory_desc = self._clean_text(row.get("accessory_desc"))
                row["accessory_desc"] = self._merge_text(accessory_desc, f"[product_spec_overflow] {overflow}")
            elif field == "address" and overflow:
                remark = self._clean_text(row.get("remark"))
                row["remark"] = self._merge_text(remark, f"[address_overflow] {overflow}")

    @staticmethod
    def _clean_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).replace("\u200b", "").replace("\ufeff", "")
        text = re.sub(r"\s+", " ", text).strip()
        return text or None

    @staticmethod
    def _merge_text(existing: str | None, extra: str | None) -> str | None:
        existing_text = LogisticsHistoryImportRepository._clean_text(existing)
        extra_text = LogisticsHistoryImportRepository._clean_text(extra)
        if existing_text and extra_text:
            return f"{existing_text} | {extra_text}"
        return existing_text or extra_text

    def _log_truncation(
        self,
        *,
        row: dict[str, Any],
        field: str,
        original_length: int,
        limit: int,
    ) -> None:
        logger.warning(
            "truncate hist dwd field field=%s original_length=%s limit=%s file=%s sheet=%s row_no=%s",
            field,
            original_length,
            limit,
            row.get("source_file_name"),
            row.get("source_sheet_name"),
            row.get("source_row_no"),
        )

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.domains.logistics.schemas.import_history import (
    LogisticsServingRefreshRequest,
    LogisticsServingRefreshResult,
)

logger = logging.getLogger(__name__)


@dataclass
class RefreshStats:
    hist_detail_rows: int = 0
    sys_detail_rows: int = 0
    monthly_rows: int = 0
    dm_rank_rows: int = 0


class LogisticsServingRefreshService:
    """刷新物流服务层宽表。

    # <<< HISTORY ETL REFRESH
    风险说明：
    1. 刷新会直接重建 `dws_logistics_detail_union`、`dws_logistics_monthly_metric`、`dm_logistics_company_month_rank`；
    2. 若后续查询服务接入 Redis/向量索引缓存，需要在刷新后追加缓存清理或重建；
    3. 当前实现按表阶段提交，不是全事务刷新。
    """

    DETAIL_UNION_PLATE_NUMBER_MAX_LEN = 512

    def refresh(self, req: LogisticsServingRefreshRequest) -> LogisticsServingRefreshResult:
        task_id = f"refresh-{uuid.uuid4().hex[:12]}"
        db: Session = SessionLocal()
        stats = RefreshStats()
        try:
            self._create_task_log(db, task_id)
            self._ensure_detail_union_plate_number_capacity(db)
            if req.refresh_hist:
                stats.hist_detail_rows = self._rebuild_hist_detail_union(db, req.target_year_month_list)
            if req.refresh_sys:
                stats.sys_detail_rows = self._rebuild_sys_detail_union(db, req.target_year_month_list)
            stats.monthly_rows = self._rebuild_monthly_metric(db, req.target_year_month_list)
            if req.rebuild_dm:
                stats.dm_rank_rows = self._rebuild_dm_company_rank(db, req.target_year_month_list)
            self._finish_task_log(db, task_id, "SUCCESS", stats)
            return LogisticsServingRefreshResult(
                task_id=task_id,
                **stats.__dict__,
                message="serving layer refreshed",
            )
        except Exception as exc:
            logger.exception("serving refresh failed")
            db.rollback()
            self._fail_task_log(db, task_id, str(exc))
            raise
        finally:
            db.close()

    def _ym_filter_sql(
        self,
        target_year_month_list: list[str] | None,
        column: str,
    ) -> tuple[str, dict[str, Any]]:
        if not target_year_month_list:
            return "", {}
        params: dict[str, Any] = {}
        placeholders: list[str] = []
        for index, year_month in enumerate(target_year_month_list):
            key = f"ym_{index}"
            params[key] = year_month
            placeholders.append(f":{key}")
        return f" AND {column} IN ({', '.join(placeholders)}) ", params

    def _rebuild_hist_detail_union(self, db: Session, target_year_month_list: list[str] | None) -> int:
        delete_filter, delete_params = self._ym_filter_sql(target_year_month_list, "biz_month")
        db.execute(
            text(f"DELETE FROM dws_logistics_detail_union WHERE source_type='HIST' {delete_filter}"),
            delete_params,
        )
        db.execute(
            text(
                f"""
                INSERT INTO dws_logistics_detail_union (
                    source_type, biz_date, biz_year, biz_month, task_id, contract_no, inquiry_no, ship_instruction_no, sap_order_no,
                    customer_name, logistics_company_name, warehouse_name, region_name, origin_place, transport_mode, plate_number,
                    product_spec, product_power, shipment_count, shipment_watt, shipment_trip_count, total_fee, extra_fee, source_ref, created_at
                )
                SELECT
                    'HIST', biz_date, biz_year, biz_month, NULL, contract_no, inquiry_no, ship_instruction_no, sap_order_no,
                    customer_name, logistics_company_name, NULL, region_name, origin_place, transport_mode,
                    NULLIF(LEFT(COALESCE(vehicle_no, ''), :plate_number_max_len), ''),
                    product_spec, product_power, actual_qty, actual_watt, shipment_trip_count, total_fee, extra_fee,
                    CONCAT(import_batch_no, ':', source_row_no), NOW()
                FROM dwd_logistics_hist_shipment_detail
                WHERE 1=1 {delete_filter}
                """
            ),
            {**delete_params, "plate_number_max_len": self.DETAIL_UNION_PLATE_NUMBER_MAX_LEN},
        )
        db.commit()
        return self._count_union_rows(db, "HIST", target_year_month_list)

    def _rebuild_sys_detail_union(self, db: Session, target_year_month_list: list[str] | None) -> int:
        delete_filter, delete_params = self._ym_filter_sql(target_year_month_list, "biz_month")
        select_filter, select_params = self._ym_filter_sql(target_year_month_list, "st.biz_month")
        db.execute(
            text(f"DELETE FROM dws_logistics_detail_union WHERE source_type='SYS' {delete_filter}"),
            delete_params,
        )
        db.execute(
            text(
                f"""
                INSERT INTO dws_logistics_detail_union (
                    source_type, biz_date, biz_year, biz_month, task_id, contract_no, inquiry_no, ship_instruction_no, sap_order_no,
                    customer_name, logistics_company_name, warehouse_name, region_name, origin_place, transport_mode, plate_number,
                    product_spec, product_power, shipment_count, shipment_watt, shipment_trip_count, total_fee, extra_fee, source_ref, created_at
                )
                SELECT
                    'SYS', st.biz_date, st.biz_year, st.biz_month, st.task_id, st.contract_no, st.inquiry_no, st.ship_instruction_no, NULL,
                    NULL, COALESCE(at.company_name, st.company_name), COALESCE(at.warehouse_name, st.warehouse_name),
                    CONCAT_WS('-', st.delivery_province, st.delivery_city, st.delivery_area), NULL, st.transport_mode,
                    NULLIF(LEFT(COALESCE(at.plate_number, ''), :plate_number_max_len), ''),
                    sp.product_spec, sp.power,
                    ad.quantity,
                    COALESCE(sp.power, 0) * COALESCE(ad.quantity, 0),
                    1,
                    COALESCE(ad.supplier_price, 0) + COALESCE(ad.extra_cost, 0),
                    ad.extra_cost,
                    CONCAT(st.task_id, ':', ad.source_id),
                    NOW()
                FROM dwd_logistics_ship_task st
                LEFT JOIN dwd_logistics_assign_task at ON at.ship_task_id = st.task_id
                LEFT JOIN dwd_logistics_assign_detail ad ON ad.assign_task_id = at.task_id
                LEFT JOIN dwd_logistics_ship_product sp ON sp.source_id = ad.product_source_id
                WHERE st.is_formal_data = 1 {select_filter}
                """
            ),
            {**select_params, "plate_number_max_len": self.DETAIL_UNION_PLATE_NUMBER_MAX_LEN},
        )
        db.commit()
        return self._count_union_rows(db, "SYS", target_year_month_list)

    def _rebuild_monthly_metric(self, db: Session, target_year_month_list: list[str] | None) -> int:
        filter_sql, params = self._ym_filter_sql(target_year_month_list, "biz_month")
        db.execute(
            text(f"DELETE FROM dws_logistics_monthly_metric WHERE 1=1 {filter_sql}"),
            params,
        )
        db.execute(
            text(
                f"""
                INSERT INTO dws_logistics_monthly_metric (
                    source_type, biz_year, biz_month, customer_name, logistics_company_name, region_name, warehouse_name, transport_mode,
                    origin_place, metric_type, shipment_watt, shipment_count, shipment_trip_count, total_fee, extra_fee, row_count, created_at
                )
                SELECT
                    source_type, biz_year, biz_month, customer_name, logistics_company_name, region_name, warehouse_name, transport_mode,
                    origin_place, 'WATT',
                    SUM(COALESCE(shipment_watt, 0)),
                    SUM(COALESCE(shipment_count, 0)),
                    SUM(COALESCE(shipment_trip_count, 0)),
                    SUM(COALESCE(total_fee, 0)),
                    SUM(COALESCE(extra_fee, 0)),
                    COUNT(*),
                    NOW()
                FROM dws_logistics_detail_union
                WHERE 1=1 {filter_sql}
                GROUP BY source_type, biz_year, biz_month, customer_name, logistics_company_name, region_name, warehouse_name, transport_mode, origin_place
                """
            ),
            params,
        )
        db.commit()
        return self._count_monthly_rows(db, target_year_month_list)

    def _rebuild_dm_company_rank(self, db: Session, target_year_month_list: list[str] | None) -> int:
        filter_sql, params = self._ym_filter_sql(target_year_month_list, "biz_month")
        db.execute(
            text(f"DELETE FROM dm_logistics_company_month_rank WHERE 1=1 {filter_sql}"),
            params,
        )
        db.execute(
            text(
                f"""
                INSERT INTO dm_logistics_company_month_rank (
                    biz_year, biz_month, logistics_company_name, shipment_watt, shipment_trip_count, total_fee,
                    rank_by_watt, rank_by_fee, created_at
                )
                SELECT
                    biz_year,
                    biz_month,
                    logistics_company_name,
                    SUM(shipment_watt),
                    SUM(shipment_trip_count),
                    SUM(total_fee),
                    DENSE_RANK() OVER (PARTITION BY biz_year, biz_month ORDER BY SUM(shipment_watt) DESC) AS rank_by_watt,
                    DENSE_RANK() OVER (PARTITION BY biz_year, biz_month ORDER BY SUM(total_fee) DESC) AS rank_by_fee,
                    NOW()
                FROM dws_logistics_monthly_metric
                WHERE logistics_company_name IS NOT NULL {filter_sql}
                GROUP BY biz_year, biz_month, logistics_company_name
                """
            ),
            params,
        )
        db.commit()
        return self._count_dm_rows(db, target_year_month_list)

    def _count_union_rows(
        self,
        db: Session,
        source_type: str,
        target_year_month_list: list[str] | None,
    ) -> int:
        filter_sql, params = self._ym_filter_sql(target_year_month_list, "biz_month")
        params["source_type"] = source_type
        result = db.execute(
            text(
                f"""
                SELECT COUNT(*) AS c
                FROM dws_logistics_detail_union
                WHERE source_type = :source_type {filter_sql}
                """
            ),
            params,
        )
        return int(result.scalar() or 0)

    def _count_monthly_rows(self, db: Session, target_year_month_list: list[str] | None) -> int:
        filter_sql, params = self._ym_filter_sql(target_year_month_list, "biz_month")
        result = db.execute(
            text(f"SELECT COUNT(*) AS c FROM dws_logistics_monthly_metric WHERE 1=1 {filter_sql}"),
            params,
        )
        return int(result.scalar() or 0)

    def _count_dm_rows(self, db: Session, target_year_month_list: list[str] | None) -> int:
        filter_sql, params = self._ym_filter_sql(target_year_month_list, "biz_month")
        result = db.execute(
            text(f"SELECT COUNT(*) AS c FROM dm_logistics_company_month_rank WHERE 1=1 {filter_sql}"),
            params,
        )
        return int(result.scalar() or 0)

    def _ensure_detail_union_plate_number_capacity(self, db: Session) -> None:
        current_length = db.execute(
            text(
                """
                SELECT CHARACTER_MAXIMUM_LENGTH
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'dws_logistics_detail_union'
                  AND COLUMN_NAME = 'plate_number'
                """
            )
        ).scalar()
        if current_length is None:
            raise RuntimeError("dws_logistics_detail_union.plate_number 不存在")
        if int(current_length) >= self.DETAIL_UNION_PLATE_NUMBER_MAX_LEN:
            return
        logger.info(
            "alter dws_logistics_detail_union.plate_number from %s to %s",
            current_length,
            self.DETAIL_UNION_PLATE_NUMBER_MAX_LEN,
        )
        db.execute(
            text(
                f"""
                ALTER TABLE dws_logistics_detail_union
                MODIFY COLUMN plate_number VARCHAR({self.DETAIL_UNION_PLATE_NUMBER_MAX_LEN}) DEFAULT NULL
                """
            )
        )
        db.commit()

    def _create_task_log(self, db: Session, task_id: str) -> None:
        db.execute(
            text(
                """
                INSERT INTO sys_task_log (
                    task_id, task_type, task_name, biz_domain, status, source_code, started_at, created_at, updated_at
                )
                VALUES (
                    :task_id, 'SERVING_REFRESH', 'refresh logistics serving layer', 'logistics', 'RUNNING',
                    'serving_refresh', NOW(), NOW(), NOW()
                )
                """
            ),
            {"task_id": task_id},
        )
        db.commit()

    def _finish_task_log(self, db: Session, task_id: str, status: str, stats: RefreshStats) -> None:
        total = stats.hist_detail_rows + stats.sys_detail_rows + stats.monthly_rows + stats.dm_rank_rows
        db.execute(
            text(
                """
                UPDATE sys_task_log
                SET status=:status,
                    total_count=:total,
                    success_count=:total,
                    fail_count=0,
                    message=:message,
                    finished_at=NOW(),
                    updated_at=NOW()
                WHERE task_id=:task_id
                """
            ),
            {
                "task_id": task_id,
                "status": status,
                "total": total,
                "message": str(stats.__dict__)[:2000],
            },
        )
        db.commit()

    def _fail_task_log(self, db: Session, task_id: str, message: str) -> None:
        try:
            db.execute(
                text(
                    """
                    UPDATE sys_task_log
                    SET status='FAILED',
                        fail_count=1,
                        message=:message,
                        finished_at=NOW(),
                        updated_at=NOW()
                    WHERE task_id=:task_id
                    """
                ),
                {"task_id": task_id, "message": message[:2000]},
            )
            db.commit()
        except Exception:
            logger.exception("failed to update serving refresh task log")

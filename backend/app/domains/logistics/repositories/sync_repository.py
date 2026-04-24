from __future__ import annotations

import logging
from typing import Any, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.db.session import SourceSessionLocal

logger = logging.getLogger(__name__)


class LogisticsSyncRepository:
    """物流系统同步仓储。

    设计原则：
    1. 源库读取和目标库写入统一收口到 repository，service 只负责业务编排；
    2. 目标表结构以一期初始化脚本为准，当前使用原生 SQL 是为了精确控制 upsert 行为；
    3. 这里不尝试接入二期对象，避免把未落表的逻辑混入一期主链路。
    """

    # 分批查询时每批最大 ID 数量
    # 远程 MySQL 5.6 对 IN 子句参数数量敏感，即使 100 个参数在复杂查询下
    # 仍可能触发 Lost connection during query。进一步降低到 30，
    # 以减小单批 SQL 体积和网络传输压力，提高连接稳定性。
    _CHUNK_SIZE = 30

    def __init__(self, *, db: Session, source_db: Session) -> None:
        self.db = db
        self.source_db = source_db

    def ensure_extended_columns(self) -> None:
        """确保物流数据问答 MVP 需要的扩展字段已落到 ODS/DWD。

        说明：
            1. 这里优先补 2026 最终口径要求的关键字段；
            2. 使用 IF NOT EXISTS 避免重复执行报错；
            3. 对历史已同步数据，只做结构补齐，不伪造字段值。
        """
        column_specs = [
            ("ods_logistic_ship_task", "project_name", "VARCHAR(255) NULL AFTER company_id"),
            ("ods_logistic_ship_task", "pickup_date", "DATE NULL AFTER project_name"),
            ("ods_logistic_ship_task", "expand_dept", "VARCHAR(128) NULL AFTER ship_type"),
            ("ods_logistic_ship_task", "entrusted_person", "VARCHAR(128) NULL AFTER expand_dept"),
            ("ods_logistic_ship_product", "price", "DECIMAL(18,2) NULL AFTER quantity"),
            ("dwd_logistics_ship_task", "project_name", "VARCHAR(255) NULL AFTER company_name"),
            ("dwd_logistics_ship_task", "pickup_date", "DATE NULL AFTER project_name"),
            ("dwd_logistics_ship_task", "expand_dept", "VARCHAR(128) NULL AFTER ship_type"),
            ("dwd_logistics_ship_task", "entrusted_person", "VARCHAR(128) NULL AFTER expand_dept"),
            ("dwd_logistics_ship_task", "normalized_region_name", "VARCHAR(32) NULL AFTER delivery_area"),
            ("dwd_logistics_ship_task", "region_resolve_source", "VARCHAR(32) NULL AFTER normalized_region_name"),
            ("dwd_logistics_ship_product", "price", "DECIMAL(18,2) NULL AFTER quantity"),
        ]
        for table_name, column_name, column_sql in column_specs:
            self._ensure_column(table_name=table_name, column_name=column_name, column_sql=column_sql)
        self.db.commit()

    def _ensure_column(self, *, table_name: str, column_name: str, column_sql: str) -> None:
        """按当前 MySQL 版本可兼容的方式补齐字段。

        说明：
            1. 本机 MySQL 版本不支持 ADD COLUMN IF NOT EXISTS；
            2. 因此先查 information_schema，再决定是否执行 ALTER；
            3. 这里只做结构补齐，不对字段值做伪造。
        """
        exists = self.db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = :table_name
                  AND COLUMN_NAME = :column_name
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        ).scalar()
        if exists:
            return
        self.db.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"))

    # =========================
    # SYS task log
    # =========================
    def create_task_log(
        self,
        *,
        task_id: str,
        task_type: str,
        task_name: str,
        source_code: str,
    ) -> None:
        self.db.execute(
            text(
                """
                INSERT INTO sys_task_log (
                    task_id, task_type, task_name, biz_domain, status, source_code, started_at, created_at, updated_at
                ) VALUES (
                    :task_id, :task_type, :task_name, 'logistics', 'RUNNING', :source_code, NOW(), NOW(), NOW()
                )
                """
            ),
            {
                "task_id": task_id,
                "task_type": task_type,
                "task_name": task_name,
                "source_code": source_code,
            },
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
                SET status = :status,
                    total_count = :total_count,
                    success_count = :success_count,
                    fail_count = :fail_count,
                    message = :message,
                    finished_at = NOW(),
                    updated_at = NOW()
                WHERE task_id = :task_id
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
        source_table_name: str | None = None,
        source_pk: str | None = None,
        raw_payload: str | None = None,
    ) -> None:
        self.db.execute(
            text(
                """
                INSERT INTO sys_task_error_log (
                    task_id, error_stage, source_table_name, source_pk, error_message, raw_payload, created_at
                ) VALUES (
                    :task_id, :error_stage, :source_table_name, :source_pk, :error_message, CAST(:raw_payload AS JSON), NOW()
                )
                """
            ),
            {
                "task_id": task_id,
                "error_stage": error_stage,
                "source_table_name": source_table_name,
                "source_pk": source_pk,
                "error_message": error_message[:4000],
                "raw_payload": raw_payload,
            },
        )
        self.db.commit()

    # =========================
    # Source fetch helpers
    # =========================
    def fetch_companies(self) -> list[dict[str, Any]]:
        sql = text(
            """
            SELECT
                company_id AS source_id,
                company_name,
                base_code AS company_code,
                del_flag
            FROM logistic_logistic_company
            ORDER BY company_id ASC
            """
        )
        return [dict(row._mapping) for row in self.source_db.execute(sql)]

    def fetch_warehouses(self) -> list[dict[str, Any]]:
        sql = text(
            """
            SELECT
                warehouse_id AS source_id,
                warehouse_name,
                base_code AS warehouse_code,
                del_flag
            FROM logistic_warehouse
            ORDER BY warehouse_id ASC
            """
        )
        return [dict(row._mapping) for row in self.source_db.execute(sql)]

    def fetch_ship_tasks(
        self,
        *,
        start_date: str,
        updated_since: str | None,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        filters = ["DATE(create_time) >= :start_date"]
        params: dict[str, Any] = {
            "start_date": start_date,
            "limit": limit,
            "offset": offset,
        }
        if updated_since:
            filters.append("update_time >= :updated_since")
            params["updated_since"] = updated_since
        sql = text(
            f"""
            SELECT
                task_id AS source_id,
                task_id,
                company_id,
                project_name,
                pickup_date,
                NULL AS warehouse_id,
                status,
                ship_type,
                expand_dept,
                entrusted_person,
                transport,
                contract_number,
                inquiry_number,
                bidding_number,
                shipping_instruction,
                rd_number,
                procurement_type, car_model, loading_trucks,
                delivery_province, delivery_city, delivery_area, delivery_distance,
                reconciliation_status, extra_cost_audited, base_code, del_flag,
                DATE(create_time) AS biz_date,
                create_time AS created_at,
                update_time AS updated_at
            FROM logistic_ship_task
            WHERE {' AND '.join(filters)}
            ORDER BY create_time ASC, task_id ASC
            LIMIT :limit OFFSET :offset
            """
        )
        return [dict(row._mapping) for row in self.source_db.execute(sql, params)]

    def fetch_ship_products_by_task_ids(self, task_ids: Sequence[str]) -> list[dict[str, Any]]:
        """根据发货任务 ID 列表批量查询发货产品，使用分批查询避免 IN 子句过大。"""
        if not task_ids:
            return []
        return self._chunked_fetch(
            """
            SELECT
                product_id AS source_id,
                task_id,
                product_name AS product_code,
                specification AS product_spec,
                power,
                quantity,
                price,
                unit,
                extra_cost,
                base_code,
                del_flag,
                create_time AS created_at,
                update_time AS updated_at
            FROM logistic_ship_product
            WHERE task_id IN :values
            ORDER BY product_id ASC
            """,
            task_ids,
        )

    def fetch_assign_tasks_by_ship_task_ids(self, ship_task_ids: Sequence[str]) -> list[dict[str, Any]]:
        """根据发货任务 ID 列表批量查询派车任务，使用分批查询避免 IN 子句过大。"""
        if not ship_task_ids:
            return []
        return self._chunked_fetch(
            """
            SELECT
                at.task_id AS source_id,
                at.task_id,
                at.ship_task_id,
                st.company_id,
                NULL AS warehouse_id,
                at.status,
                at.plate_number,
                at.driver_name,
                at.phone AS driver_phone,
                at.id_number AS driver_id_number,
                at.enter_time,
                at.delivery_note_parse_status,
                at.base_code,
                at.del_flag,
                at.create_time AS created_at,
                at.update_time AS updated_at
            FROM logistic_assign_task AS at
            LEFT JOIN logistic_ship_task st ON st.task_id = at.ship_task_id
            WHERE at.ship_task_id IN :values
            ORDER BY at.create_time ASC, at.task_id ASC
            """,
            ship_task_ids,
        )

    def fetch_assign_details_by_assign_task_ids(self, assign_task_ids: Sequence[str]) -> list[dict[str, Any]]:
        """根据派车任务 ID 列表批量查询派车明细，使用分批查询避免 IN 子句过大。"""
        if not assign_task_ids:
            return []
        return self._chunked_fetch(
            """
            SELECT
                d.detail_id AS source_id,
                d.assign_task_id,
                at.ship_task_id,
                d.ship_product_id AS product_id,
                d.quantity,
                d.supplier_price,
                d.extra_cost,
                d.cost_proof_url,
                d.base_code,
                d.del_flag,
                d.create_time AS created_at,
                d.update_time AS updated_at
            FROM logistic_assign_detail AS d
            LEFT JOIN logistic_assign_task at ON at.task_id = d.assign_task_id
            WHERE d.assign_task_id IN :values
            ORDER BY d.create_time ASC, d.detail_id ASC
            """,
            assign_task_ids,
        )

    # =========================
    # ODS upsert
    # =========================
    def upsert_ods_companies(self, sync_batch_no: str, rows: Sequence[dict[str, Any]]) -> int:
        if not rows:
            return 0
        sql = text(
            """
            INSERT INTO ods_logistic_company (
                sync_batch_no, source_id, company_code, company_name, base_code, del_flag, raw_json, created_at
            ) VALUES (
                :sync_batch_no, :source_id, :company_code, :company_name, :base_code, :del_flag, CAST(:raw_json AS JSON), NOW()
            )
            ON DUPLICATE KEY UPDATE
                company_code = VALUES(company_code),
                company_name = VALUES(company_name),
                base_code = VALUES(base_code),
                del_flag = VALUES(del_flag),
                raw_json = VALUES(raw_json)
            """
        )
        payload = [{**row, "sync_batch_no": sync_batch_no} for row in rows]
        self.db.execute(sql, payload)
        self.db.commit()
        return len(payload)

    def upsert_ods_warehouses(self, sync_batch_no: str, rows: Sequence[dict[str, Any]]) -> int:
        if not rows:
            return 0
        sql = text(
            """
            INSERT INTO ods_logistic_warehouse (
                sync_batch_no, source_id, warehouse_code, warehouse_name, base_code, del_flag, raw_json, created_at
            ) VALUES (
                :sync_batch_no, :source_id, :warehouse_code, :warehouse_name, :base_code, :del_flag, CAST(:raw_json AS JSON), NOW()
            )
            ON DUPLICATE KEY UPDATE
                warehouse_code = VALUES(warehouse_code),
                warehouse_name = VALUES(warehouse_name),
                base_code = VALUES(base_code),
                del_flag = VALUES(del_flag),
                raw_json = VALUES(raw_json)
            """
        )
        payload = [{**row, "sync_batch_no": sync_batch_no} for row in rows]
        self.db.execute(sql, payload)
        self.db.commit()
        return len(payload)

    def upsert_ods_ship_tasks(self, sync_batch_no: str, rows: Sequence[dict[str, Any]]) -> int:
        if not rows:
            return 0
        sql = text(
            """
            INSERT INTO ods_logistic_ship_task (
                sync_batch_no, source_id, task_id, company_id, project_name, pickup_date, warehouse_id, status, ship_type, expand_dept, entrusted_person, transport,
                contract_number, inquiry_number, bidding_number, shipping_instruction, rd_number,
                procurement_type, car_model, loading_trucks,
                delivery_province, delivery_city, delivery_area, delivery_distance,
                reconciliation_status, extra_cost_audited, base_code, del_flag,
                biz_date, source_created_at, source_updated_at, raw_json, created_at
            ) VALUES (
                :sync_batch_no, :source_id, :task_id, :company_id, :project_name, :pickup_date, :warehouse_id, :status, :ship_type, :expand_dept, :entrusted_person, :transport,
                :contract_number, :inquiry_number, :bidding_number, :shipping_instruction, :rd_number,
                :procurement_type, :car_model, :loading_trucks,
                :delivery_province, :delivery_city, :delivery_area, :delivery_distance,
                :reconciliation_status, :extra_cost_audited, :base_code, :del_flag,
                :biz_date, :created_at, :updated_at, CAST(:raw_json AS JSON), NOW()
            )
            ON DUPLICATE KEY UPDATE
                task_id = VALUES(task_id), company_id = VALUES(company_id), project_name = VALUES(project_name),
                pickup_date = VALUES(pickup_date), warehouse_id = VALUES(warehouse_id),
                status = VALUES(status), ship_type = VALUES(ship_type), expand_dept = VALUES(expand_dept),
                entrusted_person = VALUES(entrusted_person), transport = VALUES(transport),
                contract_number = VALUES(contract_number), inquiry_number = VALUES(inquiry_number),
                bidding_number = VALUES(bidding_number), shipping_instruction = VALUES(shipping_instruction),
                rd_number = VALUES(rd_number), procurement_type = VALUES(procurement_type),
                car_model = VALUES(car_model), loading_trucks = VALUES(loading_trucks),
                delivery_province = VALUES(delivery_province), delivery_city = VALUES(delivery_city),
                delivery_area = VALUES(delivery_area), delivery_distance = VALUES(delivery_distance),
                reconciliation_status = VALUES(reconciliation_status), extra_cost_audited = VALUES(extra_cost_audited),
                base_code = VALUES(base_code), del_flag = VALUES(del_flag), biz_date = VALUES(biz_date),
                source_created_at = VALUES(source_created_at), source_updated_at = VALUES(source_updated_at),
                raw_json = VALUES(raw_json)
            """
        )
        payload = [{**row, "sync_batch_no": sync_batch_no} for row in rows]
        self.db.execute(sql, payload)
        self.db.commit()
        return len(payload)

    def upsert_ods_ship_products(self, sync_batch_no: str, rows: Sequence[dict[str, Any]]) -> int:
        if not rows:
            return 0
        sql = text(
            """
            INSERT INTO ods_logistic_ship_product (
                sync_batch_no, source_id, task_id, product_code, product_spec, power, quantity, price, unit,
                extra_cost, base_code, del_flag, source_created_at, source_updated_at, raw_json, created_at
            ) VALUES (
                :sync_batch_no, :source_id, :task_id, :product_code, :product_spec, :power, :quantity, :price, :unit,
                :extra_cost, :base_code, :del_flag, :created_at, :updated_at, CAST(:raw_json AS JSON), NOW()
            )
            ON DUPLICATE KEY UPDATE
                task_id = VALUES(task_id), product_code = VALUES(product_code), product_spec = VALUES(product_spec),
                power = VALUES(power), quantity = VALUES(quantity), price = VALUES(price),
                unit = VALUES(unit), extra_cost = VALUES(extra_cost),
                base_code = VALUES(base_code), del_flag = VALUES(del_flag), source_created_at = VALUES(source_created_at),
                source_updated_at = VALUES(source_updated_at), raw_json = VALUES(raw_json)
            """
        )
        payload = [{**row, "sync_batch_no": sync_batch_no} for row in rows]
        self.db.execute(sql, payload)
        self.db.commit()
        return len(payload)

    def upsert_ods_assign_tasks(self, sync_batch_no: str, rows: Sequence[dict[str, Any]]) -> int:
        if not rows:
            return 0
        sql = text(
            """
            INSERT INTO ods_logistic_assign_task (
                sync_batch_no, source_id, task_id, ship_task_id, company_id, warehouse_id, status, plate_number,
                driver_name, driver_phone, driver_id_number, enter_time, delivery_note_parse_status,
                base_code, del_flag, source_created_at, source_updated_at, raw_json, created_at
            ) VALUES (
                :sync_batch_no, :source_id, :task_id, :ship_task_id, :company_id, :warehouse_id, :status, :plate_number,
                :driver_name, :driver_phone, :driver_id_number, :enter_time, :delivery_note_parse_status,
                :base_code, :del_flag, :created_at, :updated_at, CAST(:raw_json AS JSON), NOW()
            )
            ON DUPLICATE KEY UPDATE
                task_id = VALUES(task_id), ship_task_id = VALUES(ship_task_id), company_id = VALUES(company_id),
                warehouse_id = VALUES(warehouse_id), status = VALUES(status), plate_number = VALUES(plate_number),
                driver_name = VALUES(driver_name), driver_phone = VALUES(driver_phone),
                driver_id_number = VALUES(driver_id_number), enter_time = VALUES(enter_time),
                delivery_note_parse_status = VALUES(delivery_note_parse_status), base_code = VALUES(base_code),
                del_flag = VALUES(del_flag), source_created_at = VALUES(source_created_at),
                source_updated_at = VALUES(source_updated_at), raw_json = VALUES(raw_json)
            """
        )
        payload = [{**row, "sync_batch_no": sync_batch_no} for row in rows]
        self.db.execute(sql, payload)
        self.db.commit()
        return len(payload)

    def upsert_ods_assign_details(self, sync_batch_no: str, rows: Sequence[dict[str, Any]]) -> int:
        if not rows:
            return 0
        sql = text(
            """
            INSERT INTO ods_logistic_assign_detail (
                sync_batch_no, source_id, assign_task_id, ship_task_id, product_id, quantity, supplier_price,
                extra_cost, cost_proof_url, base_code, del_flag, source_created_at, source_updated_at, raw_json, created_at
            ) VALUES (
                :sync_batch_no, :source_id, :assign_task_id, :ship_task_id, :product_id, :quantity, :supplier_price,
                :extra_cost, :cost_proof_url, :base_code, :del_flag, :created_at, :updated_at, CAST(:raw_json AS JSON), NOW()
            )
            ON DUPLICATE KEY UPDATE
                assign_task_id = VALUES(assign_task_id), ship_task_id = VALUES(ship_task_id),
                product_id = VALUES(product_id), quantity = VALUES(quantity),
                supplier_price = VALUES(supplier_price), extra_cost = VALUES(extra_cost),
                cost_proof_url = VALUES(cost_proof_url), base_code = VALUES(base_code),
                del_flag = VALUES(del_flag), source_created_at = VALUES(source_created_at),
                source_updated_at = VALUES(source_updated_at), raw_json = VALUES(raw_json)
            """
        )
        payload = [{**row, "sync_batch_no": sync_batch_no} for row in rows]
        self.db.execute(sql, payload)
        self.db.commit()
        return len(payload)

    # =========================
    # DWD rebuild/upsert
    # =========================
    def rebuild_dwd_company(self, sync_batch_no: str) -> int:
        # 风险：该维表采用全量重建策略，运行前必须确认不会影响并发查询窗口。
        self.db.execute(text("DELETE FROM dwd_logistics_company"))
        self.db.execute(
            text(
                """
                INSERT INTO dwd_logistics_company (source_id, company_code, company_name, created_at)
                SELECT source_id, company_code, company_name, NOW()
                FROM ods_logistic_company
                WHERE sync_batch_no = :sync_batch_no AND COALESCE(del_flag, '0') = '0'
                """
            ),
            {"sync_batch_no": sync_batch_no},
        )
        self.db.commit()
        return self.scalar("SELECT COUNT(*) FROM dwd_logistics_company")

    def rebuild_dwd_warehouse(self, sync_batch_no: str) -> int:
        # 风险：该维表采用全量重建策略，运行前必须确认不会影响并发查询窗口。
        self.db.execute(text("DELETE FROM dwd_logistics_warehouse"))
        self.db.execute(
            text(
                """
                INSERT INTO dwd_logistics_warehouse (source_id, warehouse_code, warehouse_name, created_at)
                SELECT source_id, warehouse_code, warehouse_name, NOW()
                FROM ods_logistic_warehouse
                WHERE sync_batch_no = :sync_batch_no AND COALESCE(del_flag, '0') = '0'
                """
            ),
            {"sync_batch_no": sync_batch_no},
        )
        self.db.commit()
        return self.scalar("SELECT COUNT(*) FROM dwd_logistics_warehouse")

    def upsert_dwd_ship_task(self, sync_batch_no: str) -> int:
        self.db.execute(
            text(
                """
                INSERT INTO dwd_logistics_ship_task (
                    source_id, task_id, company_id, company_name, warehouse_id, warehouse_name, status, ship_type,
                    project_name, pickup_date, expand_dept, entrusted_person,
                    transport_mode, contract_no, inquiry_no, bidding_no, ship_instruction_no, rd_no,
                    procurement_type, car_model, loading_trucks,
                    delivery_province, delivery_city, delivery_area, normalized_region_name, region_resolve_source, delivery_distance,
                    reconciliation_status, extra_cost_audited, base_code, del_flag,
                    biz_date, biz_year, biz_month, is_formal_data, created_at, updated_at
                )
                SELECT
                    s.source_id,
                    s.task_id,
                    s.company_id,
                    c.company_name,
                    s.warehouse_id,
                    w.warehouse_name,
                    s.status,
                    s.ship_type,
                    s.project_name,
                    s.pickup_date,
                    s.expand_dept,
                    s.entrusted_person,
                    s.transport,
                    s.contract_number,
                    s.inquiry_number,
                    s.bidding_number,
                    s.shipping_instruction,
                    s.rd_number,
                    s.procurement_type,
                    s.car_model,
                    s.loading_trucks,
                    s.delivery_province,
                    s.delivery_city,
                    s.delivery_area,
                    CASE
                        WHEN NULLIF(TRIM(s.delivery_area), '') IS NOT NULL THEN TRIM(s.delivery_area)
                        WHEN s.delivery_province IN ('上海市', '江苏省', '浙江省', '安徽省', '福建省', '江西省', '山东省') THEN '华东'
                        WHEN s.delivery_province IN ('广东省', '广西壮族自治区', '海南省') THEN '华南'
                        WHEN s.delivery_province IN ('河南省', '湖北省', '湖南省') THEN '华中'
                        WHEN s.delivery_province IN ('北京市', '天津市', '河北省', '山西省', '内蒙古自治区') THEN '华北'
                        WHEN s.delivery_province IN ('重庆市', '四川省', '贵州省', '云南省', '西藏自治区') THEN '西南'
                        WHEN s.delivery_province IN ('陕西省', '甘肃省', '青海省', '宁夏回族自治区', '新疆维吾尔自治区') THEN '西北'
                        WHEN s.delivery_province IN ('辽宁省', '吉林省', '黑龙江省') THEN '东北'
                        ELSE '其他'
                    END,
                    CASE
                        WHEN NULLIF(TRIM(s.delivery_area), '') IS NOT NULL THEN 'delivery_area'
                        WHEN s.delivery_province IS NOT NULL AND s.delivery_province <> '' THEN 'delivery_province'
                        ELSE 'other'
                    END,
                    s.delivery_distance,
                    s.reconciliation_status,
                    s.extra_cost_audited,
                    s.base_code,
                    s.del_flag,
                    s.biz_date,
                    YEAR(s.biz_date),
                    DATE_FORMAT(s.biz_date, '%Y-%m'),
                    1,
                    NOW(),
                    NOW()
                FROM ods_logistic_ship_task s
                LEFT JOIN dwd_logistics_company c ON s.company_id = c.source_id
                LEFT JOIN dwd_logistics_warehouse w ON s.warehouse_id = w.source_id
                WHERE s.sync_batch_no = :sync_batch_no
                  AND COALESCE(s.del_flag, '0') = '0'
                  AND s.biz_date >= '2026-01-01'
                ON DUPLICATE KEY UPDATE
                    company_id = VALUES(company_id), company_name = VALUES(company_name),
                    warehouse_id = VALUES(warehouse_id), warehouse_name = VALUES(warehouse_name),
                    status = VALUES(status), ship_type = VALUES(ship_type),
                    project_name = VALUES(project_name), pickup_date = VALUES(pickup_date),
                    expand_dept = VALUES(expand_dept), entrusted_person = VALUES(entrusted_person),
                    transport_mode = VALUES(transport_mode),
                    contract_no = VALUES(contract_no), inquiry_no = VALUES(inquiry_no), bidding_no = VALUES(bidding_no),
                    ship_instruction_no = VALUES(ship_instruction_no), rd_no = VALUES(rd_no),
                    procurement_type = VALUES(procurement_type), car_model = VALUES(car_model),
                    loading_trucks = VALUES(loading_trucks), delivery_province = VALUES(delivery_province),
                    delivery_city = VALUES(delivery_city), delivery_area = VALUES(delivery_area),
                    normalized_region_name = VALUES(normalized_region_name),
                    region_resolve_source = VALUES(region_resolve_source),
                    delivery_distance = VALUES(delivery_distance), reconciliation_status = VALUES(reconciliation_status),
                    extra_cost_audited = VALUES(extra_cost_audited), base_code = VALUES(base_code),
                    del_flag = VALUES(del_flag), biz_date = VALUES(biz_date), biz_year = VALUES(biz_year),
                    biz_month = VALUES(biz_month), is_formal_data = VALUES(is_formal_data), updated_at = NOW()
                """
            ),
            {"sync_batch_no": sync_batch_no},
        )
        self.db.commit()
        return self.scalar("SELECT COUNT(*) FROM dwd_logistics_ship_task")

    def upsert_dwd_ship_product(self, sync_batch_no: str) -> int:
        self.db.execute(
            text(
                """
                INSERT INTO dwd_logistics_ship_product (
                    source_id, task_id, product_code, product_spec, power, quantity, price, unit, extra_cost, created_at
                )
                SELECT source_id, task_id, product_code, product_spec, power, quantity, price, unit, extra_cost, NOW()
                FROM ods_logistic_ship_product
                WHERE sync_batch_no = :sync_batch_no
                  AND COALESCE(del_flag, '0') = '0'
                  AND task_id IN (SELECT task_id FROM dwd_logistics_ship_task)
                ON DUPLICATE KEY UPDATE
                    task_id = VALUES(task_id), product_code = VALUES(product_code),
                    product_spec = VALUES(product_spec), power = VALUES(power),
                    quantity = VALUES(quantity), price = VALUES(price),
                    unit = VALUES(unit), extra_cost = VALUES(extra_cost)
                """
            ),
            {"sync_batch_no": sync_batch_no},
        )
        self.db.commit()
        return self.scalar("SELECT COUNT(*) FROM dwd_logistics_ship_product")

    def upsert_dwd_assign_task(self, sync_batch_no: str) -> int:
        self.db.execute(
            text(
                """
                INSERT INTO dwd_logistics_assign_task (
                    source_id, task_id, ship_task_id, company_id, company_name, warehouse_id, warehouse_name, status,
                    plate_number, driver_name, driver_phone, driver_id_number, enter_time, delivery_note_parse_status, created_at
                )
                SELECT
                    a.source_id,
                    a.task_id,
                    a.ship_task_id,
                    a.company_id,
                    c.company_name,
                    a.warehouse_id,
                    w.warehouse_name,
                    a.status,
                    a.plate_number,
                    a.driver_name,
                    a.driver_phone,
                    a.driver_id_number,
                    a.enter_time,
                    a.delivery_note_parse_status,
                    NOW()
                FROM ods_logistic_assign_task a
                LEFT JOIN dwd_logistics_company c ON a.company_id = c.source_id
                LEFT JOIN dwd_logistics_warehouse w ON a.warehouse_id = w.source_id
                WHERE a.sync_batch_no = :sync_batch_no
                  AND COALESCE(a.del_flag, '0') = '0'
                  AND a.ship_task_id IN (SELECT task_id FROM dwd_logistics_ship_task)
                ON DUPLICATE KEY UPDATE
                    ship_task_id = VALUES(ship_task_id), company_id = VALUES(company_id),
                    company_name = VALUES(company_name), warehouse_id = VALUES(warehouse_id),
                    warehouse_name = VALUES(warehouse_name), status = VALUES(status),
                    plate_number = VALUES(plate_number), driver_name = VALUES(driver_name),
                    driver_phone = VALUES(driver_phone), driver_id_number = VALUES(driver_id_number),
                    enter_time = VALUES(enter_time), delivery_note_parse_status = VALUES(delivery_note_parse_status)
                """
            ),
            {"sync_batch_no": sync_batch_no},
        )
        self.db.commit()
        return self.scalar("SELECT COUNT(*) FROM dwd_logistics_assign_task")

    def upsert_dwd_assign_detail(self, sync_batch_no: str) -> int:
        self.db.execute(
            text(
                """
                INSERT INTO dwd_logistics_assign_detail (
                    source_id, assign_task_id, ship_task_id, product_source_id, quantity, supplier_price,
                    extra_cost, cost_proof_url, created_at
                )
                SELECT
                    d.source_id,
                    d.assign_task_id,
                    d.ship_task_id,
                    d.product_id,
                    d.quantity,
                    d.supplier_price,
                    d.extra_cost,
                    d.cost_proof_url,
                    NOW()
                FROM ods_logistic_assign_detail d
                WHERE d.sync_batch_no = :sync_batch_no
                  AND COALESCE(d.del_flag, '0') = '0'
                  AND d.assign_task_id IN (SELECT task_id FROM dwd_logistics_assign_task)
                """
            ),
            {"sync_batch_no": sync_batch_no},
        )
        self.db.commit()
        return self.scalar("SELECT COUNT(*) FROM dwd_logistics_assign_detail")

    def cleanup_dwd_assign_detail_duplicates(self) -> None:
        # 风险：这里依赖目标表存在自增主键 `id`，如果线上表结构不同，需要先调整去重 SQL。
        self.db.execute(
            text(
                """
                DELETE t1 FROM dwd_logistics_assign_detail t1
                INNER JOIN dwd_logistics_assign_detail t2
                    ON t1.source_id = t2.source_id AND t1.id > t2.id
                """
            )
        )
        self.db.commit()

    def scalar(self, sql: str, params: dict[str, Any] | None = None) -> int:
        return int(self.db.execute(text(sql), params or {}).scalar() or 0)

    def _chunked_fetch(
        self,
        sql_tpl: str,
        ids: Sequence[str],
    ) -> list[dict[str, Any]]:
        """分批查询辅助方法，将大批量 ID 拆分为多批执行 SQL 后合并结果。

        解决问题：
            当 ID 数量过大（如 1000+）时，一次性放入 IN 子句会导致
            生成的 SQL 体积过大，远程 MySQL 5.6 服务器可能断开连接
            （Lost connection during query）。

        参数：
            sql_tpl: 包含 :values 占位符的 SQL 模板字符串，
                     与 _in_sql 方法的 sql_tpl 格式一致。
            ids: 需要查询的 ID 序列。

        返回：
            合并后的全部查询结果列表，每项为字典。
            多批结果按批次顺序拼接，同批次内保持 SQL 中的 ORDER BY 排序。

        重试机制：
            每批次查询如果因连接断开失败，会自动关闭旧 session、
            从 SourceSessionLocal 创建新连接后重试，最多重试 2 次。
            非连接类异常直接抛出，不会进入重试。
        """
        if not ids:
            return []
        all_rows: list[dict[str, Any]] = []
        # 将 ID 序列按分批大小切片，逐批查询
        for start in range(0, len(ids), self._CHUNK_SIZE):
            chunk = ids[start : start + self._CHUNK_SIZE]
            rows = self._execute_chunk_with_retry(sql_tpl, chunk)
            all_rows.extend(rows)
        return all_rows

    def _execute_chunk_with_retry(
        self,
        sql_tpl: str,
        chunk: Sequence[str],
        max_retries: int = 2,
    ) -> list[dict[str, Any]]:
        """执行单批次源库查询，带连接断开自动重试。

        参数：
            sql_tpl: SQL 模板字符串，含 :values 占位符。
            chunk: 当前批次的 ID 列表。
            max_retries: 最大重试次数（不含首次尝试）。

        返回：
            当前批次的查询结果列表。

        逻辑说明：
            1. 首次使用当前 self.source_db 执行查询；
            2. 若抛出异常且错误信息包含连接断开关键字，
               则关闭旧 session、从 SourceSessionLocal 创建新 session
               并更新 self.source_db，然后重试；
            3. 若非连接类异常，直接抛出；
            4. 重试次数耗尽后仍失败，抛出最后一次异常。
        """
        sql, params = self._in_sql(sql_tpl, chunk)
        last_exception: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                return [dict(row._mapping) for row in self.source_db.execute(sql, params)]
            except Exception as exc:
                last_exception = exc
                error_msg = str(exc).lower()
                # 仅对连接断开类异常进行重试
                if any(
                    keyword in error_msg
                    for keyword in ("lost connection", "mysql server has gone away", "broken pipe")
                ):
                    logger.warning(
                        f"源库连接断开，批次查询第 {attempt + 1}/{max_retries + 1} 次尝试失败，"
                        f"准备重建连接后重试: {exc}"
                    )
                    try:
                        self.source_db.close()
                    except Exception:
                        pass
                    self.source_db = SourceSessionLocal()
                else:
                    # 非连接类异常直接抛出，不重试
                    raise

        # 重试次数耗尽，抛出最后一次异常
        raise last_exception  # type: ignore[misc]

    @staticmethod
    def _in_sql(sql_tpl: str, values: Sequence[Any]) -> tuple[Any, dict[str, Any]]:
        placeholders = ",".join(f":v{i}" for i in range(len(values)))
        sql = text(sql_tpl.replace(":values", f"({placeholders})"))
        params = {f"v{i}": value for i, value in enumerate(values)}
        return sql, params

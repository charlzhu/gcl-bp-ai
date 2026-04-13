from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Iterable, Sequence

from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal, SourceSessionLocal
from backend.app.domains.logistics.repositories.sync_repository import LogisticsSyncRepository
from backend.app.domains.logistics.schemas.sync import LogisticsSystemSyncRequest, LogisticsSystemSyncResult

logger = logging.getLogger(__name__)


@dataclass
class SyncStats:
    """同步过程统计。

    `ship_task` 是主链路锚点，其余表都依赖它向下展开。
    """

    ship_task_count: int = 0
    ship_product_count: int = 0
    assign_task_count: int = 0
    assign_detail_count: int = 0
    company_count: int = 0
    warehouse_count: int = 0
    dwd_company_count: int = 0
    dwd_warehouse_count: int = 0
    dwd_ship_task_count: int = 0
    dwd_ship_product_count: int = 0
    dwd_assign_task_count: int = 0
    dwd_assign_detail_count: int = 0


class LogisticsSystemSyncService:
    """物流系统同步服务。

    当前版本只覆盖一期主链路，不包含：
    1. allocate_task / allocate_detail
    2. delivery_note
    3. 图片、打卡、轨迹类数据

    风险说明：
    1. 真实运行依赖本地 ODS/DWD/SYS 表结构已提前建好；
    2. `dry_run=False` 时会写 ODS 和 DWD，且公司/仓库维表会执行全量重建；
    3. 当前实现按阶段提交，不是单事务全量回滚模型，失败后可能留下已成功写入的阶段数据；
    4. 当前实现为同步阻塞调用，适合管理后台手动触发，不适合直接挂到高频前台入口。
    """

    def sync_formal_data(self, req: LogisticsSystemSyncRequest) -> LogisticsSystemSyncResult:
        task_id = f"sys-sync-{uuid.uuid4().hex[:12]}"
        sync_batch_no = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        stats = SyncStats()

        db: Session = SessionLocal()
        source_db: Session = SourceSessionLocal()
        repo = LogisticsSyncRepository(db=db, source_db=source_db)

        try:
            repo.create_task_log(
                task_id=task_id,
                task_type="SYS_SYNC",
                task_name="2026+ formal logistics system sync",
                source_code="logistics_system_mysql",
            )

            if req.sync_companies:
                companies = [self._normalize_company_row(row) for row in repo.fetch_companies()]
                stats.company_count = len(companies)
                if not req.dry_run:
                    repo.upsert_ods_companies(sync_batch_no, companies)

            if req.sync_warehouses:
                warehouses = [self._normalize_warehouse_row(row) for row in repo.fetch_warehouses()]
                stats.warehouse_count = len(warehouses)
                if not req.dry_run:
                    repo.upsert_ods_warehouses(sync_batch_no, warehouses)

            ship_task_rows = self._fetch_all_ship_tasks(repo, req)
            normalized_ship_tasks = [self._normalize_ship_task_row(row) for row in ship_task_rows]
            stats.ship_task_count = len(normalized_ship_tasks)

            if req.sync_ship_tasks and not req.dry_run:
                repo.upsert_ods_ship_tasks(sync_batch_no, normalized_ship_tasks)

            ship_task_ids = [str(row.get("task_id")) for row in normalized_ship_tasks if row.get("task_id")]

            normalized_ship_products: list[dict] = []
            if req.sync_ship_products:
                ship_products: list[dict] = []
                for chunk in self._chunked(ship_task_ids, req.batch_size):
                    ship_products.extend(repo.fetch_ship_products_by_task_ids(chunk))
                normalized_ship_products = [self._normalize_ship_product_row(row) for row in ship_products]
                stats.ship_product_count = len(normalized_ship_products)
                if not req.dry_run:
                    repo.upsert_ods_ship_products(sync_batch_no, normalized_ship_products)

            normalized_assign_tasks: list[dict] = []
            if req.sync_assign_tasks:
                assign_tasks: list[dict] = []
                for chunk in self._chunked(ship_task_ids, req.batch_size):
                    assign_tasks.extend(repo.fetch_assign_tasks_by_ship_task_ids(chunk))
                normalized_assign_tasks = [self._normalize_assign_task_row(row) for row in assign_tasks]
                stats.assign_task_count = len(normalized_assign_tasks)
                if not req.dry_run:
                    repo.upsert_ods_assign_tasks(sync_batch_no, normalized_assign_tasks)

            assign_task_ids = [str(row.get("task_id")) for row in normalized_assign_tasks if row.get("task_id")]
            if req.sync_assign_details:
                assign_details: list[dict] = []
                for chunk in self._chunked(assign_task_ids, req.batch_size):
                    assign_details.extend(repo.fetch_assign_details_by_assign_task_ids(chunk))
                normalized_assign_details = [self._normalize_assign_detail_row(row) for row in assign_details]
                stats.assign_detail_count = len(normalized_assign_details)
                if not req.dry_run:
                    repo.upsert_ods_assign_details(sync_batch_no, normalized_assign_details)

            if not req.dry_run:
                stats.dwd_company_count = repo.rebuild_dwd_company(sync_batch_no)
                stats.dwd_warehouse_count = repo.rebuild_dwd_warehouse(sync_batch_no)
                stats.dwd_ship_task_count = repo.upsert_dwd_ship_task(sync_batch_no)
                stats.dwd_ship_product_count = repo.upsert_dwd_ship_product(sync_batch_no)
                stats.dwd_assign_task_count = repo.upsert_dwd_assign_task(sync_batch_no)
                stats.dwd_assign_detail_count = repo.upsert_dwd_assign_detail(sync_batch_no)
                repo.cleanup_dwd_assign_detail_duplicates()

            total_count = (
                stats.ship_task_count
                + stats.ship_product_count
                + stats.assign_task_count
                + stats.assign_detail_count
                + stats.company_count
                + stats.warehouse_count
            )
            repo.finish_task_log(
                task_id=task_id,
                status="SUCCESS",
                total_count=total_count,
                success_count=total_count,
                fail_count=0,
                message=f"sync_batch_no={sync_batch_no}; dry_run={req.dry_run}",
            )

            return LogisticsSystemSyncResult(
                task_id=task_id,
                sync_batch_no=sync_batch_no,
                dry_run=req.dry_run,
                start_date=req.start_date,
                updated_since=req.updated_since,
                message="system sync success",
                **asdict(stats),
            )
        except Exception as exc:
            logger.exception("logistics system sync failed")
            db.rollback()
            source_db.rollback()
            self._safe_log_failure(repo=repo, task_id=task_id, req=req, exc=exc)
            raise
        finally:
            source_db.close()
            db.close()

    def _safe_log_failure(
        self,
        *,
        repo: LogisticsSyncRepository,
        task_id: str,
        req: LogisticsSystemSyncRequest,
        exc: Exception,
    ) -> None:
        """同步失败后的兜底日志。

        如果 `sys_task_log` / `sys_task_error_log` 本身尚未建表，这里也不能再把异常放大，
        否则会覆盖原始错误原因。
        """

        payload = json.dumps(req.model_dump(), ensure_ascii=False, default=str)
        try:
            repo.create_error_log(
                task_id=task_id,
                error_stage="SYNC",
                error_message=str(exc),
                raw_payload=payload,
            )
        except Exception:
            logger.exception("failed to write sys_task_error_log")

        try:
            repo.finish_task_log(
                task_id=task_id,
                status="FAILED",
                total_count=0,
                success_count=0,
                fail_count=1,
                message=str(exc),
            )
        except Exception:
            logger.exception("failed to update sys_task_log")

    def _fetch_all_ship_tasks(
        self,
        repo: LogisticsSyncRepository,
        req: LogisticsSystemSyncRequest,
    ) -> list[dict]:
        """分页拉取发货任务，避免一次性把源表全部拉进内存。"""
        all_rows: list[dict] = []
        offset = 0
        while True:
            rows = repo.fetch_ship_tasks(
                start_date=req.start_date,
                updated_since=req.updated_since,
                limit=req.batch_size,
                offset=offset,
            )
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < req.batch_size:
                break
            offset += req.batch_size
        return all_rows

    @staticmethod
    def _chunked(items: Sequence[str], size: int) -> Iterable[list[str]]:
        for index in range(0, len(items), size):
            yield list(items[index : index + size])

    @staticmethod
    def _normalize_company_row(row: dict) -> dict:
        return {
            "source_id": row.get("source_id"),
            "company_code": row.get("company_code"),
            "company_name": (row.get("company_name") or "").strip() or None,
            "base_code": row.get("company_code"),
            "del_flag": str(row.get("del_flag")) if row.get("del_flag") is not None else "0",
            "raw_json": json.dumps(row, ensure_ascii=False, default=str),
        }

    @staticmethod
    def _normalize_warehouse_row(row: dict) -> dict:
        return {
            "source_id": row.get("source_id"),
            "warehouse_code": row.get("warehouse_code"),
            "warehouse_name": (row.get("warehouse_name") or "").strip() or None,
            "base_code": row.get("warehouse_code"),
            "del_flag": str(row.get("del_flag")) if row.get("del_flag") is not None else "0",
            "raw_json": json.dumps(row, ensure_ascii=False, default=str),
        }

    @staticmethod
    def _normalize_ship_task_row(row: dict) -> dict:
        """标准化发货任务主表。

        目标字段名按 ODS 表列设计固定，后续 DWD 汇总直接复用这套字段。
        """
        return {
            "source_id": row.get("source_id"),
            "task_id": row.get("task_id"),
            "company_id": row.get("company_id"),
            "warehouse_id": row.get("warehouse_id"),
            "status": row.get("status"),
            "ship_type": row.get("ship_type"),
            "transport": row.get("transport"),
            "contract_number": row.get("contract_number"),
            "inquiry_number": row.get("inquiry_number"),
            "bidding_number": row.get("bidding_number"),
            "shipping_instruction": row.get("shipping_instruction"),
            "rd_number": row.get("rd_number"),
            "procurement_type": row.get("procurement_type"),
            "car_model": row.get("car_model"),
            "loading_trucks": row.get("loading_trucks"),
            "delivery_province": row.get("delivery_province"),
            "delivery_city": row.get("delivery_city"),
            "delivery_area": row.get("delivery_area"),
            "delivery_distance": LogisticsSystemSyncService._normalize_decimal(row.get("delivery_distance")),
            "reconciliation_status": row.get("reconciliation_status"),
            "extra_cost_audited": row.get("extra_cost_audited"),
            "base_code": row.get("base_code"),
            "del_flag": str(row.get("del_flag")) if row.get("del_flag") is not None else "0",
            "biz_date": row.get("biz_date"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "raw_json": json.dumps(row, ensure_ascii=False, default=str),
        }

    @staticmethod
    def _normalize_ship_product_row(row: dict) -> dict:
        return {
            "source_id": row.get("source_id"),
            "task_id": row.get("task_id"),
            "product_code": row.get("product_code"),
            "product_spec": row.get("product_spec"),
            "power": LogisticsSystemSyncService._normalize_decimal(row.get("power"), fallback_text=row.get("product_spec")),
            "quantity": LogisticsSystemSyncService._normalize_decimal(row.get("quantity")),
            "unit": row.get("unit"),
            "extra_cost": LogisticsSystemSyncService._normalize_decimal(row.get("extra_cost")),
            "base_code": row.get("base_code"),
            "del_flag": str(row.get("del_flag")) if row.get("del_flag") is not None else "0",
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "raw_json": json.dumps(row, ensure_ascii=False, default=str),
        }

    @staticmethod
    def _normalize_assign_task_row(row: dict) -> dict:
        return {
            "source_id": row.get("source_id"),
            "task_id": row.get("task_id"),
            "ship_task_id": row.get("ship_task_id"),
            "company_id": row.get("company_id"),
            "warehouse_id": row.get("warehouse_id"),
            "status": row.get("status"),
            "plate_number": row.get("plate_number"),
            "driver_name": row.get("driver_name"),
            "driver_phone": row.get("driver_phone"),
            "driver_id_number": row.get("driver_id_number"),
            "enter_time": row.get("enter_time"),
            "delivery_note_parse_status": row.get("delivery_note_parse_status"),
            "base_code": row.get("base_code"),
            "del_flag": str(row.get("del_flag")) if row.get("del_flag") is not None else "0",
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "raw_json": json.dumps(row, ensure_ascii=False, default=str),
        }

    @staticmethod
    def _normalize_assign_detail_row(row: dict) -> dict:
        return {
            "source_id": row.get("source_id"),
            "assign_task_id": row.get("assign_task_id"),
            "ship_task_id": row.get("ship_task_id"),
            "product_id": row.get("product_id"),
            "quantity": LogisticsSystemSyncService._normalize_decimal(row.get("quantity")),
            "supplier_price": LogisticsSystemSyncService._normalize_decimal(row.get("supplier_price")),
            "extra_cost": LogisticsSystemSyncService._normalize_decimal(row.get("extra_cost")),
            "cost_proof_url": row.get("cost_proof_url"),
            "base_code": row.get("base_code"),
            "del_flag": str(row.get("del_flag")) if row.get("del_flag") is not None else "0",
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "raw_json": json.dumps(row, ensure_ascii=False, default=str),
        }

    @staticmethod
    def _normalize_decimal(value: object, fallback_text: object | None = None) -> Decimal | None:
        """把源表里的数值字段统一清洗成 Decimal。

        源库里存在 `"/"` 这类占位符或空串，直接写入 DECIMAL 列会触发 1366。
        这里优先做严格解析，解析失败则返回 `None` 让数据库落空值。
        """

        candidate = value
        if candidate is None:
            candidate = fallback_text
        if candidate is None:
            return None
        if isinstance(candidate, Decimal):
            return candidate
        if isinstance(candidate, (int, float)) and not isinstance(candidate, bool):
            return Decimal(str(candidate))

        text = str(candidate).strip().replace(",", "")
        if not text or text in {"/", "-", "--", "N/A", "NULL", "null"}:
            if fallback_text is None or fallback_text == value:
                return None
            fallback = str(fallback_text).strip().replace(",", "")
            match = re.search(r"(\d+(?:\.\d+)?)\s*[wW]$", fallback)
            if not match:
                return None
            text = match.group(1)
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return None
        try:
            return Decimal(match.group(0))
        except InvalidOperation:
            return None

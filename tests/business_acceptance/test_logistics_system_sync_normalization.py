"""物流系统同步字段归一化回归测试。"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.domains.logistics.repositories.sync_repository import LogisticsSyncRepository
from backend.app.domains.logistics.services.sync_service import LogisticsSystemSyncService


def test_ship_task_blank_loading_trucks_normalized_to_none() -> None:
    """验证源库空字符串装车数不会写入 DECIMAL 字段导致 1366 错误。"""

    row = {
        "source_id": 12364,
        "task_id": 12364,
        "loading_trucks": "",
        "delivery_distance": "404.00",
    }

    normalized = LogisticsSystemSyncService._normalize_ship_task_row(row)

    assert normalized["loading_trucks"] is None
    assert normalized["delivery_distance"] == Decimal("404.00")


def test_ship_task_numeric_loading_trucks_keeps_decimal_value() -> None:
    """验证合法装车数字符串仍按数值写入中间层。"""

    row = {
        "source_id": 11159,
        "task_id": 11159,
        "loading_trucks": "11",
        "delivery_distance": None,
    }

    normalized = LogisticsSystemSyncService._normalize_ship_task_row(row)

    assert normalized["loading_trucks"] == Decimal("11")


def test_fetch_ship_tasks_uses_pickup_date_as_formal_scope() -> None:
    """验证正式物流同步按提货日期纳入 2026 数据，而不是按创建日期误排除跨年任务。"""

    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as source_db:
        source_db.execute(
            text(
                """
                CREATE TABLE logistic_ship_task (
                    task_id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    project_name TEXT,
                    pickup_date TEXT,
                    status TEXT,
                    ship_type TEXT,
                    expand_dept TEXT,
                    entrusted_person TEXT,
                    transport TEXT,
                    contract_number TEXT,
                    inquiry_number TEXT,
                    bidding_number TEXT,
                    shipping_instruction TEXT,
                    rd_number TEXT,
                    procurement_type TEXT,
                    car_model TEXT,
                    loading_trucks TEXT,
                    delivery_province TEXT,
                    delivery_city TEXT,
                    delivery_area TEXT,
                    delivery_distance TEXT,
                    reconciliation_status TEXT,
                    extra_cost_audited TEXT,
                    base_code TEXT,
                    del_flag TEXT,
                    create_time TEXT,
                    update_time TEXT
                )
                """
            )
        )
        source_db.execute(
            text(
                """
                INSERT INTO logistic_ship_task (
                    task_id, pickup_date, transport, del_flag, create_time, update_time
                ) VALUES
                    (11147, '2026-01-03', '铁路', '0', '2025-12-31 15:42:56', '2026-01-26 08:41:30'),
                    (11148, '2026-01-04', '铁路', '0', '2026-01-02 10:00:00', '2026-01-03 10:00:00'),
                    (11151, NULL, '铁路', '0', '2026-01-05 10:00:00', '2026-01-05 12:00:00'),
                    (90001, '2025-12-31', '铁路', '0', '2025-12-31 10:00:00', '2026-01-02 10:00:00')
                """
            )
        )
        repo = LogisticsSyncRepository(db=source_db, source_db=source_db)

        rows = repo.fetch_ship_tasks(start_date="2026-01-01", updated_since=None, limit=100, offset=0)

    task_ids = [row["task_id"] for row in rows]
    assert task_ids == [11147, 11148, 11151]
    early_cross_year_row = next(row for row in rows if row["task_id"] == 11147)
    assert str(early_cross_year_row["biz_date"]).startswith("2026-01-03")
    missing_pickup_date_row = next(row for row in rows if row["task_id"] == 11151)
    assert str(missing_pickup_date_row["biz_date"]).startswith("2026-01-05")

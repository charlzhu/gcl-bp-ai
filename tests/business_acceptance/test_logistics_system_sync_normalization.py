"""物流系统同步字段归一化回归测试。"""

from __future__ import annotations

from decimal import Decimal

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

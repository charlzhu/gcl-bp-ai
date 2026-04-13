from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class LogisticsSystemSyncRequest(BaseModel):
    """物流系统同步请求。

    一期仅覆盖主链路六张源表：
    1. `logistic_ship_task`
    2. `logistic_ship_product`
    3. `logistic_assign_task`
    4. `logistic_assign_detail`
    5. `logistic_logistic_company`
    6. `logistic_warehouse`

    风险说明：
    1. 二期对象如 `allocate_task`、`delivery_note`、图片、打卡数据明确不在本版本范围内；
    2. `start_date` 和 `updated_since` 会直接进入源库过滤条件，格式错误会导致 SQL 查询失败，
       因此在 schema 层先做严格校验。
    """

    start_date: str = Field(default="2026-01-01", description="正式数据起始日期，格式 YYYY-MM-DD")
    updated_since: str | None = Field(
        default=None,
        description="增量同步起点，格式 YYYY-MM-DD HH:MM:SS",
    )
    batch_size: int = Field(default=1000, ge=100, le=10000)
    dry_run: bool = Field(default=False, description="仅预演，不写 ODS/DWD，也不改任务统计结果")
    sync_companies: bool = True
    sync_warehouses: bool = True
    sync_ship_tasks: bool = True
    sync_ship_products: bool = True
    sync_assign_tasks: bool = True
    sync_assign_details: bool = True

    @field_validator("start_date")
    @classmethod
    def validate_start_date(cls, value: str) -> str:
        datetime.strptime(value, "%Y-%m-%d")
        return value

    @field_validator("updated_since")
    @classmethod
    def validate_updated_since(cls, value: str | None) -> str | None:
        if value is None:
            return value
        datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        return value


class LogisticsSystemSyncResult(BaseModel):
    """物流系统同步结果。"""

    task_id: str
    sync_batch_no: str
    dry_run: bool
    start_date: str
    updated_since: str | None = None
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
    message: str = ""

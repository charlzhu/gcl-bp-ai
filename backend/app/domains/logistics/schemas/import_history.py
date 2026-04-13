from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator, model_validator

_YEAR_MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class LogisticsHistoryImportRequest(BaseModel):
    """历史 Excel 导入请求。

    支持两种输入方式：
    1. `file_path`：服务端本地可访问文件；
    2. `upload_id`：先走上传接口保存文件，再用上传任务 ID 触发导入。
    """

    file_path: str | None = Field(default=None, description="服务器本地 Excel 文件绝对路径")
    upload_id: str | None = Field(default=None, description="上传接口返回的 upload_id")
    source_year: int = Field(..., ge=2023, le=2025, description="历史数据年份")
    source_factory: str | None = Field(default=None, description="来源工厂/区域，例如 合肥/阜宁")
    sheet_names: list[str] | None = Field(default=None, description="指定导入的 sheet 列表，不传则导入全部")
    import_batch_no: str | None = Field(default=None, description="导入批次号，不传则自动生成")
    refresh_serving: bool = Field(default=True, description="导入完成后是否自动刷新服务层")
    truncate_current_batch_before_import: bool = Field(default=False, description="同批次重跑时，是否先删除当前批次数据")

    @model_validator(mode="after")
    def validate_input_source(self) -> "LogisticsHistoryImportRequest":
        if not self.file_path and not self.upload_id:
            raise ValueError("file_path 和 upload_id 至少提供一个")
        return self

    @field_validator("sheet_names")
    @classmethod
    def normalize_sheet_names(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        normalized = [item.strip() for item in value if item and item.strip()]
        return normalized or None


class LogisticsHistoryImportResult(BaseModel):
    task_id: str
    import_batch_no: str
    source_year: int
    file_path: str
    total_sheets: int = 0
    imported_sheets: int = 0
    raw_row_count: int = 0
    dwd_row_count: int = 0
    skipped_row_count: int = 0
    message: str = ""


class LogisticsServingRefreshRequest(BaseModel):
    refresh_hist: bool = True
    refresh_sys: bool = True
    rebuild_dm: bool = True
    target_year_month_list: list[str] | None = None

    @field_validator("target_year_month_list")
    @classmethod
    def validate_target_year_month_list(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        normalized: list[str] = []
        for item in value:
            month = item.strip()
            if not _YEAR_MONTH_PATTERN.match(month):
                raise ValueError("target_year_month_list 元素格式必须为 YYYY-MM")
            normalized.append(month)
        return normalized


class LogisticsServingRefreshResult(BaseModel):
    task_id: str
    hist_detail_rows: int = 0
    sys_detail_rows: int = 0
    monthly_rows: int = 0
    dm_rank_rows: int = 0
    message: str = ""

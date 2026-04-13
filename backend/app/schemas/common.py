from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from backend.app.utils.time_utils import month_index

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
SortOrder = Literal["asc", "desc"]


class MonthRange(BaseModel):
    start_month: str = Field(..., pattern=MONTH_PATTERN, description="开始月份，格式 YYYY-MM")
    end_month: str = Field(..., pattern=MONTH_PATTERN, description="结束月份，格式 YYYY-MM")

    @model_validator(mode="after")
    def validate_month_range(self) -> "MonthRange":
        if month_index(self.start_month) > month_index(self.end_month):
            raise ValueError("start_month 不能晚于 end_month")
        return self


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any | None = None
    trace_id: str | None = None

    @classmethod
    def success(
        cls,
        data: Any = None,
        message: str = "success",
        *,
        trace_id: str | None = None,
    ) -> "ApiResponse":
        return cls(code=0, message=message, data=data, trace_id=trace_id)

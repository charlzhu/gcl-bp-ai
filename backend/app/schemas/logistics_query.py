from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.app.schemas.common import MonthRange, PaginationParams, PageMeta

MetricField = Literal["shipment_watt", "shipment_trip_count", "total_fee", "extra_fee"]
GroupField = Literal["year", "month", "company", "transport_mode", "business_type", "source_type"]
SourceType = Literal["history", "system_formal", "mixed"]
CompareMode = Literal["custom", "yoy", "mom"]
DetailSortField = Literal[
    "shipment_date",
    "shipment_watt",
    "shipment_trip_count",
    "total_fee",
    "extra_fee",
]


class LogisticsFilters(BaseModel):
    companies: list[str] = Field(default_factory=list)
    transport_modes: list[str] = Field(default_factory=list)
    business_types: list[str] = Field(default_factory=list)
    source_type: SourceType = "mixed"
    keyword: str | None = Field(default=None, max_length=100)


class MetricsQueryRequest(BaseModel):
    period: MonthRange
    metrics: list[MetricField] = Field(default_factory=lambda: ["shipment_watt"])
    group_by: list[GroupField] = Field(default_factory=lambda: ["month"])
    filters: LogisticsFilters = Field(default_factory=LogisticsFilters)

    @field_validator("metrics")
    @classmethod
    def normalize_metrics(cls, value: list[MetricField]) -> list[MetricField]:
        return list(dict.fromkeys(value))

    @field_validator("group_by")
    @classmethod
    def normalize_group_fields(cls, value: list[GroupField]) -> list[GroupField]:
        return list(dict.fromkeys(value))


class MetricsQueryResult(BaseModel):
    period: MonthRange
    group_by: list[str]
    filters: LogisticsFilters
    summary: dict[str, float]
    records: list[dict[str, Any]]
    record_count: int


class CompareQueryRequest(BaseModel):
    metric: MetricField = "shipment_watt"
    base_period: MonthRange
    compare_period: MonthRange | None = None
    compare_mode: CompareMode = "custom"
    group_by: list[GroupField] = Field(default_factory=list)
    filters: LogisticsFilters = Field(default_factory=LogisticsFilters)

    @field_validator("group_by")
    @classmethod
    def normalize_group_fields(cls, value: list[GroupField]) -> list[GroupField]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_compare_args(self) -> "CompareQueryRequest":
        if self.compare_mode == "custom" and self.compare_period is None:
            raise ValueError("compare_mode 为 custom 时必须传 compare_period")
        return self


class CompareQueryResult(BaseModel):
    metric: str
    compare_mode: str
    base_period: MonthRange
    compare_period: MonthRange
    filters: LogisticsFilters
    summary: dict[str, float | None | str]
    records: list[dict[str, Any]]


class DetailQueryRequest(PaginationParams):
    period: MonthRange
    filters: LogisticsFilters = Field(default_factory=LogisticsFilters)
    sort_by: DetailSortField = "shipment_date"
    sort_order: Literal["asc", "desc"] = "desc"


class DetailQueryResult(BaseModel):
    period: MonthRange
    filters: LogisticsFilters
    items: list[dict[str, Any]]
    page: PageMeta


class ExportQueryRequest(MetricsQueryRequest):
    file_name: str | None = Field(default=None, max_length=120)


class ExportPreviewResult(BaseModel):
    file_name: str
    headers: list[str]
    rows: list[list[Any]]
    total_rows: int

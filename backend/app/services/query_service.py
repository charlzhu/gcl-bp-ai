from typing import Any, Iterable

from backend.app.repositories.logistics_query_repo import InMemoryLogisticsQueryRepository, LogisticsRecord
from backend.app.schemas.common import PageMeta
from backend.app.schemas.logistics_query import (
    DetailQueryRequest,
    DetailQueryResult,
    ExportPreviewResult,
    ExportQueryRequest,
    LogisticsFilters,
    MetricsQueryRequest,
    MetricsQueryResult,
)
from backend.app.utils.time_utils import month_index


class QueryService:
    def __init__(self, repository: InMemoryLogisticsQueryRepository) -> None:
        self.repository = repository

    def list_records(
        self,
        *,
        period,
        filters: LogisticsFilters,
    ) -> list[LogisticsRecord]:
        return self.repository.list_records(
            start_month=period.start_month,
            end_month=period.end_month,
            companies=filters.companies,
            transport_modes=filters.transport_modes,
            business_types=filters.business_types,
            source_type=filters.source_type,
            keyword=filters.keyword,
        )

    def query_metrics(self, request: MetricsQueryRequest) -> MetricsQueryResult:
        records = self.list_records(period=request.period, filters=request.filters)
        aggregated_records = self.aggregate_records(
            records=records,
            metrics=request.metrics,
            group_by=request.group_by,
        )
        summary = self.summarize_records(records=records, metrics=request.metrics)
        return MetricsQueryResult(
            period=request.period,
            group_by=request.group_by,
            filters=request.filters,
            summary=summary,
            records=aggregated_records,
            record_count=len(records),
        )

    def query_detail(self, request: DetailQueryRequest) -> DetailQueryResult:
        records = self.list_records(period=request.period, filters=request.filters)
        sorted_records = sorted(
            records,
            key=lambda item: self._detail_sort_value(item, request.sort_by),
            reverse=request.sort_order == "desc",
        )
        start = (request.page - 1) * request.page_size
        end = start + request.page_size
        page_items = [record.to_dict() for record in sorted_records[start:end]]
        return DetailQueryResult(
            period=request.period,
            filters=request.filters,
            items=page_items,
            page=PageMeta(page=request.page, page_size=request.page_size, total=len(records)),
        )

    def export_metrics(self, request: ExportQueryRequest) -> ExportPreviewResult:
        metrics_result = self.query_metrics(
            MetricsQueryRequest(
                period=request.period,
                metrics=request.metrics,
                group_by=request.group_by,
                filters=request.filters,
            )
        )
        headers = [*request.group_by, *request.metrics, "record_count"]
        rows = [[record.get(column) for column in headers] for record in metrics_result.records]
        file_name = request.file_name or (
            f"logistics_metrics_{request.period.start_month}_{request.period.end_month}.csv"
        )
        return ExportPreviewResult(
            file_name=file_name,
            headers=headers,
            rows=rows,
            total_rows=len(rows),
        )

    def aggregate_records(
        self,
        *,
        records: Iterable[LogisticsRecord],
        metrics: list[str],
        group_by: list[str],
    ) -> list[dict[str, Any]]:
        buckets: dict[tuple[Any, ...], dict[str, Any]] = {}
        for record in records:
            dimensions = {field: self._dimension_value(record, field) for field in group_by}
            key = tuple(dimensions.get(field) for field in group_by)
            bucket = buckets.setdefault(
                key,
                {**dimensions, **{metric: 0.0 for metric in metrics}, "record_count": 0},
            )
            for metric in metrics:
                bucket[metric] = round(bucket[metric] + self._metric_value(record, metric), 2)
            bucket["record_count"] += 1

        aggregated = list(buckets.values())
        aggregated.sort(key=lambda item: self._group_sort_key(item, group_by))
        return aggregated

    def summarize_records(
        self,
        *,
        records: Iterable[LogisticsRecord],
        metrics: list[str],
    ) -> dict[str, float]:
        summary = {metric: 0.0 for metric in metrics}
        for record in records:
            for metric in metrics:
                summary[metric] = round(summary[metric] + self._metric_value(record, metric), 2)
        return summary

    @staticmethod
    def _metric_value(record: LogisticsRecord, metric: str) -> float:
        return float(getattr(record, metric))

    @staticmethod
    def _dimension_value(record: LogisticsRecord, field: str) -> Any:
        if field == "year":
            return record.year
        if field == "month":
            return record.month_key
        return getattr(record, field)

    @staticmethod
    def _group_sort_key(record: dict[str, Any], group_by: list[str]) -> tuple[Any, ...]:
        values: list[Any] = []
        for field in group_by:
            value = record.get(field)
            if field == "month" and isinstance(value, str):
                values.append(month_index(value))
            else:
                values.append(value)
        return tuple(values)

    @staticmethod
    def _detail_sort_value(record: LogisticsRecord, field: str) -> Any:
        if field == "shipment_date":
            return record.shipment_date
        return getattr(record, field)

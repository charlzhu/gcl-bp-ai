from typing import Any

from backend.app.core.exceptions import AppException
from backend.app.schemas.common import MonthRange
from backend.app.schemas.logistics_query import CompareQueryRequest, CompareQueryResult
from backend.app.services.query_service import QueryService
from backend.app.utils.time_utils import month_index, months_between, shift_month


class CompareService:
    def __init__(self, query_service: QueryService) -> None:
        self.query_service = query_service

    def compare(self, request: CompareQueryRequest) -> CompareQueryResult:
        compare_period = self._resolve_compare_period(request)
        base_records = self.query_service.list_records(
            period=request.base_period,
            filters=request.filters,
        )
        compare_records = self.query_service.list_records(
            period=compare_period,
            filters=request.filters,
        )

        if request.group_by == ["month"]:
            rows = self._build_month_aligned_rows(
                base_records=base_records,
                compare_records=compare_records,
                metric=request.metric,
            )
            base_total = round(sum(row["base_value"] for row in rows), 2)
            compare_total = round(sum(row["compare_value"] for row in rows), 2)
        else:
            base_map = self._aggregate_metric(base_records, request.metric, request.group_by)
            compare_map = self._aggregate_metric(compare_records, request.metric, request.group_by)
            merged_keys = sorted(
                set(base_map) | set(compare_map),
                key=lambda item: self._sort_key(item, request.group_by),
            )

            rows = []
            for key in merged_keys:
                dimensions = {field: key[index] for index, field in enumerate(request.group_by)}
                base_value = round(base_map.get(key, 0.0), 2)
                compare_value = round(compare_map.get(key, 0.0), 2)
                delta = round(base_value - compare_value, 2)
                delta_ratio = round(delta / compare_value, 4) if compare_value else None
                rows.append(
                    {
                        **dimensions,
                        "base_value": base_value,
                        "compare_value": compare_value,
                        "delta": delta,
                        "delta_ratio": delta_ratio,
                    }
                )

            base_total = round(sum(base_map.values()), 2)
            compare_total = round(sum(compare_map.values()), 2)

        total_delta = round(base_total - compare_total, 2)
        total_ratio = round(total_delta / compare_total, 4) if compare_total else None
        trend = "flat"
        if total_delta > 0:
            trend = "up"
        elif total_delta < 0:
            trend = "down"

        return CompareQueryResult(
            metric=request.metric,
            compare_mode=request.compare_mode,
            base_period=request.base_period,
            compare_period=compare_period,
            filters=request.filters,
            summary={
                "base_total": base_total,
                "compare_total": compare_total,
                "delta": total_delta,
                "delta_ratio": total_ratio,
                "trend": trend,
            },
            records=rows,
        )

    def _build_month_aligned_rows(
        self,
        *,
        base_records,
        compare_records,
        metric: str,
    ) -> list[dict[str, Any]]:
        base_rows = self.query_service.aggregate_records(
            records=base_records,
            metrics=[metric],
            group_by=["month"],
        )
        compare_rows = self.query_service.aggregate_records(
            records=compare_records,
            metrics=[metric],
            group_by=["month"],
        )
        max_length = max(len(base_rows), len(compare_rows))
        rows: list[dict[str, Any]] = []
        for index in range(max_length):
            base_row = base_rows[index] if index < len(base_rows) else {}
            compare_row = compare_rows[index] if index < len(compare_rows) else {}
            base_value = round(float(base_row.get(metric, 0.0)), 2)
            compare_value = round(float(compare_row.get(metric, 0.0)), 2)
            delta = round(base_value - compare_value, 2)
            delta_ratio = round(delta / compare_value, 4) if compare_value else None
            rows.append(
                {
                    "base_month": base_row.get("month"),
                    "compare_month": compare_row.get("month"),
                    "base_value": base_value,
                    "compare_value": compare_value,
                    "delta": delta,
                    "delta_ratio": delta_ratio,
                }
            )
        return rows

    @staticmethod
    def _aggregate_metric(records, metric: str, group_by: list[str]) -> dict[tuple[Any, ...], float]:
        result: dict[tuple[Any, ...], float] = {}
        for record in records:
            key = tuple(QueryService._dimension_value(record, field) for field in group_by)
            result[key] = round(result.get(key, 0.0) + QueryService._metric_value(record, metric), 2)
        if not group_by:
            result.setdefault(tuple(), 0.0)
        return result

    @staticmethod
    def _resolve_compare_period(request: CompareQueryRequest) -> MonthRange:
        if request.compare_period is not None:
            return request.compare_period
        if request.compare_mode == "yoy":
            return MonthRange(
                start_month=shift_month(request.base_period.start_month, -12),
                end_month=shift_month(request.base_period.end_month, -12),
            )
        if request.compare_mode == "mom":
            delta = months_between(
                request.base_period.start_month,
                request.base_period.end_month,
            )
            return MonthRange(
                start_month=shift_month(request.base_period.start_month, -delta),
                end_month=shift_month(request.base_period.end_month, -delta),
            )
        raise AppException("缺少对比周期", code=4001, status_code=400)

    @staticmethod
    def _sort_key(key: tuple[Any, ...], group_by: list[str]) -> tuple[Any, ...]:
        values: list[Any] = []
        for index, field in enumerate(group_by):
            value = key[index]
            if field == "month" and isinstance(value, str):
                values.append(month_index(value))
            else:
                values.append(value)
        return tuple(values)

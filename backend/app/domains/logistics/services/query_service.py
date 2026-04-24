from __future__ import annotations

from copy import deepcopy
import json
import logging
import re
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.core.exceptions import AppException
from backend.app.domains.logistics.repositories.query_repository import LogisticsQueryRepository
from backend.app.domains.logistics.schemas.query import (
    LogisticsAggregateQuery,
    LogisticsCompareQuery,
    LogisticsDetailQuery,
)
from backend.app.domains.logistics.services.no_result_analyzer import LogisticsNoResultAnalyzer
from backend.app.domains.logistics.services.query_response_standardizer import LogisticsQueryResponseStandardizer
from backend.app.domains.logistics.services.result_count_helper import LogisticsResultCountHelper
from backend.app.domains.logistics.services.result_explainer import LogisticsResultExplainer
from backend.app.repositories.logistics_query_repo import LogisticsRecord
from backend.app.schemas.common import MonthRange
from backend.app.schemas.logistics_query import LogisticsFilters
from backend.app.services.compare_service import CompareService
from backend.app.services.query_service import QueryService as CoreQueryService
from backend.app.utils.time_utils import format_month, month_index

logger = logging.getLogger(__name__)

# 数据库模式下的指标字段映射，必须与一期查询表列名保持一致。
SQL_METRIC_FIELD_MAP = {
    "shipment_watt": "shipment_watt",
    "shipment_count": "shipment_count",
    "shipment_trip_count": "shipment_trip_count",
    "total_fee": "total_fee",
    "extra_fee": "extra_fee",
}
# fallback 模式运行在 demo 明细数据上，因此这里要把“查询指标”映射到 demo 记录结构。
FALLBACK_METRIC_MAPPING = {
    "shipment_watt": "shipment_watt",
    "shipment_count": "__shipment_count__",
    "shipment_trip_count": "shipment_trip_count",
    "total_fee": "total_fee",
    "extra_fee": "extra_fee",
}
# 新包沿用了 legacy 字段名，这里做一次“前端字段 -> demo 记录字段”的映射。
FALLBACK_GROUP_BY_MAPPING = {
    "biz_year": ("year", "biz_year"),
    "biz_month": ("month", "biz_month"),
    # 注意：demo 数据里的 company 字段实际存的是“基地”，并不是真正的承运商/物流公司。
    # 因此这里不再把 logistics_company_name 映射到 company，避免 fallback 结果误导业务。
    "warehouse_name": ("warehouse", "warehouse_name"),
    "transport_mode": ("transport_mode", "transport_mode"),
    "source_type": ("source_type", "source_type"),
}
# 这些字段在 fallback 模式下虽然“看起来能映射”，但语义并不可靠，
# 因此应显式拒绝返回，避免把“基地”错误当成“承运商/物流公司”。
FALLBACK_UNSAFE_GROUP_FIELDS = {"logistics_company_name"}
SOURCE_SCOPE_MAPPING = {
    "hist": "history",
    "sys": "system_formal",
    "all": "mixed",
}


class LogisticsQueryService:
    """物流查询服务。

    设计目标：
    1. 优先走真实数据库查询表，满足一期联调需求；
    2. 数据库不可用时自动回退到 demo repository，避免本地开发完全阻塞；
    3. 对 aggregate/detail/compare/nl2query 统一收口日志写入和异常处理。
    """

    def __init__(
        self,
        *,
        db: Session | None = None,
        fallback_query_service: CoreQueryService | None = None,
        fallback_compare_service: CompareService | None = None,
        repository: LogisticsQueryRepository | None = None,
        result_explainer: LogisticsResultExplainer | None = None,
        no_result_analyzer: LogisticsNoResultAnalyzer | None = None,
        query_response_standardizer: LogisticsQueryResponseStandardizer | None = None,
    ) -> None:
        self.db = db
        self.fallback_query_service = fallback_query_service
        self.fallback_compare_service = fallback_compare_service
        self.repository = repository or LogisticsQueryRepository()
        self.result_explainer = result_explainer or LogisticsResultExplainer()
        self.no_result_analyzer = no_result_analyzer or LogisticsNoResultAnalyzer()
        self.query_response_standardizer = (
            query_response_standardizer or LogisticsQueryResponseStandardizer()
        )

    def aggregate(
        self,
        payload: LogisticsAggregateQuery,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """统计查询主入口。

        优先走数据库；如果连接失败、表不存在或 SQL 执行异常，则自动回退。
        """
        metric_field = self._sql_metric_field(payload.metric_type)
        if self.db is not None:
            try:
                result = self.repository.aggregate(
                    db=self.db,
                    filters=payload.model_dump(),
                    metric_field=metric_field,
                    group_by=payload.group_by,
                    order_by=payload.order_by or metric_field,
                    order_direction=payload.order_direction,
                    limit=payload.limit,
                )
                result.update(
                    {
                        "query_type": "aggregate",
                        "metric_type": payload.metric_type,
                        "source_scope": payload.source_scope,
                        "filters": payload.model_dump(),
                        "execution_mode": "database",
                    }
                )
                aggregate_question = self._build_aggregate_question(payload)
                aggregate_parsed = self._build_aggregate_parsed_snapshot(payload)
                self._attach_aggregate_contract(payload=payload, query_result=result)
                aggregate_response_meta = deepcopy(result.get("response_meta") or {})
                self._safe_write_log(
                    trace_id=trace_id,
                    query_type="AGGREGATE",
                    payload=payload.model_dump(),
                    metric_type=payload.metric_type,
                    result_count=LogisticsResultCountHelper.extract_count(result),
                    route_type=payload.source_scope,
                    question_text=aggregate_question,
                    # aggregate 直连日志也补最小快照，后续历史详情优先消费原生字段。
                    payload_snapshot=self._build_direct_query_log_payload(
                        question=aggregate_question,
                        request_payload=payload.model_dump(),
                        parsed_snapshot=aggregate_parsed,
                        query_result=result,
                        response_meta=aggregate_response_meta,
                    ),
                )
                return result
            except SQLAlchemyError as exc:
                # 这里不直接抛错，是为了让无库环境仍然能继续前后端联调。
                logger.warning("aggregate query fallback to demo repository: %s", exc)

        return self._aggregate_fallback(payload, trace_id=trace_id)

    def detail(
        self,
        payload: LogisticsDetailQuery,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """明细查询主入口。"""
        if self.db is not None:
            try:
                result = self.repository.detail(
                    db=self.db,
                    filters=payload.model_dump(),
                    order_by=payload.order_by,
                    order_direction=payload.order_direction,
                    page=payload.page,
                    page_size=payload.page_size,
                )
                result.update(
                    {
                        "query_type": "detail",
                        "metric_type": payload.metric_type,
                        "source_scope": payload.source_scope,
                        "filters": payload.model_dump(),
                        "execution_mode": "database",
                    }
                )
                detail_question = self._build_detail_question(payload)
                detail_parsed = self._build_detail_parsed_snapshot(payload)
                detail_response_meta = self._attach_direct_query_contract(
                    question=detail_question,
                    parsed_snapshot=detail_parsed,
                    query_result=result,
                )
                self._safe_write_log(
                    trace_id=trace_id,
                    query_type="DETAIL",
                    payload=payload.model_dump(),
                    metric_type=payload.metric_type,
                    result_count=LogisticsResultCountHelper.extract_count(result),
                    route_type=payload.source_scope,
                    question_text=detail_question,
                    payload_snapshot=self._build_direct_query_log_payload(
                        question=detail_question,
                        request_payload=payload.model_dump(),
                        parsed_snapshot=detail_parsed,
                        query_result=result,
                        response_meta=detail_response_meta,
                    ),
                )
                return result
            except SQLAlchemyError as exc:
                logger.warning("detail query fallback to demo repository: %s", exc)

        return self._detail_fallback(payload, trace_id=trace_id)

    def probe_detail_business_no(
        self,
        *,
        field_name: str,
        field_value: Any,
        source_scope: str = "all",
    ) -> bool:
        """检查明细服务层中某个业务编号是否存在。

        该方法主要服务于 V10 的“无结果原因增强分析”，
        不直接参与主查询链路，也不会抛出异常影响正常结果返回。
        """
        if self.db is None:
            return False
        try:
            return bool(
                self.repository.exists_detail_business_no(
                    db=self.db,
                    field_name=field_name,
                    field_value=field_value,
                    source_scope=source_scope,
                )
            )
        except Exception as exc:
            logger.warning("probe detail business no failed: %s", exc)
            return False


    def compare(
        self,
        payload: LogisticsCompareQuery,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """对比查询主入口。"""
        metric_field = self._sql_metric_field(payload.metric_type)
        if self.db is not None:
            try:
                base_filters = payload.model_dump(exclude={"left", "right", "compare_dim"})
                result = self.repository.compare(
                    db=self.db,
                    base_filters=base_filters,
                    metric_field=metric_field,
                    compare_dim=payload.compare_dim,
                    left=payload.left.model_dump(),
                    right=payload.right.model_dump(),
                )
                result.update(
                    {
                        "query_type": "compare",
                        "metric_type": payload.metric_type,
                        "source_scope": payload.source_scope,
                        "compare_dim": payload.compare_dim,
                        "filters": payload.model_dump(),
                        "execution_mode": "database",
                    }
                )
                compare_question = self._build_compare_question(payload)
                compare_parsed = self._build_compare_parsed_snapshot(payload)
                compare_response_meta = self._attach_direct_query_contract(
                    question=compare_question,
                    parsed_snapshot=compare_parsed,
                    query_result=result,
                )
                # compare total-mode 返回的是左右总量三元组，`items` 合法情况下也可能为空。
                # 日志中的 result_count 不能再直接按 len(items) 计算，否则历史列表和详情会被误判成空结果。
                compare_result_count = LogisticsResultCountHelper.extract_count(result)
                self._safe_write_log(
                    trace_id=trace_id,
                    query_type="COMPARE",
                    payload=payload.model_dump(),
                    metric_type=payload.metric_type,
                    result_count=compare_result_count,
                    route_type=payload.source_scope,
                    question_text=compare_question,
                    payload_snapshot=self._build_direct_query_log_payload(
                        question=compare_question,
                        request_payload=payload.model_dump(),
                        parsed_snapshot=compare_parsed,
                        query_result=result,
                        response_meta=compare_response_meta,
                    ),
                )
                return result
            except SQLAlchemyError as exc:
                logger.warning("compare query fallback to demo repository: %s", exc)

        return self._compare_fallback(payload, trace_id=trace_id)

    def _aggregate_fallback(
        self,
        payload: LogisticsAggregateQuery,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """统计查询的回退实现。

        这里复用当前项目已有的 in-memory 明细数据，把 legacy 查询协议转换成 demo 可执行格式。
        """
        if self.fallback_query_service is None:
            raise AppException("查询服务未初始化", code=5004, status_code=500)

        period = self._resolve_period(payload)
        records = self.fallback_query_service.list_records(period=period, filters=self._resolve_filters(payload))

        # 安全兜底：fallback 数据源中的 company 实际是“基地”，不是“承运商/物流公司”。
        # 如果当前问题要求按 logistics_company_name 分组，继续返回结果会误导业务，
        # 因此这里显式拒绝，交由上层走“空结果解释 / 兼容提示”。
        unsafe_group_fields = [
            field for field in getattr(payload, "group_by", []) if field in FALLBACK_UNSAFE_GROUP_FIELDS
        ]
        if unsafe_group_fields:
            response = {
                "query_type": "aggregate",
                "metric_type": payload.metric_type,
                "source_scope": payload.source_scope,
                "filters": payload.model_dump(),
                "summary": {},
                "items": [],
                "record_count": len(records),
                "execution_mode": "fallback",
                "compatibility_notice": self._compatibility_notice(payload),
                "fallback_blocked_reason": (
                    "fallback 数据源缺少真实承运商维度，已阻止使用基地字段冒充物流公司结果。"
                ),
            }
            self._attach_aggregate_contract(payload=payload, query_result=response)
            aggregate_question = self._build_aggregate_question(payload)
            aggregate_parsed = self._build_aggregate_parsed_snapshot(payload)
            aggregate_response_meta = deepcopy(response.get("response_meta") or {})
            self._safe_write_log(
                trace_id=trace_id,
                query_type="AGGREGATE",
                payload=payload.model_dump(),
                metric_type=payload.metric_type,
                result_count=0,
                route_type=f"{payload.source_scope}:fallback_blocked",
                question_text=aggregate_question,
                # 即使 fallback 被阻断，也要把最小快照写入日志，避免历史详情再补造。
                payload_snapshot=self._build_direct_query_log_payload(
                    question=aggregate_question,
                    request_payload=payload.model_dump(),
                    parsed_snapshot=aggregate_parsed,
                    query_result=response,
                    response_meta=aggregate_response_meta,
                ),
            )
            return response

        # 只保留 fallback 能识别的 group_by 字段，其他字段在 compatibility_notice 中提示。
        group_by_pairs = [
            (field, mapped)
            for field in payload.group_by
            if (mapping := FALLBACK_GROUP_BY_MAPPING.get(field)) is not None
            for mapped in [mapping]
        ]
        if not group_by_pairs:
            group_by_pairs = [("biz_month", ("month", "biz_month"))]

        items = self._fallback_group_records(records, payload.metric_type, group_by_pairs)
        summary = self._fallback_summary(records, payload.metric_type)
        response = {
            "query_type": "aggregate",
            "metric_type": payload.metric_type,
            "source_scope": payload.source_scope,
            "filters": payload.model_dump(),
            "summary": summary,
            "items": self._sort_aggregate_items(items, payload.order_by or payload.metric_type, payload.order_direction),
            "record_count": len(records),
            "execution_mode": "fallback",
            "compatibility_notice": self._compatibility_notice(payload),
        }
        self._attach_aggregate_contract(payload=payload, query_result=response)
        aggregate_question = self._build_aggregate_question(payload)
        aggregate_parsed = self._build_aggregate_parsed_snapshot(payload)
        aggregate_response_meta = deepcopy(response.get("response_meta") or {})
        self._safe_write_log(
            trace_id=trace_id,
            query_type="AGGREGATE",
            payload=payload.model_dump(),
            metric_type=payload.metric_type,
            result_count=LogisticsResultCountHelper.extract_count(response),
            route_type=f"{payload.source_scope}:fallback",
            question_text=aggregate_question,
            # fallback aggregate 也复用统一快照结构，保证 direct query 日志口径一致。
            payload_snapshot=self._build_direct_query_log_payload(
                question=aggregate_question,
                request_payload=payload.model_dump(),
                parsed_snapshot=aggregate_parsed,
                query_result=response,
                response_meta=aggregate_response_meta,
            ),
        )
        return response

    def _detail_fallback(
        self,
        payload: LogisticsDetailQuery,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """明细查询的回退实现。"""
        if self.fallback_query_service is None:
            raise AppException("查询服务未初始化", code=5004, status_code=500)

        records = self.fallback_query_service.list_records(
            period=self._resolve_period(payload),
            filters=self._resolve_filters(payload),
        )
        items = [self._fallback_detail_item(record) for record in records]
        order_by = self._detail_sort_field(payload.order_by)
        reverse = payload.order_direction != "asc"
        # `None` 值先排后排，避免 demo 模型里缺失字段时报 TypeError。
        items.sort(key=lambda item: (item.get(order_by) is None, item.get(order_by)), reverse=reverse)
        start = (payload.page - 1) * payload.page_size
        end = start + payload.page_size
        page_items = items[start:end]
        response = {
            "query_type": "detail",
            "metric_type": payload.metric_type,
            "source_scope": payload.source_scope,
            "filters": payload.model_dump(),
            "total": len(items),
            "page": payload.page,
            "page_size": payload.page_size,
            "items": page_items,
            "execution_mode": "fallback",
            "compatibility_notice": self._compatibility_notice(payload),
        }
        detail_question = self._build_detail_question(payload)
        detail_parsed = self._build_detail_parsed_snapshot(payload)
        detail_response_meta = self._attach_direct_query_contract(
            question=detail_question,
            parsed_snapshot=detail_parsed,
            query_result=response,
        )
        self._safe_write_log(
            trace_id=trace_id,
            query_type="DETAIL",
            payload=payload.model_dump(),
            metric_type=payload.metric_type,
            result_count=LogisticsResultCountHelper.extract_count(response),
            route_type=f"{payload.source_scope}:fallback",
            question_text=detail_question,
            payload_snapshot=self._build_direct_query_log_payload(
                question=detail_question,
                request_payload=payload.model_dump(),
                parsed_snapshot=detail_parsed,
                query_result=response,
                response_meta=detail_response_meta,
            ),
        )
        return response

    def _compare_fallback(
        self,
        payload: LogisticsCompareQuery,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """对比查询的回退实现。"""
        if self.fallback_query_service is None:
            raise AppException("查询服务未初始化", code=5004, status_code=500)

        # 左右两侧各自带时间窗口，但共用一套基础过滤条件。
        left_records = self.fallback_query_service.list_records(
            period=self._resolve_period(payload, payload.left.model_dump()),
            filters=self._resolve_filters(payload),
        )
        right_records = self.fallback_query_service.list_records(
            period=self._resolve_period(payload, payload.right.model_dump()),
            filters=self._resolve_filters(payload),
        )

        if payload.compare_dim:
            mapping = FALLBACK_GROUP_BY_MAPPING.get(payload.compare_dim)
            if mapping is None:
                raise AppException(
                    f"fallback 模式下暂不支持 compare_dim={payload.compare_dim}",
                    code=4007,
                    status_code=400,
                )
            items = self._build_fallback_compare_items(
                left_records=left_records,
                right_records=right_records,
                metric_type=payload.metric_type,
                compare_dim=payload.compare_dim,
                mapped_field=mapping[0],
            )
            response = {
                "query_type": "compare",
                "metric_type": payload.metric_type,
                "left_label": payload.left.label,
                "right_label": payload.right.label,
                "compare_dim": payload.compare_dim,
                "items": items,
                "source_scope": payload.source_scope,
                "filters": payload.model_dump(),
                "execution_mode": "fallback",
                "compatibility_notice": self._compatibility_notice(payload),
            }
        else:
            # compare_dim 为空时直接比较左右总量。
            left_value = self._metric_total(left_records, payload.metric_type)
            right_value = self._metric_total(right_records, payload.metric_type)
            diff_value = right_value - left_value
            response = {
                "query_type": "compare",
                "metric_type": payload.metric_type,
                "left_label": payload.left.label,
                "right_label": payload.right.label,
                "left_value": left_value,
                "right_value": right_value,
                "diff_value": diff_value,
                "diff_rate": (diff_value / left_value) if left_value else None,
                "items": [],
                "source_scope": payload.source_scope,
                "filters": payload.model_dump(),
                "execution_mode": "fallback",
                "compatibility_notice": self._compatibility_notice(payload),
            }

        compare_question = self._build_compare_question(payload)
        compare_parsed = self._build_compare_parsed_snapshot(payload)
        compare_response_meta = self._attach_direct_query_contract(
            question=compare_question,
            parsed_snapshot=compare_parsed,
            query_result=response,
        )
        # compare total-mode 的合法结果可能没有 items，因此这里统一复用结果数量提取逻辑。
        # 这样数据库模式和 fallback 模式的日志口径保持一致，避免历史回放状态漂移。
        compare_result_count = LogisticsResultCountHelper.extract_count(response)
        self._safe_write_log(
            trace_id=trace_id,
            query_type="COMPARE",
            payload=payload.model_dump(),
            metric_type=payload.metric_type,
            result_count=compare_result_count,
            route_type=f"{payload.source_scope}:fallback",
            question_text=compare_question,
            payload_snapshot=self._build_direct_query_log_payload(
                question=compare_question,
                request_payload=payload.model_dump(),
                parsed_snapshot=compare_parsed,
                query_result=response,
                response_meta=compare_response_meta,
            ),
        )
        return response

    def _build_fallback_compare_items(
        self,
        *,
        left_records: list[LogisticsRecord],
        right_records: list[LogisticsRecord],
        metric_type: str,
        compare_dim: str,
        mapped_field: str,
    ) -> list[dict[str, Any]]:
        """按 compare_dim 把左右两侧拼成前端展示用的差异行。"""
        left_map = self._metric_by_dimension(left_records, metric_type, mapped_field)
        right_map = self._metric_by_dimension(right_records, metric_type, mapped_field)
        keys = sorted(set(left_map) | set(right_map), key=self._compare_sort_key)
        items = []
        for key in keys:
            left_value = left_map.get(key, 0.0)
            right_value = right_map.get(key, 0.0)
            diff_value = right_value - left_value
            items.append(
                {
                    compare_dim: key,
                    "left_value": left_value,
                    "right_value": right_value,
                    "diff_value": diff_value,
                    "diff_rate": (diff_value / left_value) if left_value else None,
                }
            )
        return items

    def _metric_by_dimension(
        self,
        records: list[LogisticsRecord],
        metric_type: str,
        field_name: str,
    ) -> dict[str, float]:
        """把 demo 明细按单个维度聚合成 `{维度值: 指标值}` 结构。"""
        result: dict[str, float] = {}
        for record in records:
            key = str(self._record_value(record, field_name))
            result[key] = round(result.get(key, 0.0) + self._metric_value(record, metric_type), 2)
        return result

    def _fallback_group_records(
        self,
        records: list[LogisticsRecord],
        metric_type: str,
        group_by_pairs: list[tuple[str, tuple[str, str]]],
    ) -> list[dict[str, Any]]:
        """在 fallback 模式下模拟 `GROUP BY` 聚合。"""
        buckets: dict[tuple[Any, ...], dict[str, Any]] = {}
        for record in records:
            bucket_key = tuple(self._record_value(record, mapping[0]) for _, mapping in group_by_pairs)
            bucket = buckets.setdefault(
                bucket_key,
                {request_field: self._record_value(record, mapping[0]) for request_field, mapping in group_by_pairs},
            )
            bucket.setdefault("shipment_watt", 0.0)
            bucket.setdefault("shipment_count", 0.0)
            bucket.setdefault("shipment_trip_count", 0.0)
            bucket.setdefault("total_fee", 0.0)
            bucket.setdefault("extra_fee", 0.0)
            bucket.setdefault("row_count", 0)
            # demo 数据没有独立 shipment_count 列，这里用记录条数近似代表发货次数。
            bucket["shipment_watt"] = round(bucket["shipment_watt"] + record.shipment_watt, 2)
            bucket["shipment_count"] = round(bucket["shipment_count"] + 1, 2)
            bucket["shipment_trip_count"] = round(bucket["shipment_trip_count"] + record.shipment_trip_count, 2)
            bucket["total_fee"] = round(bucket["total_fee"] + record.total_fee, 2)
            bucket["extra_fee"] = round(bucket["extra_fee"] + record.extra_fee, 2)
            bucket["row_count"] += 1
        return list(buckets.values())

    def _fallback_summary(self, records: list[LogisticsRecord], metric_type: str) -> dict[str, float]:
        """生成 fallback 模式下的 summary 区块。"""
        shipment_watt = round(sum(record.shipment_watt for record in records), 2)
        shipment_trip_count = round(sum(record.shipment_trip_count for record in records), 2)
        total_fee = round(sum(record.total_fee for record in records), 2)
        extra_fee = round(sum(record.extra_fee for record in records), 2)
        return {
            "shipment_watt": shipment_watt,
            "shipment_count": round(float(len(records)), 2),
            "shipment_trip_count": shipment_trip_count,
            "total_fee": total_fee,
            "extra_fee": extra_fee,
            "row_count": len(records),
            "metric_value": self._metric_total(records, metric_type),
        }

    def _resolve_period(
        self,
        payload,
        side_override: dict[str, Any] | None = None,
    ) -> MonthRange:
        """把 legacy 查询模型里的日期/月份列表转换成当前项目通用的 MonthRange。"""
        year_month_list = list(payload.year_month_list)
        start_date = payload.start_date
        end_date = payload.end_date
        if side_override:
            year_month_list = side_override.get("year_month_list") or year_month_list
            start_date = side_override.get("start_date") or start_date
            end_date = side_override.get("end_date") or end_date

        if year_month_list:
            ordered = sorted(year_month_list, key=month_index)
            return MonthRange(start_month=ordered[0], end_month=ordered[-1])

        start_month = self._date_to_month(start_date) if start_date else None
        end_month = self._date_to_month(end_date) if end_date else None
        if start_month and end_month:
            return MonthRange(start_month=start_month, end_month=end_month)
        if start_month:
            return MonthRange(start_month=start_month, end_month=start_month)
        if end_month:
            return MonthRange(start_month=end_month, end_month=end_month)
        return MonthRange(start_month=format_month(2026, 1), end_month=format_month(2026, 3))

    def _resolve_filters(self, payload) -> LogisticsFilters:
        """把 legacy 过滤条件折叠成当前 demo 查询可识别的过滤对象。

        由于 demo 数据字段有限，这里只能保留 source_type、transport_mode 和 keyword。
        其余条件会在 compatibility_notice 中提示人工关注。
        """
        keyword_candidates = [
            payload.customer_name,
            payload.logistics_company_name,
            payload.region_name,
            payload.warehouse_name,
            payload.origin_place,
            payload.contract_no,
            payload.inquiry_no,
            payload.ship_instruction_no,
            payload.sap_order_no,
            payload.vehicle_no,
            payload.task_id,
            payload.product_spec,
        ]
        keyword = next((item for item in keyword_candidates if item), None)
        transport_modes = [payload.transport_mode] if payload.transport_mode else []
        return LogisticsFilters(
            transport_modes=transport_modes,
            source_type=SOURCE_SCOPE_MAPPING[payload.source_scope],
            keyword=keyword,
        )

    def _sql_metric_field(self, metric_type: str) -> str:
        """校验并返回数据库模式下真实可用的指标列名。"""
        metric_field = SQL_METRIC_FIELD_MAP.get(metric_type)
        if metric_field is None:
            raise AppException(f"不支持的 metric_type: {metric_type}", code=4006, status_code=400)
        return metric_field

    def _attach_aggregate_contract(
        self,
        *,
        payload: LogisticsAggregateQuery,
        query_result: dict[str, Any],
    ) -> None:
        """给 aggregate 结果补最小统一契约。

        说明：
        1. 当前条件查询页直接消费 aggregate 返回，因此这里补齐前端直依赖字段；
        2. 保持 summary / items 等既有结构不变，只增量补 status / explanation / response_meta；
        3. 该逻辑同时覆盖数据库模式和 fallback 模式，避免前端再次分支兼容。
        """
        parsed_snapshot = self._build_aggregate_parsed_snapshot(payload)
        question = self._build_aggregate_question(payload)

        result_explanation = self.result_explainer.build(
            question=question,
            parsed=parsed_snapshot,
            query_result=query_result,
        )
        no_result_analysis = self.no_result_analyzer.analyze(
            question=question,
            parsed=parsed_snapshot,
            query_result=query_result,
        )
        status = self.query_response_standardizer.build_status(
            parsed=parsed_snapshot,
            query_result=query_result,
        )

        query_result["status"] = deepcopy(status)
        query_result["result_explanation"] = deepcopy(result_explanation)
        if no_result_analysis is not None:
            query_result["no_result_analysis"] = deepcopy(no_result_analysis)
        else:
            query_result.pop("no_result_analysis", None)

        query_result["response_meta"] = self.query_response_standardizer.build_response_meta(
            question=question,
            parsed=parsed_snapshot,
            query_result=query_result,
            status=status,
        )

    def _attach_direct_query_contract(
        self,
        *,
        question: str,
        parsed_snapshot: dict[str, Any],
        query_result: dict[str, Any],
    ) -> dict[str, Any]:
        """给 direct query 结果补最小共享字段。

        说明：
        1. 当前只服务于 detail / compare 直连查询；
        2. 保持既有结果结构不变，只增量补共享字段；
        3. 返回 response_meta，便于日志快照复用，减少后续重复构造。
        """
        result_explanation = self.result_explainer.build(
            question=question,
            parsed=parsed_snapshot,
            query_result=query_result,
        )
        no_result_analysis = self.no_result_analyzer.analyze(
            question=question,
            parsed=parsed_snapshot,
            query_result=query_result,
        )
        status = self.query_response_standardizer.build_status(
            parsed=parsed_snapshot,
            query_result=query_result,
        )

        query_result["status"] = deepcopy(status)
        query_result["result_explanation"] = deepcopy(result_explanation)
        if no_result_analysis is not None:
            query_result["no_result_analysis"] = deepcopy(no_result_analysis)
        else:
            query_result.pop("no_result_analysis", None)

        response_meta = self.query_response_standardizer.build_response_meta(
            question=question,
            parsed=parsed_snapshot,
            query_result=query_result,
            status=status,
        )
        query_result["response_meta"] = deepcopy(response_meta)
        return response_meta

    @staticmethod
    def _build_aggregate_parsed_snapshot(payload: LogisticsAggregateQuery) -> dict[str, Any]:
        """为 aggregate 结果解释补一份最小 parsed 快照。

        说明：
        1. 直接结构化查询没有自然语言解析过程，因此这里不伪造模板信息；
        2. 只补结果解释、空结果分析和状态计算真正依赖的核心字段；
        3. 统一标记为 logistics 域，便于复用现有标准化器。
        """
        return {
            "selected_domain": "logistics",
            "mode": "aggregate",
            "metric_type": payload.metric_type,
            "source_scope": payload.source_scope,
            "year_month_list": list(payload.year_month_list),
            "customer_name": payload.customer_name,
            "logistics_company_name": payload.logistics_company_name,
            "region_name": payload.region_name,
            "warehouse_name": payload.warehouse_name,
            "transport_mode": payload.transport_mode,
            "origin_place": payload.origin_place,
        }

    @staticmethod
    def _build_aggregate_question(payload: LogisticsAggregateQuery) -> str:
        """把结构化筛选条件整理成结果解释可读的问题摘要。"""
        conditions: list[str] = []
        if payload.year_month_list:
            conditions.append("月份 " + "、".join(payload.year_month_list))
        if payload.customer_name:
            conditions.append(f"客户 {payload.customer_name}")
        if payload.logistics_company_name:
            conditions.append(f"物流公司 {payload.logistics_company_name}")
        if payload.region_name:
            conditions.append(f"区域 {payload.region_name}")
        if payload.origin_place:
            conditions.append(f"始发地 {payload.origin_place}")
        if payload.transport_mode:
            conditions.append(f"运输方式 {payload.transport_mode}")

        summary = "，".join(conditions) if conditions else "当前筛选条件"
        return f"{summary} 的 {LogisticsQueryService._metric_type_label(payload.metric_type)} 统计"

    @staticmethod
    def _build_detail_parsed_snapshot(payload: LogisticsDetailQuery) -> dict[str, Any]:
        """为 detail 直连查询补一份最小 parsed 快照。"""
        return {
            "selected_domain": "logistics",
            "mode": "detail",
            "metric_type": payload.metric_type,
            "source_scope": payload.source_scope,
            "year_month_list": list(payload.year_month_list),
            "customer_name": payload.customer_name,
            "logistics_company_name": payload.logistics_company_name,
            "region_name": payload.region_name,
            "warehouse_name": payload.warehouse_name,
            "transport_mode": payload.transport_mode,
            "origin_place": payload.origin_place,
            "contract_no": payload.contract_no,
            "inquiry_no": payload.inquiry_no,
            "ship_instruction_no": payload.ship_instruction_no,
            "sap_order_no": payload.sap_order_no,
            "task_id": payload.task_id,
        }

    @staticmethod
    def _build_detail_question(payload: LogisticsDetailQuery) -> str:
        """把 detail 条件整理成可读问题标题，供日志和历史页复用。"""
        for label, value in [
            ("合同编号", payload.contract_no),
            ("询比价编号", payload.inquiry_no),
            ("发货指令", payload.ship_instruction_no),
            ("SAP 单号", payload.sap_order_no),
            ("任务编号", payload.task_id),
            ("车牌号", payload.vehicle_no),
        ]:
            if value:
                return f"{label} {value} 的明细"

        if payload.year_month_list:
            return f"月份 {'、'.join(payload.year_month_list)} 的明细"
        return "当前筛选条件的明细"

    @staticmethod
    def _build_compare_parsed_snapshot(payload: LogisticsCompareQuery) -> dict[str, Any]:
        """为 compare 直连查询补一份最小 parsed 快照。"""
        return {
            "selected_domain": "logistics",
            "mode": "compare",
            "metric_type": payload.metric_type,
            "source_scope": payload.source_scope,
            "compare_dim": payload.compare_dim,
            "left": payload.left.model_dump(),
            "right": payload.right.model_dump(),
            "customer_name": payload.customer_name,
            "logistics_company_name": payload.logistics_company_name,
            "region_name": payload.region_name,
            "warehouse_name": payload.warehouse_name,
            "transport_mode": payload.transport_mode,
            "origin_place": payload.origin_place,
        }

    @staticmethod
    def _build_compare_question(payload: LogisticsCompareQuery) -> str:
        """把 compare 条件整理成可读问题标题，供日志和历史页复用。"""
        metric_label = LogisticsQueryService._metric_type_label(payload.metric_type)
        if payload.compare_dim:
            return f"{payload.left.label} 与 {payload.right.label} 的 {metric_label} 按 {payload.compare_dim} 对比"
        return f"{payload.left.label} 与 {payload.right.label} 的 {metric_label} 对比"

    @staticmethod
    def _build_direct_query_log_payload(
        *,
        question: str,
        request_payload: dict[str, Any],
        parsed_snapshot: dict[str, Any],
        query_result: dict[str, Any],
        response_meta: dict[str, Any],
    ) -> dict[str, Any]:
        """构建 direct query 的最小历史快照。

        说明：
        1. 这里保留原始请求参数，避免后续历史重查丢失输入；
        2. 同时补上 parsed / response_meta / query_result 最小快照，减少历史详情对兼容补造的依赖；
        3. items 仍做截断保护，避免日志体积无限膨胀。
        """
        safe_items = query_result.get("items") if isinstance(query_result.get("items"), list) else []
        limited_items = deepcopy(safe_items[:20])
        result_count = LogisticsResultCountHelper.extract_count(query_result)
        return {
            "question": question,
            "request_payload": deepcopy(request_payload),
            "parsed": deepcopy(parsed_snapshot),
            "execution_summary": {
                "execution_mode": query_result.get("execution_mode"),
                "result_count": result_count,
            },
            "response_meta": {
                "question": response_meta.get("question"),
                "domain": response_meta.get("domain"),
                "mode": response_meta.get("mode"),
                "metric_type": response_meta.get("metric_type"),
                "source_scope": response_meta.get("source_scope"),
                "status": deepcopy(response_meta.get("status")),
                "trace_ready": response_meta.get("trace_ready"),
                "result_count": response_meta.get("result_count"),
            },
            "query_result": {
                "query_type": query_result.get("query_type"),
                "metric_type": query_result.get("metric_type"),
                "source_scope": query_result.get("source_scope"),
                "filters": deepcopy(query_result.get("filters")),
                "execution_mode": query_result.get("execution_mode"),
                "status": deepcopy(query_result.get("status")),
                "summary": deepcopy(query_result.get("summary")),
                "total": query_result.get("total"),
                "page": query_result.get("page"),
                "page_size": query_result.get("page_size"),
                "compare_dim": query_result.get("compare_dim"),
                "left_label": query_result.get("left_label"),
                "right_label": query_result.get("right_label"),
                "left_value": query_result.get("left_value"),
                "right_value": query_result.get("right_value"),
                "diff_value": query_result.get("diff_value"),
                "diff_rate": query_result.get("diff_rate"),
                "compatibility_notice": deepcopy(query_result.get("compatibility_notice")),
                "result_explanation": deepcopy(query_result.get("result_explanation")),
                "no_result_analysis": deepcopy(query_result.get("no_result_analysis")),
                "items": limited_items,
                "item_count": len(safe_items),
                "result_count": result_count,
                "items_truncated": len(safe_items) > len(limited_items),
            },
        }

    @staticmethod
    def _metric_type_label(metric_type: str) -> str:
        """返回指标中文名，供结果解释和空结果分析复用。"""
        mapping = {
            "shipment_watt": "运量（瓦数）",
            "shipment_count": "发货件数",
            "shipment_trip_count": "车次",
            "total_fee": "总费用",
            "extra_fee": "附加费",
        }
        return mapping.get(metric_type, metric_type)

    @staticmethod
    def _date_to_month(value: str) -> str:
        return value[:7]

    @staticmethod
    def _record_value(record: LogisticsRecord, field_name: str) -> Any:
        if field_name == "year":
            return record.year
        if field_name == "month":
            return record.month_key
        if field_name == "company":
            return record.company
        if field_name == "warehouse":
            return record.warehouse
        return getattr(record, field_name)

    @staticmethod
    def _metric_value(record: LogisticsRecord, metric_type: str) -> float:
        mapped = FALLBACK_METRIC_MAPPING[metric_type]
        if mapped == "__shipment_count__":
            return 1.0
        return float(getattr(record, mapped))

    def _metric_total(self, records: list[LogisticsRecord], metric_type: str) -> float:
        return round(sum(self._metric_value(record, metric_type) for record in records), 2)

    @staticmethod
    def _detail_sort_field(order_by: str) -> str:
        mapping = {
            "biz_date": "biz_date",
            "biz_month": "biz_month",
            "shipment_watt": "shipment_watt",
            "shipment_count": "shipment_count",
            "shipment_trip_count": "shipment_trip_count",
            "total_fee": "total_fee",
            "extra_fee": "extra_fee",
            "logistics_company_name": "logistics_company_name",
            "warehouse_name": "warehouse_name",
            "task_id": "task_id",
        }
        return mapping.get(order_by, "biz_date")

    @staticmethod
    def _fallback_detail_item(record: LogisticsRecord) -> dict[str, Any]:
        """把 demo 明细记录投影成一期 detail 接口期望的字段结构。

        注意：
        demo 数据里的 `company` 实际表示“基地”，不是正式承运商。
        因此 detail fallback 不能再把它直接塞进 `logistics_company_name`，
        否则前端会把“基地”误当成“物流公司”展示。
        """
        return {
            "id": record.record_id,
            "source_type": record.source_type,
            "biz_date": record.shipment_date.isoformat(),
            "biz_year": record.year,
            "biz_month": record.month_key,
            "task_id": None,
            "contract_no": None,
            "inquiry_no": None,
            "ship_instruction_no": None,
            "sap_order_no": None,
            "customer_name": None,
            "logistics_company_name": None,
            "fallback_base_name": record.company,
            "warehouse_name": record.warehouse,
            "region_name": None,
            "origin_place": None,
            "transport_mode": record.transport_mode,
            "plate_number": None,
            "product_spec": None,
            "product_power": None,
            "shipment_count": 1,
            "shipment_watt": round(record.shipment_watt, 2),
            "shipment_trip_count": record.shipment_trip_count,
            "total_fee": round(record.total_fee, 2),
            "extra_fee": round(record.extra_fee, 2),
            "source_ref": record.record_id,
            "destination": record.destination,
        }

    @staticmethod
    def _sort_aggregate_items(items: list[dict[str, Any]], order_by: str, order_direction: str) -> list[dict[str, Any]]:
        """统计结果排序。

        这里额外处理 YYYY-MM 字符串，避免月份按字典序而不是时间序排序。
        """
        reverse = order_direction != "asc"

        def key_func(item: dict[str, Any]) -> Any:
            value = item.get(order_by)
            if isinstance(value, str) and re.match(r"^\d{4}-\d{2}$", value):
                return month_index(value)
            return value

        try:
            return sorted(items, key=key_func, reverse=reverse)
        except TypeError:
            return items

    @staticmethod
    def _compare_sort_key(value: str) -> Any:
        if re.match(r"^\d{4}-\d{2}$", value):
            return month_index(value)
        return value

    def _safe_write_log(
        self,
        *,
        trace_id: str | None,
        query_type: str,
        payload: dict[str, Any],
        metric_type: str,
        result_count: int,
        route_type: str,
        question_text: str | None = None,
        payload_snapshot: dict[str, Any] | None = None,
    ) -> None:
        """尽力写入查询日志。

        查询日志失败不会影响主请求返回，只记录 warning。
        """
        if self.db is None:
            return
        try:
            self.repository.write_query_log(
                self.db,
                {
                    "trace_id": trace_id or "local-dev",
                    "query_type": query_type,
                    "question_text": question_text,
                    # 这里统一允许写入“原始请求 + 最小快照”的增强载荷。
                    # 使用 default=str，避免 Decimal、日期等对象导致日志序列化失败。
                    "request_payload": json.dumps(payload_snapshot or payload, ensure_ascii=False, default=str),
                    "route_type": route_type,
                    "metric_type": metric_type,
                    "result_count": result_count,
                    "status": "SUCCESS",
                    "message": None,
                },
            )
            self.db.commit()
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            logger.warning("write query log failed: %s", exc)

    @staticmethod
    def _compatibility_notice(payload) -> list[str]:
        """返回 fallback 模式下需要人工注意的兼容提示。"""
        notices = [
            "当前结果为 fallback 模式，说明数据库未连通或一期查询表/日志表未就绪；上线前需确认 dws_logistics_monthly_metric、dws_logistics_detail_union、sys_query_log 已存在并有数据。"
        ]
        group_fields = list(getattr(payload, "group_by", []))
        unsupported_group_fields = [field for field in group_fields if field not in FALLBACK_GROUP_BY_MAPPING]
        if unsupported_group_fields:
            notices.append("fallback 模式下以下 group_by 字段会被忽略: " + ", ".join(unsupported_group_fields))

        unsafe_group_fields = [field for field in group_fields if field in FALLBACK_UNSAFE_GROUP_FIELDS]
        if unsafe_group_fields:
            notices.append(
                "fallback 模式下以下 group_by 字段语义不可靠，已阻止返回误导性结果: "
                + ", ".join(unsafe_group_fields)
            )
        return notices

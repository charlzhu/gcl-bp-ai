from backend.app.domains.logistics.query_templates import (
    extract_business_types,
    extract_companies,
    extract_period_tokens,
    extract_transport_modes,
    infer_compare_mode,
    infer_intent,
    infer_metric,
    metric_label,
)
from backend.app.schemas.chat import ChatQueryRequest, ChatQueryResponse
from backend.app.schemas.common import MonthRange
from backend.app.schemas.logistics_query import (
    CompareQueryRequest,
    DetailQueryRequest,
    LogisticsFilters,
    MetricsQueryRequest,
)
from backend.app.services.compare_service import CompareService
from backend.app.services.query_service import QueryService
from backend.app.utils.time_utils import format_month, shift_month


class ChatService:
    """
    对话服务
    """
    def __init__(
        self,
        *,
        query_service: QueryService,
        compare_service: CompareService,
    ) -> None:
        self.query_service = query_service
        self.compare_service = compare_service

    def ask(self, request: ChatQueryRequest) -> ChatQueryResponse:
        intent = infer_intent(request.question)
        metric = infer_metric(request.question)
        filters = LogisticsFilters(
            companies=extract_companies(request.question),
            transport_modes=extract_transport_modes(request.question),
            business_types=extract_business_types(request.question),
        )

        if intent == "compare":
            normalized_request = self._build_compare_request(
                question=request.question,
                metric=metric,
                filters=filters,
            )
            result = self.compare_service.compare(normalized_request)
            answer = self._format_compare_answer(result.summary, metric)
            return ChatQueryResponse(
                intent="compare",
                answer=answer,
                normalized_request=normalized_request.model_dump(),
                structured_result=result.model_dump(),
            )

        if intent == "detail":
            period = self._resolve_default_period(extract_period_tokens(request.question))
            normalized_request = DetailQueryRequest(period=period, filters=filters)
            result = self.query_service.query_detail(normalized_request)
            answer = f"已返回 {result.page.total} 条明细中的前 {len(result.items)} 条，可用于前端明细下钻。"
            return ChatQueryResponse(
                intent="detail",
                answer=answer,
                normalized_request=normalized_request.model_dump(),
                structured_result=result.model_dump(),
            )

        period = self._resolve_default_period(extract_period_tokens(request.question))
        normalized_request = MetricsQueryRequest(
            period=period,
            metrics=[metric],
            group_by=["month"],
            filters=filters,
        )
        result = self.query_service.query_metrics(normalized_request)
        total_value = result.summary.get(metric, 0.0)
        answer = (
            f"{period.start_month} 至 {period.end_month} 的{metric_label(metric)}为 {total_value}，"
            f"共返回 {len(result.records)} 条分组结果。"
        )
        return ChatQueryResponse(
            intent="metrics",
            answer=answer,
            normalized_request=normalized_request.model_dump(),
            structured_result=result.model_dump(),
        )

    def _build_compare_request(
        self,
        *,
        question: str,
        metric: str,
        filters: LogisticsFilters,
    ) -> CompareQueryRequest:
        tokens = extract_period_tokens(question)
        compare_mode = infer_compare_mode(question) or "custom"
        if len(tokens) >= 2:
            base_period = self._token_to_period(tokens[0])
            compare_period = self._token_to_period(tokens[1])
            compare_mode = "custom"
        else:
            base_period = self._resolve_default_period(tokens)
            compare_period = None
            if compare_mode == "custom":
                compare_mode = "yoy"

        return CompareQueryRequest(
            metric=metric,
            base_period=base_period,
            compare_period=compare_period,
            compare_mode=compare_mode,
            group_by=["month"],
            filters=filters,
        )

    @staticmethod
    def _resolve_default_period(tokens: list[tuple[int, int | None]]) -> MonthRange:
        if not tokens:
            return MonthRange(start_month="2026-01", end_month="2026-03")
        return ChatService._token_to_period(tokens[0])

    @staticmethod
    def _token_to_period(token: tuple[int, int | None]) -> MonthRange:
        year, month = token
        if month is None:
            return MonthRange(
                start_month=format_month(year, 1),
                end_month=format_month(year, 12),
            )
        value = format_month(year, month)
        return MonthRange(start_month=value, end_month=value)

    @staticmethod
    def _format_compare_answer(summary: dict[str, object], metric: str) -> str:
        delta = summary.get("delta", 0)
        direction = "上升" if isinstance(delta, (int, float)) and delta > 0 else "下降"
        if delta == 0:
            direction = "持平"
        return (
            f"{metric_label(metric)}对比结果已生成，当前周期较对比周期{direction}，"
            f"差值为 {summary.get('delta', 0)}。"
        )

from fastapi import APIRouter, Depends, Request

from backend.app.api.deps import get_compare_service, get_query_service
from backend.app.core.response import ResponseEnvelope, success_response
from backend.app.schemas.logistics_query import (
    CompareQueryRequest,
    CompareQueryResult,
    DetailQueryRequest,
    DetailQueryResult,
    ExportPreviewResult,
    ExportQueryRequest,
    MetricsQueryRequest,
    MetricsQueryResult,
)
from backend.app.services.compare_service import CompareService
from backend.app.services.query_service import QueryService

router = APIRouter(prefix="/logistics/query")


@router.post("/metrics", response_model=ResponseEnvelope[MetricsQueryResult])
def query_metrics(
    payload: MetricsQueryRequest,
    request: Request,
    query_service: QueryService = Depends(get_query_service),
) -> ResponseEnvelope[MetricsQueryResult]:
    data = query_service.query_metrics(payload)
    return success_response(request, data)


@router.post("/compare", response_model=ResponseEnvelope[CompareQueryResult])
def query_compare(
    payload: CompareQueryRequest,
    request: Request,
    compare_service: CompareService = Depends(get_compare_service),
) -> ResponseEnvelope[CompareQueryResult]:
    """
    对比查询
    """
    data = compare_service.compare(payload)
    return success_response(request, data)


@router.post("/detail", response_model=ResponseEnvelope[DetailQueryResult])
def query_detail(
    payload: DetailQueryRequest,
    request: Request,
    query_service: QueryService = Depends(get_query_service),
) -> ResponseEnvelope[DetailQueryResult]:
    data = query_service.query_detail(payload)
    return success_response(request, data)


@router.post("/export", response_model=ResponseEnvelope[ExportPreviewResult])
def export_query_result(
    payload: ExportQueryRequest,
    request: Request,
    query_service: QueryService = Depends(get_query_service),
) -> ResponseEnvelope[ExportPreviewResult]:
    data = query_service.export_metrics(payload)
    return success_response(request, data)

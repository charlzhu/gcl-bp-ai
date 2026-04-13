from __future__ import annotations

from backend.app.domains.logistics.services.nl2query_service import LogisticsNL2QueryService
from backend.app.domains.logistics.schemas.query import LogisticsNLQuery


class _DummyQueryService:
    """用于 V10 测试的简易 QueryService 替身。"""

    def aggregate(self, payload, trace_id=None):
        return {
            "query_type": "aggregate",
            "metric_type": payload.metric_type,
            "source_scope": payload.source_scope,
            "total": 1,
            "items": [{"biz_month": "2025-03", "shipment_watt": 12345}],
            "execution_mode": "database",
        }

    def compare(self, payload, trace_id=None):
        return {
            "query_type": "compare",
            "source_scope": payload.source_scope,
            "total": 1,
            "items": [{"left_value": 100, "right_value": 120, "diff_value": 20}],
            "execution_mode": "database",
        }

    def detail(self, payload, trace_id=None):
        if payload.contract_no == "ERR001":
            return {
                "query_type": "detail",
                "metric_type": payload.metric_type,
                "source_scope": payload.source_scope,
                "filters": payload.model_dump(),
                "total": 0,
                "page": payload.page,
                "page_size": payload.page_size,
                "items": [],
                "execution_mode": "database",
            }
        return {
            "query_type": "detail",
            "metric_type": payload.metric_type,
            "source_scope": payload.source_scope,
            "filters": payload.model_dump(),
            "total": 1,
            "page": payload.page,
            "page_size": payload.page_size,
            "items": [{"contract_no": payload.contract_no, "source_type": "HIST"}],
            "execution_mode": "database",
        }

    def probe_detail_business_no(self, *, field_name: str, field_value: str, source_scope: str = "all") -> bool:
        """模拟编号存在性检查：ERR001 不存在，其余存在。"""
        return field_value != "ERR001"


class _ErrorQueryService(_DummyQueryService):
    """用于验证 V10 标准状态码的异常场景。"""

    def detail(self, payload, trace_id=None):
        raise RuntimeError("mock detail error")


def test_v10_should_append_response_meta_and_status():
    service = LogisticsNL2QueryService(query_service=_DummyQueryService())
    result = service.parse_and_query(LogisticsNLQuery(question="合同编号GCL001的明细"), trace_id="t-v10-1")

    assert "response_meta" in result
    assert result["query_result"]["status"]["code"] in {"OK", "OK_WITH_ADJUSTMENTS"}
    assert result["response_meta"]["status"]["code"] == result["query_result"]["status"]["code"]


def test_v10_should_mark_detail_not_found_when_business_no_not_exist():
    service = LogisticsNL2QueryService(query_service=_DummyQueryService())
    result = service.parse_and_query(LogisticsNLQuery(question="合同编号ERR001的明细"), trace_id="t-v10-2")

    assert result["query_result"]["total"] == 0
    assert result["query_result"]["status"]["code"] == "DETAIL_NOT_FOUND"
    assert result["query_result"]["business_no_probe"]["exists"] is False


def test_v10_should_mark_execution_error_when_executor_failed():
    service = LogisticsNL2QueryService(query_service=_ErrorQueryService())
    result = service.parse_and_query(LogisticsNLQuery(question="合同编号ANY001的明细"), trace_id="t-v10-3")

    assert result["query_result"]["execution_mode"] == "error_fallback"
    assert result["query_result"]["status"]["code"] == "EXECUTION_ERROR"

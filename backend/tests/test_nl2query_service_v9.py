from __future__ import annotations

from backend.app.domains.logistics.services.nl2query_service import LogisticsNL2QueryService
from backend.app.domains.logistics.schemas.query import LogisticsNLQuery


class _DummyQueryService:
    """用于 V9 测试的简易 QueryService 替身。"""

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
        if payload.contract_no == "EMPTY001":
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
            "items": [
                {
                    "contract_no": payload.contract_no,
                    "customer_name": "浙江杭泰数智能源开发有限公司",
                    "biz_date": "2025-03-16",
                    "shipment_watt": 1116000,
                    "source_type": "HIST",
                }
            ],
            "execution_mode": "database",
        }


class _ErrorQueryService(_DummyQueryService):
    """用于验证 V9 异常兜底逻辑。"""

    def detail(self, payload, trace_id=None):
        raise RuntimeError("模拟数据库执行异常")


def test_v9_should_add_result_explanation_for_detail_query():
    service = LogisticsNL2QueryService(query_service=_DummyQueryService())
    result = service.parse_and_query(LogisticsNLQuery(question="合同编号ABC123的明细"))
    explanation = result["query_result"].get("result_explanation")
    assert explanation is not None
    assert explanation["query_type"] == "detail"
    assert explanation["result_count"] == 1
    assert "summary" in explanation


def test_v9_should_add_no_result_analysis_when_query_is_empty():
    service = LogisticsNL2QueryService(query_service=_DummyQueryService())
    result = service.parse_and_query(LogisticsNLQuery(question="合同编号EMPTY001的明细"))
    analysis = result["query_result"].get("no_result_analysis")
    assert analysis is not None
    assert analysis["is_empty_result"] is True
    assert len(analysis["suggestions"]) >= 1


def test_v9_should_return_error_fallback_when_executor_raises_exception():
    service = LogisticsNL2QueryService(query_service=_ErrorQueryService())
    result = service.parse_and_query(LogisticsNLQuery(question="合同编号ERR001的明细"))
    query_result = result["query_result"]
    assert query_result["execution_mode"] == "error_fallback"
    assert query_result["total"] == 0
    assert "execution_error" in query_result
    assert query_result["result_explanation"]["result_count"] == 0

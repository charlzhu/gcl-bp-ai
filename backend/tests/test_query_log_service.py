from __future__ import annotations

import json
from datetime import datetime

from backend.app.domains.logistics.services.query_plan_store import LogisticsQueryPlanStore
from backend.app.services.query_log_service import QueryLogService


class _FakeQueryLogRepository:
    """用于查询历史测试的轻量仓储替身。"""

    def __init__(self, row: dict | None = None) -> None:
        self.row = row
        self.written_payloads: list[dict] = []
        self.last_list_params: dict | None = None

    def list_query_logs(
        self,
        db,
        *,
        limit=100,
        offset=0,
        query_type=None,
        status=None,
        trace_id=None,
        keyword=None,
    ):
        """返回固定列表，模拟 sys_query_log 查询结果。"""
        self.last_list_params = {
            "limit": limit,
            "offset": offset,
            "query_type": query_type,
            "status": status,
            "trace_id": trace_id,
            "keyword": keyword,
        }
        rows = [self.row] if self.row else []
        return rows, len(rows)

    def get_query_log_detail(self, db, *, log_id: int):
        """返回固定详情，模拟按主键读取日志。"""
        if self.row and self.row.get("id") == log_id:
            return self.row
        return None

    def write_query_log(self, db, payload: dict) -> None:
        """记录落库载荷，供断言历史快照结构。"""
        self.written_payloads.append(payload)


class _FakeDB:
    """用于 query plan store 测试的轻量数据库替身。"""

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class _FakeQueryService:
    """为 QueryPlanStore 提供 db 和 repository 属性。"""

    def __init__(self, repository: _FakeQueryLogRepository) -> None:
        self.db = _FakeDB()
        self.repository = repository


def test_query_log_service_should_expose_detail_fields_for_frontend():
    """查询历史详情应直接返回前端需要的状态、模板命中和结果快照。"""
    row = {
        "id": 66,
        "trace_id": "trace-001",
        "query_type": "NL_QUERY_PLAN",
        "question_text": "2025年3月运量是多少",
        "request_payload": json.dumps(
            {
                "parsed": {
                    "mode": "aggregate",
                    "metric_type": "shipment_watt",
                    "source_scope": "hist",
                    "template_hit": True,
                    "template_id": "monthly_metric_total",
                    "selected_domain": "logistics",
                },
                "execution_binding": {
                    "execution_mode": "aggregate",
                },
                "execution_summary": {
                    "execution_mode": "database",
                    "result_count": 1,
                },
                "response_meta": {
                    "question": "2025年3月运量是多少",
                    "status": {
                        "code": "OK",
                        "message": "查询执行成功。",
                        "success": True,
                        "severity": "info",
                        "execution_mode": "database",
                    },
                },
                "query_result": {
                    "query_type": "aggregate",
                    "execution_mode": "database",
                    "status": {
                        "code": "OK",
                        "message": "查询执行成功。",
                        "success": True,
                        "severity": "info",
                        "execution_mode": "database",
                    },
                    "summary": {
                        "shipment_watt": 12345,
                    },
                    "items": [
                        {
                            "biz_month": "2025-03",
                            "shipment_watt": 12345,
                        }
                    ],
                    "item_count": 1,
                    "items_truncated": False,
                },
            },
            ensure_ascii=False,
        ),
        "route_type": "hist",
        "metric_type": "shipment_watt",
        "result_count": 1,
        "status": "SUCCESS",
        "message": "查询计划已落库",
        "created_at": datetime(2026, 4, 13, 12, 0, 0),
    }
    repository = _FakeQueryLogRepository(row=row)
    service = QueryLogService(db=object(), repository=repository)

    listing = service.list_query_logs(limit=10)
    detail = service.get_query_log_detail(log_id=66)

    assert listing.items[0].status_code == "OK"
    assert listing.items[0].template_hit is True
    assert listing.items[0].template_id == "monthly_metric_total"
    assert detail.response_meta["status"]["code"] == "OK"
    assert detail.query_result["status"]["code"] == "OK"
    assert detail.query_result["summary"]["shipment_watt"] == 12345


def test_query_log_service_should_support_pagination_and_keyword():
    """查询历史列表应透传分页与关键词参数，并返回统一分页信息。"""
    row = {
        "id": 77,
        "trace_id": "trace-keyword-001",
        "query_type": "AGGREGATE",
        "question_text": "2099年1月运量是多少",
        "request_payload": json.dumps({}, ensure_ascii=False),
        "route_type": "hist",
        "metric_type": "shipment_watt",
        "result_count": 0,
        "status": "SUCCESS",
        "message": "空结果查询",
        "created_at": datetime(2026, 4, 13, 15, 0, 0),
    }
    repository = _FakeQueryLogRepository(row=row)
    service = QueryLogService(db=object(), repository=repository)

    listing = service.list_query_logs(page=2, page_size=15, keyword="2099", query_type="AGGREGATE")

    assert listing.total == 1
    assert listing.page == 2
    assert listing.page_size == 15
    assert listing.items[0].question == "2099年1月运量是多少"
    assert repository.last_list_params == {
        "limit": 15,
        "offset": 15,
        "query_type": "AGGREGATE",
        "status": None,
        "trace_id": None,
        "keyword": "2099",
    }


def test_query_plan_store_should_persist_response_meta_and_trimmed_query_result():
    """查询计划落库时应保存前端直依赖字段，并限制 items 体积。"""
    repository = _FakeQueryLogRepository()
    query_service = _FakeQueryService(repository=repository)
    store = LogisticsQueryPlanStore(query_service=query_service)

    store.save_plan(
        trace_id="trace-002",
        question="查看明细",
        parsed={
            "mode": "detail",
            "metric_type": "shipment_watt",
            "source_scope": "all",
            "template_hit": False,
        },
        execution_binding={
            "execution_mode": "detail",
            "sql_template": {
                "sql_template_id": "detail_by_business_no",
            },
            "sql_whitelist": {
                "allowed": True,
            },
        },
        execution_summary={
            "execution_mode": "database",
            "result_count": 25,
        },
        response_meta={
            "question": "查看明细",
            "domain": "logistics",
            "mode": "detail",
            "metric_type": "shipment_watt",
            "source_scope": "all",
            "status": {
                "code": "OK",
                "message": "查询执行成功。",
                "success": True,
                "severity": "info",
                "execution_mode": "database",
            },
            "result_count": 25,
        },
        query_result={
            "query_type": "detail",
            "metric_type": "shipment_watt",
            "source_scope": "all",
            "execution_mode": "database",
            "status": {
                "code": "OK",
                "message": "查询执行成功。",
                "success": True,
                "severity": "info",
                "execution_mode": "database",
            },
            "items": [{"row_no": index} for index in range(25)],
            "total": 25,
            "page": 1,
            "page_size": 20,
        },
    )

    assert query_service.db.committed is True
    assert len(repository.written_payloads) == 1

    payload = json.loads(repository.written_payloads[0]["request_payload"])
    assert payload["response_meta"]["status"]["code"] == "OK"
    assert payload["query_result"]["item_count"] == 25
    assert len(payload["query_result"]["items"]) == 20
    assert payload["query_result"]["items_truncated"] is True

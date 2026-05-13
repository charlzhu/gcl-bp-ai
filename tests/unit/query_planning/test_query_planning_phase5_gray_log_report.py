from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from typing import Any

from backend.app.domains.logistics.repositories.query_repository import LogisticsQueryRepository
from backend.app.domains.query_planning.api.endpoints.query_plan_v2 import query_plan_v2_shadow_log_report
from backend.app.domains.query_planning.services.shadow_report_service import QueryPlanningV2ShadowReportService


class _NoExecutionPlanningService:
    """测试占位 planning service，Phase 5 真实日志报表不应调用它重新规划或查数。"""

    def plan(self, **_: Any) -> None:
        raise AssertionError("真实日志灰度报表只能读取 sys_query_log，不允许重新执行 Query Planning 诊断。")


class _FakeGrayLogRepository:
    """测试用只读日志仓储，记录查询参数并返回固定 sys_query_log 行。"""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[dict[str, Any]] = []

    def list_query_logs_for_query_planning_gray(
        self,
        db: object,
        *,
        domain: str = "all",
        limit: int = 200,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        self.calls.append({"db": db, "domain": domain, "limit": limit, "days": days})
        return self.rows


def _row(
    log_id: int,
    *,
    domain: str,
    status: str,
    formal_query_key: str | None,
    shadow_strategy: str | None,
    shadow_query_key: str | None,
    execution_policy: dict[str, Any] | None = None,
    payload_override: str | None = None,
) -> dict[str, Any]:
    """构造最小 sys_query_log 行，便于测试灰度报表统计。"""

    if payload_override is not None:
        request_payload = payload_override
    else:
        shadow = None
        if shadow_strategy is not None:
            shadow = {
                "schema_version": "query_plan_v2.0",
                "domain": domain,
                "original_question": f"问题{log_id}",
                "strategy": shadow_strategy,
                "intent": "aggregate",
                "query_key": shadow_query_key,
                "slots": {"filters": {"year": 2025}},
                "guardrail_decision": {"accepted": True, "blocked_reason": None},
                "execution_policy": execution_policy
                or {"shadow_only": True, "llm_can_execute": False, "sql_generation_allowed": False},
            }
        payload = {
            "question": f"问题{log_id}",
            "response_meta": {"domain": domain, "metric_type": formal_query_key},
            "query_result": {"query_plan": {"query_key": formal_query_key}},
        }
        if shadow is not None:
            payload["query_plan_v2_shadow"] = shadow
        request_payload = json.dumps(payload, ensure_ascii=False)

    return {
        "id": log_id,
        "trace_id": f"trace-{log_id}",
        "query_type": "DATA_QA" if domain == "logistics" else "PLAN_BOM_QA",
        "question_text": f"问题{log_id}",
        "request_payload": request_payload,
        "route_type": "data_qa" if domain == "logistics" else "plan_bom_qa",
        "metric_type": formal_query_key,
        "result_count": 1,
        "status": status,
        "message": "ok",
        "created_at": datetime(2026, 5, 13, 10, log_id, 0),
    }


def test_gray_log_report_reads_only_sys_query_log_and_buckets_risks() -> None:
    """Phase 5 灰度报表应只读真实日志，统计覆盖率/一致性/风险，不重新执行 QA 或 LLM。"""
    rows = [
        _row(
            1,
            domain="logistics",
            status="SUCCESS",
            formal_query_key="hist_mw_by_carrier",
            shadow_strategy="DIRECT_RETRIEVAL",
            shadow_query_key="hist_mw_by_carrier",
        ),
        _row(
            2,
            domain="plan_bom",
            status="CLARIFICATION",
            formal_query_key=None,
            shadow_strategy="CLARIFY",
            shadow_query_key=None,
        ),
        _row(
            3,
            domain="logistics",
            status="UNSUPPORTED",
            formal_query_key=None,
            shadow_strategy="UNSUPPORTED",
            shadow_query_key=None,
        ),
        _row(
            4,
            domain="logistics",
            status="SUCCESS",
            formal_query_key="hist_mw_by_carrier",
            shadow_strategy="DIRECT_RETRIEVAL",
            shadow_query_key="hist_total_fee_by_carrier",
        ),
        _row(
            5,
            domain="plan_bom",
            status="SUCCESS",
            formal_query_key="single_order_material_specs",
            shadow_strategy=None,
            shadow_query_key=None,
        ),
        _row(
            6,
            domain="logistics",
            status="SUCCESS",
            formal_query_key="hist_mw_summary",
            shadow_strategy=None,
            shadow_query_key=None,
            payload_override="{bad json",
        ),
        _row(
            7,
            domain="logistics",
            status="SUCCESS",
            formal_query_key="hist_mw_summary",
            shadow_strategy="DIRECT_RETRIEVAL",
            shadow_query_key="hist_mw_summary",
            execution_policy={"shadow_only": False, "llm_can_execute": True, "sql_generation_allowed": True},
        ),
        _row(
            8,
            domain="logistics",
            status="SUCCESS",
            formal_query_key="hist_mw_summary",
            shadow_strategy="DIRECT_RETRIEVAL",
            shadow_query_key=None,
        ),
    ]
    repository = _FakeGrayLogRepository(rows)
    db = object()
    service = QueryPlanningV2ShadowReportService(
        planning_service=_NoExecutionPlanningService(),
        query_log_repository=repository,
        db=db,
    )

    report = service.build_log_report(domain="all", limit=20, days=7)

    assert repository.calls == [{"db": db, "domain": "all", "limit": 20, "days": 7}]
    assert report.schema_version == "query_plan_v2.gray_report.v1"
    assert report.scope.domain == "all"
    assert report.scope.source == "sys_query_log"
    assert report.summary.total_logs == 8
    assert report.summary.shadow_available == 6
    assert report.summary.shadow_missing == 1
    assert report.summary.corrupt_payload == 1
    assert report.summary.strategy_distribution["DIRECT_RETRIEVAL"] == 4
    assert report.summary.strategy_distribution["CLARIFY"] == 1
    assert report.summary.strategy_distribution["UNSUPPORTED"] == 1
    assert report.summary.query_key_match_count == 2
    assert report.summary.query_key_mismatch_count == 2
    assert report.summary.clarify_agreement_count == 1
    assert report.summary.unsupported_agreement_count == 1
    assert [item.log_id for item in report.risk_buckets["missing_shadow"]] == [5]
    assert [item.log_id for item in report.risk_buckets["corrupt_payload"]] == [6]
    assert [item.log_id for item in report.risk_buckets["query_key_mismatch"]] == [4, 8]
    assert [item.log_id for item in report.risk_buckets["unsafe_execution_policy"]] == [7]
    assert all(sample.raw_payload is None for sample in report.samples)


class _FakeSqlResult:
    """测试用 SQLAlchemy Result 替身。"""

    def mappings(self) -> "_FakeSqlResult":
        return self

    def all(self) -> list[dict[str, Any]]:
        return []


class _FakeSqlSession:
    """测试用 DB session，捕获 SQL 和绑定参数。"""

    def __init__(self) -> None:
        self.sql_texts: list[str] = []
        self.params: list[dict[str, Any]] = []

    def execute(self, sql: object, params: dict[str, Any]) -> _FakeSqlResult:
        self.sql_texts.append(str(sql))
        self.params.append(params)
        return _FakeSqlResult()


def test_repository_lists_gray_logs_with_bound_filters_and_limit_cap() -> None:
    """Phase 5.1 仓储方法必须只读 sys_query_log，使用绑定参数并限制最大 limit。"""
    db = _FakeSqlSession()
    repository = LogisticsQueryRepository()

    rows = repository.list_query_logs_for_query_planning_gray(db, domain="plan_bom", limit=999, days=30)

    assert rows == []
    assert len(db.sql_texts) == 1
    assert "FROM sys_query_log" in db.sql_texts[0]
    assert "PLAN_BOM_QA" not in db.sql_texts[0]
    assert db.params[0]["query_type"] == "PLAN_BOM_QA"
    assert db.params[0]["limit"] == 500
    assert db.params[0]["days"] == 30


class _FakeEndpointReport:
    """测试用接口返回对象。"""

    def model_dump(self, mode: str = "json") -> dict[str, Any]:
        return {"schema_version": "query_plan_v2.gray_report.v1", "mode": mode}


class _FakeEndpointService:
    """测试用 endpoint service，捕获参数。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def build_log_report(self, *, domain: str = "all", limit: int = 200, days: int = 7) -> _FakeEndpointReport:
        self.calls.append({"domain": domain, "limit": limit, "days": days})
        return _FakeEndpointReport()


def test_shadow_log_report_endpoint_returns_api_response_without_running_formal_qa() -> None:
    """Phase 5.3 接口应调用只读灰度报表服务，并返回稳定 ApiResponse JSON。"""
    service = _FakeEndpointService()
    request = SimpleNamespace(state=SimpleNamespace(trace_id="trace-gray"))

    response = query_plan_v2_shadow_log_report(
        request=request,
        domain="logistics",
        limit=50,
        days=14,
        _=None,
        service=service,
    )

    assert service.calls == [{"domain": "logistics", "limit": 50, "days": 14}]
    assert response.code == 0
    assert response.trace_id == "trace-gray"
    assert response.data == {"schema_version": "query_plan_v2.gray_report.v1", "mode": "json"}

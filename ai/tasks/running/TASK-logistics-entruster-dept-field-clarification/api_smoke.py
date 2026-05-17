"""API smoke：验证经营计划/刘娟字段口径通过 HTTP 接口保留。

该脚本使用 FastAPI TestClient 和受控 LogisticsDataQaService，不连接真实数据库，
只验证接口层到 planner/service/repository 替身的确定性链路：
- 经营计划 -> expand_dept
- 刘娟 -> entrusted_person
- 未知人名 -> field_scope_mapping 澄清
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from backend.app.api.deps import get_logistics_data_qa_service
from backend.app.domains.logistics.schemas.llm_understanding import LogisticsLlmGuardrailDecision
from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.main import app


class _NoopHistoryDb:
    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


class _NoopQueryLogRepository:
    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        return 0


class _NoopGuardrail:
    def evaluate(self, **kwargs: Any) -> LogisticsLlmGuardrailDecision:
        rule_plan = kwargs["rule_plan"]
        return LogisticsLlmGuardrailDecision(
            question=kwargs["question"],
            rule_intent=rule_plan.intent,
            rule_query_key=rule_plan.query_key,
            rule_needs_clarification=rule_plan.needs_clarification,
            final_intent=rule_plan.intent,
            final_query_key=rule_plan.query_key,
            final_needs_clarification=rule_plan.needs_clarification,
            final_supported=not rule_plan.needs_clarification,
        )

    def write_audit_log(self, **kwargs: Any) -> None:
        return None


class _FakeRepository:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def sys_total_fee_by_filters(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(dict(kwargs))
        return {
            "total_fee": 1234.56,
            "task_count": 2,
            "parse_fail_count": 0,
            "price_missing_count": 0,
        }

    def sys_special_total_fee(self, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError(f"不应走 special_scope 锁定口径: {kwargs}")


repository = _FakeRepository()
service = LogisticsDataQaService(
    db=_NoopHistoryDb(),
    repository=repository,
    planner=LogisticsDataQaPlanner(),
    query_log_repository=_NoopQueryLogRepository(),
    guardrail_service=_NoopGuardrail(),
)


def _override_service() -> LogisticsDataQaService:
    return service


app.dependency_overrides[get_logistics_data_qa_service] = _override_service
try:
    with TestClient(app) as client:
        response = client.post("/api/v1/logistics/data-qa/query", json={"question": "26年 经营计划 刘娟 用车总费用是多少"})
        assert response.status_code == 200, response.text
        payload = response.json()
        data = payload["data"]
        assert data["query_plan"]["query_key"] == "sys_total_fee_by_filters"
        assert data["query_plan"]["filters"]["expand_dept"] == "经营计划"
        assert data["query_plan"]["filters"]["entrusted_person"] == "刘娟"
        assert repository.calls[-1]["expand_dept"] == "经营计划"
        assert repository.calls[-1]["entrusted_person"] == "刘娟"
        assert "扩充部门=经营计划" in data["answer_summary"]
        assert "委托人=刘娟" in data["answer_summary"]
        assert "锁定口径" not in data["answer_summary"]

        clarification_response = client.post("/api/v1/logistics/data-qa/query", json={"question": "26年 经营计划 张三 用车总费用是多少"})
        assert clarification_response.status_code == 200, clarification_response.text
        clarification_data = clarification_response.json()["data"]
        assert clarification_data["needs_clarification"] is True
        assert clarification_data["query_plan"]["clarification_category"] == "field_scope_mapping"
        assert "张三" in clarification_data["query_plan"]["clarification_reason"]
finally:
    app.dependency_overrides.pop(get_logistics_data_qa_service, None)

print("API smoke passed: field filters and clarification verified")

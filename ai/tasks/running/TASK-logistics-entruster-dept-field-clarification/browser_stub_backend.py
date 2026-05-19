"""浏览器 smoke 用受控后端。

启动真实 FastAPI app，并覆盖物流 data-qa 依赖，用于浏览器验证智能问答页面
对 `26年 经营计划 刘娟 用车总费用是多少` 展示字段过滤答案，而不是锁定口径答案。
"""

from __future__ import annotations

from typing import Any

import uvicorn

from backend.app.api.deps import get_logistics_data_qa_service
from backend.app.domains.logistics.schemas.llm_understanding import LogisticsLlmGuardrailDecision
from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.main import app
from backend.app.services import business_answer_stream_service as stream_module


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
    def sys_total_fee_by_filters(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "total_fee": 1234.56,
            "task_count": 2,
            "parse_fail_count": 0,
            "price_missing_count": 0,
        }

    def sys_special_total_fee(self, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError(f"不应走 special_scope 锁定口径: {kwargs}")


class _StubBusinessAnswerStreamService:
    """避免浏览器 smoke 依赖外部 LLM，仅回放确定性摘要。"""

    def stream_answer(self, *, fallback_answer: str | None = None, **kwargs: Any):
        yield fallback_answer or ""

    def apply_streamed_answer(self, *, deterministic_payload: dict[str, Any], streamed_answer: str, **kwargs: Any) -> dict[str, Any]:
        deterministic_payload["answer_summary"] = streamed_answer or deterministic_payload.get("answer_summary", "")
        return deterministic_payload


service = LogisticsDataQaService(
    db=_NoopHistoryDb(),
    repository=_FakeRepository(),
    planner=LogisticsDataQaPlanner(),
    query_log_repository=_NoopQueryLogRepository(),
    guardrail_service=_NoopGuardrail(),
)


def _override_service() -> LogisticsDataQaService:
    return service


app.dependency_overrides[get_logistics_data_qa_service] = _override_service
stream_module.BusinessAnswerStreamService = _StubBusinessAnswerStreamService

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=18081, log_level="warning")

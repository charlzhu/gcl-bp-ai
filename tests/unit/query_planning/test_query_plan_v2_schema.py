from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.domains.query_planning.schemas.query_plan_v2 import (
    QueryPlanningV2ExecutionPolicy,
    QueryPlanningV2Plan,
    QueryPlanningV2Slots,
    QueryPlanningV2SubQuery,
)


def test_query_plan_v2_direct_plan_is_stable_json_and_shadow_by_default() -> None:
    """DIRECT 查询计划必须可序列化且默认只 shadow，不允许 LLM 执行。"""
    plan = QueryPlanningV2Plan(
        domain="logistics",
        original_question="2025年各承运商发运量是多少？",
        strategy="DIRECT_RETRIEVAL",
        intent="aggregate",
        query_key="hist_mw_by_carrier",
        slots=QueryPlanningV2Slots(metrics=["shipment_mw"], dimensions=["carrier"], filters={"year": 2025}),
    )

    payload = plan.model_dump(mode="json")

    assert payload["schema_version"] == "query_plan_v2.0"
    assert payload["domain"] == "logistics"
    assert payload["original_question"] == "2025年各承运商发运量是多少？"
    assert payload["strategy"] == "DIRECT_RETRIEVAL"
    assert payload["slots"]["filters"] == {"year": 2025}
    assert payload["execution_policy"]["shadow_only"] is True
    assert payload["execution_policy"]["llm_can_execute"] is False
    assert payload["execution_policy"]["sql_generation_allowed"] is False


def test_query_plan_v2_rejects_unknown_strategy() -> None:
    """strategy 只能取受控枚举值，避免调用方注入自由策略。"""
    with pytest.raises(ValidationError):
        QueryPlanningV2Plan(
            domain="logistics",
            original_question="测试问题",
            strategy="FREE_SQL",  # type: ignore[arg-type]
        )


def test_hyde_plan_is_retrieval_only_and_not_executable() -> None:
    """HYDE 只能做检索增强，不能进入结构化 SQL 执行。"""
    plan = QueryPlanningV2Plan(
        domain="logistics",
        original_question="物流成本偏高的可能原因有哪些？",
        strategy="HYDE_RETRIEVAL",
        intent="semantic_retrieval",
        hyde_text="可检索物流成本、额外费用、线路报价和承运商表现等说明文档。",
        execution_policy=QueryPlanningV2ExecutionPolicy(executable=True, retrieval_only=False),
    )

    assert plan.execution_policy.retrieval_only is True
    assert plan.execution_policy.executable is False
    assert plan.execution_policy.sql_generation_allowed is False


def test_execution_policy_forces_shadow_only_and_denies_llm_sql() -> None:
    """即使调用方传入危险开关，schema 也必须强制回到 shadow 安全边界。"""
    policy = QueryPlanningV2ExecutionPolicy(
        shadow_only=False,
        llm_can_execute=True,
        sql_generation_allowed=True,
    )

    assert policy.shadow_only is True
    assert policy.llm_can_execute is False
    assert policy.sql_generation_allowed is False


def test_sub_query_forbids_unknown_sql_fields() -> None:
    """子查询结构不允许携带 raw_sql 等自由执行字段。"""
    with pytest.raises(ValidationError):
        QueryPlanningV2SubQuery(
            sub_query_id="sub_1",
            source_clause="2025年各承运商发运量",
            intent="aggregate",
            query_key="hist_mw_by_carrier",
            executable=True,
            raw_sql="select * from sys_query_log",  # type: ignore[call-arg]
        )

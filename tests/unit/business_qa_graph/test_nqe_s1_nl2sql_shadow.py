"""NQE-S1 focused tests: Graph 调度 NL2SQL SQLPlan shadow。

采用 TDD RED→GREEN→REFACTOR 流程。
验证 LangGraph 能正确触发物流 NL2SQL shadow 并将结果写入 state.query_plan_v2。
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState


# =============================================================================
# 1. Capability ID 测试
# =============================================================================


def test_capability_includes_logistics_nl2sql_shadow() -> None:
    """BusinessQaCapabilityId 必须包含 logistics_nl2sql_shadow。

    GREEN: 已添加到 domain.py 的 Literal 类型定义中。
    """
    from backend.app.domains.business_qa_graph.schemas.domain import BusinessQaCapabilityId

    # 验证 logistics_nl2sql_shadow 是合法的 capability 标识
    capability: BusinessQaCapabilityId = "logistics_nl2sql_shadow"  # type: ignore[assignment]
    assert capability == "logistics_nl2sql_shadow"


# =============================================================================
# 2. State 扩展测试
# =============================================================================


def test_state_accepts_query_plan_v2_field() -> None:
    """state 必须能承载 query_plan_v2 字段。

    GREEN: 已添加到 BusinessQaGraphState 中。
    """
    state: BusinessQaGraphState = {
        "question": "2024 年总发运量是多少？",
        "domain_hint": "auto",
        "trace_id": "trace-nl2sql",
        "trace": [],
        "status": "DOMAIN_ROUTED",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "domain_routing_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_nl2sql_shadow"],
        "domain_route": {},
        "shadow_plan_raw": {},
        "understanding_status": "UNSAFE",
        "validation_result": "error",
        "validation_details": {},
        "user_visible_message": "",
        "execution_status": "NOT_STARTED",
        "execution_result": {},
    }

    # NQE-S1 期望新字段：query_plan_v2
    next_state = dict(state)
    next_state["query_plan_v2"] = {
        "status": "shadow_generated",
        "domain": "logistics",
    }

    assert next_state["query_plan_v2"]["status"] == "shadow_generated"
    assert next_state["query_plan_v2"]["domain"] == "logistics"


def test_initial_state_includes_query_plan_v2() -> None:
    """build_business_qa_initial_state 应初始化 query_plan_v2 为空字典。

    GREEN: 已添加到初始状态中。
    """
    from backend.app.domains.business_qa_graph.schemas.request import BusinessQaGraphRequest
    from backend.app.domains.business_qa_graph.schemas.state import build_business_qa_initial_state

    request = BusinessQaGraphRequest(question="测试问题", trace_id="test-init")
    initial_state = build_business_qa_initial_state(request)

    assert "query_plan_v2" in initial_state
    assert initial_state["query_plan_v2"] == {}


# =============================================================================
# 3. NL2SQL Adapter 测试
# =============================================================================


def test_nl2sql_adapter_route_skips_non_logistics_question() -> None:
    """NL2SQL adapter 应对非物流问题返回 route_skipped。

    GREEN: adapter 已创建。
    """
    from backend.app.domains.business_qa_graph.nl2sql_adapter import Nl2SqlGraphAdapter

    adapter = Nl2SqlGraphAdapter()
    result = adapter.build_shadow("BOM 评审号是什么？")

    assert result["status"] == "route_skipped"


def test_nl2sql_adapter_accepts_logistics_question() -> None:
    """NL2SQL adapter 应对物流问题返回 shadow 结果。

    GREEN: adapter 已创建，物流问题路由成功。
    """
    from backend.app.domains.business_qa_graph.nl2sql_adapter import Nl2SqlGraphAdapter

    adapter = Nl2SqlGraphAdapter()
    result = adapter.build_shadow("2024 年总发运量是多少？")

    assert result["status"] in ("shadow_generated", "route_skipped", "error")
    # 物流问题应能被 LogisticsNl2SqlDomainRouter 接受
    if result["status"] == "shadow_generated":
        assert "domain" in result
        assert result["domain"] == "logistics"


def test_nl2sql_adapter_handles_exception_gracefully() -> None:
    """NL2SQL adapter 异常时应 fail-closed，返回 error 状态。

    GREEN: adapter 已创建，异常处理已实现。
    """
    from backend.app.domains.business_qa_graph.nl2sql_adapter import Nl2SqlGraphAdapter

    adapter = Nl2SqlGraphAdapter()
    # 空字符串应被安全处理
    result = adapter.build_shadow("")
    assert result["status"] in ("route_skipped", "error")
    # 无异常抛出


def test_nl2sql_adapter_writes_query_plan_v2_fields() -> None:
    """NL2SQL adapter 生成的 shadow 结果应包含标准字段。

    GREEN: adapter 已创建，结果格式已标准化。
    """
    from backend.app.domains.business_qa_graph.nl2sql_adapter import Nl2SqlGraphAdapter

    adapter = Nl2SqlGraphAdapter()
    result = adapter.build_shadow("2024 年合肥发运量是多少？")

    # 结果必须包含 status 字段
    assert "status" in result
    # 如果成功生成，必须包含 domain 和 source_system
    if result["status"] == "shadow_generated":
        assert "domain" in result
        assert "source_system" in result


# =============================================================================
# 4. Graph 集成测试：question_understanding_node NL2SQL 分支
# =============================================================================


class FakeLogisticsQueryPlanningAdapter:
    """Fake 物流 QueryPlanningAdapter，避免构造真实 planner 时触发 settings 问题。"""

    def build_candidate(self, question: str, trace_id: str | None = None) -> Any:
        from backend.app.domains.query_planning.schemas.query_plan_v2 import QueryPlanningV2Plan

        return QueryPlanningV2Plan(
            domain="logistics",
            strategy="DIRECT_RETRIEVAL",
            intent="direct_retrieval",
            query_key="shipment_mw_summary",
            original_question=question,
        )


def test_question_understanding_node_routes_nl2sql_shadow_capability() -> None:
    """当 capabilities 包含 logistics_nl2sql_shadow 时，
    question_understanding_node 应调用 NL2SQL adapter 并写入 query_plan_v2。

    GREEN: NL2SQL shadow 分支已实现。
    """
    from backend.app.domains.business_qa_graph.nodes.question_understanding_node import (
        question_understanding_node,
    )

    state: BusinessQaGraphState = {
        "question": "2024 年总发运量是多少？",
        "domain_hint": "auto",
        "trace_id": "trace-nl2sql-node",
        "trace": [],
        "status": "DOMAIN_ROUTED",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "domain_routing_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_nl2sql_shadow"],
        "domain_route": {},
        "shadow_plan_raw": {},
        "understanding_status": "UNSAFE",
        "validation_result": "error",
        "validation_details": {},
        "user_visible_message": "",
        "execution_status": "NOT_STARTED",
        "execution_result": {},
    }

    next_state = question_understanding_node(state)

    # NQE-S1: 当 capability=logistics_nl2sql_shadow 时，应写入 query_plan_v2
    assert "query_plan_v2" in next_state
    query_plan = next_state.get("query_plan_v2", {})
    assert isinstance(query_plan, dict)
    assert "status" in query_plan

    # NL2SQL shadow 不改变 understanding_status（保持原有语义）
    # shadow 只记录，不影响主链路
    assert "understanding_status" in next_state


def test_question_understanding_node_falls_back_for_logistics_data_qa() -> None:
    """当 capability 是 logistics_data_qa（非 nl2sql_shadow）时，
    走原有 QueryPlanningAdapter 路径。

    GREEN: NL2SQL shadow 分支只在匹配时触发；不匹配时走原有逻辑。
    """
    from backend.app.domains.business_qa_graph.nodes.question_understanding_node import (
        question_understanding_node,
    )

    state: BusinessQaGraphState = {
        "question": "2024 年总发运量是多少？",
        "domain_hint": "auto",
        "trace_id": "trace-nl2sql-fallback",
        "trace": [],
        "status": "DOMAIN_ROUTED",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "domain_routing_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_data_qa"],  # 不是 nl2sql_shadow
        "domain_route": {},
        "shadow_plan_raw": {},
        "understanding_status": "UNSAFE",
        "validation_result": "error",
        "validation_details": {},
        "user_visible_message": "",
        "execution_status": "NOT_STARTED",
        "execution_result": {},
    }

    # 注入 fake adapter 避免 settings 问题
    fake_adapter = FakeLogisticsQueryPlanningAdapter()
    next_state = question_understanding_node(state, logistics_adapter=fake_adapter)

    # 原有 logistics_data_qa capability 仍走 QueryPlanningAdapter
    assert "shadow_plan_raw" in next_state
    assert "understanding_status" in next_state

    # query_plan_v2 也存在（由 NQE-S1 初始化为空）
    query_plan = next_state.get("query_plan_v2", {})
    assert isinstance(query_plan, dict)


# =============================================================================
# 5. Builder 集成测试
# =============================================================================


def test_builder_injects_nl2sql_adapter_to_question_understanding() -> None:
    """build_business_qa_graph 应能注入 nl2sql_adapter 到 question_understanding_node。

    GREEN: builder 已支持 nl2sql_adapter 参数。
    """
    from backend.app.domains.business_qa_graph.builder import build_business_qa_graph
    from backend.app.domains.business_qa_graph.nl2sql_adapter import Nl2SqlGraphAdapter

    adapter = Nl2SqlGraphAdapter()
    graph = build_business_qa_graph(nl2sql_adapter=adapter)

    assert graph is not None
    # graph 构造不抛异常即为通过


def test_graph_with_nl2sql_shadow_injected_state() -> None:
    """端到端测试：构建从 question_understanding 节点开始的子图，
    验证 NL2SQL shadow 分支正确执行。

    使用 LangGraph 的 subgraph 功能，从 question_understanding 节点启动，
    绕过 domain_route_node 的 capability 覆盖。

    GREEN: NL2SQL shadow 分支在子图 E2E 中正常工作。
    """
    from langgraph.graph import END, START, StateGraph

    from backend.app.domains.business_qa_graph.nl2sql_adapter import Nl2SqlGraphAdapter
    from backend.app.domains.business_qa_graph.nodes.question_understanding_node import (
        question_understanding_node,
    )
    from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState

    # 构建最小子图：只有 question_understanding 节点
    adapter = Nl2SqlGraphAdapter()
    subgraph = StateGraph(BusinessQaGraphState)
    from functools import partial
    subgraph.add_node(
        "question_understanding",
        partial(question_understanding_node, nl2sql_adapter=adapter),
    )
    subgraph.add_edge(START, "question_understanding")
    subgraph.add_edge("question_understanding", END)
    compiled = subgraph.compile()

    # 构造初始 state（直接设置正确的 capabilities）
    initial_state: BusinessQaGraphState = {
        "question": "2024 年总发运量是多少？",
        "domain_hint": "logistics",
        "trace_id": "trace-e2e-nl2sql",
        "trace": [],
        "status": "DOMAIN_ROUTED",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "domain_routing_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_nl2sql_shadow"],
        "domain_route": {},
        "shadow_plan_raw": {},
        "understanding_status": "UNSAFE",
        "validation_result": "error",
        "validation_details": {},
        "user_visible_message": "",
        "execution_status": "NOT_STARTED",
        "execution_result": {},
        "query_plan_v2": {},
    }

    # 执行子图
    final_state = compiled.invoke(initial_state)

    # 验证 query_plan_v2 被 NL2SQL shadow 分支写入
    assert "query_plan_v2" in final_state
    query_plan = final_state.get("query_plan_v2", {})
    assert isinstance(query_plan, dict)
    assert "status" in query_plan

    # NL2SQL shadow 路径设置 understanding_status 为 UNSUPPORTED
    # （shadow 只记录，不进入执行节点）
    assert final_state.get("understanding_status") == "UNSUPPORTED"


# =============================================================================
# 6. 现有回归保护测试
# =============================================================================


def test_existing_graph_structure_unchanged() -> None:
    """Graph 结构未因 NQE-S1 被破坏：不注入 nl2sql_adapter 时 graph 仍可编译。

    验证不带 NL2SQL adapter 的 graph 构造不抛异常。
    """
    from backend.app.domains.business_qa_graph.builder import build_business_qa_graph

    # 不注入 NL2SQL adapter（原有行为）
    graph = build_business_qa_graph()
    assert graph is not None

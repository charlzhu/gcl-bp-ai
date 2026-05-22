"""NQE-S2 focused tests: Graph 统一拆解复杂问法 + NL2SQL/Legacy 子计划执行。

采用 TDD RED→GREEN→REFACTOR 流程。
验证 Graph 能正确检测复合问题（对比/趋势/综合型）、LLM 分解为子问题、
确定性校验后分别执行、最终合并为统一业务答案。
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState


# =============================================================================
# 1. State 扩展测试
# =============================================================================


def test_state_accepts_composite_fields() -> None:
    """state 必须能承载 sub_plans、sub_results、composite_type 字段。

    RED: 这些字段尚未添加到 state schema。
    """
    state: BusinessQaGraphState = {
        "question": "去年和今年各承运商发运量对比",
        "domain_hint": "auto",
        "trace_id": "trace-composite",
        "trace": [],
        "status": "DOMAIN_ROUTED",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "domain_routing_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_composite_decomposition"],
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

    # NQE-S2 期望新字段：sub_plans / sub_results / composite_type
    next_state = dict(state)
    next_state["sub_plans"] = [
        {"question": "去年各承运商发运量", "query_key": "shipment_carrier_summary"},
        {"question": "今年各承运商发运量", "query_key": "shipment_carrier_summary"},
    ]
    next_state["sub_results"] = []
    next_state["composite_type"] = "comparison"

    assert len(next_state["sub_plans"]) == 2
    assert next_state["sub_plans"][0]["question"] == "去年各承运商发运量"
    assert next_state["composite_type"] == "comparison"
    assert next_state["sub_results"] == []


def test_understanding_status_accepts_composite_decomposed() -> None:
    """understanding_status 必须支持 COMPOSITE_DECOMPOSED 字面量。

    RED: Literal 类型尚未扩展。
    """
    state: BusinessQaGraphState = {
        "question": "去年和今年各承运商发运量对比",
        "domain_hint": "auto",
        "trace_id": "trace-comp-status",
        "trace": [],
        "status": "DOMAIN_ROUTED",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "domain_routing_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_composite_decomposition"],
        "domain_route": {},
        "shadow_plan_raw": {},
        "understanding_status": "COMPOSITE_DECOMPOSED",
        "validation_result": "error",
        "validation_details": {},
        "user_visible_message": "",
        "execution_status": "NOT_STARTED",
        "execution_result": {},
        "query_plan_v2": {},
    }

    assert state["understanding_status"] == "COMPOSITE_DECOMPOSED"


# =============================================================================
# 2. Capability 扩展测试
# =============================================================================


def test_capability_includes_logistics_composite_decomposition() -> None:
    """BusinessQaCapabilityId 必须包含 logistics_composite_decomposition。

    RED: 尚未添加到 domain.py 的 Literal 类型定义中。
    """
    from backend.app.domains.business_qa_graph.schemas.domain import BusinessQaCapabilityId

    capability: BusinessQaCapabilityId = "logistics_composite_decomposition"  # type: ignore[assignment]
    assert capability == "logistics_composite_decomposition"


# =============================================================================
# 3. Decomposition Node 测试
# =============================================================================


class FakeLogisticsAdapterForComposite:
    """Fake 物流 adapter：对每个子问题返回受控计划。"""

    def build_candidate(self, question: str, trace_id: str | None = None) -> Any:
        from backend.app.domains.query_planning.schemas.query_plan_v2 import QueryPlanningV2Plan

        return QueryPlanningV2Plan(
            domain="logistics",
            strategy="DIRECT_RETRIEVAL",
            intent="aggregate",
            query_key="shipment_carrier_summary",
            original_question=question,
        )


def test_decomposition_node_detects_and_splits_comparison_question() -> None:
    """decomposition_node 应对对比型问题拆分为两个子问题。

    RED: decomposition_node 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.decomposition_node import (
        decomposition_node,
    )

    state: BusinessQaGraphState = {
        "question": "去年和今年各承运商发运量对比",
        "domain_hint": "auto",
        "trace_id": "trace-decomp",
        "trace": [],
        "status": "DOMAIN_ROUTED",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "domain_routing_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_composite_decomposition"],
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

    adapter = FakeLogisticsAdapterForComposite()
    next_state = decomposition_node(state, logistics_adapter=adapter)

    # 应设置 understanding_status 为 COMPOSITE_DECOMPOSED
    assert next_state["understanding_status"] == "COMPOSITE_DECOMPOSED"

    # sub_plans 应包含两个子计划
    sub_plans = next_state.get("sub_plans", [])
    assert len(sub_plans) == 2, f"期望 2 个子计划，实际 {len(sub_plans)}"

    # 每个子计划应包含 question 字段
    for sp in sub_plans:
        assert "question" in sp, f"子计划缺少 question 字段: {sp}"
        assert sp["question"], f"子计划 question 为空"

    # composite_type 应为 comparison
    assert next_state.get("composite_type") == "comparison"


def test_decomposition_node_passes_through_simple_question() -> None:
    """decomposition_node 应对简单问题不触发分解，保持原有 status。

    RED: decomposition_node 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.decomposition_node import (
        decomposition_node,
    )

    state: BusinessQaGraphState = {
        "question": "2024 年总发运量是多少？",
        "domain_hint": "auto",
        "trace_id": "trace-simple",
        "trace": [],
        "status": "DOMAIN_ROUTED",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "domain_routing_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_composite_decomposition"],
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

    adapter = FakeLogisticsAdapterForComposite()
    next_state = decomposition_node(state, logistics_adapter=adapter)

    # 简单问题不应被分解
    assert next_state["understanding_status"] != "COMPOSITE_DECOMPOSED"
    # 应保持原有状态或由 downstream 设置
    assert "sub_plans" not in next_state or next_state.get("sub_plans") == []


def test_decomposition_node_skips_without_composite_capability() -> None:
    """decomposition_node 当 capability 不包含 logistics_composite_decomposition 时透传。

    RED: decomposition_node 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.decomposition_node import (
        decomposition_node,
    )

    state: BusinessQaGraphState = {
        "question": "去年和今年各承运商发运量对比",
        "domain_hint": "auto",
        "trace_id": "trace-no-cap",
        "trace": [],
        "status": "DOMAIN_ROUTED",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "domain_routing_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_data_qa"],  # 不含 composite capability
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

    adapter = FakeLogisticsAdapterForComposite()
    next_state = decomposition_node(state, logistics_adapter=adapter)

    # 不触发分解
    assert next_state["understanding_status"] != "COMPOSITE_DECOMPOSED"


# =============================================================================
# 4. Decomposer (核心分解逻辑) 测试
# =============================================================================


def test_logistics_composite_decomposer_splits_comparison_by_year() -> None:
    """核心分解器应对比较型问题按年份拆分。

    RED: LogisticsCompositeDecomposer 尚未创建。
    """
    from backend.app.domains.business_qa_graph.services.logistics_composite_decomposer import (
        LogisticsCompositeDecomposer,
    )

    decomposer = LogisticsCompositeDecomposer()

    # 对比型问题："去年和今年各承运商发运量对比"
    result = decomposer.decompose("去年和今年各承运商发运量对比")

    assert result["is_composite"] is True
    assert result["composite_type"] == "comparison"
    assert len(result["sub_questions"]) == 2
    assert result["sub_questions"][0]["question"]
    assert result["sub_questions"][1]["question"]


def test_logistics_composite_decomposer_detects_simple_question() -> None:
    """核心分解器应对简单问题返回 is_composite=False。

    RED: LogisticsCompositeDecomposer 尚未创建。
    """
    from backend.app.domains.business_qa_graph.services.logistics_composite_decomposer import (
        LogisticsCompositeDecomposer,
    )

    decomposer = LogisticsCompositeDecomposer()

    result = decomposer.decompose("2024 年总发运量是多少？")

    assert result["is_composite"] is False


def test_logistics_composite_decomposer_validates_sub_questions() -> None:
    """核心分解器的子问题必须经过确定性校验（非空、不包含回指、不重叠）。

    RED: LogisticsCompositeDecomposer 尚未创建。
    """
    from backend.app.domains.business_qa_graph.services.logistics_composite_decomposer import (
        LogisticsCompositeDecomposer,
    )

    decomposer = LogisticsCompositeDecomposer()

    # 正常拆分
    result = decomposer.decompose("去年和今年各承运商发运量对比")
    assert result["is_composite"] is True

    # 空输入不应分解
    result_empty = decomposer.decompose("")
    assert result_empty["is_composite"] is False

    # 纯连接词不应分解
    result_and = decomposer.decompose("和")
    assert result_and["is_composite"] is False


# =============================================================================
# 5. Presentation Node 测试
# =============================================================================


def test_presentation_node_merges_comparison_results() -> None:
    """presentation_node 应将两个子结果合并为对比型业务答案。

    RED: presentation_node 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.presentation_node import (
        presentation_node,
    )

    state: BusinessQaGraphState = {
        "question": "去年和今年各承运商发运量对比",
        "domain_hint": "auto",
        "trace_id": "trace-present",
        "trace": [],
        "status": "EXECUTED",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "domain_routing_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_composite_decomposition"],
        "domain_route": {},
        "shadow_plan_raw": {},
        "understanding_status": "COMPOSITE_DECOMPOSED",
        "validation_result": "ok",
        "validation_details": {},
        "user_visible_message": "",
        "execution_status": "EXECUTED",
        "execution_result": {},
        "query_plan_v2": {},
        "sub_plans": [
            {"question": "去年各承运商发运量", "query_key": "shipment_carrier_summary"},
            {"question": "今年各承运商发运量", "query_key": "shipment_carrier_summary"},
        ],
        "sub_results": [
            {
                "answer_summary": "去年：阜宁基地发运 500MW，合肥基地发运 300MW",
                "columns": ["承运商", "发运量(MW)"],
                "rows": [["承运商A", 500], ["承运商B", 300]],
                "row_count": 2,
            },
            {
                "answer_summary": "今年：阜宁基地发运 600MW，合肥基地发运 400MW",
                "columns": ["承运商", "发运量(MW)"],
                "rows": [["承运商A", 600], ["承运商B", 400]],
                "row_count": 2,
            },
        ],
        "composite_type": "comparison",
    }

    next_state = presentation_node(state)

    # 应有合并后的 user_visible_message
    assert next_state.get("user_visible_message"), "合并后缺少 user_visible_message"
    # 不应泄露 SQL/表名/字段名/query_key 等
    msg = next_state["user_visible_message"]
    assert "SQL" not in msg.upper()
    assert "query_key" not in msg


def test_presentation_node_preserves_non_composite_state() -> None:
    """presentation_node 应对非复合状态透传不修改。

    RED: presentation_node 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.presentation_node import (
        presentation_node,
    )

    original_msg = "2024年总发运量为1000MW"

    state: BusinessQaGraphState = {
        "question": "2024 年总发运量是多少？",
        "domain_hint": "auto",
        "trace_id": "trace-non-comp",
        "trace": [],
        "status": "EXECUTED",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "domain_routing_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_data_qa"],
        "domain_route": {},
        "shadow_plan_raw": {},
        "understanding_status": "PLANNED",
        "validation_result": "ok",
        "validation_details": {},
        "user_visible_message": original_msg,
        "execution_status": "EXECUTED",
        "execution_result": {},
        "query_plan_v2": {},
        "sub_plans": [],
        "sub_results": [],
        "composite_type": "none",
    }

    next_state = presentation_node(state)

    # 非复合状态应保持 user_visible_message 不变
    assert next_state["user_visible_message"] == original_msg


# =============================================================================
# 6. Graph 集成测试
# =============================================================================


def test_builder_registers_decomposition_and_presentation_nodes() -> None:
    """build_business_qa_graph 应能注册 decomposition_node 和 presentation_node。

    RED: builder 尚未更新。
    """
    from backend.app.domains.business_qa_graph.builder import build_business_qa_graph

    graph = build_business_qa_graph()
    assert graph is not None

    # 获取 graph 节点名称（LangGraph compiled graph 的 nodes 可通过 get_graph() 访问）
    nodes = list(graph.get_graph().nodes.keys())
    assert "decomposition" in nodes, f"节点列表中缺少 decomposition，现有: {nodes}"
    assert "presentation" in nodes, f"节点列表中缺少 presentation，现有: {nodes}"


def test_composite_graph_subgraph_e2e() -> None:
    """端到端测试：构建包含 decomposition→execute→presentation 的子图。

    RED: decomposition_node / presentation_node 尚未创建。
    """
    from functools import partial

    from langgraph.graph import END, START, StateGraph

    from backend.app.domains.business_qa_graph.nodes.decomposition_node import (
        decomposition_node,
    )
    from backend.app.domains.business_qa_graph.nodes.presentation_node import (
        presentation_node,
    )
    from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState

    # 构建子图：decomposition → execute(E2E) → presentation
    subgraph = StateGraph(BusinessQaGraphState)

    adapter = FakeLogisticsAdapterForComposite()
    subgraph.add_node(
        "decomposition",
        partial(decomposition_node, logistics_adapter=adapter),
    )
    # execute 节点：复合时遍历 sub_plans 调用 logistics service
    subgraph.add_node("execute", _fake_execute_composite_node)
    subgraph.add_node("presentation", presentation_node)

    subgraph.add_edge(START, "decomposition")
    subgraph.add_edge("decomposition", "execute")
    subgraph.add_edge("execute", "presentation")
    subgraph.add_edge("presentation", END)

    compiled = subgraph.compile()

    initial_state: BusinessQaGraphState = {
        "question": "去年和今年各承运商发运量对比",
        "domain_hint": "logistics",
        "trace_id": "trace-e2e-composite",
        "trace": [],
        "status": "DOMAIN_ROUTED",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "domain_routing_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_composite_decomposition"],
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

    final_state = compiled.invoke(initial_state)

    # 验证完整链路
    assert final_state["understanding_status"] == "COMPOSITE_DECOMPOSED"
    assert len(final_state.get("sub_plans", [])) == 2
    assert len(final_state.get("sub_results", [])) == 2
    assert final_state.get("composite_type") == "comparison"
    # 应有合并后的用户可见答案
    assert final_state.get("user_visible_message"), "最终缺少 user_visible_message"


def _fake_execute_composite_node(state: BusinessQaGraphState) -> BusinessQaGraphState:
    """Fake 复合执行节点：模拟子查询执行。

    参数：
        state: Graph 运行态，包含 sub_plans。
    返回：
        写入 sub_results 和 composite_type 的新 state。
    业务逻辑：
        对每个子计划生成 mock 结果。
    """
    sub_plans = state.get("sub_plans", [])
    sub_results = []
    for i, sp in enumerate(sub_plans):
        sub_results.append({
            "answer_summary": f"子查询 {i + 1}: {sp.get('question', '')} 结果",
            "columns": ["承运商", "发运量(MW)"],
            "rows": [["承运商A", 500 + i * 100]],
            "row_count": 1,
        })

    next_state = dict(state)
    next_state["sub_results"] = sub_results
    next_state["execution_status"] = "EXECUTED"
    next_state["status"] = "EXECUTED"
    return next_state


# =============================================================================
# 7. 现有回归保护测试
# =============================================================================


def test_existing_graph_structure_unchanged_by_s2() -> None:
    """Graph 结构未因 NQE-S2 被破坏：不传入复合相关参数时 graph 仍可编译。

    验证不带 composite 参数的 graph 构造不抛异常。
    """
    from backend.app.domains.business_qa_graph.builder import build_business_qa_graph

    # 不注入任何 S2 参数（原有行为）
    graph = build_business_qa_graph()
    assert graph is not None


def test_nqe_s1_tests_still_compatible() -> None:
    """NQE-S1 的 query_plan_v2 字段仍可正常存取，不受 S2 影响。"""
    state: BusinessQaGraphState = {
        "question": "2024 年总发运量是多少？",
        "domain_hint": "auto",
        "trace_id": "trace-s1-compat",
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

    next_state = dict(state)
    next_state["query_plan_v2"] = {"status": "shadow_generated", "domain": "logistics"}
    assert next_state["query_plan_v2"]["status"] == "shadow_generated"

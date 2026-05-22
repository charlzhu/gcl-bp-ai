from __future__ import annotations

from typing import Any

from backend.app.api.router import api_router
from backend.app.core.config import Settings
from backend.app.domains.business_qa_graph.builder import build_business_qa_graph
from backend.app.domains.business_qa_graph.domain_registry import BusinessQaDomainRegistry
from backend.app.domains.business_qa_graph.nodes.domain_route_node import domain_route_node
from backend.app.domains.business_qa_graph.nodes.receive_node import receive_node
from backend.app.domains.business_qa_graph.runner import BusinessQaGraphRunner
from backend.app.domains.business_qa_graph.schemas.request import BusinessQaGraphRequest


class ExplodingGraph:
    """用于验证默认关闭时绝不调用 graph.invoke 的测试桩。"""

    def __init__(self) -> None:
        self.invoked = False

    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        """如果被调用则立即失败，证明 disabled 边界被破坏。"""
        self.invoked = True
        raise AssertionError("disabled runner must not invoke graph")


def test_langgraph_config_is_disabled_by_default_and_old_routes_stay_registered() -> None:
    """LangGraph 统一编排默认关闭，不应影响既有物流和计划 BOM 路由。"""
    settings = Settings(_env_file=None)
    route_paths = {route.path for route in api_router.routes}

    assert settings.business_qa_langgraph_enabled is False
    assert any(path.startswith("/logistics/") for path in route_paths)
    assert any(path.startswith("/plan-bom/") for path in route_paths)
    assert not any(path.startswith("/business-qa-graph") for path in route_paths)


def test_runner_disabled_mode_does_not_invoke_graph() -> None:
    """Runner 默认关闭时必须短路返回，不能提前执行任何 graph 节点。"""
    graph = ExplodingGraph()
    runner = BusinessQaGraphRunner(graph=graph, enabled=False)

    response = runner.run(BusinessQaGraphRequest(question="2025 年合肥物流发运量是多少？"))

    assert response.status == "DISABLED"
    assert response.execution_mode == "disabled"
    assert graph.invoked is False


def test_receive_node_records_question_domain_hint_and_trace() -> None:
    """receive_node 只接收请求并写入 trace，不触发业务查数或 NL2SQL 执行。"""
    next_state = receive_node(
        {
            "question": "2025 年合肥物流发运量是多少？",
            "domain_hint": "logistics",
            "trace_id": "trace-lqg-1",
            "trace": [],
        }
    )

    assert next_state["status"] == "RECEIVED"
    assert next_state["question"] == "2025 年合肥物流发运量是多少？"
    assert next_state["domain_hint"] == "logistics"
    assert len(next_state["trace"]) == 1
    event = next_state["trace"][0]
    assert event["node"] == "receive"
    assert event["event_type"] == "question_received"
    assert event["payload"]["question"] == "2025 年合肥物流发运量是多少？"
    assert event["payload"]["domain_hint"] == "logistics"
    assert event["payload"]["trace_id"] == "trace-lqg-1"


def test_domain_registry_declares_only_logistics_and_plan_bom_business_domains() -> None:
    """registry 只声明 LQG-2 范围内的物流和计划 BOM 域，功率必须归属计划 BOM。"""
    registry = BusinessQaDomainRegistry.default()
    domains = {domain.domain: domain for domain in registry.list_domains()}

    assert set(domains) == {"logistics", "plan_bom"}
    assert domains["logistics"].capabilities == ("logistics_data_qa",)
    assert set(domains["plan_bom"].capabilities) == {
        "plan_bom_qa",
        "plan_power_prediction",
        "plan_power_supplier_recommendation",
        "plan_power_factor_effect_compare",
    }
    assert "power" not in domains
    assert registry.get_capability("plan_power_prediction").domain == "plan_bom"


def test_domain_registry_routes_logistics_question_to_logistics_data_qa() -> None:
    """物流问题应命中 logistics 域和 logistics_data_qa capability。"""
    route = BusinessQaDomainRegistry.default().route("2025 年哪个承运商发运量最高？", domain_hint="auto")

    assert route.status == "ROUTED"
    assert route.domain == "logistics"
    assert route.capabilities == ("logistics_data_qa",)
    assert route.confidence >= 0.7


def test_domain_registry_routes_bom_question_to_plan_bom_qa() -> None:
    """普通 BOM 问题应命中 plan_bom 域和 plan_bom_qa capability。"""
    route = BusinessQaDomainRegistry.default().route("这个 BOM 用了什么玻璃和接线盒？")

    assert route.status == "ROUTED"
    assert route.domain == "plan_bom"
    assert route.capabilities == ("plan_bom_qa",)
    assert route.confidence >= 0.7


def test_domain_registry_routes_power_prediction_to_plan_bom_power_capability() -> None:
    """功率预测问题仍属于 plan_bom 域，不能新建独立 power 域。"""
    route = BusinessQaDomainRegistry.default().route("订单00104 预测 615 功率档位分布")

    assert route.status == "ROUTED"
    assert route.domain == "plan_bom"
    assert route.capabilities == ("plan_power_prediction",)
    assert route.capability_domain == "plan_bom"


def test_domain_registry_routes_numeric_watt_power_question_to_plan_bom() -> None:
    """只有明确数字瓦数语境的 W 才能作为功率单位命中，避免单字母 w 泛化。"""
    route = BusinessQaDomainRegistry.default().route("订单00104 预测 615W 档位分布")

    assert route.status == "ROUTED"
    assert route.domain == "plan_bom"
    assert route.capabilities == ("plan_power_prediction",)
    assert route.capability_domain == "plan_bom"


def test_domain_registry_does_not_treat_plain_english_w_as_power() -> None:
    """普通英文问题包含字母 w 时必须澄清，不能被单字符功率单位误路由。"""
    route = BusinessQaDomainRegistry.default().route("what is the weather tomorrow?")

    assert route.status == "CLARIFY"
    assert route.domain == "unknown"
    assert route.capabilities == ()


def test_domain_registry_does_not_treat_wms_as_power_unit() -> None:
    """WMS 等非功率缩写不能因为包含 W 就落入计划 BOM 功率能力。"""
    route = BusinessQaDomainRegistry.default().route("WMS 库存同步状态怎么样？")

    assert route.status == "CLARIFY"
    assert route.domain == "unknown"
    assert route.capabilities == ()


def test_domain_registry_routes_power_supplier_recommendation_to_plan_bom() -> None:
    """供应商功率推荐问题应命中 plan_bom 域和供应商推荐 capability。"""
    route = BusinessQaDomainRegistry.default().route("目标功率 615W，推荐哪些供应商和电池片比例？")

    assert route.status == "ROUTED"
    assert route.domain == "plan_bom"
    assert route.capabilities == ("plan_power_supplier_recommendation",)
    assert route.capability_domain == "plan_bom"


def test_domain_registry_routes_power_factor_effect_compare_to_plan_bom() -> None:
    """功率配置影响值对比问题应命中 plan_bom 域和配置影响值 capability。"""
    route = BusinessQaDomainRegistry.default().route("NT12R-66GDF 镀釉和非镀釉的功率影响值差异是多少？")

    assert route.status == "ROUTED"
    assert route.domain == "plan_bom"
    assert route.capabilities == ("plan_power_factor_effect_compare",)
    assert route.capability_domain == "plan_bom"


def test_domain_registry_unknown_question_returns_clarify_candidates_not_legacy_domain() -> None:
    """无法识别的问题必须进入澄清候选，不能误落旧业务域或默认物流域。"""
    route = BusinessQaDomainRegistry.default().route("帮我安排明天上午的会议")

    assert route.status == "CLARIFY"
    assert route.domain == "unknown"
    assert route.capabilities == ()
    assert [candidate.domain for candidate in route.clarify_candidates] == ["logistics", "plan_bom"]
    assert "business_analysis" not in {candidate.domain for candidate in route.clarify_candidates}


def test_domain_route_node_writes_route_result_and_trace() -> None:
    """domain_route_node 应写入领域路由结果和 trace，但不执行真实业务查数。"""
    state = receive_node(
        {
            "question": "2024 年总运费是多少？",
            "domain_hint": "auto",
            "trace_id": "trace-domain-route",
            "trace": [],
        }
    )

    routed_state = domain_route_node(state)

    assert routed_state["status"] == "DOMAIN_ROUTED"
    assert routed_state["domain"] == "logistics"
    assert routed_state["capabilities"] == ["logistics_data_qa"]
    assert routed_state["domain_route"]["domain"] == "logistics"
    assert [event["node"] for event in routed_state["trace"]] == ["receive", "domain_route"]
    assert routed_state["trace"][-1]["event_type"] == "domain_routed"


def test_minimal_state_graph_runs_receive_then_domain_route_only() -> None:
    """LQG-3 Graph 应经过 receive→domain_route→question_understanding→plan_build，不进入查数节点。"""
    graph = build_business_qa_graph()

    final_state = graph.invoke(
        {
            "question": "2025 年总发运量是多少？",
            "domain_hint": "logistics",
            "trace_id": "trace-lqg-graph",
            "trace": [],
        }
    )

    assert final_state["graph_version"] == "business_qa_graph.v0"
    assert final_state["domain"] == "logistics"
    assert final_state["capabilities"] == ["logistics_data_qa"]
    node_names = [event["node"] for event in final_state["trace"]]
    assert node_names == ["receive", "domain_route", "question_understanding", "plan_validate", "plan_build", "execute"]
    # LQG-3: shadow_plan_raw 应已写入 state
    assert "shadow_plan_raw" in final_state
    assert final_state["understanding_status"] in ("PLANNED", "CLARIFY_NEEDED", "UNSUPPORTED", "UNSAFE")


def test_runner_returns_domain_routed_response_without_business_execution() -> None:
    """Runner 返回 LQG-3 扩展响应，仍不执行查数、不替代受控 NL2SQL。"""
    runner = BusinessQaGraphRunner(enabled=True)
    response = runner.run(
        BusinessQaGraphRequest(
            question="2024 年销量是多少？",
            domain_hint="auto",
            trace_id="trace-lqg-runner",
        )
    )

    # LQG-3: unknown 问题经节点处理后最终为 UNSUPPORTED
    assert response.status == "UNSUPPORTED"
    assert response.question == "2024 年销量是多少？"
    assert response.domain_route is not None
    assert response.domain_route.domain == "unknown"
    assert [candidate.domain for candidate in response.domain_route.clarify_candidates] == ["logistics", "plan_bom"]
    # LQG-4: unknown 问题经 plan_validate 后进入 unsupported 终端节点
    node_names = [event.node for event in response.trace]
    assert "plan_validate" in node_names
    assert "unsupported" in node_names
    assert "NL2SQL" in response.boundary_notes[0]

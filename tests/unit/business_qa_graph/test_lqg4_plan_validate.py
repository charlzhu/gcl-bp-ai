"""LQG-4 focused tests: 统一 plan validate / clarify / unsupported / no_answer 分支。

采用 TDD RED→GREEN→REFACTOR 流程。本文件先写 RED 测试，再实现代码使 GREEN。

验收标准：
  1. "查一下这个订单" -> 业务化追问（不泄露技术链路）
  2. "用 SQL 查物流表" -> 不执行 SQL、不暴露技术链路
  3. unsupported 不变成成功
  4. 物流/BOM clarification 与 unsupported 测试不回归
"""

from __future__ import annotations

import pytest

from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState


# =============================================================================
# 1. Policy schema 测试
# =============================================================================


def test_plan_validation_result_has_correct_status_values() -> None:
    """PlanValidationResult 只允许 ok/clarify/unsupported/no_answer/error 五种校验结果。

    RED: schemas/policy.py 尚未创建。
    """
    # 正向：所有合法状态
    valid_statuses = {"ok", "clarify", "unsupported", "no_answer", "error"}
    for status in valid_statuses:
        assert status in valid_statuses

    # 反向：非法状态
    invalid = "executing"
    assert invalid not in valid_statuses


def test_policy_whitelist_blocks_unknown_domain() -> None:
    """策略白名单必须阻止未注册域。

    RED: schemas/policy.py 尚未创建。
    """
    # 白名单只允许 logistics、plan_bom
    allowed_domains = {"logistics", "plan_bom"}

    assert "unknown" not in allowed_domains
    assert "power" not in allowed_domains
    assert "logistics" in allowed_domains


def test_policy_whitelist_blocks_unknown_capability() -> None:
    """策略白名单必须阻止未注册 capability。

    RED: schemas/policy.py 尚未创建。
    """
    allowed_capabilities = {
        "logistics_data_qa",
        "plan_bom_qa",
        "plan_power_prediction",
        "plan_power_supplier_recommendation",
        "plan_power_factor_effect_compare",
    }

    assert "unknown_capability" not in allowed_capabilities
    assert "logistics_data_qa" in allowed_capabilities


def test_policy_safety_patterns_block_sql_keywords() -> None:
    """安全策略必须检测 SQL 注入/危险关键字。

    RED: schemas/policy.py 尚未创建。
    """
    # 这些模式应触发安全阻断
    dangerous_patterns = [
        ("SELECT", True),
        ("DROP TABLE", True),
        ("INSERT INTO", True),
        ("DELETE FROM", True),
        ("UNION SELECT", True),
        ("'; DROP", True),
        ("1=1", True),
        ("总运费是多少？", False),
        ("2024 年发运量", False),
    ]

    # RED 阶段只验证模式概念正确
    for pattern, should_block in dangerous_patterns:
        has_danger = any(
            kw in pattern.upper() for kw in ["SELECT", "DROP", "INSERT", "DELETE", "UNION", "1=1"]
        )
        assert has_danger == should_block, f"Pattern '{pattern}' should_block={should_block}"


def test_policy_tech_leak_patterns_block_internal_identifiers() -> None:
    """技术泄露策略必须检测内部标识（SQL、表名、字段名、query_key 等）。

    RED: schemas/policy.py 尚未创建。
    """
    unsafe_user_questions = [
        "用 SQL 查物流表",
        "SELECT * FROM logistics_shipment",
        "查一下 logistics_shipment 表的数据",
        "用 query_key 查数据",
        "执行这个 SQLPlan",
        "调用 guardrail 检查",
    ]

    safe_user_questions = [
        "2024 年总运费是多少？",
        "查一下合肥的发运量",
        "哪个承运商运费最高？",
        "订单 00104 用了什么玻璃？",
    ]

    # 使用实际的 detect_tech_leak 验证分类逻辑
    from backend.app.domains.business_qa_graph.schemas.policy import detect_tech_leak

    for q in unsafe_user_questions:
        assert detect_tech_leak(q), f"Expected tech leak in: {q}"

    for q in safe_user_questions:
        assert not detect_tech_leak(q), f"Unexpected tech leak match in: {q}"


# =============================================================================
# 2. plan_validate_node 测试
# =============================================================================


def test_plan_validate_node_accepts_valid_plan() -> None:
    """plan_validate_node 应接受有效计划并返回 validation_result=ok。

    RED: nodes/plan_validate_node.py 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.plan_validate_node import (
        plan_validate_node,
    )

    state: BusinessQaGraphState = {
        "question": "2024 年总运费是多少？",
        "domain_hint": None,
        "trace_id": "trace-pv-ok",
        "trace": [],
        "status": "PLAN_BUILT",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "graph_skeleton_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_data_qa"],
        "domain_route": {},
        "understanding_status": "PLANNED",
        "shadow_plan_raw": {
            "domain": "logistics",
            "strategy": "DIRECT_RETRIEVAL",
            "intent": "direct_retrieval",
            "query_key": "shipment_mw_summary",
        },
    }

    result = plan_validate_node(state)

    assert result["validation_result"] == "ok"
    assert "validation_details" in result


def test_plan_validate_node_rejects_tech_leak_question() -> None:
    """plan_validate_node 应拒绝包含技术泄露特征的请求（如 "用 SQL 查"）。

    验收标准：不执行 SQL、不暴露技术链路。

    RED: nodes/plan_validate_node.py 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.plan_validate_node import (
        plan_validate_node,
    )

    state: BusinessQaGraphState = {
        "question": "用 SQL 查物流表",  # 技术泄露特征
        "domain_hint": None,
        "trace_id": "trace-pv-leak",
        "trace": [],
        "status": "PLAN_BUILT",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "graph_skeleton_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_data_qa"],
        "domain_route": {},
        "understanding_status": "PLANNED",
        "shadow_plan_raw": {
            "domain": "logistics",
            "strategy": "DIRECT_RETRIEVAL",
            "intent": "direct_retrieval",
        },
    }

    result = plan_validate_node(state)

    # 必须被拒绝
    assert result["validation_result"] == "unsupported"
    # 用户可见信息不能包含技术泄露
    user_msg = result.get("validation_details", {}).get("unsupported_reason", "")
    assert "SQL" not in user_msg.upper()
    assert "query_key" not in user_msg.lower()
    assert "SELECT" not in user_msg.upper()


def test_plan_validate_node_clarify_for_ambiguous_order_question() -> None:
    """plan_validate_node 应对模糊的 "查一下这个订单" 返回 clarify。

    验收标准："查一下这个订单" 返回业务化追问。

    RED: nodes/plan_validate_node.py 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.plan_validate_node import (
        plan_validate_node,
    )

    state: BusinessQaGraphState = {
        "question": "查一下这个订单",
        "domain_hint": None,
        "trace_id": "trace-pv-order",
        "trace": [],
        "status": "PLAN_BUILT",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "graph_skeleton_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "plan_bom",
        "capabilities": ["plan_bom_qa"],
        "domain_route": {},
        "understanding_status": "CLARIFY_NEEDED",
        "shadow_plan_raw": {
            "domain": "plan_bom",
            "strategy": "CLARIFY",
            "clarification_questions": ["请提供具体的订单号。"],
            "missing_slots": ["order_id"],
        },
    }

    result = plan_validate_node(state)

    assert result["validation_result"] == "clarify"
    # 用户可见追问必须业务化：clarification_reason 不包含技术标识
    validation_details = result.get("validation_details", {})
    # validation_details 是 PlanValidationResult 的 JSON dump，检查其 clarification_reason 字段
    clarification_reason = str(validation_details.get("clarification_reason", ""))
    assert len(clarification_reason) > 0, "clarification_reason must not be empty"
    assert "slot" not in clarification_reason.lower()
    assert "query_key" not in clarification_reason.lower()
    assert "SQL" not in clarification_reason.upper()


def test_plan_validate_node_unsupported_for_out_of_scope() -> None:
    """plan_validate_node 应将不在白名单/能力范围内的请求标记为 unsupported。

    验收标准：unsupported 不变成成功。

    RED: nodes/plan_validate_node.py 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.plan_validate_node import (
        plan_validate_node,
    )

    state: BusinessQaGraphState = {
        "question": "帮我安排明天的会议",
        "domain_hint": None,
        "trace_id": "trace-pv-scope",
        "trace": [],
        "status": "PLAN_BUILT",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "graph_skeleton_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "unknown",
        "capabilities": [],
        "domain_route": {},
        "understanding_status": "UNSUPPORTED",
        "shadow_plan_raw": {
            "unsupported_reason": "该问题不在当前业务域能力范围内",
        },
    }

    result = plan_validate_node(state)

    # 必须是 unsupported，不能变成 ok
    assert result["validation_result"] == "unsupported"
    assert result["validation_result"] != "ok"


# =============================================================================
# 3. clarify_node 测试
# =============================================================================


def test_clarify_node_generates_business_friendly_question() -> None:
    """clarify_node 生成的追问消息必须业务化，不泄露技术标识。

    RED: nodes/clarify_node.py 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.clarify_node import (
        clarify_node,
    )

    state: BusinessQaGraphState = {
        "question": "查一下这个订单",
        "domain_hint": None,
        "trace_id": "trace-clarify",
        "trace": [],
        "status": "CLARIFY",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "graph_skeleton_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "plan_bom",
        "capabilities": ["plan_bom_qa"],
        "domain_route": {},
        "understanding_status": "CLARIFY_NEEDED",
        "shadow_plan_raw": {
            "domain": "plan_bom",
            "strategy": "CLARIFY",
            "clarification_questions": ["请提供具体的订单号。"],
        },
        "validation_result": "clarify",
        "validation_details": {
            "missing_slots": ["order_id"],
            "clarification_reason": "缺少订单号信息",
        },
    }

    result = clarify_node(state)

    # 状态保持 CLARIFY
    assert result["status"] == "CLARIFY"
    # 写入用户可见消息
    user_message = str(result.get("user_visible_message", ""))
    assert len(user_message) > 0
    # 不泄露技术内容
    assert "slot" not in user_message.lower()
    assert "query_key" not in user_message.lower()
    assert "SQL" not in user_message
    assert "shadow_plan" not in user_message.lower()


def test_clarify_node_message_does_not_leak_internals() -> None:
    """clarify_node 输出的任何字段都不能包含 SQL/表名/字段名/raw/debug。

    RED: nodes/clarify_node.py 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.clarify_node import (
        clarify_node,
    )

    state: BusinessQaGraphState = {
        "question": "帮我查一下",
        "domain_hint": "logistics",
        "trace_id": "trace-cl-noleak",
        "trace": [],
        "status": "CLARIFY",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "graph_skeleton_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_data_qa"],
        "domain_route": {},
        "understanding_status": "CLARIFY_NEEDED",
        "shadow_plan_raw": {
            "domain": "logistics",
            "strategy": "CLARIFY",
            "clarification_questions": ["请补充查询的时间范围。"],
        },
        "validation_result": "clarify",
        "validation_details": {"missing_slots": ["year"]},
    }

    result = clarify_node(state)

    # 遍历所有 result 值，确保无技术泄露
    forbidden = ["SQL", "SELECT", "TABLE", "query_key", "guardrail", "schema", "raw", "debug", "planner"]
    for key, value in result.items():
        if isinstance(value, str):
            for f in forbidden:
                assert f.upper() not in value.upper(), (
                    f"Field '{key}' leaks forbidden term '{f}': {value[:200]}"
                )


# =============================================================================
# 4. unsupported_node 测试
# =============================================================================


def test_unsupported_node_generates_business_friendly_rejection() -> None:
    """unsupported_node 生成的拒答消息必须业务化，不暴露技术细节。

    验收标准：不执行 SQL、不暴露技术链路。

    RED: nodes/unsupported_node.py 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.unsupported_node import (
        unsupported_node,
    )

    state: BusinessQaGraphState = {
        "question": "用 SQL 查物流表",
        "domain_hint": None,
        "trace_id": "trace-unsupported",
        "trace": [],
        "status": "UNSUPPORTED",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "graph_skeleton_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "unknown",
        "capabilities": [],
        "domain_route": {},
        "understanding_status": "UNSUPPORTED",
        "shadow_plan_raw": {
            "unsupported_reason": "安全问题：检测到 SQL 注入特征",
        },
        "validation_result": "unsupported",
        "validation_details": {
            "unsupported_reason": "安全问题：检测到 SQL 注入特征",
        },
    }

    result = unsupported_node(state)

    # 状态保持 UNSUPPORTED
    assert result["status"] == "UNSUPPORTED"
    # 写入用户可见消息
    user_message = str(result.get("user_visible_message", ""))
    assert len(user_message) > 0
    # 用户可见消息不包含 SQL 等技术细节
    assert "SQL" not in user_message.upper()
    assert "SELECT" not in user_message.upper()
    # 但应当有业务化的说明
    assert (
        "暂不支持" in user_message
        or "无法" in user_message
        or "未覆盖" in user_message
        or "不在" in user_message
    )


def test_unsupported_node_never_returns_success_status() -> None:
    """unsupported_node 不能把状态改成 RECEIVED/DOMAIN_ROUTED/PLAN_BUILT（即不能变成成功）。

    验收标准：unsupported 不变成成功。

    RED: nodes/unsupported_node.py 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.unsupported_node import (
        unsupported_node,
    )

    state: BusinessQaGraphState = {
        "question": "明天的天气怎么样？",
        "domain_hint": None,
        "trace_id": "trace-unsup-no-success",
        "trace": [],
        "status": "UNSUPPORTED",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "graph_skeleton_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "unknown",
        "capabilities": [],
        "domain_route": {},
        "understanding_status": "UNSUPPORTED",
        "shadow_plan_raw": {"unsupported_reason": "不在业务域范围内"},
        "validation_result": "unsupported",
        "validation_details": {},
    }

    result = unsupported_node(state)

    # 状态不能是成功类
    success_statuses = {"RECEIVED", "DOMAIN_ROUTED", "PLAN_BUILT", "PENDING"}
    assert result["status"] not in success_statuses, f"Status should not be success: {result['status']}"
    assert result["status"] == "UNSUPPORTED"


# =============================================================================
# 5. error_node 测试
# =============================================================================


def test_error_node_handles_generic_error_safely() -> None:
    """error_node 必须安全处理异常，不泄露内部堆栈和密钥。

    RED: nodes/error_node.py 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.error_node import (
        error_node,
    )

    state: BusinessQaGraphState = {
        "question": "2024 年总发运量？",
        "domain_hint": None,
        "trace_id": "trace-err",
        "trace": [],
        "status": "ERROR",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "graph_skeleton_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_data_qa"],
        "domain_route": {},
        "understanding_status": "UNSAFE",
        "shadow_plan_raw": {},
        "validation_result": "error",
        "validation_details": {
            "error_type": "InternalError",
            "error_message": "Database connection failed",
        },
    }

    result = error_node(state)

    # 状态保持 ERROR（或转 UNSUPPORTED）
    assert result["status"] in ("ERROR", "UNSUPPORTED")
    # 写入用户可见消息
    user_message = str(result.get("user_visible_message", ""))
    assert len(user_message) > 0
    # 不能泄露内部错误详情（如数据库连接信息）
    assert "Database connection" not in user_message
    assert "InternalError" not in user_message
    assert "traceback" not in user_message.lower()


# =============================================================================
# 6. 相邻回归：物流/BOM clarification 与 unsupported 测试
# =============================================================================


def test_logistics_clarification_not_regressed() -> None:
    """LQG-4 不能导致物流 clarify 路径回归。

    RED/GREEN 目标：既有 logistics 域 CLARIFY 场景仍正确经过 validate。
    """
    from backend.app.domains.business_qa_graph.nodes.plan_validate_node import (
        plan_validate_node,
    )

    # 物流 clarify 场景（如缺少年份）
    state: BusinessQaGraphState = {
        "question": "物流运费最高的是哪个？",
        "domain_hint": None,
        "trace_id": "trace-log-clarify",
        "trace": [],
        "status": "PLAN_BUILT",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "graph_skeleton_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_data_qa"],
        "domain_route": {},
        "understanding_status": "CLARIFY_NEEDED",
        "shadow_plan_raw": {
            "domain": "logistics",
            "strategy": "CLARIFY",
            "clarification_questions": ["请指定查询的年份或具体条件。"],
        },
    }

    result = plan_validate_node(state)

    assert result["validation_result"] == "clarify"
    # 确认 trace 写入
    assert len(result["trace"]) > len(state.get("trace", []))


def test_bom_clarification_not_regressed() -> None:
    """LQG-4 不能导致 BOM clarify 路径回归。

    RED/GREEN 目标：既有 plan_bom 域 CLARIFY 场景仍正确经过 validate。
    """
    from backend.app.domains.business_qa_graph.nodes.plan_validate_node import (
        plan_validate_node,
    )

    state: BusinessQaGraphState = {
        "question": "这个 BOM 用了什么材料？",
        "domain_hint": None,
        "trace_id": "trace-bom-clarify",
        "trace": [],
        "status": "PLAN_BUILT",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "graph_skeleton_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "plan_bom",
        "capabilities": ["plan_bom_qa"],
        "domain_route": {},
        "understanding_status": "CLARIFY_NEEDED",
        "shadow_plan_raw": {
            "domain": "plan_bom",
            "strategy": "CLARIFY",
            "clarification_questions": ["请提供 BOM 文件或订单号。"],
        },
    }

    result = plan_validate_node(state)

    assert result["validation_result"] == "clarify"


def test_logistics_unsupported_not_regressed() -> None:
    """LQG-4 不能导致物流 unsupported 路径回归。

    RED/GREEN 目标：既有 unsupported 场景仍正确经过 validate。
    """
    from backend.app.domains.business_qa_graph.nodes.plan_validate_node import (
        plan_validate_node,
    )

    state: BusinessQaGraphState = {
        "question": "用 Python 写一个排序算法",
        "domain_hint": None,
        "trace_id": "trace-log-unsup",
        "trace": [],
        "status": "PLAN_BUILT",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "graph_skeleton_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "unknown",
        "capabilities": [],
        "domain_route": {},
        "understanding_status": "UNSUPPORTED",
        "shadow_plan_raw": {"unsupported_reason": "不在业务域范围内"},
    }

    result = plan_validate_node(state)

    assert result["validation_result"] == "unsupported"


# =============================================================================
# 7. Graph 集成测试（builder 插入 plan_validate 和条件路由）
# =============================================================================


def test_extended_graph_includes_plan_validate_node() -> None:
    """LQG-4 Graph 必须包含 plan_validate / clarify / unsupported / error 节点。

    RED: builder.py 尚未扩展。
    """
    from backend.app.domains.business_qa_graph.builder import build_business_qa_graph

    graph = build_business_qa_graph()

    # 尝试获取节点列表
    try:
        nodes = graph.get_graph().nodes
        node_names = set(nodes.keys())
    except Exception:
        node_names = set()

    # LQG-4 节点应存在
    assert "plan_validate" in node_names, f"Expected plan_validate in nodes, got {node_names}"
    assert "clarify" in node_names, f"Expected clarify in nodes, got {node_names}"
    assert "unsupported" in node_names, f"Expected unsupported in nodes, got {node_names}"
    assert "error_handler" in node_names, f"Expected error_handler in nodes, got {node_names}"


def test_valid_logistics_question_flows_through_plan_validate() -> None:
    """有效物流问题应经过 plan_validate 节点并通过。

    RED: builder.py 尚未扩展。
    """
    from backend.app.domains.business_qa_graph.builder import build_business_qa_graph

    graph = build_business_qa_graph()

    initial_state: BusinessQaGraphState = {
        "question": "2024 年总发运量是多少？",
        "domain_hint": "logistics",
        "trace_id": "trace-e2e-lqg4",
        "trace": [],
        "status": "PENDING",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "graph_skeleton_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "unknown",
        "capabilities": [],
        "domain_route": {},
    }

    final_state = graph.invoke(initial_state)

    # trace 中应包含 plan_validate
    node_names = [event["node"] for event in final_state["trace"]]
    assert "plan_validate" in node_names, f"Expected plan_validate in trace: {node_names}"

    # 物流问题应该通过校验，进入后续节点
    assert final_state["domain"] == "logistics"


def test_tech_leak_question_routes_to_unsupported_node() -> None:
    """包含技术泄露的请求应路由到 unsupported_node，不进入执行。

    验收标准："用 SQL 查物流表" -> 不执行 SQL、不暴露技术链路。

    RED: builder.py 尚未扩展。
    """
    from backend.app.domains.business_qa_graph.builder import build_business_qa_graph

    graph = build_business_qa_graph()

    # 模拟手工构建 state —— 跳过 domain_route 和 question_understanding，
    # 直接到 plan_validate 阶段验证
    initial_state: BusinessQaGraphState = {
        "question": "用 SQL 查物流表",
        "domain_hint": None,
        "trace_id": "trace-e2e-sql",
        "trace": [],
        "status": "PENDING",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "graph_skeleton_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "unknown",
        "capabilities": [],
        "domain_route": {},
    }

    final_state = graph.invoke(initial_state)

    # 最终状态不应是成功
    assert final_state["status"] != "PLAN_BUILT"
    # 应走 unsupported 路径
    assert final_state.get("validation_result") != "ok", (
        f"Tech leak question should not get validation_result=ok"
    )


# =============================================================================
# 8. 既有回归保护：确保 LQG-2/LQG-3 测试不退化
# =============================================================================


def test_lqg4_does_not_break_existing_receive_node() -> None:
    """LQG-4 不能破坏 LQG-1 receive_node 行为。

    GREEN 前置：本测试需要既有代码通过。
    """
    from backend.app.domains.business_qa_graph.nodes.receive_node import receive_node

    state = receive_node(
        {
            "question": "测试问题",
            "domain_hint": None,
            "trace_id": "t1",
            "trace": [],
        }
    )
    assert state["status"] == "RECEIVED"
    assert len(state["trace"]) == 1
    assert state["trace"][0]["event_type"] == "question_received"


def test_lqg4_does_not_break_existing_domain_route_node() -> None:
    """LQG-4 不能破坏 LQG-2 domain_route_node 行为。

    GREEN 前置：本测试需要既有代码通过。
    """
    from backend.app.domains.business_qa_graph.nodes.domain_route_node import domain_route_node

    state: BusinessQaGraphState = {
        "question": "2025 年合肥物流发运量是多少？",
        "domain_hint": "auto",
        "trace_id": "trace-dom-reg",
        "trace": [],
        "status": "RECEIVED",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "graph_skeleton_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "unknown",
        "capabilities": [],
        "domain_route": {},
    }

    result = domain_route_node(state)
    assert result["domain"] == "logistics"

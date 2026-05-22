"""LQG-6 focused tests: execute_node 计划 BOM 分支接入 PlanBomQaService。

采用 TDD RED→GREEN→REFACTOR 流程。本文件先写 RED 测试，再实现代码使 GREEN。

验收标准：
  1. 计划 BOM 域问题经 execute_node 调用 PlanBomQaService.ask 并存储结果
  2. stream fallback 优先 presentation.answer，避免 answer_summary 泄露槽位/内部字段
  3. 执行结果不泄露 SQL/表名/字段名/query_key/planner/raw/debug
  4. 异常安全降级
  5. 旧 /plan-bom/qa/ask 与 /stream 接口不受影响
  6. 物流域仍正常工作（LQG-5 回归）
"""

from __future__ import annotations

import pytest

from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState

# =============================================================================
# 工具：构建 plan_bom PLANNED 态 state
# =============================================================================

def _plan_bom_planned_state(*, question: str = "这个 BOM 用了什么玻璃和接线盒？") -> BusinessQaGraphState:
    """构造计划 BOM 域已通过校验、可进入执行态的 state。"""
    return {
        "question": question,
        "domain_hint": "plan_bom",
        "trace_id": "trace-lqg6",
        "trace": [],
        "status": "PLAN_BUILT",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "graph_skeleton_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "plan_bom",
        "capabilities": ["plan_bom_qa"],
        "domain_route": {
            "domain": "plan_bom",
            "status": "ROUTED",
            "confidence": 0.85,
        },
        "understanding_status": "PLANNED",
        "shadow_plan_raw": {
            "domain": "plan_bom",
            "strategy": "DIRECT_RETRIEVAL",
            "intent": "single_order_material_specs",
            "query_key": "single_order_material_specs",
            "slots": {"order_id": "ABC-001"},  # LQG-6: 必须填充必填槽位，通过 plan_validate
        },
        "validation_result": "ok",
        "validation_details": {},
        "user_visible_message": "",
        "execution_status": "NOT_STARTED",
        "execution_result": {},
    }


# =============================================================================
# 假 PlanBomQaResponse：模拟 PlanBomQaService.ask 的受控返回
# =============================================================================

class FakePlanBomResult:
    """模拟 PlanBomQaResponse 的最小业务化结构。"""

    def __init__(
        self,
        *,
        answer_summary: str = "",
        presentation_answer: str = "",
        rows: list[dict] | None = None,
        columns: list[str] | None = None,
        classification: str = "A",
        status_code: str = "OK",
        supported: bool = True,
        needs_clarification: bool = False,
        clarification_questions: list[str] | None = None,
        warnings: list[str] | None = None,
        nlu_intent: str = "single_order_material_specs",
    ) -> None:
        self.question = ""
        self.domain = "plan_bom"
        self.classification = classification
        # 状态对象（模拟 PlanBomQaStatus）
        self.status = type("FakeBomStatus", (), {})()
        self.status.code = status_code
        self.status.message = "查询成功" if status_code == "OK" else "需要补充信息"
        self.status.success = supported and status_code == "OK"
        self.status.severity = "info" if status_code == "OK" else "warning"
        # NLU 候选（不暴露给用户）
        self.nlu = type("FakeBomNlu", (), {})()
        self.nlu.question = ""
        self.nlu.intent = nlu_intent
        self.nlu.slots = {}
        self.nlu.missing_slots = [] if not needs_clarification else ["order_id"]
        self.nlu.confidence = 0.85
        self.nlu.provider_mode = "rule"
        self.nlu.guardrail_notes = []
        # answer_summary
        self.answer_summary = answer_summary
        # result_table
        self.result_table = type("FakeBomTable", (), {})()
        self.result_table.columns = columns or []
        self.result_table.rows = rows or []
        # presentation（用户可见表达层）
        # presentation.answer 优先于 answer_summary
        self.presentation = type("FakeBomPresentation", (), {})()
        self.presentation.display_type = "table" if rows else "narrative"
        self.presentation.title = "BOM 材料规格查询"
        # 关键字段：presentation.answer 为业务化表达
        self.presentation.answer = presentation_answer or answer_summary
        self.presentation.highlights = []
        self.presentation.table_spec = None
        self.presentation.caveats = warnings or []
        self.presentation.caveat_items = []
        self.presentation.follow_up = None
        self.presentation.unsupported_explanation = None
        self.presentation.debug = {}
        # 其他字段
        self.warnings = warnings or []
        self.needs_clarification = needs_clarification
        self.clarification_questions = clarification_questions or []
        self.raw_result = {}
        self.calculation_logic: list = []
        self.trace_events: list[dict] = []
        # 注意：不暴露 query_key/planner/guardrail/schema/raw/debug


class FakePlanBomService:
    """模拟 PlanBomQaService，只验证调用路径和参数传递。"""

    def __init__(
        self,
        *,
        result: FakePlanBomResult | None = None,
        should_fail: bool = False,
    ) -> None:
        self.result = result or FakePlanBomResult(
            answer_summary="已查询订单 ABC-001 的 12 条 BOM 材料规格。",
            presentation_answer="订单 ABC-001 的 BOM 包含玻璃、接线盒、胶膜、焊带等 12 种核心材料，具体规格如表所示。",
            columns=["订单号", "版本", "材料类别", "材料编码", "规格描述", "单位用量", "单位"],
            rows=[
                {"订单号": "ABC-001", "版本": "V1", "材料类别": "玻璃", "材料编码": "BL-001", "规格描述": "3.2mm 钢化玻璃", "单位用量": "1.0", "单位": "片"},
                {"订单号": "ABC-001", "版本": "V1", "材料类别": "接线盒", "材料编码": "JX-001", "规格描述": "IP68 接线盒", "单位用量": "1.0", "单位": "个"},
            ],
        )
        self.should_fail = should_fail
        self.called_questions: list[str] = []

    def ask(self, question: str, *, use_llm: bool = True, trace_id: str | None = None):
        """模拟 PlanBomQaService.ask 调用。"""
        self.called_questions.append(question)
        if self.should_fail:
            raise RuntimeError("模拟 BOM 服务异常")
        return self.result


# =============================================================================
# 1. execute_node 基础功能：计划 BOM 域调用 PlanBomQaService
# =============================================================================

def test_execute_node_plan_bom_domain_calls_service() -> None:
    """execute_node 对计划 BOM 域问题应调用 plan_bom_service.ask 并写入执行结果。

    RED: execute_node.py 尚未支持 plan_bom 域。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    service = FakePlanBomService()
    state = _plan_bom_planned_state(question="这个 BOM 用了什么玻璃和接线盒？")

    result = execute_node(state, plan_bom_service=service)

    # 服务被调用
    assert len(service.called_questions) == 1
    assert service.called_questions[0] == "这个 BOM 用了什么玻璃和接线盒？"

    # 状态变更
    assert result["status"] == "EXECUTED"
    assert result["execution_status"] == "EXECUTED"

    # 执行结果已写入
    exec_result = result.get("execution_result", {})
    assert exec_result.get("answer_summary") == "已查询订单 ABC-001 的 12 条 BOM 材料规格。"
    assert exec_result.get("row_count") == 2


def test_execute_node_plan_bom_prioritizes_presentation_answer() -> None:
    """execute_node 对计划 BOM 结果，应优先使用 presentation.answer 作为 user_visible_message，
    避免 answer_summary 泄露槽位/内部字段。

    RED: execute_node.py 尚未支持 plan_bom 域。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    # 构造 presentation.answer 和 answer_summary 不同的结果
    bom_result = FakePlanBomResult(
        answer_summary="已查询订单 ABC-001，slot=order_id，BOM 材料规格。",  # 包含槽位名
        presentation_answer="订单 ABC-001 的 BOM 包含 12 种核心材料，包括玻璃、接线盒等。",  # 业务化表达
        columns=["订单号", "材料类别", "规格描述"],
        rows=[{"订单号": "ABC-001", "材料类别": "玻璃", "规格描述": "3.2mm 钢化玻璃"}],
    )
    service = FakePlanBomService(result=bom_result)
    state = _plan_bom_planned_state(question="ABC-001 用了什么玻璃？")

    result = execute_node(state, plan_bom_service=service)

    user_msg = str(result.get("user_visible_message", ""))
    # 应使用 presentation.answer（业务化），而非 answer_summary（含槽位）
    assert "订单 ABC-001 的 BOM 包含" in user_msg
    assert "slot" not in user_msg.lower()
    assert "order_id" not in user_msg.lower()


def test_execute_node_plan_bom_falls_back_to_answer_summary_when_no_presentation() -> None:
    """当 PlanBomQaResponse 没有 presentation 时，应 fallback 到 answer_summary。

    RED: execute_node.py 尚未支持 plan_bom 域。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    # 构造没有 presentation.answer 的结果（模拟旧版或无 LLM 场景）
    bom_result = FakePlanBomResult(
        answer_summary="已查询订单 ABC-002 的 3 条 BOM 材料规格。",
        presentation_answer="",  # 空
        columns=["订单号", "材料类别"],
        rows=[{"订单号": "ABC-002", "材料类别": "接线盒"}],
    )
    service = FakePlanBomService(result=bom_result)
    state = _plan_bom_planned_state(question="ABC-002 接线盒规格？")

    result = execute_node(state, plan_bom_service=service)

    user_msg = str(result.get("user_visible_message", ""))
    assert "ABC-002" in user_msg
    assert "3 条" in user_msg


# =============================================================================
# 2. 执行结果不泄露技术细节
# =============================================================================

def test_execute_node_plan_bom_result_sanitized_no_tech_leak() -> None:
    """execute_node 写入的 plan_bom execution_result 不得包含 SQL/表名/字段名/raw/debug。

    RED: execute_node.py 尚未支持 plan_bom 域。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    service = FakePlanBomService()
    state = _plan_bom_planned_state(question="这个 BOM 用了什么接线盒？")

    result = execute_node(state, plan_bom_service=service)

    exec_result = result.get("execution_result", {})

    # 递归检查不包含技术泄露字段
    forbidden = ["query_key", "querykey", "sql", "raw", "debug", "planner", "guardrail", "schema"]
    _assert_no_tech_leak(exec_result, forbidden, path="execution_result")

    # result_table 中的列名也不应泄露
    columns = exec_result.get("columns") or []
    for col in columns:
        assert "query_key" not in str(col).lower()
        assert "sql" not in str(col).lower()


def _assert_no_tech_leak(obj: object, forbidden: list[str], path: str = "root") -> None:
    """递归检查对象中不包含禁止字符串。"""
    if isinstance(obj, dict):
        for key, value in obj.items():
            for f in forbidden:
                assert f not in key.lower(), f"Key '{key}' at {path} contains forbidden '{f}'"
            _assert_no_tech_leak(value, forbidden, path=f"{path}.{key}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _assert_no_tech_leak(item, forbidden, path=f"{path}[{i}]")
    elif isinstance(obj, str):
        for f in forbidden:
            assert f not in obj.lower(), f"Value at {path} contains forbidden '{f}': {obj[:200]}"


# =============================================================================
# 3. 异常安全降级
# =============================================================================

def test_execute_node_plan_bom_exception_handles_gracefully() -> None:
    """execute_node 在 plan_bom_service 抛出异常时应安全降级，不崩溃。

    RED: execute_node.py 尚未支持 plan_bom 域。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    service = FakePlanBomService(should_fail=True)
    state = _plan_bom_planned_state(question="测试 BOM 异常问题")

    result = execute_node(state, plan_bom_service=service)

    # 不应崩溃，状态应为 ERROR
    assert result["status"] == "ERROR"
    assert result["execution_status"] == "EXECUTION_ERROR"

    # 用户可见消息不泄露异常细节
    user_msg = str(result.get("user_visible_message", ""))
    assert len(user_msg) > 0
    assert "RuntimeError" not in user_msg
    assert "traceback" not in user_msg.lower()

    # trace 中有错误事件
    trace = result.get("trace", [])
    assert any(event.get("event_type") == "execution_failed" for event in trace)


# =============================================================================
# 4. 物流域回归（LQG-5 不退化）
# =============================================================================

def test_execute_node_logistics_domain_still_works() -> None:
    """LQG-5 物流域执行在新增 plan_bom 分支后仍正常工作。

    RED: execute_node.py 修改后物流域不应退化。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    class FakeLogisticsService:
        def __init__(self) -> None:
            self.called_questions: list[str] = []

        def query(self, payload):
            self.called_questions.append(payload.question)
            result = type("FakeLogisticsResult", (), {})()
            result.answer_summary = "物流查询成功"
            result.supported = True
            result.needs_clarification = False
            result.clarification_questions = []
            result.warnings = []
            result.result_table = type("FakeTable", (), {})()
            result.result_table.columns = []
            result.result_table.rows = []
            result.result_table.row_count = 0
            result.status = type("FakeStatus", (), {})()
            result.status.code = "ok"
            result.status.success = True
            result.presentation = type("FakePres", (), {})()
            result.presentation.display_type = "narrative"
            result.presentation.title = ""
            result.presentation.answer = ""
            result.presentation.caveats = []
            result.presentation.caveat_items = []
            result.calculation_logic = []
            result.trace_events = []
            result.history_log_id = None
            result.history_ready = False
            return result

    # 物流域 state
    logistics_state = {
        "question": "2024 年总运费是多少？",
        "domain_hint": "logistics",
        "trace_id": "trace-lqg5",
        "trace": [],
        "status": "PLAN_BUILT",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "graph_skeleton_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_data_qa"],
        "domain_route": {"domain": "logistics", "status": "ROUTED", "confidence": 0.85},
        "understanding_status": "PLANNED",
        "shadow_plan_raw": {"domain": "logistics", "strategy": "DIRECT_RETRIEVAL"},
        "validation_result": "ok",
        "validation_details": {},
        "user_visible_message": "",
        "execution_status": "NOT_STARTED",
        "execution_result": {},
    }

    service = FakeLogisticsService()
    result = execute_node(logistics_state, logistics_service=service)

    assert len(service.called_questions) == 1
    assert result["status"] == "EXECUTED"


def test_execute_node_non_logistics_non_plan_bom_skips() -> None:
    """execute_node 对非物流/非计划 BOM 域应跳过执行。

    RED: execute_node.py 修改后其他域仍应跳过。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    state = _plan_bom_planned_state(question="库存还有多少？")
    state["domain"] = "material_management"  # 未支持的域

    result = execute_node(state)

    # 不应执行
    assert result.get("execution_status") != "EXECUTED"
    if result.get("execution_status") == "NOT_STARTED":
        pass  # 预期跳过


# =============================================================================
# 5. Graph 路由：plan_bom PLANNED → execute
# =============================================================================

def test_graph_path_routes_plan_bom_to_execute() -> None:
    """经 Graph 的计划 BOM 问题应经过 execute 节点（路由正确）。

    RED: builder.py 尚未路由 plan_bom 到 execute。
    测试方法：直接验证 _route_after_plan_build 条件路由函数。
    （不走完整 graph 是因为 question_understanding_node 默认构造 BOM adapter 需要 DB 连接）
    """
    from backend.app.domains.business_qa_graph.builder import _route_after_plan_build

    # 验证 plan_bom + PLAN_BUILT + PLANNED → execute
    state = _plan_bom_planned_state(question="这个 BOM 用了什么玻璃？")
    assert _route_after_plan_build(state) == "execute"

    # 验证 logistics 域仍然路由到 execute（LQG-5 回归）
    state_logistics: BusinessQaGraphState = {
        **state,
        "domain": "logistics",
        "capabilities": ["logistics_data_qa"],
        "shadow_plan_raw": {"domain": "logistics", "strategy": "DIRECT_RETRIEVAL"},
    }
    assert _route_after_plan_build(state_logistics) == "execute"

    # 验证非 logistics/plan_bom 域不路由到 execute
    state_other = {**state, "domain": "material_management"}
    assert _route_after_plan_build(state_other) == "__end__"

    # 验证 PLAN_BUILT 以外状态不路由到 execute
    state_not_built = {**state, "status": "RECEIVED"}
    assert _route_after_plan_build(state_not_built) == "__end__"


# =============================================================================
# 6. 旧接口不受影响
# =============================================================================

def test_execute_node_plan_bom_does_not_affect_old_service_api() -> None:
    """execute_node 不改变 PlanBomQaService 的外部接口。

    RED: execute_node.py 修改后旧接口应保持不变。
    """
    from backend.app.domains.plan_bom.schemas.qa import (
        PlanBomNluCandidate,
        PlanBomPresentation,
        PlanBomQaRequest,
        PlanBomQaResponse,
        PlanBomQaStatus,
    )

    # 验证旧接口结构不变
    request = PlanBomQaRequest(question="这个 BOM 用了什么玻璃？")
    assert request.question == "这个 BOM 用了什么玻璃？"

    status = PlanBomQaStatus(code="OK", message="查询成功")
    assert status.code == "OK"

    response = PlanBomQaResponse(
        question="测试问题",
        classification="A",
        status=status,
        nlu=PlanBomNluCandidate(question="测试问题", intent="single_order_material_specs"),
        answer_summary="测试回答",
        presentation=PlanBomPresentation(
            display_type="narrative",
            answer="业务化测试回答",
        ),
    )
    assert response.domain == "plan_bom"
    assert response.presentation.answer == "业务化测试回答"

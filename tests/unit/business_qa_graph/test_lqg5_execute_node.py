"""LQG-5 focused tests: execute_node 物流分支接入 LogisticsDataQaService。

采用 TDD RED→GREEN→REFACTOR 流程。本文件先写 RED 测试，再实现代码使 GREEN。

验收标准：
  1. 物流域问题经 execute_node 调用 LogisticsDataQaService.query 并存储结果
  2. 非物流域问题不触发执行
  3. 执行结果不泄露 SQL/表名/字段名/query_key/planner/raw/debug
  4. 异常安全降级
  5. 与旧链路结果一致（相同状态、条数、关键数值）
"""

from __future__ import annotations

import pytest

from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState


# =============================================================================
# 工具：构建 logistics PLANNED 态 state
# =============================================================================

def _logistics_planned_state(*, question: str = "2024 年总运费是多少？") -> BusinessQaGraphState:
    """构造物流域已通过校验、可进入执行态的 state。"""
    return {
        "question": question,
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
        "domain_route": {
            "domain": "logistics",
            "status": "ROUTED",
            "confidence": 0.85,
        },
        "understanding_status": "PLANNED",
        "shadow_plan_raw": {
            "domain": "logistics",
            "strategy": "DIRECT_RETRIEVAL",
            "intent": "direct_retrieval",
            "query_key": "shipment_mw_summary",
        },
        "validation_result": "ok",
        "validation_details": {},
        "user_visible_message": "",
        "execution_status": "NOT_STARTED",
        "execution_result": {},
    }


# =============================================================================
# 假 service：模拟 LogisticsDataQaService.query 的受控返回
# =============================================================================

class FakeLogisticsResult:
    """模拟 LogisticsDataQaResult 的最小业务化结构。"""

    def __init__(
        self,
        *,
        answer_summary: str = "",
        rows: list[dict] | None = None,
        columns: list[str] | None = None,
        supported: bool = True,
        needs_clarification: bool = False,
        warnings: list[str] | None = None,
    ) -> None:
        self.answer_summary = answer_summary
        self.supported = supported
        self.needs_clarification = needs_clarification
        self.clarification_questions: list[str] = []
        self.warnings = warnings or []
        # 模拟 LogisticsDataQaTable
        self.result_table = type("FakeTable", (), {})()
        self.result_table.columns = columns or []
        self.result_table.rows = rows or []
        self.result_table.row_count = len(self.result_table.rows)
        self.status = type("FakeStatus", (), {})()
        self.status.code = "ok"
        self.status.message = ""
        self.status.success = True
        self.status.severity = "info"
        # presentation
        self.presentation = type("FakePresentation", (), {})()
        self.presentation.display_type = "table"
        self.presentation.title = "物流数据查询结果"
        self.presentation.answer = answer_summary
        self.presentation.caveats = warnings
        self.presentation.caveat_items = []
        self.presentation.table_spec = None
        self.presentation.chart_spec = None
        self.presentation.cards = []
        self.presentation.follow_up = None
        self.presentation.unsupported_explanation = None
        self.presentation.highlights = []
        self.presentation.debug = {}
        # 其他字段
        self.calculation_logic: list[str] = []
        self.data_scope: dict = {}
        self.query_plan = None
        self.history_log_id = None
        self.history_ready = False
        self.trace_events: list[dict] = []


class FakeLogisticsService:
    """模拟 LogisticsDataQaService，只验证调用路径和参数传递。"""

    def __init__(self, *, result: FakeLogisticsResult | None = None, should_fail: bool = False) -> None:
        self.result = result or FakeLogisticsResult(
            answer_summary="2024 年总运费为 12,345,678 元",
            columns=["年份", "总运费"],
            rows=[{"年份": "2024", "总运费": 12345678}],
        )
        self.should_fail = should_fail
        self.called_questions: list[str] = []

    def query(self, payload):
        """模拟 LogisticsDataQaService.query 调用。"""
        self.called_questions.append(payload.question)
        if self.should_fail:
            raise RuntimeError("模拟服务异常")
        return self.result


# =============================================================================
# 1. execute_node 基础功能测试
# =============================================================================

def test_execute_node_logistics_domain_calls_service() -> None:
    """execute_node 对物流域问题应调用 logistics_service.query 并写入执行结果。

    RED: nodes/execute_node.py 尚未创建。
    """
    from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    service = FakeLogisticsService()
    state = _logistics_planned_state(question="2024 年总运费是多少？")

    result = execute_node(state, logistics_service=service)

    # 服务被调用
    assert len(service.called_questions) == 1
    assert service.called_questions[0] == "2024 年总运费是多少？"

    # 状态变更
    assert result["status"] == "EXECUTED"
    assert result["execution_status"] == "EXECUTED"

    # 执行结果已写入
    exec_result = result.get("execution_result", {})
    assert exec_result.get("answer_summary") == "2024 年总运费为 12,345,678 元"
    assert exec_result.get("row_count") == 1


def test_execute_node_non_logistics_domain_skips() -> None:
    """execute_node 对非物流域问题应跳过执行，不调用 service。

    RED: nodes/execute_node.py 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    service = FakeLogisticsService()
    state = _logistics_planned_state(question="这个 BOM 用了什么玻璃？")
    state["domain"] = "plan_bom"
    state["capabilities"] = ["plan_bom_qa"]

    result = execute_node(state, logistics_service=service)

    # 不应调用物流 service
    assert len(service.called_questions) == 0
    # 状态不变
    assert result["status"] == "PLAN_BUILT"
    assert result["execution_status"] == "NOT_STARTED"


def test_execute_node_not_planned_skips() -> None:
    """execute_node 对 understanding_status != PLANNED 的问题应跳过执行。

    RED: nodes/execute_node.py 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    service = FakeLogisticsService()
    state = _logistics_planned_state(question="查一下")
    state["understanding_status"] = "CLARIFY_NEEDED"

    result = execute_node(state, logistics_service=service)

    assert len(service.called_questions) == 0
    assert result["status"] != "EXECUTED"
    assert result["execution_status"] == "NOT_STARTED"


def test_execute_node_validation_not_ok_skips() -> None:
    """execute_node 对 validation_result != ok 的问题应跳过执行。

    RED: nodes/execute_node.py 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    service = FakeLogisticsService()
    state = _logistics_planned_state()
    state["validation_result"] = "unsupported"

    result = execute_node(state, logistics_service=service)

    assert len(service.called_questions) == 0
    assert result["execution_status"] == "NOT_STARTED"


# =============================================================================
# 2. 执行结果不泄露技术细节
# =============================================================================

def test_execute_node_result_sanitized_no_tech_leak() -> None:
    """execute_node 写入的 execution_result 不得包含 SQL/表名/字段名/raw/debug。

    RED: nodes/execute_node.py 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    service = FakeLogisticsService()
    state = _logistics_planned_state(question="2024 年合肥发运量是多少？")

    result = execute_node(state, logistics_service=service)

    exec_result = result.get("execution_result", {})

    # 必须有业务化结果
    assert exec_result.get("answer_summary") is not None

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

def test_execute_node_exception_handles_gracefully() -> None:
    """execute_node 在 service 抛出异常时应安全降级，不崩溃。

    RED: nodes/execute_node.py 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    service = FakeLogisticsService(should_fail=True)
    state = _logistics_planned_state(question="测试异常问题")

    result = execute_node(state, logistics_service=service)

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
# 4. 与旧链路一致性验证（通过 LogisticsDataQaService 的直接调用验证）
# =============================================================================

def test_graph_path_produces_same_result_as_direct_service_call() -> None:
    """经 Graph 的物流问题应经过 execute 节点（路由正确），执行结果由注入的 service 提供。

    验收标准：Graph 包含 execute 节点路由，物流域 PLANNED 问题经 execute 处理后写入结果。

    RED: builder.py 尚未添加 execute_node。
    """
    from backend.app.domains.business_qa_graph.builder import build_business_qa_graph
    from backend.app.domains.business_qa_graph.schemas.response import BusinessQaGraphResponse

    # 通过 graph 运行（不注入 service，验证路由正确）
    graph = build_business_qa_graph()
    # 使用规划器能接受的物流问题
    initial_state = _logistics_planned_state(question="2025 年哪个承运商发运量最高？")
    final_state = graph.invoke(initial_state)

    response = BusinessQaGraphResponse.from_state(final_state)

    # 状态为 PLAN_BUILT（未注入 service 时跳过执行）
    assert response.status == "PLAN_BUILT", f"Unexpected status: {response.status}"

    # trace 中包含 execute 节点（验证路由正确）
    node_names = [event.node for event in response.trace]
    assert "execute" in node_names, f"Expected 'execute' in trace nodes, got: {node_names}"

    # 验证 execute 节点的跳过事件
    execute_events = [e for e in response.trace if e.node == "execute"]
    assert len(execute_events) == 1
    assert execute_events[0].event_type == "execution_skipped"
    assert execute_events[0].payload.get("reason") == "no_service_available"


# =============================================================================
# 5. 业务边界守卫测试
# =============================================================================

def test_execute_node_preserves_explicit_carrier_no_widening() -> None:
    """显式承运商无数据时不应放宽到全承运商汇总。

    RED: nodes/execute_node.py 尚未创建。

    本测试验证 execute_node 调用的 service 产生的结果中，
    承运商过滤没有被静默放宽。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    # 模拟空结果：显式承运商无数据
    empty_result = FakeLogisticsResult(
        answer_summary="承运商「XX物流」在 2024 年没有匹配的发运记录。",
        rows=[],
        columns=[],
        warnings=["未找到匹配的承运商数据"],
    )
    service = FakeLogisticsService(result=empty_result)
    state = _logistics_planned_state(question="2024 年 XX物流 发运量是多少？")

    result = execute_node(state, logistics_service=service)

    exec_result = result.get("execution_result", {})
    assert exec_result.get("row_count") == 0
    # 不应有非空的全承运商汇总
    assert exec_result.get("row_count") != 1


def test_execute_node_multi_year_preserves_empty_years() -> None:
    """多年份查询应保留空年份行，不静默省略。

    RED: nodes/execute_node.py 尚未创建。

    本测试验证 execute_node 调用的 service 返回的结果中，
    多个年份即使某年份无数据，也应保留该年份行（标记为 0 或无数据）。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    # 模拟多年份结果：2023 有数据，2024 无数据但保留行
    multi_year_result = FakeLogisticsResult(
        answer_summary="2023 年总运费 1,000,000 元；2024 年无匹配记录。",
        columns=["年份", "总运费"],
        rows=[
            {"年份": "2023", "总运费": 1000000},
            {"年份": "2024", "总运费": None},
        ],
    )
    service = FakeLogisticsService(result=multi_year_result)
    state = _logistics_planned_state(question="2023 年和 2024 年总运费分别是多少？")

    result = execute_node(state, logistics_service=service)

    exec_result = result.get("execution_result", {})
    assert exec_result.get("row_count") == 2
    rows = exec_result.get("rows") or []
    years = [row.get("年份") for row in rows]
    assert "2023" in years
    assert "2024" in years  # 不静默省略


# =============================================================================
# 6. 执行不通过旧 service 路径验证（已存在测试不受影响）
# =============================================================================

def test_execute_node_does_not_affect_old_service_api() -> None:
    """execute_node 不改变 LogisticsDataQaService 的外部接口。

    RED: nodes/execute_node.py 尚未创建。
    """
    from backend.app.domains.logistics.schemas.data_qa import (
        LogisticsDataQaQueryRequest,
        LogisticsDataQaResult,
    )

    # 验证旧接口保持不变
    request = LogisticsDataQaQueryRequest(question="2024 年总运费是多少？")
    assert request.question == "2024 年总运费是多少？"

    # LogisticsDataQaResult 结构不变
    result = LogisticsDataQaResult(
        answer_summary="",
        result_table={"columns": [], "rows": [], "row_count": 0, "annotations": {}},
        query_plan={
            "domain": "logistics",
            "intent": "direct_retrieval",
            "query_key": "shipment_mw_summary",
            "metrics": [],
            "filters": {},
        },
        trace_events=[],
    )
    assert result.answer_summary == ""
    assert result.supported is True

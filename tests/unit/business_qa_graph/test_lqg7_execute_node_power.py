"""LQG-7 focused tests: execute_node 功率预测/供应商推荐/影响值对比 capability 纳入 Graph。

采用 TDD RED→GREEN→REFACTOR 流程。本文件先写 RED 测试，验证执行链路。

验收标准：
  1. plan_power_prediction capability 经 execute_node 调用 PlanBomQaService.ask 并返回功率预测结果
  2. plan_power_supplier_recommendation capability 经 execute_node 返回供应商推荐结果
  3. plan_power_factor_effect_compare capability 经 execute_node 返回配置影响值对比
  4. 缺关键参数时业务化追问（不泄露内部槽位/技术细节）
  5. 无 active power model 时业务化说明
  6. 功率结果不泄露 SQL/表名/字段名/query_key/planner/raw/debug
  7. 功率服务异常时安全降级
  8. 普通 BOM 问答和物流域不退化（LQG-5/LQG-6 回归）
"""

from __future__ import annotations

# =============================================================================
# 工具：构建 plan_bom 功率 capability PLANNED 态 state
# =============================================================================

def _power_planned_state(
    *,
    question: str = "订单 ABC-001 的目标功率 615W？",
    capabilities: tuple[str, ...] = ("plan_power_prediction",),
    shadow_plan_intent: str = "plan_power_prediction",
) -> dict:
    """构造计划 BOM 域功率 capability 已通过校验、可进入执行态的 state。"""
    return {
        "question": question,
        "domain_hint": "plan_bom",
        "trace_id": "trace-lqg7",
        "trace": [],
        "status": "PLAN_BUILT",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "graph_skeleton_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "plan_bom",
        "capabilities": list(capabilities),
        "domain_route": {
            "domain": "plan_bom",
            "status": "ROUTED",
            "confidence": 0.85,
        },
        "understanding_status": "PLANNED",
        "shadow_plan_raw": {
            "domain": "plan_bom",
            "strategy": "DIRECT_RETRIEVAL",
            "intent": shadow_plan_intent,
            "query_key": shadow_plan_intent,
            "slots": {"order_tail_no": ["ABC-001"], "target_power": "615W"},
        },
        "validation_result": "ok",
        "validation_details": {},
        "user_visible_message": "",
        "execution_status": "NOT_STARTED",
        "execution_result": {},
    }


# =============================================================================
# 假 PlanBom 功率结果：模拟 PlanBomQaService.ask 返回的功率预测响应
# =============================================================================

class FakePowerPredictionBomResult:
    """模拟 PlanBomQaResponse 的功率预测分支返回结构。"""

    def __init__(
        self,
        *,
        answer_summary: str = "",
        presentation_answer: str = "",
        rows: list[dict] | None = None,
        columns: list[str] | None = None,
        classification: str = "A",
        status_code: str = "OK",
        status_message: str = "功率预测成功",
        needs_clarification: bool = False,
        clarification_questions: list[str] | None = None,
        warnings: list[str] | None = None,
        supported: bool = True,
    ) -> None:
        self.question = ""
        self.domain = "plan_bom"
        self.classification = classification
        # 状态对象
        self.status = type("FakeBomStatus", (), {})()
        self.status.code = status_code
        self.status.message = status_message
        self.status.success = status_code == "OK" and not needs_clarification
        self.status.severity = "info" if status_code == "OK" else "warning"
        # NLU（不暴露）
        self.nlu = type("FakeBomNlu", (), {})()
        self.nlu.question = ""
        self.nlu.intent = "plan_power_prediction"
        self.nlu.slots = {"order_tail_no": ["ABC-001"], "target_power": "615W"}
        self.nlu.missing_slots = [] if not needs_clarification else ["order_tail_no"]
        self.nlu.confidence = 0.85
        self.nlu.provider_mode = "rule"
        self.nlu.guardrail_notes = []
        # answer_summary
        self.answer_summary = answer_summary
        # result_table
        self.result_table = type("FakeBomTable", (), {})()
        self.result_table.columns = columns or []
        self.result_table.rows = rows or []
        # presentation
        self.presentation = type("FakeBomPresentation", (), {})()
        self.presentation.display_type = "table" if rows else "narrative"
        self.presentation.title = "功率预测结果"
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


def _make_power_prediction_bom_result() -> FakePowerPredictionBomResult:
    """构造标准功率预测成功响应。"""
    return FakePowerPredictionBomResult(
        answer_summary="已完成订单 ABC-001 的功率预测：版型 NT72-12GDF，供应商 晶澳，中心功率 614.2378W。配置来源：玻璃 2.0mm钢化、焊带 0.3*0.7、基准标板 605W。",
        presentation_answer="订单 ABC-001 的组件功率预测结果为 614.24W，基于当前 BOM 配置（2.0mm玻璃、0.3*0.7焊带）与晶澳供应商效率，详细功率档分布见表。",
        classification="A",
        status_code="OK",
        status_message="功率预测成功",
        columns=["功率档", "预测比例", "累计比例", "中心功率", "供应商"],
        rows=[
            {"功率档": "605W", "预测比例": 0.25, "累计比例": 0.25, "中心功率": 605.0, "供应商": "晶澳"},
            {"功率档": "610W", "预测比例": 0.35, "累计比例": 0.60, "中心功率": 610.0, "供应商": "晶澳"},
            {"功率档": "615W", "预测比例": 0.40, "累计比例": 1.00, "中心功率": 615.0, "供应商": "晶澳"},
        ],
    )


class FakePowerPlanBomService:
    """模拟 PlanBomQaService，用于注入 execute_node 测试功率 capability。"""

    def __init__(self, *, result: FakePowerPredictionBomResult | None = None, should_fail: bool = False) -> None:
        self.result = result or _make_power_prediction_bom_result()
        self.should_fail = should_fail
        self.called_questions: list[str] = []

    def ask(self, question: str, *, use_llm: bool = True, trace_id: str | None = None):
        """模拟 PlanBomQaService.ask 调用。"""
        self.called_questions.append(question)
        if self.should_fail:
            raise RuntimeError("模拟功率预测服务异常")
        return self.result


# =============================================================================
# 1. 功率预测 capability 通过 execute_node 正确执行
# =============================================================================

def test_execute_node_power_prediction_capability_calls_service() -> None:
    """execute_node 对 plan_power_prediction capability 应调用 plan_bom_service.ask 并返回结果。

    RED: execute_node 需正确传递功率预测问题到 PlanBomQaService。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    service = FakePowerPlanBomService()
    state = _power_planned_state(
        question="订单 ABC-001 的目标功率 615W？",
        capabilities=("plan_power_prediction",),
        shadow_plan_intent="plan_power_prediction",
    )

    result = execute_node(state, plan_bom_service=service)

    # 服务被调用
    assert len(service.called_questions) == 1
    assert "615W" in service.called_questions[0]

    # 状态变更
    assert result["status"] == "EXECUTED"
    assert result["execution_status"] == "EXECUTED"

    # 执行结果包含功率预测数据
    exec_result = result.get("execution_result", {})
    assert "ABC-001" in str(exec_result.get("answer_summary", ""))
    assert exec_result.get("row_count", 0) > 0


def test_execute_node_power_prediction_result_preserves_business_fields() -> None:
    """功率预测结果应保留功率档、预测比例等业务化字段，不丢失关键信息。

    RED: execute_node 的 _sanitize_plan_bom_result 需正确提取功率预测特有列名和行数据。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    service = FakePowerPlanBomService()
    state = _power_planned_state(
        question="ABC-001 功率预测",
        capabilities=("plan_power_prediction",),
        shadow_plan_intent="plan_power_prediction",
    )

    result = execute_node(state, plan_bom_service=service)

    exec_result = result.get("execution_result", {})
    # 列名应包含功率预测业务字段
    columns = exec_result.get("columns", [])
    assert any("功率" in str(c) for c in columns) or any("瓦" in str(c) for c in columns)

    # 行数据包含功率数值
    rows = exec_result.get("rows", [])
    assert len(rows) == 3


# =============================================================================
# 2. 供应商推荐 capability 通过 execute_node
# =============================================================================

def _make_supplier_recommendation_bom_result() -> FakePowerPredictionBomResult:
    """构造供应商功率推荐成功响应。"""
    return FakePowerPredictionBomResult(
        answer_summary="已按订单 ABC-001 的 BOM 配置和目标功率比例完成供应商推荐，晶澳建议从 21.5% 效率段投产。",
        presentation_answer="基于订单 ABC-001 的组件版型 NT72-12GDF，推荐供应商为晶澳，建议效率段 21.5%~22.0%。",
        classification="A",
        status_code="OK",
        status_message="供应商功率推荐成功",
        columns=["供应商", "目标功率档", "目标比例", "预测比例", "CTM 值", "中心功率", "建议效率段", "落档比例预估"],
        rows=[
            {"供应商": "晶澳", "目标功率档": "615W", "目标比例": 0.6, "预测比例": 0.58, "CTM 值": 0.99, "中心功率": 614.2, "建议效率段": "21.5%~22.0%", "落档比例预估": 0.55},
            {"供应商": "隆基", "目标功率档": "615W", "目标比例": 0.6, "预测比例": 0.35, "CTM 值": 0.97, "中心功率": 612.5, "建议效率段": "22.0%~22.5%", "落档比例预估": 0.30},
        ],
    )


def test_execute_node_supplier_recommendation_capability_calls_service() -> None:
    """execute_node 对 plan_power_supplier_recommendation capability 应返回推荐结果。

    RED: execute_node 需正确路由供应商推荐 capability 到 PlanBomQaService。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    service = FakePowerPlanBomService(result=_make_supplier_recommendation_bom_result())
    state = _power_planned_state(
        question="订单 ABC-001 推荐什么供应商达到 615W？",
        capabilities=("plan_power_supplier_recommendation",),
        shadow_plan_intent="plan_power_supplier_recommendation",
    )

    result = execute_node(state, plan_bom_service=service)

    assert result["status"] == "EXECUTED"
    exec_result = result.get("execution_result", {})
    answer = str(exec_result.get("answer_summary", ""))
    # 推荐结果应包含供应商和效率段
    assert "晶澳" in answer or "供应商" in answer


# =============================================================================
# 3. 配置影响值对比 capability 通过 execute_node
# =============================================================================

def _make_factor_effect_compare_bom_result() -> FakePowerPredictionBomResult:
    """构造功率配置影响值对比成功响应。"""
    return FakePowerPredictionBomResult(
        answer_summary="NT72-12GDF 的焊带功率影响值对比：0.3*0.7 为 -8.5W，0.35*0.8 为 -2.3W，二者相差 6.2W。",
        presentation_answer="版型 NT72-12GDF 下，焊带 0.3*0.7 的功率影响值为 -8.5W，焊带 0.35*0.8 为 -2.3W，改用后者可提升约 6.2W。",
        classification="A",
        status_code="OK",
        status_message="配置影响值对比成功",
        columns=["配置项", "选项", "功率影响值"],
        rows=[
            {"配置项": "焊带", "选项": "0.3*0.7", "功率影响值": -8.5},
            {"配置项": "焊带", "选项": "0.35*0.8", "功率影响值": -2.3},
            {"配置项": "焊带", "选项": "差值", "功率影响值": 6.2},
        ],
    )


def test_execute_node_factor_effect_compare_capability_calls_service() -> None:
    """execute_node 对 plan_power_factor_effect_compare capability 应返回对比结果。

    RED: execute_node 需正确路由配置影响值对比 capability 到 PlanBomQaService。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    service = FakePowerPlanBomService(result=_make_factor_effect_compare_bom_result())
    state = _power_planned_state(
        question="NT72-12GDF 版型，焊带 0.3*0.7 和 0.35*0.8 功率影响值相差多少？",
        capabilities=("plan_power_factor_effect_compare",),
        shadow_plan_intent="plan_power_factor_effect_compare",
    )

    result = execute_node(state, plan_bom_service=service)

    assert result["status"] == "EXECUTED"
    exec_result = result.get("execution_result", {})
    # 对比结果应包含差值
    rows = exec_result.get("rows", [])
    assert any("差值" in str(r) for r in rows)


# =============================================================================
# 4. 缺关键参数时业务化追问
# =============================================================================

def _make_clarification_bom_result() -> FakePowerPredictionBomResult:
    """构造需要澄清的功率响应（缺关键参数）。"""
    return FakePowerPredictionBomResult(
        answer_summary="需要您补充订单号或 BOM 文件名才能进行功率预测。",
        presentation_answer="为了进行功率预测，请提供订单号（例如 ABC-001）或 BOM 文件名。",
        classification="B",
        status_code="CLARIFICATION_REQUIRED",
        status_message="缺少关键参数",
        needs_clarification=True,
        clarification_questions=["请提供具体的订单号或 BOM 文件名", "或指定组件版型号（如 NT72-12GDF）"],
    )


def test_execute_node_power_missing_params_triggers_clarification() -> None:
    """缺关键参数时，execute_node 应返回业务化追问，不暴露槽位/技术细节。

    RED: execute_node 需正确处理 needs_clarification 态，user_visible_message 不泄露内部信息。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    service = FakePowerPlanBomService(result=_make_clarification_bom_result())
    state = _power_planned_state(
        question="功率预测",
        capabilities=("plan_power_prediction",),
        shadow_plan_intent="plan_power_prediction",
    )

    result = execute_node(state, plan_bom_service=service)

    assert result["status"] == "EXECUTED"
    exec_result = result.get("execution_result", {})
    assert exec_result.get("needs_clarification") is True

    # user_visible_message 应包含追问内容
    user_msg = str(result.get("user_visible_message", ""))
    assert "订单号" in user_msg or "BOM" in user_msg

    # 不泄露技术细节
    assert "slot" not in user_msg.lower()
    assert "missing_slots" not in user_msg.lower()


# =============================================================================
# 5. 无 active power model 时业务化说明
# =============================================================================

def _make_no_active_model_bom_result() -> FakePowerPredictionBomResult:
    """构造无 active 功率模型的响应。"""
    return FakePowerPredictionBomResult(
        answer_summary="当前没有生效的功率模型版本，无法查询配置影响值。",
        presentation_answer="当前系统中没有已激活的功率预测模型，请先导入并激活功率模型版本后再查询。",
        classification="B",
        status_code="CLARIFICATION_REQUIRED",
        status_message="无可用功率模型",
        needs_clarification=True,
        clarification_questions=[],
        warnings=["当前没有生效的功率模型版本，请先导入功率模型。"],
        supported=False,
    )


def test_execute_node_power_no_active_model_explains() -> None:
    """无 active power model 时，execute_node 应返回业务化说明而非内部错误。

    RED: execute_node 的 user_visible_message 应提供可操作的业务指引。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    service = FakePowerPlanBomService(result=_make_no_active_model_bom_result())
    state = _power_planned_state(
        question="NT72-12GDF 焊带影响值对比",
        capabilities=("plan_power_factor_effect_compare",),
        shadow_plan_intent="plan_power_factor_effect_compare",
    )

    result = execute_node(state, plan_bom_service=service)

    user_msg = str(result.get("user_visible_message", ""))
    # 应包含业务化说明
    assert "功率" in user_msg or "模型" in user_msg
    # 不应暴露技术细节
    assert "SQL" not in user_msg
    assert "Exception" not in user_msg
    assert "traceback" not in user_msg.lower()


# =============================================================================
# 6. 功率结果不泄露技术细节
# =============================================================================

def test_execute_node_power_result_sanitized_no_tech_leak() -> None:
    """功率预测/推荐/对比结果不泄露 SQL/表名/字段名/query_key/planner/raw/debug。

    RED: _sanitize_plan_bom_result 对功率结果正确剔除技术字段。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    service = FakePowerPlanBomService()
    state = _power_planned_state(
        question="ABC-001 功率预测 615W",
        capabilities=("plan_power_prediction",),
        shadow_plan_intent="plan_power_prediction",
    )

    result = execute_node(state, plan_bom_service=service)
    exec_result = result.get("execution_result", {})

    # 递归检查不包含技术泄露字段
    forbidden = ["query_key", "querykey", "sql", "raw", "debug", "planner", "guardrail", "schema"]
    _assert_no_tech_leak(exec_result, forbidden, path="execution_result")

    # 列名也不应泄露
    columns = exec_result.get("columns") or []
    for col in columns:
        assert "query_key" not in str(col).lower()
        assert "sql" not in str(col).lower()
        assert "raw" not in str(col).lower()

    # user_visible_message 不包含技术细节
    user_msg = str(result.get("user_visible_message", ""))
    assert "SQL" not in user_msg
    assert "query_key" not in user_msg.lower()
    assert "raw_result" not in user_msg.lower()


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
# 7. 功率服务异常时安全降级
# =============================================================================

def test_execute_node_power_exception_handles_gracefully() -> None:
    """功率预测服务异常时 execute_node 应安全降级，不崩溃、不泄露异常细节。

    RED: execute_node 的异常处理路径覆盖功率分支。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    service = FakePowerPlanBomService(should_fail=True)
    state = _power_planned_state(
        question="ABC-001 功率预测",
        capabilities=("plan_power_prediction",),
        shadow_plan_intent="plan_power_prediction",
    )

    result = execute_node(state, plan_bom_service=service)

    # 不应崩溃
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
# 8. LQG-5/LQG-6 回归：普通 BOM 和物流域不退化
# =============================================================================

def test_execute_node_regular_bom_capability_still_works_after_power() -> None:
    """普通 plan_bom_qa capability 在功率 capability 代码修改后仍正常。

    RED: 功率分支不影响普通 BOM 材料查询路径。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    # 使用 LQG-6 的 FakePlanBomResult（普通 BOM 材料查询）
    class FakeRegularBomResult:
        def __init__(self):
            self.question = ""
            self.domain = "plan_bom"
            self.classification = "A"
            self.status = type("S", (), {})()
            self.status.code = "OK"
            self.status.message = "查询成功"
            self.status.success = True
            self.status.severity = "info"
            self.nlu = type("N", (), {})()
            self.nlu.intent = "single_order_material_specs"
            self.nlu.slots = {"order_tail_no": ["ABC-001"]}
            self.nlu.missing_slots = []
            self.answer_summary = "已查询订单 ABC-001 的 12 条 BOM 材料规格。"
            self.result_table = type("T", (), {})()
            self.result_table.columns = ["订单号", "版本", "材料类别", "规格描述"]
            self.result_table.rows = [{"订单号": "ABC-001", "材料类别": "玻璃"}]
            self.presentation = type("P", (), {})()
            self.presentation.display_type = "table"
            self.presentation.title = "BOM 查询"
            self.presentation.answer = "订单 ABC-001 包含玻璃、接线盒等核心材料。"
            self.warnings = []
            self.needs_clarification = False
            self.clarification_questions = []
            self.raw_result = {}
            self.calculation_logic = []
            self.trace_events = []

    class FakeRegularBomService:
        def __init__(self):
            self.called_questions = []

        def ask(self, question, **kwargs):
            self.called_questions.append(question)
            return FakeRegularBomResult()

    service = FakeRegularBomService()
    state = _power_planned_state(
        question="这个 BOM 用了什么玻璃？",
        capabilities=("plan_bom_qa",),
        shadow_plan_intent="single_order_material_specs",
    )

    result = execute_node(state, plan_bom_service=service)

    assert result["status"] == "EXECUTED"
    assert len(service.called_questions) == 1


def test_execute_node_logistics_domain_still_works_after_power() -> None:
    """物流域执行在新增功率 capability 后仍正常（LQG-5 回归）。

    RED: 功率分支不影响物流域执行路径。
    """
    from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node

    class FakeLogisticsService:
        def __init__(self):
            self.called_questions = []

        def query(self, payload):
            self.called_questions.append(payload.question)
            result = type("R", (), {})()
            result.answer_summary = "物流查询成功"
            result.supported = True
            result.needs_clarification = False
            result.clarification_questions = []
            result.warnings = []
            result.result_table = type("T", (), {})()
            result.result_table.columns = []
            result.result_table.rows = []
            result.result_table.row_count = 0
            result.status = type("S", (), {})()
            result.status.code = "ok"
            result.status.success = True
            result.presentation = type("P", (), {})()
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

    logistics_state = {
        "question": "2024 年总运费是多少？",
        "domain_hint": "logistics",
        "trace_id": "trace-lqg5-reg",
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


# =============================================================================
# 9. Graph 路由：功率 capabilities 正确路由到 execute
# =============================================================================

def test_graph_path_routes_power_capabilities_to_execute() -> None:
    """plan_bom 域功率 capability 应经 _route_after_plan_build 路由到 execute。

    RED: _route_after_plan_build 对各种功率 capability 应返回 "execute"。
    """
    from backend.app.domains.business_qa_graph.builder import _route_after_plan_build

    # plan_power_prediction
    state_pred = _power_planned_state(
        question="ABC-001 功率预测 615W",
        capabilities=("plan_power_prediction",),
        shadow_plan_intent="plan_power_prediction",
    )
    assert _route_after_plan_build(state_pred) == "execute"

    # plan_power_supplier_recommendation
    state_supp = _power_planned_state(
        question="推荐供应商",
        capabilities=("plan_power_supplier_recommendation",),
        shadow_plan_intent="plan_power_supplier_recommendation",
    )
    assert _route_after_plan_build(state_supp) == "execute"

    # plan_power_factor_effect_compare
    state_factor = _power_planned_state(
        question="焊带影响值对比",
        capabilities=("plan_power_factor_effect_compare",),
        shadow_plan_intent="plan_power_factor_effect_compare",
    )
    assert _route_after_plan_build(state_factor) == "execute"

    # 所有三个 capability 仍然通过 plan_bom 域路由
    for s in (state_pred, state_supp, state_factor):
        assert s["domain"] == "plan_bom"

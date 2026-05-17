from __future__ import annotations

import json

from backend.app.domains.logistics.schemas.data_qa import (
    LogisticsDataQaPlan,
    LogisticsDataQaResult,
    LogisticsDataQaStatus,
    LogisticsDataQaTable,
)
from backend.app.domains.logistics.services.llm_answer_presentation_service import LogisticsLlmAnswerPresentationService
from backend.app.domains.plan_bom.schemas.qa import (
    PlanBomNluCandidate,
    PlanBomQaResponse,
    PlanBomQaStatus,
    PlanBomTableSpec,
)
from backend.app.domains.plan_bom.api.endpoints.qa import _resolve_plan_bom_stream_fallback_answer
from backend.app.domains.plan_bom.services.answer_presentation_service import PlanBomAnswerPresentationService
from backend.app.services.business_answer_stream_service import BusinessAnswerStreamService


class _FakeStreamClient:
    """构造 OpenAI 兼容的测试流式客户端。"""

    def __init__(self, chunks: list[str]) -> None:
        self.chat = _FakeChat(chunks)


class _FakeChat:
    """承载 completions 入口，避免测试访问真实 LLM。"""

    def __init__(self, chunks: list[str]) -> None:
        self.completions = _FakeCompletions(chunks)


class _FakeCompletions:
    """返回固定 chunk 的流式 completion。"""

    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks

    def create(self, **_kwargs: object) -> list[dict[str, object]]:
        """返回 OpenAI chat.completions.create 兼容事件。"""

        return [{"choices": [{"delta": {"content": chunk}}]} for chunk in self._chunks]


class _FakeJsonClient:
    """构造 OpenAI 兼容的非流式 JSON 返回客户端。"""

    def __init__(self, payload: dict[str, object]) -> None:
        self.chat = _FakeJsonChat(payload)


class _FakeJsonChat:
    """承载非流式 completion 入口。"""

    def __init__(self, payload: dict[str, object]) -> None:
        self.completions = _FakeJsonCompletions(payload)


class _FakeJsonCompletions:
    """返回固定 JSON 文本的 completion。"""

    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def create(self, **_kwargs: object) -> object:
        """返回 OpenAI 非流式 completion 兼容对象。"""

        message = type("FakeMessage", (), {"content": json.dumps(self._payload, ensure_ascii=False)})()
        choice = type("FakeChoice", (), {"message": message})()
        return type("FakeCompletion", (), {"choices": [choice]})()


class _ExplodingSecondEventClient:
    """第一段可读、第二段抛错，用于证明 stream_answer 不会先读完整流再返回首段。"""

    def __init__(self) -> None:
        self.chat = _ExplodingSecondEventChat()


class _ExplodingSecondEventChat:
    """承载会中途抛错的流式 completion。"""

    def __init__(self) -> None:
        self.completions = _ExplodingSecondEventCompletions()


class _ExplodingSecondEventCompletions:
    """生成第一段安全内容后，在第二段模拟上游异常。"""

    def create(self, **_kwargs: object) -> object:
        """返回一个惰性生成器，不能在首个 yield 前被完整消费。"""

        def _events():
            yield {"choices": [{"delta": {"content": "查到了，"}}]}
            raise RuntimeError("second chunk should not be consumed before first yield")

        return _events()


def _logistics_result(*, rows: list[dict[str, object]] | None = None) -> LogisticsDataQaResult:
    """构造可复用的物流确定性结果。

    参数：
        rows: 后端查询返回的结构化行。
    返回值：
        一个 OK 状态的 LogisticsDataQaResult。
    业务逻辑：
        测试只关注展示编排，不依赖真实数据库。
    """

    result_rows = rows or [
        {"region_name": "华东", "shipment_mw": 120.5},
        {"region_name": "华南", "shipment_mw": 88.2},
    ]
    return LogisticsDataQaResult(
        answer_summary="2026年发运量统计已完成，华东 120.5MW，华南 88.2MW。",
        result_table=LogisticsDataQaTable(columns=["region_name", "shipment_mw"], rows=result_rows),
        calculation_logic=["发运量按 MW 口径汇总。"],
        data_scope={"year": 2026},
        query_plan=LogisticsDataQaPlan(
            intent="shipment_summary",
            query_key="sys_region_mw",
            metrics=["shipment_mw"],
            dimensions=["region_name"],
            filters={"year": 2026},
            group_by=["region_name"],
        ),
        status=LogisticsDataQaStatus(code="OK", message="查询成功", success=True),
    )


def _stream_payload() -> dict[str, object]:
    """构造流式答案安全测试使用的确定性 payload。"""

    result = _logistics_result()
    service = LogisticsLlmAnswerPresentationService(enabled=True, base_url=None, api_key=None, model="")
    presentation = service.build_presentation(question="统计2026年各区域发运量", result=result)
    assert presentation is not None
    result.presentation = presentation
    return result.model_dump(mode="json")


def _plan_bom_response(question: str) -> PlanBomQaResponse:
    """构造计划 BOM 确定性结果。

    参数：
        question: 用户原始问题，用于测试展示意图识别。
    返回值：
        一个 A 类 OK 的 PlanBomQaResponse。
    业务逻辑：
        计划 BOM 表格事实仍保留在 result_table，presentation 是否展示由问题意图决定。
    """

    return PlanBomQaResponse(
        question=question,
        classification="A",
        status=PlanBomQaStatus(code="OK", message="查询成功"),
        nlu=PlanBomNluCandidate(question=question, intent="plan_power_prediction", slots={"order_tail_no": ["00104"]}),
        answer_summary="订单00104功率预测已完成，中心功率为620W。",
        result_table=PlanBomTableSpec(
            columns=["功率档", "预测比例"],
            rows=[{"功率档": "620W", "预测比例": "50%"}, {"功率档": "625W", "预测比例": "50%"}],
        ),
        raw_result={"power_prediction": {"center_power": 620}},
    )


def test_logistics_answer_defaults_to_text_only_when_no_visual_request() -> None:
    """未明确要求图表/表格/指标卡时，物流智能回答只给 Markdown 文字，不固定渲染数据组件。"""

    service = LogisticsLlmAnswerPresentationService(enabled=True, base_url=None, api_key=None, model="")
    presentation = service.build_presentation(question="统计2026年各区域发运量", result=_logistics_result())

    assert presentation is not None
    assert presentation.display_type == "narrative"
    assert presentation.table_spec is None
    assert presentation.chart_spec is None
    assert presentation.cards == []
    assert presentation.title != "查询结果"
    assert not any("本次返回" in item for item in presentation.highlights)
    assert presentation.caveat_items
    assert presentation.debug["presentation_source"] == "deterministic"
    assert "requested_display" in presentation.debug
    assert presentation.debug["final_display_type"] == presentation.display_type
    assert "fallback_reason" in presentation.debug


def test_logistics_ranking_narrative_describes_top_rows_with_values() -> None:
    """排名类叙事回答不能只给一句总计，应基于后端 rows 复述前五城市和值。"""

    rows = [
        {"城市": "徐州", "总运费": 1526425},
        {"城市": "太仓", "总运费": 236305},
        {"城市": "扬州", "总运费": 229064},
        {"城市": "淮安", "总运费": 201100},
        {"城市": "无锡", "总运费": 191499},
    ]
    result = LogisticsDataQaResult(
        answer_summary="2024年江苏总运费为3462229元。",
        result_table=LogisticsDataQaTable(columns=["城市", "总运费"], rows=rows),
        calculation_logic=["按城市维度汇总总运费，并按总运费降序返回前五。"],
        data_scope={"year": 2024, "province": "江苏省"},
        query_plan=LogisticsDataQaPlan(
            intent="fee_ranking",
            query_key="city_fee_topn",
            metrics=["总运费"],
            dimensions=["城市"],
            filters={"year": 2024, "province": "江苏省"},
            group_by=["城市"],
            sort=[{"field": "总运费", "direction": "desc"}],
            limit=5,
        ),
        status=LogisticsDataQaStatus(code="OK", message="查询成功", success=True),
    )
    service = LogisticsLlmAnswerPresentationService(enabled=True, base_url=None, api_key=None, model="")

    presentation = service.build_presentation(question="2024年江苏省各城市总费用排名前五？", result=result)

    assert presentation is not None
    assert presentation.display_type == "narrative"
    assert presentation.table_spec is None
    assert presentation.cards == []
    answer = presentation.answer
    compact_answer = answer.replace(",", "").replace(" ", "")
    assert len(answer) > len(result.answer_summary) + 80
    assert "按当前返回的排序" in answer or "依次" in answer
    for row in rows:
        assert f"{row['城市']}" in answer
        assert f"{row['总运费']}元" in compact_answer
    assert "query_key" not in answer and "SQL" not in answer and "planner" not in answer


def test_stream_prompt_encourages_rich_small_ranking_narrative() -> None:
    """流式表达提示词应允许排名/小表结果复述关键行，避免一句话潦草返回。"""

    system_prompt = BusinessAnswerStreamService._build_system_prompt("logistics")
    user_prompt = BusinessAnswerStreamService(enabled=True, base_url=None, api_key=None, model="")._build_user_prompt(
        "2024年江苏省各城市总费用排名前五？",
        {
            "answer_summary": "2024年江苏总运费为3462229元。",
            "result_table": {"columns": ["城市", "总运费"], "rows": [{"城市": "徐州", "总运费": 1526425}]},
        },
    )

    assert "排名" in system_prompt
    assert "逐项" in system_prompt
    assert "五行以内" in user_prompt
    assert "不要重复铺满所有行" not in user_prompt


def test_logistics_caveat_levels_do_not_treat_generic_other_bucket_text_as_danger() -> None:
    """普通区域兜底口径不应因“异常值归入其他”几个字被渲染为危险大块风险。"""

    result = _logistics_result()
    result.warnings = ["区域口径优先使用 delivery_area；为空时用 delivery_province 映射七大区域，异常值归入“其他”。"]
    service = LogisticsLlmAnswerPresentationService(enabled=True, base_url=None, api_key=None, model="")

    presentation = service.build_presentation(question="统计2026年各区域发运量", result=result)

    assert presentation is not None
    levels_by_text = {item.text: item.level for item in presentation.caveat_items}
    assert levels_by_text[result.warnings[0]] == "warning"


def test_logistics_answer_respects_explicit_visual_requests() -> None:
    """只有用户明确要求展示形式时，才返回对应的表格、图表或指标卡组件。"""

    service = LogisticsLlmAnswerPresentationService(enabled=True, base_url=None, api_key=None, model="")

    table = service.build_presentation(question="请用表格展示2026年各区域发运量", result=_logistics_result())
    chart = service.build_presentation(question="请用柱状图展示2026年各区域发运量", result=_logistics_result())
    cards = service.build_presentation(question="请用指标卡展示2026年发运量概览", result=_logistics_result(rows=[{"scope_label": "2026年", "shipment_mw": 208.7}]))

    assert table is not None and table.display_type == "table" and table.table_spec is not None
    assert table.chart_spec is None and table.cards == []
    assert chart is not None and chart.display_type == "bar_chart" and chart.chart_spec is not None
    assert chart.table_spec is None and chart.cards == []
    assert cards is not None and cards.display_type == "summary_cards" and cards.cards
    assert cards.table_spec is None and cards.chart_spec is None


def test_plan_bom_answer_defaults_to_text_only_but_keeps_raw_result_table() -> None:
    """计划 BOM 未明确要求表格时，presentation 只做文字回答，原始 result_table 仍保留给后续导出/追溯。"""

    service = PlanBomAnswerPresentationService(enabled=True, base_url=None, api_key=None, model="")
    response = _plan_bom_response("订单00104做功率预测")

    presentation = service.build_presentation(response)

    assert response.result_table.rows
    assert presentation.display_type == "narrative"
    assert presentation.table_spec is None


def test_plan_bom_answer_uses_table_only_when_user_requests_table() -> None:
    """计划 BOM 明确要求表格时，presentation 才携带 table_spec。"""

    service = PlanBomAnswerPresentationService(enabled=True, base_url=None, api_key=None, model="")
    response = _plan_bom_response("请用表格展示订单00104功率预测")

    presentation = service.build_presentation(response)

    assert presentation.display_type == "table"
    assert presentation.table_spec is not None
    assert presentation.table_spec.rows == response.result_table.rows


def test_plan_power_presentation_uses_deterministic_answer_even_when_llm_enabled() -> None:
    """计划 BOM 功率预测表达层启用 LLM 时，也必须保持确定性答案。"""

    response = _plan_bom_response("订单00104做功率预测")
    llm_payload = {
        "display_type": "narrative",
        "title": "功率预测结果",
        "answer": "查到了。订单00104中心功率为999W，预测比例为90%。",
        "highlights": ["中心功率 999W"],
        "caveats": ["按当前数据口径整理。"],
    }
    service = PlanBomAnswerPresentationService(
        enabled=True,
        base_url="http://llm.local",
        api_key="test-key",
        model="test-model",
        client=_FakeJsonClient(llm_payload),
    )

    presentation = service.build_presentation(response)

    assert "999" not in presentation.answer
    assert "90" not in presentation.answer
    assert "620W" in presentation.answer
    assert presentation.debug["presentation_source"] == "deterministic"
    assert presentation.debug["fallback_reason"] == "plan_power_deterministic_only"


def test_plan_bom_stream_prompt_uses_business_public_keys_only() -> None:
    """计划 BOM 流式 prompt 不应把 answer_summary/result_table/display_type/table_spec 等实现键交给表达层。"""

    response = _plan_bom_response("订单00104做功率预测")
    presentation_service = PlanBomAnswerPresentationService(enabled=True, base_url=None, api_key=None, model="")
    response.presentation = presentation_service.build_presentation(response)
    prompt = BusinessAnswerStreamService(enabled=True, base_url=None, api_key=None, model="")._build_user_prompt(
        response.question,
        response.model_dump(mode="json"),
    )

    for forbidden in ("answer_summary", "result_table", "display_type", "table_spec", "query_key", "raw_result"):
        assert forbidden not in prompt
    assert "业务结论" in prompt
    assert "结构化结果" in prompt
    assert "620W" in prompt


def test_stream_answer_yields_first_safe_llm_chunk_before_consuming_full_stream() -> None:
    """LLM 可用且首段安全时，应先把首段流给前端，而不是等完整模型输出结束。"""

    payload = _stream_payload()
    service = BusinessAnswerStreamService(
        enabled=True,
        base_url="http://llm.local",
        api_key="test-key",
        model="test-model",
        client=_ExplodingSecondEventClient(),
    )

    iterator = iter(
        service.stream_answer(
            domain="logistics",
            question="统计2026年各区域发运量",
            deterministic_payload=payload,
            fallback_answer=str(payload["answer_summary"]),
        )
    )

    assert next(iterator) == "查到了，"
    rest = "".join(iterator)
    assert "2026年发运量统计已完成" in rest
    assert service._last_stream_source == "deterministic_fallback"
    assert service._last_fallback_reason.startswith("llm_stream_error")


def _assert_no_plan_bom_visible_technical_terms(text: str) -> None:
    """断言计划 BOM 面向业务员的可见文案不暴露技术实现词。"""

    forbidden_terms = (
        "槽位",
        "字段",
        "order_id",
        "material_category",
        "raw_result",
        "query_key",
        "schema",
        "Guardrail",
        "guardrail",
        "LLM",
        "SQL",
        "planner",
    )
    assert not any(term in text for term in forbidden_terms), text


def test_plan_bom_clarification_presentation_uses_business_language_without_slot_fields() -> None:
    """计划 BOM 追问不能把槽位名、字段名或内部术语直接展示给业务员。"""

    service = PlanBomAnswerPresentationService(enabled=True, base_url=None, api_key=None, model="")
    response = PlanBomQaResponse(
        question="哪些订单的接线盒规格不一样，按订单列出来。",
        classification="B",
        status=PlanBomQaStatus(code="CLARIFICATION_REQUIRED", message="需要补充关键信息后继续查询", severity="warning"),
        nlu=PlanBomNluCandidate(
            question="哪些订单的接线盒规格不一样，按订单列出来。",
            intent="cross_order_material_compare",
            slots={},
            missing_slots=["order_id", "material_category"],
        ),
        answer_summary="当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。",
    )

    presentation = service.build_presentation(response)
    follow_up_questions = presentation.follow_up.get("questions", []) if presentation.follow_up else []
    visible_text = "\n".join([presentation.title, presentation.answer, *presentation.highlights, *presentation.caveats, *follow_up_questions])

    _assert_no_plan_bom_visible_technical_terms(visible_text)
    assert len(presentation.answer) >= 100
    assert "我先" in presentation.answer
    assert "再" in presentation.answer
    assert "最后" in presentation.answer
    assert "订单" in presentation.answer
    assert "材料" in presentation.answer or "接线盒" in presentation.answer


def test_plan_bom_success_presentation_contains_analysis_process_and_complete_small_result() -> None:
    """计划 BOM 已答结果不能只有一句话；小结果应说明查询过程并完整复述关键记录。"""

    service = PlanBomAnswerPresentationService(enabled=True, base_url=None, api_key=None, model="")
    response = PlanBomQaResponse(
        question="订单00104的玻璃和接线盒规格是什么？",
        classification="A",
        status=PlanBomQaStatus(code="OK", message="查询成功"),
        nlu=PlanBomNluCandidate(
            question="订单00104的玻璃和接线盒规格是什么？",
            intent="single_order_material_specs",
            slots={"order_tail_no": ["00104"], "material_category": ["玻璃", "接线盒"]},
        ),
        answer_summary="已查询订单00104的2条BOM材料规格。",
        result_table=PlanBomTableSpec(
            columns=["订单", "材料类别", "规格描述"],
            rows=[
                {"订单": "00104", "材料类别": "玻璃", "规格描述": "双玻 2.0mm"},
                {"订单": "00104", "材料类别": "接线盒", "规格描述": "三分体 线长 1200mm"},
            ],
        ),
    )

    presentation = service.build_presentation(response)

    _assert_no_plan_bom_visible_technical_terms("\n".join([presentation.answer, *presentation.caveats, *presentation.highlights]))
    assert len(presentation.answer) >= 120
    assert "我先" in presentation.answer
    assert "再" in presentation.answer
    assert "最后" in presentation.answer
    assert "玻璃" in presentation.answer and "双玻 2.0mm" in presentation.answer
    assert "接线盒" in presentation.answer and "三分体 线长 1200mm" in presentation.answer
    assert presentation.table_spec is None


def test_plan_bom_stream_fallback_uses_business_presentation_answer_and_chunks_it() -> None:
    """计划 BOM 流式兜底应输出业务化 presentation.answer，并按 chunk 动态返回。"""

    presentation_service = PlanBomAnswerPresentationService(enabled=True, base_url=None, api_key=None, model="")
    response = PlanBomQaResponse(
        question="哪些订单的接线盒规格不一样，按订单列出来。",
        classification="B",
        status=PlanBomQaStatus(code="CLARIFICATION_REQUIRED", message="需要补充关键信息后继续查询", severity="warning"),
        nlu=PlanBomNluCandidate(
            question="哪些订单的接线盒规格不一样，按订单列出来。",
            intent="cross_order_material_compare",
            slots={},
            missing_slots=["order_id", "material_category"],
        ),
        answer_summary="当前问题缺少或存在歧义的槽位：order_id, material_category。请补充订单、版本、材料或查询范围。",
    )
    response.presentation = presentation_service.build_presentation(response)
    payload = response.model_dump(mode="json")
    fallback = _resolve_plan_bom_stream_fallback_answer(payload)
    stream_service = BusinessAnswerStreamService(enabled=False, base_url=None, api_key=None, model="")

    chunks = list(
        stream_service.stream_answer(
            domain="plan_bom",
            question=response.question,
            deterministic_payload=payload,
            fallback_answer=fallback,
        )
    )
    streamed_answer = "".join(chunks)

    assert len(chunks) > 1
    assert streamed_answer == response.presentation.answer
    _assert_no_plan_bom_visible_technical_terms(streamed_answer)


def test_plan_bom_stream_fallback_rejects_raw_answer_summary_when_presentation_missing() -> None:
    """即使 presentation 缺失，计划 BOM 流式兜底也不能返回含槽位/字段的原始摘要。"""

    fallback = _resolve_plan_bom_stream_fallback_answer(
        {
            "answer_summary": "当前问题缺少或存在歧义的槽位：order_id, material_category。",
            "status": {"message": "需要补充关键信息后继续查询"},
        }
    )

    _assert_no_plan_bom_visible_technical_terms(fallback)
    assert fallback == "需要补充关键信息后继续查询"


def test_business_chat_frontend_does_not_fallback_to_raw_tables_for_narrative_presentation() -> None:
    """前端已有 presentation 时应尊重展示编排，不能因 raw result_table 存在而固定显示“明细数据”。"""

    page = "frontend/src/views/business-chat/BusinessChatPage.vue"
    with open(page, encoding="utf-8") as file:
        chat = file.read()

    assert "function resolvePresentationTable" in chat
    assert "function shouldShowPresentationChart" in chat
    assert "presentation?.table_spec || data.result_table || null" not in chat
    assert "v-if=\"shouldShowPresentationChart(message)\"" in chat
    assert "tableDisplayTypes.has(presentation.displayType)" in chat
    assert "cardDisplayTypes.has(presentation.displayType)" in chat


def test_streamed_answer_rejects_new_numbers_and_keeps_structured_fields() -> None:
    """LLM 流式表达新增确定性上下文外数值时，必须降级且不改结构化事实。"""

    payload = _stream_payload()
    fallback_answer = str(payload["answer_summary"])
    service = BusinessAnswerStreamService(
        enabled=True,
        base_url="http://llm.local",
        api_key="test-key",
        model="test-model",
        client=_FakeStreamClient(["华东 120.5MW，华南 88.2MW，另有华北 999MW。"]),
    )

    streamed_answer = "".join(
        service.stream_answer(
            domain="logistics",
            question="统计2026年各区域发运量",
            deterministic_payload=payload,
            fallback_answer=fallback_answer,
        )
    )
    final_payload = service.apply_streamed_answer(
        domain="logistics",
        deterministic_payload=payload,
        streamed_answer=streamed_answer,
    )

    assert streamed_answer == fallback_answer
    assert final_payload["presentation"]["answer"] == fallback_answer
    assert final_payload["result_table"] == payload["result_table"]
    assert final_payload["presentation"]["table_spec"] == payload["presentation"]["table_spec"]
    assert final_payload["presentation"]["debug"]["stream_answer_source"] == "deterministic_fallback"
    assert final_payload["presentation"]["debug"]["stream_fallback_reason"] == "stream_text_number_hallucination"


def test_stream_prompt_compact_payload_removes_internal_query_key() -> None:
    """给 LLM 的表达上下文应剔除 query_key/debug 等内部排查字段，降低泄露概率。"""

    payload = _stream_payload()
    service = BusinessAnswerStreamService(enabled=True, base_url=None, api_key=None, model="")

    prompt = service._build_user_prompt("统计2026年各区域发运量", payload)

    assert "query_key" not in prompt
    assert "query_plan" not in prompt
    assert "sys_region_mw" not in prompt
    assert "group_by" not in prompt
    assert "debug" not in prompt
    assert "trace_events" not in prompt
    assert "raw_result" not in prompt



def test_stream_prompt_compact_payload_removes_internal_table_and_caveat_strings() -> None:
    """即使内部字段混入表头/行值/口径文本，也不能进入 LLM prompt。"""

    payload = {
        "answer_summary": "查询完成。",
        "result_table": {
            "columns": ["region_name", "query_key", "group_by"],
            "rows": [{"region_name": "华东", "query_key": "sys_region_mw", "group_by": "region_name"}],
        },
        "warnings": ["planner 使用 query_plan group_by 调试信息", "正常业务口径"],
        "presentation": {
            "answer": "查询完成。",
            "caveats": ["SQL 调试字段不应发送给 LLM", "可展示口径"],
        },
    }
    service = BusinessAnswerStreamService(enabled=True, base_url=None, api_key=None, model="")

    prompt = service._build_user_prompt("统计各区域发运量", payload)

    assert "query_key" not in prompt
    assert "sys_region_mw" not in prompt
    assert "group_by" not in prompt
    assert "query_plan" not in prompt
    assert "planner" not in prompt
    assert "SQL" not in prompt
    assert "正常业务口径" in prompt
    assert "可展示口径" in prompt



def test_streamed_answer_rejects_numbers_only_present_in_query_plan() -> None:
    """流式数字白名单不能从 query_plan 等内部字段放行数字。"""

    payload = _stream_payload()
    payload["query_plan"] = {"filters": {"internal_limit": 999}}
    fallback_answer = str(payload["answer_summary"])
    service = BusinessAnswerStreamService(
        enabled=True,
        base_url="http://llm.local",
        api_key="test-key",
        model="test-model",
        client=_FakeStreamClient(["华东 999MW。"]),
    )

    streamed_answer = "".join(
        service.stream_answer(
            domain="logistics",
            question="统计2026年各区域发运量",
            deterministic_payload=payload,
            fallback_answer=fallback_answer,
        )
    )

    assert streamed_answer == fallback_answer
    assert service._last_fallback_reason == "stream_text_number_hallucination"



def test_streamed_answer_rejects_multi_entity_single_value_claim() -> None:
    """一个分句把多个实体都绑定到同一个行值时，应保守降级。"""

    payload = _stream_payload()
    fallback_answer = str(payload["answer_summary"])
    service = BusinessAnswerStreamService(
        enabled=True,
        base_url="http://llm.local",
        api_key="test-key",
        model="test-model",
        client=_FakeStreamClient(["华东和华南均为120.5MW。"]),
    )

    streamed_answer = "".join(
        service.stream_answer(
            domain="logistics",
            question="统计2026年各区域发运量",
            deterministic_payload=payload,
            fallback_answer=fallback_answer,
        )
    )

    assert streamed_answer == fallback_answer
    assert service._last_fallback_reason == "stream_structured_fact_mismatch"



def test_streamed_answer_rejects_numeric_entity_multi_entity_single_value_claim() -> None:
    """带数字实体的“均为同一比例”错配也要降级。"""

    payload = {
        "answer_summary": "功率档预测比例已完成，620W 为60%，625W 为40%。",
        "result_table": {
            "columns": ["功率档", "预测比例"],
            "rows": [
                {"功率档": "620W", "预测比例": "60%"},
                {"功率档": "625W", "预测比例": "40%"},
            ],
        },
        "presentation": {"answer": "功率档预测比例已完成，620W 为60%，625W 为40%。"},
    }
    fallback_answer = str(payload["answer_summary"])
    service = BusinessAnswerStreamService(
        enabled=True,
        base_url="http://llm.local",
        api_key="test-key",
        model="test-model",
        client=_FakeStreamClient(["620W和625W均为40%。"]),
    )

    streamed_answer = "".join(
        service.stream_answer(
            domain="plan_bom",
            question="功率档预测比例",
            deterministic_payload=payload,
            fallback_answer=fallback_answer,
        )
    )

    assert streamed_answer == fallback_answer
    assert service._last_fallback_reason == "stream_structured_fact_mismatch"



def test_streamed_answer_rejects_structured_row_fact_mismatch() -> None:
    """LLM 把结构化行里的名称和值错配时，即使数字合法，也必须降级。"""

    payload = _stream_payload()
    fallback_answer = str(payload["answer_summary"])
    service = BusinessAnswerStreamService(
        enabled=True,
        base_url="http://llm.local",
        api_key="test-key",
        model="test-model",
        client=_FakeStreamClient(["华北 120.5MW，华南 88.2MW。"]),
    )

    streamed_answer = "".join(
        service.stream_answer(
            domain="logistics",
            question="统计2026年各区域发运量",
            deterministic_payload=payload,
            fallback_answer=fallback_answer,
        )
    )
    final_payload = service.apply_streamed_answer(
        domain="logistics",
        deterministic_payload=payload,
        streamed_answer=streamed_answer,
    )

    assert streamed_answer == fallback_answer
    assert final_payload["presentation"]["answer"] == fallback_answer
    assert final_payload["presentation"]["debug"]["stream_answer_source"] == "deterministic_fallback"
    assert final_payload["presentation"]["debug"]["stream_fallback_reason"] == "stream_structured_fact_mismatch"



def test_streamed_answer_rejects_swapped_row_values_in_same_sentence() -> None:
    """LLM 在同一句里把两个已有行的名称和值互换时，也必须降级。"""

    payload = _stream_payload()
    fallback_answer = str(payload["answer_summary"])
    service = BusinessAnswerStreamService(
        enabled=True,
        base_url="http://llm.local",
        api_key="test-key",
        model="test-model",
        client=_FakeStreamClient(["华南 120.5MW，华东 88.2MW。"]),
    )

    streamed_answer = "".join(
        service.stream_answer(
            domain="logistics",
            question="统计2026年各区域发运量",
            deterministic_payload=payload,
            fallback_answer=fallback_answer,
        )
    )

    assert streamed_answer == fallback_answer
    assert service._last_fallback_reason == "stream_structured_fact_mismatch"



def test_streamed_answer_rejects_numeric_entity_value_swap() -> None:
    """功率档/订单号这类带数字的实体也要参与绑定校验，不能被 LLM 对调。"""

    payload = {
        "answer_summary": "功率档预测比例已完成，620W 为60%，625W 为40%。",
        "result_table": {
            "columns": ["功率档", "预测比例"],
            "rows": [
                {"功率档": "620W", "预测比例": "60%"},
                {"功率档": "625W", "预测比例": "40%"},
            ],
        },
        "presentation": {"answer": "功率档预测比例已完成，620W 为60%，625W 为40%。"},
    }
    fallback_answer = str(payload["answer_summary"])
    service = BusinessAnswerStreamService(
        enabled=True,
        base_url="http://llm.local",
        api_key="test-key",
        model="test-model",
        client=_FakeStreamClient(["620W 为40%，625W 为60%。"]),
    )

    streamed_answer = "".join(
        service.stream_answer(
            domain="plan_bom",
            question="功率档预测比例",
            deterministic_payload=payload,
            fallback_answer=fallback_answer,
        )
    )

    assert streamed_answer == fallback_answer
    assert service._last_fallback_reason == "stream_structured_fact_mismatch"



def test_streamed_answer_rejects_respectively_style_row_swap() -> None:
    """LLM 用“分别”把多个实体和值放同一句时，无法安全证明绑定关系，应降级。"""

    payload = _stream_payload()
    fallback_answer = str(payload["answer_summary"])
    service = BusinessAnswerStreamService(
        enabled=True,
        base_url="http://llm.local",
        api_key="test-key",
        model="test-model",
        client=_FakeStreamClient(["华南和华东分别为120.5MW和88.2MW。"]),
    )

    streamed_answer = "".join(
        service.stream_answer(
            domain="logistics",
            question="统计2026年各区域发运量",
            deterministic_payload=payload,
            fallback_answer=fallback_answer,
        )
    )

    assert streamed_answer == fallback_answer
    assert service._last_fallback_reason == "stream_structured_fact_mismatch"



def test_streamed_answer_rejects_numeric_entity_respectively_style_swap() -> None:
    """带数字实体也不能用“分别”句式绕过行绑定校验。"""

    payload = {
        "answer_summary": "功率档预测比例已完成，620W 为60%，625W 为40%。",
        "result_table": {
            "columns": ["功率档", "预测比例"],
            "rows": [
                {"功率档": "620W", "预测比例": "60%"},
                {"功率档": "625W", "预测比例": "40%"},
            ],
        },
        "presentation": {"answer": "功率档预测比例已完成，620W 为60%，625W 为40%。"},
    }
    fallback_answer = str(payload["answer_summary"])
    service = BusinessAnswerStreamService(
        enabled=True,
        base_url="http://llm.local",
        api_key="test-key",
        model="test-model",
        client=_FakeStreamClient(["620W和625W分别为40%和60%。"]),
    )

    streamed_answer = "".join(
        service.stream_answer(
            domain="plan_bom",
            question="功率档预测比例",
            deterministic_payload=payload,
            fallback_answer=fallback_answer,
        )
    )

    assert streamed_answer == fallback_answer
    assert service._last_fallback_reason == "stream_structured_fact_mismatch"



def test_streamed_answer_rejects_metric_column_with_incidental_id_substring_swap() -> None:
    """paid_amount 这类指标字段不能因包含 id 子串被误判成实体字段。"""

    payload = {
        "answer_summary": "区域金额统计已完成，华东 120.5元，华南 88.2元。",
        "result_table": {
            "columns": ["region_name", "paid_amount"],
            "rows": [
                {"region_name": "华东", "paid_amount": 120.5},
                {"region_name": "华南", "paid_amount": 88.2},
            ],
        },
        "presentation": {"answer": "区域金额统计已完成，华东 120.5元，华南 88.2元。"},
    }
    fallback_answer = str(payload["answer_summary"])
    service = BusinessAnswerStreamService(
        enabled=True,
        base_url="http://llm.local",
        api_key="test-key",
        model="test-model",
        client=_FakeStreamClient(["华南 120.5元，华东 88.2元。"]),
    )

    streamed_answer = "".join(
        service.stream_answer(
            domain="logistics",
            question="统计各区域金额",
            deterministic_payload=payload,
            fallback_answer=fallback_answer,
        )
    )

    assert streamed_answer == fallback_answer
    assert service._last_fallback_reason == "stream_structured_fact_mismatch"



def test_deterministic_fallback_text_with_technical_leak_is_sanitized_before_streaming() -> None:
    """即使确定性兜底文本异常携带内部字段，也不能原样流给前端。"""

    payload = _stream_payload()
    leaky_answer = "planner 命中 query_key=sys_region_mw，SQL 来自 dws_logistics_detail_union。"
    payload["answer_summary"] = leaky_answer
    payload["presentation"]["answer"] = leaky_answer
    service = BusinessAnswerStreamService(enabled=False, base_url=None, api_key=None, model="")

    streamed_answer = "".join(
        service.stream_answer(
            domain="logistics",
            question="统计2026年各区域发运量",
            deterministic_payload=payload,
            fallback_answer=leaky_answer,
        )
    )

    assert streamed_answer == "查询成功"
    assert "query_key" not in streamed_answer
    assert "SQL" not in streamed_answer
    assert "planner" not in streamed_answer



def test_apply_streamed_answer_does_not_bypass_validation_for_leaky_fallback_text() -> None:
    """候选文本等于原始 leaky fallback 时，也必须写回安全兜底。"""

    payload = _stream_payload()
    leaky_answer = "planner 命中 query_key=sys_region_mw，SQL 来自 dws_logistics_detail_union。"
    payload["answer_summary"] = leaky_answer
    payload["presentation"]["answer"] = leaky_answer
    service = BusinessAnswerStreamService(enabled=True, base_url=None, api_key=None, model="")

    final_payload = service.apply_streamed_answer(
        domain="logistics",
        deterministic_payload=payload,
        streamed_answer=leaky_answer,
    )

    assert final_payload["presentation"]["answer"] == "查询成功"
    assert "query_key" not in final_payload["presentation"]["answer"]
    assert final_payload["presentation"]["debug"]["stream_answer_source"] == "deterministic_fallback"
    assert final_payload["presentation"]["debug"]["stream_fallback_reason"] == "stream_technical_visible_leak"



def test_streamed_answer_rejects_visible_technical_leaks() -> None:
    """LLM 流式表达暴露 SQL、query_key、planner 或数仓表名时，必须降级到确定性答案。"""

    payload = _stream_payload()
    fallback_answer = str(payload["answer_summary"])
    service = BusinessAnswerStreamService(
        enabled=True,
        base_url="http://llm.local",
        api_key="test-key",
        model="test-model",
        client=_FakeStreamClient(["planner 命中 query_key=sys_region_mw，SQL 来自 dws_logistics_detail_union。"]),
    )

    streamed_answer = "".join(
        service.stream_answer(
            domain="logistics",
            question="统计2026年各区域发运量",
            deterministic_payload=payload,
            fallback_answer=fallback_answer,
        )
    )
    final_payload = service.apply_streamed_answer(
        domain="logistics",
        deterministic_payload=payload,
        streamed_answer=streamed_answer,
    )

    assert streamed_answer == fallback_answer
    assert final_payload["presentation"]["answer"] == fallback_answer
    assert final_payload["presentation"]["debug"]["stream_answer_source"] == "deterministic_fallback"
    assert final_payload["presentation"]["debug"]["stream_fallback_reason"] == "stream_technical_visible_leak"


def test_business_chat_frontend_uses_caveat_levels_secondary_actions_and_stream_stages() -> None:
    """前端主回答应以 answer 为主，并把口径、明细和导出放到二级动作中。"""

    page = "frontend/src/views/business-chat/BusinessChatPage.vue"
    with open(page, encoding="utf-8") as file:
        chat = file.read()
    template = chat.split("<script setup", 1)[0]

    assert "caveatItems" in chat
    assert "data-testid=\"answer-secondary-actions\"" in template
    assert "查看数据依据" in template
    assert "展开明细" in template
    assert "getAssistantAuditTable" in chat
    assert "result-caveats--info" in chat
    assert "result-caveats--warning" in chat
    assert "result-caveats--danger" in chat
    assert "function resolveLoadingText" in chat
    assert "function updateAssistantStreamMeta" in chat
    assert "正在理解问题" in chat
    assert "正在查询数据" in chat
    assert "正在组织回答" in chat
    assert "正在生成回答" in chat
    assert "onMeta:" in chat
    assert "rawResponse?.query_plan" not in chat
    assert "rawResponse?.presentation?.debug" not in chat


def test_business_chat_session_keeps_only_safe_audit_table_for_secondary_actions() -> None:
    """会话持久化不能丢失明细依据，但只能白名单保留 result_table，避免暴露 query_key/debug。"""

    page = "frontend/src/utils/businessChatSessions.ts"
    with open(page, encoding="utf-8") as file:
        sessions = file.read()

    assert "rawResponse: normalizeMessageRawResponse(raw.rawResponse)" in sessions
    assert "presentation: normalizeMessagePresentation(raw.presentation)" in sessions
    assert "function normalizeMessagePresentation" in sessions
    assert "function normalizeMessageRawResponse" in sessions
    assert "result_table: safeResultTable" in sessions
    assert "query_plan" not in sessions
    assert "presentation?.debug" not in sessions
    assert "presentation: raw.presentation &&" not in sessions
    assert "rawResponse: null" not in sessions


def test_business_chat_frontend_caveat_items_guard_old_payloads() -> None:
    """旧会话或旧服务端 payload 没有 caveatItems 时，前端应回落到 caveats 而不是读取 undefined.length。"""

    page = "frontend/src/views/business-chat/BusinessChatPage.vue"
    with open(page, encoding="utf-8") as file:
        chat = file.read()

    assert "Array.isArray(presentation.caveatItems)" in chat
    assert "presentation.caveatItems.length ? presentation.caveatItems" not in chat

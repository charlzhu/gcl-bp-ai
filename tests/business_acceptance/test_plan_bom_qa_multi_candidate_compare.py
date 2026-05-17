from __future__ import annotations

import json
import re

import pytest

from backend.app.db.session import SessionLocal
from backend.app.domains.plan_bom.models import PlanBomHeader
from backend.app.domains.plan_bom.repositories.query_repository import PlanBomQueryRepository
from backend.app.domains.plan_bom.schemas.qa import PlanBomNluCandidate
from backend.app.domains.plan_bom.schemas.query import PlanBomCandidate, PlanBomCompareResponse, PlanBomStatus
from backend.app.domains.plan_bom.services.answer_presentation_service import PlanBomAnswerPresentationService
from backend.app.domains.plan_bom.services.nlu_center_service import PlanBomNluCenterService
from backend.app.domains.plan_bom.services.qa_service import PlanBomQaService
from backend.app.domains.plan_bom.services.query_service import PlanBomQueryService


@pytest.fixture()
def live_db_session():
    """连接当前项目真实 BOM 数据库，用真实订单尾号复现多候选 compare 问题。"""
    session = SessionLocal()
    try:
        try:
            session.query(PlanBomHeader).limit(1).all()
        except Exception as exc:  # pragma: no cover - 本地无验收库时跳过。
            pytest.skip(f"当前环境无法连接真实 BOM 数据库，跳过计划 BOM compare 验收：{exc}")
        yield session
    finally:
        session.close()


@pytest.fixture()
def qa_service(live_db_session) -> PlanBomQaService:
    """构造关闭 LLM 的计划 BOM QA 服务，只验证确定性 NLU + 查询链路。"""
    repository = PlanBomQueryRepository(live_db_session)
    return PlanBomQaService(
        repository=repository,
        query_service=PlanBomQueryService(repository=repository),
        nlu_service=PlanBomNluCenterService(repository=repository, base_url="", api_key="", model=""),
        presentation_service=PlanBomAnswerPresentationService(enabled=False, base_url="", api_key="", model=""),
    )


class _FakeLlmClient:
    """测试用 OpenAI 兼容客户端，模拟 LLM 返回受控 NLU JSON。"""

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls = 0
        self.chat = self
        self.completions = self

    def create(self, **_: object):
        """返回最小 completion 对象，避免测试访问真实 LLM。"""
        self.calls += 1
        message = type("Message", (), {"content": json.dumps(self.payload, ensure_ascii=False)})()
        choice = type("Choice", (), {"message": message})()
        return type("Completion", (), {"choices": [choice]})()


def _qa_service_with_llm(live_db_session, payload: dict[str, object]) -> tuple[PlanBomQaService, _FakeLlmClient]:
    """构造开启伪 LLM 的 QA 服务，用于验证 LLM 合并 Guardrail。"""
    repository = PlanBomQueryRepository(live_db_session)
    fake_client = _FakeLlmClient(payload)
    service = PlanBomQaService(
        repository=repository,
        query_service=PlanBomQueryService(repository=repository),
        nlu_service=PlanBomNluCenterService(
            repository=repository,
            base_url="http://llm.invalid",
            api_key="k",
            model="test-model",
            client=fake_client,
        ),
        presentation_service=PlanBomAnswerPresentationService(enabled=False, base_url="", api_key="", model=""),
    )
    return service, fake_client


def _require_tail_headers(session, tail: str) -> list[PlanBomHeader]:
    """读取真实库中包含指定尾号的有效 BOM 头；不存在时跳过而不是伪造数据。"""
    headers = (
        session.query(PlanBomHeader)
        .filter(PlanBomHeader.is_active == 1, PlanBomHeader.order_no.contains(tail))
        .order_by(PlanBomHeader.order_no.asc(), PlanBomHeader.order_name.asc(), PlanBomHeader.version_no.asc())
        .all()
    )
    if not headers:
        pytest.skip(f"当前真实 BOM 数据缺少订单尾号 {tail}，无法复现本次业务问题。")
    return headers


def _require_another_existing_tail(session, excluded_tail: str) -> str:
    """从真实库里找一个不同于 excluded_tail 的有效尾号，避免测试只绑定单个样例号。"""
    headers = (
        session.query(PlanBomHeader)
        .filter(PlanBomHeader.is_active == 1, PlanBomHeader.order_no.isnot(None))
        .order_by(PlanBomHeader.order_no.asc())
        .limit(200)
        .all()
    )
    for header in headers:
        match = re.search(r"(\d{5})$", str(header.order_no or ""))
        if match and match.group(1) != excluded_tail:
            return match.group(1)
    pytest.skip("当前真实 BOM 数据没有第二个有效订单尾号，无法验证 LLM 注入/替换订单保护。")


def test_table_compare_expands_multi_candidate_order_tail_without_clarification(live_db_session, qa_service) -> None:
    """两个订单尾号做规格差异表时，多业务实例尾号应全部展开对比，而不是追问内部 order_identity。"""
    _require_tail_headers(live_db_session, "00067")
    right_headers = _require_tail_headers(live_db_session, "00106")
    if len({header.order_identity_key for header in right_headers}) < 2:
        pytest.skip("当前真实 BOM 数据中的 00106 未形成多业务实例候选，无法复现本次缺陷。")

    response = qa_service.ask(
        "订单00067和订单00106玻璃、间隙贴膜、焊带、汇流条、接线盒的规格描述有什么不一样，并用表格统计出来",
        use_llm=False,
    )

    assert response.classification == "A"
    assert response.status.code == "OK"
    assert response.nlu.intent == "cross_order_material_compare"
    assert "order_identity" not in response.nlu.missing_slots
    assert response.result_table.rows
    assert {"compare_pair", "left_instance", "right_instance", "left_description", "right_description"}.issubset(
        set(response.result_table.columns)
    )
    assert response.raw_result.get("expanded_compare") is True
    assert response.raw_result.get("right_candidate_count", 0) >= 2
    assert len(response.raw_result.get("compared_pairs") or []) >= 2


def test_single_ambiguous_order_tail_still_requires_business_instance_confirmation(qa_service, live_db_session) -> None:
    """单订单查询没有对比展开语义时，仍需确认业务实例，避免静默选错候选。"""
    right_headers = _require_tail_headers(live_db_session, "00106")
    if len({header.order_identity_key for header in right_headers}) < 2:
        pytest.skip("当前真实 BOM 数据中的 00106 未形成多业务实例候选，无法验证单订单保护。")

    response = qa_service.ask("订单00106玻璃规格描述是什么", use_llm=False)

    assert response.classification == "B"
    assert response.status.code == "CLARIFICATION_REQUIRED"
    assert response.result_table.rows == []
    assert any(slot in response.nlu.missing_slots for slot in ("order_identity", "candidate"))


def test_existing_order_material_table_without_order_tail_defaults_to_all_orders(qa_service) -> None:
    """业务员只说“现有订单”时应按全部当前订单生成材料表，不要求补订单号。"""
    response = qa_service.ask(
        "针对现有的订单把玻璃，焊带，汇流条，间隙贴膜线盒的规格并用表格的形式呈现",
        use_llm=False,
    )

    assert response.classification == "A"
    assert response.status.code == "OK"
    assert response.nlu.intent == "multi_order_material_table"
    assert "order_id" not in response.nlu.missing_slots
    assert "compare_orders" not in response.nlu.missing_slots
    assert response.result_table.rows
    assert "请补充" not in response.answer_summary
    assert response.raw_result.get("selected_headers_count", 0) > 1


def test_all_order_material_table_without_order_tail_does_not_require_compare_orders(qa_service) -> None:
    """“所有订单/全部订单”是明确范围，不应被误判成需要两个对比订单。"""
    response = qa_service.ask("所有订单的玻璃规格列成表格", use_llm=False)

    assert response.classification == "A"
    assert response.status.code == "OK"
    assert response.nlu.intent == "multi_order_material_table"
    assert "order_id" not in response.nlu.missing_slots
    assert "compare_orders" not in response.nlu.missing_slots
    assert response.result_table.rows


def test_scope_word_with_explicit_ambiguous_order_tail_still_requires_instance_confirmation(qa_service, live_db_session) -> None:
    """“当前订单/现有订单”若同时给出尾号，仍按该订单消歧，不能被放宽成全订单查询。"""
    right_headers = _require_tail_headers(live_db_session, "00106")
    if len({header.order_identity_key for header in right_headers}) < 2:
        pytest.skip("当前真实 BOM 数据中的 00106 未形成多业务实例候选，无法验证 scope 词保护。")

    response = qa_service.ask("当前订单00106玻璃规格描述是什么", use_llm=False)

    assert response.classification == "B"
    assert response.status.code == "CLARIFICATION_REQUIRED"
    assert response.result_table.rows == []
    assert any(slot in response.nlu.missing_slots for slot in ("order_identity", "candidate"))


def test_llm_cannot_rewrite_single_ambiguous_tail_to_multi_order_table(live_db_session) -> None:
    """生产默认 use_llm=True 时，LLM 不能把单尾号歧义问题改写成多订单清单绕过确认。"""
    right_headers = _require_tail_headers(live_db_session, "00106")
    if len({header.order_identity_key for header in right_headers}) < 2:
        pytest.skip("当前真实 BOM 数据中的 00106 未形成多业务实例候选，无法验证 LLM 合并保护。")
    service, fake_client = _qa_service_with_llm(
        live_db_session,
        {
            "intent_candidate": "multi_order_material_table",
            "slot_candidate": {"order_tail_no": ["00106"], "material_category": ["glass"]},
            "confidence": 0.95,
        },
    )

    response = service.ask("当前订单00106玻璃规格清单", use_llm=True)

    assert fake_client.calls == 1
    assert response.classification == "B"
    assert response.status.code == "CLARIFICATION_REQUIRED"
    assert response.result_table.rows == []
    assert response.nlu.intent == "single_order_material_specs"
    assert any(slot in response.nlu.missing_slots for slot in ("order_identity", "candidate"))


def test_llm_cannot_erase_missing_order_for_generic_material_question(live_db_session) -> None:
    """没有订单号也没有全订单范围词时，LLM 不能用多订单意图清空 order_id 缺槽。"""
    service, fake_client = _qa_service_with_llm(
        live_db_session,
        {
            "intent_candidate": "multi_order_material_table",
            "slot_candidate": {"material_category": ["glass"]},
            "confidence": 0.95,
        },
    )

    response = service.ask("玻璃规格描述是什么", use_llm=True)

    assert fake_client.calls == 1
    assert response.classification == "B"
    assert response.status.code == "CLARIFICATION_REQUIRED"
    assert "order_id" in response.nlu.missing_slots
    assert response.result_table.rows == []


def test_llm_batch_export_cannot_bypass_single_ambiguous_tail_confirmation(live_db_session) -> None:
    """LLM 即使返回批量导表意图，也不能把单尾号歧义订单展开成全候选清单。"""
    right_headers = _require_tail_headers(live_db_session, "00106")
    if len({header.order_identity_key for header in right_headers}) < 2:
        pytest.skip("当前真实 BOM 数据中的 00106 未形成多业务实例候选，无法验证批量导表保护。")
    service, fake_client = _qa_service_with_llm(
        live_db_session,
        {
            "intent_candidate": "batch_export_table",
            "slot_candidate": {"order_tail_no": ["00106"], "material_category": ["glass"]},
            "confidence": 0.95,
        },
    )

    response = service.ask("当前订单00106玻璃规格清单", use_llm=True)

    assert fake_client.calls == 1
    assert response.classification == "B"
    assert response.status.code == "CLARIFICATION_REQUIRED"
    assert response.result_table.rows == []
    assert response.nlu.intent == "single_order_material_specs"
    assert any(slot in response.nlu.missing_slots for slot in ("order_identity", "candidate"))


def test_llm_cannot_inject_second_tail_into_single_tail_question(live_db_session) -> None:
    """LLM 不能给单尾号问题额外塞入第二个真实尾号来伪造成多订单清单。"""
    source_tail = "00106"
    right_headers = _require_tail_headers(live_db_session, source_tail)
    if len({header.order_identity_key for header in right_headers}) < 2:
        pytest.skip("当前真实 BOM 数据中的 00106 未形成多业务实例候选，无法验证 LLM 注入订单保护。")
    injected_tail = _require_another_existing_tail(live_db_session, source_tail)
    service, fake_client = _qa_service_with_llm(
        live_db_session,
        {
            "intent_candidate": "multi_order_material_table",
            "slot_candidate": {"order_tail_no": [source_tail, injected_tail], "material_category": ["glass"]},
            "confidence": 0.95,
        },
    )

    response = service.ask(f"当前订单{source_tail}玻璃规格清单", use_llm=True)

    assert fake_client.calls == 1
    assert response.classification == "B"
    assert response.status.code == "CLARIFICATION_REQUIRED"
    assert response.result_table.rows == []
    assert response.nlu.slots.get("order_tail_no") == [source_tail]
    assert response.nlu.intent == "single_order_material_specs"
    assert any(slot in response.nlu.missing_slots for slot in ("order_identity", "candidate"))


def test_llm_cannot_replace_explicit_tail_with_another_existing_tail(live_db_session) -> None:
    """LLM 不能把用户原文里的尾号替换成另一个真实订单尾号。"""
    source_tail = "00106"
    right_headers = _require_tail_headers(live_db_session, source_tail)
    if len({header.order_identity_key for header in right_headers}) < 2:
        pytest.skip("当前真实 BOM 数据中的 00106 未形成多业务实例候选，无法验证 LLM 替换订单保护。")
    injected_tail = _require_another_existing_tail(live_db_session, source_tail)
    service, fake_client = _qa_service_with_llm(
        live_db_session,
        {
            "intent_candidate": "single_order_material_specs",
            "slot_candidate": {"order_tail_no": [injected_tail], "material_category": ["glass"]},
            "confidence": 0.95,
        },
    )

    response = service.ask(f"当前订单{source_tail}玻璃规格清单", use_llm=True)

    assert fake_client.calls == 1
    assert response.classification == "B"
    assert response.status.code == "CLARIFICATION_REQUIRED"
    assert response.result_table.rows == []
    assert response.nlu.slots.get("order_tail_no") == [source_tail]
    assert response.nlu.intent == "single_order_material_specs"
    assert any(slot in response.nlu.missing_slots for slot in ("order_identity", "candidate"))


def test_truncated_compare_candidate_list_is_not_partially_expanded() -> None:
    """候选被截断时不能只展开前 N 个候选，否则会把不完整对比伪装成完整答案。"""
    nlu = PlanBomNluCandidate(
        question="订单A和订单B玻璃规格描述有什么不一样",
        intent="cross_order_material_compare",
        slots={"order_tail_no": ["00001", "00002"]},
        missing_slots=[],
        confidence=1.0,
    )
    candidate = PlanBomCandidate(
        order_identity_key="identity-1",
        file_instance_key="file-1",
        order_no="GCL-TEST-00002",
        order_display_label="测试客户-00002",
        order_name="测试客户-00002",
        version_no="A0",
        effective_date="2026-01-01",
        source_type="EXCEL",
        source_tag="fixture",
        match_reason="order_no_like",
    )
    candidate_result = PlanBomCompareResponse(
        query_type="plan_bom_candidate_list",
        domain="plan_bom",
        execution_mode="direct",
        status=PlanBomStatus(
            code="CANDIDATE_REQUIRED",
            message="right 侧命中多个业务实例，请先选择。",
            severity="warning",
            extras={"candidate_truncated": True},
        ),
        result_explanation={},
        response_meta={"candidate_truncated": True},
        candidate_scope="order_identity",
        candidate_side="right",
        candidates=[candidate],
        candidate_total_hint=21,
        compare_ready=False,
    )

    assert (
        PlanBomQaService._can_expand_compare_candidates(
            nlu=nlu,
            candidate_result=candidate_result,
            candidates=candidate_result.candidates,
        )
        is False
    )

from __future__ import annotations

import json

import pytest

from backend.app.db.session import SessionLocal
from backend.app.domains.plan_bom.models import PlanBomHeader, PlanPowerModelVersion
from backend.app.domains.plan_bom.repositories.query_repository import PlanBomQueryRepository
from backend.app.domains.plan_bom.services.answer_presentation_service import PlanBomAnswerPresentationService
from backend.app.domains.plan_bom.services.nlu_center_service import PlanBomNluCenterService
from backend.app.domains.plan_bom.services.power_config_resolver_service import RESOLVED_STATUS, PlanBomPowerConfigResolverService
from backend.app.domains.plan_bom.services.power_prediction_engine import PowerPredictionEngine
from backend.app.domains.plan_bom.services.power_recommendation_service import PowerRecommendationService
from backend.app.domains.plan_bom.services.qa_service import PlanBomQaService
from backend.app.domains.plan_bom.services.query_service import PlanBomQueryService


@pytest.fixture()
def live_db_session():
    """连接当前项目真实数据库，供 M5 验收从真实 BOM 与 active 功率模型中动态抽题。"""
    session = SessionLocal()
    try:
        try:
            session.query(PlanBomHeader).limit(1).all()
        except Exception as exc:  # pragma: no cover - 仅用于缺少本地验收库时跳过。
            pytest.skip(f"当前环境无法连接真实 BOM 数据库，跳过 M5 真实数据验收：{exc}")
        if session.query(PlanPowerModelVersion).filter_by(is_active=1).first() is None:
            pytest.skip("当前数据库没有 active 功率模型版本，无法执行 M5 验收。")
        yield session
    finally:
        session.close()


@pytest.fixture()
def qa_service(live_db_session) -> PlanBomQaService:
    """构造关闭 LLM 表达的 QA 服务，保证 M5 测试只验证确定性链路。"""
    repository = PlanBomQueryRepository(live_db_session)
    engine = PowerPredictionEngine(live_db_session)
    return PlanBomQaService(
        repository=repository,
        query_service=PlanBomQueryService(repository=repository),
        nlu_service=PlanBomNluCenterService(repository=repository, base_url="", api_key="", model=""),
        presentation_service=PlanBomAnswerPresentationService(enabled=False, base_url="", api_key="", model=""),
        power_config_resolver=PlanBomPowerConfigResolverService(live_db_session, repository=repository),
        power_prediction_engine=engine,
        power_recommendation_service=PowerRecommendationService(live_db_session, engine=engine),
    )


def _resolved_order_tail(session) -> tuple[str, object, object]:
    """从真实 BOM 中动态寻找一条通过自然语言订单尾号也能唯一解析的订单。"""
    resolver = PlanBomPowerConfigResolverService(session)
    headers = session.query(PlanBomHeader).filter_by(is_active=1).order_by(PlanBomHeader.id.asc()).all()
    for header in headers:
        tail = header.order_no[-5:] if header.order_no else ""
        if not tail:
            continue
        result = resolver.resolve(order_no=tail)
        required = {"model_code", "glass", "ribbon", "busbar", "cable", "cell_size", "supplier", "benchmark"}
        if result.status == RESOLVED_STATUS and required.issubset(result.resolved_config):
            return tail, header, result
    pytest.fail("当前真实 BOM 数据中未找到可通过自然语言订单尾号唯一映射并预测的订单。")


def _target_ratio_from_prediction(prediction) -> dict[str, float]:
    """从真实预测分布中抽两个有效功率档作为推荐目标比例。"""
    bins = [key for key, value in prediction.weighted_distribution.items() if value >= 0]
    if len(bins) < 2:
        pytest.skip("当前 active 功率模型有效功率档不足两个，跳过推荐问答验收。")
    return {bins[0]: 0.5, bins[1]: 0.5}


class _FakeLlmClient:
    """测试用 OpenAI 兼容客户端，记录是否真的发生 LLM 调用。"""

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls = 0
        self.chat = self
        self.completions = self

    def create(self, **_: object):
        """返回最小 completion 对象，模拟 LLM JSON 输出。"""
        self.calls += 1
        message = type("Message", (), {"content": json.dumps(self.payload, ensure_ascii=False)})()
        choice = type("Choice", (), {"message": message})()
        return type("Completion", (), {"choices": [choice]})()


def test_plan_bom_qa_answers_power_prediction_for_real_order(live_db_session, qa_service) -> None:
    """计划 BOM QA 应能把功率预测问题串联到 M4 配置解析和 M3 确定性预测。"""
    tail, _, _ = _resolved_order_tail(live_db_session)

    response = qa_service.ask(f"订单{tail}做功率预测，给出功率档分布", use_llm=False)

    assert response.classification == "A"
    assert response.status.code == "OK"
    assert response.nlu.intent == "plan_power_prediction"
    assert response.raw_result["bom_config_resolution"]["status"] == RESOLVED_STATUS
    assert response.raw_result["power_prediction"]["center_power"] > 0
    assert response.raw_result["power_prediction"]["weighted_distribution"]
    assert response.result_table.rows
    assert {"功率档", "预测比例"}.issubset(set(response.result_table.columns))
    assert response.presentation is not None
    assert response.presentation.table_spec is not None


def test_plan_bom_qa_recommends_suppliers_by_target_ratio(live_db_session, qa_service) -> None:
    """用户给出目标功率比例时，QA 应调用 M3 推荐服务并返回供应商匹配度。"""
    tail, _, resolved = _resolved_order_tail(live_db_session)
    prediction = PowerPredictionEngine(live_db_session).predict(
        model_code=resolved.model_code,
        configuration=resolved.to_prediction_configuration(),
    )
    target = _target_ratio_from_prediction(prediction)
    bins = list(target)

    response = qa_service.ask(f"订单{tail}目标{bins[0]}W 50%，{bins[1]}W 50%，推荐供应商", use_llm=False)

    assert response.classification == "A"
    assert response.status.code == "OK"
    assert response.nlu.intent == "plan_power_supplier_recommendation"
    assert response.nlu.slots["target_power_ratio"]
    recommendation = response.raw_result["power_recommendation"]
    assert recommendation["recommendations"]
    assert response.result_table.rows
    assert {"供应商", "匹配度"}.issubset(set(response.result_table.columns))


def test_plan_bom_qa_accepts_explicit_supplier_for_power_prediction(live_db_session, qa_service) -> None:
    """显式供应商只作为确定性预测输入，不由 LLM 或前端补算。"""
    tail, _, resolved = _resolved_order_tail(live_db_session)
    baseline = PowerPredictionEngine(live_db_session).predict(
        model_code=resolved.model_code,
        configuration=resolved.to_prediction_configuration(),
    )

    response = qa_service.ask(f"订单{tail}按{baseline.supplier_name}供应商预测功率分布", use_llm=False)

    assert response.classification == "A"
    assert response.nlu.slots["supplier_name"] == baseline.supplier_name
    assert response.raw_result["power_prediction"]["supplier_name"] == baseline.supplier_name


def test_power_question_without_order_requires_clarification(qa_service) -> None:
    """缺少订单的功率问题只能追问，不能绕过 BOM 配置映射直接计算。"""
    response = qa_service.ask("帮我做功率预测并推荐供应商", use_llm=False)

    assert response.classification == "B"
    assert response.status.code == "CLARIFICATION_REQUIRED"
    assert "order_id" in response.nlu.missing_slots
    assert response.raw_result == {}


def test_llm_target_ratio_without_question_grounding_is_rejected(live_db_session) -> None:
    """LLM 不能凭空补目标功率比例并绕过缺槽保护。"""
    tail, _, _ = _resolved_order_tail(live_db_session)
    repository = PlanBomQueryRepository(live_db_session)
    fake_client = _FakeLlmClient(
        {
            "intent_candidate": "plan_power_supplier_recommendation",
            "slot_candidate": {
                "order_tail_no": [tail],
                "target_power_ratio": {"620": 50, "625": 50},
            },
            "confidence": 0.95,
        }
    )
    nlu = PlanBomNluCenterService(
        repository=repository,
        base_url="http://llm.invalid",
        api_key="k",
        model="test-model",
        client=fake_client,
    )

    candidate = nlu.understand(f"订单{tail}推荐供应商", use_llm=True)

    assert fake_client.calls == 1
    assert candidate.intent == "plan_power_supplier_recommendation"
    assert candidate.slots.get("target_power_ratio") == {}
    assert "target_power_ratio" in candidate.missing_slots


def test_llm_order_without_question_grounding_cannot_trigger_power_calculation(live_db_session) -> None:
    """LLM 不能凭空补订单号并触发 M4/M3 功率计算。"""
    tail, _, _ = _resolved_order_tail(live_db_session)
    repository = PlanBomQueryRepository(live_db_session)
    fake_client = _FakeLlmClient(
        {
            "intent_candidate": "plan_power_prediction",
            "slot_candidate": {"order_tail_no": [tail]},
            "confidence": 0.95,
        }
    )
    engine = PowerPredictionEngine(live_db_session)
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
        power_config_resolver=PlanBomPowerConfigResolverService(live_db_session, repository=repository),
        power_prediction_engine=engine,
        power_recommendation_service=PowerRecommendationService(live_db_session, engine=engine),
    )

    response = service.ask("帮我做功率预测", use_llm=True)

    assert fake_client.calls == 1
    assert response.classification == "B"
    assert "order_id" in response.nlu.missing_slots
    assert response.raw_result == {}


def test_llm_supplier_and_benchmark_without_question_grounding_are_rejected(live_db_session) -> None:
    """LLM 不能凭空补供应商或标板来改变 M3 预测输入。"""
    tail, _, resolved = _resolved_order_tail(live_db_session)
    repository = PlanBomQueryRepository(live_db_session)
    fake_client = _FakeLlmClient(
        {
            "intent_candidate": "plan_power_prediction",
            "slot_candidate": {
                "order_tail_no": [tail],
                "supplier_name": resolved.resolved_config.get("supplier"),
                "benchmark": "新北德",
            },
            "confidence": 0.95,
        }
    )
    nlu = PlanBomNluCenterService(
        repository=repository,
        base_url="http://llm.invalid",
        api_key="k",
        model="test-model",
        client=fake_client,
    )

    candidate = nlu.understand(f"订单{tail}做功率预测", use_llm=True)

    assert fake_client.calls == 1
    assert candidate.intent == "plan_power_prediction"
    assert candidate.slots.get("supplier_name") is None
    assert candidate.slots.get("benchmark") is None


def test_llm_cannot_downgrade_power_recommendation_or_override_rule_power_slots(live_db_session) -> None:
    """LLM 候选不能把规则层已闭合的功率推荐降级为预测，也不能覆盖目标比例/供应商/标板。"""
    tail, _, _ = _resolved_order_tail(live_db_session)
    repository = PlanBomQueryRepository(live_db_session)
    fake_client = _FakeLlmClient(
        {
            "intent_candidate": "plan_power_prediction",
            "slot_candidate": {
                "order_tail_no": [tail],
                "target_power_ratio": {"615": 1, "620": 1},
                "supplier_name": "通威",
                "benchmark": "莱茵基准",
            },
            "confidence": 0.98,
        }
    )
    nlu = PlanBomNluCenterService(
        repository=repository,
        base_url="http://llm.invalid",
        api_key="k",
        model="test-model",
        client=fake_client,
    )

    candidate = nlu.understand(f"订单{tail}按芜湖供应商和北德标板，620:625 1:1，推荐供应商", use_llm=True)

    assert fake_client.calls == 1
    assert candidate.intent == "plan_power_supplier_recommendation"
    assert candidate.slots["target_power_ratio"] == {"620": 1.0, "625": 1.0}
    assert candidate.slots["supplier_name"] == "芜湖"
    assert candidate.slots["benchmark"] == "新北德"
    assert any("LLM power intent" in note or "功率预测类问题的 LLM intent" in note for note in candidate.guardrail_notes)


def test_power_presentation_bypasses_llm_even_when_enabled(live_db_session) -> None:
    """功率预测展示层必须保持确定性，不能让 LLM 改写数值答案。"""
    tail, _, _ = _resolved_order_tail(live_db_session)
    repository = PlanBomQueryRepository(live_db_session)
    engine = PowerPredictionEngine(live_db_session)
    fake_client = _FakeLlmClient(
        {
            "display_type": "narrative",
            "title": "LLM 改写标题",
            "answer": "LLM 伪造中心功率 999W",
            "highlights": ["LLM 伪造供应商"],
        }
    )
    service = PlanBomQaService(
        repository=repository,
        query_service=PlanBomQueryService(repository=repository),
        nlu_service=PlanBomNluCenterService(repository=repository, base_url="", api_key="", model=""),
        presentation_service=PlanBomAnswerPresentationService(
            enabled=True,
            base_url="http://llm.invalid",
            api_key="k",
            model="test-model",
            client=fake_client,
        ),
        power_config_resolver=PlanBomPowerConfigResolverService(live_db_session, repository=repository),
        power_prediction_engine=engine,
        power_recommendation_service=PowerRecommendationService(live_db_session, engine=engine),
    )

    response = service.ask(f"订单{tail}做功率预测，给出功率档分布", use_llm=False)

    assert response.classification == "A"
    assert fake_client.calls == 0
    assert response.presentation is not None
    assert response.presentation.debug["presentation_source"] == "deterministic"
    assert response.presentation.debug["fallback_reason"] == "plan_power_deterministic_only"
    assert "999W" not in response.presentation.answer

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from docx import Document

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

DOCX_PATH = Path("ai/inbox/attachments/BOM配置搭配问询：.docx")
POWER_DOCX_EXAMPLE_COUNT = 12


@pytest.fixture()
def live_db_session():
    """连接当前项目真实数据库，供 docx 问法回归从真实 BOM 与 active 功率模型动态抽题。"""
    session = SessionLocal()
    try:
        try:
            session.query(PlanBomHeader).limit(1).all()
        except Exception as exc:  # pragma: no cover - 仅用于缺少本地验收库时跳过。
            pytest.skip(f"当前环境无法连接真实 BOM 数据库，跳过 docx 问法回归：{exc}")
        if session.query(PlanPowerModelVersion).filter_by(is_active=1).first() is None:
            pytest.skip("当前数据库没有 active 功率模型版本，无法执行 docx 问法回归。")
        yield session
    finally:
        session.close()


@pytest.fixture()
def qa_service(live_db_session) -> PlanBomQaService:
    """构造关闭 LLM 的 QA 服务，确保 docx 回归只验证确定性 NLU/M4/M3 链路。"""
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


def _docx_power_questions() -> list[str]:
    """读取附件中的功率预测例题，确保测试确实锚定业务提供的 docx。"""
    document = Document(DOCX_PATH)
    return [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip().startswith("问题") and "NT" in paragraph.text]


def _resolved_order_by_model(session, model_code: str) -> tuple[str, Any]:
    """从真实 BOM 中寻找指定版型且可唯一映射到功率模型的订单尾号。"""
    resolver = PlanBomPowerConfigResolverService(session)
    headers = session.query(PlanBomHeader).filter_by(is_active=1).order_by(PlanBomHeader.id.asc()).all()
    seen_tails: set[str] = set()
    for header in headers:
        tail = (header.order_no or "")[-5:]
        if not tail or tail in seen_tails:
            continue
        seen_tails.add(tail)
        result = resolver.resolve(order_no=tail)
        required = {"model_code", "glass", "ribbon", "busbar", "cable", "cell_size", "supplier", "benchmark"}
        if result.status == RESOLVED_STATUS and result.model_code == model_code and required.issubset(result.resolved_config):
            return tail, result
    pytest.fail(f"当前真实 BOM 数据中未找到可用于 docx 问法回归的 {model_code} 订单。")


def _five_active_order_tails(session) -> list[str]:
    """从真实 BOM 中抽取五个不会触发候选歧义的真实订单尾号。"""
    tails: list[str] = []
    resolver = PlanBomPowerConfigResolverService(session)
    for header in session.query(PlanBomHeader).filter_by(is_active=1).order_by(PlanBomHeader.id.asc()).all():
        tail = (header.order_no or "")[-5:]
        if not tail or tail in tails:
            continue
        # 业务模拟题应选择当前库中可直接定位的真实评审号/订单尾号；多文件同尾号场景仍应由主链路追问。
        if resolver.resolve(order_no=tail).status != RESOLVED_STATUS:
            continue
        tails.append(tail)
        if len(tails) >= 5:
            return tails
    pytest.fail("当前真实 BOM 数据不足 5 个可唯一定位订单，无法模拟 docx 第一部分多订单问询。")


def _assert_ok_table_response(response, *, expected_intent: str | None = None) -> None:
    """断言普通 BOM 问询返回 A 类可答表格。"""
    assert response.classification == "A", response.model_dump(mode="json")
    assert response.status.code == "OK", response.model_dump(mode="json")
    if expected_intent:
        assert response.nlu.intent == expected_intent
    assert response.result_table.rows
    assert response.presentation is not None
    assert response.presentation.table_spec is not None


def _assert_power_recommendation_response(
    response,
    *,
    expected_bins: set[str],
    expected_supplier: str | None = None,
    explicit_config: bool = False,
) -> None:
    """断言功率推荐/效率段问询返回 A 类确定性推荐结果。"""
    assert response.classification == "A", response.model_dump(mode="json")
    assert response.status.code == "OK", response.model_dump(mode="json")
    assert response.nlu.intent == "plan_power_supplier_recommendation"
    assert set(response.nlu.slots["target_power_ratio"]) == expected_bins
    assert set(response.raw_result["power_recommendation"]["target_power_ratio"]) == expected_bins
    assert response.raw_result["power_recommendation"]["recommendations"]
    assert response.result_table.rows
    assert {"供应商", "匹配度", "目标功率档", "建议效率段"}.issubset(set(response.result_table.columns))
    if expected_supplier:
        assert response.nlu.slots["supplier_name"] == expected_supplier
        assert {row["供应商"] for row in response.result_table.rows} == {expected_supplier}
    if explicit_config:
        resolution = response.raw_result["bom_config_resolution"]
        assert resolution["order_no"] is None
        assert resolution["status"] == RESOLVED_STATUS
        assert resolution["resolved_config"]["model_code"]["source"] == "explicit_input"
        assert response.raw_result["power_recommendation"]["model_code"] == resolution["model_code"]


def test_docx_attachment_power_examples_are_all_loaded() -> None:
    """附件第二部分 12 道功率例题必须都进入回归测试基线。"""
    questions = _docx_power_questions()

    assert DOCX_PATH.exists()
    assert len(questions) == POWER_DOCX_EXAMPLE_COUNT
    assert any("715和720" in question for question in questions)
    assert any("问题12" in question for question in questions)


@pytest.mark.parametrize("variant", [0, 1])
def test_docx_part1_material_compare_example_has_multiple_real_questions(live_db_session, qa_service, variant: int) -> None:
    """docx 第一部分例题 1：真实订单之间的核心材料差异对比。"""
    tails = _five_active_order_tails(live_db_session)
    questions = [
        f"订单{tails[0]}和订单{tails[1]}玻璃、间隙贴膜、焊带、汇流条、接线盒材料对比，有哪些材料不一致？",
        f"帮我比较评审号{tails[0]}与{tails[1]}的五类BOM配置差异，表格展示。",
    ]

    response = qa_service.ask(questions[variant], use_llm=False)

    _assert_ok_table_response(response, expected_intent="cross_order_material_compare")


@pytest.mark.parametrize("variant", [0, 1])
def test_docx_part1_single_order_config_example_has_multiple_real_questions(live_db_session, qa_service, variant: int) -> None:
    """docx 第一部分例题 2：真实单订单五类核心材料规格查询。"""
    tail = _five_active_order_tails(live_db_session)[0]
    questions = [
        f"订单{tail}的玻璃、间隙贴膜、焊带、汇流条、接线盒的规格描述？",
        f"查一下评审号{tail}五类核心BOM配置，包含玻璃间隙膜焊带汇流条接线盒。",
    ]

    response = qa_service.ask(questions[variant], use_llm=False)

    _assert_ok_table_response(response, expected_intent="single_order_material_specs")


@pytest.mark.parametrize("variant", [0, 1])
def test_docx_part1_multi_order_table_example_has_multiple_real_questions(live_db_session, qa_service, variant: int) -> None:
    """docx 第一部分例题 3：多个真实订单五类核心材料规格生成表格。"""
    tails = _five_active_order_tails(live_db_session)
    joined = "/".join(tails)
    questions = [
        f"查找订单{joined}这几个订单的玻璃、间隙贴膜、焊带、汇流条、接线盒的规格描述并生成表格？",
        f"把{','.join(tails)}五个评审号的关键BOM配置列成清单，字段要有玻璃、间隙膜、焊带、汇流条和接线盒。",
    ]

    response = qa_service.ask(questions[variant], use_llm=False)

    _assert_ok_table_response(response, expected_intent="multi_order_material_table")


@pytest.mark.parametrize("variant", [0, 1, 2])
def test_docx_power_example_1_nt12_order_recommends_multiple_suppliers(live_db_session, qa_service, variant: int) -> None:
    """docx 第二部分例题 1：NT12/66GDF 真实订单按 715/720=2/8 推荐可满足的电池供应商。"""
    tail, _ = _resolved_order_by_model(live_db_session, "NT12-66GDF")
    questions = [
        f"NT12/66GDF（真实订单-{tail}）用哪些家电池可以满足715和720 2:8的需求占比？",
        f"评审号{tail}目标功率715:720=2:8，请推荐通威、爱旭、时创等各家电池使用方案。",
        f"订单{tail}要满足715W占20%、720W占80%，哪些供应商更合适？请表格展示。",
    ]

    response = qa_service.ask(questions[variant], use_llm=False)

    _assert_power_recommendation_response(response, expected_bins={"715", "720"})
    assert len({row["供应商"] for row in response.result_table.rows}) >= 3


@pytest.mark.parametrize("variant", [0, 1, 2])
def test_docx_power_example_2_nt12r_order_wuhu_efficiency_segment(live_db_session, qa_service, variant: int) -> None:
    """docx 第二部分例题 2：NT12R/66GDF 真实订单指定芜湖供应商，回答满足 615/620=1/1 的效率段。"""
    tail, _ = _resolved_order_by_model(live_db_session, "NT12R-66GDF")
    questions = [
        f"NT12R/66GDF（真实订单-{tail}）用供应商芜湖哪个效率可以满足615和620 1:1的需求占比？",
        f"订单{tail}指定芜湖电池，615:620 1:1，需要使用哪个效率段？",
        f"评审号{tail}按芜湖供应商做功率推荐，目标615W 50%，620W 50%，告诉我电池效率段。",
    ]

    response = qa_service.ask(questions[variant], use_llm=False)

    _assert_power_recommendation_response(response, expected_bins={"615", "620"}, expected_supplier="芜湖")
    assert all(row["建议效率段"] for row in response.result_table.rows)


EXPLICIT_ALL_SUPPLIER_CASES = [
    pytest.param("docx_q3", "0.24+0.26", "6*0.4+4*0.35反光", "新北德", id="q3-mixed-ribbon-nord-all-suppliers"),
    pytest.param("docx_q4", "0.24+0.26", "6*0.4+4*0.35反光", "计量院", id="q4-mixed-ribbon-cmi-all-suppliers"),
    pytest.param("docx_q5", "0.24+0.26", "6*0.4+4*0.35反光", "莱茵", id="q5-mixed-ribbon-rhein-all-suppliers"),
    pytest.param("docx_q6", "0.24", "6*0.4+4*0.35反光", "莱茵", id="q6-single-ribbon-rhein-all-suppliers"),
    pytest.param("docx_q7", "0.24", "6*0.4+4*0.35反光", "计量院", id="q7-single-ribbon-cmi-all-suppliers"),
    pytest.param("docx_q8", "0.24", "6*0.4+4*0.35反光", "北德", id="q8-single-ribbon-nord-all-suppliers"),
]


@pytest.mark.parametrize(("case_id", "ribbon", "busbar", "benchmark"), EXPLICIT_ALL_SUPPLIER_CASES)
@pytest.mark.parametrize("variant", [0, 1])
def test_docx_power_examples_3_to_8_explicit_config_all_suppliers(
    qa_service,
    case_id: str,
    ribbon: str,
    busbar: str,
    benchmark: str,
    variant: int,
) -> None:
    """docx 第二部分例题 3-8：显式配置直问各家供应商效率段，必须不依赖假订单也能回答。"""
    base = f"NT12R-66GDF 焊带：{ribbon}+玻璃：双镀+汇流条：{busbar}+接线盒：300/200，标板使用：{benchmark}，620:625 1:1"
    questions = [
        f"{base} 各家供应商效率段都在哪里？请用表格展示出来。",
        f"按{base}这个配置，目标620和625各占一半，请列出所有电池供应商的效率段和匹配度。",
    ]

    response = qa_service.ask(questions[variant], use_llm=False)

    _assert_power_recommendation_response(response, expected_bins={"620", "625"}, explicit_config=True)
    resolution = response.raw_result["bom_config_resolution"]["resolved_config"]
    expected_ribbon = "0.26" if ribbon == "0.24+0.26" else ribbon
    assert resolution["ribbon"]["value"] == expected_ribbon
    assert resolution["glass"]["value"] == "双镀+间隙铝膜"
    assert resolution["busbar"]["value"] == busbar
    assert resolution["cable"]["value"] == "+300/-200mm（4mm²）"
    assert len({row["供应商"] for row in response.result_table.rows}) >= 3


@pytest.mark.parametrize("phrase", ["所有电池供应商", "全部电池供应商"])
def test_explicit_config_all_battery_supplier_synonyms_ignore_example_supplier_names(qa_service, phrase: str) -> None:
    """“所有/全部电池供应商”即使句中举例供应商名称，也必须按全供应商推荐，不能误筛成单供应商。"""
    question = (
        "NT12R-66GDF 焊带：0.24+0.26+玻璃：双镀+汇流条：6*0.4+4*0.35反光+"
        f"接线盒：300/200，标板使用：北德，620:625 1:1，请对通威、芜湖等{phrase}列出效率段和匹配度。"
    )

    response = qa_service.ask(question, use_llm=False)

    _assert_power_recommendation_response(response, expected_bins={"620", "625"}, explicit_config=True)
    assert response.nlu.slots.get("supplier_name") is None
    assert len({row["供应商"] for row in response.result_table.rows}) >= 3


EXPLICIT_WUHU_CASES = [
    pytest.param("docx_q9", "0.24+0.26", "6*0.4+4*0.35反光", id="q9-mixed-ribbon-busbar-040-035"),
    pytest.param("docx_q10", "0.24+0.26", "6*0.3+4*0.3反光", id="q10-mixed-ribbon-busbar-030-030"),
    pytest.param("docx_q11", "0.24", "6*0.4+4*0.35反光", id="q11-single-ribbon-busbar-040-035"),
    pytest.param("docx_q12", "0.24", "6*0.3+4*0.3反光", id="q12-single-ribbon-busbar-030-030"),
]


@pytest.mark.parametrize(("case_id", "ribbon", "busbar"), EXPLICIT_WUHU_CASES)
@pytest.mark.parametrize("variant", [0, 1])
def test_docx_power_examples_9_to_12_explicit_config_wuhu_efficiency_segment(
    qa_service,
    case_id: str,
    ribbon: str,
    busbar: str,
    variant: int,
) -> None:
    """docx 第二部分例题 9-12：显式配置 + 芜湖供应商直问效率段，必须返回单供应商效率建议。"""
    base = f"NT12R-66GDF 焊带：{ribbon}+玻璃：双镀+汇流条：{busbar}+接线盒：300/200，标板使用：北德，620:625 1:1"
    questions = [
        f"{base} 芜湖需要使用哪个效率段？",
        f"按{base}这个方案，只看芜湖供应商，推荐哪个电池效率可以满足目标比例？",
    ]

    response = qa_service.ask(questions[variant], use_llm=False)

    _assert_power_recommendation_response(response, expected_bins={"620", "625"}, expected_supplier="芜湖", explicit_config=True)
    resolution = response.raw_result["bom_config_resolution"]["resolved_config"]
    expected_ribbon = "0.26" if ribbon == "0.24+0.26" else ribbon
    assert resolution["ribbon"]["value"] == expected_ribbon
    assert resolution["busbar"]["value"] == busbar
    assert all(row["建议效率段"] for row in response.result_table.rows)

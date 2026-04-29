from __future__ import annotations

import json
from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace
from typing import Iterator

import pytest
from sqlalchemy import text

from backend.app.db.session import SessionLocal
from backend.app.domains.logistics.repositories.data_qa_repository import LogisticsDataQaRepository
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.llm_clarification_assist_service import LogisticsLlmClarificationAssistService
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.domains.logistics.services.llm_understanding_guardrail_service import LogisticsLlmUnderstandingGuardrailService
from backend.app.domains.logistics.services.llm_understanding_service import LogisticsLlmUnderstandingService


class _FakeChatCompletions:
    """假的 completions 接口。

    说明：
        1. data-qa 主链路集成测试不依赖真实外部 LLM；
        2. 这里只返回预设 JSON，便于验证 guardrail 接入行为；
        3. 避免测试因网络或模型波动变得不稳定。
    """

    def __init__(self, content: str) -> None:
        self.content = content

    def create(self, **kwargs):  # noqa: ANN003
        _ = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class _FakeOpenAIClient:
    """假的 OpenAI 客户端。"""

    def __init__(self, content: str) -> None:
        self.chat = SimpleNamespace(completions=_FakeChatCompletions(content))


def _build_live_clarification_assist_service(payload: dict) -> LogisticsLlmClarificationAssistService:
    """构造固定返回 live 澄清辅助结果的服务。"""

    return LogisticsLlmClarificationAssistService(
        base_url="http://example.com",
        api_key="token",
        model="demo-model",
        client=_FakeOpenAIClient(json.dumps(payload, ensure_ascii=False)),
        enabled=True,
        mode="assist",
        sample_rate=1.0,
        min_confidence=0.7,
        audit_enabled=False,
    )


def _build_live_llm_service(payload: dict) -> LogisticsLlmUnderstandingService:
    """构造固定返回 live payload 的 LLM 服务。"""
    return LogisticsLlmUnderstandingService(
        base_url="http://example.com",
        api_key="token",
        model="demo-model",
        client=_FakeOpenAIClient(json.dumps(payload, ensure_ascii=False)),
    )


@contextmanager
def logistics_db() -> Iterator:
    """提供真实数据库会话。

    说明：
        1. 当前测试需要直接复核真实物流数据；
        2. 若数据库不可用，则跳过测试而不是伪造结果；
        3. 所有测试结束后统一关闭会话。
    """
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        db.close()
        pytest.skip(f"真实数据库当前不可用：{exc}")
    try:
        yield db
    finally:
        db.close()


def test_data_qa_planner_builds_q6_plan() -> None:
    """验证 2026 发运量/车次问题能落到系统查询计划。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2026年1月份总发运量（MW）和总车次")
    assert plan.query_key == "sys_mw_and_trip_count"
    assert plan.filters["year"] == 2026
    assert plan.filters["months"] == [1]


def test_data_qa_planner_builds_q6_mw_only_plan() -> None:
    """验证 2026 纯 MW 问法能落到系统统计计划。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2026年1月份总共发货多少MW？")
    assert plan.query_key == "sys_mw_and_trip_count"
    assert plan.metrics == ["shipment_mw"]
    assert plan.filters["months"] == [1]


def test_data_qa_planner_builds_hist_region_count_plan() -> None:
    """验证历史区域件数问题能落到历史汇总计划。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("华东区域在历史物流台账中的总发运件数是多少？")
    assert plan.query_key == "hist_quantity_by_region"
    assert plan.filters["region_name"] == "华东"


def test_data_qa_planner_builds_hist_top_customers_plan_without_year() -> None:
    """验证省份前五客户费用+总瓦数题可按历史累计口径直接支持。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("江苏省发运记录中，按客户名称统计前5名客户的总费用和总瓦数。")
    assert plan.query_key == "hist_top_customers_fee_and_mw_by_province"
    assert plan.filters["year"] is None
    assert plan.filters["province"] == "江苏"


def test_data_qa_planner_builds_hist_total_fee_by_province_plan_without_year() -> None:
    """验证省份历史总费用题可按历史累计口径直接支持。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("江苏省历史发运的总费用是多少？")
    assert plan.query_key == "hist_total_fee_by_province"
    assert plan.filters["year"] is None
    assert plan.filters["province"] == "江苏"


def test_data_qa_planner_builds_special_total_fee_variant_plan() -> None:
    """验证经营计划运费变体问法能落到特殊业务总费用计划。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("问题2：26年 经营计划 运费是多少")
    assert plan.query_key == "sys_special_total_fee"
    assert plan.filters["special_scope"] == "planning"


def test_data_qa_planner_builds_carrier_fee_only_plan() -> None:
    """验证承运商年度运输费用题能命中承运商 KPI 计划。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2023年各物流承运商年度运输费用各是多少？")
    assert plan.query_key == "hist_carrier_kpi_by_year"
    assert plan.filters["view_mode"] == "fee_only"


def test_data_qa_planner_builds_carrier_volume_plan() -> None:
    """验证承运商承运量简写问法能命中承运商 KPI 计划。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("25年物流公司承运量")
    assert plan.query_key == "hist_carrier_kpi_by_year"
    assert plan.filters["year"] == 2025


def test_data_qa_planner_builds_carrier_volume_plan_for_each_company_variant() -> None:
    """验证“各家物流承运量”类问法也能命中承运商 KPI 计划。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("25年各家物流承运量是多少")
    assert plan.query_key == "hist_carrier_kpi_by_year"
    assert plan.filters["year"] == 2025


def test_data_qa_planner_builds_system_company_total_fee_plan() -> None:
    """验证 2026 月度承运商总计运费题能抽取公司名并命中系统总运费计划。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2026年1月份英赋嘉总计运费是多少钱？")
    assert plan.query_key == "sys_total_fee_by_filters"
    assert plan.filters["year"] == 2026
    assert plan.filters["months"] == [1]
    assert plan.filters["company_name"] == "英赋嘉"


def test_data_qa_planner_builds_hist_vehicle_trip_count_variant() -> None:
    """验证历史车型总车次简写问法能直接命中车型车次计划。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("问题1：25年全年17.5共发运多少车")
    assert plan.query_key == "hist_vehicle_type_trip_count"
    assert plan.filters["year"] == 2025
    assert plan.filters["vehicle_type"] == "17.5"


def test_data_qa_planner_accepts_zero_prefixed_year_for_vehicle_trip_count() -> None:
    """验证“025年”这类缺位年份也能按 2025 年识别，避免真实问法误澄清。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("025年始发地合肥，车型 17.5 ，发出了多少车？")
    assert plan.query_key == "hist_vehicle_type_trip_count"
    assert plan.filters["year"] == 2025


def test_data_qa_planner_builds_system_unit_fee_plan() -> None:
    """验证 2026 月度单瓦运输成本题会落到系统单瓦成本计划。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2026年1月份单瓦运输成本是多少？")
    assert plan.query_key == "sys_unit_fee_per_watt"
    assert plan.filters["year"] == 2026
    assert plan.filters["months"] == [1]


def test_data_qa_planner_returns_clarification_for_vague_question() -> None:
    """验证模糊问题会触发澄清，而不是直接猜。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("最近物流成本是不是变高了？")
    assert plan.needs_clarification is True
    assert plan.intent == "clarification"


def test_data_qa_planner_returns_unsupported_for_forecast() -> None:
    """验证预测类问题在 MVP 阶段直接返回不支持。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("预测下个月物流费用会是多少？")
    assert plan.intent == "unsupported"
    assert "预测" in (plan.unsupported_reason or "")
    assert plan.unsupported_category == "forecast"
    assert plan.unsupported_suggestions


def test_data_qa_planner_forecast_preempts_direct_supported_region_query() -> None:
    """验证预测边界优先于高置信 A 类区域发运量 query_key。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("基于2024年前期数据，预测未来3个月各区域发运量变化趋势。")
    assert plan.intent == "unsupported"
    assert plan.query_key is None
    assert plan.unsupported_category == "forecast"


def test_data_qa_planner_returns_unsupported_for_eta_question() -> None:
    """验证 ETA / 到达时间问题会稳定返回不支持。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("华东区域当前订单预计到达时间是什么时候？")
    assert plan.intent == "unsupported"
    assert "ETA" in (plan.unsupported_reason or "") or "到达时间" in (plan.unsupported_reason or "")
    assert plan.unsupported_category == "eta"


def test_data_qa_planner_returns_unsupported_for_discussion_question() -> None:
    """验证开放讨论或治理原则题不会被误判成可执行查询。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("若某个 ship_task 被拆成100次以上派车任务，系统在做均值分析时应如何处理这种极端值？")
    assert plan.intent == "unsupported"
    assert "开放讨论" in (plan.unsupported_reason or "") or "治理原则" in (plan.unsupported_reason or "")


def test_data_qa_planner_returns_clarification_for_missing_time_metric_question() -> None:
    """验证缺少时间范围的费用类问题会先触发澄清。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("江苏省历史发运的总费用是多少？")
    assert plan.query_key == "hist_total_fee_by_province"
    assert plan.filters["province"] == "江苏"


def test_data_qa_planner_returns_business_clarification_for_transport_record_question() -> None:
    """验证运输方式记录数问题会命中业务化澄清模板。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("按运输方式统计，公路对应的发运记录数是多少？")
    assert plan.intent == "clarification"
    assert plan.needs_clarification is True
    assert any("发运明细行" in item or "物流任务数" in item or "车次" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_product_spec_question() -> None:
    """验证规格总瓦数问题会命中业务化澄清模板。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("规格为GCL-NT10/78GDF-640W的历史发运总瓦数是多少？")
    assert plan.intent == "clarification"
    assert plan.needs_clarification is True
    assert any("历史台账累计" in item or "具体年份" in item for item in plan.clarification_questions)


def test_data_qa_service_uses_llm_to_enrich_clarification_questions() -> None:
    """验证 data-qa 服务在澄清态下会使用 LLM 生成更业务化追问，但仍保持 clarification。"""

    payload = {
        "missing_slots": ["metric_definition", "source_scope"],
        "slot_reasons": {
            "metric_definition": "需要先确认是车次还是车辆数。",
            "source_scope": "需要先确认是否只看历史台账。",
        },
        "suggested_questions": [
            "请确认这里统计的是车次，还是唯一车辆数。",
            "请确认是否只看 2023–2025 历史台账，不混入 2026 系统数据。",
        ],
        "business_summary": "当前问题还需要先确认统计口径，系统才能继续汇总季度结果。",
        "confidence": 0.92,
    }

    with logistics_db() as db:
        service = LogisticsDataQaService(
            db=db,
            clarification_assist_service=_build_live_clarification_assist_service(payload),
        )
        result = service.query(LogisticsDataQaQueryRequest(question="2024Q1的物流发运车次或车辆数是多少？"))

    assert result.needs_clarification is True
    assert result.supported is False
    assert result.query_plan.intent == "clarification"
    assert result.query_plan.clarification_assist_used is True
    assert result.query_plan.clarification_assist_provider_mode == "live"
    assert result.query_plan.clarification_category == "quarter_trip_metric_scope"
    assert result.query_plan.clarification_missing_slots == ["metric_definition", "source_scope"]
    assert "车次" in result.clarification_questions[0]
    assert "统计口径" in result.answer_summary


def test_data_qa_planner_returns_unsupported_for_high_fee_address_procurement_split_question() -> None:
    """验证带采购方式拆分的高运费项目地题会正式转入不支持。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("统计一下24年创维客户发货的项目地运费金额超过20万的收货地址，并分别列出询比价和招标的发运量")
    assert plan.intent == "unsupported"
    assert "询比价" in (plan.unsupported_reason or "") or "采购方式" in (plan.unsupported_reason or "")


def test_data_qa_planner_keeps_clarification_for_high_fee_address_without_procurement_split() -> None:
    """验证不带采购方式拆分的高运费项目地题仍保持业务化澄清。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2024年客户华阳发货的项目地中，哪些收货地址的运费超过20万元？")
    assert plan.intent == "clarification"
    assert plan.needs_clarification is True
    assert any("全年累计运费" in item or "单笔项目地记录" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_state_breakdown_question() -> None:
    """验证任务状态拆分问题会命中业务化澄清模板。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2026物流任务表中，各任务状态（PREASSIGN、ASSIGNED、PRESIGNFOR、SIGNEDFOR）的数量分别是多少？")
    assert plan.intent == "clarification"
    assert plan.needs_clarification is True
    assert any("物流任务表" in item or "派车任务表" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_status_risk_question() -> None:
    """验证状态风险题会命中业务化澄清模板。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("当任务长期停留在ALLOCATED状态时，应如何识别潜在履约风险并给出优先排查清单？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "status_risk_scope"
    assert any("风险" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_procurement_metric_question() -> None:
    """验证采购方式对比题会命中业务化澄清模板。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2026年有采购方式标记的任务中，询比价与招标的任务量分别是多少？占比多少？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "procurement_metric_scope"
    assert any("采购方式" in item or "任务量" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_data_quality_question() -> None:
    """验证数据质量统计题会命中业务化澄清模板。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2026年parse_fail_reason中最常见的失败原因模式是什么？前二十条模式分别出现多少次？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "data_quality_scope"
    assert any("问题记录数量" in item or "问题率" in item or "明细清单" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_route_price_metric_question() -> None:
    """验证年份明确但价格口径不明确的线路运价题会命中业务化澄清模板。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("25年合肥发广州17.5运价")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "route_price_metric_scope"
    assert any("平均单车运费" in item or "单瓦价" in item for item in plan.clarification_questions)


def test_data_qa_planner_builds_hist_region_province_breakdown_plan() -> None:
    """验证已明确区域和指标的各省拆分题可直接进入受控查询。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("华东区域2025年各省发运量分别是多少？")
    assert plan.query_key == "hist_mw_by_region_province"
    assert plan.filters["year"] == 2025
    assert plan.filters["region_name"] == "华东"


def test_data_qa_service_uses_llm_to_enrich_status_risk_clarification_questions() -> None:
    """验证 data-qa 服务会在状态风险类问题上使用 LLM 生成更业务化追问，但仍保持 clarification。"""

    payload = {
        "missing_slots": ["evaluation_metric", "time_range"],
        "slot_reasons": {
            "evaluation_metric": "需要确认风险按什么规则定义。",
            "time_range": "需要确认看当前在途、近30天还是全年。",
        },
        "suggested_questions": [
            "请先确认这里的“风险”按什么口径判断，例如状态滞留时长、未签收时长，还是费用异常。",
            "请确认统计范围，例如当前在途任务、2026年正式任务，还是近30天内的任务。",
        ],
        "business_summary": "当前问题还需要先明确风险判定标准和统计范围，系统才能继续给出排查清单。",
        "confidence": 0.9,
    }

    with logistics_db() as db:
        service = LogisticsDataQaService(
            db=db,
            clarification_assist_service=_build_live_clarification_assist_service(payload),
        )
        result = service.query(
            LogisticsDataQaQueryRequest(question="当任务长期停留在ALLOCATED状态时，应如何识别潜在履约风险并给出优先排查清单？")
        )

    assert result.needs_clarification is True
    assert result.supported is False
    assert result.query_plan.intent == "clarification"
    assert result.query_plan.clarification_assist_used is True
    assert result.query_plan.clarification_assist_provider_mode == "live"
    assert result.query_plan.clarification_category == "status_risk_scope"
    assert result.query_plan.clarification_missing_slots == ["evaluation_metric", "time_range"]
    assert "风险" in result.clarification_questions[0]
    assert "风险判定标准" in result.answer_summary


def test_data_qa_planner_builds_system_base_total_fee_plan() -> None:
    """验证 2026 基地过滤总费用题已能命中系统基地总运费计划。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("帮我看一下从合肥基地始发，26年1-2月客户：海南创维新能源投资有限公司 总运费多少")
    assert plan.query_key == "sys_total_fee_by_filters"
    assert plan.filters["base_code"] == "1"
    assert plan.filters["months"] == [1, 2]
    assert plan.filters["customer_name"] == "海南创维新能源投资有限公司"


def test_data_qa_planner_builds_system_unit_fee_plan_for_formula_variant() -> None:
    """验证显式给出公式的月份单瓦成本题已按 2026 系统口径支持。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2月份单W运输成本是多少（（2月运费总价格+额外费用）/运输组件总W数）")
    assert plan.query_key == "sys_unit_fee_per_watt"
    assert plan.filters["year"] == 2026
    assert plan.filters["months"] == [2]
    assert plan.filters["include_extra_cost"] is True


def test_data_qa_planner_returns_unsupported_for_project_name_total_mw_question() -> None:
    """验证显式项目名称口径题会正式转入不支持。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("项目名称：国科新能源有限公司 已发出总运量是多少")
    assert plan.intent == "unsupported"
    assert "项目名称" in (plan.unsupported_reason or "") or "统计维度" in (plan.unsupported_reason or "")


def test_data_qa_planner_builds_hist_route_pricing_avg_plan() -> None:
    """验证历史线路均价题能命中路线运价分析计划。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("帮我看下23年发往乌鲁木齐13m每车的运费均价是多少")
    assert plan.query_key == "hist_route_pricing_analysis"
    assert plan.filters["view_mode"] == "avg_fee"
    assert plan.filters["city"] == "乌鲁木齐"


def test_data_qa_planner_builds_hist_route_pricing_compare_plan() -> None:
    """验证双年份线路运价对比题能命中路线运价分析计划。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("问题1：对比24年和25年合肥发广州 17.5运价")
    assert plan.query_key == "hist_route_pricing_analysis"
    assert plan.filters["view_mode"] == "year_compare"
    assert plan.filters["years"] == [2024, 2025]


def test_data_qa_planner_builds_carrier_ranking_plan() -> None:
    """验证承运商运费排名题能命中统一承运商排名计划。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2025年各承运商按运费排名前十分别是谁？")
    assert plan.query_key == "carrier_metric_ranking"
    assert plan.filters["ranking_metric"] == "total_fee"


def test_data_qa_planner_builds_sys_procurement_split_plan() -> None:
    """验证 2026 采购方式发运量拆分题能命中系统拆分计划。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("26年招标和询比价，发运量分别是多少")
    assert plan.query_key == "sys_mw_by_procurement_type"


def test_data_qa_planner_builds_sys_quality_rank_plans() -> None:
    """验证 2026 数据质量/排名题能命中正式系统 query_key。"""
    planner = LogisticsDataQaPlanner()
    city_rank_plan = planner.build_plan("2026年送达城市任务量排名前十的是哪些城市？")
    fill_rate_plan = planner.build_plan("2026年各送达省份的delivery_distance填充率分别是多少？填充率最低的前十个省份是谁？")
    parse_success_plan = planner.build_plan("哪些承运商的送货单解析成功率最高，哪些最低？")
    mapping_gap_plan = planner.build_plan("2026年任务表中是否存在company_id在承运商主数据表里找不到映射的任务？")
    assert city_rank_plan.query_key == "sys_task_count_ranking"
    assert fill_rate_plan.query_key == "sys_delivery_distance_fill_rate_by_province"
    assert parse_success_plan.query_key == "sys_parse_success_rate_by_carrier"
    assert mapping_gap_plan.query_key == "sys_company_mapping_gap"


def test_data_qa_planner_builds_hist_route_pricing_default_avg_plan() -> None:
    """验证线路简写题已统一落成历史累计平均运费口径。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("合肥发江苏 17.5 车运费")
    assert plan.query_key == "hist_route_pricing_analysis"
    assert plan.filters["view_mode"] == "avg_fee"
    assert plan.filters["years"] == [2023, 2024, 2025]
    assert plan.filters["default_year_scope"] is True


def test_data_qa_planner_builds_system_mw_composite_plan() -> None:
    """验证“2026 运量综合”题已统一解释成截至目前累计的 MW+车次。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("帮我查询2026 年的运量综合")
    assert plan.query_key == "sys_mw_and_trip_count"
    assert plan.filters["year"] == 2026
    assert plan.filters["months"] is None
    assert plan.metrics == ["shipment_mw", "shipment_trip_count"]


def test_data_qa_planner_returns_unsupported_for_supplier_price_outlier_question() -> None:
    """验证 supplier_price 分布与离群点诊断题会正式转入不支持。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2026年assign_detail中的supplier_price分布如何？高价离群点集中在哪些任务或承运商？")
    assert plan.intent == "unsupported"
    assert "supplier_price" in (plan.unsupported_reason or "") or "离群点" in (plan.unsupported_reason or "")


def test_data_qa_planner_builds_system_base_mw_plan() -> None:
    """验证 2026 基地发运量题会带上基地过滤，而不是误算全量。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2026年1月份合肥基地总发运量是多少MW？")
    assert plan.query_key == "sys_mw_and_trip_count"
    assert plan.filters["base_code"] == "1"
    assert plan.filters["base_name"] == "合肥基地"


def test_data_qa_planner_accepts_compact_year_for_signedfor_question() -> None:
    """验证不带“年”的四位年份写法也能被识别，不误落缺时间澄清。"""
    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2026各承运商SIGNEDFOR签收率前十后十分别是谁？")
    assert plan.query_key == "sys_signedfor_rate_by_carrier"
    assert plan.filters["year"] == 2026


def test_data_qa_repository_has_extended_columns() -> None:
    """验证 2026 关键字段结构已经补齐到主库链路。"""
    with logistics_db() as db:
        repo = LogisticsDataQaRepository(db)
        assets = repo.verify_assets()
        dwd_columns = assets["table_columns"]["dwd_logistics_ship_task"]
        product_columns = assets["table_columns"]["dwd_logistics_ship_product"]
        assert "project_name" in dwd_columns
        assert "pickup_date" in dwd_columns
        assert "expand_dept" in dwd_columns
        assert "entrusted_person" in dwd_columns
        assert "normalized_region_name" in dwd_columns
        assert "region_resolve_source" in dwd_columns
        assert "price" in product_columns


def test_data_qa_repository_hist_trip_count_matches_live_value() -> None:
    """验证历史区域车次查询能命中真实值。"""
    with logistics_db() as db:
        repo = LogisticsDataQaRepository(db)
        data = repo.hist_trip_count_by_region(year=2023, region_name="华东")
        assert int(data["shipment_trip_count"] or 0) == 3655


def test_data_qa_repository_sys_mw_and_trip_count_exposes_pickup_date_gap() -> None:
    """验证 2026 月度问答会暴露 pickup_date 缺失，而不是静默给 0。"""
    with logistics_db() as db:
        repo = LogisticsDataQaRepository(db)
        data = repo.sys_mw_and_trip_count(year=2026, months=[1])
        assert "pickup_date_missing_count" in data
        assert "strict_scope_task_count" in data
        assert data["pickup_date_missing_count"] >= 0
        assert data["year_task_count"] >= data["strict_scope_task_count"]


def test_data_qa_service_q06_returns_data_warning_when_pickup_date_missing() -> None:
    """验证 Q06 会根据 pickup_date 实际可用性给出对应结果。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        result = service.query(LogisticsDataQaQueryRequest(question="2026年1月份总发运量（MW）和总车次"))
        if result.supported:
            assert "2026年1月合计发运量为" in result.answer_summary
            assert len(result.result_table.rows) == 1
        else:
            assert "pickup_date" in " ".join(result.warnings)
            assert "暂无法按已锁定业务时间口径计算" in result.answer_summary


def test_data_qa_service_returns_hist_top_customers_without_year() -> None:
    """验证省份前五客户题当前可按历史累计口径稳定返回。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        result = service.query(LogisticsDataQaQueryRequest(question="江苏省发运记录中，按客户名称统计前5名客户的总费用和总瓦数。"))
        assert result.status is not None
        assert result.status.code == "OK"
        assert result.query_plan.query_key == "hist_top_customers_fee_and_mw_by_province"
        assert len(result.result_table.rows) == 5


def test_data_qa_service_returns_hist_total_fee_by_province_without_year() -> None:
    """验证省份历史总费用题已从 B 收进口径稳定的 A 类。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        result = service.query(LogisticsDataQaQueryRequest(question="江苏省历史发运的总费用是多少？"))
        assert result.status is not None
        assert result.status.code == "OK"
        assert result.query_plan.query_key == "hist_total_fee_by_province"
        assert len(result.result_table.rows) == 1


def test_data_qa_service_returns_system_company_total_fee_variant() -> None:
    """验证 2026 月度承运商总计运费题已支持泛化公司名。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        result = service.query(LogisticsDataQaQueryRequest(question="2026年1月份英赋嘉总计运费是多少钱？"))
        assert result.status is not None
        assert result.status.code == "OK"
        assert result.query_plan.query_key == "sys_total_fee_by_filters"
        assert "英赋嘉" in result.answer_summary


def test_data_qa_service_returns_system_base_customer_total_fee_variant() -> None:
    """验证 2026 基地 + 客户总运费题已从 B 收进 A。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        result = service.query(LogisticsDataQaQueryRequest(question="帮我看一下从合肥基地始发，26年1-2月客户：海南创维新能源投资有限公司 总运费多少"))
        assert result.status is not None
        assert result.status.code == "OK"
        assert result.query_plan.query_key == "sys_total_fee_by_filters"
        assert result.query_plan.filters["base_code"] == "1"
        assert "合肥基地" in result.answer_summary


def test_data_qa_service_returns_system_base_company_total_fee_variant() -> None:
    """验证 2026 基地 + 承运商总运费题已从 B 收进 A。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        result = service.query(LogisticsDataQaQueryRequest(question="帮我查一下2026年阜宁基地1月份晶茂物流总计运费是多少钱"))
        assert result.status is not None
        assert result.status.code == "OK"
        assert result.query_plan.query_key == "sys_total_fee_by_filters"
        assert result.query_plan.filters["base_code"] == "2"
        assert "阜宁基地" in result.answer_summary


def test_data_qa_service_returns_system_base_mw_variant() -> None:
    """验证 2026 基地发运量题会按基地过滤，不再误算全量。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        result = service.query(LogisticsDataQaQueryRequest(question="2026年1月份合肥基地总发运量是多少MW？"))
        assert result.status is not None
        assert result.status.code == "OK"
        assert result.query_plan.query_key == "sys_mw_and_trip_count"
        assert result.query_plan.filters["base_code"] == "1"
        assert "合肥基地" in result.answer_summary


def test_data_qa_service_returns_unsupported_for_supplier_price_outlier_question() -> None:
    """验证 supplier_price 分布与离群点诊断题会正式转入不支持。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        result = service.query(
            LogisticsDataQaQueryRequest(question="2026年assign_detail中的supplier_price分布如何？高价离群点集中在哪些任务或承运商？")
        )
        assert result.status is not None
        assert result.status.code == "UNSUPPORTED_QUESTION"
        assert result.query_plan.query_key is None


def test_data_qa_service_returns_hist_vehicle_trip_count_variant() -> None:
    """验证历史车型总车次简写问法已从 B 收进口径稳定的 A 类。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        result = service.query(LogisticsDataQaQueryRequest(question="问题1：25年全年17.5共发运多少车"))
        assert result.status is not None
        assert result.status.code == "OK"
        assert result.query_plan.query_key == "hist_vehicle_type_trip_count"


def test_data_qa_service_returns_system_unit_fee_by_month() -> None:
    """验证 2026 月度单瓦运输成本题已命中系统单瓦成本计划。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        result = service.query(LogisticsDataQaQueryRequest(question="2026年1月份单瓦运输成本是多少？"))
        assert result.status is not None
        assert result.status.code == "OK"
        assert result.query_plan.query_key == "sys_unit_fee_per_watt"
        assert len(result.result_table.rows) == 1


def test_data_qa_service_returns_special_total_fee_variant() -> None:
    """验证经营计划运费变体问法能稳定返回特殊业务总费用。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        result = service.query(LogisticsDataQaQueryRequest(question="问题2：26年 经营计划 运费是多少"))
        assert result.status is not None
        assert result.status.code == "OK"
        assert result.query_plan.query_key == "sys_special_total_fee"
        assert len(result.result_table.rows) == 1


def test_data_qa_service_returns_hist_route_pricing_result() -> None:
    """验证历史线路运价分析题已正式落入执行链路。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        result = service.query(LogisticsDataQaQueryRequest(question="帮我看下23年发往乌鲁木齐13m每车的运费均价是多少"))
        assert result.status is not None
        assert result.status.code == "OK"
        assert result.query_plan.query_key == "hist_route_pricing_analysis"
        assert len(result.result_table.rows) == 1


def test_data_qa_service_returns_carrier_ranking_result() -> None:
    """验证承运商运费排名题可直接返回前十结果。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        result = service.query(LogisticsDataQaQueryRequest(question="2025年各承运商按运费排名前十分别是谁？"))
        assert result.status is not None
        assert result.status.code == "OK"
        assert result.query_plan.query_key == "carrier_metric_ranking"
        assert len(result.result_table.rows) >= 1


def test_data_qa_service_returns_procurement_split_result() -> None:
    """验证 2026 招标/询比价发运量拆分题已批量收进 A。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        result = service.query(LogisticsDataQaQueryRequest(question="26年招标和询比价，发运量分别是多少"))
        assert result.status is not None
        assert result.status.code == "OK"
        assert result.query_plan.query_key == "sys_mw_by_procurement_type"
        assert len(result.result_table.rows) >= 2


def test_data_qa_service_returns_system_quality_rank_results() -> None:
    """验证 2026 任务量、填充率和解析成功率题都能稳定返回。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        city_rank = service.query(LogisticsDataQaQueryRequest(question="2026年送达城市任务量排名前十的是哪些城市？"))
        fill_rate = service.query(LogisticsDataQaQueryRequest(question="2026年各送达省份的delivery_distance填充率分别是多少？填充率最低的前十个省份是谁？"))
        parse_success = service.query(LogisticsDataQaQueryRequest(question="哪些承运商的送货单解析成功率最高，哪些最低？"))
        mapping_gap = service.query(LogisticsDataQaQueryRequest(question="2026年任务表中是否存在company_id在承运商主数据表里找不到映射的任务？"))
        extra_cost = service.query(LogisticsDataQaQueryRequest(question="2026年extra_cost_audited=1的主任务有多少个？主要集中在哪些承运商和省份？"))
        assert city_rank.status.code == "OK"
        assert fill_rate.status.code == "OK"
        assert parse_success.status.code == "OK"
        assert mapping_gap.status.code == "OK"
        assert extra_cost.status.code == "OK"


def test_data_qa_service_returns_round5_promoted_and_boundary_results() -> None:
    """验证 Round5 新推进进 A 和新转入 C 的题都按当前边界返回。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        route_result = service.query(LogisticsDataQaQueryRequest(question="合肥发江苏 17.5 车运费"))
        system_result = service.query(LogisticsDataQaQueryRequest(question="帮我查询2026 年的运量综合"))
        unit_fee_result = service.query(LogisticsDataQaQueryRequest(question="2月份单W运输成本是多少（（2月运费总价格+额外费用）/运输组件总W数）"))
        supplier_result = service.query(LogisticsDataQaQueryRequest(question="2026年assign_detail中的supplier_price分布如何？高价离群点集中在哪些任务或承运商？"))
        assert route_result.status.code == "OK"
        assert route_result.query_plan.query_key == "hist_route_pricing_analysis"
        assert any("2023-2025历史累计" in item for item in route_result.warnings)
        assert system_result.status.code == "OK"
        assert system_result.query_plan.query_key == "sys_mw_and_trip_count"
        assert any("截至目前累计" in item for item in system_result.warnings)
        assert unit_fee_result.status.code == "OK"
        assert unit_fee_result.query_plan.query_key == "sys_unit_fee_per_watt"
        assert any("默认按2026正式系统" in item or "默认按 2026正式系统" in item or "默认按2026正式系统月份口径" in item for item in unit_fee_result.warnings)
        assert supplier_result.status.code == "UNSUPPORTED_QUESTION"


def test_data_qa_service_returns_round3_promoted_customer_project_results() -> None:
    """验证 Round3 的客户/项目总运量题已批量收进 A。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        project_total = service.query(LogisticsDataQaQueryRequest(question="2.江苏苏美达电力运营有限公司 项目 总发运量是多少"))
        customer_rank = service.query(LogisticsDataQaQueryRequest(question="历史台账中总发运瓦数最高的前10个客户是谁？"))
        assert project_total.status is not None
        assert project_total.status.code == "OK"
        assert project_total.query_plan.query_key == "hist_customer_mw"
        assert customer_rank.status is not None
        assert customer_rank.status.code == "OK"
        assert customer_rank.query_plan.query_key == "hist_customer_mw_ranking"
        assert len(customer_rank.result_table.rows) == 10


def test_data_qa_service_returns_round3_city_carrier_avg_price_results() -> None:
    """验证 Round3 的城市承运商单车均价题已批量收进 A。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        for question in (
            "苏州城市发运中，不同物流公司的平均单价/车是多少？",
            "合肥城市发运中，不同物流公司的平均单价/车是多少？",
            "徐州城市发运中，不同物流公司的平均单价/车是多少？",
            "昭通城市发运中，不同物流公司的平均单价/车是多少？",
            "湖州城市发运中，不同物流公司的平均单价/车是多少？",
        ):
            result = service.query(LogisticsDataQaQueryRequest(question=question))
            assert result.status is not None
            assert result.status.code == "OK"
            assert result.query_plan.query_key == "hist_city_carrier_avg_fee_per_trip"
            assert len(result.result_table.rows) >= 1


def test_data_qa_service_returns_round3_business_clarification_results() -> None:
    """验证 Round5 已明确转 C 的题不会再停留在业务化澄清。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        address_result = service.query(LogisticsDataQaQueryRequest(question="统计一下24年创维客户发货的项目地运费金额超过20万的收货地址，并分别列出询比价和招标的发运量"))
        project_result = service.query(LogisticsDataQaQueryRequest(question="1.项目名称：国科新能源有限公司 已发出总运量是多少"))
        abnormal_result = service.query(LogisticsDataQaQueryRequest(question="“异常费用太高的城市有哪些？”——系统至少需要追问什么？"))
        assert address_result.status is not None
        assert address_result.status.code == "UNSUPPORTED_QUESTION"
        assert project_result.status is not None
        assert project_result.status.code == "UNSUPPORTED_QUESTION"
        assert abnormal_result.status is not None
        assert abnormal_result.status.code == "UNSUPPORTED_QUESTION"


def test_data_qa_service_returns_round4_business_clarification_results() -> None:
    """验证 Round4 新纳入的长期澄清题会稳定返回业务化追问。"""

    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        quarter_result = service.query(LogisticsDataQaQueryRequest(question="2023年一季度各区域运费分别是多少？请按区域排序展示。"))
        transport_result = service.query(LogisticsDataQaQueryRequest(question="2024年公路运输的平均单瓦成本是多少？"))
        parse_result = service.query(LogisticsDataQaQueryRequest(question="2026年派车任务的送货单解析状态分布（0/1/3/4）分别是多少？"))

        assert quarter_result.status is not None
        assert quarter_result.status.code == "CLARIFICATION_REQUIRED"
        assert quarter_result.query_plan.clarification_category == "quarter_area_metric_scope"

        assert transport_result.status is not None
        assert transport_result.status.code == "CLARIFICATION_REQUIRED"
        assert transport_result.query_plan.clarification_category == "transport_unit_fee_scope"

        assert parse_result.status is not None
        assert parse_result.status.code == "CLARIFICATION_REQUIRED"
        assert parse_result.query_plan.clarification_category == "parse_status_scope"


def test_data_qa_service_returns_round3_unsupported_correlation_result() -> None:
    """验证 Round3 的相关性分析题已正式转入 C 类不支持。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        result = service.query(LogisticsDataQaQueryRequest(question="历史台账中路程/KM与元/瓦是否呈显著正相关？哪些区域相关性最强？"))
        assert result.status is not None
        assert result.status.code == "UNSUPPORTED_QUESTION"
        assert result.supported is False


def test_data_qa_service_returns_clarification_status_for_ambiguous_question() -> None:
    """验证 B 类高频模糊题会稳定返回澄清状态和追问。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        result = service.query(LogisticsDataQaQueryRequest(question="最近物流成本是不是变高了？"))
        assert result.needs_clarification is True
        assert result.supported is False
        assert result.status is not None
        assert result.status.code == "CLARIFICATION_REQUIRED"
        assert len(result.clarification_questions) >= 2


def test_data_qa_service_returns_unsupported_status_for_eta_question() -> None:
    """验证 C 类 ETA 问题会稳定返回不支持状态。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        result = service.query(LogisticsDataQaQueryRequest(question="华东区域当前订单预计到达时间是什么时候？"))
        assert result.supported is False
        assert result.needs_clarification is False
        assert result.status is not None
        assert result.status.code == "UNSUPPORTED_QUESTION"
        assert result.query_plan.unsupported_category == "eta"
        assert result.query_plan.unsupported_suggestions
        assert "可改问" in result.answer_summary
        assert result.data_scope["unsupported"]["category"] == "eta"


def test_data_qa_service_returns_unsupported_for_model_design_question() -> None:
    """验证模型设计类问题会被规则层直接锁定为不支持。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        result = service.query(LogisticsDataQaQueryRequest(question="设计一个在途风险评分模型"))
        assert result.supported is False
        assert result.needs_clarification is False
        assert result.status is not None
        assert result.status.code == "UNSUPPORTED_QUESTION"
        assert result.query_plan.unsupported_category == "discussion"
        assert result.query_plan.unsupported_suggestions


def test_data_qa_service_assist_mode_only_recovers_a_whitelist_variant() -> None:
    """验证正式主链路接入 assist 后，只在 A 类白名单同构变体上恢复 query_key。"""
    with logistics_db() as db:
        llm_service = _build_live_llm_service(
            {
                "normalized_question": "26年1月发了多少MW，多少车",
                "intent": "aggregate",
                "metrics": ["shipment_mw", "shipment_trip_count"],
                "dimensions": [],
                "filters": {"year": 2026, "months": [1]},
                "time_range": {"year": 2026, "months": [1]},
                "source_scope": "system_2026",
                "candidate_query_keys": ["sys_mw_and_trip_count"],
                "normalized_terms": {"运量": "发运量", "多少车": "车次"},
                "needs_clarification": False,
                "clarification_questions": [],
                "unsupported_reason": None,
                "confidence": 0.95,
            }
        )
        guardrail_service = LogisticsLlmUnderstandingGuardrailService(
            llm_service=llm_service,
            enabled=True,
            mode="assist",
            sample_rate=1.0,
            audit_enabled=False,
        )
        service = LogisticsDataQaService(db=db, guardrail_service=guardrail_service)
        result = service.query(LogisticsDataQaQueryRequest(question="26年1月发了多少MW，多少车？"))
        assert result.status is not None
        assert result.status.code == "OK"
        assert result.query_plan.query_key == "sys_mw_and_trip_count"


def test_data_qa_service_assist_mode_does_not_break_b_clarification_boundary() -> None:
    """验证 assist 接入后，B 类题仍由规则层锁定澄清，不会被 LLM 改成 success。"""
    with logistics_db() as db:
        llm_service = _build_live_llm_service(
            {
                "normalized_question": "最近物流成本是不是变高了",
                "intent": "aggregate",
                "metrics": ["total_fee"],
                "dimensions": [],
                "filters": {"year": 2025},
                "time_range": {"year": 2025},
                "source_scope": "historical",
                "candidate_query_keys": ["hist_monthly_total_fee_by_year"],
                "normalized_terms": {},
                "needs_clarification": False,
                "clarification_questions": [],
                "unsupported_reason": None,
                "confidence": 0.99,
            }
        )
        guardrail_service = LogisticsLlmUnderstandingGuardrailService(
            llm_service=llm_service,
            enabled=True,
            mode="assist",
            sample_rate=1.0,
            audit_enabled=False,
        )
        service = LogisticsDataQaService(db=db, guardrail_service=guardrail_service)
        result = service.query(LogisticsDataQaQueryRequest(question="最近物流成本是不是变高了？"))
        assert result.status is not None
        assert result.status.code == "CLARIFICATION_REQUIRED"
        assert result.needs_clarification is True


@pytest.mark.parametrize(
    ("question", "expected_tokens"),
    [
        ("25年合肥发广东省，17.5车，每月平均运费是多少？", ["13,089"]),
        ("2026年各承运商的SIGNEDFOR签收率分别是多少？排名前十和后十是谁？", ["浙江海舜供应链管理有限公司", "苏州威洋供应链有限公司", "远孚物流集团有限公司", "常州安提物流有限公司"]),
        ("2024年同一客户由多个始发地发货的客户有多少个？分别是哪些客户？", ["119"]),
        ("对比2023年华东区域计划发运件数与实际发运件数的偏差率。", ["0.1"]),
    ],
)
def test_data_qa_service_focus_failures_match_live_results(question: str, expected_tokens: list[str]) -> None:
    """验证失败题当前输出与真实 SQL 结果一致，避免把数据问题误判为代码问题。"""
    with logistics_db() as db:
        service = LogisticsDataQaService(db=db)
        result = service.query(LogisticsDataQaQueryRequest(question=question))
        answer_text = result.answer_summary
        for token in expected_tokens:
            assert token in answer_text or any(token in str(row) for row in result.result_table.rows)


def test_data_qa_repository_focus_failure_sql_review() -> None:
    """用真实 SQL 复核 Q02/Q16/Q17/Q19 的当前数值。"""
    with logistics_db() as db:
        repo = LogisticsDataQaRepository(db)

        q02 = repo.hist_avg_fee_by_month(year=2025, origin_place="合肥", province="广东", vehicle_type="17.5")
        assert int(q02["overall_avg_fee"] or 0) == 13089

        q16 = repo.sys_signedfor_rate_by_carrier(year=2026)
        top10_names = {row["company_name"] for row in q16["top10"]}
        bottom10_names = {row["company_name"] for row in q16["bottom10"]}
        assert "浙江海舜供应链管理有限公司" in top10_names
        assert "苏州威洋供应链有限公司" in top10_names
        assert "远孚物流集团有限公司" in top10_names
        assert "常州安提物流有限公司" in bottom10_names

        q17 = repo.hist_multi_origin_customers(year=2024)
        assert int(q17["customer_count"] or 0) == 119

        q19 = repo.hist_plan_actual_deviation(year=2023, region_name="华东")
        assert Decimal(str(q19["deviation_rate"])) == Decimal("0.1")


def test_data_qa_planner_returns_business_clarification_for_comparison_basis_question() -> None:
    """验证比较标准类问题会命中业务化澄清模板。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2023-2025区域发运份额变化最大的区域是哪一个？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "comparison_basis_scope"
    assert any("比较" in item or "变化最大" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_mapping_consistency_question() -> None:
    """验证映射口径类问题会命中业务化澄清模板。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("物流公司、物流供应商、承运商三种问法在系统里是否映射为同一字段口径？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "mapping_consistency_scope"
    assert any("字段" in item or "口径" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_route_metric_question() -> None:
    """验证线路指标类问题会命中业务化澄清模板。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2023-2025期间，620W产品发往新疆的平均路程是多少？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "route_metric_scope"
    assert any("平均路程" in item or "delivery_distance" in item or "平均值" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_data_consistency_question() -> None:
    """验证数据一致性类问题会命中业务化澄清模板。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("哪些记录存在日计划发运件数为空或为0，但日实际发运件数大于0？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "data_consistency_scope"
    assert any("问题记录数量" in item or "异常明细" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_quarter_area_metric_question() -> None:
    """验证季度区域统计类问题会命中正式业务化澄清模板。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2023年一季度各区域运费分别是多少？请按区域排序展示。")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "quarter_area_metric_scope"
    assert any("季度" in item or "排序" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_transport_unit_fee_question() -> None:
    """验证运输方式平均单瓦成本问题会命中正式业务化澄清模板。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2024年公路运输的平均单瓦成本是多少？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "transport_unit_fee_scope"
    assert any("单瓦成本" in item or "额外费用" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_special_procurement_unit_fee_question() -> None:
    """验证特殊业务口径平均单瓦成本会命中采购口径澄清模板。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2025年经营计划场景下的平均单瓦成本是多少？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "procurement_metric_scope"
    assert any("场景标签" in item or "单瓦成本" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_parse_distribution_question() -> None:
    """验证解析状态分布类问题会命中正式业务化澄清模板。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2026年派车任务的送货单解析状态分布（0/1/3/4）分别是多少？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "parse_status_scope"
    assert any("状态" in item or "占比" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_allocate_state_breakdown_question() -> None:
    """验证 allocate_task 各状态数量类问题会命中正式业务化澄清模板。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2026年allocate_task各状态的数量分别是多少？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "state_breakdown_scope"
    assert any("allocate_task" in item or "占比" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_state_ranking_question() -> None:
    """验证状态排名类问题会命中正式业务化澄清模板。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2026年哪些省份的PREASSIGN待派车任务最多？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "state_ranking_scope"
    assert any("最多" in item or "占比" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_task_split_question() -> None:
    """验证 ship_task 拆分最多类问题会命中正式业务化澄清模板。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2026年单个ship_task被拆分为派车任务最多的是哪些任务？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "task_split_scope"
    assert any("拆分最多" in item or "派车任务" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_plate_conflict_question() -> None:
    """验证同车牌多任务冲突类问题会命中正式业务化澄清模板。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2026年是否存在同一车牌在同一天关联多个不同的派车任务？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "data_consistency_scope"
    assert any("异常明细" in item or "问题记录数量" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_delivery_city_missing_question() -> None:
    """验证送达省市缺失类问题会命中正式业务化澄清模板。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2026年哪些任务存在送达省市缺失？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "data_consistency_scope"
    assert any("异常明细" in item or "问题记录数量" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_field_alias_comparison_question() -> None:
    """验证跨年车辆数 / 车次字段差异问题会命中字段口径澄清模板。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2023台账同类字段有“车辆数”，2025台账为“车次”，若用户要求跨年比较车辆效率，系统如何处理？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "field_alias_comparison_scope"
    assert any("车次" in item and "车辆数" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_unsupported_for_warehouse_dimension_question() -> None:
    """验证仓库分配明细类问题不会被误判为可靠统计能力。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("不同仓库的平均分配明细数量分别是多少？")
    assert plan.intent == "unsupported"
    assert "仓库维度" in (plan.unsupported_reason or "")
    assert plan.unsupported_category == "warehouse_dimension_unreliable"
    assert any("allocate" in item or "仓库" in item for item in plan.unsupported_suggestions)


def test_data_qa_planner_returns_unsupported_for_system_response_strategy_question() -> None:
    """验证系统追问策略类问题会正式进入不支持边界。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("“哪些任务有问题？”——系统至少需要先界定哪些‘问题’类型？")
    assert plan.intent == "unsupported"
    assert "系统追问" in (plan.unsupported_reason or "")
    assert plan.unsupported_category in {"clarification_design", "system_response_strategy"}
    assert plan.unsupported_suggestions


def test_data_qa_planner_keeps_old_c_a_candidate_as_supported_plan() -> None:
    """验证旧 C 中当前已可答的题不会继续被硬拒答。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2023年华东区域总发运量是多少MW？")
    assert plan.intent == "aggregate"
    assert plan.query_key == "hist_mw_summary"
    assert plan.unsupported_reason is None


def test_data_qa_planner_keeps_old_c_b_candidate_as_clarification() -> None:
    """验证旧 C 中当前应澄清的题不会继续被硬拒答。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2024年华东区域通过公路发运的总件数是多少？")
    assert plan.intent == "clarification"
    assert plan.needs_clarification is True
    assert plan.query_key is None
    assert plan.unsupported_reason is None


def test_data_qa_planner_returns_bcr1_abnormal_reason_clarification() -> None:
    """验证 BCR1 异常原因题会追问异常定义、时间范围和输出形态。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("识别合肥始发地在历史数据中可能存在的异常高成本运输记录，并解释异常原因。")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "abnormal_or_reason_scope"
    assert any("异常" in item or "高成本" in item for item in plan.clarification_questions)
    assert any("明细" in item or "汇总" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_bcr1_transport_mode_metric_clarification() -> None:
    """验证 BCR1 运输方式指标题会追问运输方式、指标单位和拆分口径。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2024年华东区域通过公路发运的总件数是多少？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "transport_mode_metric_scope"
    assert any("运输方式" in item for item in plan.clarification_questions)
    assert any("单位" in item or "MW" in item or "件数" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_bcr1_procurement_metric_clarification() -> None:
    """验证 BCR1 采购方式题会追问采购方式、指标、时间和分组维度。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2024年客户华阳按询比价和招标拆分后，发运量分别是多少？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "procurement_metric_scope"
    assert any("采购方式" in item for item in plan.clarification_questions)
    assert any("承运商" in item or "区域" in item or "客户" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_bcr1_route_or_address_clarification() -> None:
    """验证 BCR1 线路地址题会追问始发目的地、指标单位和车型限制。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2023年合肥基地发往江苏省的平均运费是多少？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "route_or_address_scope"
    assert any("始发地" in item or "目的地" in item for item in plan.clarification_questions)
    assert any("车型" in item or "运输方式" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_bcr2_system_state_clarification() -> None:
    """验证 BCR2 系统状态题会追问状态枚举、指标和分组维度。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2026主任务表缺少显式成本字段时，如何利用历史台账估算任务级物流成本区间？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "system_state_scope"
    assert any("状态枚举" in item or "SIGNEDFOR" in item for item in plan.clarification_questions)
    assert any("指标" in item or "任务数" in item or "占比" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_bcr2_data_consistency_clarification() -> None:
    """验证 BCR2 对账一致性题会追问对账对象、差异阈值和比较维度。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("若contract_number、bidding_number、inquiry_number长期缺失，会对经营计划部的对账与归因造成哪些影响？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "data_consistency_scope"
    assert any("对账对象" in item or "一致性对象" in item for item in plan.clarification_questions)
    assert any("差异阈值" in item or "异常判定" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_bcr2_vehicle_or_trip_clarification() -> None:
    """验证 BCR2 历史总车次题会追问车次/车辆数口径和车型口径。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2024年1月份总车次是多少？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "vehicle_or_trip_scope"
    assert any("车次/车辆数口径" in item or "唯一车辆数" in item for item in plan.clarification_questions)
    assert any("车型口径" in item or "17.5" in item or "13 米" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_bcr3_vehicle_type_trip_clarification() -> None:
    """验证 BCR3 基地车型车次题会追问车次、车型和分组维度口径。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2024年合肥基地9.6车全年共发运多少车次？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "vehicle_or_trip_scope"
    assert any("车次/车辆数口径" in item for item in plan.clarification_questions)
    assert any("车型口径" in item or "9.6" in item for item in plan.clarification_questions)
    assert any("分组维度" in item or "基地" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_bcr3_customer_project_clarification() -> None:
    """验证 BCR3 客户总运费题会追问客户/项目名称、指标和排名口径。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2024年客户华阳总运费是多少？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "customer_project_scope"
    assert any("客户/项目名称" in item for item in plan.clarification_questions)
    assert any("指标口径" in item for item in plan.clarification_questions)
    assert any("是否需要排名" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_bcr3_ranking_basis_clarification() -> None:
    """验证 BCR3 排名题会追问排名指标、方向和 TopN 数量。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2024年长距离订单（路程≥1500KM）中，不同物流公司的平均总费用排名如何？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "ranking_basis_scope"
    assert any("排名指标" in item for item in plan.clarification_questions)
    assert any("排名方向" in item for item in plan.clarification_questions)
    assert any("TopN 数量" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_carrier_unit_fee_question() -> None:
    """验证承运商全年平均单瓦成本题会先澄清主体和费用口径。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2023年晶茂物流全年平均单瓦运输成本是多少？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "carrier_unit_fee_scope"
    assert any("承运商" in item or "客户" in item for item in plan.clarification_questions)


def test_data_qa_planner_returns_business_clarification_for_driver_identity_consistency_question() -> None:
    """验证司机手机号 / 身份证一致性问题会命中正式澄清模板。"""

    planner = LogisticsDataQaPlanner()
    plan = planner.build_plan("2026年司机手机号与身份证号是否存在一人多号或一号多人情况？")
    assert plan.intent == "clarification"
    assert plan.clarification_category == "driver_identity_consistency_scope"
    assert any("异常数量" in item or "异常司机" in item for item in plan.clarification_questions)

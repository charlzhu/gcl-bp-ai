"""物流 E2E 鲁棒性修复回归测试。

本文件覆盖 E2E 验收中暴露出的高频问法变体，防止后续回归：
1. 跨年省份总费用不能只取末尾年份；
2. 季度车辆数/车次需要按季度月份聚合；
3. “多少件”“元每瓦”“排前五”等自然表达要进入已支持 query_key。
"""

from __future__ import annotations

from backend.app.db.session import SessionLocal
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService


def test_cross_year_province_total_fee_uses_years_filter() -> None:
    """验证跨年省份总费用使用 years 列表，而不是只取 2025 年。"""

    plan = LogisticsDataQaPlanner().build_plan("2023到2025年江苏的物流总运费是多少？")

    assert plan.query_key == "hist_total_fee_by_province"
    assert plan.filters["years"] == [2023, 2024, 2025]
    assert plan.filters["year"] is None
    assert plan.filters["province"] == "江苏"


def test_quarter_vehicle_count_uses_shipment_trip_metric() -> None:
    """验证“车辆数”按车次指标和季度月份过滤进入汇总 query。"""

    plan = LogisticsDataQaPlanner().build_plan("24年一季度物流发运车辆数是多少？")

    assert plan.query_key == "hist_total_fee_summary"
    assert plan.metrics == ["shipment_trip_count"]
    assert plan.filters["year"] == 2024
    assert plan.filters["months"] == [1, 2, 3]


def test_natural_language_variants_route_to_supported_queries() -> None:
    """验证 E2E 发现的自然表达变体不会退回追问。"""

    planner = LogisticsDataQaPlanner()
    cases = {
        "华东区域历史物流一共发运了多少件？": "hist_quantity_by_region",
        "2024年华东区域通过公路发运的总件数是多少?": "hist_quantity_by_region",
        "请把华东各运输方式平均元每瓦按从低到高列出来": "hist_avg_fee_per_watt_by_transport",
        "江苏省客户按总费用排前五，并列出总费用和总瓦数": "hist_top_customers_fee_and_mw_by_province",
    }
    for question, query_key in cases.items():
        plan = planner.build_plan(question)
        assert plan.query_key == query_key
        assert not plan.needs_clarification
    transport_plan = planner.build_plan("2024年华东区域通过公路发运的总件数是多少?")
    assert transport_plan.filters["year"] == 2024
    assert transport_plan.filters["region_name"] == "华东"
    assert transport_plan.filters["transport_mode"] == "公路"


def test_service_answers_key_robustness_cases() -> None:
    """验证服务层返回关键数值，覆盖 SQL 聚合口径。"""

    cases = {
        "2023到2025年江苏的物流总运费是多少？": "10,048,300",
        "24年一季度物流发运车辆数是多少？": "2,811",
        "华东区域历史物流一共发运了多少件？": "13,877,138",
        "2024年华东区域通过公路发运的总件数是多少?": "5,379,298",
        "请把华东各运输方式平均元每瓦按从低到高列出来": "0.008648",
    }
    with SessionLocal() as db:
        service = LogisticsDataQaService(db=db)
        for question, expected_text in cases.items():
            result = service.query(LogisticsDataQaQueryRequest(question=question))
            assert not result.needs_clarification
            visible_text = result.answer_summary + " " + str(result.result_table.rows)
            assert expected_text in visible_text
        unit_fee_result = service.query(LogisticsDataQaQueryRequest(question="请把华东各运输方式平均元每瓦按从低到高列出来"))
        assert any("SUM(total_fee) / SUM(actual_watt)" in item for item in unit_fee_result.calculation_logic)

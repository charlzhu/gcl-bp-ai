from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.slot_extractor import LogisticsSlotExtractor


def test_monthly_total_fee_question_does_not_extract_fake_carrier() -> None:
    """月份范围题不能把“1到3月每个月”误抽成承运商。"""

    question = "2026 年 1 到3 月，每个月的总运费是多少"
    extractor = LogisticsSlotExtractor()
    planner = LogisticsDataQaPlanner(slot_extractor=extractor)

    assert extractor.extract_company_name(question) is None

    plan = planner.build_plan(question)
    assert plan.query_key == "sys_total_fee_by_filters"
    assert plan.filters["year"] == 2026
    assert plan.filters["months"] == [1, 2, 3]
    assert plan.filters["monthly_breakdown"] is True
    assert "company_name" not in plan.filters
    assert plan.dimensions == ["biz_month"]
    assert plan.group_by == ["biz_month"]


def test_real_carrier_phrase_is_still_supported() -> None:
    """收紧月份清洗后，真实物流公司名称仍应能被识别。"""

    extractor = LogisticsSlotExtractor()

    assert extractor.extract_company_name("晶茂物流运费占全年总运费的比例") == "晶茂物流"
    assert extractor.extract_company_name("2026年1月顺丰物流总运费是多少") == "顺丰物流"

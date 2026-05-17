"""历史线路运价问法回归测试。

本文件锁定“始发地 + 至/到 + 目的城市 + 车型 + 运费指标”这类明确线路问法，
避免用户已给足槽位时被误判为需要澄清。
"""

from __future__ import annotations

from backend.app.db.session import SessionLocal
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService


def test_2025_hefei_to_maanshan_17_5_avg_fee_answers_without_clarification() -> None:
    """验证“合肥至马鞍山 17.5 米车平均运费”可直接回答。

    参数：无。
    返回值：无；通过断言验证 planner 槽位、service 结果和确定性均价。
    业务逻辑：用户已给出年份、始发地、目的城市、车型和平均运费指标，应进入历史线路运价分析；
    “至/到”是线路表达，不应因为目的城市未抽取而进入通用澄清；均价按总费用 / 总车次计算。
    """

    question = "2025年合肥至马鞍山17.5米车的平均运费"
    plan = LogisticsDataQaPlanner().build_plan(question)

    assert plan.query_key == "hist_route_pricing_analysis"
    assert not plan.needs_clarification
    assert plan.filters == {
        "years": [2025],
        "vehicle_type": "17.5",
        "view_mode": "avg_fee",
        "price_metric": "total_fee",
        "origin_place": "合肥",
        "city": "马鞍山",
    }

    with SessionLocal() as db:
        result = LogisticsDataQaService(db=db).query(LogisticsDataQaQueryRequest(question=question, use_llm=False))

    assert not result.needs_clarification
    assert result.result_table is not None
    row = result.result_table.rows[0]
    assert int(row["avg_fee"] or 0) == 1557
    assert int(row["total_fee"] or 0) == 14009
    assert int(row["shipment_trip_count"] or 0) == 9
    assert int(row["row_count"] or 0) == 2
    assert "合肥" in result.answer_summary
    assert "马鞍山" in result.answer_summary
    assert "1,557" in result.answer_summary


def test_23_to_25_hefei_shenzhen_13_avg_fee_hyphen_range_answers_without_clarification() -> None:
    """验证“23年-25年 合肥-深圳 13米均价分别是多少”可直接回答。

    参数：无。
    返回值：无；通过断言验证两位年份区间、横线线路、车型和均价指标均被稳定识别。
    业务逻辑：用户已给出时间区间、始发地、目的城市、车型和均价指标，应按 2023-2025 年逐年返回；
    某一年没有匹配记录也要保留空值行，不能要求用户补充口径。
    """

    question = "23年-25年，3年间合肥-深圳13米均价分别是多少"
    plan = LogisticsDataQaPlanner().build_plan(question)

    assert plan.query_key == "hist_route_pricing_analysis"
    assert not plan.needs_clarification
    assert plan.filters == {
        "years": [2023, 2024, 2025],
        "vehicle_type": "13",
        "view_mode": "year_compare",
        "price_metric": "total_fee",
        "origin_place": "合肥",
        "city": "深圳",
    }

    with SessionLocal() as db:
        result = LogisticsDataQaService(db=db).query(LogisticsDataQaQueryRequest(question=question, use_llm=False))

    assert not result.needs_clarification
    assert result.result_table is not None
    rows_by_year = {int(row["biz_year"]): row for row in result.result_table.rows}
    assert set(rows_by_year) == {2023, 2024, 2025}
    assert rows_by_year[2023]["avg_fee"] is None
    assert rows_by_year[2023]["total_fee"] is None
    assert int(rows_by_year[2023]["shipment_trip_count"] or 0) == 0
    assert int(rows_by_year[2023]["row_count"] or 0) == 0
    assert rows_by_year[2024]["avg_fee"] is None
    assert rows_by_year[2024]["total_fee"] is None
    assert int(rows_by_year[2024]["shipment_trip_count"] or 0) == 0
    assert int(rows_by_year[2024]["row_count"] or 0) == 0
    assert int(rows_by_year[2025]["avg_fee"] or 0) == 9623
    assert int(rows_by_year[2025]["total_fee"] or 0) == 28870
    assert int(rows_by_year[2025]["shipment_trip_count"] or 0) == 3
    assert int(rows_by_year[2025]["row_count"] or 0) == 3
    assert "合肥" in result.answer_summary
    assert "深圳" in result.answer_summary
    assert "2023年" in result.answer_summary
    assert "2024年" in result.answer_summary
    assert "2025年" in result.answer_summary


def test_route_pricing_avg_fee_uses_total_fee_divided_by_trip_count_not_row_average() -> None:
    """验证线路“均价”按总费用除以车次数，而不是按明细行直接平均。

    参数：无。
    返回值：无；通过断言锁定加权单车均价、总费用、车次数和明细行数。
    业务逻辑：同一线路可能一行代表多车次，均价必须使用 SUM(total_fee) / SUM(shipment_trip_count)；
    若误用 AVG(total_fee)，本用例会得到约 272,108 元而不是 16,745 元。
    """

    question = "2025年合肥到乌苏17.5米车均价是多少"
    plan = LogisticsDataQaPlanner().build_plan(question)

    assert plan.query_key == "hist_route_pricing_analysis"
    assert not plan.needs_clarification
    assert plan.filters == {
        "years": [2025],
        "vehicle_type": "17.5",
        "view_mode": "avg_fee",
        "price_metric": "total_fee",
        "origin_place": "合肥",
        "city": "乌苏",
    }

    with SessionLocal() as db:
        result = LogisticsDataQaService(db=db).query(LogisticsDataQaQueryRequest(question=question, use_llm=False))

    assert not result.needs_clarification
    assert result.result_table is not None
    row = result.result_table.rows[0]
    assert int(row["total_fee"] or 0) == 7619020
    assert int(row["shipment_trip_count"] or 0) == 455
    assert int(row["row_count"] or 0) == 28
    assert int(row["avg_fee"] or 0) == 16745
    assert int(row["avg_fee"] or 0) != 272108
    assert "16,745" in result.answer_summary


def test_unknown_origin_to_maanshan_route_pricing_still_requires_clarification() -> None:
    """验证未知始发地不会因“至/到”表达被误放行为全始发线路。

    参数：无。
    返回值：无；通过断言确认当前无法稳定识别的始发地仍需澄清。
    业务逻辑：修复只补充受控始发地“合肥/阜宁”的线路连接词，不能把未知始发地静默降级为仅按目的城市过滤。
    """

    plan = LogisticsDataQaPlanner().build_plan("2025年广德至马鞍山17.5米车的平均运费")

    assert plan.query_key != "hist_route_pricing_analysis"
    assert plan.needs_clarification


def test_multihop_unknown_origin_to_hefei_maanshan_still_requires_clarification() -> None:
    """验证多段路径里的中间“合肥至马鞍山”不会被误当成完整始发线路。

    参数：无。
    返回值：无；通过断言确认包含未知前置始发地的多段路径仍需澄清。
    业务逻辑：当问句是“广德到合肥至马鞍山”时，合肥只是路径中间片段，不能忽略广德并按合肥始发直答。
    """

    plan = LogisticsDataQaPlanner().build_plan("2025年广德到合肥至马鞍山17.5米车的平均运费")

    assert plan.query_key != "hist_route_pricing_analysis"
    assert plan.needs_clarification


def test_route_pricing_arrow_connector_is_not_added_without_business_confirmation() -> None:
    """验证本次最小修复不额外扩展箭头连接词。

    参数：无。
    返回值：无；通过断言确认非本次需求的箭头连接符仍走澄清。
    业务逻辑：本次只补齐业务已反馈的自然语言连接词和普通横线，不额外支持箭头等复合路径符号，避免扩大匹配边界。
    """

    plan = LogisticsDataQaPlanner().build_plan("2025年合肥->马鞍山17.5米车的平均运费")

    assert plan.query_key != "hist_route_pricing_analysis"
    assert plan.needs_clarification


def test_multihop_after_controlled_origin_still_requires_clarification() -> None:
    """验证受控始发地后的多段路径不会把整段中转路线吞成目的城市。

    参数：无。
    返回值：无；通过断言确认“合肥至马鞍山到南京”仍需澄清。
    业务逻辑：历史线路运价当前只支持单一始发地到单一目的城市，多段路径必须澄清，不能把“马鞍山到南京”当成城市。
    """

    plan = LogisticsDataQaPlanner().build_plan("2025年合肥至马鞍山到南京17.5米车的平均运费")

    assert plan.query_key != "hist_route_pricing_analysis"
    assert plan.needs_clarification

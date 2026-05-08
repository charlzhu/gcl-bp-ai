"""物流全量 E2E 失败闭环第一轮回归测试。

本文件覆盖 1391 条样例题全量执行后剩余 FAIL 中的高优先级修复：
1. 明确“区域 + 运输方式 + 总件数”应进入确定性件数汇总，而不是被通用运输方式澄清策略截断；
2. 多年逐月 + 发运量 + 总费用 + 年度拆分属于复杂多指标报表，当前应业务化追问，不能返回单指标 12 个月汇总冒充完整答案。
"""

from __future__ import annotations

from backend.app.db.session import SessionLocal
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService


def test_region_transport_total_quantity_is_supported() -> None:
    """验证 Q0079 题型按区域、年份、运输方式过滤后返回总件数。

    参数：无。
    返回值：无；通过断言验证 planner 槽位和 service 结果。
    业务逻辑：用户已明确时间、区域、运输方式和指标，不应再要求澄清运输方式同义口径。
    """

    question = "2024年华东区域通过公路发运的总件数是多少?"
    plan = LogisticsDataQaPlanner().build_plan(question)

    assert plan.query_key == "hist_quantity_by_region"
    assert not plan.needs_clarification
    assert plan.filters == {"year": 2024, "region_name": "华东", "transport_mode": "公路"}

    with SessionLocal() as db:
        result = LogisticsDataQaService(db=db).query(LogisticsDataQaQueryRequest(question=question))

    assert not result.needs_clarification
    assert "5,379,298" in result.answer_summary


def test_missing_time_defaults_to_2023_2026_total_mw() -> None:
    """验证未给年月日时，总运量默认查询 2023-2026 全时间范围。

    参数：无。
    返回值：无；通过断言验证 planner 和 service 的默认时间范围。
    业务逻辑：用户未写时间条件不等于问题不明确，默认按 2023-2026 全部物流数据汇总，其中 2023-2025 来自历史台账、2026 来自系统数据。
    """

    question = "总运量是多少MW"
    plan = LogisticsDataQaPlanner().build_plan(question)

    assert plan.query_key == "mixed_mw_summary_2023_2026"
    assert not plan.needs_clarification
    assert plan.filters == {"years": [2023, 2024, 2025, 2026], "months": None}

    with SessionLocal() as db:
        result = LogisticsDataQaService(db=db).query(LogisticsDataQaQueryRequest(question=question))

    assert not result.needs_clarification
    assert "2023-2026" in result.answer_summary
    assert "MW" in result.answer_summary



def test_missing_time_defaults_to_2023_2026_total_fee_with_region() -> None:
    """验证未给年月日时，区域总费用默认查询 2023-2026 全时间范围。

    参数：无。
    返回值：无；通过断言验证区域过滤和默认时间范围。
    业务逻辑：问题已经明确指标和区域，只是没有时间条件，应默认全时间查询，而不是追问年份。
    """

    question = "华东区域总费用是多少"
    plan = LogisticsDataQaPlanner().build_plan(question)

    assert plan.query_key == "mixed_total_fee_summary_2023_2026"
    assert not plan.needs_clarification
    assert plan.filters == {"years": [2023, 2024, 2025, 2026], "months": None, "region_name": "华东"}

    with SessionLocal() as db:
        result = LogisticsDataQaService(db=db).query(LogisticsDataQaQueryRequest(question=question))

    assert not result.needs_clarification
    assert "2023-2026" in result.answer_summary
    assert "华东区域" in result.answer_summary
    assert "总运费" in result.answer_summary



def test_year_only_total_mw_is_supported_without_extra_clarification() -> None:
    """验证明确年份 + 总运量 + MW 口径的问题直接返回历史发运量。

    参数：无。
    返回值：无；通过断言验证 planner 与 service 都不会进入澄清。
    业务逻辑：用户已经给出 2023 年和 MW 运量口径，未限定区域/月份时应按历史全年总运量统计。
    """

    question = "2023年一年总共的运量是多少MW"
    plan = LogisticsDataQaPlanner().build_plan(question)

    assert plan.query_key == "hist_mw_summary"
    assert not plan.needs_clarification
    assert plan.filters == {"year": 2023, "months": None}

    with SessionLocal() as db:
        result = LogisticsDataQaService(db=db).query(LogisticsDataQaQueryRequest(question=question))

    assert not result.needs_clarification
    assert "2023年" in result.answer_summary
    assert "MW" in result.answer_summary



def test_clarification_audit_quantity_word_defaults_to_mw_for_hist_total() -> None:
    """验证“多少量/合计多少量”默认按 MW 发运量回答。

    参数：无。
    返回值：无；通过断言验证原本被澄清的问题进入历史发运量汇总。
    业务逻辑：用户已给出 2023 年和物流发运主体，“量”在物流经营问答中默认按当前稳定 MW 口径，不应再追问。
    """

    question = "2023年物流发运合计多少量?"
    plan = LogisticsDataQaPlanner().build_plan(question)

    assert plan.query_key == "hist_mw_summary"
    assert not plan.needs_clarification
    assert plan.filters == {"year": 2023, "months": None}

    with SessionLocal() as db:
        result = LogisticsDataQaService(db=db).query(LogisticsDataQaQueryRequest(question=question))

    assert not result.needs_clarification
    assert "2023年" in result.answer_summary
    assert "总发运量" in result.answer_summary
    assert "MW" in result.answer_summary



def test_clarification_audit_quantity_word_defaults_to_mw_for_hist_carrier() -> None:
    """验证带承运商简称的“发运多少量”默认按 MW 统计。

    参数：无。
    返回值：无；通过断言验证“英赋嘉”进入历史承运商过滤。
    业务逻辑：英赋嘉是当前台账中已校验的历史承运商别名，问题已明确年份和发运量含义，不应要求用户补充主体或单位。
    """

    question = "2023年英赋嘉发运多少量?"
    plan = LogisticsDataQaPlanner().build_plan(question)

    assert plan.query_key == "hist_mw_summary"
    assert not plan.needs_clarification
    assert plan.filters == {"year": 2023, "months": None, "carrier_name": "英赋嘉"}

    with SessionLocal() as db:
        result = LogisticsDataQaService(db=db).query(LogisticsDataQaQueryRequest(question=question))

    assert not result.needs_clarification
    assert "英赋嘉" in result.answer_summary
    assert "MW" in result.answer_summary



def test_clarification_audit_2026_special_scope_total_mw_defaults_to_cumulative() -> None:
    """验证 2026 特殊业务口径总发运量可按当前累计直接回答。

    参数：无。
    返回值：无；通过断言验证辅料送样、经营计划、刘娟用车都不再因缺月份被澄清。
    业务逻辑：用户已给出 2026 年、特殊业务范围和总发运量，未给月份时按系统侧当前累计口径返回，并在结果中暴露数据范围。
    """

    cases = [
        ("2026年辅料送样总发运量是多少?", "sample"),
        ("2026年经营计划总发运量是多少?", "planning"),
        ("2026年刘娟用车总发运量是多少?", "liujuan"),
    ]
    planner = LogisticsDataQaPlanner()
    with SessionLocal() as db:
        service = LogisticsDataQaService(db=db)
        for question, special_scope in cases:
            plan = planner.build_plan(question)
            assert plan.query_key == "sys_mw_and_trip_count"
            assert not plan.needs_clarification
            assert plan.metrics == ["shipment_mw"]
            assert plan.filters == {
                "year": 2026,
                "months": None,
                "special_scope": special_scope,
                "default_ytd_scope": True,
            }

            result = service.query(LogisticsDataQaQueryRequest(question=question))
            assert not result.needs_clarification
            assert "2026年" in result.answer_summary
            assert "合计发运量" in result.answer_summary
            assert "MW" in result.answer_summary



def test_clarification_audit_avg_pallet_per_vehicle_is_supported() -> None:
    """验证平均每车装载托数按非空字段平均值直接回答。

    参数：无。
    返回值：无；通过断言验证明确年份、月份和始发地的问题不再澄清。
    业务逻辑：历史台账已有 pallet_per_vehicle 字段，问题已明确时间和始发地；默认按非空发运记录平均，避免把可算字段误判为口径缺失。
    """

    question = "2024-01从合肥始发的订单中,平均每车装载托数是多少?"
    plan = LogisticsDataQaPlanner().build_plan(question)

    assert plan.query_key == "hist_avg_pallet_per_vehicle"
    assert not plan.needs_clarification
    assert plan.filters == {"year": 2024, "months": [1], "origin_place": "合肥"}

    with SessionLocal() as db:
        result = LogisticsDataQaService(db=db).query(LogisticsDataQaQueryRequest(question=question))

    assert not result.needs_clarification
    assert "平均每车装载托数" in result.answer_summary
    assert result.result_table.rows[0]["valid_record_count"] > 0



def test_clarification_audit_origin_vehicle_loading_summary_is_supported() -> None:
    """验证“始发地 + 各车型 + 装载托数”汇总表可直接回答。

    参数：无。
    返回值：无；通过断言验证已明确始发地和车型分组的问题不再被装载托数口径澄清截断。
    业务逻辑：历史台账已有 shipment_trip_count、actual_qty、total_fee、pallet_per_vehicle 字段；
    对“平均每车装载托数”默认使用非空 pallet_per_vehicle 平均，并在计算逻辑中说明空值处理。
    """

    question = "请统计合肥始发各车型的车次、发运件数、总费用、平均每车装载托数，并用车型汇总表展示？"
    plan = LogisticsDataQaPlanner().build_plan(question)

    assert plan.query_key == "hist_origin_vehicle_breakdown_summary"
    assert not plan.needs_clarification
    assert plan.metrics == [
        "shipment_trip_count",
        "shipment_count",
        "total_fee",
        "avg_fee_per_trip",
        "avg_pallet_per_vehicle",
    ]
    assert plan.dimensions == ["required_vehicle_type"]
    assert plan.filters == {
        "years": [2023, 2024, 2025],
        "origin_place": "合肥",
        "source_scope": "hist_pallet_metric",
    }

    with SessionLocal() as db:
        result = LogisticsDataQaService(db=db).query(LogisticsDataQaQueryRequest(question=question))

    assert not result.needs_clarification
    assert "合肥始发" in result.answer_summary
    assert "平均每车装载托数" in result.answer_summary
    assert result.result_table is not None
    assert {"车型", "发运车次", "发运件数", "总运费", "平均每车装载托数", "记录数"}.issubset(
        set(result.result_table.columns)
    )
    assert len(result.result_table.rows) > 0



def test_clarification_audit_driver_phone_name_consistency_is_supported() -> None:
    """验证 2026 同一手机号关联多个司机姓名可直接检查。

    参数：无。
    返回值：无；通过断言验证字段和年份已经明确的数据一致性问题不再泛化澄清。
    业务逻辑：正式系统派车表已有 driver_phone、driver_name、task_id 字段，可按手机号分组统计 distinct 司机姓名数并返回异常清单。
    """

    question = "2026年是否存在同一手机号关联多个司机姓名的情况?"
    plan = LogisticsDataQaPlanner().build_plan(question)

    assert plan.query_key == "sys_driver_phone_name_consistency"
    assert not plan.needs_clarification
    assert plan.filters == {"year": 2026, "top_n": 50}

    with SessionLocal() as db:
        result = LogisticsDataQaService(db=db).query(LogisticsDataQaQueryRequest(question=question))

    assert not result.needs_clarification
    assert "同一手机号关联多个司机姓名" in result.answer_summary
    assert result.result_table is not None
    assert {"driver_phone", "driver_names", "driver_name_count", "assign_task_count"}.issubset(
        set(result.result_table.columns)
    )



def test_clarification_audit_driver_id_phone_consistency_is_supported() -> None:
    """验证 2026 同一身份证号关联多个手机号可直接检查。

    参数：无。
    返回值：无；通过断言验证字段和年份已经明确的数据一致性问题不再泛化澄清。
    业务逻辑：正式系统派车表已有 driver_id_number、driver_phone、task_id 字段，可按身份证号分组统计 distinct 手机号数并返回异常清单。
    """

    question = "请检查2026年同一身份证号对应多个手机号的情况，并输出身份证号、手机号列表和任务数？"
    plan = LogisticsDataQaPlanner().build_plan(question)

    assert plan.query_key == "sys_driver_id_phone_consistency"
    assert not plan.needs_clarification
    assert plan.filters == {"year": 2026, "top_n": 50}

    with SessionLocal() as db:
        result = LogisticsDataQaService(db=db).query(LogisticsDataQaQueryRequest(question=question))

    assert not result.needs_clarification
    assert "同一身份证号对应多个手机号" in result.answer_summary
    assert result.result_table is not None
    assert {"driver_id_number", "driver_phones", "driver_phone_count", "assign_task_count"}.issubset(
        set(result.result_table.columns)
    )



def test_multi_year_monthly_multi_metric_report_requires_clarification() -> None:
    """验证 Q0876 题型进入复杂报表追问边界。

    参数：无。
    返回值：无；通过断言验证 planner 与 service 均不会输出误导性成功态。
    业务逻辑：多年逐月、目的地过滤、发运量和总费用同时输出，需要 year-month 多指标表格模板；当前不能用 12 个月单表冒充 2023–2025 年度拆分结果。
    """

    question = "请按月份汇总发往贵州的发运量和总费用，并区分2023、2024、2025三个年度？"
    plan = LogisticsDataQaPlanner().build_plan(question)

    assert plan.needs_clarification
    assert plan.query_key is None
    assert "报表模板" in plan.clarification_missing_slots

    with SessionLocal() as db:
        result = LogisticsDataQaService(db=db).query(LogisticsDataQaQueryRequest(question=question))

    assert result.needs_clarification
    assert "不支持一次性生成宽表" in result.answer_summary

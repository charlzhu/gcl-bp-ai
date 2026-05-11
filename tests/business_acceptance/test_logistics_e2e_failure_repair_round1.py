"""物流全量 E2E 失败闭环第一轮回归测试。

本文件覆盖 1391 条样例题全量执行后剩余 FAIL 中的高优先级修复：
1. 明确“区域 + 运输方式 + 总件数”应进入确定性件数汇总，而不是被通用运输方式澄清策略截断；
2. 多年逐月 + 发运量 + 总费用 + 年度拆分属于复杂多指标报表，当前应业务化追问，不能返回单指标 12 个月汇总冒充完整答案。
"""

from __future__ import annotations

from backend.app.db.session import SessionLocal
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
from backend.app.domains.logistics.schemas.llm_understanding import LogisticsLlmUnderstandingResult
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


def test_hist_city_total_fee_rank_supports_variable_top_n() -> None:
    """验证历史省份内城市总费用排名支持前五、前十等同类 TopN 问法。

    参数：无。
    返回值：无；通过断言验证 planner 解析年份、省份、城市维度和 TopN 限制。
    业务逻辑：用户把“排名前五”换成“排名前十/前10”时，问题的时间、地域、指标和维度仍然完整，不应被要求澄清。
    """

    planner = LogisticsDataQaPlanner()
    cases = [
        ("2024年江苏省各城市总费用排名前五？", 2024, 5),
        ("2025年江苏省各城市总费用排名前十？", 2025, 10),
        ("2025年江苏省各城市总费用排名前10？", 2025, 10),
        ("2025年江苏省各城市总费用排名前十一？", 2025, 11),
        ("2025年江苏省各城市总费用排名前二十？", 2025, 20),
        ("2025年江苏省各城市总费用排名TOP20？", 2025, 20),
    ]

    for question, expected_year, expected_limit in cases:
        plan = planner.build_plan(question)

        assert plan.query_key == "hist_total_fee_city_rank", question
        assert not plan.needs_clarification, question
        assert plan.filters == {"year": expected_year, "province": "江苏"}
        assert plan.dimensions == ["city"]
        assert plan.group_by == ["city"]
        assert plan.sort == [{"field": "total_fee", "direction": "desc"}]
        assert plan.limit == expected_limit


def test_hist_city_total_fee_rank_guardrail_candidate_keeps_top_n() -> None:
    """验证 Guardrail 候选回构同步使用问句中的 TopN，不再固定为前五。

    参数：无。
    返回值：无；通过断言验证候选 query_key 回构后的 limit 和过滤条件。
    业务逻辑：LLM 只能补齐受控槽位，最终执行计划仍必须由规则层从原始问句确定 TopN，避免同类问法在 assist 链路中退回固定前五。
    """

    planner = LogisticsDataQaPlanner()
    llm_result = LogisticsLlmUnderstandingResult(filters={"year": 2025, "province": "江苏"})

    plan = planner.build_plan_from_guardrail_candidate(
        "2025年江苏省各城市总费用排名前十？",
        candidate_query_key="hist_total_fee_city_rank",
        llm_result=llm_result,
    )

    assert plan is not None
    assert plan.query_key == "hist_total_fee_city_rank"
    assert plan.filters == {"year": 2025, "province": "江苏"}
    assert plan.limit == 10


def test_hist_city_total_fee_rank_does_not_swallow_extra_scope() -> None:
    """验证城市总费用 TopN 分支不吞掉额外维度、额外指标或反向排序口径。

    参数：无。
    返回值：无；通过断言验证复杂问法不会被误规划成单纯城市总费用 TopN。
    业务逻辑：只有“各城市总费用排名前N”这种窄问题可以直答；如果用户追加承运商拆分、发运量、最低排名或复合中文数字，不能静默忽略这些口径。
    """

    planner = LogisticsDataQaPlanner()
    cases = [
        "2025年江苏省各城市内承运商总费用排名前十？",
        "2025年江苏省各城市总费用排名前十，按承运商拆分？",
        "2025年江苏省按承运商拆分各城市总费用排名前十？",
        "2025年江苏省按物流公司拆分各城市总费用排名前十？",
        "2025年江苏省发运量和各城市总费用排名前十？",
        "2025年江苏省各城市总费用和发运量排名前十？",
        "2025年江苏省各城市总费用最低排名前十？",
    ]

    for question in cases:
        plan = planner.build_plan(question)

        assert plan.query_key != "hist_total_fee_city_rank", question

    llm_result = LogisticsLlmUnderstandingResult(filters={"year": 2025, "province": "江苏"})
    blocked = planner.build_plan_from_guardrail_candidate(
        "2025年江苏省各城市总费用排名前十，按承运商拆分？",
        candidate_query_key="hist_total_fee_city_rank",
        llm_result=llm_result,
    )
    assert blocked is None

    prefix_blocked = planner.build_plan_from_guardrail_candidate(
        "2025年江苏省按承运商拆分各城市总费用排名前十？",
        candidate_query_key="hist_total_fee_city_rank",
        llm_result=llm_result,
    )
    assert prefix_blocked is None


def test_logistics_ranking_branches_parse_variable_top_n() -> None:
    """验证其它物流排名分支不再写死前五、前十或前二十。

    参数：无。
    返回值：无；通过断言验证 TopN 从问句抽取并写入 plan。
    业务逻辑：用户只改“前几名”时，年份、维度、指标和排序口径没有变化，应继续进入同一确定性 query_key。
    """

    planner = LogisticsDataQaPlanner()
    cases = [
        (
            "2025年各承运商总运费排名前五？",
            "carrier_metric_ranking",
            {"year": 2025, "months": None, "ranking_metric": "total_fee", "top_n": 5},
            5,
            ["carrier_name"],
        ),
        (
            "2026年1月各承运商总费用排名前5？",
            "carrier_metric_ranking",
            {"year": 2026, "months": [1], "ranking_metric": "total_fee", "top_n": 5},
            5,
            ["carrier_name"],
        ),
        (
            "2026年1月各承运商总费用TOP5？",
            "carrier_metric_ranking",
            {"year": 2026, "months": [1], "ranking_metric": "total_fee", "top_n": 5},
            5,
            ["carrier_name"],
        ),
        (
            "2026年送达城市任务量排名前五？",
            "sys_task_count_ranking",
            {"year": 2026, "dimension": "delivery_city", "top_n": 5},
            5,
            ["delivery_city"],
        ),
        (
            "2026年project_name维度任务量排名前五？",
            "sys_task_count_ranking",
            {"year": 2026, "dimension": "project_name", "top_n": 5},
            5,
            ["project_name"],
        ),
        (
            "2026年PREASSIGN状态按省任务量排名前五？",
            "sys_task_status_province_ranking",
            {"year": 2026, "status": "PREASSIGN", "top_n": 5},
            5,
            ["delivery_province"],
        ),
        (
            "2026年司机派车任务量排名前十？",
            "sys_driver_task_ranking",
            {"year": 2026, "top_n": 10},
            10,
            ["driver_name"],
        ),
        (
            "2025年江苏省前10名客户总费用和发运量是多少？",
            "hist_top_customers_fee_and_mw_by_province",
            {"year": 2025, "province": "江苏", "top_n": 10},
            10,
            ["customer_name"],
        ),
        (
            "历史台账前5个客户总发运量？",
            "hist_customer_mw_ranking",
            {"year": None, "top_n": 5},
            5,
            ["customer_name"],
        ),
        (
            "2026年ship_product明细平均每个物流任务前五？",
            "sys_ship_product_detail_stats",
            {"year": 2026, "top_n": 5},
            5,
            ["task_id"],
        ),
        (
            "2026年delivery_distance填充率最低前五省份？",
            "sys_delivery_distance_fill_rate_by_province",
            {"year": 2026, "top_n": 5},
            5,
            ["delivery_province"],
        ),
        (
            "2026年按承运商统计送货单解析成功率前五和后五？",
            "sys_parse_success_rate_by_carrier",
            {"year": 2026, "top_n": 5},
            5,
            ["company_name"],
        ),
        (
            "2026年承运商SIGNEDFOR签收率前五和后五？",
            "sys_signedfor_rate_by_carrier",
            {"year": 2026, "top_n": 5},
            5,
            ["carrier"],
        ),
        (
            "2026年extra_cost_audited=1前五集中在哪里？",
            "sys_extra_cost_audited_concentration",
            {"year": 2026, "top_n": 5},
            5,
            ["company_name", "delivery_province"],
        ),
    ]

    for question, expected_query_key, expected_filters, expected_limit, expected_dimensions in cases:
        plan = planner.build_plan(question)

        assert plan.query_key == expected_query_key, question
        assert not plan.needs_clarification, question
        assert plan.filters == expected_filters
        assert plan.limit == expected_limit
        assert plan.dimensions == expected_dimensions


def test_logistics_ranking_variable_top_n_does_not_drop_extra_dimensions() -> None:
    """验证 TopN 泛化不会吞掉额外维度、额外指标或反向排序。

    参数：无。
    返回值：无；通过断言验证复杂问法不会被误规划成简单 TopN。
    业务逻辑：TopN 可以灵活解析，但不能把“按区域/承运商拆分、最低排序、额外指标”等口径静默丢弃。
    """

    planner = LogisticsDataQaPlanner()
    cases = [
        "2025年各承运商总运费排名前五并按区域拆分？",
        "2025年各承运商总运费排名前五名按区域？",
        "2026年送达城市任务量排名前五并按承运商拆分？",
        "2026年送达城市任务量排名前五名按省份？",
        "2026年前5个月送达城市任务量排名？",
        "2026年送达城市任务量排名top5个月？",
        "2026年司机派车任务量最低前十？",
        "2026年司机派车任务量排名前十名按月份？",
        "2025年江苏省前10名客户总费用和发运量按城市拆分？",
        "2025年江苏省前10名客户总费用和发运量按城市？",
        "历史台账前5个客户总发运量和总费用？",
        "2025年江苏省按区域各城市总费用排名前十？",
        "2026年PREASSIGN状态按省任务量和总费用排名前五？",
        "2026年送达城市任务量和车次排名前五？",
        "2026年司机派车任务量和车次排名前十？",
        "2026年1月各承运商总费用和任务量排名前五？",
    ]

    simple_ranking_keys = {
        "hist_total_fee_city_rank",
        "carrier_metric_ranking",
        "sys_task_count_ranking",
        "sys_task_status_province_ranking",
        "sys_driver_task_ranking",
        "hist_top_customers_fee_and_mw_by_province",
        "hist_customer_mw_ranking",
    }

    for question in cases:
        plan = planner.build_plan(question)

        assert plan.query_key not in simple_ranking_keys, question
        assert plan.needs_clarification or plan.unsupported_reason or plan.query_key is None, question


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



def test_clarification_audit_unknown_origin_vehicle_loading_summary_requires_clarification() -> None:
    """验证未知始发地不能被误放行为全始发地分组。

    参数：无。
    返回值：无；通过断言验证当前无法稳定识别的始发地必须继续澄清。
    业务逻辑：当问题指定了“广德始发”等当前别名表无法识别的始发地时，不能返回全部真实始发地汇总冒充结果。
    """

    plan = LogisticsDataQaPlanner().build_plan(
        "请统计广德始发各车型的车次、发运件数、总费用、平均每车装载托数，并用车型汇总表展示？"
    )

    assert plan.needs_clarification
    assert plan.query_key is None
    assert "始发地" in "".join(plan.clarification_missing_slots)



def test_clarification_audit_2026_all_ship_task_status_distribution_is_supported() -> None:
    """验证 Q0746 明确问 2026 年各任务状态数量时可直接返回主任务表状态分布。

    参数：无。
    返回值：无；通过断言验证 planner 与 service 都不会进入澄清。
    业务逻辑：只支持无额外维度、无排名、无明细诉求的主任务表 status 总分布，避免把相邻复杂问题静默降级。
    """

    question = "2026年各任务状态的数量分别是多少?"
    plan = LogisticsDataQaPlanner().build_plan(question)

    assert plan.query_key == "sys_task_status_distribution"
    assert not plan.needs_clarification
    assert plan.metrics == ["task_count", "task_share_pct"]
    assert plan.dimensions == ["status"]
    assert plan.filters == {"year": 2026, "table_scope": "ship_task"}
    assert plan.group_by == ["status"]

    with SessionLocal() as db:
        result = LogisticsDataQaService(db=db).query(LogisticsDataQaQueryRequest(question=question))

    assert not result.needs_clarification
    assert "2026年主任务表状态分布已返回" in result.answer_summary
    assert result.result_table is not None
    assert {"status", "task_count", "task_share_pct"}.issubset(set(result.result_table.columns))
    assert len(result.result_table.rows) > 0



def test_clarification_audit_2026_all_ship_task_status_distribution_rejects_noncanonical_scope() -> None:
    """验证 Q0746 修复只放行精确总分布模板，相邻状态问题继续澄清。

    参数：无。
    返回值：无；通过断言验证状态含义、派车任务表、额外维度、排名、明细、无年份/非 2026 等都不被误放行。
    业务逻辑：状态分布支持范围以主任务表全量 status 数量/占比为边界，其余问题必须先确认统计表和输出维度。
    """

    for question in (
        "2026年各任务状态分别是什么?",
        "2026年各任务状态的含义分别是什么?",
        "2026年各任务状态多少?",
        "2026年各任务状态分别多少?",
        "2026年各任务状态的数量分别是多少，并按省份拆分?",
        "2026年各任务状态PREASSIGN和ASSIGNED各省的数量分别是多少?",
        "2026年各任务状态PREASSIGN和ASSIGNED数量top3是多少?",
        "2026年各任务状态PREASSIGN和ASSIGNED的前50条明细是多少?",
        "2026年物流任务中状态为PREASSIGN和ASSIGNED的数量分别是多少?",
        "2026年物流任务中状态为PREASSIGN各省的数量分别是多少?",
        "2026年物流任务中状态为PREASSIGN的前50条明细有哪些?",
        "2026年各任务状态各城市的数量分别是多少?",
        "2026年各任务状态各省的数量分别是多少?",
        "2026年各任务状态各车型的数量分别是多少?",
        "2026年各任务状态每个仓库的数量分别是多少?",
        "2026年各任务状态每月的数量分别是多少?",
        "2026年各任务状态月度分布是多少?",
        "2026年各任务状态分月数量是多少?",
        "2026年各任务状态各基地的数量分别是多少?",
        "2026年各任务状态各项目的数量分别是多少?",
        "2026年各任务状态各采购方式的数量分别是多少?",
        "2026年各任务状态各采购类型的数量分别是多少?",
        "2026年各任务状态各供应商的数量分别是多少?",
        "2026年各任务状态各物流商的数量分别是多少?",
        "2026年各任务状态占比最高的省份?",
        "2026年各任务状态数量最少的是哪个?",
        "2026年各任务状态占比最低的是哪个?",
        "2026年各任务状态数量top3是多少?",
        "2026年各任务状态数量TOP3是多少?",
        "2026年各任务状态数量倒数前三是多少?",
        "2026年派车任务表中各任务状态的数量分别是多少?",
        "各任务状态的数量分别是多少?",
        "2025年各任务状态的数量分别是多少?",
        "请列出2026年各任务状态的前50条明细?",
    ):
        plan = LogisticsDataQaPlanner().build_plan(question)
        assert plan.needs_clarification, question
        assert plan.query_key is None, question



def test_clarification_audit_driver_consistency_summary_not_limited_by_top_n() -> None:
    """验证司机一致性摘要总量不受明细 top_n 截断影响。

    参数：无。
    返回值：无；通过断言验证 repository 返回全量异常组/任务数，同时明细行数可按 top_n 截断。
    业务逻辑：用户问“是否存在”时摘要必须是全量异常数量，表格只展示前 N 条明细。
    """

    with SessionLocal() as db:
        repo = LogisticsDataQaService(db=db).repository
        all_data = repo.sys_driver_phone_name_consistency(year=2026, top_n=50)
        limited_data = repo.sys_driver_phone_name_consistency(year=2026, top_n=1)

    assert all_data["abnormal_group_count"] >= len(all_data["items"])
    assert limited_data["abnormal_group_count"] == all_data["abnormal_group_count"]
    assert limited_data["abnormal_task_count"] == all_data["abnormal_task_count"]
    assert len(limited_data["items"]) == 1



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



def test_remark_keyword_fee_ratio_is_supported_before_complex_report_guard() -> None:
    """验证备注关键词费用占比题不被复杂报表兜底误拦截。

    参数：无。
    返回值：无；通过断言验证 planner 与 service 进入既有确定性关键词占比计算链路。
    业务逻辑：题目只要求“倒运/中转”备注关键词费用占历史总费用比例，
    后端已有 remark 字段与 total_fee 确定性计算方法，不需要生成宽表或透视报表。
    """

    question = "备注中包含“倒运”或“中转”的记录,其总费用占历史物流总费用的比例是多少?"
    plan = LogisticsDataQaPlanner().build_plan(question)

    assert plan.query_key == "hist_remark_keyword_fee_ratio"
    assert not plan.needs_clarification
    assert plan.filters == {"keywords": ["倒运", "中转"], "default_history_scope": "2023-2025"}

    with SessionLocal() as db:
        result = LogisticsDataQaService(db=db).query(LogisticsDataQaQueryRequest(question=question))

    assert not result.needs_clarification
    assert "备注包含倒运/中转" in result.answer_summary
    assert "占历史总费用" in result.answer_summary
    assert result.result_table is not None
    assert {"keywords", "keyword_total_fee", "total_fee", "fee_share_pct"}.issubset(
        set(result.result_table.columns)
    )


def test_remark_multi_keyword_year_amount_summary_is_supported() -> None:
    """验证年度备注多关键词记录数和费用金额可确定性汇总。

    参数：无。
    返回值：无；通过断言验证明确年份、关键词、记录数量和费用金额的问题不再被复杂报表兜底。
    业务逻辑：历史台账已有 remark 与 total_fee 字段，年度关键词命中记录数和费用金额可直接计算；
    但该支持仅限汇总，不自动扩展到明细清单或区域/年份交叉报表。
    """

    question = "请统计2023年备注中包含倒运、中转、换车、压车、放空的记录数量和费用金额？"
    plan = LogisticsDataQaPlanner().build_plan(question)

    assert plan.query_key == "hist_remark_keyword_amount_summary"
    assert not plan.needs_clarification
    assert plan.filters == {
        "year": 2023,
        "keywords": ["倒运", "中转", "换车", "压车", "放空"],
    }

    with SessionLocal() as db:
        result = LogisticsDataQaService(db=db).query(LogisticsDataQaQueryRequest(question=question))

    assert not result.needs_clarification
    assert "2023年" in result.answer_summary
    assert "备注包含倒运/中转/换车/压车/放空" in result.answer_summary
    assert result.result_table is not None
    assert {"year", "keywords", "keyword_record_count", "keyword_total_fee"}.issubset(
        set(result.result_table.columns)
    )


def _assert_remark_keyword_question_requires_clarification(question: str) -> None:
    """断言备注关键词越界问法必须保持澄清状态。

    参数：
        question: 待验证的自然语言问题。
    返回值：无；通过断言验证问题没有进入窄口径 remark 或通用总费用 query_key。
    业务逻辑：remark 关键词能力只支持已审计的年度金额汇总和历史物流总费用占比，额外年份、维度、分母、别名或明细诉求都必须先追问。
    """

    plan = LogisticsDataQaPlanner().build_plan(question)

    assert plan.needs_clarification, question
    assert plan.query_key is None, question


def test_remark_keyword_fee_ratio_without_record_delimiter_is_supported() -> None:
    """验证关键词后直接接“总费用占比”的窄口径费用占比问法可支持。

    参数：无。
    返回值：无；通过断言验证没有显式“记录/其”分隔符时仍能识别备注关键词列表。
    业务逻辑：业务常说“备注中包含倒运或中转的总费用占...”，该问法与“记录，其总费用占...”等价，应进入同一确定性 query_key。
    """

    for question in (
        "备注中包含倒运或中转的总费用占历史物流总费用的比例是多少？",
        "备注包含倒运或中转的总费用占历史物流总费用的比例是多少？",
        "备注中包含“倒运”或“中转”的记录,其总费用占历史物流总费用的比例是多少?",
        "备注，包含倒运或中转的总费用占历史物流总费用的比例是多少？",
        "备注：包含倒运或中转的总费用占历史物流总费用的比例是多少？",
        "备注里包含倒运或中转的总费用占历史物流总费用的比例是多少？",
    ):
        plan = LogisticsDataQaPlanner().build_plan(question)
        assert plan.query_key == "hist_remark_keyword_fee_ratio"
        assert not plan.needs_clarification
        assert plan.filters == {"keywords": ["倒运", "中转"], "default_history_scope": "2023-2025"}


def test_remark_keyword_fee_ratio_rejects_aliases_and_extra_scope() -> None:
    """验证备注关键词费用占比遇到别名、显式时间、替代分母或额外维度时必须追问。

    参数：无。
    返回值：无；通过断言验证窄口径历史物流总费用占比不会吞掉用户指定条件。
    业务逻辑：`hist_remark_keyword_fee_ratio` 固定使用 2023-2025 历史物流总费用作为分母，且只支持“总费用”口径。
    """

    for question in (
        "2023年备注中包含倒运或中转的记录，其总费用占历史物流总费用的比例是多少？",
        "今年备注包含倒运或中转的总费用占历史物流总费用的比例是多少？",
        "近三年备注中包含倒运或中转的总费用占历史物流总费用的比例是多少？",
        "本月备注包含倒运或中转的总费用占历史物流总费用的比例是多少？",
        "备注中包含倒运或中转的记录数量占历史总记录数的比例是多少？",
        "备注包含倒运或中转的总费用占华东区域总费用的比例是多少？",
        "备注中包含倒运或中转的总费用占历史物流总费用里的水路费用的比例是多少？",
        "各发货地备注包含倒运或中转的总费用占历史物流总费用的比例是多少？",
        "备注包含倒运或中转和滞留的总费用占历史物流总费用的比例是多少？",
        "备注中包含滞留的总运费占历史物流总运费的比例是多少？",
        "备注包含倒运或中转的总运费占历史物流总运费的比例是多少？",
        "备注包含倒运或中转的总费用占历史总费用的比例是多少？",
        "备注包含倒运或中转的总费用占历史物流总费用的百分比是多少？",
        "备注包含倒运或中转的总费用占历史物流总费用的比例是多少，并给出具体记录？",
        "备注包含装卸的总费用占历史物流总费用的比例是多少？",
        "备注中包含装卸的总运费占历史物流总运费的比例是多少？",
        "备注包含装卸多少钱？",
        "备注字段包含装卸多少钱？",
        "备注内容包含装卸多少钱？",
        "备注项含有装卸多少钱？",
        "备注栏含装卸多少钱？",
        "备注中是否包含装卸多少钱？",
        "备注字段是否含有装卸多少钱？",
        "备注中：是否包含装卸多少钱？",
        "备注，包含装卸多少钱？",
        "备注：包含装卸多少钱？",
        "备注，，包含装卸多少钱？",
        "备注：：包含装卸多少钱？",
        "备注、包含装卸多少钱？",
        "备注中：包含装卸多少钱？",
        "备注里包含装卸多少钱？",
        "备注中包含装卸花了多少钱？",
        "备注中，包含装卸的总运费是多少？",
        "2023年华东区域备注包含装卸的总费用是多少？",
        "2026年1月备注中包含装卸的总运费是多少？",
        "2026年1月备注中，包含装卸的总运费是多少？",
        "2023年合肥始发各车型备注包含装卸的车次和总费用是多少？",
        "备注包含倒运或中转的总费用占华东区域的总费用占历史物流总费用的比例是多少？",
        "备注包含倒运或中转的总费用占装卸的总费用占历史物流总费用的比例是多少？",
        "备注包含倒运或或中转的总费用占历史物流总费用的比例是多少？",
        "备注包含倒运或中转或的总费用占历史物流总费用的比例是多少？",
    ):
        _assert_remark_keyword_question_requires_clarification(question)


def test_remark_keyword_amount_summary_rejects_ratio_and_extra_scope() -> None:
    """验证备注关键词年度金额汇总遇到占比、未知关键词或额外维度时必须追问。

    参数：无。
    返回值：无；通过断言验证年度记录数/费用金额窄口径不会静默忽略额外条件。
    业务逻辑：该 query_key 只支持单年、受控关键词、无额外维度的记录数和费用金额；比例、区域、总运费、未知关键词都会改变口径。
    """

    supported = LogisticsDataQaPlanner().build_plan("请统计2023年备注里包含倒运，中转，换车，压车，放空的记录数量和费用金额？")
    assert supported.query_key == "hist_remark_keyword_amount_summary"
    assert not supported.needs_clarification

    for question in (
        "请统计2023年备注包含倒运或中转的记录数量和费用金额占历史物流总费用的比例是多少？",
        "请统计2023年华东区域备注中包含倒运、中转、换车、压车、放空的记录数量和费用金额？",
        "请统计2023年备注中包含倒运、中转、滞留的记录数量和费用金额？",
        "请统计2023年备注包含倒运、中转的记录数量和费用金额，返空是否也计算？",
        "请统计2023年各发货地备注包含倒运、中转的记录数量和费用金额？",
        "请统计去年备注中包含倒运、中转的记录数量和费用金额？",
        "请统计2023年备注中包含倒运、中转的记录数量和费用金额比重？",
        "请统计2023年备注包含倒运、中转的每条记录详情和费用金额？",
        "请统计2023年备注包含倒运、中转的记录数量和总运费？",
        "请统计2023年备注包含装卸的记录数量和费用金额？",
        "请统计2023年备注包含倒运的记录数量和装卸的记录数量和费用金额？",
        "请统计2023年备注包含倒运、、中转的记录数量和费用金额？",
        "请统计2023年备注包含倒运和和中转的记录数量和费用金额？",
    ):
        _assert_remark_keyword_question_requires_clarification(question)


def test_remark_keyword_detail_list_still_requires_clarification() -> None:
    """验证备注关键词明细清单仍保持澄清边界。

    参数：无。
    返回值：无；通过断言验证明细字段、线路口径和 TopN 输出未被年度汇总规则误放行。
    业务逻辑：年度汇总只回答记录数和费用金额；如果用户要求前 50 条明细及线路字段，
    当前仍需确认明细模板和线路展示口径，不能用汇总结果冒充明细。
    """

    plan = LogisticsDataQaPlanner().build_plan(
        "请列出备注中包含“倒运”的前50条明细，包含客户、合同编号、线路、车型、物流公司和费用？"
    )

    assert plan.needs_clarification
    assert plan.query_key is None
    assert "时间范围或明细模板" in plan.clarification_missing_slots


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

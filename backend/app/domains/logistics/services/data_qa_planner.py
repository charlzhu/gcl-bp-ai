from __future__ import annotations

import re
from typing import Any

from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaPlan
from backend.app.domains.logistics.schemas.llm_understanding import LogisticsLlmUnderstandingResult
from backend.app.domains.logistics.services.question_bank_response_policy import LogisticsQuestionBankResponsePolicy
from backend.app.domains.logistics.services.slot_extractor import LogisticsSlotExtractor


class LogisticsDataQaPlanner:
    """物流数据问答查询计划构造器。

    说明：
        1. 当前只覆盖 MVP 核心验收题和少量澄清/不支持识别；
        2. 所有别名归一集中写在本类，避免散落到业务执行层；
        3. 不直接生成 SQL，只生成受控 query_key 和过滤条件。
    """

    YEAR_ALIAS = {"23": 2023, "24": 2024, "25": 2025, "26": 2026}
    REGION_NAMES = ("华东", "华北", "华南", "华中", "西北", "西南", "东北")
    PROVINCE_ALIAS = {
        "江苏省": "江苏",
        "江苏": "江苏",
        "广东省": "广东",
        "广东": "广东",
        "安徽省": "安徽",
        "安徽": "安徽",
        "山东省": "山东",
        "山东": "山东",
        "浙江省": "浙江",
        "浙江": "浙江",
        "湖南省": "湖南",
        "湖南": "湖南",
        "湖北省": "湖北",
        "湖北": "湖北",
        "云南省": "云南",
        "云南": "云南",
        "贵州省": "贵州",
        "贵州": "贵州",
        "四川省": "四川",
        "四川": "四川",
        "新疆维吾尔自治区": "新疆",
        "新疆自治区": "新疆",
        "新疆": "新疆",
        "宁夏回族自治区": "宁夏",
        "宁夏": "宁夏",
        "内蒙古自治区": "内蒙",
        "内蒙古": "内蒙",
    }
    ORIGIN_ALIAS = {"合肥基地": "合肥", "阜宁基地": "阜宁"}
    SYSTEM_BASE_ALIAS = {
        "合肥基地": "1",
        "阜宁基地": "2",
    }
    CARRIER_ALIAS = {"物流公司": "承运商", "物流供应商": "承运商"}
    TRANSPORT_MODE_ALIAS = {
        "铁路": "铁路",
        "公路": "公路",
        "汽运": "公路",
    }
    VEHICLE_TYPE_ALIAS = {
        "17.5": "17.5",
        "17.5车": "17.5",
        "17米五": "17.5",
        "17米5": "17.5",
        "13m": "13",
        "13米": "13",
    }
    MW_KEYWORDS = (
        "发运量",
        "总发运量",
        "总运量",
        "运量",
        "发货量",
        "承运量",
        "运输量",
        "运输总量",
        "总共发货多少mw",
        "总瓦数",
        "发运瓦数",
        "总发运瓦数",
    )
    TRIP_KEYWORDS = ("总车次", "承运车次", "发运车次", "多少车次", "多少车", "总共发了多少车次", "总车数", "车数")
    TOTAL_FEE_KEYWORDS = (
        "总费用",
        "总运费",
        "运费是多少",
        "总计运费",
        "多少钱",
        "用车运费",
        "用车总费用",
        "运费多少",
        "运输费用",
    )
    ASSIST_SUPPORTED_QUERY_KEYS = {
        "hist_total_fee_city_rank",
        "hist_avg_fee_by_month",
        "hist_avg_fee_per_watt_by_transport",
        "hist_extra_fee_ratio_peak_month",
        "hist_total_fee_by_origin_and_carrier",
        "sys_mw_and_trip_count",
        "hist_trip_count_by_region",
        "hist_quantity_by_region",
        "hist_customer_mw",
        "hist_vehicle_type_trip_count",
        "sys_signedfor_rate_by_carrier",
        "hist_multi_origin_customers",
        "sys_companies_without_tasks",
        "hist_plan_actual_deviation",
        "sys_special_total_fee",
    }

    def __init__(self, *, slot_extractor: LogisticsSlotExtractor | None = None) -> None:
        """初始化 planner。

        参数：
            slot_extractor: 公共槽位抽取器，用于复用年份、月份、区域、省份、车型等基础槽位。

        返回：
            无返回值。
        """

        self.slot_extractor = slot_extractor or LogisticsSlotExtractor()

    def build_plan(self, question: str) -> LogisticsDataQaPlan:
        """把自然语言问题转换成最小可执行查询计划。"""
        normalized_question = question.strip()
        compact = re.sub(r"\s+", "", normalized_question)
        policy = LogisticsQuestionBankResponsePolicy().match(normalized_question)

        # 不支持边界必须先于高置信 A 类候选生效。
        # 例如“预测未来 3 个月各区域发运量”虽然包含“年份+各区域+发运量”，
        # 但业务本质是预测题，不能被历史区域汇总 query_key 抢先命中。
        if policy and policy.decision_type == "unsupported":
            return LogisticsDataQaPlan(
                intent="unsupported",
                unsupported_reason=policy.reason,
                unsupported_category=policy.category,
                unsupported_template=policy.unsupported_template,
                unsupported_suggestions=policy.unsupported_suggestions,
            )

        # 当前正式运量口径是瓦数/MW；用户明确要求“吨”时不能用 MW 结果替代。
        if "吨" in compact and any(keyword in compact for keyword in ("发运量", "运量", "发货量")):
            return LogisticsDataQaPlan(
                intent="clarification",
                needs_clarification=True,
                clarification_questions=[
                    "当前系统默认按瓦数 / MW 统计发运量，请确认是否有可用的吨重字段或换算规则。",
                    "如仍按 MW 口径统计，请改问“发运量 MW”；如需吨口径，请先补充吨重数据来源。",
                ],
                clarification_missing_slots=["吨重数据口径"],
                clarification_reason="用户要求吨口径，但当前稳定数据链路只支持瓦数 / MW 发运量。",
            )

        pre_year = self._extract_year(compact)
        pre_origin_place = self._extract_origin_place(compact)
        if (
            "目的省份和车型组合" in compact
            and any(keyword in compact for keyword in ("平均单车费用", "平均单车运费", "平均单价/车", "车次", "总费用"))
        ):
            # “始发地 + 目的省份 + 车型 + 多指标”需要目的省份、车型和平均单车费用三层口径；
            # 旧的始发地车型查询不能覆盖该问题，先追问避免返回 0。
            return LogisticsDataQaPlan(
                intent="clarification",
                needs_clarification=True,
                clarification_questions=[
                    "请确认是否需要按目的省份和车型同时分组，并统一平均单车费用的计算分母。",
                    "当前可以先拆成单项查询，例如“2024年合肥始发按车型统计总费用”。",
                ],
                clarification_missing_slots=["目的省份分组口径", "车型口径", "平均单车费用口径"],
                clarification_reason="当前查询链路不支持始发地、目的省份、车型和平均单车费用的组合报表。",
            )
        if self._is_hist_origin_vehicle_breakdown_question(compact) and pre_year in {2023, 2024, 2025}:
            # “某年某基地始发不同车型的车次/费用/单车费用”是源数据可稳定计算的明细汇总题，
            # 需要在复杂报表兜底之前放行，避免被多指标保护逻辑误降级为 B。
            filters: dict[str, Any] = {"year": pre_year}
            dimensions = ["required_vehicle_type"]
            if pre_origin_place:
                filters["origin_place"] = pre_origin_place
            else:
                # 对“广德始发”这类当前始发地别名无法校验的问题，不硬造不存在始发地；
                # 保留始发地分组，让业务能看到真实源数据中可核验的始发地 + 车型汇总。
                filters["include_origin_dimension"] = True
                dimensions = ["origin_place", "required_vehicle_type"]
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_origin_vehicle_breakdown_summary",
                metrics=["shipment_trip_count", "total_fee", "avg_fee_per_trip"],
                dimensions=dimensions,
                filters=filters,
                group_by=dimensions,
                sort=[{"field": "total_fee", "direction": "desc"}],
            )

        if self._is_complex_report_question(compact):
            # 宽表、透视表、同比变化和多指标经营汇总属于报表模板能力；
            # 当前不能用单指标 query_key 返回局部数据冒充完整报表。
            return LogisticsDataQaPlan(
                intent="clarification",
                needs_clarification=True,
                clarification_questions=[
                    "请先确认报表模板和列口径，例如年度、季度、月份、区域等维度，以及总费用、发运量、车次、平均元/瓦等指标是否都需要同时输出。",
                    "当前可以先拆成单项查询，例如“2024年各月总费用是多少”或“2025年各区域发运量是多少”。",
                ],
                clarification_missing_slots=["报表模板", "多指标口径", "维度范围"],
                clarification_reason="当前查询链路不支持一次性生成宽表、透视表、同比变化或多指标经营汇总表。",
            )

        # 历史台账没有稳定采购方式字段，不能把“询比价/招标”拆分结果伪造成确定性答案。
        if (
            any(keyword in compact for keyword in ("询比价", "招标"))
            and any(keyword in compact for keyword in ("超过20万元", "超过20万", "运费超过", "运输费用金额超过"))
            and any(keyword in compact for keyword in ("发运量", "运量", "发货量"))
        ):
            return LogisticsDataQaPlan(
                intent="unsupported",
                unsupported_reason="当前历史物流台账缺少稳定采购方式字段，不能按询比价和招标拆分发运量。",
                unsupported_category="historical_procurement_split_missing",
                unsupported_template="historical_procurement_split_missing",
                unsupported_suggestions=[
                    "可以先按客户和收货地址查询运费超过 20 万的项目地清单。",
                    "如需按询比价/招标拆分，请先补充历史台账中的采购方式字段或确认映射规则。",
                ],
            )

        # 先走“高置信支持模式”，只放行已经确认可以稳定计算的明确题型。
        # 这样能把部分高价值 B 题收进 A，同时不放松 B/C 的正式边界。
        direct_supported_plan = self._build_direct_supported_plan(compact)
        if direct_supported_plan is not None:
            return direct_supported_plan

        # 高置信度澄清题统一走正式澄清模板，不允许继续落入兜底成功态。
        if policy and policy.decision_type == "clarification":
            return LogisticsDataQaPlan(
                intent="clarification",
                needs_clarification=True,
                clarification_questions=policy.clarification_questions,
                clarification_category=policy.category,
                clarification_reason=policy.reason,
                clarification_missing_slots=policy.clarification_missing_slots,
                clarification_template=policy.clarification_template,
            )

        # 预测类问题在 MVP 阶段统一识别为不支持。
        if any(keyword in compact for keyword in ("预测", "预估", "预计", "将会", "未来")):
            return LogisticsDataQaPlan(
                intent="unsupported",
                unsupported_reason="当前问题属于预测分析，MVP 暂未实现预测模型。",
                unsupported_category="forecast",
                unsupported_template="forecast",
                unsupported_suggestions=[
                    "可以改问：2023–2025 年各月物流总费用是多少？",
                    "可以改问：2026 年已发生月份的运费、发运量或单瓦成本是多少？",
                ],
            )

        # 2026 额外费用当前只支持总额，不支持项目/原因/明细。
        if "额外费用" in compact and any(keyword in compact for keyword in ("项目", "原因", "明细")):
            return LogisticsDataQaPlan(
                intent="unsupported",
                unsupported_reason="当前 MVP 仅支持额外费用总额，不支持额外费用项目、原因或明细。",
                unsupported_category="extra_fee_detail",
                unsupported_template="extra_fee_detail",
                unsupported_suggestions=[
                    "可以改问：2026 年 1 月额外费用总额是多少？",
                    "如需项目/原因明细，请先由数据 owner 确认字段和归因口径。",
                ],
            )

        # 典型模糊问题先要求澄清，避免直接猜口径。
        if any(keyword in compact for keyword in ("最近", "最差", "异常", "效率怎么样", "有没有问题")):
            return LogisticsDataQaPlan(
                intent="clarification",
                needs_clarification=True,
                clarification_questions=[
                    "请先明确时间范围，例如近7天、近30天、本月或今年。",
                    "请明确指标口径，例如总费用、单瓦成本、签收率或异常率。",
                ],
            )

        year = self._extract_year(compact)
        months = self._extract_months(compact)
        region = self._extract_region(compact)
        province = self._extract_province(compact)
        origin_place = self._extract_origin_place(compact)
        system_base_name = self._extract_system_base_name(compact)
        system_base_code = self._extract_system_base_code(compact)
        customer_name = self._extract_customer_name(compact)
        company_name = self._extract_company_name(compact)
        transport_mode = self._extract_transport_mode(compact)
        procurement_type = self._extract_procurement_type(compact)
        if (
            company_name
            and (
                company_name in {"总", "全年", "区域", "运输", "公路运输", "铁路运输"}
                or (transport_mode and transport_mode in company_name)
                or (procurement_type and procurement_type in company_name)
                or company_name.endswith("运输")
                or "场景" in company_name
                or company_name in {"累计", "各按"}
            )
        ):
            # “公路运输/铁路运输”是运输方式，不是承运商名称；避免系统侧总运费按 company_name 过滤到 0。
            company_name = None
        monthly_breakdown = self._is_monthly_breakdown_request(compact)

        if "各城市总费用排名前五" in compact:
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="hist_total_fee_city_rank",
                metrics=["total_fee"],
                dimensions=["city"],
                filters={"year": year, "province": province},
                group_by=["city"],
                sort=[{"field": "total_fee", "direction": "desc"}],
                limit=5,
            )

        if "每月平均运费" in compact and origin_place and province and "17.5" in compact:
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_avg_fee_by_month",
                metrics=["total_fee"],
                dimensions=["biz_month"],
                filters={"year": year, "origin_place": origin_place, "province": province, "vehicle_type": "17.5"},
                group_by=["biz_month"],
                sort=[{"field": "biz_month", "direction": "asc"}],
            )

        if "平均元/瓦" in compact and "运输方式" in compact and region:
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="hist_avg_fee_per_watt_by_transport",
                metrics=["unit_watt_fee"],
                dimensions=["transport_mode"],
                filters={"region_name": region},
                group_by=["transport_mode"],
                sort=[{"field": "avg_fee_per_watt", "direction": "asc"}],
            )

        if "额外费用占总费用比重最高" in compact:
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="hist_extra_fee_ratio_peak_month",
                metrics=["extra_fee", "total_fee", "extra_fee_ratio"],
                dimensions=["biz_month"],
                filters={"year": year},
                group_by=["biz_month"],
                sort=[{"field": "extra_fee_ratio", "direction": "desc"}],
                limit=1,
            )

        if self._is_total_fee_question(compact) and origin_place and "晶茂" in compact:
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_total_fee_by_origin_and_carrier",
                metrics=["total_fee"],
                dimensions=[],
                filters={"year": year, "origin_place": origin_place, "carrier_name": "晶茂"},
            )

        if year == 2026 and self._is_mw_question(compact) and (
            self._is_trip_question(compact) or "总共发了多少车次" in compact or "总共发了多少车" in compact
        ):
            if not months and not self._is_ytd_scope_question(compact):
                return LogisticsDataQaPlan(
                    intent="clarification",
                    needs_clarification=True,
                    clarification_questions=[
                        "请补充 2026 系统侧的统计时间范围，例如 1 月、1-2 月，或明确说明按当前累计统计。",
                        "如需同时看车次，请确认是按当前累计还是某个具体月份口径。",
                        "请确认输出形态：只输出汇总总数，还是需要表格并按采购方式、基地或承运商继续拆分。",
                    ],
                )
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_mw_and_trip_count",
                metrics=["shipment_mw", "shipment_trip_count"],
                dimensions=[],
                filters={
                    "year": year,
                    "months": months or None,
                    "transport_mode": transport_mode,
                    "base_code": system_base_code,
                    "base_name": system_base_name,
                    "monthly_breakdown": self._is_monthly_breakdown_request(compact),
                },
            )

        if year == 2026 and months and self._is_unit_fee_question(compact) and "额外费用" not in compact:
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_unit_fee_per_watt",
                metrics=["unit_fee_per_watt"],
                dimensions=[],
                filters={"year": year, "months": months, "company_name": company_name},
            )

        if year == 2026 and self._is_mw_question(compact):
            if not months and not self._is_ytd_scope_question(compact):
                return LogisticsDataQaPlan(
                    intent="clarification",
                    needs_clarification=True,
                    clarification_questions=[
                        "请补充 2026 系统侧的统计时间范围，例如 1 月、1-2 月，或明确说明按当前累计统计。",
                        "如需看总运量，请确认是只看 MW，还是同时需要车次或采购方式拆分。",
                        "请确认输出形态：只输出汇总总数，还是需要表格并按采购方式、基地或承运商继续拆分。",
                    ],
                )
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_mw_and_trip_count",
                metrics=["shipment_mw"],
                dimensions=[],
                filters={
                    "year": year,
                    "months": months or None,
                    "transport_mode": transport_mode,
                    "base_code": system_base_code,
                    "base_name": system_base_name,
                    "monthly_breakdown": self._is_monthly_breakdown_request(compact),
                },
            )

        if "总车次" in compact and region and year in {2023, 2024, 2025}:
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_trip_count_by_region",
                metrics=["shipment_trip_count"],
                dimensions=[],
                filters={"year": year, "region_name": region},
            )

        if "总发运件数" in compact and region:
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_quantity_by_region",
                metrics=["shipment_count"],
                dimensions=[],
                filters={"year": year, "region_name": region},
            )

        if year in {2023, 2024, 2025} and customer_name and self._is_mw_question(compact):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_customer_mw",
                metrics=["shipment_mw"],
                dimensions=[],
                filters={"year": year, "customer_name": customer_name},
            )

        if year in {2023, 2024, 2025} and origin_place and "晶茂" in compact and self._is_mw_question(compact):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_mw_by_origin_and_carrier",
                metrics=["shipment_mw"],
                dimensions=[],
                filters={"year": year, "origin_place": origin_place, "carrier_name": "晶茂"},
            )

        if "17.5车发运多少车" in compact:
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_vehicle_type_trip_count",
                metrics=["shipment_trip_count"],
                dimensions=[],
                filters={"year": year, "vehicle_type": "17.5"},
            )

        if "SIGNEDFOR签收率" in compact and "承运商" in compact and year == 2026:
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="sys_signedfor_rate_by_carrier",
                metrics=["signedfor_rate"],
                dimensions=["carrier"],
                filters={"year": year},
                group_by=["carrier"],
            )

        if year in {2023, 2024, 2025} and self._is_carrier_kpi_question(compact) and not self._is_monthly_fee_compare_question(compact):
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="hist_carrier_kpi_by_year",
                metrics=["shipment_mw", "shipment_share_pct", "total_fee"],
                dimensions=["carrier_name"],
                filters={
                    "year": year,
                    "view_mode": self._resolve_carrier_kpi_view_mode(compact),
                },
                group_by=["carrier_name"],
                sort=[{"field": "shipment_mw", "direction": "desc"}],
            )

        if "同一客户由多个始发地发货" in compact and year:
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="hist_multi_origin_customers",
                metrics=["customer_count"],
                dimensions=["customer_name"],
                filters={"year": year},
                group_by=["customer_name"],
            )

        if "已建档但2026年没有任何任务" in compact:
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="sys_companies_without_tasks",
                metrics=["company_count"],
                dimensions=["company_name"],
                filters={"year": 2026},
                group_by=["company_name"],
            )

        if year in {2023, 2024, 2025} and self._is_monthly_fee_compare_question(compact):
            return LogisticsDataQaPlan(
                intent="compare",
                query_key="hist_monthly_total_fee_by_year",
                metrics=["total_fee"],
                dimensions=["biz_month"],
                filters={"year": year},
                group_by=["biz_month"],
                sort=[{"field": "biz_month", "direction": "asc"}],
            )

        if "计划发运件数与实际发运件数的偏差率" in compact and region and year:
            return LogisticsDataQaPlan(
                intent="compare",
                query_key="hist_plan_actual_deviation",
                metrics=["plan_qty", "actual_qty", "deviation_rate"],
                dimensions=[],
                filters={"year": year, "region_name": region},
            )

        if year == 2026 and procurement_type and self._is_total_fee_question(compact):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_total_fee_by_filters",
                metrics=["total_fee"],
                dimensions=[],
                filters={"year": year, "months": months, "procurement_type": procurement_type},
            )

        if year == 2026 and any(keyword in compact for keyword in ("经营计划", "经营计划部")) and self._is_total_fee_question(compact):
            if months:
                return LogisticsDataQaPlan(
                    intent="aggregate",
                    query_key="sys_total_fee_by_filters",
                    metrics=["total_fee"],
                    dimensions=[],
                    filters={"year": year, "months": months, "special_scope": "planning"},
                )
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_special_total_fee",
                metrics=["total_fee"],
                dimensions=[],
                filters={"year": year, "special_scope": "planning"},
            )

        if year == 2026 and "辅料送样" in compact and self._is_total_fee_question(compact):
            if system_base_code or months:
                return LogisticsDataQaPlan(
                    intent="aggregate",
                    query_key="sys_total_fee_by_filters",
                    metrics=["total_fee"],
                    dimensions=[],
                    filters={
                        "year": year,
                        "months": months,
                        "base_code": system_base_code,
                        "base_name": system_base_name,
                        "special_scope": "sample",
                    },
                )
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_special_total_fee",
                metrics=["total_fee"],
                dimensions=[],
                filters={"year": year, "special_scope": "sample"},
            )

        if year == 2026 and "刘娟" in compact and self._is_total_fee_question(compact):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_special_total_fee",
                metrics=["total_fee"],
                dimensions=[],
                filters={"year": year, "special_scope": "liujuan"},
            )

        if year == 2026 and customer_name and self._is_total_fee_question(compact) and not origin_place:
            filters: dict[str, Any] = {"year": year, "months": months, "customer_name": customer_name}
            if monthly_breakdown:
                filters["monthly_breakdown"] = True
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_total_fee_by_filters",
                metrics=["total_fee"],
                dimensions=["biz_month"] if monthly_breakdown else [],
                filters=filters,
                group_by=["biz_month"] if monthly_breakdown else [],
                sort=[{"field": "biz_month", "direction": "asc"}] if monthly_breakdown else [],
            )

        if year == 2026 and company_name and self._is_total_fee_question(compact) and not origin_place and not customer_name:
            filters: dict[str, Any] = {"year": year, "months": months, "company_name": company_name}
            if monthly_breakdown:
                filters["monthly_breakdown"] = True
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_total_fee_by_filters",
                metrics=["total_fee"],
                dimensions=["biz_month"] if monthly_breakdown else [],
                filters=filters,
                group_by=["biz_month"] if monthly_breakdown else [],
                sort=[{"field": "biz_month", "direction": "asc"}] if monthly_breakdown else [],
            )

        # 2026 单月/多月总运费在没有其他过滤条件时，直接使用系统侧总运费确定性口径。
        # 这覆盖“2026年1月份总运费”“2026年1-2月累计总运输费用”等业务高频问法。
        if (
            year == 2026
            and months
            and self._is_total_fee_question(compact)
            and not monthly_breakdown
            and not origin_place
            and not customer_name
            and not company_name
            and not transport_mode
            and not system_base_code
            and not procurement_type
            and not any(keyword in compact for keyword in ("经营计划", "辅料送样", "刘娟"))
        ):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_total_fee_by_filters",
                metrics=["total_fee"],
                dimensions=[],
                filters={"year": year, "months": months},
            )

        # 2026 系统侧“每个月总运费”已经具备总费用确定性计算能力。
        # 这里只改变返回颗粒度为按月，不新增 query_key，也不把月份短语误当承运商。
        if (
            year == 2026
            and months
            and monthly_breakdown
            and self._is_total_fee_question(compact)
            and not origin_place
            and not customer_name
            and not company_name
        ):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_total_fee_by_filters",
                metrics=["total_fee"],
                dimensions=["biz_month"],
                filters={"year": year, "months": months, "monthly_breakdown": True},
                group_by=["biz_month"],
                sort=[{"field": "biz_month", "direction": "asc"}],
            )

        if (
            year == 2026
            and months
            and transport_mode
            and self._is_total_fee_question(compact)
            and not origin_place
            and not customer_name
            and not company_name
        ):
            # 2026 “公路/铁路运输 + 月份 + 总运费”按运输方式下推过滤，
            # 不再把“公路运输”误识别为承运商。
            filters: dict[str, Any] = {"year": year, "months": months, "transport_mode": transport_mode}
            if monthly_breakdown:
                filters["monthly_breakdown"] = True
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_total_fee_by_filters",
                metrics=["total_fee"],
                dimensions=["biz_month"] if monthly_breakdown else [],
                filters=filters,
                group_by=["biz_month"] if monthly_breakdown else [],
                sort=[{"field": "biz_month", "direction": "asc"}] if monthly_breakdown else [],
            )

        if year in {2023, 2024, 2025} and province and self._is_unit_fee_question(compact):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_unit_fee_per_watt",
                metrics=["unit_fee_per_watt"],
                dimensions=[],
                filters={
                    "year": year,
                    "province": province,
                    "months": months,
                    "include_extra_fee": "额外费用" in compact,
                },
            )

        if year in {2023, 2024, 2025} and region and self._is_mw_question(compact):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_mw_summary",
                metrics=["shipment_mw"],
                dimensions=[],
                filters={"year": year, "months": months, "region_name": region, "origin_place": origin_place},
            )

        if year in {2023, 2024, 2025} and self._is_mw_question(compact) and not region and not customer_name and months:
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_mw_summary",
                metrics=["shipment_mw"],
                dimensions=[],
                filters={"year": year, "months": months},
            )

        return LogisticsDataQaPlan(
            intent="clarification",
            needs_clarification=True,
            clarification_questions=[
                "当前 MVP 只支持时间聚合、区域筛选、承运商排名、费用/运量统计等结构化数据问题。",
                "请补充明确的时间、指标和维度，例如“2025年华东区域总运费”或“2026年1月总发运量”。",
            ],
        )

    def build_plan_from_guardrail_candidate(
        self,
        question: str,
        *,
        candidate_query_key: str,
        llm_result: LogisticsLlmUnderstandingResult,
    ) -> LogisticsDataQaPlan | None:
        """根据 Guardrail 放行的单一候选 query_key 回构正式查询计划。

        说明：
            1. 这里只服务于 A 类白名单 query_key 的受控增强，不参与 B/C 裁决；
            2. 只有当原始问题缺少的槽位能通过问句抽取或 LLM 结构化输出稳定补齐时，才返回 plan；
            3. 如果任何关键口径仍不明确，必须返回 None，让主链路继续保持原规则结果。
        """
        if candidate_query_key not in self.ASSIST_SUPPORTED_QUERY_KEYS:
            return None

        compact = re.sub(r"\s+", "", question.strip())
        year = self._resolve_assist_year(compact, llm_result)
        months = self._resolve_assist_months(compact, llm_result)
        region = self._resolve_assist_region(compact, llm_result)
        province = self._resolve_assist_province(compact, llm_result)
        origin_place = self._resolve_assist_origin_place(compact, llm_result)
        customer_name = self._resolve_assist_customer_name(compact, llm_result)
        carrier_name = self._resolve_assist_carrier_name(compact, llm_result)
        vehicle_type = self._resolve_assist_vehicle_type(compact, llm_result)
        special_scope = self._resolve_assist_special_scope(compact, llm_result)

        if candidate_query_key == "hist_total_fee_city_rank" and year and province:
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key=candidate_query_key,
                metrics=["total_fee"],
                dimensions=["city"],
                filters={"year": year, "province": province},
                group_by=["city"],
                sort=[{"field": "total_fee", "direction": "desc"}],
                limit=5,
            )

        if candidate_query_key == "hist_avg_fee_by_month" and year and origin_place and province and vehicle_type:
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key=candidate_query_key,
                metrics=["total_fee"],
                dimensions=["biz_month"],
                filters={"year": year, "origin_place": origin_place, "province": province, "vehicle_type": vehicle_type},
                group_by=["biz_month"],
                sort=[{"field": "biz_month", "direction": "asc"}],
            )

        if candidate_query_key == "hist_avg_fee_per_watt_by_transport" and region:
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key=candidate_query_key,
                metrics=["unit_watt_fee"],
                dimensions=["transport_mode"],
                filters={"region_name": region},
                group_by=["transport_mode"],
                sort=[{"field": "avg_fee_per_watt", "direction": "asc"}],
            )

        if candidate_query_key == "hist_extra_fee_ratio_peak_month" and year:
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key=candidate_query_key,
                metrics=["extra_fee", "total_fee", "extra_fee_ratio"],
                dimensions=["biz_month"],
                filters={"year": year},
                group_by=["biz_month"],
                sort=[{"field": "extra_fee_ratio", "direction": "desc"}],
                limit=1,
            )

        if candidate_query_key == "hist_total_fee_by_origin_and_carrier" and year and origin_place and carrier_name:
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key=candidate_query_key,
                metrics=["total_fee"],
                dimensions=[],
                filters={"year": year, "origin_place": origin_place, "carrier_name": carrier_name},
            )

        if candidate_query_key == "sys_mw_and_trip_count" and year == 2026 and months:
            metrics = ["shipment_mw", "shipment_trip_count"]
            if not self._is_trip_question(compact):
                metrics = ["shipment_mw"]
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key=candidate_query_key,
                metrics=metrics,
                dimensions=[],
                filters={"year": year, "months": months},
            )

        if candidate_query_key == "hist_trip_count_by_region" and year and region:
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key=candidate_query_key,
                metrics=["shipment_trip_count"],
                dimensions=[],
                filters={"year": year, "region_name": region},
            )

        if candidate_query_key == "hist_quantity_by_region" and region:
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key=candidate_query_key,
                metrics=["shipment_count"],
                dimensions=[],
                filters={"region_name": region},
            )

        if candidate_query_key == "hist_customer_mw" and year in {2023, 2024, 2025} and customer_name:
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key=candidate_query_key,
                metrics=["shipment_mw"],
                dimensions=[],
                filters={"year": year, "customer_name": customer_name},
            )

        if candidate_query_key == "hist_vehicle_type_trip_count" and year and vehicle_type:
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key=candidate_query_key,
                metrics=["shipment_trip_count"],
                dimensions=[],
                filters={"year": year, "vehicle_type": vehicle_type},
            )

        if candidate_query_key == "sys_signedfor_rate_by_carrier" and year == 2026:
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key=candidate_query_key,
                metrics=["signedfor_rate"],
                dimensions=["carrier"],
                filters={"year": year},
                group_by=["carrier"],
            )

        if candidate_query_key == "hist_multi_origin_customers" and year:
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key=candidate_query_key,
                metrics=["customer_count"],
                dimensions=["customer_name"],
                filters={"year": year},
                group_by=["customer_name"],
            )

        if candidate_query_key == "sys_companies_without_tasks":
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key=candidate_query_key,
                metrics=["company_count"],
                dimensions=["company_name"],
                filters={"year": 2026},
                group_by=["company_name"],
            )

        if candidate_query_key == "hist_plan_actual_deviation" and year and region:
            return LogisticsDataQaPlan(
                intent="compare",
                query_key=candidate_query_key,
                metrics=["plan_qty", "actual_qty", "deviation_rate"],
                dimensions=[],
                filters={"year": year, "region_name": region},
            )

        if candidate_query_key == "sys_special_total_fee" and year == 2026 and special_scope:
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key=candidate_query_key,
                metrics=["total_fee"],
                dimensions=[],
                filters={"year": year, "special_scope": special_scope},
            )
        return None

    def _build_direct_supported_plan(self, compact: str) -> LogisticsDataQaPlan | None:
        """构造需要在正式澄清策略之前放行的高置信支持题型。

        说明：
            1. 当前只放行已经确认可稳定计算的明确题型；
            2. 主要用于避免“各省分别是多少”“前五客户”这类高价值题被通用 B 类规则截住；
            3. 这里不处理模糊题，也不突破既有 B/C 边界。
        """
        year = self._extract_year(compact)
        years = self._extract_years(compact)
        region = self._extract_region(compact)
        province = self._extract_province(compact)
        province_list = self._extract_province_list(compact)
        origin_place = self._extract_origin_place(compact)
        vehicle_type = self._extract_vehicle_type(compact)
        city = self._extract_destination_city(compact)
        if province:
            # 当“江苏省/上海市”已经被稳定识别成省级目的地时，不再把
            # “江苏的平均”这类后缀误抽成城市，避免线路 query_key 过滤到空结果。
            city = None
        months = self._extract_months(compact)
        customer_name = self._extract_customer_name(compact)
        company_name = self._extract_company_name(compact)
        transport_mode = self.slot_extractor.extract_transport_mode(compact)
        carrier_name = self._extract_historical_carrier_name(compact)
        procurement_type = self._extract_procurement_type(compact)
        monthly_breakdown = self._is_monthly_breakdown_request(compact)
        if (
            company_name
            and (
                company_name in {"总", "全年", "区域", "运输"}
                or (region and region in company_name)
                or (transport_mode and transport_mode in company_name)
                or (procurement_type and procurement_type in company_name)
                or company_name.endswith("区域")
                or "场景" in company_name
                or company_name in {"累计", "各按"}
            )
        ):
            company_name = None
        system_base_name = self._extract_system_base_name(compact)
        system_base_code = self._extract_system_base_code(compact)
        quarter = self.slot_extractor.extract_quarter(compact)

        if year in {2023, 2024, 2025} and any(
            keyword in compact for keyword in ("招标场景", "询比价场景", "经营计划场景", "辅料送样场景")
        ):
            return LogisticsDataQaPlan(
                intent="clarification",
                needs_clarification=True,
                clarification_questions=[
                    "历史物流台账缺少稳定采购方式或业务场景字段，不能直接按招标、询比价、经营计划或辅料送样场景拆分统计。",
                    "如需统计该口径，请先提供历史场景映射规则，或改问不区分场景的年度总运费、总发运量。",
                ],
                clarification_missing_slots=["历史业务场景字段口径", "历史数据映射规则"],
                clarification_reason="历史台账缺少稳定场景字段，不能把场景词当承运商过滤到 0。",
            )

        if (
            years
            and all(item in {2023, 2024, 2025} for item in years)
            and monthly_breakdown
            and (region or province)
            and (self._is_total_fee_question(compact) or self._is_mw_question(compact))
            and not any(keyword in compact for keyword in ("平均", "均价", "单价"))
        ):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_monthly_metric_by_filters",
                metrics=["shipment_mw", "total_fee"],
                dimensions=["biz_month"],
                filters={"years": years, "region_name": region, "province": province},
                group_by=["biz_month"],
                sort=[{"field": "biz_month", "direction": "asc"}],
            )

        # 历史承运商简称题族：如“2023年晶茂物流全年总发运量/总运输费用/单瓦运输成本/承运车次”。
        # 这里只处理已在历史台账中可校验的承运商别名，避免把任意“物流”字样误当承运商。
        if year in {2023, 2024, 2025} and carrier_name and not origin_place and not customer_name:
            if self._is_mw_question(compact):
                return LogisticsDataQaPlan(
                    intent="aggregate",
                    query_key="hist_mw_summary",
                    metrics=["shipment_mw"],
                    dimensions=[],
                    filters={"year": year, "months": months, "carrier_name": carrier_name},
                )
            if self._is_unit_fee_question(compact):
                return LogisticsDataQaPlan(
                    intent="aggregate",
                    query_key="hist_unit_fee_per_watt",
                    metrics=["unit_fee_per_watt"],
                    dimensions=[],
                    filters={"year": year, "months": months, "carrier_name": carrier_name},
                )
            if self._is_trip_question(compact):
                return LogisticsDataQaPlan(
                    intent="aggregate",
                    query_key="hist_total_fee_summary",
                    metrics=["shipment_trip_count"],
                    dimensions=[],
                    filters={"year": year, "months": months, "carrier_name": carrier_name},
                )
            if self._is_total_fee_question(compact):
                return LogisticsDataQaPlan(
                    intent="aggregate",
                    query_key="hist_total_fee_summary",
                    metrics=["total_fee"],
                    dimensions=[],
                    filters={"year": year, "months": months, "carrier_name": carrier_name},
                )

        if year == 2026 and months and "运量综合" in compact and self._is_mw_question(compact):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_mw_and_trip_count",
                metrics=["shipment_mw", "shipment_trip_count"],
                dimensions=["biz_month"] if self._is_monthly_breakdown_request(compact) else [],
                filters={
                    "year": 2026,
                    "months": months,
                    "transport_mode": transport_mode,
                    "base_code": system_base_code,
                    "base_name": system_base_name,
                    "monthly_breakdown": self._is_monthly_breakdown_request(compact),
                },
            )

        if (
            year in {2023, 2024, 2025}
            and quarter
            and "各区域" in compact
            and any(keyword in compact for keyword in ("运费", "费用", "单瓦", "元/瓦", "单瓦运输成本"))
        ):
            metric = "unit_fee_per_watt" if self._is_unit_fee_question(compact) else "total_fee"
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="hist_quarter_region_metric",
                metrics=[metric],
                dimensions=["region_name"],
                filters={"year": year, "quarter": quarter, "metric": metric},
                group_by=["region_name"],
                sort=[{"field": metric, "direction": "desc"}],
            )

        if year in {2023, 2024, 2025} and quarter and "各区域" in compact and self._is_mw_question(compact):
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="hist_quarter_region_metric",
                metrics=["shipment_mw"],
                dimensions=["region_name"],
                filters={"year": year, "quarter": quarter, "metric": "shipment_mw"},
                group_by=["region_name"],
                sort=[{"field": "shipment_mw", "direction": "desc"}],
            )

        product_spec = self._extract_product_spec(compact)
        if "历史" in compact and product_spec and any(keyword in compact for keyword in ("总瓦数", "总发运瓦数", "发运总瓦数")):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_product_spec_mw_summary",
                metrics=["shipment_watt", "shipment_mw"],
                dimensions=[],
                filters={"product_spec": product_spec, "default_history_scope": "2023-2025"},
            )

        if (
            transport_mode
            and any(keyword in compact for keyword in ("发运记录数", "记录有多少条", "记录数", "占比"))
            and ("历史" in compact or year in {2023, 2024, 2025} or year is None)
            and "2026" not in compact
            and "系统" not in compact
        ):
            years_for_mode = years if years and all(item in {2023, 2024, 2025} for item in years) else [2023, 2024, 2025]
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_transport_mode_record_summary",
                metrics=["record_count", "record_share_pct"],
                dimensions=["transport_mode"],
                filters={"years": years_for_mode, "transport_mode": transport_mode},
            )

        if (
            year in {2023, 2024, 2025}
            and transport_mode
            and self._is_mw_question(compact)
            and not any(keyword in compact for keyword in ("风险", "预测", "切换"))
        ):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_mw_summary",
                metrics=["shipment_mw"],
                dimensions=[],
                filters={"year": year, "months": months, "transport_mode": transport_mode},
            )

        if (
            year in {2023, 2024, 2025}
            and transport_mode
            and self._is_unit_fee_question(compact)
            and not any(keyword in compact for keyword in ("风险", "预测", "切换"))
        ):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_unit_fee_per_watt",
                metrics=["unit_fee_per_watt"],
                dimensions=[],
                filters={"year": year, "months": months, "transport_mode": transport_mode},
            )

        if "倒运" in compact and "中转" in compact and any(keyword in compact for keyword in ("总费用占", "总运费占", "比例", "占比")):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_remark_keyword_fee_ratio",
                metrics=["total_fee", "fee_share_pct"],
                dimensions=[],
                filters={"keywords": ["倒运", "中转"], "default_history_scope": "2023-2025"},
            )

        if (
            year in {2023, 2024, 2025}
            and customer_name
            and any(keyword in compact for keyword in ("收货地址", "项目地"))
            and any(keyword in compact for keyword in ("超过20万元", "超过20万", "运费超过"))
        ):
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="hist_high_fee_addresses_by_customer",
                metrics=["total_fee"],
                dimensions=["address"],
                filters={"year": year, "customer_name": customer_name, "threshold_fee": 200000},
                sort=[{"field": "total_fee", "direction": "desc"}],
            )

        if year == 2026 and "平均装车数" in compact and province:
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_avg_loading_trucks_by_province",
                metrics=["avg_loading_trucks"],
                dimensions=[],
                filters={"year": year, "province": province},
            )

        if year == 2026 and "各任务状态" in compact and any(status in compact for status in ("PREASSIGN", "ASSIGNED", "PRESIGNFOR", "SIGNEDFOR")):
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="sys_task_status_distribution",
                metrics=["task_count", "task_share_pct"],
                dimensions=["status"],
                filters={"year": year, "table_scope": "ship_task"},
                group_by=["status"],
            )

        if year == 2026 and "物流任务中状态为" in compact and self.slot_extractor.extract_status(compact):
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="sys_task_status_distribution",
                metrics=["task_count", "task_share_pct"],
                dimensions=["status"],
                filters={"year": year, "table_scope": "ship_task", "status": self.slot_extractor.extract_status(compact)},
                group_by=["status"],
            )

        if year == 2026 and "派车任务表中" in compact and "状态" in compact and any(status in compact for status in ("PREALLOCATE", "ALLOCATED", "ENTER", "LEAVE")):
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="sys_task_status_distribution",
                metrics=["task_count", "task_share_pct"],
                dimensions=["status"],
                filters={"year": year, "table_scope": "assign_task"},
                group_by=["status"],
            )

        if year == 2026 and "PREASSIGN" in compact and "省" in compact and any(keyword in compact for keyword in ("最多", "排名")):
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="sys_task_status_province_ranking",
                metrics=["task_count"],
                dimensions=["delivery_province"],
                filters={"year": year, "status": "PREASSIGN", "top_n": 10},
                group_by=["delivery_province"],
                sort=[{"field": "task_count", "direction": "desc"}],
                limit=10,
            )

        if year == 2026 and "reconciliation_status" in compact and "填充率" in compact and "月份" in compact:
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="sys_reconciliation_fill_rate_by_month",
                metrics=["fill_rate"],
                dimensions=["biz_month"],
                filters={"year": year},
                group_by=["biz_month"],
                sort=[{"field": "biz_month", "direction": "asc"}],
            )

        if year == 2026 and "ship_product" in compact and "明细" in compact and "平均每个物流任务" in compact:
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="sys_ship_product_detail_stats",
                metrics=["avg_detail_count", "detail_count"],
                dimensions=["task_id"],
                filters={"year": year, "top_n": 10},
                sort=[{"field": "detail_count", "direction": "desc"}],
                limit=10,
            )

        if year == 2026 and "司机" in compact and any(keyword in compact for keyword in ("派车任务量最高", "前20", "前二十")):
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="sys_driver_task_ranking",
                metrics=["assign_task_count"],
                dimensions=["driver_name"],
                filters={"year": year, "top_n": 20},
                group_by=["driver_name"],
                sort=[{"field": "assign_task_count", "direction": "desc"}],
                limit=20,
            )

        if year == 2026 and "送货单解析状态分布" in compact:
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="sys_delivery_note_parse_status_distribution",
                metrics=["record_count", "record_share_pct"],
                dimensions=["delivery_note_parse_status"],
                filters={"year": year},
                group_by=["delivery_note_parse_status"],
            )

        if year == 2026 and "派车任务中" in compact and "回单解析状态为" in compact:
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="sys_delivery_note_parse_status_distribution",
                metrics=["record_count", "record_share_pct"],
                dimensions=["delivery_note_parse_status"],
                filters={"year": year},
                group_by=["delivery_note_parse_status"],
            )

        if year == 2026 and any(keyword in compact for keyword in ("询比价", "招标")) and "任务量" in compact and "占比" in compact:
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="sys_procurement_task_distribution",
                metrics=["task_count", "task_share_pct"],
                dimensions=["procurement_type"],
                filters={"year": year},
                group_by=["procurement_type"],
            )

        if year == 2026 and any(keyword in compact for keyword in ("询比价", "招标")) and "平均装车数" in compact:
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="sys_procurement_avg_loading_trucks",
                metrics=["avg_loading_trucks"],
                dimensions=["procurement_type"],
                filters={"year": year},
                group_by=["procurement_type"],
            )

        if year == 2026 and months and system_base_code and "额外费用总额" in compact:
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_extra_fee_summary",
                metrics=["extra_fee"],
                dimensions=[],
                filters={"year": year, "months": months, "base_code": system_base_code, "base_name": system_base_name},
            )

        # Q02 这类“每月平均运费”已有更严格的专用 query_key 和精确断言基线。
        # 这里必须显式让路，避免被通用线路运价能力截走，导致关键题回归退化。
        if (
            "每月平均运费" in compact
            and origin_place
            and province
            and vehicle_type
            and len(years) == 1
            and years[0] in {2023, 2024, 2025}
        ):
            return None

        route_view_mode = self._resolve_route_pricing_view_mode(compact, years=years)
        # 对“合肥发江苏 17.5 车运输费用”这类没有显式年份、但线路/车型/费用口径明确的问法，
        # 使用历史台账 2023-2025 累计口径；这是既有历史线路运价 query_key 的默认统计范围，
        # 不引入新 query_key，也不让 LLM 参与查数。
        route_years = years or ([2023, 2024, 2025] if route_view_mode not in {"monthly_avg", "year_compare"} else [])
        if (
            route_view_mode
            and vehicle_type
            and (province or city)
            and route_years
            and all(item in {2023, 2024, 2025} for item in route_years)
        ):
            filters: dict[str, Any] = {
                "years": route_years,
                "vehicle_type": vehicle_type,
                "view_mode": route_view_mode,
            }
            if not years:
                filters["default_year_scope_label"] = "2023-2025历史累计"
            if origin_place:
                filters["origin_place"] = origin_place
            if province:
                filters["province"] = province
            if city:
                filters["city"] = city
            if route_view_mode == "monthly_avg":
                filters["year"] = route_years[0]
                filters["years"] = [route_years[0]]
            return LogisticsDataQaPlan(
                intent="compare" if route_view_mode == "year_compare" else "aggregate",
                query_key="hist_route_pricing_analysis",
                metrics=["avg_fee"] if route_view_mode != "fee_extremes" else ["min_fee", "max_fee"],
                dimensions=["biz_month"] if route_view_mode == "monthly_avg" else ["biz_year"] if route_view_mode == "year_compare" else [],
                filters=filters,
                group_by=["biz_month"] if route_view_mode == "monthly_avg" else ["biz_year"] if route_view_mode == "year_compare" else [],
                sort=[{"field": "biz_month", "direction": "asc"}] if route_view_mode == "monthly_avg" else [{"field": "biz_year", "direction": "asc"}] if route_view_mode == "year_compare" else [],
            )

        # B-gap Wave1：历史“某年某月总车次”题族已具备明确年份、月份和车次口径。
        # 这里新增通用月度车次 query_key，不再把该类题停留在通用澄清。
        if (
            year in {2023, 2024, 2025}
            and months
            and self._is_trip_question(compact)
            and not region
            and not vehicle_type
            and not any(keyword in compact for keyword in ("区域", "基地", "承运商", "物流公司", "客户", "排名"))
        ):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_monthly_trip_count_summary",
                metrics=["shipment_trip_count"],
                dimensions=[],
                filters={"year": year, "months": months},
            )

        # B-gap Wave1：历史始发地到目的省/市的平均运费或发运量 MW 题族。
        # 只放行“单始发 + 单目的 + 单指标”的明确统计题；多始发对比、差值和评价题仍继续澄清。
        if (
            year in {2023, 2024, 2025}
            and origin_place
            and (province or city)
            and not vehicle_type
            and not any(keyword in compact for keyword in ("分别", "差值", "对比", "最高", "最低", "排名", "前10", "前十"))
        ):
            route_metric = None
            if self._is_mw_question(compact):
                route_metric = "shipment_mw"
            elif "每车" in compact or "单车" in compact:
                route_metric = "avg_fee_per_trip"
            elif "平均运费" in compact or ("平均" in compact and any(keyword in compact for keyword in ("运费", "费用"))):
                route_metric = "avg_fee"
            if route_metric:
                return LogisticsDataQaPlan(
                    intent="aggregate",
                    query_key="hist_route_aggregate_summary",
                    metrics=[route_metric],
                    dimensions=[],
                    filters={
                        "year": year,
                        "origin_place": origin_place,
                        "province": province,
                        "city": city,
                        "metric": route_metric,
                    },
                )

        # B-gap Wave1：历史“始发地 + 车型”的平均单车运费 / 平均单瓦价题族。
        # 该题族缺的是可复用参数化 query_key，不涉及新业务口径；仍排除线路排名和多目的地问题。
        origin_vehicle_metric = self._resolve_origin_vehicle_metric(compact)
        if (
            year in {2023, 2024, 2025}
            and origin_place
            and vehicle_type
            and origin_vehicle_metric
            and not province
            and not city
            and not any(keyword in compact for keyword in ("排名", "前10", "前十", "最高", "最低"))
        ):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_origin_vehicle_metric_summary",
                metrics=[origin_vehicle_metric],
                dimensions=[],
                filters={
                    "year": year,
                    "origin_place": origin_place,
                    "vehicle_type": vehicle_type,
                    "metric": origin_vehicle_metric,
                },
            )

        # Round5：月份 + 额外费用 + 总W 数的单瓦成本题，当前统一按 2026 正式系统月份口径支持。
        # 这类问法已经明确给出公式，不再继续走缺年份的通用澄清。
        if (
            year in {None, 2026}
            and months
            and self._is_unit_fee_question(compact)
            and "额外费用" in compact
            and any(keyword in compact for keyword in ("总W数", "总瓦数", "运输组件总W数"))
        ):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_unit_fee_per_watt",
                metrics=["unit_fee_per_watt"],
                dimensions=[],
                filters={
                    "year": 2026,
                    "months": months,
                    "company_name": company_name,
                    "include_extra_cost": True,
                    "default_year_scope": True,
                    "default_year_scope_label": "2026正式系统",
                },
            )

        # Round5：像“2026年的运量综合”这类高频问法，当前统一解释为 2026 截至目前累计的
        # 发运量 MW + 车次综合结果，不再继续掉进通用澄清。
        if year == 2026 and "运量综合" in compact and not months:
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_mw_and_trip_count",
                metrics=["shipment_mw", "shipment_trip_count"],
                dimensions=[],
                filters={
                    "year": 2026,
                    "months": None,
                    "transport_mode": None,
                    "base_code": system_base_code,
                    "base_name": system_base_name,
                    "default_ytd_scope": True,
                    "monthly_breakdown": False,
                },
            )

        # Round5：线路简写题如果已经给出始发地、目的地和车型，则统一按 2023–2025
        # 历史累计平均运费返回，避免继续停留在通用澄清。
        if (
            not years
            and vehicle_type
            and origin_place
            and (province or city)
            and any(keyword in compact for keyword in ("运费", "运价", "报价"))
            and "每月" not in compact
            and "各月" not in compact
            and "最高价" not in compact
            and "最低价" not in compact
            and "均价" not in compact
            and "平均" not in compact
        ):
            filters: dict[str, Any] = {
                "years": [2023, 2024, 2025],
                "vehicle_type": vehicle_type,
                "view_mode": "avg_fee",
                "default_year_scope": True,
                "default_year_scope_label": "2023-2025历史累计",
            }
            if origin_place:
                filters["origin_place"] = origin_place
            if province:
                filters["province"] = province
            if city:
                filters["city"] = city
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_route_pricing_analysis",
                metrics=["avg_fee"],
                dimensions=[],
                filters=filters,
            )

        carrier_ranking_metric = self._resolve_carrier_ranking_metric(compact)
        if (
            carrier_ranking_metric
            and any(keyword in compact for keyword in ("承运商", "物流公司", "各物流"))
            and "前十" in compact
            and year in {2024, 2025, 2026}
            and (year in {2024, 2025} or months)
        ):
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="carrier_metric_ranking",
                metrics=[carrier_ranking_metric],
                dimensions=["carrier_name"],
                filters={
                    "year": year,
                    "months": months if year == 2026 else None,
                    "ranking_metric": carrier_ranking_metric,
                    "top_n": 10,
                },
                group_by=["carrier_name"],
                sort=[{"field": carrier_ranking_metric, "direction": "desc"}],
                limit=10,
            )

        if year == 2026 and any(keyword in compact for keyword in ("招标", "询比价")) and self._is_mw_question(compact):
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="sys_mw_by_procurement_type",
                metrics=["shipment_mw"],
                dimensions=["procurement_type"],
                filters={"year": year},
                group_by=["procurement_type"],
                sort=[{"field": "shipment_mw", "direction": "desc"}],
            )

        if year == 2026 and self._is_ytd_scope_question(compact) and self._is_mw_question(compact):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_mw_and_trip_count",
                metrics=["shipment_mw"],
                dimensions=[],
                filters={"year": year, "months": None, "base_code": system_base_code, "base_name": system_base_name},
            )

        # 903 全量补槽闭环：2026 基地 + 月份 + 总费用已经具备系统侧 base_code
        # 与 sys_total_fee_by_filters 执行能力，可直接进入 A 类受控查询。
        if year == 2026 and months and system_base_code and self._is_total_fee_question(compact):
            filters: dict[str, Any] = {
                "year": year,
                "months": months,
                "base_code": system_base_code,
                "base_name": system_base_name,
            }
            if customer_name:
                filters["customer_name"] = customer_name
            elif company_name:
                filters["company_name"] = company_name
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_total_fee_by_filters",
                metrics=["total_fee"],
                dimensions=[],
                filters=filters,
            )

        # Round4：2026 基地经营过滤总运费题在系统侧已具备稳定 base_code，可正式收进 A。
        # 这里只放行“基地 + 月份 + 客户/承运商 + 总运费”这组高价值题，不顺带放开全部基地题。
        if (
            year == 2026
            and months
            and system_base_code
            and self._is_total_fee_question(compact)
            and (customer_name or company_name)
        ):
            filters: dict[str, Any] = {
                "year": year,
                "months": months,
                "base_code": system_base_code,
                "base_name": system_base_name,
            }
            if customer_name:
                filters["customer_name"] = customer_name
            elif company_name:
                filters["company_name"] = company_name
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_total_fee_by_filters",
                metrics=["total_fee"],
                dimensions=[],
                filters=filters,
            )

        if year == 2026 and "送达城市任务量排名前十" in compact:
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="sys_task_count_ranking",
                metrics=["task_count"],
                dimensions=["delivery_city"],
                filters={"year": year, "dimension": "delivery_city", "top_n": 10},
                group_by=["delivery_city"],
                sort=[{"field": "task_count", "direction": "desc"}],
                limit=10,
            )

        if year == 2026 and "project_name维度任务量排名前十" in compact:
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="sys_task_count_ranking",
                metrics=["task_count"],
                dimensions=["project_name"],
                filters={"year": year, "dimension": "project_name", "top_n": 10},
                group_by=["project_name"],
                sort=[{"field": "task_count", "direction": "desc"}],
                limit=10,
            )

        if year == 2026 and "delivery_distance" in compact and "填充率" in compact:
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="sys_delivery_distance_fill_rate_by_province",
                metrics=["fill_rate"],
                dimensions=["delivery_province"],
                filters={"year": year, "top_n": 10},
                group_by=["delivery_province"],
                sort=[{"field": "fill_rate", "direction": "asc"}],
                limit=10,
            )

        if (year == 2026 or "送货单解析成功率" in compact) and "承运商" in compact and "解析成功率" in compact:
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="sys_parse_success_rate_by_carrier",
                metrics=["parse_success_rate"],
                dimensions=["company_name"],
                filters={"year": 2026, "top_n": 10},
                group_by=["company_name"],
            )

        if year == 2026 and "company_id" in compact and "找不到映射" in compact:
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="sys_company_mapping_gap",
                metrics=["task_count"],
                dimensions=["task_id", "company_id"],
                filters={"year": year, "limit": 20},
            )

        if year == 2026 and "extra_cost_audited=1" in compact:
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="sys_extra_cost_audited_concentration",
                metrics=["task_count"],
                dimensions=["company_name", "delivery_province"],
                filters={"year": year, "top_n": 10},
            )

        if province and "前5名客户" in compact and "总费用" in compact and self._is_mw_question(compact):
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="hist_top_customers_fee_and_mw_by_province",
                metrics=["total_fee", "shipment_mw"],
                dimensions=["customer_name"],
                filters={"year": year, "province": province},
                group_by=["customer_name"],
                sort=[{"field": "total_fee", "direction": "desc"}],
                limit=5,
            )

        if (
            "历史台账" in compact
            and "前10个客户" in compact
            and self._is_mw_question(compact)
        ):
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="hist_customer_mw_ranking",
                metrics=["shipment_mw"],
                dimensions=["customer_name"],
                filters={"year": year if year in {2023, 2024, 2025} else None, "top_n": 10},
                group_by=["customer_name"],
                sort=[{"field": "shipment_mw", "direction": "desc"}],
                limit=10,
            )

        if (
            province
            and self._is_total_fee_question(compact)
            and ("历史" in compact or (year in {2023, 2024, 2025}))
            and not origin_place
            and not vehicle_type
            and "平均" not in compact
            and not any(keyword in compact for keyword in ("前5", "前10", "排名", "客户", "城市", "填充率"))
        ):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_total_fee_by_province",
                metrics=["total_fee"],
                dimensions=[],
                filters={"year": year if year in {2023, 2024, 2025} else None, "province": province},
            )

        # 903 全量补槽闭环：历史总运费高频题族统一走通用汇总 query_key。
        # 只放行已经有明确年份且至少有一个确定过滤槽位的问题，避免把“年度经营评价”
        # 或“长距离订单排名”等仍需澄清/扩能力的题误收进 A。
        effective_company_name = company_name if company_name not in {"各", "各家", "不同"} else None
        if (
            year in {2023, 2024, 2025}
            and self._is_total_fee_question(compact)
            # 客户全称可能以“广东/江苏”等省名开头；若已经抽到客户槽位，
            # 省份槽位只能视为客户名称的一部分，不能阻断客户总运费受控 query_key。
            and not (province and not customer_name)
            and not origin_place
            and not vehicle_type
            and not any(keyword in compact for keyword in ("平均", "排名", "前5", "前10", "最高", "最低", "长距离", "路程", "距离"))
            and not any(keyword in compact for keyword in ("各物流承运商", "各承运商", "各物流公司", "各家物流", "不同物流公司"))
            and (months or region or transport_mode or effective_company_name or customer_name)
        ):
            filters: dict[str, Any] = {"year": year}
            if months:
                filters["months"] = months
            if region:
                filters["region_name"] = region
            if transport_mode:
                filters["transport_mode"] = transport_mode
            if effective_company_name:
                filters["carrier_name"] = effective_company_name
            if customer_name:
                filters["customer_name"] = customer_name
            if any(keyword in compact for keyword in ("占比", "比例", "占全年")):
                filters["include_share"] = True
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_total_fee_summary",
                metrics=["total_fee"],
                dimensions=[],
                filters=filters,
            )

        if year in {2023, 2024, 2025} and region and "各省" in compact and self._is_mw_question(compact):
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="hist_mw_by_region_province",
                metrics=["shipment_mw"],
                dimensions=["province"],
                filters={"year": year, "region_name": region, "provinces": province_list},
                group_by=["province"],
                sort=[{"field": "shipment_mw", "direction": "desc"}],
            )

        if year in {2023, 2024, 2025} and "各区域" in compact and self._is_mw_question(compact):
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="hist_mw_by_all_regions",
                metrics=["shipment_mw"],
                dimensions=["region_name"],
                filters={"year": year},
                group_by=["region_name"],
                sort=[{"field": "shipment_mw", "direction": "desc"}],
            )

        if self._is_city_carrier_avg_price_question(compact) and city:
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="hist_city_carrier_avg_fee_per_trip",
                metrics=["avg_fee_per_trip"],
                dimensions=["carrier_name"],
                filters={"year": year if year in {2023, 2024, 2025} else None, "city": city},
                group_by=["carrier_name"],
                sort=[{"field": "avg_fee_per_trip", "direction": "desc"}],
            )

        if (
            year is None
            and customer_name
            and "项目名称" not in compact
            and "项目" in compact
            and self._is_mw_question(compact)
        ):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_customer_mw",
                metrics=["shipment_mw"],
                dimensions=[],
                filters={"year": None, "customer_name": customer_name},
            )

        if year in {2023, 2024, 2025} and vehicle_type and self._is_trip_question(compact):
            # 车型车次题如果用户同时给出始发基地，必须保留始发过滤条件；
            # 否则“合肥基地 13m 车车次”会被误算成全历史同车型车次。
            trip_filters = {"year": year, "vehicle_type": vehicle_type}
            if origin_place:
                trip_filters["origin_place"] = origin_place
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_vehicle_type_trip_count",
                metrics=["shipment_trip_count"],
                dimensions=[],
                filters=trip_filters,
            )
        return None

    def _extract_year(self, question: str) -> int | None:
        """从公共槽位抽取器提取单一年份。"""

        return self.slot_extractor.extract_year(question)

    def _extract_years(self, question: str) -> list[int]:
        """提取问句里出现的全部年份。

        说明：
            1. Round2 需要支持“24年和25年对比”这类双年份问法；
            2. 返回值按出现顺序去重，避免 compare 题丢掉年份维度；
            3. 只识别当前物流一期已经锁定的 2023–2026 年。
        """
        return self.slot_extractor.extract_years(question)

    def _extract_months(self, question: str) -> list[int]:
        """提取月份列表。

        说明：
            1. 兼容“1-2月”“1至12月”“2月份”这类高频写法；
            2. 返回值按自然顺序去重，供 2026 月区间和历史月度对比复用；
            3. 这里只处理正向区间，不解析跨年表达。
        """
        return self.slot_extractor.extract_months(question)

    def _extract_region(self, question: str) -> str | None:
        """从公共槽位抽取器提取区域。"""

        return self.slot_extractor.extract_region(question)

    def _extract_province(self, question: str) -> str | None:
        """从公共槽位抽取器提取省份。"""

        return self.slot_extractor.extract_province(question)

    def _extract_origin_place(self, question: str) -> str | None:
        """从公共槽位抽取器提取始发地。"""

        return self.slot_extractor.extract_origin_place(question)

    @staticmethod
    def _is_hist_origin_vehicle_breakdown_question(question: str) -> bool:
        """判断是否为历史始发地 + 车型维度的多指标汇总题。

        参数：
            question: 已去空格的用户问题。
        返回值：
            命中返回 True，否则返回 False。

        说明：
            该判断只放行“不同车型”且含始发地语义的历史统计题，避免把宽表、
            矩阵表等真正需要模板确认的问题误迁为 A。
        """

        if "不同车型" not in question or "始发" not in question:
            return False
        metric_hits = sum(
            1
            for keyword_group in (
                ("发运车次", "车次", "车数"),
                ("总费用", "总运费", "运输费用"),
                ("平均单车费用", "平均单车运费", "平均单价/车"),
            )
            if any(keyword in question for keyword in keyword_group)
        )
        return metric_hits >= 2

    def _extract_system_base_name(self, question: str) -> str | None:
        """提取 2026 系统侧基地口径。

        说明：
            1. 当前只放行已经在正式系统里稳定出现的基地口径；
            2. 返回值保留业务展示名称，仓储层再统一映射 base_code；
            3. 不和历史台账的始发地口径混用。
        """
        return self.slot_extractor.extract_system_base_name(question)

    def _extract_system_base_code(self, question: str) -> str | None:
        """提取 2026 系统侧基地编码。

        说明：
            1. 当前一期只固化已经在 Round4 验证通过的基地编码映射；
            2. 映射统一走 dwd_logistics_ship_task.base_code；
            3. 若问题未显式提基地，则返回空值。
        """
        return self.slot_extractor.extract_system_base_code(question)

    def _extract_destination_city(self, question: str) -> str | None:
        """提取线路问法里的目的城市。

        说明：
            1. 当前只用于 Round2 的历史线路运价题族；
            2. 同时兼容 Round3 的“合肥城市发运中”这类城市统计题；
            3. 优先识别“发往乌鲁木齐”“合肥发广州”这类高频写法；
            4. 若目的地已经能稳定识别成省份，则不在这里重复返回城市。
        """
        return self.slot_extractor.extract_destination_city(question)

    def _extract_transport_mode(self, question: str) -> str | None:
        """提取正式 planner 当前可安全下推的运输方式标准值。

        说明：
            1. 公共 slot_extractor 可以识别“多式联运/水路”等更宽的 NLU 诊断槽位；
            2. 正式 planner 当前只把已验证可下推到查询层的公路/铁路作为过滤条件；
            3. 对尚未完成系统侧过滤口径验证的运输方式，保留原有行为，不把它们强行下推，
               避免把原本可回答的 A 类题误改成 unsupported。
        """

        transport_mode = self.slot_extractor.extract_transport_mode(question)
        if transport_mode in {"多式联运", "水路"}:
            return None
        return transport_mode

    def _extract_vehicle_type(self, question: str) -> str | None:
        """提取车型口径。

        说明：
            1. 当前优先兼容 Top200 里最常见的 17.5 / 13m 问法；
            2. 返回值统一成仓储层可复用的标准车型口径；
            3. 不在这里扩开放车型识别，避免误抽取。
        """
        return self.slot_extractor.extract_vehicle_type(question)

    def _extract_customer_name(self, question: str) -> str | None:
        """提取客户/项目主体名称。

        说明：
            1. 当前优先兼容 Top200 里的高价值客户问法；
            2. 只做轻量文本清洗，不做开放实体识别；
            3. 返回值仍交给仓储层按前缀或 project_name 做模糊命中。
        """
        return self.slot_extractor.extract_customer_name(question)

    def _extract_company_name(self, question: str) -> str | None:
        """提取 2026 系统口径下的承运商公司名。

        说明：
            1. 当前只服务于“某承运商某月总计运费”这类高价值题族；
            2. 如果问句已经明确走客户口径，则不在这里强行抽成承运商；
            3. 返回值交给仓储层做 LIKE 匹配，兼容简称与全称。
        """
        return self.slot_extractor.extract_company_name(question)

    def _extract_historical_carrier_name(self, question: str) -> str | None:
        """提取历史台账中已校验的承运商别名。

        参数：
            question: 已压缩空白的用户问题。

        返回：
            可交给历史明细表 logistics_company_name 做模糊匹配的承运商简称。

        说明：
            该方法只承接样例题和现有台账中可验证的“晶茂物流/苏州晶茂物流/英赋嘉”简称，
            不把所有带“物流”的短语都强行解释成承运商，避免扩大 A 类边界。
        """

        if "晶茂" in question:
            return "晶茂"
        if "英赋嘉" in question:
            return "英赋嘉"
        return None

    def _extract_province_list(self, question: str) -> list[str]:
        """提取问句里显式给出的省份列表。"""
        return self.slot_extractor.extract_province_list(question)

    def _extract_product_spec(self, question: str) -> str | None:
        """提取历史规格统计题里的组件规格。

        参数：
            question: 已压缩空白的用户问题。

        返回：
            规格文本；未识别时返回 None。

        说明：
            当前只识别题库中稳定出现的 GCL-...-xxxW 规格格式，
            不做开放产品实体识别，避免把普通型号描述误下推到查询层。
        """

        match = re.search(r"规格为([^的]+?W)的", question)
        if match:
            return match.group(1)
        return None

    def _clean_subject_phrase(self, raw_text: str) -> str:
        """清洗客户/项目主体短语。"""
        return self.slot_extractor.clean_subject_phrase(raw_text)

    def _is_city_carrier_avg_price_question(self, question: str) -> bool:
        """判断是否属于“城市 × 承运商平均单价/车”题型。

        说明：
            1. Round3 只放行已经确认高频且数据可算的城市承运商单车均价题；
            2. 这里显式要求同时出现城市、物流公司和平均单价/车口径，避免误伤其他城市统计题；
            3. 未给年份时默认走 2023–2025 历史累计，这是当前题族已经确认的统一业务口径。
        """
        carrier_group = any(keyword in question for keyword in ("不同物流公司", "不同承运商", "各物流公司", "各承运商"))
        return "城市发运中" in question and carrier_group and "平均单价/车" in question

    def _clean_company_phrase(self, raw_text: str) -> str:
        """清洗承运商主体短语。

        说明：
            1. 这里只去掉问题序号、时间前缀和通用修饰词；
            2. 保留“苏州晶茂物流”“英赋嘉”这类业务上常见简称；
            3. 如果清洗后只剩空串，则返回空值。
        """
        return self.slot_extractor.clean_company_phrase(raw_text)

    def _resolve_assist_year(self, question: str, llm_result: LogisticsLlmUnderstandingResult) -> int | None:
        """解析 assist 模式下的年份。"""
        llm_year = llm_result.time_range.get("year") or llm_result.filters.get("year")
        if isinstance(llm_year, int):
            return llm_year
        if isinstance(llm_year, str) and llm_year.isdigit():
            return int(llm_year)
        return self._extract_year(question)

    def _resolve_assist_months(self, question: str, llm_result: LogisticsLlmUnderstandingResult) -> list[int]:
        """解析 assist 模式下的月份列表。"""
        raw_months = llm_result.time_range.get("months") or llm_result.filters.get("months")
        if isinstance(raw_months, list):
            months = [int(item) for item in raw_months if str(item).isdigit()]
            if months:
                return months
        return self._extract_months(question)

    def _resolve_assist_region(self, question: str, llm_result: LogisticsLlmUnderstandingResult) -> str | None:
        """解析 assist 模式下的区域。"""
        region = llm_result.filters.get("region_name")
        if isinstance(region, str) and region in self.REGION_NAMES:
            return region
        return self._extract_region(question)

    def _resolve_assist_province(self, question: str, llm_result: LogisticsLlmUnderstandingResult) -> str | None:
        """解析 assist 模式下的省份。"""
        province = llm_result.filters.get("province")
        if isinstance(province, str) and province.strip():
            return province.replace("省", "").replace("市", "").strip()
        extracted = self._extract_province(question)
        if extracted:
            return extracted
        for alias, normalized in self.PROVINCE_ALIAS.items():
            short_alias = alias.replace("省", "").replace("自治区", "")
            if short_alias in question:
                return normalized
        return None

    def _resolve_assist_origin_place(self, question: str, llm_result: LogisticsLlmUnderstandingResult) -> str | None:
        """解析 assist 模式下的始发基地。"""
        origin_place = llm_result.filters.get("origin_place")
        if isinstance(origin_place, str) and origin_place.strip():
            return origin_place.strip().replace("基地", "")
        return self._extract_origin_place(question)

    def _resolve_assist_customer_name(self, question: str, llm_result: LogisticsLlmUnderstandingResult) -> str | None:
        """解析 assist 模式下的客户或项目主体。"""
        customer_name = llm_result.filters.get("customer_name")
        if isinstance(customer_name, str) and customer_name.strip():
            return customer_name.strip()
        return self._extract_customer_name(question)

    def _resolve_assist_carrier_name(self, question: str, llm_result: LogisticsLlmUnderstandingResult) -> str | None:
        """解析 assist 模式下的承运商。"""
        company_name = llm_result.filters.get("company_name") or llm_result.filters.get("carrier_name")
        if isinstance(company_name, str) and company_name.strip():
            return company_name.strip()
        if "晶茂" in question:
            return "晶茂"
        return None

    def _resolve_assist_vehicle_type(self, question: str, llm_result: LogisticsLlmUnderstandingResult) -> str | None:
        """解析 assist 模式下的车型口径。"""
        vehicle_type = llm_result.filters.get("vehicle_type")
        if isinstance(vehicle_type, str) and vehicle_type.strip():
            return vehicle_type.strip().replace("车", "")
        return self._extract_vehicle_type(question)

    def _resolve_assist_special_scope(self, question: str, llm_result: LogisticsLlmUnderstandingResult) -> str | None:
        """解析 assist 模式下的特殊业务口径。"""
        special_scope = llm_result.filters.get("special_scope")
        if isinstance(special_scope, str) and special_scope.strip():
            return special_scope.strip()
        if any(keyword in question for keyword in ("经营计划", "经营计划部")):
            return "planning"
        if "辅料送样" in question:
            return "sample"
        if "刘娟" in question:
            return "liujuan"
        return None

    def _extract_procurement_type(self, question: str) -> str | None:
        """抽取 2026 系统侧采购方式。

        参数：
            question: 已压缩空白的用户问题。

        返回：
            `procurement_type` 可直接校验的采购方式；未命中返回 None。

        说明：
            历史台账没有稳定采购方式字段，本函数只服务 2026 系统数据分支，
            不把历史招标/询比价场景问题硬迁为 A。
        """

        if "询比价" in question:
            return "询比价"
        if "招标" in question:
            return "招标"
        return None

    def _is_mw_question(self, question: str) -> bool:
        """判断当前问句是否在问运量/MW。"""
        if self._is_unit_fee_question(question):
            return False
        return any(keyword in question for keyword in self.MW_KEYWORDS) or "MW" in question or "mw" in question

    def _is_trip_question(self, question: str) -> bool:
        """判断当前问句是否在问车次/车数。"""
        return any(keyword in question for keyword in self.TRIP_KEYWORDS)

    def _is_total_fee_question(self, question: str) -> bool:
        """判断当前问句是否在问总费用/总运费。"""
        return any(keyword in question for keyword in self.TOTAL_FEE_KEYWORDS)

    def _is_complex_report_question(self, question: str) -> bool:
        """判断是否属于当前应追问报表模板的复杂报表题。

        参数：
            question: 已压缩空白的用户问题。

        返回：
            命中宽表、透视表、同比变化、多指标经营总表等报表模板诉求时返回 True。

        说明：
            该判断不扩 query_key，只保护现有稳定链路，避免把单指标结果包装成完整报表。
        """

        complex_keywords = (
            "宽表",
            "透视表",
            "经营总表",
            "经营汇总表",
            "区域经营表",
            "区域经营分析表",
            "结构表",
            "季度经营",
            "月报表",
            "同一张明细汇总表",
            "热力表",
            "交叉表",
            "矩阵表",
            "二维交叉表",
            "同比变化额",
            "同比变化率",
            "变化额和变化率",
            "并补充对应",
            "前20条记录",
            "发货日期",
            "按年度拆分",
            "年度拆分",
            "发运量占比",
            "运量占比",
            "费用占比",
            "前十条线路",
            "年度对比表",
            "每年的发运量",
            "平均单价/车和平均元/瓦",
            "Top10和Bottom10",
        )
        if any(keyword in question for keyword in complex_keywords):
            return True
        if (
            any(keyword in question for keyword in ("平均单价/车", "平均单车", "平均元/瓦"))
            and any(keyword in question for keyword in ("发运量", "运量", "发运瓦数"))
            and any(keyword in question for keyword in ("总费用", "总运费", "运输费用"))
        ):
            return True
        if (
            any(keyword in question for keyword in ("发运量", "运量", "发运瓦数"))
            and any(keyword in question for keyword in ("总费用", "总运费", "运输费用"))
            and any(keyword in question for keyword in ("车次", "车辆数", "车数"))
        ):
            return True
        if (
            any(keyword in question for keyword in ("车次或车辆数", "车次/车辆数", "车次", "车辆数", "车数"))
            and any(keyword in question for keyword in ("平均单车费用", "平均单车运费", "平均单价/车", "单车费用"))
            and any(keyword in question for keyword in ("跨年对比", "每年", "年度对比", "每年的"))
        ):
            # 车辆数是否去重、平均单车费用以车次还是车辆为分母，必须先业务确认；
            # 这里保持 B 类追问，避免把单指标查询误包装成车辆效率报表。
            return True
        if (
            any(keyword in question for keyword in ("额外费用", "异常费", "异常费用"))
            and any(keyword in question for keyword in ("涉及记录数", "记录数", "涉及客户数", "平均金额", "费用率", "按月份", "按物流公司", "按承运商", "按区域"))
        ):
            # 异常费口径涉及费用类型、审核状态和费用率分母，当前必须先追问确认。
            return True
        if (
            "备注中包含" in question
            and any(keyword in question for keyword in ("倒运", "中转", "换车", "压车", "放空"))
            and any(keyword in question for keyword in ("费用金额", "金额", "费用"))
        ):
            # 备注关键词命中不等于异常费用口径已确认，先保护为 B 类。
            return True
        if (
            "备注中包含" in question
            and any(keyword in question for keyword in ("历史发运记录数量", "发运记录数量", "记录数量", "总费用", "涉及区域", "按年份拆分", "前50条明细", "明细"))
        ):
            # “铁路改公路”等备注词不能被拆成运输方式过滤；关键词字段、匹配方式和明细口径需先确认。
            return True
        if "日实际发运件数" in question and "日计划发运件数" in question:
            # 计划/实际件数差异需要先确认计划字段来源、日粒度和超发/缺口计算口径。
            return True
        if "同一车号" in question and "同一天" in question and any(keyword in question for keyword in ("多个客户", "客户数", "线路数")):
            # 车号、日期、客户和线路的异常组合检查属于明细稽核，不是当前聚合查询能力。
            return True
        if (
            any(keyword in question for keyword in ("项目名称", "每个项目", "项目“", "项目\""))
            and any(keyword in question for keyword in ("任务数", "产品数量", "涉及省份", "涉及物流公司", "涉及承运商", "收货省市", "未签收", "待派车", "任务明细", "跨省发货"))
        ):
            # 项目名称未作为稳定统计维度接入，不能用省份/承运商费用查询替代项目分析。
            return True
        if "发货类型" in question and any(keyword in question for keyword in ("正常发货", "辅料送样", "客户项目数", "产品数量", "任务数")):
            # 发货类型和客户项目数涉及系统侧多表口径，当前先作为 B 类追问。
            return True
        if (
            any(keyword in question for keyword in ("项目数量", "提货单位", "采购类型"))
            and any(keyword in question for keyword in ("收货省份数量", "收货城市数量", "主要物流公司", "主要承运商", "主要目的省份", "按月份", "收货省份的分布"))
        ):
            # 项目数量、提货单位和采购类型分布依赖系统侧多表定义，当前不能用费用分组替代。
            return True
        if (
            any(keyword in question for keyword in ("发货产品", "产品功率", "功率为"))
            and any(keyword in question for keyword in ("产品名称", "规格", "产品数量", "任务数", "涉及项目", "收货省份分布", "交叉表"))
        ):
            # 产品明细和产品数量尚未进入稳定统计口径，不能用物流费用结果替代。
            return True
        if "仓库绑定" in question and any(keyword in question for keyword in ("人员数量", "未绑定人员", "人员最少")):
            # 仓库人员绑定不属于当前物流问答稳定数据域，不能误走物流费用查询。
            return True
        return "汇总成" in question and any(keyword in question for keyword in ("年度", "季度", "三层维度"))

    def _is_unit_fee_question(self, question: str) -> bool:
        """判断当前问句是否在问单瓦价/元瓦。"""
        return any(keyword in question for keyword in ("单瓦价", "单W运输成本", "元瓦", "单瓦运输成本", "单瓦成本"))

    def _is_ytd_scope_question(self, question: str) -> bool:
        """判断问句是否明确表达“当前累计 / 截至目前”。

        说明：
            1. 该判断用于 2026 系统总量类问题；
            2. 只有明确说“目前为止 / 当前累计 / 截至目前”时，才允许不传月份直接走全年当前累计；
            3. 避免把“2026年运量综合”这类模糊问法误落成 1 月默认值。
        """
        return any(keyword in question for keyword in ("目前为止", "截至目前", "当前累计", "当前总和", "运量总和"))

    def _is_monthly_breakdown_request(self, question: str) -> bool:
        """判断是否需要按月拆分返回。

        参数：
            question: 已压缩空白的用户问题。

        返回：
            用户明确要求趋势、图表、按月份展示或月度对比时返回 True。

        说明：
            该标记只影响现有 query_key 的结果展示颗粒度，不改变 query_key 和 A/B/C 边界。
        """

        return any(
            keyword in question
            for keyword in (
                "折线图",
                "趋势图",
                "看趋势",
                "趋势",
                "柱状图",
                "柱形图",
                "按月",
                "月度",
                "各月",
                "每月",
                "每个月",
                "这几个月",
                "这三个月",
                "对比一下",
            )
        )

    def _is_carrier_kpi_question(self, question: str) -> bool:
        """判断当前问句是否在问承运商年度 KPI。"""
        carrier_group = any(keyword in question for keyword in ("承运商", "物流公司", "物流供应商"))
        if "各物流公司" in question:
            carrier_group = True
        if not carrier_group and "物流" in question and any(keyword in question for keyword in ("各家", "分别", "年度")):
            carrier_group = True
        volume_or_fee = self._is_mw_question(question) or self._is_total_fee_question(question)
        if not carrier_group or not volume_or_fee:
            return False
        if any(keyword in question for keyword in ("各家", "分别", "占比", "年度")):
            return True
        # 兼容“25年物流公司承运量”“2025年物流供应商发运量是多少”“25年各家物流承运量”这类简写问法。
        return bool(re.search(r"\d{2,4}年.*(?:物流公司|承运商|物流供应商|各家物流|物流).*(承运量|运输量|发运量|发货量|运量|运输费用|运费)", question))

    def _resolve_carrier_kpi_view_mode(self, question: str) -> str:
        """根据问法决定承运商 KPI 的展示重点。"""
        if "占比" in question or self._is_mw_question(question):
            return "full_kpi"
        if self._is_total_fee_question(question):
            return "fee_only"
        return "full_kpi"

    def _is_monthly_fee_compare_question(self, question: str) -> bool:
        """判断当前问句是否在问按月运费对比。"""
        return ("每个月" in question or "各月" in question) and any(keyword in question for keyword in ("运费", "费用"))

    def _resolve_route_pricing_view_mode(self, question: str, *, years: list[int]) -> str | None:
        """解析历史线路运价题的展示模式。"""
        if ("最高价" in question or "最低价" in question) and len(years) == 1:
            return "fee_extremes"
        if "每个月" in question or "每月" in question or "各月" in question or "1-12月" in question:
            return "monthly_avg"
        if any(keyword in question for keyword in ("对比", "分别")) and len(years) >= 2:
            return "year_compare"
        if any(keyword in question for keyword in ("均价", "平均运费", "每车的运费均价", "运输费用", "运费", "运价", "报价")):
            return "avg_fee"
        return None

    def _resolve_origin_vehicle_metric(self, question: str) -> str | None:
        """解析“始发地 + 车型”成本题的指标。

        参数：
            question: 已压缩空白的用户问题。

        返回：
            avg_fee_per_trip 或 unit_fee_per_watt；无法安全识别时返回 None。

        说明：
            该函数只用于 B-gap Wave1 的受控 A 类候选题族。它不处理排名、
            最高/最低、差异解释等仍需澄清或扩 query_key 的问题。
        """

        if any(keyword in question for keyword in ("平均单车运费", "单车运费", "平均单车运输费用", "单车运输费用", "单价/车", "平均单价/车")):
            return "avg_fee_per_trip"
        if any(keyword in question for keyword in ("平均单瓦价", "单瓦价", "元/瓦", "元瓦", "单瓦成本")):
            return "unit_fee_per_watt"
        return None

    def _resolve_carrier_ranking_metric(self, question: str) -> str | None:
        """解析承运商排名题的排序指标。"""
        if self._is_unit_fee_question(question):
            return "unit_fee_per_watt"
        if any(keyword in question for keyword in ("总运费", "运费排名", "按运费排名", "运输费用排名", "按运输费用排名")):
            return "total_fee"
        return None

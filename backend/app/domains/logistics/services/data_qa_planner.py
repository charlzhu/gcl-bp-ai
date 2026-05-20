from __future__ import annotations

import re
from typing import Any

from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaPlan
from backend.app.domains.logistics.schemas.llm_understanding import LogisticsLlmUnderstandingResult
from backend.app.domains.logistics.services.business_entity_resolver import (
    CarrierCandidateProvider,
    LogisticsBusinessEntityResolver,
)
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
        "发运合计多少量",
        "物流发运合计多少量",
        "发运多少量",
    )
    TRIP_KEYWORDS = ("总车次", "承运车次", "发运车次", "多少车次", "多少车", "总共发了多少车次", "总车数", "车数", "车辆数", "车次")
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
    SYS_TOTAL_FEE_FIELD_FILTER_ALIASES = {
        # 2026 系统总费用里，“经营计划”是扩充部门字段值，不是旧的锁定特殊口径。
        "经营计划部": ("expand_dept", "经营计划部"),
        "经营计划": ("expand_dept", "经营计划"),
        # “刘娟”是委托人字段值，可与扩充部门等其他字段叠加过滤。
        "刘娟": ("entrusted_person", "刘娟"),
    }
    REMARK_SUPPORTED_KEYWORDS = ("倒运", "中转", "换车", "压车", "放空")
    REMARK_FEE_RATIO_KEYWORDS = ("倒运", "中转")
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
        "hist_avg_pallet_per_vehicle",
        "sys_driver_phone_name_consistency",
        "sys_driver_id_phone_consistency",
        "sys_special_total_fee",
        "composite_decomposed",
    }

    def __init__(
        self,
        *,
        slot_extractor: LogisticsSlotExtractor | None = None,
        business_entity_resolver: LogisticsBusinessEntityResolver | None = None,
        historical_carrier_candidate_provider: CarrierCandidateProvider | None = None,
    ) -> None:
        """初始化 planner。

        参数：
            slot_extractor: 公共槽位抽取器，用于复用年份、月份、区域、省份、车型等基础槽位。
            business_entity_resolver: 业务实体解析器，用于承运商等可随数据变化的实体解析。
            historical_carrier_candidate_provider: 历史承运商候选源；未显式传入 resolver 时用于构造默认 resolver。

        返回：
            无返回值。
        """

        self.slot_extractor = slot_extractor or LogisticsSlotExtractor()
        self.business_entity_resolver = business_entity_resolver or LogisticsBusinessEntityResolver(
            historical_carrier_candidate_provider=historical_carrier_candidate_provider
        )

    def build_plan(self, question: str) -> LogisticsDataQaPlan:
        """把自然语言问题转换成最小可执行查询计划。"""
        normalized_question = question.strip()
        compact = re.sub(r"\s+", "", normalized_question)
        ranking_top_n = self._extract_top_n(compact)
        policy = LogisticsQuestionBankResponsePolicy().match(normalized_question)
        pre_year = self._extract_year(compact)
        pre_months = self._extract_months(compact)

        if pre_year == 2026 and pre_months and "额外费用" in compact and any(keyword in compact for keyword in ("项目", "原因", "明细")):
            # 月份明确时，额外费用总额已有系统侧确定性口径；项目/原因明细尚未固化，
            # 因此先返回可审计总额，并把明细边界交给服务层作为 warning 展示。
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_extra_fee_summary",
                metrics=["extra_fee"],
                dimensions=[],
                filters={"year": pre_year, "months": pre_months, "detail_warning": "extra_fee_project_reason_unfixed"},
            )

        # 当前正式运量口径是瓦数/MW；用户明确要求“吨”时不能用 MW 结果替代。
        # 该边界必须早于复合拆分，否则“并列采购方式发运量吨”会被误拆成 MW 子查询。
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

        # 综合型问题“是否可拆、如何拆”必须由 LLM 语义理解层主导。
        # 规则 planner 不再按关键词直接拆分，只保留吨口径、历史字段缺失等硬边界；
        # 若 Guardrail 收到 LLM 的可信拆分候选，再由 build_plan_from_guardrail_candidate
        # 回构白名单子计划并执行安全校验。

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

        pre_origin_place = self._extract_origin_place(compact)
        pre_remark_amount_keywords = self._extract_valid_remark_keywords(compact, self.REMARK_SUPPORTED_KEYWORDS)
        if self._is_supported_remark_keyword_amount_summary(compact, pre_year, pre_remark_amount_keywords):
            # remark 年度汇总是受控白名单；必须早于始发地/车型等宽条件分支，避免其它 query_key 抢先吞掉备注条件。
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_remark_keyword_amount_summary",
                metrics=["record_count", "total_fee"],
                dimensions=[],
                filters={"year": pre_year, "keywords": pre_remark_amount_keywords},
            )
        if self._is_supported_remark_keyword_fee_ratio(compact):
            # remark 费用占比是受控白名单；直接放行，未命中的 remark 问法一律进入澄清保护。
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_remark_keyword_fee_ratio",
                metrics=["total_fee", "fee_share_pct"],
                dimensions=[],
                filters={"keywords": ["倒运", "中转"], "default_history_scope": "2023-2025"},
            )
        if self._is_remark_keyword_question_needing_clarification(compact):
            return LogisticsDataQaPlan(
                intent="clarification",
                needs_clarification=True,
                clarification_questions=[
                    "请先确认备注关键词、时间范围、统计指标和是否需要明细。",
                    "当前仅支持已审计的备注关键词年度记录数/费用金额汇总，以及倒运/中转总费用占历史物流总费用比例。",
                ],
                clarification_missing_slots=["备注关键词口径", "统计指标口径", "时间范围或明细模板"],
                clarification_reason="当前问题包含备注关键词条件，但未命中已审计的窄口径白名单，不能用通用费用或其它聚合结果替代。",
                clarification_category="remark_keyword_scope",
                clarification_template="remark_keyword_scope",
            )
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
        if self._is_hist_origin_vehicle_breakdown_question(compact) and (pre_year in {2023, 2024, 2025} or pre_year is None):
            # “某年某基地始发不同/各车型的车次/费用/装载托数”是源数据可稳定计算的明细汇总题，
            # 需要在复杂报表兜底之前放行，避免被“平均每车装载托数”通用澄清策略截断。
            filters: dict[str, Any] = {}
            if pre_year in {2023, 2024, 2025}:
                filters["year"] = pre_year
            else:
                # pallet_per_vehicle 当前只存在历史台账，问题未给时间时不追问，默认用可审计的 2023-2025 历史范围，
                # 并在 service 输出中明确说明 2026 系统侧暂无该字段，避免伪造 2026 装载托数。
                filters["years"] = [2023, 2024, 2025]
                filters["source_scope"] = "hist_pallet_metric"
            dimensions = ["required_vehicle_type"]
            if pre_origin_place:
                filters["origin_place"] = pre_origin_place
            else:
                # 题目写了“X始发”但当前始发地别名表无法稳定识别时，不能返回全部始发地分组冒充结果；
                # 保守转为澄清，让用户确认真实始发地名称或先维护始发地映射。
                return LogisticsDataQaPlan(
                    intent="clarification",
                    needs_clarification=True,
                    clarification_questions=[
                        "请确认始发地名称是否与历史台账一致，例如“合肥”“阜宁”等。",
                        "如需查询多个始发地，请明确是否按全部始发地分组展示。",
                    ],
                    clarification_missing_slots=["始发地标准名称"],
                    clarification_reason="当前问题包含始发地条件，但系统未能稳定识别该始发地，不能用全部始发地汇总替代。",
                    clarification_category="unknown_origin_place",
                    clarification_template="unknown_origin_place",
                )
            metrics = ["shipment_trip_count", "total_fee", "avg_fee_per_trip"]
            if any(keyword in compact for keyword in ("发运件数", "总件数", "件数")):
                metrics.insert(1, "shipment_count")
            if "平均每车装载托数" in compact:
                metrics.append("avg_pallet_per_vehicle")
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_origin_vehicle_breakdown_summary",
                metrics=metrics,
                dimensions=dimensions,
                filters=filters,
                group_by=dimensions,
                sort=[{"field": "total_fee", "direction": "desc"}],
            )

        remark_amount_keywords = self._extract_valid_remark_keywords(compact, self.REMARK_SUPPORTED_KEYWORDS)
        if self._is_supported_remark_keyword_amount_summary(compact, pre_year, remark_amount_keywords):
            # 年度 remark 多关键词记录数/费用金额是历史台账字段可直接计算的窄汇总；
            # 明细清单、区域分布、未知关键词、运费别名和跨年拆分仍保持澄清，避免扩大支持范围。
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_remark_keyword_amount_summary",
                metrics=["record_count", "total_fee"],
                dimensions=[],
                filters={"year": pre_year, "keywords": remark_amount_keywords},
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
        years = self._extract_years(compact)
        year_range = [item for item in years if item in {2023, 2024, 2025}]
        months = self._extract_months(compact)
        region = self._extract_region(compact)
        province = self._extract_province(compact)
        carrier_local_city = self._extract_local_carrier_city(compact)
        city = None if carrier_local_city else self._extract_carrier_scope_city(compact)
        origin_place = self._extract_origin_place(compact)
        system_base_name = self._extract_system_base_name(compact)
        system_base_code = self._extract_system_base_code(compact)
        customer_name = self._extract_customer_name(compact)
        company_name = self._extract_company_name(compact)
        carrier_name = self._extract_historical_carrier_name(compact)
        transport_mode = self._extract_transport_mode(compact)
        procurement_type = self._extract_procurement_type(compact)
        controlled_field_filters = self._extract_sys_total_fee_controlled_field_filters(compact)
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
        region_breakdown = self._is_all_region_breakdown_request(compact)
        no_explicit_time = not year and not year_range and not months
        if no_explicit_time and self._is_total_fee_question(compact):
            # 用户没有给年月日时，不再追问时间条件；按产品口径默认查询 2023-2026 全时间。
            # 这里只处理简单总费用汇总，复杂宽表/预测/明细类问题仍由前置保护逻辑拦截。
            filters: dict[str, Any] = {"years": [2023, 2024, 2025, 2026], "months": None}
            if region:
                filters["region_name"] = region
            if transport_mode:
                filters["transport_mode"] = transport_mode
            if company_name:
                filters["carrier_name"] = company_name
            if carrier_name:
                filters["carrier_name"] = carrier_name
            if customer_name:
                filters["customer_name"] = customer_name
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="mixed_total_fee_summary_2023_2026",
                metrics=["total_fee"],
                dimensions=[],
                filters=filters,
            )
        if no_explicit_time and self._is_mw_question(compact):
            # 用户未给时间但已明确“运量/MW”指标时，默认统计 2023-2026 全时间发运量。
            filters = {"years": [2023, 2024, 2025, 2026], "months": None}
            if region:
                filters["region_name"] = region
            if transport_mode:
                filters["transport_mode"] = transport_mode
            if carrier_name:
                filters["carrier_name"] = carrier_name
            if region_breakdown:
                # “各区域/分区域/每个区域/区域分别”表达的是按区域拆分，不能退化为全局总和。
                return LogisticsDataQaPlan(
                    intent="detail_list",
                    query_key="mixed_mw_by_all_regions_2023_2026",
                    metrics=["shipment_mw"],
                    dimensions=["region_name"],
                    filters=filters,
                    group_by=["region_name"],
                    sort=[{"field": "shipment_mw", "direction": "desc"}],
                )
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="mixed_mw_summary_2023_2026",
                metrics=["shipment_mw"],
                dimensions=[],
                filters=filters,
            )

        city_total_fee_rank_limit = self._extract_city_total_fee_rank_limit(compact)
        if (
            len(year_range) >= 2
            and carrier_name
            and self._is_mw_question(compact)
            and any(keyword in compact for keyword in ("每年", "按年", "按年份", "各年", "年度", "分别"))
            and not self._is_total_fee_question(compact)
            and not region_breakdown
        ):
            # 显式年份范围 + 显式承运商 + “按年/按年份/每年”等拆分词，业务诉求是逐年发运量；
            # 必须优先于后续单年总量 summary 分支，否则会只按首年汇总并丢失逐年维度。
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="hist_mw_by_year",
                metrics=["shipment_mw"],
                dimensions=["biz_year"],
                filters={"years": year_range, "carrier_name": carrier_name},
                group_by=["biz_year"],
                sort=[{"field": "biz_year", "direction": "asc"}],
            )

        if (
            year in {2023, 2024, 2025}
            and ranking_top_n
            and (region or province)
            and "城市" in compact
            and self._is_mw_question(compact)
            and not self._is_total_fee_question(compact)
        ):
            # 历史区域/省份下的城市发运量 TopN 是城市维度排名题，
            # 不能退化为区域或省份总发运量单行汇总。
            filters: dict[str, Any] = {"year": year, "top_n": ranking_top_n}
            if region:
                filters["region_name"] = region
            if province:
                filters["province"] = province
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="hist_city_mw_rank",
                metrics=["shipment_mw"],
                dimensions=["city"],
                filters=filters,
                group_by=["city"],
                sort=[{"field": "shipment_mw", "direction": "desc"}],
                limit=ranking_top_n,
            )
        if year and province and city_total_fee_rank_limit:
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="hist_total_fee_city_rank",
                metrics=["total_fee"],
                dimensions=["city"],
                filters={"year": year, "province": province},
                group_by=["city"],
                sort=[{"field": "total_fee", "direction": "desc"}],
                limit=city_total_fee_rank_limit,
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

        if (
            ("平均元/瓦" in compact or "平均元每瓦" in compact or self._is_unit_fee_question(compact))
            and "运输方式" in compact
            and region
        ):
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

        if self._is_total_fee_question(compact) and origin_place and carrier_name:
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_total_fee_by_origin_and_carrier",
                metrics=["total_fee"],
                dimensions=[],
                filters={"year": year, "origin_place": origin_place, "carrier_name": carrier_name},
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

        if any(keyword in compact for keyword in ("总发运件数", "发运件数", "总件数", "多少件")) and region:
            # 区域件数题支持可选年份和运输方式过滤，例如“2024年华东区域通过公路发运的总件数”。
            # 运输方式同义归一在 repository 执行，planner 只传受控槽位，避免把“公路”类明确过滤题误降级为澄清。
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_quantity_by_region",
                metrics=["shipment_count"],
                dimensions=[],
                filters={"year": year, "region_name": region, "transport_mode": transport_mode},
            )

        if year in {2023, 2024, 2025} and customer_name and self._is_mw_question(compact):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_customer_mw",
                metrics=["shipment_mw"],
                dimensions=[],
                filters={"year": year, "months": months or None, "customer_name": customer_name},
            )

        if year in {2023, 2024, 2025} and origin_place and carrier_name and self._is_mw_question(compact):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_mw_by_origin_and_carrier",
                metrics=["shipment_mw"],
                dimensions=[],
                filters={"year": year, "origin_place": origin_place, "carrier_name": carrier_name},
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
            signedfor_top_n = self._extract_top_n(compact) or 10
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="sys_signedfor_rate_by_carrier",
                metrics=["signedfor_rate"],
                dimensions=["carrier"],
                filters={"year": year, "top_n": signedfor_top_n},
                group_by=["carrier"],
                limit=signedfor_top_n,
            )

        if (
            year in {2023, 2024, 2025}
            and self._is_carrier_kpi_question(compact)
            and not self._is_monthly_fee_compare_question(compact)
            and not self._extract_top_n(compact)
            and not self._has_extra_breakdown_intent(compact, allowed_dimension="carrier_name")
            and not (
                # “23年-25年，某承运商每年发运量分别是多少”是显式跨年 + 显式承运商的逐年发运量题；
                # 这里必须让后续 hist_mw_by_year 专用分支处理，避免本宽 KPI 分支先返回单年承运商排名。
                len(year_range) >= 2
                and carrier_name
                and self._is_mw_question(compact)
                and any(keyword in compact for keyword in ("每年", "按年", "按年份", "各年", "年度", "分别"))
                and not self._is_total_fee_question(compact)
                and not region_breakdown
            )
        ):
            filters: dict[str, Any] = {
                "year": year,
                "region_name": region,
                "city": city,
                "view_mode": self._resolve_carrier_kpi_view_mode(compact),
            }
            if carrier_local_city:
                # “苏州的物流公司/苏州本地物流公司”是承运商归属城市口径，
                # 不能复用目的城市 city，否则会把发往苏州的外地承运商统计进去。
                filters["carrier_local_city"] = carrier_local_city
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="hist_carrier_kpi_by_year",
                metrics=["shipment_mw", "shipment_share_pct", "total_fee"],
                dimensions=["carrier_name"],
                filters=filters,
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

        if len(year_range) > 1 and all(item in {2023, 2024, 2025} for item in year_range) and self._is_monthly_fee_compare_question(compact):
            # “2023–2025 年各月物流总费用”属于跨年度逐月对比题，必须保留 year-month 粒度，
            # 不能退化成单一年份或把 3 年同月份合并。
            return LogisticsDataQaPlan(
                intent="compare",
                query_key="hist_monthly_total_fee_by_year",
                metrics=["total_fee"],
                dimensions=["biz_month"],
                filters={"years": year_range},
                group_by=["biz_month"],
                sort=[{"field": "biz_month", "direction": "asc"}],
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

        unknown_field_scope_terms = self._extract_unknown_sys_total_fee_field_scope_terms(
            compact,
            controlled_field_filters=controlled_field_filters,
        )
        if year == 2026 and self._is_total_fee_question(compact) and unknown_field_scope_terms:
            unknown_text = "、".join(unknown_field_scope_terms)
            return LogisticsDataQaPlan(
                intent="clarification",
                needs_clarification=True,
                clarification_category="field_scope_mapping",
                clarification_questions=[
                    f"请确认“{unknown_text}”对应哪个字段口径：扩充部门、委托人、客户、承运商、项目还是其他字段？",
                    "字段口径确认后，系统会按该字段与已给出的时间范围叠加过滤统计用车总费用。",
                ],
                clarification_missing_slots=["字段口径"],
                clarification_reason=f"问题中的“{unknown_text}”没有受控字段映射，不能默认查全量或套用其他特殊口径。",
                clarification_template="field_scope_mapping",
            )

        if year == 2026 and self._is_total_fee_question(compact) and controlled_field_filters:
            # 受控业务词优先解释为真实字段过滤；若同句仍残留未知范围词，上方已转澄清，避免静默丢条件。
            filters: dict[str, Any] = {"year": year, "months": months, **controlled_field_filters}
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

        if (
            year == 2026
            and customer_name
            and self._is_total_fee_question(compact)
            and not origin_place
            and not ranking_top_n
            and not any(keyword in compact for keyword in ("排名", "排行", "top", "TOP"))
        ):
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

        if (
            year == 2026
            and company_name
            and self._is_total_fee_question(compact)
            and not origin_place
            and not customer_name
            and not ranking_top_n
            and not any(keyword in compact for keyword in ("排名", "排行", "top", "TOP"))
        ):
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
            and not ranking_top_n
            and not any(keyword in compact for keyword in ("排名", "排行", "top", "TOP"))
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
            monthly_breakdown = self._is_monthly_breakdown_request(compact)
            filters = {
                "year": year,
                "province": province,
                "months": months,
                "include_extra_fee": "额外费用" in compact,
            }
            if monthly_breakdown:
                filters["monthly_breakdown"] = True
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_unit_fee_per_watt",
                metrics=["unit_fee_per_watt"],
                dimensions=["biz_month"] if monthly_breakdown else [],
                filters=filters,
                group_by=["biz_month"] if monthly_breakdown else [],
                sort=[{"field": "biz_month", "direction": "asc"}] if monthly_breakdown else [],
            )

        if year in {2023, 2024, 2025} and region_breakdown and self._is_mw_question(compact):
            # 用户说“各区域/分区域/每个区域/区域分别”时，诉求是区域拆分；必须优先于总和分支。
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="hist_mw_by_all_regions",
                metrics=["shipment_mw"],
                dimensions=["region_name"],
                filters={"year": year},
                group_by=["region_name"],
                sort=[{"field": "shipment_mw", "direction": "desc"}],
            )

        if year in {2023, 2024, 2025} and region and self._is_mw_question(compact):
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_mw_summary",
                metrics=["shipment_mw"],
                dimensions=[],
                filters={"year": year, "months": months, "region_name": region, "origin_place": origin_place},
            )

        if year in {2023, 2024, 2025} and self._is_mw_question(compact) and not region and not customer_name:
            # 历史年度总运量题只要给出年份和 MW/运量口径即可直接统计全年总发运量；
            # 不应强制用户再补充月份或区域，否则“2023年一年总共的运量是多少MW”会被误判为澄清。
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_mw_summary",
                metrics=["shipment_mw"],
                dimensions=[],
                filters={"year": year, "months": months or None},
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
        compact = re.sub(r"\s+", "", question.strip())
        if candidate_query_key == "composite_decomposed":
            return self._build_composite_plan_from_llm_result(compact=compact, llm_result=llm_result)
        if candidate_query_key not in self.ASSIST_SUPPORTED_QUERY_KEYS:
            return None

        year = self._resolve_assist_year(compact, llm_result)
        months = self._resolve_assist_months(compact, llm_result)
        region = self._resolve_assist_region(compact, llm_result)
        province = self._resolve_assist_province(compact, llm_result)
        origin_place = self._resolve_assist_origin_place(compact, llm_result)
        customer_name = self._resolve_assist_customer_name(compact, llm_result)
        carrier_name = self._resolve_assist_carrier_name(compact, llm_result)
        vehicle_type = self._resolve_assist_vehicle_type(compact, llm_result)
        special_scope = self._resolve_assist_special_scope(compact, llm_result)

        city_total_fee_rank_limit = self._extract_city_total_fee_rank_limit(compact)
        if candidate_query_key == "hist_total_fee_city_rank" and year and province and city_total_fee_rank_limit:
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key=candidate_query_key,
                metrics=["total_fee"],
                dimensions=["city"],
                filters={"year": year, "province": province},
                group_by=["city"],
                sort=[{"field": "total_fee", "direction": "desc"}],
                limit=city_total_fee_rank_limit,
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
            signedfor_top_n = self._extract_top_n(compact) or 10
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key=candidate_query_key,
                metrics=["signedfor_rate"],
                dimensions=["carrier"],
                filters={"year": year, "top_n": signedfor_top_n},
                group_by=["carrier"],
                limit=signedfor_top_n,
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

    def _build_composite_plan_from_llm_result(
        self,
        *,
        compact: str,
        llm_result: LogisticsLlmUnderstandingResult,
    ) -> LogisticsDataQaPlan | None:
        """根据 LLM 拆分结果回构可执行的复合查询计划。

        参数：
            compact: 已去除空白的用户问题。
            llm_result: Guardrail 放行的 LLM 结构化理解结果。
        返回值：
            可执行的 composite_decomposed 查询计划；无法安全拆分时返回 None。
        业务说明：
            LLM 负责判断顶层并列子问题和给出子计划候选；本方法只做白名单、
            字段能力、年份来源和回指安全校验，不能再按关键词自行决定拆分。
        """

        if "吨" in compact and any(keyword in compact for keyword in ("发运量", "运量", "发货量")):
            return None

        decomposition = llm_result.filters if isinstance(llm_result.filters, dict) else {}
        sub_plan_payloads = decomposition.get("sub_plans")
        if not isinstance(sub_plan_payloads, list) or len(sub_plan_payloads) != 2:
            # LLM 只能给出当前已审计的两个顶层独立子问；额外/重复子问一律拒绝，
            # 避免静默丢弃用户意图造成漏答。
            return None
        if decomposition.get("decomposition_strategy") not in {"top_level_conjunction", "llm_top_level_conjunction"}:
            return None
        sub_query_keys = [payload.get("query_key") for payload in sub_plan_payloads if isinstance(payload, dict)]
        required_query_keys = {"hist_high_fee_addresses_by_customer", "sys_mw_by_procurement_type"}
        if set(sub_query_keys) != required_query_keys or len(sub_query_keys) != len(required_query_keys):
            return None

        high_fee_payload = self._find_llm_sub_plan_payload(
            sub_plan_payloads,
            query_key="hist_high_fee_addresses_by_customer",
        )
        procurement_payload = self._find_llm_sub_plan_payload(
            sub_plan_payloads,
            query_key="sys_mw_by_procurement_type",
        )
        if high_fee_payload is None or procurement_payload is None:
            return None

        high_fee_clause = self._extract_llm_source_clause(high_fee_payload)
        procurement_clause = self._extract_llm_source_clause(procurement_payload)
        if not high_fee_clause or not procurement_clause:
            return None
        if high_fee_clause not in compact or procurement_clause not in compact:
            # 每个 LLM 子句都必须可回溯到用户原文，防止幻觉子句补齐关键槽位。
            return None
        if not self._llm_source_clauses_cover_original_question(compact, [high_fee_clause, procurement_clause]):
            # LLM 漏报第三个顶层诉求时不能静默漏答；只能覆盖寒暄、标点和连接词。
            return None
        if not self._is_high_fee_address_clause(high_fee_clause):
            return None
        if self._high_fee_clause_contains_procurement_ask(high_fee_clause):
            # 高运费地址子句不能同时吞入采购方式发运量诉求，否则说明 LLM source_clause 过宽。
            return None
        if self._high_fee_clause_has_unsupported_qualifier(high_fee_clause):
            # 当前历史高运费地址子查询不支持区域、月份、承运商等额外限定，不能静默忽略。
            return None
        if not self._is_procurement_mw_clause(procurement_clause):
            return None
        high_fee_filters = high_fee_payload.get("filters") if isinstance(high_fee_payload.get("filters"), dict) else {}
        procurement_filters = procurement_payload.get("filters") if isinstance(procurement_payload.get("filters"), dict) else {}
        if self._filters_have_nonempty_unsupported_keys(
            high_fee_filters,
            allowed_filter_keys={"year", "customer_name", "threshold_fee"},
        ):
            # 高运费地址子查询只支持年、客户、金额阈值；LLM 额外 filters 不能静默丢弃。
            return None
        if self._procurement_clause_has_unsupported_filter(procurement_clause, procurement_filters):
            # 当前 sys_mw_by_procurement_type 仅支持全局采购方式 MW，不支持客户/区域/承运商等下推限定。
            return None
        if self._is_historical_procurement_split_request(compact, high_fee_clause, procurement_clause):
            return None

        source_high_fee_year = self._extract_year(high_fee_clause)
        llm_high_fee_year = self._coerce_int(high_fee_filters.get("year"))
        if source_high_fee_year not in {2023, 2024, 2025}:
            return None
        if llm_high_fee_year is not None and llm_high_fee_year != source_high_fee_year:
            return None
        high_fee_year = source_high_fee_year

        source_customer_name = self._extract_high_fee_customer_name(high_fee_clause) or self._extract_customer_name(high_fee_clause)
        llm_customer_name = str(high_fee_filters.get("customer_name") or "").strip()
        if not source_customer_name or len(source_customer_name) <= 1:
            return None
        if llm_customer_name and llm_customer_name != source_customer_name:
            return None
        customer_name = source_customer_name
        if self._procurement_clause_has_unsupported_filter(
            procurement_clause,
            procurement_filters,
            known_customer_name=customer_name,
        ):
            # 采购方式子句若隐式复用历史客户名，也属于当前全局 query_key 不支持的限定。
            return None

        source_threshold_fee = self._extract_fee_threshold_yuan(high_fee_clause)
        llm_threshold_fee = self._coerce_int(high_fee_filters.get("threshold_fee"))
        if not source_threshold_fee:
            return None
        if llm_threshold_fee is not None and llm_threshold_fee != source_threshold_fee:
            return None
        threshold_fee = source_threshold_fee

        source_procurement_year = self._extract_year(procurement_clause)
        llm_procurement_year = self._coerce_int(procurement_filters.get("year"))
        if source_procurement_year in {2023, 2024, 2025}:
            return None
        if llm_procurement_year is not None and llm_procurement_year != 2026:
            return None
        if source_procurement_year is not None and source_procurement_year != 2026:
            return None
        procurement_year = 2026

        high_fee_plan = LogisticsDataQaPlan(
            intent="detail_list",
            query_key="hist_high_fee_addresses_by_customer",
            metrics=["total_fee", "shipment_mw"],
            dimensions=["address"],
            filters={"year": high_fee_year, "customer_name": customer_name, "threshold_fee": threshold_fee},
            group_by=["address"],
            sort=[{"field": "total_fee", "direction": "desc"}],
        )
        procurement_plan = LogisticsDataQaPlan(
            intent="aggregate",
            query_key="sys_mw_by_procurement_type",
            metrics=["shipment_mw"],
            dimensions=["procurement_type"],
            filters={"year": procurement_year, "default_system_year": procurement_year == 2026 and self._extract_year(procurement_clause) is None},
            group_by=["procurement_type"],
            sort=[{"field": "shipment_mw", "direction": "desc"}],
        )
        return LogisticsDataQaPlan(
            intent="composite",
            query_key="composite_decomposed",
            metrics=["total_fee", "shipment_mw"],
            dimensions=["section"],
            filters={
                "decomposition_strategy": "top_level_conjunction",
                "decomposition_source": "llm_guardrail",
                "llm_confidence": llm_result.confidence,
                "sub_query_keys": ["hist_high_fee_addresses_by_customer", "sys_mw_by_procurement_type"],
                "sub_plans": [
                    {"section_label": "历史高运费收货地址", **high_fee_plan.model_dump(mode="json")},
                    {"section_label": "2026采购方式发运量", **procurement_plan.model_dump(mode="json")},
                ],
            },
        )

    @staticmethod
    def _find_llm_sub_plan_payload(sub_plan_payloads: list[Any], *, query_key: str) -> dict[str, Any] | None:
        """从 LLM 拆分结果中查找指定 query_key 的子计划。

        参数：
            sub_plan_payloads: LLM 返回的子计划候选列表。
            query_key: 需要匹配的受控查询键。
        返回值：
            匹配到的子计划字典；未匹配时返回 None。
        """

        for payload in sub_plan_payloads:
            if isinstance(payload, dict) and payload.get("query_key") == query_key:
                return payload
        return None

    @staticmethod
    def _extract_llm_source_clause(payload: dict[str, Any]) -> str:
        """提取 LLM 子计划对应的原始子句。

        参数：
            payload: 单个 LLM 子计划候选。
        返回值：
            去空白后的原始子句；如果没有可审计子句则返回空字符串。
        """

        source_clause = payload.get("source_clause") or payload.get("clause") or payload.get("question")
        return re.sub(r"\s+", "", str(source_clause or "").strip())

    @staticmethod
    def _llm_source_clauses_cover_original_question(compact: str, source_clauses: list[str]) -> bool:
        """校验 LLM 子句是否以互不重叠的原文片段覆盖全部实质诉求。

        参数：
            compact: 去空白后的原始问题。
            source_clauses: LLM 返回且已确认出现在原文中的子句。
        返回值：
            若所有 source_clause 都能定位为非重叠 span，且移除后只剩寒暄、标点、连接词，返回 True。
        业务逻辑：LLM 可以主导拆分，但不能用整句/重叠片段掩盖漏报子问。
        """

        if not compact or len(set(source_clauses)) != len(source_clauses):
            return False
        for clause in source_clauses:
            if not clause or clause == compact:
                return False
        for index, clause in enumerate(source_clauses):
            for other_index, other_clause in enumerate(source_clauses):
                if index != other_index and other_clause in clause:
                    return False

        spans = LogisticsDataQaPlanner._locate_non_overlapping_source_spans(compact, source_clauses)
        if spans is None:
            return False
        covered = [False] * len(compact)
        for start, end in spans:
            for position in range(start, end):
                if covered[position]:
                    return False
                covered[position] = True
        residue = "".join(char for position, char in enumerate(compact) if not covered[position])
        residue = re.sub(r"[\s，,；;。.!！?？：:、]", "", residue)
        residue = re.sub(
            r"(?:请|帮我|帮忙|麻烦|统计一下|统计|查询|查一下|看一下|列出|并且|并|同时|另外|再|以及|和|把|将|分别|一下|的)",
            "",
            residue,
        )
        return residue == ""

    @staticmethod
    def _locate_non_overlapping_source_spans(compact: str, source_clauses: list[str]) -> list[tuple[int, int]] | None:
        """为 LLM source_clause 寻找互不重叠的原文区间。

        参数：
            compact: 去空白后的原始问题。
            source_clauses: LLM 子句列表。
        返回值：
            成功时返回 `(start, end)` 区间列表；无法找到非重叠定位时返回 None。
        """

        occurrences: list[list[tuple[int, int]]] = []
        for clause in source_clauses:
            clause_occurrences = [(match.start(), match.end()) for match in re.finditer(re.escape(clause), compact)]
            if not clause_occurrences:
                return None
            occurrences.append(clause_occurrences)

        def backtrack(index: int, selected: list[tuple[int, int]]) -> list[tuple[int, int]] | None:
            """递归选择互不重叠的 source_clause 区间。"""

            if index >= len(occurrences):
                return selected
            for span in occurrences[index]:
                if all(span[1] <= chosen[0] or span[0] >= chosen[1] for chosen in selected):
                    resolved = backtrack(index + 1, [*selected, span])
                    if resolved is not None:
                        return resolved
            return None

        return backtrack(0, [])

    @staticmethod
    def _high_fee_clause_contains_procurement_ask(clause: str) -> bool:
        """判断高运费地址子句是否误吞了采购方式发运量诉求。"""

        return any(keyword in clause for keyword in ("询比价", "招标", "采购方式")) and any(
            keyword in clause for keyword in ("发运量", "运量", "发货量")
        )

    @staticmethod
    def _high_fee_clause_has_unsupported_qualifier(clause: str) -> bool:
        """判断历史高运费地址子句是否包含当前查询无法下推的限定。"""

        if re.search(r"(?:\d{1,2}|[一二三四五六七八九十]{1,3})月", clause):
            return True
        unsupported_keywords = (
            "区域",
            "地区",
            "华东",
            "华南",
            "华北",
            "华中",
            "西南",
            "西北",
            "东北",
            "基地",
            "园区",
            "工厂",
            "起运",
            "承运商",
            "物流公司",
            "物流供应商",
        )
        return any(keyword in clause for keyword in unsupported_keywords)

    @staticmethod
    def _filters_have_nonempty_unsupported_keys(filters: dict[str, Any], *, allowed_filter_keys: set[str]) -> bool:
        """判断 LLM filters 是否包含当前子查询无法执行的非空键。

        参数：
            filters: LLM 子计划 filters。
            allowed_filter_keys: 当前确定性子查询真正支持的 filter key。
        返回值：
            发现非空且不在白名单内的 key 时返回 True。
        """

        for key, value in filters.items():
            if key in allowed_filter_keys:
                continue
            if value is None or value == "" or value == [] or value == {}:
                continue
            return True
        return False

    @staticmethod
    def _procurement_clause_has_unsupported_filter(
        clause: str,
        filters: dict[str, Any],
        *,
        known_customer_name: str | None = None,
    ) -> bool:
        """判断采购方式全局统计子句是否携带当前无法下推的额外限定。

        参数：
            clause: LLM 识别出的采购方式发运量原文子句。
            filters: LLM 给出的采购方式子计划 filters。
            known_customer_name: 已从同一原问题其它子句确定的客户名，用于识别无“客户”后缀的隐式限定。
        返回值：
            若出现客户、区域、承运商、地址、月份等全局统计不支持的限定，返回 True。
        """

        if LogisticsDataQaPlanner._filters_have_nonempty_unsupported_keys(
            filters,
            allowed_filter_keys={"year", "default_system_year"},
        ):
            return True
        if known_customer_name and known_customer_name in clause:
            return True
        if LogisticsDataQaPlanner._procurement_clause_has_unsupported_business_residue(clause):
            return True
        if LogisticsDataQaPlanner._procurement_clause_has_leading_unsupported_qualifier(clause):
            return True
        if re.search(r"(?:\d{1,2}|[一二三四五六七八九十]{1,3})月", clause):
            return True
        unsupported_keywords = (
            "客户",
            "区域",
            "地区",
            "华东",
            "华南",
            "华北",
            "华中",
            "西南",
            "西北",
            "东北",
            "省",
            "市",
            "基地",
            "园区",
            "工厂",
            "起运",
            "承运商",
            "物流公司",
            "物流供应商",
            "收货地址",
            "地址",
            "项目地",
            "这些",
            "上述",
            "上面",
            "前述",
            "该批",
        )
        return any(keyword in clause for keyword in unsupported_keywords)

    @staticmethod
    def _procurement_clause_has_unsupported_business_residue(clause: str) -> bool:
        """剥离采购方式子句中的受支持词后，检查是否残留业务限定。

        参数：
            clause: 采购方式发运量原文子句。
        返回值：
            若剥离动作词、年份、采购方式词、发运量/MW 口径词后仍有实体残留，返回 True。
        业务逻辑：覆盖 `询比价和海尔招标` 这类限定出现在第二个采购方式词附近的表达。
        """

        residue = clause
        residue = re.sub(r"(?:20\d{2}|\d{2})年", "", residue)
        residue = re.sub(r"询比价|招标|采购方式", "", residue)
        residue = re.sub(
            r"(?:请|帮我|帮忙|麻烦|统计一下|统计|查询|查一下|看一下|列出|并且|并|同时|另外|再|以及|和|把|将|分别|一下|的|按|以|根据|对应|发运量|运量|发货量|MW|兆瓦)",
            "",
            residue,
        )
        residue = re.sub(r"[\s，,；;。.!！?？：:、]", "", residue)
        return residue != ""

    @staticmethod
    def _procurement_clause_has_leading_unsupported_qualifier(clause: str) -> bool:
        """识别采购方式关键词前方无法下推的隐式限定。

        参数：
            clause: 采购方式发运量原文子句。
        返回值：
            若 `询比价/招标/采购方式` 前仍残留客户、地点、基地等限定文本，返回 True。
        业务逻辑：`创维询比价发运量`、`常熟基地询比价发运量` 这类表达即使 LLM 未给 filters，也不能查全局。
        """

        match = re.search(r"询比价|招标|采购方式", clause)
        if match is None:
            return False
        leading = clause[: match.start()]
        leading = re.sub(r"(?:20\d{2}|\d{2})年", "", leading)
        leading = re.sub(r"(?:\d{1,2}|[一二三四五六七八九十]{1,3})月", "月份", leading)
        leading = re.sub(
            r"(?:请|帮我|帮忙|麻烦|统计一下|统计|查询|查一下|看一下|列出|并且|并|同时|另外|再|以及|和|把|将|分别|一下|的|按|以|根据|发运量|运量|发货量|MW|兆瓦)",
            "",
            leading,
        )
        leading = re.sub(r"[\s，,；;。.!！?？：:、]", "", leading)
        return leading != ""

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        """把 LLM 输出中的整数槽位安全转成 int。

        参数：
            value: LLM 输出的候选值。
        返回值：
            可用整数；转换失败或值为空时返回 None。
        """

        if value in {None, ""}:
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _split_composite_clauses(compact: str) -> list[str]:
        """按顶层并列连接词拆分复合问题子句。"""

        clauses = re.split(r"(?:，|,|；|;|。)?(?:并且|并|同时|另外|再|以及)", compact)
        return [clause for clause in clauses if clause]

    @staticmethod
    def _is_high_fee_address_clause(clause: str) -> bool:
        """判断子句是否是历史高运费收货地址清单。"""

        return (
            any(keyword in clause for keyword in ("收货地址", "项目地"))
            and any(keyword in clause for keyword in ("运费", "运输费用"))
            and "超过" in clause
            and "万" in clause
        )

    def _is_procurement_mw_clause(self, clause: str) -> bool:
        """判断子句是否是采购方式发运量统计。"""

        return any(keyword in clause for keyword in ("询比价", "招标", "采购方式")) and self._is_mw_question(clause)

    @staticmethod
    def _is_historical_procurement_split_request(compact: str, high_fee_clause: str, procurement_clause: str) -> bool:
        """识别仍需拒答的“在历史高运费地址内部按采购方式拆分”问法。"""

        if re.search(r"(?:收货地址|项目地).{0,12}按(?:询比价|招标|采购方式).{0,12}(?:拆分|分别)", compact):
            return True
        if re.search(
            r"(?:这些|上述|该|此|该批|这批|前述|以上|上面|前面)(?:的)?.{0,24}"
            r"(?:收货地址|地址|项目地|项目|结果|清单)?.{0,24}(?:询比价|招标|采购方式)",
            compact,
        ):
            # 即使 LLM 给出的 procurement_clause 省略了“这些地址”等回指，
            # 原始问题中一旦出现回指前序高运费结果集，就必须 fail-closed。
            return True
        if re.search(r"(?:这些|上述|该|此|该批|这批|前述|以上|上面|前面)(?:的)?.{0,20}(?:收货地址|地址|项目地|项目|结果|清单)", procurement_clause):
            # 采购方式子句如果回指“这些/上述/该批/上面的地址或项目地”，业务含义是
            # 在前一个历史高运费结果集内部继续拆分，不能替换成 2026 全局采购方式发运量。
            return True
        if re.search(r"(?:针对|对应|围绕).{0,8}(?:收货地址|地址|项目地|结果|清单)", procurement_clause):
            return True
        if high_fee_clause == procurement_clause:
            return True
        return False

    def _extract_high_fee_customer_name(self, clause: str) -> str | None:
        """从高运费地址子句中提取客户名称。"""

        match = re.search(r"(?:请)?(?:统计一下|统计|查询|查一下|帮我查|列出)?(?:\d{2,4}年)?(?P<name>[\u4e00-\u9fa5A-Za-z0-9（）()·&-]+?)客户", clause)
        if not match:
            return None
        customer_name = self._clean_subject_phrase(match.group("name"))
        customer_name = re.sub(r"^(?:请|帮我)?(?:统计一下|统计|查询|查一下|列出)", "", customer_name)
        return customer_name.strip(" ：:，,。？！?") or None

    @staticmethod
    def _extract_fee_threshold_yuan(clause: str) -> int | None:
        """提取“超过 N 万/元”的金额阈值，统一换算成人民币元。"""

        wan_match = re.search(r"超过(\d+(?:\.\d+)?)万", clause)
        if wan_match:
            return int(float(wan_match.group(1)) * 10000)
        yuan_match = re.search(r"超过(\d+(?:\.\d+)?)元", clause)
        if yuan_match:
            return int(float(yuan_match.group(1)))
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
        carrier_local_city = self._extract_local_carrier_city(compact)
        carrier_scope_city = None if carrier_local_city else self._extract_carrier_scope_city(compact)
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
        ranking_top_n = self._extract_top_n(compact)
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
        special_scope = None
        if "经营计划" in compact:
            special_scope = "planning"
        elif "辅料送样" in compact:
            special_scope = "sample"
        elif "刘娟" in compact:
            special_scope = "liujuan"
        region_list = self._extract_region_list(compact)
        region_breakdown = self._is_all_region_breakdown_request(compact) or (
            len(region_list) >= 2 and any(keyword in compact for keyword in ("分别", "列出", "统计", "按"))
        )
        history_year_range = [item for item in years if item in {2023, 2024, 2025}]

        if (
            len(history_year_range) >= 2
            and carrier_name
            and self._is_mw_question(compact)
            and any(keyword in compact for keyword in ("每年", "按年", "按年份", "各年", "年度", "分别"))
            and not self._is_total_fee_question(compact)
            and not region_breakdown
        ):
            # “23年-25年，某承运商每年发运量”是显式承运商 + 显式年份范围的逐年拆分题；
            # 不能落入单年“各物流公司 KPI”分组，否则会只取首年且丢失承运商过滤条件。
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="hist_mw_by_year",
                metrics=["shipment_mw"],
                dimensions=["biz_year"],
                filters={"years": history_year_range, "carrier_name": carrier_name},
                group_by=["biz_year"],
                sort=[{"field": "biz_year", "direction": "asc"}],
            )

        if year in {2023, 2024, 2025} and region_breakdown and self._is_mw_question(compact):
            # “分区域/各区域”或显式点名多个大区，业务语义都是按区域拆分；
            # 若同时给出由候选源/显式短语解析出的承运商，必须保留下推过滤，不能退化成全承运商总量。
            filters: dict[str, Any] = {"year": year}
            if carrier_name:
                filters["carrier_name"] = carrier_name
            if region_list:
                filters["regions"] = region_list
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="hist_mw_by_all_regions",
                metrics=["shipment_mw"],
                dimensions=["region_name"],
                filters=filters,
                group_by=["region_name"],
                sort=[{"field": "shipment_mw", "direction": "desc"}],
            )

        if (
            year in {2023, 2024, 2025}
            and "平均每车装载托数" in compact
            and origin_place
            and months
        ):
            # 历史台账已落地 pallet_per_vehicle 字段，且题目明确年份、月份和始发地；
            # 默认按非空发运记录平均，避免把可确定计算的问题继续误判为“需补充口径”。
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_avg_pallet_per_vehicle",
                metrics=["avg_pallet_per_vehicle"],
                dimensions=[],
                filters={"year": year, "months": months, "origin_place": origin_place},
            )

        if (
            year in {2023, 2024, 2025}
            and self._is_carrier_kpi_question(compact)
            and not self._is_monthly_fee_compare_question(compact)
            and not ranking_top_n
            and not self._has_extra_breakdown_intent(compact, allowed_dimension="carrier_name")
        ):
            # “物流公司/承运商 + 分别/各”表达的是承运商分组，
            # 需早于年度总运量兜底分支，避免“物流公司发货量分别”被误算成全年总量。
            filters: dict[str, Any] = {
                "year": year,
                "region_name": region,
                "city": carrier_scope_city,
                "view_mode": self._resolve_carrier_kpi_view_mode(compact),
            }
            if carrier_local_city:
                # 本地/当地物流公司按承运商归属城市过滤，和目的城市 city 分开建模。
                filters["carrier_local_city"] = carrier_local_city
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="hist_carrier_kpi_by_year",
                metrics=["shipment_mw", "shipment_share_pct", "total_fee"],
                dimensions=["carrier_name"],
                filters=filters,
                group_by=["carrier_name"],
                sort=[{"field": "shipment_mw", "direction": "desc"}],
            )

        if year == 2026 and "手机号" in compact and "司机姓名" in compact and any(keyword in compact for keyword in ("多个", "多名", "对应多个", "关联多个", "一号多人")):
            # 2026 派车表已有手机号和司机姓名字段，可按手机号分组做确定性一致性检查，
            # 不需要继续泛化追问“对账对象/输出形态”。
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="sys_driver_phone_name_consistency",
                metrics=["driver_name_count", "assign_task_count"],
                dimensions=["driver_phone"],
                filters={"year": 2026, "top_n": 50},
                group_by=["driver_phone"],
                sort=[{"field": "assign_task_count", "direction": "desc"}],
                limit=50,
            )

        if year == 2026 and "身份证号" in compact and "手机号" in compact and any(keyword in compact for keyword in ("多个", "对应多个", "关联多个", "一人多号")):
            # 2026 派车表已有身份证号和手机号字段，可按身份证号分组返回多手机号异常清单。
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="sys_driver_id_phone_consistency",
                metrics=["driver_phone_count", "assign_task_count"],
                dimensions=["driver_id_number"],
                filters={"year": 2026, "top_n": 50},
                group_by=["driver_id_number"],
                sort=[{"field": "assign_task_count", "direction": "desc"}],
                limit=50,
            )

        if year == 2026 and special_scope and self._is_mw_question(compact):
            # 2026 特殊业务范围 + 总发运量已具备确定性过滤条件；未给月份时按系统侧当前累计，
            # 与“2026 年总发运量”口径一致，不再要求用户额外说明 1 月或 1-2 月。
            filters: dict[str, Any] = {
                "year": 2026,
                "months": months or None,
                "special_scope": special_scope,
                "default_ytd_scope": not bool(months),
            }
            if monthly_breakdown:
                filters["monthly_breakdown"] = True
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="sys_mw_and_trip_count",
                metrics=["shipment_mw"],
                dimensions=["biz_month"] if monthly_breakdown else [],
                filters=filters,
            )

        if region and any(keyword in compact for keyword in ("总发运件数", "发运件数", "总件数", "多少件")):
            # “华东区域历史物流一共发运了多少件”这类问法没有显式写“总发运件数”，但业务口径仍是 actual_qty 件数汇总。
            # 未给年份时沿用历史累计口径；给出 2023/2024/2025 时按单年过滤；运输方式明确时透传同义过滤。
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_quantity_by_region",
                metrics=["shipment_count"],
                dimensions=[],
                filters={
                    "year": year if year in {2023, 2024, 2025} else None,
                    "region_name": region,
                    "transport_mode": transport_mode,
                },
            )

        if year in {2023, 2024, 2025} and quarter and self._is_trip_question(compact) and not region:
            # 支持“24年一季度物流发运车辆数/车次数”这类全局季度车次问题：季度转换成月份列表，复用历史汇总查询。
            quarter_months = {"Q1": [1, 2, 3], "Q2": [4, 5, 6], "Q3": [7, 8, 9], "Q4": [10, 11, 12]}[quarter]
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_total_fee_summary",
                metrics=["shipment_trip_count"],
                dimensions=[],
                filters={"year": year, "months": quarter_months, "quarter": quarter},
            )

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

        if (
            len(years) > 1
            and all(item in {2023, 2024, 2025} for item in years)
            and monthly_breakdown
            and self._is_monthly_fee_compare_question(compact)
            and not region
            and not province
        ):
            # 跨年度全局月度总费用必须优先于“历史承运商简称题族”判断，
            # 避免“2023–2025年各月运费”中的年份范围前缀被误抽成承运商。
            return LogisticsDataQaPlan(
                intent="compare",
                query_key="hist_monthly_total_fee_by_year",
                metrics=["total_fee"],
                dimensions=["biz_month"],
                filters={"years": years},
                group_by=["biz_month"],
                sort=[{"field": "biz_month", "direction": "asc"}],
            )

        # 历史承运商简称题族：如“2023年晶茂物流全年总发运量/总运输费用/单瓦运输成本/承运车次”。
        # 这里只处理已在历史台账中可校验的承运商别名，避免把任意“物流”字样误当承运商。
        if (
            year in {2023, 2024, 2025}
            and self._is_mw_question(compact)
            and not region
            and not province
            and not customer_name
            and not carrier_name
            and not origin_place
            and not transport_mode
            and not any(keyword in compact for keyword in ("各", "分别", "排名", "前十", "前10", "占比", "表"))
        ):
            # “2023年物流发运合计多少量”这类问法里的“量”按当前稳定 MW 发运量口径处理；
            # 用户已明确年份和全量主体时，不再因没有显式写 MW 而进入澄清。
            return LogisticsDataQaPlan(
                intent="aggregate",
                query_key="hist_mw_summary",
                metrics=["shipment_mw"],
                dimensions=[],
                filters={"year": year, "months": months or None},
            )

        if year in {2023, 2024, 2025} and carrier_name and not origin_place and not customer_name:
            if self._is_mw_question(compact):
                return LogisticsDataQaPlan(
                    intent="aggregate",
                    query_key="hist_mw_summary",
                    metrics=["shipment_mw"],
                    dimensions=[],
                    filters={"year": year, "months": months or None, "carrier_name": carrier_name},
                )
            if self._is_unit_fee_question(compact):
                return LogisticsDataQaPlan(
                    intent="aggregate",
                    query_key="hist_unit_fee_per_watt",
                    metrics=["unit_fee_per_watt"],
                    dimensions=[],
                    filters={"year": year, "months": months or None, "carrier_name": carrier_name},
                )
            if self._is_trip_question(compact):
                return LogisticsDataQaPlan(
                    intent="aggregate",
                    query_key="hist_total_fee_summary",
                    metrics=["shipment_trip_count"],
                    dimensions=[],
                    filters={"year": year, "months": months or None, "carrier_name": carrier_name},
                )
            if self._is_total_fee_question(compact):
                return LogisticsDataQaPlan(
                    intent="aggregate",
                    query_key="hist_total_fee_summary",
                    metrics=["total_fee"],
                    dimensions=[],
                    filters={"year": year, "months": months or None, "carrier_name": carrier_name},
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

        if self._is_supported_remark_keyword_fee_ratio(compact):
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

        status_distribution_question = re.sub(r"[？?。.!！]", "", compact)
        if re.fullmatch(r"2026年各任务状态(?:的)?(?:数量|个数|分布|占比)(?:分别)?是多少", status_distribution_question):
            # 仅放行无额外维度/排名/明细诉求的 2026 主任务表全量 status 分布；
            # 使用整句模板而不是负向关键词列表，避免“各城市/每月/top3”等相邻问题被静默降级。
            return LogisticsDataQaPlan(
                intent="detail_list",
                query_key="sys_task_status_distribution",
                metrics=["task_count", "task_share_pct"],
                dimensions=["status"],
                filters={"year": 2026, "table_scope": "ship_task"},
                group_by=["status"],
            )

        if year == 2026 and "各任务状态" in compact and any(status in compact for status in ("PREASSIGN", "ASSIGNED", "PRESIGNFOR", "SIGNEDFOR")):
            # “各任务状态 + 显式状态码”常伴随筛选、额外维度、排名或明细诉求；
            # 现有确定性 query_key 只支持全量状态分布和单状态精确句式，不能把显式状态条件丢弃后返回全量分布。
            return LogisticsDataQaPlan(
                intent="clarification",
                needs_clarification=True,
                clarification_questions=[
                    "请确认要统计的是全量主任务状态分布，还是只筛选指定状态码。",
                    "如需按省份、城市、月份、排名或明细展开，请先确认对应维度和输出模板。",
                ],
                clarification_missing_slots=["status_scope", "dimension_split", "result_metric"],
                clarification_reason="当前问题包含显式状态码或额外维度诉求，不能用全量状态分布替代。",
                clarification_category="state_breakdown_scope",
                clarification_template="state_breakdown_scope",
            )

        if year == 2026 and "物流任务中状态为" in compact and self.slot_extractor.extract_status(compact):
            present_ship_statuses = [
                status for status in ("PREASSIGN", "ASSIGNED", "PRESIGNFOR", "SIGNEDFOR") if status in compact
            ]
            unsafe_status_extra_scope = len(present_ship_statuses) != 1 or any(
                keyword in compact
                for keyword in (
                    "各省",
                    "各城市",
                    "省份",
                    "城市",
                    "每月",
                    "月度",
                    "分月",
                    "top",
                    "TOP",
                    "排名",
                    "前50",
                    "前五十",
                    "明细",
                )
            )
            if unsafe_status_extra_scope:
                # 单状态查询才有稳定 query_key；多状态、额外维度、排名或明细都会改变输出口径，必须先追问。
                return LogisticsDataQaPlan(
                    intent="clarification",
                    needs_clarification=True,
                    clarification_questions=[
                        "请确认只筛选一个状态，还是要同时比较多个状态。",
                        "如需按省份、城市、月份、排名或明细展开，请先确认输出维度和表范围。",
                    ],
                    clarification_missing_slots=["status_scope", "dimension_split", "result_metric"],
                    clarification_reason="当前状态查询包含多个状态或额外输出维度，不能静默降级为单状态全量分布。",
                    clarification_category="state_breakdown_scope",
                    clarification_template="state_breakdown_scope",
                )
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

        if (
            year == 2026
            and "PREASSIGN" in compact
            and "省" in compact
            and any(keyword in compact for keyword in ("最多", "排名", "排行"))
            and not self._has_reverse_ranking_intent(compact)
            and not self._has_extra_breakdown_intent(compact, allowed_dimension="delivery_province")
            and not self._has_extra_metric_for_single_metric_ranking(compact, allowed_metric="task_count")
        ):
            top_n = ranking_top_n or 10
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="sys_task_status_province_ranking",
                metrics=["task_count"],
                dimensions=["delivery_province"],
                filters={"year": year, "status": "PREASSIGN", "top_n": top_n},
                group_by=["delivery_province"],
                sort=[{"field": "task_count", "direction": "desc"}],
                limit=top_n,
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
                filters={"year": year, "top_n": ranking_top_n or 10},
                sort=[{"field": "detail_count", "direction": "desc"}],
                limit=ranking_top_n or 10,
            )

        if (
            year == 2026
            and "司机" in compact
            and "派车任务量" in compact
            and (ranking_top_n or "最高" in compact)
            and not self._has_reverse_ranking_intent(compact)
            and not self._has_extra_breakdown_intent(compact, allowed_dimension="driver_name")
            and not self._has_extra_metric_for_single_metric_ranking(compact, allowed_metric="assign_task_count")
        ):
            top_n = ranking_top_n or 20
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="sys_driver_task_ranking",
                metrics=["assign_task_count"],
                dimensions=["driver_name"],
                filters={"year": year, "top_n": top_n},
                group_by=["driver_name"],
                sort=[{"field": "assign_task_count", "direction": "desc"}],
                limit=top_n,
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
            price_metric = (
                "unit_price_per_vehicle"
                if any(keyword in compact for keyword in ("报价", "单价", "单价/车"))
                else "total_fee"
            )
            filters: dict[str, Any] = {
                "years": route_years,
                "vehicle_type": vehicle_type,
                "view_mode": route_view_mode,
                "price_metric": price_metric,
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
            and ranking_top_n
            and any(keyword in compact for keyword in ("承运商", "物流公司", "各物流"))
            and year in {2024, 2025, 2026}
            and (year in {2024, 2025} or months)
            and not self._has_reverse_ranking_intent(compact)
            and not self._has_extra_breakdown_intent(compact, allowed_dimension="carrier_name")
            and not self._has_extra_metric_for_single_metric_ranking(compact, allowed_metric=carrier_ranking_metric)
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
                    "top_n": ranking_top_n,
                },
                group_by=["carrier_name"],
                sort=[{"field": carrier_ranking_metric, "direction": "desc"}],
                limit=ranking_top_n,
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

        if (
            year == 2026
            and ranking_top_n
            and "送达城市" in compact
            and "任务量" in compact
            and any(keyword in compact for keyword in ("排名", "排行"))
            and not self._has_reverse_ranking_intent(compact)
            and not self._has_extra_breakdown_intent(compact, allowed_dimension="delivery_city")
            and not self._has_extra_metric_for_single_metric_ranking(compact, allowed_metric="task_count")
        ):
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="sys_task_count_ranking",
                metrics=["task_count"],
                dimensions=["delivery_city"],
                filters={"year": year, "dimension": "delivery_city", "top_n": ranking_top_n},
                group_by=["delivery_city"],
                sort=[{"field": "task_count", "direction": "desc"}],
                limit=ranking_top_n,
            )

        if (
            year == 2026
            and ranking_top_n
            and "project_name维度" in compact
            and "任务量" in compact
            and any(keyword in compact for keyword in ("排名", "排行"))
            and not self._has_reverse_ranking_intent(compact)
            and not self._has_extra_breakdown_intent(compact, allowed_dimension="project_name")
            and not self._has_extra_metric_for_single_metric_ranking(compact, allowed_metric="task_count")
        ):
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="sys_task_count_ranking",
                metrics=["task_count"],
                dimensions=["project_name"],
                filters={"year": year, "dimension": "project_name", "top_n": ranking_top_n},
                group_by=["project_name"],
                sort=[{"field": "task_count", "direction": "desc"}],
                limit=ranking_top_n,
            )

        if year == 2026 and "delivery_distance" in compact and "填充率" in compact:
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="sys_delivery_distance_fill_rate_by_province",
                metrics=["fill_rate"],
                dimensions=["delivery_province"],
                filters={"year": year, "top_n": ranking_top_n or 10},
                group_by=["delivery_province"],
                sort=[{"field": "fill_rate", "direction": "asc"}],
                limit=ranking_top_n or 10,
            )

        if (year == 2026 or "送货单解析成功率" in compact) and "承运商" in compact and "解析成功率" in compact:
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="sys_parse_success_rate_by_carrier",
                metrics=["parse_success_rate"],
                dimensions=["company_name"],
                filters={"year": 2026, "top_n": ranking_top_n or 10},
                group_by=["company_name"],
                limit=ranking_top_n or 10,
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
                filters={"year": year, "top_n": ranking_top_n or 10},
                limit=ranking_top_n or 10,
            )

        if (
            province
            and ranking_top_n
            and "客户" in compact
            and self._is_total_fee_question(compact)
            and self._is_mw_question(compact)
            and not self._has_reverse_ranking_intent(compact)
            and not self._has_extra_breakdown_intent(compact, allowed_dimension="customer_name")
        ):
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="hist_top_customers_fee_and_mw_by_province",
                metrics=["total_fee", "shipment_mw"],
                dimensions=["customer_name"],
                filters={"year": year, "province": province, "top_n": ranking_top_n},
                group_by=["customer_name"],
                sort=[{"field": "total_fee", "direction": "desc"}],
                limit=ranking_top_n,
            )

        if (
            "历史台账" in compact
            and ranking_top_n
            and "客户" in compact
            and self._is_mw_question(compact)
            and not self._is_total_fee_question(compact)
            and not self._has_reverse_ranking_intent(compact)
            and not self._has_extra_breakdown_intent(compact, allowed_dimension="customer_name")
        ):
            return LogisticsDataQaPlan(
                intent="ranking",
                query_key="hist_customer_mw_ranking",
                metrics=["shipment_mw"],
                dimensions=["customer_name"],
                filters={"year": year if year in {2023, 2024, 2025} else None, "top_n": ranking_top_n},
                group_by=["customer_name"],
                sort=[{"field": "shipment_mw", "direction": "desc"}],
                limit=ranking_top_n,
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
                filters={
                    "years": years if len(years) > 1 and all(item in {2023, 2024, 2025} for item in years) else None,
                    "year": year if year in {2023, 2024, 2025} and not len(years) > 1 else None,
                    "province": province,
                },
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

    def _extract_region_list(self, question: str) -> list[str]:
        """提取问句里显式点名的区域列表。

        参数：
            question: 已压缩空白的用户问题。
        返回：
            按问句出现顺序去重后的区域名称列表。
        业务逻辑：
            “华东、华北、华南分别”这类问法不是单一区域过滤，
            而是多个点名区域的拆分列表，需要保留给仓储层做 IN 过滤。
        """

        regions: list[str] = []
        for region_name in self.REGION_NAMES:
            if region_name in question and region_name not in regions:
                regions.append(region_name)
        return sorted(regions, key=lambda item: question.index(item))

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

        if not (("不同车型" in question or "各车型" in question) and "始发" in question):
            return False
        metric_hits = sum(
            1
            for keyword_group in (
                ("发运车次", "车次", "车数"),
                ("发运件数", "总件数", "件数"),
                ("总费用", "总运费", "运输费用"),
                ("平均单车费用", "平均单车运费", "平均单价/车"),
                ("平均每车装载托数", "装载托数"),
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

    def _normalize_carrier_city_candidate(self, candidate: str) -> str | None:
        """归一承运商城市候选词，剔除年份、范围词和本地/当地后缀。

        参数：
            candidate: 正则抽取到的城市候选片段。
        返回：
            归一后的城市名；若候选实际为省份、大区或无效范围词，则返回 None。
        """

        normalized = candidate.replace("市", "").replace("省", "").strip()
        normalized = re.sub(
            r"^(?:\d{2,4}年|年|今年|去年|上半年|下半年|全年|各|不同|发往|发至|发到|送往|到|至)",
            "",
            normalized,
        ).strip()
        normalized = re.sub(r"(?:当地|本地|本市|各|不同|各家|每家|每|全部|所有)$", "", normalized).strip()
        normalized = normalized.rstrip("的")
        if not normalized:
            return None
        if normalized in self.PROVINCE_ALIAS.values() or normalized in self.REGION_NAMES:
            return None
        if normalized.endswith(("区域", "大区", "基地")) or any(region in normalized for region in self.REGION_NAMES):
            return None
        return normalized

    def _extract_local_carrier_city(self, question: str) -> str | None:
        """提取“本地/当地物流公司”所指的承运商归属城市。

        参数：
            question: 已压缩空白的用户问题。
        返回：
            承运商归属城市，例如“苏州”；没有本地承运商语义时返回 None。
        说明：
            1. “苏州的物流公司/苏州本地物流公司”表达物流公司自身属于苏州；
            2. 该槽位不能复用目的城市 city，否则会统计所有发往苏州的外地承运商；
            3. “发往苏州的各物流公司”这类显式目的地问法仍交给 _extract_carrier_scope_city。
        """

        if re.search(
            r"^(?:\d{2,4}年|今年|去年|上半年|下半年|全年)?(?:各|不同|各家|每家|全部|所有)(?:物流公司|物流供应商|物流承运商|承运商|物流)",
            question,
        ):
            # “各物流公司/不同物流公司”是全局承运商分组，不代表某个城市的本地承运商。
            return None
        if not any(keyword in question for keyword in ("当地", "本地", "本市")) and re.search(
            r"(?:发往|发至|发到|送往|到|至)(?!各|不同|各家|每|每家|全部|所有)[\u4e00-\u9fa5]{2,10}?市?的?(?:各|不同|各家|每家|全部|所有)?(?:物流公司|物流供应商|物流承运商|承运商)",
            question,
        ):
            # 明确“发往/到达某城市的物流公司”是目的城市范围，不是本地承运商范围。
            return None
        local_patterns = (
            r"(?<!发往)(?<!发至)(?<!发到)(?<!送往)(?<!到)(?<!至)(?:\d{2,4}年)?(?P<city>(?!年|各|不同|各家|每|每家|全部|所有)[\u4e00-\u9fa5]{2,10}?)(?:市)?(?:当地|本地|本市)的?(?:物流公司|物流供应商|物流承运商|承运商)",
            r"(?<!发往)(?<!发至)(?<!发到)(?<!送往)(?<!到)(?<!至)(?:\d{2,4}年)?(?P<city>(?!年|各|不同|各家|每|每家|全部|所有|发往|发至|发到)[\u4e00-\u9fa5]{2,10}?)(?:市)?的(?:物流公司|物流供应商|物流承运商|承运商)",
        )
        for pattern in local_patterns:
            match = re.search(pattern, question)
            if not match:
                continue
            normalized = self._normalize_carrier_city_candidate(match.group("city"))
            if normalized:
                return normalized
        return None

    def _extract_carrier_scope_city(self, question: str) -> str | None:
        """提取承运商 KPI 问法中的目的城市过滤条件。

        说明：
            1. 该槽位只表达“发往/到达某城市”的目的城市范围；
            2. “苏州的物流公司/苏州本地物流公司”已由 carrier_local_city 表达承运商归属城市；
            3. 若文本命中省份或大区，不强行当作城市，避免把区域题误下推到 city。
        """

        if re.search(
            r"^(?:\d{2,4}年|今年|去年|上半年|下半年|全年)?(?:各|不同|各家|每家|全部|所有)(?:物流公司|物流供应商|物流承运商|承运商|物流)",
            question,
        ):
            # “各物流公司/不同物流公司/各承运商”表达的是全局承运商分组，
            # 不能把“各/不同”等范围词误当作城市过滤条件。
            return None
        city = self._extract_destination_city(question)
        if city:
            return self._normalize_carrier_city_candidate(city)
        destination_patterns = (
            r"(?:发往|发至|发到|送往|到|至)(?P<city>(?!各|不同|各家|每|每家|全部|所有)[\u4e00-\u9fa5]{2,10}?)(?:市)?的?(?:各|不同|各家|每家|全部|所有)?(?:物流公司|物流供应商|物流承运商|承运商)",
        )
        for pattern in destination_patterns:
            match = re.search(pattern, question)
            if not match:
                continue
            normalized = self._normalize_carrier_city_candidate(match.group("city"))
            if normalized:
                return normalized
        return None

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
        customer_name = self.slot_extractor.extract_customer_name(question)
        if not customer_name:
            return None
        # “客户华阳的总发运量”里的“的”是助词，不属于客户实体；
        # 这里只裁剪常见尾部助词，不改变中间包含“的”的真实名称。
        return customer_name.strip().rstrip("的")

    def _extract_sys_total_fee_controlled_field_filters(self, question: str) -> dict[str, str]:
        """提取 2026 系统总费用题的受控字段过滤。

        参数：
            question: 已压缩空白的用户问题。

        返回值：
            可直接写入 plan.filters 的字段过滤条件。当前只放行已经由业务确认的
            expand_dept / entrusted_person，避免把开放词随意下推为字段。
        """

        filters: dict[str, str] = {}
        sorted_aliases = sorted(self.SYS_TOTAL_FEE_FIELD_FILTER_ALIASES.items(), key=lambda item: len(item[0]), reverse=True)
        for alias, (field_name, field_value) in sorted_aliases:
            if alias in question and field_name not in filters:
                # 同一字段命中多个别名时保留最长别名，例如“经营计划部”不能被“经营计划”覆盖。
                filters[field_name] = field_value
        return filters

    def _extract_unknown_sys_total_fee_field_scope_terms(
        self,
        question: str,
        *,
        controlled_field_filters: dict[str, str],
    ) -> list[str]:
        """识别缺少字段口径的 2026 系统用车总费用范围词。

        参数：
            question: 已压缩空白的用户问题。
            controlled_field_filters: 已识别出的受控字段过滤，命中时不再把同一词当未知项。

        返回值：
            需要用户确认字段归属的词列表；为空表示无需触发字段口径澄清。

        业务说明：
            “张三用车总费用”这类问法只给了人名/业务词，没有说明它属于委托人、
            客户、承运商还是其他字段。系统不能猜测字段，也不能套用经营计划等旧
            special_scope，所以这里保守返回澄清。
        """

        if "用车" not in question:
            return []
        metric_positions = [question.find(keyword) for keyword in self.TOTAL_FEE_KEYWORDS if keyword in question]
        if not metric_positions:
            return []
        scope_text = question[: min(position for position in metric_positions if position >= 0)]
        scope_text = re.sub(r"\d{2,4}年", "", scope_text)
        scope_text = re.sub(r"\d{1,2}月份?", "", scope_text)
        scope_text = scope_text.replace("用车", "")
        for alias in self.SYS_TOTAL_FEE_FIELD_FILTER_ALIASES:
            scope_text = scope_text.replace(alias, "")
        for token in ("请问", "帮我", "查一下", "查询", "统计", "一下", "的", "按", "和", "及", "与"):
            scope_text = scope_text.replace(token, "")
        scope_text = scope_text.strip(" ：:，,。？！?")
        if not scope_text:
            return []
        return [scope_text]

    def _extract_company_name(self, question: str) -> str | None:
        """提取 2026 系统口径下的承运商公司名。

        说明：
            1. 当前只服务于“某承运商某月总计运费”这类高价值题族；
            2. 如果问句已经明确走客户口径，则不在这里强行抽成承运商；
            3. 返回值交给仓储层做 LIKE 匹配，兼容简称与全称。
        """
        return self.slot_extractor.extract_company_name(question)

    def _extract_historical_carrier_name(self, question: str) -> str | None:
        """提取历史台账承运商名称。

        参数：
            question: 已压缩空白的用户问题。

        返回：
            可交给历史明细表 logistics_company_name 做模糊匹配的承运商关键词。

        说明：
            承运商属于会随台账变化的业务实体，不能在 planner 中维护“晶茂/英赋嘉”等姓名白名单；
            这里委托业务实体解析器基于仓储候选源和受控显式短语语法解析，泛词会被拦截。
        """

        return self.business_entity_resolver.resolve_historical_carrier_name(question)

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
        return self._extract_historical_carrier_name(question)

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

    def _extract_top_n(self, question: str) -> int | None:
        """抽取排名类问题中的正整数 TopN。

        参数：
            question: 已压缩空白的用户问题。
        返回值：
            命中“前5/前五/前十一/Top20”等正整数表达时返回 N，否则返回 None。
        业务逻辑：
            该函数只负责解析数量，不单独决定 query_key；调用方必须继续校验年份、维度、
            指标和排序方向，避免把复杂排名问题误收进简单 TopN 分支。
        """

        normalized = question.rstrip("?？。.!！")
        top_match = re.search(
            r"(?i)top(?P<limit>\d+)(?:名|位|条|个(?!月|工作日|自然日|日|年))?"
            r"(?=$|[?？。.!！,，；;、]|和|与|及|客户|承运商|物流公司|城市|项目|省|状态|司机|结果)",
            normalized,
        )
        if top_match:
            return self._parse_positive_integer(top_match.group("limit"))

        front_match = re.search(
            r"前(?P<limit>\d+|[一二两三四五六七八九十]+)"
            # “前五集中在哪里/前五主要集中在哪”也是业务常见 TopN 问法，不能因为“集中”不是维度词而退回默认 10。
            r"(?:名|位|条|个(?!月|工作日|自然日|日|年)|(?=$|[?？。.!！,，；;、]|和|与|及|客户|承运商|物流公司|城市|项目|省|状态|司机|结果|集中|在哪|哪里))",
            normalized,
        )
        if not front_match:
            front_match = re.search(
                r"前(?P<limit>\d+|[一二两三四五六七八九十]+)的(?=客户|承运商|物流公司|城市|项目|省|状态|司机|结果)",
                normalized,
            )
        if not front_match:
            return None
        return self._parse_positive_integer(front_match.group("limit"))

    @staticmethod
    def _parse_positive_integer(raw_value: str) -> int | None:
        """把阿拉伯数字或常见中文数字转换为正整数。

        参数：
            raw_value: 待解析的数字文本，例如 10、五、十一、二十。
        返回值：
            可解析且大于 0 时返回整数，否则返回 None。
        业务逻辑：
            当前 TopN 只需要稳定覆盖几十以内的业务问法；不解析复杂大写金额或小数，
            防止非排名数量被误当成 limit。
        """

        value = raw_value.strip()
        if not value:
            return None
        if value.isdigit():
            parsed = int(value)
            return parsed if parsed > 0 else None

        digit_map = {
            "一": 1,
            "二": 2,
            "两": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
        }
        if value in digit_map:
            return digit_map[value]
        if value == "十":
            return 10
        if "十" not in value or value.count("十") != 1:
            return None

        tens_text, ones_text = value.split("十", 1)
        tens = 1 if tens_text == "" else digit_map.get(tens_text)
        ones = 0 if ones_text == "" else digit_map.get(ones_text)
        if tens is None or ones is None:
            return None
        parsed = tens * 10 + ones
        return parsed if parsed > 0 else None

    @staticmethod
    def _has_reverse_ranking_intent(question: str) -> bool:
        """判断问题是否要求反向排序或低值排名。"""

        return any(
            keyword in question
            for keyword in (
                "最低",
                "最少",
                "倒数",
                "升序",
                "从低到高",
                "由低到高",
                "后十",
                "后10",
                "bottom",
                "Bottom",
                "BOTTOM",
            )
        )

    @staticmethod
    def _is_all_region_breakdown_request(question: str) -> bool:
        """判断用户是否要求按所有区域拆分返回。

        参数：
            question: 已压缩空白的用户问题。
        返回值：
            命中“各区域/分区域/每个区域/区域分别/按区域”等通用区域拆分表达时返回 True。
        业务逻辑：
            “华东区域”等具体区域是筛选条件，不是拆分诉求；这里只识别全区域分组表达，
            避免把业务员要求的分区域结果误查成一条全局总和。
        """

        return any(
            keyword in question
            for keyword in (
                "各区域",
                "各大区",
                "分区域",
                "分大区",
                "每个区域",
                "每个大区",
                "各个区域",
                "各个大区",
                "区域分别",
                "大区分别",
                "按区域",
                "按大区",
                "区域拆分",
                "大区拆分",
                "区域分组",
                "大区分组",
            )
        )

    @staticmethod
    def _has_extra_breakdown_intent(question: str, *, allowed_dimension: str | None = None) -> bool:
        """判断 TopN 问题是否追加了当前 query_key 不支持的拆分维度。

        参数：
            question: 已压缩空白的问题。
            allowed_dimension: 当前 query_key 已经承载的分组维度；该维度本身不算额外拆分。
        返回值：
            用户追加“按区域/按月份/按城市”等非当前维度拆分诉求时返回 True。
        业务逻辑：
            TopN 泛化只允许改变返回条数，不能静默丢弃新的拆分维度；但像
            “按省任务量排名”本身就是 delivery_province 维度，不能被误拦截。
        """

        dimension_phrases = {
            "region_name": ("区域", "大区"),
            "carrier_name": ("承运商", "物流公司", "物流供应商"),
            "company_name": ("承运商", "物流公司", "物流供应商"),
            "delivery_city": ("城市", "送达城市"),
            "city": ("城市", "送达城市"),
            "delivery_province": ("省份", "省", "送达省份"),
            "customer_name": ("客户",),
            "project_name": ("项目", "project_name"),
            "driver_name": ("司机", "驾驶员"),
            "biz_month": ("月份", "月度", "按月"),
        }
        allowed_phrases = set(dimension_phrases.get(allowed_dimension or "", ()))

        for dimension_key, phrases in dimension_phrases.items():
            if dimension_key == allowed_dimension:
                continue
            for phrase in phrases:
                if phrase in allowed_phrases:
                    continue
                patterns = (
                    f"按{phrase}",
                    f"按{phrase}分",
                    f"按{phrase}拆分",
                    f"{phrase}拆分",
                    f"{phrase}分组",
                    f"分{phrase}",
                    f"各{phrase}",
                    f"{phrase}维度",
                )
                if any(pattern in question for pattern in patterns):
                    return True

        if any(keyword in question for keyword in ("拆分", "分组")):
            # 如果出现泛化拆分词但没有命中允许维度，保守澄清，避免丢条件。
            return not any(phrase in question for phrase in allowed_phrases)
        return False

    def _has_extra_metric_for_single_metric_ranking(self, question: str, *, allowed_metric: str) -> bool:
        """判断单指标排名问题是否混入了其它指标。

        参数：
            question: 已压缩空白的用户问题。
            allowed_metric: 当前 query_key 支持的唯一排序指标。
        返回值：
            问句中出现当前单指标 query_key 之外的费用、发运量、车次或单瓦成本诉求时返回 True。
        业务逻辑：
            TopN 泛化只改变 limit，不扩大指标集合；例如“总发运量和总费用排名”不能被
            “客户总发运量排名”或“承运商总费用排名”静默吞掉。
        """

        asks_total_fee = self._is_total_fee_question(question)
        asks_mw = self._is_mw_question(question)
        asks_trip = self._is_trip_question(question)
        asks_unit_fee = self._is_unit_fee_question(question)
        asks_task_count = any(keyword in question for keyword in ("任务量", "任务数", "订单数", "主任务数", "派车任务量"))

        if allowed_metric == "total_fee":
            return asks_mw or asks_trip or asks_unit_fee or asks_task_count
        if allowed_metric in {"shipment_mw", "task_count", "assign_task_count"}:
            return asks_total_fee or asks_trip or asks_unit_fee or (asks_task_count and allowed_metric == "shipment_mw")
        if allowed_metric == "unit_fee_per_watt":
            return asks_total_fee or asks_mw or asks_trip or asks_task_count
        return False

    def _extract_city_total_fee_rank_limit(self, question: str) -> int | None:
        """抽取省份内城市总费用排名问题的 TopN 限制。

        参数：
            question: 已压缩空白的用户问题。
        返回值：
            命中“城市 + 总费用 + 排名 + 前N”窄口径时返回 N，否则返回 None。
        业务逻辑：
            该能力只服务“YYYY年<省份>各城市总费用排名前N”类明确问题；年份和省份由调用方校验，
            本函数不放宽到缺省时间、缺省地域或非城市维度的模糊排名问题。
        """

        extra_scope_keywords = (
            "承运商",
            "物流公司",
            "发运量",
            "运量",
            "车次",
            "车型",
            "客户",
            "项目",
            "拆分",
            "分组",
            "最低",
            "最少",
            "倒数",
            "从低到高",
            "升序",
        )
        if any(keyword in question for keyword in extra_scope_keywords) or self._has_extra_breakdown_intent(question, allowed_dimension="city"):
            # 额外维度、额外指标或反向排序会改变执行口径，不能被单纯“各城市总费用 TopN”吞掉。
            return None

        normalized = question.rstrip("?？。.!！")
        rank_pattern = re.compile(
            r"(?:各)?城市"
            r"(?:总费用|总运费)"
            r"(?:排名|排行)"
            r"(?:前(?P<limit>\d+|[一二两三四五六七八九十两]+)|(?P<top>top\d+))"
            r"(?:名|个|位)?$",
            re.IGNORECASE,
        )
        match = rank_pattern.search(normalized)
        if not match:
            # 只接受“城市总费用排名前N”这一窄结构；如果用户追加了承运商拆分、发运量、最低排名等口径，
            # 这里故意不命中，让后续澄清/不支持边界接管，避免把复杂问题错答成单纯城市 TopN。
            return None

        raw_limit = match.group("limit") or (match.group("top") or "").lower().removeprefix("top")
        return self._parse_positive_integer(raw_limit)

    @staticmethod
    def _normalize_remark_question(question: str) -> str:
        """规整备注关键词问题，便于做严格整句白名单匹配。

        参数：
            question: 用户问题原文或已压缩文本。
        返回值：
            去掉空白、引号和句末问号后的问题文本。
        业务逻辑：只做格式归一，不改写业务词，避免把未审计别名扩展为已支持口径。
        """

        normalized = re.sub(r"\s+", "", question)
        normalized = re.sub(r"[“”‘’\"']", "", normalized)
        return normalized.rstrip("?？。.")

    @staticmethod
    def _has_remark_keyword_intent(question: str) -> bool:
        """判断问题是否表达“备注包含某关键词”的意图。

        参数：
            question: 已压缩空白的问题。
        返回值：
            命中“备注包含”或“备注中包含”时返回 True。
        业务逻辑：remark 字段是专门口径，未白名单支持时必须 fail closed，不能落入通用总费用/承运商链路。
        """

        normalized = LogisticsDataQaPlanner._normalize_remark_question(question)
        # 备注字段可能被业务表述为“备注/备注字段/备注内容/备注项/备注栏”，
        # “是否包含/是否含有”等问法同样是 remark 字段条件；未命中白名单时必须 fail closed。
        return bool(re.search(r"备注(?:字段|内容|项|栏|中|里)?[^\w]*(?:是否)?[^\w]*(?:包含|含有|含)", normalized))

    @staticmethod
    def _extract_keywords_from_remark_phrase(phrase: str, allowed_keywords: tuple[str, ...]) -> list[str]:
        """从已定位的备注关键词短语中抽取受控关键词。

        参数：
            phrase: 严格正则已捕获的关键词短语。
            allowed_keywords: 当前 query_key 允许的关键词集合。
        返回值：
            短语只由允许关键词和连接词构成时，返回命中的关键词；否则返回空列表。
        业务逻辑：必须校验严格 fullmatch 捕获的 phrase，不能重新从整句搜索第一个分隔符，否则会吞掉后续未知条件。
        """

        keyword_pattern = "|".join(re.escape(keyword) for keyword in allowed_keywords)
        connector_pattern = r"(?:或|和|、|,|，|/|及|与)"
        if not re.fullmatch(rf"(?:{keyword_pattern})(?:{connector_pattern}(?:{keyword_pattern}))*", phrase):
            return []
        tokens = re.findall(keyword_pattern, phrase)
        if len(tokens) != len(set(tokens)):
            return []
        return [keyword for keyword in allowed_keywords if keyword in tokens]

    def _extract_valid_remark_keywords(self, question: str, allowed_keywords: tuple[str, ...]) -> list[str]:
        """从备注关键词短语中抽取受控关键词。

        参数：
            question: 用户问题。
            allowed_keywords: 当前 query_key 允许的关键词集合。
        返回值：
            按 allowed_keywords 顺序返回问题中出现的关键词；短语包含未知词时返回空列表。
        业务逻辑：不能只靠全文包含关键词，否则“倒运和装卸”会被错误窄化为“倒运”。
        """

        normalized = self._normalize_remark_question(question)
        match = re.search(r"备注(?:中|里)?[：:,，]?包含(?P<phrase>.+?)(?:的记录数量|的记录数|的记录[，,]?其总费用占|的记录总费用占|的总费用占|其总费用占|总费用占)", normalized)
        if not match:
            return []
        phrase = match.group("phrase")
        return self._extract_keywords_from_remark_phrase(phrase, allowed_keywords)

    def _is_supported_remark_keyword_amount_summary(self, question: str, year: int | None, remark_keywords: list[str]) -> bool:
        """判断是否为已审计的年度备注关键词记录数/费用金额汇总。

        参数：
            question: 已压缩空白的问题。
            year: 抽取出的年份。
            remark_keywords: 已校验的备注关键词。
        返回值：
            仅当问题完整匹配单年、受控关键词、记录数量和费用金额口径时返回 True。
        业务逻辑：区域、明细、占比、总运费别名、未知关键词都会改变统计口径，必须澄清。
        """

        normalized = self._normalize_remark_question(question)
        match = re.fullmatch(
            r"(?:请统计|统计)?(?P<year>2023|2024|2025)年备注(?:中|里)?[：:,，]?包含(?P<phrase>.+?)的记录(?:数量|数)和(?:费用金额|金额|总费用|费用)(?:是多少)?",
            normalized,
        )
        exact_keywords = self._extract_keywords_from_remark_phrase(match.group("phrase"), self.REMARK_SUPPORTED_KEYWORDS) if match else []
        return bool(
            match
            and year in {2023, 2024, 2025}
            and int(match.group("year")) == year
            and exact_keywords
            and exact_keywords == remark_keywords
        )

    def _is_supported_remark_keyword_fee_ratio(self, question: str) -> bool:
        """判断是否为已审计的备注倒运/中转费用占历史物流总费用比例。

        参数：
            question: 用户问题。
        返回值：
            仅当问题不带显式时间、关键词只包含倒运/中转、分母为历史物流总费用且使用总费用口径时返回 True。
        业务逻辑：总运费、历史总费用、百分比、区域/车型/明细等别名或额外条件暂未审计，必须澄清。
        """

        normalized = self._normalize_remark_question(question)
        match = re.fullmatch(
            r"(?:请问|请统计|统计)?备注(?:中|里)?[：:,，]?包含(?P<phrase>.+?)(?:的记录[，,]?其|的记录|其)?的?总费用占历史物流总费用(?:的)?(?:比例|占比)(?:是多少)?",
            normalized,
        )
        remark_keywords = self._extract_keywords_from_remark_phrase(match.group("phrase"), self.REMARK_FEE_RATIO_KEYWORDS) if match else []
        return (
            bool(match)
            and not self._extract_years(question)
            and remark_keywords == list(self.REMARK_FEE_RATIO_KEYWORDS)
        )

    def _is_remark_keyword_question_needing_clarification(self, question: str) -> bool:
        """判断未落入白名单的备注关键词问题是否需要澄清保护。

        参数：
            question: 已压缩空白的用户问题。
        返回值：
            只要表达“备注包含”意图且未被白名单放行，就返回 True。
        业务逻辑：remark 字段查询不能被当作承运商名、区域名或普通总费用问题继续兜底，否则会产生误答。
        """

        return self._has_remark_keyword_intent(question)

    def _is_complex_report_question(self, question: str) -> bool:
        """判断是否属于当前应追问报表模板的复杂报表题。

        参数：
            question: 已压缩空白的用户问题。

        返回：
            命中宽表、透视表、同比变化、多指标经营总表等报表模板诉求时返回 True。

        说明：
            该判断不扩 query_key，只保护现有稳定链路，避免把单指标结果包装成完整报表。
        """

        if self._is_supported_remark_keyword_fee_ratio(question):
            # 备注“倒运/中转”费用占历史物流总费用比例已有专用确定性 query_key；
            # 不能被宽表/明细类备注关键词保护规则误判为复杂报表。
            return False
        if self._is_remark_keyword_question_needing_clarification(question):
            # 未落入严格白名单的备注关键词题必须先追问，避免掉入通用总费用/承运商抽取链路误答。
            return True

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
            and any(keyword in question for keyword in ("按月份", "月份汇总", "月度汇总"))
            and any(keyword in question for keyword in ("区分2023", "三个年度", "分别展示2023", "2023、2024、2025"))
        ):
            # 多年逐月 + 发运量 + 总费用需要 year-month 粒度和多指标表格模板；
            # 当前单指标月度链路不能用 12 个月汇总冒充 36 行年度拆分表。
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
            and "倒运" in question
            and "中转" in question
            and any(keyword in question for keyword in ("总费用占", "总运费占", "比例", "占比"))
            and not any(keyword in question for keyword in ("按年份拆分", "涉及区域", "前50条明细", "明细", "换车", "压车", "放空"))
        ):
            # 备注“倒运/中转”费用占历史总费用比例已有专用确定性 query_key；
            # 不能被宽表/明细类备注关键词保护规则误判为复杂报表。
            return False
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
        return any(keyword in question for keyword in ("单瓦价", "单W运输成本", "元瓦", "元/瓦", "元每瓦", "单瓦运输成本", "单瓦成本"))

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
                "1-12月",
                "1到12月",
                "1至12月",
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
        oral_volume = "多少量" in question and any(keyword in question for keyword in ("承运商", "物流公司", "物流供应商", "各家物流", "物流"))
        volume_or_fee = self._is_mw_question(question) or self._is_total_fee_question(question) or oral_volume
        if not carrier_group or not volume_or_fee:
            return False
        if oral_volume:
            return True
        if any(keyword in question for keyword in ("各家", "分别", "占比", "年度")):
            return True
        # 兼容“25年物流公司承运量”“2025年物流供应商发运量是多少”“25年各家物流承运量”这类简写问法。
        return bool(re.search(r"\d{2,4}年.*(?:物流公司|承运商|物流供应商|各家物流|物流).*(承运量|运输量|发运量|发货量|运量|发运多少量|多少量|运输费用|运费)", question))

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
        if any(keyword in question for keyword in ("总费用", "总运费", "费用排名", "运费排名", "按费用排名", "按运费排名", "运输费用排名", "按运输费用排名")):
            return "total_fee"
        return None

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class LogisticsQuestionPolicyDecision:
    """物流题库响应策略命中结果。

    说明：
        1. 当前只承载“需澄清”和“不支持”两类正式策略；
        2. planner 命中该结果后，应直接返回对应状态，避免继续误入执行链路；
        3. 当前保留 category，便于后续做题型统计、回归和文档沉淀。
    """

    decision_type: Literal["clarification", "unsupported"]
    category: str
    reason: str
    clarification_questions: list[str] = field(default_factory=list)
    clarification_missing_slots: list[str] = field(default_factory=list)
    clarification_template: str | None = None
    llm_assist_allowed: bool = False
    unsupported_template: str | None = None
    unsupported_suggestions: list[str] = field(default_factory=list)


class LogisticsQuestionBankResponsePolicy:
    """物流域题库响应策略。

    设计目标：
        1. 把 B / C 类题库结论下沉到系统行为，而不是只停留在文档；
        2. 当前先固化高频、边界明确的澄清和不支持模式；
        3. 避免为了扩大支持范围而让系统对模糊问题和超边界问题乱算。
    """

    # 预测、趋势、波动区间类问题统一归入不支持。
    FORECAST_KEYWORDS = ("预测", "预估", "预计", "估算", "估一下", "将会", "未来", "趋势", "波动区间", "费用区间")
    # ETA / 到货时间 / 时效推理当前不在 MVP 支持范围内。
    ETA_KEYWORDS = ("ETA", "到货时间", "到达时间", "预计到达", "何时到达", "何时能到", "什么时候到", "什么时候能到", "多久能到", "时效推演")
    # 开放讨论、治理原则、设计策略题不属于结构化数据问答。
    DISCUSSION_KEYWORDS = (
        "应如何处理",
        "应遵循什么原则",
        "还能否直接输出",
        "应如何回答",
        "如何处理这种",
        "更稳妥的做法",
        "是否还能直接输出",
        "是否应该",
        "如何设计",
        "设计一个",
        "设计一套",
        "优化策略",
        "治理原则",
        "评分模型",
        "风险评分模型",
        "根因分析",
        "原因分析",
    )
    CORRELATION_KEYWORDS = ("相关性", "显著正相关", "显著负相关", "相关性最强", "相关性最高")
    # 额外费用当前只支持总额，不支持项目、原因和明细。
    EXTRA_FEE_DETAIL_KEYWORDS = ("项目", "原因", "明细")
    SUPPLIER_PRICE_DIAGNOSTIC_KEYWORDS = ("supplier_price", "离群点", "分布如何", "高价离群点")
    # 典型模糊问题应先澄清。
    VAGUE_STATUS_KEYWORDS = ("最近", "近期", "最差", "最不好", "表现最不好", "表现不好", "异常", "效率怎么样", "效果怎么样", "有没有问题", "哪些有问题", "风险怎么样")
    SPECIAL_CASE_KEYWORDS = ("特殊订单", "特殊任务", "特殊情况")
    COST_METRIC_KEYWORDS = ("总费用", "总运费", "平均运费", "签收率", "额外费用", "元/瓦")
    TIME_HINT_KEYWORDS = ("本月", "今年", "去年", "近7天", "近30天", "近一个月", "近三个月")
    TRANSPORT_RECORD_KEYWORDS = ("按运输方式统计", "发运记录数")
    PRODUCT_SPEC_KEYWORDS = ("规格为", "总瓦数")
    HIGH_FEE_ADDRESS_KEYWORDS = ("收货地址", "项目地", "运费超过20万", "运费金额超过20万")
    BREAKDOWN_KEYWORDS = ("分别是多少", "分别是哪些", "各任务状态", "各采购方式", "各省", "各城市", "前十个省份", "填充率")
    STATE_BREAKDOWN_KEYWORDS = ("各任务状态", "PREASSIGN", "ASSIGNED", "PRESIGNFOR", "SIGNEDFOR", "PREALLOCATE", "ALLOCATED", "ENTER", "LEAVE")
    ROUTE_PRICE_KEYWORDS = ("运费", "均价", "运价", "报价")
    STATUS_RISK_KEYWORDS = ("履约风险", "风险最高", "重点盯", "优先排查", "长期停留")
    PROCUREMENT_KEYWORDS = ("询比价", "招标", "经营计划", "辅料送样", "普通发运", "采购方式")
    TRANSPORT_MODE_KEYWORDS = ("公路", "铁路", "多式联运", "水路")
    REGION_NAMES = ("华东", "华北", "华南", "华中", "西北", "西南", "东北")
    # BCR1 固化的运输方式与线路追问题族，重点不是直接算，而是先锁定同义口径和统计指标。
    TRANSPORT_MODE_SCOPE_KEYWORDS = (
        "公路运输",
        "铁路运输",
        "水路",
        "多式联运",
        "运输方式",
        "替代运输方式",
        "切换到铁路",
        "从公路切换到铁路",
    )
    ROUTE_OR_ADDRESS_SCOPE_KEYWORDS = (
        "基地发往",
        "始发与",
        "始发地",
        "发往",
        "目的地",
        "收货地址",
        "项目地",
    )
    # BCR2 系统状态 / 成本字段类问题，重点是先确认状态枚举、指标和拆分维度。
    SYSTEM_STATE_SCOPE_KEYWORDS = (
        "主任务表",
        "任务表",
        "状态枚举",
        "状态分布",
        "SIGNEDFOR",
        "PREASSIGN",
        "ASSIGNED",
        "ALLOCATED",
    )
    SYSTEM_STATE_COST_KEYWORDS = (
        "显式成本字段",
        "任务级物流成本",
        "成本区间",
        "估算任务级",
        "利用历史台账估算",
    )
    # BCR2 历史总车次类问题需要先确认车次、车辆数和车型口径，不能直接把字段名当业务口径。
    VEHICLE_OR_TRIP_SCOPE_KEYWORDS = (
        "总车次",
        "车次是多少",
        "多少车",
        "车辆数",
        "车型数量",
        "承运车次",
    )
    # BCR3 客户/项目费用类题仍需先确认客户/项目归并口径和是否需要排名展示。
    CUSTOMER_PROJECT_SCOPE_KEYWORDS = (
        "客户",
        "项目",
        "客户名称",
        "项目名称",
    )
    # BCR3 排名类题必须先确认排名指标、排序方向和 TopN 数量。
    RANKING_BASIS_SCOPE_KEYWORDS = (
        "平均总费用排名",
        "市场份额格局",
        "超计划比例最高",
        "长距离订单",
        "前十大承运商",
        "前10条记录",
    )
    DATA_QUALITY_KEYWORDS = (
        "parse_fail_reason",
        "parsed_quantity",
        "parsed_plate_number",
        "car_model",
        "delivery_distance",
        "transport为空",
        "招标号",
        "询比价号",
        "specification",
        "power字段",
        "不一致率",
        "填写完整性",
    )
    # 规则层仍未覆盖的长期澄清题，Round3 继续补“比较口径 / 映射口径 / 一致性问题 / 线路指标口径”。
    COMPARISON_BASIS_KEYWORDS = ("变化最大", "明显差异", "更偏好", "更划算", "最忙", "差异是多少")
    MAPPING_CONSISTENCY_KEYWORDS = (
        "口径统一后",
        "字段归一",
        "映射为同一字段口径",
        "为什么可能不一致",
        "应给出哪个答案",
        "状态冲突",
    )
    DATA_CONSISTENCY_KEYWORDS = (
        "为空",
        "为0",
        "不一致",
        "冲突",
        "重复",
        "没有对应",
        "没有生成",
        "最少",
        "未绑定",
        "覆盖率",
        "单调递增",
        "多个手机号",
        "多个司机姓名",
        "极端值",
        "关联多个不同的派车任务",
        "同一天关联多个不同",
        "缺失",
    )
    ROUTE_METRIC_KEYWORDS = ("平均路程", "单价/车", "平均每车运费", "平均单车运费", "平均单瓦价")
    QUARTER_AREA_KEYWORDS = ("一季度", "二季度", "三季度", "四季度", "Q1", "Q2", "Q3", "Q4")
    SYSTEM_RESPONSE_STRATEGY_KEYWORDS = (
        "系统应如何",
        "系统至少需要",
        "应如何追问",
        "应如何拆解",
        "应如何输出",
        "应如何体现",
        "字段解释后再作答",
    )
    # C-边界观察池 Round1 先固化“明确应拒答”的业务化模板；不把全部旧 C 题粗暴拒答。
    UNSUPPORTED_RESPONSE_TEMPLATES: dict[str, dict[str, list[str] | str]] = {
        "forecast": {
            "reason": "当前问题需要预测未来费用、趋势或波动区间，现阶段物流数据问答只回答已发生数据的统计结果，不编造预测值。",
            "suggestions": [
                "可以改问：2023–2025 年各月物流总费用是多少？",
                "可以改问：2026 年已发生月份的运费、发运量或单瓦成本是多少？",
            ],
        },
        "eta": {
            "reason": "当前问题需要预计到达时间或 ETA 推演，现阶段缺少受控 ETA 模型和在途轨迹推理链路。",
            "suggestions": [
                "可以改问：当前 2026 系统中各任务状态数量分别是多少？",
                "可以改问：SIGNEDFOR 或 PREASSIGN 状态的任务占比是多少？",
            ],
        },
        "extra_fee_detail": {
            "reason": "当前系统只固化了额外费用总额口径，尚未固化额外费用项目、原因和明细拆分口径。",
            "suggestions": [
                "可以改问：2026 年 1 月额外费用总额是多少？",
                "如果需要项目/原因明细，请先由数据 owner 确认明细字段和归因口径。",
            ],
        },
        "supplier_price_diagnostic": {
            "reason": "当前问题需要价格分布、离群点或异常集中度诊断，超出一期结构化统计边界。",
            "suggestions": [
                "可以先改问：2026 年某个月总运费或单瓦成本是多少？",
                "如需离群点分析，需要先定义高价阈值、样本范围和诊断规则。",
            ],
        },
        "discussion": {
            "reason": "当前问题属于开放讨论、治理原则或方案设计，不是受控结构化数据查询。",
            "suggestions": [
                "可以改问成具体统计题，例如某时间范围内的任务量、运费、签收率或异常数量。",
                "如果要做治理方案，需要另起业务规则设计任务，不应由 data-qa 直接生成结论。",
            ],
        },
        "clarification_design": {
            "reason": "当前问题是在询问系统追问策略设计，不是业务数据查询结果。",
            "suggestions": [
                "可以直接补充时间范围、指标口径和异常定义后再提问。",
                "如果要沉淀追问策略，应进入澄清模板治理任务。",
            ],
        },
        "correlation_analysis": {
            "reason": "当前问题需要相关性或显著性分析，现阶段没有纳入受控统计检验能力。",
            "suggestions": [
                "可以改问：某区域、某年份的平均单瓦成本是多少？",
                "如果要做相关性分析，需要先确认样本范围、变量口径和检验方法。",
            ],
        },
        "system_response_strategy": {
            "reason": "当前问题属于系统追问、输出原则或口径解释策略设计，不属于正式业务数据问答。",
            "suggestions": [
                "可以改问成具体业务查询，例如某月运费、发运量、车次或签收率。",
                "如果要讨论系统策略，应进入产品/规则治理任务，而不是 data-qa 查询。",
            ],
        },
        "high_fee_address_procurement_split": {
            "reason": "当前历史台账缺少稳定询比价/招标拆分字段，无法可靠回答高运费项目地的采购方式拆分。",
            "suggestions": [
                "可以先改问：24 年创维客户项目地运费超过 20 万的收货地址有哪些？",
                "如需询比价/招标拆分，请先补齐并确认采购方式字段口径。",
            ],
        },
        "warehouse_dimension_unreliable": {
            "reason": "当前一期按路线 1 暂不把仓库维度作为可靠统计维度，仓库分配明细不能作为正式结构化回答。",
            "suggestions": [
                "可以改问：2026 年各任务状态数量分别是多少？",
                "如果要统计仓库维度，需要先补齐 allocate 链路并确认仓库字段口径。",
            ],
        },
        "project_name_dimension": {
            "reason": "当前项目名称尚未沉淀为稳定可复用统计维度，直接按项目名称汇总容易误导。",
            "suggestions": [
                "可以改问：某客户在某一年的总发运量是多少 MW？",
                "如果必须按项目名称统计，请先确认项目名称归一规则和数据 owner 口径。",
            ],
        },
    }

    def _build_clarification_decision(
        self,
        *,
        category: str,
        reason: str,
        clarification_questions: list[str],
        clarification_missing_slots: list[str],
        clarification_template: str,
        llm_assist_allowed: bool = True,
    ) -> LogisticsQuestionPolicyDecision:
        """构造统一的澄清策略结果。

        说明：
            1. 当前所有正式澄清模板都尽量经过这个入口，避免字段遗漏；
            2. clarification_missing_slots 用于标记“缺什么口径”，便于后续 LLM 辅助识别；
            3. llm_assist_allowed 只表示允许生成追问候选，不表示允许改变最终裁决。
        """

        return LogisticsQuestionPolicyDecision(
            decision_type="clarification",
            category=category,
            reason=reason,
            clarification_questions=clarification_questions,
            clarification_missing_slots=clarification_missing_slots,
            clarification_template=clarification_template,
            llm_assist_allowed=llm_assist_allowed,
        )

    def _build_unsupported_decision(
        self,
        *,
        category: str,
        reason: str | None = None,
        suggestions: list[str] | None = None,
        template: str | None = None,
    ) -> LogisticsQuestionPolicyDecision:
        """构造统一的不支持策略结果。

        参数：
            category: C 类拒答类别，用于回归统计和前端展示。
            reason: 业务可理解拒答原因；为空时读取默认模板。
            suggestions: 可改问方向；为空时读取默认模板。
            template: 拒答模板编号；为空时默认等于 category。

        返回：
            不支持策略结果，planner 会把类别、模板和建议写入查询计划。
        """

        template_payload = self.UNSUPPORTED_RESPONSE_TEMPLATES.get(category, {})
        resolved_reason = reason or str(template_payload.get("reason") or "当前问题超出现有物流结构化数据问答范围。")
        raw_suggestions = suggestions if suggestions is not None else template_payload.get("suggestions", [])
        if not isinstance(raw_suggestions, list):
            raw_suggestions = []
        resolved_suggestions = [item for item in raw_suggestions if isinstance(item, str) and item.strip()]
        return LogisticsQuestionPolicyDecision(
            decision_type="unsupported",
            category=category,
            reason=resolved_reason,
            unsupported_template=template or category,
            unsupported_suggestions=resolved_suggestions,
        )

    def _contains_year_or_time_hint(self, compact: str) -> bool:
        """判断问题里是否已经包含明确年份或时间范围。"""
        return (
            bool(re.search(r"\d{2,4}年", compact))
            or bool(re.search(r"(?<!\d)20(23|24|25|26)(?!\d)", compact))
            or any(keyword in compact for keyword in self.TIME_HINT_KEYWORDS)
        )

    def match(self, question: str) -> LogisticsQuestionPolicyDecision | None:
        """识别当前问题是否命中正式响应策略。"""
        compact = re.sub(r"\s+", "", question.strip())

        # ETA / 到达时间推理超出现有结构化数据问答范围。
        if any(keyword in compact for keyword in self.ETA_KEYWORDS):
            return self._build_unsupported_decision(category="eta")

        # BCR2 的“主任务表缺少成本字段时如何估算成本区间”不是让系统直接预测，
        # 而是缺状态、指标和拆分维度口径的澄清题；该规则必须优先于通用预测拒答。
        if (
            self._extract_year_from_compact(compact) == 2026
            and any(keyword in compact for keyword in self.SYSTEM_STATE_SCOPE_KEYWORDS)
            and any(keyword in compact for keyword in self.SYSTEM_STATE_COST_KEYWORDS)
        ):
            return self._build_clarification_decision(
                category="system_state_scope",
                reason="当前问题需要先确认系统状态口径、指标口径和拆分维度，不能直接按缺失字段自行估算任务级成本。",
                clarification_questions=[
                    "请明确要看的状态枚举口径，例如 SIGNEDFOR、PREASSIGN、全部状态分布，还是只看已签收任务。",
                    "请说明统计指标口径，是任务数、占比、签收率、异常任务数量，还是需要成本区间测算。",
                    "请补充统计时间范围，以及是否需要按承运商、省份、客户或采购方式等分组维度拆分。",
                ],
                clarification_missing_slots=[
                    "time_range",
                    "status_scope",
                    "metric_definition",
                    "dimension_split",
                ],
                clarification_template="system_state_scope",
            )

        # 预测类问题必须直接返回不支持，不允许编造预测值。
        # 但“2026年1月到3月运量趋势用折线图”这类已发生数据的展示诉求，
        # 本质是图表编排，不是预测，不能被“趋势”关键词误拦截。
        if any(keyword in compact for keyword in self.FORECAST_KEYWORDS) and not self._is_past_trend_display_request(compact):
            return self._build_unsupported_decision(category="forecast")

        # 额外费用细项问题明确不支持，避免误导业务把总额当明细。
        if "额外费用" in compact and any(keyword in compact for keyword in self.EXTRA_FEE_DETAIL_KEYWORDS):
            return self._build_unsupported_decision(category="extra_fee_detail")

        # supplier_price 分布与离群点识别属于诊断分析扩展能力，当前一期不直接支持。
        if "supplier_price" in compact and any(keyword in compact for keyword in self.SUPPLIER_PRICE_DIAGNOSTIC_KEYWORDS):
            return self._build_unsupported_decision(category="supplier_price_diagnostic")

        # 业务题库中存在“应如何先澄清某类业务问题”的样例。
        # 这类问题不是让系统输出产品设计方案，而是验证系统能否识别缺少的比较口径，
        # 因此必须优先落到 B 类业务化澄清，而不是被“系统应如何”误判为 C 类拒答。
        if (
            any(keyword in compact for keyword in self.COMPARISON_BASIS_KEYWORDS)
            and any(keyword in compact for keyword in self.TRANSPORT_MODE_KEYWORDS)
            and any(keyword in compact for keyword in ("先澄清", "问题口径", "如何先澄清"))
        ):
            return self._build_clarification_decision(
                category="comparison_basis_scope",
                reason="当前运输方式比较问题缺少评价指标和判断标准，需先澄清后再比较。",
                clarification_questions=[
                    "请确认要比较公路和铁路的哪个指标，例如总运费、单瓦成本、发运量、车次、签收率或时效。",
                    "请确认“更划算”的判断标准，是看总费用、单位成本、平均单车费用，还是综合多个指标。",
                    "请补充统计时间范围，以及是否限定区域、省份、客户、承运商或线路。",
                ],
                clarification_missing_slots=["evaluation_metric", "aggregation_basis", "time_range"],
                clarification_template="comparison_basis_scope",
            )

        # 字段归一/展示口径属于 B 类映射澄清题，即使问法里带“系统应如何”，
        # 也应先追问主口径和输出形态，不能被通用产品策略拒答抢先命中。
        if (
            any(keyword in compact for keyword in self.MAPPING_CONSISTENCY_KEYWORDS)
            and any(keyword in compact for keyword in self.TRANSPORT_MODE_KEYWORDS)
            and any(keyword in compact for keyword in ("结果展示", "归一", "口径"))
        ):
            return self._build_clarification_decision(
                category="mapping_consistency_scope",
                reason="当前问题需要先确认运输方式别名归一后的主口径和展示方式，再继续输出结果。",
                clarification_questions=[
                    "请确认“铁路”和“铁运”是否需要合并为同一个运输方式口径，公路和汽运是否也按同义口径合并。",
                    "请确认是想看归一后的统计结果，还是想看归一前后的字段差异和映射明细。",
                    "请补充统计时间范围，以及结果展示按占比、运量、运费还是记录数输出。",
                ],
                clarification_missing_slots=["mapping_field", "result_metric", "time_range"],
                clarification_template="mapping_consistency_scope",
            )

        # 开放讨论 / 治理原则 / 设计题统一归为不支持。
        if any(keyword in compact for keyword in self.DISCUSSION_KEYWORDS):
            return self._build_unsupported_decision(category="discussion")

        # “系统至少需要追问什么”这类题本质上是在问系统设计，而不是业务数据结果。
        if "至少需要追问什么" in compact or "系统至少需要追问什么" in compact:
            return self._build_unsupported_decision(category="clarification_design")

        # 相关性、显著性检验类问题属于统计分析扩展能力，当前一期不直接支持。
        if any(keyword in compact for keyword in self.CORRELATION_KEYWORDS):
            return self._build_unsupported_decision(category="correlation_analysis")

        # 系统追问策略、输出原则和样本不足表达属于产品策略题，不是业务数据查询。
        if any(keyword in compact for keyword in self.SYSTEM_RESPONSE_STRATEGY_KEYWORDS):
            return self._build_unsupported_decision(category="system_response_strategy")

        # “异常费用太高”类问题需要先补异常阈值和时间范围，不能直接猜。
        if "异常费用" in compact and any(keyword in compact for keyword in ("太高", "哪些城市", "哪些")):
            return self._build_clarification_decision(
                category="abnormal_fee_scope",
                reason="当前问题需要先明确异常费用的判定阈值和统计时间范围。",
                clarification_questions=[
                    "请先确认统计时间范围，例如 2024 年、2025 年，或按 2023–2025 历史累计统计。",
                    "请说明“异常费用太高”的判定标准，例如高于多少元、超过均值多少倍，或按前 N 名筛选。",
                ],
                clarification_missing_slots=["time_range", "exception_threshold"],
                clarification_template="abnormal_fee_scope",
            )

        # BCR2 系统状态 / 成本字段问题需要先确认状态枚举、指标和拆分维度；不能让系统自行估算成本区间。
        if (
            self._extract_year_from_compact(compact) == 2026
            and any(keyword in compact for keyword in self.SYSTEM_STATE_SCOPE_KEYWORDS)
            and any(keyword in compact for keyword in self.SYSTEM_STATE_COST_KEYWORDS)
        ):
            return self._build_clarification_decision(
                category="system_state_scope",
                reason="当前问题需要先确认系统状态口径、指标口径和拆分维度，不能直接按缺失字段自行估算任务级成本。",
                clarification_questions=[
                    "请明确要看的状态枚举口径，例如 SIGNEDFOR、PREASSIGN、全部状态分布，还是只看已签收任务。",
                    "请说明统计指标口径，是任务数、占比、签收率、异常任务数量，还是需要成本区间测算。",
                    "请补充统计时间范围，以及是否需要按承运商、省份、客户或采购方式等分组维度拆分。",
                ],
                clarification_missing_slots=[
                    "time_range",
                    "status_scope",
                    "metric_definition",
                    "dimension_split",
                ],
                clarification_template="system_state_scope",
            )

        # 履约风险/重点盯防类问题本质上缺少风险定义与统计范围，不应让系统自行脑补。
        if (
            any(keyword in compact for keyword in self.STATUS_RISK_KEYWORDS)
            and any(keyword in compact for keyword in ("任务", "客户", "在途", "状态"))
        ):
            return self._build_clarification_decision(
                category="status_risk_scope",
                reason="当前问题缺少明确的风险判定标准和统计范围，需先澄清后再继续分析。",
                clarification_questions=[
                    "请先确认这里的“风险”按什么口径判断，例如状态滞留时长、未签收时长、费用异常，还是解析失败。",
                    "请确认统计范围，例如当前在途任务、2026 年正式系统任务，还是近 30 天内的任务 / 客户。",
                ],
                clarification_missing_slots=["evaluation_metric", "time_range"],
                clarification_template="status_risk_scope",
            )

        # BCR1 异常/原因类问题需要先确认异常定义、时间范围和输出形态，不能只走通用“最近/异常”追问。
        if (
            any(keyword in compact for keyword in ("异常高成本", "高成本运输", "风险分层", "外协运力异常", "高频多任务"))
            or ("PREASSIGN" in compact and "超过3天" in compact)
        ):
            return self._build_clarification_decision(
                category="abnormal_or_reason_scope",
                reason="当前问题需要先明确异常或高成本的判定标准、统计时间范围和输出形态，避免系统自行定义异常。",
                clarification_questions=[
                    "请补充统计时间范围，例如 2024 年全年、2025 年某个月、2026 年 1-2 月，或最近一个季度。",
                    "请先说明异常或高成本的判断标准，例如超过均值多少、是否按单瓦成本、单车费用、状态滞留天数或任务频次判断。",
                    "请确认输出形态：需要异常明细清单，还是只汇总异常数量、涉及区域/线路和主要原因。",
                ],
                clarification_missing_slots=[
                    "time_range",
                    "exception_threshold",
                    "result_metric",
                    "analysis_scope",
                ],
                clarification_template="abnormal_or_reason_scope",
            )

        # “最近怎么样 / 哪些有问题 / 哪个最差”这类问题本质上缺时间与评价标准。
        if any(keyword in compact for keyword in self.VAGUE_STATUS_KEYWORDS):
            return self._build_clarification_decision(
                category="vague_status",
                reason="当前问题缺少明确时间范围和评价标准，需先补充口径。",
                clarification_questions=[
                    "请先明确时间范围，例如近7天、近30天、本月或今年。",
                    "请明确指标口径，例如总费用、单瓦成本、签收率、异常率或车次。",
                ],
                clarification_missing_slots=["time_range", "evaluation_metric"],
                clarification_template="vague_status",
            )

        # “变化最大 / 更划算 / 最忙 / 是否存在明显差异”类问题需要先锁定比较基准。
        if any(keyword in compact for keyword in self.COMPARISON_BASIS_KEYWORDS):
            return self._build_clarification_decision(
                category="comparison_basis_scope",
                reason="当前问题需要先明确比较指标和判断标准，避免系统按错误口径直接比较。",
                clarification_questions=[
                    "请确认这里要比较的核心指标，例如总运费、单瓦成本、发运量、车次，还是状态占比。",
                    "请确认“变化最大 / 更划算 / 明显差异 / 最忙”按什么标准判断，例如同比差值、占比变化、均值差异还是排名。",
                ],
                clarification_missing_slots=["evaluation_metric", "aggregation_basis"],
                clarification_template="comparison_basis_scope",
            )

        # 字段映射、别名归一和跨表冲突问题需要先确认主口径，不应让系统自行猜测权威字段。
        if any(keyword in compact for keyword in self.MAPPING_CONSISTENCY_KEYWORDS):
            return self._build_clarification_decision(
                category="mapping_consistency_scope",
                reason="当前问题需要先确认统一后的字段口径和最终展示方式，再继续输出结果。",
                clarification_questions=[
                    "请确认要以哪个字段或哪张表作为主口径，例如历史台账字段、2026 系统字段，还是统一归一后的业务口径。",
                    "请确认是想看统一后的统计结果，还是想看口径冲突 / 映射不一致的明细清单。",
                ],
                clarification_missing_slots=["mapping_field", "result_metric"],
                clarification_template="mapping_consistency_scope",
            )

        # 跨年字段别名比较需要先统一车辆数、车次和效率指标的业务口径。
        if "车辆数" in compact and "车次" in compact and any(keyword in compact for keyword in ("跨年", "比较", "效率")):
            return self._build_clarification_decision(
                category="field_alias_comparison_scope",
                reason="当前问题需要先统一车辆数、车次和效率指标口径，再做跨年比较。",
                clarification_questions=[
                    "请确认跨年比较时统一按车次统计，还是按唯一车辆数统计。",
                    "请确认“车辆效率”看平均每车发运量、平均每车运费，还是其他业务指标。",
                ],
                clarification_missing_slots=["metric_definition", "aggregation_basis"],
                clarification_template="field_alias_comparison_scope",
            )

        # “特殊订单 / 特殊任务”如果没有定义规则，不应直接猜。
        if any(keyword in compact for keyword in self.SPECIAL_CASE_KEYWORDS):
            return self._build_clarification_decision(
                category="special_case",
                reason="当前问题中的“特殊”定义不明确，需先补充判定标准。",
                clarification_questions=[
                    "请说明“特殊”的判定标准，例如费用异常、时效异常、签收异常或指定订单类型。",
                    "请补充时间范围，便于系统按统一口径筛选。",
                ],
                clarification_missing_slots=["special_definition", "time_range"],
                clarification_template="special_case",
            )

        # “按运输方式统计发运记录数”缺少记录口径定义，不应直接把记录数当车次或明细行。
        if all(keyword in compact for keyword in self.TRANSPORT_RECORD_KEYWORDS):
            return self._build_clarification_decision(
                category="transport_record_scope",
                reason="当前问题中的“发运记录数”口径不明确，需先确认统计对象和时间范围。",
                clarification_questions=[
                    "请确认“发运记录数”按发运明细行、物流任务数还是车次统计。",
                    "请补充时间范围，例如 2024 年、2025 年，或明确是否按 2023–2025 历史台账累计统计。",
                ],
                clarification_missing_slots=["record_scope", "time_range"],
                clarification_template="transport_record_scope",
            )

        # 季度车次 / 车辆数问题里，季度已给出，但“车次还是车辆数”口径仍未锁定。
        if re.search(r"20(24|25)Q[1-4]", compact) and any(keyword in compact for keyword in ("车次", "车辆数")):
            return self._build_clarification_decision(
                category="quarter_trip_metric_scope",
                reason="当前问题虽然给出了季度，但“车次”和“车辆数”是两个不同口径，需先确认统计指标。",
                clarification_questions=[
                    "请确认这里统计的是车次，还是唯一车辆数。",
                    "如需跨季度比较，请确认是否统一按历史台账口径统计，不混入 2026 系统数据。",
                ],
                clarification_missing_slots=["metric_definition", "source_scope"],
                clarification_template="quarter_trip_metric_scope",
            )

        # “规格为 XXX 的总瓦数”如果没有时间范围，容易把历史累计和单年统计混在一起。
        if all(keyword in compact for keyword in self.PRODUCT_SPEC_KEYWORDS) and not self._contains_year_or_time_hint(compact):
            return self._build_clarification_decision(
                category="product_spec_scope",
                reason="当前问题缺少时间范围，需先确认规格统计按哪一段历史口径执行。",
                clarification_questions=[
                    "请确认统计范围是 2023–2025 历史台账累计，还是某一具体年份。",
                    "如需看发运量，请确认按瓦数 / MW 展示，还是按件数展示。",
                ],
                clarification_missing_slots=["time_range", "metric_definition"],
                clarification_template="product_spec_scope",
            )

        # “季度 + 各区域 + 运费/单瓦运输成本”类问题当前仍需先统一季度口径和排序方式。
        if (
            self._extract_year_from_compact(compact) in {2023, 2024, 2025}
            and "各区域" in compact
            and any(keyword in compact for keyword in self.QUARTER_AREA_KEYWORDS)
            and any(keyword in compact for keyword in ("运费分别是多少", "单瓦运输成本分别是多少"))
        ):
            return self._build_clarification_decision(
                category="quarter_area_metric_scope",
                reason="当前问题需要先确认季度统计口径和区域排序方式，避免把季度累计和展示顺序混在一起。",
                clarification_questions=[
                    "请确认这里按季度统计时，是否统一只看 2023–2025 历史台账口径，不混入 2026 正式系统数据。",
                    "请确认“按区域排序展示”是按该指标从高到低排序，还是按固定区域顺序展示。",
                ],
                clarification_missing_slots=["source_scope", "sort_order"],
                clarification_template="quarter_area_metric_scope",
            )

        # “收货地址/项目地运费超过20万”类问题需要先统一阈值统计口径和发运量拆分口径。
        if (
            ("收货地址" in compact or "项目地" in compact)
            and ("运费超过20万" in compact or "运费金额超过20万" in compact)
        ):
            if "询比价" in compact and "招标" in compact:
                return self._build_unsupported_decision(category="high_fee_address_procurement_split")
            return self._build_clarification_decision(
                category="high_fee_address_scope",
                reason="当前问题需要先统一高运费地址的统计口径，再执行筛选。",
                clarification_questions=[
                    "请确认“超过20万”是按单个收货地址全年累计运费，还是按单笔项目地记录判断。",
                    "如需继续拆分发运量，请确认按件数、瓦数还是车次展示。",
                    "如果还要按询比价/招标拆分，请先确认当前历史台账是否有稳定采购方式字段可供统计。",
                ],
                clarification_missing_slots=["threshold_scope", "metric_definition", "procurement_scope"],
                clarification_template="high_fee_address_scope",
            )

        # 采购方式/特殊业务口径对比类问题当前主要缺比较指标与统计范围。
        if (
            any(keyword in compact for keyword in self.PROCUREMENT_KEYWORDS)
            and any(keyword in compact for keyword in ("任务量", "占比", "平均装车数", "运费差异", "分别是多少", "平均单瓦成本"))
        ):
            return self._build_clarification_decision(
                category="procurement_metric_scope",
                reason="当前问题需要先确认采购方式对比的指标口径和统计范围，避免把不同任务集合混算。",
                clarification_questions=[
                    "请确认采购方式口径，例如询比价、招标、经营计划或辅料送样是否按当前系统标签直接统计。",
                    "请确认要统计的指标和单位，例如发运量 MW、总运费、车次、任务量、平均装车数或单瓦成本。",
                    "请确认统计时间范围，以及是否需要按承运商、区域、省份或客户继续拆分。",
                ],
                clarification_missing_slots=[
                    "procurement_scope",
                    "metric_definition",
                    "time_range",
                    "dimension_split",
                ],
                clarification_template="procurement_metric_scope",
            )

        # 2026 基地过滤当前缺少稳定映射，不应继续给通用澄清。
        if (
            "基地" in compact
            and ("客户" in compact or "晶茂" in compact or "承运商" in compact)
            and any(keyword in compact for keyword in ("总运费", "总费用", "总计运费", "运费多少", "多少钱"))
            and ("26年" in compact or "2026年" in compact)
        ):
            return LogisticsQuestionPolicyDecision(
                decision_type="clarification",
                category="system_base_scope",
                reason="当前问题包含 2026 基地过滤，但系统侧基地映射口径还未完全锁定，需先确认过滤方式。",
                clarification_questions=[
                    "请确认是否可以先按客户或承运商整体统计，不限定合肥/阜宁基地。",
                    "如必须限定基地，请先确认 2026 系统数据当前按哪个字段映射基地口径。",
                ],
                clarification_missing_slots=["base_scope", "mapping_field"],
                clarification_template="system_base_scope",
                llm_assist_allowed=False,
            )

        # 线路运价分析如果缺少年份或统计口径，不应直接落到通用兜底澄清。
        if (
            self._extract_vehicle_type_from_compact(compact)
            and any(keyword in compact for keyword in self.ROUTE_PRICE_KEYWORDS)
            and any(keyword in compact for keyword in ("合肥发", "阜宁发", "发往"))
            and not self._contains_year_or_time_hint(compact)
        ):
            return self._build_clarification_decision(
                category="route_pricing_scope",
                reason="当前线路运价问题缺少年份或统计口径，需先确认后再计算。",
                clarification_questions=[
                    "请补充统计年份，例如 2024 年、2025 年，或明确按 2023–2025 历史累计统计。",
                    "请确认要看平均运费、每月均价，还是最高价 / 最低价。",
                ],
                clarification_missing_slots=["time_range", "price_metric"],
                clarification_template="route_pricing_scope",
            )

        # 已给出年份的线路“运价/报价”问法仍然缺少价格指标口径时，也应先追问。
        if (
            self._extract_vehicle_type_from_compact(compact)
            and any(keyword in compact for keyword in self.ROUTE_PRICE_KEYWORDS)
            and any(keyword in compact for keyword in ("合肥发", "阜宁发", "发往"))
            and self._contains_year_or_time_hint(compact)
            and any(keyword in compact for keyword in ("运价", "报价", "平均单车运费", "平均单瓦价"))
        ):
            return self._build_clarification_decision(
                category="route_price_metric_scope",
                reason="当前问题虽给出了时间和线路，但“运价/报价”口径仍不明确，需先确认价格指标。",
                clarification_questions=[
                    "请确认这里的“运价/报价”是指平均单车运费、线路平均运费，还是平均单瓦价。",
                    "如果需要跨年份对比，请确认是否统一按 2023–2025 历史台账口径计算。",
                ],
                clarification_missing_slots=["price_metric", "source_scope"],
                clarification_template="route_price_metric_scope",
            )

        # “按运输方式的平均单瓦成本”类问题仍需先统一平均口径和费用口径。
        if (
            any(keyword in compact for keyword in self.TRANSPORT_MODE_KEYWORDS)
            and "平均单瓦成本" in compact
            and "经营计划" not in compact
            and "辅料送样" not in compact
        ):
            return self._build_clarification_decision(
                category="transport_unit_fee_scope",
                reason="当前问题需要先确认平均单瓦成本的计算基础和费用口径，避免把不同运输方式样本直接混算。",
                clarification_questions=[
                    "请确认这里的“平均单瓦成本”是按总运费除以总发运瓦数计算，还是按单条运输记录的单瓦成本再做平均。",
                    "请确认单瓦成本是否需要把额外费用一起计入分子，以及是否只统计运输方式字段稳定的记录。",
                ],
                clarification_missing_slots=["metric_definition", "fee_scope", "statistic_scope"],
                clarification_template="transport_unit_fee_scope",
            )

        # BCR1 运输方式 + 指标类问题需要先统一运输方式别名、统计指标和展示单位。
        if (
            (
                any(keyword in compact for keyword in self.TRANSPORT_MODE_SCOPE_KEYWORDS)
                or any(keyword in compact for keyword in self.TRANSPORT_MODE_KEYWORDS)
            )
            and any(keyword in compact for keyword in ("总发运量", "总运费", "总费用", "总件数", "推广", "降低成本", "适合"))
            and self._extract_year_from_compact(compact) in {None, 2023, 2024, 2025}
        ):
            return self._build_clarification_decision(
                category="transport_mode_metric_scope",
                reason="当前问题需要先明确运输方式同义口径、统计指标、单位和时间范围，避免把运输方式样本直接混算。",
                clarification_questions=[
                    "请明确运输方式口径，例如公路/汽运、铁路/铁运、水路和多式联运是否需要合并同义口径。",
                    "请说明要统计的指标和单位，是发运量 MW、总运费、车次、件数、单瓦成本，还是降本金额。",
                    "请补充统计时间范围，以及是否需要按区域、省份、承运商或线路继续拆分。",
                    "请确认输出形态：只输出汇总总数/总额，还是需要表格、排名或按月/区域/承运商展开。",
                ],
                clarification_missing_slots=[
                    "source_scope",
                    "metric_definition",
                    "time_range",
                    "dimension_split",
                ],
                clarification_template="transport_mode_metric_scope",
            )

        # 线路/基地/目的地类题目虽然给出了部分条件，但“平均路程 / 单价/车 / 单车均价 / 单瓦价”仍常缺统计基础。
        if (
            any(keyword in compact for keyword in self.ROUTE_METRIC_KEYWORDS)
            and any(keyword in compact for keyword in ("基地", "始发", "发往", "线路", "合肥", "阜宁"))
        ):
            return self._build_clarification_decision(
                category="route_metric_scope",
                reason="当前线路指标问题需要先统一统计基础，避免把单车均价、单瓦价和路程口径混算。",
                clarification_questions=[
                    "请确认这里要看的指标口径，例如平均单车运费、平均单瓦价，还是按 delivery_distance 统计的平均路程。",
                    "请确认平均值是按车次平均、按任务平均，还是只统计满足基地 / 车型 / 目的地条件的历史记录。",
                ],
                clarification_missing_slots=["metric_definition", "statistic_scope"],
                clarification_template="route_metric_scope",
            )

        # “25 年发往华东区域发运量”这类问题虽然包含“发往”，但目的地是已锁定的区域维度，
        # 且指标是总发运量 MW，不涉及线路单价、车型或平均值口径，应放行给正式 planner 回答。
        if (
            self._extract_year_from_compact(compact) in {2023, 2024, 2025}
            and any(region in compact for region in self.REGION_NAMES)
            and any(keyword in compact for keyword in ("发运量", "运量", "MW"))
            and not any(keyword in compact for keyword in ("平均", "均价", "单价", "单车", "单瓦", "差值", "车型", "17.5", "13米"))
        ):
            return None

        # BCR1 基地/始发/目的地题族需要先锁定线路范围、指标单位和车型/运输方式限制。
        if (
            any(keyword in compact for keyword in self.ROUTE_OR_ADDRESS_SCOPE_KEYWORDS)
            and any(keyword in compact for keyword in ("平均运费", "平均元/瓦", "总发运量", "发运量", "差值"))
            and self._extract_year_from_compact(compact) in {2023, 2024, 2025}
        ):
            return self._build_clarification_decision(
                category="route_or_address_scope",
                reason="当前问题需要先明确始发地/目的地范围、指标口径和车型或运输方式限制，避免线路条件看似明确但统计口径不一致。",
                clarification_questions=[
                    "请确认始发地和目的地范围，例如合肥基地发往江苏省、单条线路、某省还是某区域。",
                    "请说明要看的指标和单位，例如发运量 MW、总运费、平均运费、平均元/瓦、车次或单车均价。",
                    "请确认是否限定车型或运输方式，例如 17.5 车、13 米车、公路或铁路。",
                ],
                clarification_missing_slots=[
                    "source_scope",
                    "metric_definition",
                    "dimension_split",
                    "record_scope",
                ],
                clarification_template="route_or_address_scope",
            )

        # BCR2 历史月度“总车次”题需要先确认车次 / 车辆数 / 车型口径，不能把业务问法硬落到单一字段。
        if (
            self._extract_year_from_compact(compact) in {2023, 2024, 2025}
            and re.search(r"\d{1,2}月份?", compact)
            and any(keyword in compact for keyword in self.VEHICLE_OR_TRIP_SCOPE_KEYWORDS)
            and not self._extract_vehicle_type_from_compact(compact)
        ):
            return self._build_clarification_decision(
                category="vehicle_or_trip_scope",
                reason="当前问题需要先明确车次、车辆数和车型口径，避免把历史台账字段直接当成业务口径。",
                clarification_questions=[
                    "请明确车次/车辆数口径，是按发运车次、唯一车辆数、车型数量，还是系统任务车辆字段统计。",
                    "请补充车型口径：是否限定 17.5 米车、13 米车等，还是统计全部车型。",
                    "请确认统计时间范围是否就是题目月份，以及是否需要按区域、线路、承运商等分组维度拆分。",
                ],
                clarification_missing_slots=[
                    "time_range",
                    "metric_definition",
                    "record_scope",
                    "dimension_split",
                ],
                clarification_template="vehicle_or_trip_scope",
            )

        # BCR3 基地车型 / 承运商全年车次题需要先锁定车次、车辆数、车型和分组维度。
        if (
            self._extract_year_from_compact(compact) in {2023, 2024, 2025}
            and any(keyword in compact for keyword in self.VEHICLE_OR_TRIP_SCOPE_KEYWORDS)
            and (
                self._extract_vehicle_type_from_compact(compact)
                or "9.6车" in compact
                or "承运车次" in compact
                or "全年共发运" in compact
            )
        ):
            return self._build_clarification_decision(
                category="vehicle_or_trip_scope",
                reason="当前问题需要先明确车次/车辆数口径、车型口径和分组维度，避免把基地车型、承运商车次和车辆数混算。",
                clarification_questions=[
                    "请明确车次/车辆数口径：是按发运车次、唯一车辆数、车型数量，还是系统任务车辆字段统计。",
                    "请确认车型口径：题目中的 9.6 车、17.5 米车、13 米车等是否按车型字段精确匹配，还是按车型别名归并。",
                    "请确认分组维度和统计时间范围：只看题目指定基地/承运商，还是还要按区域、线路、客户继续拆分。",
                ],
                clarification_missing_slots=[
                    "time_range",
                    "metric_definition",
                    "record_scope",
                    "dimension_split",
                ],
                clarification_template="vehicle_or_trip_scope",
            )

        # BCR3 客户/项目总费用题需要先确认客户名称归并、指标口径和是否需要排名。
        if (
            self._extract_year_from_compact(compact) in {2023, 2024, 2025}
            and any(keyword in compact for keyword in self.CUSTOMER_PROJECT_SCOPE_KEYWORDS)
            and any(keyword in compact for keyword in ("总运费", "总费用", "运费是多少"))
            and "项目地" not in compact
            and "收货地址" not in compact
        ):
            return self._build_clarification_decision(
                category="customer_project_scope",
                reason="当前问题需要先确认客户/项目名称归并口径、指标口径和是否需要排名，避免把客户简称、项目名称和客户标准名称混算。",
                clarification_questions=[
                    "请明确客户/项目名称口径：题目里的名称按客户标准名称、项目名称，还是客户名前缀/简称归并统计。",
                    "请确认指标口径和统计时间范围：只看总运费，还是还要同步输出发运量 MW、车次或单瓦成本。",
                    "请确认是否需要排名：只查该客户/项目单项结果，还是按客户/项目做排名，并说明 TopN 数量。",
                ],
                clarification_missing_slots=[
                    "time_range",
                    "mapping_field",
                    "metric_definition",
                    "result_metric",
                ],
                clarification_template="customer_project_scope",
            )

        # BCR3 排名题需要先明确排名指标、方向和 TopN，不能把“排名/前十”直接落到单一 query_key。
        if any(keyword in compact for keyword in self.RANKING_BASIS_SCOPE_KEYWORDS):
            return self._build_clarification_decision(
                category="ranking_basis_scope",
                reason="当前问题需要先确认排名指标、排名方向和 TopN 数量，避免系统按错误指标直接排序。",
                clarification_questions=[
                    "请明确排名指标：按平均总费用、市场份额、超计划比例、发运量、车次还是单瓦成本排名。",
                    "请说明排名方向和 TopN 数量：例如从高到低前 10、从低到高后 10，还是输出全部排序。",
                    "请补充统计时间范围和分组维度：按承运商、物流公司、区域、省份、客户还是记录维度排名。",
                ],
                clarification_missing_slots=[
                    "time_range",
                    "metric_definition",
                    "aggregation_basis",
                    "dimension_split",
                ],
                clarification_template="ranking_basis_scope",
            )

        # 装载托数问题需要先确认统计对象和是否按车次平均。
        if "平均每车装载托数" in compact:
            return self._build_clarification_decision(
                category="route_loading_scope",
                reason="当前问题缺少装载托数的统计口径，需先确认按车次平均还是按任务平均。",
                clarification_questions=[
                    "请确认“平均每车装载托数”是按车次平均，还是按物流任务平均。",
                    "请确认是否只统计有完整装载托数字段的记录，还是把空值按 0 处理。",
                ],
                clarification_missing_slots=["statistic_scope", "null_handling"],
                clarification_template="route_loading_scope",
            )

        # 单月元瓦问题如果缺少年份，容易把跨年同月数据混在一起。
        if (
            any(keyword in compact for keyword in ("单W运输成本", "单瓦价", "元瓦", "单瓦运输成本"))
            and re.search(r"\d{1,2}月份?", compact)
            and not self._contains_year_or_time_hint(compact)
        ):
            return self._build_clarification_decision(
                category="unit_fee_missing_year",
                reason="当前问题只给了月份，没有给年份，无法稳定锁定单瓦成本口径。",
                clarification_questions=[
                    "请补充统计年份，例如 2024 年 2 月或 2025 年 2 月。",
                    "请确认单瓦成本是否需要把额外费用一起纳入分子。",
                ],
                clarification_missing_slots=["time_range", "fee_scope"],
                clarification_template="unit_fee_missing_year",
            )

        # “2026 运量综合”类问法缺少明确时间范围和拆分口径，先做业务化澄清。
        if (self._extract_year_from_compact(compact) == 2026) and "运量综合" in compact:
            return self._build_clarification_decision(
                category="system_mw_composite_scope",
                reason="当前问题缺少明确时间范围和展示口径，需先确认后再统计 2026 系统发运量。",
                clarification_questions=[
                    "请确认是查看 2026 年截至目前累计，还是某个具体月份 / 月区间。",
                    "请确认只看总发运量 MW，还是还需要按采购方式、区域或车次拆分。",
                ],
                clarification_missing_slots=["time_range", "dimension_split"],
                clarification_template="system_mw_composite_scope",
            )

        # 2026 系统字段完整性、解析一致性和异常记录数量类问题，需要先统一统计目标和拆分口径。
        if (
            any(keyword in compact for keyword in self.DATA_QUALITY_KEYWORDS)
            and any(keyword in compact for keyword in ("多少", "多少条", "不一致", "模式", "完整性", "为空", "哪些任务", "未按口径填写"))
        ):
            return self._build_clarification_decision(
                category="data_quality_scope",
                reason="当前问题需要先明确要看问题数量、问题率还是问题明细清单，以及是否需要继续拆分维度。",
                clarification_questions=[
                    "请确认要看的是问题记录数量、问题率，还是问题明细清单。",
                    "请确认是否只统计 2026 正式系统数据，以及是否还要按承运商、状态或采购方式继续拆分。",
                ],
                clarification_missing_slots=["result_metric", "statistic_scope", "dimension_split"],
                clarification_template="data_quality_scope",
            )

        # 数据一致性 / 重复 / 缺失 / 冲突类问题需要先确认输出目标是数量、问题率还是明细清单。
        if any(keyword in compact for keyword in self.DATA_CONSISTENCY_KEYWORDS):
            return self._build_clarification_decision(
                category="data_consistency_scope",
                reason="当前问题需要先明确对账对象、差异阈值、统计时间范围和输出形态，避免把数据质量问题直接当成结论。",
                clarification_questions=[
                    "请明确对账对象或一致性对象，例如客户名称、承运商映射、车牌、状态字段、费用字段，或合同/招标/询比价编号。",
                    "请补充差异阈值或异常判定标准，例如完全不一致、字段缺失、金额差异超过多少，或一对多/多对一。",
                    "请确认统计时间范围、比较维度和输出形态，是问题记录数量、问题率还是异常明细清单。",
                ],
                clarification_missing_slots=[
                    "time_range",
                    "mapping_field",
                    "threshold_scope",
                    "dimension_split",
                    "result_metric",
                ],
                clarification_template="data_consistency_scope",
            )

        # 司机手机号和身份证一人多号 / 一号多人属于数据一致性排查，需要先确认输出清单或统计口径。
        if "司机" in compact and any(keyword in compact for keyword in ("手机号", "身份证")) and any(
            keyword in compact for keyword in ("一人多号", "一号多人")
        ):
            return self._build_clarification_decision(
                category="driver_identity_consistency_scope",
                reason="当前问题需要先明确是看异常数量、异常司机清单，还是按承运商继续拆分。",
                clarification_questions=[
                    "请确认这里是只看一人多号 / 一号多人异常数量，还是需要输出异常司机明细清单。",
                    "请确认是否只统计 2026 正式系统数据，以及是否还要按承运商或任务状态继续拆分。",
                ],
                clarification_missing_slots=["result_metric", "statistic_scope", "dimension_split"],
                clarification_template="driver_identity_consistency_scope",
            )

        # 历史产生原因分布题需要先确认字段口径、统计范围和差异展示方式。
        if "产生原因" in compact and any(keyword in compact for keyword in ("高频前三", "分布", "差异")):
            return self._build_clarification_decision(
                category="cause_distribution_scope",
                reason="当前问题需要先确认产生原因字段口径和区域差异的展示方式。",
                clarification_questions=[
                    "请确认“产生原因”按历史台账原始字段统计，还是需要先做原因类别归并。",
                    "请确认区域差异是看各区域占比、数量排名，还是只输出前三类原因的区域分布。",
                ],
                clarification_missing_slots=["mapping_field", "result_metric", "dimension_split"],
                clarification_template="cause_distribution_scope",
            )

        # 合同编号对应多个物流公司属于数据一致性排查，需要先锁定统计口径和明细需求。
        if "合同编号" in compact and any(keyword in compact for keyword in ("多个物流公司", "涉及哪些合同")):
            return self._build_clarification_decision(
                category="contract_carrier_scope",
                reason="当前问题需要先确认合同编号与物流公司的匹配口径，以及输出数量还是明细。",
                clarification_questions=[
                    "请确认是统计同一合同编号对应多个物流公司的合同数量，还是直接输出涉及的合同明细。",
                    "请确认是否只看 2026 正式系统数据，还是也要纳入 2023–2025 历史台账。",
                ],
                clarification_missing_slots=["result_metric", "source_scope"],
                clarification_template="contract_carrier_scope",
            )

        # 项目/客户发运量如果未给年份，先确认是看单年还是历史累计。
        if "仓库" in compact and any(keyword in compact for keyword in ("分配明细", "平均分配", "平均")):
            return self._build_unsupported_decision(category="warehouse_dimension_unreliable")
        if "项目名称" in compact and any(keyword in compact for keyword in ("总发运量", "总运量", "发运量")):
            return self._build_unsupported_decision(category="project_name_dimension")
        if (
            any(keyword in compact for keyword in ("项目名称", "客户"))
            and any(keyword in compact for keyword in ("总发运量", "总运量", "发运量"))
            and not self._contains_year_or_time_hint(compact)
        ):
            return self._build_clarification_decision(
                category="customer_mw_missing_year",
                reason="当前问题缺少年份，需先确认是看某一年还是 2023–2025 历史累计。",
                clarification_questions=[
                    "请补充统计年份，例如 2024 年或 2025 年。",
                    "如果想直接看历史累计，请明确说明按 2023–2025 历史台账累计统计。",
                ],
                clarification_missing_slots=["time_range", "source_scope"],
                clarification_template="customer_mw_missing_year",
            )

        # supplier_price 分布和高价离群点问题仍需先锁定分析标准，避免直接输出不稳定结论。
        if "supplier_price" in compact and any(keyword in compact for keyword in ("离群点", "分布如何", "高价")):
            return self._build_clarification_decision(
                category="supplier_price_outlier_scope",
                reason="当前问题需要先统一 supplier_price 的分析口径，避免把统计分布和离群点判断混在一起。",
                clarification_questions=[
                    "请确认是查看 supplier_price 的整体分布，还是只看高价离群点。",
                    "如果要看离群点，请先说明判定标准，例如按分位数、均值倍数还是固定阈值。",
                ],
                clarification_missing_slots=["analysis_scope", "exception_threshold"],
                clarification_template="supplier_price_outlier_scope",
            )

        # 各区域达标率的均值与中位数问题需要先确认达标率定义和统计范围。
        if "达标率" in compact and "均值与中位数" in compact:
            return self._build_clarification_decision(
                category="rate_distribution_scope",
                reason="当前问题需要先明确达标率的定义和统计范围，避免把不同口径混算。",
                clarification_questions=[
                    "请确认“达标率”指的是按发运计划达成率、签收达成率，还是其他业务口径。",
                    "请确认均值和中位数是按区域月度值统计，还是按单条记录直接统计。",
                ],
                clarification_missing_slots=["metric_definition", "aggregation_basis"],
                clarification_template="rate_distribution_scope",
            )

        # 2026 单状态数量及占比需要先确认分母口径。
        if "2026年物流任务中状态为" in compact and "数量及占比" in compact:
            return self._build_clarification_decision(
                category="system_status_ratio_scope",
                reason="当前问题需要先确认占比的分母口径和是否只看正式有效任务。",
                clarification_questions=[
                    "请确认占比是按全部 2026 物流任务作为分母，还是按有效任务 / 某类任务作为分母。",
                    "请确认是否只统计正式系统有效任务，不包含测试或已作废状态。",
                ],
                clarification_missing_slots=["denominator_scope", "statistic_scope"],
                clarification_template="system_status_ratio_scope",
            )

        # 2026 按运输方式统计送达距离，需要先明确距离字段来源和平均口径。
        if (
            self._extract_year_from_compact(compact) == 2026
            and any(keyword in compact for keyword in self.TRANSPORT_MODE_KEYWORDS)
            and "送达距离" in compact
        ):
            return self._build_clarification_decision(
                category="transport_distance_scope",
                reason="当前问题需要先确认送达距离字段口径和平均方式，避免把空值或不同任务层级混算。",
                clarification_questions=[
                    "请确认送达距离按哪个字段统计，例如 delivery_distance，且空值是否剔除。",
                    "请确认平均距离按任务平均、按车次平均，还是只统计已签收任务。",
                ],
                clarification_missing_slots=["metric_definition", "statistic_scope", "null_handling"],
                clarification_template="transport_distance_scope",
            )

        # 解析状态计数需要先统一状态码含义和统计对象。
        if "2026年派车任务中" in compact and "回单解析状态为" in compact and any(
            keyword in compact for keyword in ("记录数量", "状态分布", "分别是多少")
        ):
            return self._build_clarification_decision(
                category="parse_status_scope",
                reason="当前问题需要先确认解析状态码含义，以及统计对象是否只看 2026 正式系统派车任务。",
                clarification_questions=[
                    "请确认解析状态码的业务含义是否按当前正式系统口径解释，例如 0/1/3/4 分别代表什么。",
                    "请确认是否只统计 2026 正式系统派车任务，不包含测试或历史迁移记录。",
                ],
                clarification_missing_slots=["status_code_meaning", "statistic_scope"],
                clarification_template="parse_status_scope",
            )

        # 2026 派车任务解析状态分布问法也应命中正式业务化澄清，而不是掉回通用模板。
        if (
            self._extract_year_from_compact(compact) == 2026
            and any(keyword in compact for keyword in ("派车任务", "assign_task"))
            and "解析状态" in compact
            and any(keyword in compact for keyword in ("状态分布", "分别是多少", "0/1/3/4"))
        ):
            return self._build_clarification_decision(
                category="parse_status_scope",
                reason="当前问题需要先确认解析状态码的解释方式，以及结果是看状态数量还是状态占比。",
                clarification_questions=[
                    "请确认这里的 0/1/3/4 是否按当前正式系统的解析状态口径解释。",
                    "请确认是直接输出各状态数量，还是还需要换算占比或继续按承运商 / 省份拆分。",
                ],
                clarification_missing_slots=["status_code_meaning", "result_metric"],
                clarification_template="parse_status_scope",
            )

        # “各任务状态分别是多少”类问题需要先统一统计对象和保留状态范围。
        if any(keyword in compact for keyword in self.STATE_BREAKDOWN_KEYWORDS) and "数量" in compact:
            return self._build_clarification_decision(
                category="state_breakdown_scope",
                reason="当前问题需要先确认统计对象和状态范围，避免把不同任务表混算。",
                clarification_questions=[
                    "请确认统计对象是物流任务表、派车任务表，还是签收结果表。",
                    "请确认是否只统计 2026 年正式系统数据，以及是否保留全部状态还是只看核心状态。",
                ],
                clarification_missing_slots=["table_scope", "status_scope"],
                clarification_template="state_breakdown_scope",
            )

        # allocate_task 各状态数量这类问法也应命中正式状态拆分澄清，而不是回落通用模板。
        if (
            self._extract_year_from_compact(compact) == 2026
            and "allocate_task" in compact
            and "各状态" in compact
            and any(keyword in compact for keyword in ("数量", "分别是多少"))
        ):
            return self._build_clarification_decision(
                category="state_breakdown_scope",
                reason="当前问题需要先确认统计对象是否只看 2026 正式系统 allocate_task，以及结果只输出数量还是还要带占比。",
                clarification_questions=[
                    "请确认这里是否只统计 2026 正式系统里的 allocate_task 数据，不包含测试或历史迁移记录。",
                    "请确认结果只看各状态数量，还是还需要同时输出占比或按省份继续拆分。",
                ],
                clarification_missing_slots=["table_scope", "result_metric"],
                clarification_template="state_breakdown_scope",
            )

        # “某状态最多的是哪些省份/承运商”类问题需要先锁定排序指标和统计对象。
        if (
            self._extract_year_from_compact(compact) == 2026
            and any(keyword in compact for keyword in self.STATE_BREAKDOWN_KEYWORDS)
            and "最多" in compact
            and any(keyword in compact for keyword in ("省份", "省", "承运商"))
        ):
            return self._build_clarification_decision(
                category="state_ranking_scope",
                reason="当前问题需要先确认按数量还是按占比排序，以及统计对象是否只看当前正式系统任务。",
                clarification_questions=[
                    "请确认这里的“最多”是按任务数量排序，还是按该状态任务占比排序。",
                    "请确认是否只统计 2026 正式系统当前状态任务，以及是否还要限定按省份还是承运商展开。",
                ],
                clarification_missing_slots=["aggregation_basis", "statistic_scope", "dimension_split"],
                clarification_template="state_ranking_scope",
            )

        # “单个 ship_task 被拆分最多”类问题需要先确认拆分口径。
        if (
            self._extract_year_from_compact(compact) == 2026
            and "ship_task" in compact
            and "拆分" in compact
            and "最多" in compact
        ):
            return self._build_clarification_decision(
                category="task_split_scope",
                reason="当前问题需要先确认“拆分最多”按什么口径统计，避免把派车任务数、车牌数和承运商数混在一起。",
                clarification_questions=[
                    "请确认这里的“拆分最多”是按关联派车任务数量、关联车牌数量，还是关联承运商数量统计。",
                    "请确认是否只统计 2026 正式系统数据，以及结果是看前几名任务还是完整清单。",
                ],
                clarification_missing_slots=["metric_definition", "statistic_scope"],
                clarification_template="task_split_scope",
            )

        # 回单解析失败最多的承运商，需要先确认失败状态口径和排序指标。
        if (
            self._extract_year_from_compact(compact) == 2026
            and "回单解析失败" in compact
            and "承运商" in compact
            and "最多" in compact
        ):
            return self._build_clarification_decision(
                category="parse_fail_ranking_scope",
                reason="当前问题需要先确认回单解析失败的状态口径和排序指标。",
                clarification_questions=[
                    "请确认“回单解析失败”按哪个解析状态或失败原因口径判断。",
                    "请确认排名按失败任务数量，还是按失败率排序，并说明是否只看 2026 正式系统数据。",
                ],
                clarification_missing_slots=["status_code_meaning", "aggregation_basis", "statistic_scope"],
                clarification_template="parse_fail_ranking_scope",
            )

        # 极短问法没有承接上下文时，必须先追问上下文、指标和时间范围。
        if compact in {"分别是多少", "分别是哪些"}:
            return self._build_clarification_decision(
                category="short_context_scope",
                reason="当前问题缺少上下文，无法判断要分别统计什么指标和维度。",
                clarification_questions=[
                    "请补充要统计的业务对象，例如区域、承运商、运输方式、客户或任务状态。",
                    "请确认结果指标和时间范围，例如发运量 MW、车次、总运费、单瓦成本，以及统计年份或月份。",
                ],
                clarification_missing_slots=["dimension_split", "result_metric", "time_range"],
                clarification_template="short_context_scope",
            )

        # “多少量”虽然符合运量默认瓦数口径，但仍需确认主体和展示单位，避免误把客户 / 承运商 / 全量混在一起。
        if any(keyword in compact for keyword in ("多少量", "发运合计多少量", "发运多少量")):
            return self._build_clarification_decision(
                category="shipment_quantity_scope",
                reason="当前问题需要先确认统计主体和展示单位，避免把全量、客户或承运商口径混在一起。",
                clarification_questions=[
                    "请确认这里的“量”按默认瓦数口径统计，并说明是否用 MW 展示。",
                    "请确认统计主体是全量物流发运、某个客户，还是某个承运商 / 物流公司。",
                ],
                clarification_missing_slots=["metric_definition", "dimension_split"],
                clarification_template="shipment_quantity_scope",
            )

        # 历史承运商全年平均单瓦运输成本需要先确认承运商识别和费用口径。
        if (
            self._extract_year_from_compact(compact) in {2023, 2024, 2025}
            and "全年平均单瓦运输成本" in compact
        ):
            return self._build_clarification_decision(
                category="carrier_unit_fee_scope",
                reason="当前问题需要先确认主体是承运商还是客户，以及单瓦成本是否包含额外费用。",
                clarification_questions=[
                    "请确认题目里的公司名称按承运商 / 物流公司统计，还是按客户名称统计。",
                    "请确认平均单瓦运输成本按总运费除以总瓦数计算，且是否把额外费用一起计入。",
                ],
                clarification_missing_slots=["dimension_split", "fee_scope", "metric_definition"],
                clarification_template="carrier_unit_fee_scope",
            )

        # “各省/各城市/分别是多少”类问题如果只给了分组方向、没有稳定统计口径，先要求补充。
        if (
            any(keyword in compact for keyword in self.BREAKDOWN_KEYWORDS)
            and "分别" in compact
            and any(keyword in compact for keyword in ("各省", "各城市", "各运输方式", "各采购方式", "填充率", "前十个省份"))
            and "平均元/瓦" not in compact
            and "按成本从低到高排序" not in compact
        ):
            return self._build_clarification_decision(
                category="breakdown_scope",
                reason="当前问题需要先明确分组维度和结果指标，才能稳定输出拆分结果。",
                clarification_questions=[
                    "请确认要按哪个主维度展开，例如省份、城市、运输方式、采购方式或送达省份。",
                    "请确认结果指标，例如发运量（MW）、件数、车次、总费用或填充率。",
                ],
                clarification_missing_slots=["dimension_split", "result_metric"],
                clarification_template="breakdown_scope",
            )

        # 成本、运费、签收率等问题如果没有明确时间范围，先追问，不直接跨年混算。
        if (
            any(keyword in compact for keyword in self.COST_METRIC_KEYWORDS)
            and not self._contains_year_or_time_hint(compact)
            and any(keyword in compact for keyword in ("省", "市", "客户", "承运商", "物流公司", "始发地", "基地"))
        ):
            return self._build_clarification_decision(
                category="missing_time_for_metric",
                reason="当前问题缺少明确的时间范围，需先补充年份或统计周期。",
                clarification_questions=[
                    "请确认统计时间，例如 2023 年、2024 年、2025 年，或按 2023–2025 历史累计统计。",
                    "如题目里的“历史发运”是指台账口径，请明确是否只看 2023–2025 历史台账，不包含 2026 正式系统数据。",
                ],
                clarification_missing_slots=["time_range", "source_scope"],
                clarification_template="missing_time_for_metric",
            )

        return None

    def _extract_year_from_compact(self, compact: str) -> int | None:
        """从紧凑问句里提取年份。

        说明：
            1. 题库策略层也需要识别“2026运量综合”这类不带空格的写法；
            2. 当前只识别物流一期锁定的 2023–2026 年；
            3. 没有明确年份时返回 None。
        """
        direct_match = re.search(r"(?<!\d)(20(?:23|24|25|26))(?!\d)", compact)
        if direct_match:
            return int(direct_match.group(1))
        with_suffix_match = re.search(r"(\d{2,4})年", compact)
        if not with_suffix_match:
            return None
        raw_year = with_suffix_match.group(1)
        if len(raw_year) == 2 and raw_year in {"23", "24", "25", "26"}:
            return int(f"20{raw_year}")
        if len(raw_year) == 4:
            return int(raw_year)
        return None

    def _is_past_trend_display_request(self, compact: str) -> bool:
        """判断“趋势”是否只是已发生数据的展示方式。

        参数：
            compact: 已压缩空白的用户问题。

        返回：
            明确给出年份和月份，并要求图表/趋势展示时返回 True。

        说明：
            该判断只豁免已发生数据的展示诉求；未来、预测、预估等仍保持 C 类拒答。
        """

        if any(keyword in compact for keyword in ("预测", "预估", "预计", "估算", "将会", "未来", "下个月", "后续")):
            return False
        year = self._extract_year_from_compact(compact)
        if year not in {2023, 2024, 2025, 2026}:
            return False
        month_token = r"(?:1[0-2]|[1-9]|十一|十二|十|[一二两三四五六七八九])"
        has_month = bool(re.search(rf"{month_token}月份?", compact))
        has_metric = any(keyword in compact for keyword in ("运量", "发运量", "发货量", "承运量", "运费", "费用", "车次"))
        has_display_request = any(keyword in compact for keyword in ("趋势", "折线图", "趋势图", "柱状图", "按月", "月度"))
        return has_month and has_metric and has_display_request

    def _extract_vehicle_type_from_compact(self, compact: str) -> str | None:
        """轻量提取策略层用到的车型别名。"""
        for alias in ("17.5", "17.5车", "17米五", "17米5", "13m", "13米"):
            if alias in compact:
                return alias
        return None

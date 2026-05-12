from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from backend.app.core.config import settings
from backend.app.domains.logistics.schemas.llm_understanding import LogisticsLlmUnderstandingResult


class LogisticsLlmUnderstandingService:
    """物流域 LLM 理解层服务。

    说明：
        1. 当前服务只做语言理解层 PoC，不参与最终 SQL 执行；
        2. LLM 只能输出语义理解候选，最终裁决仍由现有规则 planner 与 data-qa 主链路完成；
        3. 若 LLM 配置缺失或调用失败，必须显式返回 disabled / error，而不是伪造成功结果。
    """

    QUERY_KEY_WHITELIST: dict[str, str] = {
        "hist_total_fee_city_rank": "指定年份和省份，按城市统计总费用并做前 N 排名。",
        "hist_avg_fee_by_month": "指定年份、始发地、目的省和车型，按月份统计平均运费。",
        "hist_avg_fee_per_watt_by_transport": "指定区域，按运输方式统计平均元/瓦并排序。",
        "hist_extra_fee_ratio_peak_month": "指定年份，找出额外费用占总费用比重最高的月份。",
        "hist_total_fee_by_origin_and_carrier": "指定年份、始发地和承运商，统计总运费。",
        "hist_total_fee_summary": "历史台账中，按年份、月份、区域、运输方式、承运商或客户统计总运费。",
        "hist_total_fee_by_province": "历史台账中，按年份和省份统计总运费。",
        "hist_monthly_total_fee_by_year": "历史台账中，按年份统计各月总运费。",
        "hist_mw_summary": "历史台账中，按年份、区域、省份、客户或承运商等条件统计发运量 MW。",
        "hist_mw_by_all_regions": "历史台账中，按区域统计发运量 MW 分布。",
        "hist_mw_by_region_province": "历史台账中，按区域和省份统计发运量 MW。",
        "hist_mw_by_origin_and_carrier": "历史台账中，按始发地和承运商统计发运量 MW。",
        "hist_customer_mw_ranking": "历史台账中，按客户统计发运量 MW 排名。",
        "hist_top_customers_fee_and_mw_by_province": "历史台账中，指定省份下按客户统计运费和发运量排名。",
        "hist_carrier_kpi_by_year": "历史台账中，按年份和承运商统计运量、运费、车次等经营指标。",
        "hist_route_pricing_analysis": "历史台账中，按线路、始发地、目的地、车型等条件分析运价或单车均费。",
        "hist_city_carrier_avg_fee_per_trip": "历史台账中，按城市和承运商统计平均单车运费。",
        "hist_unit_fee_per_watt": "历史台账中，按条件统计单瓦运输成本。",
        "sys_mw_and_trip_count": "2026 系统数据中，按月份统计总发运量 MW 与总车次。",
        "sys_total_fee_by_filters": "2026 系统数据中，按月份、区域、省份、客户、承运商、运输方式等条件统计总费用。",
        "sys_unit_fee_per_watt": "2026 系统数据中，按月份或累计范围统计单瓦运输成本。",
        "sys_mw_by_procurement_type": "2026 系统数据中，按采购方式统计发运量 MW。",
        "sys_task_count_ranking": "2026 系统数据中，按承运商、区域或状态统计任务量排名。",
        "sys_parse_success_rate_by_carrier": "2026 系统数据中，按承运商统计解析成功率。",
        "sys_extra_cost_audited_concentration": "2026 系统数据中，统计已审核额外费用集中度。",
        "sys_delivery_distance_fill_rate_by_province": "2026 系统数据中，按省份统计送达距离填充率。",
        "sys_company_mapping_gap": "2026 系统数据中，识别承运商公司映射缺口。",
        "hist_trip_count_by_region": "历史台账中，按区域统计总车次。",
        "hist_quantity_by_region": "历史台账中，按区域统计总发运件数。",
        "hist_customer_mw": "历史台账中，按客户/项目统计发运量 MW。",
        "hist_vehicle_type_trip_count": "历史台账中，按车型统计总车次。",
        "sys_signedfor_rate_by_carrier": "2026 系统数据中，按承运商统计 SIGNEDFOR 签收率并给出前十/后十。",
        "hist_multi_origin_customers": "历史台账中，统计同一客户由多个始发地发货的客户数量与名单。",
        "sys_companies_without_tasks": "识别已建档但 2026 年没有任何任务的承运商。",
        "hist_plan_actual_deviation": "按区域统计计划发运件数与实际发运件数偏差率。",
        "sys_special_total_fee": "2026 系统数据中，按特殊业务口径统计总费用。",
        "carrier_metric_ranking": "按承运商统计指定指标并排名，例如运量、运费、车次、签收率或单瓦成本。",
        "composite_decomposed": "综合型问题的顶层 LLM 拆分结果；必须在 filters.sub_plans 中给出独立子问题、query_key、source_clause 和 filters，后端只回构受控子查询。",
    }
    B_CLARIFICATION_HINT_KEYWORDS = ("最近", "近期", "最差", "异常", "有没有问题", "哪些有问题", "分别是多少")

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        client: Any | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        """初始化 LLM 理解层。

        参数：
            base_url: 可选的 LLM 服务地址，默认读取 settings。
            api_key: 可选的 LLM 密钥，默认读取 settings。
            model: 可选的模型名，默认读取 settings。
            client: 测试时可注入假的 OpenAI 客户端，避免真实外部调用。
        """

        self.base_url = base_url if base_url is not None else settings.llm_base_url
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self.model = model if model is not None else settings.llm_model
        self._client = client
        self.timeout_seconds = timeout_seconds

    def is_enabled(self) -> bool:
        """判断当前环境是否具备真实 LLM 调用配置。"""
        return bool(self.base_url and self.api_key and self.model)

    def understand(
        self,
        question: str,
        *,
        allowed_query_keys: list[str] | None = None,
    ) -> LogisticsLlmUnderstandingResult:
        """执行一次 LLM 理解。

        说明：
            1. 这里只输出候选理解结果，不直接进入 SQL；
            2. allowed_query_keys 用于限制候选 query_key 白名单；
            3. 若调用失败，返回 error 模式，便于 PoC 报告识别误判和可用性。
        """

        normalized_question = question.strip()
        whitelist = allowed_query_keys or list(self.QUERY_KEY_WHITELIST.keys())
        if not self.is_enabled():
            return LogisticsLlmUnderstandingResult(
                normalized_question=normalized_question,
                intent="unknown",
                provider_mode="disabled",
                provider_error="当前环境未配置可用的 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL。",
            )

        last_error: Exception | None = None
        for _ in range(2):
            try:
                client = self._client or OpenAI(
                    base_url=self.base_url,
                    api_key=self.api_key,
                    timeout=self.timeout_seconds,
                    max_retries=0,
                )
                completion = client.chat.completions.create(
                    model=self.model,
                    temperature=0,
                    messages=[
                        {"role": "system", "content": self._build_system_prompt(whitelist)},
                        {"role": "user", "content": self._build_user_prompt(normalized_question, whitelist)},
                    ],
                )
                content = completion.choices[0].message.content or "{}"
                payload = self._extract_json(content)
                return self._normalize_payload(
                    question=normalized_question,
                    payload=payload,
                    whitelist=whitelist,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        return LogisticsLlmUnderstandingResult(
            normalized_question=normalized_question,
            intent="unknown",
            provider_mode="error",
            provider_error=str(last_error) if last_error else "unknown llm error",
            llm_model_name=self.model or None,
        )

    def _build_system_prompt(self, whitelist: list[str]) -> str:
        """构建系统提示词。"""
        query_key_lines = "\n".join(
            f"- {query_key}: {self.QUERY_KEY_WHITELIST[query_key]}"
            for query_key in whitelist
            if query_key in self.QUERY_KEY_WHITELIST
        )
        return (
            "你是物流数据问答系统的“语言理解层”。\n"
            "你的任务只包括：语义理解、术语归一、槽位抽取、意图识别、query_key 候选生成、澄清问题草案。\n"
            "你绝对不能直接查数据库，不能输出 SQL，不能计算最终数值，不能编造业务答案。\n"
            "如果问题条件不足，应输出 needs_clarification=true。\n"
            "如果问题超出当前能力边界，应输出 unsupported，并给出业务可理解原因。\n"
            "非常重要：\n"
            "1. 如果问题本质上是“缺时间范围、缺统计口径、缺评价标准、缺异常定义、缺拆分维度”，必须优先输出 clarification，而不是 unsupported。\n"
            "2. 只有真正超出当前结构化数据问答边界时，才允许输出 unsupported。\n"
            "3. 不要因为问题口语化、模糊或缺少口径，就直接判 unsupported。\n"
            "候选 query_key 只能从下面白名单里选择；如果不确定，可以返回空数组并降低 confidence。\n"
            "输出必须是单个 JSON 对象，不要输出 markdown，不要输出解释。\n"
            "当前白名单 query_key 如下：\n"
            f"{query_key_lines}\n"
            "术语归一参考：\n"
            "- 发运量/运量/发货量/承运量 -> 发运量\n"
            "- 总费用/总运费/运费 -> 运费\n"
            "- 单瓦价/元瓦/单瓦运输成本 -> 元/瓦\n"
            "- 车次/车辆数/发了多少车 -> 车次\n"
            "- 物流公司/承运商/物流供应商 -> 承运商\n"
            "- 17.5/17米五/17.5车 -> 17.5\n"
            "不支持边界参考：预测、趋势、波动区间、ETA、到货时间、复杂时效推理、开放讨论、方案设计、额外费用项目/原因/明细。\n"
            "典型示例：\n"
            "- “设计一个在途风险评分模型” -> unsupported，原因是当前不做模型设计或治理方案讨论。\n"
            "- “哪些额外费用项目最多？分别是什么原因？” -> unsupported，原因是当前只支持额外费用总额，不支持项目/原因/明细。\n"
            "- “江苏省历史发运的总费用是多少？” -> clarification，优先追问具体年份，以及是否只看 2023–2025 历史台账。\n"
            "- “哪个承运商最差？” -> clarification，优先追问时间范围和评价标准，例如签收率、费用或异常率。\n"
            "- “最近物流成本是不是变高了？” -> clarification，优先追问时间范围，以及按总费用、单瓦成本还是签收率判断。\n"
            "- “华东区域2025年各省发运量分别是多少” -> clarification，优先追问按 MW 还是件数统计，并确认是否按省份拆分展示。\n"
            "- “华东发运有没有异常？” -> clarification，优先追问异常按什么标准定义，例如签收率、费用偏离还是计划达成率。\n"
            "综合型问题拆分要求：\n"
            "- 当一个问题包含多个可独立回答的顶层子问时，可以选择 composite_decomposed；这一步必须由你基于语义判断，不要照抄关键词。\n"
            "- composite_decomposed 只表示拆分意图，不表示最终答案；后端会按白名单重新校验和计算。\n"
            "- filters.decomposition_strategy 必须为 top_level_conjunction。\n"
            "- filters.sub_plans 必须是数组，每项包含 source_clause、query_key、intent、metrics、dimensions、filters。\n"
            "- 当前可用于子计划的已审计示例：hist_high_fee_addresses_by_customer（历史客户高运费收货地址），sys_mw_by_procurement_type（2026 采购方式发运量 MW）。\n"
            "- 如果第二个子问明显回指“这些地址/上述地址/上面的地址”等前一个子结果，或用户明确要求吨口径，不要输出 composite_decomposed，应输出 clarification/unsupported。\n"
            "JSON 字段必须包含：normalized_question,intent,metrics,dimensions,filters,time_range,source_scope,candidate_query_keys,normalized_terms,needs_clarification,clarification_questions,unsupported_reason,confidence"
        )

    def _build_user_prompt(self, question: str, whitelist: list[str]) -> str:
        """构建用户提示词。"""
        return (
            f"原始问题：{question}\n"
            f"允许的 query_key 数量：{len(whitelist)}\n"
            "请按 JSON 输出理解结果。"
        )

    def _extract_json(self, content: str) -> dict[str, Any]:
        """从模型返回文本中提取 JSON。"""
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
            stripped = re.sub(r"\s*```$", "", stripped)
        match = re.search(r"\{.*\}", stripped, flags=re.S)
        json_text = match.group(0) if match else stripped
        parsed = json.loads(json_text)
        return parsed if isinstance(parsed, dict) else {}

    def _normalize_payload(
        self,
        *,
        question: str,
        payload: dict[str, Any],
        whitelist: list[str],
    ) -> LogisticsLlmUnderstandingResult:
        """对模型输出做白名单清洗和字段兜底。"""
        candidate_query_keys = [
            item
            for item in payload.get("candidate_query_keys", [])
            if isinstance(item, str) and item in whitelist
        ]
        confidence = payload.get("confidence", 0.0)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except Exception:  # noqa: BLE001
            confidence = 0.0

        intent = payload.get("intent", "unknown")
        if intent not in {"aggregate", "ranking", "comparison", "detail", "composite", "clarification", "unsupported", "unknown"}:
            intent = "unknown"

        source_scope = payload.get("source_scope", "unknown")
        if source_scope not in {"historical", "system_2026", "mixed", "unknown"}:
            source_scope = "unknown"

        normalized_terms = payload.get("normalized_terms", {})
        if not isinstance(normalized_terms, dict):
            normalized_terms = {}

        clarification_questions = payload.get("clarification_questions", [])
        if not isinstance(clarification_questions, list):
            clarification_questions = []
        clarification_questions = [item for item in clarification_questions if isinstance(item, str)]
        unsupported_reason = payload.get("unsupported_reason")
        needs_clarification = bool(payload.get("needs_clarification", False))

        # 如果模型已经明确给出不支持原因，则统一收敛为 unsupported，避免一条结果同时落到澄清和不支持。
        if unsupported_reason:
            intent = "unsupported"
            needs_clarification = False
            clarification_questions = []

        normalized_question = str(payload.get("normalized_question") or question).strip()
        # 对高频 B 类模糊问法做理解层后处理：
        # 如果模型把明显的“缺口径”问题误判成 unsupported，则统一拉回 clarification。
        if self._should_convert_unsupported_to_clarification(
            question=normalized_question,
            unsupported_reason=unsupported_reason,
            candidate_query_keys=candidate_query_keys,
        ):
            intent = "clarification"
            needs_clarification = True
            unsupported_reason = None
            clarification_questions = self._build_business_clarification_questions(normalized_question)

        # 对稳定 A 类 query_key，如果模型同时给出高置信单候选又保留澄清标记，
        # 统一收敛成“候选增强可用”，避免因为模型过度保守而丢掉明显可识别的同构变体。
        if (
            len(candidate_query_keys) == 1
            and candidate_query_keys[0] in self.QUERY_KEY_WHITELIST
            and confidence >= 0.9
            and not unsupported_reason
            and needs_clarification
        ):
            needs_clarification = False
            clarification_questions = []

        return LogisticsLlmUnderstandingResult(
            normalized_question=normalized_question,
            intent=intent,
            metrics=[item for item in payload.get("metrics", []) if isinstance(item, str)],
            dimensions=[item for item in payload.get("dimensions", []) if isinstance(item, str)],
            filters=payload.get("filters", {}) if isinstance(payload.get("filters", {}), dict) else {},
            time_range=payload.get("time_range", {}) if isinstance(payload.get("time_range", {}), dict) else {},
            source_scope=source_scope,
            candidate_query_keys=candidate_query_keys,
            normalized_terms={str(key): str(value) for key, value in normalized_terms.items()},
            needs_clarification=needs_clarification,
            clarification_questions=clarification_questions,
            unsupported_reason=unsupported_reason,
            confidence=confidence,
            provider_mode="live",
            llm_model_name=self.model or None,
        )

    def _should_convert_unsupported_to_clarification(
        self,
        *,
        question: str,
        unsupported_reason: str | None,
        candidate_query_keys: list[str],
    ) -> bool:
        """判断是否应把 unsupported 拉回业务化澄清。

        说明：
            1. 当前只处理高频 B 类口径缺失题；
            2. 如果模型已经给出明确 query_key 候选，则不做强制拉回；
            3. 预测、ETA、额外费用明细、设计类问题仍保持 unsupported。
        """

        compact = re.sub(r"\s+", "", question)
        if not unsupported_reason or candidate_query_keys:
            return False
        if any(keyword in compact for keyword in ("预测", "预估", "预计", "未来", "ETA", "到达时间", "额外费用项目", "额外费用原因", "设计一个", "评分模型", "风险评分模型")):
            return False
        return any(keyword in compact for keyword in self.B_CLARIFICATION_HINT_KEYWORDS)

    def _build_business_clarification_questions(self, question: str) -> list[str]:
        """为高频 B 类模糊题生成更业务化的澄清问题。"""

        compact = re.sub(r"\s+", "", question)
        if "最近" in compact or "近期" in compact:
            return [
                "请先明确时间范围，例如近7天、近30天、本月或今年。",
                "请确认要看哪类指标，例如总费用、单瓦成本、签收率或异常率。",
            ]
        if "最差" in compact:
            return [
                "请确认统计时间范围，例如 2025 年、2026 年或近30天。",
                "请确认“最差”按什么标准判断，例如签收率最低、费用最高还是异常率最高。",
            ]
        if "异常" in compact or "有没有问题" in compact or "哪些有问题" in compact:
            return [
                "请确认时间范围，例如 2025 年、2026 年或近30天。",
                "请确认异常按什么标准定义，例如签收率偏低、费用偏高、计划达成率偏低或车次异常。",
            ]
        if "分别是多少" in compact:
            return [
                "请确认拆分维度，例如按省份、城市、运输方式或采购方式展开。",
                "请确认结果指标，例如按 MW、件数、车次或总费用统计。",
            ]
        return [
            "请先明确时间范围，便于系统按统一口径查询。",
            "请补充统计指标或判断标准，避免误算。",
        ]

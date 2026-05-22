from __future__ import annotations

from collections.abc import Iterable
import re

from backend.app.domains.business_qa_graph.schemas.domain import (
    BusinessQaCapabilityDefinition,
    BusinessQaCapabilityId,
    BusinessQaDomainDefinition,
    BusinessQaDomainRouteCandidate,
    BusinessQaDomainRouteResult,
    BusinessQaNormalizedDomainHint,
    BusinessQaRoutableDomainId,
)


class BusinessQaDomainRegistry:
    """统一业务问数领域与 capability 注册表。

    参数：无。
    返回：
        可执行领域识别、capability 查询和澄清候选生成的 registry 实例。
    业务逻辑：
        LQG-2 只做外层领域路由与能力标记；所有能力最终仍必须交给既有受控领域服务执行。
    """

    _LOGISTICS_KEYWORDS = (
        "物流",
        "发运",
        "发货",
        "出货",
        "运量",
        "发运量",
        "运费",
        "运输费",
        "承运商",
        "物流公司",
        "车次",
        "线路",
        "始发",
        "目的地",
        "到货地址",
        "单价/车",
        "均价",
    )
    _PLAN_BOM_KEYWORDS = (
        "bom",
        "计划bom",
        "评审号",
        "版型",
        "版型号",
        "订单号",
        "物料编码",
        "玻璃",
        "胶膜",
        "间隙贴膜",
        "焊带",
        "接线盒",
        "汇流条",
        "边框",
        "背板",
        "组件配置",
        "bom配置",
    )
    _POWER_KEYWORDS = (
        "功率",
        "瓦",
        "档位",
        "功率档",
        "效率段",
        "标板",
        "电池片",
        "供应商效率",
        "目标功率",
        "目标比例",
    )
    _POWER_FACTOR_COMPARE_KEYWORDS = ("影响值", "配置影响", "差异", "对比", "比较", "区别", "相差")
    _POWER_SUPPLIER_RECOMMEND_KEYWORDS = ("推荐", "供应商", "电池片", "目标功率", "目标比例", "比例")
    _POWER_UNIT_PATTERN = re.compile(r"\d+(?:\.\d+)?(?:w|瓦)")

    def __init__(self) -> None:
        self._capabilities = self._build_capabilities()
        self._domains = self._build_domains()

    @classmethod
    def default(cls) -> "BusinessQaDomainRegistry":
        """构造默认 registry。

        参数：无。
        返回：
            默认领域注册表。
        业务逻辑：
            当前实现无外部依赖，直接构造即可；后续可替换为配置/语义目录加载。
        """

        return cls()

    def list_domains(self) -> tuple[BusinessQaDomainDefinition, ...]:
        """列出 LQG-2 已开放的业务域。

        参数：无。
        返回：
            按稳定顺序返回 logistics、plan_bom 两个域定义。
        业务逻辑：
            unknown 是路由结果，不是可执行业务域，因此不出现在 domain registry 中。
        """

        return tuple(self._domains.values())

    def list_capabilities(self) -> tuple[BusinessQaCapabilityDefinition, ...]:
        """列出当前 registry 中的 capability 白名单。

        参数：无。
        返回：
            所有可被 Graph 标记的受控 capability 定义。
        业务逻辑：
            这里只暴露能力元数据，不授予执行权限，也不构造实际 service。
        """

        return tuple(self._capabilities.values())

    def get_capability(self, capability: BusinessQaCapabilityId) -> BusinessQaCapabilityDefinition:
        """获取指定 capability 定义。

        参数：
            capability: capability 稳定标识。
        返回：
            对应 capability 定义。
        业务逻辑：
            未注册 capability 会自然抛出 KeyError，防止后续 adapter 误用未授权能力。
        """

        return self._capabilities[capability]

    def route(self, question: str, *, domain_hint: str | None = None) -> BusinessQaDomainRouteResult:
        """根据问题和可选 domain_hint 执行领域路由。

        参数：
            question: 用户原始问题。
            domain_hint: 可选领域提示，支持 auto/logistics/plan_bom 及少量中文别名。
        返回：
            领域路由结果；无法识别时返回 CLARIFY + 候选域。
        业务逻辑：
            路由只使用 registry 与确定性关键词启发式兜底，不调用 LLM、不查库、不计算事实。
        """

        normalized_question = self._normalize_text(question)
        normalized_hint = self.normalize_domain_hint(domain_hint)
        if normalized_hint == "unknown":
            return self._clarify(
                requested_domain=domain_hint,
                normalized_hint=normalized_hint,
                reason="调用方提供的 domain_hint 不在 auto/logistics/plan_bom 白名单内。",
            )

        if normalized_hint in {"logistics", "plan_bom"}:
            return self._routed(
                domain=normalized_hint,
                question=normalized_question,
                requested_domain=domain_hint,
                normalized_hint=normalized_hint,
                confidence=0.95,
                reason="调用方显式提供受支持业务域，按白名单直接路由。",
            )

        detected_domain, confidence, reason = self._detect_domain(normalized_question)
        if detected_domain is None:
            return self._clarify(
                requested_domain=domain_hint,
                normalized_hint=normalized_hint,
                reason=reason,
            )
        return self._routed(
            domain=detected_domain,
            question=normalized_question,
            requested_domain=domain_hint,
            normalized_hint=normalized_hint,
            confidence=confidence,
            reason=reason,
        )

    def normalize_domain_hint(self, domain_hint: str | None) -> BusinessQaNormalizedDomainHint:
        """归一化调用方领域提示。

        参数：
            domain_hint: 调用方传入的领域提示。
        返回：
            auto/logistics/plan_bom/unknown 之一。
        业务逻辑：
            功率相关 hint 归并到 plan_bom，避免出现独立 power 前端域或执行域。
        """

        if domain_hint is None:
            return "auto"
        hint = self._normalize_text(domain_hint)
        aliases: dict[str, BusinessQaNormalizedDomainHint] = {
            "": "auto",
            "auto": "auto",
            "自动": "auto",
            "自动识别": "auto",
            "logistics": "logistics",
            "logistic": "logistics",
            "物流": "logistics",
            "plan_bom": "plan_bom",
            "plan-bom": "plan_bom",
            "planbom": "plan_bom",
            "bom": "plan_bom",
            "计划bom": "plan_bom",
            "计划": "plan_bom",
            "power": "plan_bom",
            "plan_power": "plan_bom",
            "功率": "plan_bom",
        }
        return aliases.get(hint, "unknown")

    def clarify_candidates(self) -> tuple[BusinessQaDomainRouteCandidate, ...]:
        """生成无法识别时的澄清候选。

        参数：无。
        返回：
            logistics 与 plan_bom 两个候选，顺序稳定。
        业务逻辑：
            只返回当前 registry 已开放域，避免将未知问题导向未接入的旧域或远期域。
        """

        return tuple(
            BusinessQaDomainRouteCandidate(
                domain=domain.domain,
                label=domain.label,
                capabilities=domain.capabilities,
                reason=domain.description,
            )
            for domain in self.list_domains()
        )

    def _detect_domain(self, question: str) -> tuple[BusinessQaRoutableDomainId | None, float, str]:
        """使用确定性启发式识别业务域。

        参数：
            question: 已归一化的问题文本。
        返回：
            (领域, 置信度, 原因)；无法安全识别时领域为 None。
        业务逻辑：
            得分相同或无命中都 fail-closed，交给澄清节点，而不是默认路由到某个旧域。
        """

        logistics_score = self._keyword_score(question, self._LOGISTICS_KEYWORDS)
        plan_bom_score = self._keyword_score(question, self._PLAN_BOM_KEYWORDS)
        if self._has_power_signal(question):
            plan_bom_score += 3

        if logistics_score == 0 and plan_bom_score == 0:
            return None, 0.0, "问题未命中 logistics 或 plan_bom 的安全识别特征。"
        if logistics_score == plan_bom_score:
            return None, 0.0, "问题同时命中多个业务域且置信度相近，需要用户澄清。"

        if logistics_score > plan_bom_score:
            confidence = min(0.95, 0.72 + logistics_score * 0.04)
            return "logistics", confidence, "问题命中物流域发运、运费、承运商或线路等特征。"

        confidence = min(0.95, 0.72 + plan_bom_score * 0.04)
        return "plan_bom", confidence, "问题命中计划 BOM 或功率预测相关特征。"

    def _routed(
        self,
        *,
        domain: BusinessQaRoutableDomainId,
        question: str,
        requested_domain: str | None,
        normalized_hint: BusinessQaNormalizedDomainHint,
        confidence: float,
        reason: str,
    ) -> BusinessQaDomainRouteResult:
        """构造已路由结果。

        参数：
            domain: 已确定业务域。
            question: 已归一化问题。
            requested_domain: 原始领域提示。
            normalized_hint: 归一化领域提示。
            confidence: 路由置信度。
            reason: 内部审计原因。
        返回：
            ROUTED 结果。
        业务逻辑：
            capability 按业务域和问题特征选择；功率 capability 仍标记为 plan_bom 域。
        """

        capabilities = self._select_capabilities(domain, question)
        capability_domain = self._capabilities[capabilities[0]].domain if capabilities else "unknown"
        return BusinessQaDomainRouteResult(
            status="ROUTED",
            requested_domain=requested_domain,
            normalized_domain_hint=normalized_hint,
            domain=domain,
            confidence=confidence,
            capabilities=capabilities,
            capability_domain=capability_domain,
            reason=reason,
        )

    def _clarify(
        self,
        *,
        requested_domain: str | None,
        normalized_hint: BusinessQaNormalizedDomainHint,
        reason: str,
    ) -> BusinessQaDomainRouteResult:
        """构造需要澄清的路由结果。

        参数：
            requested_domain: 原始领域提示。
            normalized_hint: 归一化领域提示。
            reason: 需要澄清的内部原因。
        返回：
            CLARIFY 结果，附带安全候选域。
        业务逻辑：
            unknown 不携带 capability，后续节点不能继续查数或计算。
        """

        return BusinessQaDomainRouteResult(
            status="CLARIFY",
            requested_domain=requested_domain,
            normalized_domain_hint=normalized_hint,
            domain="unknown",
            confidence=0.0,
            capabilities=(),
            capability_domain="unknown",
            reason=reason,
            clarify_candidates=self.clarify_candidates(),
        )

    def _select_capabilities(
        self,
        domain: BusinessQaRoutableDomainId,
        question: str,
    ) -> tuple[BusinessQaCapabilityId, ...]:
        """按业务域和问题特征选择 capability。

        参数：
            domain: 已识别业务域。
            question: 已归一化问题。
        返回：
            capability 元组。
        业务逻辑：
            物流域当前只暴露 logistics_data_qa；计划 BOM 域根据功率语义再细分三个 plan_power 子能力。
        """

        if domain == "logistics":
            return ("logistics_data_qa",)
        if not self._has_any(question, self._POWER_KEYWORDS):
            return ("plan_bom_qa",)
        if self._has_any(question, self._POWER_FACTOR_COMPARE_KEYWORDS):
            return ("plan_power_factor_effect_compare",)
        if self._has_any(question, self._POWER_SUPPLIER_RECOMMEND_KEYWORDS):
            return ("plan_power_supplier_recommendation",)
        return ("plan_power_prediction",)

    def _build_domains(self) -> dict[BusinessQaRoutableDomainId, BusinessQaDomainDefinition]:
        """构建默认业务域定义。

        参数：无。
        返回：
            按插入顺序保存的业务域定义字典。
        业务逻辑：
            只注册当前卡范围内可观测、可澄清的两个业务域。
        """

        return {
            "logistics": BusinessQaDomainDefinition(
                domain="logistics",
                label="物流问数",
                description="处理发运、运费、承运商、线路、车次、目的地等物流问数。",
                capabilities=("logistics_data_qa",),
            ),
            "plan_bom": BusinessQaDomainDefinition(
                domain="plan_bom",
                label="计划 BOM 问数",
                description="处理计划 BOM 查询、BOM 配置消歧，以及归属计划 BOM 的功率预测/推荐/影响值对比。",
                capabilities=(
                    "plan_bom_qa",
                    "plan_power_prediction",
                    "plan_power_supplier_recommendation",
                    "plan_power_factor_effect_compare",
                ),
            ),
        }

    def _build_capabilities(self) -> dict[BusinessQaCapabilityId, BusinessQaCapabilityDefinition]:
        """构建默认 capability 定义。

        参数：无。
        返回：
            capability 定义字典。
        业务逻辑：
            executable_service 仅记录后续 adapter 目标，当前节点不会实例化或调用这些服务。
        """

        definitions = (
            BusinessQaCapabilityDefinition(
                capability="logistics_data_qa",
                domain="logistics",
                label="物流数据问答",
                description="调用既有 LogisticsDataQaService 处理物流结构化问数。",
                risk_level="read_only_data_qa",
                executable_service="LogisticsDataQaService",
            ),
            BusinessQaCapabilityDefinition(
                capability="plan_bom_qa",
                domain="plan_bom",
                label="计划 BOM 问答",
                description="调用既有 PlanBomQaService 处理 BOM 查询、消歧和对比。",
                risk_level="read_only_data_qa",
                executable_service="PlanBomQaService",
            ),
            BusinessQaCapabilityDefinition(
                capability="plan_power_prediction",
                domain="plan_bom",
                label="计划 BOM 功率预测",
                description="调用既有功率预测确定性能力处理功率档位分布。",
                risk_level="deterministic_calculation",
                executable_service="PowerPredictionEngine",
            ),
            BusinessQaCapabilityDefinition(
                capability="plan_power_supplier_recommendation",
                domain="plan_bom",
                label="供应商功率匹配推荐",
                description="调用既有供应商功率推荐确定性能力处理目标功率匹配。",
                risk_level="deterministic_calculation",
                executable_service="PowerRecommendationService",
            ),
            BusinessQaCapabilityDefinition(
                capability="plan_power_factor_effect_compare",
                domain="plan_bom",
                label="功率配置影响值对比",
                description="调用既有功率配置影响值对比能力处理同因子选项差异。",
                risk_level="deterministic_calculation",
                executable_service="PlanPowerFactorEffectCompareService",
            ),
        )
        return {definition.capability: definition for definition in definitions}

    @staticmethod
    def _normalize_text(value: str | None) -> str:
        """归一化短文本以便做安全关键词匹配。

        参数：
            value: 原始文本。
        返回：
            小写并去除常见空白后的文本。
        业务逻辑：
            仅用于路由启发式，不改变用户原始问题在 state 中的存储。
        """

        return "".join(str(value or "").lower().split())

    @staticmethod
    def _has_power_signal(text: str) -> bool:
        """判断文本是否包含功率信号 —— 匹配功率关键词或数字+W/瓦 模式。

        参数：
            text: 已归一化文本。
        返回：
            是否包含功率信号。
        业务逻辑：
            1. _POWER_KEYWORDS 已移除单字符 "w" 避免英文误匹配。
            2. 额外匹配 "数字+W" 或 "数字+瓦" 模式（如 615W、620瓦）。
            3. _POWER_UNIT_PATTERN 的 w 匹配是小写的，因为 text 已归一化。
        """

        if BusinessQaDomainRegistry._has_any(text, BusinessQaDomainRegistry._POWER_KEYWORDS):
            return True
        return bool(BusinessQaDomainRegistry._POWER_UNIT_PATTERN.search(text))

    @staticmethod
    def _has_any(text: str, keywords: Iterable[str]) -> bool:
        """判断文本是否命中任一关键词。

        参数：
            text: 已归一化文本。
            keywords: 待匹配关键词。
        返回：
            是否命中。
        业务逻辑：
            简单包含匹配只做安全兜底；识别不充分时会进入澄清而非强行路由。
        """

        return any(BusinessQaDomainRegistry._normalize_text(keyword) in text for keyword in keywords)

    @classmethod
    def _keyword_score(cls, text: str, keywords: Iterable[str]) -> int:
        """计算关键词命中数量。

        参数：
            text: 已归一化文本。
            keywords: 待匹配关键词。
        返回：
            命中关键词数量。
        业务逻辑：
            分数只用于选择候选域，无法拉开差距时必须澄清。
        """

        return sum(1 for keyword in keywords if cls._normalize_text(keyword) in text)

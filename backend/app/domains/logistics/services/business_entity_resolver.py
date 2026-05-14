from __future__ import annotations

import re
from collections.abc import Callable, Sequence

CarrierCandidateProvider = Callable[[], Sequence[str]] | Sequence[str]


class LogisticsBusinessEntityResolver:
    """物流域业务实体解析器。

    说明：
        1. 解析客户、承运商等“会随业务数据变化”的实体时，优先使用候选源；
        2. 候选源可以来自数据库 distinct 结果、测试注入或后续字典服务，避免在 planner 内写死实体白名单；
        3. 对候选源没有覆盖但用户显式写出“某某物流/运输/供应链”的场景，使用受控语法抽取；
        4. 泛词“历史物流/物流发运/各物流公司”会被停用词拦截，避免把结构词误识别成承运商。
    """

    _LEGAL_SUFFIXES = (
        "股份有限公司",
        "有限责任公司",
        "物流有限公司",
        "运输有限公司",
        "供应链有限公司",
        "货运有限公司",
        "速运有限公司",
        "快运有限公司",
        "有限公司",
        "股份公司",
        "集团公司",
        "公司",
    )
    _CARRIER_SUFFIXES = ("物流", "供应链", "运输", "货运", "速运", "快运")
    _CARRIERISH_MARKERS = _CARRIER_SUFFIXES + ("承运",)
    _GENERIC_CARRIER_WORDS = {
        "物流",
        "历史",
        "历史物流",
        "发运",
        "物流发运",
        "运输",
        "承运",
        "公司",
        "供应商",
        "承运商",
        "物流公司",
        "物流供应商",
        "区域",
        "各区域",
        "各省",
        "各城市",
        "全国",
        "全量",
        "全部",
        "所有",
        "不同",
        "各",
        "每个",
        "客户",
        "项目",
        "业务",
        "数据",
        "年",
        "月",
        "当前",
        "累计",
        "总",
    }
    _EXPLICIT_CARRIER_PATTERNS = (
        re.compile(
            r"(?:^|[，,。；;？?])(?:20\d{2}|\d{2})?年?(?P<name>[\u4e00-\u9fa5A-Za-z0-9·（）()]{2,30}?(?:物流|供应链|运输|货运|速运|快运))"
            r"(?=在|的|发运|承运|运费|运输费用|总运费|总费用|承运量|运输量|发货量|各区域|分区域|各省|各城市|占|$)"
        ),
        re.compile(
            r"(?P<name>[\u4e00-\u9fa5A-Za-z0-9·（）()]{2,30}?(?:物流|供应链|运输|货运|速运|快运))"
            r"(?=在各区域|在各省|在各城市|在|的|发运|承运|运费|运输费用|总运费|总费用|承运量|运输量|发货量|占)"
        ),
    )

    def __init__(
        self,
        *,
        historical_carrier_candidate_provider: CarrierCandidateProvider | None = None,
    ) -> None:
        """初始化实体解析器。

        参数：
            historical_carrier_candidate_provider: 历史台账承运商候选源；生产链路通常由仓储层 distinct 查询提供。

        返回：
            无返回值。
        """
        self._historical_carrier_candidate_provider = historical_carrier_candidate_provider
        self._historical_carrier_candidate_cache: list[str] | None = None

    def resolve_historical_carrier_name(self, question: str) -> str | None:
        """解析历史台账承运商名称。

        参数：
            question: 用户问题或压缩后的问题文本。

        返回：
            可交给 logistics_company_name 模糊匹配的承运商关键词；无法安全识别时返回 None。
        """
        compact = self._compact(question)
        candidate_match = self._match_candidate_carrier(compact)
        if candidate_match:
            return candidate_match
        return self._extract_explicit_carrier_phrase(compact)

    def _historical_carrier_candidates(self) -> list[str]:
        """加载并缓存历史承运商候选。

        返回：
            去重后的候选名称列表；候选源异常时返回空列表，避免影响问答主链路。
        """
        if self._historical_carrier_candidate_cache is not None:
            return self._historical_carrier_candidate_cache
        provider = self._historical_carrier_candidate_provider
        if provider is None:
            self._historical_carrier_candidate_cache = []
            return []
        try:
            values = provider() if callable(provider) else provider
        except Exception:
            self._historical_carrier_candidate_cache = []
            return []
        seen: set[str] = set()
        candidates: list[str] = []
        for value in values:
            text = self._normalize_company_text(str(value or ""))
            if not text or text in seen:
                continue
            seen.add(text)
            candidates.append(text)
        self._historical_carrier_candidate_cache = candidates
        return candidates

    def _match_candidate_carrier(self, compact_question: str) -> str | None:
        """基于候选承运商列表做最长别名匹配。"""
        aliases: list[tuple[str, str]] = []
        for candidate in self._historical_carrier_candidates():
            for alias in self._candidate_aliases(candidate):
                aliases.append((alias, self._strip_carrier_suffix(alias)))
        for alias, resolved in sorted(aliases, key=lambda item: len(item[0]), reverse=True):
            if alias in compact_question and self._is_valid_carrier_core(resolved):
                return resolved
        return None

    def _candidate_aliases(self, candidate: str) -> set[str]:
        """为单个候选承运商生成可匹配别名。

        业务逻辑：
            候选来自真实数据，因此可以从“苏州晶茂物流有限公司”派生“苏州晶茂物流 / 苏州晶茂 / 晶茂”；
            但不会派生“物流”等泛词，避免再次形成结构硬编码或过宽误判。
        """
        normalized = self._normalize_company_text(candidate)
        without_legal = self._strip_legal_suffix(normalized)
        core = self._strip_carrier_suffix(without_legal)
        raw_is_carrierish = any(marker in normalized for marker in self._CARRIERISH_MARKERS)
        aliases = {normalized, without_legal, core}
        if raw_is_carrierish:
            for prefix in self._carrier_marker_prefixes(normalized):
                aliases.add(prefix)
                if len(prefix) >= 4:
                    aliases.add(prefix[2:])
            aliases.add(f"{core}物流")
            # 真实承运商常带城市/省份前缀。只有候选本身像承运商时才派生去前缀简称，
            # 避免把普通公司名任意截断成无意义主体。
            if len(core) >= 4:
                aliases.add(core[2:])
                aliases.add(f"{core[2:]}物流")
        return {alias for alias in aliases if self._is_valid_alias(alias)}

    def _extract_explicit_carrier_phrase(self, compact_question: str) -> str | None:
        """从显式“某某物流/运输/供应链”短语中提取承运商关键词。"""
        for pattern in self._EXPLICIT_CARRIER_PATTERNS:
            for match in pattern.finditer(compact_question):
                raw = match.group("name")
                resolved = self._clean_explicit_carrier_name(raw)
                if resolved:
                    return resolved
        return None

    def _carrier_marker_prefixes(self, value: str) -> set[str]:
        """提取行业标记前的公司主体。

        例如：
            - “浙江英赋嘉供应链科技股份有限公司” -> “浙江英赋嘉”；
            - “英赋嘉（浙江）供应链科技有限公司” -> “英赋嘉”。
        """
        prefixes: set[str] = set()
        for marker in self._CARRIER_SUFFIXES:
            index = value.find(marker)
            if index <= 0:
                continue
            prefix = self._strip_parenthetical(value[:index])
            if self._is_valid_carrier_core(prefix):
                prefixes.add(prefix)
        return prefixes

    @staticmethod
    def _strip_parenthetical(value: str) -> str:
        """移除公司名中的括号补充说明。"""
        return re.sub(r"[（(][^）)]*[）)]", "", value)

    def _clean_explicit_carrier_name(self, raw: str) -> str | None:
        """清洗显式承运商短语。"""
        raw_text = self._normalize_company_text(raw)
        # 显式语法只兜底“京东物流/德邦物流”这类短公司名；如果短语里混入年份、范围、结构词，
        # 说明它很可能是“江苏的物流总运费/历史物流”等业务描述，必须拒绝，避免回退成承运商过滤。
        if any(token in raw_text for token in ("年", "月", "到", "至", "从", "的物流", "历史物流", "物流发运")):
            return None
        text = re.sub(r"^(?:请问|请查询|请统计|帮我查一下|帮我看一下|查询|统计)", "", raw_text)
        text = re.sub(r"^\d{1,2}月份?", "", text)
        text = self._strip_carrier_suffix(self._strip_legal_suffix(text))
        if any(token in text for token in ("的", "区域", "历史", "发运", "累计", "全年", "各")):
            return None
        return text if self._is_valid_carrier_core(text) else None

    def _is_valid_alias(self, value: str) -> bool:
        """判断候选别名是否足够具体。"""
        core = self._strip_carrier_suffix(self._strip_legal_suffix(value))
        return bool(value and self._is_valid_carrier_core(core) and value not in self._GENERIC_CARRIER_WORDS)

    def _is_valid_carrier_core(self, value: str) -> bool:
        """判断承运商核心词是否不是泛化结构词。"""
        text = self._normalize_company_text(value)
        if len(text) < 2:
            return False
        if text in self._GENERIC_CARRIER_WORDS:
            return False
        if any(text.endswith(word) and text != word for word in ("各", "所有", "全部", "不同")):
            return False
        if re.fullmatch(r"\d+", text):
            return False
        return True

    def _strip_legal_suffix(self, value: str) -> str:
        """去掉公司法律后缀。"""
        text = value
        changed = True
        while changed:
            changed = False
            for suffix in self._LEGAL_SUFFIXES:
                if text.endswith(suffix) and len(text) > len(suffix):
                    text = text[: -len(suffix)]
                    changed = True
                    break
        return text

    def _strip_carrier_suffix(self, value: str) -> str:
        """去掉物流/运输等承运商行业后缀，返回更适合模糊查询的核心词。"""
        text = value
        for suffix in self._CARRIER_SUFFIXES:
            if text.endswith(suffix) and len(text) > len(suffix):
                return text[: -len(suffix)]
        return text

    @staticmethod
    def _normalize_company_text(value: str) -> str:
        """归一化公司文本。"""
        return re.sub(r"[\s：:，,。？！?、；;\"'“”‘’]+", "", value.strip())

    @staticmethod
    def _compact(question: str) -> str:
        """压缩问句空白。"""
        return re.sub(r"\s+", "", question.strip())

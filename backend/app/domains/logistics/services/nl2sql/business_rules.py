from __future__ import annotations

import re
from datetime import date

from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalog


class LogisticsNl2SqlBusinessRules:
    """物流 NL2SQL 业务规则助手。

    业务逻辑：
        1. 从 Semantic Catalog 读取默认时间、 unsupported 规则和空结果策略；
        2. 只做规则解释，不生成 SQL、不查库、不计算业务答案；
        3. 供 M1 单测和后续 SQLPlan validator 复用。
    """

    def __init__(self, catalog: LogisticsSemanticCatalog) -> None:
        """初始化规则助手。

        参数：
            catalog: 已加载的物流 Semantic Catalog。
        返回：
            无。
        """

        self.catalog = catalog

    def is_unsupported_question(self, question: str) -> bool:
        """判断问题是否命中当前明确不支持的口径。"""

        compact = self._compact(question)
        for rule in self.catalog.rules:
            if rule.action != "reject":
                continue
            if any(self._compact(alias) in compact for alias in rule.aliases):
                return True
        return False

    def resolve_years(self, question: str, *, today: date | None = None) -> list[int]:
        """根据问题和 catalog 规则解析年份。

        参数：
            question: 用户原始问题。
            today: 测试可注入的当前日期；为空时使用系统日期。
        返回：
            年份列表；无显式时间时返回 2023-2026 默认范围。
        """

        current_day = today or date.today()
        compact = self._compact(question)
        current_rule = self.catalog.get_rule("current_year_reference")
        if any(self._compact(alias) in compact for alias in current_rule.aliases):
            return [current_day.year]

        explicit_years = self._extract_years(question)
        if explicit_years:
            return explicit_years

        default_rule = self.catalog.get_rule("default_time_range")
        return [int(year) for year in (default_rule.value or [])]

    def cross_source_years_allowed(self, years: list[int]) -> bool:
        """判断历史侧和 2026 系统侧混合年份是否允许。"""

        rule = self.catalog.get_rule("cross_source_years")
        has_hist = any(year <= 2025 for year in years)
        has_system = any(year >= 2026 for year in years)
        return rule.action == "allow" and has_hist and has_system

    def empty_result_policy(self) -> dict[str, object]:
        """返回空结果策略，后续 SQL 执行层不得静默放宽过滤条件。"""

        rule = self.catalog.get_rule("empty_result_no_relax")
        return {
            "relax_filters": bool(rule.relax_filters),
            "business_message": rule.business_message or "无匹配数据，请调整问题后重试。",
        }

    @staticmethod
    def _extract_years(question: str) -> list[int]:
        """从问题中抽取 2023-2026 四位年份或 23/24/25/26 年。"""

        years: list[int] = []
        for match in re.findall(r"20(?:2[3-6])", question):
            years.append(int(match))
        for match in re.findall(r"(?<!\d)(2[3-6])\s*年", question):
            years.append(2000 + int(match))
        return LogisticsNl2SqlBusinessRules._dedupe_years(years)

    @staticmethod
    def _dedupe_years(years: list[int]) -> list[int]:
        """保持顺序去重年份。"""

        result: list[int] = []
        seen: set[int] = set()
        for year in years:
            if year not in seen:
                seen.add(year)
                result.append(year)
        return result

    @staticmethod
    def _compact(text: str) -> str:
        """压缩空白并统一大小写，便于中文口径匹配。"""

        return "".join(str(text).strip().lower().split())


__all__ = ["LogisticsNl2SqlBusinessRules"]

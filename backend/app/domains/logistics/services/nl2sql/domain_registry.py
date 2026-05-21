"""NL2SQL 域注册表——管理各域的 catalog 加载和路由判断。

设计原则：
1. 每个业务域通过 register() 方法注册 catalog + templates + 关键词
2. 域间 catalog 隔离，互不污染
3. 已有 Logistics 域的 catalog/templates 注册方式不变
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class DomainCatalogRegistration:
    """域 catalog 注册信息。

    参数：
        domain: 业务域名称（logistics / business_analysis / plan_bom / material_management）。
        priority: 域匹配优先级，数字越小优先级越高。
        keywords: 域识别关键词列表，路由时按优先级遍历。
        catalog_loader: 返回该域 semantic catalog 的可调用对象。
        templates_loader: 返回该域 query_templates 的可调用对象。
        allowed_tables: 该域允许查询的中间库表白名单。
    """

    domain: str
    priority: int = 100
    keywords: list[str] = field(default_factory=list)
    catalog_loader: Callable[[], Any] | None = None
    templates_loader: Callable[[], Any] | None = None
    allowed_tables: tuple[str, ...] = field(default_factory=tuple)


class Nl2SqlDomainRegistry:
    """NL2SQL 域注册表。

    职责：
        1. 管理各域的 DomainCatalogRegistration；
        2. 提供域识别（关键词匹配）；
        3. 提供 catalog / templates 按域获取。
    """

    def __init__(self) -> None:
        self._domains: dict[str, DomainCatalogRegistration] = {}

    def register(self, registration: DomainCatalogRegistration) -> None:
        """注册一个业务域到注册表。

        参数：
            registration: 域注册信息。
        """
        self._domains[registration.domain] = registration

    def identify(self, text: str) -> tuple[str, int] | None:
        """根据关键词识别域。

        参数：
            text: 用户问题文本（已归一化）。

        返回：
            (domain, priority) 元组，未识别返回 None。
        """
        if not text:
            return None

        # 按优先级排序，优先检查高优先级域
        sorted_domains = sorted(
            self._domains.items(),
            key=lambda item: item[1].priority,
        )
        for domain, reg in sorted_domains:
            for token in reg.keywords:
                if token in text:
                    return domain, reg.priority
        return None

    def get_registration(self, domain: str) -> DomainCatalogRegistration | None:
        """获取指定域的注册信息。

        参数：
            domain: 业务域名称。

        返回：
            DomainCatalogRegistration 或 None。
        """
        return self._domains.get(domain)

    def get_catalog(self, domain: str) -> Any | None:
        """获取指定域的 semantic catalog。

        参数：
            domain: 业务域名称。

        返回：
            catalog 对象（域特有类型，如 LogisticsSemanticCatalog），
            未注册或无 loader 则返回 None。
        """
        reg = self._domains.get(domain)
        if reg is None or reg.catalog_loader is None:
            return None
        return reg.catalog_loader()

    def get_templates(self, domain: str) -> list[dict] | None:
        """获取指定域的 query_templates。

        参数：
            domain: 业务域名称。

        返回：
            templates 列表（dict），未注册或无 loader 则返回 None。
        """
        reg = self._domains.get(domain)
        if reg is None or reg.templates_loader is None:
            return None
        return reg.templates_loader()

    @property
    def domains(self) -> dict[str, DomainCatalogRegistration]:
        """返回所有已注册域的只读副本。"""
        return dict(self._domains)


__all__ = [
    "DomainCatalogRegistration",
    "Nl2SqlDomainRegistry",
]

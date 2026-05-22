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
            catalog 对象（域特有类型），未注册或无 loader 则返回 None。
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
    "register_logistics_domain",
    "register_business_analysis_domain",
    "create_default_registry",
]


def register_logistics_domain(registry: Nl2SqlDomainRegistry) -> None:
    """注册物流业务域到 registry。

    注册内容：
        - domain: logistics
        - keywords: 物流域识别关键词
        - catalog_loader: 懒加载物流 semantic catalog
        - templates_loader: 懒加载物流 query_templates
        - allowed_tables: 物流中间库允许读取的表
    """
    from backend.app.domains.logistics.services.nl2sql.semantic_catalog import (
        LOGISTICS_NL2SQL_ALLOWED_READ_TABLES,
        LogisticsSemanticCatalogLoader,
    )

    def _load_catalog() -> Any:
        loader = LogisticsSemanticCatalogLoader()
        return loader.load()

    def _load_templates() -> list[dict]:
        from pathlib import Path

        import yaml

        templates_path = (
            Path(__file__).resolve().parents[3]
            / "config" / "domains" / "logistics" / "query_templates.yaml"
        )
        if templates_path.exists():
            data = yaml.safe_load(templates_path.read_text(encoding="utf-8"))
            return (data or {}).get("templates", [])
        return []

    registry.register(DomainCatalogRegistration(
        domain="logistics",
        priority=10,
        keywords=["物流", "发运", "运输", "托运", "承运", "运费", "运价", "车次", "车辆", "发车"],
        catalog_loader=_load_catalog,
        templates_loader=_load_templates,
        allowed_tables=LOGISTICS_NL2SQL_ALLOWED_READ_TABLES,
    ))


def register_business_analysis_domain(registry: Nl2SqlDomainRegistry) -> None:
    """注册经营分析（产销存）业务域到 registry。

    注册内容：
        - domain: business_analysis
        - keywords: 经营分析域识别关键词
        - catalog_loader: 懒加载产销存 semantic catalog（简要描述）
        - templates_loader: 懒加载产销存 query_templates
        - allowed_tables: 产销存中间库允许读取的表
    """
    from pathlib import Path

    from backend.app.domains.business_analysis.services.inventory_sales_production.semantic_catalog import (
        ISP_ALLOWED_READ_TABLES,
    )

    def _load_catalog() -> Any:
        """加载产销存 nl2sql_catalog YAML 文件，返回 LogisticsSemanticCatalog 对象。"""
        import yaml

        from backend.app.domains.logistics.services.nl2sql.semantic_catalog import (
            LOGISTICS_NL2SQL_ALLOWED_READ_TABLES,
            LogisticsSemanticCatalog,
        )

        catalog_dir = (Path(__file__).resolve().parents[3] / "logistics"
                       / "config" / "nl2sql_catalog" / "business_analysis")
        raw_files = {}
        for fname in ("tables.yaml", "metrics.yaml", "dimensions.yaml", "rules.yaml", "examples.yaml"):
            path = catalog_dir / fname
            if path.exists():
                raw_files[fname] = yaml.safe_load(path.read_text(encoding="utf-8"))
            else:
                raw_files[fname] = {}

        # 适配产销存自有 schema 到 LogisticsSemanticCatalog 兼容格式
        tables = raw_files.get("tables.yaml", {}).get("tables", [])
        metrics = raw_files.get("metrics.yaml", {}).get("metrics", [])
        adapted_tables = []
        for t in tables:
            t_copy = dict(t)
            t_copy.pop("sub_domain", None)
            adapted_tables.append(t_copy)
        adapted_metrics = []
        for m in metrics:
            m_copy = dict(m)
            # 确保 sql_expression 字段
            if "sql_expression" not in m_copy or not m_copy.get("sql_expression"):
                m_copy["sql_expression"] = f"SUM({','.join(m_copy.get('source_columns', ['value']))})"
            # metric_category → 拼入 business_note
            cat = m_copy.pop("metric_category", None)
            if cat:
                existing_note = m_copy.get("business_note") or ""
                m_copy["business_note"] = f"指标分类 {cat}。{existing_note}"
            # default_for_sales → 拼入 business_note
            default_sales = m_copy.pop("default_for_sales", None)
            if default_sales:
                existing_note = m_copy.get("business_note") or ""
                m_copy["business_note"] = f"{existing_note} （默认销量口径）"
            # requires_explicit_phrase → 拼入 business_note
            explicit = m_copy.pop("requires_explicit_phrase", None)
            if explicit:
                existing_note = m_copy.get("business_note") or ""
                m_copy["business_note"] = f"{existing_note} （需要显式用户词触发）"
            adapted_metrics.append(m_copy)

        payload = {
            "catalog_version": "business_analysis_nl2sql_catalog.v1",
            "domain": "business_analysis",
            "tables": adapted_tables,
            "metrics": adapted_metrics,
            "dimensions": raw_files.get("dimensions.yaml", {}).get("dimensions", []),
            "joins": [],
            "rules": raw_files.get("rules.yaml", {}).get("rules", []),
            "examples": raw_files.get("examples.yaml", {}).get("examples", []),
        }
        return LogisticsSemanticCatalog.model_validate(payload)

    def _load_templates() -> list[dict]:
        from pathlib import Path

        import yaml

        templates_path = (
            Path(__file__).resolve().parents[3]
            / "config" / "domains" / "business_analysis" / "query_templates.yaml"
        )
        if templates_path.exists():
            data = yaml.safe_load(templates_path.read_text(encoding="utf-8"))
            return (data or {}).get("templates", [])
        return []

    registry.register(DomainCatalogRegistration(
        domain="business_analysis",
        priority=10,
        keywords=["经营分析", "毛利", "收入", "利润", "产销存", "销售量", "销量", "产量",
                   "预算达成率", "库存周转率", "成本分析", "经营指标", "经营情况"],
        catalog_loader=_load_catalog,
        templates_loader=_load_templates,
        allowed_tables=ISP_ALLOWED_READ_TABLES,
    ))


def register_plan_bom_domain(registry: Nl2SqlDomainRegistry) -> None:
    """注册计划 BOM（含功率测算）业务域到 registry。

    注册内容：
        - domain: plan_bom
        - keywords: BOM 域识别关键词
        - catalog_loader: 懒加载 BOM 表描述
        - templates_loader: 懒加载 BOM query_templates
        - allowed_tables: BOM 中间库允许读取的表
    """
    from pathlib import Path

    def _load_catalog() -> Any:
        """加载计划 BOM nl2sql_catalog YAML 文件，返回 LogisticsSemanticCatalog 对象。"""
        import yaml

        from backend.app.domains.logistics.services.nl2sql.semantic_catalog import (
            LogisticsSemanticCatalog,
        )

        catalog_dir = (Path(__file__).resolve().parents[3] / "logistics"
                       / "config" / "nl2sql_catalog" / "plan_bom")
        raw_files = {}
        for fname in ("tables.yaml", "metrics.yaml", "dimensions.yaml", "rules.yaml", "examples.yaml"):
            path = catalog_dir / fname
            if path.exists():
                raw_files[fname] = yaml.safe_load(path.read_text(encoding="utf-8"))
            else:
                raw_files[fname] = {}

        # 适配计划 BOM 自有 schema 到 LogisticsSemanticCatalog 兼容格式
        metrics = raw_files.get("metrics.yaml", {}).get("metrics", [])
        adapted_metrics = []
        for m in metrics:
            m_copy = dict(m)
            # 确保 sql_expression 字段
            if "sql_expression" not in m_copy or not m_copy.get("sql_expression"):
                m_copy["sql_expression"] = f"SUM({','.join(m_copy.get('source_columns', ['value']))})"
            # metric_category → 拼入 business_note
            cat = m_copy.pop("metric_category", None)
            if cat:
                existing_note = m_copy.get("business_note") or ""
                m_copy["business_note"] = f"指标分类 {cat}。{existing_note}"
            adapted_metrics.append(m_copy)

        payload = {
            "catalog_version": "plan_bom_nl2sql_catalog.v1",
            "domain": "plan_bom",
            "tables": raw_files.get("tables.yaml", {}).get("tables", []),
            "metrics": adapted_metrics,
            "dimensions": raw_files.get("dimensions.yaml", {}).get("dimensions", []),
            "joins": [],
            "rules": raw_files.get("rules.yaml", {}).get("rules", []),
            "examples": raw_files.get("examples.yaml", {}).get("examples", []),
        }
        return LogisticsSemanticCatalog.model_validate(payload)

    def _load_templates() -> list[dict]:
        from pathlib import Path

        import yaml

        templates_path = (
            Path(__file__).resolve().parents[3]
            / "config" / "domains" / "plan_bom" / "query_templates.yaml"
        )
        if templates_path.exists():
            data = yaml.safe_load(templates_path.read_text(encoding="utf-8"))
            return (data or {}).get("templates", [])
        return []

    registry.register(DomainCatalogRegistration(
        domain="plan_bom",
        priority=10,
        keywords=["BOM", "版型", "功率", "评审号", "物料清单", "材料明细",
                   "功率测算", "功率预测", "功率档位", "供应商效率", "标板基准",
                   "搭配虚拟件", "版号", "物料匹配"],
        catalog_loader=_load_catalog,
        templates_loader=_load_templates,
        allowed_tables=(
            "plan_bom_header",
            "plan_bom_material_line",
            "plan_bom_revision",
            "plan_power_model_version",
            "plan_power_model_sheet",
            "plan_power_factor_option",
            "plan_power_supplier_efficiency_distribution",
            "plan_power_power_bin",
        ),
    ))


def create_default_registry() -> Nl2SqlDomainRegistry:
    """创建包含物流域 + 产销存域 + 计划 BOM 域的默认注册表。

    用途：
        1. 被 Nl2SqlDomainRouter 默认构造使用；
        2. 物流域 + 产销存域 + 计划BOM域已注册；
        3. 后续 Phase D（material_management）在此函数中追加注册。
    """
    registry = Nl2SqlDomainRegistry()
    register_logistics_domain(registry)
    register_business_analysis_domain(registry)
    register_plan_bom_domain(registry)
    return registry

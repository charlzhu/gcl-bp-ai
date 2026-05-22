from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domains.business_analysis.repositories.inventory_sales_production_repository import (
    METRIC_ALIASES,
    METRIC_CATALOG,
)

# S1: NL2SQL Semantic Catalog 增强——指标 NL 描述和示例问法
_METRIC_NL_DESCRIPTIONS: dict[str, str] = {
    "production_actual_including_oem": "实际产量，包含委外/代工部分，单位为MW（兆瓦）。用户说生产了多少、产出量、实际生产量通常指这个指标。",
    "production_actual_excluding_oem": "实际产量，不含委外/代工部分，单位为MW。",
    "production_by_base": "按生产基地拆分的产量，每个基地一个值，包括合肥、阜宁、广德等。",
    "production_outsourced": "委外加工产量，委托外部供应商生产的部分，单位为MW。",
    "production_self": "自产产量，公司自有生产线生产的产量，单位为MW。",
    "production_oem": "代工/受托加工产量，OEM、双经销、TW等生产模式的产出，单位为MW。",
    "production_by_model_type": "按版型拆分的产量，版型如P型、N型、182N、183N、210N、210R等，单位为MW。",
    "production_budget": "产量预算或目标值，来源于年度预算或综合计划书，单位为MW。用于计算预算达成率。",
    "shipment_volume": "发货量/销量，用户确认默认销量=发货量，单位为MW。用户说卖了多少、出货了多少、发运了多少通常指这个指标。",
    "shipment_by_base": "按生产基地拆分的发货量/销量，单位为MW。",
    "shipment_external_excluding_internal": "对外销量，剔除集团内部交易部分。2024年用户默认采用此口径作为销量。",
    "invoice_sales_volume": "开票销量，仅当用户明确提到开票时使用，不是默认销量口径，单位为MW。",
    "ending_inventory_volume": "期末库存/存货，库存、存货、库存(SAP数据)完全等价。单位为MW，取期末时点值(非累计值)。",
    "ending_inventory_by_base": "按生产基地拆分的期末库存/存货，单位为MW。",
    "consigned_inventory_volume": "寄存库存，寄存仓与寄存合计完全等价。单位为MW，取期末时点值。",
    "consigned_inventory_by_base": "按生产基地拆分的寄存库存，单位为MW。",
    "operating_volume_unclassified": "未分类经营数量，兜底保留的历史特殊经营数量，单位为MW。",
}
_METRIC_EXAMPLE_QUESTIONS: dict[str, list[str]] = {
    "production_actual_including_oem": ["2024年产量是多少？", "2025年生产了多少？", "今年实际产出"],
    "production_by_base": ["各基地产量", "按基地的产量分布", "合肥基地生产了多少"],
    "production_by_model_type": ["各版型产量", "按版型的生产情况", "P型和N型产量"],
    "production_budget": ["2024年产量预算", "今年的生产目标是多少"],
    "shipment_volume": ["2024年销量是多少？", "今年卖了多少？", "发货量数据", "出货量"],
    "shipment_external_excluding_internal": ["2024年对外销量", "2024年销量（剔除内部交易）"],
    "invoice_sales_volume": ["2025年开票销量", "开票了多少"],
    "ending_inventory_volume": ["2024年库存", "存货数据", "期末库存"],
    "consigned_inventory_volume": ["寄存库存", "寄存合计有多少"],
    "production_budget_achievement_rate": ["2024年预算达成率", "预算完成率", "目标完成情况"],
}

ISP_ALLOWED_READ_TABLES = (
    "dwd_ba_isp_monthly_fact",
    "dim_ba_isp_metric",
    "dim_ba_isp_metric_alias",
)
ISP_SUPPORTED_QUERY_KEYS = (
    "ba_isp_metric_summary",
    "ba_isp_metric_breakdown",
    "ba_isp_metric_trend",
    "ba_isp_budget_achievement",
    "ba_isp_inventory_snapshot",
    "ba_isp_period_compare",
)
ISP_SUPPORTED_STATUS = {"supported", "unsupported", "planned"}
ISP_BLOCKED_ALLOWED_COLUMN_PREFIXES = ("source_", "raw_", "trace_")


class InventorySalesProductionCatalogColumn(BaseModel):
    """产销存语义目录字段声明。

    参数：
        name: 智能助手中间库字段名。
        data_type: 字段类型说明。
        business_name: 面向业务的字段名称。
        semantic_role: 字段角色，例如 metric、dimension、time、trace。
        nullable: 字段是否允许为空。
    返回：
        Pydantic 字段声明对象。
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    data_type: str = "unknown"
    business_name: str | None = None
    semantic_role: str | None = None
    nullable: bool = True


class InventorySalesProductionCatalogTable(BaseModel):
    """产销存语义目录表声明。

    业务逻辑：
        只允许声明智能助手中间库中的产销存标准事实/维表；ODS 工作簿、日志表、
        SAP Oracle MID 等外部源均不得进入后续 NL2SQL/QueryPlan 可读目录。
    """

    model_config = ConfigDict(extra="forbid")

    table_name: str
    display_name: str
    domain: str = "business_analysis"
    sub_domain: str = "inventory_sales_production"
    source_system: str = "middle_db"
    allowed_read: bool = True
    grain: str | None = None
    columns: list[InventorySalesProductionCatalogColumn] = Field(default_factory=list)


class InventorySalesProductionCatalogMetric(BaseModel):
    """产销存语义目录指标声明。

    参数：
        metric_id: 标准指标编码。
        display_name: 指标中文名称。
        aliases: 用户问法、Excel 原始项目和业务同义词。
        table/source_columns: 指标依赖的中间库表和字段白名单。
        depends_on_metrics: 计算类指标依赖的已注册标准指标编码。
        support_status: supported 表示当前可执行；planned/unsupported 只可记录不可执行。
        requires_explicit_phrase: 是否必须由显式用户词触发，例如开票销量。
        nl_description: NL2SQL 使用的指标业务描述，供 LLM 理解业务含义。
        example_questions: 该指标的典型用户问法示例，供 LLM 指标解析参考。
    """

    model_config = ConfigDict(extra="forbid")

    metric_id: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)
    table: str = "dwd_ba_isp_monthly_fact"
    source_columns: list[str] = Field(default_factory=list)
    aggregation: str | None = None
    unit: str | None = None
    metric_category: str | None = None
    business_note: str | None = None
    depends_on_metrics: list[str] = Field(default_factory=list)
    support_status: str = "supported"
    default_for_sales: bool = False
    requires_explicit_phrase: bool = False
    nl_description: str | None = None
    example_questions: list[str] = Field(default_factory=list)


class InventorySalesProductionCatalogDimension(BaseModel):
    """产销存语义目录维度声明。"""

    model_config = ConfigDict(extra="forbid")

    dimension_id: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)
    column: str
    table: str = "dwd_ba_isp_monthly_fact"
    business_note: str | None = None
    support_status: str = "supported"
    example_values: list[str] = Field(default_factory=list)
    nl_description: str | None = None


class InventorySalesProductionSemanticCatalog(BaseModel):
    """经营分析产销存 Semantic Catalog 聚合对象。"""

    model_config = ConfigDict(extra="forbid")

    catalog_version: str
    domain: str = "business_analysis"
    sub_domain: str = "inventory_sales_production"
    supported_query_keys: list[str] = Field(default_factory=lambda: list(ISP_SUPPORTED_QUERY_KEYS))
    tables: list[InventorySalesProductionCatalogTable] = Field(default_factory=list)
    metrics: list[InventorySalesProductionCatalogMetric] = Field(default_factory=list)
    dimensions: list[InventorySalesProductionCatalogDimension] = Field(default_factory=list)

    def get_metric(self, metric_id: str) -> InventorySalesProductionCatalogMetric:
        """按指标编码读取目录指标；不存在则抛出 KeyError。"""

        for metric in self.metrics:
            if metric.metric_id == metric_id:
                return metric
        raise KeyError(f"metric_not_found::{metric_id}")

    def resolve_metric_alias(self, alias: str) -> InventorySalesProductionCatalogMetric:
        """按用户口语、原始项目或指标名称解析标准指标。"""

        normalized = self._normalize_text(alias)
        for metric in self.metrics:
            candidates = [metric.metric_id, metric.display_name, *metric.aliases]
            if normalized in {self._normalize_text(candidate) for candidate in candidates}:
                return metric
        raise KeyError(f"metric_alias_not_found::{alias}")

    def get_dimension(self, dimension_id: str) -> InventorySalesProductionCatalogDimension:
        """按维度编码读取目录维度；不存在则抛出 KeyError。"""

        for dimension in self.dimensions:
            if dimension.dimension_id == dimension_id:
                return dimension
        raise KeyError(f"dimension_not_found::{dimension_id}")

    def resolve_dimension_alias(self, alias: str) -> InventorySalesProductionCatalogDimension:
        """按用户口语或维度名称解析标准维度。"""

        normalized = self._normalize_text(alias)
        for dimension in self.dimensions:
            candidates = [dimension.dimension_id, dimension.display_name, *dimension.aliases]
            if normalized in {self._normalize_text(candidate) for candidate in candidates}:
                return dimension
        raise KeyError(f"dimension_alias_not_found::{alias}")

    def allowed_tables(self) -> list[InventorySalesProductionCatalogTable]:
        """返回允许 QueryPlan/NL2SQL 读取的产销存中间库表。"""

        return [table for table in self.tables if table.allowed_read]

    def allowed_table_names(self) -> set[str]:
        """返回允许 QueryPlan/NL2SQL 引用的表名集合。"""

        return {table.table_name for table in self.allowed_tables()}

    def validate_query_plan_support(
        self,
        *,
        query_key: str,
        metrics: list[str],
        dimensions: list[str],
        filters: dict[str, Any] | None = None,
    ) -> None:
        """校验 QueryPlan 只引用当前支持的产销存能力。

        参数：
            query_key: 受控查询能力编码。
            metrics: QueryPlan 指标编码列表。
            dimensions: QueryPlan 维度编码列表。
            filters: QueryPlan 过滤条件，用于校验显式口径开关。
        返回：
            无；遇到未知或暂不支持能力时抛出 ValueError，后续执行器不得查数。
        """

        normalized_filters = filters or {}
        if query_key not in self.supported_query_keys:
            raise ValueError(f"catalog_query_key_not_supported::{query_key}")
        if len(metrics) != 1:
            raise ValueError(f"catalog_metric_count_not_supported::{len(metrics)}")
        requested_metric: InventorySalesProductionCatalogMetric | None = None
        for metric_id in metrics:
            try:
                metric = self.get_metric(metric_id)
            except KeyError as exc:
                # 业务逻辑：未知指标和显式标记为不可执行的指标统一 fail-closed，避免上游继续查数。
                raise ValueError(f"catalog_metric_not_supported::{metric_id}") from exc
            if metric.support_status != "supported":
                raise ValueError(f"catalog_metric_not_supported::{metric_id}")
            if metric.requires_explicit_phrase and not bool(normalized_filters.get("explicit_invoice")):
                raise ValueError(f"catalog_metric_requires_explicit_phrase::{metric_id}")
            requested_metric = metric
        for dimension_id in dimensions:
            try:
                dimension = self.get_dimension(dimension_id)
            except KeyError as exc:
                # 业务逻辑：未知维度不允许落到自由字段或原始 Excel 字段查询。
                raise ValueError(f"catalog_dimension_not_supported::{dimension_id}") from exc
            if dimension.support_status != "supported":
                raise ValueError(f"catalog_dimension_not_supported::{dimension_id}")
        if requested_metric is None:
            raise ValueError("catalog_metric_count_not_supported::0")
        self._validate_query_key_metric_policy(query_key, requested_metric, dimensions)

    @staticmethod
    def _validate_query_key_metric_policy(
        query_key: str,
        metric: InventorySalesProductionCatalogMetric,
        dimensions: list[str],
    ) -> None:
        """校验 query_key、指标聚合策略与维度使用边界一致。"""

        if query_key == "ba_isp_metric_summary" and dimensions:
            raise ValueError(f"catalog_query_key_dimension_mismatch::{query_key}::{dimensions[0]}")
        if query_key == "ba_isp_metric_breakdown" and not dimensions:
            raise ValueError(f"catalog_query_key_dimension_required::{query_key}")
        if query_key == "ba_isp_inventory_snapshot" and metric.aggregation != "period_end":
            raise ValueError(f"catalog_query_key_metric_mismatch::{query_key}::{metric.metric_id}")
        if query_key == "ba_isp_budget_achievement" and dimensions:
            raise ValueError(f"catalog_query_key_dimension_mismatch::{query_key}::{dimensions[0]}")
        budget_achievement_compatible_metrics = {
            "production_budget_achievement_rate",
            "production_actual_including_oem",
        }
        if query_key == "ba_isp_budget_achievement" and metric.metric_id not in budget_achievement_compatible_metrics:
            raise ValueError(f"catalog_query_key_metric_mismatch::{query_key}::{metric.metric_id}")
        if metric.metric_id == "production_budget_achievement_rate" and query_key != "ba_isp_budget_achievement":
            raise ValueError(f"catalog_query_key_metric_mismatch::{query_key}::{metric.metric_id}")

    @staticmethod
    def _normalize_text(value: str) -> str:
        """统一去空白并小写，避免中文/英文同义词匹配受格式影响。"""

        return "".join(str(value).strip().lower().split())


class InventorySalesProductionSemanticCatalogLoader:
    """产销存 Semantic Catalog 加载器。

    业务逻辑：
        1. 默认从当前代码内已审计的 METRIC_CATALOG/METRIC_ALIASES 和固定表字段生成目录；
        2. 测试可注入 payload 触发负例，复用物流 Semantic Catalog 的 fail-closed 校验风格；
        3. 加载过程不连接真实数据库、不读取 Excel/Oracle、不生成 SQL。
    """

    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        """初始化加载器。

        参数：payload 可选目录载荷；为空时使用项目内置产销存目录。
        返回：无。
        """

        self.payload = payload

    def load(self) -> InventorySalesProductionSemanticCatalog:
        """加载并校验产销存 Semantic Catalog。"""

        payload = self.payload if self.payload is not None else self._build_default_payload()
        catalog = InventorySalesProductionSemanticCatalog.model_validate(payload)
        self._validate_catalog(catalog)
        return catalog

    @classmethod
    def _build_default_payload(cls) -> dict[str, Any]:
        """从 M2/M4 已落地目录构造默认产销存 Semantic Catalog。"""

        aliases_by_metric: dict[str, list[str]] = defaultdict(list)
        explicit_metrics: set[str] = set()
        for alias in METRIC_ALIASES:
            aliases_by_metric[alias["metric_code"]].append(alias["alias_text"])
            if bool(alias.get("requires_explicit_phrase")):
                explicit_metrics.add(alias["metric_code"])

        return {
            "catalog_version": "business_analysis_inventory_sales_production_catalog.v1",
            "domain": "business_analysis",
            "sub_domain": "inventory_sales_production",
            "supported_query_keys": list(ISP_SUPPORTED_QUERY_KEYS),
            "tables": cls._default_tables_payload(),
            "metrics": [
                *[
                    cls._metric_payload(
                        metric,
                        aliases_by_metric.get(metric["metric_code"], []),
                        metric["metric_code"] in explicit_metrics,
                    )
                    for metric in METRIC_CATALOG
                ],
                cls._budget_achievement_metric_payload(),
            ],
            "dimensions": cls._default_dimensions_payload(),
        }

    @staticmethod
    def _metric_payload(metric: dict[str, Any], aliases: list[str], requires_explicit_phrase: bool) -> dict[str, Any]:
        """将现有指标维表配置转换为 Semantic Catalog 指标条目。"""

        metric_code = str(metric["metric_code"])
        desc = metric.get("description", "")
        return {
            "metric_id": metric_code,
            "display_name": metric["metric_name"],
            "aliases": sorted({metric["metric_name"], *aliases}),
            "table": "dwd_ba_isp_monthly_fact",
            "source_columns": [
                "business_year",
                "business_month",
                "metric_code",
                "metric_name",
                "aggregation_type",
                "value_decimal",
                "unit_standard",
                "is_published_month",
                *InventorySalesProductionSemanticCatalogLoader._metric_scope_columns(metric_code),
            ],
            "aggregation": metric.get("aggregation_type"),
            "unit": metric.get("unit_standard"),
            "metric_category": metric.get("metric_category"),
            "business_note": desc,
            "support_status": "supported",
            "default_for_sales": bool(metric.get("is_default_for_sales")),
            "requires_explicit_phrase": requires_explicit_phrase,
            "nl_description": _METRIC_NL_DESCRIPTIONS.get(metric_code, desc),
            "example_questions": _METRIC_EXAMPLE_QUESTIONS.get(metric_code, []),
        }

    @staticmethod
    def _metric_scope_columns(metric_code: str) -> list[str]:
        """返回由指标编码隐含的业务拆分维度字段。"""

        scope_columns_by_metric = {
            "production_by_base": ["base_name"],
            "production_by_model_type": ["model_type"],
            "shipment_by_base": ["base_name"],
            "ending_inventory_by_base": ["base_name"],
            "consigned_inventory_by_base": ["base_name"],
        }
        return scope_columns_by_metric.get(metric_code, [])

    @staticmethod
    def _budget_achievement_metric_payload() -> dict[str, Any]:
        """返回产量预算达成率计算指标载荷。

        业务逻辑：预算达成率不是 Excel 原始宽表自由字段，而是由实际产量与预算目标
        两个标准指标确定性计算得到；目录只声明它依赖的标准事实字段和指标依赖关系。
        """

        return {
            "metric_id": "production_budget_achievement_rate",
            "display_name": "产量预算达成率",
            "aliases": ["产量预算达成率", "生产预算达成率", "年度预算达成率", "预算达成率（含委外）"],
            "table": "dwd_ba_isp_monthly_fact",
            "source_columns": [
                "business_year",
                "business_month",
                "metric_code",
                "value_decimal",
                "is_published_month",
            ],
            "aggregation": "calculated_ratio",
            "unit": "percent",
            "metric_category": "rate",
            "business_note": "由实际产量（含委外）除以产量预算/目标确定性重算。",
            "depends_on_metrics": ["production_actual_including_oem", "production_budget"],
            "support_status": "supported",
        }

    @staticmethod
    def _default_tables_payload() -> list[dict[str, Any]]:
        """返回产销存中间库表和字段白名单载荷。"""

        return [
            {
                "table_name": "dwd_ba_isp_monthly_fact",
                "display_name": "产销存标准月度事实",
                "domain": "business_analysis",
                "sub_domain": "inventory_sales_production",
                "source_system": "middle_db",
                "allowed_read": True,
                "grain": "标准指标 + 已发布月份 + 标准业务维度",
                "columns": [
                    {"name": "business_year", "data_type": "int", "business_name": "业务年份", "semantic_role": "time", "nullable": False},
                    {"name": "business_month", "data_type": "int", "business_name": "业务月份", "semantic_role": "time", "nullable": False},
                    {"name": "metric_code", "data_type": "varchar", "business_name": "指标编码", "semantic_role": "metric", "nullable": False},
                    {"name": "metric_name", "data_type": "varchar", "business_name": "指标名称", "semantic_role": "metric", "nullable": False},
                    {"name": "metric_category", "data_type": "varchar", "business_name": "指标分类", "semantic_role": "metric", "nullable": False},
                    {"name": "aggregation_type", "data_type": "varchar", "business_name": "聚合类型", "semantic_role": "metric", "nullable": False},
                    {"name": "value_decimal", "data_type": "decimal", "business_name": "标准数值", "semantic_role": "metric", "nullable": False},
                    {"name": "unit_standard", "data_type": "varchar", "business_name": "标准单位", "semantic_role": "metric", "nullable": False},
                    {"name": "base_name", "data_type": "varchar", "business_name": "基地", "semantic_role": "dimension", "nullable": True},
                    {"name": "factory_name", "data_type": "varchar", "business_name": "工厂", "semantic_role": "dimension", "nullable": True},
                    {"name": "model_type", "data_type": "varchar", "business_name": "版型", "semantic_role": "dimension", "nullable": True},
                    {"name": "production_mode", "data_type": "varchar", "business_name": "生产模式", "semantic_role": "dimension", "nullable": True},
                    {"name": "trade_scope", "data_type": "varchar", "business_name": "交易范围", "semantic_role": "dimension", "nullable": True},
                    {"name": "is_outsourced", "data_type": "smallint", "business_name": "是否委外/代工", "semantic_role": "filter", "nullable": False},
                    {"name": "is_consigned", "data_type": "smallint", "business_name": "是否寄存", "semantic_role": "filter", "nullable": False},
                    {"name": "is_default_external_sales", "data_type": "smallint", "business_name": "是否默认对外销量", "semantic_role": "filter", "nullable": False},
                    {"name": "is_published_month", "data_type": "smallint", "business_name": "是否已发布月份", "semantic_role": "filter", "nullable": False},
                ],
            },
            {
                "table_name": "dim_ba_isp_metric",
                "display_name": "产销存标准指标维表",
                "domain": "business_analysis",
                "sub_domain": "inventory_sales_production",
                "source_system": "middle_db",
                "allowed_read": True,
                "grain": "一个标准指标编码一行",
                "columns": [
                    {"name": "metric_code", "data_type": "varchar", "semantic_role": "metric", "nullable": False},
                    {"name": "metric_name", "data_type": "varchar", "semantic_role": "metric", "nullable": False},
                    {"name": "metric_category", "data_type": "varchar", "semantic_role": "metric", "nullable": False},
                    {"name": "aggregation_type", "data_type": "varchar", "semantic_role": "metric", "nullable": False},
                    {"name": "unit_standard", "data_type": "varchar", "semantic_role": "metric", "nullable": False},
                    {"name": "description", "data_type": "text", "semantic_role": "metric", "nullable": True},
                    {"name": "calculation_formula", "data_type": "text", "semantic_role": "metric", "nullable": True},
                    {"name": "requires_budget", "data_type": "smallint", "semantic_role": "filter", "nullable": False},
                    {"name": "is_default_for_sales", "data_type": "smallint", "semantic_role": "filter", "nullable": False},
                    {"name": "is_active", "data_type": "smallint", "semantic_role": "filter", "nullable": False},
                ],
            },
            {
                "table_name": "dim_ba_isp_metric_alias",
                "display_name": "产销存指标别名表",
                "domain": "business_analysis",
                "sub_domain": "inventory_sales_production",
                "source_system": "middle_db",
                "allowed_read": True,
                "grain": "一个指标别名一行",
                "columns": [
                    {"name": "alias_text", "data_type": "varchar", "semantic_role": "metric", "nullable": False},
                    {"name": "metric_code", "data_type": "varchar", "semantic_role": "metric", "nullable": False},
                    {"name": "alias_type", "data_type": "varchar", "semantic_role": "metric", "nullable": False},
                    {"name": "priority", "data_type": "int", "semantic_role": "metric", "nullable": False},
                    {"name": "requires_explicit_phrase", "data_type": "smallint", "semantic_role": "filter", "nullable": False},
                ],
            },
        ]

    @staticmethod
    def _default_dimensions_payload() -> list[dict[str, Any]]:
        """返回产销存 QueryPlan 当前支持的维度目录。"""

        return [
            {"dimension_id": "business_year", "display_name": "年份", "aliases": ["年份", "年度", "按年", "每年", "分年"], "column": "business_year", "example_values": ["2023", "2024", "2025", "2026"]},
            {
                "dimension_id": "business_quarter",
                "display_name": "季度",
                "aliases": ["季度", "按季度", "每季度", "分季度", "Q1", "Q2", "Q3", "Q4", "一季度", "二季度", "三季度", "四季度"],
                "column": "business_month",
                "business_note": "季度维度由业务月份确定性折算，不暴露原始工作簿字段。",
                "example_values": ["Q1/一季度(1-3月)", "Q2/二季度(4-6月)", "Q3/三季度(7-9月)", "Q4/四季度(10-12月)"],
            },
            {"dimension_id": "base_name", "display_name": "基地", "aliases": ["基地", "各基地", "按基地", "分基地"], "column": "base_name", "example_values": ["合肥基地", "阜宁基地", "广德基地"], "nl_description": "公司的生产基地名称，用于按基地拆分查询。用户说各基地、按基地、分基地时使用此维度。"},
            {"dimension_id": "factory_name", "display_name": "工厂", "aliases": ["工厂", "按工厂", "各工厂", "分工厂"], "column": "factory_name"},
            {"dimension_id": "model_type", "display_name": "版型", "aliases": ["版型", "各版型", "按版型", "分版型"], "column": "model_type", "example_values": ["P型", "N型", "182N", "183N", "210N", "210R"], "nl_description": "光伏组件的版型/产品类型，用于按版型拆分查询。"},
            {"dimension_id": "production_mode", "display_name": "生产模式", "aliases": ["生产模式", "按生产模式"], "column": "production_mode", "example_values": ["自产", "委外", "OEM代工", "受托加工"]},
            {"dimension_id": "trade_scope", "display_name": "交易范围", "aliases": ["交易范围", "内部交易", "对外"], "column": "trade_scope", "example_values": ["内部销售", "对外销售"]},
            {"dimension_id": "business_month", "display_name": "月份", "aliases": ["月份", "按月", "每月", "趋势"], "column": "business_month", "example_values": ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"]},
        ]

    def _validate_catalog(self, catalog: InventorySalesProductionSemanticCatalog) -> None:
        """对产销存 Semantic Catalog 做 fail-closed 安全校验。"""

        if catalog.domain != "business_analysis":
            raise ValueError(f"catalog_domain_invalid::{catalog.domain}")
        if catalog.sub_domain != "inventory_sales_production":
            raise ValueError(f"catalog_sub_domain_invalid::{catalog.sub_domain}")
        allowed = set(ISP_ALLOWED_READ_TABLES)
        seen_tables: set[str] = set()
        for table in catalog.tables:
            if table.table_name in seen_tables:
                raise ValueError(f"catalog_table_duplicate::{table.table_name}")
            seen_tables.add(table.table_name)
            if table.table_name not in allowed:
                raise ValueError(f"catalog_table_not_allowed::{table.table_name}")
            if table.source_system != "middle_db":
                raise ValueError(f"catalog_table_source_system_invalid::{table.table_name}::{table.source_system}")
            if table.domain != "business_analysis":
                raise ValueError(f"catalog_table_domain_invalid::{table.table_name}::{table.domain}")
            if table.sub_domain != "inventory_sales_production":
                raise ValueError(f"catalog_table_sub_domain_invalid::{table.table_name}::{table.sub_domain}")
            self._validate_allowed_table_columns(table)

        allowed_names = catalog.allowed_table_names()
        column_index = self._allowed_column_index(catalog)
        seen_metrics: set[str] = set()
        for metric in catalog.metrics:
            if metric.metric_id in seen_metrics:
                raise ValueError(f"catalog_metric_duplicate::{metric.metric_id}")
            seen_metrics.add(metric.metric_id)
            self._validate_support_status("metric", metric.metric_id, metric.support_status)
            if metric.table not in allowed_names:
                raise ValueError(f"catalog_metric_table_not_allowed::{metric.metric_id}::{metric.table}")
            self._validate_metric_columns(metric, column_index)
            if metric.aggregation == "calculated_ratio" and not metric.depends_on_metrics:
                raise ValueError(f"catalog_metric_dependency_required::{metric.metric_id}")

        for metric in catalog.metrics:
            for dependency in metric.depends_on_metrics:
                if dependency == metric.metric_id or dependency not in seen_metrics:
                    raise ValueError(f"catalog_metric_dependency_not_allowed::{metric.metric_id}::{dependency}")

        seen_dimensions: set[str] = set()
        for dimension in catalog.dimensions:
            if dimension.dimension_id in seen_dimensions:
                raise ValueError(f"catalog_dimension_duplicate::{dimension.dimension_id}")
            seen_dimensions.add(dimension.dimension_id)
            self._validate_support_status("dimension", dimension.dimension_id, dimension.support_status)
            if dimension.table not in allowed_names:
                raise ValueError(f"catalog_dimension_table_not_allowed::{dimension.dimension_id}::{dimension.table}")
            self._validate_dimension_column(dimension, column_index)

        for query_key in catalog.supported_query_keys:
            if query_key not in ISP_SUPPORTED_QUERY_KEYS:
                raise ValueError(f"catalog_query_key_not_supported::{query_key}")

    @staticmethod
    def _validate_allowed_table_columns(table: InventorySalesProductionCatalogTable) -> None:
        """阻断 allowed_read 表暴露来源、原始行或链路追踪字段。"""

        for column in table.columns:
            blocked_by_name = column.name.startswith(ISP_BLOCKED_ALLOWED_COLUMN_PREFIXES)
            blocked_by_role = column.semantic_role == "trace"
            if blocked_by_name or blocked_by_role:
                raise ValueError(f"catalog_table_column_not_allowed::{table.table_name}.{column.name}")

    @staticmethod
    def _allowed_column_index(catalog: InventorySalesProductionSemanticCatalog) -> dict[str, set[str]]:
        """构造可读表字段索引。"""

        return {table.table_name: {column.name for column in table.columns} for table in catalog.allowed_tables()}

    @staticmethod
    def _validate_support_status(kind: str, item_id: str, status: str) -> None:
        """校验支持状态枚举，避免目录里出现不可解释状态。"""

        if status not in ISP_SUPPORTED_STATUS:
            raise ValueError(f"catalog_{kind}_support_status_invalid::{item_id}::{status}")

    @staticmethod
    def _validate_metric_columns(
        metric: InventorySalesProductionCatalogMetric,
        column_index: dict[str, set[str]],
    ) -> None:
        """校验指标依赖字段必须来自指标声明表。"""

        available_columns = column_index.get(metric.table, set())
        for column in metric.source_columns:
            if column not in available_columns:
                raise ValueError(f"catalog_metric_column_not_allowed::{metric.metric_id}::{metric.table}.{column}")

    @staticmethod
    def _validate_dimension_column(
        dimension: InventorySalesProductionCatalogDimension,
        column_index: dict[str, set[str]],
    ) -> None:
        """校验维度字段必须来自维度声明表。"""

        available_columns = column_index.get(dimension.table, set())
        if dimension.column not in available_columns:
            raise ValueError(f"catalog_dimension_column_not_allowed::{dimension.dimension_id}::{dimension.table}.{dimension.column}")


__all__ = [
    "ISP_ALLOWED_READ_TABLES",
    "ISP_BLOCKED_ALLOWED_COLUMN_PREFIXES",
    "ISP_SUPPORTED_QUERY_KEYS",
    "InventorySalesProductionCatalogColumn",
    "InventorySalesProductionCatalogDimension",
    "InventorySalesProductionCatalogMetric",
    "InventorySalesProductionCatalogTable",
    "InventorySalesProductionSemanticCatalog",
    "InventorySalesProductionSemanticCatalogLoader",
]

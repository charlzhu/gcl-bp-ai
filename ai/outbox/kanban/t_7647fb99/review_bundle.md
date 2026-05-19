# t_7647fb99 review bundle

Task: M5-1 产销存 semantic catalog 注册与 focused tests
Branch: feature/isp-m5-inventory-nl2sql-integration
HEAD: 0da9ad4
Generated: 2026-05-19T21:44:55

## Scope
- backend/app/domains/business_analysis/services/inventory_sales_production/semantic_catalog.py
- tests/unit/business_analysis/test_inventory_sales_production_semantic_catalog.py

## Reviewer blocking points addressed
- 年份/business_year 与 季度/business_quarter 维度注册。
- allowed_read/schema 对 source_/raw_/trace 字段 fail-closed，包含 allowed_read=False 表。
- calculated_ratio 指标必须声明 depends_on_metrics，依赖必须指向已注册指标。
- 预算达成率别名收窄：支持明确“产量/生产预算达成率”，不让泛化“预算达成率/目标达成率”直接命中。
- QueryPlan support gate 校验 query_key↔metric 兼容：预算达成率 gate 兼容执行器现有 actual metric 与目录 calculated metric，同时拒绝无维度能力不匹配。

## Verification summary
```text
generated_at=2026-05-19T21:44:55

## semantic_catalog
$ /opt/anaconda3/bin/python3.12 -m pytest tests/unit/business_analysis/test_inventory_sales_production_semantic_catalog.py -q
......                                                                   [100%]
6 passed in 0.34s
exit_code=0

## inventory_sales_production_related
$ /opt/anaconda3/bin/python3.12 -m pytest tests/unit/business_analysis/test_inventory_sales_production_semantic_catalog.py tests/unit/business_analysis/test_inventory_sales_production_m3_query_executor.py tests/unit/business_analysis/test_inventory_sales_production_m4_qa_service.py tests/unit/business_analysis/test_inventory_sales_production_m4_api_registration.py tests/business_acceptance/test_inventory_sales_production_m4_6_real_question_regression.py tests/business_acceptance/test_inventory_sales_production_m2_fact_import.py -q
...........................................                              [100%]
43 passed in 1.83s
exit_code=0

generated_at=2026-05-19T21:44:55

## py_compile_task_files
$ /opt/anaconda3/bin/python3.12 -m py_compile backend/app/domains/business_analysis/services/inventory_sales_production/semantic_catalog.py tests/unit/business_analysis/test_inventory_sales_production_semantic_catalog.py
exit_code=0

generated_at=2026-05-19T21:44:55

## added_line_static_scan
PASS: scanned 1093 added lines; no secret/shell/eval/pickle/SQL-format findings.

generated_at=2026-05-19T21:44:55

## ruff
SKIPPED: ruff is not installed in the verification interpreter.

```

## Task-scoped diff
```diff
diff --git a/backend/app/domains/business_analysis/services/inventory_sales_production/semantic_catalog.py b/backend/app/domains/business_analysis/services/inventory_sales_production/semantic_catalog.py
new file mode 100644
index 0000000..da5411b
--- /dev/null
+++ b/backend/app/domains/business_analysis/services/inventory_sales_production/semantic_catalog.py
@@ -0,0 +1,590 @@
+from __future__ import annotations
+
+from collections import defaultdict
+from typing import Any
+
+from pydantic import BaseModel, ConfigDict, Field
+
+from backend.app.domains.business_analysis.repositories.inventory_sales_production_repository import (
+    METRIC_ALIASES,
+    METRIC_CATALOG,
+)
+
+ISP_ALLOWED_READ_TABLES = (
+    "dwd_ba_isp_monthly_fact",
+    "dim_ba_isp_metric",
+    "dim_ba_isp_metric_alias",
+)
+ISP_SUPPORTED_QUERY_KEYS = (
+    "ba_isp_metric_summary",
+    "ba_isp_metric_breakdown",
+    "ba_isp_metric_trend",
+    "ba_isp_budget_achievement",
+    "ba_isp_inventory_snapshot",
+)
+ISP_SUPPORTED_STATUS = {"supported", "unsupported", "planned"}
+ISP_BLOCKED_ALLOWED_COLUMN_PREFIXES = ("source_", "raw_", "trace_")
+
+
+class InventorySalesProductionCatalogColumn(BaseModel):
+    """产销存语义目录字段声明。
+
+    参数：
+        name: 智能助手中间库字段名。
+        data_type: 字段类型说明。
+        business_name: 面向业务的字段名称。
+        semantic_role: 字段角色，例如 metric、dimension、time、trace。
+        nullable: 字段是否允许为空。
+    返回：
+        Pydantic 字段声明对象。
+    """
+
+    model_config = ConfigDict(extra="forbid")
+
+    name: str
+    data_type: str = "unknown"
+    business_name: str | None = None
+    semantic_role: str | None = None
+    nullable: bool = True
+
+
+class InventorySalesProductionCatalogTable(BaseModel):
+    """产销存语义目录表声明。
+
+    业务逻辑：
+        只允许声明智能助手中间库中的产销存标准事实/维表；ODS 工作簿、日志表、
+        SAP Oracle MID 等外部源均不得进入后续 NL2SQL/QueryPlan 可读目录。
+    """
+
+    model_config = ConfigDict(extra="forbid")
+
+    table_name: str
+    display_name: str
+    domain: str = "business_analysis"
+    sub_domain: str = "inventory_sales_production"
+    source_system: str = "middle_db"
+    allowed_read: bool = True
+    grain: str | None = None
+    columns: list[InventorySalesProductionCatalogColumn] = Field(default_factory=list)
+
+
+class InventorySalesProductionCatalogMetric(BaseModel):
+    """产销存语义目录指标声明。
+
+    参数：
+        metric_id: 标准指标编码。
+        display_name: 指标中文名称。
+        aliases: 用户问法、Excel 原始项目和业务同义词。
+        table/source_columns: 指标依赖的中间库表和字段白名单。
+        depends_on_metrics: 计算类指标依赖的已注册标准指标编码。
+        support_status: supported 表示当前可执行；planned/unsupported 只可记录不可执行。
+        requires_explicit_phrase: 是否必须由显式用户词触发，例如开票销量。
+    返回：
+        可供 QueryPlan/NL2SQL 召回与校验使用的指标条目。
+    """
+
+    model_config = ConfigDict(extra="forbid")
+
+    metric_id: str
+    display_name: str
+    aliases: list[str] = Field(default_factory=list)
+    table: str = "dwd_ba_isp_monthly_fact"
+    source_columns: list[str] = Field(default_factory=list)
+    aggregation: str | None = None
+    unit: str | None = None
+    metric_category: str | None = None
+    business_note: str | None = None
+    depends_on_metrics: list[str] = Field(default_factory=list)
+    support_status: str = "supported"
+    default_for_sales: bool = False
+    requires_explicit_phrase: bool = False
+
+
+class InventorySalesProductionCatalogDimension(BaseModel):
+    """产销存语义目录维度声明。"""
+
+    model_config = ConfigDict(extra="forbid")
+
+    dimension_id: str
+    display_name: str
+    aliases: list[str] = Field(default_factory=list)
+    column: str
+    table: str = "dwd_ba_isp_monthly_fact"
+    business_note: str | None = None
+    support_status: str = "supported"
+
+
+class InventorySalesProductionSemanticCatalog(BaseModel):
+    """经营分析产销存 Semantic Catalog 聚合对象。"""
+
+    model_config = ConfigDict(extra="forbid")
+
+    catalog_version: str
+    domain: str = "business_analysis"
+    sub_domain: str = "inventory_sales_production"
+    supported_query_keys: list[str] = Field(default_factory=lambda: list(ISP_SUPPORTED_QUERY_KEYS))
+    tables: list[InventorySalesProductionCatalogTable] = Field(default_factory=list)
+    metrics: list[InventorySalesProductionCatalogMetric] = Field(default_factory=list)
+    dimensions: list[InventorySalesProductionCatalogDimension] = Field(default_factory=list)
+
+    def get_metric(self, metric_id: str) -> InventorySalesProductionCatalogMetric:
+        """按指标编码读取目录指标；不存在则抛出 KeyError。"""
+
+        for metric in self.metrics:
+            if metric.metric_id == metric_id:
+                return metric
+        raise KeyError(f"metric_not_found::{metric_id}")
+
+    def resolve_metric_alias(self, alias: str) -> InventorySalesProductionCatalogMetric:
+        """按用户口语、原始项目或指标名称解析标准指标。"""
+
+        normalized = self._normalize_text(alias)
+        for metric in self.metrics:
+            candidates = [metric.metric_id, metric.display_name, *metric.aliases]
+            if normalized in {self._normalize_text(candidate) for candidate in candidates}:
+                return metric
+        raise KeyError(f"metric_alias_not_found::{alias}")
+
+    def get_dimension(self, dimension_id: str) -> InventorySalesProductionCatalogDimension:
+        """按维度编码读取目录维度；不存在则抛出 KeyError。"""
+
+        for dimension in self.dimensions:
+            if dimension.dimension_id == dimension_id:
+                return dimension
+        raise KeyError(f"dimension_not_found::{dimension_id}")
+
+    def resolve_dimension_alias(self, alias: str) -> InventorySalesProductionCatalogDimension:
+        """按用户口语或维度名称解析标准维度。"""
+
+        normalized = self._normalize_text(alias)
+        for dimension in self.dimensions:
+            candidates = [dimension.dimension_id, dimension.display_name, *dimension.aliases]
+            if normalized in {self._normalize_text(candidate) for candidate in candidates}:
+                return dimension
+        raise KeyError(f"dimension_alias_not_found::{alias}")
+
+    def allowed_tables(self) -> list[InventorySalesProductionCatalogTable]:
+        """返回允许 QueryPlan/NL2SQL 读取的产销存中间库表。"""
+
+        return [table for table in self.tables if table.allowed_read]
+
+    def allowed_table_names(self) -> set[str]:
+        """返回允许 QueryPlan/NL2SQL 引用的表名集合。"""
+
+        return {table.table_name for table in self.allowed_tables()}
+
+    def validate_query_plan_support(
+        self,
+        *,
+        query_key: str,
+        metrics: list[str],
+        dimensions: list[str],
+        filters: dict[str, Any] | None = None,
+    ) -> None:
+        """校验 QueryPlan 只引用当前支持的产销存能力。
+
+        参数：
+            query_key: 受控查询能力编码。
+            metrics: QueryPlan 指标编码列表。
+            dimensions: QueryPlan 维度编码列表。
+            filters: QueryPlan 过滤条件，用于校验显式口径开关。
+        返回：
+            无；遇到未知或暂不支持能力时抛出 ValueError，后续执行器不得查数。
+        """
+
+        normalized_filters = filters or {}
+        if query_key not in self.supported_query_keys:
+            raise ValueError(f"catalog_query_key_not_supported::{query_key}")
+        if len(metrics) != 1:
+            raise ValueError(f"catalog_metric_count_not_supported::{len(metrics)}")
+        requested_metric: InventorySalesProductionCatalogMetric | None = None
+        for metric_id in metrics:
+            try:
+                metric = self.get_metric(metric_id)
+            except KeyError as exc:
+                # 业务逻辑：未知指标和显式标记为不可执行的指标统一 fail-closed，避免上游继续查数。
+                raise ValueError(f"catalog_metric_not_supported::{metric_id}") from exc
+            if metric.support_status != "supported":
+                raise ValueError(f"catalog_metric_not_supported::{metric_id}")
+            if metric.requires_explicit_phrase and not bool(normalized_filters.get("explicit_invoice")):
+                raise ValueError(f"catalog_metric_requires_explicit_phrase::{metric_id}")
+            requested_metric = metric
+        for dimension_id in dimensions:
+            try:
+                dimension = self.get_dimension(dimension_id)
+            except KeyError as exc:
+                # 业务逻辑：未知维度不允许落到自由字段或原始 Excel 字段查询。
+                raise ValueError(f"catalog_dimension_not_supported::{dimension_id}") from exc
+            if dimension.support_status != "supported":
+                raise ValueError(f"catalog_dimension_not_supported::{dimension_id}")
+        if requested_metric is None:
+            raise ValueError("catalog_metric_count_not_supported::0")
+        self._validate_query_key_metric_policy(query_key, requested_metric, dimensions)
+
+    @staticmethod
+    def _validate_query_key_metric_policy(
+        query_key: str,
+        metric: InventorySalesProductionCatalogMetric,
+        dimensions: list[str],
+    ) -> None:
+        """校验 query_key、指标聚合策略与维度使用边界一致。"""
+
+        if query_key == "ba_isp_metric_summary" and dimensions:
+            raise ValueError(f"catalog_query_key_dimension_mismatch::{query_key}::{dimensions[0]}")
+        if query_key == "ba_isp_metric_breakdown" and not dimensions:
+            raise ValueError(f"catalog_query_key_dimension_required::{query_key}")
+        if query_key == "ba_isp_inventory_snapshot" and metric.aggregation != "period_end":
+            raise ValueError(f"catalog_query_key_metric_mismatch::{query_key}::{metric.metric_id}")
+        if query_key == "ba_isp_budget_achievement" and dimensions:
+            raise ValueError(f"catalog_query_key_dimension_mismatch::{query_key}::{dimensions[0]}")
+        budget_achievement_compatible_metrics = {
+            "production_budget_achievement_rate",
+            "production_actual_including_oem",
+        }
+        if query_key == "ba_isp_budget_achievement" and metric.metric_id not in budget_achievement_compatible_metrics:
+            raise ValueError(f"catalog_query_key_metric_mismatch::{query_key}::{metric.metric_id}")
+        if metric.metric_id == "production_budget_achievement_rate" and query_key != "ba_isp_budget_achievement":
+            raise ValueError(f"catalog_query_key_metric_mismatch::{query_key}::{metric.metric_id}")
+
+    @staticmethod
+    def _normalize_text(value: str) -> str:
+        """统一去空白并小写，避免中文/英文同义词匹配受格式影响。"""
+
+        return "".join(str(value).strip().lower().split())
+
+
+class InventorySalesProductionSemanticCatalogLoader:
+    """产销存 Semantic Catalog 加载器。
+
+    业务逻辑：
+        1. 默认从当前代码内已审计的 METRIC_CATALOG/METRIC_ALIASES 和固定表字段生成目录；
+        2. 测试可注入 payload 触发负例，复用物流 Semantic Catalog 的 fail-closed 校验风格；
+        3. 加载过程不连接真实数据库、不读取 Excel/Oracle、不生成 SQL。
+    """
+
+    def __init__(self, payload: dict[str, Any] | None = None) -> None:
+        """初始化加载器。
+
+        参数：payload 可选目录载荷；为空时使用项目内置产销存目录。
+        返回：无。
+        """
+
+        self.payload = payload
+
+    def load(self) -> InventorySalesProductionSemanticCatalog:
+        """加载并校验产销存 Semantic Catalog。"""
+
+        payload = self.payload if self.payload is not None else self._build_default_payload()
+        catalog = InventorySalesProductionSemanticCatalog.model_validate(payload)
+        self._validate_catalog(catalog)
+        return catalog
+
+    @classmethod
+    def _build_default_payload(cls) -> dict[str, Any]:
+        """从 M2/M4 已落地目录构造默认产销存 Semantic Catalog。"""
+
+        aliases_by_metric: dict[str, list[str]] = defaultdict(list)
+        explicit_metrics: set[str] = set()
+        for alias in METRIC_ALIASES:
+            aliases_by_metric[alias["metric_code"]].append(alias["alias_text"])
+            if bool(alias.get("requires_explicit_phrase")):
+                explicit_metrics.add(alias["metric_code"])
+
+        return {
+            "catalog_version": "business_analysis_inventory_sales_production_catalog.v1",
+            "domain": "business_analysis",
+            "sub_domain": "inventory_sales_production",
+            "supported_query_keys": list(ISP_SUPPORTED_QUERY_KEYS),
+            "tables": cls._default_tables_payload(),
+            "metrics": [
+                *[
+                    cls._metric_payload(
+                        metric,
+                        aliases_by_metric.get(metric["metric_code"], []),
+                        metric["metric_code"] in explicit_metrics,
+                    )
+                    for metric in METRIC_CATALOG
+                ],
+                cls._budget_achievement_metric_payload(),
+            ],
+            "dimensions": cls._default_dimensions_payload(),
+        }
+
+    @staticmethod
+    def _metric_payload(metric: dict[str, Any], aliases: list[str], requires_explicit_phrase: bool) -> dict[str, Any]:
+        """将现有指标维表配置转换为 Semantic Catalog 指标条目。"""
+
+        metric_code = str(metric["metric_code"])
+        return {
+            "metric_id": metric_code,
+            "display_name": metric["metric_name"],
+            "aliases": sorted({metric["metric_name"], *aliases}),
+            "table": "dwd_ba_isp_monthly_fact",
+            "source_columns": [
+                "business_year",
+                "business_month",
+                "metric_code",
+                "metric_name",
+                "aggregation_type",
+                "value_decimal",
+                "unit_standard",
+                "is_published_month",
+                *InventorySalesProductionSemanticCatalogLoader._metric_scope_columns(metric_code),
+            ],
+            "aggregation": metric.get("aggregation_type"),
+            "unit": metric.get("unit_standard"),
+            "metric_category": metric.get("metric_category"),
+            "business_note": metric.get("description"),
+            "support_status": "supported",
+            "default_for_sales": bool(metric.get("is_default_for_sales")),
+            "requires_explicit_phrase": requires_explicit_phrase,
+        }
+
+    @staticmethod
+    def _metric_scope_columns(metric_code: str) -> list[str]:
+        """返回由指标编码隐含的业务拆分维度字段。"""
+
+        scope_columns_by_metric = {
+            "production_by_base": ["base_name"],
+            "production_by_model_type": ["model_type"],
+            "shipment_by_base": ["base_name"],
+            "ending_inventory_by_base": ["base_name"],
+            "consigned_inventory_by_base": ["base_name"],
+        }
+        return scope_columns_by_metric.get(metric_code, [])
+
+    @staticmethod
+    def _budget_achievement_metric_payload() -> dict[str, Any]:
+        """返回产量预算达成率计算指标载荷。
+
+        业务逻辑：预算达成率不是 Excel 原始宽表自由字段，而是由实际产量与预算目标
+        两个标准指标确定性计算得到；目录只声明它依赖的标准事实字段和指标依赖关系。
+        """
+
+        return {
+            "metric_id": "production_budget_achievement_rate",
+            "display_name": "产量预算达成率",
+            "aliases": ["产量预算达成率", "生产预算达成率", "年度预算达成率", "预算达成率（含委外）"],
+            "table": "dwd_ba_isp_monthly_fact",
+            "source_columns": [
+                "business_year",
+                "business_month",
+                "metric_code",
+                "value_decimal",
+                "is_published_month",
+            ],
+            "aggregation": "calculated_ratio",
+            "unit": "percent",
+            "metric_category": "rate",
+            "business_note": "由实际产量（含委外）除以产量预算/目标确定性重算。",
+            "depends_on_metrics": ["production_actual_including_oem", "production_budget"],
+            "support_status": "supported",
+        }
+
+    @staticmethod
+    def _default_tables_payload() -> list[dict[str, Any]]:
+        """返回产销存中间库表和字段白名单载荷。"""
+
+        return [
+            {
+                "table_name": "dwd_ba_isp_monthly_fact",
+                "display_name": "产销存标准月度事实",
+                "domain": "business_analysis",
+                "sub_domain": "inventory_sales_production",
+                "source_system": "middle_db",
+                "allowed_read": True,
+                "grain": "标准指标 + 已发布月份 + 标准业务维度",
+                "columns": [
+                    {"name": "business_year", "data_type": "int", "business_name": "业务年份", "semantic_role": "time", "nullable": False},
+                    {"name": "business_month", "data_type": "int", "business_name": "业务月份", "semantic_role": "time", "nullable": False},
+                    {"name": "metric_code", "data_type": "varchar", "business_name": "指标编码", "semantic_role": "metric", "nullable": False},
+                    {"name": "metric_name", "data_type": "varchar", "business_name": "指标名称", "semantic_role": "metric", "nullable": False},
+                    {"name": "metric_category", "data_type": "varchar", "business_name": "指标分类", "semantic_role": "metric", "nullable": False},
+                    {"name": "aggregation_type", "data_type": "varchar", "business_name": "聚合类型", "semantic_role": "metric", "nullable": False},
+                    {"name": "value_decimal", "data_type": "decimal", "business_name": "标准数值", "semantic_role": "metric", "nullable": False},
+                    {"name": "unit_standard", "data_type": "varchar", "business_name": "标准单位", "semantic_role": "metric", "nullable": False},
+                    {"name": "base_name", "data_type": "varchar", "business_name": "基地", "semantic_role": "dimension", "nullable": True},
+                    {"name": "factory_name", "data_type": "varchar", "business_name": "工厂", "semantic_role": "dimension", "nullable": True},
+                    {"name": "model_type", "data_type": "varchar", "business_name": "版型", "semantic_role": "dimension", "nullable": True},
+                    {"name": "production_mode", "data_type": "varchar", "business_name": "生产模式", "semantic_role": "dimension", "nullable": True},
+                    {"name": "trade_scope", "data_type": "varchar", "business_name": "交易范围", "semantic_role": "dimension", "nullable": True},
+                    {"name": "is_outsourced", "data_type": "smallint", "business_name": "是否委外/代工", "semantic_role": "filter", "nullable": False},
+                    {"name": "is_consigned", "data_type": "smallint", "business_name": "是否寄存", "semantic_role": "filter", "nullable": False},
+                    {"name": "is_default_external_sales", "data_type": "smallint", "business_name": "是否默认对外销量", "semantic_role": "filter", "nullable": False},
+                    {"name": "is_published_month", "data_type": "smallint", "business_name": "是否已发布月份", "semantic_role": "filter", "nullable": False},
+                ],
+            },
+            {
+                "table_name": "dim_ba_isp_metric",
+                "display_name": "产销存标准指标维表",
+                "domain": "business_analysis",
+                "sub_domain": "inventory_sales_production",
+                "source_system": "middle_db",
+                "allowed_read": True,
+                "grain": "一个标准指标编码一行",
+                "columns": [
+                    {"name": "metric_code", "data_type": "varchar", "semantic_role": "metric", "nullable": False},
+                    {"name": "metric_name", "data_type": "varchar", "semantic_role": "metric", "nullable": False},
+                    {"name": "metric_category", "data_type": "varchar", "semantic_role": "metric", "nullable": False},
+                    {"name": "aggregation_type", "data_type": "varchar", "semantic_role": "metric", "nullable": False},
+                    {"name": "unit_standard", "data_type": "varchar", "semantic_role": "metric", "nullable": False},
+                    {"name": "description", "data_type": "text", "semantic_role": "metric", "nullable": True},
+                    {"name": "calculation_formula", "data_type": "text", "semantic_role": "metric", "nullable": True},
+                    {"name": "requires_budget", "data_type": "smallint", "semantic_role": "filter", "nullable": False},
+                    {"name": "is_default_for_sales", "data_type": "smallint", "semantic_role": "filter", "nullable": False},
+                    {"name": "is_active", "data_type": "smallint", "semantic_role": "filter", "nullable": False},
+                ],
+            },
+            {
+                "table_name": "dim_ba_isp_metric_alias",
+                "display_name": "产销存指标别名表",
+                "domain": "business_analysis",
+                "sub_domain": "inventory_sales_production",
+                "source_system": "middle_db",
+                "allowed_read": True,
+                "grain": "一个指标别名一行",
+                "columns": [
+                    {"name": "alias_text", "data_type": "varchar", "semantic_role": "metric", "nullable": False},
+                    {"name": "metric_code", "data_type": "varchar", "semantic_role": "metric", "nullable": False},
+                    {"name": "alias_type", "data_type": "varchar", "semantic_role": "metric", "nullable": False},
+                    {"name": "priority", "data_type": "int", "semantic_role": "metric", "nullable": False},
+                    {"name": "requires_explicit_phrase", "data_type": "smallint", "semantic_role": "filter", "nullable": False},
+                ],
+            },
+        ]
+
+    @staticmethod
+    def _default_dimensions_payload() -> list[dict[str, Any]]:
+        """返回产销存 QueryPlan 当前支持的维度目录。"""
+
+        return [
+            {"dimension_id": "business_year", "display_name": "年份", "aliases": ["年份", "年度", "按年", "每年", "分年"], "column": "business_year"},
+            {
+                "dimension_id": "business_quarter",
+                "display_name": "季度",
+                "aliases": ["季度", "按季度", "每季度", "分季度", "Q1", "Q2", "Q3", "Q4", "一季度", "二季度", "三季度", "四季度"],
+                "column": "business_month",
+                "business_note": "季度维度由业务月份确定性折算，不暴露原始工作簿字段。",
+            },
+            {"dimension_id": "base_name", "display_name": "基地", "aliases": ["基地", "各基地", "按基地", "分基地"], "column": "base_name"},
+            {"dimension_id": "factory_name", "display_name": "工厂", "aliases": ["工厂", "按工厂", "各工厂", "分工厂"], "column": "factory_name"},
+            {"dimension_id": "model_type", "display_name": "版型", "aliases": ["版型", "各版型", "按版型", "分版型"], "column": "model_type"},
+            {"dimension_id": "production_mode", "display_name": "生产模式", "aliases": ["生产模式", "按生产模式"], "column": "production_mode"},
+            {"dimension_id": "trade_scope", "display_name": "交易范围", "aliases": ["交易范围", "内部交易", "对外"], "column": "trade_scope"},
+            {"dimension_id": "business_month", "display_name": "月份", "aliases": ["月份", "按月", "每月", "趋势"], "column": "business_month"},
+        ]
+
+    def _validate_catalog(self, catalog: InventorySalesProductionSemanticCatalog) -> None:
+        """对产销存 Semantic Catalog 做 fail-closed 安全校验。"""
+
+        if catalog.domain != "business_analysis":
+            raise ValueError(f"catalog_domain_invalid::{catalog.domain}")
+        if catalog.sub_domain != "inventory_sales_production":
+            raise ValueError(f"catalog_sub_domain_invalid::{catalog.sub_domain}")
+        allowed = set(ISP_ALLOWED_READ_TABLES)
+        seen_tables: set[str] = set()
+        for table in catalog.tables:
+            if table.table_name in seen_tables:
+                raise ValueError(f"catalog_table_duplicate::{table.table_name}")
+            seen_tables.add(table.table_name)
+            if table.table_name not in allowed:
+                raise ValueError(f"catalog_table_not_allowed::{table.table_name}")
+            if table.source_system != "middle_db":
+                raise ValueError(f"catalog_table_source_system_invalid::{table.table_name}::{table.source_system}")
+            if table.domain != "business_analysis":
+                raise ValueError(f"catalog_table_domain_invalid::{table.table_name}::{table.domain}")
+            if table.sub_domain != "inventory_sales_production":
+                raise ValueError(f"catalog_table_sub_domain_invalid::{table.table_name}::{table.sub_domain}")
+            self._validate_allowed_table_columns(table)
+
+        allowed_names = catalog.allowed_table_names()
+        column_index = self._allowed_column_index(catalog)
+        seen_metrics: set[str] = set()
+        for metric in catalog.metrics:
+            if metric.metric_id in seen_metrics:
+                raise ValueError(f"catalog_metric_duplicate::{metric.metric_id}")
+            seen_metrics.add(metric.metric_id)
+            self._validate_support_status("metric", metric.metric_id, metric.support_status)
+            if metric.table not in allowed_names:
+                raise ValueError(f"catalog_metric_table_not_allowed::{metric.metric_id}::{metric.table}")
+            self._validate_metric_columns(metric, column_index)
+            if metric.aggregation == "calculated_ratio" and not metric.depends_on_metrics:
+                raise ValueError(f"catalog_metric_dependency_required::{metric.metric_id}")
+
+        for metric in catalog.metrics:
+            for dependency in metric.depends_on_metrics:
+                if dependency == metric.metric_id or dependency not in seen_metrics:
+                    raise ValueError(f"catalog_metric_dependency_not_allowed::{metric.metric_id}::{dependency}")
+
+        seen_dimensions: set[str] = set()
+        for dimension in catalog.dimensions:
+            if dimension.dimension_id in seen_dimensions:
+                raise ValueError(f"catalog_dimension_duplicate::{dimension.dimension_id}")
+            seen_dimensions.add(dimension.dimension_id)
+            self._validate_support_status("dimension", dimension.dimension_id, dimension.support_status)
+            if dimension.table not in allowed_names:
+                raise ValueError(f"catalog_dimension_table_not_allowed::{dimension.dimension_id}::{dimension.table}")
+            self._validate_dimension_column(dimension, column_index)
+
+        for query_key in catalog.supported_query_keys:
+            if query_key not in ISP_SUPPORTED_QUERY_KEYS:
+                raise ValueError(f"catalog_query_key_not_supported::{query_key}")
+
+    @staticmethod
+    def _validate_allowed_table_columns(table: InventorySalesProductionCatalogTable) -> None:
+        """阻断 allowed_read 表暴露来源、原始行或链路追踪字段。"""
+
+        for column in table.columns:
+            blocked_by_name = column.name.startswith(ISP_BLOCKED_ALLOWED_COLUMN_PREFIXES)
+            blocked_by_role = column.semantic_role == "trace"
+            if blocked_by_name or blocked_by_role:
+                raise ValueError(f"catalog_table_column_not_allowed::{table.table_name}.{column.name}")
+
+    @staticmethod
+    def _allowed_column_index(catalog: InventorySalesProductionSemanticCatalog) -> dict[str, set[str]]:
+        """构造可读表字段索引。"""
+
+        return {table.table_name: {column.name for column in table.columns} for table in catalog.allowed_tables()}
+
+    @staticmethod
+    def _validate_support_status(kind: str, item_id: str, status: str) -> None:
+        """校验支持状态枚举，避免目录里出现不可解释状态。"""
+
+        if status not in ISP_SUPPORTED_STATUS:
+            raise ValueError(f"catalog_{kind}_support_status_invalid::{item_id}::{status}")
+
+    @staticmethod
+    def _validate_metric_columns(
+        metric: InventorySalesProductionCatalogMetric,
+        column_index: dict[str, set[str]],
+    ) -> None:
+        """校验指标依赖字段必须来自指标声明表。"""
+
+        available_columns = column_index.get(metric.table, set())
+        for column in metric.source_columns:
+            if column not in available_columns:
+                raise ValueError(f"catalog_metric_column_not_allowed::{metric.metric_id}::{metric.table}.{column}")
+
+    @staticmethod
+    def _validate_dimension_column(
+        dimension: InventorySalesProductionCatalogDimension,
+        column_index: dict[str, set[str]],
+    ) -> None:
+        """校验维度字段必须来自维度声明表。"""
+
+        available_columns = column_index.get(dimension.table, set())
+        if dimension.column not in available_columns:
+            raise ValueError(f"catalog_dimension_column_not_allowed::{dimension.dimension_id}::{dimension.table}.{dimension.column}")
+
+
+__all__ = [
+    "ISP_ALLOWED_READ_TABLES",
+    "ISP_BLOCKED_ALLOWED_COLUMN_PREFIXES",
+    "ISP_SUPPORTED_QUERY_KEYS",
+    "InventorySalesProductionCatalogColumn",
+    "InventorySalesProductionCatalogDimension",
+    "InventorySalesProductionCatalogMetric",
+    "InventorySalesProductionCatalogTable",
+    "InventorySalesProductionSemanticCatalog",
+    "InventorySalesProductionSemanticCatalogLoader",
+]
diff --git a/tests/unit/business_analysis/test_inventory_sales_production_semantic_catalog.py b/tests/unit/business_analysis/test_inventory_sales_production_semantic_catalog.py
new file mode 100644
index 0000000..7fca89c
--- /dev/null
+++ b/tests/unit/business_analysis/test_inventory_sales_production_semantic_catalog.py
@@ -0,0 +1,503 @@
+from __future__ import annotations
+
+import pytest
+
+from backend.app.domains.business_analysis.repositories.inventory_sales_production_repository import METRIC_CATALOG
+from backend.app.domains.business_analysis.services.inventory_sales_production.semantic_catalog import (
+    InventorySalesProductionSemanticCatalogLoader,
+)
+
+
+def _minimal_catalog_payload(**overrides):
+    """构造最小产销存语义目录载荷，便于 focused 负例只表达本轮边界。"""
+
+    payload = {
+        "catalog_version": "business_analysis_inventory_sales_production_catalog.v1",
+        "domain": "business_analysis",
+        "sub_domain": "inventory_sales_production",
+        "tables": [
+            {
+                "table_name": "dwd_ba_isp_monthly_fact",
+                "display_name": "产销存月度事实",
+                "domain": "business_analysis",
+                "sub_domain": "inventory_sales_production",
+                "source_system": "middle_db",
+                "allowed_read": True,
+                "columns": [
+                    {"name": "business_year", "data_type": "int"},
+                    {"name": "business_month", "data_type": "int"},
+                    {"name": "metric_code", "data_type": "varchar"},
+                    {"name": "value_decimal", "data_type": "decimal"},
+                    {"name": "is_published_month", "data_type": "smallint"},
+                ],
+            }
+        ],
+    }
+    payload.update(overrides)
+    return payload
+
+
+def test_isp_semantic_catalog_registers_mvp_metrics_aliases_and_dimensions() -> None:
+    """产销存语义目录必须注册 M2/M4 已落地指标、同义词和 QueryPlan 白名单维度。"""
+
+    catalog = InventorySalesProductionSemanticCatalogLoader().load()
+
+    assert catalog.catalog_version == "business_analysis_inventory_sales_production_catalog.v1"
+    assert catalog.domain == "business_analysis"
+    assert catalog.sub_domain == "inventory_sales_production"
+
+    seeded_metric_ids = {entry["metric_code"] for entry in METRIC_CATALOG}
+    catalog_metric_ids = {metric.metric_id for metric in catalog.metrics}
+    assert seeded_metric_ids <= catalog_metric_ids
+    assert len(catalog_metric_ids) == len(seeded_metric_ids) + 1
+
+    production = catalog.get_metric("production_actual_including_oem")
+    assert production.display_name == "实际产量（含委外）"
+    assert production.table == "dwd_ba_isp_monthly_fact"
+    assert production.aggregation == "flow_sum"
+    assert production.unit == "MW"
+    assert "value_decimal" in production.source_columns
+    assert "business_month" in production.source_columns
+
+    model_type_production = catalog.get_metric("production_by_model_type")
+    assert model_type_production.display_name == "版型产量"
+    assert model_type_production.metric_category == "production"
+    assert "model_type" in model_type_production.source_columns
+
+    production_budget = catalog.get_metric("production_budget")
+    assert production_budget.display_name == "产量预算/目标"
+    assert production_budget.metric_category == "budget"
+    assert production_budget.aggregation == "flow_sum"
+    assert production_budget.unit == "MW"
+
+    shipment_external = catalog.get_metric("shipment_external_excluding_internal")
+    assert shipment_external.support_status == "supported"
+    assert shipment_external.default_for_sales is True
+    assert catalog.resolve_metric_alias("销量").metric_id == "shipment_volume"
+    assert catalog.resolve_metric_alias("销售量").metric_id == "shipment_volume"
+    assert catalog.resolve_metric_alias("库存（SAP数据）").metric_id == "ending_inventory_volume"
+    assert catalog.resolve_metric_alias("寄存合计").metric_id == "consigned_inventory_volume"
+    assert catalog.resolve_metric_alias("开票").requires_explicit_phrase is True
+
+    year_dimension = catalog.get_dimension("business_year")
+    assert year_dimension.display_name == "年份"
+    assert year_dimension.table == "dwd_ba_isp_monthly_fact"
+    assert year_dimension.column == "business_year"
+    assert catalog.resolve_dimension_alias("年份").dimension_id == "business_year"
+
+    quarter_dimension = catalog.get_dimension("business_quarter")
+    assert quarter_dimension.display_name == "季度"
+    assert quarter_dimension.table == "dwd_ba_isp_monthly_fact"
+    assert quarter_dimension.column == "business_month"
+    assert catalog.resolve_dimension_alias("季度").dimension_id == "business_quarter"
+
+    base_dimension = catalog.get_dimension("base_name")
+    assert base_dimension.display_name == "基地"
+    assert base_dimension.table == "dwd_ba_isp_monthly_fact"
+    assert base_dimension.column == "base_name"
+    assert catalog.resolve_dimension_alias("按基地").dimension_id == "base_name"
+    assert catalog.resolve_dimension_alias("各版型").dimension_id == "model_type"
+
+
+def test_isp_semantic_catalog_registers_budget_achievement_as_calculated_metric() -> None:
+    """预算达成率必须作为可校验的计算类指标进入语义目录。"""
+
+    catalog = InventorySalesProductionSemanticCatalogLoader().load()
+
+    metric = catalog.get_metric("production_budget_achievement_rate")
+    assert metric.display_name == "产量预算达成率"
+    assert metric.aggregation == "calculated_ratio"
+    assert metric.unit == "percent"
+    assert metric.metric_category == "rate"
+    assert metric.support_status == "supported"
+    assert metric.source_columns == [
+        "business_year",
+        "business_month",
+        "metric_code",
+        "value_decimal",
+        "is_published_month",
+    ]
+    assert metric.depends_on_metrics == ["production_actual_including_oem", "production_budget"]
+    assert catalog.resolve_metric_alias("产量预算达成率").metric_id == "production_budget_achievement_rate"
+    assert catalog.resolve_metric_alias("生产预算达成率").metric_id == "production_budget_achievement_rate"
+    with pytest.raises(KeyError, match="metric_alias_not_found::预算达成率"):
+        catalog.resolve_metric_alias("预算达成率")
+    with pytest.raises(KeyError, match="metric_alias_not_found::目标达成率"):
+        catalog.resolve_metric_alias("目标达成率")
+    catalog.validate_query_plan_support(
+        query_key="ba_isp_budget_achievement",
+        metrics=["production_budget_achievement_rate"],
+        dimensions=[],
+        filters={},
+    )
+    catalog.validate_query_plan_support(
+        query_key="ba_isp_budget_achievement",
+        metrics=["production_actual_including_oem"],
+        dimensions=[],
+        filters={},
+    )
+    with pytest.raises(
+        ValueError,
+        match="catalog_query_key_dimension_mismatch::ba_isp_budget_achievement::business_year",
+    ):
+        catalog.validate_query_plan_support(
+            query_key="ba_isp_budget_achievement",
+            metrics=["production_actual_including_oem"],
+            dimensions=["business_year"],
+            filters={},
+        )
+
+
+def test_isp_semantic_catalog_rejects_trace_columns_even_when_table_not_readable() -> None:
+    """字段边界必须对所有目录表 fail-closed，不能靠 allowed_read=False 隐藏原始来源字段。"""
+
+    blocked_columns = [
+        {"name": "source_file_name", "data_type": "varchar"},
+        {"name": "raw_item", "data_type": "varchar"},
+        {"name": "import_audit_id", "data_type": "varchar", "semantic_role": "trace"},
+    ]
+    for column in blocked_columns:
+        payload = _minimal_catalog_payload(
+            tables=[
+                {
+                    "table_name": "dwd_ba_isp_monthly_fact",
+                    "display_name": "产销存月度事实",
+                    "domain": "business_analysis",
+                    "sub_domain": "inventory_sales_production",
+                    "source_system": "middle_db",
+                    "allowed_read": False,
+                    "columns": [
+                        {"name": "value_decimal", "data_type": "decimal"},
+                        column,
+                    ],
+                }
+            ]
+        )
+        with pytest.raises(
+            ValueError,
+            match=f"catalog_table_column_not_allowed::dwd_ba_isp_monthly_fact.{column['name']}",
+        ):
+            InventorySalesProductionSemanticCatalogLoader(payload=payload).load()
+
+
+def test_isp_semantic_catalog_tables_are_limited_to_middle_db_business_analysis_whitelist() -> None:
+    """产销存语义目录只能暴露智能助手中间库的标准事实/维表，不能混入 ODS、日志或外部源表。"""
+
+    catalog = InventorySalesProductionSemanticCatalogLoader().load()
+    table_names = catalog.allowed_table_names()
+
+    assert table_names == {
+        "dwd_ba_isp_monthly_fact",
+        "dim_ba_isp_metric",
+        "dim_ba_isp_metric_alias",
+    }
+    assert "ods_ba_isp_excel_workbook" not in table_names
+    assert "ods_ba_isp_excel_sheet" not in table_names
+    assert "sys_query_log" not in table_names
+    assert "V_SAP_HFFN_CRKLSZ" not in table_names
+
+    for table in catalog.allowed_tables():
+        assert table.domain == "business_analysis"
+        assert table.sub_domain == "inventory_sales_production"
+        assert table.source_system == "middle_db"
+        assert table.allowed_read is True
+        assert table.columns
+        for column in table.columns:
+            assert not column.name.startswith(("source_", "raw_", "trace_")), column.name
+            assert column.semantic_role != "trace", column.name
+
+
+def test_isp_semantic_catalog_validates_query_key_metric_dimension_and_explicit_alias_status() -> None:
+    """语义目录必须 fail-closed 校验查询能力、指标、维度和必须显式触发的同义词状态。"""
+
+    catalog = InventorySalesProductionSemanticCatalogLoader().load()
+
+    catalog.validate_query_plan_support(
+        query_key="ba_isp_metric_breakdown",
+        metrics=["shipment_by_base"],
+        dimensions=["base_name"],
+        filters={},
+    )
+    catalog.validate_query_plan_support(
+        query_key="ba_isp_metric_summary",
+        metrics=["invoice_sales_volume"],
+        dimensions=[],
+        filters={"explicit_invoice": True},
+    )
+
+    with pytest.raises(ValueError, match="catalog_query_key_not_supported::ba_isp_free_sql"):
+        catalog.validate_query_plan_support(
+            query_key="ba_isp_free_sql",
+            metrics=["shipment_volume"],
+            dimensions=[],
+            filters={},
+        )
+    with pytest.raises(ValueError, match="catalog_metric_not_supported::unknown_metric"):
+        catalog.validate_query_plan_support(
+            query_key="ba_isp_metric_summary",
+            metrics=["unknown_metric"],
+            dimensions=[],
+            filters={},
+        )
+    with pytest.raises(ValueError, match="catalog_dimension_not_supported::raw_item"):
+        catalog.validate_query_plan_support(
+            query_key="ba_isp_metric_breakdown",
+            metrics=["shipment_volume"],
+            dimensions=["raw_item"],
+            filters={},
+        )
+    with pytest.raises(ValueError, match="catalog_metric_requires_explicit_phrase::invoice_sales_volume"):
+        catalog.validate_query_plan_support(
+            query_key="ba_isp_metric_summary",
+            metrics=["invoice_sales_volume"],
+            dimensions=[],
+            filters={},
+        )
+    with pytest.raises(
+        ValueError,
+        match="catalog_query_key_dimension_mismatch::ba_isp_metric_summary::base_name",
+    ):
+        catalog.validate_query_plan_support(
+            query_key="ba_isp_metric_summary",
+            metrics=["shipment_volume"],
+            dimensions=["base_name"],
+            filters={},
+        )
+    with pytest.raises(ValueError, match="catalog_query_key_dimension_required::ba_isp_metric_breakdown"):
+        catalog.validate_query_plan_support(
+            query_key="ba_isp_metric_breakdown",
+            metrics=["shipment_volume"],
+            dimensions=[],
+            filters={},
+        )
+    with pytest.raises(
+        ValueError,
+        match="catalog_query_key_metric_mismatch::ba_isp_inventory_snapshot::shipment_volume",
+    ):
+        catalog.validate_query_plan_support(
+            query_key="ba_isp_inventory_snapshot",
+            metrics=["shipment_volume"],
+            dimensions=[],
+            filters={},
+        )
+    with pytest.raises(
+        ValueError,
+        match="catalog_query_key_metric_mismatch::ba_isp_budget_achievement::shipment_volume",
+    ):
+        catalog.validate_query_plan_support(
+            query_key="ba_isp_budget_achievement",
+            metrics=["shipment_volume"],
+            dimensions=[],
+            filters={},
+        )
+    with pytest.raises(
+        ValueError,
+        match="catalog_query_key_metric_mismatch::ba_isp_metric_summary::production_budget_achievement_rate",
+    ):
+        catalog.validate_query_plan_support(
+            query_key="ba_isp_metric_summary",
+            metrics=["production_budget_achievement_rate"],
+            dimensions=[],
+            filters={},
+        )
+
+
+def test_isp_semantic_catalog_rejects_unsafe_table_and_field_config() -> None:
+    """目录加载期必须阻断非白名单表、非中间库来源和未声明字段引用。"""
+
+    unsafe_table_payload = {
+        "catalog_version": "business_analysis_inventory_sales_production_catalog.v1",
+        "domain": "business_analysis",
+        "sub_domain": "inventory_sales_production",
+        "tables": [
+            {
+                "table_name": "ods_ba_isp_excel_workbook",
+                "display_name": "原始工作簿",
+                "domain": "business_analysis",
+                "sub_domain": "inventory_sales_production",
+                "source_system": "middle_db",
+                "allowed_read": True,
+                "columns": [{"name": "source_file_name", "data_type": "varchar"}],
+            }
+        ],
+    }
+    with pytest.raises(ValueError, match="catalog_table_not_allowed::ods_ba_isp_excel_workbook"):
+        InventorySalesProductionSemanticCatalogLoader(payload=unsafe_table_payload).load()
+
+    unsafe_source_payload = {
+        "catalog_version": "business_analysis_inventory_sales_production_catalog.v1",
+        "domain": "business_analysis",
+        "sub_domain": "inventory_sales_production",
+        "tables": [
+            {
+                "table_name": "dwd_ba_isp_monthly_fact",
+                "display_name": "产销存月度事实",
+                "domain": "business_analysis",
+                "sub_domain": "inventory_sales_production",
+                "source_system": "sap_mid",
+                "allowed_read": True,
+                "columns": [{"name": "value_decimal", "data_type": "decimal"}],
+            }
+        ],
+    }
+    with pytest.raises(ValueError, match="catalog_table_source_system_invalid::dwd_ba_isp_monthly_fact::sap_mid"):
+        InventorySalesProductionSemanticCatalogLoader(payload=unsafe_source_payload).load()
+
+    unsafe_column_prefix_payload = {
+        "catalog_version": "business_analysis_inventory_sales_production_catalog.v1",
+        "domain": "business_analysis",
+        "sub_domain": "inventory_sales_production",
+        "tables": [
+            {
+                "table_name": "dwd_ba_isp_monthly_fact",
+                "display_name": "产销存月度事实",
+                "domain": "business_analysis",
+                "sub_domain": "inventory_sales_production",
+                "source_system": "middle_db",
+                "allowed_read": True,
+                "columns": [
+                    {"name": "value_decimal", "data_type": "decimal"},
+                    {"name": "source_file_name", "data_type": "varchar"},
+                ],
+            }
+        ],
+    }
+    with pytest.raises(
+        ValueError,
+        match="catalog_table_column_not_allowed::dwd_ba_isp_monthly_fact.source_file_name",
+    ):
+        InventorySalesProductionSemanticCatalogLoader(payload=unsafe_column_prefix_payload).load()
+
+    unsafe_trace_column_payload = {
+        "catalog_version": "business_analysis_inventory_sales_production_catalog.v1",
+        "domain": "business_analysis",
+        "sub_domain": "inventory_sales_production",
+        "tables": [
+            {
+                "table_name": "dwd_ba_isp_monthly_fact",
+                "display_name": "产销存月度事实",
+                "domain": "business_analysis",
+                "sub_domain": "inventory_sales_production",
+                "source_system": "middle_db",
+                "allowed_read": True,
+                "columns": [
+                    {"name": "value_decimal", "data_type": "decimal"},
+                    {"name": "import_audit_id", "data_type": "varchar", "semantic_role": "trace"},
+                ],
+            }
+        ],
+    }
+    with pytest.raises(
+        ValueError,
+        match="catalog_table_column_not_allowed::dwd_ba_isp_monthly_fact.import_audit_id",
+    ):
+        InventorySalesProductionSemanticCatalogLoader(payload=unsafe_trace_column_payload).load()
+
+    unsafe_metric_payload = {
+        "catalog_version": "business_analysis_inventory_sales_production_catalog.v1",
+        "domain": "business_analysis",
+        "sub_domain": "inventory_sales_production",
+        "tables": [
+            {
+                "table_name": "dwd_ba_isp_monthly_fact",
+                "display_name": "产销存月度事实",
+                "domain": "business_analysis",
+                "sub_domain": "inventory_sales_production",
+                "source_system": "middle_db",
+                "allowed_read": True,
+                "columns": [{"name": "value_decimal", "data_type": "decimal"}],
+            }
+        ],
+        "metrics": [
+            {
+                "metric_id": "broken_metric",
+                "display_name": "错误指标",
+                "aliases": ["错误指标"],
+                "table": "dwd_ba_isp_monthly_fact",
+                "source_columns": ["missing_value"],
+                "aggregation": "flow_sum",
+                "unit": "MW",
+            }
+        ],
+    }
+    with pytest.raises(
+        ValueError,
+        match="catalog_metric_column_not_allowed::broken_metric::dwd_ba_isp_monthly_fact.missing_value",
+    ):
+        InventorySalesProductionSemanticCatalogLoader(payload=unsafe_metric_payload).load()
+
+    unsafe_calculated_without_dependencies_payload = {
+        "catalog_version": "business_analysis_inventory_sales_production_catalog.v1",
+        "domain": "business_analysis",
+        "sub_domain": "inventory_sales_production",
+        "tables": [
+            {
+                "table_name": "dwd_ba_isp_monthly_fact",
+                "display_name": "产销存月度事实",
+                "domain": "business_analysis",
+                "sub_domain": "inventory_sales_production",
+                "source_system": "middle_db",
+                "allowed_read": True,
+                "columns": [
+                    {"name": "business_year", "data_type": "int"},
+                    {"name": "business_month", "data_type": "int"},
+                    {"name": "metric_code", "data_type": "varchar"},
+                    {"name": "value_decimal", "data_type": "decimal"},
+                    {"name": "is_published_month", "data_type": "smallint"},
+                ],
+            }
+        ],
+        "metrics": [
+            {
+                "metric_id": "broken_calculated_metric",
+                "display_name": "错误计算指标",
+                "aliases": ["错误计算指标"],
+                "table": "dwd_ba_isp_monthly_fact",
+                "source_columns": ["business_year", "business_month", "metric_code", "value_decimal", "is_published_month"],
+                "aggregation": "calculated_ratio",
+                "unit": "percent",
+            }
+        ],
+    }
+    with pytest.raises(ValueError, match="catalog_metric_dependency_required::broken_calculated_metric"):
+        InventorySalesProductionSemanticCatalogLoader(payload=unsafe_calculated_without_dependencies_payload).load()
+
+    unsafe_dependency_payload = {
+        "catalog_version": "business_analysis_inventory_sales_production_catalog.v1",
+        "domain": "business_analysis",
+        "sub_domain": "inventory_sales_production",
+        "tables": [
+            {
+                "table_name": "dwd_ba_isp_monthly_fact",
+                "display_name": "产销存月度事实",
+                "domain": "business_analysis",
+                "sub_domain": "inventory_sales_production",
+                "source_system": "middle_db",
+                "allowed_read": True,
+                "columns": [
+                    {"name": "business_year", "data_type": "int"},
+                    {"name": "business_month", "data_type": "int"},
+                    {"name": "metric_code", "data_type": "varchar"},
+                    {"name": "value_decimal", "data_type": "decimal"},
+                    {"name": "is_published_month", "data_type": "smallint"},
+                ],
+            }
+        ],
+        "metrics": [
+            {
+                "metric_id": "broken_calculated_metric",
+                "display_name": "错误计算指标",
+                "aliases": ["错误计算指标"],
+                "table": "dwd_ba_isp_monthly_fact",
+                "source_columns": ["business_year", "business_month", "metric_code", "value_decimal", "is_published_month"],
+                "aggregation": "calculated_ratio",
+                "unit": "percent",
+                "depends_on_metrics": ["missing_metric"],
+            }
+        ],
+    }
+    with pytest.raises(
+        ValueError,
+        match="catalog_metric_dependency_not_allowed::broken_calculated_metric::missing_metric",
+    ):
+        InventorySalesProductionSemanticCatalogLoader(payload=unsafe_dependency_payload).load()

```

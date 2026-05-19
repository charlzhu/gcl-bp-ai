# t_7647fb99 review bundle

Task: M5-1 产销存 semantic catalog 注册与 focused tests
Branch: feature/isp-m5-inventory-nl2sql-integration
HEAD: 9ce7e90
Generated: 2026-05-19T21:40:01

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
generated_at=2026-05-19T21:40:01

## semantic_catalog
$ /opt/anaconda3/bin/python3.12 -m pytest tests/unit/business_analysis/test_inventory_sales_production_semantic_catalog.py -q
......                                                                   [100%]
6 passed in 0.29s
exit_code=0

## inventory_sales_production_related
$ /opt/anaconda3/bin/python3.12 -m pytest tests/unit/business_analysis/test_inventory_sales_production_semantic_catalog.py tests/unit/business_analysis/test_inventory_sales_production_m3_query_executor.py tests/unit/business_analysis/test_inventory_sales_production_m4_qa_service.py tests/unit/business_analysis/test_inventory_sales_production_m4_api_registration.py tests/business_acceptance/test_inventory_sales_production_m4_6_real_question_regression.py tests/business_acceptance/test_inventory_sales_production_m2_fact_import.py -q
...........................................                              [100%]
43 passed in 1.78s
exit_code=0

generated_at=2026-05-19T21:40:01

## py_compile_task_files
$ /opt/anaconda3/bin/python3.12 -m py_compile backend/app/domains/business_analysis/services/inventory_sales_production/semantic_catalog.py tests/unit/business_analysis/test_inventory_sales_production_semantic_catalog.py
exit_code=0

generated_at=2026-05-19T21:40:01

## added_line_static_scan
PASS: scanned 7 added lines; no secret/shell/eval/pickle/SQL-format findings.

generated_at=2026-05-19T21:40:01

## ruff
SKIPPED: ruff is not installed in the verification interpreter.

```

## Task-scoped diff
```diff
diff --git a/backend/app/domains/business_analysis/services/inventory_sales_production/semantic_catalog.py b/backend/app/domains/business_analysis/services/inventory_sales_production/semantic_catalog.py
index da744eb..da5411b 100644
--- a/backend/app/domains/business_analysis/services/inventory_sales_production/semantic_catalog.py
+++ b/backend/app/domains/business_analysis/services/inventory_sales_production/semantic_catalog.py
@@ -235,7 +235,13 @@ class InventorySalesProductionSemanticCatalog(BaseModel):
             raise ValueError(f"catalog_query_key_dimension_required::{query_key}")
         if query_key == "ba_isp_inventory_snapshot" and metric.aggregation != "period_end":
             raise ValueError(f"catalog_query_key_metric_mismatch::{query_key}::{metric.metric_id}")
-        if query_key == "ba_isp_budget_achievement" and metric.metric_id != "production_budget_achievement_rate":
+        if query_key == "ba_isp_budget_achievement" and dimensions:
+            raise ValueError(f"catalog_query_key_dimension_mismatch::{query_key}::{dimensions[0]}")
+        budget_achievement_compatible_metrics = {
+            "production_budget_achievement_rate",
+            "production_actual_including_oem",
+        }
+        if query_key == "ba_isp_budget_achievement" and metric.metric_id not in budget_achievement_compatible_metrics:
             raise ValueError(f"catalog_query_key_metric_mismatch::{query_key}::{metric.metric_id}")
         if metric.metric_id == "production_budget_achievement_rate" and query_key != "ba_isp_budget_achievement":
             raise ValueError(f"catalog_query_key_metric_mismatch::{query_key}::{metric.metric_id}")
@@ -528,8 +534,6 @@ class InventorySalesProductionSemanticCatalogLoader:
     def _validate_allowed_table_columns(table: InventorySalesProductionCatalogTable) -> None:
         """阻断 allowed_read 表暴露来源、原始行或链路追踪字段。"""

-        if not table.allowed_read:
-            return
         for column in table.columns:
             blocked_by_name = column.name.startswith(ISP_BLOCKED_ALLOWED_COLUMN_PREFIXES)
             blocked_by_role = column.semantic_role == "trace"

```

# NQE 中间库与向量库能力审计报告

更新时间：2026-05-25

---

## 总体结论

**当前中间库和向量库已存在，但 NQE SQL Agent 主链路未真正使用它们。**

中间库现状：logistics_ai 有 45 张表，数据量充足，四域均已结构化入库。但 NQE 的 metadata context 构建来自 YAML 文件 + Python 常量，不读中间库表。向量库（Milvus, 398 entities, 1024-dim）存在但 NQE SQL Agent Graph 不调用。

---

## 一、logistics_ai 中间库现状

### 表总数：44（不含 alembic_version）

| 业务域 | 表数 | 代表表 | 数据量 |
|---|---|---|---|
| 物流 ODS | 5 | ods_logistic_ship_task/product/warehouse/company/assign | 4,923-1,533 |
| 物流 DWD | 5 | dwd_logistics_ship_task/product/warehouse/company/hist_shipment_detail | 1,423-24,234 |
| 物流 DWS | 2 | dws_logistics_detail_union/monthly_metric | 28,754 / 7,762 |
| 物流 DM | 1 | dm_logistics_company_month_rank | 429 |
| 产销存 DWD | 1 | dwd_ba_isp_monthly_fact | 1,413 |
| 产销存 DIM | 2 | dim_ba_isp_metric/alias | 17 / 21 |
| 产销存 ODS | 2 | ods_ba_isp_excel_workbook/sheet | 4 / 5 |
| BOM | 6 | plan_bom_header/material_line/revision/import_batch/export_file/export_task | 51-5,751 |
| 功率 | 7 | plan_power_model_version/sheet/factor_option/supplier_efficiency_distribution/power_bin/benchmark_factor/parse_issue | 1-916 |
| 系统 | 5 | sys_query_log/chat_message/chat_session/data_source/task_log | 34,491 / 26 |
| 历史 ODS | 2 | ods_hist_excel_file/row | 5 / 24,235 |

### 数据状态

| 域 | 源类型 | 已入库 | 行数 |
|---|---|---|---|
| 物流 | Excel 2023-2025 + xst_cloud 2026 | ✅ 28,754 rows (dws_logistics_detail_union) | 
| 产销存 | Excel | ✅ 1,413 rows | 
| BOM | Excel | ✅ 5,751 material lines | 
| 功率 | Excel | ✅ model/supplier/bin/factor all present | 

---

## 二、Milvus 向量库现状

| 属性 | 值 |
|---|---|
| Connection | ✅ localhost:19530 |
| Collection | `gcl_bp_ai_logistics_nl2sql_catalog` |
| Entities | 398 |
| Embedding dim | 1024 |
| Schema fields | id(VARCHAR), catalog_id, catalog_version, doc_type, title, content, keywords_json, metadata_json, source_table, vector(1024) |
| doc_type | table/column/metric/dimension/business_rule/enum_value |

**集合仅覆盖物流域**——命名含 "logistics"。

---

## 三、NQE 是否真正使用中间库

| 数据源 | NQE SQL Agent 使用？ |
|---|---|
| logistics_ai 中间库表 | ❌ 不直接查询（SQL generation 是 LLM 动态 SQL） |
| NQE metadata tables (nqe_domain 等) | ❌ **这些表不存在！** `upsert_nqe_metadata_bundle()` 从未运行 |
| Milvus collection | ❌ NQE SQL Agent Graph 不调用 |
| YAML catalog | ✅ `nqe_metadata_sync.py` 读取 YAML → context |
| Python 常量 | ✅ QUICK_CHIPS, `_GENERATE_SQL_DEFAULT` prompt, `_AUTO_CONTEXT_DOMAINS` |
| Prompt 补丁 | ✅ ba_metric_resolver.py, `value_for_sql` 字段 |

**结论：NQE SQL Agent 的上下文来自 YAML + Python 常量，而不是中间库或向量库。**

---

## 四、四域资产覆盖

| 域 | 中间库 | 向量库 | YAML catalog | NQE 当前用 |
|---|---|---|---|---|
| 物流 | ✅ 完整 | ✅ | ✅ | YAML |
| 产销存 | ✅ | ❌ | ✅ | YAML + prompt |
| BOM | ✅ | ❌ | ✅ | YAML |
| 功率 | ✅ | ❌ | ✅ | YAML |

---

## 五、关键表是否被代码引用

SQL Agent 读取 real 表做 EXPLAIN/execute（通过 LLM 生成的 SQL 直接查询这些表）。但 metadata context 不读这些表——读的是 YAML catalog 和 Python 常量。

---

## 六、当前缺口

| 缺口 | 说明 |
|---|---|
| NQE metadata 未入库 | nqe_domain/table_info/column_info/metric_info/dimension_info 表不存在 |
| 向量库仅物流 | 产销存/BOM/功率 domain 无向量索引 |
| 向量库未被 NQE 使用 | NQE SQL Agent Graph 不调用 Milvus |
| Semantic catalog 落库未执行 | `upsert_nqe_metadata_bundle()` 未运行 |
| Metric resolver 未资产化 | ba_metric_resolver 是代码补丁 |
| Quick chips 未配置化 | Python 常量 |
| SQL prompt 依赖 YAML + 常量 | 非中间库驱动 |

---

## 七、优先级

| P0 | 运行 `upsert_nqe_metadata_bundle()` 落库语义资产 |
| P0 | NQE context 切换为读中间库 sematic tables（替代 YAML） |
| P1 | 将 vector collection 从 "logistics" 扩展为四域 |
| P1 | NQE retrieve 接入 Milvus 做 column/metric recall |
| P1 | ba_metric_resolver 迁移到 dim_ba_isp_metric_alias |
| P2 | quick chips 迁移到 sys 配置表 |

---

## 八、建议

先落库 semantic catalog（P0），再扩展向量库（P1），然后改造 context builder 从 DB 读取以替代 YAML。代码补丁（ba_metric_resolver, prompt 补丁）应逐步资产化。

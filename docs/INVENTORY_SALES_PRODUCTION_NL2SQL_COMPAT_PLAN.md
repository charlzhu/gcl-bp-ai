# 产销存智能问答 NL2SQL 兼容建模方案（M1）

> 任务：产销存（经营分析业务）智能问答 M1 文档与建模方案
> 目标：在不等待物流 NL2SQL 全部完成的前提下，先完成产销存数据接入和问答能力设计，并保证后续能平滑接入统一 NL2SQL。
> 本轮边界：只输出方案，不实现迁移、接口、前端或正式计算引擎。

---

## 1. 设计结论

产销存智能问答建议立即启动，但必须按未来 NL2SQL 的目标形态设计，避免再堆旧规则解析。

推荐路线：

```text
产销存 Excel
↓
文件版本与导入批次管理
↓
原始宽表只读解析与来源行列追溯
↓
标准长表事实模型
↓
指标/维度/别名语义目录
↓
受控 QueryPlan MVP
↓
确定性查询和计算
↓
LLM 只做问题理解和答案表达
↓
后续统一 NL2SQL 接管 QueryPlan/SQLPlan 生成
```

核心原则：

1. 不等 NL2SQL 全量完成，但从第一天就为 NL2SQL 留接口。
2. 不以原始 Excel 表头作为长期查询模型。
3. 不写一堆关键词 if/else 直接查表。
4. 不让 LLM 直接读取 Excel 或计算业务数字。
5. 所有业务数字由后端从中间库确定性查询与计算。
6. 所有回答必须业务化，不向用户暴露表名、字段名、SQL、planner、guardrail、query_key 等技术细节。

---

## 2. 业务域定位

产销存属于经营分析业务，不属于物流域、物管域或计划 BOM 域。

建议业务域命名：

```text
domain = business_analysis
sub_domain = inventory_sales_production
```

建议后端目录在后续 M2 建设时采用：

```text
backend/app/domains/business_analysis/
  api/
  models.py
  repositories/
  schemas/
  services/
    inventory_sales_production/
```

如果当前项目希望先小步接入，也可以先只创建：

```text
backend/app/domains/business_analysis/services/inventory_sales_production/
```

但不要混入：

1. `logistics`：物流问答域。
2. `material_management`：物管 SAP 库存/出入库域。
3. `plan_bom`：计划 BOM / 功率预测域。

---

## 3. 数据分层方案

### 3.1 分层目标

产销存 Excel 属于经营分析报表型数据，建议采用 ODS / DWD / DWS / DM 分层。

```text
ODS：保留原始文件、sheet、行列、单元格、公式、导入批次。
DWD：将宽表解析为标准月度事实长表。
DWS：按指标类型生成可直接问答的期间事实。
DM：为高频问题、排行、趋势、对比生成轻量汇总。
```

### 3.2 ODS 层建议表

#### `ods_ba_isp_excel_workbook`

用途：记录每个产销存 Excel 文件版本。

核心字段：

| 字段 | 含义 |
|---|---|
| `id` | 主键 |
| `source_file_name` | 原始文件名 |
| `source_file_sha256` | 文件哈希 |
| `source_file_size` | 文件大小 |
| `business_year` | 业务年份 |
| `data_cutoff_month` | 数据截止月份，2026.04 对应 4 |
| `source_version_label` | 来源版本标签，如 `2026.04` |
| `upload_batch_no` | 导入批次 |
| `sheet_count` | sheet 数量 |
| `has_vba` | 是否有 VBA |
| `external_link_count` | 外链数量 |
| `parser_version` | 解析器版本 |
| `quality_status` | 质量状态 |
| `quality_message` | 质量说明 |
| `created_at` / `updated_at` | 时间戳 |

#### `ods_ba_isp_excel_sheet`

用途：记录每个 sheet 的结构。

核心字段：

| 字段 | 含义 |
|---|---|
| `id` | 主键 |
| `workbook_id` | 工作簿 ID |
| `sheet_name` | 原始 sheet 名 |
| `sheet_role` | summary / detail / unknown |
| `dimension_ref` | Excel 范围，如 `A1:S43` |
| `max_row` / `max_col` | 最大行列 |
| `formula_count` | 公式数 |
| `merged_cell_count` | 合并单元格数量 |
| `hidden_rows` / `hidden_cols` | 隐藏行列 JSON |
| `header_rows` | 表头行 JSON |
| `created_at` / `updated_at` | 时间戳 |

#### `ods_ba_isp_excel_cell`

用途：保留可追溯原始单元格，不直接作为问答事实表。

核心字段：

| 字段 | 含义 |
|---|---|
| `id` | 主键 |
| `workbook_id` / `sheet_id` | 来源工作簿和 sheet |
| `cell_ref` | 单元格坐标 |
| `row_index` / `col_index` | 行列号 |
| `raw_value` | 原始值 |
| `cached_value` | 缓存值 |
| `formula` | 公式文本 |
| `row_label_1` / `row_label_2` / `row_label_3` | 行标签 |
| `col_label_raw` | 原始列表头 |
| `is_hidden_row` / `is_hidden_col` | 是否隐藏 |
| `created_at` | 时间戳 |

说明：`ods_ba_isp_excel_cell` 用于审计、追溯和异常定位，不建议直接暴露给 NL2SQL。

---

### 3.3 DWD 层建议表

#### `dwd_ba_isp_monthly_fact`

用途：产销存标准月度事实长表，是后续查询和 NL2SQL 的主事实表。

建议粒度：

```text
一个来源文件 + 一个 sheet + 一个原始行项目 + 一个标准指标 + 一个已发布月份 + 一组标准维度
```

核心字段：

| 字段 | 含义 |
|---|---|
| `id` | 主键 |
| `business_year` | 年份 |
| `business_month` | 月份 |
| `period_start_date` | 期间开始日期 |
| `period_end_date` | 期间结束日期 |
| `data_cutoff_month` | 来源文件截止月份 |
| `is_published_month` | 是否已发布月份 |
| `domain` | 固定 `business_analysis` |
| `sub_domain` | 固定 `inventory_sales_production` |
| `metric_code` | 标准指标编码 |
| `metric_name` | 标准指标中文名 |
| `metric_category` | production / shipment / inventory / consignment / budget / rate |
| `aggregation_type` | flow_sum / period_end / calculated_ratio |
| `value_decimal` | 数值 |
| `unit_standard` | 标准单位，MW / percent |
| `base_name` | 基地：合肥、阜宁、广德等 |
| `factory_name` | 工厂：合肥一厂、阜宁二厂等 |
| `model_type` | 版型：P型、N型、182N、183N、210N、210R |
| `production_mode` | 生产模式：自产、代工、委外等 |
| `trade_scope` | 交易范围：全球营销中心、剔除内部交易等 |
| `is_outsourced` | 是否委外/代工 |
| `is_consigned` | 是否寄存 |
| `source_file_name` | 来源文件 |
| `source_file_sha256` | 来源文件哈希 |
| `source_sheet` | 来源 sheet |
| `source_row_index` | 来源行 |
| `source_col_index` | 来源列 |
| `source_cell_ref` | 来源单元格 |
| `raw_category` | 原始分类 |
| `raw_item` | 原始项目 |
| `raw_unit` | 原始单位 |
| `parser_version` | 解析器版本 |
| `quality_flags` | 质量标记 JSON |
| `created_at` / `updated_at` | 时间戳 |

关键约束：

1. 只导入已发布月份。
2. 2026 文件中的 5-12 月隐藏列不进入事实表。
3. 2023 年度列不进入事实表作为全年结果，只保留月度事实后重算。
4. 百分比指标优先不作为月度原始事实直接问答，而是由后端按分子/分母计算。

---

### 3.4 DWS 层建议表

#### `dws_ba_isp_period_fact`

用途：面向问答的期间事实表，由 DWD 月度事实按规则汇总生成。

核心字段：

| 字段 | 含义 |
|---|---|
| `business_year` | 年份 |
| `period_type` | month / quarter / half_year / year / ytd |
| `period_label` | 2025-01、2025-Q1、2025-YTD 等 |
| `period_start_month` | 起始月份 |
| `period_end_month` | 结束月份 |
| `metric_code` | 标准指标 |
| `value_decimal` | 聚合后数值 |
| `unit_standard` | 单位 |
| `base_name` / `model_type` / `production_mode` | 维度 |
| `aggregation_type` | flow_sum / period_end / calculated_ratio |
| `source_month_count` | 参与计算的月份数 |
| `source_row_count` | 参与计算的事实行数 |
| `data_cutoff_month` | 数据截止月份 |
| `calculation_policy` | 计算策略编码 |
| `quality_flags` | 质量标记 |

生成规则：

1. 流量指标：按月份 SUM。
2. 时点指标：取期间内最后一个已发布月份的值。
3. 比率指标：用后端公式重算，而不是平均月度比率。
4. 2023 年度：强制 `recompute_from_months_1_12`。
5. 2026 年度：强制 `recompute_from_published_months_1_4`。

---

### 3.5 语义目录建议表

#### `dim_ba_isp_metric`

用途：标准指标定义。

字段建议：

| 字段 | 含义 |
|---|---|
| `metric_code` | 指标编码 |
| `metric_name` | 中文指标名 |
| `metric_category` | 指标分类 |
| `aggregation_type` | 聚合类型 |
| `unit_standard` | 标准单位 |
| `description` | 业务说明 |
| `calculation_formula` | 后端公式说明 |
| `requires_budget` | 是否需要预算 |
| `is_default_for_sales` | 是否作为“销量”默认口径 |
| `is_active` | 是否启用 |

#### `dim_ba_isp_metric_alias`

用途：中文问法、原始字段、同义词映射。

字段建议：

| 字段 | 含义 |
|---|---|
| `alias_text` | 别名文本 |
| `metric_code` | 标准指标 |
| `alias_type` | user_phrase / raw_excel_item / synonym |
| `priority` | 优先级 |
| `requires_explicit_phrase` | 是否必须显式触发 |
| `notes` | 说明 |

示例：

| alias_text | metric_code | 说明 |
|---|---|---|
| 销量 | `shipment_volume` | 用户确认默认销量=发货 |
| 销售量 | `shipment_volume` | 同上 |
| 发货量 | `shipment_volume` | 同上 |
| 实际发出量 | `shipment_volume` | 2024 原始字段 |
| 开票销量 | `invoice_sales_volume` | 仅显式问开票时使用 |
| 开票合计 | `invoice_sales_volume` | 2023 原始字段 |
| 存货 | `ending_inventory_volume` | 时点指标 |
| 库存 | `ending_inventory_volume` | 时点指标 |
| 寄存仓 | `consigned_inventory_volume` | 时点指标 |

---

## 4. 解析器设计

### 4.1 解析器分层

建议后续 M2 实现时将解析器分为三层：

```text
WorkbookScanner
  负责文件名、sheet、范围、公式、隐藏列、外链、hash、截止月份识别。

SheetLayoutParser
  负责不同年份/sheet 的表头、行区块、月份列、汇总列定位。

FactNormalizer
  负责把原始行项目转换为标准指标、维度和 DWD 月度事实。
```

### 4.2 文件版本识别

规则：

| 文件 | 年份 | 截止月份 |
|---|---:|---:|
| `2023年产量与预算达成率分析.xlsx` | 2023 | 12 |
| `经营数据汇总表2024年.xlsx` | 2024 | 12 |
| `组件事业部月度产销存-2025年.xlsx` | 2025 | 12 |
| `组件事业部月度产销存-2026.04.xlsx` | 2026 | 4 |

后续每月更新建议要求文件名包含截止月份，例如：

```text
组件事业部月度产销存-2026.05.xlsx
组件事业部月度产销存-2026.06.xlsx
```

如果文件名无法识别截止月份，应进入待确认状态，不自动按全年导入。

### 4.3 2023 解析策略

1. Sheet 固定识别为 `0103`。
2. A/B 列作为分类和项目，C 列为单位。
3. I-T 列为 1-12 月月度事实。
4. D-H 列作为原始汇总列只用于审计，不作为正式期间事实。
5. 年度和预算达成率由 DWS 后端重算。
6. `销量` 分类默认不作为用户问“销量”的首选；用户问销量默认转向 `发货` 分类。
7. 用户明确问“开票”时，才查询 `开票合计`。

### 4.4 2024 解析策略

1. `2024` sheet 作为汇总来源，负责产出、发货、库存。
2. `明细` sheet 作为目标、工厂明细、版型结构和发货细分来源。
3. 两个 sheet 的同口径指标不能重复累计。
4. 对问答默认指标优先级：

```text
发货/销量：优先 `2024` sheet 的发货合计；需要明细时使用 `明细` sheet 发货细分。
产量：优先 `2024` sheet 的产出合计；需要目标/版型/工厂明细时使用 `明细` sheet。
库存：使用 `2024` sheet 的库存（SAP数据）。
```

5. 预算达成率可由 `明细` sheet 中目标与实际产量计算，但必须明确目标口径。

### 4.5 2025 解析策略

1. `产销存汇总` 是标准模板。
2. H-S 列为 1-12 月月度事实。
3. C-G 年度/季度列作为校验参考，不作为唯一事实来源。
4. 产量、发货按流量 SUM 聚合。
5. 库存、寄存按期末 LAST 聚合。
6. 版型、基地、生产模式从 `项目` 文本中抽取并标准化。

### 4.6 2026 解析策略

1. `产销存汇总` 与 2025 类似，但没有 Q4。
2. 文件名 `2026.04` 表示截止 4 月。
3. G-J 列为 1-4 月已发布月度事实。
4. K-R 列对应 5-12 月，当前隐藏且未发布，不导入事实。
5. 问“2026 年”时：
   - 流量指标返回截至 4 月累计。
   - 时点指标返回 4 月期末值。
6. Q2 当前只表示截至 4 月的 Q2 已发布数据，不能补 5/6 月为 0。

---

## 5. 后端计算策略

### 5.1 指标聚合策略

| 指标类型 | 聚合策略 | 示例 |
|---|---|---|
| 流量 SUM | 对已发布月份求和 | 产量、发货量、预算 |
| 时点 LAST | 取期间最后已发布月份 | 库存、存货、寄存 |
| 比率 CALCULATED | 后端分子/分母重算 | 预算达成率 |
| 显式开票 | 仅显式触发 | 开票销量 |

### 5.2 2023 年度重算策略

策略编码：

```text
policy_2023_recompute_annual_from_12_months
```

规则：

```text
2023 年度产量 = SUM(2023-01 ... 2023-12 月度产量)
2023 年度预算 = SUM(2023-01 ... 2023-12 月度预算)
2023 达成率（含委外） = SUM(实际产出量含委外 1-12月) / SUM(年度预算 1-12月)
2023 达成率（不含委外） = SUM(实际产量不含委外 1-12月) / SUM(年度预算 1-12月)
```

禁止：

```text
直接使用 Excel D列 23年作为全年事实。
```

### 5.3 2026 截止月策略

策略编码：

```text
policy_current_year_use_published_months_only
```

规则：

```text
2026 当前发布月份 = 1-4 月
2026 产量/发货 = SUM(1-4 月)
2026 存货/寄存 = 4 月期末值
2026 Q2 = 当前已发布 Q2 月份，即 4 月；不补 5/6 月
```

禁止：

```text
把 5-12 月隐藏列、空值、0 当成实际数据。
```

### 5.4 销量/发货策略

策略编码：

```text
policy_sales_defaults_to_shipment_volume
```

规则：

```text
用户问：销量、销售量、卖了多少、出货量、发货量、实际发出量
默认指标：shipment_volume
```

显式例外：

```text
用户明确问：开票、开票销量、开票量
指标：invoice_sales_volume
```

---

## 6. 受控 QueryPlan MVP 设计

在统一 NL2SQL 完整接入前，产销存可以先用受控 QueryPlan MVP。关键是输出结构必须兼容未来 SQLPlan，而不是直接规则查表。

### 6.1 QueryPlan 结构

示例：用户问“2025 年各基地销量分别是多少？”

```json
{
  "domain": "business_analysis",
  "sub_domain": "inventory_sales_production",
  "intent": "metric_breakdown",
  "metrics": ["shipment_volume"],
  "dimensions": ["base_name"],
  "filters": {
    "business_year": 2025
  },
  "period": {
    "period_type": "year",
    "year": 2025
  },
  "calculation_policy": "flow_sum",
  "display_preference": "narrative_with_table"
}
```

示例：用户问“2026 年截至目前产量是多少？”

```json
{
  "domain": "business_analysis",
  "sub_domain": "inventory_sales_production",
  "intent": "metric_summary",
  "metrics": ["production_actual_including_oem"],
  "dimensions": [],
  "filters": {
    "business_year": 2026
  },
  "period": {
    "period_type": "ytd",
    "year": 2026,
    "end_month": 4
  },
  "calculation_policy": "policy_current_year_use_published_months_only"
}
```

### 6.2 QueryPlan 校验规则

1. `domain` 必须是 `business_analysis`。
2. `sub_domain` 必须是 `inventory_sales_production`。
3. `metrics` 必须来自 `dim_ba_isp_metric` 白名单。
4. `dimensions` 必须来自语义目录白名单。
5. 年份必须在已导入文件范围内。
6. 月份必须是已发布月份。
7. 2026 不允许查询 5 月及之后的实际值。
8. 库存/存货/寄存不允许使用 SUM 聚合。
9. 预算达成率缺少预算数据时必须 fail closed。
10. “销量”必须归一为 `shipment_volume`，除非用户明确问“开票”。

### 6.3 查询执行方式

MVP 阶段不让 LLM 写 SQL。程序根据 QueryPlan 选择预定义查询能力：

| query_key | 能力 | 说明 |
|---|---|---|
| `ba_isp_metric_summary` | 单指标汇总 | 例如全年产量、截至目前销量 |
| `ba_isp_metric_breakdown` | 按维度拆分 | 例如各基地发货、各版型产量 |
| `ba_isp_metric_trend` | 月度趋势 | 例如 2025 年每月产量走势 |
| `ba_isp_budget_achievement` | 预算达成率 | 后端按实际/预算重算 |
| `ba_isp_inventory_snapshot` | 时点库存 | 例如 2026 年 4 月末存货 |
| `ba_isp_period_compare` | 年/月/基地对比 | 例如 2025 与 2026 同期产量对比 |

每个 query_key 对应固定 repository 查询模板和参数校验，不执行 LLM 自由 SQL。

---

## 7. 未来 NL2SQL 接入方案

统一 NL2SQL 稳定后，产销存可从受控 QueryPlan 平滑升级为 SQLPlan。

目标链路：

```text
用户问题
↓
领域路由：business_analysis.inventory_sales_production
↓
语义目录召回：指标、维度、口径、样例 QueryPlan
↓
LLM 生成 SQLPlan 候选，不直接生成可执行 SQL
↓
SQLPlan Validator 校验指标、维度、时间、聚合、表白名单
↓
SQL Renderer 渲染只读 SQL
↓
SQL Safety 二次校验
↓
EXPLAIN / dry run / row limit
↓
只读查询智能助手中间库
↓
确定性结果
↓
LLM 仅基于结果做业务化表达
```

### 7.1 语义目录条目示例

```yaml
metric_code: shipment_volume
metric_name: 发货量/销量
business_definition: 用户确认“销量”等同“发货量”，默认按发货口径返回。
source_tables:
  - dwd_ba_isp_monthly_fact
  - dws_ba_isp_period_fact
allowed_dimensions:
  - business_year
  - business_month
  - base_name
  - model_type
  - production_mode
aggregation_type: flow_sum
unit: MW
aliases:
  - 销量
  - 销售量
  - 发货量
  - 出货量
  - 实际发出量
safety_rules:
  - explicit_invoice_phrase_required_for_invoice_sales
```

### 7.2 SQLPlan 候选示例

```json
{
  "select_metrics": [
    {"metric_code": "shipment_volume", "aggregation": "sum"}
  ],
  "dimensions": ["base_name"],
  "filters": [
    {"field": "business_year", "op": "=", "value": 2025}
  ],
  "source_subject": "dws_ba_isp_period_fact",
  "period": {
    "period_type": "year",
    "year": 2025
  },
  "safety": {
    "read_only": true,
    "row_limit": 200
  }
}
```

该 SQLPlan 仍不是可执行 SQL，必须经过 validator 和 renderer。

### 7.3 SQLPlan Validator 规则

1. 只允许查询产销存白名单主题表。
2. 禁止查询 ODS 原始单元格表作为普通问答事实来源；除非是审计追溯接口。
3. 禁止 `SELECT *`。
4. 禁止 DDL/DML。
5. 禁止跨业务域 join。
6. 禁止引用非白名单字段。
7. 聚合函数必须与指标聚合类型匹配。
8. 时点指标只允许 LAST_VALUE / max period end 语义，不允许 SUM。
9. 2023 年度必须命中重算策略。
10. 2026 必须带 `data_cutoff_month <= 4` 或已发布月份约束。
11. 缺预算时预算达成率不得退化为产量查询。
12. 用户显式问开票时才允许 `invoice_sales_volume`。

---

## 8. 回答展示设计

### 8.1 回答原则

1. 用户可见回答只展示业务含义、数据口径、关键结果和必要提醒。
2. 不暴露表名、SQL、字段名、query_key、planner、guardrail、debug、schema 等技术内容。
3. LLM 只能基于后端返回的结构化事实润色，不能新增数字和结论。
4. 普通问题默认用自然语言回答；表格、趋势图、排行仅在问题需要或用户明确要求时展示。
5. 数据来源以业务化方式展示，例如“来源：2025 年组件事业部月度产销存文件，已发布 1-12 月”。

### 8.2 响应结构建议

```json
{
  "status": "success",
  "answer": "业务化自然语言回答",
  "result_table": {
    "columns": [],
    "rows": []
  },
  "calculation_basis": {
    "metric": "发货量/销量",
    "period": "2025年全年",
    "aggregation": "按月度发货量求和",
    "unit": "MW"
  },
  "data_scope": {
    "source_file": "组件事业部月度产销存-2025年.xlsx",
    "published_months": [1,2,3,4,5,6,7,8,9,10,11,12]
  },
  "warnings": []
}
```

### 8.3 典型回答口径

用户问：“2026 年销量是多少？”

回答应体现：

```text
2026 年当前产销存文件已发布到 4 月，因此这里的销量按发货口径统计为 1-4 月累计发货量。
```

用户问：“2023 年预算达成率是多少？”

回答应体现：

```text
2023 年原表年度列漏计 12 月，本次按 1-12 月实际产量和预算重新计算。
```

---

## 9. 测试与验收设计

### 9.1 M2 Parser focused tests

至少覆盖：

1. 四个 Excel 文件均可识别年份、sheet、表头和数据截止月份。
2. 2023 年只导入 1-12 月事实，不把 `23年` 列当全年事实。
3. 2023 全年产量按 1-12 月求和。
4. 2023 预算达成率按 1-12 月实际/预算重算。
5. 2024 汇总表和明细表不重复计算同口径数据。
6. 2025 流量指标年度值等于 1-12 月求和。
7. 2025 库存年度值等于 12 月期末值。
8. 2026 文件识别 `data_cutoff_month=4`。
9. 2026 隐藏列 K:R 不导入事实。
10. 2026 年度产量只按 1-4 月累计。
11. 2026 年度存货取 4 月期末值。
12. 销量、销售量、发货量均归一到 `shipment_volume`。
13. 开票销量只在显式“开票”问法下归一到 `invoice_sales_volume`。

### 9.2 QueryPlan focused tests

至少覆盖：

1. “2025 年销量是多少” → `shipment_volume + year=2025`。
2. “2025 年各基地销量分别是多少” → `shipment_volume + dimension=base_name`。
3. “2023 全年产量是多少” → 命中 2023 12 个月重算策略。
4. “2023 预算达成率是多少” → 命中后端计算策略。
5. “2026 年截至目前产量是多少” → end_month=4。
6. “2026 年 5 月销量是多少” → 返回未发布月份说明，不自动返回 0。
7. “2025 年末库存是多少” → period_end 聚合。
8. “2025 年库存合计是多少” → 不使用 SUM，取年末值。
9. “2024 年开票销量是多少” → 数据源无明确开票时返回缺数据说明。
10. “2023 年开票销量是多少” → 显式开票口径查询。

### 9.3 NL2SQL 接入验收

后续接入统一 NL2SQL 后，需验证：

1. SQLPlan 只引用白名单产销存主题表。
2. 时点指标不生成 SUM。
3. 2023 年度不使用原始年度列。
4. 2026 不查询未发布月份。
5. 结果数字与受控 QueryPlan MVP 一致。
6. 空结果或缺口径不被 LLM 粉饰为成功回答。
7. 用户可见回答不暴露 SQL、表名、字段名、planner 等技术内容。

---

## 10. 阶段拆分建议

### M1：审计与建模方案（本轮）

交付：

```text
docs/INVENTORY_SALES_PRODUCTION_EXCEL_AUDIT.md
docs/INVENTORY_SALES_PRODUCTION_NL2SQL_COMPAT_PLAN.md
```

不做实现。

### M2：Excel 入库与解析器 MVP

目标：把四个 Excel 解析为标准月度事实长表。

建议任务：

1. 新建 `business_analysis` 后端目录骨架。
2. 新建 Alembic 迁移：workbook、sheet、cell、monthly_fact、metric、alias。
3. 写 parser focused tests，先 RED。
4. 实现 WorkbookScanner。
5. 实现 2023/2024/2025/2026 SheetLayoutParser。
6. 实现 FactNormalizer。
7. 写导入服务和批次追溯。
8. 导入四个附件并输出质量报告。

### M3：受控问答 MVP

目标：支持首批产量、销量/发货、库存、寄存、预算达成率问题。

建议任务：

1. 新增 QueryPlan schema。
2. 新增指标/维度 resolver。
3. 新增 QueryPlan validator。
4. 新增 repository 查询模板。
5. 新增 QA service。
6. 新增流式回答适配。
7. 写 20 条 focused QA tests。

### M4：前端入口与业务化展示

目标：在智能助手中增加经营分析/产销存入口。

建议任务：

1. 复用现有 BusinessChatPage。
2. 增加 business_analysis domain switch。
3. 展示自然语言回答、数据口径、来源文件、发布月份、明细表。
4. 普通回答默认 narrative，不强制展开技术表格。

### M5：统一 NL2SQL 接入

目标：将产销存纳入统一 NL2SQL 语义目录和 SQLPlan validator。

建议任务：

1. 产销存 semantic catalog 入库。
2. 产销存 SQLPlan validator 白名单。
3. Shadow 对比 QueryPlan MVP 与 NL2SQL 结果。
4. 通过灰度日志确认稳定后逐步接管。

---

## 11. 实施时的强制禁止项

1. 禁止把产销存逻辑继续塞进物流 `data_qa_planner.py`。
2. 禁止把 Excel 原始宽表作为 LLM 可自由查询的表。
3. 禁止让 LLM 直接读 Excel 回答。
4. 禁止让 LLM 直接生成 SQL 并执行。
5. 禁止把 2023 原年度列当作全年事实。
6. 禁止把 2026 未发布月份当作 0 或实际数据。
7. 禁止对库存、存货、寄存做年度 SUM。
8. 禁止用户问“销量”时默认返回开票口径。
9. 禁止为了少数样例题 hardcode 答案。
10. 禁止在用户可见回答中暴露内部技术实现。

---

## 12. 首批语义目录草案

### 12.1 指标

| 指标编码 | 中文名 | 默认触发词 | 聚合类型 | 默认问答状态 |
|---|---|---|---|---|
| `production_actual_including_oem` | 实际产量（含委外） | 产量、实际产量、产出 | flow_sum | 支持 |
| `production_actual_excluding_oem` | 实际产量（不含委外） | 不含委外产量 | flow_sum | 支持 |
| `shipment_volume` | 发货量/销量 | 销量、销售量、发货量、出货量 | flow_sum | 支持，默认销量口径 |
| `invoice_sales_volume` | 开票销量 | 开票、开票销量 | flow_sum | 仅显式支持 |
| `ending_inventory_volume` | 期末库存/存货 | 库存、存货、库存合计 | period_end | 支持 |
| `consigned_inventory_volume` | 寄存库存 | 寄存、寄存仓 | period_end | 支持 |
| `production_budget` | 产量预算/目标 | 预算、目标、产量目标 | flow_sum | 部分年份支持 |
| `production_budget_achievement_rate_including_oem` | 预算达成率（含委外） | 达成率、预算达成率 | calculated_ratio | 2023/2024 可支持 |
| `production_by_model_type` | 版型产量 | N型、P型、182N、183N、210N、210R | flow_sum | 支持 |

### 12.2 维度

| 维度编码 | 中文名 | 示例 |
|---|---|---|
| `business_year` | 年份 | 2023、2024、2025、2026 |
| `business_month` | 月份 | 1月、2月、3月 |
| `quarter` | 季度 | Q1、Q2、Q3、Q4 |
| `base_name` | 基地 | 合肥、阜宁、广德 |
| `factory_name` | 工厂 | 合肥一厂、阜宁二厂 |
| `model_type` | 版型 | N型、P型、182N、210N |
| `production_mode` | 生产模式 | 自产、代工、委外 |
| `trade_scope` | 交易范围 | 全球营销中心、剔除内部交易 |

---

## 13. 首批验收问法草案

| 问题 | 预期能力 |
|---|---|
| 2023 全年产量是多少？ | 2023 年按 1-12 月重算 |
| 2023 年预算达成率是多少？ | 2023 年实际/预算重算 |
| 2024 年各基地发货量是多少？ | 发货量按基地拆分 |
| 2024 年合肥产量目标达成情况怎么样？ | 目标与实际对比 |
| 2025 年销量是多少？ | 销量归一为发货量 |
| 2025 年各基地销量分别是多少？ | 发货量按基地拆分 |
| 2025 年末库存是多少？ | 年末库存取 12 月期末 |
| 2025 年 210N 产量是多少？ | 版型维度过滤 |
| 2026 年截至目前产量是多少？ | 截至 4 月累计 |
| 2026 年 5 月销量是多少？ | 返回 5 月未发布说明 |
| 2026 年 4 月末存货是多少？ | 4 月期末存货 |
| 2026 年 Q2 销量是多少？ | 当前 Q2 仅含 4 月已发布数据 |

---

## 14. 与现有能力的影响评估

| 能力 | 是否影响 | 说明 |
|---|---|---|
| 物流问答 | 否 | 产销存为独立经营分析子域，不修改物流链路 |
| 物流 NL2SQL | 否 | 后续只复用架构思想和语义目录/SQLPlan 机制 |
| 物管 SAP MID | 否 | 产销存 Excel 与物管 SAP Oracle MID 不混用 |
| 计划 BOM | 否 | 不接入计划 BOM 域 |
| 功率预测 | 否 | 不修改功率模型、功率问答、前端 |
| 前端智能助手 | M1 无影响 | M1 不改前端，后续 M4 再接入口 |

---

## 15. M1 完成标准

本轮 M1 完成后应满足：

1. 四个 Excel 的结构、公式、隐藏列和字段差异已记录。
2. 用户确认的业务口径已写入文档。
3. 明确了产销存应作为经营分析子域建设。
4. 明确了标准长表事实模型。
5. 明确了流量/时点/比率三类聚合策略。
6. 明确了销量=发货量的默认口径。
7. 明确了 2023、2026 特殊处理规则。
8. 明确了受控 QueryPlan MVP 与未来 NL2SQL 的兼容路径。
9. 未修改代码、接口、迁移、前端。

---

## 16. 结论

产销存能力不需要等待物流 NL2SQL 完成后再做。当前应先完成数据资产标准化和问答最小闭环，但必须从 M2 开始就采用未来 NL2SQL 可接管的结构：

```text
标准指标目录 + 标准维度目录 + 标准长表事实 + 受控 QueryPlan + 确定性计算 + 业务化表达
```

这样后续统一 NL2SQL 接入时，只需要替换或增强 QueryPlan / SQLPlan 生成层，不需要重做数据模型、口径规则、计算逻辑和验收题集。

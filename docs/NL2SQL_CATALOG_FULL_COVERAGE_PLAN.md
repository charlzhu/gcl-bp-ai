# NL2SQL Catalog 全覆盖修复计划

## 一、目标

让所有业务域的维度、指标、字段语义、规则、示例 **全部覆盖到 YAML catalog** 中，
确保 NL2SQL 链路能正确理解用户问法并生成精准的 SQLPlan。

## 二、各域当前 vs 目标状态

| 业务域 | tables | metrics | dimensions | rules | examples | join |
|---|---|---|---|---|---|---|
| **物流 logistics** | ✅ 8/8 | ❌ 8→**30+** | ❌ 8→**15+** | ✅ 6 | ❌ 2→**10+** | ✅ 3 |
| **产销存 business_analysis** | ❌ 0→**3** | ❌ 0→**31** | ❌ 0→**10+** | ❌ 0→**5+** | ❌ 0→**5+** | ❌ 0 |
| **计划BOM plan_bom** | ❌ 0→**8** | ❌ 0→**10+** | ❌ 0→**10+** | ❌ 0→**5+** | ❌ 0→**5+** | ❌ 0 |

## 三、修复步骤

### P0：物流域维度补齐（30分钟）
**当前 8 个维度 → 目标 15+ 个维度**

**缺失的5个常用维度**：
1. `expand_dept`（扩充部门）— 用户问"经营计划"需要
2. `entrusted_person`（委托人）— 用户问人名（刘娟等）需要
3. `required_vehicle_type`（车型）— 用户问车型需要
4. `contract_no`（合同号）— 用户按合同号查需要
5. `warehouse_name`（仓库）— 用户按仓库分组需要

**当前5个维度缺 business_note**：
- `region_name`、`customer_name`、`origin_place`、`city`、`transport_mode`

### P1：物流域指标补齐（2-3小时）
**当前 8 个指标 → 目标 30+ 个指标**

基于 query_key 分析，核心需要补充的指标类型：

| 类别 | 核心 query_key 示例 | 新增指标 |
|---|---|---|
| 费用类 | `total_fee_summary`, `total_fee_by_province`, `total_fee_city_rank` | `total_fee_summary`, `total_fee_by_province` |
| 发运量类 | `mw_summary`, `mw_by_region_province`, `mw_by_origin_and_carrier` | `mw_summary`, `mw_by_region` |
| 车次类 | `monthly_trip_count_summary`, `trip_count_by_region`, `vehicle_type_trip_count` | `trip_count_summary`, `trip_count_by_region` |
| 运价类 | `route_pricing_analysis`, `avg_fee_per_watt_by_transport`, `avg_fee_by_month` | `avg_fee_per_watt`, `route_pricing` |
| 排名类 | `carrier_metric_ranking`, `top_customers_fee_and_mw_by_province` | `carrier_ranking`, `top_customer` |
| 系统侧 | `sys_mw_and_trip_count`, `sys_total_fee_by_filters`, `sys_avg_loading_trucks` | `sys_total_fee`, `sys_mw` |

### P2：产销存域 catalog 创建（2-3小时）

**新建目录**：`backend/app/domains/logistics/config/nl2sql_catalog/business_analysis/`

| 文件 | 内容 | 条目数 |
|---|---|---|
| `tables.yaml` | dwd_ba_isp_monthly_fact, dim_ba_isp_metric, dim_ba_isp_metric_alias | 3 |
| `metrics.yaml` | 31 个标准指标（production/sales/inventory/cost 四大类） | 31 |
| `dimensions.yaml` | 基地、工厂、产品型号、生产模式、贸易范围、委外标记等 | 10+ |
| `rules.yaml` | 预算口径、已发布月份过滤、内部交易剔除等 | 5+ |
| `examples.yaml` | 产销存典型问答示例 | 5+ |

### P3：计划 BOM 域 catalog 创建（2-3小时）

**新建目录**：`backend/app/domains/logistics/config/nl2sql_catalog/plan_bom/`

| 文件 | 内容 | 条目数 |
|---|---|---|
| `tables.yaml` | 6 BOM 表 + 6 功率表 | 12 |
| `metrics.yaml` | 材料数量、版本数、功率档位、效率值等 | 10+ |
| `dimensions.yaml` | 订单号、版本号、SAP编码、物料类别、供应商等 | 10+ |
| `rules.yaml` | 版本消歧、搭配判定、评审号归一化等 | 5+ |
| `examples.yaml` | BOM 查询典型示例 | 5+ |

### P4：重新索引 + 全量回归验证

1. 重新生成所有 catalog 文档向量
2. 写入 Milvus
3. 验证 recall 能在三种自然问法下正确召回
4. 全量单元测试回归

---

*执行人：Hermes Agent*
*预计总工时：6-10 小时*

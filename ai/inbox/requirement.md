# Goal：物管域 SAP Oracle MID 数据同步、智能问数与前端适配建设

> 建议文件路径：`gc_bp_ai/ai/inbox/requirement.md`  
> 执行模式：Hermes Goal Mode  
> 项目名称：经营计划智能助手 / gc_bp_ai  
> 当前首次执行阶段：M1 数据资产审计、同步方案设计、中间库建模、智能问数链路设计、前端适配方案设计  
> 核心原则：SAP Oracle MID 只作为外部同步源；用户问答必须基于智能助手中间库，不允许面向用户实时直接查询 SAP Oracle MID。

---

## 0. 本次 Goal 总目标

本次任务有三个总体目标。

---

### 目标一：将 SAP Oracle MID 库中的相关视图同步到智能助手中间库

需要通过代码层连接 SAP Oracle MID，将物管业务域、计划 BOM 业务域相关视图数据同步到智能助手中间库。

同步能力必须同时支持：

#### 1. 自动同步

要求：

1. 支持定时任务。
2. 支持全量初始化同步。
3. 支持后续增量同步。
4. 支持按业务主题同步。
5. 支持按单个 SAP MID 视图同步。
6. 支持同步批次记录。
7. 支持同步任务日志。
8. 支持同步错误日志。
9. 支持失败重试。
10. 支持幂等执行，重复同步不能产生脏数据或重复业务数据。
11. 支持同步结果统计，例如读取行数、写入行数、更新行数、跳过行数、失败行数。

#### 2. 手动同步

要求：

1. 支持人工触发某个业务主题同步。
2. 支持人工触发某个 SAP MID 视图同步。
3. 支持指定时间范围同步。
4. 支持指定同步模式，例如全量、增量、重跑。
5. 支持查看同步任务状态。
6. 支持查看同步结果。
7. 支持失败后重试。
8. 后续前端需要提供手动同步入口。
9. M1 阶段只设计手动同步方案，不直接大规模开发。
10. M2 起可优先实现后端 CLI / 管理接口；前端入口随接口成熟后逐步增加。

---

### 目标二：基于智能助手中间库实现智能问数、分析和回答

智能助手不能面向用户实时直接查询 SAP Oracle MID。

用户问数时，必须基于已经同步沉淀到智能助手中间库中的 ODS / DWD / DWS / DM 表进行准确查询，再由 LLM 润色回答。

目标链路如下：

```text
用户自然语言问题
    ↓
LLM 进行问题理解、业务域识别、意图识别、参数抽取
    ↓
程序根据识别结果选择业务对象、字段字典、SQL 模板、查询服务
    ↓
程序查询智能助手中间库
    ↓
程序返回结构化查询结果、查询条件、来源信息
    ↓
LLM 基于用户问题 + 查询结果 + 来源信息生成自然语言回答
    ↓
前端展示回答、明细、查询条件、来源追溯
```

核心原则：

```text
LLM 负责理解和表达。
程序负责准确查数。
第一阶段不允许让 LLM 自由生成 SQL 直接查库。
```

---

### 目标三：前端页面适配物管业务域与 SAP/MID 同步能力

当前前端页面主要适配了物流和计划 BOM 的问答能力，尚未完整适配物管业务域。

后续需要在前端增加或优化：

1. 智能问答页中增加物管业务域问答能力。
2. 手动同步 SAP/MID 数据触发入口。

具体包括：

#### 1. 智能问答页增加物管业务域问答能力

要求：

1. 在现有智能问答页中增加“物管”业务域入口或业务域选择能力。
2. 用户选择或识别为物管业务域后，问题应进入物管问数链路。
3. 支持物管相关问题提交，例如库存、出入库、采购执行、工单组件、物料消耗等。
4. 前端展示方式应与现有物流、计划 BOM 问答体验保持一致。
5. 前端需要展示流式自然语言回答。
6. 前端需要展示结构化查询结果。
7. 前端需要展示查询条件。
9. 前端需要展示空结果、错误、暂不支持、需要澄清等状态。
10. 前端不能破坏现有物流和计划 BOM 页面。

#### 2. 增加手动同步 SAP/MID 数据触发入口

要求：

1. 前端需要提供 SAP/MID 手动同步入口。
2. 支持选择同步业务主题，例如库存、出入库、采购执行、工单组件、SAP BOM。
3. 支持选择同步模式，例如全量、增量、指定时间范围。
4. 支持触发手动同步任务。
5. 支持展示同步任务状态。
6. 支持展示同步开始时间、结束时间、读取行数、写入行数、失败行数。
7. 支持展示错误信息摘要。
8. 支持失败后重试入口。
9. M1 阶段只做前端适配方案，不直接开发页面。
10. M2 起根据后端能力逐步开发手动同步入口。

前端整体交互流程应与现有物流、计划 BOM 保持一致：

```text
用户输入问题
    ↓
前端提交到对应业务域问答接口
    ↓
后端进行 LLM 意图识别与程序查数
    ↓
前端展示自然语言回答、结构化结果、来源信息、明细表格
```

M1 阶段只允许输出前端适配方案，不直接大规模修改前端。  
M2 以后再根据后端能力逐步开发页面。

---

## 1. 当前业务背景

经营计划部智能助手平台规划包含四大业务域：

1. 物流
2. 物管
3. 计划 BOM
4. 经营分析

本次 SAP Oracle MID 数据接入，主要归属于：

```text
物管业务域
```

同时，本次任务还涉及：

```text
计划 BOM 业务域的数据源改造
```

当前计划 BOM 问答能力主要依赖手动上传的 BOM Excel。后续需要支持 SAP BOM 数据源，将 SAP BOM 相关视图同步到智能助手中间库，并逐步与现有计划 BOM 查询 / 问答能力兼容。

---

## 2. 当前系统现状

当前项目不是从零开始。必须基于已有智能助手项目进行扩展。

---

### 2.1 已有物流业务域

当前智能助手中间库已经支持公司物流数据同步，并形成了较清晰的数据分层。

已有代表表包括：

```text
ods_logistic_*
dwd_logistics_*
dws_logistics_*
dm_logistics_*
```

需要重点参考现有物流域的：

1. ODS 原始同步层设计。
2. DWD 标准明细层设计。
3. DWS 统一主题层设计。
4. DM 面向问数结果层设计。
5. 数据同步任务设计。
6. 查询服务设计。
7. NLU / SQL 模板 / 查询日志设计。
8. 前端问答页面与结果展示方式。

---

### 2.2 已有计划 BOM 业务域

当前已有计划 BOM 问答功能，主要数据来源是手动上传 BOM Excel 文件。

已有相关表包括：

```text
plan_bom_import_batch
plan_bom_header
plan_bom_revision
plan_bom_material_line
plan_bom_export_task
```

本任务不能推翻现有 BOM Excel 能力，而是要设计为：

```text
Excel BOM 数据源
SAP BOM 数据源
```

在一段时间内并存，并逐步向 SAP BOM 标准数据源演进。

如果现有表结构已经支持 `source_type`、`source_tag`、`import_batch_id` 等字段，应优先复用；如果不支持，需要提出兼容改造方案，不要贸然破坏现有功能。

---

### 2.3 当前物管业务域

当前物管业务域可作为本次 SAP MID 数据接入的主要承接域。

建议后续新增或扩展后端目录时，优先归入：

```text
backend/app/domains/material_management/
```

不要新建一个完全割裂的 `sap` 业务域。

---

### 2.4 当前前端状态

当前前端主要适配：

1. 物流问答。
2. 计划 BOM 问答。

当前前端尚需补充：

1. 物管业务域问答入口。
2. 物管问答结果展示能力。
3. SAP/MID 手动同步触发入口。
4. SAP/MID 同步任务状态展示能力。
5. SAP/MID 同步日志展示能力。

M1 阶段必须分析当前前端结构，包括：

1. 当前路由结构。
2. 当前页面结构。
3. 当前 API 封装方式。
4. 当前问答组件复用方式。
5. 当前物流问答页面。
6. 当前计划 BOM 问答页面。
7. 当前布局菜单入口。
8. 当前结果展示组件。
9. 当前状态组件，例如 loading、empty、error、clarify、unsupported。

---

## 3. SAP Oracle MID 连接配置

SAP Oracle MID 连接信息已经配置在项目：

```text
backend/.env
```

配置项为：

```text
SAP_ORACLE_HOST
SAP_ORACLE_PORT
SAP_ORACLE_SERVICE
SAP_ORACLE_USER
SAP_ORACLE_PASSWORD
```

要求：

1. 代码必须通过环境变量读取这些配置。
2. 不允许在代码、文档、测试用例、日志、提交记录中硬编码真实账号密码。
3. 不允许将 `.env` 中的真实密码输出到报告。
4. 不允许将 `.env` 提交到 Git。
5. 如果需要示例配置，只能写入 `.env.example`，且必须使用占位符。
6. SAP Oracle MID 账号原则上应只读。
7. Oracle MID 只作为同步源，不作为用户实时问答查询库。

建议配置读取层放在基础设施层，例如：

```text
backend/app/infra/oracle/
```

或遵循当前项目已有配置规范。

---

## 4. SAP MID 已知视图范围

### 4.1 物管域：库存 / 出入库

```text
V_HF_SAP_INOUT_DAILY
V_SAP_HFFN_CRKLSZ
```

业务含义：

1. `V_HF_SAP_INOUT_DAILY`
   - 对应 ZMB52 实时库存。
   - 用于查询当前库存、现存量、结存数量、工厂、库存地点、批次、物料等。

2. `V_SAP_HFFN_CRKLSZ`
   - 对应 ZMB51 物料出入库明细。
   - 用于查询材料出入库、车间领料、退料、物料流转等流水。

---

### 4.2 物管域：采购执行

```text
V_SAP_HFFN_EKKO
V_SAP_HFFN_EKPO
V_SAP_HFFN_EKET
V_SAP_HFFN_EKBE
V_SAP_HFFN_EBAN
```

业务含义：

1. 采购申请。
2. 采购订单头。
3. 采购订单行。
4. 交货计划。
5. 采购历史。
6. 到货数量。
7. 未到货数量。
8. 延期情况。
9. 供应商交付情况。

---

### 4.3 物管域：生产订单 / 工单组件 / 实际用料

```text
V_SAP_HFFN_AFKO
V_SAP_HFFN_AFPO
V_SAP_HFFN_AUFK
V_SAP_HFFN_RESB
```

业务含义：

1. 生产订单头。
2. 生产订单行。
3. 工单主数据。
4. 工单组件。
5. 预留需求。
6. 实际生产用料。
7. 生产订单组件修改。
8. BOM 实际搭配确定化。

特别注意：

```text
STPO 更偏理论 BOM。
RESB 更偏生产订单实际组件需求。
```

---

### 4.4 计划 BOM 域：SAP BOM 数据源

```text
V_SAP_HFFN_MAST
V_SAP_HFFN_STKO
V_SAP_HFFN_STPO
V_SAP_HFFN_STAS
V_SAP_HFFN_STZU
```

业务含义：

1. `MAST`：物料与 BOM 的分配关系。
2. `STKO`：BOM 头。
3. `STPO`：BOM 组件明细。
4. `STAS`：BOM 项目选择 / 替代 / 有效性相关。
5. `STZU`：BOM 永久数据 / 辅助信息。

---

## 5. 已提供附件

请读取以下类型附件。

---

### 5.1 SAP MID 元数据附件

建议路径：

```text
ai/inbox/attachments/sap_mid/
```

包括：

```text
MID下所有视图.xlsx
MID下所有视图字段.xlsx
视图SQL.xlsx
```

用途：

1. 分析 MID 下有哪些视图。
2. 分析字段结构。
3. 分析视图 SQL。
4. 判断业务对象关系。
5. 判断主键、关联键、增量字段候选。

---

### 5.2 SAP MID 重点视图样例数据

建议路径：

```text
ai/inbox/attachments/sap_mid/
```

包括：

```text
V_HF_SAP_INOUT_DAILY.xlsx
V_SAP_HFFN_CRKLSZ.xlsx

V_SAP_HFFN_EKKO.xlsx
V_SAP_HFFN_EKPO.xlsx
V_SAP_HFFN_EKET.xlsx
V_SAP_HFFN_EKBE.xlsx
V_SAP_HFFN_EBAN.xlsx

V_SAP_HFFN_AFKO.xlsx
V_SAP_HFFN_AFPO.xlsx
V_SAP_HFFN_AUFK.xlsx
V_SAP_HFFN_RESB.xlsx

V_SAP_HFFN_MAST.xlsx
V_SAP_HFFN_STKO.xlsx
V_SAP_HFFN_STPO.xlsx
V_SAP_HFFN_STAS.xlsx
V_SAP_HFFN_STZU.xlsx
```

用途：

1. 辅助理解字段含义。
2. 辅助判断业务口径。
3. 辅助设计中间库字段。
4. 辅助设计查询模板。
5. 不作为正式数据源。

---

### 5.3 智能助手中间库表附件

建议路径：

```text
ai/inbox/attachments/middle_db/
```

包括：

```text
智能助手中间库表.zip
```

用途：

1. 分析当前中间库表结构。
2. 分析物流 ODS/DWD/DWS/DM 分层规范。
3. 分析 sys 日志表。
4. 分析计划 BOM Excel 数据模型。
5. 为 SAP MID 接入设计统一规范。

---

## 6. 必须读取的项目文件

请先读取并理解当前项目，不要盲目开发。

建议至少读取：

```text
AGENTS.md
README_WORKSPACE.md
docs/CURRENT_STATUS.md
docs/NEXT_TASK.md
docs/HANDOFF.md
backend/.env
backend/app/domains/logistics/
backend/app/domains/plan_bom/
backend/app/domains/material_management/
backend/app/domains/query_planning/
backend/app/core/
backend/app/infra/
backend/alembic/
frontend/
```

前端必须重点读取：

```text
frontend/src/router/
frontend/src/layouts/
frontend/src/views/
frontend/src/api/
frontend/src/components/
```

如果实际路径不同，请以当前项目结构为准。

注意：

1. 读取 `backend/.env` 只用于本地连接配置，不允许输出真实密钥。
2. 需要重点研究物流域的中间库同步和结构化问数链路。
3. 需要重点研究计划 BOM 现有 Excel 数据源模型。
4. 需要判断物管域当前是否已有代码骨架。
5. 需要研究前端当前如何接入物流和计划 BOM 问答。
6. 需要复用现有架构风格，不要另起一套割裂架构。

---

## 7. 总体架构要求

本任务必须采用以下架构：

```text
SAP Oracle MID
    ↓
代码层 Oracle 连接器
    ↓
同步任务：自动同步 / 手动同步 / 全量 / 增量
    ↓
智能助手中间库 ODS 层
    ↓
智能助手中间库 DWD 层
    ↓
智能助手中间库 DWS / DM 层
    ↓
物管 / 计划 BOM 查询服务
    ↓
LLM 意图识别 + 程序准确查数 + LLM 润色回答
    ↓
前端智能问答页展示
    ↓
用户
```

禁止采用以下架构：

```text
用户问题
    ↓
LLM
    ↓
直接查询 SAP Oracle MID
    ↓
回答用户
```

原因：

1. SAP Oracle MID 是外部同步源，不应作为用户问答实时查询库。
2. 直接查询 Oracle MID 不利于性能控制。
3. 直接查询 Oracle MID 不利于数据治理。
4. 直接查询 Oracle MID 不利于权限控制。
5. 直接查询 Oracle MID 不利于问答结果追溯。
6. 直接查询 Oracle MID 不利于统一指标口径。

---

## 8. 中间库建模要求

### 8.1 命名原则

物管域中间表建议采用统一命名风格。

候选命名如下，最终以代码现有规范为准。

#### ODS 层候选

```text
ods_mm_sap_inventory_daily
ods_mm_sap_material_flow
ods_mm_sap_purchase_requisition
ods_mm_sap_purchase_order_header
ods_mm_sap_purchase_order_item
ods_mm_sap_purchase_schedule
ods_mm_sap_purchase_history
ods_mm_sap_work_order_header
ods_mm_sap_work_order_item
ods_mm_sap_work_order_master
ods_mm_sap_work_order_component
```

#### DWD 层候选

```text
dwd_mm_inventory_balance
dwd_mm_material_flow
dwd_mm_purchase_execution
dwd_mm_purchase_arrival_detail
dwd_mm_work_order
dwd_mm_work_order_component
dwd_mm_material_demand
```

#### DWS / DM 层候选

```text
dws_mm_inventory_query
dws_mm_material_flow_query
dws_mm_purchase_execution_summary
dws_mm_material_consumption_summary
dws_mm_work_order_component_query

dm_mm_inventory_risk
dm_mm_purchase_delay
dm_mm_material_shortage
```

---

### 8.2 ODS 层要求

ODS 层用于保留 SAP MID 视图的原始数据或近原始数据。

要求：

1. 保留来源视图名。
2. 保留同步批次号。
3. 保留同步时间。
4. 保留来源系统。
5. 保留原始业务主键或主键候选字段。
6. 必要时保留 raw_json。
7. 字段尽量贴近 SAP MID 视图原字段。
8. 不在 ODS 层做复杂业务聚合。
9. ODS 层必须支持追溯。

建议公共字段：

```text
id
source_system
source_schema
source_view
source_pk
sync_batch_no
sync_mode
sync_started_at
sync_finished_at
synced_at
source_updated_at
raw_hash
raw_json
created_at
updated_at
```

---

### 8.3 DWD 层要求

DWD 层用于标准化业务明细。

要求：

1. 字段命名统一。
2. 类型统一。
3. 日期字段标准化。
4. 数量字段标准化。
5. 金额字段标准化。
6. 工厂、库存地点、物料、采购单、工单等关键字段统一。
7. 保留来源追溯字段。
8. 处理空值、异常值、单位转换等基础清洗。
9. 不过度聚合。

---

### 8.4 DWS / DM 层要求

DWS / DM 层用于面向智能问数和分析。

要求：

1. 面向常见业务问题建主题宽表或汇总表。
2. 支持查询服务直接使用。
3. 支持排名、趋势、汇总、明细穿透。
4. 支持来源追溯。
5. 支持后续权限过滤。
6. 支持查询性能优化。

---

## 9. 同步功能要求

### 9.1 Oracle 连接层

需要实现或设计 Oracle 连接层。

要求：

1. 通过 `SAP_ORACLE_*` 环境变量读取连接配置。
2. 支持 Oracle Service Name。
3. 设置连接超时。
4. 设置查询超时。
5. 设置 fetch size / 分批读取。
6. 只允许访问白名单视图。
7. 不允许拼接不可信 SQL。
8. 不允许无条件全表 `SELECT *` 导出。
9. 对大表必须分页或按条件分批抽取。
10. 连接失败时要有明确错误日志。

---

### 9.2 同步模式

必须设计并逐步实现：

1. 全量初始化同步。
2. 增量同步。
3. 指定视图同步。
4. 指定业务主题同步。
5. 指定时间范围同步。
6. 手动重跑。
7. 失败重试。

---

### 9.3 同步主题

建议按业务主题组织同步任务：

```text
inventory
material_flow
purchase_execution
work_order_component
sap_bom
```

主题与视图关系：

```text
inventory:
  - V_HF_SAP_INOUT_DAILY

material_flow:
  - V_SAP_HFFN_CRKLSZ

purchase_execution:
  - V_SAP_HFFN_EBAN
  - V_SAP_HFFN_EKKO
  - V_SAP_HFFN_EKPO
  - V_SAP_HFFN_EKET
  - V_SAP_HFFN_EKBE

work_order_component:
  - V_SAP_HFFN_AFKO
  - V_SAP_HFFN_AFPO
  - V_SAP_HFFN_AUFK
  - V_SAP_HFFN_RESB

sap_bom:
  - V_SAP_HFFN_MAST
  - V_SAP_HFFN_STKO
  - V_SAP_HFFN_STPO
  - V_SAP_HFFN_STAS
  - V_SAP_HFFN_STZU
```

---

### 9.4 幂等要求

同步必须幂等。

要求：

1. 相同同步批次重复执行不能重复插入脏数据。
2. 相同来源主键重复同步应更新或跳过。
3. 应设计 `source_pk` 或业务联合键。
4. 如果来源无明显主键，需要用字段组合 + hash 形成唯一标识。
5. 每次同步必须记录批次和结果。
6. 同步失败不能污染已成功数据。

---

### 9.5 日志要求

必须复用或扩展当前系统日志体系。

重点参考：

```text
sys_data_source
sys_task_log
sys_task_error_log
sys_query_log
```

同步日志至少包含：

```text
task_name
task_type
business_domain
business_topic
source_system
source_view
target_table
sync_mode
sync_batch_no
status
started_at
finished_at
read_count
insert_count
update_count
skip_count
error_count
error_message
operator
trigger_type
```

---

## 10. 前端功能要求

### 10.1 智能问答页增加物管业务域

需要在现有智能问答页中支持物管业务域。

要求：

1. 支持用户选择“物管”业务域。
2. 或支持系统自动识别物管问题后进入物管问数链路。
3. 支持提交物管自然语言问题。
4. 支持展示物管问答结果。
5. 支持展示结构化结果表格。
6. 支持展示查询条件。
7. 支持展示来源信息，例如中间库表、数据主题、同步批次。
8. 支持展示空结果说明。
9. 支持展示错误信息。
10. 支持展示需要澄清的问题。
11. 风格与现有物流、计划 BOM 问答页面保持一致。

### 10.2 物管问答结果展示类型

前端至少需要规划以下结果展示能力：

#### 库存类

展示：

1. 物料编码
2. 物料名称
3. 工厂
4. 库存地点
5. 批次
6. 当前库存
7. 单位
8. 库存日期
9. 来源表

#### 出入库流水类

展示：

1. 物料编码
2. 物料名称
3. 工厂
4. 库存地点
5. 移动类型
6. 入库 / 出库方向
7. 数量
8. 单位
9. 过账日期
10. 凭证号
11. 工单号
12. 来源表

#### 采购执行类

展示：

1. 采购单号
2. 采购行号
3. 物料编码
4. 物料名称
5. 供应商
6. 下单数量
7. 已到货数量
8. 未到货数量
9. 交货日期
10. 是否延期
11. 来源表

#### 工单组件类

展示：

1. 工单号
2. 产品物料
3. 组件物料
4. 组件名称
5. 需求数量
6. 已领数量
7. 缺口数量
8. 工厂
9. 来源表

### 10.3 手动同步 SAP/MID 数据触发入口

前端需要新增手动同步入口。初期可以是管理入口或物管页面内的同步入口。

要求：

1. 支持选择同步主题：
   - 库存
   - 出入库流水
   - 采购执行
   - 工单组件
   - SAP BOM

2. 支持选择同步方式：
   - 全量同步
   - 增量同步
   - 指定时间范围同步
   - 重跑某批次

3. 支持填写或选择时间范围。

4. 支持点击触发同步。

5. 支持展示同步任务状态：
   - 待执行
   - 执行中
   - 成功
   - 失败
   - 部分成功

6. 支持展示同步统计：
   - 读取行数
   - 插入行数
   - 更新行数
   - 跳过行数
   - 失败行数
   - 开始时间
   - 结束时间

7. 支持查看错误摘要。

8. 支持失败重试。

9. 不允许前端展示真实 Oracle 密码。

10. 不允许前端直接连接 Oracle。

前端只能调用后端提供的同步管理接口。

### 10.4 前端阶段限制

M1 阶段：

1. 只分析当前前端结构。
2. 只输出前端适配方案。
3. 不直接修改前端。
4. 不新增正式前端页面。
5. 不改坏现有物流和计划 BOM 页面。

M2 起：

1. 根据后端接口逐步增加物管问答入口。
2. 根据同步接口逐步增加手动同步入口。
3. 先做 MVP，不一次性做所有页面。

---

## 11. Oracle 源数据验证要求

### 11.1 M1 阶段允许的 Oracle 验证

M1 可以允许做只读 smoke test，但必须非常克制。

允许：

```sql
SELECT 1 FROM dual;
```

允许：

```sql
SELECT COUNT(*) FROM MID.V_HF_SAP_INOUT_DAILY;
```

允许：

```sql
SELECT *
FROM MID.V_HF_SAP_INOUT_DAILY
WHERE ROWNUM <= 5;
```

允许查询字段结构：

```sql
SELECT
    owner,
    table_name,
    column_name,
    data_type,
    data_length,
    nullable
FROM all_tab_columns
WHERE owner = 'MID'
  AND table_name IN (...)
ORDER BY table_name, column_id;
```

禁止：

1. 全量导出 SAP MID 视图。
2. 对大视图无条件 `SELECT *`。
3. 写入 SAP Oracle MID。
4. 修改 SAP Oracle MID。
5. 在日志和文档中输出敏感连接信息。

---

### 11.2 如果 Oracle 不可访问

如果当前机器无法访问 Oracle MID：

1. 不要伪造结果。
2. 使用已提供的 SAP MID 元数据和样例 Excel 完成 M1 设计。
3. 在报告中明确标记阻塞项。
4. 输出需要人工确认的网络、账号、权限、驱动依赖问题。

---

## 12. 智能问数链路要求

### 12.1 总体流程

物管域问数流程必须与现有物流、计划 BOM 类似。

要求：

```text
用户问题
    ↓
LLM 识别业务域、业务意图、查询参数
    ↓
程序选择查询模板和查询服务
    ↓
程序查询智能助手中间库
    ↓
程序返回结构化结果
    ↓
LLM 结合结果润色回答
```

---

### 12.2 第一阶段禁止自由 SQL Agent

第一阶段不允许：

```text
用户问题
    ↓
LLM 自由生成 SQL
    ↓
直接执行
```

必须先采用：

1. 业务域识别。
2. 意图分类。
3. 参数抽取。
4. SQL 模板。
5. 白名单字段。
6. 白名单表。
7. 程序执行。
8. LLM 润色。

---

### 12.3 物管域首批建议意图

#### 库存类

```text
查询某物料当前库存
查询某工厂某物料库存
查询某库存地点库存
查询某类物料库存
查询库存为 0 的物料
查询库存不足的物料
查询库存最多的物料
```

#### 出入库流水类

```text
查询某物料最近出入库流水
查询某物料最近领料情况
查询某工单领了哪些料
查询某时间段物料消耗
查询某工厂出库最多的物料
```

#### 采购执行类

```text
查询某采购单执行情况
查询某物料还有多少未到货
查询某供应商未交付情况
查询延期采购订单
查询未来一段时间预计到货
```

#### 工单组件类

```text
查询某工单需要哪些物料
查询某工单实际组件
查询某工单缺哪些料
查询某物料被哪些工单需要
```

#### BOM 类

```text
查询某产品 BOM
查询某产品用了哪些组件
查询某物料被哪些 BOM 使用
查询 BOM 层级结构
查询理论 BOM 与工单实际用料差异
```

---

## 13. 计划 BOM SAP 数据源改造要求

当前计划 BOM 主要来自 Excel 上传。后续需要支持 SAP BOM。

### 13.1 目标链路

```text
SAP MID BOM 视图
    ↓
智能助手中间库 BOM 标准模型
    ↓
现有计划 BOM 查询 / 问答能力
```

### 13.2 必须兼容现有功能

禁止：

1. 推翻现有 Excel BOM 能力。
2. 破坏现有 BOM 查询接口。
3. 破坏现有 BOM QA。
4. 破坏现有功率预测相关功能。
5. 不经评估直接删除现有 plan_bom 表。

### 13.3 建议设计

需要分析：

1. Excel BOM 与 SAP BOM 字段差异。
2. Excel BOM 与 SAP BOM 版本语义差异。
3. Excel BOM 与 SAP BOM 物料行语义差异。
4. Excel BOM 与 SAP BOM 生效时间差异。
5. Excel BOM 与 SAP BOM 主键差异。
6. 现有 plan_bom_* 表是否能通过 source_type 扩展。
7. 是否需要新增 SAP BOM ODS 表。
8. 是否需要新增 BOM 标准 DWD 表。
9. 如何让现有查询服务支持多数据源。

### 13.4 并存策略

至少需要支持一段时间：

```text
source_type = EXCEL
source_type = SAP_MID
```

如果现有字段不支持，应设计兼容升级方案。

---

## 14. 阶段拆分要求

请使用 Hermes Goal Mode 分阶段执行，不要一次性开发全部功能。

---

### M1：数据资产审计、总体方案与前端适配方案

当前首次启动只执行 M1。

目标：

1. 阅读项目代码和文档。
2. 阅读 SAP MID 元数据与样例附件。
3. 阅读智能助手中间库表附件。
4. 分析当前物流中间库分层规范。
5. 分析当前计划 BOM Excel 数据模型。
6. 分析当前前端物流和计划 BOM 问答页面。
7. 分析当前前端路由、API、布局、组件结构。
8. 分析物管域 SAP MID 视图。
9. 分析计划 BOM SAP 视图。
10. 设计 SAP MID → 智能助手中间库的同步架构。
11. 设计自动同步与手动同步方案。
12. 设计 ODS/DWD/DWS/DM 表模型。
13. 设计物管域智能问数链路。
14. 设计计划 BOM SAP 数据源改造方案。
15. 设计前端物管问答入口方案。
16. 设计前端 SAP/MID 手动同步入口方案。
17. 可做 Oracle 只读 smoke test。
18. 输出设计文档和后续阶段任务拆分。

M1 禁止：

1. 不做大规模正式开发。
2. 不改前端页面。
3. 不新增正式业务接口。
4. 不直接把问答链路接入生产功能。
5. 不破坏现有物流、计划 BOM、功率预测功能。
6. 不全量导出 SAP MID 数据。
7. 不将真实账号密码写入任何文档或日志。
8. 不让智能助手直接查询 SAP Oracle MID。
9. 不让 LLM 自由生成 SQL 并执行。

M1 产出文档：

```text
docs/MATERIAL_MANAGEMENT_SAP_MID_DATA_ASSET_AUDIT.md
docs/MATERIAL_MANAGEMENT_MIDDLE_DB_MODEL_PLAN.md
docs/SAP_MID_SYNC_DESIGN.md
docs/MATERIAL_MANAGEMENT_AI_QUERY_PLAN.md
docs/PLAN_BOM_SAP_DATA_SOURCE_MIGRATION_PLAN.md
docs/FRONTEND_MATERIAL_MANAGEMENT_ADAPTATION_PLAN.md
docs/SAP_MID_INTEGRATION_ROADMAP.md
docs/SAP_MID_ORACLE_SMOKE_TEST_REPORT.md
docs/CURRENT_STATUS.md
docs/NEXT_TASK.md
docs/HANDOFF.md
```

---

### M2：库存 / 出入库同步 MVP + 物管问答前端入口 MVP

范围：

```text
V_HF_SAP_INOUT_DAILY
V_SAP_HFFN_CRKLSZ
```

后端目标：

1. 建立库存和出入库 ODS 表。
2. 建立 DWD 标准库存 / 流水表。
3. 实现 Oracle 连接器。
4. 实现白名单视图读取。
5. 实现手动同步命令或后端管理触发能力。
6. 实现基础自动同步任务。
7. 写入同步日志和错误日志。
8. 实现基础库存问数服务。
9. 支持用户查询某物料库存、某物料出入库流水。
10. 查询必须基于智能助手中间库。

前端目标：

1. 在智能问答页增加物管业务域入口或业务域选择。
2. 支持提交库存 / 出入库类物管问题。
3. 支持自然语言回答展示。
4. 支持结构化表格展示。
5. 支持查询条件展示。
6. 支持来源表 / 中间库表展示。
7. 如后端已提供手动同步接口，则增加简单手动同步按钮；否则只预留入口。
8. 不改坏现有物流问答页面。
9. 不改坏现有计划 BOM 页面。

M2 验收：

1. 可以从 Oracle MID 抽取小批量库存数据并写入中间库。
2. 重复同步不产生重复脏数据。
3. 同步日志可追溯。
4. 可以基于中间库回答至少 5 个库存/出入库测试问题。
5. 前端可以进入物管问答入口并展示库存/出入库结果。
6. 不影响现有物流和计划 BOM 功能。

---

### M3：采购执行同步与问数 + 采购结果前端展示

范围：

```text
V_SAP_HFFN_EBAN
V_SAP_HFFN_EKKO
V_SAP_HFFN_EKPO
V_SAP_HFFN_EKET
V_SAP_HFFN_EKBE
```

后端目标：

1. 建立采购主题 ODS 表。
2. 建立采购执行 DWD/DWS 表。
3. 支持采购单执行查询。
4. 支持未到货数量查询。
5. 支持延期采购查询。
6. 支持供应商交付分析。
7. 支持采购执行问数模板。

前端目标：

1. 支持采购执行问答结果展示。
2. 支持采购订单明细表格。
3. 支持到货 / 未到货数量展示。
4. 支持延期采购订单展示。
5. 支持供应商维度统计展示。
6. 支持来源追溯展示。

M3 验收：

1. 可以查询采购单下单、到货、未到货情况。
2. 可以查询某物料采购未到货情况。
3. 可以查询延期采购订单。
4. 查询结果可追溯来源。
5. 前端可展示采购执行结果。

---

### M4：工单组件 / 实际用料同步与问数 + 工单结果前端展示

范围：

```text
V_SAP_HFFN_AFKO
V_SAP_HFFN_AFPO
V_SAP_HFFN_AUFK
V_SAP_HFFN_RESB
```

后端目标：

1. 建立工单相关 ODS 表。
2. 建立工单组件 DWD/DWS 表。
3. 支持查询工单实际组件。
4. 支持查询工单物料需求。
5. 支持结合库存做缺料初步分析。
6. 支持工单实际用料与理论 BOM 差异分析的基础能力。

前端目标：

1. 支持工单组件查询结果展示。
2. 支持工单实际用料明细展示。
3. 支持工单缺料风险展示。
4. 支持工单与物料关联结果展示。
5. 支持来源追溯展示。

M4 验收：

1. 可以查询某工单需要哪些物料。
2. 可以查询某工单组件数量。
3. 可以查询某物料被哪些工单需要。
4. 可以输出基础缺料风险提示。
5. 前端可展示工单组件和缺料结果。

---

### M5：计划 BOM SAP 数据源改造 + BOM 来源前端展示

范围：

```text
V_SAP_HFFN_MAST
V_SAP_HFFN_STKO
V_SAP_HFFN_STPO
V_SAP_HFFN_STAS
V_SAP_HFFN_STZU
```

后端目标：

1. 建立 SAP BOM ODS 表。
2. 建立 BOM 标准模型。
3. 支持 Excel BOM 与 SAP BOM 并存。
4. 改造现有 plan_bom 查询服务以支持数据源选择。
5. 保持现有 Excel BOM 查询能力不受影响。
6. 逐步让计划 BOM 查询能力支持 SAP BOM。

前端目标：

1. 支持 BOM 数据源选择或展示。
2. 区分 Excel BOM 与 SAP BOM。
3. 展示 BOM 来源。
4. 展示 BOM 生效日期、版本、物料关系。
5. 保持现有计划 BOM 页面兼容。

M5 验收：

1. 可以同步 SAP BOM 数据。
2. 可以查询某物料对应 BOM。
3. 可以查询某 BOM 的组件。
4. 可以查询某组件被哪些 BOM 使用。
5. Excel BOM 原功能仍可用。
6. 前端可展示 BOM 来源信息。

---

### M6：物管域智能问数增强 + 手动同步管理页面增强

目标：

1. 完善物管域意图识别。
2. 完善业务口语词典。
3. 完善 SQL 模板。
4. 增加结果解释。
5. 增加来源追溯展示。
6. 增加测试题集。
7. 增加查询日志和评测机制。
8. 增强前端物管问答体验。
9. 增强 SAP/MID 手动同步管理入口。
10. 增强同步任务状态和日志展示。

前端目标：

1. 物管问答体验优化。
2. 多类型结果卡片。
3. 明细表格分页。
4. 下载查询结果。
5. 查询历史。
6. 查询来源追溯。
7. 同步任务状态查看。
8. 错误提示和空结果提示优化。
9. 手动同步任务重试。
10. 同步日志详情查看。

M6 验收：

1. 常见物管问数问题可回答。
2. 明细、汇总、趋势类问题可区分。
3. 结构化查询结果准确。
4. LLM 润色不改变事实。
5. 所有回答有来源和查询条件。
6. 前端可支持完整物管问答和同步管理体验。

---

## 15. M1 必须输出的核心文档说明

### 15.1 `docs/MATERIAL_MANAGEMENT_SAP_MID_DATA_ASSET_AUDIT.md`

内容必须包括：

1. MID 资源库总体判断。
2. 物管相关视图清单。
3. 库存视图分析。
4. 出入库流水视图分析。
5. 采购执行视图分析。
6. 工单组件视图分析。
7. BOM 视图分析。
8. 字段含义初步解释。
9. 主键/关联键初步判断。
10. 增量同步字段候选。
11. 数据质量问题。
12. 当前缺失信息。
13. 人工确认项。

---

### 15.2 `docs/MATERIAL_MANAGEMENT_MIDDLE_DB_MODEL_PLAN.md`

内容必须包括：

1. ODS/DWD/DWS/DM 分层方案。
2. 表命名建议。
3. 字段设计建议。
4. 来源追溯字段。
5. 幂等字段。
6. 同步批次字段。
7. 库存主题模型。
8. 出入库流水主题模型。
9. 采购执行主题模型。
10. 工单组件主题模型。
11. 物料消耗主题模型。
12. 缺料分析主题模型。
13. 数据质量规则。
14. 后续迁移建议。

---

### 15.3 `docs/SAP_MID_SYNC_DESIGN.md`

内容必须包括：

1. Oracle 连接配置读取方案。
2. Oracle 连接池方案。
3. 白名单视图设计。
4. 自动同步设计。
5. 手动同步设计。
6. 全量同步设计。
7. 增量同步设计。
8. 指定时间范围同步设计。
9. 指定视图同步设计。
10. 指定主题同步设计。
11. 分批读取设计。
12. 幂等写入设计。
13. 失败重试设计。
14. 同步日志设计。
15. 错误日志设计。
16. 安全控制。
17. 性能风险。
18. Oracle 不可访问时的降级策略。
19. 前端手动同步触发接口规划。
20. 前端同步状态查询接口规划。

---

### 15.4 `docs/MATERIAL_MANAGEMENT_AI_QUERY_PLAN.md`

内容必须包括：

1. 物管问数总体链路。
2. 与物流问数链路的复用点。
3. 与计划 BOM 问答链路的复用点。
4. 业务域识别。
5. 意图识别。
6. 参数抽取。
7. 字段字典。
8. 业务口语词典。
9. SQL 模板设计。
10. 查询服务设计。
11. 结果解释设计。
12. 来源追溯设计。
13. 查询日志设计。
14. 测试题集设计。
15. 不允许 LLM 自由生成 SQL 的约束说明。
16. 前端问答结果数据结构设计。
17. 前端结构化结果展示建议。

---

### 15.5 `docs/PLAN_BOM_SAP_DATA_SOURCE_MIGRATION_PLAN.md`

内容必须包括：

1. 当前 Excel BOM 数据源现状。
2. 当前 plan_bom 表结构理解。
3. SAP BOM 视图关系。
4. MAST/STKO/STPO/STAS/STZU 关系分析。
5. Excel BOM 与 SAP BOM 差异。
6. 多数据源并存方案。
7. source_type / source_tag 设计建议。
8. 标准 BOM 模型演进建议。
9. 如何不影响现有 BOM 查询。
10. 如何不影响功率预测。
11. 分阶段迁移路线。
12. 风险和人工确认项。
13. 前端 BOM 来源展示方案。

---

### 15.6 `docs/FRONTEND_MATERIAL_MANAGEMENT_ADAPTATION_PLAN.md`

内容必须包括：

1. 当前前端页面结构分析。
2. 当前物流问答页面如何实现。
3. 当前计划 BOM 问答页面如何实现。
4. 当前前端路由结构。
5. 当前 API 调用封装方式。
6. 当前问答结果组件结构。
7. 物管业务域前端入口设计。
8. 物管问答页面设计。
9. 智能问答页如何增加物管业务域。
10. 库存查询结果展示设计。
11. 出入库流水结果展示设计。
12. 采购执行结果展示设计。
13. 工单组件结果展示设计。
14. SAP/MID 手动同步入口设计。
15. 手动同步触发交互设计。
16. 同步任务状态展示设计。
17. 同步日志查看页面设计。
18. 来源追溯展示设计。
19. 与现有物流 / 计划 BOM 前端组件的复用方案。
20. M2-M6 前端开发路线。
21. 不影响现有页面的风险控制方案。

---

### 15.7 `docs/SAP_MID_INTEGRATION_ROADMAP.md`

内容必须包括：

1. M1-M6 阶段路线。
2. 每阶段目标。
3. 每阶段允许事项。
4. 每阶段禁止事项。
5. 每阶段验收标准。
6. 每阶段预计改动范围。
7. 后续 Codex 任务拆分建议。
8. 人工确认节点。
9. 回滚策略。
10. 风险清单。
11. 前后端协同开发节奏。

---

### 15.8 `docs/SAP_MID_ORACLE_SMOKE_TEST_REPORT.md`

如执行 Oracle 连接验证，必须输出：

1. 是否读取到 `SAP_ORACLE_*` 配置。
2. 是否成功连接 Oracle。
3. 是否成功执行 `SELECT 1 FROM dual`。
4. 是否能读取白名单视图字段结构。
5. 是否能对重点视图做 `ROWNUM <= 5` 抽样。
6. 是否能做 count 验证。
7. 遇到的错误。
8. 网络/权限/驱动问题。
9. 后续建议。

禁止在报告中输出真实密码。

---

## 16. 代码开发规范

### 16.1 基本原则

1. 复用现有项目架构。
2. 复用现有日志体系。
3. 复用现有数据库连接体系。
4. 复用现有查询链路思想。
5. 复用现有前端页面风格。
6. 不要大规模重构。
7. 不要破坏现有功能。
8. 不要提交真实密钥。
9. 重要改动必须有文档。
10. 重要逻辑必须有测试。
11. 数据同步必须可追溯。

---

### 16.2 后端目录建议

最终目录以实际项目规范为准，候选结构如下：

```text
backend/app/infra/oracle/
  client.py
  config.py
  errors.py

backend/app/domains/material_management/
  sap_mid/
    config/
    sync/
    models/
    repositories/
    services/
    query/
    nlu/
    templates/
    schemas/
    tests/
```

不要为了目录整洁而过度重构现有代码。

---

### 16.3 前端目录建议

最终目录以实际项目规范为准，候选结构如下：

```text
frontend/src/views/material-management/
frontend/src/api/materialManagement.ts
frontend/src/components/material-management/
```

或复用现有问答页面组件。

原则：

1. 优先复用现有物流和计划 BOM 的问答组件。
2. 优先复用现有布局和路由风格。
3. 不要复制出大量重复页面。
4. 不要破坏现有菜单。
5. 不要破坏现有接口封装。
6. 不要在前端保存 Oracle 连接信息。

---

### 16.4 SQL 安全要求

1. 只允许访问白名单表/视图。
2. SQL 模板参数必须绑定，不允许直接拼接用户输入。
3. 用户输入不能直接进入表名、字段名、排序字段。
4. 排序字段、筛选字段必须来自白名单。
5. 大查询必须分页或限制行数。
6. 查询超时必须可配置。
7. 返回给 LLM 的结果必须限制行数和字段范围。

---

## 17. 权限与安全要求

1. SAP Oracle MID 账号必须只读。
2. `.env` 不得提交。
3. 不得输出真实连接密码。
4. 用户问数只能查询中间库。
5. 后续需要支持业务域权限。
6. 后续需要支持工厂/组织范围权限。
7. 后续需要支持敏感字段脱敏。
8. 同步任务必须有操作人或触发来源记录。
9. 手动同步必须有审计日志。
10. 失败日志不得泄漏敏感连接信息。
11. 前端不得展示 Oracle 密码。
12. 前端不得直接连接 Oracle。
13. 手动同步入口后续需要权限控制，不能所有用户都能触发。

---

## 18. 测试要求

### 18.1 M1 测试

M1 以文档和 smoke test 为主。

要求：

1. 检查附件可读取。
2. 检查中间库结构可理解。
3. 检查前端结构可理解。
4. 如网络允许，做 Oracle 只读连接 smoke test。
5. 不做正式数据写入。
6. 不做前端正式改造。

---

### 18.2 M2 及以后测试

必须逐步增加：

1. Oracle 连接配置测试。
2. 视图白名单测试。
3. 同步任务单元测试。
4. 幂等测试。
5. 数据写入测试。
6. 查询模板测试。
7. 结果解释测试。
8. 前端问答页面测试。
9. 前端手动同步入口测试。
10. 端到端问数测试。
11. 回归测试，确保物流、计划 BOM、功率预测不受影响。

---

### 18.3 测试题集要求

物管域需要建立测试题集，例如：

```text
某物料当前库存是多少？
某物料最近一周出库多少？
某工厂库存最多的前 10 个物料是什么？
某采购单到了多少，还剩多少没到？
某物料有哪些采购订单未到货？
某工单需要哪些组件？
某工单是否存在缺料风险？
某产品 BOM 包含哪些组件？
某组件被哪些 BOM 使用？
```

每个测试题需要记录：

1. 用户原始问法。
2. 标准意图。
3. 参数。
4. 期望查询模板。
5. 期望数据来源。
6. 验收口径。
7. 人工校验结果。
8. 前端预期展示方式。

---

## 19. 状态文档维护要求

Hermes Goal Mode 执行过程中必须持续维护：

```text
docs/CURRENT_STATUS.md
docs/NEXT_TASK.md
docs/HANDOFF.md
```

要求：

### `docs/CURRENT_STATUS.md`

记录：

1. 当前阶段。
2. 当前已完成内容。
3. 当前项目状态。
4. 当前确认的关键决策。
5. 当前风险。
6. 当前阻塞。

### `docs/NEXT_TASK.md`

记录：

1. 下一步任务。
2. 任务优先级。
3. 任务输入。
4. 任务输出。
5. 验收标准。
6. 禁止事项。

### `docs/HANDOFF.md`

记录：

1. 给下一轮 Hermes/Codex 的上下文。
2. 已读文件。
3. 已改文件。
4. 关键结论。
5. 未完成事项。
6. 注意事项。
7. 回滚建议。

---

## 20. Hermes 与 Codex 分工要求

### Hermes 角色

Hermes 作为技术经理 / 调度者，负责：

1. 阅读需求。
2. 拆分阶段。
3. 指挥 Codex。
4. 审查 Codex 输出。
5. 校验是否符合阶段边界。
6. 更新状态文档。
7. 发现风险并暂停。
8. 向用户汇报阶段结果。

### Codex 角色

Codex 作为执行者，负责：

1. 阅读指定代码。
2. 实现小范围明确任务。
3. 输出代码改动。
4. 执行测试。
5. 汇报改动文件。
6. 不自行扩大范围。
7. 不越权进入下一阶段。
8. 不绕过 Hermes 的阶段限制。

### 重要要求

不要让 Codex 自己无限扩展范围。  
每个阶段结束后，必须由 Hermes 汇总并判断是否进入下一阶段。

---

## 21. 当前首次执行指令

当前首次启动 Goal Mode 时，请只执行 M1。

请按以下顺序：

1. 进入项目根目录。
2. 读取 `ai/inbox/requirement.md`。
3. 读取项目文档和代码。
4. 读取 SAP MID 附件。
5. 读取智能助手中间库附件。
6. 分析现有物流中间库设计。
7. 分析现有 plan_bom 数据模型。
8. 分析 material_management 当前状态。
9. 分析前端当前页面、路由、API、组件。
10. 分析 SAP MID 重点视图。
11. 如网络和依赖允许，执行 Oracle 只读 smoke test。
12. 输出 M1 所需文档。
13. 更新 `CURRENT_STATUS.md`、`NEXT_TASK.md`、`HANDOFF.md`。
14. 汇报 M1 结论和 M2 建议。
15. 等待人工确认后再进入 M2。

---

## 22. M1 完成汇报格式

M1 完成后，请用以下格式汇报：

```text
# M1 完成报告

## 1. 本阶段读取的项目文件

## 2. 本阶段读取的附件

## 3. 本阶段是否连接 Oracle MID

## 4. Oracle smoke test 结果

## 5. 本阶段前端分析结果

## 6. 输出的文档

## 7. 当前确认的核心结论

## 8. 当前发现的风险

## 9. 当前需要人工确认的问题

## 10. 下一阶段 M2 建议

## 11. 是否建议进入 M2
```

---

## 23. 明确禁止事项总表

在没有人工确认之前，禁止：

1. 删除现有表。
2. 删除现有代码。
3. 大规模重构。
4. 修改现有物流主链路。
5. 修改现有计划 BOM 主链路。
6. 修改现有功率预测主链路。
7. 将 `.env` 中真实密钥写入任何文件。
8. 将 `.env` 提交 Git。
9. 对 SAP Oracle MID 执行写操作。
10. 全量导出 SAP Oracle MID 大表。
11. 让 LLM 自由生成 SQL 并执行。
12. 让智能助手面向用户实时查询 SAP Oracle MID。
13. 跳过中间库直接做问答。
14. 未设计幂等机制就做正式同步。
15. 未设计日志就做同步。
16. 未设计回滚策略就做数据库迁移。
17. 未执行回归检查就宣称完成。
18. 未经确认，不允许大规模重构前端页面结构。
19. 不允许为了新增物管页面破坏现有物流和计划 BOM 页面。
20. M1 阶段不允许直接开发前端，只允许输出前端适配设计方案。
21. 不允许前端保存或展示 Oracle 连接信息。
22. 不允许前端直接连接 SAP Oracle MID。

---

## 24. 成功标准

本 Goal 最终成功标准：

1. SAP Oracle MID 相关数据可以通过代码层同步到智能助手中间库。
2. 同步支持自动同步和手动同步。
3. 同步过程有日志、错误记录、批次追溯、幂等保障。
4. 物管域形成库存、出入库、采购执行、工单组件等中间库主题模型。
5. 计划 BOM 支持 SAP BOM 数据源，并兼容现有 Excel BOM。
6. 用户可以在智能问答页选择或进入物管业务域进行自然语言询问。
7. 系统通过 LLM 理解问题，通过程序准确查数，通过 LLM 润色回答。
8. 查询基于智能助手中间库，不直接查 SAP Oracle MID。
9. 回答能展示查询依据、来源表、查询条件或明细。
10. 前端能展示物管问答结果、结构化明细、来源追溯。
11. 前端提供 SAP/MID 手动同步触发入口和同步状态展示能力。
12. 现有物流、计划 BOM、功率预测能力不受破坏。

# 物流一期 NL2SQL 改造架构规划

> 状态：设计规划稿  
> 范围：第一阶段只做物流域；只查询智能助手 MySQL 中间库；不实时直查 SAP Oracle MID。  
> 当前自查证据：已只读连接 `MYSQL_*` 指向的智能助手中间库并完成表结构、行数、索引、EXPLAIN 可用性检查；敏感连接信息未写入本文档。

---

## 1. 本轮仓库状态判断

### 1.1 已完成 / 可复用能力

当前仓库不是空白状态，已有以下可复用基础：

1. 物流确定性 QA 主链路：`LogisticsDataQaPlanner -> LogisticsDataQaService -> Repository -> ResultExplainer / Presentation`。
2. 已有 Query Planning V2 影子诊断域：
   - `backend/app/domains/query_planning/schemas/query_plan_v2.py`
   - `backend/app/domains/query_planning/services/query_planning_v2_service.py`
   - `backend/app/domains/query_planning/services/logistics_adapter.py`
   - `backend/app/domains/query_planning/services/shadow_report_service.py`
3. 已有物流 LLM Query Planner V2 雏形：
   - `backend/app/domains/logistics/services/query_planner_v2/`
   - 已包含 `prompt_builder / llm_parser / normalizer / validator / capability_registry / fallback / legacy_adapter`。
4. 已有 SQL 模板治理雏形：`nl2query_service.py` 中存在模板、白名单、审计、参数校验概念。
5. 已有查询日志：`sys_query_log`，可作为 shadow 记录与评估样本来源。
6. 当前仓库中已有大量物流业务口径、query_key、回归样例和验收测试，可作为 Semantic Catalog 和评测集的主要来源。

### 1.2 当前未完成能力

1. 还没有完整的“Semantic Catalog -> 召回 -> Rerank -> SQLPlan -> SQL 生成 -> SQL 校验 -> EXPLAIN -> 试执行 -> 自修复 -> 正式执行”的端到端 NL2SQL 管道。
2. 现有 `query_planner_v2` 仍偏 shadow QueryPlan，不是真正的 SQLPlan + SQL 执行候选。
3. 现有能力注册表仍主要是代码内 dataclass，尚未形成可版本化、可索引、可审计的 Semantic Catalog。
4. 还没有 Milvus catalog collection 和百炼 Qwen3 Embedding / Reranker 的接入层。
5. 还没有基于中间库真实数据自动生成“问题样例 + 标准答案”的流水线。
6. 还没有面向 NL2SQL 的 SQL 安全策略、EXPLAIN 门禁、试执行和自修复闭环。
7. 还没有 NL2SQL shadow 与现有确定性 QA 的一致性评估报表。

### 1.3 与本次用户要求的一致性

本次用户确认的方向与当前仓库状态一致：

- 当前已有物流 QA、Query Planning V2、sys_query_log，可作为改造层基础；
- 用户要求第一阶段只做物流，符合当前物流能力基线；
- 用户要求只查智能助手中间库，符合现有 `MYSQL_*` 主库定位；
- 用户允许 SQLPlan / SQL hash / EXPLAIN shadow 记录，正好可接入 `sys_query_log.request_payload` 或后续独立审计表；
- 用户允许 Milvus、embedding、rerank、sqlglot，引入后可补齐 Semantic Catalog 与 SQL 安全校验。

### 1.4 本轮允许范围

1. 设计并逐步实现物流 NL2SQL 改造层。
2. 只读连接智能助手 MySQL 中间库，执行 `SELECT / EXPLAIN`。
3. 读取当前代码和已有业务口径，构建 Semantic Catalog。
4. 使用本地 Docker Milvus 作为向量库。
5. 使用百炼 Qwen3-Embedding-4B 和 Qwen3-Reranker。
6. 复用当前百炼 DeepSeek 主 LLM 配置。
7. 引入 `sqlglot`、embedding/reranker 客户端等依赖。
8. 在 shadow 阶段记录 SQLPlan、SQL hash、EXPLAIN、验证结果和一致性评估。

### 1.5 本轮禁止范围

1. 禁止面向用户实时直查 SAP Oracle MID。
2. 禁止绕过智能助手中间库查询任何业务源库。
3. 禁止让 LLM 直接执行 SQL、直接查数或直接计算业务事实。
4. 禁止输出 `.env` 真实账号、密码、Key、DSN。
5. 禁止把新问法识别主逻辑继续堆到 `data_qa_planner.py`。
6. 第一阶段不扩展到 BOM、物管、经营分析。
7. 第一阶段不改前端展示主链路，除非后续单独确认 NL2SQL shadow 可视化入口。

---

## 2. 中间库自查结果摘要

已通过项目 `backend/.env` 中的 `MYSQL_*` 配置只读连接智能助手中间库。

### 2.1 连接与能力

| 项 | 结果 |
| --- | --- |
| 数据库类型 | MySQL |
| 版本 | 8.0.45 |
| 当前库 | `logistics_ai` |
| 总表数 | 40 |
| 物流/日志相关表数 | 20 |
| EXPLAIN | 可执行 |

### 2.2 物流核心表

| 表 | 行数 | 定位 | NL2SQL 使用建议 |
| --- | ---: | --- | --- |
| `dws_logistics_detail_union` | 28447 | 物流统一明细事实层，融合历史与系统侧 | 明细、筛选、分组、聚合的首选事实表 |
| `dws_logistics_monthly_metric` | 7745 | 月度聚合指标层 | 月度趋势、按月汇总、部分常规聚合优先使用 |
| `dwd_logistics_hist_shipment_detail` | 24234 | 2023-2025 历史台账标准明细 | 历史专项口径、源字段追溯、路线/车型/报价等细粒度分析 |
| `dwd_logistics_ship_task` | 1301 | 2026 系统侧发货任务标准层 | 2026 系统任务、状态、部门、委托人等系统侧问题 |
| `dwd_logistics_ship_product` | 1355 | 系统侧任务产品明细 | 2026 产品规格、功率、数量问题 |
| `dm_logistics_company_month_rank` | 429 | 承运商月度排名结果层 | 承运商排名/看板类查询可优先使用 |
| `sys_query_log` | 31069 | 查询日志 | shadow、评估、问题样例挖掘 |

### 2.3 字段与 Join 关系初判

数据库当前未暴露可依赖的外键约束，因此 NL2SQL 不能依赖数据库 FK 自动推断 Join。需要在 Semantic Catalog 中显式声明逻辑关系：

1. 统一事实优先：大多数物流问数优先从 `dws_logistics_detail_union` 或 `dws_logistics_monthly_metric` 单表完成，避免不必要 Join。
2. 历史明细：`dwd_logistics_hist_shipment_detail` 的业务键包括合同号、询比价编号、发货指令、SAP 单号、客户、城市、省份、区域、始发地、运输方式、车型、承运商等。
3. 2026 系统侧：`dwd_logistics_ship_task.task_id` 可与 `dwd_logistics_ship_product.task_id`、`dwd_logistics_assign_task.ship_task_id/task_id`、`dwd_logistics_assign_detail.ship_task_id/assign_task_id` 建立逻辑关联。
4. 承运商维度：系统侧可通过 `company_id/company_name` 关联 `dwd_logistics_company`；历史侧以 `logistics_company_name` 为准。
5. 仓库维度：系统侧可通过 `warehouse_id/warehouse_name` 关联 `dwd_logistics_warehouse`；统一层有 `warehouse_name`。
6. Query 日志：`sys_query_log` 不参与业务回答，只用于 shadow、评估、回放和样例生成。

---

## 3. 目标 NL2SQL 流程

用户初稿的 12 步流程保留，并改造成受控企业级执行链路：

```text
用户问题
↓
0. 请求上下文与权限/数据域边界
↓
1. Query Rewrite / 标准化
↓
2. Domain Router / 第一阶段固定 logistics
↓
3. Semantic Catalog 召回：Schema / Metric / Rule / Example / Business Glossary
↓
4. Rerank 精排
↓
5. SQLPlan 生成
↓
6. SQL 生成
↓
7. SQL 安全校验
↓
8. EXPLAIN / 试执行门禁
↓
9. SQL 自修复，最多 2 轮
↓
10. 正式执行
↓
11. 结果解释 / 业务化回答
↓
12. 查询日志 / shadow / 评估 / 样例沉淀
```

### 3.1 LLM 与后端职责边界

| 环节 | LLM 可做 | 后端必须做 |
| --- | --- | --- |
| Query Rewrite | 改写为标准业务问法；补充同义表达 | 保留原问题；不能覆盖事实边界 |
| Domain Router | 给候选领域和置信度 | 第一阶段强制只允许 logistics；未知领域 fail closed |
| Catalog 召回 | 不直接做召回，可辅助生成检索 query | Milvus 向量召回、关键词召回、规则召回 |
| SQLPlan | 生成结构化候选 | schema 校验、catalog 对齐、字段/指标/权限校验 |
| SQL 生成 | 基于 SQLPlan 生成候选 SQL | sqlglot 解析、安全规则、表/列白名单、参数化、EXPLAIN |
| 自修复 | 根据安全错误修正 SQLPlan/SQL | 限制修复轮次；错误类型白名单；禁止越权扩大范围 |
| 执行 | 不允许 | MySQL 只读事务执行 |
| 结果解释 | 业务化表达 | 固定数值、表格、计算口径、来源追溯；不暴露技术细节给业务用户 |

---

## 4. Semantic Catalog 设计

### 4.1 Catalog 目标

Semantic Catalog 是 NL2SQL 的确定性知识底座，不能只依赖 prompt 临时塞上下文。

它必须回答：

1. 哪些表可查？
2. 哪些字段可查、可筛选、可分组、可排序？
3. 业务指标如何计算？
4. 默认口径是什么？
5. 哪些问法对应哪些指标/维度/SQL 模式？
6. 哪些问题必须澄清或拒答？
7. 哪些 Join 是允许的？
8. 哪些样例来自真实数据并有标准答案？

### 4.2 Catalog 分层

建议第一阶段使用“版本化 YAML/JSON + Milvus 向量索引 + 可选 MySQL shadow 记录”的组合，不急于先建正式 catalog 表。

```text
backend/app/domains/logistics/config/nl2sql_catalog/
  tables.yaml        # 表、字段、索引、行数、可用范围
  metrics.yaml       # 指标定义、SQL 表达式、单位、默认口径
  dimensions.yaml    # 维度、枚举、同义词、归一化
  joins.yaml         # 允许的逻辑 Join 关系
  rules.yaml         # 安全规则、澄清/拒答规则、默认时间范围
  examples.yaml      # 自动生成并人工抽检后的真实样例
  prompts.yaml       # SQLPlan/SQL generation prompt 片段，不含密钥
```

向量库中索引的是 catalog item 文本与元数据：

```json
{
  "catalog_id": "logistics.metric.shipment_mw.v1",
  "item_type": "metric",
  "domain": "logistics",
  "title": "发运量 / 运量 / 运输量 / 物流量 / 出货量",
  "text": "发货量、运量、运输量、物流量、出货量默认映射为发运量，单位 MW，字段优先 shipment_watt。",
  "metadata": {
    "metric_name": "shipment_mw",
    "tables": ["dws_logistics_detail_union", "dws_logistics_monthly_metric"],
    "columns": ["shipment_watt"],
    "unit": "MW",
    "aggregation": "SUM"
  }
}
```

### 4.3 首批核心指标

| 指标 | 业务同义词 | SQL 口径 | 默认单位/说明 |
| --- | --- | --- | --- |
| `shipment_mw` | 发货量、运量、运输量、物流量、出货量、发运量、瓦数、件数 | `SUM(shipment_watt)` | MW；用户确认“件数”也默认按 MW 口径回答 |
| `shipment_trip_count` | 车次、车辆数、趟次 | `SUM(shipment_trip_count)` | 主要用于均价分母 |
| `total_fee` | 总费用、总运费、运输费用 | `SUM(total_fee)` | 元 |
| `avg_fee_per_trip` | 均价、平均运费、平均每车费用 | `SUM(total_fee) / SUM(shipment_trip_count)` | 元/车；不能用 `AVG(total_fee)` |
| `unit_price_per_vehicle` | 报价、单价、运价、单价/车 | `unit_price_per_vehicle` | 元/车；与“均价”严格区分，不乘车次、不按总费用替代 |
| `extra_fee` | 额外费用、附加费、异常费用 | `SUM(extra_fee)` | 元 |
| `row_count` | 记录数、单数、明细数 | `COUNT(*)` | 条 |
| `carrier_rank_by_mw` | 哪个物流跑得最多、承运商发运量排行 | 按承运商分组后 `SUM(shipment_watt) DESC` | 默认按发运量排序 |

### 4.4 首批拒答 / 澄清规则

1. `吨数 / 运输吨位 / 重量吨`：当前不支持，不得用 MW 替代。
2. 未给时间条件的物流问题：默认查询 2023-2026 全部时间。
3. “今年 / 当前 / 最近”：按系统当前年份解释；实现时必须由后端运行时日期决定，不在 catalog 中硬编码具体年份。
4. 多年份对比：必须保留每个用户显式请求年份，某年无数据也要返回空值行。
5. 2023-2025 历史侧与 2026 系统侧混合查询：所有维度均允许跨源对比；SQLPlan 需要保留 source_type 追溯字段，但默认不因跨源维度而拒答。
6. 空结果：不自动放宽时间、实体或筛选条件，只说明当前条件下无数据，并给出业务化改问建议。
7. 未知业务实体或字段口径无法确定时：澄清，不得扩大成全量。
8. 问题要求预测未来趋势、原因归因、外部供应商实时状态等当前数据不支持事项：拒答或澄清。
9. 用户可见答案不得暴露 SQL、表名、字段名、query_key、planner、guardrail、schema、raw/debug、LLM 等内部技术内容。

---

## 5. 召回与 Rerank 方案

### 5.1 召回输入

Query Rewrite 后生成三类检索 query：

1. 原始问题；
2. 标准化业务问法；
3. 槽位候选摘要，例如“物流 发运量 承运商 排名 2023-2026”。

### 5.2 召回通道

1. Milvus 向量召回：对 catalog item 做 Qwen3-Embedding-4B embedding。
2. 关键词召回：表名、字段别名、指标名、枚举值、query_key、业务词精确/模糊匹配。
3. 规则召回：强制加入安全规则、默认口径、当前领域核心事实表。
4. 历史样例召回：从真实数据自动生成且通过验收的 question-answer 示例。

### 5.3 Rerank

使用百炼 Qwen3-Reranker 对候选 catalog item 精排。

精排输出分层：

1. 必选：安全规则、默认口径、可查表/字段。
2. 高优：指标/维度/Join/样例。
3. 辅助：相关但不直接参与 SQL 的业务解释。

Rerank 后输入 SQLPlan 的内容必须限长、去重、带 catalog_id 和版本号。

---

## 6. SQLPlan Schema

SQLPlan 是 SQL 生成前的核心中间层，必须结构化、可校验、可回放。

建议 schema：

```json
{
  "schema_version": "logistics_sql_plan.v1",
  "domain": "logistics",
  "original_question": "...",
  "rewritten_question": "...",
  "intent": "aggregate|ranking|detail|comparison|trend|clarification|unsupported",
  "tables": ["dws_logistics_detail_union"],
  "metrics": [
    {
      "name": "shipment_mw",
      "expression_id": "metric.shipment_mw.sum",
      "aggregation": "SUM",
      "unit": "MW"
    }
  ],
  "dimensions": ["logistics_company_name"],
  "filters": [
    {"field": "biz_year", "op": "between", "value": [2023, 2026]}
  ],
  "group_by": ["logistics_company_name"],
  "order_by": [{"field_or_metric": "shipment_mw", "direction": "desc"}],
  "limit": 10,
  "business_rules": ["default_time_2023_2026", "carrier_rank_by_shipment_mw"],
  "safety": {
    "read_only": true,
    "requires_explain": true,
    "max_rows": 500,
    "max_execution_ms": 8000
  },
  "clarification": null,
  "unsupported": null
}
```

### 6.1 SQLPlan 校验

SQLPlan 必须通过确定性校验：

1. domain 必须为 `logistics`。
2. table 必须在 catalog 表白名单。
3. fields 必须在对应表字段白名单。
4. metrics 必须引用 catalog 中已定义表达式。
5. filter 值类型必须与字段类型匹配。
6. 默认时间规则必须被显式写入 filters。
7. detail 查询必须有合理 `LIMIT`。
8. ranking 查询必须有排序方向和上限。
9. 任何 `unsupported` 或 `clarification` 非空时禁止生成 SQL。
10. 禁止 SQLPlan 携带原始 SQL 字符串。

---

## 7. SQL 生成与安全策略

### 7.1 SQL 生成原则

1. SQL 只能由 SQLPlan 生成，不允许跳过 SQLPlan。
2. LLM 可生成候选 SQL，但后端必须重新解析和校验。
3. 更推荐第一阶段由后端 deterministic renderer 根据 SQLPlan 渲染 SQL；LLM 只生成 SQLPlan。
4. 所有 value 使用绑定参数，不拼接用户原文。
5. SQL 方言固定 MySQL。

### 7.2 SQL 安全校验

使用 `sqlglot` + 自定义规则：

1. 必须是单条 `SELECT`。
2. 禁止 `INSERT/UPDATE/DELETE/MERGE/REPLACE/TRUNCATE/DROP/ALTER/CREATE/GRANT/REVOKE/CALL`。
3. 禁止多语句、分号注入、注释绕过。
4. 禁止访问非白名单表。
5. 禁止访问非白名单列。
6. 禁止 `information_schema/mysql/performance_schema/sys` 等系统库。
7. 禁止危险函数：`LOAD_FILE`、`SLEEP`、`BENCHMARK`、`INTO OUTFILE` 等。
8. 聚合查询的 `GROUP BY` 与 select 非聚合列必须一致。
9. 明细查询必须有限制行数。
10. 对运行成本高的语句设置 max execution time 和 row cap。

### 7.3 EXPLAIN / 试执行

执行门禁：

1. 先执行 `EXPLAIN`。
2. 检查是否访问白名单表。
3. 检查扫描行数和 join 类型是否超过阈值。
4. 先试执行：明细类 `LIMIT 20`，聚合类可完整跑但需超时限制。
5. 试执行通过后才正式执行。
6. 记录 SQL hash、参数 hash、EXPLAIN 摘要、执行耗时、返回行数。

---

## 8. SQL 自修复策略

自修复只允许修复“可安全识别的问题”，最多 2 轮。

允许修复：

1. 字段别名错误：根据 catalog 替换为合法字段。
2. 指标表达式错误：改为 catalog 指标表达式。
3. MySQL 方言语法错误：例如日期函数、LIMIT 语法。
4. GROUP BY 缺失或冗余。
5. 缺默认时间过滤。
6. detail 查询缺 LIMIT。

禁止修复：

1. 用户问题本身业务口径不清。
2. LLM 试图访问非白名单表或系统库。
3. 试图把不支持吨口径改成 MW 继续执行。
4. 试图扩大时间范围、实体范围来绕过空结果。
5. 连续 2 次失败后继续重试。

自修复输入只能包含：原问题、SQLPlan、catalog 摘要、安全错误类型、数据库错误摘要；不得包含真实密钥或大量业务明细数据。

---

## 9. 真实数据自动生成问题样例与标准答案

### 9.1 样例来源

1. `sys_query_log` 中真实用户问法。
2. 当前物流配置样例 JSON。
3. 当前业务验收测试中的问题族。
4. 中间库真实数据的维度值采样，例如年份、承运商、区域、城市、车型、客户。

### 9.2 标准答案生成原则

1. 标准答案必须由确定性 SQL / Python 计算生成。
2. 不使用 LLM 生成数值标准答案。
3. 每个样例保存：问题、SQLPlan、SQL hash、参数、结果摘要、关键数值、生成时间、catalog 版本。
4. 生成样例时要覆盖空结果、澄清、拒答、对比、排名、明细、聚合。
5. 对外展示只展示业务答案；内部评估可保存 SQLPlan / SQL hash / EXPLAIN。

### 9.3 首批样例族

1. 无时间条件发运量汇总：默认 2023-2026。
2. 指定年份/月份发运量汇总。
3. 承运商发运量排行：“哪个物流跑得最多”。
4. 区域/省份/城市分组发运量。
5. 总费用汇总。
6. 线路均价：`SUM(total_fee) / SUM(shipment_trip_count)`。
7. 多年份对比，保留无数据年份。
8. 2026 系统侧按扩充部门/委托人过滤，例如经营计划、刘娟口径。
9. 明细清单，强制 LIMIT。
10. 不支持吨数/运输吨位。

---

## 10. 日志与评估

### 10.1 Shadow 记录

允许在 shadow 阶段记录：

1. 原始问题；
2. rewritten question；
3. domain；
4. catalog 召回 IDs 与版本；
5. SQLPlan；
6. SQL hash；
7. 参数 hash；
8. SQL 安全校验结果；
9. EXPLAIN 摘要；
10. 试执行状态；
11. 正式执行状态；
12. 与当前确定性 QA 结果的一致性。

建议先落 `sys_query_log.request_payload.nl2sql_shadow`；如果后续日志量变大，再新增专用表。

### 10.2 评价指标

| 指标 | 目标 |
| --- | --- |
| SQL 安全违规放行数 | 0 |
| LLM 直接 SQL/答案越权放行数 | 0 |
| 支持问题 SQLPlan 生成成功率 | 第一阶段观察，不设硬门槛 |
| SQL 校验通过率 | 逐步提升 |
| EXPLAIN 通过率 | 逐步提升 |
| 与确定性 QA 数值一致率 | 核心 A 类问题 >= 99% 后才能考虑接管 |
| 澄清/拒答一致率 | >= 95% 后小流量灰度 |
| 用户可见技术泄露 | 0 |

---

## 11. 推荐实施阶段

### M0：只读发现与规划（已开始）

交付：

1. 中间库表结构快照。
2. 物流现有 query_key / 口径扫描。
3. 本设计文档。

不进入正式执行链路。

### M1：Semantic Catalog MVP

目标：先把“可查什么、怎么算、不能问什么”固化。

任务：

1. 新增 catalog YAML/JSON。
2. 写 catalog loader 与 schema 校验。
3. 自动从 MySQL inspector 生成 `tables.yaml` 初稿。
4. 从代码和用户确认口径生成 `metrics/rules/dimensions` 初稿。
5. 写单测，确保关键指标口径固定。

### M2：Milvus + Embedding + Rerank 接入

目标：让 catalog 可召回、可精排。

任务：

1. 新增百炼 embedding/rerank 配置项。
2. 接入 Qwen3-Embedding-4B。
3. 接入 Qwen3-Reranker。
4. 建 Milvus collection。
5. 写 catalog index/reindex 脚本。
6. 写召回/Rerank 单测和 smoke。

当前本机探测结果：Docker 中 `milvus-standalone` 和 `milvus-etcd` 处于退出状态，`localhost:19530` 暂不可连接；用户正在搭建本地 Milvus，预计很快可正常启动。进入 M2 前需要重新 smoke test Milvus 连接，并核对 `.env` 中实际 URI 配置。

### M3：SQLPlan 生成与确定性校验

目标：先生成可审计 SQLPlan，不执行 SQL。

任务：

1. 新增 SQLPlan schema。
2. 新增 SQLPlan validator。
3. 接入 Query Rewrite / Domain Router / Catalog context。
4. LLM 只输出 SQLPlan JSON。
5. 单测覆盖默认时间、均价、承运商排名、吨数拒答、字段越权。

### M4：SQL 渲染与安全校验

目标：后端从 SQLPlan 渲染 SQL，并通过 sqlglot 校验。

任务：

1. 引入 sqlglot。
2. 新增 deterministic SQL renderer。
3. 新增 SQL safety validator。
4. 新增参数绑定策略。
5. 单测覆盖注入、多语句、DDL/DML、系统库、非白名单表列。

### M5：EXPLAIN / 试执行 / 自修复 shadow

目标：在 shadow 中完成完整 NL2SQL 闭环，但不改变正式答案。

任务：

1. EXPLAIN 门禁。
2. 试执行门禁。
3. 自修复最多 2 轮。
4. shadow 写入 `sys_query_log`。
5. 与现有 QA 结果对比。

### M6：真实数据样例与标准答案自动生成

目标：形成可持续评估集。

任务：

1. 从真实中间库采样维度值。
2. 根据模板生成问题。
3. 用确定性 SQL 生成标准答案。
4. 保存评估样例和执行证据。
5. 接入回归测试。

### M7：灰度接管候选

只有当 M1-M6 的安全和一致性指标达标后，才考虑小范围接管：

1. 首批只接管高确定性聚合/排名问题。
2. 仍保留旧 QA fallback。
3. 可一键关闭 NL2SQL assist。
4. 每次接管必须有 focused tests + full regression + reviewer。

---

## 12. 建议目录结构

```text
backend/app/domains/query_planning/services/nl2sql/
  __init__.py
  query_rewriter.py
  domain_router.py
  catalog_retriever.py
  reranker.py
  sql_plan_generator.py
  sql_plan_validator.py
  sql_renderer.py
  sql_safety_validator.py
  explain_runner.py
  sql_repairer.py
  execution_service.py
  shadow_logger.py

backend/app/domains/query_planning/schemas/
  nl2sql.py

backend/app/domains/logistics/config/nl2sql_catalog/
  tables.yaml
  metrics.yaml
  dimensions.yaml
  joins.yaml
  rules.yaml
  examples.yaml

backend/app/domains/logistics/services/nl2sql/
  logistics_catalog_builder.py
  logistics_example_generator.py
  logistics_business_rules.py

tests/unit/query_planning/nl2sql/
  test_sql_plan_schema.py
  test_sql_plan_validator.py
  test_sql_safety_validator.py
  test_catalog_retriever.py

tests/business_acceptance/
  test_logistics_nl2sql_shadow.py
  test_logistics_nl2sql_real_data_examples.py

scripts/
  build_logistics_semantic_catalog.py
  index_logistics_semantic_catalog.py
  generate_logistics_nl2sql_examples.py
```

原则：共享 NL2SQL 框架放 `query_planning`，物流业务 catalog 与样例生成放 `logistics`，不要把新主逻辑继续塞到 `data_qa_planner.py`。

---

## 13. 已确认业务口径与仍需确认事项

### 13.1 已确认业务口径

1. 本地 Milvus 由用户继续搭建；实现 M2 前重新做连接 smoke test。
2. “件数”默认按 MW 回答，不启用 `shipment_count` 作为默认口径。
3. “今年 / 当前 / 最近”按系统当前年份解释。
4. 2023-2025 历史侧与 2026 系统侧混合查询时，所有维度都允许跨源对比。
5. 空结果时不放宽条件，只说明无数据并给出改问建议。

6. 线路“报价 / 单价 / 运价”继续走 `unit_price_per_vehicle`，并与“均价 = SUM(total_fee)/SUM(shipment_trip_count)”严格区分。

### 13.2 仍需后续业务确认事项

暂无。后续若业务方补充新的指标或口径，再作为 Semantic Catalog 版本升级处理。

---

## 14. 下一步建议

建议直接进入 M1：Semantic Catalog MVP。

第一批 TDD 任务：

1. 写 `metrics.yaml` schema 测试，锁定 `shipment_mw`、`avg_fee_per_trip`、`unit_price_per_vehicle`、`carrier_rank_by_mw`、`unsupported_tonnage`，并覆盖“件数”默认归入 `shipment_mw`、“报价/单价/运价”不走均价。
2. 写 `tables.yaml` 生成器测试，确保只纳入智能助手中间库物流白名单表。
3. 写 catalog loader 测试，确保表/字段/指标/规则都能按版本加载。
4. 写 SQLPlan validator RED 测试，先覆盖默认时间 2023-2026、“今年/当前/最近”按系统当前年份、均价分母、吨数拒答、跨源维度允许、空结果不放宽条件、非白名单表拦截。

完成 M1 后，再接 Milvus/Embedding/Rerank。

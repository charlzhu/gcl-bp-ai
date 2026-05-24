# NQE 统一 SQL Agent 正式主链路替换方案（最终修正版）

> 项目：gcl-bp-ai 经营计划智能助手  
> 文档定位：本轮 NQE 改造的最终主需求报告。  
> 核心目标：将当前物流、计划 BOM、电池 / 功率预测、产销存 / 经营分析等分散问答链路，逐步统一替换为“统一 SQL Agent 正式主链路”。  
> 当前主流程：LLM 生成 SQL → EXPLAIN 校验 → 错误则修正 SQL → 再执行 → 返回结果。  
> 重要修正：当前项目中的 `docs/HANDOFF.md`、`docs/CURRENT_STATUS.md`、`docs/NEXT_TASK.md` 记录的是物管 / SAP MID 相关任务状态，不是本轮 NQE 改造事实源。NQE 改造不得把这三个文件当作 NQE 当前状态，也不得直接覆盖其中物管任务内容。  
> 命名要求：代码、表名、接口、类名、变量、注释、提交信息、前端文案、项目文档中，均不得出现外部参考项目名称。统一使用 NQE、Unified SQL Agent、统一 SQL Agent、智能问数等内部命名。

---

## 1. 当前事实源边界修正

### 1.1 现有三份状态文件的定位

当前项目中的：

```text
docs/HANDOFF.md
docs/CURRENT_STATUS.md
docs/NEXT_TASK.md
```

内容是物管 / SAP MID 建设相关任务状态，不是 NQE 统一 SQL Agent 改造任务状态。

因此，本轮 NQE 改造中：

```text
不能把它们当作 NQE 需求依据
不能把它们当作 NQE 当前状态
不能直接覆盖它们已有的物管任务内容
不能要求 Hermes 在 NQE-SQL-MAIN-0 中强行更新这三份文件
```

### 1.2 NQE 应建立独立事实源

本轮 NQE 改造应新增独立事实源文档：

```text
docs/NQE_SQL_MAIN_CURRENT_STATUS.md
docs/NQE_SQL_MAIN_NEXT_TASK.md
docs/NQE_SQL_MAIN_HANDOFF.md
```

这三份文件用于记录 NQE 统一 SQL Agent 改造的状态、下一步任务和交接信息。

### 1.3 原三份文件的正确使用方式

原三份文件只能用于：

```text
了解当前项目是否存在并行物管任务
判断是否有任务冲突
判断是否有 worktree 风险
避免误覆盖其他任务状态
```

不能用于：

```text
作为 NQE 需求输入
作为 NQE 任务事实源
作为 NQE 验收标准
作为 NQE 看板内容来源
```

---

## 2. 本轮改造的最终口径

当前项目已经具备多个业务域能力：

1. 物流问答
2. 计划 BOM 问答
3. 电池 / 功率预测问答
4. 产销存 / 经营分析问答

但这些能力目前存在多套正式链路：

```text
物流：独立 planner / query_key / data QA service / 部分 NL2SQL shadow
BOM：独立候选消歧 / 明细查询 / compare / replay / QA service
功率预测：独立 Excel 模型解析 / 预测引擎 / 推荐服务
产销存：独立指标问答 / QueryPlan / 事实表查询
```

本轮改造目标是：

```text
从“多业务域、多条问答链路”
收敛为“一套统一 SQL Agent 主链路”
```

新主链路核心流程为：

```text
用户自然语言问题
→ 统一问数入口
→ 领域识别
→ 关键词提取
→ 表 / 字段 / 指标 / 字段取值 / 示例问法 / 口径召回
→ 合并召回信息
→ 过滤表、字段、指标、取值
→ 添加数据库上下文、日期上下文、业务域上下文
→ LLM 生成 SQL
→ SQL 安全预检
→ EXPLAIN / validate SQL
→ 如果 SQL 错误，则 LLM 修正 SQL
→ 再次 EXPLAIN / validate
→ 执行 SQL
→ 返回结果表格、指标、图表和答案表达
→ 记录 trace / query log / replay
```

---

## 3. 命名与保密边界

### 3.1 禁止出现的内容

后续所有代码、文档、提交信息、注释、前端文案中，禁止出现外部参考项目名称。

禁止出现在：

```text
目录名
文件名
类名
函数名
变量名
接口路径
数据库表名
配置项
注释
README
需求文档
提交信息
测试名称
前端标题
日志字段
看板标题
```

### 3.2 统一内部命名

统一使用以下内部名称：

| 场景 | 推荐命名 |
|---|---|
| 总能力 | NQE |
| 后端模块 | nqe |
| 主链路 | Unified SQL Agent |
| 中文名称 | 统一 SQL Agent / 统一问数 / 智能问数 |
| 前端页面 | NqeChatPage / 智能问数 |
| 元数据表 | nqe_* |
| Graph | NqeSqlAgentGraph |
| Trace | nqe_query_trace |
| 看板 Epic | NQE-SQL-MAIN |

### 3.3 对外说明口径

对领导或业务侧，只表达为：

```text
建设统一智能问数底座，整合物流、BOM、功率预测、产销存等业务域，提升自然语言问数、数据查询和结果表达能力。
```

不要表达为：

```text
参考 / 复刻 / 吸收某某外部项目。
```

---

## 4. 技术路线

### 4.1 当前阶段采用的主路线

当前阶段明确采用：

```text
LLM 生成 SQL
→ EXPLAIN 校验
→ SQL 错误则 LLM 修正
→ 再次校验
→ 执行 SQL
→ 返回结果
```

这条路线是本轮正式主链路替换目标，不只是实验线。

### 4.2 SQLPlan / ToolPlan 的定位

SQLPlan / ToolPlan 暂不作为当前第一阶段主目标。

它们保留为后续增强方向，用于：

1. 高风险查询的可控化。
2. 特殊复杂业务能力的工具化。
3. 后续生产安全收敛。
4. BOM compare / replay、功率预测等复杂业务 fallback。

当前不能让 Hermes 把主路线拉回“先 SQLPlan 化”，否则会偏离本轮目标。

---

## 5. 统一 SQL Agent 主流程设计

```text
receive_query
  ↓
domain_route
  ↓
extract_keywords
  ↓
recall_metadata 并行召回：
  - recall_tables
  - recall_columns
  - recall_metrics
  - recall_values
  - recall_examples
  - recall_business_rules
  ↓
merge_retrieved_context
  ↓
filter_metadata
  ↓
entity_resolve / optional_disambiguation
  ↓
add_extra_context
  ↓
generate_sql
  ↓
precheck_sql_safety
  ↓
explain_validate_sql
  ↓
need_correct?
  ├─ 是：correct_sql → explain_validate_sql
  └─ 否：execute_sql
  ↓
execute_sql_readonly
  ↓
present_result
  ↓
trace_log
```

---

## 6. 统一元数据知识库

### 6.1 建设目标

为 LLM 生成 SQL 提供可靠上下文，避免凭空猜表、猜字段、猜指标。

统一元数据知识库至少包含：

```text
业务域
表信息
字段信息
指标信息
字段与指标关系
维度信息
字段取值
表关联关系
示例问法
业务口径
Prompt 版本
评测集
查询 trace
```

### 6.2 建议新增表

```text
nqe_domain
nqe_table_info
nqe_column_info
nqe_metric_info
nqe_dimension_info
nqe_column_metric
nqe_value_info
nqe_join_info
nqe_example_question
nqe_business_rule
nqe_prompt_version
nqe_query_trace
nqe_shadow_compare
nqe_eval_suite
nqe_eval_case
```

### 6.3 技术取舍

| 能力 | 推荐方案 |
|---|---|
| 元数据存储 | 当前 MySQL 中间库，新增 nqe_* 表 |
| 向量检索 | 复用 Milvus |
| 字段取值检索 | 第一阶段优先 MySQL value index |
| 全文搜索 | 不强制引入 ES |
| 后端框架 | 沿用 FastAPI |
| 前端框架 | 沿用 Vue |
| 编排框架 | 使用 LangGraph / 现有 graph 能力 |

---

## 7. SQL 安全边界

### 7.1 只允许 SELECT

允许：

```text
SELECT
WITH ... SELECT
```

禁止：

```text
INSERT
UPDATE
DELETE
DROP
ALTER
TRUNCATE
CREATE
REPLACE
MERGE
CALL
EXEC
GRANT
REVOKE
LOAD
LOCK
UNLOCK
```

### 7.2 白名单表

只能访问业务白名单表。

禁止访问：

```text
用户表
权限表
系统配置表
密钥表
日志敏感表
任务调度表
数据库系统表
information_schema
mysql
performance_schema
sys
```

### 7.3 LIMIT 和结果规模

要求：

```text
明细查询默认 LIMIT 200
最大 LIMIT 1000
禁止无条件大表明细扫描
聚合查询需要限制 group by 结果规模
结果体积必须限制
```

### 7.4 EXPLAIN 校验

每条 SQL 执行前必须：

```text
EXPLAIN SQL
```

如果 EXPLAIN 失败：

```text
把数据库错误信息交给 correct_sql 节点
由 LLM 修正 SQL
再次 EXPLAIN
```

修正次数：

```text
最多 2 次
超过 2 次返回失败，并记录 trace
```

---

## 8. 业务域替换方案

### 8.1 物流：第一阶段替换

物流最适合作为首个替换域。

保留：

```text
旧 LogisticsDataQaService 作为 fallback
旧 query_key 作为对照
旧 NL2SQL shadow 结果作为参考
```

### 8.2 产销存 / 经营分析：第二阶段替换

保留：

```text
旧产销存 QA service 作为 fallback
旧 QueryPlan 结果作为对照
```

### 8.3 BOM：第三阶段替换

替换原则：

```text
简单明细查询优先 SQL Agent 化
订单 / 文件 / 版本候选需要接入统一消歧
compare / replay 暂时保留 fallback
不强行一次性 SQL 化复杂业务规则
```

### 8.4 电池 / 功率预测：第四阶段替换

替换原则：

```text
SQL Agent 作为统一主入口
SQL Agent 查询模型参数、配置项、历史分布、供应商效率
涉及预测计算时保留 PowerPredictionEngine fallback
长期再评估是否把部分预测逻辑 SQL 化
```

---

## 9. 看板 Epic 与任务拆解

总 Epic：

```text
NQE-SQL-MAIN：统一 SQL Agent 正式主链路替换
```

### 9.1 第一批：只读审计与总设计

| 卡号 | 标题 | 是否编码 |
|---|---|---|
| NQE-SQL-MAIN-0 | 只读审计现有四大业务域正式链路 | 否 |
| NQE-SQL-MAIN-1 | 统一 SQL Agent 主链路设计 | 否 |
| NQE-SQL-MAIN-2 | 统一元数据知识库表设计 | 否 |
| NQE-SQL-MAIN-3 | 多路召回机制设计与实现方案 | 否 |
| NQE-SQL-MAIN-4 | LangGraph SQL Agent 主流程设计 | 否 |
| NQE-SQL-MAIN-5 | SQL 生成 / validate / correct / execute 安全边界设计 | 否 |

### 9.2 第二批：底座实现

| 卡号 | 标题 | 是否编码 |
|---|---|---|
| NQE-SQL-MAIN-6 | nqe_* 元数据表 Alembic 迁移 | 是 |
| NQE-SQL-MAIN-7 | 元数据同步脚本 | 是 |
| NQE-SQL-MAIN-8 | Milvus 元数据向量索引 | 是 |
| NQE-SQL-MAIN-9 | MySQL value index 字段取值索引 | 是 |
| NQE-SQL-MAIN-10 | 统一 SQL Agent Graph 骨架 | 是 |
| NQE-SQL-MAIN-11 | SQL 安全预检与白名单拦截 | 是 |
| NQE-SQL-MAIN-12 | EXPLAIN validate 与 correct SQL 节点 | 是 |
| NQE-SQL-MAIN-13 | trace / query log / replay | 是 |

### 9.3 第三批：物流替换

| 卡号 | 标题 | 是否编码 |
|---|---|---|
| NQE-SQL-MAIN-14 | 物流元数据同步 | 是 |
| NQE-SQL-MAIN-15 | 物流 SQL Agent 接入 | 是 |
| NQE-SQL-MAIN-16 | 物流正式链路灰度切换 | 是 |
| NQE-SQL-MAIN-17 | 物流 fallback 与 shadow compare | 是 |
| NQE-SQL-MAIN-18 | 物流评测集回归 | 是 |

### 9.4 第四批：产销存替换

| 卡号 | 标题 | 是否编码 |
|---|---|---|
| NQE-SQL-MAIN-19 | 产销存元数据同步 | 是 |
| NQE-SQL-MAIN-20 | 产销存 SQL Agent 接入 | 是 |
| NQE-SQL-MAIN-21 | 产销存正式链路灰度切换 | 是 |
| NQE-SQL-MAIN-22 | 产销存 fallback 与回归评测 | 是 |

### 9.5 第五批：BOM 替换

| 卡号 | 标题 | 是否编码 |
|---|---|---|
| NQE-SQL-MAIN-23 | BOM 元数据同步 | 是 |
| NQE-SQL-MAIN-24 | BOM SQL Agent 接入 | 是 |
| NQE-SQL-MAIN-25 | BOM 候选消歧接入 SQL Agent | 是 |
| NQE-SQL-MAIN-26 | BOM compare / replay fallback 策略 | 是 |
| NQE-SQL-MAIN-27 | BOM 正式入口灰度切换 | 是 |
| NQE-SQL-MAIN-28 | BOM 评测集回归 | 是 |

### 9.6 第六批：功率预测替换

| 卡号 | 标题 | 是否编码 |
|---|---|---|
| NQE-SQL-MAIN-29 | 功率预测元数据同步 | 是 |
| NQE-SQL-MAIN-30 | 功率预测 SQL Agent 接入 | 是 |
| NQE-SQL-MAIN-31 | PowerPredictionEngine fallback 接入 | 是 |
| NQE-SQL-MAIN-32 | 功率预测正式入口灰度切换 | 是 |
| NQE-SQL-MAIN-33 | 功率预测评测集回归 | 是 |

---

## 10. 第一轮执行要求

第一轮只执行：

```text
NQE-SQL-MAIN-0：只读审计现有四大业务域正式链路
```

要求：

```text
只读审计
设计文档
看板建设
不修改业务代码
不调用 Codex 编码
不替换任何正式链路
不覆盖物管任务状态文件
```

NQE-SQL-MAIN-0 需要产出：

```text
docs/NQE_SQL_MAIN_ARCHITECTURE.md
docs/NQE_SQL_MAIN_REPLACEMENT_PLAN.md
docs/NQE_SQL_MAIN_DOMAIN_AUDIT.md
docs/NQE_SQL_MAIN_SAFETY_BOUNDARY.md
docs/NQE_SQL_MAIN_TASK_BREAKDOWN.md
docs/NQE_SQL_MAIN_KANBAN_PLAN.md
docs/NQE_SQL_MAIN_CURRENT_STATUS.md
docs/NQE_SQL_MAIN_NEXT_TASK.md
docs/NQE_SQL_MAIN_HANDOFF.md
```

---

## 11. 当前最重要的执行口径

```text
以统一 SQL Agent 作为新正式主链路目标；
旧链路先保留 fallback；
物流先替换；
产销存第二；
BOM 第三；
功率预测最后；
第一轮只读审计和建看板；
代码和文档中不得出现外部参考项目名称；
不要把现有 HANDOFF / CURRENT_STATUS / NEXT_TASK 当作 NQE 事实源；
NQE 单独建立 NQE_SQL_MAIN_* 状态文档。
```

# NQE-SQL-MAIN-1：统一 SQL Agent 主链路设计

> 本文档属于 NQE-SQL-MAIN 独立事实源。当前卡只做主链路设计，不修改业务代码、不调用编码代理、不替换正式链路。

## 1. 设计结论

NQE 统一 SQL Agent 应作为新的智能问数主链路，目标是把物流、产销存/经营分析、计划 BOM、功率预测逐步收敛到同一套自然语言问数底座。

当前阶段主路线保持为：

```text
自然语言问题
→ 统一问数入口
→ 领域识别
→ 关键词提取
→ 多路元数据召回
→ 召回信息合并和过滤
→ 添加日期、数据库、业务口径上下文
→ LLM 直接生成 SQL
→ SQL 安全预检
→ EXPLAIN 校验
→ SQL 错误修正闭环
→ 只读执行
→ 业务化结果表达
→ trace / query log / replay / shadow compare
```

本阶段不引入 SQLPlan / ToolPlan 作为主路线。它们仅保留为后续高风险查询、复杂工具编排、特殊业务能力 fallback 的增强方向。

## 2. 当前仓库与目标主链路差距

| 维度 | 当前仓库已有能力 | NQE-SQL-MAIN-1 设计判断 | 后续承接卡 |
|---|---|---|---|
| Graph 编排 | 已有统一 Graph 雏形，覆盖领域路由、关键词、三路召回、合并过滤、生成 SQL、校验、修正、执行 | 可作为 NQE Graph 的技术基础，但需迁移到 NQE 命名、补齐安全预检、trace 和正式入口契约 | NQE-SQL-MAIN-4、10、11、12、13 |
| API 入口 | 现有正式入口仍面向业务问答分流，另有历史统一 SQL 原型入口 | 需要新增 NQE 统一入口，保留旧入口 fallback，不直接替换 | NQE-SQL-MAIN-10、34、35 |
| 多路召回 | 当前已有字段、指标、字段取值召回能力 | 目标需要扩展为表、字段、指标、取值、示例问法、业务口径六类召回 | NQE-SQL-MAIN-3、8、9 |
| 元数据 | 当前存在 unified catalog 与领域 catalog | 需要沉淀为 nqe_* 统一元数据知识库，解决四域覆盖和版本追溯 | NQE-SQL-MAIN-2、6、7 |
| SQL 安全 | 当前校验闭环不足以直接作为正式生产主链路 | 必须在 EXPLAIN 前增加只读、单语句、白名单、系统库、LIMIT、超时等预检 | NQE-SQL-MAIN-5、11、12 |
| 四域替换 | 物流、产销存、BOM、功率预测均有独立旧链路 | 统一 SQL Agent 逐域灰度，旧链路作为 fallback / shadow compare / replay | NQE-SQL-MAIN-14～33 |
| 前端体验 | 当前页面已有多业务域流式体验和结果表格 | 需新增或改造 NQE Chat 统一问数入口，用户可见内容不得暴露内部技术细节 | NQE-SQL-MAIN-34～39 |

## 3. 目标主链路逻辑节点

### 3.1 入口与状态初始化

```text
receive_query
```

职责：

1. 接收 `question`、`domain_hint`、`mode`、`trace_id`。
2. 生成本次查询 trace 上下文。
3. 写入请求来源、前端入口、灰度模式。
4. 对用户问题做长度、空值、敏感输入初筛。

设计约束：

1. 用户可见响应不得回显内部 SQL、表名、字段名、prompt、raw/debug。
2. trace 内部记录需要脱敏，禁止记录凭证、连接串、真实密钥。
3. NQE 入口默认 `shadow` 或 `off`，不得全域直接 `on`。

### 3.2 领域识别

```text
domain_route
```

职责：

1. 判断问题属于物流、产销存/经营分析、计划 BOM、功率预测或暂不支持。
2. 支持 `domain_hint` 强约束，但仍需校验该域是否开放。
3. 低置信度时返回业务化澄清，不执行 SQL。

输出：

```text
domain
confidence
route_reason_internal
need_clarify
```

约束：

1. 不允许纯关键词硬编码覆盖全部语义。
2. 不允许把物管 / SAP MID 并行任务状态误当作本轮 NQE 事实源。
3. 功率预测仍归属计划 BOM 子能力，预测计算不能由 LLM 直接完成。

### 3.3 关键词提取

```text
extract_keywords
```

职责：

1. 提取业务实体、时间表达、指标词、维度词、动作词。
2. 将问题中的年份、月份、基地、客户、承运商、物料、BOM 标识等输入归一为候选槽位。
3. 只做候选，不直接决定最终 SQL。

### 3.4 多路召回

```text
recall_tables
recall_columns
recall_metrics
recall_values
recall_examples
recall_business_rules
```

设计要求：

1. 字段召回：根据问题关键词、别名、字段说明、业务域做向量召回。
2. 指标召回：根据指标名、口径、单位、聚合方式、适用域召回。
3. 字段取值召回：第一阶段优先 MySQL value index + 字符串相似度，不强制引入新的外部全文检索栈。
4. 表召回：基于业务域、字段覆盖、指标关系、join 关系召回候选表。
5. 示例问法召回：召回历史验收题和标准问法，辅助 SQL 生成但不能 hardcode 答案。
6. 业务口径召回：召回默认时间范围、指标等价词、字段映射、口径限制。

### 3.5 合并、过滤、消歧

```text
merge_retrieved_context
filter_metadata
entity_resolve
optional_disambiguation
```

职责：

1. 合并表、字段、指标、取值、示例、口径上下文。
2. 去重并按业务域和置信度排序。
3. 过滤不属于当前域或未开放的表字段。
4. 对 BOM 文件、客户实例、评审号、版本等多候选场景触发消歧。
5. 低置信度或多候选无法确定时返回业务化澄清，不生成 SQL。

### 3.6 上下文补充

```text
add_extra_context
```

补充内容：

1. 当前日期、年月、季度、默认时间范围。
2. 数据库方言和只读执行约束。
3. 当前业务域已开放表、字段、指标、join 关系。
4. 当前灰度模式和 fallback 策略。
5. 用户可见内容屏蔽要求。

### 3.7 SQL 生成

```text
generate_sql
```

输入：

1. 用户原始问题。
2. 当前业务域。
3. 已过滤元数据上下文。
4. 业务口径和默认时间规则。
5. 数据库方言、LIMIT 和聚合约束。

输出：

```text
单条 SQL 文本
```

约束：

1. 本阶段坚持 LLM 直接生成 SQL，不生成 SQLPlan JSON。
2. 只能生成单条 SELECT 或 WITH ... SELECT。
3. 明细查询必须带 LIMIT。
4. 不允许访问未召回或未白名单开放的表。
5. SQL 仅作为内部执行和 trace 数据，不向用户展示。

### 3.8 SQL 安全预检

```text
precheck_sql_safety
```

必须在 EXPLAIN 前执行，至少覆盖：

1. 单语句检查。
2. 只读检查：仅允许 SELECT / WITH ... SELECT。
3. 禁止 DDL / DML / 权限 / 过程调用 / 锁表等危险语句。
4. 白名单表检查。
5. 系统库和敏感表检查。
6. LIMIT / 最大返回行数 / 超时策略。
7. 注释、堆叠语句、危险函数、文件读写函数检查。
8. SQL 方言解析失败时进入错误分支，不执行。

### 3.9 EXPLAIN 校验与 SQL 修正

```text
explain_validate_sql
correct_sql
```

闭环：

1. 安全预检通过后执行 EXPLAIN。
2. EXPLAIN 失败时，脱敏数据库错误信息后交给修正节点。
3. 修正后的 SQL 必须重新经过安全预检和 EXPLAIN。
4. 最大修正次数建议为 2 次；超过后返回业务化失败提示并记录 trace。
5. 安全预检失败不得交给 LLM 绕过规则修正后直接执行，应按安全失败处理。

### 3.10 只读执行

```text
execute_sql_readonly
```

执行约束：

1. 使用只读数据库连接或只读事务。
2. 设置语句超时和结果行数上限。
3. 聚合查询返回结果规模必须受控。
4. 明细查询最多返回配置上限。
5. 执行结果进入统一 result model。
6. 不允许直接查询外部同步源生产库；用户问答只查智能助手中间库。

### 3.11 业务化表达与用户可见输出

```text
present_result
```

输出结构：

```text
answer_summary
result_table
metric_cards
chart_suggestions
clarification
warnings
trace_id
```

用户可见限制：

1. 不展示 SQL。
2. 不展示表名、字段名、query_key、planner、guardrail、schema、raw/debug、LLM 等技术内容。
3. 展示业务口径、筛选条件、时间范围、统计口径和结果摘要。
4. 对空结果、缺数据、口径不明确场景给业务化说明或澄清问题。

### 3.12 trace / query log / replay / shadow compare

```text
record_trace
record_query_log
record_replay_snapshot
record_shadow_compare
```

内部记录：

1. 请求、领域识别、召回摘要、过滤摘要。
2. SQL 生成版本、预检结果、EXPLAIN 结果、修正次数。
3. 执行耗时、行数、错误码、fallback 状态。
4. shadow 模式下新旧链路结果差异。
5. replay 所需的 prompt 版本、元数据版本、灰度模式。

记录边界：

1. 内部 trace 可以记录脱敏 SQL，用于审计和回放。
2. 用户可见回答不得暴露内部 SQL 和技术字段。
3. trace 表不得记录凭证、连接串、真实密钥。

## 4. 灰度与 fallback 模式

每个域独立支持：

```text
off
shadow
assist
on
```

| 模式 | 行为 | 用户看到的结果 | 用途 |
|---|---|---|---|
| off | 不走 NQE | 旧链路 | 默认安全关闭 |
| shadow | NQE 后台执行并记录对比 | 旧链路 | 评估正确率和风险 |
| assist | NQE 参与理解/召回/候选，旧链路可兜底 | 旧链路或混合结果 | 灰度增强 |
| on | NQE 优先作为正式主链路，旧链路 fallback | NQE 结果或 fallback 结果 | 正式替换 |

切换原则：

1. 每个域单独开关，不允许全域一次性切换。
2. `on` 前必须完成本域评测集、fallback、shadow compare 和回滚演练。
3. 出现安全预检失败、EXPLAIN 失败、执行超时、低置信度或多候选未消歧时，按配置 fallback 或业务化失败。

## 5. 四域接入策略

| 业务域 | 首版 NQE 主链路范围 | 必须 fallback | 关键验收 |
|---|---|---|---|
| 物流 | 费用、车次、客户、承运商、线路、基地、时间维度的明细和聚合查询 | 现有物流 QA service、旧口径链路、shadow compare | 物流全量样例和历史回归通过，均价等口径一致 |
| 产销存/经营分析 | 产量、销量、库存、预算达成率等指标查询 | 现有产销存 QA service、缺数据反问逻辑 | 指标口径、发布月份、库存等价词一致 |
| 计划 BOM | BOM 明细、物料、供应商、项目、文件维度查询 | 候选消歧、compare、replay、计划 BOM QA service | 文件名、客户实例、评审号、版本消歧通用，不 hardcode |
| 功率预测 | 统一入口、预测输入参数、历史分布、配置项、结果追溯查询 | PowerPredictionEngine、推荐服务 | 预测计算由确定性引擎完成，LLM 不直接计算 |

## 6. API 与前端契约设计

### 6.1 后端入口

建议后续新增内部命名入口：

```text
POST /api/v1/nqe/query
POST /api/v1/nqe/query/stream
```

请求字段：

```text
question
domain_hint
mode
trace_id
client_context
```

响应事件：

```text
received
domain_routed
metadata_recalled
metadata_filtered
sql_generated_internal
sql_prechecked
sql_validated
sql_corrected
sql_executed
fallback_used
answer_delta
done
error
```

注意：`sql_generated_internal`、`sql_prechecked`、`sql_validated` 等事件可以用于内部进度和 trace，但前端用户可见文案必须业务化，不直接展示 SQL 文本。

### 6.2 前端入口

目标：

1. 新增或改造智能问数入口。
2. 支持领域自动识别和显式领域选择。
3. 支持进度时间线、结果表格、指标卡、图表建议、多候选消歧。
4. 复用当前成熟流式体验，但事件协议统一为 NQE。
5. 禁止在界面暴露 SQL、内部表字段、prompt、raw/debug 等技术内容。

## 7. NQE-SQL-MAIN-1 验收判断

本卡完成后应满足：

1. 已明确统一 SQL Agent 主链路逻辑节点。
2. 已明确当前仓库与目标链路差距。
3. 已明确 SQL 安全预检在 EXPLAIN 前执行。
4. 已明确 LLM 直接生成 SQL 是当前阶段主路线，不回退为 SQLPlan 主路线。
5. 已明确四域灰度、fallback 和接入顺序。
6. 已明确 API/前端契约方向。
7. 未修改业务代码。
8. 未调用编码代理。
9. 未覆盖物管 / SAP MID 状态文件。
10. 新增文档未包含外部参考项目名称。

## 8. 后续看板衔接

NQE-SQL-MAIN-1 完成后，按编号进入：

```text
NQE-SQL-MAIN-2：统一元数据知识库表设计
```

NQE-SQL-MAIN-2 应基于本文件确定的逻辑节点，细化 `nqe_*` 元数据表、字段、关系、索引、版本、同步和审计设计。

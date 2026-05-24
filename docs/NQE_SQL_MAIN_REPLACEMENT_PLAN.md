# NQE 正式链路替换计划

> 本文档属于 NQE-SQL-MAIN 独立事实源。当前只执行 NQE-SQL-MAIN-0：只读审计、总体设计、建看板；不修改业务代码、不调用编码代理、不替换正式链路。

## 1. 替换原则

1. 新统一 SQL Agent 逐步成为正式主入口。
2. 旧链路先保留为 fallback / replay / shadow compare。
3. 通过配置开关逐域切换，不一次性替换四域。
4. 每个业务域独立验收、独立回滚。
5. SQL Agent 失败时必须能回退到旧服务或业务化失败提示。
6. 用户可见回答不得暴露 SQL、表名、字段名、query_key、planner、guardrail、schema、raw/debug、LLM 等内部技术内容。

## 2. 推荐上线顺序

| 顺序 | 业务域 | 原因 | 主要 fallback |
|---:|---|---|---|
| 1 | 物流 | 数据结构相对表格化；已有 NL2SQL/shadow/assist 基础；回归样例最充分 | 物流现有 QA service、旧 query_key/planner、shadow compare |
| 2 | 产销存 / 经营分析 | 指标口径较清晰，适合沉淀 nqe_metric_info 与业务规则召回 | 现有产销存 QA service 和指标计算服务 |
| 3 | 计划 BOM | 简单明细查询适合 SQL Agent；但消歧/compare/replay 较复杂 | 计划 BOM QA service、候选消歧、compare/replay |
| 4 | 功率预测 | 统一入口可承接问法，但预测计算必须由确定性引擎完成 | PowerPredictionEngine、推荐服务、计划 BOM 子能力 |

## 3. 阶段划分

### 阶段 A：只读审计与设计（NQE-SQL-MAIN-0～5）

交付：

1. 四域正式链路审计。
2. 统一 SQL Agent 主链路设计。
3. nqe_* 元数据知识库设计。
4. 多路召回机制设计。
5. Graph 主流程设计。
6. SQL 安全边界设计。

验收：不改业务代码、不启动编码代理、设计覆盖四域、看板任务完整。

### 阶段 B：底座实现（NQE-SQL-MAIN-6～13）

交付：

1. nqe_* 元数据表迁移。
2. 元数据同步脚本。
3. Milvus 元数据向量索引。
4. MySQL value index 字段取值索引。
5. NQE Graph 骨架。
6. SQL 安全预检。
7. EXPLAIN validate / correct SQL。
8. trace / query log / replay。

验收：底座单测通过；SQL 安全测试覆盖只读、白名单、系统库、DML/DDL、LIMIT、超时、错误修正。

### 阶段 C：物流替换（NQE-SQL-MAIN-14～18）

交付：物流元数据同步、物流 SQL Agent 接入、灰度切换、fallback/shadow compare、物流评测集回归。

切换策略：

```text
off → shadow → assist → on
```

回滚：配置切回 off 或旧物流服务；保留 NQE trace 用于复盘。

验收：物流主链路全量回归通过；用户可见回答不泄露内部技术内容；shadow compare 有统计。

### 阶段 D：产销存替换（NQE-SQL-MAIN-19～22）

交付：产销存元数据同步、SQL Agent 接入、正式链路灰度、fallback 与回归评测。

回滚：切回现有产销存 QA service。

验收：产量、销量、库存、达成率等核心指标口径一致；缺数据场景业务化反问或提示。

### 阶段 E：计划 BOM 替换（NQE-SQL-MAIN-23～28）

交付：BOM 元数据同步、简单查询 SQL Agent 化、候选消歧接入、compare/replay fallback、灰度切换、回归评测。

回滚：切回现有 PlanBomQaService 与候选消歧逻辑。

验收：BOM 文件名、客户实例、评审号、版本消歧保持通用确定性，不硬编码具体案例；复杂 compare/replay 不被强行 SQL 化。

### 阶段 F：功率预测替换（NQE-SQL-MAIN-29～33）

交付：功率预测元数据同步、统一入口接入、PowerPredictionEngine fallback、灰度切换、评测回归。

回滚：切回计划 BOM 功率预测原有入口。

验收：功率档位、比例、供应商效率、匹配度等由确定性引擎输出；LLM 不直接计算业务事实。

### 阶段 G：前端、运营与最终评审（NQE-SQL-MAIN-34～43）

交付：NQE Chat 页面、流式事件消费器、进度时间线、结果表格/指标卡/图表、多候选消歧、quick chips 后端化、灰度配置、运营指标看板、旧链路下线评估、Go/No-Go 评审。

## 4. 每域替换矩阵

| 域 | 可直接 SQL Agent 化 | 必须保留 fallback | 不建议第一版做 |
|---|---|---|---|
| 物流 | 按时间、基地、客户、承运商、线路、费用、车次、功率等维度聚合/明细查询 | 旧物流 QA service、业务化回答兜底、shadow compare | 删除旧 service、绕过现有全量回归 |
| 产销存 | 月度事实表聚合、预算达成率、库存/发货/产量对比 | 旧产销存指标服务、缺数据反问 | 把未来月份当实际数据、未确认口径即 SQL 化 |
| 计划 BOM | BOM 明细、物料、供应商、项目、文件维度查询 | 候选消歧、compare、replay、计划 BOM QA service | 硬编码样例、一次性重写 BOM 全链路 |
| 功率预测 | 预测输入参数、历史分布、配置项、结果追溯查询 | PowerPredictionEngine、推荐服务 | 让 LLM 直接算功率预测结果 |

## 5. 配置开关建议

建议按域配置：

```text
NQE_LOGISTICS_MODE=off|shadow|assist|on
NQE_BUSINESS_ANALYSIS_MODE=off|shadow|assist|on
NQE_PLAN_BOM_MODE=off|shadow|assist|on
NQE_PLAN_POWER_MODE=off|shadow|assist|on
```

开关约束：

1. 默认 off 或 shadow。
2. 每域独立控制，不允许全域同开。
3. on 之前必须完成本域评测集与 fallback。
4. 每次切换必须记录 trace、版本、操作者、时间和回滚方式。

## 6. 下线旧链路条件

旧链路不在前期删除。只有满足以下条件，才进入下线评估：

1. 对应域 NQE on 模式稳定运行。
2. 本域全量评测与历史回归通过。
3. shadow compare 指标达到用户确认阈值。
4. fallback 触发率和错误率可接受。
5. 已完成旧链路影响面审计和回滚演练。
6. 用户明确批准下线。

## 7. 当前替换结论

1. 当前不建议直接进入编码切换；应先执行设计卡 NQE-SQL-MAIN-1～5。
2. 当前最大风险是 SQL 安全闭环不足，必须先做 NQE-SQL-MAIN-5/11/12。
3. 物流可作为第一正式替换域，但必须保留旧链路 fallback 和全量回归。
4. 产销存、BOM、功率预测均不能越过元数据、口径、消歧和 fallback 设计直接接入。

# NQE-SQL-MAIN 任务拆解

> 本文档是 NQE-SQL-MAIN Epic 的任务拆解说明。看板卡已按同名任务创建，后续编码卡必须先经用户确认和 Hermes 验收，不得自动启动。

## 1. Epic

```text
NQE-SQL-MAIN：统一 SQL Agent 正式主链路替换
```

## 2. 任务总表

| 卡号 | 标题 | 类型 | 是否允许编码 | 依赖 |
|---|---|---|---|---|
| NQE-SQL-MAIN-0 | 只读审计现有四大业务域正式链路 | 审计/规划 | 否 | 无 |
| NQE-SQL-MAIN-1 | 统一 SQL Agent 主链路设计 | 设计 | 否 | 0 |
| NQE-SQL-MAIN-2 | 统一元数据知识库表设计 | 设计 | 否 | 1 |
| NQE-SQL-MAIN-3 | 多路召回机制设计与实现方案 | 设计 | 否 | 1,2 |
| NQE-SQL-MAIN-4 | LangGraph SQL Agent 主流程设计 | 设计 | 否 | 1,3 |
| NQE-SQL-MAIN-5 | SQL 生成 / validate / correct / execute 安全边界设计 | 设计 | 否 | 1 |
| NQE-SQL-MAIN-6 | nqe_* 元数据表 Alembic 迁移 | 底座实现 | 是 | 2,5 |
| NQE-SQL-MAIN-7 | 元数据同步脚本 | 底座实现 | 是 | 6 |
| NQE-SQL-MAIN-8 | Milvus 元数据向量索引 | 底座实现 | 是 | 7 |
| NQE-SQL-MAIN-9 | MySQL value index 字段取值索引 | 底座实现 | 是 | 7 |
| NQE-SQL-MAIN-10 | 统一 SQL Agent Graph 骨架 | 底座实现 | 是 | 4,5 |
| NQE-SQL-MAIN-11 | SQL 安全预检与白名单拦截 | 底座实现 | 是 | 5,10 |
| NQE-SQL-MAIN-12 | EXPLAIN validate 与 correct SQL 节点 | 底座实现 | 是 | 10,11 |
| NQE-SQL-MAIN-13 | trace / query log / replay | 底座实现 | 是 | 10,11,12 |
| NQE-SQL-MAIN-14 | 物流元数据同步 | 物流 | 是 | 7,8,9 |
| NQE-SQL-MAIN-15 | 物流 SQL Agent 接入 | 物流 | 是 | 10,11,12,14 |
| NQE-SQL-MAIN-16 | 物流正式链路灰度切换 | 物流 | 是 | 15 |
| NQE-SQL-MAIN-17 | 物流 fallback 与 shadow compare | 物流 | 是 | 15,16 |
| NQE-SQL-MAIN-18 | 物流评测集回归 | 物流 | 是 | 15,16,17 |
| NQE-SQL-MAIN-19 | 产销存元数据同步 | 经营分析 | 是 | 7,8,9 |
| NQE-SQL-MAIN-20 | 产销存 SQL Agent 接入 | 经营分析 | 是 | 10,11,12,19 |
| NQE-SQL-MAIN-21 | 产销存正式链路灰度切换 | 经营分析 | 是 | 20 |
| NQE-SQL-MAIN-22 | 产销存 fallback 与回归评测 | 经营分析 | 是 | 20,21 |
| NQE-SQL-MAIN-23 | BOM 元数据同步 | 计划 BOM | 是 | 7,8,9 |
| NQE-SQL-MAIN-24 | BOM SQL Agent 接入 | 计划 BOM | 是 | 10,11,12,23 |
| NQE-SQL-MAIN-25 | BOM 候选消歧接入 SQL Agent | 计划 BOM | 是 | 24 |
| NQE-SQL-MAIN-26 | BOM compare / replay fallback 策略 | 计划 BOM | 是 | 24,25 |
| NQE-SQL-MAIN-27 | BOM 正式入口灰度切换 | 计划 BOM | 是 | 24,25,26 |
| NQE-SQL-MAIN-28 | BOM 评测集回归 | 计划 BOM | 是 | 27 |
| NQE-SQL-MAIN-29 | 功率预测元数据同步 | 功率预测 | 是 | 7,8,9 |
| NQE-SQL-MAIN-30 | 功率预测 SQL Agent 接入 | 功率预测 | 是 | 10,11,12,29 |
| NQE-SQL-MAIN-31 | PowerPredictionEngine fallback 接入 | 功率预测 | 是 | 30 |
| NQE-SQL-MAIN-32 | 功率预测正式入口灰度切换 | 功率预测 | 是 | 30,31 |
| NQE-SQL-MAIN-33 | 功率预测评测集回归 | 功率预测 | 是 | 32 |
| NQE-SQL-MAIN-34 | 前端 NQE Chat 页面 | 前端 | 是 | 10,13 |
| NQE-SQL-MAIN-35 | 流式事件消费器 | 前端 | 是 | 13,34 |
| NQE-SQL-MAIN-36 | SQL Agent 进度时间线组件 | 前端 | 是 | 35 |
| NQE-SQL-MAIN-37 | 查询结果表格 / 指标卡 / 图表组件 | 前端 | 是 | 34,35 |
| NQE-SQL-MAIN-38 | 多候选消歧组件 | 前端 | 是 | 25,34 |
| NQE-SQL-MAIN-39 | quick chips 后端化 | 前端 | 是 | 34 |
| NQE-SQL-MAIN-40 | shadow / assist / on 灰度配置 | 灰度 | 是 | 10,13 |
| NQE-SQL-MAIN-41 | 运营指标与正确率看板 | 运营 | 是 | 13,18,22,28,33 |
| NQE-SQL-MAIN-42 | 四域旧链路下线评估报告 | 评审 | 否 | 18,22,28,33,41 |
| NQE-SQL-MAIN-43 | 最终 Go / No-Go 评审 | 评审 | 否 | 42 |

## 3. 第一阶段建议执行顺序

当前只完成 NQE-SQL-MAIN-0。后续建议按以下顺序推进：

```text
1 → 2 → 3 → 4 → 5 → 用户确认 → 6～13 → 14～18 → 19～22 → 23～28 → 29～33 → 34～41 → 42～43
```

说明：

1. NQE-SQL-MAIN-1～5 都是设计卡，不建议跳过。
2. NQE-SQL-MAIN-6～13 是底座实现，未完成前不能切任何正式链路。
3. NQE-SQL-MAIN-14～18 只替换物流，不扩到其他域。
4. 后续每域都必须先 shadow/assist，再 on。

## 4. 每张卡通用字段要求

每张看板卡必须包含：

1. 任务标题。
2. 背景。
3. 目标。
4. 不做什么。
5. 涉及文件范围。
6. 依赖任务。
7. 交付物。
8. 验收标准。
9. 风险点。
10. 是否允许 Codex 编码。
11. 是否只读。
12. 推荐状态。

## 5. 编码卡启动前置条件

任何允许编码的卡启动前，必须完成：

1. `git status` 检查。
2. 分支检查。
3. dirty worktree 检查。
4. scoped 文件范围确认。
5. 明确本卡禁止修改文件。
6. 明确测试命令。
7. 明确验收标准。
8. 用户确认进入该阶段。
9. Hermes claim 对应看板卡。
10. 编码完成后由 Hermes 复查 diff 与测试。

## 6. 当前看板状态策略

1. NQE-SQL-MAIN-0：已执行并验收。
2. NQE-SQL-MAIN-1：已进入执行并输出主链路设计。
3. NQE-SQL-MAIN-2～43：按编号逐卡监控、解锁、claim、验收；设计卡 2～5 不允许编码，编码卡 6～41 启动前必须先完成 scoped 范围、测试和回滚设计。

## 7. 当前风险

1. 如果跳过 1～5 直接进入实现，会导致 SQL 安全、元数据模型和 Graph 边界不清。
2. 如果跳过底座 6～13 直接替换物流，会出现 SQL 执行不可控和 trace 不完整。
3. 如果四域并行替换，会显著增加回归风险。
4. 如果文档或代码出现外部参考项目名称，会违反本轮命名边界。
5. 如果覆盖物管状态文件，会干扰并行 SAP MID 任务事实源。

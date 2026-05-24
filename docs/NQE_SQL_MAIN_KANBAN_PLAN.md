# NQE-SQL-MAIN Kanban 计划

> 本文档记录 NQE-SQL-MAIN Epic 的看板建设结果与执行规则。当前已完成 NQE-SQL-MAIN-0，并已进入自动监控、按编号逐卡推进模式；设计卡仍不编码，编码卡启动前必须另行完成 scoped 范围、测试和回滚设计。

## 1. 看板建设结果

已创建或复用 44 张任务卡：

```text
NQE-SQL-MAIN-0 ～ NQE-SQL-MAIN-43
```

本轮实际执行卡：

| 卡号 | Kanban ID | 标题 | 状态策略 |
|---|---|---|---|
| NQE-SQL-MAIN-0 | t_9dae3c35 | 只读审计现有四大业务域正式链路 | 本轮 claim、验收、完成 |

后续卡状态策略：

| 范围 | 状态策略 | 原因 |
|---|---|---|
| NQE-SQL-MAIN-1～5 | 按编号逐卡解锁、claim、验收 | 设计阶段，只读不编码 |
| NQE-SQL-MAIN-6～41 | 完成前置设计后逐卡启动 | 编码/实现卡，启动前必须完成 scoped 文件范围、测试命令、回滚说明和 Codex 指令 |
| NQE-SQL-MAIN-42～43 | 等待前序完成 | 下线评估与 Go/No-Go 必须在四域回归后执行 |

## 2. 看板卡清单

| 卡号 | Kanban ID | 标题 |
|---|---|---|
| NQE-SQL-MAIN-0 | t_9dae3c35 | 只读审计现有四大业务域正式链路 |
| NQE-SQL-MAIN-1 | t_f41e1548 | 统一 SQL Agent 主链路设计 |
| NQE-SQL-MAIN-2 | t_1f8731b0 | 统一元数据知识库表设计 |
| NQE-SQL-MAIN-3 | t_95f2eabf | 多路召回机制设计与实现方案 |
| NQE-SQL-MAIN-4 | t_3cf3eb24 | LangGraph SQL Agent 主流程设计 |
| NQE-SQL-MAIN-5 | t_33b49452 | SQL 生成 / validate / correct / execute 安全边界设计 |
| NQE-SQL-MAIN-6 | t_836e6340 | nqe_* 元数据表 Alembic 迁移 |
| NQE-SQL-MAIN-7 | t_c8b38b1a | 元数据同步脚本 |
| NQE-SQL-MAIN-8 | t_cceeff7b | Milvus 元数据向量索引 |
| NQE-SQL-MAIN-9 | t_205f18fc | MySQL value index 字段取值索引 |
| NQE-SQL-MAIN-10 | t_29c2d646 | 统一 SQL Agent Graph 骨架 |
| NQE-SQL-MAIN-11 | t_408809eb | SQL 安全预检与白名单拦截 |
| NQE-SQL-MAIN-12 | t_c26b538b | EXPLAIN validate 与 correct SQL 节点 |
| NQE-SQL-MAIN-13 | t_7b27c00e | trace / query log / replay |
| NQE-SQL-MAIN-14 | t_9c5f1f49 | 物流元数据同步 |
| NQE-SQL-MAIN-15 | t_b280ecb1 | 物流 SQL Agent 接入 |
| NQE-SQL-MAIN-16 | t_5a833e34 | 物流正式链路灰度切换 |
| NQE-SQL-MAIN-17 | t_ed9da504 | 物流 fallback 与 shadow compare |
| NQE-SQL-MAIN-18 | t_eafee70b | 物流评测集回归 |
| NQE-SQL-MAIN-19 | t_7803ad7b | 产销存元数据同步 |
| NQE-SQL-MAIN-20 | t_885e67c6 | 产销存 SQL Agent 接入 |
| NQE-SQL-MAIN-21 | t_c5382680 | 产销存正式链路灰度切换 |
| NQE-SQL-MAIN-22 | t_775fe13e | 产销存 fallback 与回归评测 |
| NQE-SQL-MAIN-23 | t_a19c8d98 | BOM 元数据同步 |
| NQE-SQL-MAIN-24 | t_b996e3ce | BOM SQL Agent 接入 |
| NQE-SQL-MAIN-25 | t_af250a17 | BOM 候选消歧接入 SQL Agent |
| NQE-SQL-MAIN-26 | t_3936118b | BOM compare / replay fallback 策略 |
| NQE-SQL-MAIN-27 | t_9e58cd30 | BOM 正式入口灰度切换 |
| NQE-SQL-MAIN-28 | t_915b0956 | BOM 评测集回归 |
| NQE-SQL-MAIN-29 | t_a6521edf | 功率预测元数据同步 |
| NQE-SQL-MAIN-30 | t_e22064a6 | 功率预测 SQL Agent 接入 |
| NQE-SQL-MAIN-31 | t_8601b211 | PowerPredictionEngine fallback 接入 |
| NQE-SQL-MAIN-32 | t_f1b4fff1 | 功率预测正式入口灰度切换 |
| NQE-SQL-MAIN-33 | t_2bc1a261 | 功率预测评测集回归 |
| NQE-SQL-MAIN-34 | t_bd4ffb2c | 前端 NQE Chat 页面 |
| NQE-SQL-MAIN-35 | t_b45199fb | 流式事件消费器 |
| NQE-SQL-MAIN-36 | t_61eeca50 | SQL Agent 进度时间线组件 |
| NQE-SQL-MAIN-37 | t_d4993b02 | 查询结果表格 / 指标卡 / 图表组件 |
| NQE-SQL-MAIN-38 | t_17160080 | 多候选消歧组件 |
| NQE-SQL-MAIN-39 | t_a572fb1d | quick chips 后端化 |
| NQE-SQL-MAIN-40 | t_a7c49d2f | shadow / assist / on 灰度配置 |
| NQE-SQL-MAIN-41 | t_a1ab4b3c | 运营指标与正确率看板 |
| NQE-SQL-MAIN-42 | t_1f25aee8 | 四域旧链路下线评估报告 |
| NQE-SQL-MAIN-43 | t_e1dc87c1 | 最终 Go / No-Go 评审 |

## 3. 推进规则

用户已授权 NQE-SQL-MAIN 后续按编号自动推进，但仍必须逐卡验收、逐卡 claim，不允许绕过看板生命周期。

推进规则：

1. 当前卡不再运行时，先判断是正常完成还是异常停止。
2. 若出现 stale、blocked、reclaimed、crashed、验收材料不足等异常，必须先修复并重新运行当前卡。
3. 若当前卡正常完成并验收通过，才允许解锁和 claim 下一张编号卡。
4. NQE-SQL-MAIN-1～5 仍是设计卡，不允许编码。
5. NQE-SQL-MAIN-6 及后续编码卡启动前，必须有 scoped 文件范围、测试命令、回滚说明和 Codex 执行说明。

## 4. NQE-SQL-MAIN-0 验收标准

1. 读取主执行指令和主需求报告。
2. 只读查看当前代码和附件参考资料。
3. 只读查看物管状态文件用于冲突判断。
4. 输出 9 份 NQE 设计/状态文档。
5. 创建完整 NQE-SQL-MAIN 看板。
6. 不修改业务代码。
7. 不调用编码代理。
8. 不覆盖物管状态文件。
9. 后续卡按编号逐卡推进，避免并发启动和越过验收。

## 5. 下一步建议

按当前自动推进规则，NQE-SQL-MAIN-0 完成后进入：

```text
NQE-SQL-MAIN-1：统一 SQL Agent 主链路设计
```

NQE-SQL-MAIN-1 仍是设计卡，不允许编码；完成后再进入元数据和安全边界细化。
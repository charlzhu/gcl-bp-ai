# NQE 统一 SQL Agent 主链路架构设计

> 本文档属于 NQE-SQL-MAIN 独立事实源。`docs/CURRENT_STATUS.md`、`docs/NEXT_TASK.md`、`docs/HANDOFF.md` 仅用于并行物管任务冲突判断，不作为本轮 NQE 需求依据，且本轮不覆盖它们。

## 1. 本轮目标

NQE-SQL-MAIN 的长期目标是把当前分散的物流、计划 BOM、功率预测、产销存/经营分析问答链路，逐步统一到一条 **统一 SQL Agent 正式主链路**。

本阶段主流程采用：

```text
用户自然语言问题
→ 统一问数入口
→ 领域识别
→ 关键词提取
→ 多路召回
→ 合并召回上下文
→ 过滤表、字段、指标、取值
→ 添加数据库上下文、日期上下文、业务口径上下文
→ LLM 生成 SQL
→ SQL 安全预检
→ EXPLAIN / validate SQL
→ SQL 错误则 correct SQL
→ 再次 validate
→ 只读执行 SQL
→ 结果表达
→ trace / query log / replay
```

当前阶段明确不把 SQLPlan / ToolPlan 作为第一主路线；它们只作为后续企业级增强、复杂工具 fallback 或高风险场景收敛方向。

## 2. 已审计到的当前能力

| 类别 | 当前仓库能力 | 可复用性 | 当前缺口 |
|---|---|---|---|
| 统一 Graph | 已存在 13 节点统一 Graph 原型，覆盖 receive、domain_route、extract_keywords、三路 recall、merge、filter、add_context、generate_sql、validate_sql、correct_sql、execute_sql、clarify/error | 可作为 NQE Graph 雏形 | 仍有历史非 NQE 命名、注释和接口痕迹；未成为正式入口 |
| 物流问答 | 现有正式入口主要经 `/api/v1/business-qa/stream` 与物流服务链路；物流 NL2SQL/shadow/assist 相关模块和测试已存在 | 最适合作为第一替换域 | 正式链路仍保留旧 planner/service，NQE 未完全主链路化 |
| 计划 BOM | 独立 QA、候选消歧、明细、对比、replay 能力较成熟 | 简单查询可 SQL Agent 化 | 候选消歧、compare/replay 不能直接一次性 SQL 化 |
| 功率预测 | 有确定性 PowerPredictionEngine、推荐服务和计划 BOM 子能力沉淀 | 可由 NQE 统一入口调度 | 预测计算必须保留确定性引擎 fallback，不允许 LLM 直接计算 |
| 产销存/经营分析 | 已有独立产销存 QA endpoint/service | 第二阶段适合替换 | 当前前端和业务问答入口仍与物流/BOM 分流 |
| 前端 | BusinessChatPage 已承载 auto/logistics/plan_bom/business_analysis 等模式，并消费流式事件 | 可复用页面骨架、结果表格、流式体验 | 需要 NQE Chat/统一事件消费器；不能暴露 SQL/字段/表名等内部技术细节 |
| Catalog/召回 | 已有 unified catalog、Milvus 召回、rapidfuzz value 匹配、能力注册 | 可迁移成 nqe_* 元数据知识库与召回服务 | 覆盖度和四域一致性仍需全量审计；当前部分字典/维度表仍硬编码 |

## 3. 目标架构分层

```text
前端层
  NQE Chat 页面 / 领域入口 / 流式事件消费器 / 结果表格 / 指标卡 / 消歧组件

API 层
  /api/v1/nqe/query 或等价统一入口
  统一请求模型、trace_id、domain_hint、灰度模式、SSE/NDJSON 输出

编排层
  NqeSqlAgentGraph
  receive → domain_route → extract_keywords → recall_* → merge/filter → generate/validate/correct/execute → present/log

知识层
  nqe_domain / nqe_table_info / nqe_column_info / nqe_metric_info / nqe_value_info
  nqe_join_info / nqe_example_question / nqe_business_rule / nqe_prompt_version

执行层
  SQL safety precheck
  EXPLAIN validate
  readonly execute with timeout/limit
  fallback service dispatcher

观测层
  nqe_query_trace
  nqe_shadow_compare
  nqe_eval_suite / nqe_eval_case
  replay / shadow / assist / on 灰度统计
```

## 4. 多路召回设计

NQE 召回不应只依赖单一路径。第一版建议保留以下召回：

1. 字段召回：基于用户问题、关键词扩展、Milvus 向量索引。
2. 指标召回：基于指标名称、别名、业务口径、单位、关联字段。
3. 字段取值召回：优先 MySQL value index + rapidfuzz；暂不强制引入 ES。
4. 表召回：基于业务域、字段覆盖、指标关联、表角色。
5. 示例问法召回：基于历史验收问题、标准问法、相似问题。
6. 业务口径召回：按业务域、指标、时间口径、过滤规则召回。

## 5. SQL 执行闭环

```text
generate_sql
  输入：问题、候选表字段、指标口径、取值、日期、业务域上下文
  输出：单条 SQL 文本

precheck_sql_safety
  校验：只读、单语句、白名单表、禁止系统库、禁止危险函数/DDL/DML、LIMIT/超时策略

validate_sql
  执行 EXPLAIN，失败则把安全脱敏后的错误交给 correct_sql

correct_sql
  最多 2 次修正；修正 SQL 仍必须重新 precheck + EXPLAIN

execute_sql_readonly
  只读事务、超时、最大行数、结果摘要、trace 记录
```

## 6. 与旧链路的关系

统一 SQL Agent 不是一次性删除旧链路，而是逐域替换：

1. shadow：新链路生成 SQL 和结果，但用户仍看旧链路答案。
2. assist：新链路参与理解/召回/候选生成，旧链路仍负责最终答案或 fallback。
3. on：该域正式入口优先 NQE；旧链路作为失败回退。
4. off：完全关闭 NQE，回到旧链路。

所有域必须独立配置开关，不允许一次性替换四域。

## 7. 附件参考资料吸收口径

附件中的外部参考教程和源码仅用于学习技术流程，禁止在 NQE 代码、文档、接口、注释、提交信息、前端文案中暴露来源命名。

可吸收：

1. LangGraph 风格的分步编排。
2. SSE/NDJSON 流式进度与结果事件。
3. 多路召回后生成 SQL 的流程。
4. EXPLAIN 失败后修正 SQL 的闭环。
5. 元数据实体抽象和 prompt 组织方式。

不照搬：

1. 外部项目名称、目录、类名、接口路径、前端标题。
2. 外部示例凭证或部署参数。
3. 其他非当前第一阶段必要的外部技术栈。
4. 与 gcl-bp-ai 四域业务口径不一致的表结构和样例。

## 8. 当前架构结论

1. 当前仓库已有 NQE 所需的部分 Graph/召回/SQL 生成原型，但还不是正式可上线主链路。
2. 最大瓶颈不是“没有 Graph”，而是：正式入口未统一、SQL 安全预检不足、元数据覆盖不足、四域 fallback/灰度/回归未闭环、存在历史非 NQE 命名痕迹。
3. NQE-SQL-MAIN-1 已进一步输出 `docs/NQE_SQL_MAIN_1_MAIN_LINK_DESIGN.md`，明确目标主链路节点、API/前端契约、SQL 安全预检位置、四域灰度接入和 trace/replay/shadow compare 边界。
4. 下一步应进入 NQE-SQL-MAIN-2，细化 nqe_* 统一元数据知识库表设计；在 NQE-SQL-MAIN-1～5 完成前，不应直接启动编码卡。

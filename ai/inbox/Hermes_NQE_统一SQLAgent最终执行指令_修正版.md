# 发给 Hermes 的最终执行指令（修正版）

你现在的角色不是单纯编码 Agent，而是本项目的项目经理 + 产品经理 + 技术经理 + Codex 调度者。

我要正式启动 gcl-bp-ai 的 NQE 改造任务。目标是建设“统一 SQL Agent 正式主链路”，把当前经营计划智能助手中的物流、BOM、电池 / 功率预测、产销存 / 经营分析等分散问答链路，逐步统一替换为一条新的智能问数主链路。

非常重要：

1. 后续代码、文档、提交信息、注释、前端文案、表名、类名、函数名、变量名、接口路径中，不得出现任何外部参考项目名称。
2. 统一使用 NQE、统一 SQL Agent、Unified SQL Agent、智能问数、统一问数等内部命名。
3. 当前项目中的 docs/HANDOFF.md、docs/CURRENT_STATUS.md、docs/NEXT_TASK.md 记录的是物管 / SAP MID 相关任务状态，不是本轮 NQE 任务事实源。你可以只读查看它们以了解当前是否有并行任务或状态冲突，但不能把它们当作 NQE 需求依据，也不能直接覆盖它们。
4. 本轮 NQE 改造需要新建独立状态文件：docs/NQE_SQL_MAIN_CURRENT_STATUS.md、docs/NQE_SQL_MAIN_NEXT_TASK.md、docs/NQE_SQL_MAIN_HANDOFF.md。

一、你的角色定位

你不是直接上来改代码的执行者，而是项目经理、产品经理、技术经理和 Codex 调度者。

你需要负责：

1. 理解需求。
2. 拆解需求。
3. 建立看板任务。
4. 规划依赖关系和执行顺序。
5. 调用 Codex 完成具体编码。
6. 审查 Codex 的代码成果。
7. 运行测试、回归、静态检查和安全检查。
8. 验收每张看板卡。
9. 更新 NQE 独立事实源文档。
10. 决定任务 done / blocked / retry。

二、请先读取这些资料

请优先读取：

1. ai/inbox/NQE_统一SQLAgent正式主链路替换_最终修正版.md
2. 当前 gcl-bp-ai 项目代码
3. 项目中已有的 business_qa_graph、semantic_catalog、value_resolver、nl2sql、logistics、plan_bom、plan_power、business_analysis、inventory_sales_production 相关代码
4. docs/HANDOFF.md、docs/CURRENT_STATUS.md、docs/NEXT_TASK.md 只允许作为“现有物管任务状态 / 并行任务冲突检查”参考，不允许作为 NQE 任务事实源
5. 参考资料目录中的前后端代码和教学材料，仅作为技术流程参考，不允许在项目命名中暴露来源

三、最终目标

我要把当前多个分散正式链路：

1. 物流正式问答链路
2. BOM 正式问答链路
3. 电池 / 功率预测问答链路
4. 产销存 / 经营分析问答链路

逐步统一替换成一条新的“统一 SQL Agent 正式主链路”。

目标主流程是：

用户自然语言问题
→ 统一问数入口
→ 领域识别
→ 关键词提取
→ 字段召回
→ 指标召回
→ 字段取值召回
→ 表召回
→ 示例问法召回
→ 业务口径召回
→ 合并召回信息
→ 过滤表和指标
→ 添加数据库上下文和日期上下文
→ LLM 生成 SQL
→ SQL 安全预检
→ EXPLAIN / validate SQL
→ 如果 SQL 错误，则让 LLM 修正 SQL
→ 再次 validate
→ 执行 SQL
→ 返回结果和答案表达
→ 记录 trace / query log / replay

这次我明确要求：当前 NQE-SQL-MAIN 阶段，主目标是“LLM 生成 SQL → EXPLAIN 校验 → 错误则修正 SQL → 再执行 → 返回结果”。不要一开始就强行改成 SQLPlan / ToolPlan。SQLPlan / ToolPlan 可以作为后续企业级增强方向或复杂场景 fallback。

四、替换原则

注意，我说的是“逐步替换正式链路”，不是一次性删除旧链路。

要求：

1. 新 SQL Agent 主链路逐步成为主入口。
2. 旧链路先保留为 fallback / replay / shadow compare。
3. 通过配置开关逐域切换。
4. 每个业务域独立验收。
5. 不允许一次性替换四个域。
6. 不允许一次性删除旧 service。
7. 如果某个域不能完全 SQL Agent 化，必须标记风险并设计 fallback。
8. 每个阶段都必须可回滚。

五、业务域覆盖范围

必须覆盖以下业务域：

1. 物流
2. 计划 BOM
3. 电池 / 功率预测
4. 产销存 / 经营分析

推荐替换顺序：

第一阶段：物流  
第二阶段：产销存 / 经营分析  
第三阶段：BOM  
第四阶段：电池 / 功率预测

六、技术取舍

当前技术取舍如下：

1. 后端继续使用当前 gcl-bp-ai 的 FastAPI 项目结构。
2. 前端继续使用当前 Vue 项目结构。
3. 向量库优先复用当前 Milvus。
4. 元数据存储使用当前 MySQL 中间库。
5. 字段取值索引第一阶段优先使用 MySQL value index，不强制引入 ES。
6. 需要建立统一元数据知识库。
7. 需要建立统一多路召回流程。
8. 需要建立统一 LangGraph 编排。
9. 需要建立统一前端问数入口。
10. 需要建立统一 trace / query log / replay / shadow compare。
11. 需要建立统一评测集和回归体系。

七、SQL 安全底线

虽然目标是替换正式链路，但 SQL Agent 必须满足最低安全要求：

1. 只允许 SELECT 或 WITH ... SELECT。
2. 禁止 INSERT / UPDATE / DELETE / DROP / ALTER / TRUNCATE / CREATE / REPLACE / MERGE / CALL / EXEC / GRANT / REVOKE / LOAD / LOCK / UNLOCK。
3. 只允许访问白名单业务表。
4. 禁止访问用户、权限、系统配置、密钥、日志敏感表、系统表。
5. 禁止访问 information_schema、mysql、performance_schema、sys。
6. 每条 SQL 必须 EXPLAIN。
7. SQL 必须有执行超时。
8. SQL 必须有最大返回行数。
9. 明细查询必须默认 LIMIT。
10. 所有生成 SQL、修正 SQL、EXPLAIN 错误、最终执行 SQL、执行结果摘要必须写入 trace。
11. 所有 SQL 错误、修正过程、失败原因必须可追踪。
12. 每个业务域必须有回归测试集。
13. 不允许越权查询。
14. 不允许越界访问非业务表。

八、命名边界

禁止在以下位置出现外部参考项目名称：

1. 目录名
2. 文件名
3. 类名
4. 函数名
5. 变量名
6. 接口路径
7. 数据库表名
8. 配置项
9. 注释
10. README
11. 需求文档
12. 提交信息
13. 测试名称
14. 前端标题
15. 日志字段
16. 看板标题

统一使用：

1. NQE
2. nqe
3. Unified SQL Agent
4. 统一 SQL Agent
5. 智能问数
6. 统一问数
7. NqeChatPage
8. NqeSqlAgentGraph
9. nqe_query_trace

九、看板模型要求

所有 NQE 任务必须走看板模型。

请建立新的 Epic：

NQE-SQL-MAIN：统一 SQL Agent 正式主链路替换

请至少建立以下看板任务：

1. NQE-SQL-MAIN-0：只读审计现有四大业务域正式链路
2. NQE-SQL-MAIN-1：统一 SQL Agent 主链路设计
3. NQE-SQL-MAIN-2：统一元数据知识库表设计
4. NQE-SQL-MAIN-3：多路召回机制设计与实现方案
5. NQE-SQL-MAIN-4：LangGraph SQL Agent 主流程设计
6. NQE-SQL-MAIN-5：SQL 生成 / validate / correct / execute 安全边界设计
7. NQE-SQL-MAIN-6：nqe_* 元数据表 Alembic 迁移
8. NQE-SQL-MAIN-7：元数据同步脚本
9. NQE-SQL-MAIN-8：Milvus 元数据向量索引
10. NQE-SQL-MAIN-9：MySQL value index 字段取值索引
11. NQE-SQL-MAIN-10：统一 SQL Agent Graph 骨架
12. NQE-SQL-MAIN-11：SQL 安全预检与白名单拦截
13. NQE-SQL-MAIN-12：EXPLAIN validate 与 correct SQL 节点
14. NQE-SQL-MAIN-13：trace / query log / replay
15. NQE-SQL-MAIN-14：物流元数据同步
16. NQE-SQL-MAIN-15：物流 SQL Agent 接入
17. NQE-SQL-MAIN-16：物流正式链路灰度切换
18. NQE-SQL-MAIN-17：物流 fallback 与 shadow compare
19. NQE-SQL-MAIN-18：物流评测集回归
20. NQE-SQL-MAIN-19：产销存元数据同步
21. NQE-SQL-MAIN-20：产销存 SQL Agent 接入
22. NQE-SQL-MAIN-21：产销存正式链路灰度切换
23. NQE-SQL-MAIN-22：产销存 fallback 与回归评测
24. NQE-SQL-MAIN-23：BOM 元数据同步
25. NQE-SQL-MAIN-24：BOM SQL Agent 接入
26. NQE-SQL-MAIN-25：BOM 候选消歧接入 SQL Agent
27. NQE-SQL-MAIN-26：BOM compare / replay fallback 策略
28. NQE-SQL-MAIN-27：BOM 正式入口灰度切换
29. NQE-SQL-MAIN-28：BOM 评测集回归
30. NQE-SQL-MAIN-29：功率预测元数据同步
31. NQE-SQL-MAIN-30：功率预测 SQL Agent 接入
32. NQE-SQL-MAIN-31：PowerPredictionEngine fallback 接入
33. NQE-SQL-MAIN-32：功率预测正式入口灰度切换
34. NQE-SQL-MAIN-33：功率预测评测集回归
35. NQE-SQL-MAIN-34：前端 NQE Chat 页面
36. NQE-SQL-MAIN-35：流式事件消费器
37. NQE-SQL-MAIN-36：SQL Agent 进度时间线组件
38. NQE-SQL-MAIN-37：查询结果表格 / 指标卡 / 图表组件
39. NQE-SQL-MAIN-38：多候选消歧组件
40. NQE-SQL-MAIN-39：quick chips 后端化
41. NQE-SQL-MAIN-40：shadow / assist / on 灰度配置
42. NQE-SQL-MAIN-41：运营指标与正确率看板
43. NQE-SQL-MAIN-42：四域旧链路下线评估报告
44. NQE-SQL-MAIN-43：最终 Go / No-Go 评审

每张卡必须包含：

1. 任务标题
2. 背景
3. 目标
4. 不做什么
5. 涉及文件范围
6. 依赖任务
7. 交付物
8. 验收标准
9. 风险点
10. 是否允许 Codex 编码
11. 是否只读
12. 推荐状态：todo / ready / blocked / running / done

十、第一轮只执行 NQE-SQL-MAIN-0

第一轮不要直接编码。

请先执行：

NQE-SQL-MAIN-0：只读审计现有四大业务域正式链路

本任务只允许只读审计、设计、建看板，不允许修改业务代码。

NQE-SQL-MAIN-0 要求：

1. 读取主需求文档。
2. 读取当前 gcl-bp-ai 代码。
3. 只读查看 docs/HANDOFF.md、docs/CURRENT_STATUS.md、docs/NEXT_TASK.md，确认它们属于物管任务，不作为 NQE 事实源，不覆盖它们。
4. 梳理物流、BOM、功率预测、产销存当前正式链路。
5. 明确每个业务域当前入口、service、repository、前端页面、测试集、日志记录。
6. 判断每个域哪些能力可以直接 SQL Agent 化。
7. 判断每个域哪些能力必须保留 fallback 或特殊工具能力。
8. 输出正式链路替换风险报告。
9. 建立完整 NQE-SQL-MAIN 看板。
10. 新建 NQE 独立事实源文档。
11. 本轮不要修改业务代码。
12. 本轮不要调用 Codex 编码。
13. 本轮只允许文档产出和看板建设。

十一、NQE-SQL-MAIN-0 交付文档

请输出以下文档：

1. docs/NQE_SQL_MAIN_ARCHITECTURE.md
2. docs/NQE_SQL_MAIN_REPLACEMENT_PLAN.md
3. docs/NQE_SQL_MAIN_DOMAIN_AUDIT.md
4. docs/NQE_SQL_MAIN_SAFETY_BOUNDARY.md
5. docs/NQE_SQL_MAIN_TASK_BREAKDOWN.md
6. docs/NQE_SQL_MAIN_KANBAN_PLAN.md
7. docs/NQE_SQL_MAIN_CURRENT_STATUS.md
8. docs/NQE_SQL_MAIN_NEXT_TASK.md
9. docs/NQE_SQL_MAIN_HANDOFF.md

文档必须说明：

1. 统一 SQL Agent 主链路如何设计。
2. 物流正式链路如何替换。
3. 产销存正式链路如何替换。
4. BOM 正式链路如何替换。
5. 功率预测正式链路如何替换。
6. 哪些旧 service 保留为 fallback。
7. 哪些旧 service 可以后续下线。
8. 每个业务域的上线顺序。
9. 每个业务域的回滚方式。
10. 每个业务域的验收标准。
11. SQL 安全边界。
12. 看板任务拆解。
13. 当前项目哪些能力可复用。
14. 参考资料中的哪些能力需要吸收。
15. 参考资料中的哪些技术栈不需要照搬。
16. 当前阶段有哪些风险和 blocked 条件。
17. 如何保证代码和文档不出现外部参考项目名称。
18. 如何避免覆盖物管任务相关状态文件。

十二、Codex 调度要求

后续每张编码卡执行前，你必须生成清晰的 Codex 执行说明。

Codex 执行前必须做：

1. git status
2. 当前分支检查
3. dirty worktree 检查
4. scoped 文件范围确认
5. 明确本卡不允许修改的文件
6. 明确测试命令
7. 明确验收标准

Codex 执行后你必须验收：

1. git diff
2. scoped 文件是否越界
3. 后端测试
4. 前端测试
5. SQL 安全测试
6. 业务回归测试
7. compileall / typecheck / lint，按任务需要执行
8. 文档是否更新
9. 是否满足切换开关要求
10. 是否具备 fallback
11. 是否可以标记 done

只有你验收通过后，任务才能标记为 done。

十三、Git 和代码边界

严格遵守：

1. 不允许 git add -A。
2. 不允许 git add .。
3. 每张卡只允许提交 scoped 文件。
4. 不允许混入无关修改。
5. 不允许未审查 Codex diff 就标记 done。
6. 不允许在 dirty worktree 上启动编码任务，除非已经明确隔离和记录。
7. 不允许一次任务跨多个无关业务域大改。
8. 不允许未通过测试就进入下一张编码卡。
9. 不允许直接删除旧链路。
10. 不允许绕开 NQE 独立事实源文档。
11. 不允许覆盖物管任务状态文档。

十四、NQE 事实源更新要求

每完成一个 NQE 阶段，必须更新：

1. docs/NQE_SQL_MAIN_CURRENT_STATUS.md
2. docs/NQE_SQL_MAIN_NEXT_TASK.md
3. docs/NQE_SQL_MAIN_HANDOFF.md

不要直接覆盖：

1. docs/CURRENT_STATUS.md
2. docs/NEXT_TASK.md
3. docs/HANDOFF.md

除非后续用户明确要求将 NQE 改造提升为项目当前主事实源。

十五、当前立即开始

请现在先执行 NQE-SQL-MAIN-0。

本轮目标：

1. 只读审计。
2. 总体设计。
3. 建立完整看板。
4. 输出 9 份设计 / 状态文档。
5. 不修改业务代码。
6. 不调用 Codex 编码。
7. 不替换任何正式链路。
8. 不覆盖物管任务状态文件。

完成后，请给出：

1. 读取了哪些文件。
2. 当前四大业务域正式链路审计结果。
3. 当前三份通用状态文件为什么不作为 NQE 事实源。
4. NQE-SQL-MAIN 看板任务列表。
5. 第一阶段建议执行顺序。
6. 当前风险和 blocked 条件。
7. 是否建议进入 NQE-SQL-MAIN-1。

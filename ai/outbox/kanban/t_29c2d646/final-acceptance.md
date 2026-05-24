# NQE-SQL-MAIN-10 最终验收材料

## 1. 修改文件清单

1. `backend/app/domains/business_qa_graph/nqe_sql_agent_state.py`
2. `backend/app/domains/business_qa_graph/nqe_sql_agent_graph.py`
3. `tests/unit/business_qa_graph/test_nqe_sql_agent_graph_skeleton.py`
4. `ai/outbox/kanban/t_29c2d646/test.log`
5. `ai/outbox/kanban/t_29c2d646/diff.patch`
6. `ai/outbox/kanban/t_29c2d646/final-acceptance.md`

## 2. 关键设计说明

1. 新增独立 `NqeSqlAgentState`，覆盖请求上下文、运行模式、领域、理解、召回、内部查询生命周期、执行占位和输出终态字段。
2. 新增 `NQE_SQL_AGENT_NODE_SEQUENCE`，声明 19 个设计节点，顺序与本卡要求一致。
3. 新增 `build_nqe_sql_agent_graph()`，只构建独立骨架，不导入正式 API、runner、服务入口，不修改 `builder_v2.py`。
4. 显式建模灰度模式：
   - `off`：进入 `legacy_fallback`，不进入内部查询生成、预检、解释校验或执行占位。
   - `shadow` / `assist` / `on`：进入 NQE 骨架链路。
5. 显式建模内部查询生命周期：
   - `generate_sql_direct`
   - `precheck_sql_safety`
   - `explain_validate_sql`
   - `correct_sql`
   - 回到 `precheck_sql_safety`
   - 最多 2 轮修正。
6. 显式建模终态：
   - `clarify`
   - `safety_reject`
   - `error`
   - `legacy_fallback`
   - `completed`
7. 所有终态均进入 `record_query_log_and_trace` 后再结束。
8. 用户可见回答均为业务化文本，不包含内部实现细节。

## 3. 测试结果

已执行：

```bash
/opt/anaconda3/bin/python3 -m pytest tests/unit/business_qa_graph/test_nqe_sql_agent_graph_skeleton.py tests/unit/business_qa_graph/test_business_qa_graph_skeleton.py -q
/opt/anaconda3/bin/python3 -m py_compile backend/app/domains/business_qa_graph/nqe_sql_agent_state.py backend/app/domains/business_qa_graph/nqe_sql_agent_graph.py tests/unit/business_qa_graph/test_nqe_sql_agent_graph_skeleton.py
git diff --check
```

结果：

1. `24 passed, 7 warnings`
2. `py_compile` 通过
3. `git diff --check` 通过

完整输出见：`ai/outbox/kanban/t_29c2d646/test.log`

## 4. 安全扫描

已对本卡新增代码和测试做 scoped 扫描：

1. 未发现真实凭证、连接串或绝对本机路径。
2. 未连接数据库，未读取 `.env`。
3. 未调用真实模型。
4. 未修改前端。
5. 未修改正式 API、runner、builder_v2 或现有正式节点。

说明：代码和测试中存在内部字段名、节点名和屏蔽词常量，这是本卡骨架与测试要求的一部分；用户可见输出已通过测试验证不包含这些词。

## 5. 风险点

1. 本卡指定的 `docs/NQE_SQL_MAIN_4_GRAPH_FLOW_DESIGN.md` 与 `docs/NQE_SQL_MAIN_5_SQL_SAFETY_DESIGN.md` 在当前 worktree 不存在；实现依据为用户本轮 scoped 指令和现有允许读取代码/测试。
2. `generate_sql_direct`、`precheck_sql_safety`、`explain_validate_sql`、`execute_sql_readonly` 均为确定性占位，不代表真实安全预检、真实解释校验或真实执行能力。
3. 当前未接入正式入口，需后续卡片再决定 shadow/assist/on 如何与现有问答链路集成。

## 6. 未做事项

1. 未实现完整安全解析。
2. 未实现真实解释校验。
3. 未实现真实只读执行。
4. 未写入任何查询日志表。
5. 未接入正式 API。
6. 未修改前端。

## 7. 影响范围确认

1. 不影响现有物流问答主链路。
2. 不影响计划 BOM 问答、导入、查询、QA、消歧和对比能力。
3. 不影响计划 BOM 功率预测相关能力。
4. 遵守本轮阶段边界：只新增 NQE SQL Agent Graph 独立骨架与测试。
5. 未自动 commit、push、deploy。

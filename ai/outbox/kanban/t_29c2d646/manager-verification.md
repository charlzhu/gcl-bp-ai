# NQE-SQL-MAIN-10 Hermes 经理验收记录

## 1. 看板状态说明

本卡曾在 run 106 中被手动 claim，但未及时启动 side-channel Codex worker，导致看板锁过期后自动 reclaimed，并回到 ready。

本轮已按 stale-ready 恢复流程重新处理：

1. 读取 `hermes kanban show t_29c2d646 --json`，确认 run 106 为 `reclaimed`，原因是 `stale_lock`，不是功能失败。
2. 检查当时无 NQE-10 代码、测试或 outbox 产物。
3. 重新 claim 本卡，生成 run 107。
4. 立即启动 Codex side-channel worker 执行 `tmp/hermes/nqe10_preflight/codex_prompt.md`。
5. Codex 进程 `proc_6cfee2af0dcd` 正常退出，exit code 为 0。

## 2. Codex 交付物核验

本卡新增产物：

1. `backend/app/domains/business_qa_graph/nqe_sql_agent_state.py`
2. `backend/app/domains/business_qa_graph/nqe_sql_agent_graph.py`
3. `tests/unit/business_qa_graph/test_nqe_sql_agent_graph_skeleton.py`
4. `ai/outbox/kanban/t_29c2d646/final-acceptance.md`
5. `ai/outbox/kanban/t_29c2d646/test.log`
6. `ai/outbox/kanban/t_29c2d646/diff.patch`

实现范围符合 NQE-SQL-MAIN-10：只新增独立统一 SQL Agent Graph 骨架，不接入正式业务问答入口，不修改前端，不连接数据库，不调用真实 LLM。

## 3. Hermes 独立验收命令与结果

工作目录：`.worktrees/nqe-sql-main-6-metadata-migrations`

已执行：

```bash
/opt/anaconda3/bin/python3 -m pytest tests/unit/business_qa_graph/test_nqe_sql_agent_graph_skeleton.py tests/unit/business_qa_graph/test_business_qa_graph_skeleton.py -q
/opt/anaconda3/bin/python3 -m py_compile backend/app/domains/business_qa_graph/nqe_sql_agent_state.py backend/app/domains/business_qa_graph/nqe_sql_agent_graph.py tests/unit/business_qa_graph/test_nqe_sql_agent_graph_skeleton.py
git diff --check
```

结果：

1. focused tests：`24 passed, 7 warnings in 1.45s`
2. `py_compile`：通过，无输出。
3. `git diff --check`：通过，无输出。

## 4. 架构审查结论

已人工审查核心实现：

1. `build_nqe_sql_agent_graph()` 是独立 builder，没有导入正式 API、runner 或现有正式入口。
2. `NQE_SQL_AGENT_NODE_SEQUENCE` 声明 19 个节点，覆盖接收、模式初始化、领域能力、归一化、召回、上下文检查、内部查询生命周期、终态和记录节点。
3. 灰度模式显式建模：`off`、`shadow`、`assist`、`on`。
4. `off` 模式进入 `legacy_fallback`，不会进入内部查询生成、预检、解释校验或执行占位。
5. 内部查询生命周期顺序为 `generate_sql_direct` → `precheck_sql_safety` → `explain_validate_sql` → `correct_sql` → 回到 `precheck_sql_safety`。
6. 修正循环最多 2 轮，超过后进入 `error` 终态。
7. 终态覆盖 `clarify`、`safety_reject`、`error`、`legacy_fallback`、`completed`。
8. 所有终态均先经过 `record_query_log_and_trace` 再结束。
9. 用户可见回答为业务化文本，测试覆盖不暴露内部技术词。

## 5. 安全与边界扫描

已对本卡新增代码、测试和 outbox 做 scoped 扫描：

1. 禁用外部参考命名：0 命中。
2. 凭证关键词：0 命中。
3. 本机绝对路径：0 命中。
4. 未修改 `frontend/`。
5. 未修改 `builder_v2.py`、正式 API、runner、现有正式 nodes 或 prompt。
6. 未修改 `docs/HANDOFF.md`、`docs/CURRENT_STATUS.md`、`docs/NEXT_TASK.md` 等物管/SAP MID 状态文件。
7. 未读取 `.env`，未连接数据库，未 commit/push/deploy。

说明：通用字段名 `user_visible_response`、`user_context` 属于代码状态字段，不是凭证或外部项目命名。

## 6. 结论

NQE-SQL-MAIN-10 验收通过，可以完成看板卡。

本卡只完成统一 SQL Agent Graph 独立骨架，不代表正式主链路已切流；后续卡片仍需继续完成真实安全预检、解释校验、只读执行、shadow/assist/on 接入与逐域灰度验收。

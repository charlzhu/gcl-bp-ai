# t_408809eb / NQE-SQL-MAIN-11 最终验收

## 1. 本轮阻塞根因

本卡阻塞由两个问题叠加造成：

1. 看板卡 `workspace_path` 原先指向父 checkout：
   `/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai`。
   NQE-6 之后实际 stacked worktree 是：
   `/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/nqe-sql-main-6-metadata-migrations`。
   因此 dispatcher 多次在错误目录启动 worker，形成 wrong-cwd 阻塞。
2. SQL 安全预检仍存在两个真实绕过点：
   - 嵌套子查询中的逗号连接非白名单对象未被抽取。
   - `dblink_connect`、`dblink_get_result`、`dblink_disconnect` 等 `dblink_*` 同族危险函数未被拦截。

## 2. 恢复动作

1. 暂停 NQE watchdog，避免自动巡检继续抢跑。
2. reclaim 并终止错误目录 worker。
3. 备份 Kanban DB：备份路径记录在 `tmp/hermes/nqe11_recovery/kanban_db_backup_path.txt`。
4. 修正 `t_408809eb` 的 `workspace_path` 为当前 NQE stacked worktree。
5. 在 `feature/nqe-sql-main-11-sql-safety-precheck` 分支内完成 scoped 修复。

## 3. 修改文件清单

1. `backend/app/domains/business_qa_graph/nqe_sql_safety.py`
2. `tests/unit/business_qa_graph/test_nqe_sql_agent_safety_precheck.py`
3. `ai/outbox/kanban/t_408809eb/test.log`
4. `ai/outbox/kanban/t_408809eb/diff.patch`
5. `ai/outbox/kanban/t_408809eb/static-scan.log`
6. `ai/outbox/kanban/t_408809eb/final-acceptance.md`

## 4. 关键修复说明

1. 安全预检现在扫描候选文本中的所有 `FROM` 片段，覆盖嵌套子查询里的逗号连接对象，避免只校验外层 `FROM`。
2. 对无法可靠解析的复杂逗号片段仍保持 fail-closed。
3. `dblink` 扩展函数族现在按 `dblink_*()` 前缀统一识别为危险表达式。
4. 增加回归测试覆盖：
   - 嵌套子查询逗号连接非白名单表必须拒绝。
   - `dblink_connect` / `dblink_get_result` / `dblink_disconnect` 必须拒绝。

## 5. Hermes 独立验收结果

已执行：

```bash
PYTHONPATH=. /opt/anaconda3/bin/python3 -m pytest tests/unit/business_qa_graph/test_nqe_sql_agent_safety_precheck.py -q
PYTHONPATH=. /opt/anaconda3/bin/python3 -m pytest tests/unit/business_qa_graph/test_nqe_sql_agent_graph_skeleton.py tests/unit/business_qa_graph/test_business_qa_graph_skeleton.py tests/unit/business_qa_graph/test_nqe_sql_agent_safety_precheck.py -q
PYTHONPATH=. /opt/anaconda3/bin/python3 -m py_compile backend/app/domains/business_qa_graph/nqe_sql_safety.py backend/app/domains/business_qa_graph/nqe_sql_agent_graph.py backend/app/domains/business_qa_graph/nqe_sql_agent_state.py tests/unit/business_qa_graph/test_nqe_sql_agent_safety_precheck.py
git diff --check
```

结果：

- SQL 安全 focused tests：`15 passed, 7 warnings`
- graph + safety focused tests：`39 passed, 7 warnings`
- `py_compile`：通过
- `git diff --check`：通过
- blocker 探针：全部转为 reject
- scoped 禁用命名 / 凭证 / 绝对用户路径扫描：`issue_count=0`

## 6. blocker 探针结论

以下历史绕过点均已拒绝：

1. 嵌套子查询逗号连接非白名单对象：reject。
2. `dblink_connect`：reject。
3. `dblink_get_result`：reject。
4. `dblink_disconnect`：reject。
5. 跨 schema basename 绕过：reject。
6. 顶层逗号连接非白名单对象：reject。

## 7. 边界确认

未执行：

- 未读取 `.env`。
- 未连接真实数据库。
- 未 commit。
- 未 push。
- 未 deploy。
- 未启动下一张 NQE 卡。

未修改：

- `frontend/`
- `docs/HANDOFF.md`
- `docs/CURRENT_STATUS.md`
- `docs/NEXT_TASK.md`
- 物管 / SAP MID 状态文件

## 8. 仍需后续任务处理

本卡只完成 NQE-11 的 SQL 安全预检与白名单拦截，不替代后续 EXPLAIN/执行前校验、真实只读库权限控制、正式入口替换或灰度放量。
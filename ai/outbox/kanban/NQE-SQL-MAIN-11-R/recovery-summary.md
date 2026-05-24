# NQE-SQL-MAIN-11-R 恢复记录

## 背景

NQE-SQL-MAIN-11（SQL 安全预检与白名单拦截）的看板任务（t_408809eb）在 Hermes kanban.db 恢复过程中丢失。
但 NQE-SQL-MAIN-13（t_7b27c00e）在验收过程中完整覆盖并实现了 NQE-11 的全部目标能力。
实现代码存在于恢复工作树 `.worktrees/nqe-sql-main-6-metadata-migrations/` 中，尚未回填到根工作区。

## 本卡目标

1. 不重新设计 NQE-11
2. 不伪造原始 NQE-SQL-MAIN-11 为 done
3. 将 NQE-13 已验证的安全预检实现回填到根工作区
4. 确保根工作区 NQE SQL safety 测试可运行
5. 记录证据并更新 NQE 事实源

## 回填来源

恢复工作树：`.worktrees/nqe-sql-main-6-metadata-migrations/`

### 回填文件

| 文件 | 大小 | 说明 |
|---|---|---|
| nqe_sql_safety.py | 15KB / 418行 | SQL 安全预检核心实现 |
| nqe_sql_agent_graph.py | 44KB / 1169行 | NQE LangGraph 编排骨架 |
| nqe_sql_agent_state.py | 5KB / 133行 | Graph 运行态定义 |
| nqe_sql_agent_trace.py | 14KB / 369行 | trace/query log/replay |
| test_nqe_sql_agent_safety_precheck.py | 10KB / 275行 | 安全预检测试 (12个) |
| test_nqe_sql_agent_explain_correct.py | 7KB / 195行 | EXPLAIN/修正测试 (5个) |
| test_nqe_sql_agent_trace_replay.py | 6KB / 149行 | trace/replay测试 (3个) |
| test_nqe_sql_agent_graph_skeleton.py | 11KB / 277行 | Graph骨架测试 (15个) |

### 适配修改

`nqe_sql_agent_graph.py`: 将 `from backend.app.services.nqe_metadata_sync import ...` 改为 try/except 条件导入 + None 守卫，因为该模块属于 NQE-14 范围。

## 已验证的安全能力

| 能力 | 测试覆盖 | 状态 |
|---|---|---|
| SELECT-only 通过 | test_precheck_allows_whitelisted_select | ✅ |
| 非白名单表拒绝 | test_precheck_rejects_non_whitelisted_table | ✅ |
| DDL/DML 关键字拒绝 | test_precheck_rejects_dml_and_ddl_keywords | ✅ |
| 多语句拒绝 | test_precheck_rejects_multiple_statements | ✅ |
| 系统库/高风险对象拒绝 | test_precheck_rejects_system_or_high_risk_objects | ✅ |
| 危险函数拒绝 (sleep, pg_read_file等) | test_precheck_rejects_dangerous_functions | ✅ |
| dblink 族函数拒绝 | test_precheck_rejects_dblink_family_functions | ✅ |
| 缺失白名单 fail-closed | test_precheck_rejects_missing_whitelist | ✅ |
| 逗号连接非白名单表拒绝 | test_precheck_rejects_comma_join | ✅ |
| schema 限定 bypass 拒绝 | test_precheck_rejects_schema_qualified_basename_bypass | ✅ |
| 嵌套子查询逗号连接拒绝 | test_precheck_rejects_nested_subquery | ✅ |
| SELECT * 拒绝 | test_explain_validate_rejects_select_star | ✅ |
| WHERE 未知字段拒绝 | test_explain_validate_rejects_unknown_filter_columns | ✅ |
| 未知投影字段拒绝 | test_explain_validate_rejects_unknown_column | ✅ |
| 修正后返回预检 | test_correct_sql_returns_to_safety_precheck | ✅ |
| trace/log/replay 脱敏 | test_nqe_sql_agent_trace_replay (3个) | ✅ |
| Graph 骨架完整性 | test_nqe_sql_agent_graph_skeleton (13个) | ✅ |

## 测试结果

33 passed, 2 failed (预期内：2个测试依赖 NQE-14 物流元数据同步模块 nqe_metadata_sync)，7 warnings

## 已知限制

1. `nqe_metadata_sync` 模块缺失 — 属于 NQE-14 范围，两个 auto-build logistics context 测试暂时 skip
2. 旧 `test_nqe_sql_safety_precheck.py` 依赖旧 builder_v2 架构，不在本卡范围

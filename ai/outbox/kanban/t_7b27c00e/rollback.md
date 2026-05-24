# NQE-SQL-MAIN-13 rollback

回滚范围：仅回滚本卡 scoped 文件中的 trace/query log/replay 与 explain 校验改动。

建议步骤：
1. 不回滚其它 NQE 卡或物管/SAP MID 状态文件。
2. 若需回滚本卡，应用 ai/outbox/kanban/t_7b27c00e/diff.patch 的反向补丁，或在独立 review 后删除本卡新增的 NQE agent trace/replay 测试与实现。
3. 回滚后重新运行 py_compile 与 focused pytest，确认旧链路 fallback 不受影响。
4. 禁止通过删除安全预检模块绕过 import；若 nqe_sql_safety.py 已被后续卡依赖，应保留并只回滚本卡字段解释/trace replay 相关改动。

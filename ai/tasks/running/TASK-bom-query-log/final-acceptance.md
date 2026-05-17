# TASK-bom-query-log 最终验收报告

## 任务

修复 `sys_query_log` 只记录物流问答、计划 BOM 问答未入表的问题。

## 根因

- 物流问答链路已有统一查询历史写入路径，会把问答快照写入 `sys_query_log`。
- 计划 BOM QA 只有确定性问答响应与 trace/presentation 组装，正常成功/澄清返回没有调用统一查询历史写入；API 异常路径也没有兜底写错误日志。
- 因此业务在 `sys_query_log` 里只能看到物流问题，BOM 相关问题丢失。

## 修改文件

1. `backend/app/domains/plan_bom/services/qa_service.py`
   - 为 `PlanBomQaService` 注入/复用 `LogisticsQueryRepository` 写入同一张 `sys_query_log`。
   - 在 `_complete_traced_response()` 末尾写入 BOM QA 查询历史快照，并追加 `history_snapshot_written` trace 节点。
   - 新增 `_write_history_snapshot()`，统一写入 `PLAN_BOM_QA` / `plan_bom_qa` 日志，包含问题、状态、NLU intent、结果行数、响应快照等。
   - 新增 `write_error_log()`，API 异常时写入 `ERROR` 快照。
   - 新增 `_safe_log_message()`，对异常信息中的 `sk-`、Bearer、api_key/token/password/secret、DB URL 密码、JSON/字典形式敏感字段进行脱敏。
   - 写异常日志前先 rollback，避免 failed transaction 导致错误日志丢失；日志写入失败不影响主问答链路。

2. `backend/app/domains/plan_bom/api/endpoints/qa.py`
   - `/ask` 异常路径委托 `service.write_error_log()` 写入错误日志后继续抛出原异常。

3. `tests/business_acceptance/test_plan_bom_query_log.py`
   - 新增 BOM QA 日志回归测试：成功、澄清、异常错误快照、异常脱敏、事务恢复、日志失败不阻断主链路、API 异常委托写日志。

## 验证结果

- Focused：`backend/.venv/bin/python -m pytest tests/business_acceptance/test_plan_bom_query_log.py -q --tb=short`
  - 结果：`5 passed`
- 相关回归：`test_plan_bom_query_log.py` + `test_plan_power_m5_qa_integration.py` + 两个物流基础回归
  - 结果：`18 passed`
- 编译检查：`compileall` 覆盖本轮变更文件
  - 结果：通过
- 静态 diff 检查：`git diff --check`
  - 结果：通过
- 独立 review：最终结论 `PASS`，无阻塞问题。

## 全量回归说明

- 全量 `tests/business_acceptance` 已重新执行通过：`157 passed, 2 warnings in 34.61s`。
- 2 个 warning 来自 `openpyxl` 对 xlsm 扩展/条件格式的既有提示，与本轮 BOM QA 日志写入无关。

## 风险与影响

- 对物流：不修改物流日志写入实现，仅复用 `LogisticsQueryRepository.write_query_log()`；BOM 使用独立 `query_type=PLAN_BOM_QA`、`route_type=plan_bom_qa`，不影响现有物流 `DATA_QA` 行为。
- 对主链路：日志写入失败会 rollback 并返回 `0`，不会阻断 BOM QA 正常回答。
- 安全：异常日志已做敏感信息脱敏；测试覆盖普通键值、Bearer、DB URL、JSON/字典形式。

## 验收材料

- `ai/tasks/running/TASK-bom-query-log/diff.patch`
- `ai/tasks/running/TASK-bom-query-log/test.log`
- `ai/tasks/running/TASK-bom-query-log/final-acceptance.md`

# t_3ca95bf9 final acceptance

## 结论

M5 产销存 shadow compare review blocker 已修复并完成复验。当前实现保持 shadow-only，不执行 live DB，不接管正式 QA 主链路，不引入自由 SQL 执行。

## 修复范围

- 为 QueryPlan 与独立 SQLPlan candidate 的期间语义增加不可逆安全指纹比较，能够区分不同年份、月份、季度和 YTD 截止范围，同时 artifact 不持久化明文期间参数。
- 移除 QueryPlan 反向生成 SQLPlan candidate 的旧 helper；缺少独立 candidate 时 fail-closed。
- 默认 artifact 输出目录改为优先使用 `HERMES_KANBAN_TASK` 对应 outbox，避免写入旧任务目录。
- 扩展脱敏覆盖：DSN、连接串、Bearer、password/token/secret/api_key/access_token/secret_key/api-key/apiKey 等赋值形态。
- 补齐 RED/GREEN 单测，覆盖默认 outbox、缺失独立 candidate、期间指纹错配和脱敏。

## 验证结果

- M5 focused shadow compare：11 passed。
- 产销存 M2/M3/M4/M4-6 + semantic catalog + SQLPlan regression：85 passed。
- 物流/BOM/功率 focused regression：25 passed。
- post-review cleanup 合并回归：110 passed。
- 后端 scoped py_compile：passed。
- 前端 build：passed（仅保留既有 chunk size warning）。
- M5 shadow artifact generation：total 11，matched 7，fail-closed 4，expected_status_mismatch_count 0，shadow_only true。
- static scan：passed，no findings。
- independent review：passed true。

## 验收材料

- `ai/outbox/kanban/t_3ca95bf9/test.log`
- `ai/outbox/kanban/t_3ca95bf9/static-scan.log`
- `ai/outbox/kanban/t_3ca95bf9/static-scan.json`
- `ai/outbox/kanban/t_3ca95bf9/review-result.json`
- `ai/outbox/kanban/t_3ca95bf9/diff.patch`
- `ai/outbox/kanban/t_3ca95bf9/m5-inventory-sales-production-shadow-records.jsonl`
- `ai/outbox/kanban/t_3ca95bf9/m5-inventory-sales-production-shadow-report.md`

## 风险与说明

- 未执行 live DB smoke，符合本卡边界。
- 未 push、未 merge、未 deploy、未自动 commit。
- 工作树仍保留前序任务 outbox 未跟踪目录 `t_d76060c2/`、`t_87762691/`，按任务要求未 reset/stash/clean。
- 本次改动未修改物流、计划 BOM、功率预测主链路代码；仅运行 focused regression 验证未受影响。

# M5-2 final acceptance — 产销存 SQLPlan validator 白名单与安全门禁

## 变更范围

- `backend/app/domains/business_analysis/services/inventory_sales_production/sql_plan.py`
- `tests/unit/business_analysis/test_inventory_sales_production_sql_plan.py`

## 本轮修复的 reviewer blockers

1. standalone `sys_query_log` 等内部日志表标识：作为 internal identifier 处理，scanner path、schema path、catalog/table/metric/dimension/support error 的动态片段统一脱敏为 `redacted`。
2. `business_flags` 绕过：`yoy`、`year_over_year`、`mom`、`month_over_month` 均 fail-closed；未知 `business_flags` 也拒绝。
3. 非 active `period_type` 夹带时间字段：所有提供的 `month`/`quarter` 都进行 1-12 / 1-4 范围与 2026 已发布月份边界校验，并额外拒绝与 `period_type` 不匹配的 smuggling 字段。
4. `business_month` filter 绕过：只允许 `=` / `in`，拒绝任意区间；值必须为 1-12，且按 plan year 校验已发布月份边界。
5. `group_by` 维度纳入 query_key support gate，避免 summary query_key 通过 group_by 偷带拆分维度。

## TDD / verification

- RED reviewer blocker tests：修复前 12 failed in 0.46s。
- GREEN reviewer blocker tests：修复后 12 passed in 0.34s。
- SQLPlan focused file：38 passed in 0.36s。
- business_analysis unit slice：57 passed in 1.34s。
- py_compile：rc=0。
- static scan：added diff lines 1399，无 hardcoded secret assignment / shell injection / eval-exec / pickle / SQL string formatting 命中。
- independent read-only review：passed，无 security_concerns / logic_errors。

## 产物

- diff: `ai/outbox/kanban/t_c7c1f8de/diff.patch`
- tests: `ai/outbox/kanban/t_c7c1f8de/test.log`
- static scan: `ai/outbox/kanban/t_c7c1f8de/static-scan.log` / `static-scan.json`
- diff check: `ai/outbox/kanban/t_c7c1f8de/diff-check.log`
- review: `ai/outbox/kanban/t_c7c1f8de/review-result.json`

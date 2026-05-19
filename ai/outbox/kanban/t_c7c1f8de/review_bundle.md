# M5-2 review bundle: 产销存 SQLPlan validator 白名单与安全门禁

Task: t_c7c1f8de
Branch: feature/isp-m5-inventory-nl2sql-integration
Worktree: /Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/isp-m5-inventory-nl2sql-integration

## Changed files

- backend/app/domains/business_analysis/services/inventory_sales_production/sql_plan.py
  - 定义产销存 SQLPlan candidate/plan/filter/order_by/validation result/validator。
  - 只表达受控结构，不执行 SQL、不连接数据库。
  - 固定 candidate schema_version 与 semantic catalog version。
  - 只允许 business_analysis / inventory_sales_production / middle_db / ISP_ALLOWED_READ_TABLES 范围内的产销存事实/维表。
  - scanner/schema/non-scanner errors 的动态片段经 `_safe_error_value` / `_safe_error_path` / `_child_error_path` 脱敏，覆盖 SQL-like 字符串、函数式表达式与 standalone `sys_query_log` 内部日志标识。
  - query_key/metric/dimension/group_by 复用 semantic catalog support gate，并二次校验 catalog_refs、metric source columns、dimension columns、依赖指标、表范围。
  - 聚合策略门禁覆盖流量 SUM、period_end 库存/存货/寄存不能年度 SUM、calculated_ratio、limit。
  - 时间边界门禁覆盖年份、月份、季度、未发布月份、任意月份区间、非活跃 period_type 夹带 month/quarter/start/end、business_month filter、同比/环比 business_rules/business_flags。

- tests/unit/business_analysis/test_inventory_sales_production_sql_plan.py
  - 38 个 focused SQLPlan validator 测试。
  - 覆盖合法/不合法 candidate、catalog v1/domain/subdomain/table/source_system 边界、raw SQL key/string、dynamic redaction、query_key support、group_by smuggling、aggregation policy、time boundary、business_month filter、business_flags gate、polluted catalog 等。

## Latest reviewer blocker closure

独立 reviewer 最新阻塞项均已按 TDD 补 RED 并修复：

1. standalone `sys_query_log` 未识别/未脱敏
   - 修复：`INTERNAL_IDENTIFIER_RE` 同时用于 scanner 与 `_safe_error_value`。
   - 测试：`test_isp_sql_plan_validator_redacts_standalone_internal_log_table_identifiers`。

2. `business_flags` 携带 `yoy` / `month_over_month` 绕过
   - 修复：新增 `_validate_business_flags`，支持开关白名单，并对 `yoy/year_over_year/mom/month_over_month` fail-closed。
   - 测试：`test_isp_sql_plan_validator_blocks_time_comparison_flags_in_business_flags`、`test_isp_sql_plan_validator_rejects_unknown_business_flags`。

3. 非 active `period_type` 夹带 `month` / `quarter` 绕过
   - 修复：所有提供的 month/quarter 均校验范围和已发布月份边界，并拒绝与 period_type 不匹配的字段。
   - 测试：`test_isp_sql_plan_validator_rejects_period_field_smuggling`、`test_isp_sql_plan_validator_checks_supplied_month_quarter_even_when_period_type_differs`。

4. `business_month` filter 绕过范围/未发布月份/任意区间
   - 修复：新增 `_validate_month_filter_shapes` 和 `_parse_month_filter_value`；仅允许 `=` / `in`，拒绝 `between`，校验 1-12 和 2026 已发布月份边界。
   - 测试：`test_isp_sql_plan_validator_checks_business_month_filter_boundaries`。

5. `group_by` 维度绕过 query_key support gate
   - 修复：`_validate_query_key_support` 使用 `plan.dimensions + plan.group_by`。
   - 测试：`test_isp_sql_plan_validator_blocks_group_by_dimension_smuggling_for_summary_query_key`。

## Verification

- RED reviewer blocker tests before fix: 12 failed in 0.46s。
- GREEN reviewer blocker tests after fix: 12 passed in 0.34s。
- SQLPlan focused file: 38 passed in 0.36s。
- business_analysis unit slice: 57 passed in 1.34s。
- py_compile: rc=0。
- static scan: 1399 added diff lines scanned, no findings for hardcoded secret assignment / shell injection / eval-exec / pickle / SQL string formatting。
- independent read-only review: passed; no security_concerns / logic_errors。

Artifacts:
- ai/outbox/kanban/t_c7c1f8de/diff.patch
- ai/outbox/kanban/t_c7c1f8de/test.log
- ai/outbox/kanban/t_c7c1f8de/static-scan.log
- ai/outbox/kanban/t_c7c1f8de/static-scan.json
- ai/outbox/kanban/t_c7c1f8de/diff-check.log
- ai/outbox/kanban/t_c7c1f8de/review-result.json
- ai/outbox/kanban/t_c7c1f8de/final-acceptance.md

## Review focus

- fail-closed safety for SQL-like/raw/internal payloads without leaking dynamic strings。
- fixed semantic catalog version and allowed middle-db read table boundary。
- group_by/query_key support gate and catalog_ref enforcement。
- period_end/calculated_ratio aggregation policy。
- month/quarter/business_month/unpublished-month/business_flags edge cases。
- no SQL execution, shell/eval/exec/pickle, string-concatenated SQL, or raw LLM payload exposure。

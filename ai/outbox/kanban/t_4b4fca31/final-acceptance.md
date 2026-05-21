# t_4b4fca31 final acceptance

## 结论

M5-6 产销存 NL2SQL shadow 扩样与安全回归已完成。默认 shadow 样例从 M5-5 的 11 条扩展到 31 条，总体保持 shadow-only：未执行 live DB，未让 NL2SQL 正式接管用户可见 QA，未 push / merge / deploy。

## 修改文件清单

本次 scoped 修改/归档范围：

- `backend/app/domains/business_analysis/services/inventory_sales_production/m5_shadow_compare.py`
- `tests/unit/business_analysis/test_inventory_sales_production_m5_shadow_compare.py`
- `ai/outbox/kanban/t_4b4fca31/m5-6-precheck.md`
- `ai/outbox/kanban/t_4b4fca31/m5-inventory-sales-production-shadow-records.jsonl`
- `ai/outbox/kanban/t_4b4fca31/m5-inventory-sales-production-shadow-report.md`
- `ai/outbox/kanban/t_4b4fca31/test.log`
- `ai/outbox/kanban/t_4b4fca31/diff.patch`
- `ai/outbox/kanban/t_4b4fca31/review_bundle.md`
- `ai/outbox/kanban/t_4b4fca31/review-result.json`
- `ai/outbox/kanban/t_4b4fca31/final-acceptance.md`

未修改/未提交范围：

- 未修改 `scripts/dev/run_inventory_sales_production_m5_shadow_compare.py`。
- 未修改物流、计划 BOM、功率预测主链路。
- 未修改 `.env`、连接串、密钥、真实 host/账号。
- 未提交 `tmp/hermes/**` 临时执行脚本。

## 新增 shadow 样例覆盖说明

默认样例总数：31。

覆盖范围：

- 产量、销量/发货量、库存/存货、寄存库存、预算达成率等核心指标。
- 年度、季度、月度、YTD、已发布月份、未来/未发布月份等时间边界。
- 对外销量/组件事业部剔除内部交易、发货量同义词、存货/库存同义词、中文季度等业务口径和同义表达。
- 按型号、基地等维度拆分的安全 matched 场景。
- fail-closed 场景：未来月份、暂不支持同比/环比、未知指标澄清、显式多年默认范围缺候选、直接无时间默认范围 guard、raw SQL/debug/internal candidate 拒绝。
- 安全负例：持久化 artifact 不保留真实 SQL、原始问题、连接串、密钥、具体期间边界值。

关键修复：第二轮独立 review 发现 SQLPlan 未发布月份错误码会把具体期间边界写入 artifact；已按 TDD 增加 RED 回归测试，并将持久化错误码清洗为 `sqlplan_unpublished_month_blocks_sql_direct::[PERIOD_BOUNDARY]`。

## 测试方法与结果

完整验收日志：`ai/outbox/kanban/t_4b4fca31/test.log`。

已通过：

- M5-6 focused GREEN：1 passed。
- review-fix RED/GREEN：`test_m5_shadow_redacts_period_values_from_validation_error_codes` 修复前失败，修复后通过。
- M5/M5-6 shadow compare regression：13 passed。
- 产销存 M2/M3/M4/M4-6 regression：85 passed。
- 物流 focused regression：22 passed。
- 计划 BOM / 功率 focused regression：21 passed。
- `py_compile`：m5_shadow_compare.py、runner、unit test 均通过。
- backend compileall：通过。
- M5-6 shadow runner：total=31，matched=20，fail_closed_count=11，expected_status_mismatch_count=0，shadow_only=true，formal_qa_executed=false，live_db_executed=false。
- artifact-check：31 records，全部 shadow_only，formal_qa_executed=false，live_db_executed=false，未发现 forbidden SQL/credential fragments。
- static scan：added_lines=394，findings=0。
- `git diff --check`：通过。
- `git diff --cached --check`：最终通过；中途仅因 `diff.patch`/`test.log` 证据文件中的历史失败输出含尾随空格失败，已只清理证据文件尾随空格，生产源码/测试逻辑未改变，并复跑 cached check 通过。
- M5-6R 收口复跑：focused 1 passed、shadow compare 13 passed、产销存回归 85 passed、物流 22 passed、计划 BOM/功率 21 passed、py_compile/compileall/runner/artifact-check/static scan/diff-check 均通过。

## Static scan 结果

静态扫描结果：passed=true，findings=0。

扫描重点覆盖新增 diff 行中的 hardcoded secret、shell injection、eval/exec、pickle、SQL format 注入等风险；同时 artifact-check 验证 JSONL/Markdown 不泄露真实 SQL、连接串、密钥、原始参数或具体期间边界值。

## 独立 review 结果

Review 结果文件：`ai/outbox/kanban/t_4b4fca31/review-result.json`。

最终 verdict：

- passed=true
- security_concerns=[]
- logic_errors=[]
- suggestions=[]
- shadow_only=true
- live_db_executed=false
- formal_qa_takeover=false
- user_visible_technical_leakage=false
- sensitive_or_period_boundary_leakage=false
- impacts_logistics_plan_bom_power=false
- review_blockers=[]

Review 过程：

1. 第一轮独立 review 通过，仅建议增强测试断言；已补强基线排序、全部 M5-6 新样例 ID、直接无时间默认范围 guard。
2. 第二轮独立 review 发现 blocker：未发布月份错误码持久化具体期间边界；已按 TDD 修复并重新跑验收。
3. 当前任务再次执行独立只读复审，结合完整回归日志后通过，无阻塞安全或逻辑问题。

## Commit id

提交前无法在同一提交内容中自包含最终 commit hash（hash 会随文件内容变化）。本文件随 `[verified] 扩展产销存M5-6影子对比样例` 提交归档；实际 commit id 在提交后由 `git rev-parse HEAD` 读取，并记录在本卡看板完成备注和最终回复中。

## 当前 git status

提交前最终 staged 范围仅限：

```text
A  ai/outbox/kanban/t_4b4fca31/diff.patch
A  ai/outbox/kanban/t_4b4fca31/final-acceptance.md
A  ai/outbox/kanban/t_4b4fca31/m5-6-precheck.md
A  ai/outbox/kanban/t_4b4fca31/m5-inventory-sales-production-shadow-records.jsonl
A  ai/outbox/kanban/t_4b4fca31/m5-inventory-sales-production-shadow-report.md
A  ai/outbox/kanban/t_4b4fca31/review-result.json
A  ai/outbox/kanban/t_4b4fca31/review_bundle.md
A  ai/outbox/kanban/t_4b4fca31/test.log
M  backend/app/domains/business_analysis/services/inventory_sales_production/m5_shadow_compare.py
M  tests/unit/business_analysis/test_inventory_sales_production_m5_shadow_compare.py
```

未 staged/未提交禁止文件：无。

## 风险点

- 当前仍是 shadow-only 扩样与安全回归，不能把本轮结果误解为 live provider gate 已通过或正式用户可见 QA 已接管。
- 直接无时间默认范围在本轮作为 fail-closed guard 记录，后续若要让产销存正式承接“无时间条件默认 2023-2026”，需要另开阶段卡做 live/provider 与用户可见链路接管。
- M5-6 样例使用离线 SQLPlan fixture，不代表已执行真实数据库查询。

## 当前仍未解决的问题

- 未执行 live DB。
- 未进入 live provider gate。
- 未让 NL2SQL 正式接管产销存用户可见 QA。
- 未实现采购/供应链/产供销范围，本轮保持经营分析域的产销存。

## 对既有能力影响

- 物流：focused regression 22 passed；未修改物流主链路。
- 计划 BOM：计划 BOM / 功率 focused regression 合计 21 passed；未修改计划 BOM 主链路。
- 功率预测：计划 BOM / 功率 focused regression 合计 21 passed；未修改功率预测主链路。

## 阶段边界与发布动作

- 已遵守 shadow-only 阶段边界。
- 未执行 live DB。
- 未让 NL2SQL 正式接管用户可见 QA。
- 未 push / merge / deploy。

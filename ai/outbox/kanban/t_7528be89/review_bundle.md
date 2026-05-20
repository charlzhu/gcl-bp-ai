# t_7528be89 二次返工后独立 review bundle

## 任务范围

- 任务：合入并复验产销存 M5/M5-6 shadow 治理成果，并处理独立 review 阻塞反馈。
- 当前工作区：`/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/hermes-9fa1e059`
- 当前分支：`hermes/hermes-9fa1e059`
- 当前 HEAD：`ad31f3e0 [verified] 扩展产销存M5-6影子对比样例`
- 合入前基线 / merge base：`f24d39ae318cea9af081aa05b3edfdcdcf46ef33`
- 本轮仍保持 shadow-only：不启用 live provider、不连接 live DB、不让 NL2SQL 正式接管用户可见产销存 QA。

## 当前未提交变更

当前未提交源码/测试变更仅 2 个文件：

```text
M backend/app/domains/business_analysis/services/inventory_sales_production/sql_plan.py
M tests/unit/business_analysis/test_inventory_sales_production_sql_plan.py
```

post-review fix diff：

```text
ai/outbox/kanban/t_7528be89/post-review-fix.diff.patch
ai/outbox/kanban/t_7528be89/post-review-fix.diff.stat
ai/outbox/kanban/t_7528be89/post-review-fix.diff.name-status
```

统计：`2 files changed, 93 insertions(+)`。

## 已处理的 review 阻塞

上一轮独立 review 阻塞：`business_rules` 内部/debug 脱敏只覆盖 `_`/`-` 分隔形式，`debug trace`、`debug.trace`、`raw/debug`、`debugTrace`、`sysAuditHint` 会在错误码里明文回显。

本轮 TDD 处理：

1. 先新增 RED 参数用例，覆盖空白、点号、斜杠、camelCase 和 sys/audit 组合；现有实现下 5 failed / 3 passed。
2. 最小实现：`INTERNAL_BUSINESS_RULE_RE` 对 `debug|trace|internal|raw|sys|audit` 采用保守包含式匹配，仅用于 `business_rules` 未知规则错误片段脱敏。
3. GREEN：`test_isp_sql_plan_validator_rejects_unknown_or_internal_business_rules` + `test_isp_sql_plan_validator_accepts_known_business_rule_labels` 通过，后续相关回归通过。

## 请重点 review 的修复点

1. `business_rules` 是否只接受显式白名单标签。
2. 未知规则是否产生 `sqlplan_business_rule_not_allowed::*`。
3. 内部治理词变体是否都脱敏为 `redacted`，包括 `_`、`-`、空白、`.`、`/`、camelCase 形式。
4. 合法未知业务规则如 `unsafe_rule` 是否仍可在错误码里保留安全业务片段。
5. 同比/环比/月区间/未发布月份等已阻断规则是否仍 fail-closed。
6. 已存在合法 shadow 业务规则是否未被误伤：
   - `budget_achievement_recalculated`
   - `explicit_invoice_metric`
   - `period_end_inventory_snapshot`
   - `ytd_by_published_months`
7. 修复是否仍保持 shadow-only，不接入 live provider / live DB / 用户可见正式 QA。

## 全量 scoped source/test diff

若需要核对完整 M5/M5-6 合入范围，可查看：

```text
ai/outbox/kanban/t_7528be89/scoped-source.diff.patch
ai/outbox/kanban/t_7528be89/scoped-source.diff.stat
ai/outbox/kanban/t_7528be89/scoped-source.diff.name-status
```

完整源码、脚本、测试范围：

```text
backend/app/domains/business_analysis/services/inventory_sales_production/m5_shadow_compare.py
backend/app/domains/business_analysis/services/inventory_sales_production/sql_plan.py
scripts/dev/run_inventory_sales_production_m5_shadow_compare.py
tests/unit/business_analysis/test_inventory_sales_production_m5_shadow_compare.py
tests/unit/business_analysis/test_inventory_sales_production_sql_plan.py
```

## 最终验证摘要

最终日志：`ai/outbox/kanban/t_7528be89/test.log`。

已通过：

- RED 记录：新增 internal business_rules 变体测试先出现 `5 failed, 3 passed`，符合预期。
- GREEN：business_rules 变体 + 合法规则 focused：`9 passed`。
- SQLPlan 单测：`51 passed`。
- M5/M5-6 shadow + SQLPlan 单测：`64 passed`。
- M5/M5-6 shadow runner：`total=31`、`matched=20`、`fail_closed_count=11`、`expected_status_mismatch_count=0`、`shadow_only=true`、`formal_qa_executed=false`、`live_db_executed=false`。
- 产销存 M2/M3/M4/M4-6 回归：`94 passed`。
- 物流 focused 回归：`22 passed`。
- 计划 BOM / 功率 focused 回归：`21 passed`。
- focused `py_compile`：通过。
- backend `compileall`：通过。
- post-review fix `git diff --check`：通过，`exit_code=0`。
- scoped source/test `git diff --check`：通过，`exit_code=0`。
- static scan：`passed=true`、`findings=[]`；3 个 allowed_test_fixtures 均是测试中验证脱敏的合成红队负例。

## 已知非阻塞记录

- 探索性扩大物流回归曾发现 `tests/business_acceptance/test_logistics_carrier_filter_scope.py` 2 个既有失败；本轮没有修改 logistics 目录，且同口径物流 focused 22 条通过，故不作为本卡阻塞。
- 整个 f24d39ae..HEAD 的历史 outbox 证据中有旧任务 diff.patch 尾随空格；本轮 scoped source/test diff-check 已通过，本卡不改写旧任务证据文件。
- 本轮没有 frontend diff，不跑 frontend build。

## 期望 review 输出

请返回严格 JSON，不要附加 Markdown：

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": [],
  "review_blockers": [],
  "suggestions": [],
  "summary": "..."
}
```

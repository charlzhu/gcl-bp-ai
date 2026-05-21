# t_7528be89 final acceptance

## 结论

本轮 Kanban 卡 `t_7528be89` 已完成：将产销存 M5/M5-6 shadow 治理成果合入当前工作分支后复验，并处理独立 review 提出的 `business_rules` 脱敏阻塞项。

当前仍保持 **shadow-only**：未启用 live provider，未连接 live DB，未让 NL2SQL 正式接管用户可见产销存 QA，未 push，未 deploy。

## 当前仓库已完成能力判断

- 已具备产销存 M2/M3/M4/M4-6 正式 MVP 链路：中间库事实入库、受控 QueryPlan/QueryExecutor、QA/API、真实问法回归。
- 已合入 M5/M5-6 shadow 治理能力：SQLPlan candidate 结构、Semantic Catalog 对齐校验、白名单与 fail-closed 安全门禁、shadow-only QueryPlan/SQLPlan 对比、31 条 shadow 样例、脱敏 artifact 输出。
- 本轮额外补齐 `business_rules` 白名单门禁：未知规则 fail-closed，内部/debug/raw/sys/audit 规则变体统一脱敏。
- 现有物流、计划 BOM、功率预测主链路未被本轮修改。

## 当前未完成能力判断

- M6 live provider gate 未开始。
- live DB 验证未开始。
- NL2SQL 正式接管用户可见产销存 QA 未开始。
- renderer/executor 正式 SQL 生成/执行链路未进入生产路径。
- 后续新增产销存需求必须另开 Kanban 卡，不在当前聊天分支直接开发。

## 本次任务与当前仓库状态是否一致

一致。本轮是在当前 `hermes/hermes-9fa1e059` 工作分支上做 M5/M5-6 shadow 合入复验与 review 返工，不扩大到 M6/live provider/正式 QA 接管。

## 本轮允许修改范围

- 合入并复验产销存经营分析域 M5/M5-6 SQLPlan validator、shadow compare、扩样测试、安全脱敏/fail-closed 相关成果。
- 对独立 review 发现的 `business_rules` 脱敏阻塞点做最小 TDD 返工。
- 生成本轮复验证据、review 材料、提交清单。

## 本轮禁止修改范围

- 不启用 live provider。
- 不让 NL2SQL 正式接管用户可见 QA。
- 不连接生产库、不修改 `.env`、不写入真实凭据/连接串。
- 不修改原始附件。
- 不 push、不 deploy、不自动合并到 main。
- 不扩采购/供应链/物管，不改物流/计划 BOM/功率预测主链路。

## 修改 / 合入文件清单

### 本轮 review 返工源码/测试变更

- `backend/app/domains/business_analysis/services/inventory_sales_production/sql_plan.py`
- `tests/unit/business_analysis/test_inventory_sales_production_sql_plan.py`

post-review fix diff：

- `ai/outbox/kanban/t_7528be89/post-review-fix.diff.patch`
- `ai/outbox/kanban/t_7528be89/post-review-fix.diff.stat`
- `ai/outbox/kanban/t_7528be89/post-review-fix.diff.name-status`

统计：`2 files changed, 93 insertions(+)`。

### 当前分支相对合入前基线 `f24d39ae` 的 M5/M5-6 scoped source/test 范围

- `backend/app/domains/business_analysis/services/inventory_sales_production/sql_plan.py`
- `backend/app/domains/business_analysis/services/inventory_sales_production/m5_shadow_compare.py`
- `scripts/dev/run_inventory_sales_production_m5_shadow_compare.py`
- `tests/unit/business_analysis/test_inventory_sales_production_sql_plan.py`
- `tests/unit/business_analysis/test_inventory_sales_production_m5_shadow_compare.py`

### 本轮验收材料目录

- `ai/outbox/kanban/t_7528be89/test.log`
- `ai/outbox/kanban/t_7528be89/diff.patch`
- `ai/outbox/kanban/t_7528be89/diff.stat`
- `ai/outbox/kanban/t_7528be89/diff.name-status`
- `ai/outbox/kanban/t_7528be89/source-diff.patch`
- `ai/outbox/kanban/t_7528be89/source-diff.stat`
- `ai/outbox/kanban/t_7528be89/source-diff.name-status`
- `ai/outbox/kanban/t_7528be89/scoped-source.diff.patch`
- `ai/outbox/kanban/t_7528be89/scoped-source.diff.stat`
- `ai/outbox/kanban/t_7528be89/scoped-source.diff.name-status`
- `ai/outbox/kanban/t_7528be89/post-review-fix.diff.patch`
- `ai/outbox/kanban/t_7528be89/post-review-fix.diff.stat`
- `ai/outbox/kanban/t_7528be89/post-review-fix.diff.name-status`
- `ai/outbox/kanban/t_7528be89/post-review-fix.diff-check.log`
- `ai/outbox/kanban/t_7528be89/diff-check-scoped.log`
- `ai/outbox/kanban/t_7528be89/m5-inventory-sales-production-shadow-records.jsonl`
- `ai/outbox/kanban/t_7528be89/m5-inventory-sales-production-shadow-report.md`
- `ai/outbox/kanban/t_7528be89/review_bundle.md`
- `ai/outbox/kanban/t_7528be89/review-result.json`
- `ai/outbox/kanban/t_7528be89/final-acceptance.md`

## 关键改动说明

- 新增/合入产销存 SQLPlan candidate / plan 数据结构与确定性 validator。
- validator 对 raw_sql/sql/where/free_sql、SQL-like 字符串、内部日志标识、非中间库表、非白名单字段、旧 catalog 版本、指标/维度/query_key 不匹配、未发布月份、同比/环比/月区间等场景 fail-closed。
- 新增 M5/M5-6 shadow-only 对比 runner：只做离线 QueryPlan 与 SQLPlan candidate 签名对齐和安全校验，不执行正式 QA 主链路，不连接 live DB。
- shadow artifact 只输出脱敏摘要，不持久化 SQL、原始问题、真实参数、连接串、密钥或具体期间边界值。
- 新增 31 条默认 shadow 样例，覆盖销量/发货量、产量、库存/存货、寄存库存、预算达成率、年度/季度/月度/YTD、未来/未发布月份、未知指标、SQL/debug/internal candidate 等场景。
- review 返工点：`business_rules` 使用显式白名单；未知安全标签给出受控错误；`debug|trace|internal|raw|sys|audit` 等内部治理词即使以空白、点号、斜杠或 camelCase 形式出现，也统一在错误片段中显示为 `redacted`。

## TDD 记录

- RED：新增 `business_rules` 内部标签变体测试，覆盖 `debug trace`、`debug.trace`、`raw/debug`、`debugTrace`、`sysAuditHint`，现有实现下 `5 failed, 3 passed`。
- GREEN：最小调整 `INTERNAL_BUSINESS_RULE_RE` 为 `business_rules` 专用保守包含式脱敏，focused 用例 `9 passed`。
- REFACTOR：未做大范围重构，仅保留中文注释说明保守脱敏原因。

## 测试方法与结果

最终日志：`ai/outbox/kanban/t_7528be89/test.log`。

通过项：

- business_rules 变体 + 合法规则 focused：`9 passed`。
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
- static scan：`passed=true`、`findings=[]`；3 个 allowed_test_fixtures 均为测试中用于验证脱敏的合成红队负例，不是真实凭据。

补充记录：

- 探索性扩大物流回归曾发现 `tests/business_acceptance/test_logistics_carrier_filter_scope.py` 2 个既有失败。本轮 diff 未修改 logistics 目录，且同口径物流 focused 22 条通过；该问题不作为本卡阻塞。
- 全量历史 outbox artifact 中存在旧证据文件尾随空格；本轮 scoped source/test diff-check 通过，本卡不改写旧任务证据文件。

## 独立 review 结果

Review 文件：`ai/outbox/kanban/t_7528be89/review-result.json`。

最终结果：

- `passed=true`
- `security_concerns=[]`
- `logic_errors=[]`
- `review_blockers=[]`
- `suggestions=[]`

结论：business_rules 白名单门禁已补齐，内部/debug/raw/sys/audit 规则变体已脱敏，时间规则继续 fail-closed，合法 shadow 业务规则未被误伤且保持 shadow-only。

## 风险点

- 当前 M5/M5-6 仍是 shadow 治理层，不能代表 live provider、SQL renderer/executor 或用户可见正式 NL2SQL 接管已完成。
- 全量历史 outbox artifact 中存在旧证据文件尾随空格；未影响生产代码、脚本、测试，也未在本轮改写历史证据。
- 探索性扩大物流回归发现 2 个既有物流测试失败，建议后续单独 Kanban 卡处理，不在本轮产销存合入卡内修改物流主链路。

## 当前仍未解决的问题

- M6 live provider gate 未做。
- live DB smoke / shadow 验证未做。
- NL2SQL 正式接管用户可见产销存 QA 未做。
- 物流 `test_logistics_carrier_filter_scope.py` 2 个探索性扩大回归失败未在本轮修复。

## 是否影响现有 BOM / 物流 / 功率预测能力

按本轮同口径 focused 回归：未发现影响。

- 物流 focused：通过。
- 计划 BOM / 功率 focused：通过。
- 本轮没有修改物流、计划 BOM、功率预测源码。

## 是否遵守本轮阶段边界

遵守。

- 仅合入并复验 M5/M5-6 shadow 治理成果。
- 仅对 reviewer 阻塞项做最小 TDD 返工。
- 未启用 live provider。
- 未让 NL2SQL 正式接管用户可见 QA。
- 未连接 live DB。
- 未扩展到采购/供应链/物管。

## commit / push / deploy

- 本验收材料随本轮 scoped verified commit 一起提交。
- 未 push。
- 未 deploy。

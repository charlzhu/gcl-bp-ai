# M5-6 precheck：产销存 NL2SQL shadow 扩样与安全回归

## 1. 当前仓库已完成能力判断

- 当前 worktree 已在 `feature/isp-m5-6-shadow-expansion` 分支，基线 commit 为 `4a21908020eb82e6e5f57c07f12cf38129631c76`，与任务卡声明一致。
- 父任务 `t_4131bbbb` 已完成 M5-5 收口并提交：产销存 M5 shadow-only QueryPlan / SQLPlan 离线对比能力、runner、focused tests、脱敏 JSONL/Markdown 证据已合入基线。
- 当前 `build_default_inventory_sales_production_m5_shadow_samples()` 返回 11 条默认 shadow 样例；状态覆盖 `matched`、`queryplan_clarification`、`queryplan_unsupported`、`sqlplan_validation_failed`。
- 当前 M5 shadow runner 已具备 `shadow_only=true`、`formal_qa_executed=false`、`live_db_executed=false` 的脱敏摘要输出能力。
- 已有安全边界包括：不调用正式 QA 主链路、不执行 live DB、记录中不持久化原始问句/SQL/连接信息/参数明文、时间参数使用形状与不可逆指纹比较。
- 已读取并遵守任务要求中的必读文档、项目协议、技术经理角色规范、company-code-builder 工作流、M5-5 验收材料及现有产销存测试/服务文件。

## 2. 当前未完成能力判断

- 默认 shadow 样例仍为 11 条，未达到本卡要求的至少 30 条总样例。
- M5-6 尚未覆盖足够的同义问法、年度/月度/YTD/未来月份/无时间默认 2023-2026、预算达成率、对外销量、内部交易剔除等扩展样例。
- fail-closed 场景还需要扩充：澄清、暂不支持、空结果或边界不安全、SQL/raw/debug/LLM/连接信息泄露负例。
- 本卡所需 `test.log`、`static-scan`、`review-result.json`、`final-acceptance.md` 尚未生成。
- 尚未执行本卡 focused/regression/compile/runner/static scan/diff check，也尚未执行独立 review 与本卡 commit。

## 3. 本次任务与当前仓库状态一致性

一致。当前仓库刚完成 M5 最小 shadow-only 对比与 M5-5 收口，正适合在不进入 live provider gate、不接管正式 QA 的前提下扩充离线样例与安全回归。当前分支、worktree、基线 commit、父卡结果均与任务卡声明一致，且当前工作区启动时无可见未提交 diff。

## 4. 本轮允许修改范围

仅限以下范围内增量修改或新增：

1. `backend/app/domains/business_analysis/services/inventory_sales_production/m5_shadow_compare.py`
2. `scripts/dev/run_inventory_sales_production_m5_shadow_compare.py`
3. `tests/unit/business_analysis/test_inventory_sales_production_m5_shadow_compare.py`
4. 必要时新增仅服务 M5-6 shadow 扩样的 fixture/helper/test 文件，路径必须在产销存或 test 相关目录下。
5. `ai/outbox/kanban/t_4b4fca31/**`

## 5. 本轮禁止修改范围

- 不修改 main，不 push、merge、deploy。
- 不执行 live DB，不读取或提交 `.env`、连接串、真实 host、账号、密钥或数据库凭据。
- 不使用 `git add -A` 或 `git add .`；提交前只 staging 本卡允许范围。
- 不修改正式 QA 用户可见接管逻辑，不让 NL2SQL 接管正式问答。
- 不将采购、供应链或“产供销”纳入本轮；业务域仍限定为产销存 `inventory_sales_production`。
- 不修改物流、计划 BOM、功率预测主链路。
- 不提交 `frontend/tsconfig.tsbuildinfo` 等构建缓存差异。

## 6. 为什么选择 shadow 扩样，而不是 live provider gate 或正式接管

- 当前 M5 只完成 11 条最小 shadow 样例，样本面不足以证明 QueryPlan 与 SQLPlan/NL2SQL 候选在真实问法、边界问法和安全负例上的稳定性。
- live provider gate 会引入真实 provider、召回、rerank、LLM 候选等更多变量；在离线样例不足时直接进入会放大定位难度和误接管风险。
- 正式接管会影响用户可见 QA 主链路，当前阶段明确禁止。
- shadow 扩样风险最低，能继续保护既有物流、计划 BOM、功率预测能力，同时为后续 live provider gate 提供更可靠的样例基线和 fail-closed 安全回归。

## 7. 本轮执行计划

1. TDD：先新增 M5-6 样例数量、覆盖范围、脱敏/安全负例、runner 输出的失败测试，并验证 RED。
2. 实现：在 `m5_shadow_compare.py` 中增量补齐独立 SQLPlan fixture 与必要 helper，保持 QueryPlan/SQLPlan 独立、shadow-only、fail-closed 与脱敏。
3. 验证：运行 focused M5/M5-6、产销存 M2/M3/M4/M4-6、物流 focused、计划 BOM/功率 focused、compileall、runner、static scan、diff check，并写入 `test.log`。
4. Review：生成 scoped diff 与 review bundle，执行独立 review，修复 blocker 后复验。
5. Commit/Handoff：只 staging 允许范围，运行 cached diff check，中文 `[verified]` commit，生成 final acceptance 并完成 Kanban handoff。

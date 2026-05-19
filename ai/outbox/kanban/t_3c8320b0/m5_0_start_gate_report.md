# M5-0 开工门禁、现状审查与 worktree/分支创建方案

生成时间：2026-05-19 19:04:35 CST
任务：t_3c8320b0 / M5-0：开工门禁、现状审查与 worktree/分支创建方案
当前工作区：/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/hermes-1af52d1d

## 1. 本轮已读取资料

已按任务要求读取并核对：

1. `AGENTS.md`
2. `README_WORKSPACE.md`
3. `docs/CURRENT_STATUS.md`
4. `docs/NEXT_TASK.md`
5. `docs/INVENTORY_SALES_PRODUCTION_NL2SQL_COMPAT_PLAN.md`
6. `docs/HANDOFF.md`
7. `ai/inbox/requirement.md`
8. M4-6 验收材料：
   - `/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/isp-m4-6-business-acceptance/ai/outbox/inventory_sales_production_m4_6/final-acceptance.md`
   - `/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/isp-m4-6-business-acceptance/ai/outbox/inventory_sales_production_m4_6/test.log`
   - `/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/isp-m4-6-business-acceptance/ai/outbox/inventory_sales_production_m4_6/review-result.json`
   - `/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/isp-m4-6-business-acceptance/ai/outbox/inventory_sales_production_m4_6/static-scan.log`
   - `/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/isp-m4-6-business-acceptance/ai/outbox/inventory_sales_production_m4_6/diff.patch`

## 2. M4-6 门禁确认

看板评论中已有最新用户确认：M4-6 任务已经收口，可以开始 M5-0；M5-0 完成后按依赖链自动推进 M5-1 -> M5-2 -> M5-3 -> M5-4。

验收材料显示 M4-6 业务验证结论为通过：

1. M4-6 + M2/M3/M4 组合回归：`40 passed in 1.80s`。
2. 后端编译：通过，无编译错误。
3. 前端 build：通过，`frontend_build_exit_code=0`。
4. 静态扫描：`status=PASS`，未发现本轮范围硬编码密钥模式。
5. 独立 review：二次只读审查通过，`passed=true`。

同时，当前实际 git 状态有一个必须传给下一张卡的风险：

1. M4-6 worktree：`/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/isp-m4-6-business-acceptance`
2. 分支：`feature/isp-m4-6-business-acceptance`
3. HEAD：`c66ca93`
4. 与 `agent/bp-main` 关系：以 `agent/bp-main...HEAD` 计算，M4-6 分支比 `agent/bp-main` 多 1 个提交。
5. M4-6 worktree 当前仍有未提交改动：
   - `M backend/app/domains/business_analysis/services/inventory_sales_production/nl_query_planner.py`
   - `?? ai/outbox/inventory_sales_production_m4_6/`
   - `?? docs/INVENTORY_SALES_PRODUCTION_M4_6_REAL_QUESTION_REGRESSION.md`
   - `?? tests/business_acceptance/test_inventory_sales_production_m4_6_real_question_regression.py`

结论：M5-0 已获用户确认可执行；但 M5-1 真正写代码前，必须重新核对 M4-6 基线是否已经以用户认可方式提交/合并，或确认 M5 分支是否允许基于 `c66ca93` 并显式引用 M4-6 outbox 作为输入。不能从 dirty worktree 静默创建 M5 分支，不能自动替用户 commit/merge/push。

## 3. 当前仓库已完成能力判断

1. 产销存属于 `business_analysis.inventory_sales_production`，不是物流、物管 SAP MID 或计划 BOM 域。
2. 产销存 M2/M3/M4 基础能力已形成：Excel 解析、事实入库、受控 QueryPlan、确定性查询执行、QA 服务、API 注册、前端 business_analysis domain 入口均有历史/现有测试覆盖。
3. M4-6 已固化真实业务问法回归样例，验收日志显示组合回归 40 条通过。
4. 已确认的业务口径包括：
   - 销量/销售量/发货量同义，默认走发货口径。
   - 2023 全年需按 1-12 月重新计算，不能直接用原表年度列。
   - 2026 只使用已发布月份，当前截止 4 月。
   - 库存/存货/库存（SAP数据）等价，寄存仓/寄存合计等价。
   - 同比、环比、任意月份区间、库存周转率等当前按业务化 fail-closed/澄清处理。
5. 现有上位方案 `docs/INVENTORY_SALES_PRODUCTION_NL2SQL_COMPAT_PLAN.md` 已定义 M5：统一 NL2SQL 接入，目标是将产销存纳入统一语义目录和 SQLPlan validator。

## 4. 当前未完成能力判断

1. M5 尚未开始正式代码开发。
2. 产销存语义目录尚未纳入统一 NL2SQL semantic catalog。
3. 产销存 SQLPlan validator 白名单尚未建立。
4. QueryPlan MVP 与 NL2SQL SQLPlan 的 shadow 对比尚未建立。
5. 统一 NL2SQL 尚未接管产销存正式用户回答。
6. M4-6 验收改动当前在 M4-6 worktree 仍有 dirty/untracked 文件，尚不能假设已经合入 `agent/bp-main` 或可被新 worktree 自动继承。

## 5. 本轮 M5-0 允许修改范围

1. 只做开工门禁、现状审查、风险判断和 worktree/分支方案。
2. 允许生成本报告到 `ai/outbox/kanban/t_3c8320b0/`。
3. 允许给下一张卡写清楚前置检查、可执行边界和阻塞条件。
4. 允许读取 M4-6 验收材料和当前 git 状态。

## 6. 本轮 M5-0 禁止修改范围

1. 不修改业务代码。
2. 不创建/切换 M5 feature 分支。
3. 不从 dirty M4-6 worktree 创建新 worktree。
4. 不 commit、push、deploy、merge。
5. 不修改 `.env`、密钥、连接串。
6. 不修改物流、物管 SAP MID、计划 BOM、功率预测主链路。
7. 不让 LLM 自由生成 SQL 并执行。
8. 不把 Excel 原始宽表作为自由查询表。
9. 不在用户可见回答中暴露 SQL、表名、字段名、query_key、planner、guardrail、schema、raw/debug、LLM 等内部技术内容。

## 7. M5 worktree 与分支创建方案

目标分支：`feature/isp-m5-inventory-nl2sql-integration`
建议 worktree 路径：`/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/isp-m5-inventory-nl2sql-integration`
当前核对结果：本地分支不存在、远端分支不存在、候选 worktree 路径不存在。

推荐创建前置条件：

1. 先由下一张卡在启动时重新执行：
   - `git branch --show-current`
   - `git status --short`
   - `git log --oneline --decorate -5`
   - `git worktree list --porcelain`
2. 若 M4-6 worktree 仍存在未提交改动，必须停下来判断：
   - 选项 A：等待用户/人工将 M4-6 变更按项目规则提交/合并到认可基线后，再从该基线创建 M5 分支。
   - 选项 B：若用户明确同意不继承 M4-6 未提交改动，则从 clean 的 `c66ca93` 创建 M5 分支，并把 M4-6 outbox/doc/test 作为只读参考重新纳入 M5 范围。
3. 禁止下一张卡自动 commit M4-6、自动 merge 到 `agent/bp-main`、自动 push 或自动清理 dirty worktree。

候选命令只作为方案，不在 M5-0 执行：

```bash
git worktree add /Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/isp-m5-inventory-nl2sql-integration -b feature/isp-m5-inventory-nl2sql-integration <已确认的干净基线>
```

## 8. M5-1 可执行边界建议

下一张卡：`t_7647fb99` / M5-1：产销存 semantic catalog 注册与 focused tests。

建议状态：可以作为下一张执行卡，但必须带启动门禁；若启动时发现 M4-6 基线仍未明确或目标 worktree/branch 不是 clean 的 `feature/isp-m5-inventory-nl2sql-integration`，应立即 block，不写业务代码。

M5-1 允许范围：

1. 只做 semantic catalog 注册和 focused tests。
2. 指标范围：产量、销量/发货、库存/存货、寄存、预算/目标、预算达成率、版型产量。
3. 维度范围：年份、月份、季度、基地、工厂、版型、生产模式、交易范围。
4. 同义词与业务口径必须遵守 `docs/INVENTORY_SALES_PRODUCTION_NL2SQL_COMPAT_PLAN.md` 与 M4-6 验收样例。
5. 严格 TDD：先写 RED focused tests，确认失败，再实现最小 GREEN。
6. 只查询/注册智能助手中间库语义目录，不接正式用户回答。

M5-1 禁止范围：

1. 不接正式回答链路。
2. 不让 LLM 直接读 Excel。
3. 不把原始宽表作为自由查询表。
4. 不自由生成并执行 SQL。
5. 不修改物流、物管、计划 BOM、功率预测主链路。
6. 不 hardcode 样例答案。

## 9. 风险与处理建议

1. 最大风险：M4-6 验收通过但实际 worktree 仍 dirty/untracked；M5 若从错误基线开分支，可能丢失 M4-6 真实问法回归样例和 planner 修复。
   - 建议：M5-1 启动后第一步复查 M4-6 基线；未解决则 block，请用户选择提交/合并 M4-6 或允许从 clean 基线另起。
2. 分支风险：当前 `feature/isp-m5-inventory-nl2sql-integration` 尚不存在，不能假定 dispatcher 已创建好 worktree。
   - 建议：M5-1 worker 若拿到 unresolved worktree，需要先按 kanban worktree 规则创建，且基线必须明确。
3. 范围风险：M5 是统一 NL2SQL 接入的一部分，不是完整经营分析重构。
   - 建议：M5-1 只做语义目录和测试，不做接管、不做影子对比、不做灰度开关。
4. 安全风险：语义目录/SQLPlan 相关代码容易泄漏内部字段到用户可见回答。
   - 建议：测试中继续断言用户可见回答不出现 SQL、表名、字段名、query_key、planner、guardrail、schema、raw/debug、LLM 等内部词。

## 10. M5-0 结论

M5-0 开工门禁报告已完成。本轮没有修改业务代码，没有创建 M5 分支/worktree，没有 commit、push、deploy、merge。

推荐看板流转：完成 M5-0；下一张卡 `t_7647fb99` 可被依赖链推进，但 M5-1 worker 必须先执行基线/dirty/worktree 门禁。如果 M4-6 dirty 基线仍未解决，应在 M5-1 内立即 block，而不是直接开发。

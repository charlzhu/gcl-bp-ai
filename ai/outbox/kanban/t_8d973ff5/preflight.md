# t_8d973ff5 preflight

生成时间：2026-05-19 17:50:16 CST
状态：BLOCKED / 未进入 gate 执行

## 0. 任务前置结论

本次按看板任务 `t_8d973ff5` 启动后，已先执行只读看板定位、技能/参考资料读取、必读文档抽查和 git preflight。

关键前置冲突仍存在：

1. 任务要求必须在分支 `feature/nl2sql-m9-sqlplan-shadow-mvp` 工作。
2. 任务同时明确禁止 worker 自行切分支。
3. 当前工作区实际分支为 `feature/m15-sap-mid-oracle-smoke-t_2c15aff8`。
4. 本地/远端可见 `*nl2sql-m9*` 分支中没有 `feature/nl2sql-m9-sqlplan-shadow-mvp`，仅有：
   - `feature/nl2sql-m9-1-yearly-mw-breakdown-hardening`
   - `feature/nl2sql-m9-1-yearly-mw-hardening-v2`
5. 现有 worktree `.worktrees/nl2sql-m9-1-hardening-v2` 位于 `feature/nl2sql-m9-1-yearly-mw-hardening-v2`，也不是任务指定分支。

因此，本轮不能安全运行真实 reindex、live provider shadow gate、测试、compile/static scan 或 reviewer；继续执行会违反任务分支约束与 dirty worktree 隔离要求。

## 1. 当前仓库已完成能力判断

只读资料显示：

- 当前仓库已保留物流 NL2SQL M9 shadow MVP 方案文档：`docs/NL2SQL_LOGISTICS_M9_SQLPLAN_GENERATION_SHADOW_MVP_PLAN.md`。
- M9 目标是 shadow-only 的自然语言 → SQLPlan candidate 前半段，不替换正式物流 QA 主链路。
- 项目总规则要求用户问答不得直接查询 SAP Oracle MID，不得让 LLM 自由生成/执行 raw SQL。
- 当前更高层项目阶段文档已转到物管 SAP MID M2 准备；但本看板任务明确限定为 M9 live provider shadow gate 收口，不进入 M10/M2/物管正式开发。

## 2. 当前未完成能力判断

本轮因分支前置冲突，未执行以下能力验证：

- 真实 catalog reindex。
- live provider shadow gate。
- focused/broader NL2SQL tests。
- compile/static scan。
- independent reviewer。
- scoped diff 更新。

因此不能把历史 PASS、其他任务 PASS、provider smoke PASS 或旧验收材料当成本任务最新 PASS。

## 3. 本次任务是否与当前仓库状态一致

不一致。

- 任务要求分支：`feature/nl2sql-m9-sqlplan-shadow-mvp`。
- 当前实际分支：`feature/m15-sap-mid-oracle-smoke-t_2c15aff8`。
- 当前 HEAD：`0b14a71 NL2SQL M9 文档保存`。
- 任务禁止 worker 自行切分支。
- 必读交接材料 `ai/outbox/kanban/t_0b20b27f/{final-acceptance.md,gate-summary.json,scoped-submission-checklist.md}` 当前缺失。

## 4. 本轮允许修改范围

在分支前提满足时，任务允许的 M9 scoped 候选范围包括任务正文列出的 NL2SQL M9 文件、M9 脚本/测试、M9 文档，以及：

- `ai/outbox/kanban/t_8d973ff5/**`
- `ai/outbox/kanban/t_m9_nl2sql_shadow/**`

本轮实际只允许并只执行 blocked handoff 产物更新：

- `ai/outbox/kanban/t_8d973ff5/preflight.md`
- `ai/outbox/kanban/t_8d973ff5/dirty-worktree-audit.txt`
- `ai/outbox/kanban/t_8d973ff5/gate-summary.json`
- `ai/outbox/kanban/t_8d973ff5/final-acceptance.md`

## 5. 本轮禁止修改范围

- 不切分支。
- 不 stash/reset/clean/delete 用户文件。
- 不 stage。
- 不 commit/push/deploy。
- 不查询 SAP Oracle MID。
- 不进入 M10 sidecar 规划。
- 不混入 business_analysis、产销存、SAP MID、前端无关、全局路由等非 M9 dirty 文件。
- 不让 LLM 生成/执行 raw SQL。

## 6. 已执行只读命令摘要

```text
git branch --show-current
=> feature/m15-sap-mid-oracle-smoke-t_2c15aff8

git status --short --branch
=> 当前分支 feature/m15-sap-mid-oracle-smoke-t_2c15aff8，存在多项 tracked/untracked dirty 文件。

git log --oneline -8
=> HEAD 0b14a71 NL2SQL M9 文档保存

git diff --cached --name-status
=> 无 staged 文件

git worktree list --porcelain
=> 主工作区在 feature/m15-sap-mid-oracle-smoke-t_2c15aff8；现有 nl2sql worktree 在 feature/nl2sql-m9-1-yearly-mw-hardening-v2，不是任务指定分支。
```

## 7. 结论

当前应继续 BLOCKED。最小人工处理项：

1. 人工切到或恢复任务指定分支 `feature/nl2sql-m9-sqlplan-shadow-mvp` 后重新运行；或
2. 在看板评论/用户指令中明确授权使用当前分支或指定现有 worktree，并确认该授权覆盖任务正文的“必须分支/不得切分支”冲突；同时
3. 恢复或确认 `t_0b20b27f` 三个缺失交接产物的替代依据。

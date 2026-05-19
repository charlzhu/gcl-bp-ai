# t_3d0c55ce preflight

## 执行位置

- Kanban workspace: `/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai`
- 主工作区当前存在 M15/SAP MID 与其他任务 dirty 文件，不能直接切换或清理。
- 为避免触碰主工作区 dirty 状态，本轮在已存在且 clean 的隔离 worktree 执行：`/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/nl2sql-m9-1-hardening-v2`
- 隔离 worktree 分支：`feature/nl2sql-m9-1-yearly-mw-hardening-v2`
- 隔离 worktree HEAD：`0b14a715eaae5e539b43dcdbd973ed6863bad012`
- `origin/agent/bp-main`：`0b14a715eaae5e539b43dcdbd973ed6863bad012`

说明：任务正文第 2 节要求在 `agent/bp-main` 且 clean 的基线开始；当前主工作区不满足且存在任务外 dirty 文件。为执行用户“work kanban task t_3d0c55ce”的指令，同时避免清理/重置/切换主工作区，本轮只在该 clean feature worktree 上做 M9.1 scoped 修改与验证，不 push、不 commit、不触碰主工作区 dirty 文件。

## 原始检查命令输出

详见同目录 `preflight-current.txt`。

## AGENTS 要求的 5 项判断

1. 当前仓库已完成能力判断：M9 已具备自然语言→SQLPlan shadow MVP 基线；M9 主收口已合并到 `agent/bp-main`，当前任务只针对 live provider shadow gate 的 `m9_success_yearly_mw_breakdown` 稳定性失败加固。
2. 当前未完成能力判断：live provider gate 中该 yearly_mw_breakdown 样例仍可能出现多表无 join、默认时间过滤缺失等 provider drift，导致 validator fail-closed。
3. 本次任务是否与当前仓库状态一致：与隔离 worktree 的 `origin/agent/bp-main` HEAD 一致；与主工作区当前分支/dirty 状态不一致，因此不在主工作区执行。
4. 本轮允许修改范围：仅限任务正文第 5 节列出的物流 NL2SQL M9 相关文件、`tests/unit/logistics/nl2sql/**` 中 focused tests，以及本任务 outbox。
5. 本轮禁止修改范围：不进入 M10；不改 frontend、business_analysis、inventorySalesProduction、BOM、功率预测、物管/SAP MID；不改正式物流 QA 主链路；不修改/清理主工作区 dirty 文件；不 push、不自动 commit、不 clean、不 reset。

## 必读资料检查

已确认存在并读取任务相关资料：

- `AGENTS.md`
- `README_WORKSPACE.md`
- `docs/PLATFORM_OVERALL_ARCHITECTURE_AND_ROADMAP.md`
- `docs/CURRENT_STATUS.md`
- `docs/NEXT_TASK.md`
- `docs/HANDOFF.md`
- `ai/protocols/company_task_protocol.md`
- `ai/company/roles/technical_manager.md`
- `ai/hermes_skills/company-code-builder/SKILL.md`
- `ai/inbox/requirement.md`
- `ai/inbox/attachments_manifest.md`
- `docs/NL2SQL_LOGISTICS_M9_SQLPLAN_GENERATION_SHADOW_MVP_PLAN.md`

本任务不读取或修改附件原始文件，不进入 M2/SAP MID/功率预测/BOM 范围。

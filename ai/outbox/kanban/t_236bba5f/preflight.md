# M10-0 preflight：物流 NL2SQL M9 当前树复核与 M10 启动门禁

- task_id: t_236bba5f
- generated_at: 2026-05-19 23:42:30 CST
- workspace: `/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/nl2sql-m10-preflight-revalidation`
- branch: `feature/nl2sql-m10-preflight-revalidation`
- HEAD: `f24d39ae318cea9af081aa05b3edfdcdcf46ef33`
- 任务定位：只读复核/门禁，不做 M10 代码开发。

## 1. 必读资料检查

已检查任务列出的 17 项资料/目录；缺失项：无。

记录到：`required-reading-presence.json`。

注意：`docs/CURRENT_STATUS.md` / `docs/NEXT_TASK.md` 仍描述物管 SAP MID M2 作为更大项目近期主线；本看板卡是显式指定的物流 NL2SQL M10 启动前 M9 当前树复核门禁，因此本轮按看板卡范围执行，不把 SAP MID M2 扩入本轮。

## 2. 开始工作前 5 项判断

1. 当前仓库已完成能力判断：
   - M9/M9.1 NL2SQL 目录、catalog、测试目录与 provider/reindex/shadow runner 脚本均存在。
   - 当前树 NL2SQL 单测在外部项目 backend venv 下通过：190 passed, 9 warnings。
   - compileall / git diff --check / offline shadow runner / scoped static scan 均通过。
2. 当前未完成能力判断：
   - 当前 worktree 缺 workspace-local `backend/.venv`、缺 `.env` / `backend/.env`，system python 缺 pytest/pydantic/yaml。
   - provider smoke 当前为 BLOCKED，embedding/LLM/rerank 配置缺失。
   - catalog reindex 当前为 disabled/BLOCKED，原因是 embedding unavailable。
   - live-provider shadow gate 当前未通过刷新，recall_failed=1，mismatch=1。
3. 本次任务与当前仓库状态一致性：
   - 分支/worktree 一致：当前在 `feature/nl2sql-m10-preflight-revalidation`，非 main。
   - 门禁结论不一致/不满足：当前环境无法刷新 provider/reindex/live gate，因此不能判定 M10 可启动。
4. 本轮允许修改范围：
   - 仅允许写入 `ai/outbox/kanban/t_236bba5f/` 验收/复核材料。
5. 本轮禁止修改范围：
   - 禁止改源码、正式物流 QA 主链路、前端、BOM、功率预测、物管 SAP、business_analysis。
   - 禁止 stage、commit、push、deploy；禁止 reset/stash/clean/delete 用户文件。

## 3. Git 与环境快照

详见：`preflight-env.log`。

```text
branch=feature/nl2sql-m10-preflight-revalidation
status_short_branch
## feature/nl2sql-m10-preflight-revalidation
?? ai/outbox/kanban/t_236bba5f/
HEAD=f24d39ae318cea9af081aa05b3edfdcdcf46ef33
python3=/usr/local/bin/python3
Python 3.11.9
workspace_backend_venv=missing_or_not_executable
external_project_backend_venv=Python 3.12.7
env_presence root=.env:missing
env_presence backend/.env:missing
staged_changes
tracked_changes
status_short_full
?? ai/outbox/kanban/t_236bba5f/
```

## 4. 当前代码能力存在性

| 路径 | 状态 |
|---|---|
| `backend/app/domains/logistics/services/nl2sql/` | 存在 |
| `backend/app/domains/logistics/config/nl2sql_catalog/` | 存在 |
| `tests/unit/logistics/nl2sql/` | 存在 |
| `scripts/reindex_logistics_nl2sql_catalog.py` | 存在 |
| `scripts/dev/run_logistics_nl2sql_m9_provider_smoke.py` | 存在 |
| `scripts/dev/run_logistics_nl2sql_m9_shadow_sqlplan_generation.py` | 存在 |

## 5. 预检结论

当前树具备 M9/M9.1 shadow 代码与离线门禁基础，但 provider/reindex/live-provider gate 因环境配置缺失未通过刷新。本卡应 BLOCK，而不是将历史 PASS 或离线 runner PASS 当作 M10 启动通过。

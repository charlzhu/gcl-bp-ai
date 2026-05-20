# M10-B preflight

## 当前仓库已完成能力判断

1. 当前工作区：`/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/nl2sql-m10b-shadow-runner-gate`。
2. 当前分支：`feature/nl2sql-m10b-shadow-runner-gate`。
3. 当前 HEAD：`090af2e0e344a1523bc1ae74cfc1d2bc4f2ab779`，与任务卡声明的 M10-A 基线一致。
4. 当前 `git status --short --branch`：`## feature/nl2sql-m10b-shadow-runner-gate...origin/agent/bp-main`，启动时无本任务改动。
5. 已读取项目约束：`AGENTS.md`、`README_WORKSPACE.md`、`docs/PLATFORM_OVERALL_ARCHITECTURE_AND_ROADMAP.md`、`docs/CURRENT_STATUS.md`、`docs/NEXT_TASK.md`、`docs/HANDOFF.md`、`ai/protocols/company_task_protocol.md`、`ai/company/roles/technical_manager.md`、`ai/hermes_skills/company-code-builder/SKILL.md`、`ai/inbox/requirement.md`、`ai/inbox/attachments_manifest.md`。
6. M10-A 已存在 `backend/app/domains/logistics/services/nl2sql/candidate_sql_gate.py`，提供 `LogisticsCandidateSqlGate` 与 `check_logistics_candidate_sql`。
7. 现有 `shadow_pipeline.py` 已串联 SQLPlan validator、renderer、safety、EXPLAIN/trial executor，并只输出 SQL hash 与参数 key。
8. 现有 `m9_sqlplan_generation.py` 已提供自然语言到 SQLPlan 的 shadow runner 与脱敏 artifact/report 输出。

## 当前未完成能力判断

1. `LogisticsNl2SqlShadowPipelineRequest` 尚不能接收 raw candidate SQL。
2. `LogisticsCandidateSqlGate` 尚未在 shadow pipeline 入口处执行。
3. raw candidate SQL 被拒绝时尚未形成“跳过 validator/renderer/safety/executor”的 fail-closed 集成证据。
4. M9 runner/report 尚未显式透出 candidate SQL gate 的 shadow-only 审计摘要。

## 本次任务是否与当前仓库状态一致

一致。当前分支从 M10-A 基线开始，目标是把已存在的 candidate SQL gate 以 shadow-only 方式接入 shadow runner/pipeline，不接正式物流问答主链路。

## 本轮允许修改范围

1. `backend/app/domains/logistics/services/nl2sql/shadow_pipeline.py`
2. `backend/app/domains/logistics/services/nl2sql/m9_sqlplan_generation.py`
3. `backend/app/domains/logistics/services/nl2sql/__init__.py`（如需导出新增字段）
4. `tests/unit/logistics/nl2sql/test_shadow_pipeline.py`
5. `tests/unit/logistics/nl2sql/test_m9_sqlplan_generation.py`
6. 可新增 `tests/unit/logistics/nl2sql/test_m10b_candidate_sql_shadow_gate.py`
7. `ai/outbox/kanban/t_cb150261/` 下验收材料
8. 如 CLI 参数确有必要，可最小修改 `scripts/dev/run_logistics_nl2sql_m9_shadow_sqlplan_generation.py`

## 本轮禁止修改范围

1. 不接正式物流 QA/chat 主链路。
2. 不执行 LLM 自由生成 SQL。
3. 不让 raw candidate SQL 绕过 SQLPlan、renderer、safety。
4. 不读取、输出、提交 `.env` 或密钥。
5. 不修改 frontend、business_analysis、plan_bom、power、material_management、SAP MID、Oracle 相关代码。
6. 不提交 M8 artifact：`ai/outbox/kanban/t_7895e090/m8-shadow-eval-records.jsonl`。
7. 不引入 `ai/outbox/kanban/t_236bba5f/**`。
8. 不合入任务卡列出的其他 feature/hermes 分支。
9. 不 push、不 deploy、不 merge main、不清理 backup、不清理 worktree、不 `git clean`、不 `git reset --hard`。

## TDD/验收口径

1. 先写 RED 测试：raw candidate SQL 被拒绝时不调用 validator/renderer/executor。
2. 再写 allowed 路径测试：gate allowed 后仍只使用受控 SQLPlan 渲染出的 SQL，不使用 raw candidate SQL。
3. 保留兼容测试：未提供 raw candidate SQL 时现有 shadow pipeline 行为不变。
4. 增加脱敏测试：result、evaluation log、report 不保存 candidate SQL 原文及敏感词。
5. 完成后运行任务卡要求的 pytest、compileall、git diff --check，并生成验收材料。

# M10-B final acceptance

## 任务

M10-B：物流 NL2SQL candidate SQL gate 接入 shadow runner。

## 当前仓库已完成能力判断

1. M10-A candidate SQL gate 已在本任务基线 `origin/agent/bp-main@090af2e0e344a1523bc1ae74cfc1d2bc4f2ab779` 上存在。
2. M10-B 已在独立 feature worktree `feature/nl2sql-m10b-shadow-runner-gate` 中完成 shadow-only 集成。
3. shadow pipeline 已可接收可选 `raw_candidate_sql`，并在 SQLPlan validation 之前先运行 gate。
4. M9 shadow runner 已能把样例中的 raw candidate SQL 传入 pipeline，并在 report/records 中输出 gate 摘要统计。
5. 恢复验证阶段补齐了 gate allowed 路径复用入口 gate 结果的保护，避免后续 `_finish` 重复检查同一段 raw SQL。

## 当前未完成能力判断

1. 本轮没有把 M10-B 接入正式物流 QA/chat 主链路。
2. 本轮没有让 LLM 自由生成 SQL 并执行。
3. 本轮没有进入 live takeover、真实数据库执行切换或 M10-C 后续阶段。
4. 本轮没有提交、推送、部署。

## 本次任务是否与当前仓库状态一致

一致。本轮从正确远端 M10-A 基线创建独立 worktree，避开主项目本地 `agent/bp-main` 的未推送异常提交，仅完成 M10-B shadow-only 接入与恢复验证。

## 修改文件清单

1. `backend/app/domains/logistics/services/nl2sql/shadow_pipeline.py`
2. `backend/app/domains/logistics/services/nl2sql/evaluation_log.py`
3. `backend/app/domains/logistics/services/nl2sql/m9_sqlplan_generation.py`
4. `tests/unit/logistics/nl2sql/test_shadow_pipeline.py`
5. `tests/unit/logistics/nl2sql/test_m9_sqlplan_generation.py`
6. `ai/outbox/kanban/t_cb150261/` 验收材料

## 关键改动说明

1. `LogisticsNl2SqlShadowPipelineRequest` 新增 `raw_candidate_sql`，仅用于 shadow gate 审计。
2. `LogisticsNl2SqlShadowPipeline` 新增可注入 `candidate_sql_gate`，默认使用 M10-A 的 `LogisticsCandidateSqlGate`。
3. pipeline 在 SQLPlan validation 前执行 candidate SQL gate：
   - 拒绝时 fail-closed，停在 `candidate_sql_gate` 阶段，不进入 validator/renderer/safety/executor。
   - 允许时继续现有 SQLPlan validator -> renderer -> safety -> executor 链路，但不执行 raw SQL。
   - 允许路径和后续失败路径统一复用入口 gate 结果，不在 `_finish` 中重复 gate check。
4. evaluation log 新增 `candidate_sql_gate_*` 脱敏摘要字段。
5. M9 shadow sample/outcome/report 增加 gate 摘要和统计，raw SQL 字段设置为 `exclude=True`。
6. 单测覆盖拒绝路径、允许路径、gate 结果复用、日志/report 脱敏以及 M9 runner 汇总。

## TDD 证据

1. 初始 RED：新增 raw candidate SQL 字段与 M9 sample 字段前，相关测试因 pydantic extra forbidden 失败，记录在 `red-test.log`。
2. 恢复 RED：`test_shadow_pipeline_reuses_raw_candidate_sql_gate_result_for_allowed_path` 曾失败，证明允许路径会重复调用 gate，记录在 `red-test.log`。
3. GREEN：补齐 `finish_with_gate` 复用后，该 focused test 通过，记录在 `green-focused-test.log`。

## 测试方法与结果

使用解释器：`/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/backend/.venv/bin/python`。

结果：

1. `python -m pytest tests/unit/logistics/nl2sql/test_candidate_sql_gate.py -q`：26 passed。
2. `python -m pytest tests/unit/logistics/nl2sql/test_shadow_pipeline.py -q`：13 passed。
3. `python -m pytest tests/unit/logistics/nl2sql/test_m9_sqlplan_generation.py -q`：27 passed。
4. `python -m pytest tests/unit/logistics/nl2sql -q`：220 passed, 9 warnings。
5. `python -m compileall backend/app/domains/logistics/services/nl2sql -q`：passed。
6. `git diff --check`：passed。
7. task-scoped static scan：passed，added lines scanned 355，findings 0。
8. 独立 review：passed=true，无 security_concerns，无 logic_errors。

日志文件：

- `ai/outbox/kanban/t_cb150261/red-test.log`
- `ai/outbox/kanban/t_cb150261/green-focused-test.log`
- `ai/outbox/kanban/t_cb150261/test.log`
- `ai/outbox/kanban/t_cb150261/compile-static-scan.log`
- `ai/outbox/kanban/t_cb150261/diff.patch`
- `ai/outbox/kanban/t_cb150261/review.md`

## 风险点

1. Kanban worker 因上游 API timeout / protocol violation 多次无法正常完成任务状态，已由主控接管验收。
2. 本轮仍是 shadow-only，不代表可直接切换线上链路。
3. 后续如进入 live takeover，仍需单独任务完成只读库 smoke、灰度、审计与用户可见技术泄露防护验收。
4. 独立 review 建议后续可补 gate.check 异常路径测试；本轮不是阻断项。

## 当前仍未解决的问题

1. 未把 M10-B 提交到 git commit。
2. 未合入 `agent/bp-main`。
3. 未 push。
4. 未进入 M10-C 或正式问答链路接入。

## 是否影响既有能力

1. 物流问答主链路：不影响，本轮未接正式主链路。
2. 计划 BOM：不影响。
3. 功率预测：不影响。
4. 物管/SAP MID/Oracle：不影响。
5. 前端：不影响。

## 是否遵守阶段边界

遵守。本轮只完成 M10-B shadow-only candidate SQL gate 接入与验收恢复。

## 是否未自动 commit / push / deploy

是。当前未 commit、未 push、未 deploy。

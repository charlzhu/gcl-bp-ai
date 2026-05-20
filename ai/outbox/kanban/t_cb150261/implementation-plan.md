# M10-B implementation plan

## 阶段边界

本轮只做物流 NL2SQL shadow-only candidate SQL gate 集成。raw candidate SQL 只作为上游候选文本的安全审计输入，不作为执行 SQL，不进入正式物流 QA/chat 主链路。

## RED 测试计划

1. 在 shadow pipeline 测试中新增拒绝路径：
   - 构造带 raw candidate SQL 的 request。
   - 注入 recording validator/renderer/executor。
   - 断言 gate 拒绝后状态停在 `candidate_sql_gate` 阶段。
   - 断言 validator、renderer、executor 均未被调用。
   - 断言结果和 evaluation log 只包含 reason code、sanitized reason、repair_info，不包含 SQL 原文、password/token/DSN。
2. 在 shadow pipeline 测试中新增允许路径：
   - raw candidate SQL 是允许形态。
   - 仍提供 SQLPlan candidate。
   - 断言 executor 收到的 SQL 来自 renderer 的受控 SQLPlan，而不是 raw candidate SQL。
3. 在 M9 runner 测试中新增 raw candidate SQL 审计摘要：
   - 用样例字段模拟上游 raw candidate SQL。
   - runner 将该值传给 pipeline request。
   - gate 拒绝时 report/records 只展示 gate 状态与 reason，不展示 SQL 原文。

## GREEN 实现计划

1. 扩展 `LogisticsNl2SqlShadowPipelineRequest`：新增 `raw_candidate_sql: str | None = None`。
2. 扩展 `LogisticsNl2SqlShadowPipelineResult`：新增 gate 审计字段，例如 `candidate_sql_gate_allowed`、`candidate_sql_gate_rejected`、`candidate_sql_gate_reason_code`、`candidate_sql_gate_sanitized_reason`、`candidate_sql_gate_repair_info`。
3. 在 `LogisticsNl2SqlShadowPipeline.__init__` 增加可注入 `candidate_sql_gate`，默认使用 `LogisticsCandidateSqlGate`。
4. 在 pipeline `run` 的 SQLPlan validation 前执行 gate：
   - 无 raw candidate SQL：完全保持原行为，gate 字段为空。
   - 有 raw candidate SQL 且 gate 拒绝：构造 fail-closed 结果，写 evaluation log，不进入 validation/render/safety/executor。
   - 有 raw candidate SQL 且 gate 允许：记录 allowed 摘要，然后继续现有 SQLPlan validator -> renderer -> safety -> executor 链路。
5. 扩展 `LogisticsNl2SqlEvaluationLogRecord` 与 `from_pipeline_result`，仅持久化 gate 的稳定审计字段，不保存 raw SQL。
6. 如测试需要，扩展 M9 sample/outcome/report：
   - sample 可携带测试用 `raw_candidate_sql`。
   - runner 传入 shadow pipeline request。
   - outcome/report 汇总 gate allowed/rejected 计数与 reason code。
7. 所有新增/修改函数、参数、安全边界添加中文注释。

## 验证计划

按任务卡要求运行并写入日志：

1. `backend/.venv/bin/python -m pytest tests/unit/logistics/nl2sql/test_candidate_sql_gate.py -q`
2. `backend/.venv/bin/python -m pytest tests/unit/logistics/nl2sql/test_shadow_pipeline.py -q`
3. `backend/.venv/bin/python -m pytest tests/unit/logistics/nl2sql/test_m9_sqlplan_generation.py -q`
4. `backend/.venv/bin/python -m pytest tests/unit/logistics/nl2sql -q`
5. `backend/.venv/bin/python -m compileall backend/app/domains/logistics/services/nl2sql -q`
6. `git diff --check`

## 交付物

1. `ai/outbox/kanban/t_cb150261/preflight.md`
2. `ai/outbox/kanban/t_cb150261/implementation-plan.md`
3. `ai/outbox/kanban/t_cb150261/red-test.log`
4. `ai/outbox/kanban/t_cb150261/test.log`
5. `ai/outbox/kanban/t_cb150261/compile-static-scan.log`
6. `ai/outbox/kanban/t_cb150261/diff.patch`
7. `ai/outbox/kanban/t_cb150261/review.md`
8. `ai/outbox/kanban/t_cb150261/final-acceptance.md`
9. `ai/outbox/kanban/t_cb150261/m10b-gate-integration-summary.json`

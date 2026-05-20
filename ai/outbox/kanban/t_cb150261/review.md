# M10-B review

## 审查结论

通过。最新恢复验证后，本轮改动保持在物流 NL2SQL shadow-only 范围内；未接正式物流 QA/chat 主链路，未引入前端、BOM、功率、物管、Oracle 或经营分析相关改动。

## 代码范围审查

本轮实际修改文件：

1. `backend/app/domains/logistics/services/nl2sql/shadow_pipeline.py`
2. `backend/app/domains/logistics/services/nl2sql/evaluation_log.py`
3. `backend/app/domains/logistics/services/nl2sql/m9_sqlplan_generation.py`
4. `tests/unit/logistics/nl2sql/test_shadow_pipeline.py`
5. `tests/unit/logistics/nl2sql/test_m9_sqlplan_generation.py`

验收材料位于：`ai/outbox/kanban/t_cb150261/`。

## 安全边界审查

1. `raw_candidate_sql` 只作为 M10-B shadow gate 审计输入。
2. gate 拒绝时停在 `candidate_sql_gate` 阶段，并返回 `validation_failed`，不会调用 SQLPlan validator、renderer、safety 或 executor。
3. gate 允许时仍只执行受控 SQLPlan 渲染结果，不使用 raw candidate SQL 文本作为执行 SQL。
4. 入口 gate 结果会在允许路径和后续失败路径复用，避免重复检查同一段 raw SQL；evaluation log 只记录脱敏摘要。
5. evaluation log 新增的 `candidate_sql_gate_*` 字段只保留 allowed/rejected、reason code、脱敏 reason 与 repair_info，不保存 raw SQL 原文。
6. M9 runner 的 sample 字段 `raw_candidate_sql` 设置 `exclude=True`，records/report 仅输出 gate 摘要和统计。
7. 未读取、输出或提交 `.env`、密钥、真实 DSN、账号密码等敏感信息。

## 测试审查

最新复跑验证：

- `test_candidate_sql_gate.py`：26 passed。
- `test_shadow_pipeline.py`：13 passed。
- `test_m9_sqlplan_generation.py`：27 passed。
- `tests/unit/logistics/nl2sql`：220 passed, 9 warnings。
- `compileall backend/app/domains/logistics/services/nl2sql`：passed。
- `git diff --check`：passed。
- task-scoped static scan：passed，added lines scanned 355，findings 0。

详细日志：

- `ai/outbox/kanban/t_cb150261/red-test.log`
- `ai/outbox/kanban/t_cb150261/green-focused-test.log`
- `ai/outbox/kanban/t_cb150261/test.log`
- `ai/outbox/kanban/t_cb150261/compile-static-scan.log`

## 独立 review JSON

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": [],
  "suggestions": [
    "可在后续补充 gate.check 异常路径的回归用例，确保异常也转换为 fail-closed 且只写脱敏摘要；本轮 diff 未发现会导致 raw SQL 执行或泄露的阻断问题。"
  ],
  "summary": "审查通过：diff 显示 raw_candidate_sql 仅用于 shadow gate 审计，拒绝路径在 validator/renderer/safety/executor 前 fail-closed，允许路径仍走 SQLPlan 受控链路，日志与报告仅保存脱敏 gate 摘要，静态扫描和测试日志均通过。"
}
```

## 风险与处置

1. Kanban worker 多次因上游 API timeout / protocol violation 未能正常调用 `kanban_complete`；主控已接管并完成恢复验证。
2. 全量 NL2SQL 测试会改写历史 M8 artifact；本轮已按任务卡允许范围精确恢复 `ai/outbox/kanban/t_7895e090/m8-shadow-eval-records.jsonl`。
3. 当前 feature worktree 保持未 commit、未 push、未 deploy 状态，等待用户后续确认是否提交。

## 结论

M10-B 的 shadow-only candidate SQL gate 接入满足本轮阶段边界；最新恢复修复了允许路径 gate 结果重复检查问题，可以作为待提交/待合入候选。

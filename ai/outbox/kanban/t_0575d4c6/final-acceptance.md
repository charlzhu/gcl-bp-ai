# t_0575d4c6 / M10-D1 Final Acceptance

## 1. 结论

**D1 验收结论：PASS，可收口。**

本轮只完成 M10-D1：物流 NL2SQL fake executor EXPLAIN / readonly trial shadow gate 的 schema、状态枚举、错误码、默认关闭策略、fail-closed 依赖关系与脱敏 report。未进入 D2 的真实库执行、正式 QA 接入、前端接入或 SAP Oracle MID 范围。

## 2. 修改文件清单

### 任务范围代码

1. `backend/app/domains/logistics/services/nl2sql/__init__.py`
2. `backend/app/domains/logistics/services/nl2sql/m10d_shadow_gate.py`
3. `tests/unit/logistics/nl2sql/test_m10d_shadow_gate.py`

### 验收材料

1. `ai/outbox/kanban/t_0575d4c6/diff.patch`
2. `ai/outbox/kanban/t_0575d4c6/test.log`
3. `ai/outbox/kanban/t_0575d4c6/static-scan.json`
4. `ai/outbox/kanban/t_0575d4c6/review_bundle.md`
5. `ai/outbox/kanban/t_0575d4c6/review-result-final.json`
6. `ai/outbox/kanban/t_0575d4c6/git_status.txt`
7. `ai/outbox/kanban/t_0575d4c6/final-acceptance.md`

## 3. 关键改动说明

1. 新增 `LogisticsNl2SqlM10DShadowGateConfig`：
   - 默认 `enabled=False`。
   - 默认 `explain_enabled=False`。
   - 默认 `trial_enabled=False`。
   - `timeout_ms` / `row_cap` 做非负整数收敛。

2. 新增 `LogisticsNl2SqlM10DShadowGateReport`：
   - 输出脱敏审计字段：状态、阶段、错误码、EXPLAIN/trial 状态、行数摘要、timeout/elapsed、SQL hash、reason code、`shadow_only=True`。
   - 禁止输出 SQL 原文、参数值、表名、字段名、连接串、executor 异常原文、trial 行值。

3. 新增 `LogisticsNl2SqlM10DShadowGate`：
   - 默认关闭时不构造 executor、不触库、不 hash SQL。
   - 只允许 `middle_db` 来源；非中间库来源直接跳过。
   - 进入 executor 前重新执行 `LogisticsSqlSafetyChecker` 复核。
   - `trial_enabled=True` 必须依赖 `explain_enabled=True`。
   - EXPLAIN 失败时 fail-closed，并跳过 trial。
   - trial 成功仅返回 `row_count` 与 `row_cap_applied` 摘要。
   - 默认 executor 为 `FakeLogisticsSqlExecutor`，D1 不连接真实数据库。

4. `__init__.py` 增加 M10-D gate 相关导出，不改正式 QA 主链路。

## 4. 测试方法与结果

证据文件：`ai/outbox/kanban/t_0575d4c6/test.log`

1. Focused：
   - 命令：`python -m pytest tests/unit/logistics/nl2sql/test_m10d_shadow_gate.py -q`
   - 结果：`8 passed`

2. Adjacent full NL2SQL unit：
   - 命令：`python -m pytest tests/unit/logistics/nl2sql -q`
   - 结果：`234 passed, 9 warnings`
   - 说明：warnings 为第三方依赖 deprecation warnings，非本轮新增失败。

3. Compile / diff-check：
   - 命令：`python -m py_compile ... && git diff --check ...`
   - 结果：passed。

## 5. 静态扫描结果

证据文件：`ai/outbox/kanban/t_0575d4c6/static-scan.json`

- `blocking_count=0`
- `needs_review_count=0`
- findings：
  - `redaction_logic=1`
  - `test_redaction_probe=8`

说明：扫描命中均为脱敏逻辑和测试负例字符串；未发现真实 hardcoded secret、shell injection、eval/exec、pickle 或 SQL 字符串拼接执行风险。

## 6. 独立 Review 结果

证据文件：`ai/outbox/kanban/t_0575d4c6/review-result-final.json`

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": []
}
```

Reviewer 结论：补丁仅涉及任务范围文件，默认关闭、fake executor、middle_db 边界、EXPLAIN/trial 依赖、安全复核和脱敏报告均符合 M10-D1 要求，未发现阻断性安全或逻辑问题。

非阻塞后续建议：

1. D2/后续阶段可将 `candidate_gate_reason_code` / `safety_reason_code` / executor `error_codes` 进一步收敛为显式白名单枚举。
2. D2/真实执行阶段再补充 timeout 的真实中断语义；D1 fake executor/schema 阶段仅记录 timeout/elapsed 可接受。

## 7. 风险点

1. D1 仍是 fake executor/schema gate，不代表真实数据库 EXPLAIN/trial 已通过。
2. `timeout_ms` 当前只进入脱敏报告，不做真实执行中断；需在 D2 真实只读执行器中实现。
3. reason code 当前通过脱敏短码收敛，后续建议进一步显式枚举白名单。
4. 当前 worktree 存在历史无关 dirty 文件：`ai/outbox/kanban/t_7895e090/m8-shadow-eval-records.jsonl`；不属于本轮任务，不应混入提交。

## 8. 当前仍未解决的问题

1. 尚未实现真实只读 executor。
2. 尚未对真实中间库执行 EXPLAIN / bounded trial。
3. 尚未把 M10-D gate 接入 shadow pipeline 或正式 QA 入口。
4. 尚未生成真实执行阶段的安全审计记录。

上述均属于 D2 或更后续阶段，不阻塞 D1 收口。

## 9. 对既有能力影响判断

- 物流正式问答主链路：未接入，预期无影响。
- 计划 BOM：未修改，预期无影响。
- 功率预测：未修改，预期无影响。
- 前端：未修改，预期无影响。
- SAP Oracle MID / 物管：未修改，预期无影响。

## 10. 阶段边界遵守情况

已遵守 D1 边界：

- 未连接真实数据库。
- 未读取 `.env` 凭据。
- 未输出真实 host/user/password/DSN。
- 未让用户问答直查 SAP Oracle MID。
- 未执行真实 EXPLAIN / trial。
- 未接正式 QA、前端或 SAP/Oracle。
- 未自动进入完整多 Agent、多工具、RAG、经营分析或全域入口。

## 11. 是否自动 commit / push / deploy

- 未自动 commit。
- 未自动 push。
- 未自动 deploy。

如后续需要提交，应只 stage 本轮范围文件和验收材料，不要 `git add -A`。

建议 scoped stage 命令：

```bash
git add backend/app/domains/logistics/services/nl2sql/__init__.py \
  backend/app/domains/logistics/services/nl2sql/m10d_shadow_gate.py \
  tests/unit/logistics/nl2sql/test_m10d_shadow_gate.py \
  ai/outbox/kanban/t_0575d4c6/diff.patch \
  ai/outbox/kanban/t_0575d4c6/test.log \
  ai/outbox/kanban/t_0575d4c6/static-scan.json \
  ai/outbox/kanban/t_0575d4c6/review_bundle.md \
  ai/outbox/kanban/t_0575d4c6/review-result-final.json \
  ai/outbox/kanban/t_0575d4c6/git_status.txt \
  ai/outbox/kanban/t_0575d4c6/final-acceptance.md
```

## 12. 是否建议继续 D2

**建议继续 D2，但需作为新一轮受控任务执行，不在 D1 中自动进入。**

D2 建议目标：在保持默认关闭和 shadow-only 的前提下，接入真实中间库只读 executor / EXPLAIN / bounded trial，并补充真实 timeout、只读连接、审计日志、失败脱敏和 live smoke 证据。D2 仍不得接正式用户问答主链路，除非另行验收确认。

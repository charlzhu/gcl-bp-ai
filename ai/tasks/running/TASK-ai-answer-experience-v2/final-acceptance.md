# AI Answer Experience V2 — final acceptance

## 1. 本轮目标

在已完成的 AI Answer Experience V2 基础上，继续修复“排名类自然语言回答过短/不够专业”的体验问题，并补齐 LLM 流式表达的事实安全校验，确保：

1. 排名/TopN 小表回答更完整，能基于确定性表格逐项复述名称和值；
2. LLM 仍只做表达优化，不允许改状态、表格、卡片、图表或业务事实；
3. LLM 不得新增数字、错配行实体和值、暴露 query_key / SQL / planner / guardrail 等内部信息；
4. 前端主体验仍以自然语言 AI 回答为主，结构化明细保留为二级依据。

## 2. 修改范围

### 代码/测试

- `backend/app/services/business_answer_stream_service.py`
  - 新增/强化公共流式答案表达服务；
  - LLM 不可用或输出不安全时回落到确定性 `presentation.answer`；
  - prompt 采用白名单压缩 + 递归清理内部字段/内部字符串；
  - 数字安全校验改为基于压缩后的 prompt 上下文；
  - 强化行实体-指标值绑定校验，覆盖同句错配、带数字实体、分别句式、多实体单值、`paid_amount` 这类指标字段误判等场景。

- `tests/business_acceptance/test_business_chat_answer_format_preference.py`
  - 补充 AI Answer Experience V2 展示策略与流式安全回归；
  - 覆盖默认 narrative、显式表格/图表/指标卡、前端不固定铺表、stream prompt 不泄露内部字段、非法数字/错配/技术泄露降级等场景；
  - 最终该文件共 `24` 个用例通过。

### 验收材料

- `ai/tasks/running/TASK-ai-answer-experience-v2/diff.patch`
- `ai/tasks/running/TASK-ai-answer-experience-v2/diff-richer-ranking-final.patch`
- `ai/tasks/running/TASK-ai-answer-experience-v2/test.log`
- `ai/tasks/running/TASK-ai-answer-experience-v2/review_bundle_richer_ranking_final.md`
- `ai/tasks/running/TASK-ai-answer-experience-v2/codex_review_richer_ranking_final_prompt.txt`
- `ai/tasks/running/TASK-ai-answer-experience-v2/codex_review_richer_ranking_final_result.json`

## 3. 关键实现说明

### 3.1 排名回答更像专业助手

针对“2024年江苏省各城市总费用排名前五？”这类问题，后端 deterministic presentation 不再只输出一句总计，而是在小表排名结果中逐项复述前五城市和值。例如：

- 徐州：1526425 元；
- 太仓：236305 元；
- 扬州：229064 元；
- 淮安：201100 元；
- 无锡：191499 元。

该内容只来自 `result_table.rows` 的确定性排序，不新增比例、差额、均值或其他推导结论。

### 3.2 流式 LLM 只替换 answer，不改事实结构

`BusinessAnswerStreamService.apply_streamed_answer()` 只写回 `presentation.answer`，并保留：

- `status`；
- `result_table`；
- `presentation.table_spec`；
- `cards` / `chart_spec` 等结构化展示数据。

LLM 输出为空、调用失败、包含非法数字、技术泄露或结构化事实错配时，统一回落到确定性答案。

### 3.3 Prompt 白名单与内部字段清理

发给 LLM 的 payload 只保留表达所需字段，并递归删除：

- `query_key`；
- `query_plan`；
- `group_by`；
- `debug` / `trace`；
- `raw_result`；
- `planner` / `guardrail`；
- `SQL`；
- `ods_` / `dwd_` / `dws_` 等内部数仓表名痕迹。

不仅清理 dict key，也清理 list/string value，避免内部字段混入表头、口径提示或行值后进入 LLM prompt。

### 3.4 数字与行绑定安全

已覆盖以下风险：

- LLM 新增确定性上下文中不存在的数字；
- 数字只存在于 `query_plan` 等内部字段时被误放行；
- “华北 120.5MW”这类实体错配；
- “华南 120.5MW，华东 88.2MW”同句互换；
- “620W 为40%，625W 为60%”带数字实体互换；
- “华南和华东分别为120.5MW和88.2MW”分别句式顺序错配；
- “华东和华南均为120.5MW”多实体绑定同一行值；
- `paid_amount` 因包含 `id` 子串被误判成实体字段。

## 4. 测试结果

详见：`ai/tasks/running/TASK-ai-answer-experience-v2/test.log`

最终结果：

| 验证项 | 结果 |
| --- | --- |
| focused fallback-leak regressions | `2 passed in 0.97s` |
| answer-format acceptance suite | `26 passed in 0.89s` |
| frontend build | 通过，Vite 仅有既有 chunk-size warning |
| full business acceptance | `189 passed, 2 warnings in 21.28s` |
| independent Codex review | `passed=true`，无 blocking security / logic issue |
| static scan | 无真实密钥；无 shell/eval/exec 风险；技术词仅出现在安全规则和测试断言中 |

## 5. 独立 review 结论

### 5.1 richer ranking review

Read-only Codex review 输出：

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": [],
  "suggestions": [
    "Consider validating deterministic fallback text for visible technical leaks before streaming or merging it, even though current deterministic presentation text is expected to be safe.",
    "Remove or wire the unused _has_ambiguous_multi_row_binding_clause helper to avoid drift between intended and active respectively-style safeguards."
  ],
  "summary": "The focused patch preserves deterministic ranking facts, keeps stream fallback limited to answer text, sanitizes prompt context with a whitelist that excludes query_plan/query_key/group_by/internal strings, validates streamed numbers against the compacted prompt context, and conservatively rejects the specified row/value mismatch cases including numeric-looking entities and paid_amount-like metric fields. No blocking security or logic errors found in the reviewed files."
}
```

### 5.2 fallback safety follow-up review

上述两条非阻塞建议已继续处理：

1. `_resolve_fallback_answer()` 现在会对 explicit fallback、`presentation.answer`、`answer_summary`、`status.message` 依次做可见技术字段泄露校验，跳过不安全候选；
2. 删除未使用的 `_has_ambiguous_multi_row_binding_clause` helper，避免代码漂移。

Read-only Codex follow-up review 输出：

```json
{"passed":true,"security_concerns":[],"logic_errors":[],"suggestions":["Consider extending the visible leak denylist in a later hardening pass to catch variants such as query-plan/query plan/queryPlan and guard rail, although the reviewed patch covers the explicit SQL/query_key/planner/guardrail cases in scope."],"summary":"The patch passes the requested fallback-safety review. Deterministic fallback candidates are screened before streaming, leaky fallback/presentation/summary text falls through to status.message when available, and apply_streamed_answer no longer preserves a leaky candidate equal to the original unsafe fallback. Stream merge only updates presentation.answer plus debug metadata and leaves status/result_table/table_spec/cards/chart payloads intact. Active row/entity validation remains covered by the stricter binding logic and targeted tests after removing the unused helper. No real secret or new user-facing SQL/query_key/planner/guardrail leak is introduced in the reviewed files."}
```

Review 结论：通过；当前仅剩一条后续增强建议，即未来可把技术字段 denylist 扩展到 `query-plan` / `query plan` / `queryPlan` / `guard rail` 等变体。

## 6. 风险点与后续建议

1. **fallback 安全校验已补齐**：deterministic fallback 候选会跳过 SQL、`query_key`、planner、数仓表名等可见技术泄露文本；即使 LLM 不可用或调用方直接 merge，也不会把不安全 fallback 原样展示给前端。
2. **未使用 helper 已清理**：`_has_ambiguous_multi_row_binding_clause` 已删除；当前仍由 `_answer_row_bindings_are_safe()` 的实体-指标绑定校验覆盖错配风险。
3. **技术字段变体 denylist**：follow-up review 建议未来可继续扩展到 `query-plan` / `query plan` / `queryPlan` / `guard rail` 等拼写变体；当前范围内的 SQL / `query_key` / planner / guardrail 已覆盖。
4. **Vite chunk-size warning**：构建通过，但仍有大 chunk 警告，这是既有前端体积问题，不影响本次功能验收。
5. **浏览器截图**：已在最终 stream guard 微调前验证过自然语言展示；最终微调只影响不安全 LLM 文本降级，不改变确定性回答和 UI 渲染。

## 7. 是否影响现有能力

- 物流确定性查询：不改变查询事实来源，不改变 repository/service 查询口径。
- 物流流式回答：增强 fallback 和安全校验，非法 LLM 输出会更保守降级。
- 计划 BOM：公共 stream guard 支持 plan_bom 领域；不改变 BOM 计算或查询事实。
- 前端展示：继续保持 narrative 主体验；明细/依据作为次级操作保留。

## 8. 人工处理

- 当前分支：`agent/TASK-ai-answer-experience-v2`。
- 不建议我自动合并到 main。
- 若你认可本轮结果，下一步可人工确认后提交/合并。

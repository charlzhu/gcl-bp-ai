# Query Planning V2 Phase 5.5 Final Acceptance

## 1. 任务范围

本轮进入 Phase 5.5：在线 shadow 对比增强。

目标是在 Phase 5.1–5.4 已有真实日志灰度报表和运营验收门槛基础上，把 formal/shadow 的关键差异摘要直接写入每条 `query_plan_v2_shadow` 快照，便于后续报表、运营看板和人工抽检减少重复解析成本。

## 2. 修改文件

```text
backend/app/domains/query_planning/services/shadow_snapshot_builder.py
backend/app/domains/logistics/services/data_qa_service.py
backend/app/domains/plan_bom/services/qa_service.py
docs/QUERY_PLANNING_V2_PHASE5_GRAY_RELEASE_DESIGN.md
tests/unit/query_planning/test_query_planning_phase5_shadow_compare.py
```

验收材料：

```text
ai/tasks/running/TASK-query-planning-v2-phase55/diff.patch
ai/tasks/running/TASK-query-planning-v2-phase55/test.log
ai/tasks/running/TASK-query-planning-v2-phase55/review-result.json
ai/tasks/running/TASK-query-planning-v2-phase55/final-acceptance.md
```

## 3. 核心实现

### 3.1 `query_plan_v2_shadow.comparison`

新增在线对比摘要：

```json
{
  "schema_version": "query_plan_v2.comparison.v1",
  "domain": "logistics | plan_bom",
  "formal_status": "SUCCESS | CLARIFICATION | UNSUPPORTED | EMPTY_RESULT | ERROR",
  "formal_intent": "...",
  "formal_query_key": "...",
  "formal_result_count": 0,
  "shadow_strategy": "DIRECT_RETRIEVAL | CLARIFY | UNSUPPORTED | NO_ANSWER | QUERY_DECOMPOSITION",
  "shadow_query_key": "...",
  "query_key_matched": true,
  "matched": true,
  "risk_tags": [],
  "guardrail_status": "accepted | rejected | blocked | shadow | missing",
  "shadow_only": true,
  "llm_can_execute": false,
  "sql_generation_allowed": false
}
```

### 3.2 风险标签

当前覆盖：

```text
query_key_mismatch
clarify_boundary_mismatch
unsupported_boundary_mismatch
no_answer_boundary_mismatch
guardrail_blocked
unsafe_execution_policy
```

说明：

- `guardrail_blocked` 只表示存在明确 `blocked_reason` 的安全拦截。
- 业务拒答 / 空结果造成的 `accepted=false` 只显示为 `guardrail_status=rejected`，不误记为安全拦截。
- Plan BOM `EXECUTION_ERROR` 不再被 shadow 误判为 `DIRECT_RETRIEVAL`，而是落到非可执行 `UNSUPPORTED` 策略并通过风险标签暴露差异。

### 3.3 response_meta 轻量摘要

物流 / BOM 历史日志 `response_meta` 新增：

```text
query_plan_v2_compare_matched
query_plan_v2_formal_query_key
query_plan_v2_shadow_query_key
query_plan_v2_risk_tags
```

只暴露轻量对比摘要，不暴露完整 raw payload。

## 4. 安全边界

确认：

1. 不改变物流 Data QA 正式查询结果；
2. 不改变 Plan BOM QA 正式查询结果；
3. 不调用 LLM；
4. 不生成 SQL；
5. 不查业务数据；
6. 不让 shadow 参与正式查询决策；
7. 不恢复临时 token/header；
8. shadow comparison 构建失败时 fail-soft，不向上抛出异常。

## 5. 测试结果

```text
Focused Phase 5.5: 6 passed
Query Planning V2 unit: 34 passed
Full regression: 223 passed, 2 warnings
Compile: PASS
Static scan: PASS
Pyflakes: PASS
Diff check: PASS
Ruff: SKIPPED，当前环境未安装 ruff
```

## 6. 环境说明

全量回归中发现本地 `backend/.venv/bin/python` 存在但无法导入 sqlalchemy/pydantic，导致一个功率模型 schema import 测试失败。
已将未跟踪虚拟环境文件 `backend/.venv/pyvenv.cfg` 的 `include-system-site-packages` 改为 `true`，使其读取 `/opt/anaconda3` 已安装依赖；随后该单测与全量回归通过。
该 venv 配置不纳入本轮 git 提交。

## 7. 影响范围

本轮为 additive metadata 增强：

- `query_plan_v2_shadow.comparison`
- `query_plan_v2_shadow.risk_tags`
- `response_meta` 轻量摘要字段

不会改变正式 `query_result`、`status`、`answer_summary`、`result_table`。

## 8. Review 结论

已完成两轮独立 review：

1. 第一轮无阻塞，提出 C/no_answer/error/guardrail 语义建议，已返工；
2. 第二轮发现 `Any` 未导入导致 pyflakes 阻塞，已补齐并重跑验证通过。

最终无阻塞问题。

## 9. 仍未解决 / 后续建议

建议下一步进入 Phase 5.6：可选响应 meta 暴露。

注意：Phase 5.6 必须默认关闭，并继续沿用生产 fail-closed / 正式权限模块控制，不允许新增临时 token 或 header。

# Query Planning V2 Phase 5.1–5.3 Final Acceptance

## 1. 任务范围

本轮进入 Phase 5.1–5.3，实现 Query Planning V2 的真实日志灰度接入能力：

1. Phase 5.1：从真实 `sys_query_log` 只读读取 `request_payload.query_plan_v2_shadow` 相关日志。
2. Phase 5.2：生成真实日志灰度报表，统计覆盖率、策略分布、query_key 一致性、澄清/拒答一致性和风险桶。
3. Phase 5.3：新增受保护的内部只读接口。

本轮不替换物流 Data QA / Plan BOM QA 主链路，不执行正式查询，不让 LLM 生成 SQL、查数或生成最终业务答案。

## 2. 修改文件

```text
backend/app/api/deps.py
backend/app/domains/logistics/repositories/query_repository.py
backend/app/domains/query_planning/api/endpoints/query_plan_v2.py
backend/app/domains/query_planning/services/shadow_report_service.py
tests/unit/query_planning/test_query_planning_endpoint_registration.py
tests/unit/query_planning/test_query_planning_phase5_gray_log_report.py
ai/tasks/running/TASK-query-planning-v2-phase5/diff.patch
ai/tasks/running/TASK-query-planning-v2-phase5/test.log
ai/tasks/running/TASK-query-planning-v2-phase5/review-result.json
ai/tasks/running/TASK-query-planning-v2-phase5/final-acceptance.md
```

## 3. 关键实现

### 3.1 只读日志仓储

新增：

```text
LogisticsQueryRepository.list_query_logs_for_query_planning_gray(...)
```

特性：

- 只读 `sys_query_log`。
- 支持 `domain=all|logistics|plan_bom`。
- `limit` 强制限制在 `1..500`。
- `days` 强制限制在 `1..365`。
- 查询类型使用绑定参数，不拼接用户输入。
- 不执行 Data QA / BOM QA。

### 3.2 真实日志灰度报表

在 `QueryPlanningV2ShadowReportService` 中新增：

```text
build_log_report(domain="all", limit=200, days=7)
```

输出稳定 JSON：

- `schema_version=query_plan_v2.gray_report.v1`
- `scope`
- `summary`
- `risk_buckets`
- `samples`

统计项包括：

- `total_logs`
- `shadow_available`
- `shadow_missing`
- `corrupt_payload`
- `shadow_coverage_rate`
- `strategy_distribution`
- `status_distribution`
- `domain_distribution`
- `query_key_match_count`
- `query_key_mismatch_count`
- `query_key_match_rate`
- `clarify_agreement_count`
- `unsupported_agreement_count`
- `decomposition_candidate_count`
- `rewrite_candidate_count`
- `hyde_candidate_count`

风险桶包括：

- `missing_shadow`
- `corrupt_payload`
- `query_key_mismatch`
- `clarify_disagreement`
- `unsupported_disagreement`
- `guardrail_blocked`
- `unsafe_execution_policy`

按 reviewer 建议，本轮已补强：

- formal/shadow `query_key` 单侧缺失时也计入 mismatch，避免高估 match rate。
- `/query-planning/v2/shadow-report/logs` 路由依赖测试，确认继续挂内部访问保护。

### 3.3 受保护内部接口

新增：

```text
GET /query-planning/v2/shadow-report/logs?domain=all&limit=200&days=7
```

边界：

- 继续复用 `require_query_planning_internal_access`。
- 生产环境 `APP_ENV=prod` 仍 fail closed，等待正式用户权限模块接管。
- 只读日志，不重新运行 `QueryPlanningV2Service.plan()`。
- 不执行正式 Logistics / Plan BOM QA。
- 不暴露完整 `raw_payload`。

## 4. 测试结果

详见：

```text
ai/tasks/running/TASK-query-planning-v2-phase5/test.log
```

摘要：

```text
Focused Phase 5 + route tests: 5 passed
Query Planning V2 unit regression: 22 passed
Full regression: 204 passed, 2 warnings
Compile: PASS
Static scan: PASS
Ruff: SKIPPED，当前环境未安装 ruff
```

warning 来源：`openpyxl` 读取 xlsm 扩展/条件格式，属于既有非阻断 warning。

## 5. Review 结果

详见：

```text
ai/tasks/running/TASK-query-planning-v2-phase5/review-result.json
```

摘要：

```json
{
  "passed": true,
  "blocker_issues": [],
  "security_concerns": [],
  "logic_errors": []
}
```

独立 reviewer 提出的非阻断建议中，已处理：

1. 补路由级内部保护测试。
2. formal/shadow `query_key` 单侧缺失纳入 mismatch 风险桶。

保留为后续优化：

1. 如果后续从内部诊断扩大到普通用户权限，可继续对 `question_text` / `trace_id` 做更严格脱敏或截断。
2. 若产品要求“只读 `query_plan_v2_shadow`”是字面约束，可进一步调整报表契约；当前实现读取的是 `sys_query_log` 中的正式结果快照元数据，仅用于一致性对比，不暴露 raw payload，不重新执行查询。

## 6. 对现有能力影响

- 不破坏物流 `data-qa` 主链路。
- 不破坏 Plan BOM `qa` 主链路。
- 不让 LLM 直接生成 SQL。
- 不让 LLM 查数。
- 不让 LLM 生成最终业务答案。
- 不替换 Phase 4 默认 10 类 shadow report。
- 新增接口为内部只读灰度报表接口。

## 7. 当前结论

Phase 5.1–5.3 已满足本轮验收标准，可以提交 scoped commit。

# Query Planning V2 Phase 5.4 Final Acceptance

## 1. 任务范围

本轮进入 Phase 5.4：灰度指标门槛与可视化/运营验收。

目标是在 Phase 5.1–5.3 已有真实 `sys_query_log` 只读灰度报表基础上，补充：

1. 自动化运营验收门槛；
2. `PASS` / `WATCH` / `BLOCKED` 判定；
3. 阻断原因和整改建议；
4. chart-ready KPI / 分布图数据；
5. 不暴露完整 `request_payload`；
6. 不改变正式物流 / BOM QA 主链路。

## 2. 修改文件

```text
backend/app/domains/query_planning/services/shadow_report_service.py
docs/QUERY_PLANNING_V2_PHASE5_GRAY_RELEASE_DESIGN.md
tests/unit/query_planning/test_query_planning_phase54_gray_acceptance.py
```

验收材料：

```text
ai/tasks/running/TASK-query-planning-v2-phase54/diff.patch
ai/tasks/running/TASK-query-planning-v2-phase54/test.log
ai/tasks/running/TASK-query-planning-v2-phase54/review-result.json
ai/tasks/running/TASK-query-planning-v2-phase54/final-acceptance.md
```

## 3. 关键实现

### 3.1 acceptance_gate

`QueryPlanningV2GrayLogReport` 新增：

```text
acceptance_gate
```

包含：

- `status`: `PASS` / `WATCH` / `BLOCKED`
- `passed`
- `eligible_for_controlled_rollout`
- `thresholds`
- `checks`
- `blocking_reasons`
- `watch_reasons`
- `recommended_actions`

默认门槛：

```text
shadow_coverage_rate >= 95%
query_key_match_rate >= 98%
clarify_agreement_rate >= 95%
unsupported_agreement_rate >= 95%
corrupt_payload_count <= 0
unsafe_execution_policy_count <= 0
clarify_disagreement_count <= 0
unsupported_disagreement_count <= 0
guardrail_blocked_count <= 0 作为 WATCH 观察项
```

### 3.2 visualization

`QueryPlanningV2GrayLogReport` 新增：

```text
visualization
```

包含：

- KPI 卡片：样本日志数、shadow 覆盖率、query_key 一致率、澄清一致率、拒答/无答案一致率、阻断项数量；
- 图表数据：strategy 分布、domain 分布、正式状态分布、risk bucket 数量；
- `raw_payload` 固定为 `None`，避免报表接口暴露完整原始日志 payload；
- 无可比 `query_key` 时，`query_key_match_rate` KPI 显示 `N/A` / `neutral`，避免和 `acceptance_gate` 的 info 口径冲突。

### 3.3 安全边界

本轮保持：

- 只读真实日志；
- 不调用正式物流/BOM QA；
- 不重新执行 `QueryPlanningV2Service.plan()`；
- 不调用 LLM；
- 不生成 SQL；
- 不生成最终业务答案；
- 不恢复临时 token/header；
- 不替换正式主链路。

## 4. TDD 与 review 返工证据

RED：新增 Phase 5.4 测试后，因 `acceptance_gate` / `visualization` 不存在而失败。

GREEN：实现后通过。

独立 review 通过，无阻塞问题。按非阻塞建议已补强：

1. 无可比 query_key 时 visualization 改为 `N/A` / `neutral`；
2. 补充 guardrail blocked 只进入 WATCH 的测试；
3. 补充 corrupt payload / clarify disagreement 必须 BLOCKED 的测试；
4. 设计文档同步写入 guardrail blocked WATCH 观察口径。

## 5. 验证结果

```text
Focused Phase 5.4: 6 passed
Focused Phase 5.4 + Phase 5.1–5.3: 9 passed
Query Planning V2 unit: 28 passed
Full regression: 215 passed, 2 warnings
Compile: PASS
Static scan: PASS
Diff check: PASS
Ruff: SKIPPED（当前环境未安装 ruff）
```

## 6. 对现有能力影响

确认：

- 不破坏物流 Data QA 主链路；
- 不破坏 Plan BOM QA 主链路；
- 不影响 Phase 4 内置 10 类 shadow report；
- 不影响 Phase 5.1–5.3 真实日志只读汇总接口；
- 新字段为 additive JSON 字段，既有 summary/risk_buckets/samples 保持不变。

## 7. 风险与后续建议

1. 当前 `acceptance_gate` 使用固定默认阈值，后续如需运营可调，应通过正式配置模块或权限模块控制，不要引入临时 token/header。
2. 当前 `visualization` 是后端 chart-ready 数据，尚未新增前端页面；如后续要做可视化 UI，应继续保护内部权限并避免导出完整 payload。
3. `guardrail_blocked_count` 当前作为 WATCH 观察项，不直接阻断；若业务希望更严格，可在后续配置化为 blocker。
4. 下一步可进入 Phase 5.5：在线 shadow 对比增强，进一步把 formal/shadow 差异摘要写入 shadow 快照。

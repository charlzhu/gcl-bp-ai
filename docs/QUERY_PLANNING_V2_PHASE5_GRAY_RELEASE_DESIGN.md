# Query Planning V2 Phase 5 灰度接入设计

> 本文是 Query Planning V2 的 Phase 5 灰度接入设计，不直接修改现有物流 Data QA / Plan BOM QA 主链路。  
> 当前基线：Phase 1/2 审计与设计文档、Phase 3 诊断接口、Phase 4 shadow 日志接入与 10 类 shadow 报表已完成，并已提交为 `[verified] feat: add query planning v2 shadow diagnostics`。

## 1. 目标

Phase 5 的目标不是让 Query Planning V2 立即替代现有规则 planner，而是在真实问法流量中形成**可审计、可回放、可量化的灰度观察闭环**：

1. 对物流与 Plan BOM 正式 QA 请求持续生成 `query_plan_v2_shadow`。
2. 从 `sys_query_log.request_payload.query_plan_v2_shadow` 汇总真实问法覆盖率、策略分布、风险分布。
3. 对比现有正式 `query_plan` / NLU 结果与 Query Planning V2 shadow 结果。
4. 在不改变正式答案的前提下验证 DIRECT / CLARIFY / UNSUPPORTED / DECOMPOSITION / REWRITE / HYDE 的可用边界。
5. 为后续“小范围受控接入”提供数据门槛、回滚策略和验收标准。

## 2. 非目标与安全边界

Phase 5 明确不做以下事项：

1. 不让 LLM 生成 SQL。
2. 不让 LLM 查数。
3. 不让 LLM 生成最终业务答案。
4. 不替换物流 `LogisticsDataQaPlanner`。
5. 不替换 Plan BOM `PlanBomQaService.ask()` 主执行链路。
6. 不把 `HYDE_RETRIEVAL` 文本作为事实答案。
7. 不把 `QUERY_REWRITE_SIMPLIFY` 改写结果覆盖原始问题。
8. 不做自由通用拆分；`QUERY_DECOMPOSITION` 仍必须落到受控白名单 `query_key` / sub plan。
9. 不恢复任何临时 token / 前端 admin token 输入；生产环境访问继续等待正式用户权限模块。
10. 不因 shadow 失败阻断正式 QA 请求。

## 3. 当前可复用基线

### 3.1 已有文档

- `docs/QUERY_PLANNING_V2_CURRENT_AUDIT.md`
- `docs/QUERY_PLANNING_V2_DESIGN.md`

### 3.2 已有后端模块

- `backend/app/domains/query_planning/schemas/query_plan_v2.py`
- `backend/app/domains/query_planning/services/query_planning_v2_service.py`
- `backend/app/domains/query_planning/services/logistics_adapter.py`
- `backend/app/domains/query_planning/services/plan_bom_adapter.py`
- `backend/app/domains/query_planning/services/strategy_router.py`
- `backend/app/domains/query_planning/services/query_plan_v2_audit_writer.py`
- `backend/app/domains/query_planning/services/shadow_snapshot_builder.py`
- `backend/app/domains/query_planning/services/shadow_report_service.py`
- `backend/app/domains/query_planning/api/endpoints/query_plan_v2.py`

### 3.3 已有接口

- `POST /query-planning/v2/diagnose`
- `GET /query-planning/v2/shadow-report`

两者当前均受 `require_query_planning_internal_access` 保护：生产环境 `APP_ENV=prod` 下 fail-closed，等待正式用户权限模块接管。

### 3.4 已有日志接入

Phase 4 已在正式 QA 历史快照中追加：

```json
{
  "query_plan_v2_shadow": {
    "schema_version": "query_plan_v2.shadow_snapshot.v1",
    "domain": "logistics | plan_bom",
    "strategy": "DIRECT_RETRIEVAL | CLARIFY | NO_ANSWER | UNSUPPORTED | QUERY_DECOMPOSITION | QUERY_REWRITE_SIMPLIFY | HYDE_RETRIEVAL",
    "query_key": "...",
    "slots": {},
    "guardrail_decision": {},
    "execution_policy": {
      "shadow_only": true,
      "llm_can_execute": false,
      "sql_generation_allowed": false
    }
  }
}
```

写入位置：`sys_query_log.request_payload.query_plan_v2_shadow`。写入失败沿用现有 try/except + rollback，不阻断正式回答。

## 4. Phase 5 总体架构

```text
业务员问题
  ↓
现有物流 / Plan BOM 正式 QA 主链路
  ↓
正式规则 planner / NLU / repository / service 执行
  ↓
正式答案返回（不被 Phase 5 改写）
  ↓
Query Planning V2 Shadow Snapshot Builder
  ↓
sys_query_log.request_payload.query_plan_v2_shadow
  ↓
Phase 5 Gray Report Service（只读汇总）
  ↓
覆盖率 / 一致性 / 风险 / 候选接入门槛报告
```

核心原则：**先观察，再比较，再小范围灰度，最后才考虑受控接入。**

## 5. 灰度分层

### 5.1 L0：离线/内置样例 shadow

当前 Phase 4 已具备：

- 使用 10 类默认 case 生成 shadow report。
- 不读取真实历史日志。
- 不影响正式 QA。

作用：验证 schema、策略路由、adapter 基本形态。

### 5.2 L1：真实日志只读汇总

新增只读报表，从 `sys_query_log` 中读取最近 N 条物流 / Plan BOM QA 记录，提取：

- 原始问题；
- 正式 domain / status / query_key；
- `query_plan_v2_shadow`；
- response meta 中的 shadow strategy / query_key；
- 正式与 shadow 的差异。

L1 不重新执行 QA、不调用 repository 查数、不调用 LLM，只做历史日志 JSON 汇总。

### 5.3 L2：真实请求在线 shadow 对比

在正式 QA 请求执行后，记录更完整的对比元数据：

- 正式 `query_plan.query_key` vs shadow `query_key`；
- 正式 `needs_clarification` vs shadow `CLARIFY`；
- 正式 `supported=false/status=unsupported/no_answer` vs shadow `UNSUPPORTED/NO_ANSWER`；
- 正式复合计划 vs shadow `QUERY_DECOMPOSITION`；
- 正式 filters / slots 与 shadow slots 差异。

L2 仍不改变正式结果，只增强审计字段。

### 5.4 L3：响应 meta 可选暴露

在非生产或有正式权限的灰度环境中，可通过 feature flag 将 `query_plan_v2_shadow` 的**摘要**加入 QA 响应 meta，便于前端或测试工具展示。

约束：

- 默认关闭。
- 不暴露完整 prompt、LLM 原始输出或敏感 trace。
- 不改变 `answer` / `table` / `status` / `result_table`。
- 仅展示 `strategy`、`query_key`、`guardrail_status`、`shadow_only` 等摘要。

### 5.5 L4：受控策略小步接入候选

只有当 L1-L3 连续通过验收门槛后，才允许讨论 L4。

L4 的候选范围：

1. `DIRECT_RETRIEVAL`：仅当正式 planner 与 shadow planner query_key 一致或 shadow 提供更严格但白名单内的 query_key 时，进入人工确认队列。
2. `CLARIFY`：可优先接入，因为它是 fail-closed 策略；但必须证明不会把可回答问题误拦截。
3. `UNSUPPORTED / NO_ANSWER`：仅作为拒答辅助，不允许覆盖已有可回答路径。
4. `QUERY_REWRITE_SIMPLIFY`：继续只作为检索辅助，不覆盖原始问题。
5. `HYDE_RETRIEVAL`：只允许进入 RAG/语义检索 PoC，不进入结构化 SQL 查询。
6. `QUERY_DECOMPOSITION`：只扩展现有 `composite_decomposed` 白名单，不做自由拆分。

## 6. 报表设计

### 6.1 新增真实日志汇总报表

建议接口：

```text
GET /query-planning/v2/shadow-report/logs?domain=logistics&limit=200&days=7
```

生产环境继续受正式权限模块保护；在正式权限模块完成前，沿用 `APP_ENV=prod -> 403`。

### 6.2 报表输出字段

```json
{
  "schema_version": "query_plan_v2.gray_report.v1",
  "scope": {
    "domain": "logistics | plan_bom | all",
    "days": 7,
    "limit": 200,
    "source": "sys_query_log"
  },
  "summary": {
    "total_logs": 200,
    "shadow_available": 180,
    "shadow_missing": 20,
    "shadow_coverage_rate": 0.9,
    "strategy_distribution": {},
    "status_distribution": {},
    "domain_distribution": {},
    "query_key_match_rate": 0.0,
    "clarify_agreement_rate": 0.0,
    "unsupported_agreement_rate": 0.0,
    "decomposition_candidate_count": 0,
    "rewrite_candidate_count": 0,
    "hyde_candidate_count": 0
  },
  "risk_buckets": {
    "missing_shadow": [],
    "query_key_mismatch": [],
    "clarify_disagreement": [],
    "unsupported_disagreement": [],
    "guardrail_blocked": [],
    "unsafe_execution_policy": []
  },
  "samples": []
}
```

### 6.3 样例记录字段

```json
{
  "log_id": 123,
  "created_at": "2026-05-13T10:00:00",
  "domain": "logistics",
  "question": "2025年各物流公司发运量是多少？",
  "formal_status": "success",
  "formal_query_key": "...",
  "shadow_strategy": "DIRECT_RETRIEVAL",
  "shadow_query_key": "...",
  "query_key_matched": true,
  "guardrail_status": "accepted | shadow | blocked | missing",
  "shadow_only": true,
  "llm_can_execute": false,
  "sql_generation_allowed": false,
  "risk_tags": []
}
```

## 7. 评价指标与接入门槛

### 7.1 必须持续观测的指标

| 指标 | 含义 | 初始门槛 |
| --- | --- | --- |
| shadow 覆盖率 | 有 `query_plan_v2_shadow` 的正式日志比例 | >= 95% |
| unsafe policy 数 | `shadow_only=false` 或允许 LLM SQL/执行 | 必须为 0 |
| query_key 一致率 | DIRECT 类 shadow query_key 与正式 query_key 一致比例 | 先观察，不强制 |
| clarify 一致率 | 正式澄清与 shadow CLARIFY 一致比例 | 接入前 >= 95% |
| unsupported 一致率 | 正式拒答/unsupported 与 shadow 一致比例 | 接入前 >= 95% |
| decomposition 候选数 | 复合拆解候选数量与类型 | 需人工抽检 |
| B/C 边界误改 | shadow 不得把澄清/拒答改成可执行 | 必须为 0 |
| 日志写入失败率 | shadow 写入失败占比 | 不阻断，但需告警 |
| p95 额外耗时 | shadow 构建增加的耗时 | 初期目标 < 30ms（无 LLM） |

### 7.2 接入前人工抽检

每一类策略至少抽检：

1. 物流明确查询。
2. 物流口语化查询。
3. 物流复杂复合查询。
4. 物流缺槽澄清。
5. 物流无答案/unsupported。
6. BOM 单订单查询。
7. BOM 多订单表格。
8. BOM 订单对比。
9. BOM 缺槽澄清。
10. BOM 问法变体鲁棒性。

抽检必须验证：

- 原始问题保留；
- strategy 稳定；
- slots 可解释；
- guardrail 决策完整；
- 不存在 LLM 计算事实值；
- 不存在 SQL 字符串；
- 不存在敏感信息泄露。

## 8. Feature Flag 设计

建议新增配置项（仅设计，Phase 5 实现时再落地）：

```env
QUERY_PLANNING_V2_GRAY_ENABLED=false
QUERY_PLANNING_V2_GRAY_LOG_REPORT_ENABLED=false
QUERY_PLANNING_V2_RESPONSE_META_ENABLED=false
QUERY_PLANNING_V2_GRAY_SAMPLE_RATE=1.0
QUERY_PLANNING_V2_GRAY_MAX_LOGS=500
QUERY_PLANNING_V2_GRAY_ALLOW_LLM=false
```

说明：

- `QUERY_PLANNING_V2_GRAY_ENABLED`：是否生成在线 shadow。
- `QUERY_PLANNING_V2_GRAY_LOG_REPORT_ENABLED`：是否启用真实日志汇总接口。
- `QUERY_PLANNING_V2_RESPONSE_META_ENABLED`：是否在响应 meta 暴露 shadow 摘要。
- `QUERY_PLANNING_V2_GRAY_SAMPLE_RATE`：采样率；默认 1.0 便于测试，生产可降采样。
- `QUERY_PLANNING_V2_GRAY_MAX_LOGS`：报表读取上限，避免大查询。
- `QUERY_PLANNING_V2_GRAY_ALLOW_LLM`：初期必须为 false；未来若启用 HYDE/rewrite 的 LLM 生成，也只能用于 shadow 文本，不得执行。

## 9. 权限与审计

1. 内部接口必须继续使用正式权限模块；正式模块未完成前，生产环境 fail-closed。
2. 不新增临时 token、header 或前端 token 输入。
3. 报表只返回必要摘要；完整原始 payload 仅限后端审计。
4. 对异常文本、trace、LLM 原始内容做脱敏。
5. 所有灰度开关变化需记录操作者、时间、环境与原因。

## 10. 数据与隐私处理

`sys_query_log` 可能包含业务问题、订单号、项目名、客户名等敏感业务信息。Phase 5 报表必须遵守：

1. 默认不导出完整 request payload。
2. 样例问题可展示，但下载/外发前需脱敏。
3. 不展示数据库连接串、token、异常堆栈中的敏感值。
4. 报表样例数量受限，例如每类最多 20 条。
5. 若后续前端展示，仅面向有权限用户。

## 11. 实现拆分建议

### Task 5.1：真实日志读取 repository 方法

**目标**：在不影响现有 query log 写入的前提下，增加只读查询方法。

**建议文件**：

- 修改：`backend/app/domains/logistics/repositories/query_repository.py`
- 测试：`tests/unit/query_planning/test_query_planning_gray_log_report.py`

**要点**：

- 支持 domain / days / limit 过滤。
- limit 必须有上限。
- 只读取必要字段。
- 不改变现有 `write_query_log`。

### Task 5.2：Gray Log Report Service

**目标**：基于真实 `sys_query_log` 构建灰度汇总报表。

**建议文件**：

- 新增或扩展：`backend/app/domains/query_planning/services/shadow_report_service.py`
- 测试：`tests/unit/query_planning/test_query_planning_gray_log_report.py`

**要点**：

- 统计 shadow 覆盖率、策略分布、query_key 一致率。
- 输出风险 buckets。
- 对缺失/损坏 JSON fail-soft，记录风险。
- 不重新执行 QA。

### Task 5.3：只读报表接口

**目标**：新增真实日志汇总接口。

**建议文件**：

- 修改：`backend/app/domains/query_planning/api/endpoints/query_plan_v2.py`
- 修改：`backend/app/api/deps.py`
- 测试：`tests/unit/query_planning/test_query_planning_endpoint_registration.py`

**要点**：

- 路径建议：`GET /query-planning/v2/shadow-report/logs`。
- 继续依赖 `require_query_planning_internal_access`。
- 参数必须有默认 limit 和最大 limit。
- 返回 `ApiResponse.success(...)`。

### Task 5.4：灰度指标门槛与可视化/运营验收

**目标**：在真实日志灰度报表中增加可自动判定的运营门槛、阻断原因、整改建议和 chart-ready 看板数据。

**建议文件**：

- 修改：`backend/app/domains/query_planning/services/shadow_report_service.py`
- 测试：`tests/unit/query_planning/test_query_planning_phase54_gray_acceptance.py`

**要点**：

- 输出 `acceptance_gate`，包含 `PASS` / `WATCH` / `BLOCKED`、阈值、逐项 check、阻断原因和建议动作。
- 初始自动化门槛：shadow 覆盖率 `>=95%`、query_key 一致率 `>=98%`、澄清一致率 `>=95%`、拒答/无答案一致率 `>=95%`、unsafe execution policy / B/C 边界分歧 / 损坏 payload 必须为 `0`。
- `guardrail_blocked_count` 初期作为 `WATCH` 观察项：不直接放行受控接入，需要人工抽检候选是否为合理阻断。
- 输出 `visualization`，包含 KPI 卡片和 `strategy/domain/status/risk_bucket` 分布图数据，供内部运营看板直接消费。
- 继续只读 `sys_query_log`；不重新执行 QA、不调用 LLM、不暴露完整 `request_payload`。

### Task 5.5：在线 shadow 对比增强

**目标**：增强 `query_plan_v2_shadow`，记录正式 query_plan 与 shadow 的差异摘要。

**建议文件**：

- 修改：`backend/app/domains/query_planning/services/shadow_snapshot_builder.py`
- 修改：`backend/app/domains/logistics/services/data_qa_service.py`
- 修改：`backend/app/domains/plan_bom/services/qa_service.py`
- 测试：`tests/unit/query_planning/test_query_planning_phase5_shadow_compare.py`

**要点**：

- 只新增审计字段，不改变正式结果。
- 对比字段包括 `formal_status`、`formal_intent`、`formal_query_key`、`formal_result_count`、`shadow_strategy`、`shadow_query_key`、`query_key_matched`、`matched`、`risk_tags`、`guardrail_status` 和安全开关摘要。
- `risk_tags` 至少覆盖 `query_key_mismatch`、`clarify_boundary_mismatch`、`unsupported_boundary_mismatch`、`no_answer_boundary_mismatch`、`guardrail_blocked`、`unsafe_execution_policy`。
- `guardrail_blocked` 只表示存在明确 `blocked_reason` 的安全拦截；业务拒答/空结果等 `accepted=false` 不应被误记为安全拦截。
- `response_meta` 只暴露轻量摘要字段：`query_plan_v2_compare_matched`、`query_plan_v2_formal_query_key`、`query_plan_v2_shadow_query_key`、`query_plan_v2_risk_tags`。
- 构建失败不阻断主链路，最多导致历史 shadow 日志写入失败或返回 `log_id=0`。
- 不重新执行物流 Data QA / Plan BOM QA，不调用 LLM，不生成 SQL。

### Task 5.6：可选响应 meta 暴露

**目标**：在非生产/授权环境中通过 feature flag 暴露 shadow 摘要。

**建议文件**：

- 修改：物流/BOM response meta 构造位置。
- 测试：新增 response meta flag 测试。

**要点**：

- 默认关闭。
- 不暴露完整 trace。
- 不改变 `answer`、`status`、`table`。
- 生产环境需正式权限和开关双重控制。

### Task 5.7：验收材料

**目标**：形成可审计交付。

**建议产物**：

- `ai/tasks/running/TASK-query-planning-v2-phase5/test.log`
- `ai/tasks/running/TASK-query-planning-v2-phase5/diff.patch`
- `ai/tasks/running/TASK-query-planning-v2-phase5/final-acceptance.md`

## 12. 测试策略

### 12.1 RED/GREEN 单元测试

新增测试应覆盖：

1. 真实日志缺少 shadow 时计入 `missing_shadow`。
2. shadow JSON 损坏时 fail-soft 并计入风险。
3. unsafe execution policy 被标记为风险。
4. DIRECT query_key 一致/不一致统计正确。
5. CLARIFY agreement 统计正确。
6. UNSUPPORTED / NO_ANSWER agreement 统计正确。
7. report limit 上限生效。
8. 生产环境接口仍 403。
9. 非生产环境接口可调用。
10. shadow builder 异常不阻断正式 QA。

### 12.2 回归测试

每次 Phase 5 实现必须至少运行：

```bash
python -m pytest tests/unit/query_planning -q
python -m pytest tests/business_acceptance/test_plan_power_m2_model_versioning.py::test_plan_power_write_access_allows_non_prod_and_blocks_prod_until_user_permission_module -q
python -m pytest tests -q
```

如修改前端展示，再补充：

```bash
npm run build
```

### 12.3 静态安全扫描

扫描新增 diff 行：

- hardcoded secret / token / password；
- shell injection；
- eval/exec；
- pickle；
- SQL 字符串拼接；
- 临时 token/header 复活；
- raw SQL / LLM SQL 执行通路。

## 13. 灰度验收标准

Phase 5 设计进入实现后，验收标准如下：

1. 不破坏现有物流 Data QA 主链路。
2. 不破坏现有 Plan BOM QA 主链路。
3. 生产环境内部接口仍 fail-closed 或接入正式权限模块。
4. `query_plan_v2_shadow` 覆盖率可统计。
5. 报表从真实 `sys_query_log` 读取，不重新查数。
6. 报表能识别 missing shadow、query_key mismatch、clarify disagreement、unsupported disagreement、unsafe policy。
7. 所有 LLM 相关字段仍不可执行。
8. `HYDE_RETRIEVAL` 与 `QUERY_REWRITE_SIMPLIFY` 仍只作为 shadow/辅助，不影响正式答案。
9. `QUERY_DECOMPOSITION` 仍受白名单与 guardrail 约束。
10. 新增测试通过，并有 `test.log` / `diff.patch` / `final-acceptance.md`。

## 14. 回滚策略

1. 关闭 `QUERY_PLANNING_V2_GRAY_ENABLED`。
2. 关闭 `QUERY_PLANNING_V2_RESPONSE_META_ENABLED`。
3. 保留既有正式 QA 主链路不变。
4. 如报表接口异常，关闭 `QUERY_PLANNING_V2_GRAY_LOG_REPORT_ENABLED` 或回退对应 commit。
5. 如 shadow 写入导致 DB session 异常，保留当前 fail-soft 策略，并优先回退 shadow builder 接入点。
6. 不需要数据迁移回滚，因为 Phase 5 初期不新增数据库表；历史 JSON payload 可保留为审计数据。

## 15. 建议执行顺序

1. 先实现 L1：真实日志只读汇总报表。
2. 再实现 L2：正式 plan 与 shadow plan 的差异摘要。
3. 再考虑 L3：非生产响应 meta 摘要展示。
4. 最后基于连续灰度报告讨论 L4：部分策略受控接入。

建议下一轮正式开发只做：

```text
Phase 5.1 + Phase 5.2 + Phase 5.3
```

即：真实日志读取、灰度汇总服务、只读报表接口。暂不做响应 meta 暴露，暂不做正式策略接入。

## 16. 技术经理结论

当前最稳妥的 Phase 5 路线是：

```text
不替换主链路
不新增 LLM 执行权
不恢复临时 token
不让 HYDE/Rewrite 进入结构化 SQL
先基于 sys_query_log 做真实 shadow 报表
用连续数据决定是否进入小范围受控接入
```

因此，下一步应优先开发“真实日志灰度报表”，而不是直接让 Query Planning V2 参与正式查询决策。

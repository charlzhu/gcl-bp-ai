# NQE-SQL-MAIN-4：LangGraph SQL Agent 主流程设计

## 0. 文档边界

本文是 NQE 统一 SQL Agent 正式主链路替换任务的第四张设计卡交付物。

本卡性质：

```text
只读设计卡；不写业务代码；不改前端；不新增数据库迁移；不创建真实表；不调用编码代理；不替换正式链路。
```

本卡事实源：

1. `ai/inbox/Hermes_NQE_统一SQLAgent最终执行指令_修正版.md`
2. `ai/inbox/NQE_统一SQLAgent正式主链路替换_最终报告_修正版.md`
3. `docs/NQE_SQL_MAIN_1_MAIN_LINK_DESIGN.md`
4. `docs/NQE_SQL_MAIN_2_METADATA_KB_DESIGN.md`
5. `docs/NQE_SQL_MAIN_3_RETRIEVAL_DESIGN.md`
6. `docs/NQE_SQL_MAIN_SAFETY_BOUNDARY.md`
7. 当前仓库 Graph、节点、服务、API 只读审计结果

明确排除：

1. `docs/CURRENT_STATUS.md`
2. `docs/NEXT_TASK.md`
3. `docs/HANDOFF.md`

上述三份通用状态文件当前记录物管 / SAP MID 并行任务，只读用于冲突判断，不作为 NQE 需求依据，也不得被本任务覆盖。

---

## 1. 当前仓库能力判断

### 1.1 已完成能力

只读审计确认当前仓库已经具备以下可复用基础：

1. 已有统一 Graph 原型，主流程覆盖接收问题、领域路由、关键词抽取、字段召回、指标召回、字段取值召回、合并、过滤、上下文补充、SQL 生成、SQL 验证、SQL 修正、SQL 执行。
2. Graph 已使用 LangGraph `StateGraph` 形式组织节点，具备后续迁移为 NQE 主流程的技术基础。
3. 已有状态对象雏形，可承载 `question`、`domain_hint`、`trace_id`、`trace`、`domain`、`capabilities`、`execution_result` 等字段。
4. 已有领域路由节点，支持关键词快速路由和语义兜底路由。
5. 已有流式服务雏形，可以监听节点生命周期并向前端输出进度事件。
6. 已有 SQL 生成、校验、修正、执行节点雏形，且当前主路线已经是 LLM 直接生成 SQL，而不是 SQLPlan 中间层。

### 1.2 未完成能力

当前仓库与 NQE 正式主流程仍有明显差距：

1. Graph、API、服务和节点命名仍属于历史原型，不是正式 NQE 命名。
2. 当前 Graph 只有字段 / 指标 / 取值三路召回，尚未承接 NQE-SQL-MAIN-3 的多路召回上下文包。
3. 当前 SQL 验证节点以 EXPLAIN 为主，缺少 EXPLAIN 前的确定性 SQL 安全预检节点。
4. 当前无完整的 `nqe_query_trace` / `nqe_query_trace_step` / `nqe_sql_revision` / `nqe_shadow_compare` 写入链路。
5. 当前 state 缺少 NQE 所需的灰度模式、元数据版本、prompt 版本、安全预检结果、SQL 修订轮次、fallback 状态、shadow compare 结果等字段。
6. 当前服务层进度事件仍偏原型命名，未形成 NQE 统一事件协议。
7. 当前 execute 节点在无数据库连接时会返回 SQL 生成占位说明；NQE 正式链路用户可见输出不得暴露 SQL 片段。
8. 当前 correct loop 的安全边界不够明确，修正后的 SQL 必须重新经过安全预检和 EXPLAIN。
9. 当前四域灰度 off / shadow / assist / on 还没有在 Graph 分支中显式建模。
10. 当前旧链路 fallback、replay、shadow compare 只停留在设计层，尚未成为 Graph 的显式分支。

### 1.3 本次任务与当前状态是否一致

一致。本卡只输出主流程设计，不修改代码。重点是把 NQE-SQL-MAIN-1 的主链路和 NQE-SQL-MAIN-3 的召回上下文包细化为：

1. Graph 节点清单。
2. 节点输入输出。
3. State 字段设计。
4. 条件路由和终态。
5. SQL 安全预检位置。
6. correct loop 与 SQL revision。
7. 灰度模式分支。
8. trace / streaming / replay / shadow compare 挂载点。
9. 后续编码卡 scoped 文件范围和验收标准。

### 1.4 本轮允许修改范围

仅允许新增或更新 NQE 独立文档：

1. `docs/NQE_SQL_MAIN_4_GRAPH_FLOW_DESIGN.md`
2. `docs/NQE_SQL_MAIN_CURRENT_STATUS.md`
3. `docs/NQE_SQL_MAIN_NEXT_TASK.md`
4. `docs/NQE_SQL_MAIN_HANDOFF.md`

### 1.5 本轮禁止修改范围

1. 不修改 `backend/` 业务代码。
2. 不修改 `frontend/` 代码。
3. 不新增 Alembic 迁移。
4. 不创建真实数据库表。
5. 不调用编码代理。
6. 不改正式问答链路。
7. 不覆盖物管 / SAP MID 的三份通用状态文件。
8. 不写入真实密钥、连接串、账号、Token 或内部凭证。

---

## 2. NQE Graph 总体设计结论

NQE 正式主流程建议采用单 Graph + 明确分支的方式，不再维持“多个业务域各自一套问答主链路”的长期形态。

目标主流程：

```text
receive_query
  ↓
init_trace_and_mode
  ↓
route_domain_and_capability
  ↓
normalize_query
  ↓
retrieve_context_multiway
  ↓
merge_rank_and_build_context
  ↓
check_context_readiness
  ↓
generate_sql_direct
  ↓
precheck_sql_safety
  ↓
explain_validate_sql
  ↓
correct_sql_loop ≤ 2
  ↓
execute_sql_readonly
  ↓
present_business_answer
  ↓
record_query_log_and_trace
  ↓
END
```

并行分支：

```text
shadow mode:
  同步执行旧链路与 NQE 链路 → shadow_compare → 用户仍看旧链路结果

assist mode:
  NQE 输出理解 / 召回 / 候选 → 旧链路可使用这些上下文 → 用户看旧链路或混合结果

on mode:
  NQE 优先输出 → 安全失败 / 低置信 / 执行失败时 fallback 到旧链路

off mode:
  不进入 NQE 执行链路，直接旧链路
```

核心原则：

1. LLM 只负责理解、召回辅助、SQL 文本生成、错误修正和答案表达辅助。
2. 后端确定性代码负责元数据白名单、安全预检、EXPLAIN、只读执行、trace、fallback 和灰度开关。
3. SQL 安全预检必须位于 SQL 生成后、EXPLAIN 前。
4. 安全预检失败时不得进入 EXPLAIN，也不得直接执行。
5. 修正后的 SQL 必须重新进入安全预检，再进入 EXPLAIN。
6. 用户可见回答不得展示 SQL、表名、字段名、query_key、planner、guardrail、schema、raw/debug、LLM、prompt、trace 原文。
7. trace 内部可记录脱敏 SQL 和资产 ID，用于审计、replay、shadow compare，但必须脱敏、截断、权限隔离。

---

## 3. Graph 节点清单

### 3.1 主流程节点总表

| 序号 | 节点名 | 类型 | 主要职责 | 失败分支 |
|---:|---|---|---|---|
| 1 | `receive_query` | 入口 | 接收问题、校验空值和长度、生成 trace_id | `terminal_error` |
| 2 | `init_trace_and_mode` | 初始化 | 写入灰度模式、入口来源、元数据版本、prompt 版本 | `terminal_error` |
| 3 | `route_domain_and_capability` | 路由 | 识别业务域和能力，校验域是否开放 | `terminal_clarify` / `legacy_fallback` |
| 4 | `normalize_query` | 理解 | 标准化问题、提取关键词、时间词、实体词、指标词 | `terminal_clarify` |
| 5 | `retrieve_context_multiway` | 召回 | 调用 NQE 多路召回，输出候选集合 | `legacy_fallback` / `terminal_clarify` |
| 6 | `merge_rank_and_build_context` | 上下文 | 合并、排序、裁剪并构造 `RetrievalContextPackage` | `legacy_fallback` / `terminal_clarify` |
| 7 | `check_context_readiness` | 门禁 | 检查表、字段、指标、join、时间、取值是否足够生成 SQL | `terminal_clarify` / `legacy_fallback` |
| 8 | `generate_sql_direct` | 生成 | 基于上下文包让 LLM 直接生成单条 SQL | `terminal_error` / `legacy_fallback` |
| 9 | `precheck_sql_safety` | 安全 | 单语句、只读、白名单、系统库、危险函数、LIMIT、字段等预检 | `terminal_safety_reject` / `legacy_fallback` |
| 10 | `explain_validate_sql` | 校验 | 对安全通过的 SQL 做 EXPLAIN / 语法 / 执行计划校验 | `correct_sql` / `terminal_error` |
| 11 | `correct_sql` | 修正 | 基于脱敏错误和上下文修正 SQL，最多 2 次 | `precheck_sql_safety` / `terminal_error` |
| 12 | `execute_sql_readonly` | 执行 | 使用只读连接、超时、行数上限执行 SQL | `legacy_fallback` / `terminal_error` |
| 13 | `present_business_answer` | 表达 | 业务化摘要、结果表、指标卡、澄清或缺数据说明 | `terminal_error` |
| 14 | `record_query_log_and_trace` | 审计 | 记录 trace、query log、SQL revision、结果摘要 | `END` |
| 15 | `legacy_fallback` | 兜底 | 调用本域旧链路并记录 fallback 原因 | `present_business_answer` / `terminal_error` |
| 16 | `shadow_compare` | 对比 | shadow 模式下对比旧链路与 NQE 输出 | `record_query_log_and_trace` |
| 17 | `terminal_clarify` | 终态 | 返回业务化澄清问题 | `record_query_log_and_trace` |
| 18 | `terminal_safety_reject` | 终态 | 返回业务化安全拒绝或不支持说明 | `record_query_log_and_trace` |
| 19 | `terminal_error` | 终态 | 返回业务化失败说明，隐藏内部错误 | `record_query_log_and_trace` |

### 3.2 设计取舍

1. `receive_query` 与 `init_trace_and_mode` 分开，避免入口校验和灰度策略混在一起。
2. `route_domain_and_capability` 必须早于召回，避免跨域召回扩大 Prompt。
3. `normalize_query` 输出仅是候选理解，不直接决定 SQL。
4. `retrieve_context_multiway` 与 `merge_rank_and_build_context` 分开，便于 trace 分析每一路召回质量。
5. `check_context_readiness` 是 SQL 生成前门禁，用来阻止缺表、缺字段、缺 join、指标口径不完整时让 LLM 猜测。
6. `precheck_sql_safety` 必须在 `explain_validate_sql` 前。
7. `correct_sql` 不得绕过安全预检，必须回到 `precheck_sql_safety`。
8. `record_query_log_and_trace` 是统一尾节点，所有成功、失败、澄清、fallback 都必须经过。

---

## 4. NQE State 设计

NQE Graph state 建议分为九类字段。

### 4.1 请求上下文

| 字段 | 含义 |
|---|---|
| `question` | 用户原始问题 |
| `normalized_question` | 规范化问题 |
| `domain_hint` | 前端或上游传入的业务域提示 |
| `client_context` | 前端入口、会话、页面域、业务模式等非敏感上下文 |
| `user_context` | 用户角色、组织、权限摘要，不写密钥 |
| `trace_id` | 查询追踪号 |

### 4.2 运行模式

| 字段 | 含义 |
|---|---|
| `nqe_mode` | off / shadow / assist / on |
| `domain_mode` | 当前业务域的灰度模式 |
| `fallback_policy` | 低置信、错误、安全失败、超时等场景是否 fallback |
| `graph_version` | NQE Graph 版本 |
| `metadata_version_id` | 元数据版本 |
| `prompt_version_id` | Prompt 版本 |

### 4.3 领域与理解

| 字段 | 含义 |
|---|---|
| `selected_domain` | 选中业务域 |
| `domain_candidates` | 候选业务域及置信度 |
| `selected_capability` | 选中能力 |
| `capability_candidates` | 候选能力 |
| `intent_hints` | 明细、汇总、对比、趋势、排名、预测入口等意图候选 |
| `keyword_terms` | 关键词 |
| `entity_terms` | 实体词 |
| `metric_terms` | 指标词 |
| `time_terms` | 时间词 |
| `compare_terms` | 对比对象 |

### 4.4 召回上下文

| 字段 | 含义 |
|---|---|
| `retrieval_query` | NQE-SQL-MAIN-3 定义的标准化召回查询 |
| `retrieval_candidates` | 各路召回候选集合 |
| `retrieval_context_package` | 最终进入 SQL 生成的上下文包 |
| `context_readiness` | 上下文是否足以生成 SQL |
| `clarification_hints` | 需要澄清的问题候选 |
| `fallback_hints` | 触发 fallback 的原因 |

### 4.5 SQL 生命周期

| 字段 | 含义 |
|---|---|
| `generated_sql` | 生成 SQL，内部字段，不可用户可见 |
| `sql_revision_id` | 当前 SQL 修订 ID |
| `sql_revision_round` | 当前修正轮次 |
| `sql_safety_result` | 安全预检结果 |
| `explain_result` | EXPLAIN 校验结果摘要 |
| `sql_error_sanitized` | 脱敏后的 SQL 错误摘要 |
| `max_correction_rounds` | 最大修正轮次，建议 2 |

### 4.6 执行结果

| 字段 | 含义 |
|---|---|
| `execution_status` | NOT_STARTED / EXECUTED / EXECUTION_ERROR / SKIPPED |
| `execution_result_internal` | 内部执行结果，包含列名、行数、耗时等 |
| `execution_result_public` | 用户可见结果模型，使用业务化列名和摘要 |
| `row_count` | 返回行数 |
| `latency_ms` | 执行耗时 |
| `result_truncated` | 是否截断 |

### 4.7 旧链路与灰度

| 字段 | 含义 |
|---|---|
| `legacy_result` | 旧链路结果摘要 |
| `fallback_used` | 是否使用 fallback |
| `fallback_reason` | fallback 原因 |
| `shadow_result` | shadow 模式下 NQE 结果摘要 |
| `shadow_compare_result` | 新旧链路差异摘要 |

### 4.8 用户可见输出

| 字段 | 含义 |
|---|---|
| `answer_summary` | 业务化答案摘要 |
| `result_table` | 业务化结果表 |
| `metric_cards` | 指标卡 |
| `chart_suggestions` | 图表建议 |
| `warnings` | 业务化提醒 |
| `clarification` | 澄清问题 |
| `public_trace_id` | 可给用户报障用的 trace_id，不暴露内部 trace |

### 4.9 Trace 与审计

| 字段 | 含义 |
|---|---|
| `trace_steps` | 内部 trace step 摘要 |
| `query_log_id` | 查询日志 ID |
| `audit_warnings` | 内部审计告警 |
| `replay_snapshot_ref` | replay 所需快照引用 |

---

## 5. 条件路由设计

### 5.1 入口模式路由

```text
receive_query → init_trace_and_mode

if nqe_mode == off:
  → legacy_fallback
else:
  → route_domain_and_capability
```

规则：

1. `off` 模式不得执行 NQE SQL 链路。
2. `shadow`、`assist`、`on` 才允许进入 NQE Graph 主体。
3. 每个业务域可以有独立模式，不能全域一次性切到 `on`。

### 5.2 领域路由后分支

```text
route_domain_and_capability

if domain unsupported:
  → terminal_clarify
if domain disabled:
  → legacy_fallback
if confidence low:
  → terminal_clarify
else:
  → normalize_query
```

规则：

1. `domain_hint` 可以提高置信度，但不能绕过该域是否启用的检查。
2. 功率预测仍是计划 BOM 子能力，不新建独立业务域。
3. 物管 / SAP MID 当前并行状态文件不得影响 NQE 领域判定。

### 5.3 召回与上下文门禁分支

```text
retrieve_context_multiway → merge_rank_and_build_context → check_context_readiness

if missing_table or missing_column:
  → legacy_fallback or terminal_clarify
if metric_definition_missing:
  → terminal_clarify
if join_required_but_not_registered:
  → legacy_fallback or terminal_clarify
if value_ambiguous:
  → terminal_clarify
else:
  → generate_sql_direct
```

规则：

1. 缺表、缺字段、缺指标口径时不得让 LLM 猜测。
2. 需要多表但未登记 join 时不得生成跨表 SQL。
3. 字段取值多候选无法消歧时优先澄清。
4. 召回上下文不足时，`on` 模式也必须 fallback 或澄清。

### 5.4 SQL 生命周期分支

```text
generate_sql_direct
  → precheck_sql_safety
  → explain_validate_sql

if safety_fail:
  → terminal_safety_reject or legacy_fallback
if explain_fail and revision_round < max:
  → correct_sql → precheck_sql_safety
if explain_fail and revision_round >= max:
  → terminal_error or legacy_fallback
if explain_ok:
  → execute_sql_readonly
```

规则：

1. 安全预检失败不能进入 EXPLAIN。
2. 安全预检失败不能交给 LLM 绕过规则后直接执行。
3. correct loop 最大建议 2 次。
4. 每次 SQL 修正都要写入 `nqe_sql_revision`。
5. 修正 SQL 必须重新走安全预检和 EXPLAIN。

### 5.5 执行后分支

```text
execute_sql_readonly

if execution_ok:
  → present_business_answer
if timeout or db_error:
  → legacy_fallback or terminal_error
if result_empty:
  → present_business_answer with business empty explanation
```

规则：

1. 执行必须使用只读连接或只读事务。
2. 明细和聚合结果都必须有行数、体积和超时限制。
3. 空结果不是系统错误，应返回业务化空结果说明。
4. 数据库错误必须脱敏后进入 trace，用户不可见原始错误。

### 5.6 shadow / assist / on 分支

| 模式 | NQE 行为 | 旧链路行为 | 用户看到 |
|---|---|---|---|
| off | 不执行 | 执行 | 旧链路结果 |
| shadow | 后台执行并 trace | 执行 | 旧链路结果 |
| assist | 执行理解/召回/候选，可辅助旧链路 | 执行 | 旧链路或混合业务结果 |
| on | 优先执行 | 仅在 fallback 时执行 | NQE 结果或 fallback 结果 |

shadow 模式流程：

```text
旧链路结果 → 用户可见
NQE 结果 → 内部 trace
旧链路结果 + NQE 结果 → shadow_compare → 质量门禁
```

assist 模式流程：

```text
NQE route / normalize / retrieve / context
  ↓
旧链路可读取业务化候选或约束
  ↓
旧链路执行并输出
```

on 模式流程：

```text
NQE 主链路成功 → 用户看 NQE 业务化结果
NQE 主链路失败且允许 fallback → 用户看旧链路业务化结果 + 温和提示
NQE 安全拒绝且不允许 fallback → 用户看不支持 / 需补充条件
```

---

## 6. 节点级输入输出设计

### 6.1 `receive_query`

输入：

1. `question`
2. `domain_hint`
3. `mode`
4. `trace_id`
5. `client_context`

输出：

1. 标准化后的 `question`
2. `trace_id`
3. `status=RECEIVED`
4. `trace_steps += receive_query`

失败：

1. 空问题：`terminal_clarify`
2. 超长问题：`terminal_clarify`
3. 输入包含明显敏感凭证：`terminal_safety_reject`

### 6.2 `init_trace_and_mode`

输入：

1. 入口上下文。
2. 业务域 hint。
3. 当前灰度配置。

输出：

1. `nqe_mode`
2. `domain_mode`
3. `metadata_version_id`
4. `prompt_version_id`
5. `fallback_policy`
6. `query_log_id` 初始记录

失败：

1. 灰度配置缺失：默认 `off`。
2. 元数据版本不可用：`legacy_fallback` 或 `terminal_error`。

### 6.3 `route_domain_and_capability`

输入：

1. `question`
2. `domain_hint`
3. `client_context`
4. `nqe_domain` / `nqe_capability`

输出：

1. `selected_domain`
2. `selected_capability`
3. `domain_candidates`
4. `capability_candidates`
5. `route_confidence`

失败：

1. 不支持业务域：`terminal_clarify`。
2. 低置信：`terminal_clarify`。
3. 业务域未开放：`legacy_fallback`。

### 6.4 `normalize_query`

输入：

1. `question`
2. `selected_domain`
3. `selected_capability`
4. 会话上下文

输出：

1. `normalized_question`
2. `intent_hints`
3. `keyword_terms`
4. `entity_terms`
5. `metric_terms`
6. `time_terms`
7. `compare_terms`
8. `retrieval_query`

失败：

1. 意图不支持：`terminal_clarify`。
2. 必要问题信息缺失：`terminal_clarify`。

### 6.5 `retrieve_context_multiway`

输入：

1. `retrieval_query`
2. `metadata_version_id`
3. `selected_domain`
4. `selected_capability`
5. 用户权限摘要

输出：

1. domain / capability candidates。
2. table candidates。
3. column candidates。
4. metric / dimension candidates。
5. value / entity candidates。
6. example candidates。
7. business rule candidates。
8. join path candidates。
9. time / unit / granularity candidates。

失败：

1. 召回源不可用：`legacy_fallback`。
2. 候选为空：`terminal_clarify` 或 `legacy_fallback`。

### 6.6 `merge_rank_and_build_context`

输入：

1. 各路候选。
2. NQE-SQL-MAIN-3 评分规则。
3. 上下文预算。

输出：

1. `retrieval_context_package`
2. `selected_tables`
3. `selected_columns`
4. `selected_metrics`
5. `selected_values`
6. `selected_join_paths`
7. `selected_rules`
8. `score_summary`
9. `dropped_summary`

失败：

1. 多领域高分冲突：`terminal_clarify`。
2. 多实体无法消歧：`terminal_clarify`。
3. 关键候选被过滤后为空：`legacy_fallback`。

### 6.7 `check_context_readiness`

输入：

1. `retrieval_context_package`
2. `selected_domain`
3. `selected_capability`
4. `intent_hints`

输出：

1. `context_readiness.status`: ok / clarify / fallback / unsupported。
2. `context_readiness.missing_items`。
3. `context_readiness.risk_flags`。
4. `clarification_hints`。
5. `fallback_hints`。

校验项：

1. 是否有可用表。
2. 是否有可用字段。
3. 指标定义是否完整。
4. WHERE 条件取值是否已消歧。
5. 时间字段和时间范围是否明确。
6. 多表查询是否有登记 join。
7. 是否违反权限、restricted、灰度模式。

### 6.8 `generate_sql_direct`

输入：

1. `question`
2. `normalized_question`
3. `retrieval_context_package`
4. `selected_domain`
5. `date_context`
6. `dialect_context`
7. `answer_policy`

输出：

1. `generated_sql`
2. `sql_revision_id`
3. `sql_generation_prompt_version`
4. `sql_generation_model_info` 摘要

约束：

1. 输出只能是一条 SELECT 或 WITH ... SELECT。
2. 不输出多语句。
3. 不生成 DDL / DML / 权限 / 过程调用。
4. 只能使用 `retrieval_context_package` 中 selected 的资产。
5. 明细查询必须有 LIMIT 或可由安全预检补 LIMIT。
6. SQL 只作为内部字段，不进用户可见输出。

### 6.9 `precheck_sql_safety`

输入：

1. `generated_sql`
2. `retrieval_context_package`
3. `selected_domain`
4. `metadata_version_id`
5. `safety_policy`

输出：

1. `sql_safety_result.status`: pass / reject / rewrite_limit / error。
2. `parsed_tables`
3. `parsed_columns`
4. `limit_policy_applied`
5. `safety_violations`
6. `safe_sql_candidate`

检查项：

1. SQL 是否单语句。
2. 是否只读 SELECT / WITH ... SELECT。
3. 是否访问系统库或敏感表。
4. 表是否在当前业务域白名单。
5. 字段是否在 selected columns 或允许字段集合中。
6. join 是否来自 selected join paths。
7. 是否包含危险函数、文件读写、网络访问、锁表、变量修改。
8. 明细查询是否有 LIMIT。
9. 聚合结果规模是否受控。

### 6.10 `explain_validate_sql`

输入：

1. `safe_sql_candidate`
2. `readonly_db_session`
3. `explain_policy`

输出：

1. `explain_result.status`: pass / fail。
2. `explain_error_sanitized`
3. `estimated_cost_summary`
4. `execution_plan_digest`

约束：

1. 只能对安全预检通过的 SQL 运行。
2. EXPLAIN 错误必须脱敏。
3. EXPLAIN 失败进入 `correct_sql`，但不能暴露给用户。

### 6.11 `correct_sql`

输入：

1. `generated_sql` 或上一轮修正 SQL。
2. `explain_error_sanitized`。
3. `retrieval_context_package`。
4. `sql_revision_round`。

输出：

1. 新 SQL。
2. 新 `sql_revision_id`。
3. `sql_revision_round + 1`。
4. `correction_reason`。

约束：

1. 最大 2 轮。
2. 只允许根据脱敏错误和原上下文修正。
3. 不允许引入未 selected 的表字段。
4. 修正后必须回到 `precheck_sql_safety`。
5. 每一轮都写 `nqe_sql_revision`。

### 6.12 `execute_sql_readonly`

输入：

1. EXPLAIN 通过的 SQL。
2. 只读数据库连接。
3. 超时和行数策略。

输出：

1. `execution_result_internal`
2. `row_count`
3. `latency_ms`
4. `result_truncated`
5. `execution_status`

约束：

1. 只查智能助手中间库。
2. 不直查外部同步源生产库。
3. 使用只读账号或只读事务。
4. 明细行数和结果体积受限。
5. 错误脱敏后记录 trace。

### 6.13 `present_business_answer`

输入：

1. 执行结果。
2. 业务口径。
3. 用户可见输出策略。
4. fallback / shadow / assist 状态。

输出：

1. `answer_summary`
2. `result_table`
3. `metric_cards`
4. `chart_suggestions`
5. `warnings`
6. `clarification`
7. `public_trace_id`

约束：

1. 不展示 SQL。
2. 不展示内部表名、字段名、query_key、prompt、trace 原文。
3. 使用业务中文列名。
4. 对空结果、缺数据、口径不明确、fallback 使用给业务化说明。

### 6.14 `record_query_log_and_trace`

输入：

1. 全部状态摘要。
2. trace steps。
3. SQL revision。
4. shadow compare。
5. 用户可见输出摘要。

输出：

1. `nqe_query_trace`。
2. `nqe_query_trace_step`。
3. `nqe_sql_revision`。
4. `nqe_shadow_compare`。
5. 查询日志摘要。

约束：

1. 不记录密钥、连接串、账号、Token。
2. SQL 可内部脱敏记录，但不得前端展示。
3. 字段取值候选需截断和脱敏。
4. 所有终态都要记录。

---

## 7. Trace 设计

### 7.1 trace 主表写入点

`init_trace_and_mode` 创建或确认 `nqe_query_trace`：

| 字段 | 来源 |
|---|---|
| trace_id | 入口或后端生成 |
| question_digest | 用户问题脱敏摘要 |
| domain_hint | 请求上下文 |
| nqe_mode | 灰度配置 |
| metadata_version_id | 当前版本 |
| prompt_version_id | 当前 Prompt 版本 |
| started_at | Graph 开始时间 |

`record_query_log_and_trace` 更新终态：

| 字段 | 来源 |
|---|---|
| final_status | 成功、澄清、fallback、错误、安全拒绝 |
| selected_domain | 路由结果 |
| fallback_used | fallback 状态 |
| row_count | 执行结果 |
| latency_ms | 总耗时 |
| public_answer_digest | 用户可见回答摘要 |

### 7.2 trace step 写入点

建议每个节点都写 step：

1. `receive_query`
2. `init_trace_and_mode`
3. `route_domain_and_capability`
4. `normalize_query`
5. `retrieve_context_multiway`
6. `merge_rank_and_build_context`
7. `check_context_readiness`
8. `generate_sql_direct`
9. `precheck_sql_safety`
10. `explain_validate_sql`
11. `correct_sql`
12. `execute_sql_readonly`
13. `present_business_answer`
14. `legacy_fallback`
15. `shadow_compare`
16. `terminal_clarify`
17. `terminal_safety_reject`
18. `terminal_error`
19. `record_query_log_and_trace`

每步至少记录：

| 字段 | 说明 |
|---|---|
| `step_code` | 节点编码 |
| `status` | success / clarify / fallback / error / rejected |
| `input_digest` | 输入摘要 |
| `output_digest` | 输出摘要 |
| `params` | topK、阈值、模式、版本等 |
| `warnings` | 歧义、缺 join、缺指标、低置信等 |
| `latency_ms` | 耗时 |
| `error_sanitized` | 脱敏错误 |

### 7.3 SQL revision 写入点

`generate_sql_direct` 写第 0 版 SQL revision。

`correct_sql` 每次修正写新 revision：

| 字段 | 说明 |
|---|---|
| `revision_round` | 0、1、2 |
| `sql_digest` | SQL 摘要 |
| `sql_text_encrypted_or_redacted` | 内部可审计 SQL，按安全策略保存 |
| `source` | generated / corrected |
| `error_before_sanitized` | 修正前错误 |
| `safety_result` | 预检结果 |
| `explain_result` | EXPLAIN 结果 |

---

## 8. Streaming 事件设计

NQE 前端可接收统一事件，但用户可见文案必须业务化，不暴露内部技术细节。

### 8.1 建议事件

| 事件 | 用户可见含义 | 内部 trace |
|---|---|---|
| `received` | 已收到问题 | receive_query |
| `domain_routed` | 已识别业务范围 | route_domain_and_capability |
| `query_understood` | 已理解查询条件 | normalize_query |
| `metadata_recalled` | 已匹配相关业务数据范围 | retrieve_context_multiway |
| `context_prepared` | 已整理查询口径 | merge_rank_and_build_context |
| `context_checked` | 已确认查询条件是否充足 | check_context_readiness |
| `query_generated_internal` | 正在生成查询方案 | generate_sql_direct |
| `query_safety_checked` | 已完成安全校验 | precheck_sql_safety |
| `query_validated` | 已完成可执行性校验 | explain_validate_sql |
| `query_corrected` | 已自动修正查询方案 | correct_sql |
| `query_executed` | 已完成查询 | execute_sql_readonly |
| `fallback_used` | 已切换到稳定旧链路 | legacy_fallback |
| `answer_delta` | 答案片段 | present_business_answer |
| `done` | 完成 | record_query_log_and_trace |
| `error` | 业务化失败 | terminal_error |
| `clarify` | 需要补充条件 | terminal_clarify |

### 8.2 前端展示要求

1. 前端可以展示“正在匹配业务数据范围”“正在校验查询安全”“正在整理结果”。
2. 前端不得展示 SQL 文本。
3. 前端不得展示内部表名、字段名、query_key、planner、guardrail、schema、raw/debug、LLM、prompt、trace 原文。
4. 前端可展示 `public_trace_id`，用于报障追踪。
5. shadow 模式下前端不展示 NQE 对比细节，只展示旧链路稳定结果。

---

## 9. 灰度模式 Graph 行为

### 9.1 off

```text
receive_query → init_trace_and_mode → legacy_fallback → present_business_answer → record_query_log_and_trace → END
```

用途：

1. 默认安全关闭。
2. 未接入域继续使用旧链路。
3. NQE 仅记录入口命中情况，不生成 SQL。

### 9.2 shadow

```text
receive_query
  ├─ old path: legacy_fallback → present_business_answer（用户可见）
  └─ nqe path: route → normalize → retrieve → generate → safety → explain → execute
          ↓
      shadow_compare → record_query_log_and_trace
```

用途：

1. 对比新旧链路正确性。
2. 收集失败类型和召回质量。
3. 不影响用户可见结果。

要求：

1. shadow 链路执行失败不得影响旧链路结果。
2. shadow 对比必须记录问题、域、指标、结果差异、行数差异、错误类型。
3. shadow 达标后才能进入 assist 或 on。

### 9.3 assist

```text
receive_query → route → normalize → retrieve → context
  ↓
legacy_fallback 使用 NQE 上下文增强理解
  ↓
present_business_answer → record_query_log_and_trace
```

用途：

1. 用 NQE 的领域识别、实体匹配、业务口径召回辅助旧链路。
2. 仍以旧链路结果为主，降低替换风险。

### 9.4 on

```text
receive_query → NQE 主链路 → present_business_answer
       ↓失败且允许
legacy_fallback → present_business_answer
```

用途：

1. NQE 作为正式主链路。
2. 旧链路保留为 fallback。
3. 达到稳定期后才评估下线旧链路。

---

## 10. 四域 Graph 接入策略

### 10.1 物流

接入顺序：

1. 首先进入 shadow。
2. 通过全量物流样例与历史回归后进入 assist。
3. 重点问题进入 on。
4. 旧物流链路保留 fallback。

Graph 重点：

1. 默认时间口径必须由业务规则召回。
2. 多年份无匹配年份也要保留空值说明。
3. 均价必须按总费用 / 总车次。
4. 人名、部门、基地、承运商、线路必须走 value / entity recall。

### 10.2 产销存 / 经营分析

接入顺序：

1. 元数据和指标口径补齐后 shadow。
2. 只使用已发布月份。
3. 缺平均库存等关键数据时业务化反问。

Graph 重点：

1. 指标召回必须优先于字段直连。
2. 库存、销量、产量、预算达成率要有业务口径。
3. 未来月份不能当实际数据。

### 10.3 计划 BOM

接入顺序：

1. 简单明细查询先 shadow。
2. 候选消歧、compare、replay 保留旧服务 fallback。
3. 逐步扩展到更复杂查询。

Graph 重点：

1. BOM 单号、文件名、客户实例、评审号、版本必须走 entity recall。
2. 多候选时优先业务化澄清。
3. 不针对具体案例 hardcode。

### 10.4 功率预测子能力

接入顺序：

1. 先作为计划 BOM 子能力进入 route 和 recall。
2. 查询历史结果、参数、配置项可走 NQE。
3. 实际预测计算必须 fallback 到确定性引擎。

Graph 重点：

1. NQE 不直接计算功率档位、比例、供应商效率、匹配度。
2. 预测类问题在 `check_context_readiness` 时识别为需要确定性引擎。
3. `legacy_fallback` 或专用 deterministic fallback 返回业务化预测结果。

---

## 11. 与当前代码的迁移关系

本卡只读审计当前代码，不要求立即重命名或修改。后续编码卡可按以下原则迁移：

| 当前原型能力 | NQE 目标能力 | 后续建议 |
|---|---|---|
| 统一 Graph 原型 | NQE Graph 主流程 | 保留思想，迁移为 NQE 命名与 state |
| 领域路由节点 | `route_domain_and_capability` | 增加灰度、权限、能力校验和 trace |
| 关键词抽取节点 | `normalize_query` | 输出结构化 `RetrievalQuery` |
| 三路召回节点 | `retrieve_context_multiway` | 扩展为 NQE-SQL-MAIN-3 多路召回 |
| 合并过滤节点 | `merge_rank_and_build_context` | 增加统一候选、评分、上下文预算 |
| 上下文补充节点 | context builder | 改为构造 `RetrievalContextPackage` |
| SQL 生成节点 | `generate_sql_direct` | 禁止 fallback 到任意占位 SQL，必须基于 selected 上下文 |
| SQL 校验节点 | `explain_validate_sql` | 前面新增 `precheck_sql_safety` |
| SQL 修正节点 | `correct_sql` | 加 SQL revision、最大 2 轮、重新预检 |
| SQL 执行节点 | `execute_sql_readonly` | 只读连接、超时、行数、业务化输出 |
| 流式服务 | NQE streaming API | 改为 NQE 事件协议 |

迁移原则：

1. 编码卡开始前必须创建或确认 feature 分支。
2. 不能直接替换正式入口。
3. 先在 shadow 模式运行。
4. 任何用户可见输出都不能暴露内部 SQL 或技术字段。
5. 保留旧链路 fallback，直到对应域完成 Go / No-Go。

---

## 12. 后续编码卡 scoped 文件建议

NQE-SQL-MAIN-4 本身不编码，但为 NQE-SQL-MAIN-10～13 提供实现边界。

### 12.1 NQE Graph 骨架编码卡建议范围

建议新增：

1. `backend/app/domains/nqe/graph/builder.py`
2. `backend/app/domains/nqe/graph/state.py`
3. `backend/app/domains/nqe/graph/routes.py`
4. `backend/app/domains/nqe/graph/nodes/*.py`
5. `backend/app/domains/nqe/schemas/*.py`
6. `backend/app/domains/nqe/services/query_service.py`
7. `backend/app/api/v1/nqe.py`
8. `tests/unit/nqe/test_graph_flow.py`
9. `tests/unit/nqe/test_graph_modes.py`

禁止在该卡中：

1. 删除旧 Graph 原型。
2. 替换正式物流 / BOM / 产销存入口。
3. 接入真实用户 on 模式。
4. 绕过 SQL 安全预检。

### 12.2 SQL 安全编码卡建议范围

由 NQE-SQL-MAIN-5 继续细化，后续实现建议新增：

1. `backend/app/domains/nqe/sql/safety.py`
2. `backend/app/domains/nqe/sql/parser.py`
3. `backend/app/domains/nqe/sql/explain.py`
4. `backend/app/domains/nqe/sql/revision.py`
5. `tests/unit/nqe/test_sql_safety.py`
6. `tests/unit/nqe/test_sql_revision.py`

### 12.3 Trace 编码卡建议范围

由 NQE-SQL-MAIN-12 / 13 承接，后续实现建议新增：

1. `backend/app/domains/nqe/repositories/trace_repository.py`
2. `backend/app/domains/nqe/services/trace_service.py`
3. `backend/app/domains/nqe/services/shadow_compare_service.py`
4. `tests/unit/nqe/test_trace_repository.py`
5. `tests/unit/nqe/test_shadow_compare.py`

---

## 13. 验收标准

NQE-SQL-MAIN-4 完成应满足：

1. 已形成 NQE LangGraph SQL Agent 主流程设计。
2. 已明确 Graph 节点清单、节点职责和失败分支。
3. 已明确 NQE State 字段分层。
4. 已明确 SQL 安全预检位置：SQL 生成后、EXPLAIN 前。
5. 已明确 correct loop：最多 2 轮，修正后重新安全预检和 EXPLAIN。
6. 已明确 SQL revision、trace step、query log、shadow compare 的写入点。
7. 已明确 off / shadow / assist / on 四种灰度模式的 Graph 行为。
8. 已明确旧链路 fallback 与用户可见结果关系。
9. 已明确四域接入策略。
10. 已明确后续编码卡 scoped 文件范围。
11. 未修改业务代码。
12. 未修改前端代码。
13. 未覆盖物管 / SAP MID 状态文件。
14. 文档未写入外部参考项目名称。
15. 文档未写入密钥、账号、连接串或其他敏感凭证。

---

## 14. 当前结论

NQE-SQL-MAIN-4 的设计结论是：统一 SQL Agent 应从当前统一 Graph 原型升级为具有 NQE 命名、元数据版本、灰度模式、SQL 安全预检、EXPLAIN 校验、修正闭环、只读执行、业务化表达、trace/replay/shadow compare 的正式主流程。

在 NQE-SQL-MAIN-5 安全边界设计和后续实现卡完成前，不应把 NQE 生成 SQL 直接接入正式用户链路；即使进入 shadow，也必须保证上下文来自 NQE 元数据白名单，并且所有 SQL 生命周期节点可审计、可复现、可回滚。

# Query Planning V2 现状审计

## 1. 审计目标与范围

本审计面向“业务员原始问题进入后台之后、正式检索 / SQL 查询 / RAG 查询之前”的 LLM 理解与查询规划能力，目标是确认当前仓库已有能力、真实接入点、缺口与升级风险，为后续 Query Planning V2 设计和最小实现提供依据。

本轮只做现状审计和方案设计，不替换现有物流 `data-qa` 主链路，不替换 Plan BOM QA 主链路，不新增数据库迁移，不让 LLM 直接查数、生成 SQL 或生成最终业务答案。

重点审计路径：

- 物流域：`backend/app/domains/logistics/`
- Plan BOM 域：`backend/app/domains/plan_bom/`
- 查询历史 / 日志：`backend/app/domains/logistics/repositories/query_repository.py`、`backend/app/services/query_log_service.py`、`backend/app/models/sys_query_log.py`
- 既有说明文档：`docs/LOGISTICS_LLM_UNDERSTANDING_POC.md`、`docs/LOGISTICS_LLM_GUARDRAIL_ROLLOUT.md`、`docs/LOGISTICS_NLU_CENTER_V1.md`
- 既有业务验收测试：`tests/business_acceptance/`

---

## 2. 总体结论

当前项目已经具备“规则优先 + LLM 受控候选理解 + Guardrail + 澄清 / 拒答辅助 + 答案展示层”的基础能力，尤其是物流域已经不是空白状态。Query Planning V2 不应从零重建 planner，而应以统一 envelope / adapter 的方式承接现有能力。

当前可复用能力：

1. 物流规则 planner 已输出受控 `LogisticsDataQaPlan`，可覆盖大量 `DIRECT_RETRIEVAL` 场景。
2. 物流 LLM Understanding 已能输出候选 `query_key`、slots、澄清和拒答判断，但定位是候选理解，不直接执行。
3. 物流 Guardrail 已支持 `off` / `shadow` / `assist`，并锁定 B/C 边界。
4. 物流 NLU Center v1 已形成 shadow / diagnostic 输出，含 rule plan、LLM result、guardrail 摘要和多问题识别。
5. 物流已有澄清辅助、拒答辅助和答案展示辅助，均限定 LLM 只能优化表达或辅助理解，不允许改变事实或边界。
6. Plan BOM 域已有独立 NLU Center 与 QA Service，但尚未和物流统一到 Query Planning V2 schema。
7. 查询日志和 JSONL 审计已存在，但日志结构分散，尚不足以支撑跨域、版本化、可回放的 Query Planning V2。

当前主要缺口：

1. 没有跨域统一 `query_plan_v2` schema。
2. 没有统一 `strategy` 枚举。
3. 没有正式 `HYDE_RETRIEVAL`。
4. 没有正式 `QUERY_REWRITE_SIMPLIFY`。
5. `QUERY_DECOMPOSITION` 仅覆盖受控 `composite_decomposed` 小范围场景，不是通用自由拆分。
6. `query_plan` / `llm_result` / `guardrail_decision` 的审计与回放能力分散在 response、`sys_query_log.request_payload` 和 JSONL 文件中。
7. Plan BOM 与物流的 NLU / QA schema 尚未统一。
8. Query Planning V2 所需的跨域回归测试矩阵尚未建立。

---

## 3. 物流域当前已有能力清单

### 3.1 规则 Planner

核心文件：

- `backend/app/domains/logistics/services/data_qa_planner.py`
- `backend/app/domains/logistics/schemas/data_qa.py`

当前 `LogisticsDataQaPlanner` 是物流 Data QA 的正式规则规划器，职责包括：

- 识别业务问题意图；
- 归一化年份、月份、区域、承运商、客户、运输方式等条件；
- 选择白名单 `query_key`；
- 构造 `metrics`、`dimensions`、`filters`、`group_by`、`sort`、`limit`；
- 对缺条件问题输出澄清计划；
- 对数据源或口径不支持问题输出拒答计划；
- 对少量综合问题输出受控复合计划。

`LogisticsDataQaPlan` 当前结构已经接近领域内 query plan：

```python
domain: Literal["logistics"] = "logistics"
intent: str
query_key: str | None
metrics: list[str]
dimensions: list[str]
filters: dict[str, Any]
group_by: list[str]
sort: list[dict[str, Any]]
limit: int | None
needs_clarification: bool
clarification_questions: list[str]
clarification_category: str | None
clarification_reason: str | None
clarification_missing_slots: list[str]
unsupported_reason: str | None
unsupported_category: str | None
unsupported_suggestions: list[str]
```

安全边界：

- `LogisticsDataQaPlan` 不承载任意 SQL；
- repository 层仍通过白名单字段和绑定参数执行；
- LLM 不直接生成 `LogisticsDataQaPlan` 并执行，必须经过规则与 Guardrail。

### 3.2 LLM Understanding Service

核心文件：

- `backend/app/domains/logistics/services/llm_understanding_service.py`
- `backend/app/domains/logistics/schemas/llm_understanding.py`

当前 `LogisticsLlmUnderstandingService` 的定位是物流域“语言理解层”，不是查询执行层。系统提示词明确要求：

- 只做语义理解、术语归一、槽位抽取、意图识别、`query_key` 候选生成和澄清问题草案；
- 绝不能查数据库；
- 不能输出 SQL；
- 不能计算最终数值；
- 不能编造业务答案；
- 候选 `query_key` 只能从白名单选择。

当前输出 `LogisticsLlmUnderstandingResult` 包括：

```python
normalized_question
intent
metrics
dimensions
filters
time_range
source_scope
candidate_query_keys
normalized_terms
needs_clarification
clarification_questions
unsupported_reason
confidence
provider_mode
provider_error
llm_model_name
```

LLM Understanding 当前支持的核心能力：

- A 类同构变体问题候选增强；
- B 类澄清判断辅助；
- C 类不支持判断辅助；
- `composite_decomposed` 复合问题候选输出；
- provider disabled / error 显式返回，而不是伪造成功。

### 3.3 Guardrail Candidate Assist

核心文件：

- `backend/app/domains/logistics/services/llm_understanding_guardrail_service.py`
- `backend/app/domains/logistics/schemas/llm_understanding.py`

当前 `LogisticsLlmUnderstandingGuardrailService` 是 LLM 候选进入正式链路前的安全闸门。

运行模式：

- `off`：完全不使用 LLM 候选；
- `shadow`：只审计候选，不改正式结果；
- `assist`：满足所有限制时，允许 A 类白名单候选受控回构为正式 plan。

Guardrail 关键规则：

1. 规则 planner 先执行。
2. 规则已命中正式 `query_key` 时，不需要 LLM 增强。
3. B/C 题命中正式策略后默认锁定，不允许 LLM 改写。
4. 只允许通用兜底澄清进入候选增强。
5. LLM 必须返回 live 结果。
6. LLM 不能自己判成澄清或 unsupported 后再强行放行。
7. LLM intent 必须在允许集合内。
8. 置信度必须达到阈值。
9. 候选 `query_key` 必须且只能有一个。
10. 候选 `query_key` 必须在 A 类白名单内。
11. `shadow` 模式不改正式结果。
12. `assist` 模式才允许 `final_source=llm_assist`。

Guardrail 审计结构记录：

- 原始问题；
- guardrail 是否启用；
- mode；
- 是否抽样；
- 规则层 intent / query_key / B/C 状态；
- LLM top query_key；
- LLM confidence；
- 是否推荐 assist；
- 是否实际应用；
- final source / intent / query_key；
- blocked reason；
- rollback reason。

审计落点：

- `data/logs/logistics_llm_guardrail_audit.jsonl`
- `sys_query_log.request_payload.response_meta.guardrail`

### 3.4 NLU Center v1

核心文件：

- `backend/app/domains/logistics/services/nlu_center_service.py`
- `backend/app/domains/logistics/schemas/nlu.py`
- `docs/LOGISTICS_NLU_CENTER_V1.md`

当前 NLU Center v1 是影子诊断层，不替代正式 `data-qa planner`。

`LogisticsNluResult` 包括：

```python
raw_question
normalized_question
is_multi_intent
intent
sub_questions
metrics
dimensions
filters
time_range
source_scope
candidate_query_keys
needs_clarification
missing_slots
clarification_questions
unsupported
unsupported_reason
confidence
nlu_source
guardrail_decision
route_suggestion
risk_flags
normalized_terms
rule_plan
llm_result
```

当前用途：

- 聚合规则 planner、术语归一、启发式理解、可选 LLM 候选和 Guardrail 诊断；
- 做 shadow / diagnostic 评测；
- 为未来 Query Planning V2 提供可复用的理解层证据。

限制：

- 不直接触发数据库查询；
- 不替代正式 planner；
- 不改写 B/C 边界。

### 3.5 澄清辅助

核心文件：

- `backend/app/domains/logistics/services/llm_clarification_assist_service.py`
- `backend/app/domains/logistics/schemas/llm_understanding.py`

当前澄清辅助仅在规则层已经判定必须澄清后生效。

职责：

- 识别缺失槽位；
- 生成更业务化的追问；
- 输出 missing slots、slot reasons、suggested questions；
- 写 JSONL 审计。

边界：

- 不能把澄清题改判成 success；
- 不能把澄清题改判成 unsupported；
- 最终追问仍由规则与服务层决定。

### 3.6 拒答 / 不支持辅助

核心文件：

- `backend/app/domains/logistics/services/llm_unsupported_assist_service.py`
- `backend/app/domains/logistics/schemas/llm_understanding.py`

当前拒答辅助仅服务于规则层已经明确 unsupported 的问题。

职责：

- 将拒答原因表达为业务人员更容易理解的文本；
- 给出可改问方向；
- 记录 JSONL 审计。

边界：

- 不能把 C 类改成 A 类；
- 不能生成 SQL；
- 不能查数；
- 不能编造结果。

### 3.7 答案展示辅助

核心文件：

- `backend/app/domains/logistics/services/llm_answer_presentation_service.py`
- `backend/app/domains/logistics/schemas/data_qa.py`

当前答案展示层只在后端确定性结果之后工作。

职责：

- 组织自然语言回答；
- 生成展示类型、标题、摘要、表格 / 图表 / 卡片建议；
- 对澄清、拒答、空结果、错误态做展示编排。

边界：

- 不能查数据库；
- 不能生成 SQL；
- 不能改写 planner / `query_key`；
- 不能改变 A/B/C/空结果/错误状态；
- 不能新增、删除、修改任何确定性数值事实。

---

## 4. 物流域真实接入点

### 4.1 API 接入点

文件：

- `backend/app/domains/logistics/api/endpoints/data_qa.py`

该接口接收业务员自然语言问题，并调用 `LogisticsDataQaService.query`。

### 4.2 主链路

当前物流 Data QA 主链路可概括为：

```text
HTTP 请求
→ logistics data_qa endpoint
→ LogisticsDataQaService.query
→ LogisticsDataQaPlanner 规则规划
→ LogisticsLlmUnderstandingGuardrailService.evaluate
   → 可选 LogisticsLlmUnderstandingService.understand
→ 必要时由 Guardrail 受控回构 plan
→ 按白名单 query_key 执行 repository / service
→ 生成确定性 answer_summary / result_table / status
→ 可选 LLM answer presentation
→ 写 sys_query_log / JSONL audit
→ 返回 LogisticsDataQaResult
```

关键结论：

- LLM Understanding 的真实接入点不是 API 直接调用，而是 Data QA 主链路中的 Guardrail 候选增强；
- 当前正式结果仍由规则 planner 和受控 query service 决定；
- LLM 不拥有查询执行权；
- B/C 边界由规则策略和 Guardrail 锁定。

---

## 5. Plan BOM 当前已有能力与真实接入点

### 5.1 核心文件

- `backend/app/domains/plan_bom/api/endpoints/qa.py`
- `backend/app/domains/plan_bom/services/qa_service.py`
- `backend/app/domains/plan_bom/services/nlu_center_service.py`
- `backend/app/domains/plan_bom/schemas/qa.py`

### 5.2 真实接入点

Plan BOM QA 的真实 API 入口是：

```text
backend/app/domains/plan_bom/api/endpoints/qa.py
→ PlanBomQaService
→ PlanBomNluCenterService
→ BOM 查询 / 规则处理 / 确定性服务
→ 可选答案表达
```

### 5.3 当前能力判断

Plan BOM 域已经有 NLU Center 和 QA Service，不是空白状态。当前能力包括：

- 规则抽取订单、评审号、物料、客户实例、版本等业务槽位；
- 可选 LLM 候选理解；
- 面向 Plan BOM QA 的确定性查询与回答；
- 对部分计划功率问答已有集成测试覆盖。

但 Plan BOM 与物流相比存在明显缺口：

1. 没有统一到跨域 `query_plan_v2` envelope。
2. 没有与物流一致的 `strategy` 字段。
3. 没有与物流一致的 Guardrail 决策结构。
4. 没有统一的 rewrite / hyde / decomposition 字段。
5. 日志与回放能力不如物流域完整。

---

## 6. DIRECT_RETRIEVAL 覆盖现状

### 6.1 物流域

已覆盖较充分。

物流域 `DIRECT_RETRIEVAL` 当前由以下能力承接：

- `LogisticsDataQaPlanner`；
- `LogisticsDataQaPlan.query_key`；
- 受控 `metrics` / `dimensions` / `filters`；
- repository 层白名单字段与参数绑定；
- `LogisticsDataQaService` 的 query_key 分发与结果合成。

当前 DIRECT_RETRIEVAL 的核心安全属性：

- 规则 planner 主导；
- LLM 只可能在 Guardrail 允许下补充 A 类白名单候选；
- 任何可执行计划最终必须落到白名单 `query_key` 和受控 service / repository；
- 不存在 LLM 直接生成 SQL 的正式路径。

### 6.2 Plan BOM 域

Plan BOM 域有自己的规则 QA / NLU 链路，能覆盖部分 DIRECT_RETRIEVAL，但尚未统一为跨域 query plan。

需要后续通过 adapter 把 Plan BOM 的规则理解结果包装为 Query Planning V2 envelope，而不是直接照搬物流 `LogisticsDataQaPlan`。

---

## 7. CLARIFY 覆盖现状

### 7.1 物流域

已覆盖较充分。

现有字段和服务：

- `LogisticsDataQaPlan.needs_clarification`
- `LogisticsDataQaPlan.clarification_questions`
- `clarification_category`
- `clarification_reason`
- `clarification_missing_slots`
- `LogisticsLlmClarificationAssistService`
- `LogisticsDataQaResult.needs_clarification`
- `LogisticsDataQaResult.clarification_questions`
- `LogisticsDataQaStatus`

当前链路特点：

- 规则层先判定是否需要澄清；
- LLM 只辅助缺槽识别和追问表达；
- Guardrail 不允许 LLM 把澄清题改成 success；
- 澄清状态会进入响应和查询历史。

### 7.2 Plan BOM 域

Plan BOM 域已有缺槽 / 候选消歧相关能力，但尚未形成与物流一致的 `clarification_questions` / `missing_slots` / `guardrail_decision` 统一结构。

后续应通过 V2 adapter 对齐字段，而不是强行改动 Plan BOM 主链路。

---

## 8. NO_ANSWER / UNSUPPORTED 覆盖现状

### 8.1 物流域

已覆盖较充分。

需要特别说明：当前物流域的 `NO_ANSWER` 更接近“执行后空结果 / 数据不可用 / 权限或数据源异常”等状态表达，已有 `EMPTY_RESULT`、`supported=False`、`LogisticsDataQaStatus` 等承接点；但它尚未作为 Query Planning V2 中独立、前置、统一的 `NO_ANSWER` strategy 完整存在。后续 V2 需要把“规则层不支持”与“查询范围支持但当前无可用答案”明确拆开。

现有字段和服务：

- `LogisticsDataQaPlan.unsupported_reason`
- `unsupported_category`
- `unsupported_template`
- `unsupported_suggestions`
- `LogisticsLlmUnsupportedAssistService`
- `LogisticsDataQaResult.supported = False`
- `LogisticsDataQaStatus`
- `question_bank_response_policy`
- Guardrail B/C 锁定。

当前链路特点：

- 规则层一旦判定 unsupported，LLM 不能反向放行；
- LLM 只允许优化拒答原因和可改问方向；
- C 类边界不会被 LLM 改写成 A 类查询。

### 8.2 Plan BOM 域

Plan BOM 域存在不支持 / 无法解析 / 候选不足等状态，但尚未统一映射到 Query Planning V2 的 `NO_ANSWER` / `UNSUPPORTED` 策略字段。

---

## 9. QUERY_DECOMPOSITION 覆盖现状

当前项目已有受控复合问题拆分能力，但不是通用框架。

### 9.1 已有能力

物流域中：

- LLM Understanding 白名单包含 `composite_decomposed`；
- prompt 要求综合型问题由 LLM 基于语义判断拆分；
- `filters.sub_plans` 用于承载子计划；
- Guardrail 中存在复合策略例外，允许特定旧拒答策略进入 LLM 复合拆分候选；
- `LogisticsDataQaService` 存在复合计划执行逻辑；
- 子计划必须回构为受控白名单 query_key；
- 后端负责校验、执行和合并结果。

### 9.2 当前受控范围

当前主要覆盖少量已审计模式，例如：

- 历史客户高运费收货地址；
- 2026 采购方式发运量 MW；
- 高运费地址 + 采购方式这类可拆为两个顶层独立子问的综合问题。

### 9.3 当前限制

- 不支持完全自由的多问题拆分；
- 不支持 LLM 任意生成子查询；
- 不支持复杂回指问题，例如“这些地址 / 上述地址 / 上面的地址”等依赖前一子结果的过滤；
- 不支持把 unsupported 单位或字段自动替换成近似支持字段；
- 不允许 LLM 计算、聚合或编造子结果。

结论：

> 当前 `QUERY_DECOMPOSITION` 是“LLM 语义候选 + 后端严格校验 + 白名单执行”的受控能力雏形，后续只能在该模式下扩展，不能升级为自由拆分或自由 SQL。

---

## 10. HYDE_RETRIEVAL 覆盖现状

当前未发现正式 `HYDE_RETRIEVAL` 能力。

缺失项包括：

- 无稳定 `strategy=HYDE_RETRIEVAL`；
- 无 `hyde_text` schema 字段；
- 无 HYDE 专用 prompt / service；
- 无 HYDE 只用于检索增强的执行策略；
- 无 HYDE 与 RAG / embedding / 文档检索链路的正式对接；
- 无防止 HYDE 文本被当成事实答案展示的 guardrail 字段。

结论：

> HYDE_RETRIEVAL 在当前仓库中尚未正式存在。后续只能先做 shadow / PoC，且不得进入结构化 SQL 查询。

---

## 11. QUERY_REWRITE_SIMPLIFY 覆盖现状

当前未发现正式 `QUERY_REWRITE_SIMPLIFY` 能力。

已有相关能力：

- planner 层有基础文本 normalize；
- LLM Understanding 有 `normalized_question`；
- NLU Center 有术语归一与 normalized terms。

但缺少：

- 独立 `strategy=QUERY_REWRITE_SIMPLIFY`；
- 稳定 `rewritten_question` 字段；
- rewrite shadow 记录；
- rewrite 与原始问题并存的审计契约；
- rewrite 只能辅助检索 / planner、不能覆盖原问题的 enforcement；
- rewrite 变体回归测试。

结论：

> 当前只有格式归一和术语归一，不存在正式 Query Rewrite Simplify。后续必须保证原始问题始终保留，改写结果只能作为辅助输入。

---

## 12. 是否已有统一 query_plan schema

当前没有跨域统一 Query Planning V2 schema。

### 12.1 已有领域内结构

物流域：

- `LogisticsDataQaPlan` 是领域内受控查询计划；
- 支持成功、澄清、拒答；
- 已接近 Query Plan，但缺少 V2 strategy envelope。

物流 NLU：

- `LogisticsNluResult` 是理解层诊断结构；
- 含 rule_plan 与 llm_result 快照；
- 不是可执行 query plan。

Plan BOM：

- 有 Plan BOM 自己的 QA / NLU schema；
- 不是跨域统一 Query Plan。

### 12.2 V2 缺失字段

当前缺少统一字段：

- `schema_version`
- `domain` enum：`logistics` / `plan_bom` / `unknown`
- `original_question`
- `strategy`
- `rewritten_question`
- `hyde_text`
- `sub_queries`
- `no_answer_reason`
- `guardrail_decision` 对象
- `rule_plan` 快照统一格式
- `llm_result` 快照统一格式
- `execution_policy`
- `audit.trace_id`
- `planner_version`
- `shadow` 标记
- `replay_payload`

---

## 13. 日志、落库与可审计性现状

### 13.1 sys_query_log

物流查询日志写入位于：

- `backend/app/domains/logistics/repositories/query_repository.py`

`write_query_log` 当前写入字段：

```text
trace_id
query_type
question_text
request_payload
route_type
metric_type
result_count
status
message
```

特点：

- `request_payload` 可存 JSON 快照；
- 当前 query_plan / response_meta / guardrail 等信息主要嵌入该字段；
- 查询历史服务复用 `sys_query_log` 展示历史记录。

### 13.2 JSONL 审计

当前存在多类 JSONL 审计：

- Guardrail audit：`data/logs/logistics_llm_guardrail_audit.jsonl`
- Clarification assist audit；
- Unsupported assist audit。

### 13.3 当前不足

1. 没有独立 `query_plan_v2` 表。
2. 没有统一 V2 JSONL 审计落点。
3. `query_plan`、`llm_result`、`guardrail_decision` 分散记录。
4. Plan BOM 与物流日志结构未统一。
5. 缺少稳定 `schema_version`，难以长期回放。
6. 缺少 strategy router 决策快照。
7. 缺少 HYDE / rewrite / decomposition shadow 产物的统一记录。

结论：

> 当前日志足以排查 Guardrail 和物流 Data QA，但尚不足以支撑 Query Planning V2 的跨域审计、回放和策略对比。

---

## 14. 现有测试覆盖

### 14.1 已确认测试方向

当前仓库已有以下相关业务验收测试：

- `tests/business_acceptance/test_logistics_llm_led_composite_decomposition.py`
- `tests/business_acceptance/test_logistics_field_scope_clarification.py`
- `tests/business_acceptance/test_plan_power_m5_qa_integration.py`

既有文档还记录：

- 物流 LLM Understanding PoC 样本；
- Guardrail 关键题和 A/B/C 回归；
- NLU Center v1 诊断样本。

### 14.2 已覆盖能力

- A 类 query_key 变体命中；
- B 类澄清边界；
- C 类 unsupported 边界；
- 复合问题受控拆分；
- Plan Power / Plan BOM 集成问答的一部分链路。

### 14.3 缺失测试

Query Planning V2 仍需新增：

1. 统一 schema 稳定 JSON 测试；
2. strategy enum 路由测试；
3. 物流明确查询 DIRECT_RETRIEVAL 测试；
4. 物流口语化 rewrite shadow 测试；
5. 物流复杂复合 QUERY_DECOMPOSITION 测试；
6. 物流缺槽 CLARIFY 测试；
7. 物流无答案 / 不支持 NO_ANSWER / UNSUPPORTED 测试；
8. BOM 单订单查询测试；
9. BOM 多订单表格测试；
10. BOM 订单对比测试；
11. BOM 缺槽澄清测试；
12. 问法变体鲁棒性测试；
13. HYDE shadow 不进入 SQL / 不作为事实答案测试；
14. query_plan_v2 日志和回放快照测试。

---

## 15. 当前直接升级的主要风险

| 风险 | 说明 | 建议控制方式 |
| --- | --- | --- |
| 重复造轮子 | 物流已有 planner、NLU、Guardrail、LLM assist，直接新建 planner 会分裂链路 | Query Planning V2 应做 envelope + adapter |
| 规则主导被削弱 | 当前稳定性来自规则 planner 与 query_key 白名单 | V2 中 rule_plan 必须先行，LLM 只做候选 |
| B/C 边界被 LLM 改坏 | rewrite / hyde / decomposition 若绕开 Guardrail，会把澄清或拒答变成功 | 所有 LLM 输出必须经过 Guardrail 和策略校验 |
| HYDE 事实泄漏 | 假设答案可能被误当最终答案展示 | `hyde_text` 标记 retrieval-only，禁止进入 answer |
| rewrite 覆盖原问题 | 改写可能抹掉用户原始口径 | `original_question` 必填且不可覆盖 |
| decomposition 泛化过度 | 自由拆分会产生不可执行子查询、回指错误和跨源混用 | 只扩白名单复合模式，fail closed |
| Plan BOM 与物流 schema 不一致 | 强行套用物流字段会污染 BOM 语义 | 用 domain adapter，保留领域字段 |
| 日志不可回放 | 当前日志分散且缺少 version | 新增统一 V2 audit payload |
| 测试矩阵不足 | 新 strategy 可能只在少量样例通过 | 先补 schema / strategy / 领域回归测试 |

---

## 16. 可复用模块清单

### 16.1 物流域可复用

| 模块 | 文件 | V2 复用方式 |
| --- | --- | --- |
| 规则 planner | `data_qa_planner.py` | DIRECT_RETRIEVAL 的正式计划来源 |
| 查询计划 schema | `schemas/data_qa.py` | 作为 logistics adapter 的领域 plan |
| LLM 理解层 | `llm_understanding_service.py` | LLM candidate source |
| Guardrail | `llm_understanding_guardrail_service.py` | LLM 输出进入策略路由前的安全闸门 |
| NLU Center | `nlu_center_service.py` | shadow 诊断证据与 rule / llm 快照来源 |
| 澄清辅助 | `llm_clarification_assist_service.py` | CLARIFY 表达增强 |
| 拒答辅助 | `llm_unsupported_assist_service.py` | NO_ANSWER / UNSUPPORTED 表达增强 |
| 答案展示层 | `llm_answer_presentation_service.py` | 执行后展示，不参与 planning 决策 |
| 查询日志 | `query_repository.py` / `sys_query_log` | 先复用 request_payload，再设计 V2 audit |

### 16.2 Plan BOM 可复用

| 模块 | 文件 | V2 复用方式 |
| --- | --- | --- |
| QA API | `plan_bom/api/endpoints/qa.py` | Plan BOM 真实入口，不直接替换 |
| QA Service | `plan_bom/services/qa_service.py` | BOM 领域确定性执行来源 |
| NLU Center | `plan_bom/services/nlu_center_service.py` | BOM slots / intent / candidate 来源 |
| QA schema | `plan_bom/schemas/qa.py` | BOM adapter 的领域响应来源 |

---

## 17. 审计结论与下一步建议

### 17.1 当前能力对应策略判断

| 策略 | 当前覆盖 | 结论 |
| --- | --- | --- |
| DIRECT_RETRIEVAL | 物流较完整，BOM 部分具备 | 可作为 V2 第一批正式承接能力 |
| CLARIFY | 物流较完整，BOM 需 adapter 统一 | 可复用现有能力 |
| NO_ANSWER / UNSUPPORTED | 物流已有执行后空结果 / 不支持表达，BOM 需 adapter 统一 | 可复用现有能力，但 V2 需补齐独立 strategy 映射 |
| QUERY_DECOMPOSITION | 仅受控 `composite_decomposed` | 只能白名单扩展，不做自由拆分 |
| QUERY_REWRITE_SIMPLIFY | 未正式存在 | 先 shadow |
| HYDE_RETRIEVAL | 未正式存在 | 先 PoC / shadow，不进 SQL |

### 17.2 推荐升级路径

1. 先实现 Query Planning V2 统一 schema 与诊断服务，不接管主链路。
2. logistics adapter 复用现有 `LogisticsDataQaPlanner`、`LogisticsNluCenterService`、Guardrail。
3. plan_bom adapter 优先复用 `PlanBomNluCenterService` 和领域规则；如需引用 `PlanBomQaService` 的现有 QA 结果，只能作为 post-hoc shadow 观测，不应在“检索 / 查询前”的 planning 阶段触发实际查数。
4. 所有策略先进入 shadow audit。
5. 第一批只正式承接 DIRECT_RETRIEVAL、CLARIFY、NO_ANSWER / UNSUPPORTED 的现有能力。
6. rewrite / HYDE 仅生成辅助文本和日志，不影响正式结果。
7. decomposition 只扩展受控白名单模式，必须继续 LLM-led + backend validation。
8. 建立 V2 回归测试矩阵后，再评估小步接入主链路。

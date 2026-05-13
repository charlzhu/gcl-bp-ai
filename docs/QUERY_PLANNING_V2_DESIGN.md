# Query Planning V2 设计方案

## 1. 设计目标

Query Planning V2 的目标是在“业务员原始问题进入后台之后、正式检索 / SQL 查询 / RAG 查询之前”形成一个跨物流与 Plan BOM 领域的统一查询规划层。

本方案不是推翻现有规则 planner，也不是让 LLM 直接替换 planner，而是在现有能力上增加一个稳定、可审计、可回放、可测试的 `query_plan_v2` envelope。

核心目标：

1. 统一承接规则结果、LLM 候选、rewrite、decomposition、clarification 和 no_answer。
2. 保持规则 planner 优先，LLM 只做受控理解增强。
3. 所有 LLM 输出都必须经过 Guardrail 或同等级安全校验。
4. 所有可执行查询必须落到白名单 `query_key` 或受控 repository / service。
5. `query_plan_v2` 必须是稳定 JSON，可写日志、可审计、可回放、可测试。
6. Phase 3 先实现诊断接口 / 内部服务，shadow 运行，不直接替换物流 `data-qa` 或 Plan BOM QA 主链路。

非目标：

1. 不让 LLM 直接生成 SQL。
2. 不让 LLM 直接查数据库。
3. 不让 LLM 直接生成最终业务事实答案。
4. 不新增自由查询执行器。
5. 不绕过现有物流 Guardrail、B/C 策略和 Plan BOM 确定性查询链路。
6. 不在 Phase 3 直接接管正式查询结果。

---

## 2. 总体架构

推荐架构：

```text
用户问题
↓
Domain Router
↓
Query Planning V2 Service（shadow / diagnostic）
↓
Domain Adapter
  ├─ logistics adapter
  │   ├─ LogisticsDataQaPlanner
  │   ├─ LogisticsNluCenterService
  │   ├─ LogisticsLlmUnderstandingService
  │   └─ LogisticsLlmUnderstandingGuardrailService
  └─ plan_bom adapter
      ├─ PlanBomNluCenterService
      └─ PlanBomQaService / domain rules
↓
Strategy Router
  ├─ DIRECT_RETRIEVAL
  ├─ QUERY_REWRITE_SIMPLIFY
  ├─ HYDE_RETRIEVAL
  ├─ QUERY_DECOMPOSITION
  ├─ CLARIFY
  ├─ NO_ANSWER
  └─ UNSUPPORTED
↓
受控执行层（Phase 4 小步接入）
↓
答案展示层
```

关键原则：

- Query Planning V2 是“统一规划 envelope”，不是新的自由 planner。
- 领域 adapter 负责把现有物流 / BOM 结果转换成统一 V2 schema。
- Strategy Router 只做策略分类和可执行性判断。
- 只有 `DIRECT_RETRIEVAL`、受控 `QUERY_DECOMPOSITION`、既有 `CLARIFY`、既有 `NO_ANSWER / UNSUPPORTED` 可逐步接入正式链路。
- `QUERY_REWRITE_SIMPLIFY` 与 `HYDE_RETRIEVAL` 初期只做 shadow 记录，不影响正式查询。

---

## 3. Strategy 枚举

建议新增稳定枚举 `QueryPlanningV2Strategy`：

```python
from typing import Literal

QueryPlanningV2Strategy = Literal[
    "DIRECT_RETRIEVAL",
    "HYDE_RETRIEVAL",
    "QUERY_DECOMPOSITION",
    "QUERY_REWRITE_SIMPLIFY",
    "CLARIFY",
    "NO_ANSWER",
    "UNSUPPORTED",
]
```

策略定义：

| 策略 | 定义 | 初期执行方式 |
| --- | --- | --- |
| `DIRECT_RETRIEVAL` | 意图明确、槽位完整，可落到现有白名单 `query_key` / planner / query service | 可复用现有正式链路 |
| `HYDE_RETRIEVAL` | 问题抽象、直接检索效果差，生成假设答案 / 语义扩展文本用于检索增强 | Phase 3/4 仅 shadow / PoC，不进入 SQL |
| `QUERY_DECOMPOSITION` | 多实体、多时间、多指标、多方面复杂问题，拆成多个受控子查询 | 只扩展现有受控 `composite_decomposed` 白名单 |
| `QUERY_REWRITE_SIMPLIFY` | 口语化、冗长、不规范问题，改写为标准查询问法 | 仅 shadow，不覆盖原始问题 |
| `CLARIFY` | 条件不足、指标不明确、实体不明确，需要追问 | 复用现有澄清能力 |
| `NO_ANSWER` | 数据为空、无可用数据、权限 / 数据源不可用，无法给出答案 | 输出可审计无答案原因 |
| `UNSUPPORTED` | 数据源不支持、业务口径未固化、超出当前能力边界 | 复用现有 unsupported 能力 |

`NO_ANSWER` 与 `UNSUPPORTED` 区分：

- `NO_ANSWER`：理论上属于支持范围，但当前没有可用数据或执行条件不足，例如数据表未就绪、筛选后无记录、权限或数据源不可用。
- `UNSUPPORTED`：问题本身超出已支持数据源、业务口径或确定性计算边界，例如预测趋势、开放式方案设计、未固化业务定义。

---

## 4. 统一 Query Plan Schema

建议新增统一 schema，命名可为：

- `backend/app/domains/query_planning/schemas/query_plan_v2.py`

或在 Phase 3 先放在：

- `backend/app/domains/shared/query_planning/schemas.py`

推荐 Pydantic 结构：

```python
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

QueryPlanningV2Domain = Literal["logistics", "plan_bom", "unknown"]
QueryPlanningV2Strategy = Literal[
    "DIRECT_RETRIEVAL",
    "HYDE_RETRIEVAL",
    "QUERY_DECOMPOSITION",
    "QUERY_REWRITE_SIMPLIFY",
    "CLARIFY",
    "NO_ANSWER",
    "UNSUPPORTED",
]

class QueryPlanningV2Slots(BaseModel):
    """统一槽位结构。

    metrics: 指标槽位，例如发运量、运费、单瓦成本、BOM 用量、功率档位比例。
    dimensions: 维度槽位，例如年份、月份、承运商、客户、订单、物料、供应商。
    filters: 过滤条件，必须为领域 adapter 校验后的受控字段。
    time_range: 时间条件，保留原始表达和标准化表达。
    entities: 业务实体，例如订单号、评审号、客户实例、承运商名称。
    """

    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    time_range: dict[str, Any] = Field(default_factory=dict)
    entities: dict[str, Any] = Field(default_factory=dict)

class QueryPlanningV2SubQuery(BaseModel):
    """受控子查询结构。

    子查询只允许承载候选计划，不允许承载 SQL。
    每个子查询最终必须由领域 adapter 回构为白名单 query_key 或受控 service 调用。
    """

    sub_query_id: str
    source_clause: str = ""
    original_question: str = ""
    rewritten_question: str | None = None
    strategy: QueryPlanningV2Strategy = "DIRECT_RETRIEVAL"
    intent: str = "unknown"
    query_key: str | None = None
    slots: QueryPlanningV2Slots = Field(default_factory=QueryPlanningV2Slots)
    needs_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)
    unsupported_reason: str | None = None
    executable: bool = False
    validation_errors: list[str] = Field(default_factory=list)

class QueryPlanningV2GuardrailDecision(BaseModel):
    """统一 Guardrail 决策摘要。

    该结构只保存摘要和可审计字段，领域内完整对象可放入 domain_debug。
    """

    guardrail_enabled: bool = False
    guardrail_mode: str = "off"
    final_source: str = "rule"
    rule_query_key: str | None = None
    llm_top_query_key: str | None = None
    llm_confidence: float = 0.0
    policy_locked: bool = False
    assist_recommended: bool = False
    assist_applied: bool = False
    blocked_reason: str | None = None
    rollback_reason: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

class QueryPlanningV2ExecutionPolicy(BaseModel):
    """执行安全策略。

    llm_can_execute: LLM 是否允许直接执行，固定 false。
    sql_generation_allowed: 是否允许生成 SQL，固定 false。
    requires_query_key_whitelist: 可执行查询是否必须命中白名单 query_key。
    retrieval_only: 是否仅用于检索增强。
    shadow_only: 是否仅影子运行。
    """

    llm_can_execute: bool = False
    sql_generation_allowed: bool = False
    requires_query_key_whitelist: bool = True
    retrieval_only: bool = False
    shadow_only: bool = True
    executable: bool = False

class QueryPlanningV2Audit(BaseModel):
    """审计字段。

    trace_id: 请求追踪 ID。
    created_at: 生成时间。
    planner_version: Query Planning V2 版本。
    domain_adapter_version: 领域 adapter 版本。
    shadow: 是否影子模式。
    """

    trace_id: str | None = None
    created_at: str = ""
    planner_version: str = "query_planning_v2.0"
    domain_adapter_version: str = ""
    shadow: bool = True

class QueryPlanningV2Plan(BaseModel):
    """Query Planning V2 统一输出。

    所有业务问题进入正式检索 / SQL / RAG 前，都可以生成该结构用于审计、回放和测试。
    """

    schema_version: str = "query_plan_v2.0"
    domain: QueryPlanningV2Domain = "unknown"
    original_question: str
    strategy: QueryPlanningV2Strategy
    intent: str = "unknown"
    query_key: str | None = None
    slots: QueryPlanningV2Slots = Field(default_factory=QueryPlanningV2Slots)
    rewritten_question: str | None = None
    hyde_text: str | None = None
    sub_queries: list[QueryPlanningV2SubQuery] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    no_answer_reason: str | None = None
    unsupported_reason: str | None = None
    guardrail_decision: QueryPlanningV2GuardrailDecision = Field(default_factory=QueryPlanningV2GuardrailDecision)
    rule_plan: dict[str, Any] = Field(default_factory=dict)
    llm_result: dict[str, Any] = Field(default_factory=dict)
    execution_policy: QueryPlanningV2ExecutionPolicy = Field(default_factory=QueryPlanningV2ExecutionPolicy)
    audit: QueryPlanningV2Audit = Field(default_factory=QueryPlanningV2Audit)
    warnings: list[str] = Field(default_factory=list)
    domain_debug: dict[str, Any] = Field(default_factory=dict)
```

---

## 5. 字段设计说明

### 5.1 `domain`

取值：

- `logistics`
- `plan_bom`
- `unknown`

Domain Router 初期可以使用显式入口判断：

- 物流 `data-qa` endpoint 生成 `domain=logistics`；
- Plan BOM QA endpoint 生成 `domain=plan_bom`；
- 未来统一智能助手入口再做语义 domain router。

### 5.2 `intent`

保存领域意图，例如：

物流：

- `aggregate`
- `ranking`
- `comparison`
- `detail`
- `composite`
- `clarification`
- `unsupported`

Plan BOM：

- `single_order_query`
- `multi_order_table`
- `order_comparison`
- `material_usage`
- `supplier_recommendation`
- `plan_power_prediction`
- `clarification`
- `unsupported`

V2 不强制两个领域 intent 完全相同，但要求可审计、可测试。

### 5.3 `slots`

统一 slots 只保存“受控字段”，不保存任意 SQL 片段。

物流常见 slots：

- `metrics`: `shipment_mw`、`total_fee`、`fee_per_watt`、`trip_count`、`quantity`
- `dimensions`: `year`、`month`、`region`、`province`、`carrier`、`customer`
- `filters`: `biz_year`、`biz_month`、`region_name`、`logistics_company_name`、`customer_name`
- `time_range`: 原始年份、标准年份、月份范围
- `entities`: 承运商、客户、项目名等

Plan BOM 常见 slots：

- `metrics`: `material_usage`、`bom_count`、`power_distribution`、`supplier_efficiency`
- `dimensions`: `order_no`、`review_no`、`customer_instance`、`material_type`、`supplier`
- `filters`: 由 Plan BOM adapter 校验后的受控字段
- `entities`: 订单号、文件名、客户实例、评审号、版本、供应商

### 5.4 `rewritten_question`

用于 `QUERY_REWRITE_SIMPLIFY`。

规则：

1. 必须保留 `original_question`。
2. `rewritten_question` 不得覆盖 `original_question`。
3. 初期只能用于 shadow 诊断和检索 / planner 辅助对比。
4. 不允许把 rewrite 结果直接当用户真实问题写入业务答案。
5. rewrite 不能新增实体、时间、指标或业务口径。

### 5.5 `hyde_text`

用于 `HYDE_RETRIEVAL`。

规则：

1. `hyde_text` 是“假设答案 / 语义扩展文本”，只用于检索增强。
2. `hyde_text` 不是事实答案。
3. `hyde_text` 不得进入结构化 SQL 查询。
4. `hyde_text` 不得在最终答案中展示为业务事实。
5. HYDE 初期只用于 RAG / 文档检索 PoC，不进入物流 / BOM 结构化查询执行。
6. `execution_policy.retrieval_only = true`。
7. `execution_policy.executable = false`。

### 5.6 `sub_queries`

用于 `QUERY_DECOMPOSITION`。

规则：

1. 拆分是否成立必须由 LLM 语义理解主导。
2. 后端只做白名单、字段能力、单位口径、source clause grounding、回指引用等安全校验。
3. 每个子查询必须有 `source_clause`，并能映射回原始问题片段。
4. 每个子查询必须落到白名单 `query_key` 或受控 service。
5. 不允许子查询包含 SQL。
6. 不允许子查询依赖前一个子查询结果，除非后端已有确定性 materialization 能力。
7. 对“这些地址 / 上述地址 / 上面的地址”等回指问题，默认 fail closed 到澄清或 unsupported。
8. 对 unsupported 单位或字段，不允许替换成近似支持字段。

### 5.7 `clarification_questions`

用于 `CLARIFY`。

规则：

1. 条件不足、指标不明确、实体不明确时返回。
2. 复用现有物流澄清能力与 Plan BOM 候选消歧能力。
3. LLM 可辅助表达，但不能把澄清改成成功查询。
4. 必须记录缺失 slots。

### 5.8 `no_answer_reason` 与 `unsupported_reason`

`no_answer_reason`：

- 查询范围支持，但当前无法给出答案；
- 例如筛选后无记录、数据未初始化、权限不足、数据源暂不可用。

`unsupported_reason`：

- 问题超出当前能力；
- 例如预测趋势、开放式方案设计、未固化业务口径、无对应数据源。

### 5.9 `guardrail_decision`

统一保存 Guardrail 摘要。

物流域初期直接从 `LogisticsLlmGuardrailDecision` 映射：

- `guardrail_enabled`
- `guardrail_mode`
- `final_source`
- `rule_query_key`
- `llm_top_query_key`
- `llm_confidence`
- `policy_locked`
- `assist_recommended`
- `assist_applied`
- `blocked_reason`
- `rollback_reason`

Plan BOM 初期若没有同等级 Guardrail，可生成保守默认值：

- `final_source=rule`
- `guardrail_enabled=false`
- `policy_locked=true` 对明确缺槽 / unsupported 场景生效

后续再补 Plan BOM 专属 Guardrail。

---

## 6. Strategy Router 设计

### 6.1 路由优先级

建议优先级：

```text
1. 规则层明确 unsupported → UNSUPPORTED
2. 规则层明确 needs_clarification → CLARIFY
3. 规则层明确 no data / no permission / source unavailable → NO_ANSWER
4. Guardrail 允许 `composite_decomposed` 或候选中存在已校验 `sub_queries` → QUERY_DECOMPOSITION
5. 规则层命中普通白名单 query_key 且 slots 完整 → DIRECT_RETRIEVAL
6. 问题口语化 / 冗长但规则已有安全结果 → QUERY_REWRITE_SIMPLIFY shadow
7. 问题抽象且属于非结构化检索候选 → HYDE_RETRIEVAL shadow
8. 无法分类 → CLARIFY 或 UNSUPPORTED，fail closed
```

注意：

- `QUERY_REWRITE_SIMPLIFY` 和 `HYDE_RETRIEVAL` 初期不应覆盖 `DIRECT_RETRIEVAL` 的正式结果。
- 如果规则层已经给出 B/C，rewrite 和 HYDE 不允许绕过 B/C。
- `QUERY_DECOMPOSITION` 只在 Guardrail 允许且后端校验通过时输出可执行子计划。
- `query_key=composite_decomposed` 不应被普通 `DIRECT_RETRIEVAL` 吞掉；它必须按复合计划路径校验并执行。

### 6.2 DIRECT_RETRIEVAL 策略

可执行条件：

1. `query_key` 非空；
2. `query_key` 在领域白名单内；
3. `query_key` 不是 `composite_decomposed` 或其他复合计划 key；
4. slots 经领域 adapter 校验通过；
5. `needs_clarification=false`；
6. `unsupported_reason` 为空；
7. `execution_policy.sql_generation_allowed=false`；
8. `execution_policy.llm_can_execute=false`；
9. `execution_policy.executable=true`。

### 6.3 CLARIFY 策略

触发条件：

- 缺时间、指标、实体、维度、口径；
- Plan BOM 多候选无法消歧；
- 用户问题包含人名 / 业务词但无法确定字段口径；
- 指标单位不明确。

输出要求：

- `strategy=CLARIFY`
- `clarification_questions` 非空
- `slots` 中记录已识别部分
- `execution_policy.executable=false`

### 6.4 NO_ANSWER / UNSUPPORTED 策略

`NO_ANSWER` 触发条件：

- 支持查询但数据为空；
- 服务层表未就绪；
- 数据源暂不可用；
- 权限不足；
- 当前筛选条件无匹配数据。

`UNSUPPORTED` 触发条件：

- 数据源不支持；
- 业务口径未固化；
- 问题要求预测、开放式分析、治理方案、未建模字段；
- 用户要求 LLM 直接推断事实。

输出要求：

- `no_answer_reason` 或 `unsupported_reason` 必须非空；
- 给出可改问建议；
- `execution_policy.executable=false`。

### 6.5 QUERY_REWRITE_SIMPLIFY 策略

初期只做 shadow。

触发条件：

- 原问题口语化、冗长、存在多余寒暄；
- 原问题有明显同义词，可改写为标准问法；
- 规则 planner 已经有安全结果，rewrite 仅用于对比。

禁止：

- 新增原问题没有的时间、实体、指标；
- 删除关键限制条件；
- 用 rewrite 覆盖原问题；
- 让 rewrite 绕过澄清 / 拒答。

### 6.6 HYDE_RETRIEVAL 策略

初期只做 PoC / shadow，不进入结构化查询。

触发条件：

- 用户问题偏抽象；
- 更适合文档 / RAG 检索；
- 直接关键词检索可能召回差；
- 不属于结构化 SQL 聚合查询。

禁止：

- HYDE 文本进入 SQL；
- HYDE 文本作为最终事实答案；
- HYDE 改写 B/C 边界；
- HYDE 生成不存在的订单、客户、供应商、金额、数量、比例、日期、规格、功率等事实。

### 6.7 QUERY_DECOMPOSITION 策略

初期只扩展物流现有 `composite_decomposed`，不做自由拆分。

必要校验：

1. 顶层 `query_key` 必须是 `composite_decomposed` 或未来白名单复合 key。
2. 子查询数量必须符合已审计 pattern。
3. 每个 `source_clause` 必须来自原始问题，不能是整句偷懒。
4. `source_clause` 之间不能重叠或互相包含。
5. 子查询必须覆盖原始问题中的实质 ask。
6. 每个子查询 `query_key` 必须在子查询白名单内。
7. 子查询 filters 必须通过字段能力校验。
8. 子查询不得依赖前一个子查询结果。
9. 遇到回指、unsupported 单位、未固化字段，必须 fail closed。

---

## 7. Domain Adapter 设计

### 7.1 Logistics Adapter

建议新增：

- `backend/app/domains/query_planning/services/logistics_adapter.py`

职责：

1. 调用或接收 `LogisticsDataQaPlanner` 的 rule plan。
2. 调用或接收 `LogisticsNluCenterService` 的 shadow result。
3. 调用 Guardrail 生成 `guardrail_decision`。
4. 将 `LogisticsDataQaPlan` 映射为 `QueryPlanningV2Plan`。
5. 将物流 `filters` / `metrics` / `dimensions` 映射到统一 slots。
6. 根据 rule plan 与 Guardrail 决策选择 strategy。
7. 保持原物流主链路不变。

映射建议：

| Logistics 字段 | V2 字段 |
| --- | --- |
| `plan.domain` | `domain` |
| `request.question` | `original_question` |
| `plan.intent` | `intent` |
| `plan.query_key` | `query_key` |
| `plan.metrics` | `slots.metrics` |
| `plan.dimensions` | `slots.dimensions` |
| `plan.filters` | `slots.filters` |
| `plan.needs_clarification` | `strategy=CLARIFY` |
| `plan.clarification_questions` | `clarification_questions` |
| `plan.unsupported_reason` | `unsupported_reason` |
| `guardrail decision` | `guardrail_decision` |
| `llm_result` | `llm_result` |
| `plan.model_dump()` | `rule_plan` |

### 7.2 Plan BOM Adapter

建议新增：

- `backend/app/domains/query_planning/services/plan_bom_adapter.py`

职责：

1. 调用或接收 `PlanBomNluCenterService` 结果。
2. 将 BOM 领域 slots 映射为统一 `QueryPlanningV2Slots`。
3. 识别单订单、多订单表格、订单对比、缺槽澄清、不支持等策略。
4. 不替换 `PlanBomQaService` 的正式执行链路。
5. 为未来 BOM Guardrail 预留字段。

Phase 3 的 Query Planning V2 定位在正式检索 / SQL / RAG 前，因此 Plan BOM adapter 初期应优先依赖 `PlanBomNluCenterService`、已存在领域规则和可复用的解析函数生成候选计划；不应在 planning 阶段调用会实际查数、组装最终回答或写历史的 `PlanBomQaService.ask()`。如果确需对照 `PlanBomQaService` 的结果，只能作为 post-hoc shadow 观测，不能作为 pre-retrieval planning 的事实来源。

Plan BOM adapter 不能把 BOM 语义强行套进物流字段，例如不能把 BOM 订单号写成物流承运商，不能把物料类型写成运输方式。

---

## 8. 日志与落库策略

### 8.1 Phase 3：复用现有日志，新增 V2 payload

Phase 3 不建议立即新增数据库迁移。建议先：

日志写入分两类：独立诊断接口调用时，可能不存在既有业务 `sys_query_log` 行，此时只写 JSONL audit；嵌入现有物流 / BOM QA 链路做 shadow 观测时，再把 `query_plan_v2` 摘要附加到对应 `sys_query_log.request_payload` 或 response meta 中。

1. 在 `sys_query_log.request_payload` 中增加：

```json
{
  "query_plan_v2": {...},
  "query_plan_v2_shadow": true
}
```

2. 新增 JSONL：

```text
data/logs/query_planning_v2_audit.jsonl
```

3. 每条 JSONL 记录包含：

- `trace_id`
- `created_at`
- `domain`
- `original_question`
- `strategy`
- `query_key`
- `guardrail_decision`
- `rule_plan`
- `llm_result`
- `rewritten_question`
- `hyde_text`
- `sub_queries`
- `execution_policy`
- `warnings`

### 8.2 Phase 4 / 5：评估独立表

当 V2 shadow 稳定后，再评估新增表：

```text
sys_query_plan_v2_log
```

建议字段：

- `id`
- `trace_id`
- `domain`
- `strategy`
- `question_text`
- `query_key`
- `schema_version`
- `planner_version`
- `query_plan_payload`
- `guardrail_payload`
- `llm_payload`
- `execution_policy_payload`
- `status`
- `created_at`

注意：新增表必须等用户确认实施阶段后再做，本设计文档不要求立即迁移。

### 8.3 敏感信息处理

日志中禁止写入：

- API key；
- token；
- password；
- 数据库连接串；
- 生产凭证；
- 原始异常中的敏感片段。

异常信息必须经过 redaction 后写入。

---

## 9. 测试策略

### 9.1 Schema 稳定性测试

新增测试建议：

- `tests/unit/query_planning/test_query_plan_v2_schema.py`

覆盖：

1. 最小 `DIRECT_RETRIEVAL` plan 可序列化为稳定 JSON。
2. `original_question` 必填。
3. `strategy` 只能取枚举值。
4. `execution_policy.llm_can_execute` 默认 false。
5. `execution_policy.sql_generation_allowed` 默认 false。
6. `hyde_text` 存在时 `retrieval_only=true`。
7. `sub_queries` 不允许承载 SQL 字段。

### 9.2 Logistics Adapter 测试

新增测试建议：

- `tests/unit/query_planning/test_logistics_query_planning_adapter.py`

覆盖用户要求的物流场景：

1. 物流明确查询：
   - 问题：`2025年各承运商发运量是多少？`
   - 期望：`strategy=DIRECT_RETRIEVAL`，`domain=logistics`，`query_key` 命中白名单。

2. 物流口语化查询：
   - 问题：`帮我看下25年每家物流公司发了多少货，顺便给个占比。`
   - 期望：正式策略仍安全；rewrite 仅 shadow；原始问题保留。

3. 物流复杂复合查询：
   - 期望：只有 Guardrail + LLM candidate + 后端校验通过时输出 `QUERY_DECOMPOSITION`。

4. 物流缺槽澄清：
   - 问题：`哪个承运商最差？`
   - 期望：`strategy=CLARIFY`，追问评价标准和时间范围。

5. 物流无答案 / 拒答：
   - 问题：`预测未来三个月华东物流费用波动区间。`
   - 期望：`strategy=UNSUPPORTED`，不能输出可执行查询。

### 9.3 Plan BOM Adapter 测试

新增测试建议：

- `tests/unit/query_planning/test_plan_bom_query_planning_adapter.py`

覆盖用户要求的 BOM 场景：

1. BOM 单订单查询；
2. BOM 多订单表格；
3. BOM 订单对比；
4. BOM 缺槽澄清；
5. BOM 问法变体鲁棒性；
6. BOM 文件名 / 客户实例 / 单号 / 版本消歧；
7. 不允许 hardcode 具体客户或样例题。

### 9.4 Strategy Router 测试

新增测试建议：

- `tests/unit/query_planning/test_strategy_router.py`

覆盖：

1. rule unsupported 优先于 rewrite / HYDE。
2. rule clarification 优先于 rewrite / HYDE。
3. 普通 rule query_key 命中时默认 DIRECT；`composite_decomposed` 或带 `sub_queries` 的复合计划应优先判为 `QUERY_DECOMPOSITION`。
4. HYDE 只 retrieval-only。
5. rewrite 只 shadow。
6. decomposition 必须有白名单子查询。

### 9.5 回归题集

需要构建 Query Planning V2 回归样例：

| 类别 | 数量建议 | 说明 |
| --- | --- | --- |
| 物流明确查询 | ≥ 20 | DIRECT_RETRIEVAL |
| 物流问法变体 | ≥ 50 | 同义词、口语化、简称 |
| 物流复合问题 | ≥ 10 | 受控 decomposition |
| 物流澄清 | ≥ 20 | 缺时间、缺指标、缺实体、缺口径 |
| 物流拒答 | ≥ 20 | 预测、方案设计、无字段 |
| BOM 单订单 | ≥ 20 | 订单 / 文件名 / 版本 |
| BOM 多订单表格 | ≥ 10 | 多实体 |
| BOM 对比 | ≥ 10 | 两订单 / 多订单 |
| BOM 澄清 | ≥ 20 | 候选不唯一、缺订单 |
| BOM 变体 | ≥ 50 | 问法鲁棒性 |

---

## 10. 分阶段实施计划

### Phase 1：现状审计

已产出：

- `docs/QUERY_PLANNING_V2_CURRENT_AUDIT.md`

内容包括：

- 当前已有能力；
- 物流真实接入点；
- Plan BOM 真实接入点；
- DIRECT / CLARIFY / NO_ANSWER / UNSUPPORTED 覆盖情况；
- decomposition 范围；
- HYDE / rewrite 缺口；
- schema / 日志 / 测试缺口；
- 风险。

### Phase 2：设计方案

本文件即 Phase 2 设计方案：

- `docs/QUERY_PLANNING_V2_DESIGN.md`

### Phase 3：最小实现（建议下一轮执行）

目标：先实现 Query Planning V2 诊断接口或内部服务，不替换主链路。

建议任务：

1. 新增 schema：
   - `backend/app/domains/query_planning/schemas/query_plan_v2.py`

2. 新增 service：
   - `backend/app/domains/query_planning/services/query_planning_v2_service.py`
   - `backend/app/domains/query_planning/services/strategy_router.py`

3. 新增 adapters：
   - `backend/app/domains/query_planning/services/logistics_adapter.py`
   - `backend/app/domains/query_planning/services/plan_bom_adapter.py`

4. 新增内部诊断接口：
   - `backend/app/domains/query_planning/api/endpoints/query_plan_v2.py`

5. 新增 JSONL audit：
   - `data/logs/query_planning_v2_audit.jsonl`

6. 新增单元测试：
   - `tests/unit/query_planning/test_query_plan_v2_schema.py`
   - `tests/unit/query_planning/test_strategy_router.py`
   - `tests/unit/query_planning/test_logistics_query_planning_adapter.py`
   - `tests/unit/query_planning/test_plan_bom_query_planning_adapter.py`

Phase 3 验收：

- 对物流和 BOM 问题都能输出统一 `query_plan_v2`；
- 默认 `shadow=true`；
- 不影响原物流 `data-qa` 返回；
- 不影响原 Plan BOM QA 返回；
- 不生成 SQL；
- 不调用实际执行服务改变结果；
- 有日志；
- 有测试。

### Phase 4：受控接入

只允许小步接入：

1. `DIRECT_RETRIEVAL`
   - 继续复用现有 planner。

2. `CLARIFY`
   - 继续复用现有澄清能力。

3. `NO_ANSWER / UNSUPPORTED`
   - 继续复用现有 unsupported 能力。

4. `QUERY_REWRITE_SIMPLIFY`
   - 先 shadow，不影响正式结果。

5. `HYDE_RETRIEVAL`
   - 先 PoC，不进入结构化 SQL 查询。

6. `QUERY_DECOMPOSITION`
   - 只扩展现有 `composite_decomposed` 的受控白名单。

### Phase 5：测试和验收

必须补齐用户指定 10 类测试：

1. 物流明确查询；
2. 物流口语化查询；
3. 物流复杂复合查询；
4. 物流缺槽澄清；
5. 物流无答案拒答；
6. BOM 单订单查询；
7. BOM 多订单表格；
8. BOM 订单对比；
9. BOM 缺槽澄清；
10. 问法变体鲁棒性。

---

## 11. 鲁棒性要求

禁止完整问题文本硬编码。

错误方式：

```python
if question == "25年各家物流公司发运量分别是多少":
    ...
```

正确方式：

1. 年份识别；
2. 指标识别；
3. 维度识别；
4. 主体识别；
5. 同义词归一；
6. intent 编码；
7. `query_key` 映射；
8. Guardrail 校验；
9. 受控 repository / service 执行。

以下问题应归一到相同或兼容计划：

- `25年各家物流公司发运量分别是多少？`
- `2025年各承运商承运量是多少？`
- `25年物流供应商发货量分别是多少？`
- `2025年度物流公司运输量统计。`
- `帮我统计一下25年每家物流公司的发运量和占比。`

V2 测试必须覆盖这些变体，且不能靠完整文本匹配通过。

---

## 12. 安全边界

Query Planning V2 必须长期满足：

1. LLM 不能直接生成 SQL。
2. LLM 不能直接查数。
3. LLM 不能直接生成最终业务答案。
4. LLM 不能把 B/C 边界改成 A。
5. HYDE 文本不能作为事实答案。
6. rewrite 不能覆盖原始问题。
7. decomposition 子查询必须白名单校验。
8. 可执行查询必须走受控 service / repository。
9. 所有输出必须记录原始问题。
10. 所有输出必须记录 strategy。
11. 所有输出必须记录 slots。
12. 所有 LLM 候选必须记录 provider mode / confidence / guardrail。
13. 所有可执行计划必须可审计、可回放、可测试。
14. Plan BOM 不得被强行套用物流字段。
15. 日志不得泄露密钥、token、密码或生产连接串。

---

## 13. 推荐代码目录

建议后续实现目录：

```text
backend/app/domains/query_planning/
├── __init__.py
├── api/
│   ├── __init__.py
│   └── endpoints/
│       ├── __init__.py
│       └── query_plan_v2.py
├── schemas/
│   ├── __init__.py
│   └── query_plan_v2.py
└── services/
    ├── __init__.py
    ├── query_planning_v2_service.py
    ├── strategy_router.py
    ├── logistics_adapter.py
    ├── plan_bom_adapter.py
    └── query_plan_v2_audit_writer.py
```

测试目录：

```text
tests/unit/query_planning/
├── test_query_plan_v2_schema.py
├── test_strategy_router.py
├── test_logistics_query_planning_adapter.py
└── test_plan_bom_query_planning_adapter.py
```

说明：

- Phase 3 可先不注册外部公开 API，只提供内部 endpoint 或 service 供调试。
- 若注册 API，应放在内部诊断路由下，并明确不用于生产执行。

---

## 14. 最小实现伪代码

### 14.1 QueryPlanningV2Service

```python
class QueryPlanningV2Service:
    """Query Planning V2 统一诊断服务。

    该服务只生成统一 query_plan_v2，不直接执行 SQL 或替换正式 QA 主链路。
    """

    def __init__(self, logistics_adapter, plan_bom_adapter, strategy_router, audit_writer):
        self.logistics_adapter = logistics_adapter
        self.plan_bom_adapter = plan_bom_adapter
        self.strategy_router = strategy_router
        self.audit_writer = audit_writer

    def plan(self, *, question: str, domain: str, trace_id: str | None = None) -> QueryPlanningV2Plan:
        if domain == "logistics":
            candidate = self.logistics_adapter.build_candidate(question=question, trace_id=trace_id)
        elif domain == "plan_bom":
            candidate = self.plan_bom_adapter.build_candidate(question=question, trace_id=trace_id)
        else:
            candidate = self._build_unknown_domain_plan(question=question, trace_id=trace_id)

        plan = self.strategy_router.route(candidate)
        self.audit_writer.write(plan)
        return plan
```

### 14.2 StrategyRouter

```python
class QueryPlanningV2StrategyRouter:
    """统一策略路由器。

    只决定策略和执行安全标记，不执行查询。
    """

    def route(self, candidate: QueryPlanningV2Plan) -> QueryPlanningV2Plan:
        if candidate.unsupported_reason:
            candidate.strategy = "UNSUPPORTED"
            candidate.execution_policy.executable = False
            return candidate

        if candidate.clarification_questions:
            candidate.strategy = "CLARIFY"
            candidate.execution_policy.executable = False
            return candidate

        if candidate.no_answer_reason:
            candidate.strategy = "NO_ANSWER"
            candidate.execution_policy.executable = False
            return candidate

        if candidate.sub_queries:
            candidate.strategy = "QUERY_DECOMPOSITION"
            candidate.execution_policy.executable = all(item.executable for item in candidate.sub_queries)
            return candidate

        if candidate.query_key:
            candidate.strategy = "DIRECT_RETRIEVAL"
            candidate.execution_policy.executable = True
            return candidate

        candidate.strategy = "CLARIFY"
        candidate.clarification_questions = ["请补充更明确的查询条件，例如时间、对象和指标。"]
        candidate.execution_policy.executable = False
        return candidate
```

---

## 15. 验收标准映射

| 用户验收标准 | V2 设计响应 |
| --- | --- |
| 不破坏物流 data-qa 主链路 | Phase 3 shadow，不替换主链路 |
| 不破坏 BOM QA 主链路 | Plan BOM adapter 只包装现有结果 |
| Guardrail 继续有效 | logistics adapter 复用现有 Guardrail |
| LLM 不能直接生成 SQL | `execution_policy.sql_generation_allowed=false` |
| LLM 不能直接查数 | `execution_policy.llm_can_execute=false` |
| LLM 不能直接生成最终业务答案 | V2 仅 planning，答案展示层另行受控 |
| query_plan 稳定 JSON | Pydantic schema + schema_version |
| 记录原始问题 | `original_question` 必填 |
| 记录策略 | `strategy` 必填 |
| 记录 slots | `slots` 必填 |
| 记录 guardrail 决策 | `guardrail_decision` 必填 |
| 可日志审计 | JSONL + sys_query_log.request_payload |
| 问法变体通过回归 | 新增 regression set |
| B/C 边界不能被 LLM 改坏 | 策略优先级 + Guardrail + fail closed |
| 新增能力有测试报告 | Phase 5 输出测试报告 |

---

## 16. 推荐下一步

建议用户确认后进入 Phase 3 最小实现，且按 TDD 执行：

1. 先写 schema 测试；
2. 实现 `QueryPlanningV2Plan` schema；
3. 写 strategy router 测试；
4. 实现 strategy router；
5. 写 logistics adapter 测试；
6. 实现 logistics adapter；
7. 写 plan_bom adapter 测试；
8. 实现 plan_bom adapter；
9. 写 audit writer 测试；
10. 实现 JSONL audit；
11. 加内部诊断接口；
12. 跑 focused tests；
13. 跑现有物流 / BOM 关键回归；
14. 独立 review；
15. 输出 `diff.patch`、`test.log`、`final-acceptance.md`。

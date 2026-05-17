# 物流 QA Query Planning V2 MVP 架构设计

> 目标：把物流 QA 的自然语言解析主路径，从“regex / 关键词 / if-else 补洞”逐步升级为“LLM 语义理解生成结构化 QueryPlan + 后端白名单校验 + 受控 Repository 执行”。  
> 范围：第一阶段只做物流 QA `自然语言 -> QueryPlan`，不让 LLM 直接回答业务数据，不让 LLM 生成 SQL，不做全项目重构，不替换 BOM QA 主链路。

---

## 0. 当前仓库现状与可复用结论

当前仓库已经存在 Query Planning V2 的基础模块，不能另起一套完全平行体系。

### 0.1 已有可复用代码

| 能力 | 当前文件 | 复用方式 |
| --- | --- | --- |
| 统一 Query Planning V2 envelope | `backend/app/domains/query_planning/schemas/query_plan_v2.py` | 继续复用并扩展字段，不新建第二套跨域 schema。 |
| Query Planning V2 服务入口 | `backend/app/domains/query_planning/services/query_planning_v2_service.py` | 继续作为统一入口，第一阶段新增物流 LLM planner candidate。 |
| 物流 adapter | `backend/app/domains/query_planning/services/logistics_adapter.py` | 从“仅包装规则 planner”升级为“LLM candidate + validator + fallback”。 |
| 策略路由 | `backend/app/domains/query_planning/services/strategy_router.py` | 保留 DIRECT / CLARIFY / UNSUPPORTED / QUERY_DECOMPOSITION 策略，新增更严格可执行判定。 |
| shadow 审计与报表 | `query_plan_v2_audit_writer.py`、`shadow_snapshot_builder.py`、`shadow_report_service.py` | 继续用于影子运行、对比正式 planner 与 V2 planner。 |
| 物流规则 planner | `backend/app/domains/logistics/services/data_qa_planner.py` | 降级为 fallback / validator 参考 / 回构兼容，不再作为长期主语义理解来源。 |
| 物流槽位抽取 | `backend/app/domains/logistics/services/slot_extractor.py` | 降级为 alias normalize / 安全兜底，不再无限补 regex。 |
| 物流 LLM 理解层 | `backend/app/domains/logistics/services/llm_understanding_service.py` | 可复用 OpenAI 兼容客户端、白名单 query_key、JSON 提取和模型失败模式。 |
| 物流 Guardrail | `backend/app/domains/logistics/services/llm_understanding_guardrail_service.py` | 可复用“LLM 不执行、query_key 白名单、置信度、B/C 锁定”的安全原则，但需要从规则优先改成 V2 validator 优先。 |
| 物流 NLU Center | `backend/app/domains/logistics/services/nlu_center_service.py` | 可作为诊断/对比层，不建议继续让其规则抽取承担 V2 主理解。 |
| BOM NLU Center | `backend/app/domains/plan_bom/services/nlu_center_service.py` | 第一阶段不改 BOM，但后续可接入同一 QueryPlan schema。 |

### 0.2 当前缺口

1. 现有 `query_planning` 模块本质仍是 **规则 planner 的 shadow envelope**，不是 LLM 主导 Query Planning。
2. `LogisticsLlmUnderstandingService` 虽有 LLM 候选能力，但输出 schema 仍偏“理解结果”，不是完整可执行 QueryPlan。
3. Guardrail 现在偏“规则先行，LLM 只辅助通用兜底澄清”，这会保留“规则补洞”的核心瓶颈。
4. 缺少明确的 query_key capability registry：每个 `query_key` 允许哪些 filters / metrics / dimensions / group_by / aggregations / compare_mode。
5. 缺少统一 Validator，把 LLM 输出转为“可执行 / 澄清 / 不支持 / fallback”的确定性裁决。
6. 缺少面向物流 QA 的 LLM QueryPlan prompt、schema 校验、回放样例和回归矩阵。

### 0.3 本阶段架构判断

本阶段不应新建顶层 `app/services/query_planner_v2/` 来绕开现有分层；推荐在已有 `backend/app/domains/query_planning/` 下扩展共享能力，并在物流域建立领域适配：

```text
backend/app/domains/query_planning/              # 已有统一 Query Planning V2 域，继续复用
backend/app/domains/logistics/services/query_planner_v2/  # 新增物流领域 LLM Query Planner MVP
```

这样既满足“新增 query_planner_v2 模块”的可维护性，又不复制已有 `query_planning` envelope / audit / strategy_router。

---

## 1. Query Planning V2 总体架构设计

### 1.1 目标架构

```text
用户自然语言
  ↓
Domain Router
  ↓
Logistics Query Planner V2（第一阶段只启用物流）
  ├─ PromptBuilder：构造受控 LLM 规划提示词
  ├─ LlmParser：调用 LLM，只要求 JSON QueryPlan 候选
  ├─ JsonSchema Parser：解析、类型校验、失败显式 error
  ├─ Normalizer：别名归一、字段值标准化、时间范围标准化
  ├─ Validator：query_key 白名单、字段能力、槽位完整性、安全策略
  └─ Fallback：LLM 不可用/低置信/校验失败时回退旧 planner 或澄清
  ↓
Unified QueryPlan
  ↓
LogisticsDataQaPlan Adapter（兼容旧 service）
  ↓
LogisticsDataQaService / Repository / SQL 模板 / Python 计算
  ↓
确定性结果
  ↓
答案表达层（LLM 只能润色，不改数值）
```

### 1.2 架构原则

1. **LLM 负责理解**：表达等价、语义归类、槽位候选、query_key 候选由 LLM 主导。
2. **后端负责安全**：query_key 白名单、字段能力、指标合法性、时间边界、SQL 模板、数据权限、单位口径都由后端确定性校验。
3. **LLM 不直接执行**：禁止 SQL、禁止查库、禁止算数、禁止直接输出事实答案。
4. **QueryPlan 必须结构化**：任何可执行查询必须落到 Pydantic schema，并通过 validator。
5. **旧规则层降级**：regex / synonym / keyword 只作为 normalize / fallback / legacy compatibility，不再作为新语法主入口。
6. **先 shadow 后接管**：MVP 先输出 shadow QueryPlan，对比旧 planner；达到门槛后再小流量切换。
7. **fail closed**：LLM 输出不合法、不确定、越权、低置信或多候选冲突时，不执行，转澄清或旧链路。

---

## 2. 模块拆分

### 2.1 共享 Query Planning 域

复用并扩展已有目录：

```text
backend/app/domains/query_planning/
  schemas/
    query_plan_v2.py                 # 已有统一 schema；补充用户要求的 QueryPlan 字段
  services/
    query_planning_v2_service.py      # 已有统一入口；接入 logistics planner v2 candidate
    strategy_router.py                # 已有策略路由；加强 executable / shadow_only 判定
    query_plan_v2_audit_writer.py     # 已有 JSONL 审计
    shadow_snapshot_builder.py        # 已有正式结果 vs shadow 快照
    shadow_report_service.py          # 已有 shadow 报表
    response_meta_exposure_service.py # 已有安全 meta 暴露
```

### 2.2 新增物流领域 Query Planner V2 MVP

新增目录建议：

```text
backend/app/domains/logistics/services/query_planner_v2/
  __init__.py
  planner.py                 # 编排入口：natural language -> validated QueryPlan
  prompt_builder.py          # 构造 LLM QueryPlan 提示词
  llm_parser.py              # 调用 LLM 并解析 JSON
  normalizer.py              # 值归一化：年份、月份、车型、始发地、城市、指标口径
  validator.py               # 后端白名单与字段能力校验
  capability_registry.py     # query_key 能力注册表
  legacy_adapter.py          # QueryPlan <-> LogisticsDataQaPlan 兼容适配
  fallback.py                # LLM 失败 / 校验失败 / 低置信 fallback 策略
  examples.py                # MVP few-shot 样例，或拆到 prompts/examples/*.json
```

### 2.3 为什么不直接放到 `app/services/query_planner_v2/`

项目当前后端按 domain 分层，物流 QA、Plan BOM QA 都在 `backend/app/domains/...` 下。直接新增顶层 `app/services/query_planner_v2/` 会绕开现有 domain 边界，后续容易把物流/BOM/经营分析混在一起。

推荐做法：

- 统一 schema、审计、strategy：放 `backend/app/domains/query_planning/`。
- 物流领域理解、字段能力、query_key 口径：放 `backend/app/domains/logistics/services/query_planner_v2/`。
- 未来 BOM 领域接入：放 `backend/app/domains/plan_bom/services/query_planner_v2/` 或改造现有 `nlu_center_service.py`。

---

## 3. 目录结构

第一阶段建议最终结构：

```text
backend/app/domains/query_planning/
  schemas/
    query_plan_v2.py
  services/
    query_planning_v2_service.py
    logistics_adapter.py              # 改造：可选择 rule_shadow 或 llm_planner_v2
    strategy_router.py
    query_plan_v2_audit_writer.py
    shadow_snapshot_builder.py
    shadow_report_service.py

backend/app/domains/logistics/services/query_planner_v2/
  __init__.py
  planner.py
  prompt_builder.py
  llm_parser.py
  normalizer.py
  validator.py
  capability_registry.py
  legacy_adapter.py
  fallback.py

backend/app/domains/logistics/config/
  logistics_query_planner_v2_capabilities.json  # 可选：query_key 能力白名单配置化

backend/app/domains/logistics/prompts/
  query_planner_v2_system.md                    # 可选：提示词模板
  query_planner_v2_examples.json                # 可选：few-shot 样例

tests/unit/logistics/query_planner_v2/
  test_prompt_builder.py
  test_llm_parser.py
  test_normalizer.py
  test_validator.py
  test_legacy_adapter.py

tests/business_acceptance/
  test_logistics_query_planner_v2_mvp.py
```

---

## 4. 数据流

### 4.1 Shadow 阶段数据流

```text
POST /logistics/data-qa/query
  ↓
现有 LogisticsDataQaPlanner 执行正式结果
  ↓
QueryPlanningV2ShadowSnapshotBuilder 生成旧 shadow
  ↓
LogisticsQueryPlannerV2 生成 LLM QueryPlan candidate
  ↓
Validator 判定 candidate 是否可执行 / 需澄清 / 不支持 / fallback
  ↓
记录 query_plan_v2_shadow：
  - formal_query_key
  - llm_candidate_query_key
  - validated_query_key
  - matched / mismatch
  - blocked_reason
  - risk_tags
  ↓
正式答案不变
```

### 4.2 Assist 灰度阶段数据流

仅当 shadow 指标达到门槛后，允许小流量：

```text
用户问题
  ↓
LogisticsQueryPlannerV2
  ↓
Validated QueryPlan
  ↓
如果满足：
  - strategy = DIRECT_RETRIEVAL
  - query_key 在灰度白名单
  - confidence >= 阈值
  - required slots 完整
  - validator 无 error
  - 不触发 B/C 锁定
  ↓
转换为 LogisticsDataQaPlan
  ↓
复用 LogisticsDataQaService 执行
```

旧 planner 仍保留：

- LLM 不可用时 fallback；
- validator 失败时 fallback；
- 灰度未覆盖 query_key 时 fallback；
- 线上回滚时 fallback。

---

## 5. Prompt 设计

### 5.1 Prompt 总原则

LLM prompt 只允许要求模型输出结构化 QueryPlan 候选，不允许输出答案。

系统提示词必须写死：

1. 你是“查询规划器”，不是数据查询器。
2. 你不能生成 SQL。
3. 你不能查数据库。
4. 你不能计算业务数值。
5. 你只能从后端提供的 `query_key` 白名单中选择。
6. 如果字段不在能力表中，必须输出 `unsupported_reason` 或 `needs_clarification`。
7. 如果槽位缺失，必须输出澄清，不得猜测。
8. 输出必须是严格 JSON，不能有 markdown。

### 5.2 Prompt 输入内容

PromptBuilder 应传入：

```json
{
  "domain": "logistics",
  "question": "2025年合肥至马鞍山17.5米车的平均运费",
  "allowed_query_keys": [...],
  "capabilities": {
    "hist_route_pricing_analysis": {
      "description": "历史线路运价/平均费用/报价/年度对比/月度趋势",
      "required_any": ["year_or_time_range"],
      "allowed_filters": ["years", "months", "origin_place", "province", "city", "vehicle_type", "price_metric", "view_mode"],
      "allowed_metrics": ["avg_fee", "unit_price_per_vehicle", "total_fee", "row_count"],
      "allowed_dimensions": ["month", "year", "origin_place", "city", "province", "vehicle_type"],
      "allowed_group_by": ["biz_month", "biz_year", "city", "province"],
      "allowed_compare_modes": ["year_over_year", "month_over_month", "year_compare"]
    }
  },
  "business_defaults": {
    "historical_time_scope_when_no_time": "2023-2026 per current business rule, but repository support must validate actual source availability",
    "default_route_price_metric_for_运费": "total_fee",
    "default_route_price_metric_for_报价_运价": "unit_price_per_vehicle"
  }
}
```

### 5.3 Few-shot 样例

需要覆盖语义等价，不靠 regex：

```json
[
  {
    "question": "2025年合肥发马鞍山17.5米车的平均运费",
    "query_key": "hist_route_pricing_analysis",
    "filters": {"years": [2025], "origin_place": "合肥", "city": "马鞍山", "vehicle_type": "17.5", "view_mode": "avg_fee", "price_metric": "total_fee"}
  },
  {
    "question": "2025年合肥至马鞍山17.5米车的平均运费",
    "query_key": "hist_route_pricing_analysis",
    "filters": {"years": [2025], "origin_place": "合肥", "city": "马鞍山", "vehicle_type": "17.5", "view_mode": "avg_fee", "price_metric": "total_fee"}
  },
  {
    "question": "从合肥运到马鞍山，17米五车，2025年平均每车多少钱",
    "query_key": "hist_route_pricing_analysis",
    "filters": {"years": [2025], "origin_place": "合肥", "city": "马鞍山", "vehicle_type": "17.5", "view_mode": "avg_fee", "price_metric": "total_fee"}
  },
  {
    "question": "2025年合肥到安徽各城市17.5米车平均运费月度趋势",
    "query_key": "hist_route_pricing_analysis",
    "filters": {"years": [2025], "origin_place": "合肥", "province": "安徽", "vehicle_type": "17.5", "view_mode": "monthly_avg", "price_metric": "total_fee"},
    "group_by": ["biz_month"]
  },
  {
    "question": "2025年哪个城市运费最高，TOP10",
    "query_key": "hist_total_fee_city_rank",
    "filters": {"year": 2025},
    "metrics": ["total_fee"],
    "dimensions": ["city"],
    "limit": 10
  }
]
```

### 5.4 LLM 输出限制

模型输出只能是：

```json
{
  "query_key": "hist_route_pricing_analysis",
  "filters": {},
  "metrics": [],
  "dimensions": [],
  "group_by": [],
  "aggregations": [],
  "time_range": {},
  "compare_mode": null,
  "confidence": 0.0,
  "unsupported_reason": null,
  "clarification_questions": [],
  "reasoning_summary": "一句话说明理解依据，不能包含链式推理"
}
```

禁止字段：

- `sql`
- `where_clause`
- `database`
- `table_name`
- `answer`
- `computed_value`
- `python_code`
- `tool_call`

Parser 若发现这些字段，必须打 `risk_tags=["llm_attempted_execution"]` 并 fail closed。

---

## 6. QueryPlan Schema

用户期望的统一结构建议落到已有 `QueryPlanningV2Plan` 上，但补齐缺失字段。为了不破坏已有代码，可新增轻量业务计划模型 `ValidatedQueryPlan`，再包装到 `QueryPlanningV2Plan.slots` / 顶层字段。

### 6.1 推荐新增模型

```python
class QueryPlan(BaseModel):
    """LLM Query Planner V2 的领域无关业务计划。"""

    query_key: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    aggregations: list[str] = Field(default_factory=list)
    time_range: dict[str, Any] = Field(default_factory=dict)
    compare_mode: str | None = None
    confidence: float = 0.0
    unsupported_reason: str | None = None
    clarification_questions: list[str] = Field(default_factory=list)
```

### 6.2 推荐扩展现有 `QueryPlanningV2Slots`

现有字段已有：

- metrics
- dimensions
- filters
- group_by
- sort
- limit
- entities

建议补充：

```python
aggregations: list[str] = Field(default_factory=list)
time_range: dict[str, Any] = Field(default_factory=dict)
compare_mode: str | None = None
```

这样能满足用户要求，同时兼容已有 `QueryPlanningV2Plan`。

### 6.3 QueryPlan 与旧 `LogisticsDataQaPlan` 映射

| QueryPlan 字段 | LogisticsDataQaPlan 字段 | 说明 |
| --- | --- | --- |
| `query_key` | `query_key` | 必须白名单命中。 |
| `metrics` | `metrics` | validator 过滤非法指标。 |
| `dimensions` | `dimensions` | validator 过滤非法维度。 |
| `filters` | `filters` | 只允许 capability registry 声明字段。 |
| `group_by` | `group_by` | 仅允许受控字段。 |
| `aggregations` | `filters` 或 service 内部口径 | 第一阶段可只审计，不强行执行。 |
| `time_range` | `filters.year/months/years` | normalizer 转换。 |
| `compare_mode` | `filters.view_mode` 或 `compare_dim` | 年同比/月同比/年度对比统一映射。 |
| `confidence` | `response_meta` / audit | 不进入 SQL。 |
| `unsupported_reason` | `unsupported_reason` | C 类。 |
| `clarification_questions` | `clarification_questions` | B 类。 |

---

## 7. Validator 机制

Validator 是 V2 成败关键。它必须是后端确定性代码，不依赖 LLM 自我约束。

### 7.1 Capability Registry

第一阶段物流 MVP 支持 query_key：

1. `hist_route_pricing_analysis`：路线运价、平均费用、月度趋势、年度对比。
2. `hist_total_fee_city_rank`：城市费用 TOP 排名。
3. `hist_avg_fee_by_month`：月度平均费用趋势，若后续确认与路线能力重复，可统一到 route pricing。
4. `hist_carrier_kpi_by_year` 或现有承运商排名 query_key：TOP 排名。
5. 已有同比 query_key 或用受控 `compare_mode` 映射到现有年度/月度聚合 service。

建议能力注册表示例：

```python
@dataclass(frozen=True)
class QueryKeyCapability:
    query_key: str
    intent_types: set[str]
    allowed_filters: set[str]
    required_any_filters: list[set[str]]
    allowed_metrics: set[str]
    allowed_dimensions: set[str]
    allowed_group_by: set[str]
    allowed_aggregations: set[str]
    allowed_compare_modes: set[str]
    time_scope: Literal["historical", "system_2026", "mixed"]
    executable_service: str
```

### 7.2 校验步骤

Validator 顺序：

1. **Schema 校验**：JSON 能解析，字段类型正确，extra 字段被拒绝或记录风险。
2. **query_key 白名单**：`query_key` 必须在 capability registry。
3. **SQL 禁止校验**：出现 SQL/table/where/code/answer/computed_value 字段直接 fail closed。
4. **filters 白名单**：每个 filter key 必须被 query_key 允许。
5. **metrics 白名单**：非法 metric 删除并记 warning；关键 metric 非法则 fail closed。
6. **dimensions/group_by 白名单**：非法维度 fail closed 或澄清。
7. **time_range 校验**：历史数据允许 2023–2025，用户业务默认可含 2026，但必须按数据源分流；不能把 2026 系统数据误查历史台账。
8. **槽位完整性校验**：如路线运价至少需要时间、起点/目的地或省份/城市、指标口径。
9. **实体合法性校验**：始发地只允许当前可支持基地；城市/省份若无法归一则澄清，不伪造。
10. **compare_mode 校验**：年同比、月同比必须有可比较时间范围。
11. **置信度校验**：低于阈值时 fallback 或澄清，不执行。
12. **B/C 边界校验**：预测、开放分析、未固化口径、吨口径等保持 unsupported/clarification。
13. **输出可执行策略**：`executable=True/False`、`shadow_only=True/False`、`blocked_reason`、`risk_tags`。

### 7.3 Validator 输出

```python
class QueryPlanValidationResult(BaseModel):
    accepted: bool
    strategy: Literal["DIRECT_RETRIEVAL", "CLARIFY", "UNSUPPORTED", "NO_ANSWER", "QUERY_DECOMPOSITION"]
    normalized_plan: QueryPlan | None
    blocked_reason: str | None
    validation_errors: list[str]
    warnings: list[str]
    risk_tags: list[str]
    missing_slots: list[str]
```

---

## 8. fallback 策略

### 8.1 fallback 优先级

```text
LLM QueryPlan candidate
  ↓
Parser 失败？
  → 旧 LogisticsDataQaPlanner 或通用澄清
  ↓
Validator fail closed？
  → 若旧 planner 可回答，继续旧 planner；否则澄清/unsupported
  ↓
LLM 低置信？
  → 旧 planner；旧 planner 也澄清时，返回更具体澄清
  ↓
query_key 不在灰度白名单？
  → shadow only，正式继续旧 planner
  ↓
全部通过？
  → shadow 记录；灰度阶段可转换为 LogisticsDataQaPlan 执行
```

### 8.2 不同失败类型处理

| 失败类型 | 策略 |
| --- | --- |
| LLM 未配置 | 旧 planner 继续；记录 `llm_not_configured`。 |
| LLM 超时/异常 | 旧 planner 继续；记录 `llm_error`。 |
| JSON 解析失败 | 旧 planner 或澄清；记录原始错误摘要，不暴露 prompt。 |
| query_key 越权 | fail closed，不执行。 |
| filter 越权 | fail closed 或删除非关键 filter 后澄清，不执行。 |
| 缺关键槽位 | CLARIFY，尽量提出针对性问题。 |
| 低置信 | shadow only，正式旧 planner。 |
| 与旧 planner 冲突 | shadow only，进入差异报表，不自动覆盖。 |
| 明确 B/C 边界 | 保持 B/C，不允许 LLM 放行。 |

### 8.3 旧 regex 架构如何共存

旧架构不立即删除，角色调整为：

1. **正式 fallback**：V2 未灰度接管前，旧 planner 仍是正式执行来源。
2. **安全参考**：V2 输出与旧 planner 冲突时，先不自动覆盖，进入 shadow 报表。
3. **normalizer 工具**：保留年份、月份、车型、区域、省份等基础归一能力。
4. **B/C 边界库**：保留已审计的拒答/澄清策略，如吨口径、预测、额外费用明细缺失。
5. **回归保护**：所有旧验收题继续跑，防止 V2 引入倒退。

后续禁止继续走“新问法 -> 在正式 planner 补 regex”作为主修复方式；新问法应优先进入 V2 语义样例、capability、validator 或 prompt 优化。

---

## 9. 与旧 regex 架构共存和逐步替换

### 9.1 阶段 0：只建文档和回归矩阵

- 输出本文档。
- 整理物流 QA 现有 `query_key` 能力表。
- 整理 V2 MVP 测试集，尤其是“同义表达族”。

### 9.2 阶段 1：Shadow-only LLM QueryPlan

- 新增 `LogisticsQueryPlannerV2`。
- 对真实问题生成 `llm_query_plan_candidate`。
- Validator 只打分和审计，不影响正式结果。
- 报表统计：query_key match rate、clarification disagreement、unsupported disagreement、slot mismatch。

### 9.3 阶段 2：A 类稳定 query_key assist

优先接入：

1. `hist_route_pricing_analysis`
2. 城市/承运商 TOP 排名
3. 月度趋势
4. 年度对比

接入条件：

- shadow 连续通过阈值；
- query_key 命中率高；
- B/C 误放行为 0；
- 关键槽位准确率达标；
- 出现 conflict 时自动 fallback。

### 9.4 阶段 3：规则 planner 降级

- 新问法不再优先补 `data_qa_planner.py`。
- 旧 planner 保留为 fallback 和兼容。
- `slot_extractor.py` 停止无边界扩张，只维护确定性 normalize。

### 9.5 阶段 4：BOM QA 接入同一 QueryPlan

- 改造 `PlanBomNluCenterService` 输出 QueryPlan envelope。
- 保留 BOM 订单/版本/材料索引校验。
- LLM 只做意图和槽位候选，不能绕过 BOM repository。

---

## 10. 如何逐步迁移

### 10.1 迁移对象划分

| 问题类型 | 迁移优先级 | 原因 |
| --- | --- | --- |
| 路线运价 / 平均费用 | P0 | 当前 bug 暴露最明显，表达变体多，V2 价值高。 |
| 月度趋势 | P0 | 时间和 group_by 语义适合 LLM 规划，后端易校验。 |
| TOP 排名 | P0 | query_key、limit、排序指标结构清晰。 |
| 年同比 / 月同比 | P1 | compare_mode 需要标准化，但业务价值高。 |
| 复合问题拆分 | P1/P2 | 已有 LLM-led 方向，但风险更高，需受控白名单。 |
| BOM QA | P2 | 已有 NLU Center，可复用同 schema，但第一阶段不动。 |

### 10.2 每个 query_key 迁移步骤

1. 写 capability registry。
2. 写 prompt few-shot。
3. 写 validator tests。
4. 跑 shadow 对比旧 planner。
5. 补业务验收样例族。
6. 满足门槛后只对该 query_key 开 assist。
7. 出现任何 B/C 误放行，立即回滚该 query_key assist。

---

## 11. MVP 实施路线

### M0：设计与能力表

交付：

- 本文档；
- `hist_route_pricing_analysis`、TOP、月度趋势、同比能力表草案；
- 测试样例清单。

### M1：QueryPlan Schema 补齐

最小改动：

- 扩展 `QueryPlanningV2Slots`：`time_range`、`aggregations`、`compare_mode`。
- 新增 `QueryPlan` / `QueryPlanValidationResult` 模型，或作为领域内模型。
- 保证现有 tests 兼容。

### M2：物流 Query Planner V2 shadow

新增：

- `prompt_builder.py`
- `llm_parser.py`
- `normalizer.py`
- `validator.py`
- `capability_registry.py`
- `planner.py`

只做 shadow，不改正式答案。

### M3：路线运价 MVP

支持问法族：

- 合肥发马鞍山
- 合肥至马鞍山
- 合肥到马鞍山
- 从合肥运到马鞍山
- 合肥往马鞍山发17.5米车
- 2025年合肥到马鞍山17.5米车平均每车多少钱

统一输出：

```json
{
  "query_key": "hist_route_pricing_analysis",
  "filters": {
    "years": [2025],
    "origin_place": "合肥",
    "city": "马鞍山",
    "vehicle_type": "17.5",
    "view_mode": "avg_fee",
    "price_metric": "total_fee"
  },
  "metrics": ["avg_fee"],
  "aggregations": ["avg"],
  "confidence": 0.9
}
```

### M4：TOP / 趋势 / 同比

扩展：

- TOP 排名：识别 `limit`、排序指标、升降序。
- 月度趋势：识别 `group_by=[biz_month]`。
- 年同比：识别 `compare_mode=year_over_year`。
- 月同比：识别 `compare_mode=month_over_month`。

### M5：灰度接入

- 开关：`logistics_query_planner_v2_enabled`、`logistics_query_planner_v2_mode=shadow|assist|off`。
- 默认 shadow。
- assist 只开放 P0 query_key。
- 保留一键回滚到旧 planner。

---

## 12. 风险分析

| 风险 | 表现 | 对策 |
| --- | --- | --- |
| LLM 幻觉 query_key | 输出不存在的 query_key | 白名单校验，fail closed。 |
| LLM 幻觉字段 | 输出不存在 filter 或 metric | capability registry 拦截。 |
| LLM 误把 B/C 问题放行 | 未支持口径被执行 | B/C policy 后端锁定，validator 优先级高于 LLM。 |
| LLM 直接算数 | 输出 answer 或 computed_value | Parser 禁止字段扫描，命中即 fail closed。 |
| 2023–2025 历史与 2026 系统混查 | 时间范围映射错 | time_scope 校验，跨源问题必须拆分或澄清。 |
| 问法冲突 | “合肥到马鞍山到南京”被误识别 | validator 检查多段路径、多目的地，澄清。 |
| 低置信误执行 | 模型不确定仍给 plan | 置信度阈值 + shadow-only + 旧 planner fallback。 |
| 成本/延迟 | 每次 QA 多一次 LLM | shadow 采样、缓存、超时、异步审计；正式 assist 只对灰度 query_key 调用。 |
| 回归污染 | V2 接入影响旧验收题 | 全量 business_acceptance + V2 专项矩阵。 |
| Prompt 泄露或敏感信息 | 日志记录 raw prompt/API key | 不记录 api_key；prompt 日志默认关闭，审计只存摘要和 trace。 |

---

## 13. 推荐开发顺序

### 第 1 步：冻结“不要继续补 regex”原则

- 对新问法缺陷，优先补 V2 样例和 validator，而不是继续扩张 `data_qa_planner.py`。
- 紧急线上 bug 可短期补丁，但必须同步补 V2 regression case。

### 第 2 步：补能力表

先写 `hist_route_pricing_analysis` capability：

- allowed filters
- required slots
- allowed metrics
- allowed view_mode
- allowed compare_mode
- time_scope
- legacy adapter 映射

### 第 3 步：补 QueryPlan 模型和 validator 单测

不依赖真实 LLM，直接用 fake JSON：

- 合法 plan 通过；
- 非法 query_key 拦截；
- SQL 字段拦截；
- 缺城市/时间时澄清；
- 2026 历史 query_key 拦截或分流；
- 多段路径澄清。

### 第 4 步：实现 LLM Parser + PromptBuilder

- 注入 fake client；
- 固定 temperature=0；
- JSON 解析失败可审计；
- 不直接接 service。

### 第 5 步：接入 shadow

- 在 `QueryPlanningV2Service` 或物流 QA response meta 中记录 V2 plan。
- 与旧 planner 对比，不改答案。

### 第 6 步：路线运价 P0 验收

验收集至少覆盖：

```text
2025年合肥发马鞍山17.5米车的平均运费
2025年合肥至马鞍山17.5米车的平均运费
2025年合肥到马鞍山17.5米车的平均运费
2025年从合肥运到马鞍山17.5米车平均多少钱
2025年合肥往马鞍山发17米五车均费
2025年合肥到马鞍山17.5米车月度趋势
2024和2025年合肥到马鞍山17.5米车平均运费对比
```

### 第 7 步：小流量 assist

只开放：

```text
query_key = hist_route_pricing_analysis
mode = assist
confidence >= 0.9
validator.accepted = true
legacy adapter conversion = true
```

出现任何 validator 误放行或 B/C 误回答，立即回滚 `mode=shadow`。

---

## 14. 第一阶段“物流 QA Query Planner MVP”验收标准

### 14.1 功能验收

1. LLM 能把多种线路表达统一规划到 `hist_route_pricing_analysis`。
2. QueryPlan 包含 query_key、filters、metrics、dimensions、group_by、aggregations、time_range、compare_mode、confidence、unsupported_reason。
3. Validator 能拒绝非法 query_key、非法 filter、SQL、计算答案、低置信和 B/C 越界。
4. LLM 失败不影响旧 QA 主链路。
5. Shadow 报表能展示 V2 与旧 planner 的差异。

### 14.2 安全验收

1. `llm_can_execute=false`。
2. `sql_generation_allowed=false`。
3. LLM 输出 SQL/table/answer/computed_value 时 fail closed。
4. 只有白名单 query_key 可转换为旧 `LogisticsDataQaPlan`。
5. Repository 执行仍使用既有绑定参数和受控 service。

### 14.3 回归验收

1. 原物流 QA business acceptance 不倒退。
2. 新增 V2 planner 单测通过。
3. 新增线路语义变体验收集通过。
4. B/C 负向样例不被放行。
5. build / compile / static scan 通过。

---

## 15. 对 BOM QA 的后续衔接

第一阶段不改 BOM QA，但设计必须兼容：

1. `PlanBomNluCandidate` 后续可映射到同一 QueryPlan。
2. BOM 的 `intent` 可视为领域 query_key，但需要建立 BOM capability registry。
3. BOM 的订单号、BOM 文件名、客户实例、版本消歧必须继续由后端 repository 校验。
4. LLM 不能直接判断某 BOM 事实，只能抽取 `order_tail_no`、`material_category`、`bom_version`、`target_power_ratio` 等槽位候选。
5. BOM 接入顺序应晚于物流 P0，避免同时改两条主链路。

---

## 16. 本设计对当前缺陷的直接回应

当前“2025年合肥至马鞍山17.5米车的平均运费”误澄清，根因不是单个正则写少了，而是当前主路径仍依赖规则覆盖自然语言变体。

V2 后，该问题不应通过补：

```text
合肥 + 至/到 + 城市 + 车型
```

这类 regex 解决，而应由 LLM 语义规划为：

```json
{
  "query_key": "hist_route_pricing_analysis",
  "filters": {
    "years": [2025],
    "origin_place": "合肥",
    "city": "马鞍山",
    "vehicle_type": "17.5",
    "view_mode": "avg_fee",
    "price_metric": "total_fee"
  },
  "metrics": ["avg_fee"],
  "aggregations": ["avg"],
  "confidence": 0.9,
  "unsupported_reason": null
}
```

然后由 validator 确认：

- `hist_route_pricing_analysis` 是白名单；
- `origin_place/city/vehicle_type/years/view_mode/price_metric` 是允许字段；
- `2025` 属于历史台账时间范围；
- `17.5` 是可支持车型；
- `avg_fee + total_fee` 口径可由 repository 计算；
- 不含 SQL、不含直接答案、不含越权字段。

只有通过这些后，才转换为旧 service 可执行计划。

---

## 17. 结论

推荐从现在开始停止把“自然语言识别能力”继续堆到 `data_qa_planner.py` 的 regex / if-else 中。

第一阶段正确方向是：

```text
LLM 语义 QueryPlan 候选
  + 后端 capability registry
  + validator fail-closed
  + 旧 planner fallback
  + shadow 对比报表
```

先以物流 QA 的路线运价、平均费用、月度趋势、TOP 排名、年同比、月同比为 MVP 范围，形成稳定 `自然语言 -> QueryPlan` 能力。等 shadow 指标稳定后，再小范围把 `hist_route_pricing_analysis` 从旧规则主导迁移到 V2 assist。

# PLATFORM_M1_2_CONTRACT_BASELINE.md

## 一、文档用途

本文件用于沉淀【里程碑 1 / 子里程碑 1.2：统一契约基线与域接入规范草案】的阶段性输出。

本轮目标不是做代码级统一重构，而是先明确：

1. 平台统一响应结构的最小基线；
2. 状态码与解释结构的最小基线；
3. 查询历史 / 回放 / 审计字段的最小基线；
4. 域注册最小字段定义；
5. 第二业务域接入最小清单草案。

---

## 二、设计边界

### 1. 本轮只做“最小基线”

当前基线的设计原则是：

- 优先兼容当前 logistics 已稳定运行的结构；
- 不要求立刻把所有接口重构成一种完全统一的形态；
- 先定义“平台最小共同结构”，再逐步推动各域对齐。

### 2. 本轮明确不做

- 不大规模重构 `aggregate / detail / compare / nl2query` 代码
- 不强制把所有接口一次性改成同一 payload 结构
- 不直接开始第二业务域接入
- 不直接进入 RAG / 工具层 / Agent 实现

### 3. 当前基线的判断原则

如果某个结构：

- 当前前后端已经真实消费；
- 对查询结果展示、历史回放、后续多域接入都有价值；

则应优先纳入平台基线。

---

## 三、平台统一响应结构最小基线

### 1. 外层响应基线

当前平台建议统一保留外层响应包装：

```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "trace_id": "..."
}
```

最小字段定义：

| 字段 | 是否必需 | 含义 |
| --- | --- | --- |
| `code` | 是 | 平台级外层响应码，HTTP 成功时通常为 0 |
| `message` | 是 | 平台级外层说明 |
| `data` | 是 | 真实业务数据主体 |
| `trace_id` | 建议必需 | 用于日志追踪、历史回放、问题排查 |

### 2. 查询类接口的最小数据轮廓

当前不建议强制所有查询接口立刻长成同一 payload。  
建议采用“**统一最小字段 + 允许两种数据轮廓共存**”的方式过渡。

#### 轮廓 A：自然语言查询轮廓

适用接口：

- `POST /api/v1/logistics/nl2query/parse-and-query`

最小基线：

```json
{
  "question": "...",
  "parsed": {},
  "query_result": {},
  "response_meta": {}
}
```

#### 轮廓 B：直接查询轮廓

适用接口：

- `aggregate`
- `detail`
- `compare`

当前最小基线不强制它们立刻再包一层 `query_result`，但要求：

- `data` 主体本身必须具备统一的查询结果共享字段；
- 这样前端和历史回放才能按一致语义消费。

### 3. 查询结果共享字段最小基线

无论是在：

- `data.query_result`
- 还是直接 `data`

只要它表示一次查询结果，就建议至少具备以下共享字段：

| 字段 | 是否必需 | 说明 |
| --- | --- | --- |
| `query_type` | 是 | `aggregate / detail / compare` |
| `execution_mode` | 是 | `database / fallback / error_fallback` 等 |
| `metric_type` | 条件必需 | 统计类与对比类查询需要 |
| `source_scope` | 条件必需 | `hist / sys / all` |
| `filters` | 建议必需 | 用于历史回放、联调与上下文展示 |
| `status` | 是 | 平台统一状态结构 |
| `result_explanation` | 是 | 平台统一结果解释结构 |
| `no_result_analysis` | 空结果时必需 | 平台统一空结果分析结构 |
| `compatibility_notice` | 可选 | 兼容说明或降级提示 |
| `response_meta` | 建议保留 | 便于前端与历史详情统一消费 |

### 4. 按查询模式保留的模式专属字段

#### aggregate 最小专属字段

- `summary`
- `items`

#### detail 最小专属字段

- `items`
- `total`
- `page`
- `page_size`

#### compare 最小专属字段

- `left_label`
- `right_label`
- `left_value`
- `right_value`
- `diff_value`
- `diff_rate`
- `items`（如有分组对比结果）

### 5. 当前推荐结论

平台最小基线不是“立刻统一成一个绝对同形的 JSON”，而是：

> 先统一“共享字段语义”，再视时机统一“外形”。

这更符合当前仓库状态，也不会对现有联调链路造成无必要冲击。

---

## 四、状态码与解释结构最小基线

### 1. 状态结构最小基线

当前建议平台统一状态结构至少包含：

```json
{
  "code": "OK",
  "message": "查询执行成功。",
  "success": true,
  "severity": "info",
  "execution_mode": "database"
}
```

最小字段定义：

| 字段 | 是否必需 | 含义 |
| --- | --- | --- |
| `code` | 是 | 稳定状态码 |
| `message` | 是 | 可直接给前端展示的说明 |
| `success` | 是 | 当前请求是否算成功完成 |
| `severity` | 是 | `info / warning / error` |
| `execution_mode` | 建议必需 | 当前执行路径说明 |

### 2. 当前建议纳入平台基线的状态码

基于当前 logistics 已落地的状态码，建议平台最小基线先包含：

- `OK`
- `OK_WITH_ADJUSTMENTS`
- `EMPTY_RESULT`
- `DETAIL_NOT_FOUND`
- `INVALID_QUERY_PARAM`
- `SQL_TEMPLATE_NOT_ALLOWED`
- `FALLBACK_MODE`
- `EXECUTION_ERROR`
- `UNSUPPORTED_DOMAIN_EXECUTION`

### 3. 结果解释结构最小基线

当前建议平台统一结果解释结构至少包含：

```json
{
  "summary": "...",
  "highlights": [],
  "notes": [],
  "result_count": 0,
  "query_type": "aggregate",
  "metric_type": "shipment_watt",
  "source_scope": "hist",
  "execution_mode": "database"
}
```

最小字段定义：

| 字段 | 是否必需 | 含义 |
| --- | --- | --- |
| `summary` | 是 | 结果摘要 |
| `highlights` | 建议必需 | 关键亮点 |
| `notes` | 建议必需 | 联调与解释补充 |
| `result_count` | 是 | 统一结果数 |
| `query_type` | 建议必需 | 查询模式 |
| `metric_type` | 条件必需 | 统计 / 对比类查询用 |
| `source_scope` | 条件必需 | 数据来源范围 |
| `execution_mode` | 建议必需 | 执行路径 |

### 4. 空结果分析结构最小基线

当前建议平台统一空结果分析结构至少包含：

```json
{
  "question": "...",
  "possible_reasons": [],
  "suggestions": [],
  "execution_mode": "database",
  "is_empty_result": true
}
```

最小字段定义：

| 字段 | 是否必需 | 含义 |
| --- | --- | --- |
| `question` | 建议必需 | 原始问题或可读查询标题 |
| `possible_reasons` | 是 | 可能原因列表 |
| `suggestions` | 是 | 建议操作列表 |
| `execution_mode` | 建议必需 | 执行路径 |
| `is_empty_result` | 是 | 明确这是空结果分析而非一般提示 |

### 5. 当前结论

平台层最先需要统一的，不是文案，而是：

- 状态结构字段
- 解释结构字段
- 空结果分析结构字段

只要字段语义稳定，后续各域再根据业务调整文案成本会小很多。

---

## 五、查询历史 / 回放 / 审计字段最小基线

### 1. 查询历史列表最小基线

查询历史列表建议至少保留：

| 字段 | 是否必需 | 说明 |
| --- | --- | --- |
| `id` | 是 | 历史记录主键 |
| `trace_id` | 建议必需 | 与应用日志关联 |
| `query_type` | 是 | 查询类型 |
| `question` | 是 | 历史问题或可读标题 |
| `execution_mode` | 建议必需 | 执行模式 |
| `metric_type` | 条件必需 | 统计类问题需要 |
| `result_count` | 是 | 统一结果数 |
| `status_code` | 是 | 平台统一状态码 |
| `status_message` | 建议必需 | 状态说明 |
| `template_hit` | 建议必需 | 是否命中模板 |
| `template_id` | 可选 | 命中模板标识 |
| `created_at` | 是 | 时间戳 |

### 2. 查询历史详情最小基线

查询历史详情建议至少保留：

- 列表全部字段
- `parsed`
- `query_result`
- `response_meta`
- `execution_binding`
- `execution_summary`
- `request_payload_json`

说明：

1. `query_result` 是历史快照，不等同于实时再次执行结果；
2. `response_meta` 与 `query_result` 都应作为历史详情的一级可见对象；
3. 历史详情必须能支撑“问题回放”和“联调排查”。

### 3. 执行绑定最小基线

`execution_binding` 建议至少保留：

- `execution_mode`
- `sql_template`
- `sql_whitelist`
- `sql_preview`

说明：

- 它更偏“执行前绑定信息”
- 主要用于解释“本次为什么这样执行”

### 4. 执行摘要最小基线

`execution_summary` 建议至少保留：

- `result_count`
- `execution_mode`
- `route`
- `sql_whitelist_allowed`

说明：

- 它更偏“执行后的摘要结果”
- 主要用于历史列表、快速问题判断和轻量回放

### 5. 执行审计最小基线

`execution_audit` 或等价结构，建议至少保留：

- `trace_id`
- `question`
- `selected_domain`
- `mode`
- `metric_type`
- `source_scope`
- `template_id`
- `sql_template_id`
- `validation_ok`
- `validation_issues`
- `sql_whitelist_allowed`
- `sql_whitelist_reason`
- `execution_mode`
- `result_count`
- `is_empty_result`

### 6. 当前建议

历史 / 回放 / 审计基线的关键不是“存更多字段”，而是：

- 保留能重现问题的最小结构；
- 区分“执行前绑定信息”和“执行后摘要信息”；
- 保留 `trace_id` 贯穿前端、后端和日志。

---

## 六、域注册最小字段定义

### 1. 设计目标

域注册信息的作用，不是替代模板，而是回答：

- 这个域是否可用；
- 走什么路由关键词；
- 模板目录在哪里；
- 支持哪些查询模式；
- 当前是否已经具备真实执行能力。

### 2. 建议的域注册最小字段

| 字段 | 是否必需 | 含义 |
| --- | --- | --- |
| `domain_code` | 是 | 域唯一编码，如 `logistics` |
| `domain_name` | 是 | 域中文名 |
| `enabled` | 是 | 是否启用 |
| `execution_ready` | 是 | 是否已具备真实执行能力 |
| `router_keywords_path` | 建议必需 | 域关键词配置路径 |
| `template_catalog_path` | 建议必需 | 模板目录路径 |
| `supported_modes` | 是 | 支持的查询模式，如 `aggregate/detail/compare` |
| `default_metric_type` | 可选 | 该域默认指标 |
| `history_enabled` | 建议必需 | 是否接入查询历史/回放 |
| `fallback_enabled` | 建议必需 | 是否显式启用该域 fallback，默认应为 `false` |
| `fallback_history_enabled` | 可选 | fallback 结果是否允许进入历史/回放，默认应为 `false` |
| `fallback_notes` | 可选 | fallback 数据来源、语义可信范围和展示边界说明 |
| `owner` | 可选 | 域负责人或资料归口人 |
| `notes` | 可选 | 重要边界说明 |

### 3. 当前域注册示例

以 logistics 为例，建议的注册信息应至少能表达：

- `domain_code = logistics`
- `enabled = true`
- `execution_ready = true`
- `supported_modes = [aggregate, detail, compare, nl_query]`
- `history_enabled = true`
- `fallback_enabled = true`
- `fallback_history_enabled = true` 或按当前历史策略明确声明
- `fallback_notes = 当前仅 logistics 域拥有显式声明的兼容 fallback`
- `notes = 当前平台样板域`

以计划 BOM 为例，在尚未真正接入前，建议表达为：

- `domain_code = plan_bom`
- `enabled = true`
- `execution_ready = false`
- `supported_modes = [aggregate]` 或待定
- `history_enabled = false` 或待定
- `fallback_enabled = false`
- `fallback_history_enabled = false`
- `fallback_notes = 默认不继承 logistics fallback，未声明前不可启用`
- `notes = 当前仅模板/路由预留，待数据与规则就绪后接入`

### 4. 当前结论

域注册最小字段定义的价值在于：

- 避免“目录存在 = 域已可执行”的误判；
- 给第二业务域接入前的 Go/No-Go 判断提供明确依据。

---

## 七、第二业务域接入最小清单草案

### 1. 业务输入清单

第二业务域开工前，至少需要准备：

- 域范围说明
- 业务规则说明
- 指标口径说明
- 维度口径说明
- 典型问题集

### 2. 数据输入清单

至少需要准备：

- 数据源说明
- 表结构 / 字段字典
- 核心样例数据
- 时间范围说明
- 是否存在历史 / 正式系统双源问题

### 3. 平台接入清单

至少需要准备：

- 域注册信息
- 域关键词配置
- 模板目录
- 最小模板集
- 最小查询模式说明

### 4. 契约接入清单

至少需要确认：

- 该域是否遵守平台外层响应包装
- 查询结果是否具备共享字段
- 状态结构是否遵守最小基线
- 解释结构是否遵守最小基线
- 历史 / 回放 / 审计是否接入
- 是否显式声明 `fallback_enabled`
- 若启用 fallback，是否已声明数据来源、语义可信范围、状态展示方式、是否进入历史回放

### 5. 验收清单

至少需要具备：

- 10～20 条真实问题集
- 正常场景、空结果场景、明细或等价场景
- 历史回放是否可用
- 至少一轮联调回归记录

### 6. 当前推荐结论

若第二业务域按计划 BOM 启动，那么在真正写代码前，至少要先把：

1. 规则口径
2. 字段字典
3. 最小问题集
4. 域注册信息

这 4 项准备齐，否则不建议进入真实接入开发。

如果该域未来还计划启用 fallback，则还必须额外补齐：

5. fallback 数据源说明
6. fallback 语义可信范围
7. fallback 状态展示方式
8. fallback 是否进入历史回放

在这 4 项未声明前，第二业务域默认按“不继承 fallback”处理。

---

## 八、本轮结论

### 1. 当前最小契约基线的核心结论

当前平台最适合采用的方案不是“立刻全量重构”，而是：

- 统一外层响应包装
- 统一查询结果共享字段
- 统一状态结构与解释结构
- 统一历史 / 回放 / 审计最小字段
- 统一域注册最小字段

### 2. 子里程碑 1.2 的输出结论

本轮输出可以作为下一步 1.3 的输入：

- 已经明确哪些字段应提升为平台最小契约
- 已经明确第二业务域接入至少要满足什么最小条件
- 已经明确不应该在当前阶段做全量重构

### 3. 当前仍未解决的问题

- compare / detail 是否也要在后续继续向统一共享字段靠拢，尚未在本轮展开
- 域注册信息是否要落成代码配置，当前未决定
- 第二业务域真实输入资料是否已经到位，当前未确认

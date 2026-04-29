# P0 子里程碑 A：共享字段与最小快照基线

## 一、文件用途

本文件用于确认平台主线 `P0` 子里程碑 A 的最小边界，回答以下问题：

1. 哪些字段必须提升为平台共享字段。
2. `direct query` 与 `NL_QUERY` 当前各自长什么样，后续应该如何对齐共享字段。
3. 查询历史列表 / 详情 / 回放最小需要保留哪些快照字段。
4. 后续哪些日志写入点需要补齐。
5. 这些基线对前端和历史详情页会产生什么影响。

本文件只做基线确认和后续改动清单，不直接修改主链路实现。

---

## 二、当前结论总览

### 1. 当前最小平台共享字段

当前建议提升为“平台共享字段”的最小集合如下：

| 字段名 | 必须级别 | 用途 | 当前状态 |
| --- | --- | --- | --- |
| `status` | P0 必须 | 统一状态码、文案、成功态、严重级别、执行模式 | `NL_QUERY` 已有，`aggregate` 已有，`detail/compare` 直连不足 |
| `result_explanation` | P0 必须 | 结果解释、结果数量、摘要展示 | `NL_QUERY` 已有，`aggregate` 已有，`detail/compare` 直连不足 |
| `no_result_analysis` | P0 必须 | 空结果分析、建议动作 | `NL_QUERY` 已有，`aggregate` 已有，`detail/compare` 直连不足 |
| `response_meta` | P0 必须 | 顶层或结果级元信息、模式、指标、来源、结果数 | `NL_QUERY` 已有，`aggregate` 已有，`detail/compare` 直连不足 |
| `execution_mode` | P0 必须 | 区分 `database / fallback` 等执行路径 | 各链路基本已有，但挂载位置不完全一致 |
| `query_type` | P0 必须 | 区分 `aggregate / detail / compare` | 各链路已有 |
| `metric_type` | P0 必须 | 指标口径 | 各链路已有，但历史日志提取依赖位置不完全一致 |
| `source_scope` | P0 必须 | 历史 / 系统 / 混合来源语义 | 各链路已有 |
| `filters` | P0 必须 | 回放、解释和定位问题的最小筛选上下文 | 各链路已有，但快照保真度不一致 |
| `trace_id` | P0 必须 | 前后端联调、历史回放、日志追踪 | 日志与响应链路已有 |

### 2. 当前不建议提升为平台共享字段

以下字段当前应保留为 `NL_QUERY` 轮廓特有字段，而不是要求所有直连查询都强行具备：

| 字段名 | 当前判断 | 原因 |
| --- | --- | --- |
| `question` | `NL_QUERY` 特有 | 直连查询未必有自然语言原问题 |
| `parsed` | `NL_QUERY` 特有 | 直连查询没有完整解析流程，不应伪造复杂解析结果 |
| `execution_audit` | `NL_QUERY` 特有 | 当前审计结构依赖 `NL_QUERY` 解析与绑定过程 |
| `business_no_probe` | `NL_QUERY` 特有 | 主要服务于明细空结果增强分析 |

### 3. 当前推荐对齐原则

当前不建议先追求“所有接口长得一模一样”，而是先统一：

1. **共享字段语义一致**
2. **历史列表 / 详情 / 回放能稳定提取**
3. **前端能优先吃后端原生共享字段**

后续若确有必要，再讨论外层返回结构是否进一步统一。

---

## 三、direct query 与 NL_QUERY 的轮廓对照表

### 1. 当前 `NL_QUERY` 轮廓

当前 `NL_QUERY` 的主轮廓可以概括为：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "question": "...",
    "parsed": {...},
    "query_result": {
      "query_type": "...",
      "execution_mode": "...",
      "status": {...},
      "result_explanation": {...},
      "no_result_analysis": {...},
      "response_meta": {...},
      "...": "域内原生结果字段"
    },
    "response_meta": {...}
  },
  "trace_id": "..."
}
```

特点：

1. 结果展示主要落在 `data.query_result`。
2. 同时保留顶层 `data.response_meta`，供前端快速消费。
3. `parsed / execution_audit / execution_binding` 等高保真信息主要来自 `NL_QUERY`。

### 2. 当前 `direct aggregate` 轮廓

当前 `aggregate` 直连查询已经补了最小共享字段：

```json
{
  "query_type": "aggregate",
  "execution_mode": "...",
  "metric_type": "...",
  "source_scope": "...",
  "filters": {...},
  "summary": {...},
  "items": [...],
  "status": {...},
  "result_explanation": {...},
  "no_result_analysis": {...},
  "response_meta": {...}
}
```

特点：

1. 没有 `question / parsed`。
2. 共享字段已经可以直接被前端消费。
3. 当前是最接近平台共享字段基线的 `direct query`。

### 3. 当前 `direct detail` 轮廓

当前 `detail` 直连查询仍偏域内原生返回，主要形态是：

```json
{
  "query_type": "detail",
  "execution_mode": "...",
  "metric_type": "...",
  "source_scope": "...",
  "filters": {...},
  "total": 0,
  "page": 1,
  "page_size": 20,
  "items": [...]
}
```

当前缺口：

1. 缺少稳定的 `status`
2. 缺少稳定的 `result_explanation`
3. 缺少稳定的 `no_result_analysis`
4. 缺少稳定的 `response_meta`

### 4. 当前 `direct compare` 轮廓

当前 `compare` 直连查询仍偏域内原生返回，主要形态是：

```json
{
  "query_type": "compare",
  "execution_mode": "...",
  "source_scope": "...",
  "compare_dim": "...",
  "filters": {...},
  "left_value": ...,
  "right_value": ...,
  "diff_value": ...,
  "diff_rate": ...,
  "items": [...]
}
```

当前缺口：

1. 缺少稳定的 `status`
2. 缺少稳定的 `result_explanation`
3. 缺少稳定的 `no_result_analysis`
4. 缺少稳定的 `response_meta`
5. `total-mode` 的日志 `result_count` 仍可能不可信

### 5. 当前推荐的对齐方式

推荐把平台基线定义成：

1. `NL_QUERY` 继续保留 `question / parsed / query_result / response_meta` 外轮廓
2. `direct query` 保持当前“结果体直返”的风格，不强行包一层 `query_result`
3. 但要求 `direct query` 的结果体必须至少具备本文件第二章定义的共享字段

这样做的好处是：

1. 不需要大面积改现有前后端接口外形
2. 可以先让共享字段语义稳定
3. 可以降低第二业务域接入时的理解成本

---

## 四、历史列表 / 详情 / 回放最小快照基线

### 1. 历史列表最小基线

历史列表至少应稳定提供以下字段：

| 字段名 | 用途 | 当前判断 |
| --- | --- | --- |
| `id` | 详情查询主键 | 必须 |
| `trace_id` | 日志串联 | 必须 |
| `query_type` | 类型展示与回放路由 | 必须 |
| `question` | 人可读标题 | 必须 |
| `execution_mode` | 数据库 / fallback 标识 | 必须 |
| `route_type` | 辅助排查当前走的链路 | 建议保留 |
| `metric_type` | 指标展示与回放 | 必须 |
| `result_count` | 列表快速判断结果规模 | 必须 |
| `status_code` | 前端状态标签 | 必须 |
| `status_message` | 前端状态说明 | 必须 |
| `template_hit` | 模板命中展示 | 必须 |
| `template_id` | 模板定位 | 建议保留 |
| `created_at` | 时间排序与筛选 | 必须 |

### 2. 历史详情最小基线

历史详情至少应在列表基线之上，再提供以下字段：

| 字段名 | 用途 | 当前判断 |
| --- | --- | --- |
| `parsed` | 查看问题解析与模板命中 | `NL_QUERY` 强依赖，直连可为空 |
| `execution_binding` | 查看执行绑定与路由 | 建议保留 |
| `execution_summary` | 查看执行摘要 | 建议保留 |
| `response_meta` | 前端摘要和状态恢复 | 必须 |
| `query_result` | 历史快照主体 | 必须 |
| `request_payload_json` | 排查原始请求 | 必须 |

### 3. 回放最小基线

回放并不要求“一比一重建当时整个现场”，但至少应满足：

1. 能知道这是哪类查询：`query_type`
2. 能知道展示给用户的标题：`question`
3. 能知道最关键的输入：`filters` 或等价请求参数
4. 能知道当时的执行路径：`execution_mode`
5. 能知道当时的状态：`status / response_meta`
6. 能看到最小结果快照：`query_result`

### 4. 当前快照基线判断

当前仓库里：

1. `NL_QUERY_PLAN` 已经具备较高保真快照，基本满足详情与回放要求。
2. `direct query` 日志仍偏轻量，详情页很多信息依赖 `query_log_service` 做兼容补造。
3. 因此后续 `P0` 收口重点不是继续增强 `NL_QUERY_PLAN`，而是补齐 `direct query` 的最小快照基线。

---

## 五、需要补齐的日志写入点清单

### 1. 已相对完善的写入点

| 写入点 | 当前状态 | 说明 |
| --- | --- | --- |
| `query_plan_store.save_plan` | 已相对完善 | 当前 `NL_QUERY_PLAN` 已会落 `parsed / execution_binding / execution_summary / response_meta / query_result` 快照 |

### 2. 后续需要补齐的写入点

| 写入点 | 当前问题 | 后续需要补什么 |
| --- | --- | --- |
| `LogisticsQueryService.aggregate -> _safe_write_log` | 当前只写轻量 payload，未形成统一最小快照约束 | 明确 aggregate 直连日志的最小快照基线 |
| `LogisticsQueryService.detail -> _safe_write_log` | 当前日志可回放信息不足，详情依赖兼容补造 | 后续补齐 `status / response_meta / query_result` 最小快照 |
| `LogisticsQueryService.compare -> _safe_write_log` | 当前除快照不足外，`total-mode` 的 `result_count` 还存在可信度问题 | 后续同时修复日志可信度与最小快照 |

### 3. 当前不建议新增的写入点

当前不建议为了平台化，单独再造一套新的日志表或新的审计 service。  
优先策略应是：

1. 沿用现有 `sys_query_log`
2. 沿用现有 `_safe_write_log`
3. 沿用现有 `query_plan_store`
4. 在既有写入点上补齐最小共享字段和最小快照

---

## 六、对前端和历史详情的影响说明

### 1. 对结果页前端的影响

当前前端结果展示已经优先消费后端原生共享字段。  
因此后续若 `detail / compare` 也补齐共享字段，前端收益是：

1. 结果卡片可进一步减少兼容分支
2. 条件查询、自然语言查询、历史详情的展示逻辑会更一致
3. 第二业务域接入时，前端更容易直接复用现有结果展示组件

### 2. 对查询历史页的影响

当前历史详情对 `direct query` 的很多字段仍需做兼容补造。  
后续若补齐最小快照基线，收益是：

1. 列表状态、结果数和执行模式的可信度会更高
2. 详情页不必过度依赖“从轻量 payload 反推上下文”
3. 重新查询、历史回放和多域复用会更稳定

### 3. 对平台化抽象的影响

当前最关键的不是把所有接口改成一样，而是先让：

1. 前端知道哪些字段可被稳定依赖
2. 历史详情知道哪些字段一定会有
3. 第二业务域知道接入后最低要产出哪些共享字段

这一步做完后，后续子里程碑 B、C 才有明确落点。

---

## 七、本子里程碑验收标准

本子里程碑 A 视为完成，至少应满足：

1. 平台共享字段最小集合已经确认
2. `direct query` 与 `NL_QUERY` 的轮廓差异已经说清楚
3. 历史列表 / 详情 / 回放最小快照基线已经确认
4. 后续需要补齐的日志写入点已经列清楚
5. 前端与历史详情的影响已经明确

---

## 八、风险点

1. 如果后续把“统一共享字段”做成“强行统一全部外层结构”，容易扩大改动范围。
2. 如果不先补最小快照基线，历史详情仍会长期依赖兼容补造，影响第二业务域复用。
3. 如果把 `parsed / execution_audit` 这类 `NL_QUERY` 特有字段也强行纳入平台共享字段，会抬高直连查询接入成本。

---

## 九、本子里程碑明确不做

1. 不直接修改大段主链路实现
2. 不进入 `compare` 修复实现
3. 不进入 `fallback` 边界实现
4. 不进入第二业务域接入开发


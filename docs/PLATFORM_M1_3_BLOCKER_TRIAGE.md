# PLATFORM_M1_3_BLOCKER_TRIAGE.md

## 一、文档用途

本文件用于沉淀【里程碑 1 / 子里程碑 1.3：物流域剩余平台阻塞问题清单】的阶段性结论。

本轮只做：

1. compare 平台化阻塞问题分级
2. fallback 平台化阻塞问题分级
3. 跨接口契约不一致对第二业务域的阻塞判断
4. 查询历史 / 回放 / 审计结构中仍会影响多域复用的阻塞判断
5. 输出“必须先修 / 可以后置”边界说明

本轮不做：

- 不直接修这些问题
- 不大规模后端重构
- 不进入第二业务域代码开发
- 不做 RAG / 工具层 / Agent 实现

---

## 二、分级规则

### 1. 分级定义

为避免把所有问题都堆成“待优化”，本轮统一按下面分级：

- `P0 阻塞`
  - 不处理就会直接影响平台主线下一步推进
  - 或会导致第二业务域接入时平台共性承诺失真

- `P1 高优先`
  - 不一定阻塞当前文档设计，但会明显增加第二业务域接入成本
  - 建议在进入第二业务域代码开发前收口

- `P2 可后置`
  - 当前不会阻断平台主线下一步
  - 但会影响体验、解释完整度或后续治理质量

### 2. 判断原则

本轮判断的重点不是“有没有问题”，而是：

- 它会不会阻塞第二业务域接入；
- 它会不会破坏平台最小契约；
- 它会不会让查询历史 / 回放 / 审计失去平台复用价值。

---

## 三、compare 平台化阻塞问题分级

### 1. compare 直连接口尚未补齐平台共享字段

当前现象：

- `NL_QUERY` 路径下，compare 结果会被补齐：
  - `status`
  - `result_explanation`
  - `no_result_analysis`
  - `response_meta`
- 但 `POST /logistics/query-service/compare` 直连路径当前仍只返回 compare 结果主体，没有像 aggregate 一样补齐平台共享字段。

影响：

- 如果后续第二业务域要复用“直接查询接口 + 共用前端结果卡片”的模式，compare 会再次出现一条独立兼容分支；
- 平台层难以宣称“direct query 都遵守同一共享结果字段”。

分级：

- `P1 高优先`

判断：

- 对当前 logistics 自然语言主链路不是阻塞；
- 但对“第二业务域是否能直接复用 direct query + 历史回放模型”是高优先阻塞。

### 2. compare 总量模式的数据库日志结果数仍可能误记为 0

当前现象：

- 数据库模式下的 `compare()` 写日志时，当前仍用 `len(result.get("items", []))` 记 `result_count`；
- 但总量 compare 场景下，合法返回可能是：
  - `left_value`
  - `right_value`
  - `diff_value`
  - `items = []`

这会让日志把“有结果的总量对比”误记成 0 条。

影响：

- 查询历史列表中的 `result_count` 不可信；
- 历史详情补造 `query_result` 时会继续放大误差；
- 平台若把“历史回放 / 查询审计”作为共性能力，会被 compare 总量模式破坏。

分级：

- `P0 阻塞`

判断：

- 这是平台共性层的问题，不只是 compare 展示问题；
- 在第二业务域接入前，至少要把“平台日志里的结果数量”纠正到可信。

### 3. compare 解释结构在总量模式下仍偏弱

当前现象：

- compare 结果解释器当前主要根据 `items` 生成 highlights；
- 对总量 compare 虽然能给出 summary，但 highlights 不够强。

影响：

- 更多影响解释完整度和演示体验；
- 不直接破坏平台契约。

分级：

- `P2 可后置`

判断：

- 可在平台主线后续专项中继续增强；
- 当前不阻塞第二业务域最小接入。

### 4. compare 平台化结论

必须优先关注的是两件事：

1. compare 直连接口是否要纳入平台共享字段基线；
2. compare 总量模式的日志 `result_count` 误记问题。

其中第二条属于必须先修；第一条属于进入第二业务域 direct compare 前建议先修。

---

## 四、fallback 平台化阻塞问题分级

### 1. fallback 当前仍是 logistics 域专属兜底，不适合作为平台默认能力

当前现象：

- fallback 直接依赖：
  - `InMemoryLogisticsQueryRepository`
  - `CoreQueryService`
  - `CompareService`
- fallback 的过滤、分组和明细映射规则也都深度绑定 logistics 数据形态。

影响：

- 这意味着 fallback 目前只能被视为 logistics 域本地兼容能力；
- 不能把“当前已有 fallback”误判成“平台已经具备通用兜底机制”。

分级：

- `P0 阻塞`

判断：

- 不要求现在就把 fallback 抽成平台能力；
- 但在第二业务域启动前，必须先明确：
  - fallback **不是**平台默认继承能力；
  - 第二业务域默认不应无条件继承 logistics fallback。

### 2. fallback 的过滤语义明显弱化，不能承诺平台级可信结果

当前现象：

- `_resolve_filters()` 当前会把大量过滤条件折叠为：
  - `keyword`
  - `source_type`
  - `transport_mode`
- 许多条件只能通过 `compatibility_notice` 提示人工关注。

影响：

- fallback 查询结果无法承诺与数据库模式同等语义精度；
- 如果平台后续对外承诺“统一查询能力”，fallback 会成为语义漂移来源。

分级：

- `P1 高优先`

判断：

- 这不是必须立刻修代码的问题；
- 但必须在平台规范里明确 fallback 的边界，否则第二业务域容易复制这个问题。

### 3. fallback compare_dim 支持能力有限

当前现象：

- fallback compare 只支持映射表中有限的 `compare_dim`；
- 不支持时直接返回 400。

影响：

- 说明 fallback 不适合被当作通用 compare 能力；
- 但当前不会直接阻塞平台基线设计。

分级：

- `P2 可后置`

### 4. fallback 平台化结论

当前最关键的不是“把 fallback 做强”，而是先把边界说清楚：

- fallback 当前属于 logistics 域特有兼容能力；
- 它不是平台级默认能力；
- 第二业务域接入时，默认应按“无 fallback 继承”来设计。

---

## 五、跨接口契约不一致的阻塞判断

### 1. `NL_QUERY` 与 direct query 仍不是同一层级的共享契约

当前现象：

- `NL_QUERY` 返回：
  - `question`
  - `parsed`
  - `query_result`
  - `response_meta`
- `aggregate` 直连已补齐最小共享字段；
- `detail / compare` 直连当前还没有完整补齐共享字段。

影响：

- 平台层虽然已有“共享字段基线”思路，但当前还不是所有 direct query 都真正对齐；
- 第二业务域如果要复用 direct query，会面临“不同模式不同契约”的问题。

分级：

- `P0 阻塞`

判断：

- 这不要求立刻做大规模重构；
- 但在第二业务域真正编码前，必须先明确：
  - 第二业务域到底复用哪一种轮廓；
  - `detail / compare` 是否至少要补最小共享字段。

### 2. 平台外层响应已统一，但内部数据主体仍存在多形态

当前现象：

- 外层 `ApiResponse / ResponseEnvelope` 已存在；
- 但内部 `data` 的形态仍依赖接口类型和历史阶段演进。

影响：

- 前端和历史回放层仍需知道“这个接口是哪种轮廓”；
- 若不在平台规范里提前说清楚，会导致第二业务域重复造兼容层。

分级：

- `P1 高优先`

判断：

- 可不在当前阶段统一成一个外形；
- 但必须在平台规范中明确“允许哪些轮廓并存、共享字段是什么”。

### 3. chat/logistics 接口不属于当前平台主线统一对象

当前现象：

- chat 入口仍走老的聊天式聚合/明细/对比服务模型；
- 与当前 logistics 域主查询主线不是同一套契约。

影响：

- 如果把它也纳入当前平台主线，会显著扩大范围。

分级：

- `P2 可后置`

判断：

- 当前可以明确将其排除在平台基线统一之外；
- 后续若要把 chat 做成平台统一入口，再单开专项。

---

## 六、查询历史 / 回放 / 审计结构阻塞判断

### 1. 只有 `NL_QUERY_PLAN` 日志具备高保真快照

当前现象：

- `NL_QUERY_PLAN` 会落：
  - `parsed`
  - `execution_binding`
  - `execution_summary`
  - `response_meta`
  - `query_result`
- direct `AGGREGATE / DETAIL / COMPARE` 日志当前只落：
  - 原始 payload
  - result_count
  - route_type
  - metric_type

详情接口会对这些直连日志做“最小补造”，但不是高保真快照。

影响：

- 历史回放的精度在不同接口之间不一致；
- 平台若承诺“查询历史与回放是共性能力”，当前只在 `NL_QUERY` 路径上算真正完整。

分级：

- `P0 阻塞`

判断：

- 第二业务域若也希望复用历史详情与回放，不应建立在“只有 NL_QUERY 才有完整快照”的前提上；
- 至少要先明确平台最小日志快照基线，再决定 direct query 是否同步补齐。

### 2. direct query 日志的 `question_text` 为空，影响历史检索与回放可读性

当前现象：

- `_safe_write_log()` 写 direct query 日志时，`question_text` 当前固定为 `None`；
- 历史列表的标题只能靠后续 fallback 构造。

影响：

- 关键词检索质量下降；
- 查询历史页对 direct query 的可读性和可检索性变差；
- 第二业务域接入后，这个问题会被放大，而不是消失。

分级：

- `P1 高优先`

判断：

- 这是进入第二业务域代码开发前建议先修的问题；
- 否则历史页会继续只对 NL_QUERY 友好，对 direct query 不友好。

### 3. execution_audit 当前只在 NL_QUERY 路径上完整生成

当前现象：

- `execution_audit` 当前主要在 `LogisticsNL2QueryService` 中生成；
- direct `aggregate / detail / compare` 并没有对齐同样深度的审计结构。

影响：

- 平台层的“审计结构”目前只在自然语言主链路完整；
- 第二业务域若先走 direct query，审计层会出现不一致。

分级：

- `P1 高优先`

判断：

- 当前不是必须立刻补代码；
- 但必须在平台规范里先定：direct query 是否要求最低审计字段。

### 4. 查询历史 / 回放 / 审计结论

这一组里最关键的阻塞是：

1. 只有 `NL_QUERY_PLAN` 有高保真快照；
2. direct query 历史标题和结果快照深度都偏弱。

如果不先处理这个边界，第二业务域即便接上，也只能得到“半套历史回放能力”。

---

## 七、必须先修 / 可以后置 边界说明

### 1. 必须先修

以下问题建议在进入第二业务域真实编码前先收口：

1. `compare` 总量模式日志 `result_count` 误记问题  
   原因：它直接破坏平台历史与审计的可信度。

2. direct query 与 `NL_QUERY` 的共享字段边界  
   原因：不明确这一点，第二业务域会重复制造契约分叉。

3. 查询历史 / 回放的最小快照基线  
   原因：如果只有 `NL_QUERY` 有完整快照，平台无法宣称历史回放可复用。

4. fallback 的平台边界说明  
   原因：必须明确 fallback 不是平台默认能力，第二业务域不能自动继承。

### 2. 建议先修

以下问题建议在第二业务域编码前尽量处理，但不是绝对阻塞：

1. direct query 的 `question_text` 可读性与关键词检索问题
2. direct query 的最小审计字段一致性问题
3. compare 直连接口是否补齐共享字段问题

### 3. 可以后置

以下问题当前可以后置到平台主线后续专项：

1. compare 总量模式下的 highlights 丰富度
2. fallback compare_dim 的更广支持
3. chat/logistics 接口是否纳入平台统一契约
4. fallback 全量语义专项清理

---

## 八、非阻塞说明

### 1. 打包卫生问题

当前仍需注意重新打包时排除：

- `.env`
- `.env.local`
- `node_modules`
- `dist`
- `.git`
- `.idea`
- `.pytest_cache`
- `__pycache__`
- `__MACOSX`

说明：

- 这是工程交付卫生问题；
- 当前先不阻塞 1.3 阻塞分级结论；
- 但在下一次重新打包前必须处理。

---

## 九、本轮结论

### 1. 当前最核心的平台化阻塞

当前真正会阻塞平台主线下一步的，不是前端，也不是 RAG，而是：

1. compare 与 direct query 的共享契约尚未真正统一；
2. 查询历史 / 回放 / 审计在 `NL_QUERY` 与 direct query 之间深度不一致；
3. fallback 仍缺少明确的平台边界定义。

### 2. 子里程碑 1.3 的结论

本轮结论可以直接作为 1.4 的输入：

- 已经明确哪些问题必须在第二业务域前收口；
- 已经明确哪些问题可以后置，不必拖慢平台主线；
- 已经明确 fallback 不应被当成平台默认能力。

### 3. 当前仍未解决的问题

- 这些阻塞目前只完成了分级与边界划分，还没有进入修复阶段；
- 第二业务域真实输入条件是否到位，仍需在 1.4 单独做 Go/No-Go 判断。

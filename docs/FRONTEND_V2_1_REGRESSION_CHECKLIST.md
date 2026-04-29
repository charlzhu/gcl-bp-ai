# FRONTEND_V2_1_REGRESSION_CHECKLIST.md

## 一、文档用途

本文件用于沉淀《前端 V2 + V2.1 稳定性补强》阶段的标准联调回归清单。

适用对象：

- 前后端联调人员
- 验收人员
- 后续继续优化 V2.1 / V3 的开发者
- 新接手本项目的 Codex / 工程代理

使用原则：

- 本清单优先服务“每次改动后快速回归”
- 先跑核心链路，再跑跨页面链路
- 每次执行都应保留结果记录，不建议只口头确认

---

## 二、建议执行顺序

建议按下面顺序执行：

### 第 1 组：单页主链路

先验证查询主入口是否正常，避免后面跨页链路在“基础查询已经坏掉”的前提下继续浪费时间。

执行顺序建议：

1. E. 条件查询正常场景
2. F. 条件查询空结果场景
3. A. 自然语言正常查询
4. B. 自然语言空结果
5. C. 自然语言明细
6. D. compare 场景

### 第 2 组：跨页链路

在主链路确认后，再验证跨页跳转、历史回放和上下文保留。

执行顺序建议：

7. G. 查询历史与重新查询
8. H. 查询页 -> 明细页 -> 返回查询页

### 第 3 组：补充说明

- 若第 1 组已有阻塞失败，不建议继续跑第 2 组
- 若查询历史接口异常，应先记录并停止 G/H 的详细回归
- 若只是单条场景数据异常，应先区分“数据问题”和“契约/UI 问题”

---

## 三、标准回归清单

### A. 自然语言正常查询

- 场景编号：`A`
- 页面入口：`/nl-query`
- 后端接口：`POST /api/v1/logistics/nl2query/parse-and-query`
- 输入问题：`2025年3月运量是多少`

预期关键字段：

- `parsed.mode = aggregate`
- `query_result.query_type = aggregate`
- `query_result.status.code = OK`
- `response_meta.status.code = OK`
- `query_result.result_explanation.result_count > 0`
- `parsed.execution_audit.result_count > 0`

页面判断标准：

- 页面能展示解析结果卡片
- 页面能展示状态码、执行模式、模板命中
- 页面能展示结果摘要卡片与汇总指标
- 结果表格正常展示，且不以原始 JSON 为主

通过判定：

- 后端关键字段完整且互相一致
- 页面展示与字段语义一致

### B. 自然语言空结果

- 场景编号：`B`
- 页面入口：`/nl-query`
- 后端接口：`POST /api/v1/logistics/nl2query/parse-and-query`
- 输入问题：`合同编号ERR001的明细`

预期关键字段：

- `query_result.query_type = detail`
- `query_result.status.code = DETAIL_NOT_FOUND` 或与当前业务规则一致的空结果状态
- `response_meta.status.code` 与 `query_result.status.code` 一致
- `query_result.no_result_analysis` 非空
- `query_result.result_explanation.result_count = 0`

页面判断标准：

- 空结果提示块与正常结果视觉明显区分
- 能看到状态说明
- 能看到空结果分析与建议
- 页面没有被结果表格逻辑破坏

通过判定：

- 空结果状态码明确
- 空结果分析可读
- 页面无错误跳转和异常渲染

### C. 自然语言明细

- 场景编号：`C`
- 页面入口：`/nl-query`
- 后端接口：`POST /api/v1/logistics/nl2query/parse-and-query`
- 输入问题：`合同编号GCL5010ZJ202503015的明细`

预期关键字段：

- `query_result.query_type = detail`
- `query_result.status.code = OK`
- `query_result.total > 0`
- `query_result.items` 非空
- 明细记录中包含 `source_type`

页面判断标准：

- 页面能看到明细结果表格
- 行点击查看详情正常
- “查看”按钮正常
- 进入明细页后可看到结构化上下文

通过判定：

- 明细列表、明细页、返回链路都可用

### D. compare 场景

- 场景编号：`D`
- 页面入口：`/nl-query`
- 后端接口：`POST /api/v1/logistics/nl2query/parse-and-query`
- 输入问题：`2025年3月和2026年3月运量对比`

预期关键字段：

- `query_result.query_type = compare`
- `query_result.status.code = OK`
- `query_result.left_value` 存在
- `query_result.right_value` 存在
- `query_result.diff_value` 存在
- `query_result.diff_rate` 存在

页面判断标准：

- 能看到对比摘要
- 差值与差异率展示正常
- 状态码和解释不冲突

通过判定：

- compare 结果完整
- 页面可读性正常

### E. 条件查询正常场景

- 场景编号：`E`
- 页面入口：`/structured-query`
- 后端接口：`POST /api/v1/logistics/query-service/aggregate`
- 输入条件：
  - `year_month_list = ["2025-03"]`
  - `metric_type = shipment_watt`
  - `source_scope = hist`
  - `group_by = ["biz_month"]`

预期关键字段：

- `status.code = OK`
- `result_explanation` 非空
- `response_meta` 非空
- `response_meta.status.code = OK`
- `items` 非空

页面判断标准：

- 页面优先展示后端原生状态与解释
- 汇总指标卡片正常
- 结果表格正常
- 不出现“只能依赖前端兼容兜底”的表现

通过判定：

- 后端原生契约生效
- 页面展示与后端字段一致

### F. 条件查询空结果场景

- 场景编号：`F`
- 页面入口：`/structured-query`
- 后端接口：`POST /api/v1/logistics/query-service/aggregate`
- 输入条件：
  - `year_month_list = ["2099-01"]`
  - `metric_type = shipment_watt`
  - `source_scope = hist`
  - `group_by = ["biz_month"]`

预期关键字段：

- `status.code = EMPTY_RESULT`
- `result_explanation.result_count = 0`
- `no_result_analysis` 非空
- `response_meta.status.code = EMPTY_RESULT`
- `response_meta.result_count = 0`

页面判断标准：

- 条件查询页空结果提示块正常
- 空结果分析内容可读
- 页面无“OK 但 items 为空”的误导状态

通过判定：

- 后端空结果契约正确
- 页面空结果展示正确

### G. 查询历史与重新查询

- 场景编号：`G`
- 页面入口：`/history`
- 后端接口：
  - `GET /api/v1/sys/query/log`
  - `GET /api/v1/sys/query/log/{log_id}`

操作项：

- 输入关键词查询
- 翻页
- 修改每页条数
- 查看详情
- 重新查询

预期关键字段：

- 列表返回 `total / page / page_size / items`
- 列表项包含 `status_code / execution_mode / template_hit`
- 详情返回 `parsed / query_result / response_meta`

页面判断标准：

- 关键词过滤后列表正确变化
- 重置后列表恢复默认
- 分页与每页条数联动正常
- 详情抽屉正常
- 重新查询能跳到对应页面并回填问题/条件

通过判定：

- 历史页列表、详情、回放闭环可用

### H. 查询页 -> 明细页 -> 返回查询页

- 场景编号：`H`
- 页面入口：
  - `/nl-query`
  - `/detail-view`
- 依赖能力：
  - `sessionStorage` 查询上下文缓存

操作项：

- 从查询页进入明细页
- 再从明细页返回来源查询页

预期关键字段：

- 最近一次 `question / requestPayload / parsed / queryResult / selectedRow` 被保留

页面判断标准：

- 返回后查询条件不丢
- 返回后最近一次结果仍可见或可恢复
- 不出现回到空白页、丢条件、跳错页

通过判定：

- 查询上下文保留正常

---

## 四、通过 / 失败记录模板

建议每次执行回归时，都至少按下面模板记录一次。

### 1. 单条记录模板

```md
场景编号：
执行日期：
执行人：
页面入口：
后端接口：
输入条件 / 问题：

预期关键字段：
- 

实际关键字段：
- 

页面表现：
- 

判定：
- 通过 / 失败 / 阻塞

问题说明：
- 

证据：
- 截图：
- Trace ID：
- 接口响应摘要：
```

### 2. 汇总表模板

| 场景 | 页面 | 接口 | 判定 | 备注 |
| --- | --- | --- | --- | --- |
| A | `/nl-query` | `POST /api/v1/logistics/nl2query/parse-and-query` |  |  |
| B | `/nl-query` | `POST /api/v1/logistics/nl2query/parse-and-query` |  |  |
| C | `/nl-query` -> `/detail-view` | `POST /api/v1/logistics/nl2query/parse-and-query` |  |  |
| D | `/nl-query` | `POST /api/v1/logistics/nl2query/parse-and-query` |  |  |
| E | `/structured-query` | `POST /api/v1/logistics/query-service/aggregate` |  |  |
| F | `/structured-query` | `POST /api/v1/logistics/query-service/aggregate` |  |  |
| G | `/history` | `GET /api/v1/sys/query/log` |  |  |
| H | `/nl-query` / `/detail-view` | 页面上下文链路 |  |  |

---

## 五、建议的执行节奏

### 1. 日常小改动后

至少执行：

- A
- B
- E
- F
- G

适用场景：

- 前端展示调整
- 条件查询页调整
- 历史页调整
- 结果解释相关调整

### 2. 后端契约或查询逻辑改动后

建议执行全量：

- A
- B
- C
- D
- E
- F
- G
- H

适用场景：

- `nl2query`
- `aggregate`
- `detail`
- `compare`
- 状态标准化
- 查询历史契约调整

### 3. 演示 / 试运行前

建议执行：

- 全量清单
- 并为失败项单独留痕

---

## 六、当前未覆盖但需要关注的高风险场景

当前这份清单已经覆盖主链路，但仍有以下高风险场景暂未纳入本轮标准回归：

### 1. fallback 深水区场景

- fallback + 有结果
- fallback + 空结果
- fallback + 业务编号不存在

原因：

- 这类场景目前已做关键收口，但仍属于更偏后端稳定性专项的范围

### 2. compare 单边有结果场景

- 左侧有值、右侧为空
- 左右都为空但仍走 compare

原因：

- 当前 compare 主链路已可用，但更细的解释正确性仍建议单独做专项回归

### 3. 查询历史高级筛选

- 按状态组合筛选
- 按模板 ID 筛选
- 按时间范围筛选

原因：

- 当前里程碑只做到分页与关键词检索，没有扩展高级筛选

### 4. 多来源混合查询的细口径验证

- `source_scope = all`
- 历史 + 系统跨年混合

原因：

- 当前已有能力，但是否完全符合业务口径，仍建议在真实数据上单独复核

---

## 七、当前结论

当前《前端 V2 + V2.1》阶段，已经具备一套可重复执行的联调回归清单。

后续每次改动后，建议至少按本文件的执行顺序跑一轮回归，再决定是否放行。

# PLAN_BOM_COMPARE_TECH_DESIGN

> 历史基线说明：
> 本文保留 compare 技术设计形成时的原始设计口径。
> 当前仓库事实状态已经推进到：compare 里程碑 1 / 2 / 3 / 4 已完成，`BOM compare Go / No-Go 判断` 已执行，且 `compare.go` 已同步为 `true`。
> 当前状态请以 `docs/CURRENT_STATUS.md`、`docs/HANDOFF.md` 与 compare 运行态报告为准。

## 1. 设计目标

本文件用于定义 `计划 BOM` 一期中 `compare` 能力的正式技术设计基线。

当前前提（设计形成时）：
- BOM 一期 Excel 开发期链路已完成阶段性收口；
- `full_import_controlled.go = true`，仅表示受控全量导入抽验链路 Go；
- `compare.go = false`，当前仍未进入 compare 实现与运行态验证。

本设计目标是：
1. 明确 BOM compare 的业务范围与边界。
2. 定义 compare 的输入参数、候选处理规则和结果结构。
3. 明确 `00106` 与 `00120` 这两类特殊场景在 compare 中的处理方式。
4. 为后续 compare 代码实现、历史快照写入、前端展示和验收提供唯一事实源。

---

## 2. compare 的业务范围

### 2.1 纳入范围

一期 compare 仅覆盖以下三类：

1. 两订单对比
- 左右两侧为不同订单。
- 允许同版本或不同版本。

2. 同订单不同版本对比
- 左右两侧为同一订单或同一业务实例。
- 版本不同。

3. 指定 `file_instance_key` 的文件实例对比
- 用于 `00120` 这类“同业务实例、同版本、多文件实例”场景。
- 左右两侧可为同一 `order_identity_key` 下的不同 `file_instance_key`。

### 2.2 不纳入范围

- 不做 SAP 数据 compare。
- 不做跨来源混合 compare。
- 不做替代料关系推断 compare。
- 不做并集 compare。
- 不做未明确业务实例或文件实例时的自动 compare。

---

## 3. compare 输入参数设计

## 3.1 总体原则

compare 输入应按左右两侧分别建模，避免把左右侧的选择条件混在一个平面结构里。

建议最小请求结构：

```json
{
  "query_type": "plan_bom_compare",
  "left": {
    "order_no": "2026-00104",
    "version_no": "A0",
    "order_identity_key": null,
    "file_instance_key": null
  },
  "right": {
    "order_no": "2026-00104",
    "version_no": "A1",
    "order_identity_key": null,
    "file_instance_key": null
  },
  "material_categories": [
    "glass",
    "gap_film",
    "interconnect_bar",
    "busbar",
    "junction_box"
  ]
}
```

## 3.2 单侧最小参数

每一侧允许的最小字段：
- `order_no`
- `version_no`
- `order_identity_key`
- `file_instance_key`

补充说明：
- `order_no` 用于业务输入口径。
- `version_no` 用于显式指定版本。
- `order_identity_key` 用于 `00106` 这类“同短号不同业务实例”精确定位。
- `file_instance_key` 用于 `00120` 这类“同业务实例同版本多文件实例”精确定位。
- `material_categories` 为 compare 全局过滤条件。

## 3.3 参数优先级

单侧参数优先级建议如下：

1. `file_instance_key`
2. `order_identity_key + version_no`
3. `order_no + version_no`
4. `order_identity_key`
5. `order_no`

含义：
- 只要传了 `file_instance_key`，必须直接按文件实例定位，不再自动折算其他候选。
- 只要传了 `order_identity_key`，必须直接在该业务实例内处理，不再回退到短号模糊定位。

---

## 4. compare 结果结构设计

## 4.1 总体响应结构

compare 应继续复用平台统一响应外壳：
- `query_type`
- `status`
- `result_explanation`
- `no_result_analysis`
- `response_meta`
- `query_result`

其中 `query_type` 固定为：

```text
compare
```

## 4.2 `query_result` 建议结构

```json
{
  "compare_scope": "order_vs_order",
  "left": {},
  "right": {},
  "only_left": [],
  "only_right": [],
  "changed": [],
  "same": [],
  "diff_summary": {}
}
```

### 4.2.1 `left / right`

左右侧都应返回最终被 compare 的已解析上下文，至少包含：
- `order_no`
- `order_name`
- `version_no`
- `order_identity_key`
- `file_instance_key`
- `raw_file_name`
- `effective_date`
- `source_type`

### 4.2.2 `only_left / only_right`

定义：
- 左侧存在、右侧不存在的底层材料行：`only_left`
- 右侧存在、左侧不存在的底层材料行：`only_right`

### 4.2.3 `changed`

定义：
- 左右两侧都存在同一底层材料主键，但字段值有变化。

### 4.2.4 `same`

定义：
- 左右两侧都存在同一底层材料主键，且比较字段完全一致。

### 4.2.5 `diff_summary`

至少包含：
- `left_total`
- `right_total`
- `only_left_count`
- `only_right_count`
- `changed_count`
- `same_count`
- `material_category_summary`

`material_category_summary` 建议按 5 类核心材料分别汇总左右差异数。

---

## 5. 当前版本与指定版本的处理规则

## 5.1 指定版本优先

如果单侧传入 `version_no`，则必须按指定版本 compare，不做当前版本自动判定。

## 5.2 未指定版本时

如果单侧未传 `version_no`，则：
- 先按当前版本判定规则选择版本：
  - `effective_date` 倒序
  - 若相同或缺失，再按版本号自然序倒序

## 5.3 当前版本无法唯一判定时

必须返回候选，不允许误落单。

候选类型：
- `candidate_scope = version`

---

## 6. 00120 文件实例场景的处理规则

`00120` 属于：
- 同业务实例
- 同版本
- 多文件实例

处理原则：
- compare 遇到多个 `file_instance_key` 时，必须先返回候选或要求明确选择。
- 不允许默认覆盖。
- 不允许默认并集。

### 6.1 候选返回规则

当 compare 已经定位到：
- 唯一 `order_identity_key`
- 唯一 `version_no`

但该版本下存在多个 `file_instance_key` 时，返回：
- `status.code = CANDIDATE_REQUIRED`
- `candidate_scope = file_instance`
- `candidate_side = left` 或 `right`

### 6.2 显式选择后

用户在单侧传入 `file_instance_key` 后，该侧必须精确定位到该文件实例，再进入 compare。

---

## 7. 00106 多业务实例候选场景的处理规则

`00106` 属于：
- 同短号
- 不同业务实例

处理原则：
- compare 遇到多个 `order_identity_key` 时，必须先返回候选。
- 不允许误落单。

### 7.1 候选返回规则

当 compare 某一侧通过：
- `order_no`
- `review_no`
- `order_name`

定位后命中多个 `order_identity_key` 时，返回：
- `status.code = CANDIDATE_REQUIRED`
- `candidate_scope = order_identity`
- `candidate_side = left` 或 `right`

### 7.2 显式选择后

用户在单侧传入 `order_identity_key` 后，该侧必须精确定位到该业务实例，再做版本选择或 file_instance 选择。

---

## 8. 5 类核心材料的差异判断规则

## 8.1 比较粒度

一期 compare 按底层材料行比较，不按口语类别直接粗暴合并。

建议以以下键识别“同一底层材料”：
- `sap_code`
- 如需稳健回显，可附加：
  - `material_category`
  - `material_name`

## 8.2 字段比较范围

同一 `sap_code` 两侧都存在时，建议比较以下字段：
- `material_name`
- `description`
- `standard_usage`
- `unit`
- `production_loss`
- `remark`
- `replacement_marker`
- `material_category`

## 8.3 only / changed / same 规则

- 左侧有、右侧无：`only_left`
- 右侧有、左侧无：`only_right`
- 两侧都有但比较字段不同：`changed`
- 两侧都有且比较字段一致：`same`

## 8.4 `material_categories` 过滤

- 如果未传 `material_categories`，默认 compare 全部材料行。
- 如果传了 `material_categories`，则只 compare 指定类别。
- 一期重点验收类别仍是：
  - `glass`
  - `gap_film`
  - `interconnect_bar`
  - `busbar`
  - `junction_box`

---

## 9. 标准答案对照与验收方式

## 9.1 对照原则

compare 验收必须优先使用已确认的标准答案，不允许用聊天结论代替。

## 9.2 特殊场景要求

- `00106`：
  - 若存在多个 `order_identity_key`，标准答案必须明确 compare 的左右侧到底选哪个业务实例。
- `00120`：
  - 若 compare 涉及该订单，标准答案必须拆到文件实例级。
  - 未明确 `file_instance_key` 时，不能把并集答案拿来验 compare。

## 9.3 验收口径

至少校验：
- 左侧解析是否正确
- 右侧解析是否正确
- `only_left / only_right / changed / same` 的条数
- `diff_summary` 是否与标准答案一致

---

## 10. 查询历史 / 快照 / 回放是否需要写入

需要。

## 10.1 历史写入

compare 应沿用 `sys_query_log`，不另起一套 compare 日志表。

## 10.2 最小快照基线

成功 compare 时，日志快照建议至少写入：
- 左右侧解析后的：
  - `order_no`
  - `version_no`
  - `order_identity_key`
  - `file_instance_key`
  - `raw_file_name`
- `material_categories`
- `diff_summary`
- 适度截断后的 `query_result`

## 10.3 候选场景是否写入

也建议写入。

原因：
- compare 遇到 `order_identity` 或 `file_instance` 候选时，前端后续需要回放当前候选状态。

---

## 11. 前端后续展示需要的最小字段

前端后续最少需要这些字段：
- `candidate_scope`
- `candidate_side`
- `order_identity_key`
- `file_instance_key`
- `raw_file_name`
- `left`
- `right`
- `only_left`
- `only_right`
- `changed`
- `same`
- `diff_summary`
- `material_category`
- `sap_code`
- `material_name`
- `description`

这样前端可以最小实现：
- 候选选择
- 差异表格
- 左右侧上下文展示
- 差异摘要展示

---

## 12. 不做范围

本设计明确不覆盖：
- 导出
- 前端实现
- SAP
- RAG
- Agent

本轮只定义 compare 的最小设计基线，不进入代码实现。

---

## 13. 推荐开发里程碑

### 里程碑 1：compare 契约与候选链路
- 输入 schema
- 候选返回结构
- `order_identity` / `file_instance` / `version` 三类候选规则

### 里程碑 2：compare 核心对比逻辑
- 左右侧定位
- 当前版本 / 指定版本处理
- `only_left / only_right / changed / same`
- `diff_summary`

### 里程碑 3：日志 / 快照 / 回放
- `sys_query_log` 快照写入
- 候选状态回放
- compare 历史详情基线

### 里程碑 4：标准答案与运行态抽验
- compare 专项答案集
- 小样本对照
- 中样本对照
- Go / No-Go 复判

---

## 14. 风险点与 Go / No-Go 标准

## 14.1 风险点

1. `00106` 这类多业务实例场景，如果候选链路没先跑通，会直接误落单。
2. `00120` 这类文件实例场景，如果不先选 `file_instance_key`，就会重新落回覆盖或并集误区。
3. compare 结果是组合结果，比单订单查询更依赖版本链、候选链和标准答案基线完整性。
4. `00106_SJZKL_A0` 标准答案仍待业务侧修订，在 compare 阶段不能混成实现问题。

## 14.2 Go / No-Go 标准

### compare 设计进入实现的 Go 条件

- `00106` 候选链路稳定
- `00120` 文件实例候选链路稳定
- 标准答案已能支撑 compare 样本设计
- 日志 / 快照 / 回放最小基线已确认

### compare 设计进入实现的 No-Go 条件

- 多业务实例场景仍会误落单
- 多文件实例场景仍会默认覆盖或并集
- compare 标准答案还没明确左右侧或文件实例
- 查询历史 / 快照基线还没定义清楚

---

## 15. 当前结论

当前 `compare` 的最小技术设计结论如下：

1. compare 必须按左右两侧分别建模。
2. `00106` 用 `order_identity_key` 解决业务实例候选问题。
3. `00120` 用 `file_instance_key` 解决文件实例候选问题。
4. compare 遇到多个 `order_identity_key` 或多个 `file_instance_key` 时，必须先返回候选，不允许误落单，也不允许默认覆盖或并集。
5. 当前可以进入 compare 技术设计收口，但仍不能直接宣告 compare 进入实现 Go。

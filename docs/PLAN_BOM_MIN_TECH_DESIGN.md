# BOM 一期最小技术设计

## 一、设计目标

本文件用于定义 `计划 BOM` 一期完整范围进入代码开发前的最小技术设计基线。

当前状态：

> **BOM 一期完整范围：正式 Go（Excel 开发期模式）。**

本设计目标是：

1. 在不接入 SAP 正式源的前提下，先完成 Excel 开发期最小可运行链路。
2. 在不重构 logistics 主链路的前提下，复用平台已有响应、状态、日志、历史详情、回放和审计基线。
3. 在不进入 RAG / 工具层 / Agent / 前端 V3 的前提下，支撑 BOM 一期查询、对比和导出。
4. 让后续代码实现有唯一设计基线，避免按零散规则直接写实现。

---

## 二、一期受控范围说明

### 1. 一期纳入范围

| 范围 | 说明 | 实现属性 |
| --- | --- | --- |
| Excel 开发期入库 | 解析业务提供的 BOM Excel 样本，入库 BOM 头、材料行、修订区 | BOM 域特有 |
| 订单定位 | 支持订单号、订单名称、评审号别名定位 | BOM 域特有 |
| 当前版本判定 | 按生效日期倒序，再按版本号自然序倒序 | BOM 域特有 |
| 5 类材料查询 | 玻璃、间隙膜、互联条、汇流条、接线盒 | BOM 域特有 |
| 多订单表格查询 | 支持多个订单材料规格汇总展示 | BOM 域特有 |
| 两订单差异对比 | 按底层物料行比较，不按口语类别粗暴合并 | BOM 域特有 |
| 查询历史 / 快照 / 回放 | 沿用 `sys_query_log` 和现有历史详情接口思路 | 平台复用 |
| 响应结构 | 沿用 `response_meta / status / result_explanation / query_result` 基线 | 平台复用 |
| 异步导出 | 当前查询结果导出，xlsx / csv，500 行分段 | BOM 域实现，平台规范复用 |

### 2. 一期明确不做

- 不接入 SAP 正式源。
- 不做“功率预测 -> 电池配置”。
- 不做替代料关系推断。
- 不做 RAG。
- 不做工具层。
- 不做 Agent 编排。
- 不做前端 V3 或领导演示版 UI。
- 不做不受查询条件约束的无限制全量导出。

### 3. 文档一致性审查结论

已审查当前仓库正式文档：

- `docs/NEXT_TASK.md`
- `docs/CURRENT_STATUS.md`
- `docs/PLAN_BOM_RULES_TEMPLATE.md`
- `docs/PLAN_BOM_FIELD_DICTIONARY_TEMPLATE.md`
- `docs/PLAN_BOM_QUESTION_SET_TEMPLATE.md`
- `docs/PLAN_BOM_REAL_MATERIALS_PREASSESSMENT.md`
- `docs/PLAN_BOM_OWNER_CONFIRMATION.md`
- `docs/PLAN_BOM_SOURCE_SWITCH_RULE.md`
- `docs/PLAN_BOM_EXPORT_SPEC.md`
- `docs/PLAN_BOM_INPUT_PACKAGE_CHECKLIST.md`
- `docs/PLAN_BOM_INPUT_PACKAGE_GUIDE.md`

当前未发现会阻塞本设计的规则冲突。统一结论为：BOM 一期正式 Go，Excel 开发期模式，SAP 和功率预测均不进入本期。

---

## 三、数据模型设计

### 1. 总体模型

建议新增 BOM 域独立业务表，不复用 logistics 业务表。

推荐最小表：

1. `plan_bom_import_batch`
2. `plan_bom_header`
3. `plan_bom_material_line`
4. `plan_bom_revision`
5. `plan_bom_export_task`
6. `plan_bom_export_file`

其中：

- `sys_query_log` 继续作为平台查询历史、快照、回放和审计表，不在 BOM 域新建一套查询历史表。
- `plan_bom_export_task / plan_bom_export_file` 是导出任务业务状态表，建议新增，因为导出异步状态、文件分段、过期清理不适合塞入 `sys_query_log`。

### 2. BOM 头表：`plan_bom_header`

用途：存储订单维度、版本维度和文件维度的 BOM 头信息。

推荐字段：

| 字段 | 类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| id | bigint | 是 | 技术主键 |
| order_no | varchar(128) | 是 | 订单号，评审号别名最终也查该字段 |
| version_no | varchar(64) | 是 | 版本号，例如 A0、A1、A10 |
| file_no | varchar(128) | 否 | 文件号 |
| order_name | varchar(512) | 否 | 订单名称，支持模糊查询 |
| effective_date | date | 否 | 当前版本排序优先字段，来自修订区或可解析日期 |
| source_type | varchar(32) | 是 | `EXCEL` 或后续 `SAP` |
| source_tag | varchar(64) | 是 | Excel 开发期固定为 `manual_import_source` |
| import_batch_id | varchar(64) | 是 | 入库批次号 |
| raw_file_name | varchar(512) | 否 | 原始文件名 |
| raw_sheet_name | varchar(128) | 否 | 原始 sheet 名 |
| is_active | tinyint | 是 | 是否当前有效记录，默认 1 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

唯一键：

```text
uk_plan_bom_header = order_no + version_no + source_type
```

业务唯一键：

```text
order_no + version_no
```

说明：

- 文档确认的 BOM 头唯一键是 `订单号 + 版本号`。
- 表级唯一键建议额外带 `source_type`，用于 SAP 切换期保留 Excel 旧数据。
- 查询时必须按来源优先级折算为业务唯一版本：同一 `订单号 + 版本号` 同时存在 SAP 和 Excel 时，SAP 优先。

### 3. BOM 材料明细表：`plan_bom_material_line`

用途：存储 BOM 材料行，是 5 类材料查询和差异对比的核心表。

推荐字段：

| 字段 | 类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| id | bigint | 是 | 技术主键 |
| order_no | varchar(128) | 是 | 冗余订单号，便于查询 |
| version_no | varchar(64) | 是 | 冗余版本号 |
| sap_code | varchar(128) | 是 | SAP 编码，材料行唯一键组成部分 |
| line_no | varchar(64) | 否 | Excel 原始序号，不作为稳定主键 |
| material_name | varchar(256) | 是 | 原始物料名称 |
| material_category | varchar(64) | 否 | 系统归类：glass / gap_film / interconnect_bar / busbar / junction_box / other |
| description | text | 否 | 原始描述 |
| standard_usage | decimal(18,6) | 否 | 标准用量 |
| unit | varchar(64) | 否 | 单位 |
| production_loss | varchar(64) | 否 | 生产损耗，保留原始文本更稳 |
| remark | text | 否 | 备注 |
| replacement_marker | varchar(32) | 否 | 是否出现明确替代标识，仅用于原样提示 |
| source_type | varchar(32) | 是 | `EXCEL` 或后续 `SAP` |
| source_tag | varchar(64) | 是 | Excel 开发期固定为 `manual_import_source` |
| import_batch_id | varchar(64) | 是 | 入库批次号 |
| raw_row_no | int | 否 | 原始 Excel 行号 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

唯一键：

```text
uk_plan_bom_material_line = order_no + version_no + sap_code + source_type
```

业务唯一键：

```text
order_no + version_no + sap_code
```

说明：

- 文档确认的材料行唯一键是 `订单号 + 版本号 + SAP编码`。
- `line_no` 只能作为辅助展示或排查字段，不参与一期稳定唯一键。
- 如真实数据出现同一 `订单号 + 版本号 + SAP编码` 下多行不能合并的情况，先作为数据异常进入导入报告，不在一期直接改唯一键。

### 4. 修订区表：`plan_bom_revision`

用途：存储版本修订记录，用于当前版本判定和修订内容展示。

推荐字段：

| 字段 | 类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| id | bigint | 是 | 技术主键 |
| order_no | varchar(128) | 是 | 订单号 |
| version_no | varchar(64) | 是 | 版本号 |
| revision_version | varchar(64) | 否 | 修订版本 |
| revision_content | text | 否 | 修订内容 |
| reviser | varchar(128) | 否 | 修订人 |
| effective_date | date | 否 | 生效日期 |
| source_type | varchar(32) | 是 | `EXCEL` 或后续 `SAP` |
| source_tag | varchar(64) | 是 | Excel 开发期固定为 `manual_import_source` |
| import_batch_id | varchar(64) | 是 | 入库批次号 |
| raw_row_no | int | 否 | 原始 Excel 行号 |
| created_at | datetime | 是 | 创建时间 |

索引建议：

- `idx_plan_bom_revision_order = order_no`
- `idx_plan_bom_revision_version = order_no + version_no`
- `idx_plan_bom_revision_effective = order_no + effective_date`

说明：

- 如果 Excel 中修订区无法稳定拆出为多行，允许先把修订区原始文本入库到 `revision_content`，但必须尽量解析 `revision_version` 和 `effective_date`。
- 当前版本判定依赖 `effective_date` 和 `version_no`，因此这两个字段是解析质量的核心验收点。

### 5. 导入批次表：`plan_bom_import_batch`

用途：记录一次 Excel 入库任务，便于回溯、失败排查和后续 SAP 切换重跑。

推荐字段：

| 字段 | 类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| batch_id | varchar(64) | 是 | 批次号 |
| source_type | varchar(32) | 是 | 一期为 `EXCEL` |
| source_tag | varchar(64) | 是 | 一期为 `manual_import_source` |
| file_name | varchar(512) | 是 | 文件名 |
| file_hash | varchar(128) | 否 | 文件哈希，防重复导入 |
| status | varchar(32) | 是 | pending / running / success / failed |
| total_files | int | 否 | 文件数 |
| total_headers | int | 否 | BOM 头数量 |
| total_lines | int | 否 | 材料行数量 |
| error_message | text | 否 | 失败原因，内部可见 |
| created_at | datetime | 是 | 创建时间 |
| finished_at | datetime | 否 | 完成时间 |

### 6. 导出任务表：`plan_bom_export_task`

用途：记录异步导出主任务。

推荐字段：

| 字段 | 类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| export_id | varchar(64) | 是 | 导出任务 ID |
| batch_id | varchar(64) | 是 | 导出批次号，文件名使用 |
| query_log_id | bigint | 否 | 对应 `sys_query_log.id` |
| query_type | varchar(64) | 是 | plan_bom_detail / plan_bom_compare / plan_bom_multi |
| export_format | varchar(16) | 是 | xlsx / csv |
| status | varchar(32) | 是 | pending / running / success / failed / expired |
| total_rows | int | 是 | 导出总行数 |
| part_total | int | 是 | 总分段数 |
| expires_at | datetime | 是 | 过期时间，创建后 7 天 |
| error_message | text | 否 | 内部失败原因 |
| user_message | varchar(256) | 否 | 用户可见失败文案 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

### 7. 导出文件表：`plan_bom_export_file`

用途：记录每个分段文件。

推荐字段：

| 字段 | 类型建议 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| id | bigint | 是 | 技术主键 |
| export_id | varchar(64) | 是 | 导出任务 ID |
| part_no | int | 是 | 第几段 |
| part_total | int | 是 | 共几段 |
| row_start | int | 是 | 起始行 |
| row_end | int | 是 | 结束行 |
| file_name | varchar(512) | 是 | 文件名 |
| file_path | varchar(1024) | 是 | 服务端存储路径 |
| file_size | bigint | 否 | 文件大小 |
| status | varchar(32) | 是 | pending / running / success / failed / expired |
| created_at | datetime | 是 | 创建时间 |

---

## 四、Excel 入库链路设计

### 1. 解析流程

建议流程：

1. 上传或指定 BOM Excel 文件。
2. 生成 `import_batch_id`。
3. 读取 workbook，逐个 sheet 识别 BOM 头、材料明细区、修订区。
4. 解析 BOM 头字段：文件号、版本号、订单号、订单名称。
5. 解析材料明细行：序号、SAP编码、物料名称、描述、标准用量、单位、生产损耗、备注。
6. 解析修订区：修订版本、修订内容、修订人、生效日期。
7. 执行字段标准化：去空格、全角半角统一、日期解析、数值解析。
8. 执行材料类别归类：按物料名称 + 描述识别 5 类核心材料。
9. 执行唯一键校验和去重。
10. 写入 `plan_bom_header / plan_bom_material_line / plan_bom_revision`。
11. 写入导入批次统计和异常报告。

### 2. 去重逻辑

去重分三层：

| 层级 | 规则 | 处理方式 |
| --- | --- | --- |
| 文件级 | 同一文件哈希重复导入 | 默认阻止重复导入，允许人工选择覆盖 |
| BOM 头级 | 同一 `订单号 + 版本号 + source_type` | 同批次覆盖旧记录，保留批次记录 |
| 材料行级 | 同一 `订单号 + 版本号 + SAP编码 + source_type` | 同批次覆盖；跨批次按最新成功批次生效 |

说明：

- 文档业务唯一键不包含 `source_type`，但表级唯一键建议包含 `source_type`，用于 SAP 和 Excel 共存期。
- 查询层统一执行来源优先级折算，避免 Excel 覆盖 SAP。

### 3. 唯一键规则

业务唯一键：

```text
BOM 头：订单号 + 版本号
材料行：订单号 + 版本号 + SAP编码
```

开发期表级唯一键：

```text
BOM 头：订单号 + 版本号 + source_type
材料行：订单号 + 版本号 + SAP编码 + source_type
```

版本链排序：

- 版本号按自然序比较，例如 `A2 < A10`。
- 不允许直接按字符串字典序比较。

### 4. 旧数据保留方式

Excel 开发期数据统一标记：

```text
source_type = EXCEL
source_tag = manual_import_source
```

SAP 后续接入时：

- Excel 旧数据继续保留。
- SAP 数据 `source_type = SAP`。
- 同一 `订单号 + 版本号` 同时存在 SAP 与 Excel 时，查询层优先返回 SAP。
- SAP 切换时必须重跑入库、重建索引、重做去重、重跑一期问题集回归。

---

## 五、查询设计

### 1. 查询入口建议

建议后续实现时先提供 BOM 域直连接口，再接自然语言路由。

最小接口建议：

| 接口 | 用途 | 说明 |
| --- | --- | --- |
| `POST /api/v1/plan-bom/import/excel` | Excel 入库 | 可先做本地文件路径或上传二选一 |
| `POST /api/v1/plan-bom/query/detail` | 单订单或多订单材料规格查询 | 支持订单号、订单名称、评审号别名 |
| `POST /api/v1/plan-bom/query/compare` | 两订单材料差异对比 | 按底层材料行比较 |
| `POST /api/v1/plan-bom/export` | 当前查询结果导出 | 异步任务 |
| `GET /api/v1/plan-bom/export/{export_id}` | 查询导出任务状态 | 返回分段文件状态 |

说明：

- 接口路径只是设计建议，代码阶段可结合当前 router 风格微调。
- BOM 查询结果必须写 `sys_query_log`，便于历史页复用。

### 2. 订单号查询

输入：

- 完整订单号。
- 短订单号片段，例如 `00104`。

策略：

1. 若输入符合完整订单号格式，优先精确匹配 `order_no`。
2. 若不是完整订单号，按 `order_no LIKE %输入%` 查候选。
3. 若命中 1 个订单，进入版本选择。
4. 若命中多个订单，返回候选列表。
5. 若无命中，返回空结果状态。

候选列表字段：

- `order_no`
- `order_name`
- `version_no`
- `effective_date`
- `source_type`

### 3. 订单名称查询

输入：

- 客户、国家、型号、订单名称片段。

策略：

1. 按 `order_name LIKE %输入%` 查询。
2. 可辅助匹配 `order_no`，避免订单名称中包含订单号时漏查。
3. 多命中返回候选列表。
4. 单命中进入版本选择。

### 4. 评审号别名查询

规则：

- 评审号不单独建核心业务字段。
- 前端输入“评审号”时，后端直接查 `order_no`。
- 评审号作为订单号别名进入词典。
- 类似 `创维-01182` 的输入，按完整字符串做 `LIKE` 匹配。
- 同题同时给订单号和评审号时，订单号优先。

设计建议：

```text
if order_no is not empty:
    use order_no
elif review_no is not empty:
    use review_no as order_no_like
else:
    use order_name or return parameter error
```

多命中时返回：

```json
{
  "query_type": "candidate_list",
  "candidates": [],
  "result_explanation": {
    "summary": "评审号命中多个订单，请选择后继续查询。"
  }
}
```

### 5. 当前版本选择策略

输入未指定版本时，自动选择当前版本。

排序规则：

1. 先按 `effective_date` 倒序。
2. 若生效日期相同或缺失，再按 `version_no` 自然序倒序。
3. 若仍无法判断，返回“版本待人工确认”。

自然序比较要求：

- `A2 < A10`
- `V1 < V2 < V10`
- 数字片段按数字比较，非数字片段按原文本比较。

建议输出：

| 场景 | status.code | 说明 |
| --- | --- | --- |
| 成功选择当前版本 | OK | 正常返回 |
| 无版本 | EMPTY_RESULT | 没有匹配 BOM |
| 多版本但无法排序 | VERSION_NEED_CONFIRM | 返回候选版本 |

### 6. 5 类材料规格查询

标准类别：

| 标准类别 | 用户说法 | 命中规则 |
| --- | --- | --- |
| glass | 玻璃 | 物料名称 + 描述 |
| gap_film | 间隙膜、间隙贴膜、贴膜 | 物料名称 + 描述 |
| interconnect_bar | 互联条、焊带 | 物料名称 + 描述 |
| busbar | 汇流条、汇流 | 物料名称 + 描述 |
| junction_box | 接线盒、线盒 | 物料名称 + 描述 |

查询规则：

- 查询时看 `material_name + description`。
- 返回时展示原始 `material_name`。
- 同一订单下同类材料多行命中时全部返回。
- 替代料仅在备注、修订内容、物料名称中出现明确替代标识时原样展示。
- 不输出结构化替代关系。

返回建议字段：

- `order_no`
- `order_name`
- `version_no`
- `effective_date`
- `material_category`
- `material_name`
- `sap_code`
- `description`
- `standard_usage`
- `unit`
- `production_loss`
- `remark`
- `replacement_marker`
- `source_type`

### 7. 多订单表格查询

适用问题：

- “查找多个订单的玻璃、间隙贴膜、焊带、汇流条、接线盒规格描述并生成表格”

设计：

1. 对每个订单独立执行订单定位和版本选择。
2. 每个订单查询 5 类材料。
3. 返回扁平行结构，便于前端表格和导出复用。
4. 单个订单无数据时，在结果中保留该订单的状态说明，不让整批失败。

结果结构：

```json
{
  "query_type": "detail",
  "mode": "multi_order_materials",
  "items": [],
  "order_status": []
}
```

### 8. 两订单差异对比

适用问题：

- “订单 A 和订单 B 材料规格有什么不一样”

设计：

1. 分别定位两个订单。
2. 分别选择当前版本，除非用户指定版本。
3. 分别取当前版本下材料行。
4. 按底层材料行比较，不按映射后的 5 类粗暴合并。
5. 优先按 `sap_code` 对齐。
6. 若一侧存在、一侧不存在，标记为 `missing_left` 或 `missing_right`。
7. 若两侧均存在，比较 `material_name / description / standard_usage / unit / production_loss / remark`。
8. 同一订单和自己对比时，返回无差异或题面重复提示，不抛系统异常。

差异类型建议：

| diff_type | 含义 |
| --- | --- |
| same | 无差异 |
| changed | 同 SAP 编码但字段不同 |
| missing_left | 右侧有，左侧无 |
| missing_right | 左侧有，右侧无 |
| duplicate_or_ambiguous | 同一侧存在重复或无法唯一对齐 |

---

## 六、结果结构设计

### 1. 是否复用现有平台响应结构

结论：复用。

BOM 域不应另起一套前端不兼容的响应结构。建议沿用当前平台基线：

```json
{
  "question": "...",
  "parsed": {},
  "query_result": {},
  "response_meta": {}
}
```

若走直连接口，也应保证 `query_result` 内含最小共享字段：

```json
{
  "query_type": "detail",
  "domain": "plan_bom",
  "execution_mode": "direct",
  "status": {},
  "result_explanation": {},
  "no_result_analysis": null,
  "response_meta": {},
  "items": [],
  "total": 0
}
```

### 2. 字段复用建议

| 字段 | BOM 设计 | 复用方式 |
| --- | --- | --- |
| domain | 固定 `plan_bom` | 平台共享字段 |
| query_type | detail / compare / candidate_list / export | 平台共享字段 |
| execution_mode | direct / fallback / error_fallback | 平台共享字段 |
| status | OK / EMPTY_RESULT / VERSION_NEED_CONFIRM / CANDIDATE_REQUIRED 等 | 平台状态基线扩展 |
| result_explanation | 结构化摘要说明 | 复用前端解释展示模式 |
| no_result_analysis | 空结果原因和建议 | 复用空结果展示模式 |
| response_meta | question / domain / mode / status / result_count | 复用平台响应元信息 |
| trace_id | 请求追踪 ID | 复用平台审计链路 |

### 3. 状态码建议

建议 BOM 域在平台状态基线之上新增少量域内状态码：

| code | 场景 | success | severity |
| --- | --- | --- | --- |
| OK | 查询成功 | true | info |
| EMPTY_RESULT | 无匹配 BOM 或无匹配材料 | true | warning |
| CANDIDATE_REQUIRED | 订单号 / 评审号命中多个候选 | true | warning |
| VERSION_NEED_CONFIRM | 当前版本无法自动判定 | true | warning |
| PARAMETER_INVALID | 缺少订单条件或参数冲突 | false | error |
| EXPORT_FAILED | 导出失败 | false | error |
| EXECUTION_ERROR | 主链路异常 | false | error |

说明：

- `fallback` 不是 BOM 平台默认能力，一期不主动设计 fallback 语义结果。
- 如后续临时需要 fallback，必须明确来源、可信范围、状态展示和是否进入历史回放。

### 4. 结果解释设计

`result_explanation` 建议最小结构：

```json
{
  "summary": "已查询订单 GCL-... 当前版本 A1 的 5 类材料规格。",
  "query_scope": {
    "order_no": "...",
    "version_no": "...",
    "materials": ["glass", "gap_film"]
  },
  "data_source": {
    "source_type": "EXCEL",
    "source_tag": "manual_import_source"
  },
  "warnings": []
}
```

空结果时 `no_result_analysis` 建议包含：

- 未找到订单。
- 订单存在但当前版本无材料。
- 材料类别未命中。
- 评审号命中多个候选，需用户选择。

---

## 七、历史 / 快照 / 回放设计

### 1. 是否沿用 `sys_query_log`

结论：沿用。

原因：

- 当前平台查询历史、详情和重新查询已经基于 `sys_query_log`。
- BOM 域只需要补齐 request_payload 中的原生快照，历史详情即可复用。
- 不建议 BOM 域新增独立查询历史表，否则前端历史页和回放链路会重复建设。

### 2. `sys_query_log` 写入建议

最小字段：

| 字段 | BOM 写入建议 |
| --- | --- |
| trace_id | 每次查询生成 |
| query_type | `PLAN_BOM_DETAIL` / `PLAN_BOM_COMPARE` / `PLAN_BOM_EXPORT` |
| question_text | 原始问题或条件摘要 |
| request_payload | JSON 快照 |
| route_type | `plan_bom` |
| metric_type | 可填 `bom_material` / `bom_compare` / `bom_export` |
| result_count | 结果行数或差异行数 |
| status | 顶层状态码 |
| message | 状态说明 |

### 3. 最小快照结构

`request_payload` 建议写入：

```json
{
  "question": "...",
  "parsed": {
    "selected_domain": "plan_bom",
    "mode": "detail",
    "query_type": "detail",
    "order_no": "...",
    "review_no": "...",
    "order_name": "...",
    "version_no": "...",
    "material_categories": [],
    "source_scope": "excel"
  },
  "response_meta": {
    "question": "...",
    "domain": "plan_bom",
    "mode": "detail",
    "status": {},
    "trace_ready": true,
    "result_count": 0
  },
  "query_result": {
    "query_type": "detail",
    "domain": "plan_bom",
    "execution_mode": "direct",
    "status": {},
    "result_explanation": {},
    "no_result_analysis": null,
    "items": [],
    "total": 0
  },
  "execution_summary": {
    "source_type": "EXCEL",
    "source_tag": "manual_import_source",
    "table_names": [
      "plan_bom_header",
      "plan_bom_material_line",
      "plan_bom_revision"
    ]
  }
}
```

### 4. 重新查询设计

历史重新查询应优先使用：

1. `parsed.order_no`
2. `parsed.review_no`
3. `parsed.order_name`
4. `parsed.version_no`
5. `parsed.material_categories`
6. `parsed.mode`

若历史记录是候选列表状态：

- 重新查询应回到候选列表，而不是随机选择某个候选。
- 用户选择候选后再发起新查询，并生成新的 `sys_query_log`。

### 5. 审计复用方式

复用平台审计字段：

- `trace_id`
- `execution_mode`
- `status.code`
- `result_count`
- `source_type`
- `source_tag`
- `import_batch_id`

BOM 域特有审计补充：

- `order_no`
- `version_no`
- `source_priority`
- `candidate_count`
- `export_id`

---

## 八、导出设计

### 1. 接口建议

最小接口：

| 接口 | 方法 | 用途 |
| --- | --- | --- |
| `/api/v1/plan-bom/export` | POST | 创建导出任务 |
| `/api/v1/plan-bom/export/{export_id}` | GET | 查询导出状态 |
| `/api/v1/plan-bom/export/{export_id}/files/{file_id}` | GET | 下载单个分段文件 |

创建导出请求建议：

```json
{
  "query_log_id": 123,
  "format": "xlsx",
  "query_snapshot": {},
  "columns": []
}
```

说明：

- 优先基于 `query_log_id` 导出，保证“只导当前查询结果”。
- 如果允许直接传 `query_snapshot`，必须验证其来源和查询条件，不允许绕过查询条件做全量导出。

### 2. 任务状态

状态沿用导出规范：

| 状态 | 含义 |
| --- | --- |
| pending | 已提交，等待处理 |
| running | 正在生成文件 |
| success | 文件已生成 |
| failed | 生成失败 |
| expired | 文件已过期 |

失败用户文案固定：

```text
系统异常，导出失败，请联系管理员
```

内部错误写入：

- `plan_bom_export_task.error_message`
- 后端日志
- 必要时关联 `sys_query_log.message`

### 3. 分段导出策略

规则：

- 只导当前查询结果。
- 支持 `xlsx / csv`。
- 单文件最大 500 行。
- 超过 500 行自动分段。
- 每段都包含表头。
- 文件保留一周。

分段计算：

```text
part_total = ceil(total_rows / 500)
part_no 从 1 开始
row_start = (part_no - 1) * 500 + 1
row_end = min(part_no * 500, total_rows)
```

### 4. 文件命名策略

命名格式：

```text
BOM查询结果_{yyyyMMddHHmmss}_{batch_id}_{part_no}of{part_total}.{ext}
```

示例：

```text
BOM查询结果_20260415193000_批次001_1of3.xlsx
```

### 5. 导出结果与查询结果一致性

导出必须基于查询快照：

- 查询结果页展示什么，导出就导什么。
- 不重新扩大查询范围。
- 不绕开候选列表选择。
- 候选列表状态不能直接导出为材料明细，除非用户选择候选后形成正式查询结果。

---

## 九、平台复用与 BOM 域特有边界

### 1. 可直接复用 logistics / 平台主线能力

| 能力 | 复用方式 |
| --- | --- |
| `sys_query_log` | 查询历史、详情、回放、审计统一复用 |
| 历史列表 / 详情接口思路 | 通过快照字段兼容 BOM 域 |
| `response_meta / status / result_explanation` | 作为 BOM 查询响应基线 |
| `query_type / result_count / status_code` | 作为前端消费共享字段 |
| 前端 V2 表格展示能力 | 后续可复用结构化 `items` |
| 空结果展示能力 | 复用 `no_result_analysis` |
| 日志最小快照基线 | BOM 查询写入原生快照，减少历史详情兼容补造 |

### 2. 必须 BOM 域特有实现

| 能力 | 原因 |
| --- | --- |
| Excel BOM 解析 | BOM 文件结构与 logistics Excel 完全不同 |
| BOM 头 / 材料行 / 修订区表 | 业务实体不同，不能复用物流 DWS 表 |
| 当前版本判定 | 依赖 BOM 生效日期和版本号自然序 |
| 评审号别名查订单号 | BOM 特有业务语义 |
| 5 类材料归类 | 依赖物料名称 + 描述 |
| 两订单底层材料行对比 | BOM 特有对比口径 |
| 异步导出任务表 | BOM 一期明确要求分段、保留和状态管理 |

---

## 十、风险点

| 风险 | 影响 | 处理建议 |
| --- | --- | --- |
| Excel 样本格式不稳定 | 入库解析失败或字段错位 | 第一阶段先做解析报告和失败行输出 |
| 同一 `订单号 + 版本号 + SAP编码` 出现多行 | 违反当前唯一键设计 | 先作为数据异常报告，不擅自改主键 |
| 生效日期缺失较多 | 当前版本可能无法自动判定 | 返回“版本待人工确认”和候选版本 |
| 评审号 / 短订单号多命中 | 查询无法直接落到唯一订单 | 返回候选列表，不强行选择 |
| 标准答案与样本版本不一致 | 验收时误判 | 验收前锁定样本批次和答案版本 |
| 导出任务文件清理未实现 | 文件长期堆积 | 第一版就设计 `expires_at` 和清理策略 |
| SAP 后续字段与 Excel 字段不一致 | 切换成本增加 | 以逻辑字段为核心，SAP 映射后置补齐 |
| 复用 `sys_query_log` 但快照不完整 | 历史详情仍需兼容补造 | BOM 首版即写入 parsed / response_meta / query_result |

---

## 十一、后续实现顺序建议

### 里程碑 1：BOM 域骨架与数据模型

目标：

- 建立 `plan_bom` 域目录、schemas、repositories、services、api。
- 新增 BOM 头、材料行、修订区、导入批次、导出任务表模型或迁移设计。

验收：

- 表结构能表达正式字段字典。
- 唯一键规则清楚。
- 不影响 logistics 现有接口。

### 里程碑 2：Excel 入库与解析报告

目标：

- 支持 Excel 样本入库。
- 输出导入批次、成功数量、失败行和字段异常。
- 写入 `manual_import_source`。

验收：

- 能从样本解析出 BOM 头、材料行、修订区。
- 能识别并报告唯一键冲突。

### 里程碑 3：基础查询与当前版本判定

目标：

- 支持订单号、订单名称、评审号别名查询。
- 支持候选列表。
- 支持当前版本选择。
- 支持 5 类材料查询。

验收：

- 覆盖 `BOM问题_答案.xlsx` 中单订单材料问题。
- 多命中不误选，返回候选列表。

### 里程碑 4：两订单对比与历史快照

目标：

- 支持两个订单材料行差异对比。
- 写入 `sys_query_log` 原生快照。
- 历史详情可展示 BOM 查询结果。

验收：

- 同一订单和自己对比不报错。
- 对比结果能按 `sap_code` 标记 changed / missing。
- 历史详情优先消费 BOM 原生快照。

### 里程碑 5：异步导出最小实现

目标：

- 支持从当前查询结果创建导出任务。
- 支持 xlsx / csv。
- 支持 500 行分段。
- 支持状态查询和文件过期。

验收：

- 当前查询结果可导出。
- 超过 500 行自动分段。
- 失败时返回固定文案。

### 里程碑 6：一期验收回归

目标：

- 基于 `BOM问题_答案.xlsx` 做一期验收回归。
- 剔除 5 条留空题。
- 汇总未通过题目和原因。

验收：

- 能解释每条失败是数据缺失、规则不匹配还是实现问题。
- 不把二期题和留空题计入一期失败。

---

## 十二、设计附录：实现前细化约束

### 1. 评审号 / 短订单号多命中候选列表协议

触发条件：

- `review_no` 按订单号别名模糊匹配命中多个订单。
- 短订单号片段按 `order_no LIKE` 命中多个订单。
- 订单名称片段命中多个订单，且无法通过当前版本规则收敛到唯一订单。

最大返回条数：

- 默认最多返回 20 条候选。
- 超过 20 条时只返回前 20 条，并在 `response_meta.status.extras.candidate_truncated = true` 中标记被截断。
- 前端应提示“候选过多，请补充更完整的订单号或订单名称”。

排序规则：

1. `source_type` 优先级：SAP 高于 EXCEL。
2. `effective_date` 倒序，空日期排后。
3. `version_no` 自然序倒序。
4. `order_no` 升序，保证同条件下稳定排序。

返回字段：

| 字段 | 说明 |
| --- | --- |
| order_no | 订单号 |
| order_name | 订单名称 |
| version_no | 版本号 |
| effective_date | 生效日期 |
| source_type | 来源类型，EXCEL / SAP |
| source_tag | 来源标记，Excel 开发期为 manual_import_source |
| file_no | 文件号 |
| match_reason | 命中原因，例如 review_no_like / order_no_like / order_name_like |

候选列表响应建议：

```json
{
  "query_type": "candidate_list",
  "domain": "plan_bom",
  "execution_mode": "direct",
  "status": {
    "code": "CANDIDATE_REQUIRED",
    "message": "命中多个订单，请选择后继续查询。",
    "success": true,
    "severity": "warning"
  },
  "candidates": [],
  "total": 20,
  "candidate_total_hint": 35
}
```

说明：

- 候选列表状态不允许直接导出材料明细。
- 重新查询候选列表历史时，应回到候选列表，不随机选择第一条。

### 2. 材料行唯一键冲突处理规则

唯一键基线：

```text
业务唯一键：订单号 + 版本号 + SAP编码
表级唯一键：订单号 + 版本号 + SAP编码 + source_type
```

冲突分级：

| 冲突类型 | 处理规则 | 是否阻塞导入 |
| --- | --- | --- |
| 同批次完全重复行 | 按唯一键去重，仅保留第一条，记录重复警告 | 否 |
| 同批次同键但字段不同 | 写入导入异常报告，不自动合并 | 是，阻塞该 BOM 版本入库 |
| 跨批次同键同 source_type | 最新成功批次覆盖查询生效记录，旧批次保留导入记录 | 否 |
| SAP 与 Excel 同业务键 | 查询层 SAP 优先，Excel 保留 manual_import_source | 否 |
| 同键但 SAP 编码为空 | 视为关键字段缺失，写入异常报告 | 是，阻塞该材料行入库 |

原则：

- 不为了绕开冲突擅自把 `序号` 加入业务唯一键。
- 如果真实资料证明 `SAP编码` 不能唯一代表材料行，必须先回到文档和 owner 重新确认。
- 冲突报告至少包含 `order_no / version_no / sap_code / source_type / raw_file_name / raw_sheet_name / raw_row_no / error_message`。

### 3. 当前版本自动判定的程序化顺序

程序化步骤：

1. 按订单定位得到候选 BOM 头。
2. 若用户明确传入 `version_no`，优先使用指定版本。
3. 若未传版本，过滤 `is_active = 1` 的候选。
4. 对候选按 `effective_date` 分组：
   - 有有效日期的版本优先于无日期版本；
   - 有日期版本按 `effective_date` 倒序。
5. 若最高 `effective_date` 下只有一个版本，选中该版本。
6. 若最高 `effective_date` 下有多个版本，按 `version_no` 自然序倒序。
7. 若自然序最高版本唯一，选中该版本。
8. 若日期和版本号仍无法唯一判断，返回 `VERSION_NEED_CONFIRM`，并给出候选版本。

自然序比较要求：

- 拆分字母段和数字段。
- 数字段按整数比较。
- 字母段按原始文本比较。
- 示例：`A2 < A10`，`V1 < V2 < V10`。

状态输出：

| 场景 | status.code | 处理 |
| --- | --- | --- |
| 指定版本存在 | OK | 使用指定版本 |
| 自动判定唯一当前版本 | OK | 使用当前版本 |
| 无任何版本 | EMPTY_RESULT | 返回空结果分析 |
| 多版本无法自动判定 | VERSION_NEED_CONFIRM | 返回候选版本 |

### 4. SAP / Excel 切换时的工程兼容原则

兼容原则：

1. 逻辑字段优先：查询和响应只依赖 `order_no / version_no / sap_code / material_name / description` 等逻辑字段，不直接暴露 Excel 列名或 SAP 原始列名。
2. 来源隔离：Excel 数据 `source_type = EXCEL`，SAP 数据 `source_type = SAP`，Excel 旧数据 `source_tag = manual_import_source`。
3. 查询优先级：同一 `订单号 + 版本号` 同时存在 SAP 与 Excel 时，查询层优先 SAP。
4. 错误显性化：SAP 字段缺失或映射失败时，不允许用 Excel 静默覆盖 SAP，应返回异常或进入人工确认。
5. 可重建：SAP 切换必须支持重跑入库、重建索引、重做去重、重跑一期问题集回归。
6. 可回溯：查询快照必须写入 `source_type / source_tag / import_batch_id`，保证历史详情可解释当时使用的数据源。

后续 SAP 接入前置条件仍按 `PLAN_BOM_SOURCE_SWITCH_RULE.md` 执行，本设计不把 SAP 接入视为一期当前实现范围。

### 5. 导出任务状态机和失败 / 过期行为

状态机：

```text
pending -> running -> success
pending -> running -> failed
success -> expired
failed -> expired
```

状态说明：

| 状态 | 进入条件 | 用户可见行为 |
| --- | --- | --- |
| pending | 导出任务创建成功，尚未开始生成文件 | 显示“导出任务已提交” |
| running | 后台开始生成分段文件 | 显示“正在生成导出文件” |
| success | 所有分段文件生成成功 | 展示下载入口 |
| failed | 任一关键步骤失败且无法生成完整文件 | 显示“系统异常，导出失败，请联系管理员” |
| expired | 文件超过一周保留期 | 显示“文件已超过保留期限，请重新导出” |

失败行为：

- 用户文案固定为：`系统异常，导出失败，请联系管理员`。
- 内部错误写入 `plan_bom_export_task.error_message`。
- 已生成的临时文件可清理，不向用户暴露半成品。
- `sys_query_log` 中保留导出请求快照和失败状态，便于排查。

过期行为：

- `expires_at = created_at + 7 days`。
- 到期后状态置为 `expired`。
- 过期文件不可下载。
- 用户需要基于原查询历史重新发起导出。

分段一致性：

- 单文件最大 500 行。
- 所有分段属于同一 `batch_id`。
- 任一分段失败时，整个导出任务状态为 `failed`。
- 每个分段文件都必须包含表头。

---

## 十三、是否具备进入代码开发条件

结论：

> **具备进入代码开发条件，但建议先按本设计拆成小里程碑开发。**

依据：

- 文档事实源已经一致。
- 数据源、字段、规则、问题集、owner 和导出边界均已满足开发 Go。
- `plan_bom` 当前仍是占位目录，不存在复杂历史实现包袱。
- 平台已有日志、历史、响应结构和前端 V2 基线可复用。

进入代码开发前仍需注意：

- 第一轮代码应优先做数据模型和 Excel 入库，不要直接做全功能查询。
- 不要把 SAP 切换、RAG、Agent 或功率预测提前混入一期。
- 所有新增和修改代码必须写中文注释。

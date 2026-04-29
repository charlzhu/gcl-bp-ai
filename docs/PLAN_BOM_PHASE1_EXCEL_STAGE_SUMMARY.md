# PLAN_BOM_PHASE1_EXCEL_STAGE_SUMMARY

## 1. 当前阶段目标
本阶段目标是完成 **BOM 一期 Excel 开发期** 的最小可运行链路，并在真实 BOM Excel 样本上完成从导入、落库、查询到答案对照的闭环验证。

当前阶段的重点不是生产级上线，而是确认以下能力已经在开发期模式下真实跑通：
- Excel 作为开发期数据源可稳定入库
- 失败批次不会污染业务数据
- 单订单查询链路可运行
- 当前版本判定可运行
- 5 类核心材料查询可运行
- 受控全量导入抽验链路可运行

## 2. 已完成能力

### 2.1 Excel 单文件导入
- 已支持真实 BOM Excel 单文件读取、解析、批次入库。
- 已支持 BOM 头、材料行、修订记录的落库。
- 已支持导入报告输出。

### 2.2 失败批次回滚
- 已实现失败批次整批回滚。
- 当前策略下，失败批次不会残留 `plan_bom_header / plan_bom_material_line / plan_bom_revision` 半成品数据。

### 2.3 `order_identity_key`
- 已引入 `order_identity_key` 作为开发期内部实例键。
- 该字段用于处理 `00106` 这类“同短号不同业务实例”场景。
- 该字段是开发期内部技术键，不是正式业务主键。

### 2.4 `file_instance_key`
- 已引入 `file_instance_key` 作为开发期内部文件实例键。
- 该字段用于处理 `00120` 这类“同业务实例、同版本、多文件非重复”场景。
- 当前业务确认口径为：开发期按文件实例保留。
- 该字段是开发期内部技术键，不是正式业务主键。

### 2.5 基础查询
- 已支持：
  - 订单号查询
  - 订单名称查询
  - `review_no` / 别名查询
  - 候选列表返回
  - 文件实例候选返回

### 2.6 当前版本判定
- 已支持按当前业务规则执行当前版本选择。
- 在当前中样本与受控全量抽验中，`revision / effective_date` 已恢复到可用状态。

### 2.7 5 类核心材料查询
- 已支持以下 5 类核心材料查询：
  - `glass`
  - `gap_film`
  - `interconnect_bar`
  - `busbar`
  - `junction_box`
- 已完成真实样本下的去噪治理，避免图纸区、备注区、标签区误入核心材料结果。

### 2.8 受控全量导入抽验
- 已对 `BOM 源数据.zip` 中识别出的 `34` 个正文 BOM Excel 文件完成受控全量导入抽验。
- 已排除 `__MACOSX`、`._*` 和非 BOM 正文附件。
- 已完成导入、抽样查询、标准答案对照和全量报告刷新。

## 3. 当前报告结论
- `34` 个正文 BOM Excel 全部导入成功。
- 标准答案对照结果为 `34` 条 `exact_match`。
- `full_import_controlled.go = true`
  - 含义：**受控全量导入抽验链路 Go**
  - 不代表生产级上线 Go。
- `compare.go = true`
  - compare 技术设计、里程碑 1、里程碑 2、里程碑 3、里程碑 4 已完成当前阶段实现。
  - 当前为 `true` 的原因是：Go / No-Go 判断已执行，且当前阶段 Go 结论已完成状态位同步。

## 4. 已知待办
- `00106_SJZKL_A0` 标准答案待业务侧修订。
- compare 里程碑 1 已完成：骨架与候选链路已落代码。
- compare 里程碑 2 已完成：核心差异计算已落代码。
- compare 里程碑 3 已完成最小实现：查询历史 / 快照 / 回放已落代码。
- compare 里程碑 4 已完成：运行态抽验与标准答案对照已执行。
- `BOM compare Go / No-Go 判断` 已执行，当前结论是：**compare 当前阶段 Go**。
- 当前 `compare.go` 已同步为 `true`。
- 导出尚未实现。
- 前端 BOM 明细查询 MVP 已落代码并完成真实常驻前后端 + 浏览器联调。
- SAP 尚未接入。
- 当前全量报告中的部分中文文件名仍存在乱码，如果后续需要发业务侧或领导查看，应额外生成可读版报告。

## 5. 当前不建议继续做什么
- 不建议把 `full_import_controlled.go = true` 误解为生产级全量上线通过。
- 不建议把 `compare.go = true` 误解为 compare 全部完成或生产级上线 Go。
- 不建议直接做导出实现。
- 不建议直接扩到前端 BOM 下一阶段（如 compare 前端页、导出联动或复杂筛选）。
- 不建议直接做 SAP 接入。
- 不建议继续改 `file_instance_key` 或 `order_identity_key` 逻辑，除非出现新的真实样本证据。

## 6. 下一阶段候选任务

### 6.1 导出技术设计
- compare 当前阶段 Go 结论与 `compare.go` 状态位同步已完成。
- 下一步不再是 compare 状态切换，而是 compare 之外的主线任务选择。

### 6.2 导出技术设计
- 输出 BOM 查询结果导出的最小技术设计。
- 明确文件实例场景下导出前是否必须先选择文件实例。

### 6.3 前端 BOM 查询页
- 已完成 BOM 明细查询 MVP。
- 已完成真实常驻前后端 + 浏览器联调。
- 当前已覆盖：
  - `order_no / review_no / order_name` 查询
  - 成功态
  - `order_identity` candidate 态
  - `file_instance` candidate 态
  - 空结果态
  - 错误态
  - 5 类核心材料展示
- 当前未进入：
  - compare 前端页
  - 导出联动
  - 前端权限
  - SAP

### 6.4 SAP 接入前置准备
- 在 Excel 开发期能力稳定后，再评估 SAP 接入前置资料、字段映射和切换方案。

## 7. Go / No-Go 状态说明

### 7.1 受控全量导入抽验
- 状态：`Go`
- 说明：
  - 表示当前 Excel 开发期链路已经具备受控全量抽验通过条件。
  - 不表示生产级上线 Go。

### 7.2 compare
- 状态：`当前阶段 Go（compare.go 已同步为 true）`
- 说明：
  - compare 技术设计已完成。
  - compare 里程碑 1 已完成：骨架与候选链路已落代码。
  - compare 里程碑 2 已完成：核心差异计算已落代码。
  - compare 里程碑 3 已完成最小实现：查询历史 / 快照 / 回放已落代码。
  - compare 里程碑 4 已完成：运行态抽验与标准答案对照已执行。
  - 当前 compare 仍必须遵守：
    - 多业务实例先返回 `order_identity` candidate
    - 多版本先返回 `version` candidate
    - 多文件实例先返回 `file_instance` candidate
    - candidate 未消除前禁止进入差异计算
  - 当前 compare 历史能力复用 `sys_query_log`，没有新增 compare 专用历史表。
  - 当前 replay 读取历史快照，不重新计算 compare。
  - 当前快照采用受控截断策略，不能视为无限制全量明细历史。
  - 当前运行态结果：
    - candidate `2/2` 通过
    - success `3/3` 通过
    - replay `5/5` 通过
    - compare `POST` smoke 通过
    - compare replay `GET` smoke 通过
  - `BOM compare Go / No-Go 判断` 已执行。
  - 当前结论是：**compare 当前阶段 Go**。
  - 该 Go 仅针对 BOM 一期 Excel 开发期范围内的 compare 主线。
  - 不等于 compare 全部完成。
  - 不等于生产级上线 Go。
  - 不包含导出、前端、SAP、RAG、Agent。
  - 当前 `compare.go = true` 表示：当前阶段 Go 结论已同步到事实源。
  - `00106_SJZKL_A0` 标准答案仍待业务侧修订。
  - 因此当前不能判定 compare 已全部完成，但已经完成当前阶段 Go 判断。

### 7.3 导出
- 状态：`No-Go`
- 说明：
  - 导出尚未实现，不建议直接推进。

### 7.4 前端联调
- 状态：`BOM 明细查询 MVP 已联调通过`
- 说明：
  - 已完成真实常驻前端 + 常驻后端 + 浏览器联调。
  - 当前通过的范围仅限 BOM 明细查询 MVP。
  - 不等于 compare 前端页已实现。
  - 不等于导出、权限或 SAP 已接通。

### 7.5 SAP 接入
- 状态：`No-Go`
- 说明：
  - 当前仍处于 Excel 开发期，不进入 SAP 接入实现。

## 8. 当前阶段结论
当前可以明确判定：
- **BOM 一期 Excel 开发期阶段已完成阶段性收口。**
- 当前最适合进入的不是生产级上线，而是：
  - 导出技术设计
  - 前端 BOM 查询页下一阶段规划
  - SAP 接入前置准备

在进入这些阶段前，应继续保留以下事实：
- `00106_SJZKL_A0` 仍是业务侧标准答案待修订项
- `file_instance_key` 仍是开发期内部技术键，不是业务主键
- `full_import_controlled.go = true` 仅表示受控全量导入抽验链路 Go

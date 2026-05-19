
# 物管域 SAP MID 数据资产审计（M1）

执行时间：2026-05-14 17:02:43 CST
范围：只读审计 `ai/inbox/requirement.md`、SAP MID 元数据/样例附件、智能助手中间库附件和现有后端/前端代码；未连接 Oracle 执行业务表导出，未修改正式业务代码。

## 1. MID 资源库总体判断

1. `ai/inbox/attachments/sap_mid/` 提供了 MID 视图清单、字段元数据、视图 SQL 和 16 个重点视图样例。
2. 附件审计到 MID 视图总数 87 个，字段元数据 7718 行，视图 SQL 记录 87 条。
3. 16 个重点视图覆盖 M2-M5 规划范围：库存、出入库、采购执行、工单组件、SAP BOM。
4. 样例附件每个重点视图均为受控小样本（本次读取为 20 行样例），可用于字段理解和模型设计；不能当作正式源数据。
5. Oracle 真实只读 smoke test 受本地 Python Oracle 驱动缺失阻塞；本报告中关于字段、主键和增量字段的判断均来自附件和现有代码，只能作为 M1 初步方案，M2 进入前必须用只读 Oracle 连接复核。

## 2. 物管相关视图清单与主题归属


| 主题 | MID 视图 | 样例规模 | 初步用途 | 主键/关联键候选 | 增量字段候选 |
|---|---:|---:|---|---|---|
| 库存 | V_HF_SAP_INOUT_DAILY | 20 行 / 35 列 | ZMB52 实时库存、现存量、结存数量、工厂、库存地点、批次、客户/供应商库存 | 物料编码 + 工厂代码 + 库存地点 + 批次 + 评估类型 + 库存日期；无批次时需 source_hash 兜底 | TS、库存日期 |
| 出入库流水 | V_SAP_HFFN_CRKLSZ | 20 行 / 68 列 | ZMB51 出入库明细、移动类型、过账日期、入库/出库数量、采购/工单关联 | 年度 + 单据号 + 单据行 + 工厂代码 + 物料编码；必要时拼接移动类型/过账日期 | 过账日期、创建日期、过账时间 |
| 采购申请 | V_SAP_HFFN_EBAN | 20 行 / 46 列 | 采购申请、申请数量、采购订单回写、需求日期 | BANFN + BNFPO | ERDAT、申请日期、计划日期、批准日期 |
| 采购订单头 | V_SAP_HFFN_EKKO | 20 行 / 169 列 | 采购订单头、供应商、组织、币种、合同/状态 | MANDT + EBELN | AEDAT、BEDAT、RELEASE_DATE |
| 采购订单行 | V_SAP_HFFN_EKPO | 20 行 / 348 列 | 采购订单行、物料、工厂、数量、价格、删除标识 | MANDT + EBELN + EBELP | AEDAT、交货/变更相关字段需业务确认 |
| 交货计划 | V_SAP_HFFN_EKET | 20 行 / 79 列 | 采购订单交期、计划数量、已收货数量 | MANDT + EBELN + EBELP + ETENR | EINDT、SLFDT |
| 采购历史 | V_SAP_HFFN_EKBE | 20 行 / 91 列 | 到货、退货、发票、采购历史流水 | MANDT + EBELN + EBELP + GJAHR + BELNR + BUZEI | BUDAT |
| 生产订单头 | V_SAP_HFFN_AFKO | 20 行 / 167 列 | 工单计划日期、数量、BOM/路线关联 | MANDT + AUFNR | GSTRP、GLTRP、FTRMS；变更字段需确认 |
| 生产订单行 | V_SAP_HFFN_AFPO | 20 行 / 100 列 | 工单产出物料、销售订单关联、计划/入库数量 | MANDT + AUFNR + POSNR | STRMP、ETRMP |
| 工单主数据 | V_SAP_HFFN_AUFK | 20 行 / 127 列 | 工单类型、文本、公司/工厂、状态辅助 | MANDT + AUFNR | ERDAT、AEDAT |
| 工单组件 | V_SAP_HFFN_RESB | 20 行 / 205 列 | 预留/组件需求、组件物料、需求数量、领料状态 | MANDT + RSNUM + RSPOS + RSART；或 AUFNR + MATNR + BDTER 辅助 | BDTER、变更/删除字段需确认 |
| BOM 分配 | V_SAP_HFFN_MAST | 20 行 / 13 列 | 物料到 BOM 的分配关系 | MANDT + MATNR + WERKS + STLAN + STLNR + STLAL | ANDAT、AEDAT |
| BOM 头 | V_SAP_HFFN_STKO | 20 行 / 30 列 | BOM 头、用途、替代、有效期、基数量 | MANDT + STLTY + STLNR + STLAL + STKOZ | DATUV、ANDAT、AEDAT |
| BOM 组件 | V_SAP_HFFN_STPO | 20 行 / 139 列 | BOM 组件、组件物料、数量、项目类别、有效性 | MANDT + STLTY + STLNR + STLKN + STPOZ | DATUV、ANDAT、AEDAT |
| BOM 选择/替代 | V_SAP_HFFN_STAS | 20 行 / 21 列 | BOM 项目选择、替代、有效性 | MANDT + STLTY + STLNR + STLAL + STLKN + STASZ | DATUV、ANDAT、AEDAT |
| BOM 永久数据 | V_SAP_HFFN_STZU | 20 行 / 24 列 | BOM 辅助/永久属性 | MANDT + STLTY + STLNR + STLAN | HISDT、辅助变更字段需确认 |


## 3. 库存视图分析

`V_HF_SAP_INOUT_DAILY` 对应实时库存/结存快照。核心字段包括物料编码、物料描述、物料组、批次、现存量、结存数量、公司/工厂/库存地点、供应商、客户、库存日期、TS。建议 ODS 保留原始字段与 `raw_json`，DWD 统一到 `material_code/material_name/plant_code/storage_location/batch_no/on_hand_qty/balance_qty/uom/inventory_date`。

初步风险：库存视图是状态快照，不是流水；同步策略应按快照日期/TS 幂等覆盖，不能简单累加数量。

## 4. 出入库流水视图分析

`V_SAP_HFFN_CRKLSZ` 对应 ZMB51 物料移动明细。核心字段包括工厂、创建/过账日期、移动类型、单据号/单据行、物料、批次、入库数量、出库数量、采购订单、投产工单号、金额、采购申请部门等。建议 DWD 拆出 `movement_direction`，将入库数量/出库数量统一为带方向的 `movement_qty`，同时保留原始数量列用于追溯。

初步风险：移动类型与业务方向需要物管业务确认；同一单据可能存在冲销/退料，问数口径需明确是否净额化。

## 5. 采购执行视图分析

采购主题由 EBAN/EKKO/EKPO/EKET/EKBE 组成：

1. EBAN：采购申请，主键候选 BANFN+BNFPO。
2. EKKO：采购订单头，主键候选 MANDT+EBELN。
3. EKPO：采购订单行，主键候选 MANDT+EBELN+EBELP。
4. EKET：交货计划，主键候选 MANDT+EBELN+EBELP+ETENR。
5. EKBE：采购历史，到货/退货/发票流水，主键候选 MANDT+EBELN+EBELP+GJAHR+BELNR+BUZEI。

DWS 建议沉淀采购执行行宽表，指标包括下单数量、计划交货日期、已到货数量、未到货数量、延期天数、供应商、工厂、物料。

## 6. 工单组件视图分析

工单主题由 AFKO/AFPO/AUFK/RESB 组成。AFKO/AUFK 以 AUFNR 关联工单头与主数据；AFPO 描述产出物料/销售订单关联；RESB 描述组件预留和需求。问数优先基于 RESB + AFKO/AFPO/AUFK 形成 `dwd_mm_work_order_component`，再结合库存主题形成缺料分析。

初步风险：RESB 与 STPO 语义不同，RESB 更偏生产订单实际组件需求，STPO 更偏理论 BOM；问答中必须区分“工单实际需求”和“理论 BOM 组件”。

## 7. BOM 视图分析

SAP BOM 主题由 MAST/STKO/STPO/STAS/STZU 组成：MAST 负责物料与 BOM 分配，STKO 负责 BOM 头，STPO 负责组件行，STAS 负责项目选择/替代/有效性，STZU 负责辅助永久数据。后续应先形成 SAP BOM ODS，再转换到计划 BOM 标准模型，不应直接替换现有 Excel BOM 表。

## 8. 字段含义初步解释

1. SAP 标准编码字段：MATNR 物料、WERKS 工厂、LGORT 库存地点、CHARG 批次、EBELN/EBELP 采购订单/行、BANFN/BNFPO 采购申请/行、AUFNR 工单、RSNUM/RSPOS 预留、STLNR/STLAL/STLKN/STPOZ BOM 编号/替代/节点/项目。
2. 中文增强字段：物料描述、工厂名称、供应商名称、客户名称、移动类型描述等可直接用于前端展示和 LLM 润色，但查询主键不应依赖中文名称。
3. 时间字段：SAP 视图里同时存在 YYYYMMDD 字符串、DATE/TIMESTAMP 和业务日期字段，DWD 必须统一转换为 date/datetime 并保留 raw 值。

## 9. 主键/关联键初步判断

详见上方清单。通用原则：ODS 以 SAP 原始主键或业务联合键生成 `source_pk`；无法稳定判断时使用“关键业务字段 + source_view + source_hash”兜底。DWD/DWS 只消费 ODS 的稳定 `source_pk`，不直接依赖 Oracle ROWID。

## 10. 增量同步字段候选

1. 库存：TS、库存日期。
2. 出入库：过账日期、创建日期、过账时间。
3. 采购：ERDAT/AEDAT/BEDAT/EINDT/BUDAT 等，按视图分别确认。
4. 工单：ERDAT/AEDAT、计划开始/结束日期、需求日期 BDTER。
5. BOM：ANDAT/AEDAT/DATUV。

M2 前需要 Oracle 字段结构、count 和小样本抽验确认这些字段是否可用、是否有索引、是否支持跨天增量。

## 11. 数据质量问题

1. 多数视图字段 nullable，需要在 DWD 建立必填校验和异常隔离。
2. 部分中文字段长度很长（供应商/客户/特殊库存等），中间库 varchar 长度需保守设计或使用 text/raw_json 兜底。
3. SAP 日期存在字符串格式，必须处理空字符串、00000000、非法日期。
4. 库存快照与流水不可混算，必须区分存量指标和流量指标。
5. 采购/工单/BOM 视图字段数量较多，M2 不应一次性全建宽表，应按问数 MVP 先覆盖关键字段。

## 12. 当前缺失信息

1. Oracle live 连接未通过，未获取真实 count、执行计划、权限范围和字段 owner 复核。
2. 物管业务没有确认移动类型方向、库存结存口径、采购未到货计算口径、缺料风险阈值。
3. 未确认增量字段的稳定性和是否存在软删除/冲销标记。
4. 未确认前端最终菜单命名、同步管理权限边界。

## 13. 人工确认项

1. Oracle 驱动采用 `oracledb` thin 模式还是需要 instant client thick 模式。
2. MID schema/owner、白名单视图完整名称和只读账号权限。
3. M2 首批只做 `V_HF_SAP_INOUT_DAILY` 与 `V_SAP_HFFN_CRKLSZ` 是否满足业务优先级。
4. `source_type` 是否统一采用需求文档中的 `SAP_MID`；现有代码里计划 BOM 常量已有 `SAP`，需确认兼容命名。

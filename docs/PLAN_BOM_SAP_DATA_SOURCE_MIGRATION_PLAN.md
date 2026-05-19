
# 计划 BOM SAP 数据源改造方案（M1）

## 1. 当前 Excel BOM 数据源现状

现有计划 BOM 能力以 Excel 上传为主，已有导入批次、BOM 头、修订、材料行、查询、compare、QA 和功率模型相关能力。M1 不修改这些能力。

## 2. 当前 plan_bom 表结构理解

`plan_bom_import_batch`、`plan_bom_header`、`plan_bom_material_line` 已包含 `source_type`、`source_tag`、`import_batch_id`、`order_identity_key`、`file_instance_key` 等追溯/并存字段。材料行唯一键包含 `source_type`，具备多来源并存基础。

## 3. SAP BOM 视图关系

1. MAST：物料与 BOM 分配，连接 MATNR/WERKS/STLAN/STLNR/STLAL。
2. STKO：BOM 头，连接 STLNR/STLAL，有效日期 DATUV、基数量 BMENG。
3. STPO：BOM 组件明细，连接 STLNR/STLKN/STPOZ，组件物料 IDNRK。
4. STAS：项目选择/替代/有效性，连接 STLNR/STLAL/STLKN。
5. STZU：BOM 辅助属性，连接 STLNR/STLAN。

## 4. MAST/STKO/STPO/STAS/STZU 关系分析

标准链路：MATNR/WERKS/STLAN → MAST.STLNR/STLAL → STKO BOM 头 → STPO 组件行；STAS 用于选择有效组件；STZU 提供辅助属性。有效日期、删除标识和替代 BOM 需要业务确认后参与当前版本判定。

## 5. Excel BOM 与 SAP BOM 差异

Excel BOM 以订单/文件/版本/材料行为核心，字段更贴近计划 BOM 业务展示；SAP BOM 以物料、工厂、用途、BOM 编号、替代 BOM、有效期和组件节点为核心。Excel 有文件实例、修订说明和手动上传批次；SAP 有系统主键、有效性和替代项目。

## 6. 多数据源并存方案

需求文档要求并存：`source_type = EXCEL` 与 `source_type = SAP_MID`。现有代码常量已有 `SOURCE_TYPE_SAP = "SAP"`，建议 M2 人工确认后采用一种兼容策略：

1. 推荐：新增 `SOURCE_TYPE_SAP_MID = "SAP_MID"`，查询层将旧 `SAP` 作为兼容别名。
2. 或：沿用 `SAP`，但在展示层 source_tag 明确 `sap_mid`。该方案与需求文本不完全一致，不推荐。

## 7. source_type / source_tag 设计建议

- Excel：source_type=EXCEL，source_tag=manual_import_source。
- SAP MID：source_type=SAP_MID，source_tag=sap_mid_sync，import_batch_id=同步批次号。
- 所有查询响应展示“Excel 上传”或“SAP MID 同步”，不展示技术主键。

## 8. 标准 BOM 模型演进建议

先新增 SAP BOM ODS 表；再新增或扩展标准 DWD：`dwd_plan_bom_sap_header`、`dwd_plan_bom_sap_component`；最后将可兼容字段映射到现有 `plan_bom_header/material_line` 或统一查询视图。不要直接把 SAP 原始宽字段塞进现有材料行。

## 9. 如何不影响现有 BOM 查询

1. Excel 查询默认仍查 EXCEL active 数据。
2. 未显式选择 SAP_MID 时，不改变现有候选排序。
3. 所有 SAP 接入先 shadow，对比通过后再开放。
4. 回归测试覆盖现有 BOM QA、compare、上传、功率模型。

## 10. 如何不影响功率预测

功率预测现阶段依赖计划 BOM 标准材料和 active 功率模型。SAP BOM 接入不得恢复临时 token，不得改变功率模型激活权限；SAP BOM 映射到功率问答前必须经过材料类别归一、客户实例/单号消歧和业务验收。

## 11. 分阶段迁移路线

M1 文档方案；M2-M4 先完成物管库存/采购/工单；M5 单独实施 SAP BOM ODS/DWD、标准模型和查询兼容；M6 再增强问答体验和来源展示。

## 12. 风险和人工确认项

风险：SAP BOM 有效性语义复杂、替代 BOM/替代项目可能与 Excel 版本不一致、组件单位换算不明、source_type 命名需统一。人工确认：是否以 SAP_MID 作为正式枚举、当前版本判定规则、Excel/SAP 数据优先级。

## 13. 前端 BOM 来源展示方案

计划 BOM 结果中增加来源标签：Excel 上传 / SAP MID 同步；展示 BOM 生效日期、版本/替代、同步批次、来源主题。用户可筛选数据源，但默认不改变现有 Excel 查询体验。

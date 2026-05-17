
# 物管域智能助手中间库建模方案（M1）

## 1. ODS / DWD / DWS / DM 分层方案

1. ODS：按 SAP MID 视图一视图一表落地，保留原始字段、来源视图、同步批次、source_pk、source_hash、raw_json。只做最小类型转换和幂等控制。
2. DWD：按业务对象标准化，统一物料、工厂、库存地点、供应商、客户、采购单、工单、BOM 等字段命名和日期/数量单位。
3. DWS：面向问数主题形成可直接查询的宽表/汇总表，支持库存、出入库、采购执行、工单组件、缺料分析、SAP BOM 组件关系。
4. DM：面向高频问题和前端展示形成轻量结果表或物化汇总，例如库存排行、延期采购、缺料风险清单。

## 2. 表命名建议

ODS：
- `ods_mm_sap_inventory_snapshot` ← V_HF_SAP_INOUT_DAILY
- `ods_mm_sap_material_flow` ← V_SAP_HFFN_CRKLSZ
- `ods_mm_sap_purchase_requisition` ← V_SAP_HFFN_EBAN
- `ods_mm_sap_purchase_order_header` ← V_SAP_HFFN_EKKO
- `ods_mm_sap_purchase_order_line` ← V_SAP_HFFN_EKPO
- `ods_mm_sap_purchase_schedule` ← V_SAP_HFFN_EKET
- `ods_mm_sap_purchase_history` ← V_SAP_HFFN_EKBE
- `ods_mm_sap_work_order_header` ← V_SAP_HFFN_AFKO / AUFK 可拆表
- `ods_mm_sap_work_order_item` ← V_SAP_HFFN_AFPO
- `ods_mm_sap_reservation_component` ← V_SAP_HFFN_RESB
- `ods_plan_bom_sap_mast/stko/stpo/stas/stzu`

DWD/DWS/DM：
- `dwd_mm_inventory_balance`
- `dwd_mm_material_movement`
- `dwd_mm_purchase_execution_line`
- `dwd_mm_work_order_component`
- `dwd_mm_material_consumption`
- `dwd_plan_bom_sap_component`
- `dws_mm_inventory_current`
- `dws_mm_material_flow_daily`
- `dws_mm_purchase_delivery_status`
- `dws_mm_work_order_component_need`
- `dws_mm_shortage_risk`
- `dm_mm_inventory_rank`、`dm_mm_delayed_purchase`、`dm_mm_shortage_risk_rank`

## 3. 字段设计建议

通用字段：`id`、`source_system`、`source_view`、`source_type`、`source_pk`、`source_hash`、`sync_batch_no`、`sync_task_id`、`source_created_at`、`source_updated_at`、`raw_json`、`created_at`、`updated_at`。

业务字段应采用英文稳定名并保留中文展示名映射：
- 物料：`material_code`、`material_name`、`material_group_code`、`material_group_name`
- 组织：`company_code`、`company_name`、`plant_code`、`plant_name`、`storage_location`、`storage_location_name`
- 数量金额：`qty`、`in_qty`、`out_qty`、`balance_qty`、`amount_without_tax`、`amount_with_tax`、`currency`
- 日期：`biz_date`、`posting_date`、`create_date`、`delivery_date`、`need_date`、`inventory_date`
- 采购：`purchase_order_no`、`purchase_order_item`、`purchase_requisition_no`、`supplier_code`、`supplier_name`
- 工单：`work_order_no`、`component_material_code`、`required_qty`、`issued_qty`、`shortage_qty`
- BOM：`bom_no`、`bom_alt_no`、`bom_usage`、`bom_item_node`、`component_code`、`component_qty`、`effective_date`

## 4. 来源追溯字段

所有 DWD/DWS/DM 结果至少保留：`source_view`、`source_pk`、`sync_batch_no`、`source_row_count`、`source_ref`。前端展示时只展示业务化来源：来源主题、来源中间库表、同步批次、数据日期；不展示 Oracle 账号、DSN 或敏感连接信息。

## 5. 幂等字段

1. `source_pk`：优先 SAP 原主键/联合键。
2. `source_hash`：原视图关键字段 JSON 排序后哈希，用于无主键或变更检测。
3. ODS 唯一索引：`source_view + source_pk` 或 `source_view + source_hash`。
4. DWD 唯一索引：业务主键 + `source_type`，避免 SAP/Excel/历史数据互相覆盖。

## 6. 同步批次字段

复用/扩展 `sys_task_log`、`sys_task_error_log`、`sys_data_source`。同步批次字段建议包括：`task_id`、`task_type`、`biz_domain`、`business_topic`、`source_system`、`source_view`、`target_table`、`sync_mode`、`sync_batch_no`、`trigger_type`、`operator`、`read_count`、`insert_count`、`update_count`、`skip_count`、`error_count`。

## 7. 库存主题模型

`dwd_mm_inventory_balance` 保留每个物料/工厂/库存地点/批次/库存日期的快照。`dws_mm_inventory_current` 只保留当前可问数口径，支持查询某物料当前库存、库存为 0、库存不足、库存排行。

## 8. 出入库流水主题模型

`dwd_mm_material_movement` 以物料凭证行或单据号/单据行作为粒度，统一 `movement_direction`、`movement_qty`、`posting_date`、`movement_type`。支持物料流水、工单领料、退料、按时间汇总。

## 9. 采购执行主题模型

`dwd_mm_purchase_execution_line` 关联 EBAN/EKKO/EKPO/EKET/EKBE，形成采购订单行级执行状态。DWS 计算下单数量、计划交货数量、已到货数量、未到货数量、延期状态、供应商维度交付情况。

## 10. 工单组件主题模型

`dwd_mm_work_order_component` 以工单 + 组件物料 + 预留行为粒度，关联 AFKO/AFPO/AUFK/RESB。支持查询某工单组件、某物料被哪些工单需求、需求数量/已领数量/缺口数量。

## 11. 物料消耗主题模型

物料消耗由 `dwd_mm_material_movement` 中领料/退料移动类型沉淀，按工单、物料、工厂、日期聚合到 `dws_mm_material_consumption_daily`。移动类型净额化规则需业务确认后实现。

## 12. 缺料分析主题模型

`dws_mm_shortage_risk` 将工单组件需求与当前库存关联，计算 `shortage_qty = required_qty - issued_qty - available_qty`。MVP 只做静态缺口提示，不做复杂排产承诺。

## 13. 数据质量规则

1. 主键字段缺失进入异常表，不进入 DWD。
2. 日期无法解析时保留 raw 值并标记 quality_issue。
3. 数量字段统一 Decimal，单位不一致时先不强转，等待业务换算规则。
4. 删除/冲销/冻结标记进入状态字段，问数模板按业务口径过滤。
5. 每批同步输出质量统计和异常样例，不输出敏感连接信息。

## 14. 后续迁移建议

M2 只落地库存/出入库最小表和迁移；M3-M5 再分主题增加采购、工单、SAP BOM。每阶段先写 Alembic + ORM + repository + focused tests，再接同步和问数模板。

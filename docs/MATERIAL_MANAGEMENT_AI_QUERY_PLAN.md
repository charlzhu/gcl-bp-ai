
# 物管域智能问数链路设计（M1）

## 1. 总体链路

用户问题 → LLM 识别业务域/意图/参数 → 程序选择物管查询能力与 SQL 模板 → 查询智能助手中间库 → 返回结构化结果/查询条件/来源 → LLM 仅基于结果润色回答 → 前端展示自然语言、表格、条件、来源和状态。

## 2. 与物流问数链路的复用点

复用 `backend/app/domains/logistics/services/data_qa_service.py` 的“计划/执行/结果组装”思路，复用查询日志 `sys_query_log`、SQL 白名单、模板注册、StreamingResponse、前端流式展示与 ResultTable 组件模式。物管域应新建独立 `material_management` domain，不把逻辑混入物流。

## 3. 与计划 BOM 问答链路的复用点

复用计划 BOM 的候选确认、多数据源 `source_type/source_tag`、结果解释和 answer presentation 思路。SAP BOM 接入后仍通过标准中间库模型供现有 PlanBomQaService 逐步兼容。

## 4. 业务域识别

业务域候选：logistics、plan_bom、material_management、business_analysis。物管触发词包括库存、现存量、结存、出入库、移动类型、采购申请、采购订单、到货、未到货、工单、领料、退料、缺料、组件、预留。

## 5. 意图识别

首批意图：`inventory_current`、`inventory_zero`、`inventory_shortage`、`material_flow_recent`、`work_order_material_flow`、`purchase_delivery_status`、`delayed_purchase_orders`、`supplier_delivery_summary`、`work_order_components`、`material_required_by_orders`、`bom_components`。

## 6. 参数抽取

参数包括物料编码/名称、工厂、库存地点、批次、时间范围、移动类型、采购单号、采购申请号、供应商、工单号、BOM 编号/物料、是否延期、排行/TopN。缺少关键参数时返回业务化澄清，不暴露字段名或 SQL。

## 7. 字段字典

建立 `material_management` 字段字典，映射中文问法到标准字段：物料→material_code/material_name，工厂→plant_code/plant_name，库位→storage_location，库存→on_hand_qty/balance_qty，到货→received_qty，未到货→open_qty，工单→work_order_no，组件→component_material_code。

## 8. 业务口语词典

库存：现存量、库存量、结存、在库；出入库：流水、领料、退料、发料、入库；采购：采购单、PO、采购申请、未交、欠交、延期；工单：生产订单、工单、组件、预留、缺料。

## 9. SQL 模板设计

只允许预定义模板，例如按物料查库存、查最近流水、查采购未到货、查工单组件、查缺料风险。模板参数必须类型化校验，禁止 LLM 自由生成 SQL，禁止查询 Oracle MID。

## 10. 查询服务设计

建议目录：`backend/app/domains/material_management/services/`、`repositories/`、`schemas/`。Repository 只查中间库 DWD/DWS/DM；Service 负责意图分发、参数校验、空结果/澄清/不支持状态和结果解释。

## 11. 结果解释设计

回答必须业务化：说明查询口径、时间范围、关键结果、异常/空结果原因和来源批次。LLM 只基于结构化结果润色，不新增事实。

## 12. 来源追溯设计

响应元数据包含 source_topic、source_table、source_view、sync_batch_no、data_date、row_count。前端展示“数据来源：智能助手中间库，来源主题/批次/数据日期”，不展示 Oracle DSN。

## 13. 查询日志设计

`sys_query_log` 增加/复用 query_type、domain、route_type、metric_type、request_payload、result_count、status、message、trace_id。敏感参数脱敏。

## 14. 测试题集设计

M2 至少 5 个库存/出入库问题；M3 增加采购执行问题；M4 增加工单组件/缺料；M5 增加 SAP BOM；M6 增加趋势、排行、明细穿透和澄清/拒答边界题。

## 15. 不允许 LLM 自由生成 SQL

物管域第一阶段必须采用业务域识别 + 意图分类 + 参数抽取 + SQL 模板 + 白名单表字段 + 程序执行。LLM 不能生成任意 SQL，不能直接访问 SAP Oracle MID。

## 16. 前端问答结果数据结构设计

沿用现有流式 done payload：status、answer、presentation、result_table、query_conditions、source_trace、warnings、clarification。物管新增 result_type：inventory、material_flow、purchase_execution、work_order_component、shortage_risk、sap_bom。

## 17. 前端结构化结果展示建议

库存展示物料/工厂/库位/批次/当前库存/单位/库存日期；流水展示过账日期/移动类型/方向/数量/单据/工单/采购单；采购展示采购单/物料/供应商/下单/到货/未到货/交期/延期；工单展示工单/产品/组件/需求/已领/缺口。

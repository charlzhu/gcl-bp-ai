# 智能助手中间库附件结构摘要

## sys_task_log
- 附件: ai/inbox/attachments/middle_db/sys_task_log.xlsx
- 字段数: 0
- 字段:

## sys_task_error_log
- 附件: ai/inbox/attachments/middle_db/sys_task_error_log.xlsx
- 字段数: 0
- 字段:

## ods_logistic_ship_task
- 附件: ai/inbox/attachments/middle_db/Result_12.xlsx
- 字段数: 34
- 约束/索引:
  - PRIMARY KEY (`id`)
  - UNIQUE KEY `uk_sync_ship_task` (`sync_batch_no`,`source_id`)
  - UNIQUE KEY `uk_ods_ship_task_source_id` (`source_id`)
  - KEY `idx_task_id` (`task_id`)
  - KEY `idx_biz_date` (`biz_date`)
  - KEY `idx_status` (`status`)
- 字段:
  - id: bigint NOT NULL AUTO_INCREMENT
  - sync_batch_no: varchar(64) NOT NULL
  - source_id: bigint NOT NULL // 源系统主键
  - task_id: varchar(64) DEFAULT NULL
  - company_id: bigint DEFAULT NULL
  - project_name: varchar(255) DEFAULT NULL
  - pickup_date: date DEFAULT NULL
  - warehouse_id: bigint DEFAULT NULL
  - status: varchar(64) DEFAULT NULL
  - ship_type: varchar(32) DEFAULT NULL
  - expand_dept: varchar(128) DEFAULT NULL
  - entrusted_person: varchar(128) DEFAULT NULL
  - transport: varchar(64) DEFAULT NULL
  - contract_number: varchar(128) DEFAULT NULL
  - inquiry_number: varchar(128) DEFAULT NULL
  - bidding_number: varchar(128) DEFAULT NULL
  - shipping_instruction: varchar(128) DEFAULT NULL
  - rd_number: varchar(128) DEFAULT NULL
  - procurement_type: varchar(64) DEFAULT NULL
  - car_model: varchar(128) DEFAULT NULL
  - loading_trucks: decimal(18,4) DEFAULT NULL
  - delivery_province: varchar(64) DEFAULT NULL
  - delivery_city: varchar(64) DEFAULT NULL
  - delivery_area: varchar(64) DEFAULT NULL
  - delivery_distance: decimal(18,4) DEFAULT NULL
  - reconciliation_status: varchar(64) DEFAULT NULL
  - extra_cost_audited: varchar(32) DEFAULT NULL
  - base_code: varchar(32) DEFAULT NULL
  - del_flag: varchar(8) DEFAULT NULL
  - biz_date: date DEFAULT NULL
  - source_created_at: datetime DEFAULT NULL
  - source_updated_at: datetime DEFAULT NULL
  - raw_json: json DEFAULT NULL
  - created_at: datetime NOT NULL DEFAULT CURRENT_TIMESTAMP

## dwd_logistics_ship_task
- 附件: ai/inbox/attachments/middle_db/Result_12_2.xlsx
- 字段数: 38
- 约束/索引:
  - PRIMARY KEY (`id`)
  - UNIQUE KEY `uk_task_id` (`task_id`)
  - UNIQUE KEY `uk_dwd_ship_task_source_id` (`source_id`)
  - KEY `idx_biz_date` (`biz_date`)
  - KEY `idx_biz_year_month` (`biz_year`,`biz_month`)
  - KEY `idx_company_id` (`company_id`)
  - KEY `idx_status` (`status`)
- 字段:
  - id: bigint NOT NULL AUTO_INCREMENT
  - source_id: bigint NOT NULL
  - task_id: varchar(64) NOT NULL
  - company_id: bigint DEFAULT NULL
  - company_name: varchar(255) DEFAULT NULL
  - project_name: varchar(255) DEFAULT NULL
  - pickup_date: date DEFAULT NULL
  - warehouse_id: bigint DEFAULT NULL
  - warehouse_name: varchar(255) DEFAULT NULL
  - status: varchar(64) DEFAULT NULL
  - ship_type: varchar(32) DEFAULT NULL
  - expand_dept: varchar(128) DEFAULT NULL
  - entrusted_person: varchar(128) DEFAULT NULL
  - transport_mode: varchar(64) DEFAULT NULL
  - contract_no: varchar(128) DEFAULT NULL
  - inquiry_no: varchar(128) DEFAULT NULL
  - bidding_no: varchar(128) DEFAULT NULL
  - ship_instruction_no: varchar(128) DEFAULT NULL
  - rd_no: varchar(128) DEFAULT NULL
  - procurement_type: varchar(64) DEFAULT NULL
  - car_model: varchar(128) DEFAULT NULL
  - loading_trucks: decimal(18,4) DEFAULT NULL
  - delivery_province: varchar(64) DEFAULT NULL
  - delivery_city: varchar(64) DEFAULT NULL
  - delivery_area: varchar(64) DEFAULT NULL
  - normalized_region_name: varchar(32) DEFAULT NULL
  - region_resolve_source: varchar(32) DEFAULT NULL
  - delivery_distance: decimal(18,4) DEFAULT NULL
  - reconciliation_status: varchar(64) DEFAULT NULL
  - extra_cost_audited: varchar(32) DEFAULT NULL
  - base_code: varchar(32) DEFAULT NULL
  - del_flag: varchar(8) DEFAULT NULL
  - biz_date: date DEFAULT NULL
  - biz_year: int DEFAULT NULL
  - biz_month: varchar(16) DEFAULT NULL
  - is_formal_data: tinyint NOT NULL DEFAULT '1' // 仅保留2026+正式数据
  - created_at: datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
  - updated_at: datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP

## dws_logistics_detail_union
- 附件: ai/inbox/attachments/middle_db/Result_12_3.xlsx
- 字段数: 26
- 约束/索引:
  - PRIMARY KEY (`id`)
  - KEY `idx_biz_date` (`biz_date`)
  - KEY `idx_contract_no` (`contract_no`)
  - KEY `idx_inquiry_no` (`inquiry_no`)
  - KEY `idx_ship_instruction_no` (`ship_instruction_no`)
  - KEY `idx_sap_order_no` (`sap_order_no`)
  - KEY `idx_plate_number` (`plate_number`)
  - KEY `idx_task_id` (`task_id`)
- 字段:
  - id: bigint NOT NULL AUTO_INCREMENT
  - source_type: varchar(32) NOT NULL // HIST/SYS
  - biz_date: date DEFAULT NULL
  - biz_year: int DEFAULT NULL
  - biz_month: varchar(16) DEFAULT NULL
  - task_id: varchar(64) DEFAULT NULL
  - contract_no: varchar(128) DEFAULT NULL
  - inquiry_no: varchar(128) DEFAULT NULL
  - ship_instruction_no: varchar(128) DEFAULT NULL
  - sap_order_no: varchar(128) DEFAULT NULL
  - customer_name: varchar(255) DEFAULT NULL
  - logistics_company_name: varchar(255) DEFAULT NULL
  - warehouse_name: varchar(255) DEFAULT NULL
  - region_name: varchar(64) DEFAULT NULL
  - origin_place: varchar(128) DEFAULT NULL
  - transport_mode: varchar(64) DEFAULT NULL
  - plate_number: varchar(512) DEFAULT NULL
  - product_spec: varchar(128) DEFAULT NULL
  - product_power: decimal(18,4) DEFAULT NULL
  - shipment_count: decimal(18,4) DEFAULT NULL
  - shipment_watt: decimal(20,4) DEFAULT NULL
  - shipment_trip_count: decimal(18,4) DEFAULT NULL
  - total_fee: decimal(18,4) DEFAULT NULL
  - extra_fee: decimal(18,4) DEFAULT NULL
  - source_ref: varchar(128) DEFAULT NULL // 来源ID或复合主键
  - created_at: datetime NOT NULL DEFAULT CURRENT_TIMESTAMP

## dws_logistics_monthly_metric
- 附件: ai/inbox/attachments/middle_db/Result_12_4.xlsx
- 字段数: 18
- 约束/索引:
  - PRIMARY KEY (`id`)
  - KEY `idx_year_month` (`biz_year`,`biz_month`)
  - KEY `idx_company_month` (`logistics_company_name`,`biz_year`,`biz_month`)
  - KEY `idx_region_month` (`region_name`,`biz_year`,`biz_month`)
  - KEY `idx_warehouse_month` (`warehouse_name`,`biz_year`,`biz_month`)
- 字段:
  - id: bigint NOT NULL AUTO_INCREMENT
  - source_type: varchar(32) NOT NULL // HIST/SYS/MIXED
  - biz_year: int NOT NULL
  - biz_month: varchar(16) NOT NULL
  - customer_name: varchar(255) DEFAULT NULL
  - logistics_company_name: varchar(255) DEFAULT NULL
  - region_name: varchar(64) DEFAULT NULL
  - warehouse_name: varchar(255) DEFAULT NULL
  - transport_mode: varchar(64) DEFAULT NULL
  - origin_place: varchar(128) DEFAULT NULL
  - metric_type: varchar(32) NOT NULL DEFAULT 'WATT' // WATT/COUNT/TRIP/FEE
  - shipment_watt: decimal(20,4) DEFAULT '0.0000'
  - shipment_count: decimal(20,4) DEFAULT '0.0000'
  - shipment_trip_count: decimal(20,4) DEFAULT '0.0000'
  - total_fee: decimal(20,4) DEFAULT '0.0000'
  - extra_fee: decimal(20,4) DEFAULT '0.0000'
  - row_count: int DEFAULT '0'
  - created_at: datetime NOT NULL DEFAULT CURRENT_TIMESTAMP

## dm_logistics_company_month_rank
- 附件: ai/inbox/attachments/middle_db/Result_12_5.xlsx
- 字段数: 10
- 约束/索引:
  - PRIMARY KEY (`id`)
  - KEY `idx_year_month` (`biz_year`,`biz_month`)
  - KEY `idx_company` (`logistics_company_name`)
- 字段:
  - id: bigint NOT NULL AUTO_INCREMENT
  - biz_year: int NOT NULL
  - biz_month: varchar(16) NOT NULL
  - logistics_company_name: varchar(255) NOT NULL
  - shipment_watt: decimal(20,4) DEFAULT '0.0000'
  - shipment_trip_count: decimal(20,4) DEFAULT '0.0000'
  - total_fee: decimal(20,4) DEFAULT '0.0000'
  - rank_by_watt: int DEFAULT NULL
  - rank_by_fee: int DEFAULT NULL
  - created_at: datetime NOT NULL DEFAULT CURRENT_TIMESTAMP

## plan_bom_import_batch
- 附件: ai/inbox/attachments/middle_db/Result_13.xlsx
- 字段数: 12
- 约束/索引:
  - PRIMARY KEY (`batch_id`)
  - KEY `ix_plan_bom_import_batch_file_hash` (`file_hash`)
  - KEY `ix_plan_bom_import_batch_status` (`status`)
- 字段:
  - batch_id: varchar(64) COLLATE utf8mb4_general_ci NOT NULL // 导入批次号
  - source_type: varchar(32) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'EXCEL' // 数据来源类型，一期为 EXCEL，后续可扩展 SAP
  - source_tag: varchar(64) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'manual_import_source' // 来源标记，Excel 开发期固定为 manual_import_source
  - file_name: varchar(512) COLLATE utf8mb4_general_ci NOT NULL // 原始文件名
  - file_hash: varchar(128) COLLATE utf8mb4_general_ci DEFAULT NULL // 文件哈希，用于防重复导入
  - status: varchar(32) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'pending' // 导入批次状态
  - total_files: int NOT NULL DEFAULT '0' // 本批次文件数量
  - total_headers: int NOT NULL DEFAULT '0' // 解析出的 BOM 头数量
  - total_lines: int NOT NULL DEFAULT '0' // 解析出的材料行数量
  - error_message: text COLLATE utf8mb4_general_ci // 内部失败原因
  - created_at: datetime NOT NULL DEFAULT CURRENT_TIMESTAMP // 创建时间
  - finished_at: datetime DEFAULT NULL // 完成时间

## plan_bom_header
- 附件: ai/inbox/attachments/middle_db/Result_13_2.xlsx
- 字段数: 16
- 约束/索引:
  - PRIMARY KEY (`id`)
  - UNIQUE KEY `uk_plan_bom_header_identity_file_version_source` (`order_identity_key`,`file_instance_key`,`version_no`,`source_type`)
  - KEY `idx_plan_bom_header_order` (`order_no`)
  - KEY `idx_plan_bom_header_order_name` (`order_name`)
  - KEY `idx_plan_bom_header_effective` (`order_no`,`effective_date`)
  - KEY `ix_plan_bom_header_import_batch_id` (`import_batch_id`)
  - KEY `idx_plan_bom_header_identity` (`order_identity_key`)
  - KEY `idx_plan_bom_header_identity_version_source` (`order_identity_key`,`version_no`,`source_type`)
- 字段:
  - id: bigint NOT NULL AUTO_INCREMENT // 技术主键
  - order_no: varchar(128) COLLATE utf8mb4_general_ci NOT NULL // 订单号，评审号别名最终也查该字段
  - version_no: varchar(64) COLLATE utf8mb4_general_ci NOT NULL // 版本号，例如 A0、A1、A10
  - file_no: varchar(128) COLLATE utf8mb4_general_ci DEFAULT NULL // BOM 文件号
  - order_name: varchar(512) COLLATE utf8mb4_general_ci DEFAULT NULL // 订单名称，支持模糊查询
  - effective_date: date DEFAULT NULL // 生效日期，当前版本排序优先字段
  - source_type: varchar(32) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'EXCEL' // 来源类型
  - source_tag: varchar(64) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'manual_import_source' // 来源标记
  - import_batch_id: varchar(64) COLLATE utf8mb4_general_ci NOT NULL // 导入批次号
  - raw_file_name: varchar(512) COLLATE utf8mb4_general_ci DEFAULT NULL // 原始文件名
  - raw_sheet_name: varchar(128) COLLATE utf8mb4_general_ci DEFAULT NULL // 原始 sheet 名
  - is_active: smallint NOT NULL DEFAULT '1' // 是否当前有效记录，1 表示有效
  - created_at: datetime NOT NULL DEFAULT CURRENT_TIMESTAMP // 创建时间
  - updated_at: datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP // 更新时间
  - order_identity_key: varchar(64) COLLATE utf8mb4_general_ci NOT NULL
  - file_instance_key: varchar(64) COLLATE utf8mb4_general_ci NOT NULL

## plan_bom_revision
- 附件: ai/inbox/attachments/middle_db/Result_13_3.xlsx
- 字段数: 14
- 约束/索引:
  - PRIMARY KEY (`id`)
  - KEY `idx_plan_bom_revision_order` (`order_no`)
  - KEY `idx_plan_bom_revision_version` (`order_no`,`version_no`)
  - KEY `idx_plan_bom_revision_effective` (`order_no`,`effective_date`)
  - KEY `ix_plan_bom_revision_import_batch_id` (`import_batch_id`)
  - KEY `idx_plan_bom_revision_identity_version` (`order_identity_key`,`version_no`)
  - KEY `idx_plan_bom_revision_identity_file_version` (`order_identity_key`,`file_instance_key`,`version_no`)
- 字段:
  - id: bigint NOT NULL AUTO_INCREMENT // 技术主键
  - order_no: varchar(128) COLLATE utf8mb4_general_ci NOT NULL // 订单号
  - version_no: varchar(64) COLLATE utf8mb4_general_ci NOT NULL // 版本号
  - revision_version: varchar(64) COLLATE utf8mb4_general_ci DEFAULT NULL // 修订版本
  - revision_content: text COLLATE utf8mb4_general_ci // 修订内容
  - reviser: varchar(128) COLLATE utf8mb4_general_ci DEFAULT NULL // 修订人
  - effective_date: date DEFAULT NULL // 生效日期
  - source_type: varchar(32) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'EXCEL' // 来源类型
  - source_tag: varchar(64) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'manual_import_source' // 来源标记
  - import_batch_id: varchar(64) COLLATE utf8mb4_general_ci NOT NULL // 导入批次号
  - raw_row_no: int DEFAULT NULL // 原始 Excel 行号
  - created_at: datetime NOT NULL DEFAULT CURRENT_TIMESTAMP // 创建时间
  - order_identity_key: varchar(64) COLLATE utf8mb4_general_ci NOT NULL
  - file_instance_key: varchar(64) COLLATE utf8mb4_general_ci NOT NULL

## plan_bom_material_line
- 附件: ai/inbox/attachments/middle_db/Result_13_4.xlsx
- 字段数: 21
- 约束/索引:
  - PRIMARY KEY (`id`)
  - UNIQUE KEY `uk_plan_bom_line_identity_file_version_sap_source` (`order_identity_key`,`file_instance_key`,`version_no`,`sap_code`,`source_type`)
  - KEY `idx_plan_bom_line_order_version` (`order_no`,`version_no`)
  - KEY `idx_plan_bom_line_category` (`material_category`)
  - KEY `idx_plan_bom_line_sap` (`sap_code`)
  - KEY `ix_plan_bom_material_line_import_batch_id` (`import_batch_id`)
  - KEY `idx_plan_bom_line_identity_version` (`order_identity_key`,`version_no`)
  - KEY `idx_plan_bom_line_identity_file_version` (`order_identity_key`,`file_instance_key`,`version_no`)
- 字段:
  - id: bigint NOT NULL AUTO_INCREMENT // 技术主键
  - order_no: varchar(128) COLLATE utf8mb4_general_ci NOT NULL // 订单号
  - version_no: varchar(64) COLLATE utf8mb4_general_ci NOT NULL // 版本号
  - sap_code: varchar(128) COLLATE utf8mb4_general_ci NOT NULL // SAP 编码，材料行唯一键组成部分
  - line_no: varchar(64) COLLATE utf8mb4_general_ci DEFAULT NULL // Excel 原始序号，不作为稳定主键
  - material_name: varchar(256) COLLATE utf8mb4_general_ci NOT NULL // 原始物料名称
  - material_category: varchar(64) COLLATE utf8mb4_general_ci DEFAULT NULL // 系统材料归类
  - description: text COLLATE utf8mb4_general_ci // 原始规格描述
  - standard_usage: decimal(18,6) DEFAULT NULL // 标准用量
  - unit: varchar(64) COLLATE utf8mb4_general_ci DEFAULT NULL // 单位
  - production_loss: varchar(64) COLLATE utf8mb4_general_ci DEFAULT NULL // 生产损耗，保留原始文本
  - remark: text COLLATE utf8mb4_general_ci // 备注
  - replacement_marker: varchar(32) COLLATE utf8mb4_general_ci DEFAULT NULL // 明确替代标识，仅原样展示
  - source_type: varchar(32) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'EXCEL' // 来源类型
  - source_tag: varchar(64) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'manual_import_source' // 来源标记
  - import_batch_id: varchar(64) COLLATE utf8mb4_general_ci NOT NULL // 导入批次号
  - raw_row_no: int DEFAULT NULL // 原始 Excel 行号
  - created_at: datetime NOT NULL DEFAULT CURRENT_TIMESTAMP // 创建时间
  - updated_at: datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP // 更新时间
  - order_identity_key: varchar(64) COLLATE utf8mb4_general_ci NOT NULL
  - file_instance_key: varchar(64) COLLATE utf8mb4_general_ci NOT NULL

## plan_bom_export_task
- 附件: ai/inbox/attachments/middle_db/Result_13_5.xlsx
- 字段数: 13
- 约束/索引:
  - PRIMARY KEY (`export_id`)
  - KEY `idx_plan_bom_export_query_log` (`query_log_id`)
  - KEY `idx_plan_bom_export_status` (`status`)
  - KEY `ix_plan_bom_export_task_batch_id` (`batch_id`)
- 字段:
  - export_id: varchar(64) COLLATE utf8mb4_general_ci NOT NULL // 导出任务 ID
  - batch_id: varchar(64) COLLATE utf8mb4_general_ci NOT NULL // 导出批次号
  - query_log_id: bigint DEFAULT NULL // 关联 sys_query_log.id
  - query_type: varchar(64) COLLATE utf8mb4_general_ci NOT NULL // 导出对应的查询类型
  - export_format: varchar(16) COLLATE utf8mb4_general_ci NOT NULL // 导出格式，xlsx 或 csv
  - status: varchar(32) COLLATE utf8mb4_general_ci NOT NULL DEFAULT 'pending' // 导出任务状态
  - total_rows: int NOT NULL DEFAULT '0' // 导出总行数
  - part_total: int NOT NULL DEFAULT '0' // 总分段数
  - expires_at: datetime NOT NULL // 文件过期时间
  - error_message: text COLLATE utf8mb4_general_ci // 内部失败原因
  - user_message: varchar(256) COLLATE utf8mb4_general_ci DEFAULT NULL // 用户可见提示
  - created_at: datetime NOT NULL DEFAULT CURRENT_TIMESTAMP // 创建时间
  - updated_at: datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP // 更新时间

## Result_14
- 附件: ai/inbox/attachments/middle_db/Result_14.xlsx
- 字段数: 0
- 字段:

## logistics_ai_dm_logics_company_month_rank
- 附件: ai/inbox/attachments/middle_db/logistics_ai_dm_logics_company_month_rank.xlsx
- 字段数: 0
- 字段:

## logistics_ai_dwd_logistics_ship_task
- 附件: ai/inbox/attachments/middle_db/logistics_ai_dwd_logistics_ship_task.xlsx
- 字段数: 0
- 字段:

## logistics_ai_dws_logistics_detail_union
- 附件: ai/inbox/attachments/middle_db/logistics_ai_dws_logistics_detail_union.xlsx
- 字段数: 0
- 字段:

## logistics_ai_dws_logistics_monthly_metric
- 附件: ai/inbox/attachments/middle_db/logistics_ai_dws_logistics_monthly_metric.xlsx
- 字段数: 0
- 字段:

## logistics_ai_ods_logistic_ship_task
- 附件: ai/inbox/attachments/middle_db/logistics_ai_ods_logistic_ship_task.xlsx
- 字段数: 0
- 字段:

## logistics_ai_plan_bom_header
- 附件: ai/inbox/attachments/middle_db/logistics_ai_plan_bom_header.xlsx
- 字段数: 0
- 字段:

## logistics_ai_plan_bom_import_batch
- 附件: ai/inbox/attachments/middle_db/logistics_ai_plan_bom_import_batch.xlsx
- 字段数: 0
- 字段:

## logistics_ai_plan_bom_material_line
- 附件: ai/inbox/attachments/middle_db/logistics_ai_plan_bom_material_line.xlsx
- 字段数: 0
- 字段:

## logistics_ai_plan_bom_revision
- 附件: ai/inbox/attachments/middle_db/logistics_ai_plan_bom_revision.xlsx
- 字段数: 0
- 字段:

## logistics_ai_sys_query_log
- 附件: ai/inbox/attachments/middle_db/logistics_ai_sys_query_log.xlsx
- 字段数: 0
- 字段:

## sys_data_source
- 附件: ai/inbox/attachments/middle_db/sys_data_source.xlsx
- 字段数: 9
- 约束/索引:
  - PRIMARY KEY (`id`)
  - UNIQUE KEY `uk_source_code` (`source_code`)
- 字段:
  - id: bigint NOT NULL AUTO_INCREMENT
  - source_code: varchar(64) NOT NULL // 数据源编码
  - source_name: varchar(128) NOT NULL // 数据源名称
  - source_type: varchar(32) NOT NULL // EXCEL/MYSQL/API
  - biz_domain: varchar(64) NOT NULL // 业务域，如 logistics
  - source_desc: varchar(500) DEFAULT NULL
  - is_enabled: tinyint NOT NULL DEFAULT '1'
  - created_at: datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
  - updated_at: datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP

## sys_query_log
- 附件: ai/inbox/attachments/middle_db/sys_query_log.xlsx
- 字段数: 11
- 约束/索引:
  - PRIMARY KEY (`id`)
  - KEY `idx_trace_id` (`trace_id`)
  - KEY `idx_query_type` (`query_type`)
  - KEY `idx_created_at` (`created_at`)
- 字段:
  - id: bigint NOT NULL AUTO_INCREMENT
  - trace_id: varchar(64) NOT NULL
  - query_type: varchar(64) NOT NULL // METRICS/COMPARE/DETAIL/CHAT
  - question_text: text
  - request_payload: json DEFAULT NULL
  - route_type: varchar(64) DEFAULT NULL // HIST/SYS/MIXED
  - metric_type: varchar(64) DEFAULT NULL
  - result_count: int DEFAULT NULL
  - status: varchar(32) NOT NULL DEFAULT 'SUCCESS'
  - message: text
  - created_at: datetime NOT NULL DEFAULT CURRENT_TIMESTAMP

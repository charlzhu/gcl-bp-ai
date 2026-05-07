# 903 B->A 新增 A 行为回归

生成时间：2026-04-27T00:38:15

## 一、结论

本轮新增 A 行为回归共 `61` 条，通过 `61` 条，失败 `0` 条。

## 二、回归规则

- 真实调用当前物流 data-qa 主链路。
- 要求 query_key 命中预期。
- 要求状态码 OK、supported=true、needs_clarification=false。
- 要求结果表非空。

## 三、query_key 分布

- `hist_transport_mode_record_summary`：`7`
- `hist_product_spec_mw_summary`：`5`
- `sys_task_status_distribution`：`6`
- `sys_delivery_note_parse_status_distribution`：`5`
- `sys_avg_loading_trucks_by_province`：`5`
- `hist_remark_keyword_fee_ratio`：`1`
- `sys_task_status_province_ranking`：`2`
- `sys_procurement_task_distribution`：`1`
- `sys_reconciliation_fill_rate_by_month`：`1`
- `sys_ship_product_detail_stats`：`1`
- `sys_driver_task_ranking`：`1`
- `hist_mw_summary`：`6`
- `hist_unit_fee_per_watt`：`6`
- `hist_high_fee_addresses_by_customer`：`10`
- `sys_extra_fee_summary`：`4`

## 四、未通过题

- 当前无未通过题。

## 五、代表题

| 题号 | query_key | 问题 |
| --- | --- | --- |
| Q016 | hist_transport_mode_record_summary | 按运输方式统计，公路对应的发运记录数是多少？ |
| Q017 | hist_transport_mode_record_summary | 按运输方式统计，铁路对应的发运记录数是多少？ |
| Q018 | hist_transport_mode_record_summary | 按运输方式统计，水路对应的发运记录数是多少？ |
| Q019 | hist_transport_mode_record_summary | 按运输方式统计，汽运对应的发运记录数是多少？ |
| Q020 | hist_transport_mode_record_summary | 按运输方式统计，铁运对应的发运记录数是多少？ |
| Q021 | hist_product_spec_mw_summary | 规格为GCL-NT10/78GDF-640W的历史发运总瓦数是多少？ |
| Q022 | hist_product_spec_mw_summary | 规格为GCL-NT10/72GDF-590W的历史发运总瓦数是多少？ |
| Q023 | hist_product_spec_mw_summary | 规格为GCL-NT10/72GDF-585W的历史发运总瓦数是多少？ |
| Q024 | hist_product_spec_mw_summary | 规格为GCL-NT12R/66GDF-620W的历史发运总瓦数是多少？ |
| Q025 | hist_product_spec_mw_summary | 规格为GCL-NT12/66GDF-710W的历史发运总瓦数是多少？ |
| Q063 | sys_task_status_distribution | 2026年物流任务中状态为PREASSIGN的任务数量及占比是多少？ |
| Q064 | sys_task_status_distribution | 2026年物流任务中状态为ASSIGNED的任务数量及占比是多少？ |
| Q065 | sys_task_status_distribution | 2026年物流任务中状态为SIGNEDFOR的任务数量及占比是多少？ |
| Q066 | sys_task_status_distribution | 2026年物流任务中状态为PRESIGNFOR的任务数量及占比是多少？ |
| Q067 | sys_delivery_note_parse_status_distribution | 2026年派车任务中，回单解析状态为0的记录数量是多少？ |

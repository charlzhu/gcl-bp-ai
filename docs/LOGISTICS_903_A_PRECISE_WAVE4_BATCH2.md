# 903 A 类精确断言增强 Wave4 Batch2

生成时间：2026-04-27T11:21:19

## 一、覆盖统计

- 当前 A 总数：`652`
- 批次前已精确断言覆盖：`410`
- 批次前未覆盖 A：`242`
- 可直接进入精确断言候选：`242`

## 二、本批回归结论

- 本批题数：`30`
- 通过：`30`
- 失败：`0`
- query_key 分布：`{'hist_transport_mode_record_summary': 7, 'hist_unit_fee_per_watt': 6, 'hist_product_spec_mw_summary': 5, 'sys_task_status_distribution': 6, 'hist_high_fee_addresses_by_customer': 4, 'hist_mw_summary': 2}`

## 三、标准答案来源与断言口径

- 标准答案来源：当前 `logistics_ai` 数据快照，经正式 data-qa 主链路执行后固化。
- 断言字段：`status.code`、`query_plan.query_key`、`answer_summary`、`result_table.columns`、`result_table.rows`。
- 失败归因：query_key/status/columns 异常归为代码问题；answer_summary/rows 变化归为数据基线变化；预期 A 题进入澄清或不支持归为分层误判。

## 四、题目清单

| plan_id | 题号 | query_key | 问题 |
| --- | --- | --- | --- |
| A-W4-P2-001 | Q016 | hist_transport_mode_record_summary | 按运输方式统计，公路对应的发运记录数是多少？ |
| A-W4-P2-002 | Q017 | hist_transport_mode_record_summary | 按运输方式统计，铁路对应的发运记录数是多少？ |
| A-W4-P2-003 | Q018 | hist_transport_mode_record_summary | 按运输方式统计，水路对应的发运记录数是多少？ |
| A-W4-P2-004 | Q019 | hist_transport_mode_record_summary | 按运输方式统计，汽运对应的发运记录数是多少？ |
| A-W4-P2-005 | Q020 | hist_transport_mode_record_summary | 按运输方式统计，铁运对应的发运记录数是多少？ |
| A-W4-P2-006 | Q243 | hist_transport_mode_record_summary | 将“公路/汽运”口径统一后，2023-2025公路类运输的发运件数占比是多少？ |
| A-W4-P2-007 | Q259 | hist_transport_mode_record_summary | 历史台账中的水路记录有多少条？主要集中在哪些省份和月份？ |
| A-W4-P2-008 | SQ291 | hist_unit_fee_per_watt | 2024年公路运输的平均单瓦成本是多少？ |
| A-W4-P2-009 | SQ294 | hist_unit_fee_per_watt | 2024年铁路运输的平均单瓦成本是多少？ |
| A-W4-P2-010 | SQ297 | hist_unit_fee_per_watt | 2024年多式联运运输的平均单瓦成本是多少？ |
| A-W4-P2-011 | SQ300 | hist_unit_fee_per_watt | 2025年公路运输的平均单瓦成本是多少？ |
| A-W4-P2-012 | SQ303 | hist_unit_fee_per_watt | 2025年铁路运输的平均单瓦成本是多少？ |
| A-W4-P2-013 | SQ306 | hist_unit_fee_per_watt | 2025年多式联运运输的平均单瓦成本是多少？ |
| A-W4-P2-014 | Q021 | hist_product_spec_mw_summary | 规格为GCL-NT10/78GDF-640W的历史发运总瓦数是多少？ |
| A-W4-P2-015 | Q022 | hist_product_spec_mw_summary | 规格为GCL-NT10/72GDF-590W的历史发运总瓦数是多少？ |
| A-W4-P2-016 | Q023 | hist_product_spec_mw_summary | 规格为GCL-NT10/72GDF-585W的历史发运总瓦数是多少？ |
| A-W4-P2-017 | Q024 | hist_product_spec_mw_summary | 规格为GCL-NT12R/66GDF-620W的历史发运总瓦数是多少？ |
| A-W4-P2-018 | Q025 | hist_product_spec_mw_summary | 规格为GCL-NT12/66GDF-710W的历史发运总瓦数是多少？ |
| A-W4-P2-019 | Q063 | sys_task_status_distribution | 2026年物流任务中状态为PREASSIGN的任务数量及占比是多少？ |
| A-W4-P2-020 | Q064 | sys_task_status_distribution | 2026年物流任务中状态为ASSIGNED的任务数量及占比是多少？ |
| A-W4-P2-021 | Q065 | sys_task_status_distribution | 2026年物流任务中状态为SIGNEDFOR的任务数量及占比是多少？ |
| A-W4-P2-022 | Q066 | sys_task_status_distribution | 2026年物流任务中状态为PRESIGNFOR的任务数量及占比是多少？ |
| A-W4-P2-023 | Q262 | sys_task_status_distribution | 2026物流任务表中，各任务状态（PREASSIGN、ASSIGNED、PRESIGNFOR、SIGNEDFOR）的数量分别是多少？ |
| A-W4-P2-024 | Q271 | sys_task_status_distribution | 2026年派车任务表中，各状态（PREALLOCATE、ALLOCATED、ENTER、LEAVE）的数量分别是多少？ |
| A-W4-P2-025 | SQ478 | hist_high_fee_addresses_by_customer | 2025年客户创维客户发货的项目地中，哪些收货地址的运费超过20万元？ |
| A-W4-P2-026 | SQ480 | hist_high_fee_addresses_by_customer | 2025年客户海南创维新能源投资有限公司发货的项目地中，哪些收货地址的运费超过20万元？ |
| A-W4-P2-027 | SQ482 | hist_high_fee_addresses_by_customer | 2025年客户广东粤电阳西新能源有限公司发货的项目地中，哪些收货地址的运费超过20万元？ |
| A-W4-P2-028 | SQ484 | hist_high_fee_addresses_by_customer | 2025年客户华润新能源（皮山）有限公司发货的项目地中，哪些收货地址的运费超过20万元？ |
| A-W4-P2-029 | SQ289 | hist_mw_summary | 2024年公路运输的总发运量是多少MW？ |
| A-W4-P2-030 | SQ292 | hist_mw_summary | 2024年铁路运输的总发运量是多少MW？ |

## 五、未通过题

- 当前无未通过题。

# 903 A 类精确断言增强 Wave5 Batch3

生成时间：2026-04-27T11:21:18

## 一、覆盖统计

- 当前 A 总数：`656`
- 批次前已精确断言覆盖：`440`
- 批次前未覆盖 A：`216`
- 可直接进入精确断言候选：`216`

## 二、本批回归结论

- 本批题数：`40`
- 通过：`40`
- 失败：`0`
- query_key 分布：`{'hist_total_fee_summary': 4, 'hist_mw_summary': 4, 'sys_delivery_note_parse_status_distribution': 5, 'sys_avg_loading_trucks_by_province': 5, 'sys_extra_fee_summary': 4, 'sys_task_status_province_ranking': 2, 'hist_remark_keyword_fee_ratio': 1, 'sys_driver_task_ranking': 1, 'sys_procurement_task_distribution': 1, 'sys_reconciliation_fill_rate_by_month': 1, 'sys_ship_product_detail_stats': 1, 'hist_route_aggregate_summary': 11}`

## 三、标准答案来源与断言口径

- 标准答案来源：当前 `logistics_ai` 数据快照，经正式 data-qa 主链路执行后固化。
- 断言字段：`status.code`、`query_plan.query_key`、`answer_summary`、`result_table.columns`、`result_table.rows`。
- 失败归因：query_key/status/columns 异常归为代码问题；answer_summary/rows 变化归为数据基线变化；预期 A 题进入澄清或不支持归为分层误判。

## 四、题目清单

| plan_id | 题号 | query_key | 问题 |
| --- | --- | --- | --- |
| A-W5-P3-001 | SQ431 | hist_total_fee_summary | 2024年客户广东粤电阳西新能源有限公司总运费是多少？ |
| A-W5-P3-002 | SQ437 | hist_total_fee_summary | 2024年客户江苏苏美达电力运营有限公司总运费是多少？ |
| A-W5-P3-003 | SQ445 | hist_total_fee_summary | 2025年客户广东粤电阳西新能源有限公司总运费是多少？ |
| A-W5-P3-004 | SQ451 | hist_total_fee_summary | 2025年客户江苏苏美达电力运营有限公司总运费是多少？ |
| A-W5-P3-005 | SQ295 | hist_mw_summary | 2024年多式联运运输的总发运量是多少MW？ |
| A-W5-P3-006 | SQ298 | hist_mw_summary | 2025年公路运输的总发运量是多少MW？ |
| A-W5-P3-007 | SQ301 | hist_mw_summary | 2025年铁路运输的总发运量是多少MW？ |
| A-W5-P3-008 | SQ304 | hist_mw_summary | 2025年多式联运运输的总发运量是多少MW？ |
| A-W5-P3-009 | Q067 | sys_delivery_note_parse_status_distribution | 2026年派车任务中，回单解析状态为0的记录数量是多少？ |
| A-W5-P3-010 | Q068 | sys_delivery_note_parse_status_distribution | 2026年派车任务中，回单解析状态为1的记录数量是多少？ |
| A-W5-P3-011 | Q069 | sys_delivery_note_parse_status_distribution | 2026年派车任务中，回单解析状态为3的记录数量是多少？ |
| A-W5-P3-012 | Q070 | sys_delivery_note_parse_status_distribution | 2026年派车任务中，回单解析状态为4的记录数量是多少？ |
| A-W5-P3-013 | Q274 | sys_delivery_note_parse_status_distribution | 2026年派车任务的送货单解析状态分布（0/1/3/4）分别是多少？ |
| A-W5-P3-014 | Q071 | sys_avg_loading_trucks_by_province | 2026年送达省份为江苏省的任务中，平均装车数（loading_trucks）是多少？ |
| A-W5-P3-015 | Q072 | sys_avg_loading_trucks_by_province | 2026年送达省份为安徽省的任务中，平均装车数（loading_trucks）是多少？ |
| A-W5-P3-016 | Q073 | sys_avg_loading_trucks_by_province | 2026年送达省份为云南省的任务中，平均装车数（loading_trucks）是多少？ |
| A-W5-P3-017 | Q074 | sys_avg_loading_trucks_by_province | 2026年送达省份为浙江省的任务中，平均装车数（loading_trucks）是多少？ |
| A-W5-P3-018 | Q075 | sys_avg_loading_trucks_by_province | 2026年送达省份为四川省的任务中，平均装车数（loading_trucks）是多少？ |
| A-W5-P3-019 | SQ540 | sys_extra_fee_summary | 2026年1月份合肥基地额外费用总额是多少？ |
| A-W5-P3-020 | SQ543 | sys_extra_fee_summary | 2026年2月份合肥基地额外费用总额是多少？ |
| A-W5-P3-021 | SQ546 | sys_extra_fee_summary | 2026年1月份阜宁基地额外费用总额是多少？ |
| A-W5-P3-022 | SQ549 | sys_extra_fee_summary | 2026年2月份阜宁基地额外费用总额是多少？ |
| A-W5-P3-023 | Q264 | sys_task_status_province_ranking | 2026年各送达省份中，PREASSIGN待派车任务最多的是哪些省份？ |
| A-W5-P3-024 | SQ583 | sys_task_status_province_ranking | 2026年哪些省份的PREASSIGN待派车任务最多？ |
| A-W5-P3-025 | Q258 | hist_remark_keyword_fee_ratio | 备注中包含“倒运”或“中转”的记录，其总费用占历史物流总费用的比例是多少？ |
| A-W5-P3-026 | Q306 | sys_driver_task_ranking | 2026年派车任务量最高的前20位司机是谁？ |
| A-W5-P3-027 | Q265 | sys_procurement_task_distribution | 2026年有采购方式标记的任务中，询比价与招标的任务量分别是多少？占比多少？ |
| A-W5-P3-028 | Q281 | sys_reconciliation_fill_rate_by_month | 2026年各月份的reconciliation_status填充率分别是多少？ |
| A-W5-P3-029 | Q288 | sys_ship_product_detail_stats | 2026年平均每个物流任务包含多少条ship_product明细？明细数最高的任务是哪几个？ |
| A-W5-P3-030 | SQ181 | hist_route_aggregate_summary | 2023年合肥基地发往江苏省的平均运费是多少？ |
| A-W5-P3-031 | SQ182 | hist_route_aggregate_summary | 2023年合肥基地发往江苏省的总发运量是多少MW？ |
| A-W5-P3-032 | SQ183 | hist_route_aggregate_summary | 2023年合肥基地发往浙江省的平均运费是多少？ |
| A-W5-P3-033 | SQ184 | hist_route_aggregate_summary | 2023年合肥基地发往浙江省的总发运量是多少MW？ |
| A-W5-P3-034 | SQ185 | hist_route_aggregate_summary | 2023年合肥基地发往上海市的平均运费是多少？ |
| A-W5-P3-035 | SQ186 | hist_route_aggregate_summary | 2023年合肥基地发往上海市的总发运量是多少MW？ |
| A-W5-P3-036 | SQ187 | hist_route_aggregate_summary | 2023年合肥基地发往安徽省的平均运费是多少？ |
| A-W5-P3-037 | SQ188 | hist_route_aggregate_summary | 2023年合肥基地发往安徽省的总发运量是多少MW？ |
| A-W5-P3-038 | SQ189 | hist_route_aggregate_summary | 2023年合肥基地发往广东省的平均运费是多少？ |
| A-W5-P3-039 | SQ190 | hist_route_aggregate_summary | 2023年合肥基地发往广东省的总发运量是多少MW？ |
| A-W5-P3-040 | SQ191 | hist_route_aggregate_summary | 2023年合肥基地发往广西壮族自治区的平均运费是多少？ |

## 五、未通过题

- 当前无未通过题。

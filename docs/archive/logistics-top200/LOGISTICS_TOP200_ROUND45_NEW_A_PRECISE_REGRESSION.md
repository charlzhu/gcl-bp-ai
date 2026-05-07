# Round4 / Round5 新进 A 题精确断言回归

## 结论

当前 Round4 / Round5 新进 A 题共 **5** 条，精确断言回归结果为：通过 **5** 条，失败 **0** 条。

## 题目清单

| 回归编号 | 来源轮次 | 题号 | query_key | 标准答案来源 | 断言口径 | 断言字段 |
| --- | --- | --- | --- | --- | --- | --- |
| R45A001 | Round4 | RAW052 | sys_total_fee_by_filters | logistics_ai 当前主链路快照（2026系统口径，2026-04-23） | 2026系统总运费精确断言 | status.code；query_plan.query_key；answer_summary；result_table.rows[0].total_fee；result_table.rows[0].task_count |
| R45A002 | Round4 | RAW056 | sys_total_fee_by_filters | logistics_ai 当前主链路快照（2026系统口径，2026-04-23） | 2026系统总运费精确断言 | status.code；query_plan.query_key；answer_summary；result_table.rows[0].total_fee；result_table.rows[0].task_count |
| R45A003 | Round5 | RAW057 | sys_unit_fee_per_watt | logistics_ai 当前主链路快照（2026系统口径，2026-04-23） | 2026系统单瓦运输成本精确断言 | status.code；query_plan.query_key；answer_summary；result_table.rows[0].total_fee；result_table.rows[0].extra_fee_amount；result_table.rows[0].shipment_mw；result_table.rows[0].unit_fee_per_watt |
| R45A004 | Round5 | RAW011 | sys_mw_and_trip_count | logistics_ai 当前主链路快照（2026系统口径，2026-04-23） | 2026截至目前累计运量综合精确断言 | status.code；query_plan.query_key；answer_summary；result_table.rows[0].shipment_mw；result_table.rows[0].shipment_trip_count |
| R45A005 | Round5 | RAW025 | hist_route_pricing_analysis | logistics_ai 当前主链路快照（2023-2025历史口径，2026-04-23） | 2023-2025历史累计平均运费精确断言 | status.code；query_plan.query_key；answer_summary；result_table.rows[0].avg_fee；result_table.rows[0].row_count |

## 失败归因规则

- `代码问题`：query_key 错误、误入澄清/不支持、状态码异常、执行异常。
- `数据基线变化`：链路执行成功，但 answer_summary 或关键结果字段与当前精确断言基线不一致。

## 当前未通过题

- 当前无未通过题。

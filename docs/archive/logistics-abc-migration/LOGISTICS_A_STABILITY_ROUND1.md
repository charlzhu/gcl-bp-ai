# A-稳定增强池 Round1 精确断言回归

## 结论

当前 A-稳定增强池 Round1 共纳管 **39** 条 P1 高价值 A 题，精确断言回归结果为：通过 **39** 条，失败 **0** 条。

## 选题规则

- 当前已进入 A；当前优先级为 P1；已在 Top200；但尚未纳入历史既有精确断言。

## 题目清单

| 回归编号 | 题号 | 优先级 | query_key | 断言口径 | 断言字段 |
| --- | --- | --- | --- | --- | --- |
| ASTABR1-001 | Q008 | P1 | hist_total_fee_by_province | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-002 | Q047 | P1 | hist_top_customers_fee_and_mw_by_province | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-003 | Q048 | P1 | hist_top_customers_fee_and_mw_by_province | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-004 | Q049 | P1 | hist_top_customers_fee_and_mw_by_province | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-005 | Q050 | P1 | hist_top_customers_fee_and_mw_by_province | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-006 | Q051 | P1 | hist_top_customers_fee_and_mw_by_province | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-007 | Q052 | P1 | hist_top_customers_fee_and_mw_by_province | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-008 | Q053 | P1 | hist_top_customers_fee_and_mw_by_province | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-009 | Q054 | P1 | hist_top_customers_fee_and_mw_by_province | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-010 | Q256 | P1 | hist_customer_mw_ranking | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-011 | Q267 | P1 | sys_delivery_distance_fill_rate_by_province | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-012 | Q268 | P1 | sys_task_count_ranking | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-013 | Q275 | P1 | sys_parse_success_rate_by_carrier | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-014 | Q280 | P1 | sys_extra_cost_audited_concentration | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-015 | Q287 | P1 | sys_company_mapping_gap | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-016 | SQ002 | P1 | hist_quantity_by_region | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-017 | SQ006 | P1 | hist_quantity_by_region | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-018 | SQ010 | P1 | hist_quantity_by_region | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-019 | SQ014 | P1 | hist_quantity_by_region | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-020 | SQ018 | P1 | hist_quantity_by_region | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-021 | SQ022 | P1 | hist_quantity_by_region | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-022 | SQ026 | P1 | hist_quantity_by_region | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-023 | SQ030 | P1 | hist_quantity_by_region | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-024 | SQ034 | P1 | hist_quantity_by_region | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-025 | SQ038 | P1 | hist_quantity_by_region | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-026 | SQ042 | P1 | hist_quantity_by_region | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-027 | SQ046 | P1 | hist_quantity_by_region | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-028 | SQ518 | P1 | carrier_metric_ranking | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-029 | SQ528 | P1 | sys_unit_fee_per_watt | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-030 | SQ570 | P1 | sys_total_fee_by_filters | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-031 | RAW012 | P1 | hist_carrier_kpi_by_year | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-032 | RAW013 | P1 | hist_carrier_kpi_by_year | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-033 | RAW029 | P1 | hist_route_pricing_analysis | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-034 | RAW036 | P1 | sys_mw_by_procurement_type | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-035 | RAW043 | P1 | sys_special_total_fee | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-036 | RAW044 | P1 | sys_mw_and_trip_count | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-037 | RAW045 | P1 | sys_special_total_fee | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-038 | RAW066 | P1 | sys_mw_and_trip_count | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR1-039 | RAW067 | P1 | hist_vehicle_type_trip_count | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |

## 失败归因规则

- `代码问题`：query_key 错误、状态码异常、结果结构变化、执行异常。
- `数据基线变化`：answer_summary 或 result_table.rows 与当前精确断言基线不一致。

## 当前未通过题

- 当前无未通过题。

## 当前边界

- 这轮只把已进入 A 的高价值题纳入更严格精确断言，不扩新 query_key。
- 20 条关键题、75 条 A 类行为回归、Round4/5 新进 A 的 5 条精确断言都必须继续保持不回退。

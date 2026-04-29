# A-稳定增强池 Round2 精确断言回归

## 结论

当前 A-稳定增强池 Round2 共纳管 **34** 条 P2 高价值 A 题，精确断言回归结果为：通过 **34** 条，失败 **0** 条。

## 选题规则

- 当前已进入 A；当前优先级为 P2；已在 Top200；但尚未纳入更严格精确断言。

## 题目清单

| 回归编号 | 题号 | 优先级 | query_key | 断言口径 | 断言字段 |
| --- | --- | --- | --- | --- | --- |
| ASTABR2-001 | Q055 | P2 | hist_city_carrier_avg_fee_per_trip | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-002 | Q056 | P2 | hist_city_carrier_avg_fee_per_trip | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-003 | Q057 | P2 | hist_city_carrier_avg_fee_per_trip | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-004 | Q058 | P2 | hist_city_carrier_avg_fee_per_trip | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-005 | Q059 | P2 | hist_city_carrier_avg_fee_per_trip | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-006 | SQ050 | P2 | hist_quantity_by_region | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-007 | SQ054 | P2 | hist_quantity_by_region | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-008 | SQ058 | P2 | hist_quantity_by_region | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-009 | SQ062 | P2 | hist_quantity_by_region | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-010 | SQ066 | P2 | hist_quantity_by_region | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-011 | SQ522 | P2 | carrier_metric_ranking | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-012 | RAW004 | P2 | hist_mw_summary | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-013 | RAW005 | P2 | hist_mw_summary | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-014 | RAW007 | P2 | hist_mw_by_region_province | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-015 | RAW009 | P2 | sys_mw_and_trip_count | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-016 | RAW014 | P2 | hist_carrier_kpi_by_year | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-017 | RAW018 | P2 | hist_carrier_kpi_by_year | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-018 | RAW019 | P2 | hist_carrier_kpi_by_year | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-019 | RAW022 | P2 | hist_carrier_kpi_by_year | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-020 | RAW026 | P2 | hist_mw_by_all_regions | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-021 | RAW028 | P2 | hist_monthly_total_fee_by_year | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-022 | RAW031 | P2 | hist_carrier_kpi_by_year | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-023 | RAW035 | P2 | hist_customer_mw | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-024 | RAW037 | P2 | hist_mw_by_origin_and_carrier | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-025 | RAW040 | P2 | hist_mw_summary | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-026 | RAW041 | P2 | hist_customer_mw | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-027 | RAW042 | P2 | sys_special_total_fee | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-028 | RAW048 | P2 | hist_unit_fee_per_watt | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-029 | RAW051 | P2 | sys_total_fee_by_filters | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-030 | RAW058 | P2 | sys_mw_and_trip_count | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-031 | RAW059 | P2 | sys_mw_and_trip_count | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-032 | RAW069 | P2 | hist_mw_by_region_province | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-033 | RAW070 | P2 | hist_mw_summary | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR2-034 | RAW071 | P2 | hist_mw_by_region_province | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |

## 失败归因规则

- `代码问题`：query_key 错误、状态码异常、结果结构变化、执行异常。
- `数据基线变化`：answer_summary 或 result_table.rows 与当前精确断言基线不一致。

## 当前未通过题

- 当前无未通过题。

## 当前边界

- 这轮仍然只做已进入 A 的高价值题精确断言，不扩新 query_key。
- 下一步如继续推进，应优先进入 A-稳定增强池 Round3，而不是回头扩 Top200/TopN 名单。

# A-稳定增强池 Round3 精确断言回归

## 结论

当前 A-稳定增强池 Round3 共纳管 **33** 条 P3 高价值 A 题，精确断言回归结果为：通过 **33** 条，失败 **0** 条。

## 选题规则

- 当前已进入 A；当前优先级为 P3；已在 Top200；但尚未纳入更严格精确断言。

## 题目清单

| 回归编号 | 题号 | 优先级 | query_key | 断言口径 | 断言字段 |
| --- | --- | --- | --- | --- | --- |
| ASTABR3-001 | Q009 | P3 | hist_total_fee_by_province | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-002 | Q010 | P3 | hist_total_fee_by_province | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-003 | Q011 | P3 | hist_total_fee_by_province | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-004 | Q012 | P3 | hist_total_fee_by_province | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-005 | Q013 | P3 | hist_total_fee_by_province | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-006 | Q014 | P3 | hist_total_fee_by_province | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-007 | Q015 | P3 | hist_total_fee_by_province | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-008 | Q269 | P3 | sys_task_count_ranking | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-009 | SQ515 | P3 | carrier_metric_ranking | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-010 | SQ516 | P3 | carrier_metric_ranking | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-011 | SQ519 | P3 | carrier_metric_ranking | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-012 | SQ521 | P3 | carrier_metric_ranking | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-013 | SQ532 | P3 | sys_unit_fee_per_watt | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-014 | SQ562 | P3 | sys_total_fee_by_filters | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-015 | SQ564 | P3 | sys_total_fee_by_filters | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-016 | SQ566 | P3 | sys_total_fee_by_filters | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-017 | SQ568 | P3 | sys_total_fee_by_filters | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-018 | SQ572 | P3 | sys_total_fee_by_filters | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-019 | RAW003 | P3 | hist_vehicle_type_trip_count | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-020 | RAW016 | P3 | hist_carrier_kpi_by_year | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-021 | RAW017 | P3 | hist_carrier_kpi_by_year | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-022 | RAW020 | P3 | hist_carrier_kpi_by_year | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-023 | RAW021 | P3 | hist_carrier_kpi_by_year | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-024 | RAW023 | P3 | hist_carrier_kpi_by_year | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-025 | RAW024 | P3 | hist_carrier_kpi_by_year | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-026 | RAW027 | P3 | hist_mw_summary | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-027 | RAW039 | P3 | hist_vehicle_type_trip_count | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-028 | RAW047 | P3 | hist_route_pricing_analysis | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-029 | RAW053 | P3 | hist_route_pricing_analysis | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-030 | RAW061 | P3 | hist_route_pricing_analysis | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-031 | RAW063 | P3 | hist_route_pricing_analysis | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-032 | RAW072 | P3 | hist_carrier_kpi_by_year | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |
| ASTABR3-033 | RAW073 | P3 | hist_carrier_kpi_by_year | answer_summary + result_table.columns + result_table.rows 精确快照断言 | answer_summary；result_table.columns；result_table.rows |

## 失败归因规则

- `代码问题`：query_key 错误、状态码异常、结果结构变化、执行异常。
- `数据基线变化`：answer_summary 或 result_table.rows 与当前精确断言基线不一致。

## 当前未通过题

- 当前无未通过题。

## 当前边界

- 这轮把 A-稳定增强池剩余 Top200 题全部纳入更严格精确断言，作为当前 A 池收尾批。
- 后续若继续推进，应优先处理非 Top200 的 A 池长尾题，或转入项目级文档同步。

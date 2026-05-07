# B2A-P1 B->A 新进 A 精确断言回归

## 一、结论

B2A-P1 共纳管 **25** 条 B->A 新迁入 A 题，精确断言回归通过 **25** 条，失败 **0** 条。

## 二、标准答案来源与断言口径

- 标准答案来源：当前 `logistics_ai` 数据快照，经正式 data-qa 主链路执行后固化。
- 断言字段：`status.code`、`query_plan.query_key`、`answer_summary`、`result_table.columns`、`result_table.rows`。
- 失败归因：query_key/status/columns 异常归为代码问题；answer_summary/rows 变化归为数据基线变化；预期 A 题实际进入 clarification/unsupported 时归为题目分层误判。

## 三、题目清单

| plan_id | 题号 | query_key | 断言字段 | 问题 |
| --- | --- | --- | --- | --- |
| B2A-PREC-001 | SQ550 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1月份运输方式为铁路的运输总量是多少MW？ |
| B2A-PREC-002 | SQ556 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1月份运输方式为公路的运输总量是多少MW？ |
| B2A-PREC-003 | SQ558 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年2月份运输方式为公路的运输总量是多少MW？ |
| B2A-PREC-004 | SQ539 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1月份合肥基地总运费是多少？ |
| B2A-PREC-005 | SQ542 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年2月份合肥基地总运费是多少？ |
| B2A-PREC-006 | SQ545 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1月份阜宁基地总运费是多少？ |
| B2A-PREC-007 | SQ548 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年2月份阜宁基地总运费是多少？ |
| B2A-PREC-008 | SQ003 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2023年华东区域总运费是多少？ |
| B2A-PREC-009 | SQ007 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2023年华南区域总运费是多少？ |
| B2A-PREC-010 | SQ011 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2023年华中区域总运费是多少？ |
| B2A-PREC-011 | SQ015 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2023年华北区域总运费是多少？ |
| B2A-PREC-012 | SQ019 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2023年西南区域总运费是多少？ |
| B2A-PREC-013 | SQ023 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2023年西北区域总运费是多少？ |
| B2A-PREC-014 | SQ027 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年华东区域总运费是多少？ |
| B2A-PREC-015 | SQ031 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年华南区域总运费是多少？ |
| B2A-PREC-016 | SQ035 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年华中区域总运费是多少？ |
| B2A-PREC-017 | SQ039 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年华北区域总运费是多少？ |
| B2A-PREC-018 | SQ043 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年西南区域总运费是多少？ |
| B2A-PREC-019 | SQ047 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年西北区域总运费是多少？ |
| B2A-PREC-020 | SQ051 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年华东区域总运费是多少？ |
| B2A-PREC-021 | SQ055 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年华南区域总运费是多少？ |
| B2A-PREC-022 | SQ059 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年华中区域总运费是多少？ |
| B2A-PREC-023 | SQ063 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年华北区域总运费是多少？ |
| B2A-PREC-024 | SQ067 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年西南区域总运费是多少？ |
| B2A-PREC-025 | SQ071 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年西北区域总运费是多少？ |

## 四、未通过题

- 当前无未通过题。

## 五、边界

- 本轮只固化 B2A-P1 已通过精确断言的新进 A 题，不扩 B/C 边界。
- 未通过题不得纳入稳定精确基线，需回到总账迁移复核。
- B/C 边界仍由规则层主导，不受本轮精确断言影响。

# C2A-P1 新进 A 精确断言回归

## 一、结论

C2A-P1 共纳管 **30** 条新迁入 A 题，精确断言回归通过 **30** 条，失败 **0** 条。

## 二、标准答案来源与断言口径

- 标准答案来源：当前 `logistics_ai` 数据快照，经正式 data-qa 主链路执行后固化。
- 断言字段：`status.code`、`query_plan.query_key`、`answer_summary`、`result_table.columns`、`result_table.rows`。
- 失败归因：query_key/status/columns 异常归为代码问题；answer_summary/rows 变化归为数据基线变化；预期 A 题实际进入 clarification/unsupported 时归为题目分层误判。

## 三、题目清单

| plan_id | 题号 | query_key | 断言字段 | 问题 |
| --- | --- | --- | --- | --- |
| C2A-PREC-001 | SQ307 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月公路运输的总发运量是多少MW？ |
| C2A-PREC-002 | SQ310 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月铁路运输的总发运量是多少MW？ |
| C2A-PREC-003 | SQ313 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月多式联运运输的总发运量是多少MW？ |
| C2A-PREC-004 | SQ452 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月客户华阳总发运量是多少MW？ |
| C2A-PREC-005 | SQ454 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月客户创维客户总发运量是多少MW？ |
| C2A-PREC-006 | SQ456 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月客户海南创维新能源投资有限公司总发运量是多少MW？ |
| C2A-PREC-007 | SQ458 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月客户广东粤电阳西新能源有限公司总发运量是多少MW？ |
| C2A-PREC-008 | SQ460 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月客户华润新能源（皮山）有限公司总发运量是多少MW？ |
| C2A-PREC-009 | SQ462 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月客户国科新能源有限公司总发运量是多少MW？ |
| C2A-PREC-010 | SQ464 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月客户江苏苏美达电力运营有限公司总发运量是多少MW？ |
| C2A-PREC-011 | SQ504 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月经营计划场景下的总发运量是多少？ |
| C2A-PREC-012 | SQ507 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月辅料送样场景下的总发运量是多少？ |
| C2A-PREC-013 | SQ520 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月各承运商按发运量排名前十分别是谁？ |
| C2A-PREC-014 | SQ538 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1月份合肥基地总发运量是多少MW？ |
| C2A-PREC-015 | SQ541 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年2月份合肥基地总发运量是多少MW？ |
| C2A-PREC-016 | SQ544 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1月份阜宁基地总发运量是多少MW？ |
| C2A-PREC-017 | SQ547 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年2月份阜宁基地总发运量是多少MW？ |
| C2A-PREC-018 | SQ563 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1月份晶茂物流总发运量是多少MW？ |
| C2A-PREC-019 | SQ565 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年2月份晶茂物流总发运量是多少MW？ |
| C2A-PREC-020 | SQ567 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1月份苏州晶茂物流总发运量是多少MW？ |
| C2A-PREC-021 | SQ569 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年2月份苏州晶茂物流总发运量是多少MW？ |
| C2A-PREC-022 | SQ571 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1月份英赋嘉总发运量是多少MW？ |
| C2A-PREC-023 | SQ573 | sys_mw_and_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年2月份英赋嘉总发运量是多少MW？ |
| C2A-PREC-024 | SQ308 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月公路运输的总运费是多少？ |
| C2A-PREC-025 | SQ311 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月铁路运输的总运费是多少？ |
| C2A-PREC-026 | SQ314 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月多式联运运输的总运费是多少？ |
| C2A-PREC-027 | SQ453 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月客户华阳总运费是多少？ |
| C2A-PREC-028 | SQ455 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月客户创维客户总运费是多少？ |
| C2A-PREC-029 | SQ457 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月客户海南创维新能源投资有限公司总运费是多少？ |
| C2A-PREC-030 | SQ459 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月客户广东粤电阳西新能源有限公司总运费是多少？ |

## 四、未通过题

- 当前无未通过题。

## 五、边界

- 本轮只固化 C2A-P1 已通过精确断言的新进 A 题，不扩新 query_key。
- 未通过题不得纳入 A 精确基线，需回到总账迁移复核。
- B/C 边界仍由规则层主导，不受本轮精确断言影响。

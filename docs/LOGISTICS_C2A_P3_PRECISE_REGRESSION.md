# C2A-P3 新进 A 精确断言回归

## 一、结论

C2A-P3 共纳管 **30** 条新迁入 A 题，精确断言回归通过 **28** 条，失败 **2** 条。

## 二、标准答案来源与断言口径

- 标准答案来源：当前 `logistics_ai` 数据快照，经正式 data-qa 主链路执行后固化。
- 断言字段：`status.code`、`query_plan.query_key`、`answer_summary`、`result_table.columns`、`result_table.rows`。
- 失败归因：query_key/status/columns 异常归为代码问题；answer_summary/rows 变化归为数据基线变化；预期 A 题实际进入 clarification/unsupported 时归为题目分层误判。

## 三、题目清单

| plan_id | 题号 | query_key | 断言字段 | 问题 |
| --- | --- | --- | --- | --- |
| C2A-PREC-061 | SQ514 | hist_carrier_kpi_by_year | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年各承运商按发运量排名前十分别是谁？ |
| C2A-PREC-062 | SQ517 | hist_carrier_kpi_by_year | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年各承运商按发运量排名前十分别是谁？ |
| C2A-PREC-063 | SQ145 | hist_mw_by_all_regions | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2023年一季度各区域发运量分别是多少？请按区域排序展示。 |
| C2A-PREC-064 | SQ148 | hist_mw_by_all_regions | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2023年二季度各区域发运量分别是多少？请按区域排序展示。 |
| C2A-PREC-065 | SQ151 | hist_mw_by_all_regions | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2023年三季度各区域发运量分别是多少？请按区域排序展示。 |
| C2A-PREC-066 | SQ154 | hist_mw_by_all_regions | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2023年四季度各区域发运量分别是多少？请按区域排序展示。 |
| C2A-PREC-067 | SQ157 | hist_mw_by_all_regions | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年一季度各区域发运量分别是多少？请按区域排序展示。 |
| C2A-PREC-068 | SQ160 | hist_mw_by_all_regions | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年二季度各区域发运量分别是多少？请按区域排序展示。 |
| C2A-PREC-069 | SQ163 | hist_mw_by_all_regions | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年三季度各区域发运量分别是多少？请按区域排序展示。 |
| C2A-PREC-070 | SQ166 | hist_mw_by_all_regions | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年四季度各区域发运量分别是多少？请按区域排序展示。 |
| C2A-PREC-071 | SQ169 | hist_mw_by_all_regions | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年一季度各区域发运量分别是多少？请按区域排序展示。 |
| C2A-PREC-072 | SQ172 | hist_mw_by_all_regions | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年二季度各区域发运量分别是多少？请按区域排序展示。 |
| C2A-PREC-073 | SQ175 | hist_mw_by_all_regions | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年三季度各区域发运量分别是多少？请按区域排序展示。 |
| C2A-PREC-074 | SQ178 | hist_mw_by_all_regions | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年四季度各区域发运量分别是多少？请按区域排序展示。 |
| C2A-PREC-075 | SQ591 | hist_mw_by_all_regions | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 基于2024年前期数据，预测未来3个月各区域发运量变化趋势。 |
| C2A-PREC-076 | SQ595 | hist_mw_by_all_regions | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 基于2025年前期数据，预测未来3个月各区域发运量变化趋势。 |
| C2A-PREC-077 | SQ253 | hist_vehicle_type_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年合肥基地17.5车全年共发运多少车次？ |
| C2A-PREC-078 | SQ256 | hist_vehicle_type_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年合肥基地13m车全年共发运多少车次？ |
| C2A-PREC-079 | SQ262 | hist_vehicle_type_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年阜宁基地17.5车全年共发运多少车次？ |
| C2A-PREC-080 | SQ265 | hist_vehicle_type_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年阜宁基地13m车全年共发运多少车次？ |
| C2A-PREC-081 | SQ271 | hist_vehicle_type_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年合肥基地17.5车全年共发运多少车次？ |
| C2A-PREC-082 | SQ274 | hist_vehicle_type_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年合肥基地13m车全年共发运多少车次？ |
| C2A-PREC-083 | SQ280 | hist_vehicle_type_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年阜宁基地17.5车全年共发运多少车次？ |
| C2A-PREC-084 | SQ283 | hist_vehicle_type_trip_count | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年阜宁基地13m车全年共发运多少车次？ |
| C2A-PREC-085 | SQ001 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2023年华东区域总发运量是多少MW？ |
| C2A-PREC-086 | SQ005 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2023年华南区域总发运量是多少MW？ |
| C2A-PREC-087 | SQ009 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2023年华中区域总发运量是多少MW？ |
| C2A-PREC-088 | SQ013 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2023年华北区域总发运量是多少MW？ |
| C2A-PREC-089 | SQ017 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2023年西南区域总发运量是多少MW？ |
| C2A-PREC-090 | SQ021 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2023年西北区域总发运量是多少MW？ |

## 四、未通过题

- C2A-PREC-075 / SQ591：题目分层误判，预期 A 类 query_key=hist_mw_by_all_regions，实际进入 unsupported 边界
- C2A-PREC-076 / SQ595：题目分层误判，预期 A 类 query_key=hist_mw_by_all_regions，实际进入 unsupported 边界

## 五、边界

- 本轮只固化 C2A-P3 已通过精确断言的新进 A 题，不扩新 query_key。
- 未通过题不得纳入 A 精确基线，需回到总账迁移复核。
- B/C 边界仍由规则层主导，不受本轮精确断言影响。

# C Round2 新进 A 精确断言补强计划

## 一、结论

C Round2 新迁入 A 共 `127` 条，已全部进入分批精确断言补强计划。
本轮只建立分批计划，不直接刷新 127 条黄金答案基线。

## 二、批次安排

- `C2A-P1`：Round1：系统侧与费用高价值题，`30` 条
- `C2A-P2`：Round2：客户/承运商与费用补强题，`30` 条
- `C2A-P3`：Round3：区域/车型/承运商历史题，`30` 条
- `C2A-P4`：Round4：历史区域总量批量补强题，`37` 条

## 三、query_key 分布

- `sys_mw_and_trip_count`：`23`
- `sys_total_fee_by_filters`：`21`
- `sys_mw_by_procurement_type`：`2`
- `hist_customer_mw`：`14`
- `hist_carrier_kpi_by_year`：`2`
- `hist_mw_by_all_regions`：`14`
- `hist_vehicle_type_trip_count`：`8`
- `hist_mw_summary`：`43`

## 四、断言口径

- 标准答案来源：当前 `logistics_ai` 数据快照，由正式 data-qa 主链路执行后固化。
- 断言字段：`status.code`、`query_plan.query_key`、`answer_summary`、`result_table.columns`、`result_table.rows`。
- 失败归因：query_key/status 异常归为代码问题；answer_summary/rows 快照不一致归为数据基线变化。

## 五、第一批代表题

| plan_id | 题号 | query_key | 问题 |
| --- | --- | --- | --- |
| C2A-PREC-001 | SQ307 | sys_mw_and_trip_count | 2026年1-2月公路运输的总发运量是多少MW？ |
| C2A-PREC-002 | SQ310 | sys_mw_and_trip_count | 2026年1-2月铁路运输的总发运量是多少MW？ |
| C2A-PREC-003 | SQ313 | sys_mw_and_trip_count | 2026年1-2月多式联运运输的总发运量是多少MW？ |
| C2A-PREC-004 | SQ452 | sys_mw_and_trip_count | 2026年1-2月客户华阳总发运量是多少MW？ |
| C2A-PREC-005 | SQ454 | sys_mw_and_trip_count | 2026年1-2月客户创维客户总发运量是多少MW？ |
| C2A-PREC-006 | SQ456 | sys_mw_and_trip_count | 2026年1-2月客户海南创维新能源投资有限公司总发运量是多少MW？ |
| C2A-PREC-007 | SQ458 | sys_mw_and_trip_count | 2026年1-2月客户广东粤电阳西新能源有限公司总发运量是多少MW？ |
| C2A-PREC-008 | SQ460 | sys_mw_and_trip_count | 2026年1-2月客户华润新能源（皮山）有限公司总发运量是多少MW？ |
| C2A-PREC-009 | SQ462 | sys_mw_and_trip_count | 2026年1-2月客户国科新能源有限公司总发运量是多少MW？ |
| C2A-PREC-010 | SQ464 | sys_mw_and_trip_count | 2026年1-2月客户江苏苏美达电力运营有限公司总发运量是多少MW？ |

## 六、下一步

建议优先执行 `C2A-P1`，形成第一批 30 条精确断言基线；通过后再继续推进 P2/P3/P4。

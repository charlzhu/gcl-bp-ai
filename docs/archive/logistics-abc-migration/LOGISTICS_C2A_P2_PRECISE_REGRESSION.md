# C2A-P2 新进 A 精确断言回归

## 一、结论

C2A-P2 共纳管 **30** 条新迁入 A 题，精确断言回归通过 **30** 条，失败 **0** 条。

## 二、标准答案来源与断言口径

- 标准答案来源：当前 `logistics_ai` 数据快照，经正式 data-qa 主链路执行后固化。
- 断言字段：`status.code`、`query_plan.query_key`、`answer_summary`、`result_table.columns`、`result_table.rows`。
- 失败归因：query_key/status/columns 异常归为代码问题；answer_summary/rows 变化归为数据基线变化；预期 A 题实际进入 clarification/unsupported 时归为题目分层误判。

## 三、题目清单

| plan_id | 题号 | query_key | 断言字段 | 问题 |
| --- | --- | --- | --- | --- |
| C2A-PREC-031 | SQ461 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月客户华润新能源（皮山）有限公司总运费是多少？ |
| C2A-PREC-032 | SQ463 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月客户国科新能源有限公司总运费是多少？ |
| C2A-PREC-033 | SQ465 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月客户江苏苏美达电力运营有限公司总运费是多少？ |
| C2A-PREC-034 | SQ499 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月招标场景下的总运费是多少？ |
| C2A-PREC-035 | SQ502 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月询比价场景下的总运费是多少？ |
| C2A-PREC-036 | SQ527 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1月份总运费是多少？ |
| C2A-PREC-037 | SQ531 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年2月份总运费是多少？ |
| C2A-PREC-038 | SQ535 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月累计总运费是多少？ |
| C2A-PREC-039 | SQ551 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1月份运输方式为铁路的总运费是多少？ |
| C2A-PREC-040 | SQ553 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年2月份运输方式为铁路的总运费是多少？ |
| C2A-PREC-041 | SQ555 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月累计运输方式为铁路的总运费是多少？ |
| C2A-PREC-042 | SQ557 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1月份运输方式为公路的总运费是多少？ |
| C2A-PREC-043 | SQ559 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年2月份运输方式为公路的总运费是多少？ |
| C2A-PREC-044 | SQ561 | sys_total_fee_by_filters | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月累计运输方式为公路的总运费是多少？ |
| C2A-PREC-045 | SQ498 | sys_mw_by_procurement_type | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月招标场景下的总发运量是多少？ |
| C2A-PREC-046 | SQ501 | sys_mw_by_procurement_type | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2026年1-2月询比价场景下的总发运量是多少？ |
| C2A-PREC-047 | SQ424 | hist_customer_mw | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年客户华阳总发运量是多少MW？ |
| C2A-PREC-048 | SQ426 | hist_customer_mw | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年客户创维客户总发运量是多少MW？ |
| C2A-PREC-049 | SQ428 | hist_customer_mw | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年客户海南创维新能源投资有限公司总发运量是多少MW？ |
| C2A-PREC-050 | SQ430 | hist_customer_mw | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年客户广东粤电阳西新能源有限公司总发运量是多少MW？ |
| C2A-PREC-051 | SQ432 | hist_customer_mw | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年客户华润新能源（皮山）有限公司总发运量是多少MW？ |
| C2A-PREC-052 | SQ434 | hist_customer_mw | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年客户国科新能源有限公司总发运量是多少MW？ |
| C2A-PREC-053 | SQ436 | hist_customer_mw | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年客户江苏苏美达电力运营有限公司总发运量是多少MW？ |
| C2A-PREC-054 | SQ438 | hist_customer_mw | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年客户华阳总发运量是多少MW？ |
| C2A-PREC-055 | SQ440 | hist_customer_mw | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年客户创维客户总发运量是多少MW？ |
| C2A-PREC-056 | SQ442 | hist_customer_mw | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年客户海南创维新能源投资有限公司总发运量是多少MW？ |
| C2A-PREC-057 | SQ444 | hist_customer_mw | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年客户广东粤电阳西新能源有限公司总发运量是多少MW？ |
| C2A-PREC-058 | SQ446 | hist_customer_mw | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年客户华润新能源（皮山）有限公司总发运量是多少MW？ |
| C2A-PREC-059 | SQ448 | hist_customer_mw | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年客户国科新能源有限公司总发运量是多少MW？ |
| C2A-PREC-060 | SQ450 | hist_customer_mw | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年客户江苏苏美达电力运营有限公司总发运量是多少MW？ |

## 四、未通过题

- 当前无未通过题。

## 五、边界

- 本轮只固化 C2A-P2 已通过精确断言的新进 A 题，不扩新 query_key。
- 未通过题不得纳入 A 精确基线，需回到总账迁移复核。
- B/C 边界仍由规则层主导，不受本轮精确断言影响。

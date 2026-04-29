# B2A-P2 B->A 新进 A 精确断言回归

## 一、结论

B2A-P2 共纳管 **30** 条 B->A 新迁入 A 题，精确断言回归通过 **30** 条，失败 **0** 条。

## 二、标准答案来源与断言口径

- 标准答案来源：当前 `logistics_ai` 数据快照，经正式 data-qa 主链路执行后固化。
- 断言字段：`status.code`、`query_plan.query_key`、`answer_summary`、`result_table.columns`、`result_table.rows`。
- 失败归因：query_key/status/columns 异常归为代码问题；answer_summary/rows 变化归为数据基线变化；预期 A 题实际进入 clarification/unsupported 时归为题目分层误判。

## 三、题目清单

| plan_id | 题号 | query_key | 断言字段 | 问题 |
| --- | --- | --- | --- | --- |
| B2A-PREC-026 | SQ425 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年客户华阳总运费是多少？ |
| B2A-PREC-027 | SQ427 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年客户创维客户总运费是多少？ |
| B2A-PREC-028 | SQ429 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年客户海南创维新能源投资有限公司总运费是多少？ |
| B2A-PREC-029 | SQ433 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年客户华润新能源（皮山）有限公司总运费是多少？ |
| B2A-PREC-030 | SQ435 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年客户国科新能源有限公司总运费是多少？ |
| B2A-PREC-031 | SQ439 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年客户华阳总运费是多少？ |
| B2A-PREC-032 | SQ441 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年客户创维客户总运费是多少？ |
| B2A-PREC-033 | SQ443 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年客户海南创维新能源投资有限公司总运费是多少？ |
| B2A-PREC-034 | SQ447 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年客户华润新能源（皮山）有限公司总运费是多少？ |
| B2A-PREC-035 | SQ449 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年客户国科新能源有限公司总运费是多少？ |
| B2A-PREC-036 | SQ493 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年经营计划场景下的总运费是多少？ |
| B2A-PREC-037 | SQ496 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年辅料送样场景下的总运费是多少？ |
| B2A-PREC-038 | SQ074 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年1月份总运费是多少？ |
| B2A-PREC-039 | SQ077 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年2月份总运费是多少？ |
| B2A-PREC-040 | SQ080 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年3月份总运费是多少？ |
| B2A-PREC-041 | SQ083 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年4月份总运费是多少？ |
| B2A-PREC-042 | SQ086 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年5月份总运费是多少？ |
| B2A-PREC-043 | SQ089 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年6月份总运费是多少？ |
| B2A-PREC-044 | SQ092 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年7月份总运费是多少？ |
| B2A-PREC-045 | SQ095 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年8月份总运费是多少？ |
| B2A-PREC-046 | SQ098 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年9月份总运费是多少？ |
| B2A-PREC-047 | SQ101 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年10月份总运费是多少？ |
| B2A-PREC-048 | SQ104 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年11月份总运费是多少？ |
| B2A-PREC-049 | SQ107 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年12月份总运费是多少？ |
| B2A-PREC-050 | SQ110 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年1月份总运费是多少？ |
| B2A-PREC-051 | SQ113 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年2月份总运费是多少？ |
| B2A-PREC-052 | SQ116 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年3月份总运费是多少？ |
| B2A-PREC-053 | SQ119 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年4月份总运费是多少？ |
| B2A-PREC-054 | SQ122 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年5月份总运费是多少？ |
| B2A-PREC-055 | SQ125 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年6月份总运费是多少？ |

## 四、未通过题

- 当前无未通过题。

## 五、边界

- 本轮只固化 B2A-P2 已通过精确断言的新进 A 题，不扩 B/C 边界。
- 未通过题不得纳入稳定精确基线，需回到总账迁移复核。
- B/C 边界仍由规则层主导，不受本轮精确断言影响。

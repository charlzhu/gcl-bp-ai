# B2A-P3 B->A 新进 A 精确断言回归

## 一、结论

B2A-P3 共纳管 **30** 条 B->A 新迁入 A 题，精确断言回归通过 **30** 条，失败 **0** 条。

## 二、标准答案来源与断言口径

- 标准答案来源：当前 `logistics_ai` 数据快照，经正式 data-qa 主链路执行后固化。
- 断言字段：`status.code`、`query_plan.query_key`、`answer_summary`、`result_table.columns`、`result_table.rows`。
- 失败归因：query_key/status/columns 异常归为代码问题；answer_summary/rows 变化归为数据基线变化；预期 A 题实际进入 clarification/unsupported 时归为题目分层误判。

## 三、题目清单

| plan_id | 题号 | query_key | 断言字段 | 问题 |
| --- | --- | --- | --- | --- |
| B2A-PREC-056 | SQ128 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年7月份总运费是多少？ |
| B2A-PREC-057 | SQ131 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年8月份总运费是多少？ |
| B2A-PREC-058 | SQ134 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年9月份总运费是多少？ |
| B2A-PREC-059 | SQ137 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年10月份总运费是多少？ |
| B2A-PREC-060 | SQ140 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年11月份总运费是多少？ |
| B2A-PREC-061 | SQ143 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年12月份总运费是多少？ |
| B2A-PREC-062 | SQ377 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2023年晶茂物流全年总运费是多少？ |
| B2A-PREC-063 | SQ381 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2023年苏州晶茂物流全年总运费是多少？ |
| B2A-PREC-064 | SQ385 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2023年英赋嘉全年总运费是多少？ |
| B2A-PREC-065 | SQ389 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年晶茂物流全年总运费是多少？ |
| B2A-PREC-066 | SQ393 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年苏州晶茂物流全年总运费是多少？ |
| B2A-PREC-067 | SQ397 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年英赋嘉全年总运费是多少？ |
| B2A-PREC-068 | SQ401 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年晶茂物流全年总运费是多少？ |
| B2A-PREC-069 | SQ405 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年苏州晶茂物流全年总运费是多少？ |
| B2A-PREC-070 | SQ409 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年英赋嘉全年总运费是多少？ |
| B2A-PREC-071 | SQ413 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年晶茂物流运费占全年总运费的比例是多少？ |
| B2A-PREC-072 | SQ415 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年苏州晶茂物流运费占全年总运费的比例是多少？ |
| B2A-PREC-073 | SQ417 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年英赋嘉运费占全年总运费的比例是多少？ |
| B2A-PREC-074 | SQ419 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年晶茂物流运费占全年总运费的比例是多少？ |
| B2A-PREC-075 | SQ421 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年苏州晶茂物流运费占全年总运费的比例是多少？ |
| B2A-PREC-076 | SQ423 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年英赋嘉运费占全年总运费的比例是多少？ |
| B2A-PREC-077 | SQ487 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年招标场景下的总运费是多少？ |
| B2A-PREC-078 | SQ490 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年询比价场景下的总运费是多少？ |
| B2A-PREC-079 | Q239 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年西南区域通过铁路发运的总费用是多少？ |
| B2A-PREC-080 | SQ290 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年公路运输的总运费是多少？ |
| B2A-PREC-081 | SQ293 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年铁路运输的总运费是多少？ |
| B2A-PREC-082 | SQ296 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年多式联运运输的总运费是多少？ |
| B2A-PREC-083 | SQ299 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年公路运输的总运费是多少？ |
| B2A-PREC-084 | SQ302 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年铁路运输的总运费是多少？ |
| B2A-PREC-085 | SQ305 | hist_total_fee_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年多式联运运输的总运费是多少？ |

## 四、未通过题

- 当前无未通过题。

## 五、边界

- 本轮只固化 B2A-P3 已通过精确断言的新进 A 题，不扩 B/C 边界。
- 未通过题不得纳入稳定精确基线，需回到总账迁移复核。
- B/C 边界仍由规则层主导，不受本轮精确断言影响。

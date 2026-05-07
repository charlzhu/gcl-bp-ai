# C2A-P4 新进 A 精确断言回归

## 一、结论

C2A-P4 共纳管 **37** 条新迁入 A 题，精确断言回归通过 **37** 条，失败 **0** 条。

## 二、标准答案来源与断言口径

- 标准答案来源：当前 `logistics_ai` 数据快照，经正式 data-qa 主链路执行后固化。
- 断言字段：`status.code`、`query_plan.query_key`、`answer_summary`、`result_table.columns`、`result_table.rows`。
- 失败归因：query_key/status/columns 异常归为代码问题；answer_summary/rows 变化归为数据基线变化；预期 A 题实际进入 clarification/unsupported 时归为题目分层误判。

## 三、题目清单

| plan_id | 题号 | query_key | 断言字段 | 问题 |
| --- | --- | --- | --- | --- |
| C2A-PREC-091 | SQ025 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年华东区域总发运量是多少MW？ |
| C2A-PREC-092 | SQ029 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年华南区域总发运量是多少MW？ |
| C2A-PREC-093 | SQ033 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年华中区域总发运量是多少MW？ |
| C2A-PREC-094 | SQ037 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年华北区域总发运量是多少MW？ |
| C2A-PREC-095 | SQ041 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年西南区域总发运量是多少MW？ |
| C2A-PREC-096 | SQ045 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年西北区域总发运量是多少MW？ |
| C2A-PREC-097 | SQ049 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年华东区域总发运量是多少MW？ |
| C2A-PREC-098 | SQ053 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年华南区域总发运量是多少MW？ |
| C2A-PREC-099 | SQ057 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年华中区域总发运量是多少MW？ |
| C2A-PREC-100 | SQ061 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年华北区域总发运量是多少MW？ |
| C2A-PREC-101 | SQ065 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年西南区域总发运量是多少MW？ |
| C2A-PREC-102 | SQ069 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年西北区域总发运量是多少MW？ |
| C2A-PREC-103 | SQ073 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年1月份总发运量是多少MW？ |
| C2A-PREC-104 | SQ076 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年2月份总发运量是多少MW？ |
| C2A-PREC-105 | SQ079 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年3月份总发运量是多少MW？ |
| C2A-PREC-106 | SQ082 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年4月份总发运量是多少MW？ |
| C2A-PREC-107 | SQ085 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年5月份总发运量是多少MW？ |
| C2A-PREC-108 | SQ088 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年6月份总发运量是多少MW？ |
| C2A-PREC-109 | SQ091 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年7月份总发运量是多少MW？ |
| C2A-PREC-110 | SQ094 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年8月份总发运量是多少MW？ |
| C2A-PREC-111 | SQ097 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年9月份总发运量是多少MW？ |
| C2A-PREC-112 | SQ100 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年10月份总发运量是多少MW？ |
| C2A-PREC-113 | SQ103 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年11月份总发运量是多少MW？ |
| C2A-PREC-114 | SQ106 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2024年12月份总发运量是多少MW？ |
| C2A-PREC-115 | SQ109 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年1月份总发运量是多少MW？ |
| C2A-PREC-116 | SQ112 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年2月份总发运量是多少MW？ |
| C2A-PREC-117 | SQ115 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年3月份总发运量是多少MW？ |
| C2A-PREC-118 | SQ118 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年4月份总发运量是多少MW？ |
| C2A-PREC-119 | SQ121 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年5月份总发运量是多少MW？ |
| C2A-PREC-120 | SQ124 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年6月份总发运量是多少MW？ |
| C2A-PREC-121 | SQ127 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年7月份总发运量是多少MW？ |
| C2A-PREC-122 | SQ130 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年8月份总发运量是多少MW？ |
| C2A-PREC-123 | SQ133 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年9月份总发运量是多少MW？ |
| C2A-PREC-124 | SQ136 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年10月份总发运量是多少MW？ |
| C2A-PREC-125 | SQ139 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年11月份总发运量是多少MW？ |
| C2A-PREC-126 | SQ142 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年12月份总发运量是多少MW？ |
| C2A-PREC-127 | RAW006 | hist_mw_summary | status.code；query_plan.query_key；answer_summary；result_table.columns；result_table.rows | 2025年华东区域（上海、江苏、浙江、安徽、福建、江西、山东）全年总发运量（吨） |

## 四、未通过题

- 当前无未通过题。

## 五、边界

- 本轮只固化 C2A-P4 已通过精确断言的新进 A 题，不扩新 query_key。
- 未通过题不得纳入 A 精确基线，需回到总账迁移复核。
- B/C 边界仍由规则层主导，不受本轮精确断言影响。

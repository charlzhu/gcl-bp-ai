# 物流域 A 类关键题精确答案断言回归

## 结论

当前第一批关键 A 题共 **20** 条，精确答案断言回归结果为：通过 **20** 条，失败 **0** 条。

当前这批关键题直接选用已通过的 20 条核心验收题，原因是它们：
- 覆盖了当前最核心的稳定 query_key；
- 已有正式基线与业务确认口径；
- 适合作为从行为级回归升级到黄金答案断言的第一批题集。

## 关键题清单

| 回归编号 | 题号 | 题库编号 | query_key | 标准答案来源 | 断言口径 | 断言字段 |
| --- | --- | --- | --- | --- | --- | --- |
| AKEY01 | Q01 | Q241 | hist_total_fee_city_rank | backend/app/domains/logistics/config/data_qa_acceptance_questions.json#Q01 | 关键数值精确断言 | answer_summary；result_table.rows[*].total_fee |
| AKEY02 | Q02 | RAW064 | hist_avg_fee_by_month | backend/app/domains/logistics/config/data_qa_acceptance_questions.json#Q02 | 月度表格与摘要双口径精确断言 | result_table.rows[*].biz_month；result_table.rows[*].avg_fee；answer_summary |
| AKEY03 | Q03 | Q031 | hist_avg_fee_per_watt_by_transport | backend/app/domains/logistics/config/data_qa_acceptance_questions.json#Q03 | 关键运输方式与元瓦值断言 | answer_summary；result_table.rows[*].transport_mode；result_table.rows[*].avg_fee_per_watt |
| AKEY04 | Q04 | Q242 | hist_extra_fee_ratio_peak_month | backend/app/domains/logistics/config/data_qa_acceptance_questions.json#Q04 | 峰值月份与关键比例断言 | answer_summary；result_table.rows[*].biz_month；result_table.rows[*].extra_fee_ratio |
| AKEY05 | Q05 | RAW033 | hist_total_fee_by_origin_and_carrier | backend/app/domains/logistics/config/data_qa_acceptance_questions.json#Q05 | 总费用精确断言 | answer_summary；result_table.rows[*].total_fee |
| AKEY06 | Q06 | RAW001 | sys_mw_and_trip_count | backend/app/domains/logistics/config/data_qa_acceptance_questions.json#Q06 | MW 与车次精确断言 | result_table.rows[0].shipment_mw；result_table.rows[0].shipment_trip_count；answer_summary |
| AKEY07 | Q07 | SQ004 | hist_trip_count_by_region | backend/app/domains/logistics/config/data_qa_acceptance_questions.json#Q07 | 区域车次精确断言 | answer_summary；result_table.rows[*].shipment_trip_count |
| AKEY08 | Q08 | Q003 | hist_quantity_by_region | backend/app/domains/logistics/config/data_qa_acceptance_questions.json#Q08 | 区域件数精确断言 | answer_summary；result_table.rows[*].shipment_count |
| AKEY09 | Q09 | SQ008 | hist_trip_count_by_region | backend/app/domains/logistics/config/data_qa_acceptance_questions.json#Q09 | 区域车次精确断言 | answer_summary；result_table.rows[*].shipment_trip_count |
| AKEY10 | Q10 | RAW034 | hist_customer_mw | backend/app/domains/logistics/config/data_qa_acceptance_questions.json#Q10 | 客户项目 MW 精确断言 | answer_summary；result_table.rows[*].shipment_mw |
| AKEY11 | Q11 | Q001 | hist_quantity_by_region | backend/app/domains/logistics/config/data_qa_acceptance_questions.json#Q11 | 区域件数精确断言 | answer_summary；result_table.rows[*].shipment_count |
| AKEY12 | Q12 | Q004 | hist_quantity_by_region | backend/app/domains/logistics/config/data_qa_acceptance_questions.json#Q12 | 区域件数精确断言 | answer_summary；result_table.rows[*].shipment_count |
| AKEY13 | Q13 | Q006 | hist_quantity_by_region | backend/app/domains/logistics/config/data_qa_acceptance_questions.json#Q13 | 区域件数精确断言 | answer_summary；result_table.rows[*].shipment_count |
| AKEY14 | Q14 | Q032 | hist_avg_fee_per_watt_by_transport | backend/app/domains/logistics/config/data_qa_acceptance_questions.json#Q14 | 运输方式排序与元瓦值断言 | answer_summary；result_table.rows[*].transport_mode；result_table.rows[*].avg_fee_per_watt |
| AKEY15 | Q15 | Q007 | hist_quantity_by_region | backend/app/domains/logistics/config/data_qa_acceptance_questions.json#Q15 | 区域件数精确断言 | answer_summary；result_table.rows[*].shipment_count |
| AKEY16 | Q16 | Q263 | sys_signedfor_rate_by_carrier | backend/app/domains/logistics/config/data_qa_acceptance_questions.json#Q16 | 前十/后十成员精确断言 | result_table.rows[*].bucket；result_table.rows[*].company_name；result_table.rows[*].signedfor_rate |
| AKEY17 | Q17 | Q245 | hist_multi_origin_customers | backend/app/domains/logistics/config/data_qa_acceptance_questions.json#Q17 | 客户总数与样例客户断言 | answer_summary；result_table.rows[*].customer_name；result_table.rows[*].origin_place_count |
| AKEY18 | Q18 | Q286 | sys_companies_without_tasks | backend/app/domains/logistics/config/data_qa_acceptance_questions.json#Q18 | 存在性与结果结构断言 | answer_summary；result_table.rows[*].company_name |
| AKEY19 | Q19 | Q042 | hist_plan_actual_deviation | backend/app/domains/logistics/config/data_qa_acceptance_questions.json#Q19 | 计划件数、实际件数和偏差率精确断言 | result_table.rows[0].plan_qty_total；result_table.rows[0].actual_qty_total；answer_summary |
| AKEY20 | Q20 | Q043 | hist_plan_actual_deviation | backend/app/domains/logistics/config/data_qa_acceptance_questions.json#Q20 | 计划件数、实际件数和偏差率精确断言 | answer_summary；result_table.rows[0].deviation_rate |

## 失败归因规则

- `代码问题`：query_key 错误、误入澄清/不支持、状态码异常、执行异常。
- `数据基线变化`：链路执行成功，但结果与当前官方验收基线不一致。

## 当前未通过题

- 当前无未通过题。

## 当前边界

- 物流数据问答 MVP 已收口。
- A 类能力已经开始进入精确答案断言回归阶段。
- B/C 类响应策略继续保持系统级固化，不回退。
- 但物流域 903 条题库仍未完全收口。

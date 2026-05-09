# 物流 Planner Clarification 扫描（after fix round6）

- 输入文件：`ai/eval/runs/run_20260507_001940_full_all/actual_answers.jsonl`
- 统计范围：跳过前 14 条非物流样例，保留物流样例 1377 条。
- 当前 planner clarification：607 / 1377
- round5 基线：609 / 1377
- 本轮净变化：-2

## 按 planner category 统计

| category | count |
|---|---:|
| uncategorized | 548 |
| procurement_metric_scope | 15 |
| missing_time_for_metric | 13 |
| unknown_origin_place | 5 |
| vague_status | 4 |
| rate_distribution_scope | 3 |
| route_metric_scope | 3 |
| comparison_basis_scope | 3 |
| transport_unit_fee_scope | 3 |
| ranking_basis_scope | 2 |
| status_risk_scope | 1 |
| route_or_address_scope | 1 |
| cause_distribution_scope | 1 |
| contract_carrier_scope | 1 |
| transport_distance_scope | 1 |
| short_context_scope | 1 |
| mapping_consistency_scope | 1 |
| state_breakdown_scope | 1 |

## 业务聚类与处理判断

| cluster | count | handling | examples |
|---|---:|---|---|
| other_uncategorized_or_policy | 361 | 其他 uncategorized 需继续逐类拆分；其中开放讨论、追问策略、复杂数据质量、字段映射等不应强行修复。 | Q0072: 2023年各区域发运达标率的均值与中位数分别是多少?<br>Q0073: 2024年各区域发运达标率的均值与中位数分别是多少?<br>Q0074: 2025年各区域发运达标率的均值与中位数分别是多少?<br>Q0075: 最近物流成本是不是变高了?<br>Q0076: 帮我看看华东发运有没有异常。 |
| missing_time_dimension_metric | 156 | 保留或待细分。简单总运量/总费用无时间已默认 2023-2026；但“各物流公司/客户/省市拆分 + 多指标/平均元瓦”等仍可能涉及分组模板和跨历史/系统口径合并风险。 | Q0761: 请按年汇总历史台账中各始发地发运量占比和运费占比，并做成基地份额表？<br>Q0798: 请统计华东区域各物流公司的发运量、总费用、平均元/瓦，并按总费用降序展示？<br>Q0803: 请统计华南区域各物流公司的发运量、总费用、平均元/瓦，并按总费用降序展示？<br>Q0808: 请统计华中区域各物流公司的发运量、总费用、平均元/瓦，并按总费用降序展示？<br>Q0813: 请统计华北区域各物流公司的发运量、总费用、平均元/瓦，并按总费用降序展示？ |
| complex_multi_metric_report | 50 | 保留澄清/unsupported。宽表、透视表、同比、多指标经营分析需要报表模板、列口径和分母口径确认。 | Q0752: 请把2023年至2025年每个月的发运件数、发运瓦数、总费用、平均元/瓦放在同一张明细汇总表里？<br>Q0754: 请按年度和季度汇总发运量、发运件数、总费用、车次或车辆数，并生成季度经营汇总表？<br>Q0755: 请把2023年至2025年的发运量按年度、季度、区域三层维度汇总成透视表？<br>Q0756: 请把2023年至2025年的总费用按年度、季度、始发地三层维度汇总成透视表？<br>Q0757: 请按年度输出历史台账中运输方式、区域、始发地三者组合的发运量交叉表？ |
| remark_keyword_summary_or_detail | 20 | 本轮已放行字段明确的 Q0095 倒运/中转费用占比，以及 Q1242/Q1248/Q1254 年度备注多关键词记录数+费用金额。仍保留按年份拆分、涉及区域、前50明细等问题为澄清，因需要明细模板、线路口径或区域展示口径确认。 | Q1267: 请统计备注中包含“倒运”的历史发运记录数量、总费用和涉及区域，并按年份拆分？<br>Q1268: 请列出备注中包含“倒运”的前50条明细，包含客户、合同编号、线路、车型、物流公司和费用？<br>Q1269: 请统计备注中包含“中转”的历史发运记录数量、总费用和涉及区域，并按年份拆分？<br>Q1270: 请列出备注中包含“中转”的前50条明细，包含客户、合同编号、线路、车型、物流公司和费用？<br>Q1271: 请统计备注中包含“换车”的历史发运记录数量、总费用和涉及区域，并按年份拆分？ |
| product_power_carrier_fee | 12 | 保留澄清。历史侧可按 product_power + actual_watt + logistics_company_name + total_fee 汇总；2026 系统侧按产品功率拆分费用存在 task 级 price×解析车数与明细 supplier_price/extra_cost 两套可见口径，多功率任务费用分摊不安全，需人工确认后再实现。 | Q1149: 请统计545W功率产品按物流公司拆分的承运量、费用和平均元/瓦？<br>Q1152: 请统计550W功率产品按物流公司拆分的承运量、费用和平均元/瓦？<br>Q1155: 请统计575W功率产品按物流公司拆分的承运量、费用和平均元/瓦？<br>Q1158: 请统计580W功率产品按物流公司拆分的承运量、费用和平均元/瓦？<br>Q1161: 请统计585W功率产品按物流公司拆分的承运量、费用和平均元/瓦？ |
| product_power_region_fee | 7 | 保留澄清，原因同产品功率×承运商：2026 产品功率费用/元瓦的分摊口径未固化，不能用全量或 task 级费用冒充按功率/区域拆分。 | Q0800: 请统计华东区域各功率段产品的发运量、总费用、平均元/瓦，并用功率段汇总表展示？<br>Q0805: 请统计华南区域各功率段产品的发运量、总费用、平均元/瓦，并用功率段汇总表展示？<br>Q0810: 请统计华中区域各功率段产品的发运量、总费用、平均元/瓦，并用功率段汇总表展示？<br>Q0815: 请统计华北区域各功率段产品的发运量、总费用、平均元/瓦，并用功率段汇总表展示？<br>Q0820: 请统计西南区域各功率段产品的发运量、总费用、平均元/瓦，并用功率段汇总表展示？ |
| system_data_quality_or_status | 1 | 部分字段清晰的 2026 状态/一致性题已在前几轮支持；剩余多数涉及字段缺失、映射、状态含义或维度组合，需要逐项确认，不能批量放行。 | Q0746: 2026年各任务状态的数量分别是多少? |

## 本轮已修复并应从 clarification 移出的样例

| qid | question | query_key | needs_clarification |
|---|---|---|---:|
| Q0095 | 备注中包含“倒运”或“中转”的记录,其总费用占历史物流总费用的比例是多少? | hist_remark_keyword_fee_ratio | False |
| Q1242 | 请统计2023年备注中包含倒运、中转、换车、压车、放空的记录数量和费用金额？ | hist_remark_keyword_amount_summary | False |
| Q1248 | 请统计2024年备注中包含倒运、中转、换车、压车、放空的记录数量和费用金额？ | hist_remark_keyword_amount_summary | False |
| Q1254 | 请统计2025年备注中包含倒运、中转、换车、压车、放空的记录数量和费用金额？ | hist_remark_keyword_amount_summary | False |

## 剩余问题摘样

### uncategorized
- Q0110: 2025年华东区域(上海、江苏、浙江、安徽、福建、江西、山东)全年总发运量(吨)；missing=吨重数据口径
- Q0658: 2025年招标场景下的总发运量是多少?；missing=历史业务场景字段口径,历史数据映射规则
- Q0659: 2025年招标场景下的总运费是多少?；missing=历史业务场景字段口径,历史数据映射规则
- Q0660: 2025年招标场景下的平均单瓦成本是多少?；missing=历史业务场景字段口径,历史数据映射规则
- Q0661: 2025年询比价场景下的总发运量是多少?；missing=历史业务场景字段口径,历史数据映射规则
- Q0662: 2025年询比价场景下的总运费是多少?；missing=历史业务场景字段口径,历史数据映射规则
- Q0663: 2025年询比价场景下的平均单瓦成本是多少?；missing=历史业务场景字段口径,历史数据映射规则
- Q0664: 2025年经营计划场景下的总发运量是多少?；missing=历史业务场景字段口径,历史数据映射规则

### procurement_metric_scope
- Q0099: 招标任务与询比价任务的平均装车数分别是多少?；missing=procurement_scope,metric_definition,time_range,dimension_split
- Q0639: 2024年客户华阳按询比价和招标拆分后,发运量分别是多少?；missing=procurement_scope,metric_definition,time_range,dimension_split
- Q0641: 2024年客户创维客户按询比价和招标拆分后,发运量分别是多少?；missing=procurement_scope,metric_definition,time_range,dimension_split
- Q0643: 2024年客户海南创维新能源投资有限公司按询比价和招标拆分后,发运量分别是多少?；missing=procurement_scope,metric_definition,time_range,dimension_split
- Q0645: 2024年客户广东粤电阳西新能源有限公司按询比价和招标拆分后,发运量分别是多少?；missing=procurement_scope,metric_definition,time_range,dimension_split
- Q0647: 2024年客户华润新能源(皮山)有限公司按询比价和招标拆分后,发运量分别是多少?；missing=procurement_scope,metric_definition,time_range,dimension_split
- Q0649: 2025年客户华阳按询比价和招标拆分后,发运量分别是多少?；missing=procurement_scope,metric_definition,time_range,dimension_split
- Q0651: 2025年客户创维客户按询比价和招标拆分后,发运量分别是多少?；missing=procurement_scope,metric_definition,time_range,dimension_split

### missing_time_for_metric
- Q1149: 请统计545W功率产品按物流公司拆分的承运量、费用和平均元/瓦？；missing=time_range,source_scope
- Q1152: 请统计550W功率产品按物流公司拆分的承运量、费用和平均元/瓦？；missing=time_range,source_scope
- Q1155: 请统计575W功率产品按物流公司拆分的承运量、费用和平均元/瓦？；missing=time_range,source_scope
- Q1158: 请统计580W功率产品按物流公司拆分的承运量、费用和平均元/瓦？；missing=time_range,source_scope
- Q1161: 请统计585W功率产品按物流公司拆分的承运量、费用和平均元/瓦？；missing=time_range,source_scope
- Q1164: 请统计590W功率产品按物流公司拆分的承运量、费用和平均元/瓦？；missing=time_range,source_scope
- Q1167: 请统计620W功率产品按物流公司拆分的承运量、费用和平均元/瓦？；missing=time_range,source_scope
- Q1170: 请统计625W功率产品按物流公司拆分的承运量、费用和平均元/瓦？；missing=time_range,source_scope

### unknown_origin_place
- Q0915: 请统计广德始发各车型的车次、发运件数、总费用、平均每车装载托数，并用车型汇总表展示？；missing=始发地标准名称
- Q0923: 请统计天长始发各车型的车次、发运件数、总费用、平均每车装载托数，并用车型汇总表展示？；missing=始发地标准名称
- Q0935: 请统计2023年广德始发不同车型的发运车次、总费用和平均单车费用？；missing=始发地标准名称
- Q0944: 请统计2024年广德始发不同车型的发运车次、总费用和平均单车费用？；missing=始发地标准名称
- Q0953: 请统计2025年广德始发不同车型的发运车次、总费用和平均单车费用？；missing=始发地标准名称

### vague_status
- Q0075: 最近物流成本是不是变高了?；missing=time_range,evaluation_metric
- Q0076: 帮我看看华东发运有没有异常。；missing=time_range,evaluation_metric
- Q0078: 把最近几个特殊订单列出来。；missing=time_range,evaluation_metric
- Q0092: 哪些记录出现“每车装在托数偏高但车辆数很少”的装载异常?；missing=time_range,evaluation_metric

### rate_distribution_scope
- Q0072: 2023年各区域发运达标率的均值与中位数分别是多少?；missing=metric_definition,aggregation_basis
- Q0073: 2024年各区域发运达标率的均值与中位数分别是多少?；missing=metric_definition,aggregation_basis
- Q0074: 2025年各区域发运达标率的均值与中位数分别是多少?；missing=metric_definition,aggregation_basis

### route_metric_scope
- Q0084: 2023-2025期间,620W产品发往新疆的平均路程是多少?；missing=metric_definition,statistic_scope
- Q0087: 2023-2025单价/车最高的前10条线路是什么?；missing=metric_definition,statistic_scope
- Q0765: 请按年度统计每个始发地的平均运输距离、平均单价/车、平均元/瓦，并用基地经营分析表展示？；missing=metric_definition,statistic_scope

### comparison_basis_scope
- Q0097: 2023-2025区域发运份额变化最大的区域是哪一个?；missing=evaluation_metric,aggregation_basis
- Q0101: 不同承运商的派车状态分布是否存在明显差异?；missing=evaluation_metric,aggregation_basis
- Q0105: 哪些省份更偏好铁路运输,哪些省份几乎全部使用公路?；missing=evaluation_metric,aggregation_basis

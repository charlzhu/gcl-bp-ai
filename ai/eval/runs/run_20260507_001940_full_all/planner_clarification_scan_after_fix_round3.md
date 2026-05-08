# Planner clarification scan after round3 fixes

- total_questions: 1391
- clarification_count: 627

## by domain
- unknown: 627

## by category
- uncategorized: 563
- procurement_metric_scope: 15
- missing_time_for_metric: 13
- data_consistency_scope: 5
- vague_status: 4
- route_loading_scope: 4
- rate_distribution_scope: 3
- route_metric_scope: 3
- comparison_basis_scope: 3
- transport_unit_fee_scope: 3
- ranking_basis_scope: 2
- status_risk_scope: 1
- route_or_address_scope: 1
- cause_distribution_scope: 1
- contract_carrier_scope: 1
- transport_distance_scope: 1
- short_context_scope: 1
- mapping_consistency_scope: 1
- state_breakdown_scope: 1
- driver_identity_consistency_scope: 1

## examples by category
### uncategorized (563)
- Q0002 [] 订单00001的玻璃、间隙贴膜,焊带、汇流条、接线盒的规格描述?
- Q0003 [] 查找订单00001/00002/00003/00004/00005这几个订单的玻璃、间隙贴膜,焊带、汇流条、接线盒的规格描述并生成表格?
- Q0004 [] 订单00104的的玻璃、间隙贴膜,焊带、汇流条、接线盒的规格描述?
- Q0005 [] 订单00067和订单00106玻璃、间隙贴膜,焊带、汇流条、接线盒的规格描述有什么不一样,并用表格统计出来
- Q0006 [] 哥伦比亚COEXITO -2026-00067,NT10/78GDF的线盒物料描述
- Q0007 [] NT12R/66GDF(法国Synapsun-2026-00114)订单的玻璃,焊带,汇流条,间隙贴膜线盒的规格
- Q0008 [] NT12R/66GDF(法国Synapsun-2026-00114)订单的玻璃,焊带,汇流条,间隙贴膜线盒的规格,并生成表格
- Q0009 [] NT12R/66GDF(法国Synapsun-2026-00114)和NT12R/66GDF(法国Synapsun-2026-00114)订单的玻璃,焊带,汇流条,间隙贴膜线盒的规格对比

### procurement_metric_scope (15)
- Q0099 [] 招标任务与询比价任务的平均装车数分别是多少?
  - missing: procurement_scope,metric_definition,time_range,dimension_split
  - reason: 当前问题需要先确认采购方式对比的指标口径和统计范围，避免把不同任务集合混算。
- Q0639 [] 2024年客户华阳按询比价和招标拆分后,发运量分别是多少?
  - missing: procurement_scope,metric_definition,time_range,dimension_split
  - reason: 当前问题需要先确认采购方式对比的指标口径和统计范围，避免把不同任务集合混算。
- Q0641 [] 2024年客户创维客户按询比价和招标拆分后,发运量分别是多少?
  - missing: procurement_scope,metric_definition,time_range,dimension_split
  - reason: 当前问题需要先确认采购方式对比的指标口径和统计范围，避免把不同任务集合混算。
- Q0643 [] 2024年客户海南创维新能源投资有限公司按询比价和招标拆分后,发运量分别是多少?
  - missing: procurement_scope,metric_definition,time_range,dimension_split
  - reason: 当前问题需要先确认采购方式对比的指标口径和统计范围，避免把不同任务集合混算。
- Q0645 [] 2024年客户广东粤电阳西新能源有限公司按询比价和招标拆分后,发运量分别是多少?
  - missing: procurement_scope,metric_definition,time_range,dimension_split
  - reason: 当前问题需要先确认采购方式对比的指标口径和统计范围，避免把不同任务集合混算。
- Q0647 [] 2024年客户华润新能源(皮山)有限公司按询比价和招标拆分后,发运量分别是多少?
  - missing: procurement_scope,metric_definition,time_range,dimension_split
  - reason: 当前问题需要先确认采购方式对比的指标口径和统计范围，避免把不同任务集合混算。
- Q0649 [] 2025年客户华阳按询比价和招标拆分后,发运量分别是多少?
  - missing: procurement_scope,metric_definition,time_range,dimension_split
  - reason: 当前问题需要先确认采购方式对比的指标口径和统计范围，避免把不同任务集合混算。
- Q0651 [] 2025年客户创维客户按询比价和招标拆分后,发运量分别是多少?
  - missing: procurement_scope,metric_definition,time_range,dimension_split
  - reason: 当前问题需要先确认采购方式对比的指标口径和统计范围，避免把不同任务集合混算。

### missing_time_for_metric (13)
- Q1149 [] 请统计545W功率产品按物流公司拆分的承运量、费用和平均元/瓦？
  - missing: time_range,source_scope
  - reason: 当前问题缺少明确的时间范围，需先补充年份或统计周期。
- Q1152 [] 请统计550W功率产品按物流公司拆分的承运量、费用和平均元/瓦？
  - missing: time_range,source_scope
  - reason: 当前问题缺少明确的时间范围，需先补充年份或统计周期。
- Q1155 [] 请统计575W功率产品按物流公司拆分的承运量、费用和平均元/瓦？
  - missing: time_range,source_scope
  - reason: 当前问题缺少明确的时间范围，需先补充年份或统计周期。
- Q1158 [] 请统计580W功率产品按物流公司拆分的承运量、费用和平均元/瓦？
  - missing: time_range,source_scope
  - reason: 当前问题缺少明确的时间范围，需先补充年份或统计周期。
- Q1161 [] 请统计585W功率产品按物流公司拆分的承运量、费用和平均元/瓦？
  - missing: time_range,source_scope
  - reason: 当前问题缺少明确的时间范围，需先补充年份或统计周期。
- Q1164 [] 请统计590W功率产品按物流公司拆分的承运量、费用和平均元/瓦？
  - missing: time_range,source_scope
  - reason: 当前问题缺少明确的时间范围，需先补充年份或统计周期。
- Q1167 [] 请统计620W功率产品按物流公司拆分的承运量、费用和平均元/瓦？
  - missing: time_range,source_scope
  - reason: 当前问题缺少明确的时间范围，需先补充年份或统计周期。
- Q1170 [] 请统计625W功率产品按物流公司拆分的承运量、费用和平均元/瓦？
  - missing: time_range,source_scope
  - reason: 当前问题缺少明确的时间范围，需先补充年份或统计周期。

### data_consistency_scope (5)
- Q0001 [] 订单A-00001和订单B-00002材料对比,有哪些材料不一致?
  - missing: time_range,mapping_field,threshold_scope,dimension_split,result_metric
  - reason: 当前问题需要先明确对账对象、差异阈值、统计时间范围和输出形态，避免把数据质量问题直接当成结论。
- Q0102 [] 2026年是否存在同一身份证号关联多个手机号的司机记录?
  - missing: time_range,mapping_field,threshold_scope,dimension_split,result_metric
  - reason: 当前问题需要先明确对账对象、差异阈值、统计时间范围和输出形态，避免把数据质量问题直接当成结论。
- Q0103 [] 2026年是否存在同一手机号关联多个司机姓名的情况?
  - missing: time_range,mapping_field,threshold_scope,dimension_split,result_metric
  - reason: 当前问题需要先明确对账对象、差异阈值、统计时间范围和输出形态，避免把数据质量问题直接当成结论。
- Q1329 [] 请检查2026年同一手机号对应多个司机姓名的情况，并输出手机号、司机姓名列表和任务数？
  - missing: time_range,mapping_field,threshold_scope,dimension_split,result_metric
  - reason: 当前问题需要先明确对账对象、差异阈值、统计时间范围和输出形态，避免把数据质量问题直接当成结论。
- Q1330 [] 请检查2026年同一身份证号对应多个手机号的情况，并输出身份证号、手机号列表和任务数？
  - missing: time_range,mapping_field,threshold_scope,dimension_split,result_metric
  - reason: 当前问题需要先明确对账对象、差异阈值、统计时间范围和输出形态，避免把数据质量问题直接当成结论。

### route_loading_scope (4)
- Q0899 [] 请统计合肥始发各车型的车次、发运件数、总费用、平均每车装载托数，并用车型汇总表展示？
  - missing: statistic_scope,null_handling
  - reason: 当前问题缺少装载托数的统计口径，需先确认按车次平均还是按任务平均。
- Q0907 [] 请统计阜宁始发各车型的车次、发运件数、总费用、平均每车装载托数，并用车型汇总表展示？
  - missing: statistic_scope,null_handling
  - reason: 当前问题缺少装载托数的统计口径，需先确认按车次平均还是按任务平均。
- Q0915 [] 请统计广德始发各车型的车次、发运件数、总费用、平均每车装载托数，并用车型汇总表展示？
  - missing: statistic_scope,null_handling
  - reason: 当前问题缺少装载托数的统计口径，需先确认按车次平均还是按任务平均。
- Q0923 [] 请统计天长始发各车型的车次、发运件数、总费用、平均每车装载托数，并用车型汇总表展示？
  - missing: statistic_scope,null_handling
  - reason: 当前问题缺少装载托数的统计口径，需先确认按车次平均还是按任务平均。

### vague_status (4)
- Q0075 [] 最近物流成本是不是变高了?
  - missing: time_range,evaluation_metric
  - reason: 当前问题缺少明确时间范围和评价标准，需先补充口径。
- Q0076 [] 帮我看看华东发运有没有异常。
  - missing: time_range,evaluation_metric
  - reason: 当前问题缺少明确时间范围和评价标准，需先补充口径。
- Q0078 [] 把最近几个特殊订单列出来。
  - missing: time_range,evaluation_metric
  - reason: 当前问题缺少明确时间范围和评价标准，需先补充口径。
- Q0092 [] 哪些记录出现“每车装在托数偏高但车辆数很少”的装载异常?
  - missing: time_range,evaluation_metric
  - reason: 当前问题缺少明确时间范围和评价标准，需先补充口径。

### comparison_basis_scope (3)
- Q0097 [] 2023-2025区域发运份额变化最大的区域是哪一个?
  - missing: evaluation_metric,aggregation_basis
  - reason: 当前问题需要先明确比较指标和判断标准，避免系统按错误口径直接比较。
- Q0101 [] 不同承运商的派车状态分布是否存在明显差异?
  - missing: evaluation_metric,aggregation_basis
  - reason: 当前问题需要先明确比较指标和判断标准，避免系统按错误口径直接比较。
- Q0105 [] 哪些省份更偏好铁路运输,哪些省份几乎全部使用公路?
  - missing: evaluation_metric,aggregation_basis
  - reason: 当前问题需要先明确比较指标和判断标准，避免系统按错误口径直接比较。

### rate_distribution_scope (3)
- Q0072 [] 2023年各区域发运达标率的均值与中位数分别是多少?
  - missing: metric_definition,aggregation_basis
  - reason: 当前问题需要先明确达标率的定义和统计范围，避免把不同口径混算。
- Q0073 [] 2024年各区域发运达标率的均值与中位数分别是多少?
  - missing: metric_definition,aggregation_basis
  - reason: 当前问题需要先明确达标率的定义和统计范围，避免把不同口径混算。
- Q0074 [] 2025年各区域发运达标率的均值与中位数分别是多少?
  - missing: metric_definition,aggregation_basis
  - reason: 当前问题需要先明确达标率的定义和统计范围，避免把不同口径混算。

### route_metric_scope (3)
- Q0084 [] 2023-2025期间,620W产品发往新疆的平均路程是多少?
  - missing: metric_definition,statistic_scope
  - reason: 当前线路指标问题需要先统一统计基础，避免把单车均价、单瓦价和路程口径混算。
- Q0087 [] 2023-2025单价/车最高的前10条线路是什么?
  - missing: metric_definition,statistic_scope
  - reason: 当前线路指标问题需要先统一统计基础，避免把单车均价、单瓦价和路程口径混算。
- Q0765 [] 请按年度统计每个始发地的平均运输距离、平均单价/车、平均元/瓦，并用基地经营分析表展示？
  - missing: metric_definition,statistic_scope
  - reason: 当前线路指标问题需要先统一统计基础，避免把单车均价、单瓦价和路程口径混算。

### transport_unit_fee_scope (3)
- Q0481 [] 2026年1-2月公路运输的平均单瓦成本是多少?
  - missing: metric_definition,fee_scope,statistic_scope
  - reason: 当前问题需要先确认平均单瓦成本的计算基础和费用口径，避免把不同运输方式样本直接混算。
- Q0484 [] 2026年1-2月铁路运输的平均单瓦成本是多少?
  - missing: metric_definition,fee_scope,statistic_scope
  - reason: 当前问题需要先确认平均单瓦成本的计算基础和费用口径，避免把不同运输方式样本直接混算。
- Q0487 [] 2026年1-2月多式联运运输的平均单瓦成本是多少?
  - missing: metric_definition,fee_scope,statistic_scope
  - reason: 当前问题需要先确认平均单瓦成本的计算基础和费用口径，避免把不同运输方式样本直接混算。

### ranking_basis_scope (2)
- Q0089 [] 2024年长距离订单(路程≥1500KM)中,不同物流公司的平均总费用排名如何?
  - missing: time_range,metric_definition,aggregation_basis,dimension_split
  - reason: 当前问题需要先确认排名指标、排名方向和 TopN 数量，避免系统按错误指标直接排序。
- Q0091 [] 2025年实际发运件数超计划比例最高的前10条记录是什么?
  - missing: time_range,metric_definition,aggregation_basis,dimension_split
  - reason: 当前问题需要先确认排名指标、排名方向和 TopN 数量，避免系统按错误指标直接排序。

### cause_distribution_scope (1)
- Q0090 [] 历史台账中“产生原因”高频前三类是什么?按区域看分布有何差异?
  - missing: mapping_field,result_metric,dimension_split
  - reason: 当前问题需要先确认产生原因字段口径和区域差异的展示方式。

### contract_carrier_scope (1)
- Q0094 [] 同一合同编号对应多个物流公司的合同有多少个?涉及哪些合同?
  - missing: result_metric,source_scope
  - reason: 当前问题需要先确认合同编号与物流公司的匹配口径，以及输出数量还是明细。

### driver_identity_consistency_scope (1)
- Q0747 [] 2026年司机手机号与身份证号是否存在一人多号或一号多人情况?
  - missing: result_metric,statistic_scope,dimension_split
  - reason: 当前问题需要先明确是看异常数量、异常司机清单，还是按承运商继续拆分。

### mapping_consistency_scope (1)
- Q0691 [] 客户名写成“客户:华润新能源(皮山)有限公司”和“华润新能源(皮山)有限公司 项目”时,查询结果为什么可能不一致?
  - missing: mapping_field,result_metric
  - reason: 当前问题需要先确认统一后的字段口径和最终展示方式，再继续输出结果。

### route_or_address_scope (1)
- Q0081 [] 2023年合肥始发与阜宁始发的平均元/瓦分别是多少?两者差值是多少?
  - missing: source_scope,metric_definition,dimension_split,record_scope
  - reason: 当前问题需要先明确始发地/目的地范围、指标口径和车型或运输方式限制，避免线路条件看似明确但统计口径不一致。

### short_context_scope (1)
- Q0118 [] 分别是多少
  - missing: dimension_split,result_metric,time_range
  - reason: 当前问题缺少上下文，无法判断要分别统计什么指标和维度。

### state_breakdown_scope (1)
- Q0746 [] 2026年各任务状态的数量分别是多少?
  - missing: table_scope,status_scope
  - reason: 当前问题需要先确认统计对象和状态范围，避免把不同任务表混算。

### status_risk_scope (1)
- Q0077 [] 当前在途风险最高的是哪几单?
  - missing: evaluation_metric,time_range
  - reason: 当前问题缺少明确的风险判定标准和统计范围，需先澄清后再继续分析。

### transport_distance_scope (1)
- Q0104 [] 2026年公路与铁路任务的平均送达距离分别是多少?
  - missing: metric_definition,statistic_scope,null_handling
  - reason: 当前问题需要先确认送达距离字段口径和平均方式，避免把空值或不同任务层级混算。

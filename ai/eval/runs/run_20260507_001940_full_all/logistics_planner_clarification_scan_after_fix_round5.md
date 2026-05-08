# Logistics planner clarification scan after fix round5

- total_samples: 1391
- logistics_samples: 1377
- clarification_total: 609

## Categories
- uncategorized: 551
- procurement_metric_scope: 15
- missing_time_for_metric: 13
- unknown_origin_place: 5
- vague_status: 4
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
- mapping_consistency_scope: 1
- state_breakdown_scope: 1

## Examples
### uncategorized (551)
- Q0095 [None] 备注中包含“倒运”或“中转”的记录,其总费用占历史物流总费用的比例是多少?
  - missing: ['报表模板', '多指标口径', '维度范围']
  - reason: 当前查询链路不支持一次性生成宽表、透视表、同比变化或多指标经营汇总表。
- Q0110 [None] 2025年华东区域(上海、江苏、浙江、安徽、福建、江西、山东)全年总发运量(吨)
  - missing: ['吨重数据口径']
  - reason: 用户要求吨口径，但当前稳定数据链路只支持瓦数 / MW 发运量。
- Q0658 [None] 2025年招标场景下的总发运量是多少?
  - missing: ['历史业务场景字段口径', '历史数据映射规则']
  - reason: 历史台账缺少稳定场景字段，不能把场景词当承运商过滤到 0。
- Q0659 [None] 2025年招标场景下的总运费是多少?
  - missing: ['历史业务场景字段口径', '历史数据映射规则']
  - reason: 历史台账缺少稳定场景字段，不能把场景词当承运商过滤到 0。
- Q0660 [None] 2025年招标场景下的平均单瓦成本是多少?
  - missing: ['历史业务场景字段口径', '历史数据映射规则']
  - reason: 历史台账缺少稳定场景字段，不能把场景词当承运商过滤到 0。

### procurement_metric_scope (15)
- Q0099 [None] 招标任务与询比价任务的平均装车数分别是多少?
  - missing: ['procurement_scope', 'metric_definition', 'time_range', 'dimension_split']
  - reason: 当前问题需要先确认采购方式对比的指标口径和统计范围，避免把不同任务集合混算。
- Q0639 [None] 2024年客户华阳按询比价和招标拆分后,发运量分别是多少?
  - missing: ['procurement_scope', 'metric_definition', 'time_range', 'dimension_split']
  - reason: 当前问题需要先确认采购方式对比的指标口径和统计范围，避免把不同任务集合混算。
- Q0641 [None] 2024年客户创维客户按询比价和招标拆分后,发运量分别是多少?
  - missing: ['procurement_scope', 'metric_definition', 'time_range', 'dimension_split']
  - reason: 当前问题需要先确认采购方式对比的指标口径和统计范围，避免把不同任务集合混算。
- Q0643 [None] 2024年客户海南创维新能源投资有限公司按询比价和招标拆分后,发运量分别是多少?
  - missing: ['procurement_scope', 'metric_definition', 'time_range', 'dimension_split']
  - reason: 当前问题需要先确认采购方式对比的指标口径和统计范围，避免把不同任务集合混算。
- Q0645 [None] 2024年客户广东粤电阳西新能源有限公司按询比价和招标拆分后,发运量分别是多少?
  - missing: ['procurement_scope', 'metric_definition', 'time_range', 'dimension_split']
  - reason: 当前问题需要先确认采购方式对比的指标口径和统计范围，避免把不同任务集合混算。

### missing_time_for_metric (13)
- Q1149 [None] 请统计545W功率产品按物流公司拆分的承运量、费用和平均元/瓦？
  - missing: ['time_range', 'source_scope']
  - reason: 当前问题缺少明确的时间范围，需先补充年份或统计周期。
- Q1152 [None] 请统计550W功率产品按物流公司拆分的承运量、费用和平均元/瓦？
  - missing: ['time_range', 'source_scope']
  - reason: 当前问题缺少明确的时间范围，需先补充年份或统计周期。
- Q1155 [None] 请统计575W功率产品按物流公司拆分的承运量、费用和平均元/瓦？
  - missing: ['time_range', 'source_scope']
  - reason: 当前问题缺少明确的时间范围，需先补充年份或统计周期。
- Q1158 [None] 请统计580W功率产品按物流公司拆分的承运量、费用和平均元/瓦？
  - missing: ['time_range', 'source_scope']
  - reason: 当前问题缺少明确的时间范围，需先补充年份或统计周期。
- Q1161 [None] 请统计585W功率产品按物流公司拆分的承运量、费用和平均元/瓦？
  - missing: ['time_range', 'source_scope']
  - reason: 当前问题缺少明确的时间范围，需先补充年份或统计周期。

### unknown_origin_place (5)
- Q0915 [None] 请统计广德始发各车型的车次、发运件数、总费用、平均每车装载托数，并用车型汇总表展示？
  - missing: ['始发地标准名称']
  - reason: 当前问题包含始发地条件，但系统未能稳定识别该始发地，不能用全部始发地汇总替代。
- Q0923 [None] 请统计天长始发各车型的车次、发运件数、总费用、平均每车装载托数，并用车型汇总表展示？
  - missing: ['始发地标准名称']
  - reason: 当前问题包含始发地条件，但系统未能稳定识别该始发地，不能用全部始发地汇总替代。
- Q0935 [None] 请统计2023年广德始发不同车型的发运车次、总费用和平均单车费用？
  - missing: ['始发地标准名称']
  - reason: 当前问题包含始发地条件，但系统未能稳定识别该始发地，不能用全部始发地汇总替代。
- Q0944 [None] 请统计2024年广德始发不同车型的发运车次、总费用和平均单车费用？
  - missing: ['始发地标准名称']
  - reason: 当前问题包含始发地条件，但系统未能稳定识别该始发地，不能用全部始发地汇总替代。
- Q0953 [None] 请统计2025年广德始发不同车型的发运车次、总费用和平均单车费用？
  - missing: ['始发地标准名称']
  - reason: 当前问题包含始发地条件，但系统未能稳定识别该始发地，不能用全部始发地汇总替代。

### vague_status (4)
- Q0075 [None] 最近物流成本是不是变高了?
  - missing: ['time_range', 'evaluation_metric']
  - reason: 当前问题缺少明确时间范围和评价标准，需先补充口径。
- Q0076 [None] 帮我看看华东发运有没有异常。
  - missing: ['time_range', 'evaluation_metric']
  - reason: 当前问题缺少明确时间范围和评价标准，需先补充口径。
- Q0078 [None] 把最近几个特殊订单列出来。
  - missing: ['time_range', 'evaluation_metric']
  - reason: 当前问题缺少明确时间范围和评价标准，需先补充口径。
- Q0092 [None] 哪些记录出现“每车装在托数偏高但车辆数很少”的装载异常?
  - missing: ['time_range', 'evaluation_metric']
  - reason: 当前问题缺少明确时间范围和评价标准，需先补充口径。

### rate_distribution_scope (3)
- Q0072 [None] 2023年各区域发运达标率的均值与中位数分别是多少?
  - missing: ['metric_definition', 'aggregation_basis']
  - reason: 当前问题需要先明确达标率的定义和统计范围，避免把不同口径混算。
- Q0073 [None] 2024年各区域发运达标率的均值与中位数分别是多少?
  - missing: ['metric_definition', 'aggregation_basis']
  - reason: 当前问题需要先明确达标率的定义和统计范围，避免把不同口径混算。
- Q0074 [None] 2025年各区域发运达标率的均值与中位数分别是多少?
  - missing: ['metric_definition', 'aggregation_basis']
  - reason: 当前问题需要先明确达标率的定义和统计范围，避免把不同口径混算。

### route_metric_scope (3)
- Q0084 [None] 2023-2025期间,620W产品发往新疆的平均路程是多少?
  - missing: ['metric_definition', 'statistic_scope']
  - reason: 当前线路指标问题需要先统一统计基础，避免把单车均价、单瓦价和路程口径混算。
- Q0087 [None] 2023-2025单价/车最高的前10条线路是什么?
  - missing: ['metric_definition', 'statistic_scope']
  - reason: 当前线路指标问题需要先统一统计基础，避免把单车均价、单瓦价和路程口径混算。
- Q0765 [None] 请按年度统计每个始发地的平均运输距离、平均单价/车、平均元/瓦，并用基地经营分析表展示？
  - missing: ['metric_definition', 'statistic_scope']
  - reason: 当前线路指标问题需要先统一统计基础，避免把单车均价、单瓦价和路程口径混算。

### comparison_basis_scope (3)
- Q0097 [None] 2023-2025区域发运份额变化最大的区域是哪一个?
  - missing: ['evaluation_metric', 'aggregation_basis']
  - reason: 当前问题需要先明确比较指标和判断标准，避免系统按错误口径直接比较。
- Q0101 [None] 不同承运商的派车状态分布是否存在明显差异?
  - missing: ['evaluation_metric', 'aggregation_basis']
  - reason: 当前问题需要先明确比较指标和判断标准，避免系统按错误口径直接比较。
- Q0105 [None] 哪些省份更偏好铁路运输,哪些省份几乎全部使用公路?
  - missing: ['evaluation_metric', 'aggregation_basis']
  - reason: 当前问题需要先明确比较指标和判断标准，避免系统按错误口径直接比较。

### transport_unit_fee_scope (3)
- Q0481 [None] 2026年1-2月公路运输的平均单瓦成本是多少?
  - missing: ['metric_definition', 'fee_scope', 'statistic_scope']
  - reason: 当前问题需要先确认平均单瓦成本的计算基础和费用口径，避免把不同运输方式样本直接混算。
- Q0484 [None] 2026年1-2月铁路运输的平均单瓦成本是多少?
  - missing: ['metric_definition', 'fee_scope', 'statistic_scope']
  - reason: 当前问题需要先确认平均单瓦成本的计算基础和费用口径，避免把不同运输方式样本直接混算。
- Q0487 [None] 2026年1-2月多式联运运输的平均单瓦成本是多少?
  - missing: ['metric_definition', 'fee_scope', 'statistic_scope']
  - reason: 当前问题需要先确认平均单瓦成本的计算基础和费用口径，避免把不同运输方式样本直接混算。

### ranking_basis_scope (2)
- Q0089 [None] 2024年长距离订单(路程≥1500KM)中,不同物流公司的平均总费用排名如何?
  - missing: ['time_range', 'metric_definition', 'aggregation_basis', 'dimension_split']
  - reason: 当前问题需要先确认排名指标、排名方向和 TopN 数量，避免系统按错误指标直接排序。
- Q0091 [None] 2025年实际发运件数超计划比例最高的前10条记录是什么?
  - missing: ['time_range', 'metric_definition', 'aggregation_basis', 'dimension_split']
  - reason: 当前问题需要先确认排名指标、排名方向和 TopN 数量，避免系统按错误指标直接排序。

### status_risk_scope (1)
- Q0077 [None] 当前在途风险最高的是哪几单?
  - missing: ['evaluation_metric', 'time_range']
  - reason: 当前问题缺少明确的风险判定标准和统计范围，需先澄清后再继续分析。

### route_or_address_scope (1)
- Q0081 [None] 2023年合肥始发与阜宁始发的平均元/瓦分别是多少?两者差值是多少?
  - missing: ['source_scope', 'metric_definition', 'dimension_split', 'record_scope']
  - reason: 当前问题需要先明确始发地/目的地范围、指标口径和车型或运输方式限制，避免线路条件看似明确但统计口径不一致。

### cause_distribution_scope (1)
- Q0090 [None] 历史台账中“产生原因”高频前三类是什么?按区域看分布有何差异?
  - missing: ['mapping_field', 'result_metric', 'dimension_split']
  - reason: 当前问题需要先确认产生原因字段口径和区域差异的展示方式。

### contract_carrier_scope (1)
- Q0094 [None] 同一合同编号对应多个物流公司的合同有多少个?涉及哪些合同?
  - missing: ['result_metric', 'source_scope']
  - reason: 当前问题需要先确认合同编号与物流公司的匹配口径，以及输出数量还是明细。

### transport_distance_scope (1)
- Q0104 [None] 2026年公路与铁路任务的平均送达距离分别是多少?
  - missing: ['metric_definition', 'statistic_scope', 'null_handling']
  - reason: 当前问题需要先确认送达距离字段口径和平均方式，避免把空值或不同任务层级混算。

### mapping_consistency_scope (1)
- Q0691 [None] 客户名写成“客户:华润新能源(皮山)有限公司”和“华润新能源(皮山)有限公司 项目”时,查询结果为什么可能不一致?
  - missing: ['mapping_field', 'result_metric']
  - reason: 当前问题需要先确认统一后的字段口径和最终展示方式，再继续输出结果。

### state_breakdown_scope (1)
- Q0746 [None] 2026年各任务状态的数量分别是多少?
  - missing: ['table_scope', 'status_scope']
  - reason: 当前问题需要先确认统计对象和状态范围，避免把不同任务表混算。

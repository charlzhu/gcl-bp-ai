# 441 条 B 缺口能力建设路线图

生成时间：2026-04-26T14:23:37

## 一、结论

- 仍需澄清 B 题：`441` 条。
- 能力建设项：`65` 个。
- 缺口类型分布：`{'data_scope_gap': 58, 'query_key_gap': 347, 'business_definition_gap': 36}`。
- 建议波次分布：`{'B-gap Wave1：优先补可参数化 query_key': 9, 'B-gap Wave2：优先补数据/业务口径确认': 4, 'B-gap Wave3：中频题族能力补齐': 4, 'B-gap Observe：低频尾项观察': 48}`。

## 二、路线原则

- `query_key_gap`：优先补受控 query_key 或参数化能力，成熟后再进入 B->A 复核。
- `data_scope_gap`：先补字段来源、数据可用性、过滤范围和空值口径，不用规则硬猜。
- `business_definition_gap`：先补异常、排名、对比、风险等业务定义，未补定义前稳定澄清。

## 三、P1 能力建设项

| capability_id | 缺口类型 | 题族 | 类别 | 数量 | 建设动作 |
| --- | --- | --- | --- | ---: | --- |
| B-GAP-001 | query_key_gap | 线路/城市运价类 | route_or_address_scope | 103 | 围绕 `线路/城市运价类` 的 `route_or_address_scope` 建立可复用 query_key 或参数化解析，不写死单题。 |
| B-GAP-002 | query_key_gap | 线路/城市运价类 | route_metric_scope | 48 | 围绕 `线路/城市运价类` 的 `route_metric_scope` 建立可复用 query_key 或参数化解析，不写死单题。 |
| B-GAP-003 | query_key_gap | 综合统计类 | vehicle_or_trip_scope | 37 | 围绕 `综合统计类` 的 `vehicle_or_trip_scope` 建立可复用 query_key 或参数化解析，不写死单题。 |
| B-GAP-004 | data_scope_gap | 综合统计类 | data_consistency_scope | 20 | 先由数据 owner 确认 `综合统计类` 的 `data_consistency_scope` 字段来源、空值处理、过滤范围和数据可用性。 |
| B-GAP-007 | query_key_gap | 2026系统状态与数据质量类 | mapping_consistency_scope | 11 | 围绕 `2026系统状态与数据质量类` 的 `mapping_consistency_scope` 建立可复用 query_key 或参数化解析，不写死单题。 |
| B-GAP-011 | query_key_gap | 综合统计类 | mapping_consistency_scope | 9 | 围绕 `综合统计类` 的 `mapping_consistency_scope` 建立可复用 query_key 或参数化解析，不写死单题。 |
| B-GAP-013 | data_scope_gap | 2026系统状态与数据质量类 | data_consistency_scope | 8 | 先由数据 owner 确认 `2026系统状态与数据质量类` 的 `data_consistency_scope` 字段来源、空值处理、过滤范围和数据可用性。 |
| B-GAP-015 | data_scope_gap | 特殊业务口径类 | data_consistency_scope | 7 | 先由数据 owner 确认 `特殊业务口径类` 的 `data_consistency_scope` 字段来源、空值处理、过滤范围和数据可用性。 |
| B-GAP-020 | query_key_gap | 客户/项目分析类 | mapping_consistency_scope | 5 | 围绕 `客户/项目分析类` 的 `mapping_consistency_scope` 建立可复用 query_key 或参数化解析，不写死单题。 |
| B-GAP-024 | data_scope_gap | 区域/省份/基地汇总类 | data_consistency_scope | 4 | 先由数据 owner 确认 `区域/省份/基地汇总类` 的 `data_consistency_scope` 字段来源、空值处理、过滤范围和数据可用性。 |
| B-GAP-032 | query_key_gap | 运输方式分析类 | mapping_consistency_scope | 4 | 围绕 `运输方式分析类` 的 `mapping_consistency_scope` 建立可复用 query_key 或参数化解析，不写死单题。 |
| B-GAP-046 | query_key_gap | 承运商经营与排名类 | mapping_consistency_scope | 2 | 围绕 `承运商经营与排名类` 的 `mapping_consistency_scope` 建立可复用 query_key 或参数化解析，不写死单题。 |
| B-GAP-061 | query_key_gap | 特殊业务口径类 | mapping_consistency_scope | 1 | 围绕 `特殊业务口径类` 的 `mapping_consistency_scope` 建立可复用 query_key 或参数化解析，不写死单题。 |

## 四、代表样例

### B-GAP-001：线路/城市运价类 / route_or_address_scope

- 缺口类型：`query_key_gap`
- 建设动作：围绕 `线路/城市运价类` 的 `route_or_address_scope` 建立可复用 query_key 或参数化解析，不写死单题。
- 验收规则：对应题族样本在语义回归中不再进入通用澄清，且 A 行为回归 query_key 稳定命中。
- 样例：2023年合肥始发与阜宁始发的平均元/瓦分别是多少？两者差值是多少？
- 样例：2023年合肥基地发往江苏省的平均运费是多少？
- 样例：2023年合肥基地发往江苏省的总发运量是多少MW？

### B-GAP-002：线路/城市运价类 / route_metric_scope

- 缺口类型：`query_key_gap`
- 建设动作：围绕 `线路/城市运价类` 的 `route_metric_scope` 建立可复用 query_key 或参数化解析，不写死单题。
- 验收规则：对应题族样本在语义回归中不再进入通用澄清，且 A 行为回归 query_key 稳定命中。
- 样例：2023-2025期间，620W产品发往新疆的平均路程是多少？
- 样例：2023-2025单价/车最高的前10条线路是什么？
- 样例：2024年合肥基地17.5车平均单车运费是多少？

### B-GAP-003：综合统计类 / vehicle_or_trip_scope

- 缺口类型：`query_key_gap`
- 建设动作：围绕 `综合统计类` 的 `vehicle_or_trip_scope` 建立可复用 query_key 或参数化解析，不写死单题。
- 验收规则：对应题族样本在语义回归中不再进入通用澄清，且 A 行为回归 query_key 稳定命中。
- 样例：2024年1月份总车次是多少？
- 样例：2024年2月份总车次是多少？
- 样例：2024年3月份总车次是多少？

### B-GAP-004：综合统计类 / data_consistency_scope

- 缺口类型：`data_scope_gap`
- 建设动作：先由数据 owner 确认 `综合统计类` 的 `data_consistency_scope` 字段来源、空值处理、过滤范围和数据可用性。
- 验收规则：数据 owner 给出口径后，题目要么进入 A 候选收口，要么稳定保留业务化澄清。
- 样例：2025年将640W规格写法归一后，640W相关产品的总发运件数是多少？
- 样例：2024年河北省与山东省的平均元/瓦哪个更高？高多少？
- 样例：与历史台账相比，2026年需求重心向哪些省份迁移最明显？

### B-GAP-005：区域/省份/基地汇总类 / quarter_area_metric_scope

- 缺口类型：`query_key_gap`
- 建设动作：围绕 `区域/省份/基地汇总类` 的 `quarter_area_metric_scope` 建立可复用 query_key 或参数化解析，不写死单题。
- 验收规则：对应题族样本在语义回归中不再进入通用澄清，且 A 行为回归 query_key 稳定命中。
- 样例：2023年一季度各区域运费分别是多少？请按区域排序展示。
- 样例：2023年二季度各区域运费分别是多少？请按区域排序展示。
- 样例：2023年三季度各区域运费分别是多少？请按区域排序展示。

### B-GAP-006：综合统计类 / quarter_area_metric_scope

- 缺口类型：`query_key_gap`
- 建设动作：围绕 `综合统计类` 的 `quarter_area_metric_scope` 建立可复用 query_key 或参数化解析，不写死单题。
- 验收规则：对应题族样本在语义回归中不再进入通用澄清，且 A 行为回归 query_key 稳定命中。
- 样例：2023年一季度各区域单瓦运输成本分别是多少？
- 样例：2023年二季度各区域单瓦运输成本分别是多少？
- 样例：2023年三季度各区域单瓦运输成本分别是多少？

### B-GAP-007：2026系统状态与数据质量类 / mapping_consistency_scope

- 缺口类型：`query_key_gap`
- 建设动作：围绕 `2026系统状态与数据质量类` 的 `mapping_consistency_scope` 建立可复用 query_key 或参数化解析，不写死单题。
- 验收规则：对应题族样本在语义回归中不再进入通用澄清，且 A 行为回归 query_key 稳定命中。
- 样例：2026年派车任务中，回单解析状态为0的记录数量是多少？
- 样例：在ENTER或LEAVE状态下，enter_time仍为空的派车任务有多少条？
- 样例：哪些任务在主任务表已是SIGNEDFOR，但派车解析结果parsed_is_signed=0？应如何判定状态冲突？

### B-GAP-008：综合统计类 / vague_status

- 缺口类型：`business_definition_gap`
- 建设动作：固化 `综合统计类` 的 `vague_status` 业务定义、异常阈值、排名口径或比较标准。
- 验收规则：未补定义前稳定返回业务化澄清；补定义后再进入 A 候选复核，不允许直接猜测。
- 样例：最近物流成本是不是变高了？
- 样例：帮我看看华东发运有没有异常。
- 样例：把最近几个特殊订单列出来。

### B-GAP-009：客户/项目分析类 / procurement_metric_scope

- 缺口类型：`query_key_gap`
- 建设动作：围绕 `客户/项目分析类` 的 `procurement_metric_scope` 建立可复用 query_key 或参数化解析，不写死单题。
- 验收规则：对应题族样本在语义回归中不再进入通用澄清，且 A 行为回归 query_key 稳定命中。
- 样例：2024年客户华阳按询比价和招标拆分后，发运量分别是多少？
- 样例：2024年客户创维客户按询比价和招标拆分后，发运量分别是多少？
- 样例：2024年客户海南创维新能源投资有限公司按询比价和招标拆分后，发运量分别是多少？

### B-GAP-010：综合统计类 / customer_project_scope

- 缺口类型：`query_key_gap`
- 建设动作：围绕 `综合统计类` 的 `customer_project_scope` 建立可复用 query_key 或参数化解析，不写死单题。
- 验收规则：对应题族样本在语义回归中不再进入通用澄清，且 A 行为回归 query_key 稳定命中。
- 样例：2023年晶茂物流全年平均单瓦运输成本是多少？
- 样例：2023年苏州晶茂物流全年平均单瓦运输成本是多少？
- 样例：2023年英赋嘉全年平均单瓦运输成本是多少？

### B-GAP-011：综合统计类 / mapping_consistency_scope

- 缺口类型：`query_key_gap`
- 建设动作：围绕 `综合统计类` 的 `mapping_consistency_scope` 建立可复用 query_key 或参数化解析，不写死单题。
- 验收规则：对应题族样本在语义回归中不再进入通用澄清，且 A 行为回归 query_key 稳定命中。
- 样例：历史台账中“产生原因”高频前三类是什么？按区域看分布有何差异？
- 样例：哪些记录存在日计划发运件数为空或为0，但日实际发运件数大于0？
- 样例：哪些记录存在“规格文本中的功率”与功率字段不一致的情况？

### B-GAP-012：运输方式分析类 / transport_unit_fee_scope

- 缺口类型：`query_key_gap`
- 建设动作：围绕 `运输方式分析类` 的 `transport_unit_fee_scope` 建立可复用 query_key 或参数化解析，不写死单题。
- 验收规则：对应题族样本在语义回归中不再进入通用澄清，且 A 行为回归 query_key 稳定命中。
- 样例：2024年公路运输的平均单瓦成本是多少？
- 样例：2024年铁路运输的平均单瓦成本是多少？
- 样例：2024年多式联运运输的平均单瓦成本是多少？

## 五、下一步

- 先推进 `B-gap Wave1` 中 P1 query_key_gap，目标是批量吃掉线路/城市、综合统计、系统状态等可参数化题族。
- 同步把 `data_scope_gap` 和 `business_definition_gap` 交给数据/业务 owner 明确口径，避免误答。
- 每个能力项完成后必须回到 903 语义回归和 B->A 迁移复核，不允许直接手工改 A。

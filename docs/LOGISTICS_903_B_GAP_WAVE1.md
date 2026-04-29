# 903 B-gap Wave1 P1 query_key_gap 能力建设与迁移复核

生成时间：2026-04-26T15:07:15

## 一、结论

- 本轮复核 P1 query_key_gap 题：`228` 条。
- 真实链路稳定可答、建议迁入 A：`184` 条。
- 继续留 B：`44` 条。

## 二、本轮工程化能力

- `hist_monthly_trip_count_summary`：历史某年某月总车次。
- `hist_route_aggregate_summary`：历史始发地到省/市的平均运费或发运量 MW。
- `hist_origin_vehicle_metric_summary`：历史始发地 + 车型的平均单车运费或平均单瓦价。

## 三、能力项统计

| capability_id | 复核数 | 可迁 A | 留 B | query_key 分布 |
| --- | ---: | ---: | ---: | --- |
| B-GAP-007 | 11 | 0 | 11 | {'NONE': 11} |
| B-GAP-032 | 4 | 0 | 4 | {'NONE': 4} |
| B-GAP-001 | 103 | 102 | 1 | {'NONE': 1, 'hist_route_aggregate_summary': 102} |
| B-GAP-002 | 56 | 54 | 2 | {'NONE': 2, 'hist_origin_vehicle_metric_summary': 24, 'hist_route_aggregate_summary': 30} |
| B-GAP-011 | 9 | 0 | 9 | {'NONE': 9} |
| B-GAP-046 | 2 | 0 | 2 | {'NONE': 2} |
| B-GAP-061 | 1 | 0 | 1 | {'NONE': 1} |
| B-GAP-003 | 37 | 28 | 9 | {'hist_monthly_trip_count_summary': 24, 'hist_vehicle_type_trip_count': 4, 'NONE': 9} |
| B-GAP-020 | 5 | 0 | 5 | {'NONE': 5} |

## 四、新增可迁 A 候选

- SQ075 | hist_monthly_trip_count_summary | 2024年1月份总车次是多少？
- SQ078 | hist_monthly_trip_count_summary | 2024年2月份总车次是多少？
- SQ081 | hist_monthly_trip_count_summary | 2024年3月份总车次是多少？
- SQ084 | hist_monthly_trip_count_summary | 2024年4月份总车次是多少？
- SQ087 | hist_monthly_trip_count_summary | 2024年5月份总车次是多少？
- SQ090 | hist_monthly_trip_count_summary | 2024年6月份总车次是多少？
- SQ093 | hist_monthly_trip_count_summary | 2024年7月份总车次是多少？
- SQ096 | hist_monthly_trip_count_summary | 2024年8月份总车次是多少？
- SQ099 | hist_monthly_trip_count_summary | 2024年9月份总车次是多少？
- SQ102 | hist_monthly_trip_count_summary | 2024年10月份总车次是多少？
- SQ105 | hist_monthly_trip_count_summary | 2024年11月份总车次是多少？
- SQ108 | hist_monthly_trip_count_summary | 2024年12月份总车次是多少？
- SQ111 | hist_monthly_trip_count_summary | 2025年1月份总车次是多少？
- SQ114 | hist_monthly_trip_count_summary | 2025年2月份总车次是多少？
- SQ117 | hist_monthly_trip_count_summary | 2025年3月份总车次是多少？
- SQ120 | hist_monthly_trip_count_summary | 2025年4月份总车次是多少？
- SQ123 | hist_monthly_trip_count_summary | 2025年5月份总车次是多少？
- SQ126 | hist_monthly_trip_count_summary | 2025年6月份总车次是多少？
- SQ129 | hist_monthly_trip_count_summary | 2025年7月份总车次是多少？
- SQ132 | hist_monthly_trip_count_summary | 2025年8月份总车次是多少？
- SQ135 | hist_monthly_trip_count_summary | 2025年9月份总车次是多少？
- SQ138 | hist_monthly_trip_count_summary | 2025年10月份总车次是多少？
- SQ141 | hist_monthly_trip_count_summary | 2025年11月份总车次是多少？
- SQ144 | hist_monthly_trip_count_summary | 2025年12月份总车次是多少？
- SQ181 | hist_route_aggregate_summary | 2023年合肥基地发往江苏省的平均运费是多少？
- SQ182 | hist_route_aggregate_summary | 2023年合肥基地发往江苏省的总发运量是多少MW？
- SQ183 | hist_route_aggregate_summary | 2023年合肥基地发往浙江省的平均运费是多少？
- SQ184 | hist_route_aggregate_summary | 2023年合肥基地发往浙江省的总发运量是多少MW？
- SQ185 | hist_route_aggregate_summary | 2023年合肥基地发往上海市的平均运费是多少？
- SQ186 | hist_route_aggregate_summary | 2023年合肥基地发往上海市的总发运量是多少MW？
- SQ187 | hist_route_aggregate_summary | 2023年合肥基地发往安徽省的平均运费是多少？
- SQ188 | hist_route_aggregate_summary | 2023年合肥基地发往安徽省的总发运量是多少MW？
- SQ189 | hist_route_aggregate_summary | 2023年合肥基地发往广东省的平均运费是多少？
- SQ190 | hist_route_aggregate_summary | 2023年合肥基地发往广东省的总发运量是多少MW？
- SQ191 | hist_route_aggregate_summary | 2023年合肥基地发往广西壮族自治区的平均运费是多少？
- SQ192 | hist_route_aggregate_summary | 2023年合肥基地发往广西壮族自治区的总发运量是多少MW？
- SQ193 | hist_route_aggregate_summary | 2023年阜宁基地发往江苏省的平均运费是多少？
- SQ194 | hist_route_aggregate_summary | 2023年阜宁基地发往江苏省的总发运量是多少MW？
- SQ195 | hist_route_aggregate_summary | 2023年阜宁基地发往浙江省的平均运费是多少？
- SQ196 | hist_route_aggregate_summary | 2023年阜宁基地发往浙江省的总发运量是多少MW？
- SQ197 | hist_route_aggregate_summary | 2023年阜宁基地发往上海市的平均运费是多少？
- SQ198 | hist_route_aggregate_summary | 2023年阜宁基地发往上海市的总发运量是多少MW？
- SQ199 | hist_route_aggregate_summary | 2023年阜宁基地发往安徽省的平均运费是多少？
- SQ200 | hist_route_aggregate_summary | 2023年阜宁基地发往安徽省的总发运量是多少MW？
- SQ201 | hist_route_aggregate_summary | 2023年阜宁基地发往广东省的平均运费是多少？
- SQ202 | hist_route_aggregate_summary | 2023年阜宁基地发往广东省的总发运量是多少MW？
- SQ203 | hist_route_aggregate_summary | 2023年阜宁基地发往广西壮族自治区的平均运费是多少？
- SQ204 | hist_route_aggregate_summary | 2023年阜宁基地发往广西壮族自治区的总发运量是多少MW？
- SQ205 | hist_route_aggregate_summary | 2024年合肥基地发往江苏省的平均运费是多少？
- SQ206 | hist_route_aggregate_summary | 2024年合肥基地发往江苏省的总发运量是多少MW？
- SQ207 | hist_route_aggregate_summary | 2024年合肥基地发往浙江省的平均运费是多少？
- SQ208 | hist_route_aggregate_summary | 2024年合肥基地发往浙江省的总发运量是多少MW？
- SQ209 | hist_route_aggregate_summary | 2024年合肥基地发往上海市的平均运费是多少？
- SQ210 | hist_route_aggregate_summary | 2024年合肥基地发往上海市的总发运量是多少MW？
- SQ211 | hist_route_aggregate_summary | 2024年合肥基地发往安徽省的平均运费是多少？
- SQ212 | hist_route_aggregate_summary | 2024年合肥基地发往安徽省的总发运量是多少MW？
- SQ213 | hist_route_aggregate_summary | 2024年合肥基地发往广东省的平均运费是多少？
- SQ214 | hist_route_aggregate_summary | 2024年合肥基地发往广东省的总发运量是多少MW？
- SQ215 | hist_route_aggregate_summary | 2024年合肥基地发往广西壮族自治区的平均运费是多少？
- SQ216 | hist_route_aggregate_summary | 2024年合肥基地发往广西壮族自治区的总发运量是多少MW？
- SQ217 | hist_route_aggregate_summary | 2024年阜宁基地发往江苏省的平均运费是多少？
- SQ218 | hist_route_aggregate_summary | 2024年阜宁基地发往江苏省的总发运量是多少MW？
- SQ219 | hist_route_aggregate_summary | 2024年阜宁基地发往浙江省的平均运费是多少？
- SQ220 | hist_route_aggregate_summary | 2024年阜宁基地发往浙江省的总发运量是多少MW？
- SQ221 | hist_route_aggregate_summary | 2024年阜宁基地发往上海市的平均运费是多少？
- SQ222 | hist_route_aggregate_summary | 2024年阜宁基地发往上海市的总发运量是多少MW？
- SQ223 | hist_route_aggregate_summary | 2024年阜宁基地发往安徽省的平均运费是多少？
- SQ224 | hist_route_aggregate_summary | 2024年阜宁基地发往安徽省的总发运量是多少MW？
- SQ225 | hist_route_aggregate_summary | 2024年阜宁基地发往广东省的平均运费是多少？
- SQ226 | hist_route_aggregate_summary | 2024年阜宁基地发往广东省的总发运量是多少MW？
- SQ227 | hist_route_aggregate_summary | 2024年阜宁基地发往广西壮族自治区的平均运费是多少？
- SQ228 | hist_route_aggregate_summary | 2024年阜宁基地发往广西壮族自治区的总发运量是多少MW？
- SQ229 | hist_route_aggregate_summary | 2025年合肥基地发往江苏省的平均运费是多少？
- SQ230 | hist_route_aggregate_summary | 2025年合肥基地发往江苏省的总发运量是多少MW？
- SQ231 | hist_route_aggregate_summary | 2025年合肥基地发往浙江省的平均运费是多少？
- SQ232 | hist_route_aggregate_summary | 2025年合肥基地发往浙江省的总发运量是多少MW？
- SQ233 | hist_route_aggregate_summary | 2025年合肥基地发往上海市的平均运费是多少？
- SQ234 | hist_route_aggregate_summary | 2025年合肥基地发往上海市的总发运量是多少MW？
- SQ235 | hist_route_aggregate_summary | 2025年合肥基地发往安徽省的平均运费是多少？
- SQ236 | hist_route_aggregate_summary | 2025年合肥基地发往安徽省的总发运量是多少MW？
- 其余 104 条详见 JSON 报告。

## 五、继续留 B 的边界

- Q067 | remain_b_clarification | 2026年派车任务中，回单解析状态为0的记录数量是多少？
- Q233 | remain_b_clarification | 同一笔发运记录在历史台账中运输方式为“公路”，但在2026任务表中对应任务transport为空，系统应给出哪个答案？
- Q233 | remain_b_clarification | 同一笔发运记录在历史台账中运输方式为“公路”，但在2026任务表中对应任务transport为空，系统应给出哪个答案？
- Q240 | remain_b_clarification | 2023年合肥始发与阜宁始发的平均元/瓦分别是多少？两者差值是多少？
- Q243 | remain_b_clarification | 将“公路/汽运”口径统一后，2023-2025公路类运输的发运件数占比是多少？
- Q244 | remain_b_clarification | 2023-2025期间，620W产品发往新疆的平均路程是多少？
- Q248 | remain_b_clarification | 2023-2025单价/车最高的前10条线路是什么？
- Q251 | remain_b_clarification | 历史台账中“产生原因”高频前三类是什么？按区域看分布有何差异？
- Q253 | remain_b_clarification | 哪些记录存在日计划发运件数为空或为0，但日实际发运件数大于0？
- Q260 | remain_b_clarification | 哪些记录存在“规格文本中的功率”与功率字段不一致的情况？
- Q273 | remain_b_clarification | 在ENTER或LEAVE状态下，enter_time仍为空的派车任务有多少条？
- Q279 | remain_b_clarification | 哪些任务在主任务表已是SIGNEDFOR，但派车解析结果parsed_is_signed=0？应如何判定状态冲突？
- Q292 | remain_b_clarification | 2026年assign_detail中extra_cost大于0但cost_proof_url为空的记录有多少条？
- Q294 | remain_b_clarification | 2026年有多少allocate_task没有对应的allocate_detail明细？
- Q295 | remain_b_clarification | 2026年有多少派车任务没有生成allocate_task？
- Q298 | remain_b_clarification | 哪些仓库绑定的warehouse_user人数最少？是否存在未绑定人员的仓库？
- Q299 | remain_b_clarification | 哪些承运商绑定的company_user人数最少？是否存在无责任人配置的承运商？
- Q300 | remain_b_clarification | 2026年LEAVE或ENTER状态的派车任务中，有打卡记录的覆盖率是多少？
- Q301 | remain_b_clarification | 哪些派车任务存在多条打卡记录？这些任务的打卡时间序列是否单调递增？
- Q302 | remain_b_clarification | punch_record中的location文本与经纬度点位是否存在明显重复或冲突？
- Q303 | remain_b_clarification | 2026年是否存在同一车牌在同一天关联多个不同的派车任务？
- Q304 | remain_b_clarification | 2026年是否存在同一身份证号关联多个手机号的司机记录？
- Q305 | remain_b_clarification | 2026年是否存在同一手机号关联多个司机姓名的情况？
- Q324 | remain_b_clarification | 解析车牌与登记车牌不一致，会如何影响签收校验与后续对账？应如何排序处理优先级？
- Q331 | remain_b_clarification | 若contract_number、bidding_number、inquiry_number长期缺失，会对经营计划部的对账与归因造成哪些影响？
- Q346 | remain_b_clarification | 历史台账同时存在“铁路”和“铁运”。当业务问“铁路占比”时，系统应如何进行字段归一与结果展示？
- SQ379 | remain_b_clarification | 2023年晶茂物流全年承运车次是多少？
- SQ383 | remain_b_clarification | 2023年苏州晶茂物流全年承运车次是多少？
- SQ387 | remain_b_clarification | 2023年英赋嘉全年承运车次是多少？
- SQ391 | remain_b_clarification | 2024年晶茂物流全年承运车次是多少？
- SQ395 | remain_b_clarification | 2024年苏州晶茂物流全年承运车次是多少？
- SQ399 | remain_b_clarification | 2024年英赋嘉全年承运车次是多少？
- SQ403 | remain_b_clarification | 2025年晶茂物流全年承运车次是多少？
- SQ407 | remain_b_clarification | 2025年苏州晶茂物流全年承运车次是多少？
- SQ411 | remain_b_clarification | 2025年英赋嘉全年承运车次是多少？
- SQ431 | remain_b_clarification | 2024年客户广东粤电阳西新能源有限公司总运费是多少？
- SQ437 | remain_b_clarification | 2024年客户江苏苏美达电力运营有限公司总运费是多少？
- SQ445 | remain_b_clarification | 2025年客户广东粤电阳西新能源有限公司总运费是多少？
- SQ451 | remain_b_clarification | 2025年客户江苏苏美达电力运营有限公司总运费是多少？
- SQ523 | remain_b_clarification | 客户名写成“客户：华润新能源（皮山）有限公司”和“华润新能源（皮山）有限公司 项目”时，查询结果为什么可能不一致？
- 其余 4 条详见 JSON 报告。

## 六、治理边界

- 本轮只迁移真实 data-qa 主链路稳定可答的题。
- 状态/映射一致性、异常原因、风险解释、业务定义不清的题继续保留 B，不强行迁 A。
- B/C 正式边界仍由规则层与 response policy 主导，LLM/Guardrail 不参与改写。

# 物流 903 收口验收总报告

生成时间：2026-04-27T11:25:17

## 一、当前总账分布

- A：`656`
- B：`178`
- C：`69`
- D：`0`

## 二、A 类验收结论

- 当前 A 总数：`656`
- 行为回归：`75/75`
- 关键题精确断言：`20/20`
- B2A 精确断言：`85/85`
- Wave1-Wave4 行为回归：`184/184 / 61/61 / 24/24 / 4/4`
- Wave3-Wave5 精确断言：`30/30 / 30/30 / 40/40`
- Batch4 精确断言：`{'total_questions': 50, 'passed_questions': 50, 'failed_questions': 0, 'query_key_breakdown': {'hist_route_aggregate_summary': 50}, 'failure_classification_breakdown': {}}`
- 当前精确断言覆盖：`530/656`
- 仍未进入精确断言：`126`
- 903 全量真实问法语义回归：`1559/1559`

## 三、B 类验收结论

- 当前 B 总数：`178`
- Wave5 分层：`{'B-长期澄清池': 118, 'B-业务定义缺口池': 29, 'B-补槽后可答池': 6, 'B-数据口径缺口池': 25}`
- 追问质量：`{'total_b_questions': 178, 'acceptable_clarification': 124, 'needs_optimization': 0, 'business_confirmation_required': 54, 'missing_slot_breakdown': {'metric_definition': 79, 'time_range': 173, 'business_definition': 32, 'business_owner_confirmation': 29, 'evaluation_standard': 32, 'comparison_baseline': 7, 'transport_scope': 17, 'data_owner_confirmation': 25, 'data_scope': 22, 'ranking_metric': 3, 'sort_order': 3, 'top_n': 3}, 'quality_breakdown': {'acceptable': 124, 'business_confirmation_required': 54}}`
- 业务确认包：`{'total_confirmation_items': 54, 'bucket_breakdown': {'B-业务定义缺口池': 29, 'B-数据口径缺口池': 25}}`

B 类不能硬迁 A 的原因：

- 剩余 B 原题仍缺关键时间、指标、比较基准、数据口径或业务定义。
- 补槽后可答不等于原题可直接迁 A；原题必须保持追问边界。
- 数据口径缺口和业务定义缺口必须由业务或数据 owner 确认后再决定迁 A、留 B 或转 C。

## 四、C 类验收结论

- 当前 C 总数：`69`
- 拒答解释复检：`{'total_c_questions': 69, 'boundary_passed': 69, 'boundary_failed': 0, 'explanation_available': 69, 'category_breakdown': {'forecast': 31, 'eta': 7, 'correlation_analysis': 1, 'extra_fee_detail': 7, 'supplier_price_diagnostic': 1, 'warehouse_dimension_unreliable': 1, 'discussion': 12, 'system_response_strategy': 6, 'clarification_design': 1, 'high_fee_address_procurement_split': 1, 'project_name_dimension': 1}, 'provider_mode_breakdown': {'off': 69}, 'failure_reason_breakdown': {}}`

C 类不能硬迁 A 的原因：

- C 类包含预测、ETA、开放分析、原因诊断、未建模口径或系统无数据支撑问题。
- 当前受控 data-qa 主链路不允许凭 LLM 编造结果或直接生成 SQL。
- 后续若要支持，必须补数据、补口径、补受控 query_key 并重新回归。

## 五、NLU / Guardrail 边界

- NLU Center 模式：`dry-run / diagnostic`
- LLM 只允许做理解辅助、追问表达和解释表达。
- LLM 不允许查数、生成 SQL 或改写 A/B/C 边界。
- Guardrail 配置：`{'enabled': False, 'mode': 'off', 'sample_rate': 0.0, 'min_confidence': 0.9, 'a_querykey_whitelist': ['hist_total_fee_city_rank', 'hist_avg_fee_by_month', 'hist_avg_fee_per_watt_by_transport', 'hist_extra_fee_ratio_peak_month', 'hist_total_fee_by_origin_and_carrier', 'sys_mw_and_trip_count', 'hist_trip_count_by_region', 'hist_quantity_by_region', 'hist_customer_mw', 'hist_vehicle_type_trip_count', 'sys_signedfor_rate_by_carrier', 'hist_multi_origin_customers', 'sys_companies_without_tasks', 'hist_plan_actual_deviation', 'sys_special_total_fee'], 'audit_enabled': True, 'audit_path': 'data/logs/logistics_llm_guardrail_audit.jsonl'}`

## 六、试运行验收闭环

- 真实用户验收样例：`85/85`
- 样例状态覆盖：`{'answerable': 20, 'answerable_variant': 20, 'needs_clarification': 12, 'clarification_then_answerable': 8, 'business_confirmation_required': 10, 'unsupported': 12, 'empty_result': 1, 'execution_error': 1, 'loading': 1}`
- 前端联调检查：`9/9`
- 是否存在前端阻断问题：`False`

## 七、未进入精确断言 A 题清单

| 题号 | query_key | 题族 | 问题 |
| --- | --- | --- | --- |
| SQ075 | hist_monthly_trip_count_summary | 综合统计类 | 2024年1月份总车次是多少？ |
| SQ078 | hist_monthly_trip_count_summary | 综合统计类 | 2024年2月份总车次是多少？ |
| SQ081 | hist_monthly_trip_count_summary | 综合统计类 | 2024年3月份总车次是多少？ |
| SQ084 | hist_monthly_trip_count_summary | 综合统计类 | 2024年4月份总车次是多少？ |
| SQ087 | hist_monthly_trip_count_summary | 综合统计类 | 2024年5月份总车次是多少？ |
| SQ090 | hist_monthly_trip_count_summary | 综合统计类 | 2024年6月份总车次是多少？ |
| SQ093 | hist_monthly_trip_count_summary | 综合统计类 | 2024年7月份总车次是多少？ |
| SQ096 | hist_monthly_trip_count_summary | 综合统计类 | 2024年8月份总车次是多少？ |
| SQ099 | hist_monthly_trip_count_summary | 综合统计类 | 2024年9月份总车次是多少？ |
| SQ102 | hist_monthly_trip_count_summary | 综合统计类 | 2024年10月份总车次是多少？ |
| SQ105 | hist_monthly_trip_count_summary | 综合统计类 | 2024年11月份总车次是多少？ |
| SQ108 | hist_monthly_trip_count_summary | 综合统计类 | 2024年12月份总车次是多少？ |
| SQ111 | hist_monthly_trip_count_summary | 综合统计类 | 2025年1月份总车次是多少？ |
| SQ114 | hist_monthly_trip_count_summary | 综合统计类 | 2025年2月份总车次是多少？ |
| SQ117 | hist_monthly_trip_count_summary | 综合统计类 | 2025年3月份总车次是多少？ |
| SQ120 | hist_monthly_trip_count_summary | 综合统计类 | 2025年4月份总车次是多少？ |
| SQ123 | hist_monthly_trip_count_summary | 综合统计类 | 2025年5月份总车次是多少？ |
| SQ126 | hist_monthly_trip_count_summary | 综合统计类 | 2025年6月份总车次是多少？ |
| SQ129 | hist_monthly_trip_count_summary | 综合统计类 | 2025年7月份总车次是多少？ |
| SQ132 | hist_monthly_trip_count_summary | 综合统计类 | 2025年8月份总车次是多少？ |
| SQ135 | hist_monthly_trip_count_summary | 综合统计类 | 2025年9月份总车次是多少？ |
| SQ138 | hist_monthly_trip_count_summary | 综合统计类 | 2025年10月份总车次是多少？ |
| SQ141 | hist_monthly_trip_count_summary | 综合统计类 | 2025年11月份总车次是多少？ |
| SQ144 | hist_monthly_trip_count_summary | 综合统计类 | 2025年12月份总车次是多少？ |
| SQ242 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年阜宁基地发往江苏省的总发运量是多少MW？ |
| SQ243 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年阜宁基地发往浙江省的平均运费是多少？ |
| SQ244 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年阜宁基地发往浙江省的总发运量是多少MW？ |
| SQ245 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年阜宁基地发往上海市的平均运费是多少？ |
| SQ246 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年阜宁基地发往上海市的总发运量是多少MW？ |
| SQ247 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年阜宁基地发往安徽省的平均运费是多少？ |
| SQ248 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年阜宁基地发往安徽省的总发运量是多少MW？ |
| SQ249 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年阜宁基地发往广东省的平均运费是多少？ |
| SQ250 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年阜宁基地发往广东省的总发运量是多少MW？ |
| SQ251 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年阜宁基地发往广西壮族自治区的平均运费是多少？ |
| SQ252 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年阜宁基地发往广西壮族自治区的总发运量是多少MW？ |
| SQ254 | hist_origin_vehicle_metric_summary | 线路/城市运价类 | 2024年合肥基地17.5车平均单车运费是多少？ |
| SQ255 | hist_origin_vehicle_metric_summary | 线路/城市运价类 | 2024年合肥基地17.5车平均单瓦价是多少？ |
| SQ257 | hist_origin_vehicle_metric_summary | 线路/城市运价类 | 2024年合肥基地13m车平均单车运费是多少？ |
| SQ258 | hist_origin_vehicle_metric_summary | 线路/城市运价类 | 2024年合肥基地13m车平均单瓦价是多少？ |
| SQ259 | hist_vehicle_type_trip_count | 综合统计类 | 2024年合肥基地9.6车全年共发运多少车次？ |
| SQ260 | hist_origin_vehicle_metric_summary | 区域/省份/基地汇总类 | 2024年合肥基地9.6车平均单车运费是多少？ |
| SQ261 | hist_origin_vehicle_metric_summary | 综合统计类 | 2024年合肥基地9.6车平均单瓦价是多少？ |
| SQ263 | hist_origin_vehicle_metric_summary | 线路/城市运价类 | 2024年阜宁基地17.5车平均单车运费是多少？ |
| SQ264 | hist_origin_vehicle_metric_summary | 线路/城市运价类 | 2024年阜宁基地17.5车平均单瓦价是多少？ |
| SQ266 | hist_origin_vehicle_metric_summary | 线路/城市运价类 | 2024年阜宁基地13m车平均单车运费是多少？ |
| SQ267 | hist_origin_vehicle_metric_summary | 线路/城市运价类 | 2024年阜宁基地13m车平均单瓦价是多少？ |
| SQ268 | hist_vehicle_type_trip_count | 综合统计类 | 2024年阜宁基地9.6车全年共发运多少车次？ |
| SQ269 | hist_origin_vehicle_metric_summary | 区域/省份/基地汇总类 | 2024年阜宁基地9.6车平均单车运费是多少？ |
| SQ270 | hist_origin_vehicle_metric_summary | 综合统计类 | 2024年阜宁基地9.6车平均单瓦价是多少？ |
| SQ272 | hist_origin_vehicle_metric_summary | 线路/城市运价类 | 2025年合肥基地17.5车平均单车运费是多少？ |
| SQ273 | hist_origin_vehicle_metric_summary | 线路/城市运价类 | 2025年合肥基地17.5车平均单瓦价是多少？ |
| SQ275 | hist_origin_vehicle_metric_summary | 线路/城市运价类 | 2025年合肥基地13m车平均单车运费是多少？ |
| SQ276 | hist_origin_vehicle_metric_summary | 线路/城市运价类 | 2025年合肥基地13m车平均单瓦价是多少？ |
| SQ277 | hist_vehicle_type_trip_count | 综合统计类 | 2025年合肥基地9.6车全年共发运多少车次？ |
| SQ278 | hist_origin_vehicle_metric_summary | 区域/省份/基地汇总类 | 2025年合肥基地9.6车平均单车运费是多少？ |
| SQ279 | hist_origin_vehicle_metric_summary | 综合统计类 | 2025年合肥基地9.6车平均单瓦价是多少？ |
| SQ281 | hist_origin_vehicle_metric_summary | 线路/城市运价类 | 2025年阜宁基地17.5车平均单车运费是多少？ |
| SQ282 | hist_origin_vehicle_metric_summary | 线路/城市运价类 | 2025年阜宁基地17.5车平均单瓦价是多少？ |
| SQ284 | hist_origin_vehicle_metric_summary | 线路/城市运价类 | 2025年阜宁基地13m车平均单车运费是多少？ |
| SQ285 | hist_origin_vehicle_metric_summary | 线路/城市运价类 | 2025年阜宁基地13m车平均单瓦价是多少？ |
| SQ286 | hist_vehicle_type_trip_count | 综合统计类 | 2025年阜宁基地9.6车全年共发运多少车次？ |
| SQ287 | hist_origin_vehicle_metric_summary | 区域/省份/基地汇总类 | 2025年阜宁基地9.6车平均单车运费是多少？ |
| SQ288 | hist_origin_vehicle_metric_summary | 综合统计类 | 2025年阜宁基地9.6车平均单瓦价是多少？ |
| SQ316 | hist_route_aggregate_summary | 线路/城市运价类 | 2023年合肥基地发往广州的平均运费是多少？ |
| SQ317 | hist_route_aggregate_summary | 线路/城市运价类 | 2023年合肥基地发往广州的平均每车运费是多少？ |
| SQ318 | hist_route_aggregate_summary | 线路/城市运价类 | 2023年合肥基地发往乌鲁木齐的平均运费是多少？ |
| SQ319 | hist_route_aggregate_summary | 线路/城市运价类 | 2023年合肥基地发往乌鲁木齐的平均每车运费是多少？ |
| SQ320 | hist_route_aggregate_summary | 线路/城市运价类 | 2023年合肥基地发往苏州的平均运费是多少？ |
| SQ321 | hist_route_aggregate_summary | 线路/城市运价类 | 2023年合肥基地发往苏州的平均每车运费是多少？ |
| SQ322 | hist_route_aggregate_summary | 线路/城市运价类 | 2023年合肥基地发往宁波的平均运费是多少？ |
| SQ323 | hist_route_aggregate_summary | 线路/城市运价类 | 2023年合肥基地发往宁波的平均每车运费是多少？ |
| SQ324 | hist_route_aggregate_summary | 线路/城市运价类 | 2023年合肥基地发往南昌的平均运费是多少？ |
| SQ325 | hist_route_aggregate_summary | 线路/城市运价类 | 2023年合肥基地发往南昌的平均每车运费是多少？ |
| SQ326 | hist_route_aggregate_summary | 线路/城市运价类 | 2023年合肥基地发往福州的平均运费是多少？ |
| SQ327 | hist_route_aggregate_summary | 线路/城市运价类 | 2023年合肥基地发往福州的平均每车运费是多少？ |
| SQ328 | hist_route_aggregate_summary | 线路/城市运价类 | 2023年合肥基地发往海口的平均运费是多少？ |
| SQ329 | hist_route_aggregate_summary | 线路/城市运价类 | 2023年合肥基地发往海口的平均每车运费是多少？ |
| SQ330 | hist_route_aggregate_summary | 线路/城市运价类 | 2023年合肥基地发往南宁的平均运费是多少？ |
| SQ331 | hist_route_aggregate_summary | 线路/城市运价类 | 2023年合肥基地发往南宁的平均每车运费是多少？ |
| SQ332 | hist_route_aggregate_summary | 线路/城市运价类 | 2023年合肥基地发往徐州的平均运费是多少？ |
| SQ333 | hist_route_aggregate_summary | 线路/城市运价类 | 2023年合肥基地发往徐州的平均每车运费是多少？ |
| SQ334 | hist_route_aggregate_summary | 线路/城市运价类 | 2023年合肥基地发往温州的平均运费是多少？ |
| SQ335 | hist_route_aggregate_summary | 线路/城市运价类 | 2023年合肥基地发往温州的平均每车运费是多少？ |
| SQ336 | hist_route_aggregate_summary | 线路/城市运价类 | 2024年合肥基地发往广州的平均运费是多少？ |
| SQ337 | hist_route_aggregate_summary | 线路/城市运价类 | 2024年合肥基地发往广州的平均每车运费是多少？ |
| SQ338 | hist_route_aggregate_summary | 线路/城市运价类 | 2024年合肥基地发往乌鲁木齐的平均运费是多少？ |
| SQ339 | hist_route_aggregate_summary | 线路/城市运价类 | 2024年合肥基地发往乌鲁木齐的平均每车运费是多少？ |
| SQ340 | hist_route_aggregate_summary | 线路/城市运价类 | 2024年合肥基地发往苏州的平均运费是多少？ |
| SQ341 | hist_route_aggregate_summary | 线路/城市运价类 | 2024年合肥基地发往苏州的平均每车运费是多少？ |
| SQ342 | hist_route_aggregate_summary | 线路/城市运价类 | 2024年合肥基地发往宁波的平均运费是多少？ |
| SQ343 | hist_route_aggregate_summary | 线路/城市运价类 | 2024年合肥基地发往宁波的平均每车运费是多少？ |
| SQ344 | hist_route_aggregate_summary | 线路/城市运价类 | 2024年合肥基地发往南昌的平均运费是多少？ |
| SQ345 | hist_route_aggregate_summary | 线路/城市运价类 | 2024年合肥基地发往南昌的平均每车运费是多少？ |
| SQ346 | hist_route_aggregate_summary | 线路/城市运价类 | 2024年合肥基地发往福州的平均运费是多少？ |
| SQ347 | hist_route_aggregate_summary | 线路/城市运价类 | 2024年合肥基地发往福州的平均每车运费是多少？ |
| SQ348 | hist_route_aggregate_summary | 线路/城市运价类 | 2024年合肥基地发往海口的平均运费是多少？ |
| SQ349 | hist_route_aggregate_summary | 线路/城市运价类 | 2024年合肥基地发往海口的平均每车运费是多少？ |
| SQ350 | hist_route_aggregate_summary | 线路/城市运价类 | 2024年合肥基地发往南宁的平均运费是多少？ |
| SQ351 | hist_route_aggregate_summary | 线路/城市运价类 | 2024年合肥基地发往南宁的平均每车运费是多少？ |
| SQ352 | hist_route_aggregate_summary | 线路/城市运价类 | 2024年合肥基地发往徐州的平均运费是多少？ |
| SQ353 | hist_route_aggregate_summary | 线路/城市运价类 | 2024年合肥基地发往徐州的平均每车运费是多少？ |
| SQ354 | hist_route_aggregate_summary | 线路/城市运价类 | 2024年合肥基地发往温州的平均运费是多少？ |
| SQ355 | hist_route_aggregate_summary | 线路/城市运价类 | 2024年合肥基地发往温州的平均每车运费是多少？ |
| SQ356 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年合肥基地发往广州的平均运费是多少？ |
| SQ357 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年合肥基地发往广州的平均每车运费是多少？ |
| SQ358 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年合肥基地发往乌鲁木齐的平均运费是多少？ |
| SQ359 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年合肥基地发往乌鲁木齐的平均每车运费是多少？ |
| SQ360 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年合肥基地发往苏州的平均运费是多少？ |
| SQ361 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年合肥基地发往苏州的平均每车运费是多少？ |
| SQ362 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年合肥基地发往宁波的平均运费是多少？ |
| SQ363 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年合肥基地发往宁波的平均每车运费是多少？ |
| SQ364 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年合肥基地发往南昌的平均运费是多少？ |
| SQ365 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年合肥基地发往南昌的平均每车运费是多少？ |
| SQ366 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年合肥基地发往福州的平均运费是多少？ |
| SQ367 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年合肥基地发往福州的平均每车运费是多少？ |
| SQ368 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年合肥基地发往海口的平均运费是多少？ |
| SQ369 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年合肥基地发往海口的平均每车运费是多少？ |
| SQ370 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年合肥基地发往南宁的平均运费是多少？ |
| SQ371 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年合肥基地发往南宁的平均每车运费是多少？ |
| SQ372 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年合肥基地发往徐州的平均运费是多少？ |
| SQ373 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年合肥基地发往徐州的平均每车运费是多少？ |
| SQ374 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年合肥基地发往温州的平均运费是多少？ |
| SQ375 | hist_route_aggregate_summary | 线路/城市运价类 | 2025年合肥基地发往温州的平均每车运费是多少？ |
| SQ536 | sys_unit_fee_per_watt | 综合统计类 | 2026年1-2月累计单瓦运输成本是多少？ |
| SQ554 | sys_mw_and_trip_count | 运输方式分析类 | 2026年1-2月累计运输方式为铁路的运输总量是多少MW？ |
| SQ560 | sys_mw_and_trip_count | 运输方式分析类 | 2026年1-2月累计运输方式为公路的运输总量是多少MW？ |

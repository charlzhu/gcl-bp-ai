# NL2SQL Logistics Shadow Smoke Evaluation Report

## Summary
- total: 12
- success_count: 6
- failure_count: 4
- skipped_count: 1
- unsupported_count: 1
- success_rate: 0.5000
- fail_closed_count: 4
- safety_block_count: 1
- safety_pass_count: 6
- executor_touched_count: 6
- executor_not_touched_count: 6
- expected_status_match_count: 12
- expected_status_mismatch_count: 0
- expected_status_match_rate: 1.0000
- execution_failure_count: 0
- sql_hash_coverage: 1.0000
- catalog_ref_coverage: 0.9167
- distinct_catalog_ref_count: 18

## By Status
- success: 6
- validation_failed: 3
- safety_failed: 1
- skipped: 1
- unsupported: 1

## By Stage
- trial: 6
- validation: 3
- safety: 1
- candidate: 2

## Top Errors
- sqlplan_unsupported_tonnage_rule_blocks_sql_direct: 1
- sqlplan_unsupported_unit::吨: 1
- sqlplan_catalog_id_not_found::metric:unknown_price_metric: 1
- sqlplan_metric_not_found::unknown_price_metric: 1
- sqlplan_metric_table_not_in_plan::unit_price_per_vehicle::dwd_logistics_hist_shipment_detail: 1
- sql_safety_not_select: 1
- sql_safety_forbidden_token::update: 1
- sql_safety_table_required: 1
- sql_safety_unqualified_identifier::update: 1
- sql_safety_unqualified_identifier::set: 1

## By Metric
- shipment_mw: 7
- row_count: 6
- avg_fee_per_trip: 1
- total_fee: 4
- shipment_trip_count: 2
- unknown_price_metric: 1
- carrier_rank_by_mw: 1
- unit_price_per_vehicle: 1

## By Dimension
- biz_year: 11
- logistics_company_name: 3
- biz_month: 1
- region_name: 1
- transport_mode: 1
- origin_place: 1
- customer_name: 1

## By Table
- dws_logistics_detail_union: 11

## By Category
- trend: 2
- ranking: 2
- breakdown: 1
- validation: 4
- detail: 1
- safety: 1
- environment: 1

## By Business Case
- explicit_year_bucket_shipment_volume: 1
- carrier_average_freight_by_trip: 1
- monthly_total_fee_trend: 1
- region_transport_mode_breakdown: 1
- unsupported_tonnage_fail_closed: 1
- unknown_price_metric_fail_closed: 1
- carrier_rank_by_shipment_mw: 1
- origin_customer_topn_detail: 1
- unit_price_scope_fail_closed: 1
- forbidden_update_sql_blocked: 1
- missing_candidate_skipped: 1
- non_sql_direct_strategy_unsupported: 1

## By Metric Family
- shipment_volume: 3
- average_freight: 1
- total_fee: 1
- unsupported: 4
- trip_count: 1
- unit_price: 1
- safety_negative: 1

## Sample Outcomes
| sample_id | description | status | stage | error_codes |
| --- | --- | --- | --- | --- |
| m8_success_yearly_shipment_mw_by_year | 按年份汇总发运量和明细行数，验证显式多年份桶覆盖 | success | trial |  |
| m8_success_carrier_avg_fee_per_trip | 按承运商统计平均每车费用，验证均价口径与总费用/车次同时可追溯 | success | trial |  |
| m8_success_monthly_total_fee_trend | 按年月汇总总费用，验证月度趋势维度覆盖 | success | trial |  |
| m8_success_region_transport_mode_shipment_fee | 按区域和运输方式拆分发运量、总费用，验证多维 group by 覆盖 | success | trial |  |
| m8_validation_tonnage_unit_rejected | 吨数/吨位当前不支持，必须停在 SQLPlan 校验边界 | validation_failed | validation | sqlplan_unsupported_tonnage_rule_blocks_sql_direct, sqlplan_unsupported_unit::吨 |
| m8_validation_unknown_price_metric_rejected | 未知价格指标不能默认为均价或报价，必须 fail-closed | validation_failed | validation | sqlplan_catalog_id_not_found::metric:unknown_price_metric, sqlplan_metric_not_found::unknown_price_metric |
| m8_success_carrier_rank_by_mw | 按承运商统计发运量排名，验证哪个物流跑得最多的排名口径 | success | trial |  |
| m8_success_origin_customer_topn_detail | 按始发地和客户输出明细 TopN，验证明细类 limit 与路线/客户维度覆盖 | success | trial |  |
| m8_validation_quote_metric_requires_supported_hist_scope | 报价/单价/运价依赖历史明细单价表，M8 dws-only shadow 样例必须受控失败 | validation_failed | validation | sqlplan_metric_table_not_in_plan::unit_price_per_vehicle::dwd_logistics_hist_shipment_detail |
| m8_safety_forbidden_update_sql_blocked | 渲染器异常输出写 SQL 时必须停在 safety gate，且不触达 executor | safety_failed | safety | sql_safety_not_select, sql_safety_forbidden_token::update, sql_safety_table_required, sql_safety_unqualified_identifier::update, sql_safety_unqualified_identifier::set, sql_safety_unqualified_identifier::shipment_watt |
| m8_skipped_missing_candidate | 缺少 SQLPlan candidate 时跳过 SQL 阶段，保持 shadow 不影响主流程 | skipped | candidate | shadow_candidate_missing |
| m8_unsupported_non_sql_direct_strategy | 非 sql_direct strategy 停在 candidate 边界 | unsupported | candidate | shadow_strategy_not_sql_direct::clarify |

## Warnings
- logistics_nl2sql_m8_shadow_eval.v1 shadow-only; no live database query executed
- m8_safety_negative_renderer

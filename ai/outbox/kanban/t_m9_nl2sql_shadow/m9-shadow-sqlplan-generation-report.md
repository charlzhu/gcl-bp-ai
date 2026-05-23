# M9 NL2SQL Shadow SQLPlan Generation Report

- version: logistics_nl2sql_m9_shadow_sqlplan_generation.v1
- shadow_only: True
- total: 17
- success_count: 0
- generated_count: 0
- validation_pass_count: 0
- recall_failed_count: 0
- candidate_sql_gate_allowed_count: 0
- candidate_sql_gate_rejected_count: 0
- expected_status_mismatch_count: 15

## By Status
- error: 9
- validation_failed: 8

## Samples
- m9_success_carrier_mw_ranking_default_years: status=error, stage=generation, generated=False
- m9_success_yearly_mw_breakdown: status=error, stage=generation, generated=False
- m9_guard_tonnage_fail_closed: status=validation_failed, stage=rewrite, generated=False
- m9_success_total_fee_summary: status=error, stage=generation, generated=False
- m9_success_mw_summary: status=error, stage=generation, generated=False
- m9_success_carrier_mw_by_year: status=error, stage=generation, generated=False
- m9_success_origin_customer_topn: status=validation_failed, stage=generation, generated=False
- m9_success_route_pricing: status=validation_failed, stage=generation, generated=False
- m9_success_multi_year_fee_compare: status=validation_failed, stage=generation, generated=False
- m9_success_region_monthly_mw: status=error, stage=generation, generated=False
- m9_success_multi_metric_aggregate: status=validation_failed, stage=rewrite, generated=False
- m9_success_vehicle_type_summary: status=error, stage=generation, generated=False
- m9_success_extra_fee_by_month: status=error, stage=generation, generated=False
- m9_guard_tonnage_fail_closed: status=validation_failed, stage=rewrite, generated=False
- m9_success_avg_fee_per_watt: status=validation_failed, stage=generation, generated=False
- m9_success_extra_fee_ratio: status=validation_failed, stage=generation, generated=False
- m9_success_customer_mw_by_year: status=error, stage=generation, generated=False

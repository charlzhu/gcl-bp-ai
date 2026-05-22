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
- disabled: 14
- validation_failed: 3

## Samples
- m9_success_carrier_mw_ranking_default_years: status=disabled, stage=generation, generated=False
- m9_success_yearly_mw_breakdown: status=disabled, stage=generation, generated=False
- m9_guard_tonnage_fail_closed: status=validation_failed, stage=rewrite, generated=False
- m9_success_total_fee_summary: status=disabled, stage=generation, generated=False
- m9_success_mw_summary: status=disabled, stage=generation, generated=False
- m9_success_carrier_mw_by_year: status=disabled, stage=generation, generated=False
- m9_success_origin_customer_topn: status=disabled, stage=generation, generated=False
- m9_success_route_pricing: status=disabled, stage=generation, generated=False
- m9_success_multi_year_fee_compare: status=disabled, stage=generation, generated=False
- m9_success_region_monthly_mw: status=disabled, stage=generation, generated=False
- m9_success_multi_metric_aggregate: status=validation_failed, stage=rewrite, generated=False
- m9_success_vehicle_type_summary: status=disabled, stage=generation, generated=False
- m9_success_extra_fee_by_month: status=disabled, stage=generation, generated=False
- m9_guard_tonnage_fail_closed: status=validation_failed, stage=rewrite, generated=False
- m9_success_avg_fee_per_watt: status=disabled, stage=generation, generated=False
- m9_success_extra_fee_ratio: status=disabled, stage=generation, generated=False
- m9_success_customer_mw_by_year: status=disabled, stage=generation, generated=False

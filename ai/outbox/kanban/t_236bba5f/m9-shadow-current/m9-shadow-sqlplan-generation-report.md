# M9 NL2SQL Shadow SQLPlan Generation Report

- version: logistics_nl2sql_m9_shadow_sqlplan_generation.v1
- shadow_only: True
- total: 3
- success_count: 2
- generated_count: 2
- validation_pass_count: 2
- recall_failed_count: 0
- expected_status_mismatch_count: 0

## By Status
- success: 2
- validation_failed: 1

## Samples
- m9_success_carrier_mw_ranking_default_years: status=success, stage=trial, generated=True
- m9_success_yearly_mw_breakdown: status=success, stage=trial, generated=True
- m9_guard_tonnage_fail_closed: status=validation_failed, stage=rewrite, generated=False

# 产销存 M5 Shadow Compare Report

version: business_analysis_inventory_sales_production_m5_shadow_compare.v1
shadow_only: true
formal_qa_executed: false
live_db_executed: false
total: 31
matched_count: 20
fail_closed_count: 11
expected_status_mismatch_count: 0

## by_status
- matched: 20
- queryplan_clarification: 3
- queryplan_unsupported: 4
- sqlplan_candidate_unavailable: 1
- sqlplan_validation_failed: 3

## sample_outcomes
- m4_6_sales_year_summary: category=sales_summary; status=matched; expected=matched; stage=shadow_compare; errors=-
- m4_6_sales_quarter_summary: category=sales_summary; status=matched; expected=matched; stage=shadow_compare; errors=-
- m4_6_sales_ytd_summary: category=sales_summary; status=matched; expected=matched; stage=shadow_compare; errors=-
- m4_6_inventory_snapshot: category=inventory_snapshot; status=matched; expected=matched; stage=shadow_compare; errors=-
- m4_6_consigned_inventory_snapshot: category=inventory_snapshot; status=matched; expected=matched; stage=shadow_compare; errors=-
- m4_6_budget_achievement: category=budget_achievement; status=matched; expected=matched; stage=shadow_compare; errors=-
- m4_6_invoice_sales_summary: category=sales_summary; status=matched; expected=matched; stage=shadow_compare; errors=-
- m4_6_unsupported_yoy: category=unsupported_guard; status=queryplan_unsupported; expected=queryplan_unsupported; stage=queryplan_planning; errors=queryplan_unsupported
- m4_6_unsupported_month_range: category=unsupported_guard; status=queryplan_unsupported; expected=queryplan_unsupported; stage=queryplan_planning; errors=queryplan_unsupported
- m4_6_clarification_inventory_turnover: category=clarification_guard; status=queryplan_clarification; expected=queryplan_clarification; stage=queryplan_planning; errors=queryplan_clarification
- m5_redaction_sql_payload_blocked: category=redaction_guard; status=sqlplan_validation_failed; expected=sqlplan_validation_failed; stage=sqlplan_validation; errors=sqlplan_forbidden_key::plan.raw_sql,sqlplan_forbidden_sql_string::plan.raw_sql,sqlplan_schema_invalid::plan.raw_sql::extra_forbidden,sqlplan_month_filter_operator_unsupported::like
- m5_6_production_year_summary: category=production_summary; status=matched; expected=matched; stage=shadow_compare; errors=-
- m5_6_sales_external_default_scope: category=sales_summary; status=matched; expected=matched; stage=shadow_compare; errors=-
- m5_6_sales_year_synonym_shipment: category=sales_summary; status=matched; expected=matched; stage=shadow_compare; errors=-
- m5_6_sales_chinese_quarter_synonym: category=sales_summary; status=matched; expected=matched; stage=shadow_compare; errors=-
- m5_6_sales_ytd_prefix_synonym: category=time_boundary_guard; status=matched; expected=matched; stage=shadow_compare; errors=-
- m5_6_inventory_stock_synonym: category=inventory_snapshot; status=matched; expected=matched; stage=shadow_compare; errors=-
- m5_6_consigned_inventory_synonym: category=inventory_snapshot; status=matched; expected=matched; stage=shadow_compare; errors=-
- m5_6_budget_achievement_current_year_boundary: category=budget_achievement; status=matched; expected=matched; stage=shadow_compare; errors=-
- m5_6_production_by_model_type: category=dimension_breakdown; status=matched; expected=matched; stage=shadow_compare; errors=-
- m5_6_inventory_by_base_period_end: category=dimension_breakdown; status=matched; expected=matched; stage=shadow_compare; errors=-
- m5_6_sales_by_base_breakdown: category=dimension_breakdown; status=matched; expected=matched; stage=shadow_compare; errors=-
- m5_6_sales_monthly_trend: category=time_boundary_guard; status=matched; expected=matched; stage=shadow_compare; errors=-
- m5_6_production_ytd_boundary: category=time_boundary_guard; status=matched; expected=matched; stage=shadow_compare; errors=-
- m5_6_sales_future_month_blocked: category=time_boundary_guard; status=queryplan_unsupported; expected=queryplan_unsupported; stage=queryplan_planning; errors=queryplan_unsupported
- m5_6_missing_time_default_years_scope: category=missing_time_scope_guard; status=sqlplan_candidate_unavailable; expected=sqlplan_candidate_unavailable; stage=sqlplan_candidate; errors=sqlplan_candidate_unavailable
- m5_6_missing_time_no_time_default_scope_guard: category=missing_time_scope_guard; status=queryplan_clarification; expected=queryplan_clarification; stage=queryplan_planning; errors=queryplan_clarification
- m5_6_unsupported_mom: category=unsupported_guard; status=queryplan_unsupported; expected=queryplan_unsupported; stage=queryplan_planning; errors=queryplan_unsupported
- m5_6_clarification_unknown_metric: category=clarification_guard; status=queryplan_clarification; expected=queryplan_clarification; stage=queryplan_planning; errors=queryplan_clarification
- m5_6_sqlplan_unpublished_month_guard: category=time_boundary_guard; status=sqlplan_validation_failed; expected=sqlplan_validation_failed; stage=sqlplan_validation; errors=sqlplan_unpublished_month_blocks_sql_direct::[PERIOD_BOUNDARY]
- m5_6_sqlplan_internal_debug_key_guard: category=redaction_guard; status=sqlplan_validation_failed; expected=sqlplan_validation_failed; stage=sqlplan_validation; errors=sqlplan_forbidden_sql_string::plan.business_flags.redacted,sqlplan_business_flag_not_allowed::redacted

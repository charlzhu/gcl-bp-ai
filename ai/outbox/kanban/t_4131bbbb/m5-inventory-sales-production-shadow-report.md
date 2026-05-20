# 产销存 M5 Shadow Compare Report

version: business_analysis_inventory_sales_production_m5_shadow_compare.v1
shadow_only: true
formal_qa_executed: false
live_db_executed: false
total: 11
matched_count: 7
fail_closed_count: 4
expected_status_mismatch_count: 0

## by_status
- matched: 7
- queryplan_clarification: 1
- queryplan_unsupported: 2
- sqlplan_validation_failed: 1

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

# NL2SQL Logistics M7 Readonly Middle DB Shadow Smoke Evaluation Report

## Summary
- total: 2
- success_count: 2
- failure_count: 0
- skipped_count: 0
- unsupported_count: 0
- success_rate: 1.0000
- fail_closed_count: 0
- safety_block_count: 0
- safety_pass_count: 2
- executor_touched_count: 2
- executor_not_touched_count: 0
- expected_status_match_count: 0
- expected_status_mismatch_count: 0
- expected_status_match_rate: 0.0000
- execution_failure_count: 0
- sql_hash_coverage: 1.0000
- catalog_ref_coverage: 0.0000
- distinct_catalog_ref_count: 0

## By Status
- success: 2

## By Stage
- trial: 2

## Top Errors
- none

## Sample Outcomes
| sample_id | description | status | stage | error_codes |
| --- | --- | --- | --- | --- |
| m7_success_valid_ranking | 合法 SQLPlan + 真实只读中间库 EXPLAIN/trial smoke（ranking） | success | trial |  |
| m7_success_valid_aggregate | 合法 SQLPlan + 真实只读中间库 EXPLAIN/trial smoke（aggregate） | success | trial |  |

## Warnings
- M7 readonly middle-db shadow smoke only; production QA chain is not connected

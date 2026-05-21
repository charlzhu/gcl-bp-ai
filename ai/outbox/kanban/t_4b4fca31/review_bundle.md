# M5-6 Shadow Expansion Review Bundle

## Scope
- Task: t_4b4fca31 / ISP M5-6 shadow expansion
- Branch: feature/isp-m5-6-shadow-expansion
- Goal: extend default inventory-sales-production M5 shadow samples to 30+ and verify shadow-only QueryPlan/SQLPlan compare remains fail-closed and redacted.

## Scoped changed files
- backend/app/domains/business_analysis/services/inventory_sales_production/m5_shadow_compare.py
- tests/unit/business_analysis/test_inventory_sales_production_m5_shadow_compare.py
- ai/outbox/kanban/t_4b4fca31/test.log
- ai/outbox/kanban/t_4b4fca31/m5-inventory-sales-production-shadow-report.md
- ai/outbox/kanban/t_4b4fca31/m5-inventory-sales-production-shadow-records.jsonl
- ai/outbox/kanban/t_4b4fca31/diff.patch
- ai/outbox/kanban/t_4b4fca31/review_bundle.md
- ai/outbox/kanban/t_4b4fca31/review-result.json
- ai/outbox/kanban/t_4b4fca31/final-acceptance.md

## Diff artifact
- ai/outbox/kanban/t_4b4fca31/diff.patch

## Verification summary
All commands completed with exit code 0. Full details are in ai/outbox/kanban/t_4b4fca31/test.log.

- focused GREEN: 1 passed
- review-fix RED/GREEN: new period-boundary error-code redaction test failed before fix, then passed after sanitization
- regression shadow compare tests: 13 passed
- M2/M3/M4/M4-6 inventory-sales-production regression: 85 passed
- logistics focused regression: 22 passed
- plan BOM / power focused regression: 21 passed
- compile: py_compile passed for m5_shadow_compare.py, runner, and unit test
- backend compileall: passed
- runner: total 31 shadow samples, matched 20, fail-closed 11, expected_status_mismatch_count 0
- artifact-check: 31 records, all shadow_only, formal_qa_executed=false, live_db_executed=false, no forbidden raw SQL/credential fragments in persisted artifacts
- static scan: added_lines=394, findings=0
- diff-check: git diff --check passed
- cached diff check: final pre-commit `git diff --cached --check` passed after evidence-only trailing whitespace cleanup

## Shadow report summary
- total: 31
- matched_count: 20
- fail_closed_count: 11
- expected_status_mismatch_count: 0
- by_status: matched=20, queryplan_clarification=3, queryplan_unsupported=4, sqlplan_candidate_unavailable=1, sqlplan_validation_failed=3
- period-boundary SQLPlan validation error is persisted as sqlplan_unpublished_month_blocks_sql_direct::[PERIOD_BOUNDARY], not concrete year/month values.

## Review feedback addressed before final review
- First independent review passed and suggested stronger assertions: baseline ordering now locks first 11 samples, M5-6 expected IDs list all added samples, and a direct no-time default-scope guard sample was added.
- Second independent review found a blocking artifact redaction issue: SQLPlan unpublished-month error codes persisted concrete period boundary values. A RED test was added, then `_dedupe_safe_texts` now redacts that error code to a safe `[PERIOD_BOUNDARY]` marker before JSONL/Markdown persistence; full verification was rerun.
- Final independent review passed with `security_concerns=[]`, `logic_errors=[]`, `suggestions=[]`; verdict saved to `review-result.json`.

## Review focus
1. Check the M5-6 default sample expansion is business-relevant and reaches 30+ without replacing the original M4-6 baseline ordering.
2. Check matched samples use independent SQLPlan fixtures, not QueryPlan reverse-generation.
3. Check fail-closed guard samples are safe: future/unpublished month, unsupported comparison, unknown metric clarification, explicit multi-year default-scope missing candidate, direct no-time default-scope guard, and raw/debug/internal candidate rejection.
4. Check persisted artifacts and summaries do not leak raw SQL text, concrete period boundary values, user questions, credentials, host/user/password/DSN, or connection strings.
5. Check tests assert the new requirements and do not overfit to implementation internals beyond the established shadow fixture contract.

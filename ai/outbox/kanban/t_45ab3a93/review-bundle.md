# t_45ab3a93 review bundle

## Task
M5-4R final quality gate after t_3ca95bf9 shadow fix.

Acceptance to verify:
- M5 focused tests pass.
- Inventory-sales-production M2/M3/M4/M4-6 regression passes.
- Necessary logistics, plan BOM, and power focused regression passes.
- Backend compileall passes.
- Frontend npm build passes.
- Static scan for secret/connection-string and SQL/raw/debug/internal leakage passes.
- M5 shadow runner remains shadow-only, no live DB execution, no formal QA takeover.
- Independent review result must be passed=true.
- final-acceptance.md will be written after review.

## Workspace
- Repo: /Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/isp-m5-inventory-nl2sql-integration
- Branch: feature/isp-m5-inventory-nl2sql-integration
- Outbox: ai/outbox/kanban/t_45ab3a93
- Full scoped diff: ai/outbox/kanban/t_45ab3a93/diff.patch
- Test log: ai/outbox/kanban/t_45ab3a93/test.log
- Static scan: ai/outbox/kanban/t_45ab3a93/static-scan.log and .json
- Shadow report: ai/outbox/kanban/t_45ab3a93/m5-inventory-sales-production-shadow-report.md
- Shadow records: ai/outbox/kanban/t_45ab3a93/m5-inventory-sales-production-shadow-records.jsonl
- Git status snapshot: ai/outbox/kanban/t_45ab3a93/git-status.txt

## Scope to review
Source/test/runner from parent fix, still untracked in this worktree:
- backend/app/domains/business_analysis/services/inventory_sales_production/m5_shadow_compare.py
- scripts/dev/run_inventory_sales_production_m5_shadow_compare.py
- tests/unit/business_analysis/test_inventory_sales_production_m5_shadow_compare.py

Current evidence artifacts added by this task:
- ai/outbox/kanban/t_45ab3a93/test.log
- ai/outbox/kanban/t_45ab3a93/static-scan.log
- ai/outbox/kanban/t_45ab3a93/static-scan.json
- ai/outbox/kanban/t_45ab3a93/diff.patch
- ai/outbox/kanban/t_45ab3a93/git-status.txt
- ai/outbox/kanban/t_45ab3a93/m5-inventory-sales-production-shadow-records.jsonl
- ai/outbox/kanban/t_45ab3a93/m5-inventory-sales-production-shadow-report.md

## Verification results from test.log
- M5 focused shadow compare: 11 passed, exit 0.
- M2/M3/M4/M4-6 inventory-sales-production regression: 85 passed, exit 0.
- Existing logistics focused regression: 22 passed, exit 0.
- Existing plan BOM and power focused regression: 21 passed, exit 0.
- Backend compileall backend/app: exit 0.
- Frontend npm run build: exit 0; only existing Vite chunk-size warning.
- M5 shadow compare dev runner: exit 0; total 11, matched 7, fail_closed_count 4, expected_status_mismatch_count 0, shadow_only true, formal_qa_executed false, live_db_executed false.

## Static scan summary
static scan passed: true
findings: none
Targets include M5 source, runner, focused tests, current shadow artifacts, test.log, static-scan.log/json.

## Git status note
The pre-run status already had prior untracked parent/task artifacts and the three M5 source/test/runner files. Frontend build updated tracked frontend/tsconfig.tsbuildinfo by adding the already tracked frontend/src/api/inventorySalesProduction.ts to the TypeScript buildinfo root list. No push/merge/deploy/commit was performed.

## Reviewer focus
Please fail closed if any of these are true:
1. Shadow compare can execute live DB / formal QA / free SQL, or artifacts show live_db_executed/formal_qa_executed true.
2. Period comparison can false-match different concrete year/month/quarter/YTD values after redaction.
3. Missing independent SQLPlan candidate can be accepted or generated from QueryPlan self-comparison.
4. Secret/DSN/Bearer/raw SQL is persisted in generated artifacts.
5. Current evidence is insufficient or inconsistent with task acceptance.
6. The frontend buildinfo modification is a blocking task-scope issue rather than a generated build artifact that should simply be documented.

Return only JSON verdict in review-result.json shape.

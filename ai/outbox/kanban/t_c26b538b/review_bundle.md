# t_c26b538b focused review bundle

## Task
NQE-SQL-MAIN-12: implement EXPLAIN validate and correct-SQL loop between safety precheck and readonly execution.

## Scope reviewed
- backend/app/domains/business_qa_graph/nqe_sql_agent_graph.py
- tests/unit/business_qa_graph/test_nqe_sql_agent_explain_correct.py
- ai/outbox/kanban/t_c26b538b/* evidence files

Do not review or modify unrelated dirty worktree files listed in git-status.log.

## Key implementation summary
- Added deterministic offline explain validation helpers in nqe_sql_agent_graph.py.
- explain_validate_sql now checks safe candidate projections against table_columns / columns_by_table / table_column_whitelist metadata from retrieval_context_package.
- Projection validation extracts simple identifiers, quoted identifiers, and identifiers inside aggregate/function expressions; single-quoted constants and numeric constants remain ignored.
- correct_sql now uses only explicit retrieval_context_package correction candidates, records revision metadata, and routes back through precheck_sql_safety before another explain/execute step.
- No database connection was added. No free model-generated correction was added.
- Existing force_explain_fail test hook remains supported.

## Reviewer fix history
- First Codex read-only review failed due fail-open projection validation for SUM(missing_metric) and quoted identifiers.
- Added RED regression: reviewer-red-test.log shows the new reviewer case failed before the fix.
- Implemented expression identifier extraction and reran GREEN: reviewer-green-test.log shows the reviewer case passed.

## Verification evidence
- RED: ai/outbox/kanban/t_c26b538b/red-test.log shows the initial new tests failed before implementation: 2 failed.
- GREEN: ai/outbox/kanban/t_c26b538b/green-test.log shows the final new test file passed: 3 passed.
- Focused regression: ai/outbox/kanban/t_c26b538b/focused-test.log shows graph skeleton + safety precheck + new tests: 26 passed, 7 warnings.
- py_compile: ai/outbox/kanban/t_c26b538b/py-compile.log completed with exit code 0 and no output.
- Scoped diff check: ai/outbox/kanban/t_c26b538b/diff-check.log has no whitespace-error output.
- Secret scan: ai/outbox/kanban/t_c26b538b/secret-scan.log found 0 matches in scoped files.
- Broader exploratory run: ai/outbox/kanban/t_c26b538b/business-qa-graph-full-dir-test.log shows 213 passed and 22 failed. The failures are outside this task scope, mainly existing builder/adapter/assist tests; they are recorded as non-blocking broader baseline risk, not hidden.

## Known dirty worktree note
This worktree already contains many unrelated untracked/modified files from earlier NQE cards. Review only the focused diff.patch and scoped files above.

## Artifacts
- ai/outbox/kanban/t_c26b538b/diff.patch
- ai/outbox/kanban/t_c26b538b/focused-test.log
- ai/outbox/kanban/t_c26b538b/green-test.log
- ai/outbox/kanban/t_c26b538b/red-test.log
- ai/outbox/kanban/t_c26b538b/reviewer-red-test.log
- ai/outbox/kanban/t_c26b538b/reviewer-green-test.log
- ai/outbox/kanban/t_c26b538b/business-qa-graph-full-dir-test.log
- ai/outbox/kanban/t_c26b538b/git-status.log

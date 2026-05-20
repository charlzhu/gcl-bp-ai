# M10-C live shadow code review bundle

## Scope

- `backend/app/domains/logistics/services/nl2sql/live_shadow_adapter.py`
- `backend/app/domains/logistics/services/data_qa_service.py`
- `tests/unit/logistics/nl2sql/test_m10c_live_shadow_adapter.py`

## Task intent

- In the formal logistics QA branch, add an opt-in NL2SQL live-provider shadow adapter.
- Default must be disabled and must not instantiate recall / LLM / pipeline provider dependencies.
- When explicitly enabled, run: query rewrite -> domain route -> catalog recall -> SQLPlan generator -> M10-B shadow pipeline, still shadow-only.
- Raw candidate SQL, if supplied, must go through the existing M10-B candidate SQL gate and never be executed or exposed.
- Main `LogisticsDataQaResult` must not be mutated; only server-side query-history `response_meta` may receive a sanitized `nl2sql_live_shadow` summary.
- Adapter exceptions must fail closed and must not break formal QA/history write.
- `nl2sql_live_shadow` is treated as history/detail-visible metadata, so error metadata must be public-safe: error messages are generic, error codes are mapped to M10-C/M10-B stable allowlist codes, identifier suffixes are discarded/redacted.
- No user-visible SQL/table/field/provider/debug payload may be exposed.

## Reviewer concern addressed

Previous independent review failed because arbitrary generator/pipeline error codes could contain `::<table/field>` or provider/debug details. The final patch now:

- maps unknown error codes to `m10c_error_redacted`;
- preserves only `m10c_generation_not_ok::<safe_status>` and `candidate_sql_gate_rejected::<safe_reason>` allowlisted suffixes;
- maps arbitrary `candidate_sql_gate_reason_code` to a fixed M10-B reason enum or `redacted`;
- maps arbitrary `error_message` to `shadow error redacted`, except the known fallback message `shadow audit failed`;
- adds tests for SQLPlan/table/field/provider/debug leakage and adapter exception fallback.

## Final tests already run

See `ai/outbox/kanban/t_15f6d558/test.log`.

- `python -m pytest tests/unit/logistics/nl2sql/test_m10c_live_shadow_adapter.py -q` -> 6 passed
- `python -m pytest tests/unit/logistics/nl2sql/test_candidate_sql_gate.py tests/unit/logistics/nl2sql/test_shadow_pipeline.py tests/unit/logistics/nl2sql/test_m9_sqlplan_generation.py tests/unit/logistics/nl2sql/test_m10c_live_shadow_adapter.py -q` -> 72 passed
- `python -m pytest tests/unit/logistics/nl2sql -q` -> 226 passed, 9 dependency warnings
- `python -m pytest tests/unit/query_planning/test_query_planning_phase5_shadow_compare.py tests/unit/query_planning/test_query_planning_phase5_gray_log_report.py tests/business_acceptance/test_logistics_field_scope_clarification.py -q` -> 15 passed
- `python -m compileall backend/app/domains/logistics/services/nl2sql -q` -> passed
- `git diff --check` -> passed

## Static scan summary

- Production scoped files searched for secret-like keys, DB URLs, dangerous shell/eval/pickle, f-string SQL and fake dangerous SQL terms.
- There are no hardcoded credentials, DB URLs, subprocess/shell/eval/exec/pickle, or raw production SQL statements.
- The only scoped production hits are safe code/comment words such as `token` in sanitizer helper names and comments about preventing SQL/table/field leakage.
- Test file intentionally contains fake dangerous SQL/secret/provider strings as negative redaction assertions; do not treat those as production secret exposure.

## Patch path

- `/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/nl2sql-m10c-live-shadow-gate/ai/outbox/kanban/t_15f6d558/diff.patch`

## Review focus

Fail if any of these are true:

- default disabled path can instantiate provider dependencies;
- enabled shadow can mutate user-visible `LogisticsDataQaResult`;
- raw SQL can bypass candidate SQL gate or appear in summary/history metadata;
- shadow exceptions can break formal QA/history or leak secrets in logs/summary;
- code writes raw SQL, provider payloads, table/field names, credentials, or debug internals into user-visible output;
- fallback audit path bypasses sanitized summary schema;
- live-shadow error metadata can still expose internal table/field/provider/debug details in query-history response metadata.

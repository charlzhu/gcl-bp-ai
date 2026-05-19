# NL2SQL M7 Readonly Middle DB Smoke Focused Review Bundle

## Scope

Task: `t_1fceb427` — logistics NL2SQL M7 readonly middle DB shadow smoke MVP.
Branch: `feature/nl2sql-m7-readonly-middle-db-smoke`.

Changed source/test/docs files under review:

- `backend/app/domains/logistics/services/nl2sql/readonly_middle_db.py`
- `backend/app/domains/logistics/services/nl2sql/m7_readonly_smoke.py`
- `backend/app/domains/logistics/services/nl2sql/__init__.py`
- `scripts/dev/run_logistics_nl2sql_m7_readonly_smoke.py`
- `tests/unit/logistics/nl2sql/test_m7_readonly_middle_db_smoke.py`
- `docs/NL2SQL_LOGISTICS_M7_READONLY_MIDDLE_DB_SMOKE_MVP_PLAN.md`

Focused diff:

- `ai/outbox/kanban/t_1fceb427/diff.patch`

Generated verification artifacts:

- `ai/outbox/kanban/t_1fceb427/test.log`
- `ai/outbox/kanban/t_1fceb427/static-scan.json`
- `ai/outbox/kanban/t_1fceb427/m7-shadow-smoke-report.md`
- `ai/outbox/kanban/t_1fceb427/m7-shadow-smoke-records.jsonl`

Known unrelated dirty files not in review scope:

- `docs/INVENTORY_SALES_PRODUCTION_EXCEL_AUDIT.md`
- `docs/INVENTORY_SALES_PRODUCTION_NL2SQL_COMPAT_PLAN.md`

## Requirements to Review

Please fail closed on any of these issues:

1. Real DB path can perform writes or non-SELECT statements.
2. Executor can bypass the M4 safety gate in the M7 runner.
3. Trial SELECT can execute unbounded or with LIMIT > 20.
4. SQL is string-concatenated with parameter values instead of bound parameters.
5. `.env` host/user/password/database/full DSN/API key/token can leak into JSONL, Markdown, CLI output, or errors.
6. Real SQL text can leak into generated M7 reports.
7. M7 accidentally connects the formal logistics QA main chain instead of remaining shadow-only.
8. New script violates AGENTS.md command-safety rules or uses temporary token mechanisms.
9. Existing logistics/BOM capabilities are affected outside the scoped NL2SQL shadow package.

## Post-Review Fix Context

A previous independent review failed because direct `LogisticsReadonlyMiddleDbExecutor.trial()` accepted bounded but dangerous SELECT variants such as `SELECT ... INTO OUTFILE ... LIMIT 1` before driver execution.

Implemented fixes:

- DB executor rejects unsafe SELECT variants before driver: SQL comments, `INTO OUTFILE`, `INTO DUMPFILE`, `UNION`, `LOAD_FILE`, `FOR UPDATE`, `LOCK IN SHARE MODE`, `PROCEDURE ANALYSE`, `SLEEP`, `BENCHMARK`.
- M7 runner clamps caller-supplied `trial_limit` / `max_limit` to hard upper bound `20` before safety checker and execution service construction.
- Public package `__init__.py` no longer re-exports direct readonly DB config/executor helpers; M7 exports remain runner/sample API only.
- Recovery pass also addressed the previous non-blocking suggestion by adding explicit tests for `FOR UPDATE`, `LOCK IN SHARE MODE`, `PROCEDURE ANALYSE`, `SLEEP`, and `BENCHMARK`.

## Verification Summary

Recorded in `ai/outbox/kanban/t_1fceb427/test.log` after recovery:

- `backend/.venv/bin/python -m pytest tests/unit/logistics/nl2sql/test_*m7*.py -q` → 23 passed.
- `backend/.venv/bin/python -m pytest tests/unit/logistics/nl2sql -q` → 156 passed, 9 warnings from existing pymilvus/pkg_resources deprecations.
- `backend/.venv/bin/python -m pytest tests/unit/logistics -q` → 170 passed, 9 same warnings.
- `backend/.venv/bin/python -m pytest tests/unit -q` → 214 passed, 9 same warnings.
- `backend/.venv/bin/python -m py_compile backend/app/domains/logistics/services/nl2sql/readonly_middle_db.py backend/app/domains/logistics/services/nl2sql/m7_readonly_smoke.py scripts/dev/run_logistics_nl2sql_m7_readonly_smoke.py` → passed.
- `backend/.venv/bin/python scripts/dev/run_logistics_nl2sql_m7_readonly_smoke.py --artifact-dir ai/outbox/kanban/t_1fceb427` → live smoke executed, environment_status available, total 2, success 2, success_rate 1.0.
- `git diff --check` → passed.

Static scan artifact: `ai/outbox/kanban/t_1fceb427/static-scan.json`.

- Production hardcoded secret/dangerous pattern scan: passed.
- M7 generated artifact leak scan for SQL/DSN/token patterns: passed.
- One `unit-password` fixture in the unit test is intentional artificial test data for redaction and not a real secret.

## Key Implementation Points

- `readonly_middle_db.py` loads only `MYSQL_*` config from a provided `.env` path and returns a JSON-safe load result that excludes the in-memory config.
- `LogisticsReadonlyMiddleDbExecutor` only exposes `explain()` and `trial()`; it rejects multi-statement SQL, non-`EXPLAIN SELECT`, non-`SELECT`, missing trial LIMIT, invalid LIMIT, LIMIT above config upper bound, and dangerous SELECT variants before opening a DB connection.
- Renderer `:name` params are converted to PyMySQL `%(name)s` placeholders; values remain bound parameters.
- `m7_readonly_smoke.py` builds a shadow-only runner from existing M6 success samples, uses `LogisticsSqlExecutionService` with `LogisticsSqlSafetyChecker`, writes redacted JSONL/Markdown artifacts, and treats DB config/connection unavailable as environment-unavailable rather than fake success.
- CLI script only prints a redacted JSON summary and returns nonzero on environment unavailable.

## Reviewer Output Contract

Return only JSON:

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": [],
  "suggestions": [],
  "summary": "one sentence verdict"
}
```

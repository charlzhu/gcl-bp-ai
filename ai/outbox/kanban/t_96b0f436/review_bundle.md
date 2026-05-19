# Review bundle: t_96b0f436 NL2SQL M4 (post-review-fix)

## Scope

Implement logistics-only controlled NL2SQL M4 MVP:
- deterministic SQL renderer from M3 validated `LogisticsSqlPlanValidationResult` to parameterized read-only SELECT;
- SQL Safety Checker second-pass validation for SELECT-only, single statement, allow-listed tables/columns, no comments/DDL/DML/UNION/dangerous functions, params, joins, controlled LIMIT syntax, and SELECT INTO/OUTFILE/DUMPFILE denial;
- EXPLAIN/trial execution service with injectable executor, safety gate, bound params, trial limit, and sanitized errors.

Must not connect formal QA path, frontend, DB migrations, SAP Oracle MID, or LLM raw SQL.

## Reviewer blocking findings from first pass and fixes

1. Non-catalog join could pass when `referenced_joins` was non-empty.
   - Fixed: Safety now parses SQL JOIN clauses and compares count/type/table/ON expression against canonical catalog joins.
   - Tests: `test_safety_rejects_join_clause_mismatch_even_when_join_id_is_present`.
2. Uncontrolled LIMIT syntax (`LIMIT ALL`, `LIMIT 0, 999999`, `LIMIT ... OFFSET ...`) could bypass trial cap.
   - Fixed: Safety now accepts only renderer-shaped terminal `LIMIT :param` or literal integer within max.
   - Tests: `test_safety_rejects_non_renderer_limit_syntax`, `test_trial_rejects_uncontrolled_limit_syntax_before_executor`.
3. SELECT INTO / OUTFILE / DUMPFILE were not explicitly blocked.
   - Fixed: Safety now forbids `into`, `outfile`, and `dumpfile` tokens.
   - Tests: `test_safety_rejects_select_into_and_file_export_tokens`.
4. Renderer/safety catalog boundary should mirror hard allow-list.
   - Fixed: Safety intersects loaded catalog tables with `LOGISTICS_NL2SQL_ALLOWED_READ_TABLES`, logistics domain, and `middle_db` source.

## Changed files

- `backend/app/domains/logistics/services/nl2sql/__init__.py`
- `backend/app/domains/logistics/services/nl2sql/sql_renderer.py`
- `backend/app/domains/logistics/services/nl2sql/sql_safety.py`
- `backend/app/domains/logistics/services/nl2sql/sql_execution.py`
- `tests/unit/logistics/nl2sql/test_sql_renderer.py`
- `tests/unit/logistics/nl2sql/test_sql_safety.py`
- `tests/unit/logistics/nl2sql/test_sql_execution.py`

## Verification summary

- 28 passed in 1.84s
- =============================== warnings summary ===============================
- -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
- 79 passed, 9 warnings in 2.72s
- =============================== warnings summary ===============================
- -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
- 107 passed, 9 warnings in 4.14s
- =============================== warnings summary ===============================
- -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
- 151 passed, 9 warnings in 5.14s
- py_compile passed
- git diff --check scoped files passed
- ruff not installed; skipped

## Static scan

```json
{
  "task_id": "t_96b0f436",
  "scope": "added lines in ai/outbox/kanban/t_96b0f436/diff.patch",
  "patterns": [
    "hardcoded_secret_assignment",
    "shell_injection",
    "dangerous_eval_exec",
    "unsafe_pickle",
    "sql_string_formatting"
  ],
  "finding_count": 0,
  "findings": [],
  "passed": true
}
```

## Patch

Full scoped patch is saved at `/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/ai/outbox/kanban/t_96b0f436/diff.patch` and contains only task source/test files.

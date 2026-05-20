# review

## static scan

Source: `compile-static-scan.log` after final tree.

- hardcoded secret assignment: no matches
- raw SQL direct execution: no matches
- shell injection / dangerous eval: no matches
- unsafe deserialization: no matches
- main QA route takeover: no matches
- `git diff --check`: exit 0
- `compileall backend/app/domains/logistics/services/nl2sql`: exit 0

## independent review cycle

### first independent review

Result: failed.

Findings:

1. `SELECT ... INTO @x ... LIMIT 1` could pass as a generic SELECT-like shape.
2. `GET_LOCK()` / `RELEASE_LOCK()` side-effect lock functions were not explicitly blocked.
3. Unknown body between `FROM <table>` and final `LIMIT`, e.g. `RANDOM_GARBAGE`, could pass.
4. Extremely long LIMIT digits could raise `ValueError` instead of returning a structured rejected result.

TDD recovery:

- Added RED regression coverage in `review-fix2-red.log`; it failed with 5 expected failures.
- Fixed only the reported blockers: generic `INTO` rejection, advisory-lock function rejection, no unparsed body between FROM and LIMIT for M10-A, and safe limit-token length/ValueError handling.
- Re-ran focused and full NL2SQL tests after the fix.

### final independent review

Raw JSON verdict returned by the independent reviewer:

```json
{"passed":true,"security_concerns":[],"logic_errors":[],"suggestions":["后续若从 shadow-only 进入可执行链路，建议再加入 SQL parser 与物流表/字段白名单校验。"],"summary":"仅审查 diff 后确认前次发现的 SELECT INTO、GET_LOCK/RELEASE_LOCK、未知子句和超长 LIMIT 问题均已 fail-closed 闭合，未发现本切片范围内阻断问题。"}
```

Final review status: passed.

## scope review

- New gate is shadow-only and not connected to formal logistics QA/chat routes.
- No SQL execution API was added or invoked by the gate.
- `sanitized_reason` uses stable reason codes only and does not echo raw SQL, table names, file paths, credentials, or secret-looking values.
- M10-A remains conservative: only simple `SELECT <list> FROM <table> LIMIT <n>` passes; unknown clauses are rejected until a later parser-backed slice.

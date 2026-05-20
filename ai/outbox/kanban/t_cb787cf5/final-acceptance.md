# final acceptance — t_cb787cf5

## conclusion

M10-A logistics NL2SQL candidate SQL safety gate minimal TDD slice is complete in the task worktree.

The implementation adds a shadow-only conservative candidate SQL gate and does not execute SQL, does not connect to the formal logistics QA/chat route, and does not bypass existing SQLPlan / renderer / readonly-runner safety layers.

## workspace and branch

- Workspace: `/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/nl2sql-m10a-candidate-sql-gate`
- Branch: `feature/nl2sql-m10a-candidate-sql-gate`
- Task id: `t_cb787cf5`
- Base stated by task: `f24d39ae318cea9af081aa05b3edfdcdcf46ef33`

## changed files in task scope

- `backend/app/domains/logistics/services/nl2sql/candidate_sql_gate.py`
- `backend/app/domains/logistics/services/nl2sql/__init__.py`
- `tests/unit/logistics/nl2sql/test_candidate_sql_gate.py`
- `ai/outbox/kanban/t_cb787cf5/*`

Unrelated tracked residue `ai/outbox/kanban/t_7895e090/m8-shadow-eval-records.jsonl` was restored to HEAD before final handoff.

## implemented behavior

The new gate returns structured `allowed/rejected`, stable `reason_code`, sanitized `sanitized_reason`, and optional `repair_info`.

Allowed in this M10-A slice:

- single simple `SELECT <list> FROM <table> LIMIT <number>` with numeric LIMIT within `max_limit`.

Rejected fail-closed:

- empty SQL
- missing LIMIT
- multi-statement semicolon
- comments
- non-SELECT / DDL / DML / transaction tokens
- UNION
- INTO OUTFILE / INTO DUMPFILE / generic SELECT INTO
- LOAD_FILE / SLEEP / BENCHMARK
- GET_LOCK / RELEASE_LOCK / IS_FREE_LOCK / IS_USED_LOCK
- FOR UPDATE / LOCK
- malformed or structure-uncertain SELECT shapes
- unparsed clauses between FROM and final LIMIT in this minimal no-parser slice
- LIMIT outside configured range or with extreme digit count

Visible reasons are stable code strings and do not echo the full SQL or sensitive-looking values.

## TDD evidence

RED evidence:

- `ai/outbox/kanban/t_cb787cf5/red-test.log`
  - expected failure before implementation: `ModuleNotFoundError` for the missing gate module.
- `ai/outbox/kanban/t_cb787cf5/review-fix2-red.log`
  - expected failure after independent review blockers were converted to tests: 5 failures for SELECT INTO, advisory lock functions, unknown body, and extreme LIMIT digits.

GREEN evidence:

- `ai/outbox/kanban/t_cb787cf5/test.log`
  - GREEN focused: `56 passed in 0.98s`, exit 0.
  - Full focused NL2SQL unit suite: `216 passed, 9 warnings in 5.40s`, exit 0.
  - The 9 warnings are third-party deprecation warnings from pymilvus/pkg_resources/google protobuf, not task regressions.

## compile / diff / static scan evidence

Source: `ai/outbox/kanban/t_cb787cf5/compile-static-scan.log`.

- compileall `backend/app/domains/logistics/services/nl2sql`: exit 0.
- `git diff --check`: exit 0.
- `diff.patch` regenerated at `ai/outbox/kanban/t_cb787cf5/diff.patch`.
- static scan: hardcoded secret assignment: no matches.
- static scan: raw SQL direct execution: no matches.
- static scan: shell injection or dangerous eval: no matches.
- static scan: unsafe deserialization: no matches.
- static scan: main QA route takeover: no matches.

## independent review evidence

Source: `ai/outbox/kanban/t_cb787cf5/review.md`.

First independent review failed and found four blockers:

1. Generic `SELECT ... INTO @x` was not rejected.
2. `GET_LOCK()` / `RELEASE_LOCK()` side-effect functions were not explicitly rejected.
3. Unknown text between FROM and final LIMIT could pass.
4. Extremely long LIMIT digits could raise an exception instead of returning structured rejection.

All four were fixed with RED tests first.

Final independent review passed:

```json
{"passed":true,"security_concerns":[],"logic_errors":[],"suggestions":["后续若从 shadow-only 进入可执行链路，建议再加入 SQL parser 与物流表/字段白名单校验。"],"summary":"仅审查 diff 后确认前次发现的 SELECT INTO、GET_LOCK/RELEASE_LOCK、未知子句和超长 LIMIT 问题均已 fail-closed 闭合，未发现本切片范围内阻断问题。"}
```

## required artifacts

- `ai/outbox/kanban/t_cb787cf5/preflight.md`
- `ai/outbox/kanban/t_cb787cf5/implementation-plan.md`
- `ai/outbox/kanban/t_cb787cf5/red-test.log`
- `ai/outbox/kanban/t_cb787cf5/review-fix2-red.log`
- `ai/outbox/kanban/t_cb787cf5/test.log`
- `ai/outbox/kanban/t_cb787cf5/compile-static-scan.log`
- `ai/outbox/kanban/t_cb787cf5/diff.patch`
- `ai/outbox/kanban/t_cb787cf5/review.md`
- `ai/outbox/kanban/t_cb787cf5/final-acceptance.md`
- `ai/outbox/kanban/t_cb787cf5/gate-summary.json`

## git hygiene

Final handoff intentionally did not stage, commit, push, deploy, reset, stash, or clean.

Final observed status before this file was written:

```text
## feature/nl2sql-m10a-candidate-sql-gate
 M backend/app/domains/logistics/services/nl2sql/__init__.py
?? ai/outbox/kanban/t_cb787cf5/
?? backend/app/domains/logistics/services/nl2sql/candidate_sql_gate.py
?? tests/unit/logistics/nl2sql/test_candidate_sql_gate.py

[staged]

[tracked-diff]
backend/app/domains/logistics/services/nl2sql/__init__.py
```

No staged files were present.

## submission note

If a human later decides to submit this work, use scoped staging only. Do not use `git add -A` or `git add .` in this worktree.

# TASK-plan-power-fall-ratio-subrows Review

## Reviewer result

passed=true

## Blocking issues

None.

## Non-blocking notes

- `落档比例预估` now uses a specific display path: split by newline / Chinese semicolon / English semicolon into one efficiency segment per child row.
- Each child row uses `white-space: nowrap`, `word-break: keep-all`, and `overflow-wrap: normal`; the cell container uses horizontal overflow, so a segment does not wrap internally.
- Frontend only splits display strings and does not compute power, CTM, prediction ratio, or probability values.
- Non-fall-ratio columns still use the normal cell renderer and normal tooltip behavior.
- No token/secret restoration found; token strings in tests are negative guard assertions only.
- Full tests have 2 unrelated pre-existing logistics WIP failures; excluding that unrelated file gives `123 passed, 2 warnings`.

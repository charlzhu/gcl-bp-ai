# TASK-plan-power-fall-ratio-subrows Review Bundle

## User request

User clarified that the previous multi-line `落档比例预估` fix was not good enough. They want the detail table to match the attached Excel-like screenshot: each red-box segment should be one independent row/line. Example:

- `25.5%→615W 12.98%、620W 82.08%` is one row.
- `25.6%→615W 2.59%、620W 77.17%` is another row.

The key issue was that the UI wrapped inside each segment, creating multiple visual lines inside one segment. The expected structure is an irregular / Excel-like display: split by efficiency segment, but do not wrap within a segment.

## Scope

Focused task files:

- `frontend/src/views/business-chat/BusinessChatPage.vue`
- `tests/business_acceptance/test_plan_power_frontend_upload_entry.py`

The worktree contains unrelated pre-existing dirty files from earlier tasks. Review should focus on the files above and `ai/tasks/running/TASK-plan-power-fall-ratio-subrows/diff.patch`.

## Implementation summary

- Added frontend helper `isFallRatioEstimateColumn(column)` for the specific `落档比例预估` column.
- Added `splitFallRatioEstimateLines(value)` so both current newline-separated data and older semicolon-separated data are split into one efficiency segment per child row.
- Updated the table template:
  - `落档比例预估` renders a special child-row structure with `v-for` over split segments.
  - Non-fall-ratio columns keep the existing normal cell renderer.
  - Column min-width is dynamic; `落档比例预估` gets wider `420` min-width.
- Added CSS:
  - `.result-table__fall-ratio-lines { overflow-x: auto; }`
  - `.result-table__fall-ratio-line { white-space: nowrap; word-break: keep-all; overflow-wrap: normal; }`
- Added acceptance test `test_business_chat_fall_ratio_estimate_uses_independent_nowrap_segment_rows`.

## TDD / verification evidence

RED:

- `test_business_chat_fall_ratio_estimate_uses_independent_nowrap_segment_rows` failed because `isFallRatioEstimateColumn` / split-line renderer did not exist.

GREEN / verification:

- Focused new test -> `1 passed`.
- Focused table presentation tests -> `2 passed`.
- Related frontend/business presentation contracts -> `17 passed`.
- Frontend build -> passed.
- Compileall for modified Python test -> passed.
- `git diff --check` for focused files -> passed.
- Focused static/secret scan -> passed.
- Browser smoke -> Vite page loaded; scoped CSS verified `overflow-x=auto`, segment line `white-space=nowrap`, `word-break=keep-all`, two segments render as two child rows.
- Full `PYTHONPATH=. python -m pytest tests -q --tb=short` currently has 2 failures in `tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py`; those are unrelated pre-existing logistics WIP dirty files, not touched by this task.
- Full tests excluding that unrelated logistics WIP file -> `123 passed, 2 warnings`.

## Static scan

No focused credential/secret/token findings. Legacy token strings only appear in negative guard assertions in tests.

## Known risk / review focus

- Verify that frontend only splits/labels display strings and does not calculate Plan BOM power/CTM/prediction facts.
- Verify each segment line cannot wrap internally; if content is too long, it should scroll horizontally rather than split within the segment.
- Verify non-`落档比例预估` columns are not affected.

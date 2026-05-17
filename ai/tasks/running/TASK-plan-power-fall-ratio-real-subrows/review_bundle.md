# TASK-plan-power-fall-ratio-real-subrows Review Bundle

## User clarification

The user said the previous fix is close but still not correct:

> 不仅仅是能换行，我要的是再起一行来书写。就像供应商“中润”、“和光同程”就是两行内容一样。

Interpretation: `落档比例预估` must not be just multiple visual lines inside one table cell. Each efficiency segment/red-box should become an actual table sub-row, like normal supplier rows. Other columns in the same original business row should be vertically merged, producing an irregular Excel-like table.

## Focused changed files

- `frontend/src/views/business-chat/BusinessChatPage.vue`
- `tests/business_acceptance/test_plan_power_frontend_upload_entry.py`

The worktree contains unrelated dirty files from earlier tasks. Review only the focused diff:

- `ai/tasks/running/TASK-plan-power-fall-ratio-real-subrows/diff.patch`

## Implementation summary

- `normalizeTable` now calls `expandFallRatioEstimateRows`.
- `expandFallRatioEstimateRows` splits the visible `落档比例预估` value by newline / Chinese semicolon / English semicolon into actual table rows.
- Each expanded row carries display-only metadata:
  - `__resultTableRowSpan`
  - `__resultTableSubRowIndex`
  - `__resultTableSourceRowIndex`
- `<el-table>` now uses `:span-method="getResultTableSpanMethod"`.
- `getResultTableSpanMethod` keeps the `落档比例预估` column as one row per segment and merges all other columns vertically across the expanded segment rows.
- The previous in-cell child-row renderer was removed; there is no longer a `v-for` inside the `落档比例预估` cell.
- The `落档比例预估` cell remains nowrap with horizontal overflow, so an individual segment does not wrap internally.
- Excel export now adds `worksheet['!merges']` via `buildAssistantTableExportMerges`, so exported Excel matches the irregular/merged structure. Non-top merged subrows blank non-fall-ratio cells before merge.
- Frontend still only changes labels/display structure. It does not compute power, CTM, prediction ratio, or probabilities.

## TDD / verification evidence

RED:

- New acceptance test `test_business_chat_fall_ratio_estimate_uses_real_table_subrows_with_rowspan` failed first because `expandFallRatioEstimateRows` and `getResultTableSpanMethod` did not exist.

GREEN / checks:

- New focused test -> `1 passed`.
- Focused frontend table presentation tests -> `2 passed`.
- Related frontend/business presentation contracts -> `17 passed`.
- Frontend build -> passed.
- Compileall modified Python test -> passed.
- Full tests excluding unrelated logistics WIP file -> `123 passed, 2 warnings`.
- Full tests including unrelated dirty logistics WIP currently fail 2 tests in `tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py`; failures are unrelated logistics planner WIP and not caused by this frontend-only task.
- `git diff --check` focused files -> passed.
- Focused static/secret scan -> passed.
- Browser smoke -> Vite loaded; scoped CSS verified `.result-table__cell--fall-ratio` has `white-space=nowrap`, `word-break=keep-all`, `overflow-wrap=normal`; column overflow-x rule is present.

## Review focus

- Does this satisfy the user clarification: actual table rows, not merely cell-internal wrapping?
- Does rowspan merge non-fall-ratio cells correctly while keeping `落档比例预估` one row per segment?
- Does the frontend remain display-only and deterministic-service boundary safe?
- Are hidden metadata keys excluded from displayed columns/exported hidden fields?
- Any token/secret or unrelated task pollution in the focused files?

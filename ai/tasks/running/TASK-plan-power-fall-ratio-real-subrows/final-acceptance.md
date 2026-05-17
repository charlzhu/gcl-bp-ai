# TASK-plan-power-fall-ratio-real-subrows Final Acceptance

## Task

User clarified that `落档比例预估` should not merely wrap lines inside one cell. Each efficiency segment/red-box should start as a real table row, similar to suppliers such as `中润` and `和光同程` being separate table rows.

## Root cause

Previous fix rendered each segment as child text rows inside one `el-table` cell. Visually it was closer, but it was still one data row/cell. The user's expected structure is an irregular Excel-like table:

- `落档比例预估` has one actual row per efficiency segment.
- Other columns for the same supplier/recommendation row are vertically merged across those segment rows.

## Changed files

- `frontend/src/views/business-chat/BusinessChatPage.vue`
- `tests/business_acceptance/test_plan_power_frontend_upload_entry.py`

## Implementation

- `normalizeTable` now calls `expandFallRatioEstimateRows` after column localization.
- `expandFallRatioEstimateRows` splits `落档比例预估` by newline / Chinese semicolon / English semicolon and returns actual expanded rows.
- Each expanded display row carries metadata:
  - `__resultTableRowSpan`
  - `__resultTableSubRowIndex`
  - `__resultTableSourceRowIndex`
- `<el-table>` now uses `:span-method="getResultTableSpanMethod"`.
- `getResultTableSpanMethod`:
  - keeps `落档比例预估` as normal 1-row cells;
  - merges all other columns vertically across the expanded rows.
- Removed the previous in-cell `v-for` renderer for fall-ratio child rows.
- The `落档比例预估` segment text remains nowrap with horizontal overflow if a single segment is very long.
- Excel export now mirrors the irregular table with `worksheet['!merges']`; hidden display metadata is not exported because export still iterates only visible `table.columns`.

## Verification

- RED: `test_business_chat_fall_ratio_estimate_uses_real_table_subrows_with_rowspan` failed before implementation because `expandFallRatioEstimateRows` / `getResultTableSpanMethod` did not exist.
- GREEN new focused test: `1 passed`.
- Focused table presentation tests: `2 passed`.
- Related frontend/business presentation contracts: `17 passed`.
- Frontend build: passed.
- Compileall modified Python test: passed.
- Full tests excluding unrelated logistics WIP file: `123 passed, 2 warnings`.
- Full tests including unrelated dirty logistics WIP: `146 passed, 2 failed, 2 warnings`; failures are in `tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py` and unrelated to this frontend-only table display fix.
- `git diff --check` focused files: passed.
- Focused static/secret scan: passed.
- Browser smoke: Vite page loaded; scoped CSS verified `white-space=nowrap`, `word-break=keep-all`, `overflow-wrap=normal`, and column overflow-x rule exists.
- Reviewer: `passed=true`, no blocking issues.

## Risk

- Because this is now actual row expansion, the displayed row count and exported Excel row count reflect expanded segment rows rather than original supplier/recommendation rows. This matches the user's latest “另起一行” requirement.
- Extremely long single segments will scroll horizontally rather than wrap.

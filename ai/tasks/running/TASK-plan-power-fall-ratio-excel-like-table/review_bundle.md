# TASK-plan-power-fall-ratio-excel-like-table Review Bundle

## User clarification

User said the previous fall-ratio display still did not match the requirement. They uploaded a manually debugged screenshot and asked to follow that format.

The screenshot shows an Excel-like irregular table:

- Columns: `供应商`, `目标功率档`, `目标比例`, `预测比例`, `CTM 值`, `中心功率`, `建议效率段`, `落档比例预估`.
- For each supplier/recommendation row, `落档比例预估` has one actual table row per efficiency segment.
- Other columns are vertically merged across those fall-ratio rows, like Excel merged cells.
- Individual fall-ratio segment text stays on one line.

## Focused changed files

- `frontend/src/views/business-chat/BusinessChatPage.vue`
- `tests/business_acceptance/test_plan_power_frontend_upload_entry.py`

Current worktree has unrelated dirty files from previous tasks. Review focused diff only:

- `ai/tasks/running/TASK-plan-power-fall-ratio-excel-like-table/diff.patch`

## Root cause

The earlier fixes still looked like text/Element-Plus-cell handling. The user-provided screenshot requires a native Excel-like table shape: physical rows for each fall-ratio segment plus vertically merged non-fall-ratio columns. The final fix uses a dedicated native HTML `<table>` renderer only for tables containing `落档比例预估`, and all display/export decisions now resolve through `getAssistantResultTable(message)` so replayed/older raw message tables are normalized before rendering/export.

## Implementation summary

- Backend deterministic output unchanged.
- `normalizeTable` localizes columns and expands `落档比例预估` into display rows with metadata:
  - `__resultTableRowSpan`
  - `__resultTableSubRowIndex`
  - `__resultTableSourceRowIndex`
- Added `getAssistantResultTable(message)` so table row count, summary, layout, export, and replayed messages all use the normalized/expanded visible table instead of raw `message.presentation.table`.
- `shouldUseIrregularResultTable(message)` now uses `getAssistantResultTable(message)` directly, fixing reviewer blocker about replayed/raw message compatibility.
- For tables with `落档比例预估`, template uses native `<table class="result-table result-table--irregular">` rather than Element Plus `<el-table>`.
- Native table renders:
  - one `<tr>` per fall-ratio segment;
  - `<td rowspan="...">` for non-fall-ratio columns on the first segment row;
  - no non-fall-ratio cells on subsequent segment rows;
  - fall-ratio cell on every segment row.
- Normal tables still use Element Plus `<el-table>` fallback via `v-else`.
- CSS explicitly sets native irregular table grid/borders, vertical centering, header stickiness, nowrap fall-ratio cells, and horizontal overflow.
- Excel export uses the same visible table, writes `worksheet['!merges']`, and does not export display metadata keys.

## Verification

TDD RED:

- `test_business_chat_fall_ratio_estimate_uses_excel_like_irregular_rows` failed first because `shouldUseIrregularResultTable` / native irregular table renderer did not exist.
- Additional RED failed because display/export did not yet resolve through `getAssistantResultTable` for replayed/raw message tables.
- Reviewer then found `shouldUseIrregularResultTable()` itself still read raw `message.presentation.table`; a tighter test using regex failed until the function was changed to use `getAssistantResultTable(message)`.

GREEN / checks:

- New focused test: passed.
- Related frontend/business presentation contracts: `17 passed`.
- Frontend build: passed.
- Compileall modified Python test: passed.
- Full tests excluding unrelated dirty logistics WIP: `123 passed, 2 warnings`.
- Full tests including current unrelated dirty logistics WIP: `147 passed, 1 failed, 2 warnings`; failing test is `tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py::test_logistics_ranking_branches_parse_variable_top_n`, unrelated logistics WIP.
- Focused `git diff --check`: passed.
- Focused static/secret scan: passed.
- Browser smoke: Vite page loaded. Scoped native irregular table CSS verified with Vue `data-v-*`: `tbody tr count=2`, `rowspan=2`, `border-collapse=collapse`, `vertical-align=middle`, fall-ratio `white-space=nowrap`, `word-break=keep-all`, container `overflow-x=auto`.

## Review focus

- Does the native table DOM match the user's attached screenshot format better than Element Plus row/cell rendering?
- Does every fall-ratio segment become a physical `<tr>` while other columns are merged with native `rowspan`?
- Does display/export use the normalized visible table for both new and replayed raw messages?
- Does it avoid calculating any business numbers in the frontend?
- Are normal tables unaffected?
- Is export metadata safe and no secrets/tokens restored?

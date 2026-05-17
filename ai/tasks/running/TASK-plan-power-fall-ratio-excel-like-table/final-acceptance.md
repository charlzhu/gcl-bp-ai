# TASK-plan-power-fall-ratio-excel-like-table Final Acceptance

## Task

User uploaded a manually debugged screenshot and clarified that `落档比例预估` should follow an Excel-like irregular table format:

- not text wrapping inside one cell;
- not internal spans inside an Element Plus cell;
- each fall-ratio / efficiency segment should be a real table row;
- other columns, such as `供应商`, `目标功率档`, `目标比例`, `预测比例`, `CTM 值`, `中心功率`, `建议效率段`, should be vertically merged across those rows.

## Root cause

Previous fixes still treated the requirement as cell-level wrapping or cell-level subcontent. The screenshot showed a true irregular table: physical rows for `落档比例预估`, plus rowspan-like merged cells for the rest of the recommendation row.

## Changes

Focused files:

- `frontend/src/views/business-chat/BusinessChatPage.vue`
- `tests/business_acceptance/test_plan_power_frontend_upload_entry.py`

Implemented behavior:

1. Keep backend deterministic calculation unchanged.
2. Normalize/detail-table rendering now uses `getAssistantResultTable(message)` so new and replayed/raw messages are both normalized before display/export.
3. When a table contains `落档比例预估`, render it with a native HTML table:
   - `<table class="result-table result-table--irregular">`
   - one `<tr>` per fall-ratio segment;
   - non-fall-ratio columns render only on the first subrow;
   - non-fall-ratio cells use native `rowspan`;
   - fall-ratio cells render once per subrow.
4. Normal tables still use the Element Plus `<el-table>` path.
5. CSS matches the screenshot-style table:
   - collapsed grid borders;
   - vertical centering for merged cells;
   - sticky header;
   - `落档比例预估` segment text stays nowrap;
   - horizontal overflow is allowed when a segment is too long.
6. Excel export uses the same visible normalized table, writes `worksheet['!merges']`, and does not export internal metadata keys.

## TDD and verification

RED:

- New test failed first because native irregular table renderer did not exist.
- A second RED captured replayed/raw message compatibility: display/export needed to resolve through `getAssistantResultTable(message)`.
- Reviewer found one blocker where `shouldUseIrregularResultTable` still read raw `message.presentation.table`; a stricter regex assertion failed until fixed.

GREEN / checks:

- Focused fall-ratio irregular table test: passed.
- Related frontend/business presentation contracts: `17 passed`.
- Frontend build: passed.
- Compileall modified Python test: passed.
- Full tests excluding unrelated dirty logistics WIP: `123 passed, 2 warnings`.
- Full tests including current unrelated dirty logistics WIP: `147 passed, 1 failed, 2 warnings`; failing test is unrelated logistics WIP: `tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py::test_logistics_ranking_branches_parse_variable_top_n`.
- Focused `git diff --check`: passed.
- Focused static/secret scan: passed.
- Browser smoke: verified scoped CSS with Vue `data-v-*`:
  - `tbody tr count=2`
  - `rowspan=2`
  - `border-collapse=collapse`
  - `vertical-align=middle`
  - fall-ratio `white-space=nowrap`
  - fall-ratio `word-break=keep-all`
  - container `overflow-x=auto`

## Reviewer

Final reviewer result: `passed=true`, blocking issues none.

## Artifacts

- `ai/tasks/running/TASK-plan-power-fall-ratio-excel-like-table/test.log`
- `ai/tasks/running/TASK-plan-power-fall-ratio-excel-like-table/diff.patch`
- `ai/tasks/running/TASK-plan-power-fall-ratio-excel-like-table/review_bundle.md`
- `ai/tasks/running/TASK-plan-power-fall-ratio-excel-like-table/review.md`
- `ai/tasks/running/TASK-plan-power-fall-ratio-excel-like-table/final-acceptance.md`

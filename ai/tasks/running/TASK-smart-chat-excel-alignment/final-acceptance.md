# TASK-smart-chat-excel-alignment Final Acceptance

## Task

用户要求下载的智能助手明细 Excel 内容格式调整为：

- 垂直居中
- 左对齐

## Root cause

The existing export created a worksheet and merges, but did not assign alignment styles to cells. A plain `xlsx` CE writer also does not truly serialize `cell.s.alignment` into `xl/styles.xml`, so merely adding `cell.s` while keeping `xlsx` would not satisfy the downloaded-file requirement.

## Changes

Focused files:

- `frontend/src/views/business-chat/BusinessChatPage.vue`
- `tests/business_acceptance/test_plan_power_frontend_upload_entry.py`
- `frontend/package.json`
- `frontend/package-lock.json`

Implementation:

1. Added `xlsx-js-style@^1.2.0` for the smart-chat detail export path.
2. Changed BusinessChatPage export import from `xlsx` to `xlsx-js-style`.
3. Added `applyAssistantTableExportAlignment(worksheet)`.
4. `exportAssistantTableToExcel` now calls this helper after worksheet creation and merge setup.
5. The helper walks `worksheet['!ref']` with `XLSX.utils.decode_range` / `XLSX.utils.encode_cell` and sets every existing exported cell:

```ts
alignment: {
  vertical: 'center',
  horizontal: 'left',
}
```

6. Existing behavior preserved:
   - export uses normalized visible table via `getAssistantResultTable(message)`;
   - `worksheet['!merges']` for irregular fall-ratio tables is kept;
   - internal `__resultTable*` metadata is still not exported;
   - normal empty-table warning and success message remain unchanged;
   - logistics export still uses the original `xlsx` path and is not modified.

## TDD

RED:

- Added contract assertions requiring:
  - `xlsx-js-style` import/dependency;
  - `applyAssistantTableExportAlignment`;
  - `XLSX.utils.decode_range` / `XLSX.utils.encode_cell`;
  - `vertical: 'center'`;
  - `horizontal: 'left'`;
  - `cell.s =`.
- Focused test failed before implementation because the helper did not exist.

GREEN:

- Focused export test passed after implementation.

## Verification

- Focused export test: passed.
- Related presentation tests excluding unrelated streaming WIP: `17 passed, 1 deselected`.
- Full tests excluding unrelated dirty logistics and streaming WIP tests: `131 passed, 1 deselected, 2 warnings`.
- Full tests including current unrelated WIP: `155 passed, 2 failed, 2 warnings`:
  - unrelated logistics WIP: `test_logistics_ranking_branches_parse_variable_top_n`
  - unrelated streaming WIP: `test_business_chat_uses_backend_llm_streaming_answer_pipeline`
- Frontend build: passed.
- Compileall touched test: passed.
- Focused `git diff --check`: passed.
- Focused static/secret scan: passed.
- Package-level XLSX verification: generated a sample file with `xlsx-js-style` and inspected `xl/styles.xml`; `horizontal="left"` and `vertical="center"` were present.
- Reviewer: `passed=true`, no blocking issues.

## Artifacts

- `ai/tasks/running/TASK-smart-chat-excel-alignment/test.log`
- `ai/tasks/running/TASK-smart-chat-excel-alignment/diff.patch`
- `ai/tasks/running/TASK-smart-chat-excel-alignment/review_bundle.md`
- `ai/tasks/running/TASK-smart-chat-excel-alignment/review.md`
- `ai/tasks/running/TASK-smart-chat-excel-alignment/final-acceptance.md`

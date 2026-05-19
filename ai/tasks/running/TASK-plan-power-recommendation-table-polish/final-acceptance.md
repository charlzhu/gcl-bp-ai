# TASK-plan-power-recommendation-table-polish Final Acceptance

## Task

Fix Plan BOM power QA supplier recommendation detail table based on user screenshot feedback:

1. Remove explanation copy for `预测比例` and `中心功率`.
2. Rename `指标5` / `CTM值` to `CTM 值`.
3. Display `落档比例预估` in multiple lines so each efficiency segment is readable.

## Changed files

- `backend/app/domains/plan_bom/services/qa_service.py`
- `frontend/src/views/business-chat/BusinessChatPage.vue`
- `tests/business_acceptance/test_plan_power_real_business_qa_regression.py`
- `tests/business_acceptance/test_plan_power_docx_question_regression.py`
- `tests/business_acceptance/test_plan_power_m5_qa_integration.py`
- `tests/business_acceptance/test_plan_power_frontend_upload_entry.py`

## Result

- Backend recommendation answer now only says recommendation completed and identifies the top supplier; verbose explanations are removed.
- Recommendation table column is now `CTM 值`.
- `落档比例预估` is returned as newline-separated efficiency segment details, e.g. one line for `25.5%` and one line for `25.6%`.
- Frontend table rendering preserves newline formatting for `落档比例预估` and disables overflow tooltip only for this multi-line column.
- Frontend still exports the displayed table data to Excel.

## Verification

- RED backend focused test: failed on old `CTM值` column.
- RED frontend focused test: failed because CTM alias and multi-line display contract did not exist.
- GREEN focused tests: passed.
- Focused regression: `32 passed`.
- Related Plan Power regression: `76 passed`.
- Full backend/business tests: `144 passed, 2 warnings`.
- Frontend build: passed.
- Compileall: passed.
- `git diff --check`: passed.
- Focused static/secret scan: passed; old token strings only appear in negative guard assertions.
- Browser smoke: BusinessChatPage scoped CSS verified with `white-space=pre-line` for multi-line table cells.
- Reviewer: `passed=true`, no blocking issues.

## Notes

- Existing full-test warnings are openpyxl warnings for unsupported Excel extension/conditional formatting.
- Frontend build still reports existing large chunk warnings.
- Worktree contains unrelated pre-existing dirty/untracked files from earlier tasks; this acceptance is scoped to the files above.

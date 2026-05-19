# TASK-plan-power-recommendation-table-polish Review Bundle

## Scope

User reported the supplier recommendation detail table for Plan BOM power QA is hard to read and needs display wording changes:

1. Do not show the explanatory sentences for `预测比例` and `中心功率` in the answer text.
2. Rename `指标5` / `CTM值` display to `CTM 值`.
3. Render `落档比例预估` as multiple lines, instead of packing multiple efficiency rows into one semicolon-separated line.

## Focused files

- `backend/app/domains/plan_bom/services/qa_service.py`
- `frontend/src/views/business-chat/BusinessChatPage.vue`
- `tests/business_acceptance/test_plan_power_real_business_qa_regression.py`
- `tests/business_acceptance/test_plan_power_docx_question_regression.py`
- `tests/business_acceptance/test_plan_power_m5_qa_integration.py`
- `tests/business_acceptance/test_plan_power_frontend_upload_entry.py`

Note: the worktree contains pre-existing unrelated dirty files from earlier tasks. Review should focus on the above files and `ai/tasks/running/TASK-plan-power-recommendation-table-polish/diff.patch`.

## Implementation summary

- Backend recommendation table now emits `CTM 值` as the visible column/key.
- Backend answer summary no longer includes verbose explanatory copy for prediction ratio/center power; deterministic numeric data remains in raw result/table.
- Backend `落档比例预估` joins selected efficiency-segment estimates with `\n`, preserving one efficiency segment per line.
- Frontend BusinessChat detail table now uses a scoped cell template instead of `show-overflow-tooltip` for every column.
- Frontend disables overflow tooltip only for multi-line columns, currently `落档比例预估`, and preserves line breaks via `white-space: pre-line`.
- Frontend localization maps legacy `ctm值`, `ctm_值`, and `ctm_value` to `CTM 值` so older payloads also render correctly.

## TDD / verification evidence

RED:

- Backend focused test failed because actual table still returned `CTM值` instead of `CTM 值`.
- Frontend focused test failed because no `CTM 值` alias / multi-line table contract existed.

GREEN / verification:

- `PYTHONPATH=. python -m pytest tests/business_acceptance/test_plan_power_real_business_qa_regression.py::test_business_power_recommendation_table_matches_sales_excel_export_columns -q --tb=short` -> passed
- `PYTHONPATH=. python -m pytest tests/business_acceptance/test_plan_power_frontend_upload_entry.py::test_business_chat_detail_table_can_export_excel_when_rows_exist -q --tb=short` -> passed
- `PYTHONPATH=. python -m pytest tests/business_acceptance/test_plan_power_real_business_qa_regression.py tests/business_acceptance/test_plan_power_frontend_upload_entry.py -q --tb=short` -> `32 passed`
- Related Plan Power tests -> `76 passed`
- Full tests -> `144 passed, 2 warnings`
- `npm run build --prefix frontend` -> passed
- `python -m compileall ...` -> passed
- `git diff --check` -> passed
- Focused static/secret scan -> passed after excluding negative guard assertions only
- Browser smoke: Vite page loaded; scoped CSS for `.result-table__cell--multi-line` computed as `white-space=pre-line`.

## Known non-blocking notes

- Full tests keep existing `openpyxl` warnings about unsupported Excel extensions/conditional formatting.
- Frontend build keeps existing Vite chunk-size warnings.
- Initial static scan attempt flagged negative guard assertions containing old token strings; retry confirmed they are only `not in` assertions and not live token handling.

# AI Answer Experience V2 — Ranking Narrative Polish Review Bundle

## Scope
User reported that backend natural-language AI answers are too terse for ranking questions. Example: “2024年江苏省各城市总费用排名前五？” previously returned only “2024年江苏总运费为3462229元。” while the table contained top five cities and fees.

## Current focused changes
1. `backend/app/domains/logistics/services/llm_answer_presentation_service.py`
   - deterministic fallback answer now calls `_build_deterministic_answer()` instead of raw `answer_summary`.
   - ranking/TopN small-table answers use only `result_table.rows` to narrate each returned dimension/value row.
   - no derived ratios, gaps, averages, or recomputed totals are added.
   - Chinese metric columns such as `总运费` / `总费用` infer unit `元`.

2. `backend/app/services/business_answer_stream_service.py`
   - stream LLM prompt now explicitly encourages ranking/TopN answers with <= five rows to list each name/value.
   - prompt still forbids new facts/numbers and internal-field leaks.

3. `backend/app/domains/logistics/api/endpoints/data_qa.py`
   - stream fallback now prefers `presentation.answer` over raw `answer_summary`, so LLM unavailable/invalid fallback still uses the enriched safe narrative.

4. `tests/business_acceptance/test_business_chat_answer_format_preference.py`
   - added RED/GREEN regression tests for ranking narrative richness and stream prompt wording.

## Verification
- RED observed before implementation:
  - `test_logistics_ranking_narrative_describes_top_rows_with_values` failed because answer length remained raw summary only.
  - `test_stream_prompt_encourages_rich_small_ranking_narrative` failed because prompt had no ranking/small-table guidance.
- GREEN after implementation:
  - focused 2 tests: passed.
  - `python -m pytest tests/business_acceptance/test_business_chat_answer_format_preference.py -q`: 13 passed.
  - `python -m pytest tests/business_acceptance -q`: 176 passed, 2 existing openpyxl warnings.
  - `npm run build`: passed, existing Vite chunk-size warning only.
- API probe on fresh backend `18110` for `2024年江苏省各城市总费用排名前五？` returned narrative:
  - total: `2024年江苏总运费为3462229元。`
  - rows: 徐州 1526425元；太仓 236305元；扬州 229064元；淮安 201100元；无锡 191499元。
- stream probe returned same enriched answer with `stream_answer_source=deterministic_fallback` because local LLM import unavailable, proving fallback no longer returns terse summary.
- Browser E2E default state: natural-language answer includes total and five city fees; detail table remains collapsed behind “展开明细”. Screenshot: `/Users/zhuchangchao/.hermes/cache/screenshots/browser_screenshot_475550e26771444281f359fb42a4fe36.png`.

## Static scan notes
- Focused patch: `ai/tasks/running/TASK-ai-answer-experience-v2/diff-richer-ranking.patch`.
- `api_key="test-key"` appears only in tests.
- `SQL/query_key/planner/guardrail` occurrences are safety patterns/tests/assertions or query_plan fixtures, not user-facing answer templates.
- Dirty worktree contains unrelated untracked historical files; review only this bundle and focused patch.

## Review focus
- Confirm the richer ranking narrative only uses deterministic `answer_summary` and `result_table.rows`.
- Confirm it does not add derived calculations or hidden fact changes.
- Confirm stream fallback to `presentation.answer` is safe and does not alter status/table/cards/chart.
- Confirm no user-facing SQL/query_key/planner/guardrail leak was introduced.

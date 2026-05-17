# AI Answer Experience V2 — Ranking Narrative Polish Final Review Bundle

## Scope
User reported the backend natural-language answer for “2024年江苏省各城市总费用排名前五？” was too terse. Goal: make ranking answers richer/professional while keeping deterministic query results as the only fact source.

## Current state
- Branch: `agent/TASK-ai-answer-experience-v2`.
- Current HEAD `4350977 结果返回内容优化` already contains deterministic ranking narrative and logistics stream fallback wiring.
- Working tree also contains AI Answer Experience V2 files from the same feature work; review only focused patch: `diff-richer-ranking-final.patch`.
- Focused patch line count: 1470 lines. It includes full file additions because the focused diff is generated to include untracked/current task files for review.

## Implemented behavior
1. Ranking narrative
   - Uses existing `answer_summary` as opening.
   - For ranking/TopN small tables, narrates rows from `result_table.rows` in current backend order.
   - Does not compute ratios, gaps, averages, new totals, or new conclusions.
   - Verified example:
     - `2024年江苏总运费为3462229元。`
     - 徐州 1526425元；太仓 236305元；扬州 229064元；淮安 201100元；无锡 191499元。

2. Stream fallback
   - `/query/stream` uses `presentation.answer` as fallback when available, so LLM unavailable/invalid no longer falls back to terse raw summary.

3. Prompt and streamed-answer safety
   - Prompt instructs LLM to list <=5-row ranking details but forbids new facts/numbers/internal fields.
   - Prompt compact payload uses a whitelist and recursive sanitization.
   - It keeps only answer_summary, status code/message/success, result_table columns/rows, presentation display/title/answer/caveats/table_spec, and caveats/warnings after sanitization.
   - It removes internal keys and string values containing query_key, query_plan, group_by, debug, trace, raw_result, planner, guardrail, SQL, internal, ods_/dwd_/dws_ markers.
   - Numeric validation collects allowed numbers from this same compacted/sanitized prompt context, not from full deterministic_payload internals.
   - Row binding validation rejects:
     - visible technical leaks;
     - new numeric tokens;
     - row entity/value mismatch;
     - swapped values in same sentence;
     - numeric-looking entities such as `620W` power bins swapped with metric values;
     - respectively-style multi-entity/multi-metric clauses;
     - multi-entity single-value claims such as `华东和华南均为120.5MW` and `620W和625W均为40%`;
     - metric columns containing incidental substrings such as `paid_amount` no longer get skipped as entity/id columns.

## Review failures fixed
1. Non-numeric fact swap could pass numeric-only validation.
   - Fixed with row binding validation and regression `test_streamed_answer_rejects_structured_row_fact_mismatch`.
2. Prompt could include `query_key` / `query_plan` / `group_by`.
   - Fixed with whitelist prompt compaction plus recursive key/value sanitization.
   - Regressions:
     - `test_stream_prompt_compact_payload_removes_internal_query_key`
     - `test_stream_prompt_compact_payload_removes_internal_table_and_caveat_strings`
3. Numbers only present in query_plan/internal payload could pass validation.
   - Fixed by collecting numeric whitelist from compacted prompt context.
   - Regression: `test_streamed_answer_rejects_numbers_only_present_in_query_plan`.
4. Swapped existing rows in one sentence could pass.
   - Fixed by row-token/entity binding validation and regression `test_streamed_answer_rejects_swapped_row_values_in_same_sentence`.
5. Numeric-looking entities such as `620W` were skipped.
   - Fixed by entity/metric/time column-role helpers and regression `test_streamed_answer_rejects_numeric_entity_value_swap`.
6. Respectively-style same-clause swaps could pass.
   - Fixed by conservative multi-row ambiguity/entity-token validation and regressions:
     - `test_streamed_answer_rejects_respectively_style_row_swap`
     - `test_streamed_answer_rejects_numeric_entity_respectively_style_swap`
7. Multi-entity single-value false claims could pass.
   - Fixed by rejecting clauses where a metric token is associated with entities outside the row(s) that own that token.
   - Regressions:
     - `test_streamed_answer_rejects_multi_entity_single_value_claim`
     - `test_streamed_answer_rejects_numeric_entity_multi_entity_single_value_claim`
8. Metric columns containing incidental `id`, e.g. `paid_amount`, could be skipped.
   - Fixed by token-aware entity detection and metric-precedence role checks.
   - Regression: `test_streamed_answer_rejects_metric_column_with_incidental_id_substring_swap`.

## Verification
- RED observed before fixes:
  - ranking narrative test failed when answer was terse.
  - prompt rich-ranking guidance test failed.
  - row mismatch / prompt leak / query_plan-number / same-sentence swap / numeric entity swap / respectively-style swap / multi-entity single-value / paid_amount role tests all failed before their fixes.
- GREEN final:
  - focused final reviewer regressions: `6 passed in 0.80s`.
  - answer-format suite: `24 passed in 0.79s`.
  - full business acceptance: `187 passed, 2 warnings in 24.60s`.
  - frontend build: pass; only existing Vite chunk-size warning.
- API/browser verification before final stream guard tweaks:
  - `/query` and `/query/stream` on backend `18120` returned enriched ranking answer.
  - Browser E2E on Vite `5190` showed enriched narrative and collapsed details by default; screenshot `/Users/zhuchangchao/.hermes/cache/screenshots/browser_screenshot_fdd2ebc50a6c4477a4646687bb66dcee.png`.
  - Final stream guard tweaks only affect unsafe LLM override rejection, not deterministic presentation wording or UI rendering.

## Static scan notes
- `api_key="test-key"` appears only in tests (11 occurrences), not real credentials.
- `SQL/query_key/query_plan/group_by/planner/guardrail` occurrences are safety patterns, prompt prohibitions, test fixtures, or negative assertions; not user-facing answer templates. Prompt regressions assert these are absent from actual LLM prompt.
- `shell=True`, `os.system`, eval/exec: 0 in focused patch additions.

## Review focus
Return pass/fail. Specifically verify:
1. ranking answer remains deterministic and fact-preserving;
2. stream fallback cannot alter status/table/cards/chart;
3. prompt whitelist/sanitizer strips internal keys and string values before LLM;
4. streamed-answer validation uses compacted numeric whitelist, not full internal payload;
5. row entity/value mismatch, swapped same-sentence values, numeric-looking entity swaps, respectively-style multi-row swaps, multi-entity single-value claims, and paid_amount-like metric fields are handled safely;
6. no user-facing technical leak introduced.

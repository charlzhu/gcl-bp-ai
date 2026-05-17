# AI Answer Experience V2 — Ranking Narrative Polish Review Bundle After Fix

## Scope
User reported the backend natural-language answer for “2024年江苏省各城市总费用排名前五？” was too terse: only “2024年江苏总运费为3462229元。” while table rows contained the top five city fees. The target is a richer professional narrative without changing deterministic facts.

## Important repository context
- Branch: `agent/TASK-ai-answer-experience-v2`.
- The deterministic ranking narrative method and logistics stream fallback wiring are already present in current HEAD commit `4350977 结果返回内容优化`.
- Some files in this branch are untracked because this workspace contains earlier AI Answer Experience V2 work; review only the focused patch and evidence below.

## Evidence that deterministic builder is wired
Current `backend/app/domains/logistics/services/llm_answer_presentation_service.py` lines 254-258:
```python
status_code = result.status.code if result.status else self._resolve_status_code(result)
display_type = self._resolve_display_type(question=question, result=result, status_code=status_code)
title = self._build_title(result=result, status_code=status_code)
answer = self._build_deterministic_answer(question=question, result=result, status_code=status_code)
requested_display = self._detect_requested_display(question)
```
So `_build_deterministic_answer()` is the active presentation answer path, not dead code.

## Focused changed behavior
1. `LogisticsLlmAnswerPresentationService`
   - `_build_deterministic_answer()` enriches OK ranking/TopN small-table answers.
   - `_build_ranking_narrative_answer()` narrates each returned row using only `result_table.rows` and existing `answer_summary`.
   - It does not compute ratios/gaps/averages/new totals.
   - Chinese fee columns infer unit `元`.

2. `data_qa.py` stream endpoint
   - stream fallback uses `presentation.answer` when present instead of raw terse `answer_summary`.

3. `BusinessAnswerStreamService`
   - prompt encourages <=5-row ranking/TopN answers to list each name/value.
   - LLM prompt compacting now removes `query_key`, `debug`, `trace`, `raw_result`, `planner`, `guardrail` recursively.
   - streamed answer validation now checks:
     - technical visible leaks;
     - new numeric tokens;
     - structured row entity/value binding mismatch, e.g. rejects saying “华北 120.5MW” when deterministic row is “华东 120.5MW”.
   - `apply_streamed_answer()` still only changes `presentation.answer` and debug stream fields; status/table/cards/chart remain deterministic.

4. Regression tests
   - ranking narrative must include total, top-five city names, and each fee value.
   - prompt must encourage rich small ranking narrative.
   - prompt must remove internal `query_key` and debug-like fields.
   - LLM row fact mismatch must downgrade even if numbers are legal.

## Verification
- RED observed:
  - ranking narrative test failed before implementation because answer remained terse.
  - prompt ranking guidance test failed before implementation.
  - row mismatch test failed before fix: “华北 120.5MW” was accepted.
  - prompt internal query_key test failed before fix: prompt contained `query_key=sys_region_mw`.
- GREEN after fixes:
  - focused reviewer-fix tests: `2 passed in 0.85s`.
  - focused answer-format suite: `15 passed in 0.85s`.
  - full business acceptance: `178 passed, 2 warnings in 29.45s`.
  - frontend build: `npm run build` passed; only existing Vite chunk-size warning.
- API verification on backend `18120`:
  - `/query` and `/query/stream` for “2024年江苏省各城市总费用排名前五？” returned:
    - `2024年江苏总运费为3462229元。`
    - 徐州 1526425元；太仓 236305元；扬州 229064元；淮安 201100元；无锡 191499元。
  - local stream source was deterministic fallback due local LLM import unavailable, proving fallback remains rich.
- Browser E2E on Vite `5190`:
  - natural-language answer includes total and all top-five city fees.
  - detail table default collapsed; only “展开明细 / 导出 Excel”等次级操作 visible.
  - console: no JS errors.
  - screenshot: `/Users/zhuchangchao/.hermes/cache/screenshots/browser_screenshot_fdd2ebc50a6c4477a4646687bb66dcee.png`.

## Static scan notes
- Focused patch: `ai/tasks/running/TASK-ai-answer-experience-v2/diff-richer-ranking-after-review.patch`.
- `api_key="test-key"` appears only in test fakes.
- `SQL/query_key/planner/guardrail` occurrences are safety patterns, prompt prohibitions, field-removal code, or tests/assertions; not user-facing answer templates.

## Review focus
Return pass/fail. Check:
1. richer ranking narrative only uses deterministic `answer_summary` and `result_table.rows`;
2. no derived calculations or hidden fact changes;
3. stream fallback to `presentation.answer` is safe;
4. prompt no longer sends internal query_key/debug fields;
5. LLM cannot swap a row entity while reusing allowed metric numbers;
6. no user-facing SQL/query_key/planner/guardrail leak introduced.

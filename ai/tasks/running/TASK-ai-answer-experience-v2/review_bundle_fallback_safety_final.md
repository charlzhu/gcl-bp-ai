# AI Answer Experience V2 — fallback safety cleanup review bundle

## Scope
After user accepted `final-acceptance.md` and confirmed a commit, continue with the two non-blocking reviewer suggestions:

1. Validate deterministic fallback text for visible technical leaks before streaming or merging.
2. Remove the unused `_has_ambiguous_multi_row_binding_clause` helper to avoid drift.

## Current branch/worktree note
- Branch: `agent/TASK-ai-answer-experience-v2`.
- HEAD observed: `173429f [verified] feat: add query planning v2 gray acceptance gate`.
- The repo remains a dirty multi-task worktree with many unrelated untracked files. Focus review only on:
  - `backend/app/services/business_answer_stream_service.py`
  - `tests/business_acceptance/test_business_chat_answer_format_preference.py`
  - focused patch: `diff-fallback-safety-final.patch`

## Implemented behavior

### Safe fallback selection
`BusinessAnswerStreamService._resolve_fallback_answer()` is now a classmethod and evaluates fallback candidates in order:

1. explicit `fallback_answer`;
2. `presentation.answer`;
3. `answer_summary`;
4. `status.message`;
5. generic completion text.

It returns the first non-empty candidate that does **not** match visible technical leak patterns. If all candidates are unsafe, it returns `当前查询已完成，请查看下方结构化结果。`.

### Technical leak checker reuse
`_visible_text_has_technical_leak()` is now a classmethod so both streamed LLM text and deterministic fallback candidates use the same visible leak patterns.

### Apply path no longer bypasses leaky fallback
Previously `apply_streamed_answer()` allowed a candidate if `candidate_answer == fallback`, so a leaky deterministic fallback could bypass validation. Because fallback resolution now returns a safe candidate, a leaky streamed/candidate answer fails validation and writes back the safe fallback with `stream_fallback_reason=stream_technical_visible_leak`.

### Unused helper removal
Removed `_has_ambiguous_multi_row_binding_clause`. The active row/value guard is the stricter token-entity binding logic in `_answer_row_bindings_are_safe()`.

## New RED/GREEN tests
Added two tests; both failed before implementation and pass now:

1. `test_deterministic_fallback_text_with_technical_leak_is_sanitized_before_streaming`
   - no-LLM fallback path with leaky fallback/presentation/summary should stream `查询成功`, not SQL/query_key/planner text.
2. `test_apply_streamed_answer_does_not_bypass_validation_for_leaky_fallback_text`
   - direct merge path with leaky candidate equal to original fallback should write back `查询成功` and record `stream_technical_visible_leak`.

## Verification
- RED before implementation:
  - the two new fallback-leak tests failed because leaky fallback text streamed/merged unchanged.
- GREEN after implementation:
  - fallback-leak tests: `2 passed in 0.97s`.
  - answer-format suite: `26 passed in 0.89s`.
  - full business acceptance: `189 passed, 2 warnings in 21.28s`.
  - frontend build: pass, only existing Vite chunk-size warning.
- Helper removal verified:
  - `search_files` found zero `_has_ambiguous_multi_row_binding_clause` references.

## Static scan notes
- Hardcoded secret-like matches are only `api_key="test-key"` in unit tests (11 occurrences), not real credentials.
- SQL/query_key/query_plan/group_by/planner/guardrail occurrences are denylist/prompt prohibitions/test fixtures/negative assertions; new fallback tests intentionally use leaky text as input and assert it is not output.
- shell injection patterns: 0.
- eval/exec patterns: 0.

## Review focus
Return pass/fail JSON. Specifically verify:
1. deterministic fallback text with visible technical leaks cannot be streamed or merged into `presentation.answer`;
2. safe fallback still preserves a useful business-safe message (`status.message` when available);
3. LLM output remains limited to narrative answer text; status/table/cards/chart are unchanged;
4. removing `_has_ambiguous_multi_row_binding_clause` does not weaken active row/entity validation because tests still cover swapped rows, respectively-style swaps, numeric-looking entity swaps, multi-entity single-value claims, and paid_amount-like metric fields;
5. no user-facing SQL/query_key/planner/guardrail leak or secret introduced.

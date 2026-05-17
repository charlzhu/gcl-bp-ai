# Review bundle — Plan BOM answer business-language hardening

## Scope
User reported that Plan BOM backend responses still exposed technical details (e.g. slot/field names such as `order_id`, `material_category`) and were too short. The requested behavior:
1. User-visible answer text must not expose technical implementation terms: slot definitions, field names, table/database names, SQL/query/debug/planner/guardrail/schema/raw payload names, etc.
2. Text should be more complete and include analysis/query-process description.
3. Streamed response should output the business answer dynamically in chunks.

## Files in current-task scope
- `backend/app/domains/plan_bom/services/answer_presentation_service.py`
- `backend/app/domains/plan_bom/services/qa_service.py`
- `backend/app/domains/plan_bom/api/endpoints/qa.py`
- `backend/app/services/business_answer_stream_service.py`
- `tests/business_acceptance/test_business_chat_answer_format_preference.py`

The worktree is dirty from other tasks. Review only the files above and the task patch:
- `ai/tasks/running/TASK-planbom-answer-business-language/diff.patch`

## Key implementation points to verify
1. `PlanBomAnswerPresentationService.build_deterministic_presentation()` now uses `_build_deterministic_answer()` instead of raw `answer_summary`.
2. Clarification answers convert `missing_slots` into business language, e.g. “订单号/订单范围、材料范围”, not `order_id/material_category`.
3. Small successful result sets include an analysis process and repeat key row facts in business labels/values.
4. Follow-up questions are business-language suggestions rather than raw slot names.
5. LLM presentation validation rejects visible text containing technical leaks.
6. LLM prompt/context no longer sends raw deterministic payload as the primary prompt; it sends compact public business context.
7. Plan BOM `/ask/stream` fallback uses `presentation.answer` first and rejects leaky fallback candidates even when `presentation` is missing.
8. `BusinessAnswerStreamService` denylist now includes Chinese technical terms and variants such as query-plan/query plan/guard rail/schema/LLM.
9. Stream fallback still chunks text (`FALLBACK_CHUNK_SIZE`) so frontend receives multiple `delta` events.
10. Deterministic facts, tables, statuses, and raw trace payloads remain preserved in structured result for audit; only visible narrative is changed.

## Tests run
- focused Plan BOM answer tests: `4 passed in 0.83s`
- answer-format suite: `30 passed in 0.87s`
- query planning stream meta unit: `8 passed in 0.90s`
- full business acceptance: `205 passed, 2 warnings in 21.30s`
- compile check: passed
- frontend build: passed with existing Vite chunk-size warning

## Static scan
Added-lines scan found no real hardcoded secrets. Matches were constructor/test parameters like `api_key=None` / `api_key="test-key"` only.

## Known dirty worktree caveat
The active branch is currently `agent/TASK-plan-bom-multi-candidate-compare`, while this is a focused follow-up. Do not review unrelated modified/untracked files outside the listed scope.

## Requested reviewer output
Return ONLY valid JSON:
{
  "passed": true or false,
  "security_concerns": [],
  "logic_errors": [],
  "suggestions": [],
  "summary": "one sentence verdict"
}

Fail if:
- user-visible path can still expose raw slot/field/table/query/debug terms;
- streaming fallback can still output leaky technical text;
- answer text becomes too terse or loses process explanation;
- LLM can alter status/table/numeric facts;
- there is a security issue or obvious regression.

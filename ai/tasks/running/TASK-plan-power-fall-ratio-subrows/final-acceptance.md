# TASK-plan-power-fall-ratio-subrows Final Acceptance

## Task

Refine `落档比例预估` display based on user clarification: each screenshot red-box / efficiency segment should be an independent row, and each segment must not be split into multiple wrapped visual lines.

## Root cause

The previous implementation only preserved backend newlines with `white-space: pre-line`. Because the table column was still narrow and the cell used normal word wrapping, each segment could wrap internally, producing:

```text
25.5%→615W
12.98%、620W
82.08%
```

The user expects:

```text
25.5%→615W 12.98%、620W 82.08%
25.6%→615W 2.59%、620W 77.17%
```

That is an irregular Excel-like presentation: one logical efficiency segment per child row, not a standard single wrapped table cell.

## Changed files

- `frontend/src/views/business-chat/BusinessChatPage.vue`
- `tests/business_acceptance/test_plan_power_frontend_upload_entry.py`

## Implementation

- Added `isFallRatioEstimateColumn(column)` so only `落档比例预估` uses the special renderer.
- Added `splitFallRatioEstimateLines(value)` to split both current newline-separated and historical semicolon-separated display strings into one segment per row.
- Added dynamic column min width: `落档比例预估` gets wider `420`, other columns remain `130`.
- Added a special child-row template for `落档比例预估`:
  - one `<span class="result-table__fall-ratio-line">` per segment;
  - no business calculation in frontend.
- Added CSS:
  - outer fall-ratio cell: `overflow-x: auto`;
  - each segment line: `white-space: nowrap`, `word-break: keep-all`, `overflow-wrap: normal`.

## Verification

- RED focused test failed before implementation: missing `isFallRatioEstimateColumn` / split-line renderer.
- GREEN new focused test: `1 passed`.
- Focused table presentation tests: `2 passed`.
- Related frontend/business presentation contracts: `17 passed`.
- Frontend build: passed.
- Compileall for modified Python test: passed.
- `git diff --check`: passed.
- Focused static/secret scan: passed.
- Browser smoke: verified scoped CSS applies; fall-ratio container `overflow-x=auto`, segment line `white-space=nowrap`, `word-break=keep-all`, and two segments render as two child rows.
- Reviewer: `passed=true`, no blocking issues.

## Full-test note

A full `PYTHONPATH=. python -m pytest tests -q --tb=short` currently reports 2 failures in unrelated pre-existing logistics WIP tests:

- `tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py::test_hist_city_total_fee_rank_supports_variable_top_n`
- `tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py::test_logistics_ranking_branches_parse_variable_top_n`

These files are dirty from another task and were not modified by this fix. Running the full suite excluding that unrelated WIP file gives:

- `123 passed, 2 warnings`

## Risk

- Very long fall-ratio segments will remain one visual line and use horizontal scroll instead of wrapping. This matches the user requirement but may require users to scroll horizontally for unusually long target-bin combinations.

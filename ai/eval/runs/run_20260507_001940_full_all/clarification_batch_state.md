# Logistics Clarification Batch Repair State

Workspace: `/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai`

## Authoritative branch

User clarified on 2026-05-09:

- The previous dedicated logistics clarification branch no longer exists.
- The authoritative task branch is the current Plan Power branch: `agent/TASK-plan-power-real-business-qa-fix`.

All future logistics clarification recovery/batch jobs must use this branch as the expected branch. If `git rev-parse --abbrev-ref HEAD` returns any other branch, the job must stop and report. Jobs must not run `git checkout`, `git reset`, or `git clean`.

## Current dirty worktree note

The current branch contains Plan Power dirty files. Logistics clarification work must stay focused on logistics files and this state file only. Do not modify or revert unrelated Plan Power changes.

Observed current branch dirty files include:

- `backend/app/domains/plan_bom/config/material_aliases.json`
- `backend/app/domains/plan_bom/services/nlu_center_service.py`
- `backend/app/domains/plan_bom/services/power_config_resolver_service.py`
- `backend/app/domains/plan_bom/services/qa_service.py`
- `frontend/src/views/business-chat/BusinessChatPage.vue`
- `tests/business_acceptance/test_plan_power_real_business_qa_regression.py`

## Baseline

- Full logistics sample count: 1377
- Round5 planner clarification: 609
- Round6 planner clarification: 607
- Latest known clarification count after remark keyword work: 607 / 1377

## Completed / partially completed batches from earlier cron sessions

### round6 — remark keyword summaries

Implemented / verified earlier in prior branch/session:

- `hist_remark_keyword_fee_ratio` for: `备注中包含“倒运”或“中转”的记录,其总费用占历史物流总费用的比例是多少?`
- `hist_remark_keyword_amount_summary` for yearly questions like: `请统计2023年备注中包含倒运、中转、换车、压车、放空的记录数量和费用金额？`
- Guard: detail-list questions such as `请列出备注中包含“倒运”的前50条明细...` must still require clarification.

### review recovery — remark keyword guard hardening

Prior cron session `93753b4d1ba9` reported a valid TDD/reviewer pass, but its final logistics diff was not present after branch context changed. Therefore the next recovery job on the current Plan Power branch must verify and, if missing, re-apply the remark keyword guard hardening:

- Supported narrow cases still route to `hist_remark_keyword_fee_ratio` / `hist_remark_keyword_amount_summary`.
- Unsupported extra scopes must remain clarification:
  - explicit year/range on fee-ratio questions;
  - missing/multiple/cross-year amount-summary years;
  - region/province/destination/customer/carrier/project/contract scopes;
  - monthly/yearly split requests;
  - detail/list/top-N/line/contract/model-code requests;
  - extra remark keywords outside the supported set;
  - alternative denominators such as record count, MW, public-road fee, a customer/company subtotal.

## Next required job

Do a one-shot recovery on `agent/TASK-plan-power-real-business-qa-fix`:

1. Verify branch is exactly `agent/TASK-plan-power-real-business-qa-fix`.
2. Check whether remark keyword guard tests and planner helper exist.
3. If absent or incomplete, use strict TDD:
   - write unsupported-scope RED tests first;
   - run and verify they fail for expected reason;
   - implement only the missing guard logic;
   - run focused tests and full changed test file.
4. Run independent reviewer on the focused logistics diff.
5. Update this state file with results.
6. Stop; do not start a new clarification family in the same run.

## Foreground verification result — remark keyword short fix

A foreground verification run completed the focused remark-keyword guard hardening checks on the currently checked out branch, but the observed branch was `agent/TASK-plan-bom-batch-upload`, not the authoritative branch `agent/TASK-plan-power-real-business-qa-fix` required above. Therefore this run is recorded as **code/test/reviewer passed on current worktree, branch-scope not accepted yet**.

Focused changed files:

- `backend/app/domains/logistics/services/data_qa_planner.py`
- `tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py`

Verified behavior:

- Supported narrow cases still route to `hist_remark_keyword_fee_ratio` / `hist_remark_keyword_amount_summary`.
- Unsupported remark variants fail closed with `needs_clarification=true` and `query_key=None`.
- Guard coverage includes unknown keywords, explicit/relative time, alternative denominators, total-fee aliases (`多少钱` / `花了多少钱`), `总运费` aliases, percentage/share wording, extra dimensions, detail/list requests, embedded extra conditions, duplicate keyword connectors, and `备注包含` / `备注中包含` / `备注，包含` / `备注：包含` / `备注里包含` forms.
- Generic total-fee / origin / vehicle query_keys are no longer allowed to swallow unsupported remark-keyword conditions.

Verification commands and results:

- `python -m compileall -q backend/app/domains/logistics/services/data_qa_planner.py tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py` — passed.
- `PYTHONPATH=. python -m pytest tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py -k 'remark_keyword' -q` — `5 passed, 15 deselected`.
- `PYTHONPATH=. python -m pytest tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py -q` — `20 passed`.
- Independent focused reviewer bundle `/tmp/logistics_short_fix_final_review_bundle_v9.md` — passed with no security concerns and no logic errors.

Next action before starting c7:

- Resolve/confirm the branch mismatch. If this logistics fix must live on `agent/TASK-plan-power-real-business-qa-fix`, apply or carry only the focused logistics diff there and re-run the same tests/reviewer. Do not start a new clarification family until the branch scope is accepted.

## Hard rules

- No commit, push, deploy, merge.
- No `.env`, credentials, token, secret changes.
- No branch checkout/reset/clean from cron.
- Do not touch Plan BOM dirty files.
- Do not hardcode sample answers.
- Unknown entity / unclear scope / unclear denominator must stay clarification.
- No time condition defaults to 2023-2026 only when the metric can be safely joined across 2023-2025 history and 2026 system data.

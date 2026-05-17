# Logistics Clarification Recovery Prompt — Plan Power Branch

You are the autonomous engineering agent for `gcl-bp-ai`.

Workspace: `/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai`
Expected branch: `agent/TASK-plan-power-real-business-qa-fix`

The user explicitly clarified that the old logistics clarification branch no longer exists, and the authoritative task branch is the current Plan Power branch. Therefore this job must operate only if the current branch is exactly `agent/TASK-plan-power-real-business-qa-fix`.

## Goal for this single run

Recover and verify the logistics remark-keyword guard hardening on the current Plan Power branch. Do not enter a new clarification family in this run.

## Required steps

1. Run `git rev-parse --abbrev-ref HEAD`.
   - If it is not exactly `agent/TASK-plan-power-real-business-qa-fix`, stop immediately and report.
   - Do not run `git checkout`, `git reset`, or `git clean`.
2. Read `ai/eval/runs/run_20260507_001940_full_all/clarification_batch_state.md`.
3. Inspect only these logistics files unless absolutely necessary:
   - `backend/app/domains/logistics/services/data_qa_planner.py`
   - `backend/app/domains/logistics/repositories/data_qa_repository.py`
   - `backend/app/domains/logistics/services/data_qa_service.py`
   - `tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py`
4. Determine whether the remark-keyword unsupported-scope guard exists:
   - supported narrow cases still route to `hist_remark_keyword_fee_ratio` / `hist_remark_keyword_amount_summary`;
   - unsupported extra scopes remain clarification: explicit year/range on fee ratio, missing/multiple/cross-year amount summary, region/province/destination/customer/carrier/project/contract scopes, monthly/year split, detail/list/top-N/line/contract/model-code requests, extra remark keywords, alternative denominators.
5. If missing/incomplete, use strict TDD:
   - Add RED tests first in `tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py`.
   - Run the focused new tests and verify they fail for the expected routing reason.
   - Implement only minimal planner guard logic.
   - Run focused tests again and verify they pass.
6. Always run:
   - `python -m compileall -q backend/app/domains/logistics/services/data_qa_planner.py backend/app/domains/logistics/repositories/data_qa_repository.py backend/app/domains/logistics/services/data_qa_service.py tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py`
   - `PYTHONPATH=. python -m pytest tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py -k 'remark_keyword' -q`
   - If changed logistics tests exist, also run `PYTHONPATH=. python -m pytest tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py -q`.
7. Run static scan on focused logistics diff for secrets, shell injection, eval/exec, pickle, SQL format injection.
8. Use `delegate_task` for independent reviewer on focused logistics diff only. Ignore unrelated dirty Plan Power files. Reviewer must return JSON and fail closed.
9. Update `clarification_batch_state.md` with concise results.
10. Final response must include:
    - branch verified or mismatch;
    - files changed;
    - tests run and results;
    - reviewer result;
    - whether it is safe to schedule the next functional batch.

## Hard rules

- Do not commit, push, deploy, merge.
- Do not change branches.
- Do not edit `.env`, credentials, tokens, or secrets.
- Do not touch Plan BOM dirty files or frontend files in this recovery job.
- Do not run broad cleanup commands.
- Stop before tool-call limit.

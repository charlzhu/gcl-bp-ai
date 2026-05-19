# Review bundle — plan power explicit config clarification / no-order power-model compare fix

## Scope

Fix two related Plan BOM power QA over-clarification paths:

1. Screenshot issue:
   - User question includes model `NT12-66GDF`, ribbon `0.26+0.24`, glass wording `高透玻璃+间隙贴膜`, cable wording `300、200线长`, busbar `6*0.35+4*0.35反光`, benchmark `北德基准`, supplier `芜湖`, and target `单一功率720W`.
   - Expected behavior: direct deterministic supplier/efficiency recommendation, no clarification.
   - Safety guard: adjacent invalid explicit glass wording (`透明玻璃+间隙贴膜`) must still clarify and must not call the recommendation engine.
2. Same class of over-clarification discovered during full docx regression:
   - Question asks `NT12-66GDF，汇流条6*0.3+4*0.3反光和4 *0.4+4*0.3反光相差多少`.
   - Expected behavior: this is a power-model configuration effect comparison, not an order/BOM material query, so it must not ask for order number; it should validate both options against the active power model and return the deterministic effect-value difference.

## Root causes found

### Screenshot explicit configuration

The deterministic no-BOM explicit-configuration path did not normalize two business phrasings that are semantically complete:

1. `300、200线长` used a Chinese comma/list separator, but cable extraction/resolution only accepted slash-style `300/200`.
2. `高透玻璃+间隙贴膜` was extracted as a glass option but active model options use `超高透+间隙铝膜`; alias normalization lacked the business shorthand mapping.

Because glass/cable stayed unresolved, QA returned `CLARIFICATION_REQUIRED` even though all business inputs were present.

### No-order power-model effect compare

NLU could already identify `plan_power_factor_effect_compare`, but `PlanBomQaService.ask()` did not have an execution branch for that intent. It fell through to the generic clarification branch, which asked for order/material conditions even though the question only needs active power-model option effect values.

## Changed files / key changes

- `backend/app/domains/plan_bom/services/nlu_center_service.py`
  - cable regex accepts `/` plus Chinese/ASCII comma/list separators before `线长/线缆/接线盒`.
  - suffix ribbon extractor narrowed to numeric ribbon specs so `焊带0.26+0.24+高透玻璃` does not swallow glass text.
  - power-factor option extraction supports no-order configuration effect comparison intent.
- `backend/app/domains/plan_bom/services/power_config_resolver_service.py`
  - explicit cable length resolver accepts `/` plus `、` / `，` / `,` separators.
  - existing explicit-wire-size guard remains: invalid explicit wire size returns unresolved; omitted wire size may use active model default only after validating the resulting option exists.
- `backend/app/domains/plan_bom/config/power_aliases.json`
  - adds glass aliases for `高透+间隙贴膜`, `高透+间隙铝膜`, `高透+镀釉` to active `超高透...` option labels.
- `backend/app/domains/plan_bom/services/qa_service.py`
  - adds deterministic execution branch for `plan_power_factor_effect_compare`.
  - validates model/factor/options against current active `PlanPowerModelSheet` + `PlanPowerFactorOption` before computing the absolute effect-value difference.
  - fail-closed clarification if options do not match active model values.
- `backend/app/domains/plan_bom/services/answer_presentation_service.py`
  - treats `plan_power_factor_effect_compare` as deterministic-only power-model output so expression layer cannot rewrite numeric facts.
  - adds business labels/follow-up text for missing power-factor options.
- `tests/business_acceptance/test_plan_power_docx_question_regression.py`
  - adds positive regression for screenshot-style explicit config + 芜湖 + 720W.
  - adds negative guard for adjacent invalid `透明玻璃+间隙贴膜`.
  - includes no-order busbar effect-difference regression.
  - adds invalid effect-compare option regression to prove unmatched active-model options still clarify and do not compute a difference.
- `tests/business_acceptance/test_plan_power_m5_qa_integration.py`
  - pre-existing same-session regression retained in current dirty worktree; included in broad verification and scoped patch for reviewer visibility.

## Artifacts

- Focused patch: `ai/tasks/running/TASK-plan-power-explicit-config-clarification-fix/diff.patch`
- Test log: `ai/tasks/running/TASK-plan-power-explicit-config-clarification-fix/test.log`
- Static scan log: `ai/tasks/running/TASK-plan-power-explicit-config-clarification-fix/static-scan.log`

## Verification summary

Latest successful runs in `test.log`:

- Screenshot explicit-config regression pair: `2 passed`
- No-order factor-effect regression: `1 passed`
- Invalid factor-effect option regression pair: `2 passed`
- Full docx-derived plan-power regression file: `39 passed`
- Related M4/M5 plan-power backend regressions: `19 passed`
- Broader backend business acceptance suite: `227 passed, 2 warnings`
  - warnings are openpyxl extension/conditional formatting warnings while reading Excel; not introduced by this patch.
- Compile scoped Python files: OK
- `json.tool` for `power_aliases.json`: OK
- `git diff --check` on scoped files: OK
- Frontend production build: OK (`npm run build`; Vite emitted only existing large-chunk advisory)

Static scan: no hardcoded secret/token/password/API key, eval/exec, pickle, subprocess shell=True, or SQL string-formatting patterns in added lines.

## Dirty worktree note

The repository has many unrelated staged/modified/untracked files from other concurrent tasks and data attachments. Review only this task bundle and focused patch. The patch is restricted to the files listed above, but some files had prior same-file changes in the dirty worktree; judge only whether the current task changes introduce blockers or interact badly with those same-file changes.

## Reviewer checklist

- Does the explicit-config fix generically handle business punctuation/aliases rather than hardcoding the screenshot?
- Does the positive path still validate resolved options against active power model choices before recommendation?
- Does invalid explicit glass remain fail-closed and avoid M3 recommendation calls?
- Is invalid explicit cable wire-size handling preserved?
- Does `plan_power_factor_effect_compare` avoid order clarification only when model + one factor + at least two options are closed?
- Are compared options validated against active `PlanPowerFactorOption` rows before difference calculation?
- Does answer presentation keep power-model numeric outputs deterministic-only, with no LLM rewrite of numeric facts?
- Any security, logic, or maintainability blockers in the scoped changes?

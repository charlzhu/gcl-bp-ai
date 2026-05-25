# ON-6 Fallback/Rollback Report

## Verdict: ALL PASSED

| Domain | on success | off fallback | production guard |
|---|---|---|---|
| logistics | ✅ completed | ✅ legacy_fallback | ✅ IS_PRODUCTION→off |
| business_analysis | ✅ completed | ✅ legacy_fallback | ✅ IS_PRODUCTION→off |
| plan_bom (BOM) | ✅ completed | ✅ legacy_fallback | ✅ IS_PRODUCTION→off |
| power_prediction | ✅ completed | ✅ legacy_fallback | ✅ IS_PRODUCTION→off |

## Evidence
- on-mode: LLM SQL + real EXPLAIN + real execute
- off-mode: 4/4 legacy_fallback (old chain)
- production: IS_PRODUCTION=True → return None → old chain
- old chains: LogisticsDataQaService, PlanBomQaService, PowerPredictionEngine all intact

## Anti-rule-mode
- Fallback is exception handling, not default path
- trace distinguishes nqe_success vs fallback_used
- No old chain deletion
- No production default on

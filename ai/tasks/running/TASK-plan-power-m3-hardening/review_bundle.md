# TASK-plan-power-m3-hardening Review Bundle

## Scope
本轮仅审查计划 BOM 功率预测 hardening 变更：
1. 将“建议效率段”下沉到 M3 `PowerRecommendationItem.suggested_efficiency_segments`，M5 QA 只格式化展示。
2. 显式接线盒只写长度（如 `300/200`）时，从 active 模型默认 `cable` option 解析线径，而不是写死 `4mm²`。
3. 将“所有电池供应商 / 全部电池供应商 / 所有电池厂家 / 全部电池厂家”等识别为全供应商 marker，优先于单供应商抽取。
4. mock/live LLM 候选不能覆盖规则层功率关键槽位，也不能把规则层功率推荐降级为预测。

## Changed Files Relevant To This Review
- `backend/app/domains/plan_bom/services/power_recommendation_service.py`
  - `PowerRecommendationItem` 新增 `suggested_efficiency_segments`。
  - `_score_prediction()` 由 M3 deterministic prediction rows 计算建议效率段。
- `backend/app/domains/plan_bom/services/qa_service.py`
  - `_power_recommendation_rows()` 改为读取 M3 `item.suggested_efficiency_segments`。
  - 新增 `_format_suggested_efficiency_segments()`；不再在 M5 根据 prediction 重新推导。
- `backend/app/domains/plan_bom/services/power_config_resolver_service.py`
  - `_try_power_semantic_fallback()` 中 cable length-only fallback 改为从 active 默认 option 提取线径。
  - 新增 `_default_cable_wire_size()`。
- `backend/app/domains/plan_bom/services/nlu_center_service.py`
  - 扩展 all-supplier markers。
  - `_merge_llm_candidate()` 增加功率 intent 冲突保护：power prediction/recommendation 边界由规则层保持。
- Tests:
  - `tests/business_acceptance/test_plan_power_m3_prediction_engine.py`
  - `tests/business_acceptance/test_plan_power_docx_question_regression.py`
  - `tests/business_acceptance/test_plan_power_m5_qa_integration.py`

## Verification Commands Already Run
- Focused hardening tests:
  - `PYTHONPATH=. pytest tests/business_acceptance/test_plan_power_m3_prediction_engine.py::test_recommendation_scores_suppliers_and_rejects_unknown_target_bin tests/business_acceptance/test_plan_power_m3_prediction_engine.py::test_explicit_cable_length_uses_active_default_wire_size tests/business_acceptance/test_plan_power_docx_question_regression.py::test_explicit_config_all_battery_supplier_synonyms_ignore_example_supplier_names tests/business_acceptance/test_plan_power_m5_qa_integration.py::test_llm_cannot_downgrade_power_recommendation_or_override_rule_power_slots -q`
  - Result: `5 passed in 2.59s`
- Related power tests:
  - `PYTHONPATH=. pytest tests/business_acceptance/test_plan_power_m3_prediction_engine.py tests/business_acceptance/test_plan_power_m4_config_resolver.py tests/business_acceptance/test_plan_power_m5_qa_integration.py tests/business_acceptance/test_plan_power_docx_question_regression.py -q`
  - Result: `63 passed, 2 warnings in 15.82s`
- Full backend business acceptance:
  - `PYTHONPATH=. pytest tests/business_acceptance -q`
  - Result: `115 passed, 2 warnings in 20.22s`
- Compile:
  - `python -m compileall backend/app backend/run.py`
  - Result: passed
- Frontend build:
  - `cd frontend && npm run build`
  - Result: passed (`✓ built in 4.25s`)
- Static scan:
  - Targeted hardening files: no findings.
  - Added lines in `diff.patch`: no findings.

## Known Non-blocking Notes
- Full/related pytest warnings are existing `openpyxl` extension/conditional-formatting warnings while reading Excel; not introduced by this hardening.
- `test.log` includes one earlier root-level `npm run build` attempt that failed because the workspace root has no `package.json`; it was immediately rerun correctly from `frontend/` and passed.
- Current worktree contains prior uncommitted task files inherited from previous stages. For this review, focus on the hardening files listed above and the patch at `ai/tasks/running/TASK-plan-power-m3-hardening/diff.patch`.

## Artifacts
- Patch: `ai/tasks/running/TASK-plan-power-m3-hardening/diff.patch`
- Test log: `ai/tasks/running/TASK-plan-power-m3-hardening/test.log`

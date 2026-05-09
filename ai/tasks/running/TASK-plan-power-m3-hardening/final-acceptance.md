# TASK-plan-power-m3-hardening 最终验收报告

## 1. 任务范围

本轮按用户确认的 reviewer hardening 建议执行，不进入新业务域、不恢复功率模型管理临时 token、不修改生产部署配置。

本轮完成：

1. 将“建议效率段”进一步下沉到 M3 推荐结果中。
2. 显式接线盒只写长度（如 `300/200`）时，从 active 功率模型默认 `cable` option 解析线径。
3. 扩展“所有电池供应商 / 全部电池供应商”等全供应商同义词测试与识别。
4. 增加 mock LLM guardrail 测试，确保 LLM 候选不能覆盖规则层功率关键槽位或降级规则层推荐意图。

当前分支：`agent/TASK-plan-power-m3-hardening`

## 2. 根因与修复说明

### 2.1 建议效率段仍停留在 M5 展示层

- 根因：上一轮 QA presentation 仍根据 M3 prediction rows 在 M5 层即时推导“建议效率段”，导致推荐结果本身不携带结构化效率段，边界上不够清晰。
- 修复：在 `PowerRecommendationItem` 增加 `suggested_efficiency_segments`，由 M3 `PowerRecommendationService._score_prediction()` 基于 deterministic prediction rows 和目标功率档贡献度生成；M5 只格式化该字段展示。

### 2.2 显式接线盒长度-only 写死默认线径

- 根因：显式配置中 `接线盒：300/200` 这类表达只写长度时，旧逻辑默认拼接 `4mm²`，与 active 模型默认 option 可能不一致。
- 修复：`PlanBomPowerConfigResolverService` 从 active 模型默认 `cable` option 中解析线径（如 `4mm²` / `6mm²`），再匹配 `+300/-200mm（线径）` 候选；若默认 option 本身就是对应长度，则直接沿用 active 默认 option。

### 2.3 全供应商同义词覆盖不足

- 根因：原 all-supplier markers 覆盖“各家/所有供应商/全部供应商”等，但未显式覆盖“所有电池供应商/全部电池供应商/所有电池厂家/全部电池厂家”。
- 修复：扩展 NLU all-supplier markers，并保持 marker 优先于单供应商命中，避免句中用 `芜湖` 等作为示例时被误判为单供应商筛选。

### 2.4 LLM 候选存在覆盖规则层关键槽位/意图边界风险

- 根因：已有槽位 guardrail 会拒绝与规则层不一致的 model、benchmark、supplier、target_power_ratio 等，但 power recommendation / prediction intent 冲突还可被 LLM 候选改写。
- 修复：`_merge_llm_candidate()` 对功率类 intent 增加边界保护：当规则层已识别为功率预测/推荐时，LLM 不能在 prediction/recommendation 间改写或降级，关键槽位继续以规则层为准。

## 3. 修改文件

### 生产代码

- `backend/app/domains/plan_bom/services/power_recommendation_service.py`
  - `PowerRecommendationItem` 新增 `suggested_efficiency_segments`。
  - M3 推荐评分阶段生成效率段建议。
- `backend/app/domains/plan_bom/services/qa_service.py`
  - QA 推荐表格改为读取 M3 推荐结果中的 `suggested_efficiency_segments`。
  - M5 不再重新推导建议效率段，仅格式化展示。
- `backend/app/domains/plan_bom/services/power_config_resolver_service.py`
  - 接线盒 length-only fallback 从 active 默认 option 解析线径，移除写死 `4mm²` 的业务假设。
- `backend/app/domains/plan_bom/services/nlu_center_service.py`
  - 扩展全供应商同义词。
  - 增加功率类 LLM intent guardrail。

### 测试

- `tests/business_acceptance/test_plan_power_m3_prediction_engine.py`
  - 新增/扩展 M3 推荐结果必须携带建议效率段的断言。
  - 新增显式接线盒 length-only 从 active 默认线径解析的测试。
- `tests/business_acceptance/test_plan_power_docx_question_regression.py`
  - 新增“所有电池供应商 / 全部电池供应商”同义词参数化测试。
- `tests/business_acceptance/test_plan_power_m5_qa_integration.py`
  - 新增 mock LLM guardrail 测试，覆盖 LLM 冲突 intent 与关键槽位覆盖尝试。

### 验收材料

- `ai/tasks/running/TASK-plan-power-m3-hardening/diff.patch`
- `ai/tasks/running/TASK-plan-power-m3-hardening/test.log`
- `ai/tasks/running/TASK-plan-power-m3-hardening/review_bundle.md`
- `ai/tasks/running/TASK-plan-power-m3-hardening/reviewer_result.json`
- `ai/tasks/running/TASK-plan-power-m3-hardening/final-acceptance.md`

## 4. TDD 验证

本轮先补 RED 测试再实现。新增 hardening focused tests 初次运行失败（RED），实现后全部转绿。

### Focused hardening tests

```bash
PYTHONPATH=. pytest \
  tests/business_acceptance/test_plan_power_m3_prediction_engine.py::test_recommendation_scores_suppliers_and_rejects_unknown_target_bin \
  tests/business_acceptance/test_plan_power_m3_prediction_engine.py::test_explicit_cable_length_uses_active_default_wire_size \
  tests/business_acceptance/test_plan_power_docx_question_regression.py::test_explicit_config_all_battery_supplier_synonyms_ignore_example_supplier_names \
  tests/business_acceptance/test_plan_power_m5_qa_integration.py::test_llm_cannot_downgrade_power_recommendation_or_override_rule_power_slots \
  -q
```

结果：`5 passed in 2.59s`

### Related power tests

```bash
PYTHONPATH=. pytest \
  tests/business_acceptance/test_plan_power_m3_prediction_engine.py \
  tests/business_acceptance/test_plan_power_m4_config_resolver.py \
  tests/business_acceptance/test_plan_power_m5_qa_integration.py \
  tests/business_acceptance/test_plan_power_docx_question_regression.py \
  -q
```

结果：`63 passed, 2 warnings in 15.82s`

### Full backend business acceptance

```bash
PYTHONPATH=. pytest tests/business_acceptance -q
```

结果：`115 passed, 2 warnings in 20.22s`

### Compile / Build / Static scan

- `python -m compileall backend/app backend/run.py`：通过。
- `cd frontend && npm run build`：通过，`✓ built in 4.25s`。
- Targeted static scan：无发现。
- Added-lines static scan：无发现。

说明：`test.log` 中保留了一次从仓库根目录执行 `npm run build` 的失败记录，原因是根目录没有 `package.json`；随后已按正确目录 `frontend/` 重跑并通过。

## 5. Reviewer 结果

独立 reviewer 已审查 `review_bundle.md` 与 `diff.patch`，结论：

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": [],
  "suggestions": [],
  "summary": "Reviewed the hardening bundle and patch, ran focused hardening tests, and found no blocking security or logic issues."
}
```

## 6. 风险与边界

- 当前未恢复、未新增任何 `X-Plan-Power-Admin-Token` 或类似前端 token 输入。
- LLM 仍只参与意图/槽位理解辅助，不能覆盖规则层功率关键槽位，不能参与功率数值计算或推荐评分。
- M3/M4 deterministic 仍负责配置解析、预测、推荐、效率段建议。
- 当前 worktree 仍包含之前阶段遗留的未提交/未跟踪文件；本轮验收聚焦 hardening 文件与 `TASK-plan-power-m3-hardening` 验收材料。
- openpyxl 的 2 个 warning 是读取 Excel 扩展/条件格式的既有提示，不影响本轮 hardening 结论。

## 7. 是否影响现有能力

- 对现有物流能力：无预期影响。
- 对现有 BOM 查询主链路：无预期影响。
- 对功率预测 QA：增强边界清晰度和推荐结果可追溯性。
- 对前端：本轮未修改前端代码，但按流程已运行前端 build。

## 8. 下一步建议

如用户确认，可进入人工 review / 合并准备；合并与上线仍需用户明确确认，不自动执行。

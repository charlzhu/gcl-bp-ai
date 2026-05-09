# TASK-plan-power-m5-qa-integration Codex Final

## 任务
M5：接入 PlanBom QA / 智能问答链路。

## 本轮完成
1. NLU Center 增加计划 BOM 功率预测 / 供应商推荐意图：`plan_power_prediction`、`plan_power_supplier_recommendation`。
2. 规则层新增目标功率比例、供应商、标板基准抽取；功率关键槽位对 LLM 采用 fail-closed 策略：
   - `order_tail_no` 必须与规则层原文抽取完全一致；
   - `target_power_ratio` 必须与确定性正则抽取完全一致；
   - `supplier_name` / `benchmark` 必须与规则层原文抽取一致；
   - 否则不采纳 LLM 候选，不允许凭空触发或改变 M3 计算。
3. `PlanBomQaService` 接入 M4 `PlanBomPowerConfigResolverService`，只有 `resolved` 状态才调用 M3。
4. M4 `candidate_required` / `partial` / `not_found` / `no_active_model` 等状态受控返回 B/C，不进入 M3。
5. 预测问答调用 M3 `PowerPredictionEngine.predict()`；推荐问答调用 M3 `PowerRecommendationService.recommend()`。
6. response 保留 `bom_config_resolution`、`power_prediction` / `power_recommendation` 原始追溯。
7. 功率类 presentation 强制确定性展示，绕过 LLM 表达层，避免 LLM 改写中心功率、档位比例、供应商或匹配度。
8. 前端智能问答补充功率预测关键词与类型字段，只做路由和展示，不参与计算。
9. 新增 M5 真实数据业务验收测试，覆盖预测、推荐、显式供应商、缺订单追问、LLM 目标比例/订单/供应商/标板防幻觉、presentation 绕过 LLM。

## 修改文件
- backend/app/api/deps.py
- backend/app/domains/plan_bom/services/nlu_center_service.py
- backend/app/domains/plan_bom/services/qa_service.py
- backend/app/domains/plan_bom/services/answer_presentation_service.py
- frontend/src/api/planBom.ts
- frontend/src/views/business-chat/BusinessChatPage.vue
- tests/business_acceptance/test_plan_power_m5_qa_integration.py
- ai/tasks/running/TASK-plan-power-m5-qa-integration/plan.md
- ai/tasks/running/TASK-plan-power-m5-qa-integration/diff.patch
- ai/tasks/running/TASK-plan-power-m5-qa-integration/test.log
- ai/tasks/running/TASK-plan-power-m5-qa-integration/static_scan.txt
- ai/tasks/running/TASK-plan-power-m5-qa-integration/review_bundle.md

## 验证
- M5 focused：`8 passed in 4.29s`
- M4 regression：`9 passed in 2.78s`
- M3 regression：`9 passed, 2 warnings in 10.43s`
- M2 regression：`9 passed in 9.06s`
- Full tests：`57 passed, 2 warnings in 24.68s`
- `python -m compileall backend/app scripts`：通过
- targeted `git diff --check`：通过
- `npm run build`：通过，仅 Vite chunk size warning
- static scan：`static_findings=0`

## Reviewer
前两轮 reviewer 阻塞项已修复：
1. 功率类 presentation 不再走 LLM；
2. LLM `target_power_ratio` 必须与规则层抽取一致；
3. LLM `order_tail_no`、`supplier_name`、`benchmark` 对功率意图必须与规则层原文证据一致。

终审结果：

```json
{"passed":true,"security_concerns":[],"logic_errors":[],"suggestions":[],"summary":"M5 bundle shows power QA is deterministically grounded by rule-extracted slots, stops before M3 on unresolved M4 states, uses M3 numeric results, bypasses presentation LLM for power, and keeps frontend changes to routing/display only."}
```

## 当前 git 状态快照
```text
## agent/TASK-plan-power-m5-qa-integration
 M backend/app/api/deps.py
 M backend/app/domains/plan_bom/services/answer_presentation_service.py
 M backend/app/domains/plan_bom/services/nlu_center_service.py
 M backend/app/domains/plan_bom/services/power_excel_parser_service.py
 M backend/app/domains/plan_bom/services/qa_service.py
 M frontend/src/api/planBom.ts
 M frontend/src/views/business-chat/BusinessChatPage.vue
?? ai/tasks/running/TASK-plan-power-m3-calculation-engine/codex_final.md
?? ai/tasks/running/TASK-plan-power-m3-calculation-engine/codex_prompt.md
?? ai/tasks/running/TASK-plan-power-m3-calculation-engine/diff.patch
?? ai/tasks/running/TASK-plan-power-m3-calculation-engine/final-acceptance.md
?? ai/tasks/running/TASK-plan-power-m3-calculation-engine/m3_combined.diff
?? ai/tasks/running/TASK-plan-power-m4-bom-config-resolver/
?? ai/tasks/running/TASK-plan-power-m5-qa-integration/
?? backend/app/domains/plan_bom/config/power_aliases.json
?? backend/app/domains/plan_bom/config/power_bom_mapping.yaml
?? backend/app/domains/plan_bom/services/power_config_resolver_service.py
?? backend/app/domains/plan_bom/services/power_prediction_engine.py
?? backend/app/domains/plan_bom/services/power_recommendation_service.py
?? tests/business_acceptance/test_plan_power_m3_prediction_engine.py
?? tests/business_acceptance/test_plan_power_m4_config_resolver.py
?? tests/business_acceptance/test_plan_power_m5_qa_integration.py
```

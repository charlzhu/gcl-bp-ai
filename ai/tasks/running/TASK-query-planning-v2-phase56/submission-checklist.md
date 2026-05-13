# Scoped submission checklist

当前工作区存在其它历史/并行任务脏文件，提交时必须只 stage 下列文件，禁止 `git add -A` / `git add .`。

```bash
git add \
  backend/.env.example \
  backend/app/core/config.py \
  backend/app/domains/logistics/api/endpoints/data_qa.py \
  backend/app/domains/logistics/schemas/data_qa.py \
  backend/app/domains/plan_bom/api/endpoints/qa.py \
  backend/app/domains/plan_bom/schemas/qa.py \
  backend/app/domains/plan_bom/services/qa_service.py \
  backend/app/domains/plan_bom/services/answer_presentation_service.py \
  backend/app/domains/query_planning/services/__init__.py \
  backend/app/domains/query_planning/services/response_meta_exposure_service.py \
  docs/QUERY_PLANNING_V2_PHASE5_GRAY_RELEASE_DESIGN.md \
  tests/business_acceptance/test_plan_bom_qa_multi_candidate_compare.py \
  tests/unit/query_planning/test_query_planning_phase56_response_meta.py \
  ai/tasks/running/TASK-query-planning-v2-phase56/diff.patch \
  ai/tasks/running/TASK-query-planning-v2-phase56/test.log \
  ai/tasks/running/TASK-query-planning-v2-phase56/static-scan.log \
  ai/tasks/running/TASK-query-planning-v2-phase56/review_bundle.md \
  ai/tasks/running/TASK-query-planning-v2-phase56/review-result.json \
  ai/tasks/running/TASK-query-planning-v2-phase56/final-acceptance.md \
  ai/tasks/running/TASK-query-planning-v2-phase56/commit-message.txt \
  ai/tasks/running/TASK-query-planning-v2-phase56/submission-checklist.md \
  ai/tasks/running/TASK-plan-bom-multi-candidate-compare/diff.patch \
  ai/tasks/running/TASK-plan-bom-multi-candidate-compare/test.log \
  ai/tasks/running/TASK-plan-bom-multi-candidate-compare/static-scan.log \
  ai/tasks/running/TASK-plan-bom-multi-candidate-compare/review_bundle.md \
  ai/tasks/running/TASK-plan-bom-multi-candidate-compare/review-result.json \
  ai/tasks/running/TASK-plan-bom-multi-candidate-compare/final-acceptance.md
```

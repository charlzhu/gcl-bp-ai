# Submission checklist: TASK-business-feedback-excel-qa-fix

## Do not use broad staging

当前工作区有其他任务残留的 modified/untracked 文件。提交本任务时禁止：

```bash
git add -A
git add .
```

## Recommended scoped staging

```bash
git add \
  backend/app/domains/logistics/repositories/data_qa_repository.py \
  backend/app/domains/logistics/services/data_qa_planner.py \
  backend/app/domains/logistics/services/data_qa_service.py \
  backend/app/domains/plan_bom/services/qa_service.py \
  tests/business_acceptance/test_business_feedback_excel_qa_regression.py \
  ai/tasks/running/TASK-business-feedback-excel-qa-fix/diff.patch \
  ai/tasks/running/TASK-business-feedback-excel-qa-fix/test.log \
  ai/tasks/running/TASK-business-feedback-excel-qa-fix/static-scan.log \
  ai/tasks/running/TASK-business-feedback-excel-qa-fix/review-result.json \
  ai/tasks/running/TASK-business-feedback-excel-qa-fix/final-acceptance.md \
  ai/tasks/running/TASK-business-feedback-excel-qa-fix/commit-message.txt \
  ai/tasks/running/TASK-business-feedback-excel-qa-fix/submission-checklist.md
```

## Commit message

```text
fix: repair full Excel QA feedback regressions
```

## Final verification evidence

- focused: `14 passed`, exit `0`
- Excel full reproduction: `questions=72, ok=72, errors=0`, exit `0`
- compile: exit `0`
- full business acceptance: `185 passed, 2 warnings`, exit `0`
- frontend build: `✓ built`, exit `0`
- API smoke: done event, no error event
- browser smoke: smart-chat answered logistics carrier KPI with chart/table and 20 rows
- independent review: passed, no security concerns, no logic errors

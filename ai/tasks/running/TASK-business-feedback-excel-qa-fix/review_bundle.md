# Review bundle: TASK-business-feedback-excel-qa-fix

## Scope
Review only these task files; ignore unrelated dirty/untracked workspace state:
- backend/app/domains/logistics/repositories/data_qa_repository.py
- backend/app/domains/logistics/services/data_qa_planner.py
- backend/app/domains/logistics/services/data_qa_service.py
- backend/app/domains/plan_bom/services/qa_service.py
- tests/business_acceptance/test_business_feedback_excel_qa_regression.py (new focused regression test)

## Artifact paths
- patch: /Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/ai/tasks/running/TASK-business-feedback-excel-qa-fix/diff.patch
- static scan: /Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/ai/tasks/running/TASK-business-feedback-excel-qa-fix/static-scan.log
- test log: /Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/ai/tasks/running/TASK-business-feedback-excel-qa-fix/test.log

## Git status snapshot
```text
## agent/TASK-business-feedback-excel-qa-fix
 M backend/app/domains/logistics/repositories/data_qa_repository.py
 M backend/app/domains/logistics/services/data_qa_planner.py
 M backend/app/domains/logistics/services/data_qa_service.py
 M backend/app/domains/plan_bom/services/qa_service.py
?? ai/eval/runs/run_20260507_001940_full_all/clarification_batch_state.md
?? ai/eval/scripts/cron_batch_recover_plan_power_branch_prompt.md
?? ai/tasks/running/TASK-ai-answer-stream/
?? ai/tasks/running/TASK-bom-layout-v2/
?? ai/tasks/running/TASK-bom-query-log/
?? ai/tasks/running/TASK-bom-typography/
?? ai/tasks/running/TASK-bom-visual-polish/
?? ai/tasks/running/TASK-business-chat-markdown-rendering/
?? ai/tasks/running/TASK-business-feedback-excel-qa-fix/
?? ai/tasks/running/TASK-logistics-city-fee-topn/
?? ai/tasks/running/TASK-logistics-ranking-topn-generalization/
?? ai/tasks/running/TASK-plan-bom-batch-upload/
?? ai/tasks/running/TASK-plan-power-exact-bom-disambiguation/
?? ai/tasks/running/TASK-plan-power-fall-ratio-excel-like-table/
?? ai/tasks/running/TASK-plan-power-fall-ratio-real-subrows/
?? ai/tasks/running/TASK-plan-power-fall-ratio-subrows/
?? ai/tasks/running/TASK-plan-power-no-bom-explicit-config/
?? ai/tasks/running/TASK-plan-power-real-business-qa-fix/
?? ai/tasks/running/TASK-plan-power-recommendation-export-polish/
?? ai/tasks/running/TASK-plan-power-recommendation-table-polish/
?? ai/tasks/running/TASK-smart-chat-detail-excel-export/
?? ai/tasks/running/TASK-smart-chat-excel-alignment/
?? ai/tasks/running/TASK-smart-chat-single-fallback/
?? backend/app/services/business_answer_stream_service.py
?? frontend/src/utils/businessMarkdown.ts
?? frontend/src/utils/streamingApi.ts
?? tests/business_acceptance/test_ai_streaming_answer.py
?? tests/business_acceptance/test_business_chat_markdown_rendering.py
?? tests/business_acceptance/test_business_chat_session_lifecycle.py
?? tests/business_acceptance/test_business_feedback_excel_qa_regression.py
?? tests/business_acceptance/test_logistics_region_business_answer.py
?? tests/business_acceptance/test_plan_bom_batch_upload_endpoint.py
?? tests/business_acceptance/test_plan_bom_query_log.py
?? tests/business_acceptance/test_plan_power_real_business_qa_regression.py
?? "\347\273\217\350\220\245\350\256\241\345\210\222\346\231\272\350\203\275\344\275\223\346\265\213\350\257\225\347\273\237\350\256\241.xlsx"

```

## Diff stat tracked production files
```text
 .../logistics/repositories/data_qa_repository.py   | 162 ++++++++++++++++++---
 .../domains/logistics/services/data_qa_planner.py  | 103 +++++++++++--
 .../domains/logistics/services/data_qa_service.py  |  55 ++++++-
 .../app/domains/plan_bom/services/qa_service.py    |  40 ++++-
 4 files changed, 320 insertions(+), 40 deletions(-)

```

## Static scan
```text
# Static scan on task patch added lines
## hardcoded secrets
## shell injection
## dangerous eval/exec
## unsafe deserialization
## SQL f-string heuristic

```

## Verification summary
```text
## focused
- exit: `0`
- key: `14 passed in 1.58s`
## excel_full_reproduction
- exit: `0`
- key: `{"questions": 72, "ok": 72, "errors": 0}`
## compile
- exit: `0`
- key: `see tail`
## full_business_acceptance
- exit: `0`
- key: `185 passed, 2 warnings in 37.78s`
## frontend_build
- exit: `0`
- key: `✓ built in 5.76s | vite chunk-size warning only`
## api_stream_smoke
- exit: `0`
- key: `"event": "done"`
## browser_smoke
- exit: `0` (manual browser tool verification)
- evidence: smart-chat page accepted `25年物流公司发货量分别是多少？`, routed to 物流数据, displayed `已解答`, chart/table, 20 detail rows, no `请求出错`.
```

## Business/review focus
- Verify all Excel feedback questions were fully reproduced: 59 original rows / 72 split subquestions, latest reproduction questions=72 ok=72 errors=0.
- Verify focused tests cover service/repository contracts and guard against hardcoded single-question answers.
- Verify real repository signatures match service calls: region_name, months, monthly_breakdown, hist_city_mw_rank.
- Verify SQL dynamic fragments are constructed only from internal allow-listed clauses and bound params, not raw user input.
- Verify visible calculation text matches filtered scope, especially carrier share denominator under region filters.
- Verify Plan BOM tail ambiguity relaxation is generic (unique model_code + explicit power/material config), not hardcoded to one order/customer.

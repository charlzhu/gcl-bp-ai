# TASK-business-feedback-excel-qa-fix final acceptance

## 结论

通过。业务反馈 Excel 全量问题已完成修复后复跑：原始反馈行 `59/59` 覆盖，拆分可执行子问题 `72/72` 覆盖，最新全量复现结果 `questions=72, ok=72, errors=0`。

本轮没有执行 `commit`、`push`、`deploy`，也没有修改 `.env`、账号、密钥、token 或生产配置。

## 根因

1. focused 测试替身与真实 repository 契约不一致，导致 focused 一度可绿但真实 API/browser 链路仍会失败：
   - 服务层调用 `hist_carrier_kpi_by_year(region_name=...)`，真实 repository 原先不接收 `region_name`。
   - 服务层调用 `hist_customer_mw(months=...)`，真实 repository 原先不接收 `months`。
   - 服务层调用 `hist_unit_fee_per_watt(monthly_breakdown=...)`，真实 repository 原先不接收 `monthly_breakdown`。
   - 服务层规划到 `hist_city_mw_rank`，真实 repository 原先缺少对应方法。
2. 部分物流问题需要按照区域、省份、月份、城市 TopN 等真实业务维度下推过滤；不能用年度总量或全国口径替代。
3. Plan BOM 功率问答中，短尾号多候选与显式功率/材料配置并存时，原逻辑过早澄清，未利用“显式配置 + 唯一版型线索”这类可安全 no-BOM 计算场景。

## 修改文件

### 生产代码

- `backend/app/domains/logistics/repositories/data_qa_repository.py`
  - `hist_carrier_kpi_by_year` 增加 `region_name` 过滤，并让分子与占比分母使用同一过滤范围。
  - `hist_customer_mw` 增加 `months` 过滤，支持客户月度发运量。
  - `hist_unit_fee_per_watt` 增加 `monthly_breakdown`，按 `biz_date` 月份返回月度单瓦价表。
  - 新增 `hist_city_mw_rank`，支持年份 + 区域/省份过滤后的城市发运量 TopN。
- `backend/app/domains/logistics/services/data_qa_planner.py`
  - 增强业务反馈题对应的 query_key/filters/dimensions 规划，覆盖承运商分组、城市 TopN、月度单瓦价、客户月份过滤等通用问法。
- `backend/app/domains/logistics/services/data_qa_service.py`
  - 对齐 repository 新契约。
  - 承运商占比说明改为“当前查询范围内全部承运商”，避免区域题口径误导。
  - 月度单瓦价保留月度粒度，不再用年度总计伪造成月表。
- `backend/app/domains/plan_bom/services/qa_service.py`
  - 默认材料表格改为业务列。
  - 显式功率/材料配置 + 候选唯一版型时，允许转入 no-BOM 显式配置计算；多版型或配置不完整仍 fail-closed 澄清。

### 测试与验收材料

- `tests/business_acceptance/test_business_feedback_excel_qa_regression.py`
  - 新增/修复 focused 业务回归，覆盖 Excel 反馈中关键物流和 Plan BOM 修复路径。
- `ai/tasks/running/TASK-business-feedback-excel-qa-fix/diff.patch`
- `ai/tasks/running/TASK-business-feedback-excel-qa-fix/test.log`
- `ai/tasks/running/TASK-business-feedback-excel-qa-fix/static-scan.log`
- `ai/tasks/running/TASK-business-feedback-excel-qa-fix/review-result.json`
- `ai/tasks/running/TASK-business-feedback-excel-qa-fix/final-acceptance.md`

## 验证结果

| 验证项 | 命令/方式 | 结果 |
|---|---|---|
| focused 回归 | `python -m pytest tests/business_acceptance/test_business_feedback_excel_qa_regression.py -q --tb=short` | `14 passed`, exit `0` |
| Excel 全量复现 | `python ai/tasks/running/TASK-business-feedback-excel-qa-fix/scripts/reproduce_feedback.py` | `{"questions": 72, "ok": 72, "errors": 0}`, exit `0` |
| compile | `python -m compileall -q ...` | exit `0` |
| full business acceptance | `python -m pytest tests/business_acceptance -q --tb=short` | `185 passed, 2 warnings`, exit `0` |
| frontend build | `npm run build --prefix frontend` | `✓ built`, exit `0`；仅 Vite chunk-size warning |
| API stream smoke | 物流问答 streaming API | 返回 `done`，无 error 事件 |
| browser smoke | `/smart-chat` 页面输入 `25年物流公司发货量分别是多少？` | 页面显示“已解答”、图表与 20 行明细，无“请求出错” |
| 静态安全扫描 | added-lines grep scan | 未发现硬编码 secret、shell injection、eval/exec、pickle、SQL f-string heuristic |
| 独立 review | reviewer subagent compact review | passed=true，无 security_concerns / logic_errors |

## 独立审查结论

审查通过。没有发现阻塞安全问题或逻辑错误。SQL 动态片段来自内部固定 allow-list/布尔分支，业务输入通过 bound params 传入；Plan BOM fallback 仅在显式配置且候选可推断唯一 model_code 时生效，多候选多版型仍澄清。

非阻塞建议：

1. 后续可在 service/planner 边界进一步 clamp `top_n` 和月份范围，避免无意义的大范围查询。
2. `hist_city_mw_rank.total_shipment_mw` 当前是返回 TopN 行小计；当前服务只使用 `items`，后续若展示总量建议改名或另查过滤范围总量，避免误用。

## 风险与回滚

- 当前工作区存在较多与本任务无关的历史 untracked/dirty 文件；提交时必须按任务范围显式 `git add`，禁止 `git add -A`。
- 本轮没有 commit/push/deploy。若需回滚本任务代码，可针对上述 4 个生产文件恢复，并移除本任务测试/验收材料。

## 提交准备

建议提交信息：

```text
fix: repair full Excel QA feedback regressions
```

建议仅暂存以下文件：

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
  ai/tasks/running/TASK-business-feedback-excel-qa-fix/commit-message.txt
```

建议提交命令（需人工执行或再次明确授权）：

```bash
git commit -m "fix: repair full Excel QA feedback regressions"
```

## 当前 git 摘要

```text
## agent/TASK-business-feedback-excel-qa-fix
 M backend/app/domains/logistics/repositories/data_qa_repository.py
 M backend/app/domains/logistics/services/data_qa_planner.py
 M backend/app/domains/logistics/services/data_qa_service.py
 M backend/app/domains/plan_bom/services/qa_service.py
 M frontend/src/layouts/AppLayout.vue
 M tests/business_acceptance/test_plan_power_frontend_upload_entry.py
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

## 任务内 tracked diff stat

```text
 .../logistics/repositories/data_qa_repository.py   | 162 ++++++++++++++++++---
 .../domains/logistics/services/data_qa_planner.py  | 103 +++++++++++--
 .../domains/logistics/services/data_qa_service.py  |  55 ++++++-
 .../app/domains/plan_bom/services/qa_service.py    |  40 ++++-
 4 files changed, 320 insertions(+), 40 deletions(-)

```

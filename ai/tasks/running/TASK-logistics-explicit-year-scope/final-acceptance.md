# TASK-logistics-explicit-year-scope 最终验收报告

## 1. 问题与结论

用户问题示例：`华润新能源（皮山）有限公司 项目 24年发运量是多少`。

本轮修复目标：当用户在问题中明确给出 `24年/2024年` 时，物流客户历史发运量问答必须按 2024 年过滤，并且页面可见的答案、口径与风险提示不能再显示“未给年份 / 默认按 2023–2025 历史累计”这类误导提示；明细表也要展示统计范围，避免用户不清楚 `480.413MW` 是 2024 年值还是历史累计值。

结论：已通过。明确年份场景返回 `2024年` 口径，风险提示中不再出现“未给年份/2023–2025 默认累计”，结果表新增 `scope_label` 列用于展示统计范围。

## 2. 当前仓库与分支

- 当前分支：`agent/TASK-logistics-city-carrier-scope-fix`
- 当前工作区存在较多与本任务无关的 dirty / untracked WIP 文件。本轮验收与审查聚焦以下任务相关文件：
  - `backend/app/domains/logistics/services/data_qa_service.py`
  - `tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py`
- 任务产物：
  - `ai/tasks/running/TASK-logistics-explicit-year-scope/diff.patch`
  - `ai/tasks/running/TASK-logistics-explicit-year-scope/test.log`
  - `ai/tasks/running/TASK-logistics-explicit-year-scope/final-acceptance.md`

## 3. 根因

`hist_customer_mw` 单客户历史发运量链路存在两个用户可见口径问题：

1. 计算说明曾无条件追加“未给年份时默认按 2023–2025 历史台账累计统计。”，即使 planner 已经把 `24年` 识别为 `year=2024`，表达层仍会把该说明展示到“口径与风险提示”。
2. 明细表列只包含 `shipment_mw`，虽然行数据里有 `scope_label`，但列定义没暴露该字段，导致前端只展示“发运量”，用户无法从表格判断该值对应 `2024年` 还是历史累计范围。

## 4. 修复内容

### 后端 service

文件：`backend/app/domains/logistics/services/data_qa_service.py`

- `hist_customer_mw` 查询下推 `months=filters.get("months")`，保留明确月份过滤能力。
- 将 `calculation_logic` 改为按筛选条件动态生成：
  - `year is None`：才展示“未给年份时默认按 2023–2025 历史台账累计统计。”
  - `year + months`：展示“已按用户给出的年份和月份过滤统计。”
  - `year only`：展示“已按用户给出的年份过滤统计。”
- 结果表列从 `["shipment_mw"]` 改为 `["scope_label", "shipment_mw"]`，明细表可直接展示 `统计范围=2024年`。

### 回归测试

文件：`tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py`

新增测试：`test_explicit_two_digit_year_customer_mw_does_not_show_missing_year_caveat`

覆盖内容：

- planner 将 `24年` 识别为 `year=2024`。
- service 下推 `year=2024` 到 `hist_customer_mw`。
- `answer_summary` 包含 `2024年`。
- `answer_summary / calculation_logic / warnings / presentation.caveats` 中均不包含：
  - `未给年份`
  - `2023–2025`
  - `2023-2025`
- 结果行 `scope_label == "2024年"`。
- 结果列包含 `scope_label`，保证前端明细表展示统计范围。

## 5. TDD 证据

- RED：新增回归测试先失败，失败点为 `result_table.columns == ['shipment_mw']`，缺少 `scope_label`，因此无法在明细表展示 2024 年统计范围。
- GREEN：补齐 `scope_label` 列并保留条件化年份口径后，新增测试通过。

## 6. 验证结果

完整日志见：`ai/tasks/running/TASK-logistics-explicit-year-scope/test.log`

已执行：

```bash
python -m pytest tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py::test_explicit_two_digit_year_customer_mw_does_not_show_missing_year_caveat -q
# 1 passed

python -m pytest tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py -q
# 28 passed

python -m pytest tests/business_acceptance -q
# 196 passed, 2 warnings

python -m compileall -q backend/app/domains/logistics/services/data_qa_service.py tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py
# passed

cd frontend && npm run build
# passed；仅有既有 chunk size warning

git diff --check -- backend/app/domains/logistics/services/data_qa_service.py tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py
# passed
```

静态扫描：

- 对任务相关文件扫描 secret-like assignment / deprecated `X-Plan-Power-Admin-Token`：通过。
- 对全部 tracked dirty 文件的宽泛扫描命中非本任务文件中的变量名/断言文本 false positive：
  - `backend/app/domains/plan_bom/services/qa_service.py` 中普通局部变量 `token = ...`
  - `tests/business_acceptance/test_plan_power_frontend_upload_entry.py` 中断言“不包含 X-Plan-Power-Admin-Token”
  这些不属于本轮修改范围，且不是密钥泄漏。

## 7. Reviewer 审查

独立 reviewer 结论：PASS，不建议阻塞返工。

Reviewer 重点确认：

- `hist_customer_mw` 明确年份时不再展示“未给年份默认 2023–2025”。
- 表格包含 `scope_label`，可见统计范围。
- 新增测试覆盖 planner、service、presentation caveats。
- 独立执行验证通过：新增定向测试、focused file、full business acceptance、compileall、额外 smoke。

Reviewer 非阻塞建议：

- 未来可将测试参数化覆盖 `24年/2024年` 两种写法。
- `hist_customer_mw_ranking` 等相邻 query_key 若产品要求同样展示显式年份口径，可另起任务扩展。

## 8. 风险与影响范围

- 影响范围：物流数据问答 `hist_customer_mw` 单客户历史发运量分支。
- 不影响：计划 BOM、功率预测、物流其它主链路。
- 未给年份场景仍保留默认历史累计说明，不会误删真实需要提示的风险口径。
- 当前仓库有大量非本任务 WIP dirty/untracked 文件，提交前需由人工确认是否一起处理或拆分提交。

## 9. 是否需人工处理

无需人工介入代码返工。建议人工在提交前确认当前 dirty 工作区中的其它 WIP 是否纳入同一提交；本任务建议只提交上述两个任务相关文件及验收产物。

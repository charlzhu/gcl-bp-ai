# TASK-business-feedback-excel-qa-fix Codex 执行提示

你是执行工程师 Codex。请在当前仓库 `/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai` 内完成修复。

## 绝对约束
- 禁止 commit / push / deploy。
- 禁止修改 `.env`、密钥、token、生产连接串；不要恢复临时 admin token。
- 禁止数据库迁移、结构变更、删库、大量删除文件。
- 禁止 hardcode Excel 单题答案、客户/订单/城市/供应商单例答案；只能做通用 NLU、检索、计算、展示能力修复。
- 新增/修改代码必须写中文注释，说明函数/参数/返回值/业务口径。

## 已完成 RED
focused RED 已运行并保存在：
`ai/tasks/running/TASK-business-feedback-excel-qa-fix/current-focused-before-fix.log`
命令：
`python -m pytest tests/business_acceptance/test_business_feedback_excel_qa_regression.py -q`
当前 13 failed / 1 passed。

## 需要修复的 focused 回归
测试文件：`tests/business_acceptance/test_business_feedback_excel_qa_regression.py`
必须让该文件全绿，不允许删除/弱化测试断言。

主要失败点：
1. R17 客户名尾缀“的”未裁剪，`customer_name` 应为 `华阳`，且保留月份 `[1]`。
2. R50 “物流公司/承运商 + 分别/各”应路由到 `hist_carrier_kpi_by_year`，不是 `hist_mw_summary`。
3. R57 承运商年度分组应下推 `region_name=西北`。
4. R51/R52/R53 城市发运量 TopN 应新增或复用 `hist_city_mw_rank`，支持 year + region/province + top_n，返回 city 表。
5. R22 “1-12月 ... 单瓦价”应设置 `dimensions=["biz_month"]`、`monthly_breakdown=True`，服务层返回月份表。
6. R45 “额外费用...项目/原因”月份明确时先返回 `sys_extra_fee_summary` 总额，warnings 说明项目/原因明细口径未固化，而不是直接 UNSUPPORTED。
7. PlanBom 测试 fixture 当前用 fake nlu；如果生产代码已有通用 NLU，优先在测试中使用真实 PlanBomNluService，或补一个最小 fake `understand`；但不得为单题硬编码答案到生产代码。
8. R39 显式材料配置完整时，no-BOM 功率推荐不能被订单尾号候选阻断。
9. Plan BOM 默认材料表业务列不应包含 `source_file`、`sap_code`、`version_no`。
10. 负例：项目名称维度仍 unsupported；同一订单自对比/多候选无显式配置仍 clarification。

## 允许修改路径
- `backend/app/domains/logistics/services/*.py`
- `backend/app/domains/logistics/repositories/*.py`
- `backend/app/domains/plan_bom/services/*.py`
- `tests/business_acceptance/test_business_feedback_excel_qa_regression.py`
- 本任务目录下报告/日志

如确需改其他文件，在最终说明原因。

## 必须运行并记录
1. focused：`python -m pytest tests/business_acceptance/test_business_feedback_excel_qa_regression.py -q`
   - 输出到 `ai/tasks/running/TASK-business-feedback-excel-qa-fix/codex-green.log`
2. 如果 focused 通过，再运行至少：
   - `python -m pytest tests/business_acceptance/test_logistics_region_business_answer.py tests/business_acceptance/test_plan_power_real_business_qa_regression.py tests/business_acceptance/test_business_feedback_excel_qa_regression.py -q`
   - 输出到 `ai/tasks/running/TASK-business-feedback-excel-qa-fix/codex-regression.log`

## 交付产物
生成/更新：
- `ai/tasks/running/TASK-business-feedback-excel-qa-fix/codex-green.log`
- `ai/tasks/running/TASK-business-feedback-excel-qa-fix/codex-regression.log`
- `ai/tasks/running/TASK-business-feedback-excel-qa-fix/codex-investigation.md`
- `ai/tasks/running/TASK-business-feedback-excel-qa-fix/codex-final.md`

最终回复只给简短摘要，不要 commit。
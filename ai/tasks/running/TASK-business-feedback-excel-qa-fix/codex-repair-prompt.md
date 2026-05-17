你是 Codex 执行工程师。任务：修复当前 `TASK-business-feedback-excel-qa-fix` 的 focused 回归失败，必须按 TDD 和通用能力修复，禁止硬编码单个 Excel 题目答案。

工作目录：/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai

背景：
- 业务反馈 Excel 已完整解析：59 个问题行，拆分为 72 个可执行子问题，已生成 `ai/tasks/running/TASK-business-feedback-excel-qa-fix/excel-analysis.md` 和 `reproduction.md/json`。
- 你上一次部分修改后，focused 测试仍失败，失败日志在：`ai/tasks/running/TASK-business-feedback-excel-qa-fix/focused-after-partial-codex.log`。
- 当前允许修改：
  - `backend/app/domains/logistics/services/data_qa_planner.py`
  - `backend/app/domains/logistics/services/data_qa_service.py`
  - `backend/app/domains/logistics/repositories/data_qa_repository.py`
  - `backend/app/domains/plan_bom/services/qa_service.py`
  - `backend/app/domains/plan_bom/services/nlu_center_service.py`
  - `tests/business_acceptance/test_business_feedback_excel_qa_regression.py`
  - 当前任务目录下验收日志/报告。
- 禁止：commit/push/deploy；改 .env/密钥/token；修改数据库迁移；硬编码某个客户/订单/题目答案；大范围重构。

你必须先读取：
1. `ai/tasks/running/TASK-business-feedback-excel-qa-fix/root-cause-and-acceptance.md`
2. `ai/tasks/running/TASK-business-feedback-excel-qa-fix/focused-after-partial-codex.log`
3. `tests/business_acceptance/test_business_feedback_excel_qa_regression.py`
4. 相关生产代码。

当前 focused 测试命令：
`python -m pytest tests/business_acceptance/test_business_feedback_excel_qa_regression.py -q`

已知失败类别：
1. R17：`hist_customer_mw` service 没把 months 下推，summary 没展示月份。
2. R57：承运商 KPI service/repository 没支持 region_name 过滤，summary 未展示区域。
3. R51/R52/R53：城市发运量 TopN planner 未泛化命中 `发货量/发运量` + `排名前5/TOP5/前五` + `区域/省份`；service/repository 需要 `hist_city_mw_rank`。
4. R22：月度单瓦价 planner 已带 `monthly_breakdown`，但 service 没传给 repository，且 table columns 仍是汇总列。
5. R45：额外费用项目/原因明细未固化时，应先返回总额，并给 warnings 说明“项目/原因明细口径尚未固化”。
6. Plan BOM 测试 fixture 当前 `nlu_service=SimpleNamespace()` 导致 AttributeError；需要用真实 NLU 或测试 fake NLU（优先真实确定性 NLU），并确保生产代码通用行为：显式 no-BOM 功率配置不被尾号候选阻断；默认材料表隐藏 source/version/SAP 等追溯列；自对比/多候选无显式配置仍澄清。

要求：
- 修复必须增强通用能力，不能为单题造数。
- 新增/修改代码必须有中文注释。
- 运行 focused 测试到通过，保存日志：`ai/tasks/running/TASK-business-feedback-excel-qa-fix/codex-repair-focused.log`。
- 如果你改了 repository，至少运行一次对应 focused 测试；如受本地数据库限制，说明原因。
- 最后写报告：`ai/tasks/running/TASK-business-feedback-excel-qa-fix/codex-repair-report.md`，包含：根因、修改文件、测试命令与结果、仍未解决风险。

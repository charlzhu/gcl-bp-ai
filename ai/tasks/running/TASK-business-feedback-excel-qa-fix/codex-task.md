# Codex 执行任务卡：TASK-business-feedback-excel-qa-fix

## 角色与边界
你是执行工程师 Codex。Hermes/技术经理负责最终验收，你不能自证完成。

必须遵守：
- 禁止 commit / push / deploy。
- 禁止修改 `.env`、密钥、token、生产连接串；不要恢复任何临时 admin token。
- 禁止数据库迁移/结构变更/删库/大量删除文件。
- 禁止 hardcode Excel 单题答案、客户/订单/城市/供应商单例答案；只能做通用 NLU、检索、计算、展示能力修复。
- 新增/修改代码必须写中文注释，说明函数、参数、返回值和业务口径。
- 严格 TDD：先写 RED 测试并运行确认失败，再改生产代码，再跑 GREEN。

## 输入材料
- Excel 解析：`ai/tasks/running/TASK-business-feedback-excel-qa-fix/excel-analysis.md`
- 当前复现：`ai/tasks/running/TASK-business-feedback-excel-qa-fix/reproduction.md` / `.json`
- 逐条核对矩阵：`ai/tasks/running/TASK-business-feedback-excel-qa-fix/feedback-triage-matrix.md`
- 根因与验收：`ai/tasks/running/TASK-business-feedback-excel-qa-fix/root-cause-and-acceptance.md`

## 本轮优先修复范围（高置信，可通用修复）
优先修复下列 fail/partial_fail 中不需要业务数据 owner 决策的能力：

### L1 槽位/路由
1. R17：`2024年1月份客户华阳的总发运量是多少MW？`
   - 当前客户槽为 `华阳的` 且结果 0；应抽取 `华阳`，并保留月份过滤，返回接近业务反馈 `200.18712MW`。
   - 通用要求：客户/项目/承运商名后的助词 `的` 不应进入实体；历史客户发运量支持月份过滤。
2. R50：`25年物流公司发货量分别是多少？`
   - 当前走全年总量；应识别“物流公司/承运商 + 分别/各” 为承运商分组，走 `hist_carrier_kpi_by_year` 或等价分组 query。
3. R57：`2025年各家物流承运商在西北区域的承运量分别是多少`
   - 当前忽略 `西北区域`，结果与全局相同；应按区域过滤承运商分组。
4. R21：`26年 经营计划 刘娟 用车总费用是多少`
   - 如系统表中有申请人/联系人/创建人等稳定字段，加入通用个人过滤；若没有稳定字段，不要硬答，输出明确口径说明并在报告标记需数据 owner。

### L2 历史城市/线路排名
5. R51/R52/R53：历史区域/省份下城市发运量 TopN：
   - `25年华东区域发货量排名前5的城市是哪些，发货量分别是多少`
   - `请列出2025年安徽各城市发运量TOP5及具体数值`
   - `2024年安徽省各城市发运量排名前五？`
   - 当前都走总量；应新增/复用确定性 query_key，按 delivery city 聚合 MW，支持 year + region/province + top_n。
6. R60：`2025年合肥至马鞍山17.5米车的平均运费` 及括号中的 Q1 承运商平均运费排名。
   - 如现有字段足够，支持 year/quarter/origin/city/vehicle/carrier ranking 的平均单票运费；否则保留安全澄清，但不能答非所问。

### L3 计算/展示中可安全修复部分
7. R22：`24年 1-12月 目的地是江苏省的单瓦价是多少`
   - 当前返回全年汇总 summary；应在用户要求每个月/1-12月时返回按月表格/图表，列出月份、总费用、总发运MW、单瓦价，公式为 `SUM(total_fee [+ extra_fee按既有历史口径]) / SUM(actual_watt)`。
8. R45：`2026年1月份额外费用产生多少金额，分别是什么项目？什么原因产生的？`
   - 当前 unsupported；至少当月份明确时返回额外费用总额（反馈 1 月异常费用 29610 元可作回归期望），并说明项目/原因明细口径未固化；如果系统已有项目/原因字段，则返回明细表。
9. R28/R29/R46/R27 需要先底表核对。如果缺少稳定字段或与反馈值不一致原因不明，不要造数；生成调查日志并在 final report 标记需数据 owner。若能通过通用解析（如 power 文本 `720W` 数字提取、运输方式别名）修复，则加测试后修。

### L4 Plan BOM / Plan Power
10. R39：显式材料配置已完整但带有不可靠尾号候选时，不应被 BOM 多候选阻断；应允许走 no-BOM 显式配置功率推荐，并在 caveat 中提示忽略了未确认订单候选。
11. R34/R36/R38/R55：BOM 核心材料表默认业务展示列应精简，避免 source_file/version/SAP/追溯字段撑爆表格；多款玻璃/焊带/汇流条/线盒应按材料类别排序/分段。导出请求仍可保留追溯字段，但 UI 默认 table 应更业务友好。

## 测试要求
新增一个或多个回归测试，建议文件：
- `tests/business_acceptance/test_business_feedback_excel_qa_regression.py`

至少覆盖：
- R17 客户华阳 + 月份，不含尾缀“的”，结果约 200.18712MW 或按当前底表稳定值断言。
- R50 物流公司分别 -> 承运商分组，不是总量。
- R57 承运商 + 西北区域过滤，结果行与全局不同，filters/summary 明确区域。
- R51/R52/R53 城市 TopN 返回 table/mixed、城市列、top_n 行数。
- R22 月度单瓦价返回 12 行或有数据月份行，含 total_fee/shipment_mw/unit_fee_per_watt。
- R45 2026年1月额外费用总额可答，并保留项目/原因明细口径提示。
- R39 no-BOM 显式配置推荐不因 00106 多候选而 clarification。
- Plan BOM 默认表格列精简：业务默认 table 不包含 `source_file`，尽量不包含 `sap_code`/`version_no`；导出/trace 如需保留可另放。
- 负例：项目名称维度、同一订单自对比、多候选订单没有显式配置时仍澄清/安全拒答；不要 broaden。

必须先运行 focused 测试看到 RED，再改代码，再运行 GREEN。

## 允许修改路径
- `backend/app/domains/logistics/services/*.py`
- `backend/app/domains/logistics/repositories/*.py`
- `backend/app/domains/plan_bom/services/*.py`
- `tests/business_acceptance/test_business_feedback_excel_qa_regression.py`
- 本任务目录下报告/日志文件

如确需改其他文件，先在报告中说明原因，但不要触碰高风险文件。

## 交付产物
在 `ai/tasks/running/TASK-business-feedback-excel-qa-fix/` 下生成：
- `codex-red.log`
- `codex-green.log`
- `codex-investigation.md`（R27/R28/R29/R46 等底表核对结论，不能造数）
- `codex-final.md`（修改文件、修复点、测试命令与结果、未解决/需人工确认项）

最终不要 commit。
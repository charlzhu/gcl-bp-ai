# TASK-business-feedback-excel-qa-fix

## 目标
基于 `经营计划智能体测试统计.xlsx` 中业务员反馈的不准问答，逐条核对问题值、答案结构、图表/表格使用和表达清晰度，定位通用根因并按 TDD 修复。

## 边界
- 允许：后端问答 planner/service/repository、前端 business-chat 展示、业务验收测试、任务验收材料。
- 禁止：自动 commit/push/deploy；修改 .env/密钥；数据库迁移；硬编码单题答案；覆盖原始 Excel。

## 验收标准
1. Excel 行不能因“已解答”字样跳过，必须复现或说明数据/口径不可自动确认原因。
2. 通用修复覆盖同类问法，新增 RED/GREEN 回归测试。
3. focused/related/full/backend compile/frontend build/static scan/reviewer 通过或说明阻断。
4. 生成 diff.patch、test.log、review_bundle.md、final-acceptance.md。

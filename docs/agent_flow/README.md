# AI 龙虾协作流程

本项目采用固定三分支、三 Codex 龙虾、Hermes 复盘模式。

## 固定分支

- agent/bp-main：稳定基线，技术主管龙虾只读分析
- agent/bp-dev：开发分支，全栈开发龙虾开发
- agent/bp-test：测试分支，测试运维龙虾验收

## 固定角色

- 技术主管龙虾：只读拆任务，输出 TASK_CARD.md
- 全栈开发龙虾：读取 TASK_CARD.md，输出 DEV_PLAN.md 和 DEV_REPORT.md
- 测试运维龙虾：读取 TASK_CARD.md 和 DEV_REPORT.md，输出 TEST_REPORT.md
- Hermes Agent：读取全部交接文件，输出 HERMES_REVIEW.md

## 人工闸门

以下动作必须由用户确认：

1. 确认技术主管任务卡
2. 确认全栈开发实施计划
3. 确认开发 diff
4. 确认 agent/bp-dev 同步到 agent/bp-test
5. 确认测试报告
6. 确认 agent/bp-test 合并到 agent/bp-main
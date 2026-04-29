# AGENT_FLOW.md

## 当前需求

- 需求编号：
- 需求名称：
- 当前阶段：
- 当前负责人：

## 分支状态

- 稳定基线：agent/bp-main
- 开发分支：agent/bp-dev
- 测试分支：agent/bp-test

## 当前闸门

- [ ] Hermes 已整理需求
- [ ] 技术主管任务卡已确认
- [ ] 全栈开发实施计划已确认
- [ ] 全栈开发 diff 已确认
- [ ] agent/bp-dev 已同步到 agent/bp-test
- [ ] 测试运维报告已确认
- [ ] Hermes 合并前复盘已确认
- [ ] agent/bp-test 已合并到 agent/bp-main

## 禁止事项

- 不允许自动 push
- 不允许自动部署
- 不允许自动删除文件
- 不允许提交 .env / 日志 / 缓存 / tmp / output


## AI 龙虾协作规则

本项目采用三 Codex 龙虾 + Hermes Agent 复盘模式。

所有 AI 执行任务前，必须优先读取：

1. `AGENTS.md`
2. `README_WORKSPACE.md`
3. `docs/CURRENT_STATUS.md`
4. `docs/HANDOFF.md`
5. `docs/KNOWN_ISSUES.md`
6. `docs/BUSINESS_RULES.md`
7. `docs/agent_flow/README.md`
8. `docs/agent_flow/CURRENT_TASK.md`
9. 当前角色对应的交接文件

### 角色文件

- 技术主管龙虾：读取 `CURRENT_TASK.md`，输出 `TASK_CARD.md`
- 全栈开发龙虾：读取 `TASK_CARD.md`，先输出 `DEV_PLAN.md`，开发后输出 `DEV_REPORT.md`
- 测试运维龙虾：读取 `TASK_CARD.md` 和 `DEV_REPORT.md`，输出 `TEST_REPORT.md`
- Hermes Agent：读取 `CURRENT_TASK.md`、`TASK_CARD.md`、`DEV_PLAN.md`、`DEV_REPORT.md`、`TEST_REPORT.md`，输出 `HERMES_REVIEW.md`

### 禁止事项

- 不允许自动 push
- 不允许自动部署
- 不允许提交 `.env`
- 不允许提交日志、缓存、临时文件、构建产物
- 不允许把历史文档中的通过结论当成本轮实测结果
- 不允许把局部通过说成全量通过
# AI 公司总规则

本项目采用 Hermes Agent + Codex CLI 的本地 AI 协作开发模式。

## 角色分工

- 用户：CEO，负责提出目标、审批提交、审批合并、决定上线。
- Hermes：CTO + 项目经理 + 调度器 + 风险控制官，负责拆解任务、调用 Codex、收集报告、控制风险。
- Codex Fullstack：全栈开发龙虾，负责按任务修改前端和后端代码。
- Codex Tester：测试验收龙虾，负责测试、构建、回归和测试报告。
- Codex Reviewer：代码审查龙虾，负责审查 diff、风险和验收结论。
- Codex Backend / Frontend / Docs：备用专业角色，当前默认不启用，后续任务复杂时可由 Hermes 选择启用。

## 总原则

1. 每次只处理 `ai/inbox/requirement.md` 或指定任务文件中的当前需求。
2. 一切以当前仓库代码为准，不以历史聊天或历史补丁为事实来源。
3. 任务开始前必须先阅读 `AGENTS.md`、`README_WORKSPACE.md`、`docs/CURRENT_STATUS.md`、`docs/HANDOFF.md`、`docs/NEXT_TASK.md`。
4. 不做任务外优化。
5. 不做大范围重构，除非需求明确要求且用户批准。
6. 不修改密钥、账号、token、密码、证书。
7. 不自动合并 main / master 分支。
8. 不自动 push。
9. 不自动部署生产环境。
10. 不在测试失败时宣称完成。
11. 所有任务结果必须沉淀到 `ai/reports/` 下。
12. 所有任务必须可回溯、可审查、可回滚。

## Git 规则

1. 推荐在 `agent/TASK-xxxx` 分支执行自动化任务。
2. 自动化脚本只生成报告和建议 commit message。
3. 是否 `git add`、`git commit`、`git merge`、`git push` 必须由用户确认。
4. `ai/reports/` 默认作为本地运行产物，不建议提交到仓库。

## 输出要求

每轮任务结束后，必须尽量生成：

- `final-acceptance.md`
- `diff.patch`
- `diffstat.txt`
- `git-status.txt`
- `test.log`
- `codex-fullstack-result.md`
- `codex-reviewer-result.md`

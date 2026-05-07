# Company Task Protocol V1

## 1. 目标

本协议用于约束 Hermes TUI + Codex Runner 的本地一人公司代码构建流程。

核心目标：

1. Hermes 承担技术经理角色。
2. Codex 承担受控执行工程师角色。
3. 每个任务都有状态、事件、附件、测试、质量检查和交付报告。
4. 任务可以在窗口关闭后恢复查看。
5. 不自动 commit、push、deploy。

## 2. 任务状态

- DRAFT：需求草稿
- PLANNING：技术经理规划
- WAIT_CONFIRM：等待用户确认
- RUNNING：Codex 执行
- TESTING：运行测试
- REVIEWING：收集 diff 和质量检查
- WAIT_ACCEPT：等待人工验收
- DONE：人工确认完成
- FAILED：失败
- PAUSED：暂停
- ROLLED_BACK：已回滚

## 3. 标准任务目录

```text
ai/tasks/<state>/TASK-*/
  requirement.md
  attachments/
  attachments_manifest.md
  attachments_summary.md
  attachments_inventory.json
  plan.md
  acceptance.md
  codex_prompt.md
  repair_prompt_round_1.md
  repair_prompt_round_2.md
  state.json
  event.jsonl
  codex_stdout.log
  codex_stderr.log
  codex_final.md
  safety.log
  test.log
  git_status.txt
  diff_stat.txt
  diff.patch
  quality_review.json
  quality_review.md
  report.md
```

## 4. 附件规则

1. 附件统一放入 `ai/inbox/attachments/`。
2. 必须用 `ai/inbox/attachments_manifest.md` 描述用途、类型、是否允许读取、是否允许修改。
3. 创建任务时复制附件到 TASK 目录。
4. TASK 附件是本任务资产，原始 inbox 附件默认只读。
5. 自动生成 `attachments_summary.md`，Codex 优先读摘要和 manifest。
6. Excel 只提取工作表、表头和样例行。
7. 图片 V1 只登记路径，页面含义需要在 manifest 中人工描述。
8. PDF V1 不强行 OCR，不猜测内容。
9. ZIP V1 只列文件树，不自动解压覆盖项目。
10. report.md 必须记录附件使用情况。

## 5. 技术经理闭环

```text
需求输入
  ↓
复制附件并生成摘要
  ↓
生成计划和验收标准
  ↓
用户确认
  ↓
Codex 首轮执行
  ↓
测试
  ↓
收集 diff
  ↓
质量检查
  ↓
PASS/WARN -> 生成报告 -> WAIT_ACCEPT
FAIL -> 定向修复，最多 2 次
仍失败 -> FAILED + 失败报告
```

## 6. 质量等级

- PASS：测试通过，质量检查通过，可以进入人工验收。
- WARN：测试通过，但涉及敏感文件、diff 较大或有非阻塞风险，可以进入人工验收但必须重点检查。
- FAIL：测试失败、修改禁止目录、缺关键产物，不允许验收。
- BLOCKED：需求不清、附件不可解析、环境缺失或需要人工业务确认。

## 7. 绝对禁止

1. 自动 commit。
2. 自动 push。
3. 自动部署。
4. 连接生产数据库。
5. 修改 `.env` 和真实密钥。
6. 覆盖 `ai/inbox/attachments` 原始附件。
7. 测试失败后进入 DONE。
8. 无报告交付。

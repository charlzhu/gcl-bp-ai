# Company Task Protocol V1

## 1. 目标

本协议用于约束 Hermes TUI / Web 控制台 + Codex Runner 的本地一人公司代码构建流程。

核心目标：

1. Hermes 承担技术经理角色。
2. Codex 承担受控执行工程师角色。
3. 每个任务都有状态、事件、附件、测试、质量检查和交付报告。
4. 任务可以在窗口关闭后恢复查看。
5. 不自动 commit、push、deploy。
6. 对阶段型任务，严格遵守 `ai/inbox/requirement.md` 和 `docs/NEXT_TASK.md` 中声明的阶段边界。

---

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

---

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

---

## 4. 附件规则

1. 附件统一放入 `ai/inbox/attachments/`。
2. 必须用 `ai/inbox/attachments_manifest.md` 描述用途、类型、是否允许读取、是否允许修改。
3. 创建任务时复制附件到 TASK 目录。
4. TASK 附件是本任务资产，原始 inbox 附件默认只读。
5. 自动生成 `attachments_summary.md`，Codex 优先读摘要和 manifest。
6. Excel 默认只提取工作表、表头和样例行。
7. 如果 `requirement.md` 明确要求 Excel 公式 / 宏 / 数据验证 / 单元格依赖审计，则允许对 Excel 做更深层只读分析，包括读取公式文本、命名区域、数据验证、隐藏行列、合并单元格、VBA 工程是否存在等信息。
8. 对 xlsm 文件，允许检查是否存在 `vbaProject.bin`、宏模块名称和宏依赖风险；不允许修改原始 xlsm 附件。
9. 图片 V1 只登记路径，页面含义需要在 manifest 中人工描述。
10. PDF V1 不强行 OCR，不猜测内容。
11. ZIP V1 只列文件树，不自动解压覆盖项目。
12. report.md 必须记录附件使用情况。
13. 任何原始附件都不允许被覆盖、重命名、删除或作为代码生成输出目录。

---

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

如果用户已经在控制台明确说“正式启动 / 开始执行 / 确认执行”，且 `requirement.md` 边界清晰，可以视为本轮任务已确认。

---

## 6. 阶段边界规则

当 `requirement.md` 或 `docs/NEXT_TASK.md` 明确规定：

```text
本轮只执行 M1 / 只产出文档 / 完成后等待确认
```

则 Hermes 和 Codex 必须停止在该阶段边界，不允许自动进入后续 M2/M3/M4/M5。

即使存在“完整交付模式”，也不能越过用户明确写出的阶段边界。

---

## 7. 质量等级

- PASS：测试通过，质量检查通过，可以进入人工验收。
- WARN：测试通过，但涉及敏感文件、diff 较大或有非阻塞风险，可以进入人工验收但必须重点检查。
- FAIL：测试失败、修改禁止目录、缺关键产物，不允许验收。
- BLOCKED：需求不清、附件不可解析、环境缺失或需要人工业务确认。

---

## 8. 绝对禁止

1. 自动 commit。
2. 自动 push。
3. 自动部署。
4. 连接生产数据库。
5. 修改 `.env` 和真实密钥。
6. 覆盖 `ai/inbox/attachments` 原始附件。
7. 测试失败后进入 DONE。
8. 无报告交付。
9. hardcode 附件样例题答案。
10. 将假样例题当作真实验收数据。
11. 让 LLM 直接计算必须由后端确定性代码计算的业务结果。

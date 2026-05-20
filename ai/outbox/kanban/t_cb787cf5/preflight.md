# preflight

- task: t_cb787cf5 / M10-A 物流 NL2SQL candidate SQL safety gate 最小 TDD 切片
- tenant: gcl-planning-assistant
- worktree: /Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/nl2sql-m10a-candidate-sql-gate
- branch: feature/nl2sql-m10a-candidate-sql-gate
- base/head: f24d39ae318cea9af081aa05b3edfdcdcf46ef33

## 启动核对

1. kanban_show 已读取任务正文和边界。
2. 指定 worktree 初始不存在；按 kanban-worker worktree 规则，从主仓库 base commit 创建了指定 worktree/branch。
3. 新 worktree `git status --short` 为空，未发现本任务 worktree 内非任务 dirty 或冲突。
4. 主仓库存在历史 dirty `.gitignore`，但本次不在主仓库工作，也不 stage/commit/push/deploy。

## 当前仓库能力判断

- 已完成能力：已有 `LogisticsSqlSafetyChecker`，用于校验 renderer 产物 `LogisticsRenderedSql`，覆盖只读 SELECT、多语句/注释/危险函数、表字段 allow-list、参数、JOIN、LIMIT 上限等二次安全校验。
- 未完成能力：当前没有一个只输入原始 candidate SQL 字符串、输出 shadow-only allowed/rejected/reason/repair info 的独立 gate；现有 checker 不负责 raw candidate SQL 的最小 fail-closed 骨架，也不强制 raw candidate 必须带 LIMIT。
- 本次任务一致性：M10-A 只新增 shadow-only candidate SQL gate，不接入正式物流 QA 主链路，不执行 SQL。

## 允许修改范围

- backend/app/domains/logistics/services/nl2sql/candidate_sql_gate.py
- backend/app/domains/logistics/services/nl2sql/__init__.py（仅导出需要时）
- tests/unit/logistics/nl2sql/test_candidate_sql_gate.py
- ai/outbox/kanban/t_cb787cf5/**

## 禁止修改范围

- 不改前端、BOM、功率预测、物管、经营分析、正式物流 QA 主链路、.env、requirements。
- 不 stage/commit/push/deploy。
- 不 reset/stash/clean。
- 不安装新依赖；sqlglot 不作为必需依赖。

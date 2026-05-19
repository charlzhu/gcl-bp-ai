# M9 scoped submission checklist

任务：t_bc1100bb
分支：feature/nl2sql-m9-sqlplan-shadow-mvp

## 本次 M9 scoped 文件

代码/测试：
- backend/app/domains/logistics/services/nl2sql/m9_sqlplan_generation.py
- tests/unit/logistics/nl2sql/test_m9_sqlplan_generation.py

验收产物：
- ai/outbox/kanban/t_bc1100bb/final-acceptance.md
- ai/outbox/kanban/t_bc1100bb/test.log
- ai/outbox/kanban/t_bc1100bb/static-scan.json
- ai/outbox/kanban/t_bc1100bb/review-result-final.json
- ai/outbox/kanban/t_bc1100bb/live-provider-shadow-gate.rc
- ai/outbox/kanban/t_bc1100bb/live-provider-shadow-gate.log
- ai/outbox/kanban/t_bc1100bb/m9-shadow-sqlplan-generation-report.md
- ai/outbox/kanban/t_bc1100bb/m9-shadow-sqlplan-generation-records.jsonl
- ai/outbox/kanban/t_bc1100bb/diff.patch

## 若人工后续提交，只允许 scoped add

禁止：git add -A 或 git add .

建议命令：

git add \
  backend/app/domains/logistics/services/nl2sql/m9_sqlplan_generation.py \
  tests/unit/logistics/nl2sql/test_m9_sqlplan_generation.py \
  ai/outbox/kanban/t_bc1100bb/final-acceptance.md \
  ai/outbox/kanban/t_bc1100bb/test.log \
  ai/outbox/kanban/t_bc1100bb/static-scan.json \
  ai/outbox/kanban/t_bc1100bb/review-result-final.json \
  ai/outbox/kanban/t_bc1100bb/live-provider-shadow-gate.rc \
  ai/outbox/kanban/t_bc1100bb/live-provider-shadow-gate.log \
  ai/outbox/kanban/t_bc1100bb/m9-shadow-sqlplan-generation-report.md \
  ai/outbox/kanban/t_bc1100bb/m9-shadow-sqlplan-generation-records.jsonl \
  ai/outbox/kanban/t_bc1100bb/diff.patch

## Dirty worktree 提醒

当前仓库仍有非本任务未跟踪/已修改文件，例如 business_analysis 域、物管/经营分析前端入口、旧 outbox 产物以及 ai/outbox/kanban/t_7895e090/m8-shadow-eval-records.jsonl 的修改。不要把这些文件混入本次 M9 收口提交。

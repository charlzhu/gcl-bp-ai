# gcl-bp-ai M9 live provider shadow gate 收口验收

任务：t_bc1100bb
生成时间：2026-05-19 09:34:44 CST
分支：feature/nl2sql-m9-sqlplan-shadow-mvp
范围：仅 M9 NL2SQL SQLPlan Shadow MVP live provider shadow gate；未进入 M10，未扩大到 BOM/功率预测/物管/SAP MID/经营分析等非 M9 范围。

## 1. 根因

live provider 对默认年份问题输出的 filters.years 语义正确，为 2023、2024、2025、2026；但 plan.explicit_year_buckets 偶发重复输出 2025，形成 [2023, 2024, 2025, 2025, 2026]。

原 validator 对 explicit_year_buckets 与 filters.years 进行严格 list 比较，重复年份导致 fail-closed：

sqlplan_explicit_year_buckets_mismatch::2023,2024,2025,2026::2023,2024,2025,2025,2026

这不是年份范围理解错误，而是 provider 输出了重复 bucket。

## 2. 修复

在 M9 provider candidate 进入正式 SQLPlan validator 前增加安全归一化：

- 只读取 plan.filters 中 biz_year 的受控年份集合。
- 只在 explicit_year_buckets 所有值都可解析为合法年份时继续。
- 只在 explicit_year_buckets 去重后的集合与 biz_year filter 年份集合完全一致时，替换为排序后的去重列表。
- 多给年份、少给年份、非法年份、无法解析年份、年份过滤不合法时均不归一，继续交给 validator fail-closed。
- 未放宽 validator，未把 live gate 失败降级为 warning。

## 3. 本次改动文件

- backend/app/domains/logistics/services/nl2sql/m9_sqlplan_generation.py
- tests/unit/logistics/nl2sql/test_m9_sqlplan_generation.py
- ai/outbox/kanban/t_bc1100bb/* 验收产物

## 4. 验证结果

- RED 复现：修复前新增测试能复现 explicit_year_buckets 重复年份失败。
- focused GREEN/provider alias/timeout focused tests：5 passed。
- NL2SQL focused broader tests：185 passed, 9 warnings。
- compile：py_compile 通过。
- static scan：finding_count=0。
- live provider shadow gate：rc=0；total=1，success_count=1，generated_count=1，validation_pass_count=1，expected_status_mismatch_count=0。
- independent review：passed=true；security_concerns=[]；logic_errors=[]。

## 5. 验收产物

- ai/outbox/kanban/t_bc1100bb/test.log
- ai/outbox/kanban/t_bc1100bb/static-scan.json
- ai/outbox/kanban/t_bc1100bb/review-result-final.json
- ai/outbox/kanban/t_bc1100bb/live-provider-shadow-gate.rc
- ai/outbox/kanban/t_bc1100bb/live-provider-shadow-gate.log
- ai/outbox/kanban/t_bc1100bb/m9-shadow-sqlplan-generation-report.md
- ai/outbox/kanban/t_bc1100bb/m9-shadow-sqlplan-generation-records.jsonl
- ai/outbox/kanban/t_bc1100bb/submission-checklist.md
- ai/outbox/kanban/t_bc1100bb/diff.patch

## 6. Dirty worktree 边界

当前 worktree 仍包含本任务外未跟踪/已修改文件，尤其 business_analysis 域、物管/经营分析前端入口、旧 outbox 产物以及 ai/outbox/kanban/t_7895e090/m8-shadow-eval-records.jsonl 的修改。本次验收只声明 M9 scoped 范围，不使用 git add -A / git add .，后续人工提交应按 submission-checklist.md 精确 add。

## 7. 结论

M9 live provider shadow gate 的 explicit_year_buckets 重复年份阻塞已按 TDD 最小修复闭环，live gate 已恢复通过，验证、静态扫描和独立 review 均通过。满足本任务收口条件。

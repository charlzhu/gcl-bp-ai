# M10-D0 final acceptance — t_6c47d1b4

## 任务

M10-D0：物流 NL2SQL EXPLAIN / readonly trial gate 设计审计。

## 结论

M10-D0 已完成设计审计。本轮只产出审计与规划材料，没有写生产代码，没有执行 EXPLAIN，没有执行真实数据库查询，没有执行 readonly trial，没有 push，没有 merge，没有处理 `hermes-b7037318`。

## 实际执行位置

```text
/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/nl2sql-m10d0-design-audit
```

## 实际执行分支

```text
feature/nl2sql-m10d0-design-audit
```

## 基线

```text
HEAD = origin/agent/bp-main = 3011cdb398879ff893fdf53477e3113e88842baa
```

## 当前 Git 状态

生成本任务材料后，dirty 仅限本任务 outbox：

```text
## feature/nl2sql-m10d0-design-audit...origin/agent/bp-main
?? ai/outbox/kanban/t_6c47d1b4/
```

## 已完成验收项

1. 启动前 Git 状态确认通过。
2. 已确认新 worktree 基于 `origin/agent/bp-main@3011cdb398879ff893fdf53477e3113e88842baa`。
3. 已确认 M10-A/B/C 在当前基线上。
4. 已完成 EXPLAIN gate 设计。
5. 已完成 readonly trial gate 设计。
6. 已完成默认关闭策略设计。
7. 已完成真实数据库访问边界设计。
8. 已完成只读中间库边界设计。
9. 已明确禁止 SAP Oracle MID。
10. 已完成 SQL 安全边界设计。
11. 已完成脱敏 response/report schema 设计。
12. 已完成后续 M10-D1/D2/D3/D4 拆分建议。
13. 已完成风险审计。
14. 已给出推荐下一张看板任务标题和正文草案。

## 输出材料

1. `ai/outbox/kanban/t_6c47d1b4/preflight.md`
2. `ai/outbox/kanban/t_6c47d1b4/m10d0-design-audit.md`
3. `ai/outbox/kanban/t_6c47d1b4/implementation-plan.md`
4. `ai/outbox/kanban/t_6c47d1b4/risk-review.md`
5. `ai/outbox/kanban/t_6c47d1b4/final-acceptance.md`
6. `ai/outbox/kanban/t_6c47d1b4/gate-summary.json`

## M10-D0 设计结论

1. M10-D 可以继续推进，但必须拆小。
2. 不建议直接进入真实 EXPLAIN / readonly trial。
3. 推荐下一张卡先做 M10-D1：fake executor 下的 EXPLAIN / trial gate schema 与脱敏报告。
4. D1 完成后再考虑 D2 真实只读中间库 EXPLAIN smoke。
5. readonly trial 应延后到 D3，并以前置 EXPLAIN 成功、row cap、timeout、只读保护、泄露检查为条件。

## EXPLAIN gate 摘要

EXPLAIN gate 应作为 shadow/dry-run 内部审计步骤，仅对通过以下前置阶段的 SQL 执行：

```text
candidate_sql_gate -> SQLPlan validator -> deterministic renderer -> SQL safety
```

EXPLAIN 默认关闭，真实 DB 访问默认关闭，未配置时返回 disabled/skipped，不影响正式 QA。

EXPLAIN gate 只允许记录：

1. enabled。
2. status。
3. stage。
4. explain_status。
5. error_codes。
6. timeout_ms。
7. elapsed_ms。
8. sql_hash。
9. candidate_gate_reason_code。
10. safety_reason_code。

禁止记录 SQL 原文、params value、表名、字段名、provider debug、DB host/user/password/DSN 和 exception 原文。

## readonly trial gate 摘要

readonly trial gate 只能在 EXPLAIN gate 成功后进入，并且仅用于 shadow/dry-run。

必须满足：

1. readonly trial 显式开启。
2. 真实 DB 访问总开关显式开启。
3. 使用智能助手中间库 / 只读 MySQL。
4. 禁止 SAP Oracle MID。
5. 强制 SELECT-only。
6. 强制 LIMIT。
7. 强制 row cap。
8. 强制 timeout。
9. 强制 read-only guard。
10. 不返回 trial row value。
11. 不改变正式物流 QA 主返回。

## 后续拆分建议

1. M10-D1：fake executor 下的 EXPLAIN / trial result schema 与报告字段。
2. M10-D2：只读中间库 EXPLAIN smoke，显式开关，默认关闭。
3. M10-D3：readonly trial row cap / timeout / leak check。
4. M10-D4：M10-D 综合 shadow gate report。

## 推荐下一张任务

```text
M10-D1：物流 NL2SQL fake executor EXPLAIN / trial gate schema 与脱敏报告
```

推荐先进入 D1，不建议直接进入 D2/D3。

## 禁止事项确认

本轮已遵守：

1. 未写生产代码。
2. 未执行 EXPLAIN。
3. 未执行真实数据库查询。
4. 未执行 readonly trial。
5. 未连接 SAP Oracle MID。
6. 未 push。
7. 未 merge main。
8. 未进入 M10-D1/D2/D3/D4 开发。
9. 未进入 M10-E。
10. 未做 SQL Repair。
11. 未清理 backup。
12. 未清理其他 worktree。
13. 未处理 `hermes-b7037318` 的 dirty 文件。

# NL2SQL Logistics M7 Readonly Middle DB Shadow Smoke MVP Plan

## 目标

M7 在 M4 SQL renderer/safety、M5 shadow pipeline、M6 离线 shadow smoke/report 的基础上，增加一个“只读真实 MySQL 中间库 shadow smoke”最小闭环：

1. 使用受控 SQLPlan candidate。
2. 经过 M3 validator 与 M4 renderer。
3. 再经过 M4 safety validator。
4. 使用只读中间库 executor 执行 `EXPLAIN SELECT ...`。
5. 使用同一安全 SQL 执行带严格上限的 `SELECT ... LIMIT N` trial。
6. 生成本地 JSONL 与 Markdown 评估报告。

本阶段只用于内部 smoke/evaluation，不接正式物流 QA 主链路，不修改前端，不新增迁移。

## 只读边界

- 配置只从 `backend/.env` 读取 `MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_DB`、`MYSQL_USER`、`MYSQL_PASSWORD`、可选 `MYSQL_CHARSET`。
- 缺少 `.env` 或配置不完整时 fail-closed，记录 `blocked/environment`，不伪造成 smoke 成功。
- 只允许 executor 接收：
  - `EXPLAIN SELECT ...`
  - `SELECT ... LIMIT N`
- 非 SELECT、嵌套 EXPLAIN、无 LIMIT trial、超过 M7 上限的 LIMIT 都会在 driver 前被拒绝。
- SQL 参数保持 driver 绑定：renderer 的 `:p0` 会转换成 PyMySQL `%(p0)s`，不会拼接用户值。
- artifact 不保存 SQL 原文、参数值、host/user/password/database/full DSN/API key/token。

## 新增入口

固定脚本：

```bash
backend/.venv/bin/python scripts/dev/run_logistics_nl2sql_m7_readonly_smoke.py --artifact-dir ai/outbox/kanban/t_1fceb427
```

脚本只输出脱敏摘要，完整记录写入：

- `ai/outbox/kanban/t_1fceb427/m7-shadow-smoke-records.jsonl`
- `ai/outbox/kanban/t_1fceb427/m7-shadow-smoke-report.md`

如真实 MySQL 环境不可用，脚本返回非 0，并在上述 artifact 中记录环境阻塞原因；这不是测试伪失败，而是 M7 live smoke 的真实环境状态。

## 测试覆盖

新增单元测试覆盖：

1. `.env` 缺失 fail-closed。
2. DB 配置缺失 fail-closed，且不泄漏已存在配置值。
3. 有效配置只在内存 config 中保留，JSON 摘要脱敏。
4. 只读 executor 执行 `EXPLAIN SELECT` 与 bounded trial，并保持参数绑定。
5. executor 直接调用时拒绝非 SELECT 和无界 SELECT。
6. safety 拒绝时不调用 executor。
7. runner 在缺少环境时生成 `blocked/environment_unavailable` artifact。
8. runner 在 stub success/explain_failed/trial_failed 路径生成脱敏 artifact。

## M8 建议

M8 可在 M7 artifact 基础上做更细的真实库 schema/EXPLAIN 质量分析，例如：

- 记录脱敏后的 plan hash 与 catalog coverage 趋势。
- 对常见样例扩大 smoke 集合，但仍保持 LIMIT 上限。
- 做 shadow-only SQLPlan 修复建议，不接正式问答执行链路。

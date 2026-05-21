# M10-D0 设计审计 — 物流 NL2SQL EXPLAIN / readonly trial gate

## 1. 当前仓库已完成能力判断

### M10-A 已完成

1. 已新增 candidate SQL 文本级安全门禁。
2. 门禁对空 SQL、缺 LIMIT、多语句、注释、非 SELECT、DDL/DML/事务、UNION、文件函数、延迟函数、锁函数、FOR UPDATE、未知结构和超大 LIMIT 等 fail-closed。
3. 门禁只返回结构化状态、稳定 reason code、脱敏 reason 和可选 repair info。
4. M10-A 不执行 SQL，不连接数据库，不接正式 QA。

### M10-B 已完成

1. `shadow_pipeline` 已接入 `candidate_sql_gate`。
2. raw candidate SQL 在 SQLPlan validation 前先进入 gate。
3. gate 拒绝时停在 `candidate_sql_gate` 阶段，不进入 validator、renderer、safety、executor。
4. gate 允许时仍只执行 SQLPlan 渲染结果，不执行 raw candidate SQL。
5. shadow record/report 已记录 gate 摘要。
6. M10-B 仍是 shadow-only。

### M10-C 已完成

1. `live_shadow_adapter` 已以默认关闭方式接入正式物流 QA 旁路。
2. 默认关闭时不构造 recall、generator、pipeline 等外部依赖。
3. 显式开启后仅旁路执行 rewrite、domain route、catalog recall、SQLPlan generator、M10-B shadow pipeline。
4. 正式 `LogisticsDataQaResult` 主返回不变。
5. 仅在查询历史 `response_meta.nl2sql_live_shadow` 写入脱敏摘要。
6. adapter/provider/pipeline 异常 fail-closed，不中断正式 QA。
7. M10-C 不执行真实 SQL，不接前端，不做 live takeover。

## 2. 当前未完成能力判断

1. 尚未定义真实 EXPLAIN gate 的独立开关、执行器边界、超时和结果 schema。
2. 尚未定义 readonly trial gate 的 row cap、timeout、只读事务/只读连接约束和泄露检查。
3. 尚未接入真实只读中间库 smoke。
4. 尚未建立 D 级综合 shadow gate report。
5. 尚未形成从 fake executor 到真实只读库的分阶段验收路线。
6. 尚未进入正式 QA 答案接管，也不应在 M10-D 进入。

## 3. 本次任务是否与当前仓库状态一致

一致。当前 `origin/agent/bp-main@3011cdb398879ff893fdf53477e3113e88842baa` 已包含 M10-A/B/C。本任务在新的干净专用 worktree 上做 M10-D0 设计审计，未复用存在 dirty 的 `hermes-b7037318`。

## 4. 本轮允许修改范围

仅允许新增本任务审计材料：

```text
ai/outbox/kanban/t_6c47d1b4/**
```

## 5. 本轮禁止修改范围

1. 不修改 `backend/**` 生产代码。
2. 不修改 `frontend/**`。
3. 不修改测试代码。
4. 不修改配置、`.env`、迁移或数据脚本。
5. 不处理 backup / 其他 worktree / `hermes-b7037318`。

## 6. M10-D 推荐 Gate 顺序

后续 M10-D 必须保持以下顺序：

```text
用户问题
→ rewrite / domain route / catalog recall / SQLPlan generator
→ candidate_sql_gate
→ SQLPlan validator
→ deterministic renderer
→ SQL safety
→ EXPLAIN gate
→ readonly trial gate
→ shadow report
```

任何一步失败都必须 fail-closed，并且不得影响正式物流 QA 主返回。

## 7. EXPLAIN gate 推荐设计

### 7.1 定位

EXPLAIN gate 是 shadow/dry-run 内部审计步骤，只验证经 SQLPlan validator、deterministic renderer 和 SQL safety 通过后的 SQL 是否可被只读中间库解释执行。它不是生产执行许可，不产出用户答案。

### 7.2 输入

允许输入：

1. 已通过 SQLPlan validator 的 validation result。
2. 已由 deterministic renderer 生成的 rendered SQL 对象。
3. 已通过 SQL safety 的 safety result。
4. request_id / trace_id。
5. SQL hash。
6. 参数 key 列表或参数数量。
7. 配置快照中的非敏感项，如 timeout、row cap、enabled 状态。

禁止输入进入持久化材料：

1. SQL 原文。
2. params value。
3. DB host / user / password / DSN。
4. provider debug。
5. exception 原文。

### 7.3 前置条件

1. `candidate_sql_gate` 已执行并允许。
2. SQLPlan validator 已通过。
3. renderer 已确定性生成 SQL。
4. SQL safety 已通过。
5. domain 仅允许 logistics。
6. source system 仅允许智能助手中间库 / middle_db。
7. EXPLAIN 开关显式开启。
8. 真实 DB 访问总开关显式开启。
9. 使用只读 MySQL profile。
10. 不能连接 SAP Oracle MID。

### 7.4 输出状态

建议 `explain_status`：

1. `disabled`：默认关闭或未配置。
2. `skipped`：前置阶段失败或 source/domain 不允许。
3. `success`：EXPLAIN 成功返回脱敏摘要。
4. `failed`：EXPLAIN 异常、超时、连接不允许、泄露检查失败或安全约束失败。

建议 `status` 总体收敛为：

1. `disabled`
2. `skipped`
3. `success`
4. `failed`

### 7.5 错误码

建议错误码只用稳定枚举，不拼接 SQL、表名、字段名、连接串或异常原文：

1. `m10d_explain_disabled`
2. `m10d_real_db_access_disabled`
3. `m10d_source_not_allowed`
4. `m10d_domain_not_allowed`
5. `m10d_candidate_gate_failed`
6. `m10d_sqlplan_validation_failed`
7. `m10d_sql_safety_failed`
8. `m10d_explain_timeout`
9. `m10d_explain_executor_failed`
10. `m10d_explain_readonly_guard_failed`
11. `m10d_explain_leak_guard_failed`

### 7.6 脱敏规则

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

不记录 EXPLAIN 原始返回明细；如果后续确需记录 query plan 摘要，只能记录归一化后的非敏感布尔/数量字段，例如 `plan_row_count`、`has_full_scan`，且不能包含表名、字段名、索引名或条件值。

## 8. readonly trial gate 推荐设计

### 8.1 定位

readonly trial gate 是 shadow/dry-run 内部最小试跑，用于验证安全 SQL 在只读中间库上的最小可执行性和行数边界。它不产生业务答案，不返回 trial row value，不改变正式物流 QA 主链路。

### 8.2 输入

允许输入：

1. EXPLAIN gate 成功摘要。
2. 已通过 safety 的 rendered SQL 对象。
3. SQL hash。
4. 参数 key 列表或参数数量。
5. row cap / timeout 配置。
6. trace_id。

禁止持久化：

1. SQL 原文。
2. params value。
3. trial row value。
4. DB host/user/password/DSN。
5. exception 原文。

### 8.3 前置条件

1. readonly trial 显式开启。
2. 真实 DB 访问总开关显式开启。
3. EXPLAIN gate 成功。
4. SQL safety 成功。
5. 只允许 SELECT。
6. 不允许无 LIMIT 查询进入 trial；若 aggregate 需要 LIMIT 0/小样本，必须由确定性逻辑追加受控 limit 参数。
7. 强制 row cap。
8. 强制 timeout。
9. 强制只读连接 / 只读事务 / autocommit 约束。
10. 强制 table whitelist 和 field whitelist。
11. 禁止 SAP Oracle MID。

### 8.4 输出状态

建议 `trial_status`：

1. `disabled`：默认关闭或未配置。
2. `skipped`：EXPLAIN 未成功或前置阶段失败。
3. `success`：trial 在 row cap 和 timeout 内完成。
4. `failed`：trial 异常、超时、row cap 违规、只读保护失败或泄露检查失败。

### 8.5 错误码

建议错误码：

1. `m10d_trial_disabled`
2. `m10d_trial_skipped_explain_not_success`
3. `m10d_trial_timeout`
4. `m10d_trial_executor_failed`
5. `m10d_trial_row_cap_exceeded`
6. `m10d_trial_limit_required`
7. `m10d_trial_readonly_guard_failed`
8. `m10d_trial_leak_guard_failed`

### 8.6 脱敏输出

readonly trial gate 只允许记录：

1. row_count。
2. row_cap_applied。
3. timeout_ms。
4. elapsed_ms。
5. sql_hash。
6. trial_status。
7. error_codes。

不允许记录任何行值、字段值、参数值或异常原文。

## 9. 默认关闭策略

必须新增或复用独立配置项，且默认关闭：

1. EXPLAIN 默认关闭。
2. readonly trial 默认关闭。
3. 真实数据库访问默认关闭。
4. 单测默认不依赖真实数据库。
5. 未配置只读 profile 时返回 disabled/skipped。
6. disabled/skipped 不得影响正式 QA。

建议配置项命名：

```text
LOGISTICS_NL2SQL_EXPLAIN_GATE_ENABLED=false
LOGISTICS_NL2SQL_READONLY_TRIAL_GATE_ENABLED=false
LOGISTICS_NL2SQL_REAL_DB_ACCESS_ENABLED=false
LOGISTICS_NL2SQL_EXPLAIN_TIMEOUT_MS=1000
LOGISTICS_NL2SQL_TRIAL_TIMEOUT_MS=1000
LOGISTICS_NL2SQL_TRIAL_ROW_CAP=20
```

配置项不得承载真实 DSN、host、user、password；真实连接信息仍必须由既有安全配置体系提供，并且不能写入日志、报告或 response_meta。

## 10. 数据源边界

1. 只允许智能助手中间库 / 只读 MySQL。
2. 禁止 SAP Oracle MID。
3. 禁止生产写库。
4. 禁止实时直查第三方业务源。
5. 禁止将 DB host/user/password/DSN 写入 response_meta、evaluation log、report、outbox 验收材料。
6. 禁止把 `.env` 内容写入任何验收材料。
7. 连接 profile 仅允许记录非敏感枚举，例如 `middle_db_readonly`，不能记录连接串。

## 11. SQL 安全边界

1. 不绕过 candidate_sql_gate。
2. 不绕过 SQLPlan validator。
3. 不绕过 deterministic renderer。
4. 不绕过 SQL safety。
5. 不执行非 SELECT。
6. 不执行无 LIMIT 查询。
7. 强制 table whitelist。
8. 强制 field whitelist。
9. 强制 timeout。
10. 强制 row cap。
11. 强制 read-only execution guard。
12. EXPLAIN / trial 失败必须 fail-closed。
13. 失败不得降级成成功。
14. 不做自动 SQL Repair。

## 12. 推荐脱敏 schema

建议 response/report 只允许以下 schema：

```json
{
  "schema_version": "logistics_nl2sql_m10d_shadow_gate.v1",
  "enabled": true,
  "status": "success|failed|skipped|disabled",
  "stage": "candidate_sql_gate|validation|render|safety|explain|trial|report",
  "error_codes": [],
  "explain_status": "success|failed|skipped|disabled",
  "trial_status": "success|failed|skipped|disabled",
  "row_count": 0,
  "row_cap_applied": false,
  "timeout_ms": 1000,
  "elapsed_ms": 0,
  "sql_hash": "sha256_hex_or_null",
  "candidate_gate_reason_code": null,
  "safety_reason_code": null,
  "shadow_only": true
}
```

禁止字段：

1. SQL 原文。
2. params value。
3. 表名。
4. 字段名。
5. SQLPlan 原文。
6. provider debug。
7. DB host/user/password/DSN。
8. exception 原文。
9. trial row value。

## 13. 后续测试计划

D1/D2/D3 必须覆盖 RED/GREEN：

1. 默认关闭不实例化 DB executor。
2. fake executor explain success。
3. fake executor explain failure fail-closed。
4. fake executor trial row cap。
5. fake executor timeout。
6. SQL 原文泄露负例。
7. params value 泄露负例。
8. DB URL / host / DSN 泄露负例。
9. 非 SELECT fail-closed。
10. 无 LIMIT fail-closed。
11. 超 LIMIT fail-closed。
12. EXPLAIN / trial 异常不影响正式 QA。
13. M8 artifact 如被测试写脏必须精确恢复。

## 14. 设计结论

M10-D 可以启动，但必须先从 fake executor 的 schema/report 切片开始，不应直接做真实 DB trial。推荐下一张卡为 M10-D1：fake executor 下的 EXPLAIN / trial result schema 与报告字段。

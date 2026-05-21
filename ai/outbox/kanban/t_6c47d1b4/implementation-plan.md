# M10-D0 implementation plan — 后续 M10-D 拆分

## 总体原则

M10-D 不做生产接管，只做 shadow / dry-run 的 EXPLAIN 与 readonly trial gate。正式物流 QA 主返回保持不变，NL2SQL 结果不得作为用户答案来源。

## 推荐拆分

### M10-D1：fake executor 下的 EXPLAIN / trial result schema 与报告字段

目标：

1. 不连接真实数据库。
2. 不执行真实 EXPLAIN。
3. 不执行真实 readonly trial。
4. 在 fake executor 下定义 EXPLAIN / trial gate 结果模型。
5. 明确 report/response_meta 可记录字段白名单。
6. 补齐泄露负例测试。
7. 保持正式 QA 主返回不变。

允许修改：

1. `backend/app/domains/logistics/services/nl2sql/**` 中的 shadow-only gate/report 模型。
2. `tests/unit/logistics/nl2sql/**` focused tests。
3. 本任务 outbox。

禁止：

1. 不接真实 DB。
2. 不接前端。
3. 不开启真实执行。
4. 不做 SQL Repair。

验收：

1. 默认关闭不实例化 DB executor。
2. fake explain success/failure。
3. fake trial success/failure。
4. SQL/params/DB URL 泄露负例通过。
5. focused tests + compile + static scan + review 通过。

### M10-D2：只读中间库 EXPLAIN smoke，显式开关，默认关闭

目标：

1. 增加真实只读中间库 EXPLAIN smoke 能力。
2. 默认关闭真实数据库访问。
3. 必须显式开启真实 DB 总开关和 EXPLAIN gate 开关。
4. 只能连接智能助手中间库 / 只读 MySQL。
5. 禁止 SAP Oracle MID。
6. 失败 fail-closed，不影响正式 QA。

验收：

1. 未开启时 skipped/disabled。
2. 未配置只读 profile 时 skipped/disabled。
3. 开启后只跑小样本 smoke。
4. 不记录 host/user/password/DSN。
5. 不记录 SQL 原文和 params value。

### M10-D3：readonly trial row cap / timeout / leak check

目标：

1. 在 EXPLAIN 成功后才允许 readonly trial。
2. 强制 LIMIT、row cap、timeout。
3. 强制只读连接/只读事务保护。
4. 不返回 trial row value。
5. 不作为正式用户答案来源。

验收：

1. row cap 正常收敛。
2. timeout fail-closed。
3. 非 SELECT、无 LIMIT、超 LIMIT 拒绝。
4. trial 异常不影响正式 QA。
5. 泄露负例全部通过。

### M10-D4：M10-D 综合 shadow gate report

目标：

1. 汇总 candidate gate、SQLPlan validator、renderer、safety、EXPLAIN、trial 的状态。
2. 输出脱敏 report。
3. 支持按错误码统计阶段失败原因。
4. 不接前端、不接正式答案、不进入 M10-E。

验收：

1. report 只包含脱敏字段。
2. 不包含 SQL 原文、params value、表字段名、DB 连接信息。
3. 综合 focused tests 通过。

## 推荐下一张卡

优先进入 M10-D1，而不是 D2/D3。

原因：

1. D1 不触碰真实数据库，风险最低。
2. D1 先稳定 schema/report/泄露检查，避免 D2 真实 EXPLAIN 后返工。
3. D1 可继续复用 fake executor，保障 TDD 速度和确定性。
4. D1 产物是 D2/D3 的安全前置。

## M10-D1 推荐任务标题

```text
M10-D1：物流 NL2SQL fake executor EXPLAIN / trial gate schema 与脱敏报告
```

## M10-D1 推荐任务正文草案

```markdown
# M10-D1：物流 NL2SQL fake executor EXPLAIN / trial gate schema 与脱敏报告

## 任务目标

在不连接真实数据库、不执行真实 EXPLAIN、不执行真实 readonly trial 的前提下，基于 M10-D0 设计审计，为物流 NL2SQL shadow pipeline 增加 EXPLAIN / readonly trial gate 的结果 schema、状态枚举、错误码和脱敏 report 字段。

## 允许范围

1. 修改 `backend/app/domains/logistics/services/nl2sql/**` 中 shadow-only gate/report 模型。
2. 修改 `tests/unit/logistics/nl2sql/**` focused tests。
3. 写入本任务 outbox 材料。

## 禁止范围

1. 不连接真实数据库。
2. 不执行真实 EXPLAIN。
3. 不执行真实 readonly trial。
4. 不修改正式物流 QA 主返回。
5. 不把 NL2SQL 结果作为用户答案来源。
6. 不接前端。
7. 不连接 SAP Oracle MID。
8. 不做 SQL Repair。

## 必须覆盖

1. 默认关闭不实例化 DB executor。
2. fake executor explain success。
3. fake executor explain failure fail-closed。
4. fake executor trial success。
5. fake executor trial failure fail-closed。
6. fake executor trial row cap。
7. fake executor timeout-like failure。
8. SQL 原文泄露负例。
9. params value 泄露负例。
10. DB URL/host/DSN 泄露负例。
11. 非 SELECT / 无 LIMIT / 超 LIMIT fail-closed。
12. EXPLAIN / trial 异常不影响正式 QA。

## 验收标准

1. focused tests 通过。
2. compileall 通过。
3. diff check 通过。
4. static scan 通过。
5. 独立 review 通过。
6. 未执行真实数据库查询。
7. 未执行真实 EXPLAIN。
8. 未 push、未 merge、未 deploy。
```

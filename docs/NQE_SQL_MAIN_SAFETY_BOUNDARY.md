# NQE 统一 SQL Agent 安全边界

> 本文档属于 NQE-SQL-MAIN 独立事实源。本轮只做设计，不在当前仓库中实现 SQL 执行逻辑。

## 1. 安全目标

统一 SQL Agent 的安全目标不是“让 LLM 会写 SQL”，而是让 LLM 生成的 SQL 在执行前被确定性代码严格约束、校验、审计和回滚。

最低目标：

1. 只允许只读查询。
2. 只允许访问白名单业务表。
3. 每条 SQL 执行前必须通过安全预检和 EXPLAIN / validate。
4. SQL 错误只能进入受控 correct 流程，不能直接暴露给用户。
5. 所有 SQL、修正、执行、错误、结果摘要必须记录 trace。
6. 用户可见回答不得暴露 SQL、表名、字段名、内部 trace、raw/debug 等技术内容。

## 2. SQL 类型边界

允许：

```text
SELECT ...
WITH ... SELECT ...
```

禁止：

```text
INSERT / UPDATE / DELETE / DROP / ALTER / TRUNCATE / CREATE / REPLACE / MERGE
CALL / EXEC / GRANT / REVOKE / LOAD / LOCK / UNLOCK
```

同时禁止：

1. 多语句 SQL。
2. 注释中夹带第二语句。
3. 访问系统库或系统表。
4. 使用可导致写入、文件访问、网络访问、权限变更的函数。
5. 使用非白名单 schema/table。
6. 无限制大明细扫描。

## 3. 表与 schema 白名单

NQE 必须建立白名单模型：

```text
nqe_domain
nqe_table_info
nqe_column_info
nqe_metric_info
nqe_join_info
```

SQL 执行前必须解析出：

1. 访问的 schema。
2. 访问的表。
3. 访问的字段。
4. join 表。
5. 聚合字段和排序字段。

校验规则：

1. 表必须属于当前业务域允许范围。
2. 字段必须存在于 nqe_column_info 或兼容 catalog。
3. 禁止访问 `information_schema`、`mysql`、`performance_schema`、`sys`。
4. 禁止访问用户、权限、密钥、系统配置、任务调度、敏感日志等表。
5. 禁止跨业务域任意 join；跨域 join 必须有明确 join_info 和阶段授权。

## 4. LIMIT、超时与结果规模

建议默认：

| 场景 | 默认限制 |
|---|---|
| 明细查询 | LIMIT 200 |
| 明细最大返回 | LIMIT 1000 |
| 聚合分组 | 最大 500 组 |
| SQL 执行超时 | 5～15 秒，按环境配置 |
| 单次结果体积 | 后端限制序列化大小 |

规则：

1. 明细查询未带 LIMIT 时自动补 LIMIT。
2. 用户要求导出大数据时不走问答链路，应进入受控导出任务审批。
3. 聚合查询如 group by 结果过大，应返回业务化提示或要求补充筛选条件。
4. SQL 执行超时必须记录 trace，并触发 fallback 或用户提示。

## 5. EXPLAIN / validate / correct 闭环

流程：

```text
generate_sql
→ precheck_sql_safety
→ explain_validate_sql
→ 如果失败：correct_sql
→ precheck_sql_safety
→ explain_validate_sql
→ 最多修正 2 次
→ execute_sql_readonly 或返回业务化失败
```

要求：

1. correct_sql 只能基于脱敏后的数据库错误和原始上下文修正。
2. 修正后的 SQL 必须重新走完整预检和 EXPLAIN。
3. 超过最大修正次数后不能继续执行。
4. 失败信息对用户表达为业务化结果，不暴露原始 SQL 和数据库错误。

## 6. Trace 与审计

NQE 必须记录：

1. trace_id。
2. 用户问题。
3. 业务域识别结果。
4. 召回候选摘要。
5. SQL 生成 prompt 版本。
6. 生成 SQL。
7. 安全预检结果。
8. EXPLAIN 结果或错误摘要。
9. correct_sql 轮次与错误摘要。
10. 最终执行 SQL。
11. 执行耗时、返回行数、结果摘要。
12. fallback 是否触发。
13. 用户可见 answer 摘要。
14. 灰度模式：off / shadow / assist / on。

敏感信息处理：

1. 不记录真实密码、token、连接串。
2. 不记录完整用户隐私数据或超大结果集。
3. 对数据库错误做脱敏。
4. trace 对前端默认不可见，只能展示业务化进度。

## 7. 用户可见安全边界

用户可见回答禁止出现：

```text
SQL、表名、字段名、query_key、planner、guardrail、schema、raw/debug、LLM、prompt、trace 原始内容
```

允许展示：

1. 业务问题理解。
2. 业务筛选条件。
3. 汇总指标。
4. 结果表格中的业务字段中文名。
5. 数据日期、同步批次、查询范围等业务可解释信息。
6. 暂不支持、需要澄清、数据缺失等业务化提示。

## 8. 业务域特殊安全规则

### 8.1 物流

1. 均价按 `总费用 / 总车次` 口径，不使用明细费用 AVG。
2. 多年份显式请求时，无匹配年份也要返回空值行说明。
3. 用户未给时间时按已确认业务口径默认覆盖 2023～2026 所有时间。

### 8.2 产销存 / 经营分析

1. 只使用已发布月份，未来月份不当实际数据。
2. 销量/销售量按发货量口径。
3. 库存、存货、库存（SAP数据）等价。
4. 缺平均库存等关键数据时应业务化反问，不编造。

### 8.3 计划 BOM

1. BOM 消歧必须通用确定性，不硬编码样例。
2. compare/replay 初期保留旧服务 fallback。
3. 不把样例文档中的虚构单号/项目当真实验收数据。

### 8.4 功率预测

1. LLM 不直接计算功率档位、比例、供应商效率、匹配度。
2. 预测结果由 PowerPredictionEngine 等确定性引擎产生。
3. NQE 只负责入口、参数检索、结果追溯和表达。

## 9. 当前 blocked 条件

进入编码前必须补齐：

1. nqe_* 元数据表与白名单设计。
2. SQL parser / sqlglot 或等价解析方案。
3. EXPLAIN validate 接口与数据库只读 session 策略。
4. trace 表与脱敏策略。
5. 每域 off/shadow/assist/on 配置。
6. 每域回归测试集与 SQL 安全测试集。

## 10. 当前结论

当前不允许直接让 NQE 生成 SQL 并执行到正式用户链路。必须先完成 NQE-SQL-MAIN-1～5 设计，并在 NQE-SQL-MAIN-11～13 实现安全、validate、trace 后，才允许逐域 shadow/assist/on。
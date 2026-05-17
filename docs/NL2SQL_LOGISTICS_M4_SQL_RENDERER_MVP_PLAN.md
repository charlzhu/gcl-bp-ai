# 物流 NL2SQL M4：SQL Renderer + SQL 安全校验 + EXPLAIN/试执行闭环 MVP

## 1. 阶段目标

M4 在 M3 `SQLPlan` 确定性校验通过之后，补齐从受控 SQLPlan 到数据库执行前闭环的最小能力：

1. 将已校验的物流 SQLPlan 渲染为参数化 SQL。
2. 对 renderer 产物做第二道 SQL 安全校验。
3. 提供 EXPLAIN / 试执行服务边界。
4. 默认单测使用 fake executor，不连接真实数据库、不读取 `.env` 凭据。

本阶段仍不接正式物流 QA 主链路，不让 LLM 直接输出可执行 SQL。

## 2. 输入与输出

### 输入

- M3 `LogisticsSqlPlanValidationResult`。
- `ok=True` 且经过 catalog canonical 回查的 normalized plan。

### 输出

- `LogisticsRenderedSql`：
  - `sql`：只读、参数化 SQL 文本。
  - `params`：绑定参数字典。
  - `referenced_tables`：实际引用表。
  - `referenced_columns`：实际引用字段。
  - `referenced_joins`：实际引用 join。
  - `limit`：受控 LIMIT。
  - `explicit_year_buckets`：年份桶，用于后续结果补空和解释。
- `LogisticsSqlSafetyResult`：安全门禁结果。
- `LogisticsSqlExecutionResult`：EXPLAIN / trial 执行闭环结果。

## 3. Renderer 设计

Renderer 只消费 M3 validator 通过的结果，禁止直接消费原始 LLM candidate。

### 支持范围

- `aggregate`
- `ranking`
- `detail`

### SQL 形态约束

1. 只生成 `SELECT`。
2. 所有用户过滤值都使用 `:param` 参数绑定。
3. 不生成 `SELECT *`。
4. 不生成字符串字面量拼接。
5. 不生成反引号标识符。
6. 不生成自由 join 条件。
7. `LEFT JOIN` 必须保持 catalog 左表到右表方向，不能为连通性反向渲染。
8. 明细和排名查询必须有受控 LIMIT。
9. 物流均价严格使用 `SUM(total_fee) / SUM(shipment_trip_count)`，不能使用 `AVG(total_fee)`。

## 4. SQL Safety Checker 设计

Safety Checker 是 renderer 后的第二道门禁，不完全信任 renderer 元数据，也扫描 SQL 文本本身。

### 拒绝项

- 多语句。
- 注释：`--`、`#`、`/* */`。
- DDL / DML / 写文件相关 token。
- `UNION`。
- 嵌套 `EXPLAIN`。
- 危险函数，例如 `SLEEP`。
- `SELECT *`、`SELECT DISTINCT *`、`table.*`。
- 字符串字面量。
- 缺失绑定参数。
- 超过上限的 LIMIT。
- 非 renderer 形态的 LIMIT，例如 `LIMIT ALL`、`LIMIT 0, 999999`、`LIMIT :p0 OFFSET :p1`。
- 非 catalog allow-list 表字段。
- 裸字段、反引号标识符、系统变量和无 FROM 查询。
- 非 catalog 受控 join 或 LEFT JOIN 方向不一致。

## 5. EXPLAIN / 试执行闭环

`LogisticsSqlExecutionService` 负责在安全校验通过后调用 executor：

1. `explain()`：执行 `EXPLAIN <SQL>`。
2. `trial()`：执行受控小 LIMIT 试执行。
3. Safety 不通过时不调用 executor。
4. executor 异常必须脱敏后返回。

M4 默认只实现 fake executor 协议与单测闭环，真实数据库连接留给后续集成阶段。

## 6. 本阶段禁止范围

- 不接正式物流 QA 主链路。
- 不改前端。
- 不建数据库迁移。
- 不查询 SAP Oracle MID。
- 不让 LLM 直接输出可执行 SQL。
- 不提交 `.env`、真实 DSN、真实 token、API key。
- 不把新逻辑继续堆到 `data_qa_planner.py`。

## 7. 验收结果

已执行：

```text
focused M4 renderer/safety/execution: 41 passed
adjacent NL2SQL/planner regression: 79 passed, 9 warnings
logistics unit regression: 120 passed, 9 warnings
all unit regression: 164 passed, 9 warnings
py_compile: passed
git diff --check: passed
static scan: passed
```

9 个 warning 来自 pymilvus / pkg_resources / google._upb 第三方 deprecation warning，不影响 M4 逻辑。

## 8. 后续建议

下一阶段建议进入 M5：把 M1-M4 组件串成 shadow pipeline。M5 应仍不接正式用户可见回答，先完成离线样例/影子链路：

```text
Query Rewrite / Domain Router
→ Catalog Recall / Rerank
→ SQLPlan candidate
→ SQLPlan Validator
→ SQL Renderer
→ SQL Safety
→ EXPLAIN / Trial
→ 结构化 trace / evaluation log
```

# gcl-bp-ai: NL2SQL M4 SQL Renderer + SQL 安全校验 + EXPLAIN/试执行闭环 MVP - Final Acceptance

## 结论

任务 `t_96b0f436` 原始结束状态为 `blocked`，原因是 worker 达到迭代预算上限，非自然完成。接手复查后发现 M4 已有主体实现，但 reviewer 第二轮 blocker 修复未完成，不能直接视为完成。

当前已补完并通过复验，可判定 M4 完成。

## 原始阻塞原因

```text
Iteration budget exhausted (90/90) — task could not complete within the allowed iterations
```

worker 停止点：

1. 已生成 SQL Renderer / SQL Safety / SQL Execution 主体。
2. 已做第一轮测试和部分 reviewer 修复。
3. 第二轮 reviewer 指出安全 blocker 后，worker 已新增 RED 测试并开始修复。
4. 停止时 `_check_renderer_shape` 尚未完成，LEFT JOIN 方向和部分 safety bypass 仍未彻底收口。

## 已补救问题

### 1. SQL Safety 后置裸星号绕过

修复前风险：

```sql
SELECT dws_logistics_detail_union.biz_year, * FROM dws_logistics_detail_union
```

只检测 `SELECT *` 起始形态，后置裸 `*` 可能绕过。

当前修复：

- 扫描 SELECT list。
- 允许 `COUNT(*)` 但拒绝其他裸 `*`。
- 保留 `table.*` 拒绝。
- execution 层补充 safety fail 时不调用 executor 的回归。

### 2. 裸字段自别名绕过

修复前风险：

```sql
SELECT secret_internal AS secret_internal FROM dws_logistics_detail_union
SELECT SUM(secret_internal) AS secret_internal FROM dws_logistics_detail_union
```

别名被全局加入 allow-list，导致裸字段可借自别名绕过。

当前修复：

- `AS alias` 只在 alias 位置允许。
- ORDER BY 中允许引用 renderer 产生的 alias。
- SELECT/WHERE/GROUP/ON 中裸字段仍一律拒绝。

### 3. LEFT JOIN 链方向校验不足

修复前风险：

Safety 只校验 joined table 和 ON 文本，未确认 catalog left_table 已经在当前 FROM/JOIN 链中。

当前修复：

- Safety 解析 FROM base table 并维护 joined_tables。
- LEFT JOIN 必须满足：
  - catalog left_table 已在 joined_tables；
  - SQL joined table 必须是 catalog right_table；
  - ON 表达式必须与 catalog 精确一致。
- Renderer 侧也保持 LEFT JOIN 只能从 catalog left_table 到 right_table。

### 4. executor 异常脱敏覆盖加强

- 保留 password/token/DSN 脱敏。
- 补充 api_key、Bearer、sk-* 测试覆盖。

## 验证结果

已重新生成 `ai/outbox/kanban/t_96b0f436/test.log`。

```text
focused M4 renderer/safety/execution: 41 passed
adjacent NL2SQL/planner regression: 79 passed, 9 warnings
logistics unit regression: 120 passed, 9 warnings
all unit regression: 164 passed, 9 warnings
py_compile: passed
git diff --check: passed
static scan: passed
```

warning 说明：

- 9 个 warning 来自 pymilvus / pkg_resources / google._upb 第三方 deprecation warning。
- 与 M4 SQL renderer/safety/execution 逻辑无关。

## 独立 review

第一轮独立 review：未通过，发现 3 个 blocker：

1. `SELECT col, *` 后置裸星号绕过。
2. `secret_internal AS secret_internal` 自别名裸字段绕过。
3. LEFT JOIN safety 未验证 catalog left_table 已在 joined_tables。

已完成修复后执行第二轮独立 review。

第二轮结论：

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": []
}
```

第二轮 reviewer 同时验证：

- `SELECT col, *` 被拒绝。
- `SELECT secret_internal AS secret_internal` 被拒绝。
- `SELECT SUM(secret_internal) AS secret_internal` 被拒绝。
- LEFT JOIN 必须保持 catalog 方向。
- execution safety failure 时 explain/trial 都不会调用 executor。
- 未接正式 QA、业务库、前端、迁移或 `.env`。

## 验收产物

```text
ai/outbox/kanban/t_96b0f436/diff.patch
ai/outbox/kanban/t_96b0f436/test.log
ai/outbox/kanban/t_96b0f436/static-scan.json
ai/outbox/kanban/t_96b0f436/review-result-final.json
ai/outbox/kanban/t_96b0f436/final-acceptance.md
```

## 修改范围

```text
backend/app/domains/logistics/services/nl2sql/__init__.py
backend/app/domains/logistics/services/nl2sql/sql_renderer.py
backend/app/domains/logistics/services/nl2sql/sql_safety.py
backend/app/domains/logistics/services/nl2sql/sql_execution.py
tests/unit/logistics/nl2sql/test_sql_renderer.py
tests/unit/logistics/nl2sql/test_sql_safety.py
tests/unit/logistics/nl2sql/test_sql_execution.py
docs/NL2SQL_LOGISTICS_M4_SQL_RENDERER_MVP_PLAN.md
ai/outbox/kanban/t_96b0f436/*
```

## 阶段边界确认

未越界：

- 未接正式物流 QA 主链路。
- 未改前端。
- 未建数据库迁移。
- 未连接真实业务库。
- 未读取或提交 `.env`。
- 未直查 SAP Oracle MID。
- 未让 LLM 直接输出可执行 SQL。
- 未修改 `data_qa_planner.py`。

## 后续建议

下一阶段建议进入：

```text
NL2SQL M5：物流 NL2SQL Shadow Pipeline + 评估日志 MVP
```

目标是在仍不影响用户可见主链路的前提下，把 M1-M4 串成影子链路：

```text
Query Rewrite / Domain Router
→ Catalog Recall / Rerank
→ SQLPlan Candidate
→ SQLPlan Validator
→ SQL Renderer
→ SQL Safety
→ EXPLAIN / Trial
→ Trace / Evaluation Log
```

M5 应继续禁止正式接入用户可见回答，先做离线样例、trace、评估日志和失败分型。

# NQE-SQL-REAL 真实 SQL Agent 主链路差距审计

更新时间：2026-05-24 22:00 CST

## 逐项审计

### 1. generate_sql_direct 当前是否调用 LLM？

**❌ 否。** `nqe_sql_agent_graph.py:647-682`。优先取 `state["generated_sql"]` 或 `package["generated_sql_candidate"]` 或 `package["sql_candidate"]`。都不存在时：取白名单第一张表的第一列构造 `SELECT col FROM table LIMIT 10`。无可取列时：`SELECT * FROM table LIMIT 10`。无表时：`"SELECT 1"`。

**无 LLM 调用。**

### 2. 当前是否存在真实 LLM SQL generation prompt？

**❌ 否。** 整个 `nqe_sql_agent_graph.py` 无 LLM prompt、无 `OpenAI(...)` 调用。`generate_sql_direct` 是完全确定性的占位逻辑。

### 3. 当前是否存在真实 LLM provider 调用？

**❌ nqe_sql_agent_graph 中无。** LLM 调用只存在于：
- `domain_route_node.py`: LLM 语义域分类（OpenAI）
- `correct_sql_node.py`: LLM 修正 SQL（OpenAI）
- `recall_column_node.py`: LLM 扩展关键词

但 `nqe_sql_agent_graph.py` 的 `generate_sql_direct` 和 `explain_validate_sql` 都不调用 LLM。

### 4. 当前是否仍有 SELECT 1 / first table / first column 占位逻辑？

**✅ 是。**
- Line 674: `candidate = "SELECT 1"` — 纯占位
- Line 669-673: `col = columns[0] if columns else "*"` — first column 占位
- Line 799: `or "SELECT 1"` — correct_sql 占位 fallback

### 5. explain_validate_sql 当前是否执行真实 MySQL EXPLAIN？

**❌ 否。** `_validate_explain_against_metadata` 是确定性字段存在性校验：对比 SQL 中引用的字段名是否在 `context_package["table_columns"]` 中。无 DB 连接，无 `EXPLAIN` SQL 执行。

### 6. 当前是否有数据库连接 / 只读 session / timeout / max rows 控制？

**❌ 否。** `execute_sql_readonly` 不被允许连接 DB。代码明确注释"本卡不连接数据库，仅返回确定性占位结果"。

### 7. execute_sql_readonly 当前是否真实执行 SQL？

**❌ 否。** Line 819: `{"rows": [{"value": 1}], "source": "stub"}`。硬编码占位结果。

### 8. on-mode 当前是否返回完整业务问答协议？

**❌ 否。** `present_business_answer` 返回固定字符串："已完成本次业务问数骨架处理，后续能力卡将补齐真实数据校验与结果呈现。"且 `_nqe_on_mode_query` 在 API 层返回 `{"_nqe_shadow": {"nqe_result": ..., "mode": "on"}}` — 包装格式，非完整业务问答。

### 9~12. 四域 on-mode 实际行为

| 域 | on-mode 行为 |
|---|---|
| 物流 | domain_route → auto-context → generate(SELECT col LIMIT 10) → safety → metadata explain → correct → execute(stub) → present(stub) |
| 产销存 | 同上 |
| BOM | 同上 |
| 功率 | 同上（no PowerPredictionEngine call） |

全部走占位链路，不走真实 SQL。

### 13. production guard 是否真实强制 off？

**✅ 是。** `IS_PRODUCTION` property (config.py:365)。`domain_mode_map` 未到 production 时取域配置（"on"），生产时需通过 env var 覆盖。

### 14. 前端是否真实 SSE？

**❌ 否。** NqeChatPage.vue 使用 `fetch` 一次性调用。

### 15. quick chips 是否后端化？

**❌ 否。** 静态 `<el-tag>` 硬编码。

### 16. 前端是否能展示 answer/table？

**⚠️ 部分。** 支持 `result.answer` 和 `el-table`（rows/columns），但后端返回 stub 数据。

### 17. npm build 是否通过？

**⚠️ 未确认。** vue-tsc 通过，npm build 未执行。

### 18. 当前测试体系失败情况？

- NQE focused (`test_nqe_*.py`): ~95 passed 0 failed
- 全目录: 253/51 (S1/S2/S3/S4/ZG 预存)

### 19. stub/placeholder/report-only 清单

| 代码位置 | 类型 |
|---|---|
| generate_sql_direct | placeholder (first col / SELECT 1) |
| explain_validate_sql | placeholder (metadata-only, no real EXPLAIN) |
| execute_sql_readonly | stub (硬编码 `{"value": 1}`) |
| present_business_answer | stub ("骨架处理") |
| _nqe_on_mode_query | wrapper (nqe_result 包装) |
| correct_sql | placeholder (SELECT 1 fallback) |

### 20. 必须补齐的任务清单

| 优先级 | 任务 | 说明 |
|---|---|---|
| P0 | LLM SQL generation | 替换 generate_sql_direct 为真实 OpenAI/DeepSeek 调用 |
| P0 | 真实 MySQL EXPLAIN | 连接开发库执行 EXPLAIN |
| P0 | 真实只读 SQL 执行 | 连接开发库，readonly session, timeout, max rows |
| P0 | 真实 correct_sql LLM 修正 | LLM 接收 EXPLAIN 错误，重新生成 SQL |
| P0 | 完整业务问答输出 | present_business_answer 输出真实结果 |
| P1 | 四域真实端到端验证 | 每域至少 10 题真实 SQL Agent 链路 |
| P1 | production guard 测试 | dev=on, prod=off 真实验证 |
| P1 | SSE 流式 | EventSource 替代 fetch |
| P1 | quick chips 后端化 | API 返回推荐问题 |
| P2 | 前端 npm build | 完整构建验证 |
| P2 | 功率预测真实 fallback | on-mode 调用 PowerPredictionEngine |

## 结论

当前 NQE SQL Agent 是完整骨架，但所有核心链路（SQL 生成、EXPLAIN、执行、回答）都是 stub/placeholder。需要补齐 P0 五个核心能力才能称为"真实 SQL Agent 主链路"。

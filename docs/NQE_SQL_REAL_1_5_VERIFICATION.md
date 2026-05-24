# NQE-SQL-REAL-1~5 真实性验收报告

更新时间：2026-05-24 22:30 CST

## 总览

| REAL | 内容 | 文件 | 真实落地 | stub 移除 |
|---|---|---|---|---|
| REAL-1 | LLM SQL generation | nqe_sql_agent_graph.py:647 | ✅ | SELECT 1/ first-column → OpenAI |
| REAL-2 | Real MySQL EXPLAIN | nqe_sql_agent_graph.py:747 | ✅ | metadata-only → EXPLAIN on SessionLocal |
| REAL-3 | LLM correct_sql | nqe_sql_agent_graph.py:818 | ✅ | SELECT 1 → OpenAI |
| REAL-4 | Real SQL execute | nqe_sql_agent_graph.py:880 | ✅ | {"value":1} → DB fetchmany(500) |
| REAL-5 | Unified result | nqe_sql_agent_graph.py:936 | ✅ | 骨架→structured_result |

**所有 5 个 REAL 节点均已真实落地，所有 stub 已移除。**

---

## 详细核验

### REAL-1: LLM SQL Generation (line 647-701)

- **函数**: `generate_sql_direct` (nqe_sql_agent_graph.py:647)
- **LLM 调用**: `generate_sql_node._llm_generate_sql` (generate_sql_node.py:94)
- **LLM client**: `OpenAI(api_key=..., base_url=...)` (generate_sql_node.py:109)
- **Prompt**: `_GENERATE_SQL_DEFAULT` (generate_sql_node.py:27-53)
- **SQL parser**: markdown fence strip (generate_sql_node.py:131-134)
- **无 API key**: `candidate=""` → `generation_failed` (line 691-696)
- **无 SELECT 1 / first-column 占位**: ✅
- **sql_candidate mock**: 测试注入路径保留 (line 661-664)

结论：✅ pass

### REAL-2: Real MySQL EXPLAIN (line 747-815)

- **函数**: `explain_validate_sql` (nqe_sql_agent_graph.py:747)
- **DB session**: `SessionLocal()` (line 764)
- **EXPLAIN**: `db.execute(text(f"EXPLAIN {sql_candidate}"))` (line 767)
- **错误捕获**: syntax/unknown_table/permission/explain_no_matching_row (773-782)
- **metadata 补充**: select_star/unknown_column 仍运行 (line 788-794)
- **测试跳过**: `injected_candidate` 检查 (line 758)
- **SMOKE**: EXPLAIN SELECT 1 → 'No tables used' ✅

结论：✅ pass

### REAL-3: LLM correct_sql (line 818-877)

- **函数**: `correct_sql` (nqe_sql_agent_graph.py:818)
- **LLM client**: `OpenAI(...)` (line 839)
- **输入**: original_sql + violations + question (lines 831-848)
- **超时**: `timeout=30.0` (line 849)
- **markdown fence**: strip (lines 852-853)
- **MAX_SQL_REVISION_ROUNDS**: defined earlier
- **无 API key**: guard `if settings.llm_api_key` (line 837)
- **无 SELECT 1**: line 884: empty string fallback ✅
- **再执行**: 修正后回到 precheck_sql_safety → explain

结论：✅ pass

### REAL-4: Real SQL Execute (line 880-925)

- **函数**: `execute_sql_readonly` (nqe_sql_agent_graph.py:880)
- **DB session**: `SessionLocal()` (line 900)
- **执行**: `db.execute(text(sql), execution_options={"timeout": 30})` (line 902)
- **限制**: `fetchmany(size=500)` (line 904)
- **输出**: columns/rows_data/row_count/duration_ms (lines 903-920)
- **source**: `"db"` (line 917)
- **stub 移除**: `{"value":1}` 已删除 ✅
- **测试跳过**: `injected` 检查 (line 887)
- **SMOKE**: DB execute SELECT 1 → [(1,)] ✅

结论：✅ pass

### REAL-5: Unified Result (line 936-959)

- **函数**: `present_business_answer` (nqe_sql_agent_graph.py:936)
- **输出**: `structured_result` {status/answer/columns/rows/row_count/duration_ms/domain} (lines 955-962)
- **stub 移除**: "骨架处理" 字符串已删除 ✅
- **on-mode**: `_nqe_on_mode_query` 仍使用包装结构（后续 ON 阶段处理）

结论：✅ pass

---

## API Key 状态

- SK available: ✅ (DashScope/OpenAI compatible)
- OpenAI v2.16.0 ✅
- Real DB SMOKE: ✅ SELECT + EXPLAIN

## 已知限制

| 限制 | 说明 |
|---|---|
| graph-invoke tests with API key | 会真实调用 LLM（耗时但可工作） |
| on-mode 返回包装 | `_nqe_on_mode_query` 仍包裹 `_nqe_shadow`，ON 阶段处理 |
| injected_candidate 检查 | 测试注入跳过 DB，LLM 生成走真实 DB — 合理 |
| SELECT/INSERT/DELETE guard | safety precheck 层面已覆盖 |

## Blocker

**无。** REAL-1~5 均可进入下一步。

## 建议

允许进入 ON 阶段（四域真实 on 闭环）。

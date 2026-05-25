# NQE SQL 真实落地与资产缺口审计

更新时间：2026-05-24

## 1. _fallback_sql 是否在 on-mode 生效

**结论：否（但代码仍为死代码存在）**

- `generate_sql_node.py:138-149`: `_fallback_sql` 依赖 first-table/first-column/SELECT 1
- 该函数由 `generate_sql_node` 调用（旧 Graph），不用于 NQE Agent 的 `generate_sql_direct`
- NQE `generate_sql_direct` 优先 LLM，失败返回 `generation_failed`，不走 `_fallback_sql`
- **风险**：`_fallback_sql` 若被误引会生成 `SELECT * FROM ... LIMIT 100`
- **建议**：标记 deprecated 或增加 guard

## 2. 是否仍存在规则 SQL 路径

| 路径 | 状态 |
|---|---|
| `SELECT 1` | `_fallback_sql:143` — 死代码，不在 on-mode 生效 |
| first-table/first-column | `_fallback_sql:144-149` — 同上 |
| query_key | 仅在旧 PlanBomQaService 中，NQE 不调用 |
| SQL template | 不用于 NQE SQL generation |
| `sql_candidate` 注入 | 仅测试路径保留（injected_candidate guard） |

**结论**：on-mode 主链路上无规则 SQL，但死代码需清理。

## 3. 四域 on-mode 接入

| 域 | API entry | domain_hint passed | 实际 domain |
|---|---|---|---|
| logistics | business_qa.py:246 | **NO** → default "logistics" | ✅ 正确 |
| plan_bom | business_qa.py:310 | **NO** → default "logistics" | ❌ 错误 |
| business_analysis | 无独立 API 分支 | N/A | ❌ 路由缺失 |
| power_prediction | 无独立 API 分支 | N/A | ❌ 路由缺失 |

**CRITICAL**：`_nqe_on_mode_query` 调用 `run_nqe_logistics_graph(question, trace_id, nqe_mode="on")` — 未传递 `domain_hint`。所有四域调用均默认 `domain_hint="logistics"`。

## 4. _nqe_on_mode_query 分析

```python
# line 100: 统一调用 logistics graph
nqe_result = run_nqe_logistics_graph(question, trace_id, nqe_mode="on")
```

- 函数名含 "logistics" 但实际调用 `build_nqe_sql_agent_graph()`（通用）
- `domain_hint` 默认 "logistics"，未被覆盖
- 四域独立配置仅用于准入判断（on/off），不用于 domain 路由

**建议**：必须在调用时传入正确的 `domain_hint`。

## 5. nqe.py SSE 执行模式

```python
# nqe.py:26-32
final = _graph.invoke({"question": question, "nqe_mode": "on", "trace_id": tid})
# trace 事后回放
for i, node in enumerate(nodes):
    yield _sse_event("progress", ...)
```

**结论**：SSE 是 `graph.invoke()` 同步完成后，事后回放 trace events。**不是实时执行时推送。**

前端看到的是一个接一个快速推送的 `progress` events，但实际 SQL Agent 已执行完毕。这不是真正的"流式"——但这是当前架构限制（LangGraph 同步 invoke）。

## 6. quick chips

`nqe.py:78-111`: `QUICK_CHIPS` 是 Python 字典常量。静态定义，非配置化、非数据库化。

## 7. ba_metric_resolver.py

`ba_metric_resolver.py`: 存在但未集成到主链路。使用指标别名匹配用户问题文本，属于确定性映射。应迁移到 semantic catalog 的 `aliases` 字段。

## 8. nqe_metadata_sync.py 中间库写入

`upsert_nqe_metadata_bundle()` 通过 SQLAlchemy `_upsert_many` 写入 `NqeMetricInfo`、`NqeTableInfo`、`NqeColumnInfo` 等表。但这些表在 MySQL `logistics_ai` 库中，不属于独立的"智能助手中间库"。

**结论**：代码存在但用途是元数据缓存，非业务中间库（ODS/DWD）。

## 9. Milvus / 向量库

搜索 `Milvus`、`pymilvus`、`milvus_client`：

```
grep -r milvus backend/ --include="*.py" | wc -l
0
```

**结论**：❌ 未接入 Milvus / 向量库。RAG 能力未实现。

## 10. 能力资产化 vs 代码补丁

| 能力 | 状态 |
|---|---|
| LLM SQL generation | ✅ 真实（OpenAI） |
| MySQL EXPLAIN | ✅ 真实（SessionLocal） |
| SQL execution | ✅ 真实（fetchmany 500） |
| Domain routing | ⚠️ 四域 bug（见 #3） |
| Metric context | ✅ metadata sync builder |
| PowerPredictionEngine | ✅ adapter + 引擎未修改 |
| BOM compare/replay | ✅ adapter 包装旧 service |
| Milvus/vector | ❌ 未实现 |
| 智能助手中间库 | ❌ 未实现 |
| Oracle sync | ❌ 未实现 |
| Redis/cache | ❌ 未实现 |
| 查询日志持久化 | ❌ 无（仅 trace 写入 sys_query_log） |

## 11. 建议优先级

| 优先级 | 任务 |
|---|---|
| P0 | 修复四域 domain_hint bug |
| P0 | business_analysis/power_prediction API 独立分支 |
| P1 | 清理 `_fallback_sql` 死代码 |
| P1 | quick chips 迁移到 DB/配置 |
| P1 | metric resolver 迁移到 catalog |
| P2 | 中间库 ODS/DWD 建设 |
| P2 | Milvus RAG 接入 |
| P2 | Oracle SAP MID 同步 |

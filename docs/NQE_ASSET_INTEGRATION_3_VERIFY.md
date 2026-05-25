# NQE Milvus 接入真实性审计报告

更新时间：2026-05-25

## 总体结论

**Milvus collection 已创建并写入 961 条资产数据，四域覆盖完整。**
**但存在两个关键差距：**

1. **检索结果未注入 LLM prompt**：Milvus 检索在 `_llm_generate_sql` 之后执行，不影响 SQL 生成。
2. **未使用向量相似度搜索**：当前使用 Milvus `query()`（domain 过滤 + limit），不是 `search()`（向量相似度）。

---

## 一、Collection 详情

| 属性 | 值 |
|---|---|
| 名称 | `gcl_bp_ai_nqe_semantic_catalog` |
| 文档数 | 961 |
| 索引 | IVF_FLAT, metric=IP, nlist=128 |
| 向量维度 | 1024 |
| 旧 collection | `gcl_bp_ai_logistics_nl2sql_catalog` (398) — 未删除，未使用 |

## 二、资产分布

| 域 | 数量 |
|---|---|
| logistics | 623 |
| business_analysis | 112 |
| plan_bom | 107 |
| power_prediction | 119 |

| 资产类型 | 数量 |
|---|---|
| column | 652 |
| value | 200 |
| table | 44 |
| dimension | 25 |
| metric | 20 |
| fewshot_sql | 20 |

## 三、代码调用链路

```
generate_sql_direct()  ← nqe_sql_agent_graph.py:660
  ├─ _llm_generate_sql()  ← line 692 (LLM 调用，此时无 Milvus 结果)
  ├─ Milvus retrieval  ← lines 708-722 (在 LLM 之后执行！)
  │    └─ NqeSemanticVectorRetriever.search()
  │         └─ col.query(expr="domain==...", limit=10)  ← query(), 非 search()
  └─ return next_state
```

## 四、差距分析

| # | 差距 | 当前状态 | 影响 |
|---|---|---|---|
| 1 | 向量相似度 | `query()` 只过滤 domain，不比较向量 | 召回质量低，退化为随机取 10 条 |
| 2 | 检索时机 | LLM 生成 SQL 之后 | 不影响 prompt，仅记录 trace |
| 3 | 向量值为零 | 所有 vectors 为 `[0.0]*1024` 占位 | 无真实 embedding |
| 4 | 资产类型单一 | 只召回 column 类型 | 缺少 table/metric/dimension/value/fewshot |
| 5 | 旧 collection 未迁移 | 命名含 "logistics" 的旧 collection 闲置 | 无影响，但为技术债 |

## 五、四域 8 题验证

| # | 域 | ctx_src | ret_src | safety | explain | rows | YAML? | 状态 |
|---|---|---|---|---|---|---|---|---|
| 1 | 物流 | db | milvus | pass | pass | 1 | NO | completed |
| 2 | 物流 | db | milvus | pass | pass | 12 | NO | completed |
| 3 | 产销存 | db | milvus | pass | pass | 1 | NO | completed |
| 4 | 产销存 | db | milvus | pass | pass | 12 | NO | completed |
| 5 | BOM | db | milvus | pass | pass | 500 | NO | completed |
| 6 | BOM | db | milvus | pass | pass | 8 | NO | completed |
| 7 | 功率 | db | milvus | pass | pass | 1 | NO | completed |
| 8 | 功率 | db | milvus | pass | pass | 178 | NO | completed |

## 六、结论

| 问题 | 答案 |
|---|---|
| Milvus 已接入 NQE？ | ⚠️ 已连接并记录 trace，但未影响 prompt |
| 向量相似度搜索？ | ❌ 未实现（query() 代替 search()） |
| 检索结果进 prompt？ | ❌ 检索在 LLM 之后执行 |
| 旧 collection 影响？ | ❌ 未使用，无影响 |
| YAML fallback？ | ❌ 0 次 |
| 四域 support？ | ✅ 四域全覆盖 |

## 七、建议

**P0**: 将 Milvus 检索移至 LLM 调用之前，注入 prompt。
**P1**: 接入真实 embedding model，实现向量相似度搜索。
**P2**: 将旧 collection 数据迁移或标记 deprecated。

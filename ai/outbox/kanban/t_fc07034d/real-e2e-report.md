# ON-3 BOM Detail E2E Report

## Anti-rule-mode verification

| Question | Answer |
|---|---|
| 是否存在固定 SQL 模板？ | ❌ Three different SQL patterns |
| 是否存在关键词 if/else？ | ❌ LLM dynamic per-question |
| 是否存在 query_key 直出？ | ❌ NQE graph, no query_key |
| 是否存在 SELECT 1 fallback？ | ❌ |
| 是否由 LLM 生成？ | ✅ OpenAI qwen-max |
| 是否保留 trace？ | ✅ trace_id recorded |
| 3 个不同问法不同 SQL？ | ✅ |

## E2E Results

| Q | Question | SQL snippet | Rows |
|---|---|---|---|
| Q1 | GCL-...00127 评审号 BOM 明细 | WHERE order_no = 'GCL-...' | 144 |
| Q2 | SAP 1000448892 用量 | WHERE sap_code = '1000448892' | 8 |
| Q3 | glass 材料类别 | WHERE material_category = 'glass' | 307 |

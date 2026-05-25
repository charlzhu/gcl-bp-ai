# ASSET-INTEGRATION-3R-FIX2 最终验证报告

时间：2026-05-25

## 一、Milvus Collection

| 属性 | 值 |
|---|---|
| 名称 | gcl_bp_ai_nqe_semantic_catalog |
| 文档数 | 1573 |
| 索引 | IVF_FLAT, IP, nlist=128 |
| 状态 | LOADED |

## 二、资产分布

| 类型 | 数量 |
|---|---|
| column | 652 |
| value | 812 |
| table | 44 |
| dimension | 25 |
| metric | 20 |
| fewshot_sql | 20 |

| 域 | 数量 |
|---|---|
| logistics | 726 |
| plan_bom | 362 |
| power_prediction | 320 |
| business_analysis | 165 |

## 三、Value Asset 四域分布

| 域 | value 数量 |
|---|---|
| 物流 | 303 |
| BOM | 255 |
| 功率 | 201 |
| 产销存 | 53 |
| **合计** | **812** |

✅ 已按 domain + table + column 分组抽取，不再全局 LIMIT 200。

## 四、8/8 验证

| # | domain | context_source | retrieval_source | count | 状态 |
|---|---|---|---|---|---|
| 1 | 物流 | db_semantic_catalog | milvus | 10 | completed |
| 2 | 物流 | db_semantic_catalog | milvus | 10 | completed |
| 3 | 产销存 | db_semantic_catalog | milvus | 10 | completed |
| 4 | 产销存 | db_semantic_catalog | milvus | 10 | completed |
| 5 | BOM | db_semantic_catalog | milvus | 10 | completed |
| 6 | BOM | db_semantic_catalog | milvus | 10 | completed |
| 7 | 功率 | db_semantic_catalog | milvus | 10 | completed |
| 8 | 功率 | db_semantic_catalog | milvus | 10 | completed |

✅ 8/8 context_source=db_semantic_catalog
✅ 8/8 retrieval_source=milvus
✅ 8/8 search() 真实向量相似度
✅ YAML fallback=0

## 五、配置化

| 检查项 | 状态 |
|---|---|
| 硬编码 127.0.0.1 | ❌ 已全部移除 |
| Milvus host | ✅ settings.nqe_milvus_host |
| Milvus port | ✅ settings.nqe_milvus_port |
| Collection | ✅ settings.nqe_milvus_collection |
| SSL verify | ✅ settings.nqe_llm_ssl_verify |
| domain=None bug | ✅ 已修复 |
| 注释过时 | ✅ 已更新 |

## 六、结论

可以进入 QA-DATASET。

# NQE 资产缺口矩阵

| 业务域 | 源数据 | 中间库表 | 语义资产 | 向量资产 | LLM SQL支撑 | 主要缺口 | 优先 |
|---|---|---|---|---|---|---|---|
| 物流 | Excel 2023-2025 + xst_cloud 2026 | dws_logistics_detail_union (28K) | YAML ✅ | Milvus 398 ✅ | ⚠️ YAML驱动 | NQE读取YAML非DB | P1 |
| 产销存 | Excel | dwd_ba_isp_monthly_fact (1.4K) + dim tables | YAML ✅ | ❌ | ⚠️ YAML+prompt补丁 | 无量向量，metric resolver代码补丁 | P1 |
| BOM | Excel | plan_bom_* (6K) | YAML ✅ | ❌ | ⚠️ YAML驱动 | 无量向量，candidate resolver | P2 |
| 功率 | Excel | plan_power_* (1.3K) | YAML ✅ | ❌ | ⚠️ YAML驱动 | 无量向量 | P2 |

## 中间库支撑度

| 域 | 表完整 | 数据完整 | 字段完整 | NQE直接查询 | 结论 |
|---|---|---|---|---|---|
| 物流 | ✅ 11 | ✅ 28K | ✅ | ✅ LLM SQL | 支撑度高 |
| 产销存 | ✅ 3 | ✅ 1.4K | ⚠️ metric_name aliases缺失 | ✅ LLM SQL | 支撑度中 |
| BOM | ✅ 6 | ✅ 6K | ✅ | ✅ LLM SQL | 支撑度高 |
| 功率 | ✅ 7 | ✅ 1.3K | ✅ | ✅ LLM SQL + Engine | 支撑度高 |

## 向量库支撑度

| 域 | 向量资产 | 覆盖资产类型 | NQE接入 | 结论 |
|---|---|---|---|---|
| 物流 | ✅ 398 entities | table/column/metric/dimension/rule/value | ❌ | 存在但未接入 |
| 产销存 | ❌ 0 | - | ❌ | 完全缺失 |
| BOM | ❌ 0 | - | ❌ | 完全缺失 |
| 功率 | ❌ 0 | - | ❌ | 完全缺失 |

## 总结

- 中间库：✅ 四域表完整，数据有，可直接支撑 LLM SQL
- 向量库：‍⚠️ 仅物流，且 NQE 未接入 — 需扩域+接入
- Semantic catalog：❌ 未落库(nqe_* 表不存在)，仅 YAML 文件驱动

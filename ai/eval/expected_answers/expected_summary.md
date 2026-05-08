# E2E QA Phase 1 标准答案计算摘要

- 生成时间：2026-05-07T14:05:20
- 样例题总数：1391
- trace 总数：1391

## 状态统计

| 状态 | 数量 |
| --- | ---: |
| expected | 190 |
| no_answer | 6 |
| blocked | 160 |
| unsupported | 1035 |

## expected 支持能力统计

| 能力 | 数量 |
| --- | ---: |
| logistics_vehicle_count | 83 |
| logistics_month_total_fee | 32 |
| logistics_total_shipment_count | 26 |
| logistics_total_fee | 9 |
| logistics_province_customer_top5_fee_watt | 8 |
| logistics_region_transport_avg_yuan_per_watt_sort | 6 |
| logistics_transport_mode_record_count | 5 |
| logistics_spec_total_watt | 5 |
| logistics_origin_month_avg_pallet_per_vehicle | 5 |
| logistics_city_carrier_avg_unit_price_per_vehicle | 5 |
| bom_material_spec | 3 |
| bom_material_table | 2 |
| bom_material_compare | 1 |

## expected 分类统计

| 分类 | 数量 |
| --- | ---: |
| logistics_vehicle_count | 83 |
| logistics_count | 26 |
| logistics_other | 25 |
| logistics_shipment_watt | 12 |
| logistics_total_fee | 9 |
| logistics_topn | 8 |
| logistics_cost_sort | 6 |
| logistics_transport_mode_count | 5 |
| logistics_loading_efficiency | 5 |
| logistics_company_unit_price | 5 |
| bom_material_spec | 3 |
| bom_material_table | 2 |
| bom_material_compare | 1 |

## blocked/no_answer/unsupported 原因 Top 20

| 原因 | 数量 |
| --- | ---: |
| Phase 1 未纳入该历史物流题型：logistics_other | 280 |
| 复杂宽表/矩阵/排行榜/结构表/年度对比表超出当前物流 data-qa 稳定可执行边界。 | 249 |
| Phase 1 未纳入该历史物流题型：logistics_shipment_watt | 170 |
| 未提供显式只读数据库连接配置 EVAL_READONLY_DATABASE_URL 或 PHASE1_READONLY_DATABASE_URL；为避免误用业务写库配置，本脚本未访问 MySQL。 | 160 |
| Phase 1 未纳入该历史物流题型：logistics_cost_sort | 155 |
| Phase 1 未纳入该历史物流题型：logistics_company_unit_price | 73 |
| Phase 1 未纳入该历史物流题型：logistics_ambiguous_or_current | 49 |
| Phase 1 未纳入该历史物流题型：logistics_procurement_task | 21 |
| Phase 1 未纳入该历史物流题型：logistics_topn | 14 |
| Phase 1 未纳入该历史物流题型：logistics_distance | 7 |
| Phase 1 未纳入该历史物流题型：logistics_plan_actual_variance | 5 |
| 未在 Phase 0 BOM 源数据中匹配到问题指定的订单号或型号。 | 4 |
| Phase 1 未纳入该历史物流题型：logistics_loading_efficiency | 4 |
| Phase 1 未纳入该历史物流题型：logistics_rate_statistics | 3 |
| 该费用题包含占比/同比/矩阵/额外费用等 Phase 1 未纳入的派生分析。 | 3 |
| 样例题领域无法识别，Phase 1 不计算标准答案。 | 2 |
| 订单尾号命中多个 BOM 实例，缺少客户/型号/文件版本等消歧条件，标准答案标记为需追问。 | 1 |
| BOM 对比题未提供两个不同订单/版本，标准答案标记为需追问，避免把同一订单硬做对比。 | 1 |

## 输出文件

- `ai/eval/expected_answers/expected_answers.jsonl`
- `ai/eval/expected_answers/expected_answer_trace.jsonl`
- `ai/eval/expected_answers/expected_summary.md`

## 计算边界

- 所有 expected 数值均来自脚本对 Phase 0 Excel/xls 数据的聚合或物料行筛选。
- 2026 MySQL 题未使用业务数据库连接；缺少显式只读配置时统一 blocked。
- 未纳入 Phase 1 支持清单的派生分析、异常诊断、占比/同比/相关性等问题标记 unsupported。

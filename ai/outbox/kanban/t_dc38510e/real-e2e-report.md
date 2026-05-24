# ON-1 Real Logistics E2E Report

## 验证环境
- DB: 127.0.0.1 logistics_ai (28,754 rows in dws_logistics_detail_union)
- LLM: DashScope qwen-max
- Mode: on

## E2E 结果

| 问题 | SQL | 状态 | Rows |
|---|---|---|---|
| Q1: 2024年运输记录数 | SELECT COUNT(*) FROM dwd_logistics_hist_shipment_detail WHERE biz_year=2024 | completed | 1 (7,049) |
| Q2: 2023年各月运输量 | SELECT biz_month, SUM(shipment_trip_count) ... WHERE biz_year=2023 GROUP BY biz_month | completed | 12 |
| Q3: 哪个基地运输量最大 | SELECT origin_place, SUM(shipment_watt) ... GROUP BY origin_place ORDER BY total_shipment_watt DESC LIMIT 1 | completed | 1 (合肥) |

## 验证项
- LLM SQL: ✅ 3/3
- Real EXPLAIN: ✅ 3/3
- Real execute: ✅ 3/3
- safety pass: ✅ 3/3
- revision rounds: 0

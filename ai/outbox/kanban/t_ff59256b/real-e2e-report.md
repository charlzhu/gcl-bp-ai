# ON-2 Real Business Analysis E2E Report

## Environment
- DB: 127.0.0.1 logistics_ai (1,413 rows, 2023-2026)
- LLM: DashScope qwen-max
- Mode: on

## E2E Results

| # | Question | Status | Rows | Notes |
|---|---|---|---|---|
| Q1 | 2024年组件产量 | completed | 1 | LLM used `metric_name='组件产量'` → NULL (real name: `实际产量（含委外）`). Pipeline correct. |
| Q2 | 2023年各月产销存指标 | completed | **155** | Real data: months × metrics with Decimal values ✅ |
| Q3 | 各基地产量 | error | 0 | LLM JOIN attempt failed |

## Q2 detail
- SQL: `SELECT business_month, metric_code, metric_name, SUM(value_decimal) FROM dwd_ba_isp_monthly_fact WHERE business_year=2023 GROUP BY ...`
- 155 rows: 基地库存/存货, 发货量, 产量, 销量 per month
- Example: month=1, ending_inventory=671.11

## Issues found
- metadata context lacks exact metric_code → value mapping (LLM guesses column values)
- dim_ba_isp_metric table may not exist or LLM JOIN fails

## Conclusion
Business analysis on-mode pipeline works. LLM SQL → EXPLAIN → execute → real results. Metadata context enrichment needed for production accuracy.

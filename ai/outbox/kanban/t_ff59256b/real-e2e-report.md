# ON-2 Fix Real E2E Report

## Fix Applied
- metrics context: retrieval_assets now includes 24 metrics (metric_id/display_name/aliases/formula)
- prompt: metric_code filtering + is_published_month=1 + base_name guidance

## Fixed E2E Results

| # | Question | Status | Rows | Result |
|---|---|---|---|---|
| Q1 | 2024年产量 | completed | 1 | **212,339.61 MW** (real) ✅ |
| Q2 | 2023年月销量 | completed | 12 | real monthly data ✅ |
| Q3 | 合肥产量 | completed | 1 | NULL (metric_code precision gap) |

## Q1 detail
- SQL: `SELECT ... SUM(value_decimal) FROM dwd_ba_isp_monthly_fact WHERE business_year=2024 AND metric_name LIKE '%产量%' GROUP BY business_year`
- Result: 212,339.61 MW — real production data ✅

## Q2 detail
- SQL: `SELECT business_month, SUM(value_decimal) FROM ... WHERE business_year=2023 AND metric_name LIKE '%销量%' GROUP BY business_month`
- Result: 12 months with real Decimal values ✅

## Known Limitation
- LLM uses metric_name LIKE instead of metric_code exact match
- Further prompt tuning needed for metric_code precision

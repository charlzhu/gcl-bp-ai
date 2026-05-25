# ON-5 Fix E2E Report

## PowerPredictionEngine REAL Call

```
API: PowerPredictionEngine.predict(model_code="NT12R-48GDF")
INPUT: model_code from LLM SQL query on plan_power_model_sheet
OUTPUT:
  center_power: 457.6 W
  std_dev: 1.0
  area: 38,184 mm²
  supplier: 芜湖（80mg）
  cell_count: 48
  center_efficiency: 0.26
  efficiency_rows: 7 rows
  power_bins: [440, 445, 450, 455, 460, 465, 470]
  warnings: process config/raw_meta defaults
```

## E2E Results

| Q | Question | Status | Detail |
|---|---|---|---|
| Q1 | 功率模型版本 | completed | TOPCon 26.04.13 (LLM SQL + EXPLAIN + execute) |
| Q2 | 模型 sheet 信息 | completed | NT10/12 sheet names (LLM SQL) |
| Q3 | 预测计算 | ✅ REAL | PowerPredictionEngine.predict(NT12R-48GDF) → 457.6W |

## Anti-rule-mode
- No fixed SQL
- No fixed prediction results
- LLM SQL for queries
- Engine for computation
- Engine formula NOT modified

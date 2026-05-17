# TASK-logistics-route-year-compare-2023-fix 独立审查记录

## 审查结论

独立 reviewer 未发现阻塞问题。本轮修复有效覆盖核心问题：当用户显式请求 2023/2024/2025 年度对比、但某一年无匹配记录时，结果表不会再静默缺年，而是保留该年份空值行，并在摘要和 warnings 中提示“无匹配记录”。

## reviewer 重点检查

1. `hist_route_pricing_analysis` 的 `year_compare` 分支按请求年份补齐结果，不是硬编码 2023。
2. 缺失年份返回：`{"biz_year": year, "avg_fee": None, "row_count": 0}`，并记录 `missing_years`。
3. service 层在 `answer_summary` 和 `warnings` 中说明缺失年份，避免用户误以为系统漏查。
4. 城市口径“广州”缺 2023 时保留空值行；省份口径“广东”真实存在 2023/2024/2025 时继续返回真实均价与记录数。
5. `price_metric` 仅在受控列 `unit_price_per_vehicle` / `total_fee` 间切换，无 SQL 注入风险。

## reviewer 非阻塞建议与处理

### 建议 1：年度对比输出顺序与 `query_plan.sort` 保持一致

reviewer 发现：若用户问“25年、23年、24年……”，补齐逻辑若按原始 `years` 顺序返回，会与 planner 中 `sort=[{"field": "biz_year", "direction": "asc"}]` 不一致。

处理结果：已修复。

- 仓储层补齐时改为按 `sorted({int(year) for year in years})` 输出；
- service 层摘要中的年份范围也同步按升序展示；
- 回归测试把省份用例改为乱序输入 `25年、23年、24年...`，断言输出仍为 `[2023, 2024, 2025]`。

### 建议 2：`city LIKE` 未来可继续收敛

reviewer 认为 `city LIKE` 对“广州/广州市”兼容合理，但未来可通过城市别名表或同时下推省份进一步降低扩大匹配风险。

处理结果：记录为非阻塞后续优化。本轮不扩大范围，避免改动超出“缺年份”修复主题。

### 建议 3：空值展示可读性

reviewer 建议前端未来可把 `null` 单元格展示为 `无匹配记录` / `--`。

处理结果：本轮后端已通过摘要、warning、`row_count=0` 明确提示；前端展示优化不作为本轮阻塞项。

## 复核结果

处理 reviewer 顺序建议后，重新执行：

```bash
PYTHONPATH=. pytest -q tests/business_acceptance
```

结果：`155 passed, 2 warnings`。

```bash
python -m py_compile backend/app/domains/logistics/repositories/data_qa_repository.py backend/app/domains/logistics/services/data_qa_service.py tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py
```

结果：通过。

```bash
git diff --check -- backend/app/domains/logistics/repositories/data_qa_repository.py backend/app/domains/logistics/services/data_qa_service.py tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py
```

结果：通过。

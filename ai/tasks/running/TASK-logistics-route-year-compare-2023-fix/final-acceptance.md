# TASK-logistics-route-year-compare-2023-fix 最终验收报告

## 一、任务目标

用户反馈：物流问答答案中缺少 23 年数据，要求分析排查原因并解决，保证这一类问题不再出现。

本轮聚焦题型：历史物流线路/城市运价年度对比，例如：

```text
23年、24年、25年合肥发广州17.5车运价分别是多少？
```

## 二、根因分析

### 1. 复现现象

修复前，planner 能正确识别：

```python
query_key = "hist_route_pricing_analysis"
filters = {
    "years": [2023, 2024, 2025],
    "vehicle_type": "17.5",
    "view_mode": "year_compare",
    "price_metric": "unit_price_per_vehicle",
    "origin_place": "合肥",
    "city": "广州",
}
```

但 service 最终返回表格只有：

```text
[2024, 2025]
```

新增 RED 测试在修复前失败：

```text
E       assert [2024, 2025] == [2023, 2024, 2025]
```

### 2. 数据核验

源数据/数据库核验结果：

- `合肥 + 17.5车 + city LIKE 广州`：2024、2025 有记录；2023 无精确城市记录；
- `合肥 + 17.5车 + province=广东`：2023、2024、2025 均有记录。

因此根因不是 planner 没识别 2023，也不是 2023 源 Excel 未导入；而是：

> `year_compare` 仓储查询只按 SQL 聚合返回“有匹配记录的年份”。当某个显式请求年份在当前筛选条件下无匹配记录时，该年份不会出现在 SQL 结果中，service 又没有补齐/提示，导致答案看起来像漏查了 2023 年。

## 三、修复方案

### 1. 仓储层补齐显式年份

文件：

```text
backend/app/domains/logistics/repositories/data_qa_repository.py
```

在 `hist_route_pricing_analysis(... view_mode="year_compare")` 中：

- SQL 仍只负责真实聚合；
- SQL 返回后按请求年份集合补齐；
- 缺失年份返回空值行：

```python
{"biz_year": year, "avg_fee": None, "row_count": 0}
```

- 同时返回 `missing_years`，供服务层生成提示；
- 输出顺序按 `biz_year` 升序，和 planner 的 `sort=[{"field": "biz_year", "direction": "asc"}]` 保持一致。

### 2. 服务层明确提示无匹配记录

文件：

```text
backend/app/domains/logistics/services/data_qa_service.py
```

当 `missing_years` 非空时：

- `answer_summary` 追加：`其中2023年无匹配记录。`
- `warnings` 追加：已保留空值行，避免显式年份被静默遗漏。

### 3. 回归测试覆盖同类问题

文件：

```text
tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py
```

新增/强化：

1. `test_multi_year_route_pricing_keeps_requested_year_when_city_has_no_rows`
   - 覆盖城市口径“广州”在 2023 无匹配记录时仍返回 2023 空值行；
   - 断言 `answer_summary` 和 `warnings` 都说明 2023 无匹配记录。

2. `test_multi_year_route_pricing_does_not_drop_existing_province_year_rows`
   - 覆盖省份口径“广东”真实存在 2023/2024/2025 时全部返回真实数据；
   - 使用乱序问法 `25年、23年、24年...`，断言输出仍按年份升序 `[2023, 2024, 2025]`，防止排序/审计口径再次不一致。

## 四、验证结果

### RED

修复前新增测试失败，确认问题存在：

```text
E       assert [2024, 2025] == [2023, 2024, 2025]
```

### GREEN / 回归

```bash
PYTHONPATH=. pytest -q \
  tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py::test_multi_year_route_pricing_keeps_requested_year_when_city_has_no_rows \
  tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py::test_multi_year_route_pricing_does_not_drop_existing_province_year_rows \
  tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py::test_2025_hefei_to_guangzhou_17_5_quote_uses_unit_price_per_vehicle
```

结果：

```text
3 passed
```

```bash
PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py
```

结果：

```text
31 passed
```

```bash
PYTHONPATH=. pytest -q tests/business_acceptance
```

结果：

```text
155 passed, 2 warnings
```

说明：2 个 warning 为 openpyxl 读取 xlsm/条件格式的既有提示，不是本轮新增失败。

### 静态 / 编译 / 构建

```bash
python -m py_compile backend/app/domains/logistics/repositories/data_qa_repository.py backend/app/domains/logistics/services/data_qa_service.py tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py
```

结果：通过。

```bash
git diff --check -- backend/app/domains/logistics/repositories/data_qa_repository.py backend/app/domains/logistics/services/data_qa_service.py tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py
```

结果：通过。

```bash
cd frontend && npm run build
```

结果：通过，仅 Vite chunk size warning。

## 五、审查结果

独立 reviewer 结论：未发现阻塞问题。

reviewer 提出的“乱序年份输入时输出顺序应与 `query_plan.sort` 保持一致”建议已处理：

- 仓储层按年份升序补齐/输出；
- service 摘要按年份升序展示；
- 回归测试已覆盖乱序输入。

## 六、影响范围

### 修改文件

```text
backend/app/domains/logistics/repositories/data_qa_repository.py
backend/app/domains/logistics/services/data_qa_service.py
tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py
```

### 不影响范围

- 不修改数据库结构；
- 不修改前端；
- 不改变物流主数据导入；
- 不改变 BOM / 计划 BOM / 功率模型能力；
- 不让 LLM 参与运价计算。

## 七、交付物

```text
ai/tasks/running/TASK-logistics-route-year-compare-2023-fix/diff.patch
ai/tasks/running/TASK-logistics-route-year-compare-2023-fix/test.log
ai/tasks/running/TASK-logistics-route-year-compare-2023-fix/static_scan.txt
ai/tasks/running/TASK-logistics-route-year-compare-2023-fix/review.md
ai/tasks/running/TASK-logistics-route-year-compare-2023-fix/final-acceptance.md
```

## 八、结论

本轮已修复“显式多年份线路运价对比中，某年份无匹配记录时被静默遗漏”的通用问题。以后同类问题会按请求年份完整返回：

- 有数据年份：返回真实均价和记录数；
- 无数据年份：保留该年份空值行、`row_count=0`，并在摘要/warnings 中明确说明无匹配记录。

验收状态：通过。

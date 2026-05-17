# Codex implementation prompt

你是 gcl-bp-ai 项目的代码实现 worker。请严格按 TDD 修复当前 RED 测试，不要提交、不要推送、不要改生产配置。

## 当前工作区

- Repo: `/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai`
- 当前分支：已有脏工作树，禁止清理/回滚无关文件。
- 只允许修改与本任务直接相关的文件，优先：
  - `backend/app/domains/plan_bom/services/qa_service.py`
  - 必要时 `backend/app/domains/plan_bom/services/power_recommendation_service.py`
  - 必要时更新本任务新增的测试：`tests/business_acceptance/test_plan_power_real_business_qa_regression.py`（只能修测试格式/更准确断言，不能降低业务要求）
- 禁止：`.env`、密钥/token、数据库迁移、前端 token、提交/合并/部署、大范围重构。

## 已确认 RED

运行命令：

```bash
PYTHONPATH=. python -m pytest tests/business_acceptance/test_plan_power_real_business_qa_regression.py::test_business_power_recommendation_table_matches_sales_excel_export_columns -q
```

当前失败点：供应商功率推荐表仍是旧列：`供应商/匹配度/目标功率档/目标比例/预测比例/差异/中心功率/建议效率段`，不符合业务员的 Excel 下载意见。

## 要实现的六点业务要求

1. `匹配度` 列不要展示/导出；但 raw_result 内部可保留 `score` 用于追溯。
2. 在 answer_summary 中解释：`预测比例` 是什么意思、数据怎么来的。要求说明它来自后端确定性功率模型：供应商电池效率分布 × 正态落档概率汇总到目标功率档，不由 LLM/前端计算。
3. 原 `差异` 列改为 `CTM值`，按百分比可读格式展示，例如 `96.94%`。不要再展示目标比例和预测比例的差。
   - 建议 CTM 计算口径：`中心功率 / (中心效率 × 面积 × 电池片数 / 1000) × 100`。相关字段在 `PowerPredictionResult` 中已有 `center_power/center_efficiency/area/cell_count`。
4. 在 answer_summary 中解释：`中心功率` 怎么计算的。要求说明中心功率来自功率模型基准功率叠加玻璃、焊带、线缆、汇流条、供应商等配置影响值。
5. `建议效率段` 从最低效率开始，只保留 2 个。显示格式仍如 `25.5%、25.6%`。不要出现 3 个；若推荐源少于 2 个则按实际可用数量展示。
6. 明细表最后新增 `落档比例预估` 列，用于展示从最低建议电池效率档开始的落档比例预估。可读格式建议如：`25.5%→615W 12.98%、620W 82.08%；25.6%→615W 2.59%、620W 77.17%`。
   - 数据必须来自 `item.prediction.efficiency_rows[*].bin_probabilities`，不要编造。
   - 每个效率段至少包含目标功率档；可补充概率最高的相邻档，让业务看懂。

## 目标表头

`response.result_table.columns` 必须是：

```python
[
    "供应商",
    "目标功率档",
    "目标比例",
    "预测比例",
    "CTM值",
    "中心功率",
    "建议效率段",
    "落档比例预估",
]
```

## 验证

请完成后运行：

```bash
PYTHONPATH=. python -m pytest tests/business_acceptance/test_plan_power_real_business_qa_regression.py::test_business_power_recommendation_table_matches_sales_excel_export_columns -q
PYTHONPATH=. python -m pytest tests/business_acceptance/test_plan_power_real_business_qa_regression.py -q
```

输出你修改了哪些文件、测试结果。注意所有新增/修改 Python 函数或复杂逻辑要有中文注释。
# TASK-plan-power-m3-calculation-engine 最终验收

## 1. 结论

M3：计划 BOM 功率预测正式计算引擎已完成。

本轮已实现后端确定性计算引擎与供应商推荐服务，并通过 focused 测试、M2 回归、全量测试、compileall、diff check、静态安全扫描和独立 reviewer 第 2 轮复审。

Reviewer 最终结论：

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": [],
  "suggestions": [],
  "summary": "完成只读第2轮复审，确认第1轮 process 阻塞已修复；benchmark、output bin/terminal boundary、target ratio 校验、无 VBA/LLM/越界修改均符合预期。"
}
```

## 2. 修改文件

```text
backend/app/domains/plan_bom/services/power_prediction_engine.py
backend/app/domains/plan_bom/services/power_recommendation_service.py
backend/app/domains/plan_bom/services/power_excel_parser_service.py
tests/business_acceptance/test_plan_power_m3_prediction_engine.py
ai/tasks/running/TASK-plan-power-m3-calculation-engine/codex_prompt.md
ai/tasks/running/TASK-plan-power-m3-calculation-engine/codex_final.md
ai/tasks/running/TASK-plan-power-m3-calculation-engine/diff.patch
ai/tasks/running/TASK-plan-power-m3-calculation-engine/m3_combined.diff
ai/tasks/running/TASK-plan-power-m3-calculation-engine/test.log
ai/tasks/running/TASK-plan-power-m3-calculation-engine/final-acceptance.md
```

## 3. 核心能力

### 3.1 PowerPredictionEngine

新增：

```text
backend/app/domains/plan_bom/services/power_prediction_engine.py
```

实现：

1. 读取 active 功率模型版本。
2. 按 `model_code` 定位模型 Sheet。
3. 严格解析配置项：
   - ribbon
   - glass
   - supplier
   - cell_size
   - cable
   - busbar
   - process
   - benchmark
4. 后端确定性计算中心功率：

```text
center_power = base_power + Σ effect_value
```

5. 后端确定性计算理论功率、中心转换系数、效率段功率。
6. 使用标准正态 CDF 复现功率档概率。
7. 按供应商效率分布加权计算功率档分布。
8. 写入 `plan_power_model_validation_case`，保留输入、Excel 期望/缓存、系统结果、diff、状态。

### 3.2 PowerRecommendationService

新增：

```text
backend/app/domains/plan_bom/services/power_recommendation_service.py
```

实现：

1. 遍历候选供应商预测。
2. 校验目标功率档比例。
3. 计算目标比例匹配分。
4. 按分数降序输出推荐结果。
5. 返回 rejected suppliers 与原因。

### 3.3 parser raw_meta 增强

修改：

```text
backend/app/domains/plan_bom/services/power_excel_parser_service.py
```

新增 raw_meta：

```text
efficiency_start
center_efficiency
efficiency_end
efficiency_step
center_row_number
efficiency_first_row_number
power_bin_count
probability_output_bin_count
power_bin_has_terminal_boundary
```

用于 M3 识别功率档输出列和末尾边界列，避免错误把终止边界当成输出概率档。

## 4. 关键业务修复

### 4.1 process 严格匹配

已修复 reviewer 第 1 轮阻塞问题。

规则：

```text
模型页存在 process 有效选项：
- process=TCI 使用 effect_value=3.0
- 非法 process 抛 PowerPredictionError

模型页不存在 process 有效选项：
- 未传/空 process 才 optional_missing_as_zero
- 显式传入非法 process 仍抛 PowerPredictionError
```

### 4.2 benchmark 优先专表

规则：

```text
优先 plan_power_benchmark_factor
再 fallback plan_power_factor_option
```

测试覆盖：

```text
NT12R-78GDF 莱茵基准 effect_value=-2.59 source=benchmark_table source_cell_ref=C6
```

### 4.3 目标比例校验

已覆盖：

```text
目标档越界
非数字
NaN / Inf
负数
总和为 0
重复归一化目标档
```

越界错误不会被吞成供应商 rejected，而是整体请求失败。

## 5. 测试结果

### M3 focused

```text
PYTHONPATH=. pytest tests/business_acceptance/test_plan_power_m3_prediction_engine.py -q
9 passed, 2 warnings in 4.49s
```

### M2 回归

```text
PYTHONPATH=. pytest tests/business_acceptance/test_plan_power_m2_model_versioning.py -q
9 passed in 3.59s
```

### 全量测试

```text
PYTHONPATH=. pytest tests -q
40 passed, 2 warnings in 8.79s
```

### 其他验证

```text
compileall: 通过
git diff --check: 通过
m3_import_ok: 通过
predict smoke: predict_ok NT12R-66GDF 622.26 芜湖 9 1.0
recommend smoke: recommend_ok 1 芜湖 92.902706
static_findings=0
```

## 6. M3 未做事项 / 边界确认

本轮没有做：

```text
未修改前端
未接入 PlanBom QA / smart-chat
未实现 M4 BOM 配置自动映射
未让 LLM 计算功率预测结果
未执行 Excel VBA / 宏
未 hardcode BOM配置搭配问询.docx 中假订单、假版型、假项目名、假评审号
未新增数据库迁移
```

## 7. 风险与后续建议

1. M3 当前是 service 层能力，尚未暴露给 PlanBom QA；M4/M5 再接自然语言问答链路。
2. Excel xlsm 缓存分布可能来自最后一次人工/宏选择；M3 测试只在缓存选择状态可证明一致时做严格分布 parity，其余以中心功率和后端语义计算为准。
3. 下一阶段建议进入 M4：BOM 配置自动映射，把真实订单/版型/BOM 中的玻璃、间隙贴膜、焊带、汇流条、接线盒、认证/标板口径映射到 M3 configuration。

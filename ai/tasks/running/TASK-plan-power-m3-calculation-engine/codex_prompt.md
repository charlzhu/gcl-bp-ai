你是 gcl-bp-ai 项目的 Codex 工程师 worker。请在当前工作区完成 M3：计划 BOM 功率预测正式计算引擎。

工作目录：/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai
当前分支：agent/TASK-plan-power-m3-calculation-engine

重要：当前分支包含刚验收通过的 M2 未提交变更，不要回滚 M2 文件。仓库里还有若干物流域既有脏文件，不属于本任务，不要修改它们。

必须遵守：
1. 仅实现 M3 后端确定性计算引擎与推荐服务。
2. 不修改前端。
3. 不接入 /smart-chat。
4. 不修改 PlanBomQaService 可答逻辑。
5. 不实现 M4 BOM 配置自动映射。
6. 不 hardcode `BOM配置搭配问询：.docx` 的假订单 / 假版型 / 假答案。
7. 不让 LLM 计算功率预测结果。
8. 不执行 Excel VBA。
9. 不新增数据库迁移；M2 已有 `plan_power_model_validation_case` 可用于 M3 校验记录。
10. 新增/修改代码必须有中文注释，说明函数功能、参数、返回值、关键业务逻辑。

必须先阅读：
- AGENTS.md
- ai/tasks/running/TASK-plan-power-m3-calculation-engine/plan.md
- docs/PLAN_POWER_IMPLEMENTATION_PLAN.md 的 M3 章节
- docs/PLAN_POWER_BUSINESS_CONFIRMATION.md
- ai/inbox/attachments_manifest.md
- backend/app/domains/plan_bom/models.py
- backend/app/domains/plan_bom/repositories/power_model_repository.py
- backend/app/domains/plan_bom/services/power_model_service.py
- tests/business_acceptance/test_plan_power_m2_model_versioning.py

M3 需要新增/修改建议文件：
- backend/app/domains/plan_bom/services/power_prediction_engine.py
- backend/app/domains/plan_bom/services/power_recommendation_service.py
- backend/app/domains/plan_bom/schemas/power_prediction.py（如需要）
- backend/app/domains/plan_bom/repositories/power_model_repository.py（仅增加 M3 只读查询/校验用例写入方法）
- tests/business_acceptance/test_plan_power_m3_prediction_engine.py

核心公式口径：
- `formula_policy = semantic_fixed_mode`
- 不完全照搬 Excel 的 `NT12R-66GDF!R30/R32` 原始疑似错误公式；正式计算必须按语义修正：
  `prob = CDF((actual_power - lower_bin) / std_dev) - CDF((actual_power - upper_bin) / std_dev)`
- `normal_cdf(x) = 0.5 * (1 + erf(x / sqrt(2)))`

Excel 当前结构规律（从新版 `GCL功率测试基准（V2.1）TOPCon 26.04.13.xlsm` 审计得到）：
- 模型页电池效率区为 `C29:C48`，步长 0.001。
- 固定中心行是 Excel 第 36 行，中心功率单元格是 `I36`。
- 理论功率：`single_cell_power = efficiency * area / 1000`，`module_theoretical_power = single_cell_power * cell_count`。
- 中心行功率：`center_power = base_power + 各配置项 effect_value 之和`。
- 中心行转换系数：`center_ratio = center_power / theoretical_power_at_center_efficiency`。
- 其他效率段实际功率按 Excel H/I 列语义复现：
  `row_offset = center_row_index - row_index`
  `actual_power = theoretical_power * (center_ratio + row_offset * 0.0015)`
  其中 row_index 来自效率值在 `C29:C48` 中的位置。
- 功率档概率：
  `P(bin_i) = CDF((actual_power - bin_i) / std_dev) - CDF((actual_power - next_bin) / std_dev)`。
  对最后一档，如没有 next_bin，可使用 `bin_i + bin_step`；当前 bin_step 一般为 5W。
- 供应商加权分布：`weighted_distribution[bin] = Σ supplier_efficiency_ratio_i * P_i_bin`。

注意：M2 当前 `PlanPowerModelSheet.raw_meta_json` 可能只包含：`max_row/max_column/base_power_formula/center_power_cached/has_tail_space`，可以在 M3 中兼容两种方式：
1. 如果 raw_meta 中有 `efficiency_start/center_efficiency/efficiency_step/center_row_number` 则优先使用。
2. 如没有，按当前 Excel 模型结构兜底：
   - `NT12R-66GDF (2.0)`：efficiency_start=0.255，center_efficiency=0.262。
   - `NT12R-48GDF`、`NT12R-48BGDF`、`NT12R-54GDF`、`NT12R-54BGDF`：efficiency_start=0.253，center_efficiency=0.260。
   - 其他模型页：efficiency_start=0.247，center_efficiency=0.254。
   该兜底是对当前 Excel 结构的兼容，不是 hardcode 业务答案；请在 trace/warnings 中标明 fallback。
3. 也可以顺手增强 `PowerExcelParserService`，在 sheet raw_meta 里写入 `efficiency_start`、`center_efficiency`、`efficiency_end`、`efficiency_step`、`center_row_number`、`center_row_excel`，但不能破坏 M2 测试。

配置项匹配要求：
- 输入 configuration 至少支持 key：`ribbon/glass/supplier/cell_size/cable/busbar/process/benchmark`。
- `process` 在当前模型中可能不存在，可作为可选项；缺失时不报错，默认 effect=0 并在 trace 中说明。
- 对每个非空配置项，按 `normalized_option_label` 或 `option_label` 精确匹配，有效项才可用。
- benchmark 优先查 `plan_power_benchmark_factor` 的 `normalized_benchmark_name/benchmark_name`，其次兼容 `plan_power_factor_option factor_key=benchmark`。
- cell_size 选项需要提供 area/std_dev，若没有则使用 sheet 默认；若无法确定则失败。
- supplier 配置既参与 supplier effect，也用于选择供应商效率分布。
- 不存在或无效配置项必须返回 unresolved_items，并抛出受控异常或返回不可计算结果，不能编造。

建议输入输出结构：
- `PowerPredictionRequest`：model_code、configuration、supplier_name、target_power_ratio 可选、version_id 可选。
- `PowerPredictionResult`：version、model_sheet、center_power、area、std_dev、cell_count、factor_traces、efficiency_rows、power_bins、weighted_distribution、total_ratio、unresolved_items、warnings。
- `PowerRecommendationService`：输入 model_code/configuration/target_power_ratio/supplier_names 可选，输出 recommendations 按 score 降序。

推荐评分第一版：
`score = 100 - target_abs_error_sum*100 - leakage_ratio*50 - missing_distribution_penalty - unresolved_penalty`，限制到 0-100。

测试要求：
1. 新增 `tests/business_acceptance/test_plan_power_m3_prediction_engine.py`。
2. 用 SQLite 临时库，复用 M2 import，把新版 xlsm 导入并激活。
3. 至少 10 组配置 parity：建议对 10 个模型页使用 Excel 当前默认配置 + 当前缓存供应商分布匹配出来的供应商，与 Excel data_only 的 `I36` 和 `K71:T71`/有效档汇总做比较。
   - 可在测试中从 xlsm data_only 读取 baseline，但系统计算不能使用 Excel 运行时，也不能执行宏。
   - 阈值：center_power <= 0.01；档位比例 <= 1e-4。
4. 覆盖 `normal_cdf`、无 active 版本、版型不存在、配置不存在、供应商无有效分布、目标功率档不在模型范围、推荐排序。
5. 如写入 validation cases，检查 `plan_power_model_validation_case` 有至少 10 条且 status 合理。

运行验证：
- `PYTHONPATH=. pytest tests/business_acceptance/test_plan_power_m3_prediction_engine.py -q`
- `PYTHONPATH=. pytest tests/business_acceptance/test_plan_power_m2_model_versioning.py -q`
- `PYTHONPATH=. pytest tests -q`
- `python -m compileall backend/app scripts`
- `git diff --check -- <M3/M2 touched files>`

请完成后把总结写入：
`ai/tasks/running/TASK-plan-power-m3-calculation-engine/codex_final.md`

总结必须包含：
- 修改文件清单
- 核心公式实现说明
- 测试命令和结果
- 未做事项（M4/M5/前端/QA 接入未做）
- 风险点

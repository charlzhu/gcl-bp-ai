# ISP-M7 NL2SQL shadow 与 M4 QA 双轨对比 — 最终验收

## 任务信息

- **任务**: t_56c6e7b2
- **标题**: gcl-bp-ai ISP-M7: NL2SQL shadow 与当前 M4 QA 双轨对比
- **分支**: feature/isp-m7-shadow-qa-compare (基于 origin/agent/bp-main)
- **版本**: business_analysis_inventory_sales_production_m7_shadow_qa_compare.v1

## 变更范围

### 新增文件

1. `backend/app/domains/business_analysis/services/inventory_sales_production/m7_shadow_qa_compare.py`
   - M7 双轨对比核心模块（~880 行）
   - 定义六维度对比引擎：状态分类、指标口径、期间口径、结果行数、关键数值、用户可见文案安全性
   - M7 运行器 InventorySalesProductionM7ShadowQaCompareRunner
   - 默认样例构建函数 build_default_inventory_sales_production_m7_shadow_samples（11 条样例覆盖核心场景和 fail-closed 场景）
   - CLI 安全摘要渲染函数 render_safe_m7_shadow_qa_compare_summary_json
   - 全部异常 fail-closed，敏感信息脱敏

2. `tests/unit/business_analysis/test_inventory_sales_production_m7_shadow_qa_compare.py`
   - M7 单元测试文件（~345 行，17 条测试）
   - 覆盖：模块导入、维度完整性、全匹配、各维度不匹配、Decimal 精度容忍、文案安全检测/干净、shadow 不干扰 M4、异常 fail-closed、报告结构、敏感信息无泄露、CLI 摘要安全

### 禁止修改范围（未触碰）

- 物流问答主链路
- 计划 BOM 功率预测主链路
- M4 QA 服务 m4_qa_service.py
- M5 shadow compare m5_shadow_compare.py
- M6 live provider gate m6_live_provider_gate.py
- 前端任何文件

## 测试结果

### M7 单元测试

```
17 passed in 0.70s
```

| 测试 | 结果 |
|------|------|
| test_m7_module_importable_and_version_correct | PASS |
| test_m7_compare_dimensions_cover_all_six | PASS |
| test_m7_compare_single_sample_matched_all_dimensions | PASS |
| test_m7_compare_status_classification_mismatch | PASS |
| test_m7_compare_metric_caliber_mismatch | PASS |
| test_m7_compare_period_caliber_mismatch | PASS |
| test_m7_compare_row_count_mismatch | PASS |
| test_m7_compare_key_value_mismatch | PASS |
| test_m7_compare_key_value_decimal_tolerance | PASS |
| test_m7_compare_text_safety_leak_detection | PASS |
| test_m7_compare_text_safety_clean | PASS |
| test_m7_runner_declares_shadow_only_and_formal_qa_not_executed | PASS |
| test_m7_compare_m4_error_fail_closed | PASS |
| test_m7_compare_m6_shadow_error_fail_closed | PASS |
| test_m7_run_generates_report_with_correct_structure | PASS |
| test_m7_report_json_no_sensitive_leakage | PASS |
| test_m7_cli_safe_summary_renders_without_sensitive_data | PASS |

### 相邻域回归

```
tests/unit/business_analysis/ — 126 passed in 13.43s
```

包括 M3 查询执行器（8 测试）、M4 QA 服务（4 测试）、M5 shadow 对比（14 测试）、M6 live provider gate（14 测试）、M8 live gate（11 测试）、语义目录（6 测试）、SQLPlan 验证器（52 测试）。

**无回归** — 所有既有测试保持通过。

### 编译与静态扫描

- compile: PASS（py_compile 无错误）
- flake8: CLEAN（0 违规）

## 关键设计决策

1. **六维度对比引擎**：compare_m4_m6_results() 独立函数，接受 M4/M6 结果字典，返回逐维度对比列表。
2. **Decimal 精度容忍**：关键数值维度使用 Decimal 归一化比较，不同 scale 但相同数值视为匹配。
3. **文案安全检查**：仅检查 M4 用户可见文案（answer_summary、result_table、warnings），使用独立正则模式列表检测内部技术词泄露。
4. **异常 fail-closed**：M4 或 M6 任一路径异常时不会中断对比流程，异常维度标记为不匹配。
5. **默认样例**：11 条样例覆盖销量汇总、季度、YTD、库存快照、寄存仓、预算达成率、维度拆分、趋势、开票销量、无时间条件澄清、同比不支持场景。

## 合同保证

- `shadow_only = True` — 不接管正式 QA 链路
- `formal_qa_executed = False` — 不写正式问答记录
- 所有输出 JSON/JSONL 经过敏感信息过滤
- CLI 摘要不包含表名、SQL、provider 名称、密钥

## 验收材料

- `ai/outbox/kanban/t_56c6e7b2/diff.patch` (1209 lines)
- `ai/outbox/kanban/t_56c6e7b2/test.log` (17 tests, all PASS)
- `ai/outbox/kanban/t_56c6e7b2/final-acceptance.md` (本文件)

## 当前状态

- 代码已暂存（git add），未提交
- 未 push
- 未 deploy
- 待 review

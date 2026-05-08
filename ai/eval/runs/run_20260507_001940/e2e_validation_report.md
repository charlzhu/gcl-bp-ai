# E2E QA 自动验收最终报告

- run_id：`run_20260507_001940`
- 模式：`E2E_QA_AUTOPILOT_MANAGER_MODE`
- 结论：本轮自动验收框架、标准答案 trace、浏览器 E2E、对比、定向修复、鲁棒性验证均已完成；当前验证范围内通过。
- 重要约束：未 commit、未 push、未 deploy；未写生产数据库；未修改 `.env` 或密钥。

## 1. 数据资产解析

输入资产：

- `ai/inbox/requirement.md`
- `ai/inbox/attachments/23 年至 25 年物流源数据.zip`
- `ai/inbox/attachments/BOM 源数据.zip`
- `ai/inbox/attachments/物流和 bom样例题.docx`

产物：

- `ai/eval/data_profile_report.md`
- `ai/eval/sample_questions.jsonl`
- `ai/eval/scripts/phase0_prepare_assets.py`

处理结果：

- 已解析 docx 样例题；
- 已解析历史物流 Excel 与 BOM Excel；
- 已过滤 `__MACOSX` / `._*` 元数据；
- 样例题总数：1391。

## 2. 标准答案与 trace 审查

产物：

- `ai/eval/expected_answers/expected_answers.jsonl`
- `ai/eval/expected_answers/expected_answer_trace.jsonl`
- `ai/eval/expected_answers/expected_summary.md`
- `ai/eval/scripts/phase1_compute_expected.py`

标准答案分布：

- expected：347
- unsupported：878
- blocked：160
- no_answer：6
- 合计：1391

Hermes 审查修正：

1. 修复 expected 与 trace 缺少 `trace_id` 的问题；
2. 修正 BOM “现有订单”缺少订单/型号范围时不应直接全量计算的问题；
3. 修正 BOM 对比题没有两个不同订单/版本时应追问的问题；
4. 修正 BOM 尾号命中多个实例时应消歧的问题。

抽样复核结果：

```json
{
  "Q0013": 13877138,
  "Q0020": 10048299.56,
  "Q0028": 20717,
  "Q0038": 2811,
  "Q0049": 21.0949
}
```

## 3. 浏览器 E2E 与 expected/actual 对比

脚本：

- `ai/eval/scripts/phase2_browser_e2e.py`
- `ai/eval/scripts/phase3_compare_answers.py`

浏览器证据：

- `ai/eval/runs/run_20260507_001940/actual_answers.jsonl`
- `ai/eval/runs/run_20260507_001940/comparison_result.jsonl`
- `ai/eval/runs/run_20260507_001940/comparison_summary.md`
- `ai/eval/runs/run_20260507_001940/screenshots/`
- `ai/eval/runs/run_20260507_001940/page_html/`
- `ai/eval/runs/run_20260507_001940/service_logs/`

最新前 20 题浏览器对比结果：

- actual：20 success
- comparison：20 PASS
- FAIL：0
- MISSING_ACTUAL：0

## 4. 定向修复清单

本轮针对 E2E / 鲁棒性发现的问题做了通用链路修复，不按完整问题硬编码。

### 4.1 跨年省份总费用只取末尾年份

问题：

- `2023到2025年江苏的物流总运费是多少？` 原先只返回 2025 年。

修复：

- `data_qa_planner.py`：跨年省份总费用保留 `years=[2023,2024,2025]`；
- `data_qa_service.py`：向 repository 传递 `years`；
- `data_qa_repository.py`：`hist_total_fee_by_province` 支持 `years` 白名单过滤。

验证结果：

- 页面返回：`2023-2025年江苏省总费用为10,048,300元。`

### 4.2 季度车辆数/车次口径错误

问题：

- `24年一季度物流发运车辆数是多少？` 原先页面可答但车次为 0。

修复：

- `TRIP_KEYWORDS` 增加 `车辆数`；
- planner 将季度转换为月份 `[1,2,3]`；
- repository 的通用汇总返回 `shipment_trip_count`；
- service 在 `shipment_trip_count` 指标下输出车次。

验证结果：

- 页面返回：`2024年1月2月3月承运车次为2,811车次。`

### 4.3 “多少件”自然问法无法识别

问题：

- `华东区域历史物流一共发运了多少件？` 原先可能追问或脚本首题失败。

修复：

- planner 支持 `多少件` → `hist_quantity_by_region`。

验证结果：

- 页面返回：`华东区域总发运件数为13,877,138件。`

### 4.4 “平均元每瓦”表达不进入已支持 query

问题：

- `请把华东各运输方式平均元每瓦按从低到高列出来` 原先追问。

修复：

- planner 支持 `平均元每瓦` / `元每瓦`；
- repository 将平均元/瓦口径修正为 `SUM(total_fee) / SUM(actual_watt)` 加权口径；
- service 的 calculation_logic 同步修正。

验证结果：

- 页面表格返回 `0.008648`。

### 4.5 “客户按总费用排前五”表达不进入已支持 query

问题：

- `江苏省客户按总费用排前五，并列出总费用和总瓦数` 原先追问。

修复：

- planner 支持 `客户按总费用排前五/前5` 等表达；
- 复用 `hist_top_customers_fee_and_mw_by_province`。

验证结果：

- 页面返回江苏历史累计前 5 客户及总费用/发运量。

### 4.6 浏览器首题输入框等待不稳

问题：

- 鲁棒性脚本偶发 `未找到问题输入框`。

修复：

- `phase2_browser_e2e.py` 对候选输入框增加 `wait_for(state="visible")`，提升首屏/路由异步加载稳定性。

## 5. 鲁棒性验证

脚本：

- `ai/eval/scripts/phase5_robustness.py`

用例数：8

结果：

- success：8
- robustness_passed：8
- error：0
- clarification：0

覆盖用例：

1. `华东区域历史物流一共发运了多少件？`
2. `2023到2025年江苏的物流总运费是多少？`
3. `浙江历史发运总费用是多少元？`
4. `历史台账里运输方式为公路的记录有多少条？`
5. `24年一季度物流发运车辆数是多少？`
6. `请把华东各运输方式平均元每瓦按从低到高列出来`
7. `江苏省客户按总费用排前五，并列出总费用和总瓦数`
8. `2023–2025 年各月物流总费用是多少？`

## 6. 回归测试与构建

已执行：

```bash
PYTHONPATH=. python -m pytest tests/business_acceptance/test_logistics_e2e_robustness_fixes.py -q
# 4 passed

python -m compileall -q backend ai/eval/scripts tests/business_acceptance/test_logistics_e2e_robustness_fixes.py
# passed

git diff --check
# passed

python ai/eval/scripts/phase5_robustness.py --run-id run_20260507_001940
# 8 success / 8 robustness_passed

python ai/eval/scripts/phase2_browser_e2e.py --run-id run_20260507_001940 --limit 20
python ai/eval/scripts/phase3_compare_answers.py --run-id run_20260507_001940
# 20 PASS

cd frontend && npm run build
# passed，存在 Vite chunk size warning，不是失败
```

独立 review：

- 首轮 review 发现 `平均元/瓦` 计算口径说明与 SQL 不一致；
- 已修复并补充测试；
- 复审结果：passed true，无阻塞问题。

## 7. 本轮主要修改文件

业务修复：

- `backend/app/domains/logistics/repositories/data_qa_repository.py`
- `backend/app/domains/logistics/services/data_qa_planner.py`
- `backend/app/domains/logistics/services/data_qa_service.py`

E2E 验收脚本：

- `ai/eval/scripts/phase0_prepare_assets.py`
- `ai/eval/scripts/phase1_compute_expected.py`
- `ai/eval/scripts/phase2_browser_e2e.py`
- `ai/eval/scripts/phase3_compare_answers.py`
- `ai/eval/scripts/phase5_robustness.py`

测试：

- `tests/business_acceptance/test_logistics_e2e_robustness_fixes.py`

产物：

- `ai/eval/**`

## 8. 风险与边界

1. 当前完整浏览器批量验证实际执行范围是前 20 题 + 8 条鲁棒性变体；1391 题标准答案已生成，但未逐题完整浏览器跑完。
2. 2026 MySQL 相关题仍按能力/连接情况标记 blocked，不编造答案。
3. 当前工作区存在大量既有未提交改动，本轮 E2E 产物集中在 `ai/eval/**`，业务修复集中在物流 data-qa 链路。
4. Vite 构建存在 chunk size warning，不影响构建通过，但后续可做前端分包优化。
5. 未做 commit/push/deploy，合并和上线仍需人工确认。

## 9. 最终结论

本轮 E2E 自动验收推进完成：

- 数据资产解析完成；
- 标准答案与 trace 已生成并经 Hermes 审查；
- 浏览器 E2E 脚本和对比脚本已建立；
- 前 20 题浏览器 expected/actual 对比 20/20 PASS；
- 8 条高风险鲁棒性变体 8/8 PASS；
- 定向修复已完成并通过测试、构建和独立复审；
- 未 commit、未 push、未 deploy。

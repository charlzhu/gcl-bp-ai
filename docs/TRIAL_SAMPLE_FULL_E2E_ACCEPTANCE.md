# TRIAL_SAMPLE_FULL_E2E_ACCEPTANCE

## 当前结论
- 本轮不是抽样测试，也不是接口自测，已完成全量真实网页 E2E。
- 样例题总数：1391
- 变体总数：1890
- 总计划网页 E2E：3281
- 当前累计真实网页执行：3281
- 当前未执行：0
- 前端执行：`3281/3281 pass`
- 自动比对：`3281 PASS / 0 FAIL`
- 当前失败/待修复：`0`
- B 类正确追问：`1429/1429`
- C 类正确拒答解释：`93/93`
- 停止条件：`all_cases_completed`。
- 失败清单：`tmp/trial_sample_eval/failed_cases.json`，当前为空。
- 标准答案口径：物流以 `logistics_ai` 中间库为准；源 zip 只做源文件核验和差异说明，BOM 使用真实标准化 BOM 数据。
- 执行原则：真实 `/smart-chat` 前端页面输入、DOM 抓取前端展示答案；未使用 mock，未 hardcode 样例答案，未绕过真实业务主链路。

## 历史执行过程
- 历史过程曾从 679 条 checkpoint 续跑，新增执行 2602 条后达到全量完成。该信息仅说明执行过程，非当前状态。

## 本轮修复闭环
- 新增循环批量 runner，避免每轮只跑一个小批次。
- 修复 E2E `--only-failed` 空失败集保护，避免误覆盖 checkpoint。
- 补齐物流标准答案构建层的复杂报表、备注关键词、额外费用、非稳定业务口径 B/C 边界。
- 补齐物流 slot/planner/repository/service 的同类问题泛化处理。
- 补齐物流 NLU Center 诊断候选，恢复 903 语义基线；正式 A/B/C 执行边界不变。

## 基础回归
- Python 编译检查：通过。
- 前端 build：通过。
- 物流 NLU Center dry-run：`122/122`。
- 物流 903 语义回归：`1559/1559`。
- BOM QA API E2E：`30/30`。
- BOM 多问法语义回归：`129/129`。
- 物流 Guardrail bounded check：`10/10`。
- 发布前 readiness check：通过。

## Checkpoint
- 前端结果：`tmp/trial_sample_eval/frontend_e2e_results.json`
- 比对报告：`tmp/trial_sample_eval/answer_compare_report.json`
- 失败清单：`tmp/trial_sample_eval/failed_cases.json`
- 修复清单：`tmp/trial_sample_eval/fixed_cases.json`

## 未来复测命令
以下命令仅用于未来复测，不代表当前仍有未完成事项。

```bash
backend/.venv/bin/python scripts/trial_sample_e2e_batch_runner.py --resume --include-variants --batch-size 50 --time-budget-minutes 55
```

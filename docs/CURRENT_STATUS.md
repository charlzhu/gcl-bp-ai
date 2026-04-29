# CURRENT_STATUS.md

## 当前阶段：全量样例题真实网页 E2E 已完成

当前不是继续物流后端收口，不是 BOM Wave3，不迁 A，不扩业务能力，不做 mock demo。全量样例题真实网页 E2E 已完成，当前不再有待续跑 E2E 队列。

### 本轮样例题验收输入

- 正式样例题：`物流和 bom样例题.docx`
- 已解析有效编号问题：`1391`
- 脚本分类：`plan_bom=13 / logistics=1374 / unknown=4`
- 原题变体：`1890`
- 网页 E2E 全量计划用例：`3281`（1391 原题 + 1890 变体）
- 物流标准答案口径：以 `logistics_ai` 中间库表时间和数据为准。
- 物流源数据：`23 年至 25 年物流台账数据.zip`、`物流 26 年源数据.zip`。
- 源 zip 只做源文件核验和差异说明，不覆盖 `logistics_ai` 口径；运行环境本地路径已脱敏。

### 真实网页 E2E 最终结果

- 真实网页入口：`/smart-chat`
- 执行方式：Playwright 打开真实前端页面，输入问题，从 DOM 抓取最终展示答案。
- 当前执行状态：`completed`
- 停止条件：`all_cases_completed`
- 计划执行：`3281`
- 已执行真实网页 E2E：`3281`
- 待执行：`0`
- 前端执行状态：`pass=3281`
- 自动比对结果：`PASS=3281 / FAIL=0`
- B 类正确追问：`1429/1429`
- C 类正确拒答解释：`93/93`
- `failed_cases.json`：空列表。

### 历史执行过程

- 历史过程曾从 679 条 checkpoint 继续执行，后续新增执行 2602 条，最终达到 `3281/3281`。该信息仅用于说明执行过程，不代表当前仍有未完成队列。

### 本轮新增修复和复核

1. 增加 `scripts/trial_sample_e2e_batch_runner.py` 循环批量执行能力，避免每轮只跑一个 50 条小批次。
2. 修复 `scripts/trial_sample_frontend_e2e_eval.py` 的 `--only-failed` 空失败集保护，避免误覆盖全量 checkpoint。
3. 修复/补齐 `scripts/trial_sample_answer_comparator.py` 对恢复型 checkpoint 的比对兼容。
4. 补齐 `scripts/trial_sample_expected_answer_builder.py` 的复杂物流题 B/C 边界、额外费用、备注关键词、月度/季度/矩阵/宽表/报表类标准答案口径。
5. 修复物流 slot 清洗，避免“累计、各按”等口语连接词误抽成客户/承运商过滤条件。
6. 补齐物流 planner/repository/service 中历史始发地 + 车型费用汇总等同类题泛化处理。
7. 补齐物流 NLU Center 诊断候选：历史场景总运费和 2026 特殊业务带月份过滤问题均可恢复既有 903 语义基线；正式查询执行边界未改变。

### 当前报告

- 台账：`tmp/trial_sample_eval/sample_question_ledger.json`
- 标准答案：`tmp/trial_sample_eval/expected_answers.json`
- 前端 E2E：`tmp/trial_sample_eval/frontend_e2e_results.json`
- 比对报告：`tmp/trial_sample_eval/answer_compare_report.json`
- 总报告：`tmp/trial_sample_eval/trial_sample_full_e2e_acceptance_report.json`
- 失败题：`tmp/trial_sample_eval/failed_cases.json`
- 修复记录：`tmp/trial_sample_eval/fixed_cases.json`
- 批量执行报告：`tmp/trial_sample_eval/trial_sample_e2e_batch_runner_report.json`

### 物流当前状态

- 当前分布：`A=656 / B=178 / C=69 / D=0`
- 真实业务链路保持不变。
- 未修改物流 A/B/C 边界。
- 物流 NLU Center dry-run：`122/122`。
- 物流 903 语义回归：`1559/1559`。
- 物流 Guardrail bounded check：`10/10`，B/C 误判 success 为 `0`。

### 计划 BOM 当前状态

- 当前分布：`A=86 / B=40 / C=3 / D=0`
- 正式问题来源：`BOM问题.xlsx`
- 有效问题：`129`
- BOM 源数据：`34` 个 Excel，`4034` 条材料行
- 上传接口：`POST /api/v1/plan-bom/upload`
- 问答接口：`POST /api/v1/plan-bom/qa/ask`
- BOM QA API E2E：`30/30`
- BOM 多问法语义回归：`129/129`
- 未修改 BOM A/B/C 边界。

### 已执行检查

- Python 编译检查：通过。
- 真实网页 E2E 长跑：`3281/3281` 完成。
- 自动比对：`3281/3281` 通过。
- B 类正确追问：`1429/1429`。
- C 类正确拒答解释：`93/93`。
- 前端 build：通过，仅 Vite chunk size warning。
- BOM QA API E2E：`30/30` 通过。
- BOM 多问法语义回归：`129/129` 通过。
- 物流 NLU Center dry-run：`122/122` 通过。
- 物流 903 语义回归：`1559/1559` 通过。
- 物流 Guardrail bounded check：`10/10` 通过，B/C 误判 success 为 `0`。
- 发布前 readiness check：通过。

### 当前边界

- 没有 mock 数据。
- 没有 hardcode 样例题答案。
- 没有绕过真实前端页面。
- 没有绕过真实业务主链路。
- 没有修改物流/BOM 业务边界。
- 当前下一步已切换为领导演示、小范围业务试运行和真实反馈闭环，不继续硬迁 A，不扩 query_key，不再把 E2E 未完成当成当前状态。

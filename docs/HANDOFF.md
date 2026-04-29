# HANDOFF.md

## 交接结论：全量样例题真实网页 E2E 已完成

当前接手者无需继续续跑 E2E。本轮已经完成 `1391` 条原题 + `1890` 条变体，共 `3281` 条真实网页 E2E，自动比对 `3281/3281` 通过。当前下一步已切换为领导演示、小范围业务试运行和真实反馈闭环。

### 真实网页入口

- 首页：`/smart-chat`
- 智能问答：`/smart-chat`
- BOM 数据管理：`/bom-data`
- 试运行说明：`/trial-guide`

### 样例题验收资产

- 样例题台账脚本：`scripts/trial_sample_question_ledger.py`
- 标准答案脚本：`scripts/trial_sample_expected_answer_builder.py`
- 真实网页 E2E 脚本：`scripts/trial_sample_frontend_e2e_eval.py`
- 循环批量 runner：`scripts/trial_sample_e2e_batch_runner.py`
- 答案比对脚本：`scripts/trial_sample_answer_comparator.py`
- 总编排脚本：`scripts/trial_sample_full_e2e_acceptance.py`

### 当前验收结果

- 样例题：`1391` 条。
- 变体：`1890` 条。
- 网页 E2E 全量计划用例：`3281` 条。
- 已执行真实网页 E2E：`3281` 条。
- 待执行：`0` 条。
- 前端执行状态：`pass=3281`。
- 自动比对：`PASS=3281 / FAIL=0`。
- B 类正确追问：`1429/1429`。
- C 类正确拒答解释：`93/93`。
- 停止条件：`all_cases_completed`。
- `failed_cases.json` 当前为空。

### 已完成修复

1. `scripts/trial_sample_eval_common.py`：修复 BOM 线盒/接线盒变体生成，避免“接接线盒”。
2. `frontend/src/views/business-chat/BusinessChatPage.vue`：修复自动识别，物流历史发运/规格、运价、报价、发货类问题优先走物流。
3. `backend/app/domains/logistics/services/slot_extractor.py`：补齐全国省份别名，并增强“总运输费用/运量/累计/各按”等口语清洗。
4. `backend/app/domains/logistics/services/data_qa_planner.py`：补齐运量、运输费用、运价/报价等同义表达、复杂报表 B/C 边界和历史始发地车型汇总。
5. `backend/app/domains/logistics/repositories/data_qa_repository.py`：历史区域发运件数支持按年份过滤，并补齐历史始发地车型汇总查询。
6. `backend/app/domains/logistics/services/data_qa_service.py`：补齐历史始发地车型汇总服务分支，并在相关摘要中展示年份/口径。
7. `scripts/trial_sample_expected_answer_builder.py`：补齐线路运价、2026 客户/承运商/基地/特殊用车、系统 MW、项目名称、额外费用、备注关键词、宽表/矩阵/报表类 B/C 口径。
8. `scripts/trial_sample_frontend_e2e_eval.py`：增加逐题 checkpoint、服务日志、`--only-failed`、全量计划数统计，并修正 `--max-cases` 与空失败集保护。
9. `scripts/trial_sample_answer_comparator.py`：兼容恢复型 checkpoint 行，避免历史修复数据影响全量比对。
10. `scripts/trial_sample_e2e_batch_runner.py`：新增循环批量执行，自动跑前端 E2E + comparator 并记录可恢复状态。
11. `backend/app/domains/logistics/services/nlu_center_service.py`：补齐既有 903 A 基线的 NLU 诊断候选，不改变正式查询边界。

### 数据口径

- 物流标准答案以 `logistics_ai` 中间库为准。
- 物流源数据为 `23 年至 25 年物流台账数据.zip`、`物流 26 年源数据.zip`，只用于源文件核验和差异说明。
- BOM 标准答案来自真实 BOM 标准化材料数据。

### 边界

- 未修改物流 A/B/C 边界：`A=656 / B=178 / C=69 / D=0`
- 未修改 BOM A/B/C 边界：`A=86 / B=40 / C=3 / D=0`
- 未使用 mock 数据。
- 未 hardcode 样例题答案。
- 未绕过真实前端页面。
- 未绕过真实业务主链路。
- 不要继续硬迁 A，不要扩 query_key，不要再把 E2E 未完成当成当前状态。

### 已执行检查

- Python 编译检查：通过。
- 真实网页 E2E：`3281/3281`。
- 自动比对：`3281/3281`。
- 前端 build：通过。
- BOM QA API E2E：`30/30` 通过。
- BOM 多问法语义回归：`129/129` 通过。
- 物流 NLU Center dry-run：`122/122` 通过。
- 物流 903 语义回归：`1559/1559` 通过。
- 物流 Guardrail bounded check：`10/10` 通过。
- 发布前 readiness check：通过。

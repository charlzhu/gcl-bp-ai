# 物流 903 试运行交付清单

## 一、当前交付状态

当前物流 903 问答系统已进入试运行交付准备完成阶段。

当前总账：

- `A = 656`：可以直接回答。
- `B = 178`：需要追问、补槽、业务确认或数据口径确认。
- `C = 69`：不能回答，但可以解释原因和改问方向。
- `D = 0`。

## 二、系统能力清单

已具备：

- 自然语言物流问题输入。
- A 类问题受控查询回答。
- B 类问题业务化追问。
- B 类补槽后继续回答闭环。
- C 类拒答解释。
- 空结果解释。
- 查询结果表格展示。
- 查询计划、数据范围和计算说明展示。
- 查询历史回看。
- Excel / CSV 导出。
- Guardrail 保护 B/C 边界。
- NLU Center dry-run / diagnostic 评测。

## 三、文档清单

可交付文档：

- `docs/LOGISTICS_903_LEADER_BRIEFING.md`
- `docs/LOGISTICS_903_TRIAL_RUN_PLAN.md`
- `docs/LOGISTICS_903_DEMO_SCRIPT.md`
- `docs/LOGISTICS_903_TRIAL_FEEDBACK_TEMPLATE.md`
- `docs/LOGISTICS_903_DELIVERY_CHECKLIST.md`
- `docs/LOGISTICS_903_ACCEPTANCE_REPORT.md`
- `docs/LOGISTICS_903_USER_ACCEPTANCE_SAMPLES.md`
- `docs/LOGISTICS_DATA_QA_FRONTEND_ACCEPTANCE_CHECK.md`
- `docs/LOGISTICS_903_B_BUSINESS_CONFIRMATION_PACKAGE_V3.md`
- `docs/LOGISTICS_903_C_UNSUPPORTED_DELIVERY_PACKAGE.md`

## 四、脚本清单

可复跑脚本：

- `scripts/logistics_903_acceptance_report.py`
- `scripts/logistics_903_user_acceptance_samples.py`
- `scripts/logistics_data_qa_frontend_acceptance_check.py`
- `scripts/logistics_903_a_precise_acceptance_batch4.py`
- `scripts/logistics_903_b_c_delivery_packages.py`
- `scripts/logistics_903_master_ledger.py`
- `scripts/logistics_903_semantic_closure_eval.py`
- `scripts/logistics_nlu_center_eval.py`
- `scripts/logistics_llm_guardrail_rollout.py`

## 五、报告清单

关键 JSON 报告：

- `tmp/logistics_question_bank/logistics_903_acceptance_report.json`
- `tmp/logistics_question_bank/logistics_903_user_acceptance_samples_report.json`
- `tmp/logistics_question_bank/logistics_data_qa_frontend_acceptance_check_report.json`
- `tmp/logistics_question_bank/logistics_903_a_precise_acceptance_batch4_regression_report.json`
- `tmp/logistics_question_bank/logistics_903_b_business_confirmation_package_v3.json`
- `tmp/logistics_question_bank/logistics_903_c_unsupported_delivery_package.json`
- `tmp/logistics_question_bank/logistics_903_master_ledger_report.json`
- `tmp/logistics_question_bank/logistics_903_semantic_closure_full_report.json`

## 六、前端能力清单

物流 data-qa 页面已具备：

- 成功态展示。
- 追问态展示。
- 拒答态原因展示。
- 可改问方向展示。
- 空结果态展示。
- 错误态友好提示。
- 加载态展示。
- 边界输入态提示。
- 会话流追加提问。
- 历史结果回看。
- Excel / CSV 导出。

前后端联调检查：`9/9`。

## 七、回归测试清单

已通过：

- 关键 A 精确断言：`20/20`
- A 类行为回归：`75/75`
- Round4 / Round5 新进 A 精确断言：`5/5`
- B2A-P1/P2/P3 精确断言：`85/85`
- B-gap Wave1 / Wave2 / Wave3 / Wave4：`184/184 / 61/61 / 24/24 / 4/4`
- Wave3 / Wave4 / Wave5 / Batch4 A 精确断言：`30/30 / 30/30 / 40/40 / 50/50`
- NLU Center dry-run：`122/122`
- 903 全量真实问法语义回归：`1559/1559`
- 真实用户验收样例集：`85/85`
- C 类拒答解释：`69/69`
- Guardrail 未越权改写 B/C。
- 前端构建通过。

## 八、当前不能承诺的内容

不能承诺：

- 超出 A 类边界的问题可以直接回答。
- 预测未来费用、趋势或波动区间。
- ETA 或预计到达时间。
- 未定义异常、风险、最差、达标、效率等主观判断。
- 没有数据字段支撑的问题。
- LLM 直接查数、生成 SQL 或替代 planner。
- B/C 问题未经确认直接迁 A。

## 九、试运行期间需要业务配合的内容

需要业务配合：

- 用真实问法提问，不需要照题库原题。
- 对不满意问题填写反馈表。
- 对异常、风险、最差、达标等口径给出定义。
- 对数据字段缺口确认是否能补数据。
- 对高频问题确认优先级。
- 每周参与反馈复盘。

试运行阶段的交付口径：

> 该答的答准，不清楚的追问，不能答的解释原因。

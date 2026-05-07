# NLU Center Candidate Assist 小流量准入评估

## 一、结论

- 是否可进入 shadow candidate assist 评估：`True`
- 是否可直接打开会改写正式结果的 assist：`False`
- 当前建议：首轮 live shadow 基线已通过；建议扩大 shadow 样本，暂不建议打开会改写正式结果的 assist。

关键判断：当前首轮 **live shadow 评估** 已通过，但不建议直接开启正式 `assist` 改写结果。
原因是最新基础回归均通过，首轮 live LLM A/B/C 抽样基线也已建立；但样本量仍偏小，且正式环境仍需显式配置 pilot 白名单。

首轮 live shadow 观察：

- 抽样总数：`15`
- 通过结果：`15/15`
- live LLM 调用：`15`
- A 类 LLM 候选 query_key 命中：`5`
- B 类保持澄清边界：`5/5`
- C 类 policy locked：`5/5`
- Guardrail assist 实际采用：`0`

## 二、推荐试点配置

- `LLM_GUARDRAIL_ENABLED`：`True`
- `LLM_GUARDRAIL_MODE`：`shadow`
- `LLM_GUARDRAIL_SAMPLE_RATE`：`0.05`
- `LLM_GUARDRAIL_MIN_CONFIDENCE`：`0.95`
- `LLM_GUARDRAIL_A_QUERYKEY_WHITELIST`：`sys_mw_and_trip_count,hist_avg_fee_by_month,hist_total_fee_by_origin_and_carrier,hist_trip_count_by_region,hist_customer_mw`
- `LLM_GUARDRAIL_AUDIT_ENABLED`：`True`

推荐 pilot query_key：

- `sys_mw_and_trip_count`
- `hist_avg_fee_by_month`
- `hist_total_fee_by_origin_and_carrier`
- `hist_trip_count_by_region`
- `hist_customer_mw`

## 三、准入门禁

| 门禁 | 状态 | 证据 | 后续动作 |
| --- | --- | --- | --- |
| `global_default_off` | `pass` | enabled=False, mode=off, sample_rate=0.0 | 正式开启前必须保持默认 off，仅通过环境变量在目标环境小流量开启。 |
| `llm_runtime_config_available` | `pass` | LLM_BASE_URL=True, LLM_MODEL=True, LLM_API_KEY=True | 如果不可用，先补齐 LLM 配置；不得伪造 live LLM 结果。 |
| `latest_nlu_diagnostic_passed` | `pass` | total=122, false_success=0, bc_override=0, live=False | 继续保持 dry-run / diagnostic 作为基础回归。 |
| `live_llm_shadow_baseline_established` | `pass` | shadow_passed=True, total=15, live_invoked=15, assist_applied=0 | 正式 assist 前必须保留 live shadow 基线，并确认 shadow 不改写正式结果。 |
| `live_llm_shadow_sample_size_for_canary` | `warn` | shadow_total=15, recommended_minimum=50 | 进入 1% 以下 assist canary 前，建议先把 live shadow 样本扩大到至少 50 条。 |
| `explicit_pilot_whitelist` | `warn` | configured=[], effective_default_size=15 | 小流量 assist 前必须显式配置 3-5 个 pilot query_key，不建议直接使用内建 15 个默认白名单全量试点。 |
| `guardrail_mechanics_passed` | `pass` | {"off_keeps_rule": true, "shadow_recommends_without_apply": true, "assist_can_apply_when_all_conditions_met": true, "b_policy_locked": true, "c_policy_locked": true, "low_confidence_blocked": true, "multi_candidate_blocked": true, "non_live_blocked": true, "assist_plan_can_rebuild": true} | 任何机械门禁失败时不得进入 candidate assist。 |
| `a_regression_not_regressed` | `pass` | 20=20/20, 75=75/75, 5=5/5 | A 类任一回归失败时不得进入 assist。 |
| `c2a_baseline_not_regressed` | `pass` | P1=30/30, P2=30/30, P3=28/30, P4=37/37 | C2A 基线失败时先修复迁移基线，不得扩大 assist。 |
| `bcr_boundary_not_regressed` | `pass` | BCR1=60/60, BCR2=80/80, BCR3=80/80, BCR4=70/70 | BCR 任一失败或模板建议不为 0 时不得进入 assist。 |
| `audit_available` | `pass` | audit_enabled=True, path=data/logs/logistics_llm_guardrail_audit.jsonl | 小流量必须开启 JSONL 审计，并保留 query_log guardrail 快照。 |

## 四、Guardrail 机械验证

- `off_keeps_rule`：`True`
- `shadow_recommends_without_apply`：`True`
- `assist_can_apply_when_all_conditions_met`：`True`
- `b_policy_locked`：`True`
- `c_policy_locked`：`True`
- `low_confidence_blocked`：`True`
- `multi_candidate_blocked`：`True`
- `non_live_blocked`：`True`
- `assist_plan_can_rebuild`：`True`

## 五、不回退基线

- 关键题精确断言：`20/20`
- A 类行为回归：`75/75`
- Round4 / Round5 新进 A：`5/5`
- C2A：P1 `30/30`，P2 `30/30`，P3 保持既有真实结论 `28/30`，P4 `37/37`
- BCR：BCR1 `60/60`，BCR2 `80/80`，BCR3 `80/80`，BCR4 `70/70`，模板优化建议均为 `0`
- NLU dry-run / diagnostic：`122/122`，B/C Guardrail 改写 `0`

## 六、边界

- 不得让 NLU Center 替代正式 planner。
- 不得让 LLM 生成 SQL 或直接查数。
- 不得让 LLM 改写 B/C 边界。
- 不得在未显式配置 pilot 白名单时使用内建默认白名单直接小流量 assist。

## 七、下一步

- 继续扩大 live shadow candidate assist 观察样本，不改变正式结果。
- 重点观察 A 类候选命中率、B/C 误改写、延迟和审计完整性。
- 只有更大 live 抽样连续通过且显式 pilot 白名单配置到位后，再讨论 1% 以下 assist canary。

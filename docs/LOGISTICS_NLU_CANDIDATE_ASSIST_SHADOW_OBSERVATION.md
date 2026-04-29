# NLU Center Candidate Assist Shadow 观察报告

## 一、结论

- Shadow 观察是否通过：`True`
- 是否建议直接进入 assist canary：`False`
- 当前建议：shadow 观察通过；仍建议继续扩大 live LLM 抽样样本后，再评估 1% 以下 assist canary。

本轮真实调用 LLM，但 Guardrail 运行在 `shadow` 模式，未改写正式 planner 结果。

## 二、样本与配置

- 样本总数：`15`
- 样本分布：`{"A": 5, "B": 5, "C": 5}`
- 通过样本：`15`
- 失败样本：`0`
- live LLM 调用数：`15`
- provider 分布：`{"live": 15}`
- 平均延迟：`5015.73 ms`
- 最大延迟：`7838 ms`
- 审计日志行数：`15`

Pilot query_key 白名单：

- `sys_mw_and_trip_count`
- `hist_avg_fee_by_month`
- `hist_total_fee_by_origin_and_carrier`
- `hist_trip_count_by_region`
- `hist_customer_mw`

## 三、关键指标

- A 类 LLM query_key 命中：`5/5`
- A 类规则 query_key 命中：`0/5`
- A 类 Guardrail 推荐：`5`
- B 类 policy_locked：`4/5`
- C 类 policy_locked：`5/5`
- shadow 模式 assist_applied：`0`

## 四、失败样本

- 当前无失败样本。

## 五、边界

- 本轮不改变正式 planner 结果。
- LLM 不查数、不生成 SQL、不改写 B/C 边界。
- B/C 仍由 response policy 与 Guardrail 锁定。
- 是否进入正式 assist canary，必须另行基于更大 live 样本判断。

# 物流域 LLM Guardrail 受控接入方案

## 结论

- Guardrail 已正式受控接入 `data-qa` 主链路，但默认仍可关闭、可回退。
- 正式 planner 仍是主链路裁决者，LLM 只允许增强 A 类白名单同构变体。
- B/C 边界继续由规则层锁定，不允许被 LLM 改写。

## 接入点

当前正式接入点位于 `LogisticsDataQaService.query`：
1. 先执行规则 planner，得到 `rule_plan`；
2. 若规则层已命中正式 query_key，则直接执行；
3. 若命中 B/C 正式策略，则直接锁定；
4. 只有规则层落入通用兜底澄清时，才允许 Guardrail 评估 LLM 候选；
5. assist 模式下若满足白名单、高置信、单候选，才回构正式 plan；
6. 回构失败立即回退到纯规则结果。

## 开关与模式

- `LLM_GUARDRAIL_ENABLED`：False
- `LLM_GUARDRAIL_MODE`：off
- `LLM_GUARDRAIL_SAMPLE_RATE`：0.0
- `LLM_GUARDRAIL_MIN_CONFIDENCE`：0.9
- `LLM_GUARDRAIL_A_QUERYKEY_WHITELIST`：hist_total_fee_city_rank, hist_avg_fee_by_month, hist_avg_fee_per_watt_by_transport, hist_extra_fee_ratio_peak_month, hist_total_fee_by_origin_and_carrier, sys_mw_and_trip_count, hist_trip_count_by_region, hist_quantity_by_region, hist_customer_mw, hist_vehicle_type_trip_count, sys_signedfor_rate_by_carrier, hist_multi_origin_customers, sys_companies_without_tasks, hist_plan_actual_deviation, sys_special_total_fee
- `LLM_GUARDRAIL_AUDIT_ENABLED`：True

模式说明：
- `off`：完全退回纯规则链路；
- `shadow`：旁路评估和审计，不改动正式结果；
- `assist`：只在 A 类白名单场景受控恢复 query_key。

## 审计记录

- JSONL 审计日志：`data/logs/logistics_llm_guardrail_audit.jsonl`
- 统一查询日志：当前会把 Guardrail 决策快照写入 `sys_query_log.request_payload.response_meta.guardrail`。
- 当前至少记录：原始问题、规则 query_key、是否进入 guardrail、是否调用 LLM、LLM 候选、置信度、最终来源、回退原因。

## 收益与不回退验证

- 20 条关键题精确断言：20/20
- 75 条 A 类行为回归：75/75
- A 类变体 Guardrail 命中：50/54
- B 类 guardrail 误判 success：0
- C 类 guardrail 误判 success：0

## 当前判断

- Guardrail 是否已正式可控接入主链路：True
- 默认关闭时是否完全回到纯规则：True
- assist 是否只增强 A 类白名单：True
- B/C 边界是否未被 LLM 改坏：True
- 是否具备小流量 candidate assist 条件：True
- 是否建议让 LLM 直接替换 planner：False

## 建议

- 当前已经具备小流量 candidate assist 的条件。
- 仍然不建议让 LLM 全面替换正式 planner。
- 下一步应继续保持规则主导，只在 A 类白名单里小流量放行 assist，并持续审计。

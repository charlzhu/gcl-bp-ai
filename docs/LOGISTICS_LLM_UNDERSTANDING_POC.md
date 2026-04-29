# 物流域问法鲁棒性增强：LLM 理解层 PoC

## 1. 目标

本轮 PoC 的目标不是让 LLM 直接查数，而是验证：

- LLM 是否适合作为物流数据问答的“语言理解层”
- 是否能更稳定完成同义问法理解、术语归一、槽位抽取和 query_key 候选生成
- 是否能辅助判断“应澄清”还是“应不支持”

当前必须保持：

- 最终计算与查询仍由现有 `data-qa` 主链路完成
- 现有 `20` 条关键题精确断言回归不能回退
- 现有 `75` 条 A 类行为回归不能回退
- 现有 B/C 响应策略不能回退

## 2. 接入方式

当前 PoC 使用 **Shadow Mode + Guardrail Candidate Assist**：

1. 规则 planner / data-qa 主链路正常执行
2. LLM 理解层并行运行
3. Guardrail 层只在以下条件同时满足时，才允许把 LLM 当成 A 类候选增强：
   - 规则层没有命中正式 query_key
   - 规则层只是落到“通用兜底澄清”
   - 当前问题未命中 B/C 正式策略
   - LLM 返回单一白名单 query_key
   - LLM 置信度达到 guardrail 阈值
4. 继续比较：
   - 当前规则链路命中了什么
   - LLM 给出了什么候选理解结果
   - guardrail 最终是否允许候选增强
   - A 类是否减少误澄清
   - B/C 是否继续由规则层锁定

LLM 不参与：

- SQL 生成
- 数据库查询
- 结果计算
- 最终业务裁决

当前 guardrail 已补齐正式配置开关，且默认保持**关闭正式接管**：

- `LLM_GUARDRAIL_ENABLED`
- `LLM_GUARDRAIL_MODE`
  - `disabled`
  - `shadow`
  - `assist`
- `LLM_GUARDRAIL_SAMPLE_RATE`
- `LLM_GUARDRAIL_MIN_CONFIDENCE`
- `LLM_GUARDRAIL_AUDIT_ENABLED`

当前审计日志落点：

- `data/logs/logistics_llm_guardrail_audit.jsonl`

说明：

1. 正式 planner 仍由规则层主导；
2. guardrail 当前只为未来小流量 candidate assist 预留开关；
3. 即使打开 assist，也只允许增强 A 类同构变体问法，不允许改写 B/C 边界。

## 3. 样本集范围

PoC 样本集配置：

- `backend/app/domains/logistics/config/llm_understanding_poc_questions.json`

当前规模：

- A 类关键题：`10` 个题型
- A 类变体题：`50` 条
- B 类高频澄清题：`8` 条
- C 类不支持题：`6` 条

## 4. LLM 输出结构

当前理解层输出结构见：

- `backend/app/domains/logistics/schemas/llm_understanding.py`

核心字段包括：

- `normalized_question`
- `intent`
- `metrics`
- `dimensions`
- `filters`
- `time_range`
- `source_scope`
- `candidate_query_keys`
- `normalized_terms`
- `needs_clarification`
- `clarification_questions`
- `unsupported_reason`
- `confidence`
- `provider_mode`
- `provider_error`

Guardrail 决策结构还新增了：

- `guardrail_enabled`
- `guardrail_mode`
- `sampled_in`
- `policy_locked`
- `policy_decision_type`
- `assist_applied`
- `final_source`
- `blocked_reason`

## 5. 当前判断标准

### A 类变体题

重点看：

- `rule_query_key_hit_rate`
- `llm_candidate_hit_rate`
- `rule_llm_same_query_key_rate`
- `llm_helped_recover_query_key_count`
- `llm_wrong_candidate_count`

### B 类澄清题

重点看：

- LLM 是否识别为 `needs_clarification`
- 澄清问题是否更贴近业务表达
- 是否误落成 success

### C 类不支持题

重点看：

- LLM 是否识别为 unsupported
- 不支持原因是否业务可理解
- 是否误落成 success

## 6. 当前边界

即使 PoC 结果较好，也不能直接得出“可生产替换 planner”的结论。

当前更合理的结论只能是：

- LLM 是否**适合辅助理解层**
- 是否更接近“受控正式接入”
- 是否值得在规则 planner 旁路增加**只增强 A 类**的候选理解结果

## 7. 当前实测结果

当前实测报告：

- `tmp/logistics_question_bank/logistics_llm_understanding_poc_report.json`

本轮已真实调用 LLM：

- 模型：`qwen-plus`
- 配置状态：`LLM_BASE_URL / LLM_API_KEY / LLM_MODEL` 均已配置
- 调用结果：`64` 次 live，`0` 次 provider error

### 7.1 A 类变体题

- 变体总数：`50`
- 当前规则链路 query_key 命中：`7/50`
- LLM 候选 query_key 命中：`50/50`
- Guardrail 最终 query_key 命中：`50/50`
- Guardrail 帮助从规则误澄清中恢复 query_key：`43` 条
- LLM 错误 query_key 候选：`0`
- Guardrail 错误 query_key 候选：`0`

结论：

- 对 A 类真实变体问法，LLM 理解层对 query_key 候选生成有明显帮助。
- 扩样到 `50` 条后，这种收益依然成立，不是只在前一轮 `30` 条样本上偶然成立。
- 加上 guardrail 后，可以把这种收益稳定约束在 A 类同构变体里，而不需要放开 B/C 裁决。

### 7.2 B 类澄清题

- 样本数：`8`
- LLM 识别为澄清：`8/8`
- 业务化澄清关键词命中：`8/8`
- 误落成 success：`0`
- Guardrail 最终澄清：`8/8`
- Guardrail 误落成 success：`0`

结论：

- B 类高频模糊题的**原始 LLM 理解**已经明显改善，不再只靠规则硬锁才能压住误判。
- 但当前仍不建议让 LLM 接管 B 类正式裁决；更稳妥的做法仍然是由规则层锁定，LLM 只作为理解参考。

### 7.3 C 类不支持题

- 样本数：`6`
- LLM 识别为 unsupported：`6/6`
- 不支持原因关键词命中：`4/6`
- 误落成 success：`0`
- Guardrail 最终 unsupported：`6/6`
- Guardrail 误落成 success：`0`

结论：

- C 类边界识别整体可用，但不支持理由的业务化表达还不够稳定。
- 通过规则层锁定后，C 类不会被 LLM 误放行。

## 8. 当前建议

当前仍不建议让 LLM 直接替换正式 planner，但已经**更接近可控正式接入**，原因是：

1. A 类变体题收益明显，而且在扩样到 `50` 条后，guardrail 仍可稳定提升到 `50/50`；
2. B 类原始理解已经从前一轮的 `4/8` 提升到 `8/8`，同时 guardrail 继续把 B 类误判稳定压在 `0`；
3. C 类继续 `6/6` 锁定，不会被 LLM 误放行；
4. guardrail 已具备正式开关、抽样比例和审计日志，未来可以做小流量 candidate assist；
3. 但 LLM 自身对 B 类澄清理解仍不稳定，所以当前更合理的是：
   - 保持 shadow / candidate assist 模式
   - 只在 A 类同构变体上做受控增强
   - 不替换正式 planner

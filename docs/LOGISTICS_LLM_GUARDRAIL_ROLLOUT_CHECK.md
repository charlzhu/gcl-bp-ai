# LOGISTICS_LLM_GUARDRAIL_ROLLOUT_CHECK

## 结论

- 检查模式：`fast_boundary_check`
- B/C 边界补验证：`10/10`
- B 类误判 success：`0`
- C 类误判 success：`0`
- case timeout：`20s`

## 挂起诊断

- 原因判断：full rollout 串行执行 A 行为、A 精确、PoC 复算和 off-mode 检查，旧脚本没有进度日志；PoC B/C 默认不复用 replay，当前环境可能长时间等待外部 LLM 或数据链路。
- 本轮处理：保留 full rollout，新增进度日志与 fast boundary check；fast 模式用 B/C 样本和高置信 A 类 LLM 候选做对抗式边界验证。
- 发布门禁：full rollout 仍可复跑，但当前发布前门禁采用 fast boundary check 验证 B/C 不被 LLM 放行为 success。

## 可复跑命令

- full rollout：`PYTHONPATH=. python scripts/logistics_llm_guardrail_rollout.py --progress`
- fast boundary check：`PYTHONPATH=. python scripts/logistics_llm_guardrail_rollout.py --fast-boundary-check --progress`

## 边界验证方式

- 使用 PoC B/C 样本。
- 对每个 B/C 样本构造一个高置信、单 query_key 的 A 类 LLM 候选。
- 断言 Guardrail 最终不能把这些 B/C 问题放行为 success。

## 历史 rollout 报告引用

- latest report：`tmp/logistics_question_bank/logistics_llm_guardrail_rollout_report.json`
- generated_at：`2026-04-27T12:26:46`
- answers：`{'guardrail_formally_integrated': True, 'off_returns_pure_rule': True, 'assist_only_enhances_a_whitelist': True, 'bc_boundary_not_regressed': True, 'candidate_assist_ready': True, 'replace_planner_recommended': False}`

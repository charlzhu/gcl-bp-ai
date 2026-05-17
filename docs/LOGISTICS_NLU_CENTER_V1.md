# 物流域自然语言理解中枢 v1

## 结论

- NLU Center v1 已形成统一 schema、术语归一、规则解析、LLM 候选理解、Guardrail 诊断和多问题拆解 PoC。
- 当前默认是 shadow / diagnostic 模式，不替代正式 `data-qa planner`。
- B/C 边界仍由 `question_bank_response_policy` 和 Guardrail 锁定，LLM 不允许改写最终裁决。

## 评测规模

- 样本总数：122
- 样本分布：{"a_standard": 4, "a_variant": 11, "b_clarification": 7, "c_unsupported": 9, "multi_intent": 5, "short_colloquial": 5, "business_tone": 2, "real_business_tone": 4, "c2a_a_regression": 24, "bcr_clarification": 24, "ledger_c_unsupported": 12, "top200_a": 8, "topn_v2_a": 7}
- 来源分布：{"seed": 47, "c2a_precise_a": 24, "bcr_clarification": 24, "ledger_c_unsupported": 12, "top200_a": 8, "topn_v2_a": 7}
- 是否真实调用 LLM：False

## 指标结果

- intent 命中：120/122，命中率 0.9836
- route 命中：120/122，命中率 0.9836
- query_key 候选命中：121/122，命中率 0.9918
- metric slot 命中：122/122，命中率 1.0
- source_scope 命中：122/122，命中率 1.0
- clarification 识别：121/122，命中率 0.9918
- unsupported 识别：122/122，命中率 1.0
- 多问题识别：122/122，命中率 1.0
- 误落 success：1
- 误落 unsupported：0
- Guardrail 改写 B/C 边界：0

## 当前判断

- 是否适合 shadow / diagnostic：False
- 是否建议替换 planner：False
- 是否真实调用 LLM：False

## 未命中样本

- B_REAL_004：2026年经营计划总发运量是多少？，失败项=['intent_hit', 'route_hit', 'clarification_hit', 'mis_success']，actual_intent=aggregate，actual_route=answerable，query_keys=['sys_mw_and_trip_count']
- TOP200_A_006：2024年江苏省各城市总费用排名前五的是哪些？，失败项=['intent_hit', 'route_hit', 'query_key_candidate_hit']，actual_intent=clarification，actual_route=clarification，query_keys=[]

## 下一步建议

- 继续保持 NLU Center 诊断模式，滚动扩大真实业务问法、极短问法、多问题和边界样本。
- 公共 `slot_extractor` 已抽取；后续优先根据低命中样本补充统一 slot 规则和术语归一配置。
- 只有当多轮 dry-run 与可选 live LLM 抽样都证明 B/C 边界不被破坏后，再评估小流量 candidate assist。

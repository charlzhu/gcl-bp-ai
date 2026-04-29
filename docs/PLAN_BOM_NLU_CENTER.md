# PLAN_BOM_NLU_CENTER

- 评测问题数：`129`
- 正式问题来源：`BOM问题.xlsx`
- live_llm_configured：`True`
- qwen-plus live 调用数：`129`
- live 候选采纳：`126`
- live 候选拒绝：`3`
- 冲突数：`39`
- fallback：`3`
- 拒绝/回退原因分布：`{'order_candidate_failed': 3, 'accepted_safe_candidate': 126, 'rule_llm_conflict': 39, 'material_candidate_failed': 3}`
- 正确保护拒绝：`3`
- 未匹配材料候选观察项：`3`
- 过严拒绝观察项：`0`
- 过宽采纳观察项：`0`
- LLM 候选必须经过 intent 白名单、订单索引和材料类别校验。
- LLM 不能编造订单、材料、版本或规格；不能把 B/C 边界改成 A。

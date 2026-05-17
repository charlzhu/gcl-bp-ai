# PLAN_BOM_NLU_CENTER

- 评测问题数：`129`
- 正式问题来源：`BOM问题.xlsx`
- live_llm_configured：`True`
- deepseek-v4-flash live 调用数：`129`
- live 候选采纳：`0`
- live 候选拒绝：`129`
- 冲突数：`0`
- fallback：`129`
- 拒绝/回退原因分布：`{'llm_call_or_parse_error': 258}`
- 正确保护拒绝：`0`
- 未匹配材料候选观察项：`0`
- 过严拒绝观察项：`0`
- 过宽采纳观察项：`0`
- LLM 候选必须经过 intent 白名单、订单索引和材料类别校验。
- LLM 不能编造订单、材料、版本或规格；不能把 B/C 边界改成 A。

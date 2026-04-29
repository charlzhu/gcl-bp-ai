# Wave3 B 类补槽后续答闭环正式回归

生成时间：2026-04-26T19:33:37

## 一、结论

- 复核总数：`16`
- 补槽后稳定闭环：`3`
- 补槽后仍不宜迁移：`13`
- outcome 分布：`{'generic_or_boundary_followup_not_migratable': 13, 'answerable_after_followup_confirmed': 3}`
- gap 分布：`{'business_definition_gap': 13, 'none': 3}`

## 二、逐题结果

- Q251 | generic_or_boundary_followup_not_migratable | 补槽后虽命中通用汇总 query_key，但原题要求原因/影响/字段一致性或业务建议，不能作为真实可答闭环迁 A。 | 历史台账中“产生原因”高频前三类是什么？按区域看分布有何差异？
- Q260 | generic_or_boundary_followup_not_migratable | 补槽后虽命中通用汇总 query_key，但原题要求原因/影响/字段一致性或业务建议，不能作为真实可答闭环迁 A。 | 哪些记录存在“规格文本中的功率”与功率字段不一致的情况？
- Q273 | answerable_after_followup_confirmed | 用户补充口径后真实链路稳定进入受控 query_key，可作为后续迁移复核输入；原题仍需先澄清。 | 在ENTER或LEAVE状态下，enter_time仍为空的派车任务有多少条？
- Q279 | generic_or_boundary_followup_not_migratable | 补槽后虽命中通用汇总 query_key，但原题要求原因/影响/字段一致性或业务建议，不能作为真实可答闭环迁 A。 | 哪些任务在主任务表已是SIGNEDFOR，但派车解析结果parsed_is_signed=0？应如何判定状态冲突？
- Q298 | generic_or_boundary_followup_not_migratable | 补槽后虽命中通用汇总 query_key，但原题要求原因/影响/字段一致性或业务建议，不能作为真实可答闭环迁 A。 | 哪些仓库绑定的warehouse_user人数最少？是否存在未绑定人员的仓库？
- Q299 | generic_or_boundary_followup_not_migratable | 补槽后虽命中通用汇总 query_key，但原题要求原因/影响/字段一致性或业务建议，不能作为真实可答闭环迁 A。 | 哪些承运商绑定的company_user人数最少？是否存在无责任人配置的承运商？
- Q301 | generic_or_boundary_followup_not_migratable | 补槽后虽命中通用汇总 query_key，但原题要求原因/影响/字段一致性或业务建议，不能作为真实可答闭环迁 A。 | 哪些派车任务存在多条打卡记录？这些任务的打卡时间序列是否单调递增？
- Q302 | generic_or_boundary_followup_not_migratable | 补槽后虽命中通用汇总 query_key，但原题要求原因/影响/字段一致性或业务建议，不能作为真实可答闭环迁 A。 | punch_record中的location文本与经纬度点位是否存在明显重复或冲突？
- Q308 | answerable_after_followup_confirmed | 用户补充口径后真实链路稳定进入受控 query_key，可作为后续迁移复核输入；原题仍需先澄清。 | 哪些省份更偏好铁路运输，哪些省份几乎全部使用公路？
- Q324 | generic_or_boundary_followup_not_migratable | 补槽后虽命中通用汇总 query_key，但原题要求原因/影响/字段一致性或业务建议，不能作为真实可答闭环迁 A。 | 解析车牌与登记车牌不一致，会如何影响签收校验与后续对账？应如何排序处理优先级？
- Q328 | generic_or_boundary_followup_not_migratable | 补槽后虽命中通用汇总 query_key，但原题要求原因/影响/字段一致性或业务建议，不能作为真实可答闭环迁 A。 | 历史水路与铁路样本较少的情况下，是否值得在更多线路上推广替代运输方式？
- Q331 | generic_or_boundary_followup_not_migratable | 补槽后虽命中通用汇总 query_key，但原题要求原因/影响/字段一致性或业务建议，不能作为真实可答闭环迁 A。 | 若contract_number、bidding_number、inquiry_number长期缺失，会对经营计划部的对账与归因造成哪些影响？
- Q339 | generic_or_boundary_followup_not_migratable | 补槽后虽命中通用汇总 query_key，但原题要求原因/影响/字段一致性或业务建议，不能作为真实可答闭环迁 A。 | “铁路是不是比公路更划算？”——系统应如何先澄清问题口径？
- RAW015 | answerable_after_followup_confirmed | 用户补充口径后真实链路稳定进入受控 query_key，可作为后续迁移复核输入；原题仍需先澄清。 | 分别是多少
- SQ523 | generic_or_boundary_followup_not_migratable | 补槽后虽命中通用汇总 query_key，但原题要求原因/影响/字段一致性或业务建议，不能作为真实可答闭环迁 A。 | 客户名写成“客户：华润新能源（皮山）有限公司”和“华润新能源（皮山）有限公司 项目”时，查询结果为什么可能不一致？
- SQ524 | generic_or_boundary_followup_not_migratable | 补槽后虽命中通用汇总 query_key，但原题要求原因/影响/字段一致性或业务建议，不能作为真实可答闭环迁 A。 | “物流公司”“物流供应商”“承运商”三种问法在系统里是否映射为同一字段口径？

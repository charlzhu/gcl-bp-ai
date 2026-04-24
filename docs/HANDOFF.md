# HANDOFF.md

## 一、交接目的

本文件用于向新的接手者说明：项目当前已经推进到哪个阶段，哪些主线已经收口，哪些仍未收口，以及下一步最应该做什么。

---

## 二、项目背景

经营计划智能助手当前仍以 **logistics** 为最先收口的业务域。
当前不是平台“什么都做了一点”，而是已经把物流域推进到：

1. MVP 主链路收口
2. 题库分层建立
3. A 类自动回归
4. LLM Guardrail 受控增强
5. Top200 高价值题工厂化推进

---

## 三、物流域当前已完成的关键事实

### 1. 物流数据问答 MVP 已收口

- 结构化 data-qa 主链路已接实
- 关键验收题当前结果：
  - `20/20`
- 当前可以判定：
  - 计划通过
  - 代码通过
  - 运行态通过

### 2. 物流域题库分层结果已建立

当前物流域题库共 `903` 条，分层结果为：

- `A = 75`
- `B = 356`
- `C = 472`
- `D = 0`

这意味着：

> 物流数据问答 MVP 已收口
> 不等于物流域 903 条题库已经完全收口

### 3. A 类自动回归已建立

- A 类 `75` 条行为级自动回归：
  - `75/75`
- A 类关键题 `20` 条精确答案断言回归：
  - `20/20`

### 4. B/C 边界已开始系统化固化

- B 类：规则层主导澄清
- C 类：规则层主导不支持
- 当前不允许为了覆盖率把 B/C 硬改成 A

### 5. LLM 理解层 PoC 与 Guardrail 已完成

当前已完成：
- LLM 理解层 PoC
- Guardrail 受控接入方案

当前边界必须记住：
- Guardrail 只增强 A 类白名单同构变体
- 不允许改写 B/C 裁决
- 不允许替换正式 data-qa planner

### 6. Top200 路线图已建立

当前已经形成：
- Top200 高频优先收口对象
- Top200 高价值 B 题题族聚类
- 能力矩阵映射

### 7. Top200 高价值 B 题工厂化 Round1 已完成

当前 Round1 结果：
- 处理 `30` 条
- 推进进 A `27` 条
- 保留 B `3` 条

这说明当前推进方式已经从：
- 单题推进

升级成：
- 题族
- 能力矩阵
- 批量收口
- 自动回归

### 8. Top200 高价值 B 题工厂化 Round2 已完成

当前 Round2 结果：
- 处理 `23` 条
- 推进进 A `20` 条
- 保留 B `3` 条

当前 Top200 分布已推进到：
- `A = 158`
- `B = 17`
- `C = 25`

这说明当前推进方式不是一次性补几条散题，而是已经在按题族和能力包继续批量收口。

### 9. Top200 高价值 B 题工厂化 Round3 已完成

当前 Round3 结果：
- 处理 `11` 条
- 推进进 A `7` 条
- 保留 B `3` 条
- 转入 C `1` 条

当前 Top200 分布已推进到：
- `A = 165`
- `B = 9`
- `C = 26`

这说明当前高价值 B 题工厂化推进已经不是 Round1 / Round2 的一次性动作，而是可以持续复用的批量收口机制。

### 10. Top200 高价值 B 题工厂化 Round4 已完成

当前 Round4 结果：
- 处理 `9` 条
- 推进进 A `2` 条
- 保留 B `6` 条
- 转入 C `1` 条

当前 Top200 分布已推进到：
- `A = 167`
- `B = 6`
- `C = 27`

### 11. Top200 高价值 B 题工厂化 Round5 已完成

当前 Round5 结果：
- 处理 `6` 条
- 推进进 A `3` 条
- 保留 B `0` 条
- 转入 C `3` 条

当前 Top200 分布已推进到：
- `A = 170`
- `B = 0`
- `C = 30`

这说明当前 Top200 高价值 B 题已经完成阶段性清零，后续重点不再是继续吃高价值 B，而是把新进入 A 的题继续纳入更严格精确断言回归。

### 12. Round4 / Round5 新进 A 题精确断言回归已完成

当前本轮结果：
- 总数 `5`
- 通过 `5`
- 失败 `0`

当前已独立纳入更严格精确断言回归的题包括：
- `RAW052`
- `RAW056`
- `RAW057`
- `RAW011`
- `RAW025`

这说明当前最新进入 A 的高价值题，不只是“当前链路能答”，而是已经进入更严格基线管理。

### 13. A-稳定增强池 Round1 / Round2 / Round3 已完成

当前本轮结果：
- Round1：`39/39`
- Round2：`34/34`
- Round3：`33/33`

当前 A 池状态已经推进到：
- `A_total = 170`
- `A_precise = 170`
- `A_non_precise = 0`

这说明当前 Top200 内已进入 A 的 `170` 条题，已经全部纳入更严格精确断言和固定复检。

### 14. B-长期澄清池 Round1 已完成

当前本轮结果：
- `B-长期澄清池总量 = 230`
- `Round1 选中 = 34`
- `live 样本 = 7`
- `实际采用 LLM 业务化追问 = 7`
- `边界保持 clarification = 34/34`

当前 Round1 已覆盖的澄清题型包括：
- `vague_status`
- `transport_record_scope`
- `quarter_trip_metric_scope`
- `route_loading_scope`
- `rate_distribution_scope`
- `system_status_ratio_scope`
- `parse_status_scope`

这说明当前长期澄清题已经开始从“通用追问”进入“规则层锁边界 + LLM 补缺口径与业务化追问候选”的正式治理阶段。

### 15. B-长期澄清池 Round2 已完成

当前本轮结果：
- `B-长期澄清池总量 = 230`
- `Round1 选中 = 34`
- `Round1 去重后唯一题 = 32`
- `Round2 选中 = 37`
- `Round2 剩余 = 159`
- `live 样本 = 8`
- `实际调用 = 8`
- `实际采用 LLM 业务化追问 = 8`
- `边界保持 clarification = 37/37`

当前 Round2 已覆盖的澄清题型包括：
- `status_risk_scope`
- `data_quality_scope`
- `procurement_metric_scope`
- `state_breakdown_scope`
- `route_price_metric_scope`
- `high_fee_address_scope`

这说明当前长期澄清题已经进一步进入“规则层锁边界 + LLM 补缺口径与业务化追问候选”的正式治理阶段，而且已经明确证明：线上真实问法不能按死板 exact match 去判定是否澄清。

### 16. B-长期澄清池 Round3 已完成

当前本轮结果：
- `B-长期澄清池总量 = 230`
- `Round1 选中 = 34`
- `Round2 选中 = 37`
- `Round3 选中 = 82`
- `Round3 剩余 = 77`
- `live 样本 = 10`
- `实际调用 = 10`
- `实际采用 LLM 业务化追问 = 10`
- `边界保持 clarification = 82/82`

当前 Round3 已覆盖的澄清题型包括：
- `comparison_basis_scope`
- `mapping_consistency_scope`
- `route_metric_scope`
- `data_consistency_scope`

这说明当前长期澄清题已经进一步进入“规则层锁边界 + LLM 补缺口径与业务化追问候选”的正式治理阶段，而且已经继续证明：线上真实问法不能按死板 exact match 去判定是否澄清。

### 17. B-长期澄清池 Round4 已完成

当前本轮结果：
- `B-长期澄清池总量 = 230`
- `Round1 选中 = 34`
- `Round2 选中 = 37`
- `Round3 选中 = 82`
- `Round4 选中 = 47`
- `Round4 剩余 = 30`
- `live 样本 = 12`
- `实际调用 = 12`
- `实际采用 LLM 业务化追问 = 11`
- `边界保持 clarification = 47/47`

当前 Round4 已覆盖的澄清题型包括：
- `quarter_area_metric_scope`
- `transport_unit_fee_scope`
- `procurement_metric_scope`
- `parse_status_scope`
- `state_breakdown_scope`
- `state_ranking_scope`
- `data_consistency_scope`
- `task_split_scope`

这说明当前长期澄清题已经进一步进入“规则层锁边界 + LLM 补缺口径与业务化追问候选”的正式治理阶段，而且已经继续证明：线上真实问法不能按死板 exact match 去判定是否澄清。

### 18. B-长期澄清池 Round5 已完成

当前本轮结果：
- `B-长期澄清池总量 = 230`
- `Round1 选中 = 34`
- `Round2 选中 = 37`
- `Round3 选中 = 82`
- `Round4 选中 = 47`
- `Round5 选中 = 30`
- `Round5 剩余 = 0`
- `保留 B = 20`
- `推进进 A = 3`
- `转入 C = 7`
- `边界保持 = 27`

当前 Round5 已覆盖的澄清题型包括：
- `field_alias_comparison_scope`
- `cause_distribution_scope`
- `contract_carrier_scope`
- `data_quality_scope`
- `transport_distance_scope`
- `short_context_scope`
- `shipment_quantity_scope`
- `carrier_unit_fee_scope`
- `parse_fail_ranking_scope`
- `driver_identity_consistency_scope`

这说明 B-长期澄清池 Round1～Round5 已完成阶段性治理覆盖，下一步不应继续假定存在 Round6，而应进入 C-边界观察池。

### 19. C-边界观察池与 903 全量收口评估已完成

当前 C 池评估结果：
- `C-边界观察池 = 484`
- `P1/P2 高优先级 C 题 = 7`
- 建议正式进入治理动作

当前 903 最新全量分布：
- `A = 173`
- `B = 246`
- `C = 484`
- `D = 0`

当前治理池分布：
- `A-稳定增强池 = 173`
- `B-候选收口池 = 26`
- `B-长期澄清池 = 220`
- `C-边界观察池 = 484`
- `D-待业务/数据修订池 = 0`

当前最合理下一步：
- 进入 `C-边界观察池 Round1`
- 固化拒答边界和业务可理解原因
- 不扩 query_key，不把 C 类硬拉进 A

### 20. C-边界观察池 Round1 已完成

当前本轮结果：
- `C-边界观察池总量 = 484`
- `Round1 已固化拒答 = 67`
- `已具备业务化原因和可改问建议 = 67`
- `需台账重算 / 迁移复核 = 417`

当前运行态拆分：
- `C_hardened = 67`
- `A_candidate = 127`
- `B_candidate = 290`

当前最重要结论：
- C Round1 只固化明确应拒答的边界；
- 旧 C 中当前 planner 已可答或应澄清的题，不应继续硬拒答；
- 下一步应进入 `C-边界观察池 Round2`，做旧 C 台账重算与 A/B 迁移复核。

### 21. C-边界观察池 Round2 已完成

当前本轮结果：
- `Round2 复核总量 = 484`
- `A_candidate = 127`
- `B_candidate = 290`
- `C_confirmed = 67`
- `manual_review = 0`

当时分布判断：
- 迁移前正式总账为：`A=173 / B=246 / C=484 / D=0`
- 如果迁移建议全部接受，建议分布为：`A=300 / B=536 / C=67 / D=0`

当前最重要结论：
- Round2 已完成旧 C 台账重算与迁移复核；
- `A_candidate=127` 只是当前 planner 可答，不等于已稳定收口；
- 下一步必须先对 127 条 A_candidate 做行为级自动回归，再决定是否更新 903 正式总账。

### 22. C Round2 A_candidate 行为回归已完成

当前本轮结果：
- `A_candidate 总数 = 127`
- 初始行为回归结果：`通过 = 127`、`失败 = 0`
- C2A-P3 后复核结果：`通过 = 125`、`失败 = 2`
- 失败归因：`题目迁移误判 = 2`

当前 query_key 分布：
- `hist_mw_summary = 43`
- `hist_mw_by_all_regions = 14`
- `hist_vehicle_type_trip_count = 8`
- `sys_mw_and_trip_count = 23`
- `sys_total_fee_by_filters = 21`
- `hist_customer_mw = 14`
- `sys_mw_by_procurement_type = 2`
- `hist_carrier_kpi_by_year = 2`

当前最重要结论：
- A_candidate 已真实调用 data-qa 主链路并进入后续精确断言复核；
- C2A-P3 复核发现其中 2 条预测题不应迁入 A，已回到 C 边界；
- 当前后续已经完成 903 正式总账迁移，125 条有效 A_candidate 已迁入 A；
- 同时已把 B_candidate=290 迁入 B，并保留 C_confirmed=67 与 2 条预测边界题。

### 23. 903 正式总账迁移更新已完成

当前迁移结果：
- `125` 条已通过行为回归且通过 C2A 复核的 A_candidate 已迁入 A。
- `290` 条 B_candidate 已迁入 B，并纳入后续澄清模板复检。
- `67` 条 C_confirmed 继续保持 C，另有 `2` 条预测题回到 C 边界。

当前 903 最新正式分布：
- `A = 298`
- `B = 536`
- `C = 69`
- `D = 0`

当前治理池分布：
- `A-稳定增强池 = 298`
- `B-候选收口池 = 26`
- `B-长期澄清池 = 510`
- `C-边界观察池 = 69`
- `D-待业务/数据修订池 = 0`

当前最重要结论：
- 903 正式总账已经同步到 C Round2 迁移后的真实状态；
- 后续不应再把 125 条已验证 A_candidate 留在 C；
- 后续不应再把 290 条 B_candidate 留在 C，而应进入澄清模板复检；
- 新增 A 题仍需分批补精确断言，不应直接等同于已完成强基线。

### 24. 903 迁移后 A/B 后续治理计划已建立

当前已完成：
- `127` 条新进 A 已拆成 `C2A-P1/P2/P3/P4` 四批，规模为 `30/30/30/37`。
- `290` 条 B_candidate 已拆成 `BCR1/BCR2/BCR3/BCR4` 四批，规模为 `60/80/80/70`。

当前最重要结论：
- 新进 A 已有可执行的精确断言补强路线，但尚未直接刷新 127 条黄金答案基线；
- B_candidate 已全部纳入澄清模板复检队列，但仍必须保持澄清边界；
- LLM 只能辅助缺口径识别和追问候选生成，不能做最终边界裁决。

### 25. C2A-P1 / BCR1 Round1 已完成

当前 C2A-P1 精确断言 Round1 结果：
- `C2A-P1 总数 = 30`
- `通过 = 30`
- `失败 = 0`
- 标准答案来源：当前 `logistics_ai` 数据快照，经正式 data-qa 主链路执行后固化。
- 断言字段：`status.code`、`query_plan.query_key`、`answer_summary`、`result_table.columns`、`result_table.rows`。

当前 BCR1 澄清模板复检 Round1 结果：
- `BCR1 总数 = 60`
- `澄清边界通过 = 60`
- `澄清边界失败 = 0`
- `CLARIFICATION_REQUIRED = 60`
- `建议优化业务化追问模板 = 58`

当前 BCR1 题型分布：
- `abnormal_or_reason_scope = 5`
- `transport_mode_metric_scope = 12`
- `procurement_metric_scope = 10`
- `route_or_address_scope = 33`

当时最重要结论：
- C2A-P1 已完成第一批新进 A 精确断言基线。
- BCR1 已证明 60 条 B_candidate 澄清边界稳定，没有误落 success 或 unsupported。
- BCR1 初次复检发现 58 条仍需要把追问从通用模板升级为更业务化的缺口径追问。
- 该模板优化项已在后续 BCR1 业务化追问模板优化中完成固化。

### 26. BCR1 业务化追问模板优化 / C2A-P2 已完成

当前 BCR1 业务化追问模板优化结果：
- `BCR1 总数 = 60`
- `澄清边界通过 = 60`
- `澄清边界失败 = 0`
- `CLARIFICATION_REQUIRED = 60`
- `模板优化建议 = 0`

本轮已固化的 BCR1 澄清题型：
- `abnormal_or_reason_scope = 5`
- `transport_mode_metric_scope = 12`
- `procurement_metric_scope = 10`
- `route_or_address_scope = 33`

当前 C2A-P2 精确断言结果：
- `C2A-P2 总数 = 30`
- `通过 = 30`
- `失败 = 0`

当前最重要结论：
- BCR1 已完成业务化追问模板固化，模板优化建议从 `58` 降为 `0`。
- C2A-P2 已完成第二批新进 A 精确断言基线。
- 下一步不应重复做 BCR1 或 C2A-P2，建议进入 `BCR2` 澄清模板复检；如果优先目标是继续增强 A 精确基线，则进入 `C2A-P3`。

### 27. BCR2 澄清模板复检 Round2 已完成

当前 BCR2 澄清模板复检结果：
- `BCR2 总数 = 80`
- `澄清边界通过 = 80`
- `澄清边界失败 = 0`
- `CLARIFICATION_REQUIRED = 80`
- `模板优化建议 = 10`

当前 BCR2 题型分布：
- `route_or_address_scope = 70`
- `system_state_scope = 1`
- `data_consistency_scope = 2`
- `vehicle_or_trip_scope = 7`

当前 BCR2 模板优化建议分布：
- `system_state_scope = 1`
- `data_consistency_scope = 2`
- `vehicle_or_trip_scope = 7`

当前最重要结论：
- BCR2 已证明 80 条 B_candidate 澄清边界稳定，没有误落 success 或 unsupported。
- 70 条 `route_or_address_scope` 已被当前线路 / 地址范围追问能力稳定兜住。
- 仍有 10 条需要继续固化更业务化的追问模板，重点是系统状态、数据一致性、车次 / 车型口径。
- 下一步建议先固化 BCR2 中 10 条业务化追问模板优化项；如果优先目标是继续增强 A 精确基线，再进入 `C2A-P3`。

### 28. BCR2 业务化追问模板优化已完成

当前 BCR2 模板优化后复检结果：
- `BCR2 总数 = 80`
- `澄清边界通过 = 80`
- `澄清边界失败 = 0`
- `CLARIFICATION_REQUIRED = 80`
- `模板优化建议 = 0`

本轮已固化的 BCR2 澄清题型：
- `system_state_scope = 1`
- `data_consistency_scope = 2`
- `vehicle_or_trip_scope = 7`

当前最重要结论：
- BCR2 已从“识别出 10 条模板优化建议”推进到“80 条澄清边界稳定且模板缺口清零”。
- 规则层新增了系统状态、数据一致性、历史月度总车次三类业务化追问模板。
- LLM 澄清辅助白名单和提示已同步支持 `system_state_scope`、`vehicle_or_trip_scope`。
- 下一步如优先增强 A 精确基线，应进入 `C2A-P3`；如优先继续治理 B_candidate，可进入 `BCR3`。

### 29. C2A-P3 新进 A 精确断言 Round3 已完成

当前 C2A-P3 精确断言结果：
- `C2A-P3 总数 = 30`
- `通过 = 28`
- `失败 = 2`
- `失败归因 = 题目分层误判 2`

当前未通过题：
- `SQ591`：基于2024年前期数据，预测未来3个月各区域发运量变化趋势。
- `SQ595`：基于2025年前期数据，预测未来3个月各区域发运量变化趋势。

当前最重要结论：
- 这 2 条题包含明确预测语义，必须保持 unsupported，不允许固化为 A 类精确基线。
- 已修正规则优先级，让 unsupported 策略先于高置信 A 类 query_key 生效。
- C Round2 A_candidate 行为回归当前复核为 `125/127`。
- 903 总账重算后当前分布为 `A=298 / B=536 / C=69 / D=0`。
- 下一步如优先增强 A 精确基线，应进入 `C2A-P4`；如优先继续治理 B_candidate，可进入 `BCR3`。

### 30. C2A-P4 新进 A 精确断言 Round4 已完成

当前 C2A-P4 精确断言结果：
- `C2A-P4 总数 = 37`
- `通过 = 37`
- `失败 = 0`
- `失败归因 = 无`

当前 C2A-P4 覆盖题型：
- `hist_mw_summary = 37`
- 代表题型包括：年度 / 区域 / 省份 / 基地维度的历史发运量 MW 汇总。

当前 C2A 四批总体结论：
- `C2A-P1 = 30/30`
- `C2A-P2 = 30/30`
- `C2A-P3 = 28/30`
- `C2A-P4 = 37/37`
- `127` 条计划补强题中，`125` 条有效进入 A 精确断言，`2` 条预测题回到 C 边界。

当前最重要结论：
- C2A-P4 已完成，不应继续作为下一任务；
- 当前 903 最新正式分布保持 `A=298 / B=536 / C=69 / D=0`；
- 下一步如优先治理 B_candidate，应进入 `BCR3` 澄清模板复检；
- A-稳定增强尾项还剩 `3` 条未纳入精确断言，可后续单独补强。

### 31. BCR3 B_candidate 澄清模板复检与业务化追问模板优化已完成

当前 BCR3 澄清模板复检结果：
- `BCR3 总数 = 80`
- `澄清边界通过 = 80`
- `澄清边界失败 = 0`
- `CLARIFICATION_REQUIRED = 80`
- 初次模板优化建议：`30`
- 模板优化后复检建议：`0`

当前 BCR3 题型分布：
- `vehicle_or_trip_scope = 30`
- `customer_project_scope = 14`
- `ranking_basis_scope = 3`
- `generic_metric_scope = 33`

当前 BCR3 初次模板优化建议分布：
- `vehicle_or_trip_scope = 13`
- `customer_project_scope = 14`
- `ranking_basis_scope = 3`

本轮已固化的 BCR3 澄清题型：
- `vehicle_or_trip_scope`：补充车次 / 车辆数口径、车型口径、基地/承运商分组维度和统计时间范围追问。
- `customer_project_scope`：补充客户/项目名称归并口径、指标口径和是否需要排名追问。
- `ranking_basis_scope`：补充排名指标、排名方向、TopN 数量和分组维度追问。
- LLM 澄清辅助白名单和题型提示同步补入 `customer_project_scope`、`ranking_basis_scope`，`vehicle_or_trip_scope` 提示继续复用。

当前最重要结论：
- BCR3 已从“识别出 30 条模板优化建议”推进到“80 条澄清边界稳定且模板缺口清零”；
- 当前不需要重复执行 BCR3 固化动作；
- 下一步如继续治理 B_candidate，应进入 `BCR4`；如优先补 A 稳定增强尾项，则处理剩余 3 条未精确断言 A 题。

### 32. BCR4 B_candidate 澄清模板复检 Round4 已完成

当前 BCR4 澄清模板复检结果：
- `BCR4 总数 = 70`
- `澄清边界通过 = 70`
- `澄清边界失败 = 0`
- `CLARIFICATION_REQUIRED = 70`
- `模板优化建议 = 7`

当前 BCR4 题型分布：
- `generic_metric_scope = 70`

当前 BCR4 模板优化建议分布：
- `generic_metric_scope = 7`

当前 7 条模板优化项集中在：
- `2026` 特殊业务口径总发运量题：辅料送样、经营计划、刘娟用车，需要补充输出形态追问。
- `2024/2025` 多式联运总发运量 / 总运费题，需要补充输出形态追问。

当前最重要结论：
- BCR4 已证明 70 条 B_candidate 澄清边界稳定，没有误落 success 或 unsupported；
- 仍有 7 条需要把追问从“时间/指标/维度”进一步补齐到“输出形态”；
- 下一步应先固化 BCR4 中 7 条业务化追问模板优化项，再评估 B_candidate 队列是否阶段性完成。

---

## 四、当前最重要的边界判断

### 可以明确说的

1. 物流数据问答 MVP 已收口
2. A 类 `75` 条已具备行为级自动回归能力
3. A 类关键题 `20` 条已具备精确答案断言回归能力
4. B/C 类边界已开始系统化固化
5. Top200 高价值 B 题工厂化 Round1、Round2、Round3、Round4、Round5 已完成
6. A-稳定增强池 Round1、Round2、Round3 已完成，且当前 `170/170` 已进入更严格精确断言
7. B-长期澄清池 Round1 已完成，且当前 `34/34` 仍稳定保持 clarification 边界
8. B-长期澄清池 Round2 已完成，且当前 `37/37` 仍稳定保持 clarification 边界
9. B-长期澄清池 Round3 已完成，且当前 `82/82` 仍稳定保持 clarification 边界
10. B-长期澄清池 Round4 已完成，且当前 `47/47` 仍稳定保持 clarification 边界
11. B-长期澄清池 Round5 已完成，剩余 `30` 条已全部覆盖
12. C-边界观察池治理评估已完成，建议正式进入 C Round1
13. C-边界观察池 Round1 已完成，`67` 条已固化拒答，`417` 条需重算迁移复核
14. C-边界观察池 Round2 已完成，`A_candidate=127 / B_candidate=290 / C_confirmed=67`
15. C Round2 A_candidate 行为回归已完成并在 C2A-P3 后复核修正为 `125/127`
16. 903 正式总账迁移更新已完成，当前分布为 `A=298 / B=536 / C=69 / D=0`
17. 903 迁移后 A/B 后续治理计划已建立，`C2A=30/30/30/37`，`BCR=60/80/80/70`
18. C2A-P1 新进 A 精确断言 Round1 已完成，`30/30`
19. BCR1 B_candidate 澄清模板复检 Round1 已完成，澄清边界 `60/60`
20. BCR1 业务化追问模板优化已完成，模板优化建议从 `58` 降为 `0`
21. C2A-P2 新进 A 精确断言 Round2 已完成，`30/30`
22. BCR2 B_candidate 澄清模板复检 Round2 已完成，澄清边界 `80/80`，模板优化建议 `10`
23. BCR2 业务化追问模板优化已完成，模板优化建议从 `10` 降为 `0`
24. C2A-P3 新进 A 精确断言 Round3 已完成，`28/30`，2 条预测题回到 C 边界
25. C2A-P4 新进 A 精确断言 Round4 已完成，`37/37`
26. C2A 四批总体结果：`125` 条有效进入 A 精确断言，`2` 条预测题回到 C 边界
27. BCR3 B_candidate 澄清模板复检 Round3 已完成，澄清边界 `80/80`，初次模板优化建议 `30`
28. BCR3 业务化追问模板优化已完成，模板优化建议从 `30` 降为 `0`
29. BCR4 B_candidate 澄清模板复检 Round4 已完成，澄清边界 `70/70`，模板优化建议 `7`

### 必须继续明确说的

1. 物流域全量 `903` 条题库仍未完全收口
2. LLM 不能替换正式 planner
3. Guardrail 不能改写 B/C
4. 当前还不适合进入经营分析开发
5. 当前 903 最新正式分布为 `A=298 / B=536 / C=69 / D=0`
6. `903` 条题只是样例题库，不等于线上用户一定按一模一样的句子提问
7. 后续澄清治理必须继续按语义和槽位缺失做高精度识别，不能按死板 exact match
8. LLM 在长期澄清题里只允许做：
   - 缺口径识别
   - 追问候选生成
   不能做最终边界裁决

---

## 五、当前前端状态

前端物流数据问答页、历史页、回放、CSV/XLSX 导出都已经存在，足够支撑当前物流域能力验证和演示。
当前主线重点不再是前端扩展，而是继续收口物流域高价值题库。

---

## 六、当前仍未收口的部分

1. 物流域 `903` 条题库尚未完全收口
2. Top200 高价值 B 题虽然已经清零，但全量 `903` 条题库仍未完全收口
3. Top200 当前为：
   - `A = 170`
   - `B = 0`
   - `C = 30`
4. 当前 903 全量状态为：
   - `A = 298`
   - `B = 536`
   - `C = 69`
   - `D = 0`
5. 当前剩余问题已经不再是高价值 B 收口，也不是 B-长期澄清池继续开 Round6，而是：
   - 先固化 `BCR4` 中 7 条业务化追问模板优化项
   - 对 A-稳定增强尾项中剩余 `3` 条未精确断言 A 题做单独补强

---

## 七、推荐接手顺序

### 第一步
先完整阅读：

- `AGENTS.md`
- `CURRENT_STATUS.md`
- `NEXT_TASK.md`
- `docs/LOGISTICS_QUESTION_BANK_CLASSIFICATION.md`
- `docs/LOGISTICS_TOP200_ROADMAP.md`
- `docs/LOGISTICS_TOP200_B_CLUSTERING.md`
- `docs/LOGISTICS_CAPABILITY_MATRIX.md`
- `docs/LOGISTICS_TOP200_B_FACTORY_ROUND1.md`
- `docs/LOGISTICS_TOP200_B_FACTORY_ROUND2.md`
- `docs/LOGISTICS_TOP200_B_FACTORY_ROUND3.md`
- `docs/LOGISTICS_TOP200_B_FACTORY_ROUND4.md`
- `docs/LOGISTICS_TOP200_B_FACTORY_ROUND5.md`
- `docs/LOGISTICS_TOP200_ROUND45_NEW_A_PRECISE_REGRESSION.md`

### 第二步
先核对以下基线是否还成立：

- `20/20` 关键题精确断言
- `75/75` A 类行为级回归
- Guardrail 不越权改写 B/C
- Top200 Round1 结果仍为 `30 / 27 / 3`
- Top200 Round2 结果仍为 `23 / 20 / 3`
- Top200 Round3 结果仍为 `11 / 7 / 3 / 1`
- Top200 Round4 结果仍为 `9 / 2 / 6 / 1`
- Top200 Round5 结果仍为 `6 / 3 / 0 / 3`
- Round4 / Round5 新进 A 精确断言结果仍为 `5 / 5 / 0`
- A-稳定增强池 Round1 / Round2 / Round3 结果仍为：
  - `39 / 39`
  - `34 / 34`
  - `33 / 33`
- B-长期澄清池 Round1 结果仍为：
  - `230 / 34 / 7 / 7 / 34`
- B-长期澄清池 Round2 结果仍为：
  - `230 / 34 / 32 / 37 / 159 / 8 / 8 / 37`
- B-长期澄清池 Round3 结果仍为：
  - `230 / 34 / 37 / 82 / 77 / 10 / 10 / 82`
- B-长期澄清池 Round4 结果仍为：
  - `230 / 34 / 37 / 82 / 47 / 30 / 12 / 12 / 11 / 47`
- B-长期澄清池 Round5 结果仍为：
  - `230 / 34 / 37 / 82 / 47 / 30 / 20 / 3 / 7 / 27`
- 当前 903 全量正式分布仍为：
  - `A=298 / B=536 / C=69 / D=0`
- C-边界观察池 Round1 结果仍为：
  - `484 / 67 / 417 / A_candidate=127 / B_candidate=290`
- C-边界观察池 Round2 结果仍为：
  - `484 / A_candidate=127 / B_candidate=290 / C_confirmed=67`
- C Round2 A_candidate 行为回归当前复核结果仍为：
  - `127 / 125 / 2`
- 903 正式总账迁移更新结果仍为：
  - `125` 条 A_candidate 入 A
  - `290` 条 B_candidate 入 B
  - `69` 条 C_confirmed / 预测边界题留 C
- 903 迁移后 A/B 后续治理计划仍为：
  - `C2A-P1/P2/P3/P4 = 30/30/30/37`
  - `BCR1/BCR2/BCR3/BCR4 = 60/80/80/70`
- C2A-P1 精确断言 Round1 结果仍为：
  - `30 / 30 / 0`
- BCR1 澄清模板复检 Round1 结果仍为：
  - `60 / 60 / 0`
  - 模板优化建议 `0`
- C2A-P2 精确断言 Round2 结果仍为：
  - `30 / 30 / 0`
- BCR2 澄清模板复检 Round2 结果仍为：
  - `80 / 80 / 0`
  - 模板优化建议 `0`
- C2A-P3 精确断言 Round3 结果仍为：
  - `30 / 28 / 2`
  - 失败归因 `题目分层误判`
- C2A-P4 精确断言 Round4 结果仍为：
  - `37 / 37 / 0`
- BCR3 澄清模板复检 Round3 结果仍为：
  - `80 / 80 / 0`
  - 模板优化建议 `0`
- BCR4 澄清模板复检 Round4 结果仍为：
  - `70 / 70 / 0`
  - 模板优化建议 `7`

### 第三步
如果以上都没回退，再继续推进：

> **先固化 `BCR4` 中 7 条业务化追问模板优化项；如果优先补 A 稳定增强尾项，则处理剩余 3 条未精确断言 A 题。**

---

## 八、交接后一条最重要的原则

> **当前物流域的主要矛盾已经不是“主链路能不能跑”，也不是“903 总账是否同步”，而是“继续按 BCR/C2A 批次做新增 B 澄清复检和新增 A 精确断言”。**

因此接手后不要再回到单题挤牙膏，也不要跳去经营分析开发，应继续沿：

- BCR4 业务化追问模板优化
- A-稳定增强尾项补强
- B/C 边界不回退
- Guardrail 不越权
- 语义识别与槽位缺失识别优先于死板 exact match

这条主线推进。

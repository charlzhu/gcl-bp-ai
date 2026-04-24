# CURRENT_STATUS.md

## 一、项目概述

项目名称：经营计划智能助手
当前优先域：物流数据问答（logistics）

当前项目级状态：

> **物流数据问答 MVP：计划通过、代码通过、运行态通过。**
>
> **物流域全量 903 条题库：尚未完全收口。**

当前阶段已经从“物流数据问答主链路是否可用”，推进到“物流域题库边界是否可管理、可回归、可分批收口”。

---

## 二、当前已完成的关键事实

### 1. 物流数据问答 MVP 已收口

- 受控查询计划已接实
- 白名单 SQL 已接实
- 澄清 / 不支持 / warning / 结果结构已接实
- 当前关键验收题结果：
  - `20/20`

### 2. 物流域题库分层结果已建立

当前物流域题库总量：`903`

当前分层结果：
- `A = 75`
- `B = 356`
- `C = 472`
- `D = 0`

### 3. A 类自动回归与关键题精确断言已成立

- A 类 `75` 条行为级自动回归已成立：
  - `75/75`
- A 类关键题 `20` 条精确答案断言回归已成立：
  - `20/20`

### 4. LLM 理解层 PoC 已完成

当前已完成：
- LLM 理解层 PoC
- Guardrail 规则服务
- Guardrail 受控接入方案

当前结论：
- A 类同构变体问法收益明显
- B/C 边界仍必须由规则层主导
- 当前 Guardrail 只允许增强 A 类白名单同构变体
- 不允许改写 B/C 裁决

### 5. Top200 路线图已建立

当前已建立：
- Top200 高频问题收口路线图
- Top200 高价值 B 题题族聚类
- Top200 能力矩阵映射

### 6. Top200 高价值 B 题工厂化 Round1 已完成

当前 Round1 结果：
- 处理题数：`30`
- 推进进 A：`27`
- 保留 B：`3`

当前已经从：
- 单题推进

升级为：
- 题族
- 能力矩阵
- 批量收口
- 自动回归

### 7. Top200 高价值 B 题工厂化 Round2 已完成

当前 Round2 结果：
- 处理题数：`23`
- 推进进 A：`20`
- 保留 B：`3`

当前 Top200 分布已推进到：
- `A = 158`
- `B = 17`
- `C = 25`

### 8. Top200 高价值 B 题工厂化 Round3 已完成

当前 Round3 结果：
- 处理题数：`11`
- 推进进 A：`7`
- 保留 B：`3`
- 转入 C：`1`

当前 Top200 分布已推进到：
- `A = 165`
- `B = 9`
- `C = 26`

### 9. Top200 高价值 B 题工厂化 Round4 已完成

当前 Round4 结果：
- 处理题数：`9`
- 推进进 A：`2`
- 保留 B：`6`
- 转入 C：`1`

当前 Top200 分布已推进到：
- `A = 167`
- `B = 6`
- `C = 27`

### 10. Top200 高价值 B 题工厂化 Round5 已完成

当前 Round5 结果：
- 处理题数：`6`
- 推进进 A：`3`
- 保留 B：`0`
- 转入 C：`3`

当前 Top200 分布已推进到：
- `A = 170`
- `B = 0`
- `C = 30`

这说明当前 Top200 高价值 B 题已经完成阶段性清零，后续重点不再是继续推进高价值 B 题批量收口，而是：
- 把 Round4 / Round5 新推进进 A 的题纳入更严格精确断言回归
- 再决定是否进入下一条业务主线

### 11. Round4 / Round5 新进 A 题精确断言回归已完成

当前本轮结果：
- 总数：`5`
- 通过：`5`
- 失败：`0`

当前已独立纳入更严格精确断言回归的题包括：
- `RAW052`
- `RAW056`
- `RAW057`
- `RAW011`
- `RAW025`

这说明当前 Top200 高价值 B 题不仅已经阶段性清零，而且最新进入 A 的题也已经开始进入更严格基线管理。

### 12. A-稳定增强池 Round1 / Round2 / Round3 已完成

当前已完成：
- Round1：`39/39`
- Round2：`34/34`
- Round3：`33/33`

当前 A 池状态已经推进到：
- `A_total = 170`
- `A_precise = 170`
- `A_non_precise = 0`

这说明当前 Top200 内已进入 A 的 `170` 条题，已经全部纳入更严格精确断言和固定复检。

### 13. B-长期澄清池 Round1 已完成

当前本轮结果：
- `B-长期澄清池总量 = 230`
- `Round1 选中 = 34`
- `live 样本 = 7`
- `实际采用 LLM 业务化追问 = 7`
- `边界保持 clarification = 34/34`

当前 Round1 覆盖的澄清题型包括：
- `vague_status`
- `transport_record_scope`
- `quarter_trip_metric_scope`
- `route_loading_scope`
- `rate_distribution_scope`
- `system_status_ratio_scope`
- `parse_status_scope`

当前结论：
- 规则层仍然负责最终边界裁决；
- LLM 只做缺口径识别和追问候选生成；
- 当前已经开始把长期澄清题从“通用追问”升级成“更业务化的正式追问”；
- 题库里的 `903` 条问题只是样例，不应按死板问题文本做 exact match 判断，后续必须继续按语义和槽位缺失做高精度识别。

### 14. B-长期澄清池 Round2 已完成

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

当前 Round2 覆盖的澄清题型包括：
- `status_risk_scope`
- `data_quality_scope`
- `procurement_metric_scope`
- `state_breakdown_scope`
- `route_price_metric_scope`
- `high_fee_address_scope`

当前结论：
- 规则层仍然负责最终边界裁决；
- LLM 只做缺口径识别和追问候选生成；
- 当前已经把更多长期澄清题纳入“规则层锁边界 + LLM 补缺口径与业务化追问候选”的正式治理阶段；
- 题库里的 `903` 条问题只是样例，不应按死板问题文本做 exact match 判断，后续必须继续按语义和槽位缺失做高精度识别。

### 15. B-长期澄清池 Round3 已完成

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

当前 Round3 覆盖的澄清题型包括：
- `comparison_basis_scope`
- `mapping_consistency_scope`
- `route_metric_scope`
- `data_consistency_scope`

当前结论：
- 规则层仍然负责最终边界裁决；
- LLM 只做缺口径识别和追问候选生成；
- 当前已经把更多长期澄清题纳入“规则层锁边界 + LLM 补缺口径与业务化追问候选”的正式治理阶段；
- 题库里的 `903` 条问题只是样例，不应按死板问题文本做 exact match 判断，后续必须继续按语义和槽位缺失做高精度识别。

### 16. B-长期澄清池 Round4 已完成

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

当前 Round4 覆盖的澄清题型包括：
- `quarter_area_metric_scope`
- `transport_unit_fee_scope`
- `procurement_metric_scope`
- `parse_status_scope`
- `state_breakdown_scope`
- `state_ranking_scope`
- `data_consistency_scope`
- `task_split_scope`

当前结论：
- 规则层仍然负责最终边界裁决；
- LLM 只做缺口径识别和追问候选生成；
- 当前已经把更多长期澄清题纳入“规则层锁边界 + LLM 补缺口径与业务化追问候选”的正式治理阶段；
- 题库里的 `903` 条问题只是样例，不应按死板问题文本做 exact match 判断，后续必须继续按语义和槽位缺失做高精度识别。

### 17. B-长期澄清池 Round5 已完成

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

当前 Round5 覆盖的澄清题型包括：
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

当前结论：
- B-长期澄清池 Round1～Round5 已完成阶段性治理覆盖；
- 规则层仍然负责最终边界裁决；
- LLM 只做缺口径识别和追问候选生成；
- 下一步不应继续假定存在 B-长期澄清池 Round6，而应优先进入 C-边界观察池治理评估与拒答理由固化。

### 18. C-边界观察池治理评估已完成

当前评估结果：
- `C-边界观察池 = 484`
- `P1/P2 高优先级 C 题 = 7`
- 建议正式进入治理动作

当前治理目标不是扩 query_key，而是：
- 固化拒答边界
- 固化业务可理解原因
- 对无稳定 query_key、预测 / 开放讨论 / 治理原则、超出现有结构化统计边界三类问题统一拒答文案

### 19. 903 全量题库最新评估已完成

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

当前结论：
- 903 全量题库尚未完全收口；
- 但已经进入可管理、可复检、可分池推进状态；
- 当前最合理下一步是进入 `C-边界观察池`，先做拒答边界和业务理由治理。

### 20. C-边界观察池 Round1 已完成

当前本轮结果：
- `C-边界观察池总量 = 484`
- `Round1 已固化拒答 = 67`
- `已具备业务化原因和可改问建议 = 67`
- `需台账重算 / 迁移复核 = 417`

当前运行态拆分：
- `C_hardened = 67`
- `B_candidate = 290`
- `A_candidate = 127`

当前 Round1 固化的拒答类别包括：
- `forecast`
- `eta`
- `extra_fee_detail`
- `supplier_price_diagnostic`
- `discussion`
- `clarification_design`
- `correlation_analysis`
- `system_response_strategy`
- `high_fee_address_procurement_split`
- `warehouse_dimension_unreliable`
- `project_name_dimension`

当前结论：
- C Round1 已把明确应拒答的问题固化成业务可理解原因和可改问建议；
- 旧 C 中当前 planner 已可答或应澄清的 `417` 条，不应继续硬拒答；
- 下一步最合理的是 `C-边界观察池 Round2`，做台账重算与迁移复核。

### 21. C-边界观察池 Round2 已完成

当前本轮结果：
- `Round2 复核总量 = 484`
- `A_candidate = 127`
- `B_candidate = 290`
- `C_confirmed = 67`
- `manual_review = 0`

当前 A_candidate query_key 分布：
- `hist_mw_summary = 43`
- `hist_mw_by_all_regions = 14`
- `hist_vehicle_type_trip_count = 8`
- `sys_mw_and_trip_count = 23`
- `sys_total_fee_by_filters = 21`
- `hist_customer_mw = 14`
- `sys_mw_by_procurement_type = 2`
- `hist_carrier_kpi_by_year = 2`

当前 B_candidate 澄清类别分布：
- `generic_clarification = 274`
- `procurement_metric_scope = 10`
- `vague_status = 4`
- `data_consistency_scope = 2`

当时分布判断：
- 迁移前正式总账为：`A=173 / B=246 / C=484 / D=0`
- 如果迁移建议全部接受，建议分布为：`A=300 / B=536 / C=67 / D=0`

当前结论：
- Round2 已完成旧 C 台账迁移复核；
- 但 `A_candidate=127` 不能直接宣称为稳定 A，必须先进入行为级回归；
- 下一步最合理的是建立 `C Round2 A_candidate 行为回归`。

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

当前结论：
- A_candidate 已真实调用 data-qa 主链路并进入后续精确断言复核；
- C2A-P3 复核发现其中 2 条预测题不应迁入 A，已回到 C 边界；
- 当前后续已经完成 903 正式总账迁移，125 条有效 A_candidate 已迁入 A 并分批进入精确断言。

### 23. 903 正式总账迁移更新已完成

当前本轮总账更新结果：
- C Round2 中已通过行为回归且通过 C2A 复核的 `125` 条 A_candidate 已迁入 A。
- C Round2 中 `290` 条 B_candidate 已迁入 B，并纳入后续澄清模板复检。
- `67` 条 C_confirmed 继续保持 C，另有 `2` 条预测题回到 C 边界。

当前 903 最新正式分布：
- `A = 298`
- `B = 536`
- `C = 69`
- `D = 0`

当前迁移明细：
- `A->A = 75`
- `B->A = 98`
- `B->B = 246`
- `B->C = 12`
- `C->A = 125`
- `C->B = 290`
- `C->C = 57`

当前治理池分布：
- `A-稳定增强池 = 298`
- `B-候选收口池 = 26`
- `B-长期澄清池 = 510`
- `C-边界观察池 = 69`
- `D-待业务/数据修订池 = 0`

当前结论：
- 903 正式总账已经吸收 C Round2 迁移复核和 A_candidate 行为回归结果；
- 后续不应再把这 125 条已验证 A_candidate 留在 C；
- 后续不应再把这 290 条 B_candidate 留在 C，而应进入澄清模板复检；
- 新迁入 A 的 125 条仍需持续纳入精确断言和固定复检，后续需要按业务价值继续补强剩余 A 尾项。

### 24. 903 迁移后 A/B 后续治理计划已建立

当前已完成：
- C Round2 新进 A `127` 条精确断言补强计划已建立。
- C Round2 B_candidate `290` 条澄清模板复检计划已建立。

新进 A 精确断言批次：
- `C2A-P1 = 30`
- `C2A-P2 = 30`
- `C2A-P3 = 30`
- `C2A-P4 = 37`

B_candidate 澄清模板复检批次：
- `BCR1 = 60`
- `BCR2 = 80`
- `BCR3 = 80`
- `BCR4 = 70`

当前计划边界：
- 本轮只是建立分批治理计划，不直接刷新 127 条黄金答案基线。
- B_candidate 仍必须稳定返回澄清，不允许误落 success。
- LLM 仍只允许做缺口径识别和追问候选生成，不能做最终边界裁决。

### 25. C2A-P1 精确断言 Round1 / BCR1 澄清模板复检 Round1 已完成

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

当前 BCR1 模板优化建议分布：
- `abnormal_or_reason_scope = 5`
- `transport_mode_metric_scope = 12`
- `procurement_metric_scope = 8`
- `route_or_address_scope = 33`

当时结论：
- C2A-P1 已完成第一批新进 A 精确断言基线，不再只是行为级可答。
- BCR1 已证明 60 条 B_candidate 没有误落 success 或 unsupported，澄清边界稳定。
- BCR1 初次复检发现 58 条仍需要把追问从通用模板升级为更业务化的缺口径追问。
- 该模板优化项已在后续 BCR1 业务化追问模板优化中完成固化。

### 26. BCR1 业务化追问模板优化 / C2A-P2 精确断言已完成

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
- 标准答案来源：当前 `logistics_ai` 数据快照，经正式 data-qa 主链路执行后固化。
- 断言字段：`status.code`、`query_plan.query_key`、`answer_summary`、`result_table.columns`、`result_table.rows`。

当前结论：
- BCR1 已从“识别出 58 条模板优化建议”推进到“60 条澄清边界稳定且模板缺口清零”。
- C2A-P2 已完成第二批新进 A 精确断言基线，不再只是行为级可答。
- 下一步不应重复做 BCR1 或 C2A-P2，建议进入 `BCR2` 澄清模板复检；如果目标优先是继续增强 A 精确基线，则进入 `C2A-P3`。

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

当前结论：
- BCR2 已证明 80 条 B_candidate 没有误落 success 或 unsupported，澄清边界稳定。
- `route_or_address_scope` 的 70 条已被当前线路 / 地址范围追问能力稳定兜住。
- 仍有 10 条需要把追问从通用模板升级为更业务化的缺口径追问。
- 下一步优先固化 BCR2 中 10 条业务化追问模板优化项；如果目标优先是继续增强 A 精确基线，再进入 `C2A-P3`。

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

当前具体固化内容：
- `system_state_scope`：补充系统状态枚举、指标口径、统计时间范围和分组维度追问。
- `data_consistency_scope`：补充对账对象、差异阈值、统计时间范围、比较维度和输出形态追问。
- `vehicle_or_trip_scope`：补充车次 / 车辆数口径、车型口径、统计月份和分组维度追问。
- LLM 澄清辅助白名单和题型提示同步补入 `system_state_scope`、`vehicle_or_trip_scope`。

当前结论：
- BCR2 已从“识别出 10 条模板优化建议”推进到“80 条澄清边界稳定且模板缺口清零”。
- 当前不需要重复执行 BCR2 固化动作。
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

当前处理结论：
- 这 2 条问题包含明确“预测未来”语义，按既定 B/C 边界应保持 `unsupported`，不应被历史区域汇总 query_key 固化为 A。
- 本轮已修正规则优先级，让 unsupported 策略先于高置信 A 类 query_key 生效，避免预测题误命中 `hist_mw_by_all_regions`。
- C Round2 A_candidate 行为回归同步从 `127/127` 修正为 `125/127`。
- 903 总账重算后最新分布修正为 `A=298 / B=536 / C=69 / D=0`。

当前已经进入 C2A-P3 精确基线的题型：
- `hist_carrier_kpi_by_year = 2`
- `hist_mw_by_all_regions = 12`
- `hist_vehicle_type_trip_count = 8`
- `hist_mw_summary = 6`

当前结论：
- C2A-P3 不是 `30/30`，而是 `28/30`。
- 失败项不是代码执行错误或数据基线变化，而是题目分层误判。
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

当前结论：
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
- 初次复检模板优化建议：`30`
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

当前结论：
- BCR3 已从“识别出 30 条模板优化建议”推进到“80 条澄清边界稳定且模板缺口清零”；
- 33 条 `generic_metric_scope` 当前追问方向可接受；
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

当前结论：
- BCR4 已证明 70 条 B_candidate 澄清边界稳定，没有误落 success 或 unsupported；
- 仍有 7 条需要把追问从“时间/指标/维度”进一步补齐到“输出形态”；
- 下一步应先固化 BCR4 中 7 条业务化追问模板优化项，再评估 B_candidate 队列是否阶段性完成。

---

## 三、当前业务边界

### 1. 当前物流一期数据范围
- 历史数据：2023–2025 年 Excel
- 正式系统数据：2026 年后的 MySQL 业务数据
- 2026 年前系统库记录视为测试数据，不纳入正式统计

### 2. 当前物流一期可靠能力
- 自然语言结构化数据问答
- 结构化聚合 / 排名 / 对比 / 部分明细查询
- A 类题自动回归
- B/C 响应策略
- B-长期澄清池业务化追问增强
- B-长期澄清池 Round2 业务化追问增强
- B-长期澄清池 Round3 业务化追问增强
- B-长期澄清池 Round4 业务化追问增强
- B-长期澄清池 Round5 收尾治理
- C-边界观察池治理评估
- C-边界观察池 Round1 拒答边界固化
- C-边界观察池 Round2 台账重算与迁移复核
- C Round2 A_candidate 行为回归
- 903 正式总账迁移更新
- C2A-P1 新进 A 精确断言 Round1
- C2A-P2 新进 A 精确断言 Round2
- C2A-P3 新进 A 精确断言 Round3（`28/30`，2 条预测题回到 C 边界）
- C2A-P4 新进 A 精确断言 Round4
- BCR1 B_candidate 澄清模板复检 Round1
- BCR1 业务化追问模板优化
- BCR2 B_candidate 澄清模板复检 Round2
- BCR2 业务化追问模板优化
- BCR3 B_candidate 澄清模板复检 Round3
- BCR3 业务化追问模板优化
- BCR4 B_candidate 澄清模板复检 Round4
- LLM Guardrail 受控增强
- Top200 高价值题分批收口

### 3. 当前明确不作为可靠能力的内容
- 仓库维度精确统计（当前按路线 1，不补 allocate）
- 预测类 / ETA / 开放讨论类问题
- 让 LLM 直接替换正式 planner
- 让 LLM 改写 B/C 边界
- 经营分析域正式开发

---

## 四、当前后端状态

### 1. 已具备的数据与查询主链路
- 历史 Excel 导入 ETL
- 2026+ 系统数据同步
- ODS / DWD / DWS / DM 分层
- logistics_ai 中间层查询
- 物流数据问答主链路

### 2. 已具备的题库治理能力
- 题库分层脚本与分类产物
- A 类 `75` 条行为级回归
- A 类关键题 `20` 条精确断言
- B/C 响应策略
- B-长期澄清池 Round1 / Round2 / Round3 / Round4 / Round5
- C-边界观察池治理评估
- 903 正式总账迁移更新
- C2A-P3 新进 A 精确断言 Round3
- C2A-P4 新进 A 精确断言 Round4
- BCR2 B_candidate 澄清模板复检 Round2
- BCR2 业务化追问模板优化
- BCR3 B_candidate 澄清模板复检 Round3
- BCR3 业务化追问模板优化
- BCR4 B_candidate 澄清模板复检 Round4
- Guardrail 受控接入
- Top200 路线图与 Round1 / Round2 / Round3 / Round4 / Round5 工厂化回归

### 3. 当前不回退的关键基线
- 关键题精确断言：`20/20`
- A 类行为级回归：`75/75`
- B/C 抽样边界：不回退
- Guardrail：不越权改写 B/C

---

## 五、当前前端状态

### 1. 已完成
- 物流数据问答前端正式页
- 独立历史页
- 回放
- CSV / XLSX 导出

### 2. 当前前端边界
当前前端已满足物流数据问答主线的联调和演示要求，但本阶段重点不再是继续扩前端，而是继续收口物流域高价值题库。

---

## 六、当前最合理下一步

当前最合理下一步是：

> **先固化 `BCR4` 中 7 条业务化追问模板优化项；如果优先补 A 稳定增强尾项，则处理剩余 3 条未精确断言 A 题。**

当前不建议：
- 直接跳入经营分析开发
- 进入经营分析开发
- 扩前端新页面
- 扩 RAG
- 扩 Agent
- 碰 BOM 主链路

---

## 七、当前已知未完成项

- 物流域 `903` 条题库尚未完全收口
- 当前全量 `903` 条题库最新正式分布为：
  - `A = 298`
  - `B = 536`
  - `C = 69`
  - `D = 0`
- Top200 高价值 B 题虽然已阶段性清零，但全量 `903` 条题库仍未完全收口
- Top200 当前为：
  - `A = 170`
  - `B = 0`
  - `C = 30`
- 当前下一阶段的主要治理对象，不再是新一轮高价值 B 批量收口，也不再是 C2A-P4 / BCR3 固化，而是：
  - `BCR4` 中 7 条业务化追问模板优化项
  - A-稳定增强尾项中剩余 `3` 条未精确断言 A 题

---

## 八、当前结论

当前可以明确说：

1. 物流数据问答 MVP 已收口
2. 题库分层结果（A/B/C）已建立
3. A 类 `75` 条行为级自动回归已成立
4. A 类关键题 `20` 条精确断言回归已成立
5. LLM 理解层 PoC 已完成
6. Guardrail 受控接入方案已落地
7. Top200 路线图已建立
8. Top200 高价值 B 题工厂化 Round1 已完成
9. Top200 高价值 B 题工厂化 Round2 已完成
10. Top200 高价值 B 题工厂化 Round3 已完成
11. Top200 高价值 B 题工厂化 Round4 已完成
12. Round4 结果：处理 `9` 条、推进进 A `2` 条、保留 B `6` 条、转入 C `1` 条
13. Top200 高价值 B 题工厂化 Round5 已完成
14. Round5 结果：处理 `6` 条、推进进 A `3` 条、保留 B `0` 条、转入 C `3` 条
15. Round4 / Round5 新进 A 题精确断言回归已完成
16. 本轮结果：总数 `5`、通过 `5`、失败 `0`
17. A-稳定增强池 Round1 / Round2 / Round3 已完成
18. A 池当前状态：`A_total=170 / A_precise=170 / A_non_precise=0`
19. 当前 Top200 分布：`A=170 / B=0 / C=30`
20. B-长期澄清池 Round2 已完成，结果：
   - `B-长期澄清池总量 = 230`
   - `Round1 选中 = 34`
   - `Round1 去重后唯一题 = 32`
   - `Round2 选中 = 37`
   - `Round2 剩余 = 159`
   - `live 样本 = 8`
   - `实际采用 LLM 业务化追问 = 8`
   - `边界保持 clarification = 37/37`
21. B-长期澄清池 Round3 已完成，结果：
   - `B-长期澄清池总量 = 230`
   - `Round1 选中 = 34`
   - `Round2 选中 = 37`
   - `Round3 选中 = 82`
   - `Round3 剩余 = 77`
   - `live 样本 = 10`
   - `实际采用 LLM 业务化追问 = 10`
   - `边界保持 clarification = 82/82`
22. B-长期澄清池 Round4 已完成，结果：
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
23. B-长期澄清池 Round5 已完成，结果：
   - `Round5 选中 = 30`
   - `保留 B = 20`
   - `推进进 A = 3`
   - `转入 C = 7`
   - `Round5 剩余 = 0`
24. C-边界观察池治理评估已完成，当前 `C=484`，建议正式进入治理动作
25. 迁移前 903 分布：`A=173 / B=246 / C=484 / D=0`
26. C-边界观察池 Round1 已完成：
   - `C 池总量 = 484`
   - `Round1 固化拒答 = 67`
   - `A_candidate = 127`
   - `B_candidate = 290`
27. C-边界观察池 Round2 已完成：
   - `Round2 复核总量 = 484`
   - `A_candidate = 127`
   - `B_candidate = 290`
   - `C_confirmed = 67`
   - 建议分布：`A=300 / B=536 / C=67 / D=0`
28. C Round2 A_candidate 行为回归已完成并在 C2A-P3 后复核修正：
   - 原始结果：`127 / 127 / 0`
   - 当前复核结果：`127 / 125 / 2`
   - 失败归因：`题目迁移误判 = 2`
29. 903 正式总账迁移更新已完成：
   - `C->A = 125`
   - `C->B = 290`
   - `C_confirmed = 69`
30. 当前 903 最新正式分布：`A=298 / B=536 / C=69 / D=0`
31. 903 迁移后 A/B 后续治理计划已建立：
   - `C2A-P1/P2/P3/P4 = 30/30/30/37`
   - `BCR1/BCR2/BCR3/BCR4 = 60/80/80/70`
32. C2A-P1 新进 A 精确断言 Round1 已完成：`30/30`
33. BCR1 B_candidate 澄清模板复检 Round1 已完成：澄清边界 `60/60`
34. BCR1 业务化追问模板优化已完成：模板优化建议从 `58` 降为 `0`
35. C2A-P2 新进 A 精确断言 Round2 已完成：`30/30`
36. BCR2 B_candidate 澄清模板复检 Round2 已完成：澄清边界 `80/80`，模板优化建议 `10`
37. BCR2 业务化追问模板优化已完成：模板优化建议从 `10` 降为 `0`
38. C2A-P3 新进 A 精确断言 Round3 已完成：`28/30`，2 条预测题回到 C 边界
39. C2A-P4 新进 A 精确断言 Round4 已完成：`37/37`
40. C2A 四批总体结果：`125` 条有效进入 A 精确断言，`2` 条预测题回到 C 边界
41. BCR3 B_candidate 澄清模板复检 Round3 已完成：澄清边界 `80/80`，初次模板优化建议 `30`
42. BCR3 业务化追问模板优化已完成：模板优化建议从 `30` 降为 `0`
43. BCR4 B_candidate 澄清模板复检 Round4 已完成：澄清边界 `70/70`，模板优化建议 `7`
44. 当前最合理下一步是：先固化 `BCR4` 中 7 条业务化追问模板优化项；如果优先补 A 稳定增强尾项，则处理剩余 3 条未精确断言 A 题

但同样必须明确：

> **物流数据问答主链路已收口，不等于物流域全量题库已经收口。**

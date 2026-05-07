# B_candidate 澄清模板复检计划

## 一、结论

C Round2 迁入 B 的 B_candidate 共 `290` 条，已全部纳入后续澄清模板复检。
本轮不把 B_candidate 改成 success，也不让 LLM 改写 B/C 边界。

## 二、批次安排

- `BCR1`：Round1：异常/运输方式/采购高频澄清，`60` 条
- `BCR2`：Round2：线路/系统状态/数据一致性澄清，`80` 条
- `BCR3`：Round3：车型/客户/排名澄清，`80` 条
- `BCR4`：Round4：通用指标口径澄清收尾，`70` 条

## 三、复检题型分布

- `abnormal_or_reason_scope`：`5`
- `transport_mode_metric_scope`：`12`
- `procurement_metric_scope`：`10`
- `route_or_address_scope`：`103`
- `system_state_scope`：`1`
- `data_consistency_scope`：`2`
- `vehicle_or_trip_scope`：`37`
- `customer_project_scope`：`14`
- `ranking_basis_scope`：`3`
- `generic_metric_scope`：`103`

## 四、复检规则

- 规则层仍然是最终边界裁决者。
- LLM 只允许做缺口径识别和追问候选生成。
- 每题必须稳定返回 `needs_clarification=true`。
- 不允许误落 success，也不允许误落 unsupported。

## 五、第一批代表题

| review_id | 题号 | 复检题型 | 需检查缺口径 | 问题 |
| --- | --- | --- | --- | --- |
| BCR-001 | Q321 | abnormal_or_reason_scope | 统计时间范围；异常/高成本定义；输出形态；是否需要明细 | 对PREASSIGN状态且超过3天未流转的任务进行风险分层，哪些任务最值得优先关注？ |
| BCR-002 | Q322 | abnormal_or_reason_scope | 统计时间范围；异常/高成本定义；输出形态；是否需要明细 | 同一车牌短时间内关联高频多任务，是否可能存在外协运力异常或数据录入复用？ |
| BCR-003 | Q086 | abnormal_or_reason_scope | 统计时间范围；异常/高成本定义；输出形态；是否需要明细 | 识别合肥始发地在历史数据中可能存在的异常高成本运输记录，并解释异常原因。 |
| BCR-004 | Q087 | abnormal_or_reason_scope | 统计时间范围；异常/高成本定义；输出形态；是否需要明细 | 识别阜宁始发地在历史数据中可能存在的异常高成本运输记录，并解释异常原因。 |
| BCR-005 | Q088 | abnormal_or_reason_scope | 统计时间范围；异常/高成本定义；输出形态；是否需要明细 | 识别广德始发地在历史数据中可能存在的异常高成本运输记录，并解释异常原因。 |
| BCR-006 | Q328 | transport_mode_metric_scope | 统计时间范围；运输方式口径；指标口径；单位口径 | 历史水路与铁路样本较少的情况下，是否值得在更多线路上推广替代运输方式？ |
| BCR-007 | Q238 | transport_mode_metric_scope | 统计时间范围；运输方式口径；指标口径；单位口径 | 2024年华东区域通过公路发运的总件数是多少？ |
| BCR-008 | Q239 | transport_mode_metric_scope | 统计时间范围；运输方式口径；指标口径；单位口径 | 2025年西南区域通过铁路发运的总费用是多少？ |
| BCR-009 | Q315 | transport_mode_metric_scope | 统计时间范围；运输方式口径；指标口径；单位口径 | 若铁路资源增加10%，哪些省份最适合从公路切换到铁路以降低成本？ |
| BCR-010 | SQ289 | transport_mode_metric_scope | 统计时间范围；运输方式口径；指标口径；单位口径 | 2024年公路运输的总发运量是多少MW？ |

## 六、下一步

建议优先执行 `BCR1`，复检 60 条高频澄清题，重点优化异常、运输方式、采购方式等业务化追问模板。

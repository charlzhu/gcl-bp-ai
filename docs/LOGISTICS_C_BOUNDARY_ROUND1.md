# C-边界观察池 Round1：拒答边界与业务理由固化

## 一、结论

本轮正式进入 `C-边界观察池` 治理动作，但没有把全部旧 C 题一刀切拒答。
Round1 只固化当前规则层已经明确判定为不支持的边界，并补齐业务可理解原因和可改问方向。

## 二、本轮统计

- C 池总量：`484`
- Round1 已固化拒答：`67`
- 已具备业务化原因和可改问建议：`67`
- 需台账重算 / 迁移复核：`417`
- 其他 unsupported 复核：`0`
- 人工复核：`0`

## 三、Round1 固化的拒答类别

- `clarification_design`
- `correlation_analysis`
- `discussion`
- `eta`
- `extra_fee_detail`
- `forecast`
- `high_fee_address_procurement_split`
- `project_name_dimension`
- `supplier_price_diagnostic`
- `system_response_strategy`
- `warehouse_dimension_unreliable`

## 四、关键边界

- 预测、ETA、开放讨论、系统策略、相关性诊断、额外费用明细等继续稳定拒答。
- 仓库维度仍按一期路线 1 处理：暂不补 allocate 链路，不把仓库维度作为可靠统计维度。
- 旧 C 中当前 planner 已能命中 query_key 的题，不在本轮拒答，应进入后续台账重算和精确断言评估。
- 旧 C 中当前 planner 返回澄清的题，也不在本轮拒答，应后续复核是否迁入 B。

## 五、下一步建议

下一步建议做 `C-边界观察池 Round2`，优先处理本报告里的 `ledger_recheck` 项：把当前已可答的旧 C 题迁入 A 候选，把应澄清的旧 C 题迁入 B 候选，避免 903 总账长期携带旧分类误差。

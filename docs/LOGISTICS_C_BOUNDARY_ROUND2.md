# C-边界观察池 Round2：旧 C 台账重算与迁移复核

## 一、结论

Round2 已对 C Round1 识别出的旧 C 池题目重新按当前 planner 行为做迁移复核。
本轮没有把 A_candidate 直接宣布为稳定 A，而是形成迁移建议和后续回归要求。

## 二、迁移复核结果

- Round1 C 池总量：`484`
- Round2 复核总量：`484`
- A_candidate：`127`
- B_candidate：`290`
- C_confirmed：`67`
- manual_review：`0`

## 三、分布重算

- 当前正式总账分布：`{'A': 173, 'B': 246, 'C': 484, 'D': 0}`
- 若迁移建议全部接受后的建议分布：`{'A': 300, 'B': 536, 'C': 67, 'D': 0}`

## 四、A_candidate query_key 分布

- `hist_mw_summary`：`43`
- `hist_mw_by_all_regions`：`14`
- `hist_vehicle_type_trip_count`：`8`
- `sys_mw_and_trip_count`：`23`
- `sys_total_fee_by_filters`：`21`
- `hist_customer_mw`：`14`
- `sys_mw_by_procurement_type`：`2`
- `hist_carrier_kpi_by_year`：`2`

## 五、B_candidate 澄清类别分布

- `vague_status`：`4`
- `generic_clarification`：`274`
- `data_consistency_scope`：`2`
- `procurement_metric_scope`：`10`

## 六、迁移原则

- `A_candidate`：当前 planner 已能命中 query_key，但必须先进入行为级回归；高价值题再进入精确断言。
- `B_candidate`：当前 planner 返回澄清，应迁回 B 类治理，不应继续留在 C 池。
- `C_confirmed`：继续保持 unsupported，并沿用 C Round1 的业务化拒答原因和可改问建议。

## 七、下一步建议

下一步建议先做 `C Round2 A_candidate 行为回归`，把 127 条当前已可答题跑成可复检结果；通过后再决定是否更新 903 正式总账分布。

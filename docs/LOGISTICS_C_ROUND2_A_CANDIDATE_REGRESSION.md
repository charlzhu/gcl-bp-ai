# C Round2 A_candidate 行为回归

## 一、结论

本轮对 C Round2 识别出的 A_candidate 共 `127` 条做真实 data-qa 行为回归，通过 `125` 条，失败 `2` 条。

## 二、断言规则

- 实际 query_key 必须与 Round2 迁移复核识别出的 query_key 一致。
- 状态码必须为 `OK`。
- 不允许返回澄清态。
- 不允许返回不支持态。
- 结果表必须非空。

## 三、query_key 分布

- `hist_mw_summary`：`43`
- `hist_mw_by_all_regions`：`12`
- `hist_vehicle_type_trip_count`：`8`
- `sys_mw_and_trip_count`：`23`
- `sys_total_fee_by_filters`：`21`
- `hist_customer_mw`：`14`
- `sys_mw_by_procurement_type`：`2`
- `hist_carrier_kpi_by_year`：`2`
- `None`：`2`

## 四、失败归因

- `题目迁移误判`：`2`

## 五、下一步建议

仅通过题可进入正式 A 迁移候选；失败题继续留在复核池，不能直接更新为稳定 A。

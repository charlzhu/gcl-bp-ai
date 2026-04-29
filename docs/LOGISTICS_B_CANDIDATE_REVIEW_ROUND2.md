# BCR2 B_candidate 澄清模板复检

## 一、结论

BCR2 共复检 **80** 条 B_candidate，澄清边界通过 **80** 条，失败 **0** 条。
其中建议优化业务化追问模板 **0** 条。

## 二、边界规则

- 每题必须稳定返回 `needs_clarification=true`。
- 不允许误命中 query_key 后变成 success。
- 不允许误落 unsupported。
- LLM 只能做缺口径识别和追问候选生成，不能做最终边界裁决。
- 本次复检 live LLM 调用：`关闭`；默认关闭以稳定验证规则模板覆盖。

## 三、复检题型分布

- `route_or_address_scope`：`70`
- `system_state_scope`：`1`
- `data_consistency_scope`：`2`
- `vehicle_or_trip_scope`：`7`

## 四、失败项

- 当前无边界失败项。

## 五、建议优化模板的代表题

- 当前无建议优化项。

## 六、下一步

- 若边界失败为 0，可继续把模板优化项分批固化到规则层或 LLM 候选追问层。
- 若存在边界失败，必须先修复规则层，不能进入模板美化。

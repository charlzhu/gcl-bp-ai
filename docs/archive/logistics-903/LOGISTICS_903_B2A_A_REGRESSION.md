# 903 B->A 新增 A 行为回归

生成时间：2026-04-27T11:21:20

## 一、结论

本轮新增 A 行为回归共 `85` 条，通过 `85` 条，失败 `0` 条。

## 二、回归规则

- 真实调用当前物流 data-qa 主链路。
- 要求 query_key 命中预期。
- 要求状态码 OK、supported=true、needs_clarification=false。
- 要求结果表非空。

## 三、query_key 分布

- `hist_total_fee_summary`：`78`
- `sys_total_fee_by_filters`：`4`
- `sys_mw_and_trip_count`：`3`

## 四、未通过题

- 当前无未通过题。

## 五、代表题

| 题号 | query_key | 问题 |
| --- | --- | --- |
| SQ003 | hist_total_fee_summary | 2023年华东区域总运费是多少？ |
| SQ007 | hist_total_fee_summary | 2023年华南区域总运费是多少？ |
| SQ425 | hist_total_fee_summary | 2024年客户华阳总运费是多少？ |
| SQ011 | hist_total_fee_summary | 2023年华中区域总运费是多少？ |
| SQ427 | hist_total_fee_summary | 2024年客户创维客户总运费是多少？ |
| SQ493 | hist_total_fee_summary | 2025年经营计划场景下的总运费是多少？ |
| SQ015 | hist_total_fee_summary | 2023年华北区域总运费是多少？ |
| SQ429 | hist_total_fee_summary | 2024年客户海南创维新能源投资有限公司总运费是多少？ |
| SQ019 | hist_total_fee_summary | 2023年西南区域总运费是多少？ |
| SQ023 | hist_total_fee_summary | 2023年西北区域总运费是多少？ |
| SQ433 | hist_total_fee_summary | 2024年客户华润新能源（皮山）有限公司总运费是多少？ |
| SQ496 | hist_total_fee_summary | 2025年辅料送样场景下的总运费是多少？ |
| SQ027 | hist_total_fee_summary | 2024年华东区域总运费是多少？ |
| SQ435 | hist_total_fee_summary | 2024年客户国科新能源有限公司总运费是多少？ |
| SQ031 | hist_total_fee_summary | 2024年华南区域总运费是多少？ |

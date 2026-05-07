# 903 B->A 迁移更新与新增 A 回归计划

生成时间：2026-04-26T14:23:37

## 一、结论

- 本轮基于 86 条 B->A 直接候选复核结果，正式迁入 A：`85` 条。
- 保持 B：`1` 条，原因是数据基线阻塞。
- 迁移后 903 总账分布：`{'A': 383, 'B': 451, 'C': 69, 'D': 0}`。
- 新增 A 行为回归题集：`85` 条。
- 新增 A 精确断言计划：`85` 条，分 3 批推进。

## 二、迁移原则

- 只迁移上一轮真实 data-qa 主链路行为复核通过的题。
- 原题必须当前仍在 B，且 query_key 与复核记录一致。
- 补槽后可答但原题仍缺口径的题不迁入 A。
- 数据基线阻塞题不迁入 A。

## 三、query_key 分布

- `hist_total_fee_summary`：`78`
- `sys_total_fee_by_filters`：`4`
- `sys_mw_and_trip_count`：`3`

## 四、精确断言批次

- `B2A-P1`：Round1：系统侧与高价值费用题，`25` 条
- `B2A-P2`：Round2：历史区域/客户/运输方式费用题，`30` 条
- `B2A-P3`：Round3：历史总运费批量收尾题，`30` 条

## 五、代表迁移题

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

## 六、已完成验证与下一步

- 85 条新增 A 行为回归已完成，结果 `85/85`，迁移后的固定保护已建立。
- 先执行 `B2A-P1` 精确断言，随后推进 `B2A-P2` / `B2A-P3`。
- 结合 441 条 B 缺口路线图，优先补 P1 query_key_gap 题族。

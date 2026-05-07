# 903 A 类精确断言增强 Wave3 Batch1

生成时间：2026-04-27T11:21:17

## 一、覆盖统计

- 当前 A 总数：`652`
- 批次前已精确断言覆盖：`380`
- 批次前未覆盖 A：`272`
- 可直接进入精确断言候选：`272`

## 二、本批回归结论

- 本批题数：`30`
- 通过：`30`
- 失败：`0`
- query_key 分布：`{'hist_quarter_region_metric': 24, 'hist_high_fee_addresses_by_customer': 6}`

## 三、标准答案来源与断言口径

- 标准答案来源：当前 `logistics_ai` 数据快照，经正式 data-qa 主链路执行后固化。
- 断言字段：`status.code`、`query_plan.query_key`、`answer_summary`、`result_table.columns`、`result_table.rows`。
- 失败归因：query_key/status/columns 异常归为代码问题；answer_summary/rows 变化归为数据基线变化；预期 A 题进入澄清或不支持归为分层误判。

## 四、题目清单

| plan_id | 题号 | query_key | 问题 |
| --- | --- | --- | --- |
| A-W3-P1-001 | SQ146 | hist_quarter_region_metric | 2023年一季度各区域运费分别是多少？请按区域排序展示。 |
| A-W3-P1-002 | SQ147 | hist_quarter_region_metric | 2023年一季度各区域单瓦运输成本分别是多少？ |
| A-W3-P1-003 | SQ149 | hist_quarter_region_metric | 2023年二季度各区域运费分别是多少？请按区域排序展示。 |
| A-W3-P1-004 | SQ150 | hist_quarter_region_metric | 2023年二季度各区域单瓦运输成本分别是多少？ |
| A-W3-P1-005 | SQ152 | hist_quarter_region_metric | 2023年三季度各区域运费分别是多少？请按区域排序展示。 |
| A-W3-P1-006 | SQ153 | hist_quarter_region_metric | 2023年三季度各区域单瓦运输成本分别是多少？ |
| A-W3-P1-007 | SQ155 | hist_quarter_region_metric | 2023年四季度各区域运费分别是多少？请按区域排序展示。 |
| A-W3-P1-008 | SQ156 | hist_quarter_region_metric | 2023年四季度各区域单瓦运输成本分别是多少？ |
| A-W3-P1-009 | SQ158 | hist_quarter_region_metric | 2024年一季度各区域运费分别是多少？请按区域排序展示。 |
| A-W3-P1-010 | SQ159 | hist_quarter_region_metric | 2024年一季度各区域单瓦运输成本分别是多少？ |
| A-W3-P1-011 | SQ161 | hist_quarter_region_metric | 2024年二季度各区域运费分别是多少？请按区域排序展示。 |
| A-W3-P1-012 | SQ162 | hist_quarter_region_metric | 2024年二季度各区域单瓦运输成本分别是多少？ |
| A-W3-P1-013 | SQ164 | hist_quarter_region_metric | 2024年三季度各区域运费分别是多少？请按区域排序展示。 |
| A-W3-P1-014 | SQ165 | hist_quarter_region_metric | 2024年三季度各区域单瓦运输成本分别是多少？ |
| A-W3-P1-015 | SQ167 | hist_quarter_region_metric | 2024年四季度各区域运费分别是多少？请按区域排序展示。 |
| A-W3-P1-016 | SQ168 | hist_quarter_region_metric | 2024年四季度各区域单瓦运输成本分别是多少？ |
| A-W3-P1-017 | SQ170 | hist_quarter_region_metric | 2025年一季度各区域运费分别是多少？请按区域排序展示。 |
| A-W3-P1-018 | SQ171 | hist_quarter_region_metric | 2025年一季度各区域单瓦运输成本分别是多少？ |
| A-W3-P1-019 | SQ173 | hist_quarter_region_metric | 2025年二季度各区域运费分别是多少？请按区域排序展示。 |
| A-W3-P1-020 | SQ174 | hist_quarter_region_metric | 2025年二季度各区域单瓦运输成本分别是多少？ |
| A-W3-P1-021 | SQ176 | hist_quarter_region_metric | 2025年三季度各区域运费分别是多少？请按区域排序展示。 |
| A-W3-P1-022 | SQ177 | hist_quarter_region_metric | 2025年三季度各区域单瓦运输成本分别是多少？ |
| A-W3-P1-023 | SQ179 | hist_quarter_region_metric | 2025年四季度各区域运费分别是多少？请按区域排序展示。 |
| A-W3-P1-024 | SQ180 | hist_quarter_region_metric | 2025年四季度各区域单瓦运输成本分别是多少？ |
| A-W3-P1-025 | SQ466 | hist_high_fee_addresses_by_customer | 2024年客户华阳发货的项目地中，哪些收货地址的运费超过20万元？ |
| A-W3-P1-026 | SQ468 | hist_high_fee_addresses_by_customer | 2024年客户创维客户发货的项目地中，哪些收货地址的运费超过20万元？ |
| A-W3-P1-027 | SQ470 | hist_high_fee_addresses_by_customer | 2024年客户海南创维新能源投资有限公司发货的项目地中，哪些收货地址的运费超过20万元？ |
| A-W3-P1-028 | SQ472 | hist_high_fee_addresses_by_customer | 2024年客户广东粤电阳西新能源有限公司发货的项目地中，哪些收货地址的运费超过20万元？ |
| A-W3-P1-029 | SQ474 | hist_high_fee_addresses_by_customer | 2024年客户华润新能源（皮山）有限公司发货的项目地中，哪些收货地址的运费超过20万元？ |
| A-W3-P1-030 | SQ476 | hist_high_fee_addresses_by_customer | 2025年客户华阳发货的项目地中，哪些收货地址的运费超过20万元？ |

## 五、未通过题

- 当前无未通过题。

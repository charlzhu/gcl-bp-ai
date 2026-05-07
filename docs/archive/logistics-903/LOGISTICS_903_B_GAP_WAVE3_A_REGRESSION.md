# 903 B->A 新增 A 行为回归

生成时间：2026-04-27T00:37:50

## 一、结论

本轮新增 A 行为回归共 `24` 条，通过 `24` 条，失败 `0` 条。

## 二、回归规则

- 真实调用当前物流 data-qa 主链路。
- 要求 query_key 命中预期。
- 要求状态码 OK、supported=true、needs_clarification=false。
- 要求结果表非空。

## 三、query_key 分布

- `hist_quarter_region_metric`：`24`

## 四、未通过题

- 当前无未通过题。

## 五、代表题

| 题号 | query_key | 问题 |
| --- | --- | --- |
| SQ146 | hist_quarter_region_metric | 2023年一季度各区域运费分别是多少？请按区域排序展示。 |
| SQ147 | hist_quarter_region_metric | 2023年一季度各区域单瓦运输成本分别是多少？ |
| SQ149 | hist_quarter_region_metric | 2023年二季度各区域运费分别是多少？请按区域排序展示。 |
| SQ150 | hist_quarter_region_metric | 2023年二季度各区域单瓦运输成本分别是多少？ |
| SQ152 | hist_quarter_region_metric | 2023年三季度各区域运费分别是多少？请按区域排序展示。 |
| SQ153 | hist_quarter_region_metric | 2023年三季度各区域单瓦运输成本分别是多少？ |
| SQ155 | hist_quarter_region_metric | 2023年四季度各区域运费分别是多少？请按区域排序展示。 |
| SQ156 | hist_quarter_region_metric | 2023年四季度各区域单瓦运输成本分别是多少？ |
| SQ158 | hist_quarter_region_metric | 2024年一季度各区域运费分别是多少？请按区域排序展示。 |
| SQ159 | hist_quarter_region_metric | 2024年一季度各区域单瓦运输成本分别是多少？ |
| SQ161 | hist_quarter_region_metric | 2024年二季度各区域运费分别是多少？请按区域排序展示。 |
| SQ162 | hist_quarter_region_metric | 2024年二季度各区域单瓦运输成本分别是多少？ |
| SQ164 | hist_quarter_region_metric | 2024年三季度各区域运费分别是多少？请按区域排序展示。 |
| SQ165 | hist_quarter_region_metric | 2024年三季度各区域单瓦运输成本分别是多少？ |
| SQ167 | hist_quarter_region_metric | 2024年四季度各区域运费分别是多少？请按区域排序展示。 |

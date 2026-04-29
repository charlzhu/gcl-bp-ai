# 903 A 类精确断言增强 Batch4

生成时间：2026-04-27T11:20:28

## 一、覆盖统计

- 当前 A 总数：`656`
- 批次前已精确断言覆盖：`480`
- 批次前未覆盖 A：`176`
- 可直接进入精确断言候选：`176`

## 二、本批回归结论

- 本批题数：`50`
- 通过：`50`
- 失败：`0`
- query_key 分布：`{'hist_route_aggregate_summary': 50}`

## 三、标准答案来源与断言口径

- 标准答案来源：当前 `logistics_ai` 数据快照，经正式 data-qa 主链路执行后固化。
- 断言字段：`status.code`、`query_plan.query_key`、`answer_summary`、`result_table.columns`、`result_table.rows`。
- 失败归因：query_key/status/columns 异常归为代码问题；answer_summary/rows 变化归为数据基线变化；A 题进入澄清或不支持归为分层误判。

## 四、题目清单

| plan_id | 题号 | query_key | 问题 |
| --- | --- | --- | --- |
| A-ACCEPT-B4-001 | SQ192 | hist_route_aggregate_summary | 2023年合肥基地发往广西壮族自治区的总发运量是多少MW？ |
| A-ACCEPT-B4-002 | SQ193 | hist_route_aggregate_summary | 2023年阜宁基地发往江苏省的平均运费是多少？ |
| A-ACCEPT-B4-003 | SQ194 | hist_route_aggregate_summary | 2023年阜宁基地发往江苏省的总发运量是多少MW？ |
| A-ACCEPT-B4-004 | SQ195 | hist_route_aggregate_summary | 2023年阜宁基地发往浙江省的平均运费是多少？ |
| A-ACCEPT-B4-005 | SQ196 | hist_route_aggregate_summary | 2023年阜宁基地发往浙江省的总发运量是多少MW？ |
| A-ACCEPT-B4-006 | SQ197 | hist_route_aggregate_summary | 2023年阜宁基地发往上海市的平均运费是多少？ |
| A-ACCEPT-B4-007 | SQ198 | hist_route_aggregate_summary | 2023年阜宁基地发往上海市的总发运量是多少MW？ |
| A-ACCEPT-B4-008 | SQ199 | hist_route_aggregate_summary | 2023年阜宁基地发往安徽省的平均运费是多少？ |
| A-ACCEPT-B4-009 | SQ200 | hist_route_aggregate_summary | 2023年阜宁基地发往安徽省的总发运量是多少MW？ |
| A-ACCEPT-B4-010 | SQ201 | hist_route_aggregate_summary | 2023年阜宁基地发往广东省的平均运费是多少？ |
| A-ACCEPT-B4-011 | SQ202 | hist_route_aggregate_summary | 2023年阜宁基地发往广东省的总发运量是多少MW？ |
| A-ACCEPT-B4-012 | SQ203 | hist_route_aggregate_summary | 2023年阜宁基地发往广西壮族自治区的平均运费是多少？ |
| A-ACCEPT-B4-013 | SQ204 | hist_route_aggregate_summary | 2023年阜宁基地发往广西壮族自治区的总发运量是多少MW？ |
| A-ACCEPT-B4-014 | SQ205 | hist_route_aggregate_summary | 2024年合肥基地发往江苏省的平均运费是多少？ |
| A-ACCEPT-B4-015 | SQ206 | hist_route_aggregate_summary | 2024年合肥基地发往江苏省的总发运量是多少MW？ |
| A-ACCEPT-B4-016 | SQ207 | hist_route_aggregate_summary | 2024年合肥基地发往浙江省的平均运费是多少？ |
| A-ACCEPT-B4-017 | SQ208 | hist_route_aggregate_summary | 2024年合肥基地发往浙江省的总发运量是多少MW？ |
| A-ACCEPT-B4-018 | SQ209 | hist_route_aggregate_summary | 2024年合肥基地发往上海市的平均运费是多少？ |
| A-ACCEPT-B4-019 | SQ210 | hist_route_aggregate_summary | 2024年合肥基地发往上海市的总发运量是多少MW？ |
| A-ACCEPT-B4-020 | SQ211 | hist_route_aggregate_summary | 2024年合肥基地发往安徽省的平均运费是多少？ |
| A-ACCEPT-B4-021 | SQ212 | hist_route_aggregate_summary | 2024年合肥基地发往安徽省的总发运量是多少MW？ |
| A-ACCEPT-B4-022 | SQ213 | hist_route_aggregate_summary | 2024年合肥基地发往广东省的平均运费是多少？ |
| A-ACCEPT-B4-023 | SQ214 | hist_route_aggregate_summary | 2024年合肥基地发往广东省的总发运量是多少MW？ |
| A-ACCEPT-B4-024 | SQ215 | hist_route_aggregate_summary | 2024年合肥基地发往广西壮族自治区的平均运费是多少？ |
| A-ACCEPT-B4-025 | SQ216 | hist_route_aggregate_summary | 2024年合肥基地发往广西壮族自治区的总发运量是多少MW？ |
| A-ACCEPT-B4-026 | SQ217 | hist_route_aggregate_summary | 2024年阜宁基地发往江苏省的平均运费是多少？ |
| A-ACCEPT-B4-027 | SQ218 | hist_route_aggregate_summary | 2024年阜宁基地发往江苏省的总发运量是多少MW？ |
| A-ACCEPT-B4-028 | SQ219 | hist_route_aggregate_summary | 2024年阜宁基地发往浙江省的平均运费是多少？ |
| A-ACCEPT-B4-029 | SQ220 | hist_route_aggregate_summary | 2024年阜宁基地发往浙江省的总发运量是多少MW？ |
| A-ACCEPT-B4-030 | SQ221 | hist_route_aggregate_summary | 2024年阜宁基地发往上海市的平均运费是多少？ |
| A-ACCEPT-B4-031 | SQ222 | hist_route_aggregate_summary | 2024年阜宁基地发往上海市的总发运量是多少MW？ |
| A-ACCEPT-B4-032 | SQ223 | hist_route_aggregate_summary | 2024年阜宁基地发往安徽省的平均运费是多少？ |
| A-ACCEPT-B4-033 | SQ224 | hist_route_aggregate_summary | 2024年阜宁基地发往安徽省的总发运量是多少MW？ |
| A-ACCEPT-B4-034 | SQ225 | hist_route_aggregate_summary | 2024年阜宁基地发往广东省的平均运费是多少？ |
| A-ACCEPT-B4-035 | SQ226 | hist_route_aggregate_summary | 2024年阜宁基地发往广东省的总发运量是多少MW？ |
| A-ACCEPT-B4-036 | SQ227 | hist_route_aggregate_summary | 2024年阜宁基地发往广西壮族自治区的平均运费是多少？ |
| A-ACCEPT-B4-037 | SQ228 | hist_route_aggregate_summary | 2024年阜宁基地发往广西壮族自治区的总发运量是多少MW？ |
| A-ACCEPT-B4-038 | SQ229 | hist_route_aggregate_summary | 2025年合肥基地发往江苏省的平均运费是多少？ |
| A-ACCEPT-B4-039 | SQ230 | hist_route_aggregate_summary | 2025年合肥基地发往江苏省的总发运量是多少MW？ |
| A-ACCEPT-B4-040 | SQ231 | hist_route_aggregate_summary | 2025年合肥基地发往浙江省的平均运费是多少？ |
| A-ACCEPT-B4-041 | SQ232 | hist_route_aggregate_summary | 2025年合肥基地发往浙江省的总发运量是多少MW？ |
| A-ACCEPT-B4-042 | SQ233 | hist_route_aggregate_summary | 2025年合肥基地发往上海市的平均运费是多少？ |
| A-ACCEPT-B4-043 | SQ234 | hist_route_aggregate_summary | 2025年合肥基地发往上海市的总发运量是多少MW？ |
| A-ACCEPT-B4-044 | SQ235 | hist_route_aggregate_summary | 2025年合肥基地发往安徽省的平均运费是多少？ |
| A-ACCEPT-B4-045 | SQ236 | hist_route_aggregate_summary | 2025年合肥基地发往安徽省的总发运量是多少MW？ |
| A-ACCEPT-B4-046 | SQ237 | hist_route_aggregate_summary | 2025年合肥基地发往广东省的平均运费是多少？ |
| A-ACCEPT-B4-047 | SQ238 | hist_route_aggregate_summary | 2025年合肥基地发往广东省的总发运量是多少MW？ |
| A-ACCEPT-B4-048 | SQ239 | hist_route_aggregate_summary | 2025年合肥基地发往广西壮族自治区的平均运费是多少？ |
| A-ACCEPT-B4-049 | SQ240 | hist_route_aggregate_summary | 2025年合肥基地发往广西壮族自治区的总发运量是多少MW？ |
| A-ACCEPT-B4-050 | SQ241 | hist_route_aggregate_summary | 2025年阜宁基地发往江苏省的平均运费是多少？ |

## 五、未通过题

- 当前无未通过题。

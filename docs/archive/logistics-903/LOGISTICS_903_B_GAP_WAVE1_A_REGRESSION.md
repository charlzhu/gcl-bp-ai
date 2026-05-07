# 903 B->A 新增 A 行为回归

生成时间：2026-04-27T00:37:52

## 一、结论

本轮新增 A 行为回归共 `184` 条，通过 `184` 条，失败 `0` 条。

## 二、回归规则

- 真实调用当前物流 data-qa 主链路。
- 要求 query_key 命中预期。
- 要求状态码 OK、supported=true、needs_clarification=false。
- 要求结果表非空。

## 三、query_key 分布

- `hist_monthly_trip_count_summary`：`24`
- `hist_route_aggregate_summary`：`132`
- `hist_origin_vehicle_metric_summary`：`24`
- `hist_vehicle_type_trip_count`：`4`

## 四、未通过题

- 当前无未通过题。

## 五、代表题

| 题号 | query_key | 问题 |
| --- | --- | --- |
| SQ075 | hist_monthly_trip_count_summary | 2024年1月份总车次是多少？ |
| SQ078 | hist_monthly_trip_count_summary | 2024年2月份总车次是多少？ |
| SQ081 | hist_monthly_trip_count_summary | 2024年3月份总车次是多少？ |
| SQ084 | hist_monthly_trip_count_summary | 2024年4月份总车次是多少？ |
| SQ087 | hist_monthly_trip_count_summary | 2024年5月份总车次是多少？ |
| SQ090 | hist_monthly_trip_count_summary | 2024年6月份总车次是多少？ |
| SQ093 | hist_monthly_trip_count_summary | 2024年7月份总车次是多少？ |
| SQ096 | hist_monthly_trip_count_summary | 2024年8月份总车次是多少？ |
| SQ099 | hist_monthly_trip_count_summary | 2024年9月份总车次是多少？ |
| SQ102 | hist_monthly_trip_count_summary | 2024年10月份总车次是多少？ |
| SQ105 | hist_monthly_trip_count_summary | 2024年11月份总车次是多少？ |
| SQ108 | hist_monthly_trip_count_summary | 2024年12月份总车次是多少？ |
| SQ111 | hist_monthly_trip_count_summary | 2025年1月份总车次是多少？ |
| SQ114 | hist_monthly_trip_count_summary | 2025年2月份总车次是多少？ |
| SQ117 | hist_monthly_trip_count_summary | 2025年3月份总车次是多少？ |

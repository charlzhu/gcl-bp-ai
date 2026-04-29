# 903 B->A 新增 A 行为回归

生成时间：2026-04-27T00:38:23

## 一、结论

本轮新增 A 行为回归共 `4` 条，通过 `4` 条，失败 `0` 条。

## 二、回归规则

- 真实调用当前物流 data-qa 主链路。
- 要求 query_key 命中预期。
- 要求状态码 OK、supported=true、needs_clarification=false。
- 要求结果表非空。

## 三、query_key 分布

- `hist_total_fee_summary`：`4`

## 四、未通过题

- 当前无未通过题。

## 五、代表题

| 题号 | query_key | 问题 |
| --- | --- | --- |
| SQ431 | hist_total_fee_summary | 2024年客户广东粤电阳西新能源有限公司总运费是多少？ |
| SQ437 | hist_total_fee_summary | 2024年客户江苏苏美达电力运营有限公司总运费是多少？ |
| SQ445 | hist_total_fee_summary | 2025年客户广东粤电阳西新能源有限公司总运费是多少？ |
| SQ451 | hist_total_fee_summary | 2025年客户江苏苏美达电力运营有限公司总运费是多少？ |

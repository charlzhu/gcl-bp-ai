# PLAN_BOM_ACCEPTANCE_REPORT

## 验收结论

- 当前是否可以进入小范围业务试运行：`True`
- 当前分布：`A=86 / B=40 / C=3 / D=0`
- 正式问题：`BOM问题.xlsx`，有效问题 `129` 条
- 真实 BOM 数据：`34` 个 Excel，`4034` 条材料行

## 聚合验收结果

| 项目 | 结果 |
| --- | --- |
| 源数据解析 | `34/34` Excel，材料 `4034` 行 |
| 上传接口 | `passed=True`，route_registered=`True` |
| QA API E2E | `30/30` |
| NLU live | 调用 `129`，采纳 `126`，拒绝 `3` |
| B 类追问质量 | `{'acceptable': 40}` |
| A 精确断言 Batch1 | `25/25` |
| 全量问题回归 | `129/129` |
| 多问法语义回归 | 原题 `129/129`，变体 `258/258` |
| 答案表达层回归 | `129/129` |
| 答案表达层 live | `30/30`，LLM 采纳 `7`，fallback `23` |
| 重点 10 样例 | `10/10` |
| 前端 build | 通过，仅 Vite chunk size warning |
| BOM 单元测试 | `28/28` |
| 物流 NLU | `122/122` |
| 物流 903 语义回归 | `1559/1559` |
| 物流 Guardrail 补验证 | `10/10`，B/C 误判 success `0/0` |

## 风险边界

- LLM 只做理解候选和表达优化。
- 事实性结果来自标准化 BOM 数据。
- B/C 继续保留追问或拒答，不硬迁 A。
- 非核心材料当前不进入核心五类查询 schema。

## 报告文件

- JSON：`tmp/plan_bom/plan_bom_acceptance_report.json`
